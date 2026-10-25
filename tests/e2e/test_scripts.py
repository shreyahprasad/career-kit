"""setup.sh, start.sh and stop.sh on the copy. These run after every page test (conftest.py), and
leave the servers running as they found them."""

import hashlib
import http.server
import os
import plistlib
import socket
import subprocess
import threading
import uuid

import pytest

from conftest import PORTS, answers, eventually


def fingerprint(app) -> dict[str, str]:
    return {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(app.data.glob("*.db*"))}


@pytest.fixture
def stopped(app):
    """The servers stopped for the test, and started again after it."""
    app.run("stop.sh")
    yield app
    app.run("start.sh")


def test_setup_again_leaves_the_databases_and_settings_alone(app):
    before, env = fingerprint(app), (app.root / ".env").read_text()
    app.run("setup.sh")
    assert fingerprint(app) == before
    assert (app.root / ".env").read_text() == env


def test_the_data_and_settings_are_for_this_user_only(app):
    modes = {
        name: (app.root / name).stat().st_mode & 0o777
        for name in ("data", "data/run", ".env", "data/career.db", "data/networking.db")
    }
    assert modes == {
        "data": 0o700,
        "data/run": 0o700,
        ".env": 0o600,
        "data/career.db": 0o600,
        "data/networking.db": 0o600,
    }


def test_start_again_leaves_what_is_running_alone(app):
    done = app.run("start.sh")
    for name in ("career", "networking", "api", "web"):
        assert f"{name} already running" in done.stdout


def test_stop_stops_everything_and_says_so(stopped):
    assert not any(answers(port) for port in PORTS.values())
    assert stopped.run("stop.sh").stdout.strip() == "Nothing was running."
    assert list((stopped.data / "run").glob("*.pid")) == []


def test_start_moves_a_log_over_5_mb_aside_and_keeps_one_old_copy(stopped):
    run = stopped.data / "run"
    (run / "api.log.1").write_text("the oldest log\n")
    (run / "api.log").write_bytes(b"x" * (5 * 1024 * 1024 + 1))
    (run / "career.log").write_text("a small log\n")
    stopped.run("start.sh")
    assert (run / "api.log.1").stat().st_size == 5 * 1024 * 1024 + 1
    assert (run / "api.log").stat().st_size < 5 * 1024 * 1024
    assert (run / "career.log").read_text().startswith("a small log\n")


def test_start_refuses_a_port_something_else_has(stopped):
    other = http.server.HTTPServer(("127.0.0.1", PORTS["CAREER_PORT"]), http.server.SimpleHTTPRequestHandler)
    threading.Thread(target=other.serve_forever, daemon=True).start()
    try:
        done = stopped.run("start.sh", check=False)
    finally:
        other.shutdown()
        other.server_close()
    assert done.returncode == 1
    assert f"something else is using :{PORTS['CAREER_PORT']}" in done.stderr
    assert list((stopped.data / "run").glob("*.pid")) == []  # nothing of its own started


def test_start_refuses_a_port_in_env_that_is_not_a_number(stopped):
    env = stopped.root / ".env"
    good = env.read_text()
    env.write_text(good.replace(f"CAREER_PORT={PORTS['CAREER_PORT']}", "CAREER_PORT=abc"))
    try:
        done = stopped.run("start.sh", check=False)
    finally:
        env.write_text(good)
    assert done.returncode == 1
    assert 'CAREER_PORT must be a port number, not "abc"' in done.stderr


@pytest.fixture
def stranger():
    """Another program of yours, whose pid an old pid file now names (as after a restart)."""
    process = subprocess.Popen(["sleep", "120"])
    yield process
    process.kill()
    process.wait()


@pytest.mark.parametrize("pid_file", ["{pid}\n", "{pid} Mon Jan  1 00:00:00 2024\n"])
def test_stop_never_stops_another_program_an_old_pid_file_names(stopped, stranger, pid_file):
    (stopped.data / "run/career.pid").write_text(pid_file.format(pid=stranger.pid))
    stopped.run("stop.sh")
    assert stranger.poll() is None  # still running
    assert not (stopped.data / "run/career.pid").exists()


def test_start_does_not_take_another_program_for_a_server(stopped, stranger):
    (stopped.data / "run/career.pid").write_text(f"{stranger.pid}\n")
    done = stopped.run("start.sh")
    assert f"career on :{PORTS['CAREER_PORT']}" in done.stdout
    assert answers(PORTS["CAREER_PORT"]) and stranger.poll() is None


def test_start_gives_up_on_a_port_that_takes_the_call_and_never_answers(stopped):
    with socket.socket() as silent:
        silent.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # the writer just let it go
        silent.bind(("127.0.0.1", PORTS["CAREER_PORT"]))
        silent.listen()
        done = stopped.run("start.sh", check=False, timeout=60)
    assert done.returncode == 1
    assert f"something else is using :{PORTS['CAREER_PORT']}" in done.stderr


def launchagent(app, action: str, agents, label: str) -> subprocess.CompletedProcess:
    """scripts/launchagent.sh on the copy, with a label and folder of the test's own, so the
    owner's own LaunchAgents are never touched."""
    env = {k: v for k, v in os.environ.items() if k not in PORTS}
    env |= {"CAREER_KIT_LABEL": label, "CAREER_KIT_LAUNCH_AGENTS": str(agents)}
    return subprocess.run(
        ["bash", "scripts/launchagent.sh", action], cwd=app.root, env=env, capture_output=True, text=True, timeout=60
    )


def loaded(label: str) -> bool:
    return subprocess.run(["launchctl", "print", f"gui/{os.getuid()}/{label}"], capture_output=True).returncode == 0


@pytest.fixture
def label():
    name = f"com.career-kit.e2e-{uuid.uuid4().hex[:8]}"
    yield name
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{name}"], capture_output=True)


def test_the_launch_agent_runs_start_at_login_and_is_removed_cleanly(app, tmp_path, label):
    done = launchagent(app, "install", tmp_path, label)
    assert done.returncode == 0, done.stderr
    plist = tmp_path / f"{label}.plist"
    assert subprocess.run(["plutil", "-lint", plist], capture_output=True).returncode == 0
    settings = plistlib.loads(plist.read_bytes())
    assert settings["ProgramArguments"] == ["/bin/bash", str(app.root / "start.sh")]
    assert settings["RunAtLoad"] is True and loaded(label)
    log = app.data / "run/launchagent.log"
    eventually(lambda: log.exists() and "api already running" in log.read_text(), seconds=30)
    done = launchagent(app, "remove", tmp_path, label)
    assert done.returncode == 0 and not plist.exists() and not loaded(label)
    assert answers(PORTS["API_PORT"])  # removing it leaves the servers running


def test_the_launch_agent_is_refused_while_another_app_hosts_career_kit(stopped, tmp_path, label):
    class Hosted(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = b'{"ok":true,"app":"dashboard","serves":["career-kit"]}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    host = http.server.HTTPServer(("127.0.0.1", PORTS["API_PORT"]), Hosted)
    threading.Thread(target=host.serve_forever, daemon=True).start()
    try:
        done = launchagent(stopped, "install", tmp_path, label)
    finally:
        host.shutdown()
        host.server_close()
    assert done.returncode == 1
    assert f"another app hosts career-kit on :{PORTS['API_PORT']}" in done.stderr
    assert not (tmp_path / f"{label}.plist").exists() and not loaded(label)
