"""One scripted conversation with the drafting skills, on Arya Stark data in a scratch copy.

    python run.py <run> <out> [checkout]

<run> is draft, letter, company or style. Copies the checkout's tracked files (no data, default
this repo) to <out>/<run>/app, adds the fixture owner's files, sets up and starts the copy on the
scratch ports, adds the Dragonstone role with its posting through the writer, then talks to the
skills with claude -p, one scripted owner turn at a time. Claude runs with the shipped
.claude/settings.json only, in default permission mode, so anything it does not allow is refused
as it would be for an owner who taps "no". After each turn: the transcript, and a listing of
data/drafts with each draft's text and data/style.md. Stops the copy at the end, always.
"""

import json
import shutil
import subprocess
import sys
import urllib.request
import uuid
from pathlib import Path

from common import FIXTURES, OWNER, PORTS, REPO

DRAGONSTONE = {"company": "Dragonstone Freight", "title": "Senior Analytics Engineer"}
DRAGONSTONE_DE = {
    "company": "Dragonstone Freight",
    "title": "Data Engineer",
    "posting": "Dragonstone Freight is hiring a Data Engineer. Airflow, dbt, Snowflake, Python. "
    "Build batch pipelines for dispatch.",
}
PYKE = {
    "company": "Pyke Shipping",
    "title": "Analytics Engineer",
    "posting": "Pyke Shipping is hiring an Analytics Engineer. dbt, Snowflake, SQL, "
    "Tableau dashboards for the ops team.",
}

# The owner's turns. "NEW:" starts a new chat.
SCRIPTS = {
    "company": [
        "tailor my resume for the Dragonstone Data Engineer role",
        "now tailor my resume for the Pyke Shipping role",
    ],
    "letter": [
        "write a cover letter for the Dragonstone role",
        "too vague",
        "use this exactly for the first sentence: I build the pipelines dispatchers read every morning.",
        "thanks, that's all for now",
    ],
    "style": [
        "tailor my resume for the Dragonstone role",
        "no todo thanks. never use the word 'cutting' on any resume, say 'reducing' instead",
        "undo",
        "change 'Rebuilt' to 'Rewrote' in the pipeline bullet",
        "the route planning bullet is too vague",
        "no, I don't like the wording you added to the route planning bullet in that last version, never use any of it",
        "NEW:tailor my resume for the Pyke Shipping role",
    ],
    "draft": [
        "tailor my resume for the Dragonstone role",
        "no todo thanks. change the shipment pipeline bullet so it also says it loads about 2 million rows a night",
        "yes",
        "the dashboard bullet is too vague",
        "use this exactly for the dashboard bullet: "
        "Built the late delivery dashboard the 4 regional ops managers check daily in Tableau",
        "thanks, that's all for now",
    ],
}


def copy_app(checkout: Path, app: Path) -> None:
    files = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard"], cwd=checkout, capture_output=True, text=True, check=True
    ).stdout.split("\n")
    for f in filter(None, files):
        if f.startswith(("data/", "tests/skills/results/")) or not (checkout / f).is_file():
            continue
        (app / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(checkout / f, app / f)


def sh(app: Path, script: str) -> None:
    done = subprocess.run(["bash", f"./{script}"], cwd=app, capture_output=True, text=True, timeout=900)
    if done.returncode:
        raise SystemExit(f"{script} failed:\n{done.stdout[-2000:]}\n{done.stderr[-2000:]}")


def add_role(role: dict) -> str:
    body = {"posting": (FIXTURES / "posting.txt").read_text(), **role}
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORTS['CAREER_PORT']}/api/career/write/roles",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "X-Career-Kit-Write": "1"},
        method="POST",
    )
    with urllib.request.urlopen(req) as answer:
        return json.load(answer)["role_id"]


def snapshot(app: Path, stem: Path) -> None:
    root = app / "data/drafts"
    drafts = sorted(root.rglob("*")) if root.exists() else []
    parts = [f"files: {[str(p.relative_to(root)) for p in drafts if p.is_file()]}"]
    parts += [f"--- {p.relative_to(root)}\n{p.read_text()}" for p in drafts if p.suffix == ".md"]
    style = app / "data/style.md"
    parts.append("--- style.md\n" + (style.read_text() if style.exists() else "(none)"))
    stem.with_suffix(".drafts.txt").write_text("\n".join(parts))


def say(app: Path, turns: Path, n: int, message: str, session: str, fresh: bool) -> None:
    # --settings because claude -p ignores a project's allow rules in a folder it has not been
    # trusted in; "local" keeps the runner's own user settings out.
    done = subprocess.run(
        [
            "claude", "-p", message, *(["--session-id", session] if fresh else ["--resume", session]),
            "--output-format", "stream-json", "--verbose",
            "--setting-sources", "local", "--settings", str(app / ".claude/settings.json"),
        ],
        cwd=app, capture_output=True, text=True, timeout=1200,
    )  # fmt: skip
    stem = turns / f"{n:02d}"
    stem.with_suffix(".jsonl").write_text(done.stdout)
    reply, denied = "", []
    for line in done.stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "result":
            reply, denied = event.get("result") or "", event.get("permission_denials") or []
    refused = "".join(f"\n(refused: {d.get('tool_name')} {json.dumps(d.get('tool_input'))[:200]})" for d in denied)
    stem.with_suffix(".txt").write_text(f"OWNER: {message}\n\nCLAUDE: {reply}\n{refused}")
    snapshot(app, stem)
    print(f"[{n:02d}] OWNER: {message[:100]}\n  CLAUDE: {reply[:400]}{refused}\n", flush=True)


def main() -> None:
    name, out = sys.argv[1], Path(sys.argv[2]).resolve()
    checkout = Path(sys.argv[3]).resolve() if len(sys.argv) > 3 else REPO
    d = out / name
    shutil.rmtree(d, ignore_errors=True)
    app, turns = d / "app", d / "turns"
    turns.mkdir(parents=True)
    copy_app(checkout, app)
    shutil.copytree(OWNER, app / "data")
    (app / ".env").write_text("".join(f"{k}={v}\n" for k, v in PORTS.items()))
    sh(app, "setup.sh")
    sh(app, "start.sh")
    try:
        role_id = add_role(DRAGONSTONE)
        (d / "role_id").write_text(role_id)
        if name == "company":
            first = app / "data/drafts" / role_id
            first.mkdir(parents=True)
            shutil.copy2(FIXTURES / "first-draft.md", first / "resume-1.md")
            (d / "role_b").write_text(add_role(DRAGONSTONE_DE))
        if name == "style":
            shutil.copy2(FIXTURES / "style.md", app / "data/style.md")
        if name in ("company", "style"):
            (d / "role_c").write_text(add_role(PYKE))
        session, first_turn = str(uuid.uuid4()), 1
        for n, message in enumerate(SCRIPTS[name], 1):
            if message.startswith("NEW:"):
                session, first_turn, message = str(uuid.uuid4()), n, message.removeprefix("NEW:")
            say(app, turns, n, message, session, n == first_turn)
        with urllib.request.urlopen(f"http://127.0.0.1:{PORTS['API_PORT']}/api/career/roles/{role_id}") as answer:
            (d / "role-after.json").write_text(answer.read().decode())
    finally:
        subprocess.run(["bash", "./stop.sh"], cwd=app, capture_output=True, timeout=120)


if __name__ == "__main__":
    main()
