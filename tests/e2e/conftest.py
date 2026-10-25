"""
End-to-end tests: the real page and servers in a real browser, on a copy of this checkout.

    cd tests/e2e && uv run pytest

The copy is the checkout's files as git sees them (uncommitted changes in, data/ and .env out),
in a temp folder. setup.sh installs it and makes empty databases, its .env gets the scratch ports
below, and start.sh starts it; stop.sh always runs at the end. Nothing here touches your own
data/, your .env, or the ports your career-kit runs on. Made-up data only: the person searching
is Arya Stark.

Each test makes its own roles and people (unique names), so tests do not depend on each other.
A test checks the page, then what was saved, through the read API and the files in data/.
Any console error, page error or answer of 400 or more fails the test, unless it says it expects
that refusal (watch.allow).
"""

import json
import os
import re
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

CHECKOUT = Path(__file__).resolve().parents[2]
PORTS = {"API_PORT": 9100, "NETWORKING_PORT": 9120, "CAREER_PORT": 9140, "WEB_PORT": 6180}
LIVE = range(8100, 8141)  # where the owner's own career-kit runs: never
VIEWPORTS = {"desktop": {"width": 1280, "height": 900}, "phone": {"width": 390, "height": 844}}


def answers(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def unique(name: str) -> str:
    """name with a short tag, so every test's roles and people are its own."""
    return f"{name} {uuid.uuid4().hex[:6]}"


def eventually(check, seconds: float = 5):
    """Waits for check() to be true, for what the page shows before its save comes back (a ticked
    todo). Returns what check returned."""
    end = time.monotonic() + seconds
    while not (result := check()):
        if time.monotonic() > end:
            raise AssertionError(f"still not so after {seconds} s")
        time.sleep(0.1)
    return result


class App:
    """The copy: its folder, its scripts, and its servers over HTTP."""

    def __init__(self, root: Path):
        self.root = root
        self.data = root / "data"
        self.web = f"http://127.0.0.1:{PORTS['WEB_PORT']}"

    def run(self, script: str, check: bool = True, timeout: float = 600) -> subprocess.CompletedProcess:
        """./script in the copy, with the ports only from its .env."""
        env = {k: v for k, v in os.environ.items() if k not in PORTS}
        done = subprocess.run(
            ["bash", f"./{script}"], cwd=self.root, env=env, capture_output=True, text=True, timeout=timeout
        )
        if check and done.returncode != 0:
            raise AssertionError(f"{script} failed:\n{done.stdout}\n{done.stderr}")
        return done

    def read(self, path: str):
        with urllib.request.urlopen(f"http://127.0.0.1:{PORTS['API_PORT']}{path}") as answer:
            return json.load(answer)

    def write(self, method: str, path: str, body: dict | None = None) -> dict:
        """A change straight to its writer, as Claude makes one: path starts /api/career/write or
        /api/networking/write."""
        port = PORTS["CAREER_PORT"] if path.startswith("/api/career/") else PORTS["NETWORKING_PORT"]
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json", "X-Career-Kit-Write": "1"}
        request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data, headers, method=method)
        try:
            with urllib.request.urlopen(request) as answer:
                return json.load(answer)
        except urllib.error.HTTPError as e:
            raise AssertionError(f"{method} {path}: {e.code} {e.read().decode()}") from None

    def add_role(self, company: str, title: str, **fields) -> str:
        return self.write("POST", "/api/career/write/roles", {"company": company, "title": title, **fields})["role_id"]

    def role(self, role_id: str) -> dict:
        return self.read(f"/api/career/roles/{role_id}")

    def add_person(self, name: str, **fields) -> str:
        return self.write("POST", "/api/networking/write/people", {"name": name, **fields})["person_id"]


def copy_checkout(to: Path) -> None:
    listed = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=CHECKOUT, capture_output=True, check=True
    )
    for name in filter(None, listed.stdout.decode().split("\0")):
        source = CHECKOUT / name
        if source.exists() or source.is_symlink():  # a file deleted but not yet committed is listed too
            (to / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, to / name, follow_symlinks=False)


def set_ports(env_file: Path) -> None:
    text = env_file.read_text()
    for name, port in PORTS.items():
        text, found = re.subn(rf"^{name}=.*$", f"{name}={port}", text, flags=re.M)
        assert found == 1, f"{name} is not in .env.example"
    env_file.write_text(text)


@pytest.fixture(scope="session")
def app(tmp_path_factory):
    for port in PORTS.values():
        assert port not in LIVE, f":{port} is where your own career-kit runs"
        if answers(port):
            pytest.exit(
                f"Something is already on :{port}. Stop it first: these tests never share a port.", returncode=1
            )
    root = tmp_path_factory.mktemp("career-kit")
    copy_checkout(root)
    copy = App(root)
    try:
        copy.run("setup.sh")
        set_ports(root / ".env")
        copy.run("start.sh")
        yield copy
    finally:
        copy.run("stop.sh", check=False)
        still = [port for port in PORTS.values() if answers(port)]
        assert not still, f"still answering after stop.sh: {still}"


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        chromium = p.chromium.launch()
        yield chromium
        chromium.close()


class Watch:
    """What went wrong on the page: console errors, page errors, answers of 400 or more."""

    def __init__(self):
        self.problems: list[str] = []
        self.allowed: set[int] = set()

    def allow(self, status: int) -> None:
        """A refusal the test sets out to see."""
        self.allowed.add(status)

    def console(self, message) -> None:
        if message.type == "error" and not any(f"status of {s}" in message.text for s in self.allowed):
            self.problems.append(f"console: {message.text}")

    def answer(self, response) -> None:
        if response.status >= 400 and response.status not in self.allowed:
            self.problems.append(f"{response.status} {response.request.method} {response.url}")


@pytest.fixture
def watch() -> Watch:
    return Watch()


@pytest.fixture
def page(request, app, browser, watch):
    """A fresh page on the copy, on the Mac's width unless the test asks for the phone's too."""
    context = browser.new_context(
        viewport=VIEWPORTS[getattr(request, "param", "desktop")],
        base_url=app.web,
        permissions=["clipboard-read", "clipboard-write"],
    )
    # index.html names no icon, and the browser asks for one anyway.
    context.route("**/favicon.ico", lambda route: route.fulfill(status=204, body=""))
    tab = context.new_page()
    tab.on("console", watch.console)
    tab.on("pageerror", lambda e: watch.problems.append(f"page error: {e}"))
    tab.on("response", watch.answer)
    yield tab
    context.close()
    assert not watch.problems, "\n".join(watch.problems)


def pytest_generate_tests(metafunc):
    if metafunc.definition.get_closest_marker("phone_too"):
        metafunc.parametrize("page", list(VIEWPORTS), indirect=True)


def pytest_collection_modifyitems(items):
    """The script tests stop and start the servers, so they run after every page test."""
    items.sort(key=lambda item: item.path.name == "test_scripts.py")
