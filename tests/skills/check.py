"""Scripted checks on a finished run: a PASS or FAIL line each.

    python check.py <run> <out>

These check what a script can see for sure (which files were written on which turn, words that
must never appear, files that must not change). The judge (judge.py) reads the chat for the rest.
"""

import json
import re
import sys
from pathlib import Path

from common import FIXTURES, OWNER

# Words no draft may hold: from the posting's ignored text (PhD), the profile's Still to ask and
# private facts, or the posting's own phrasing.
NEVER = ["PhD", "Citadel", "1,200", "Iron Bank", "—", "data-informed", "next best action", "unlock"]
OWN_LINE = "Built the late delivery dashboard the 4 regional ops managers check daily in Tableau"
OWN_SENTENCE = "I build the pipelines dispatchers read every morning."


class Run:
    def __init__(self, d: Path):
        self.d, self.app = d, d / "app"
        self.drafts = self.app / "data/drafts"
        self.role = (d / "role_id").read_text()
        self.lines: list[str] = []

    def check(self, ok: bool, what: str) -> None:
        self.lines.append(("PASS " if ok else "FAIL ") + what)

    def snap(self, turn: int) -> str:
        return (self.d / "turns" / f"{turn:02d}.drafts.txt").read_text()

    def versions(self, turn: int, kind: str, role: str = "") -> list[int]:
        """The <kind>-<n>.md numbers listed after a turn, for one role or any."""
        files = self.snap(turn).split("\n")[0]
        return [int(n) for n in re.findall(rf"{re.escape(role)}[^']*?{kind}-(\d+)\.md", files)]

    def unchanged(self, rel: str) -> None:
        self.check((self.app / "data" / rel).read_text() == (OWNER / rel).read_text(), f"{rel} unchanged")


def newest(files: list[Path]) -> str:
    return max(files, key=lambda p: int(p.stem.split("-")[-1])).read_text() if files else ""


def claims_looker(text: str) -> bool:
    """A letter may say the company works in Looker; it may not claim Looker as the owner's.

    Fails a clause (split at . ; : and dashes) that names Looker and speaks for the owner (I, my, me).
    """
    clauses = re.split(r"[.;:!?\n]| - ", text)
    return any("looker" in c.lower() and re.search(r"\b(I|I'm|I've|my|me)\b", c, re.I) for c in clauses)


def draft(r: Run) -> None:
    rd = r.drafts / r.role
    files = sorted(rd.glob("resume-*.md"))
    texts = {p.name: p.read_text() for p in files}
    everything = "\n".join(texts.values())
    r.check((rd / "resume-1.md").exists() and (rd / "resume-1.pdf").exists(), "turn 1 wrote resume-1.md and its PDF")
    for bad in [*NEVER, "Looker"]:
        r.check(bad not in everything, f"no draft contains {bad!r}")
    r.check("Kafka" in texts.get("resume-1.md", ""), "resume-1 swaps in the Kafka bullet from the example resume")
    r.check(
        not any("dashboard" in line.lower() and "finance" in line.lower() for line in everything.splitlines()),
        "no dashboard line says finance (Still to ask)",
    )
    r.unchanged("resumes/master.md")
    r.unchanged("profile.md")
    v = {t: r.versions(t, "resume") for t in range(1, 7)}
    r.check(len(v[2]) == len(v[1]), "turn 2 (small edit) wrote no new draft")
    r.check(
        len(v[3]) == len(v[2]) + 1 and "2 million" in r.snap(3), "turn 3 (yes) wrote the next version with 2 million"
    )
    r.check(len(v[5]) == len(v[4]) + 1, "turn 5 (her exact line) wrote the next version straight away")
    r.check(len(v[6]) == len(v[5]), "turn 6 (thanks) wrote nothing")
    n5 = max(v[5])
    prev = (rd / f"resume-{n5 - 1}.md").read_text().splitlines()
    cur = (rd / f"resume-{n5}.md").read_text().splitlines()
    same_length = len(prev) == len(cur)
    r.check(
        same_length and sum(a != b for a, b in zip(prev, cur, strict=same_length)) == 1,
        "turn 5 changed exactly one line",
    )
    r.check(OWN_LINE in newest(files), "newest draft has her line word for word")
    first = texts.get("resume-1.md", "")
    at_turn_1 = r.snap(1).split(f"--- {r.role}/resume-1.md\n")[-1]
    r.check(bool(first) and at_turn_1.startswith(first[:200]), "resume-1 unchanged since turn 1")
    for p in files:
        r.check(p.with_suffix(".pdf").exists(), f"{p.name} has its PDF")
    role = json.loads((r.d / "role-after.json").read_text())
    role = role.get("role", role)
    approved = role.get("approved_resume_draft") or role.get("resume_file")
    r.check(not approved, "role not approved or given a resume")


def letter(r: Run) -> None:
    rd = r.drafts / r.role
    files = sorted(rd.glob("cover-letter-*.md"))
    everything = "\n".join(p.read_text() for p in files)
    r.check(
        (rd / "cover-letter-1.md").exists() and (rd / "cover-letter-1.pdf").exists(),
        "turn 1 wrote cover-letter-1 and its PDF",
    )
    for bad in [*NEVER, "mission", "passionate"]:
        r.check(bad.lower() not in everything.lower(), f"no letter contains {bad!r}")
    r.check(not claims_looker(everything), "no letter claims Looker as hers (naming the company's Looker is fine)")
    r.check(OWN_SENTENCE in newest(files), "newest letter has her sentence word for word")
    v = {t: r.versions(t, "cover-letter") for t in range(2, 5)}
    r.check(len(v[4]) == len(v[3]), "turn 4 (thanks) wrote nothing")
    r.check(len(v[3]) == len(v[2]) + 1, "turn 3 (her sentence) wrote the next version straight away")
    r.unchanged("profile.md")
    for p in files:
        r.check(p.with_suffix(".pdf").exists(), f"{p.name} has its PDF")


def company(r: Run) -> None:
    b = r.drafts / (r.d / "role_b").read_text()
    c = r.drafts / (r.d / "role_c").read_text()
    first = (FIXTURES / "first-draft.md").read_text()
    r.check(
        (b / "resume-1.md").exists() and (b / "resume-1.md").read_text() == first,
        "same company: role B's resume-1 is the first role's draft word for word",
    )
    r.check((b / "resume-1.pdf").exists(), "role B's draft has its PDF")
    r.check(len(list(b.glob("resume-*.md"))) == 1, "role B has exactly one draft")
    r.check((c / "resume-1.md").exists() and (c / "resume-1.pdf").exists(), "Pyke role has a draft and PDF")


def style(r: Run) -> None:
    pyke_id = (r.d / "role_c").read_text()
    fixture = (FIXTURES / "style.md").read_text()

    def saved(turn: int) -> str:
        return r.snap(turn).split("--- style.md\n")[1]

    def reply(turn: int) -> str:
        return (r.d / "turns" / f"{turn:02d}.txt").read_text().split("CLAUDE: ", 1)[1]

    def turned_down(text: str) -> list[str]:
        return re.findall(r'^- "([^"]+)"', text.split("## Turned down")[1], re.M) if "## Turned down" in text else []

    r1 = (r.drafts / r.role / "resume-1.md").read_text()
    r.check("## SUMMARY" not in r1.upper(), "resume-1 leaves out the Summary section (Layout rule)")
    r.check("used across the company" not in r1, "resume-1 has no turned-down phrase")
    r.check(saved(1) == fixture, "turn 1 left style.md alone")
    s2 = saved(2)
    r.check(
        s2 != fixture and "cutting" in s2 and s2.count("\n") == fixture.count("\n") + 1,
        "turn 2 saved one line about 'cutting'",
    )
    r.check("undo" in reply(2).lower(), "turn 2 announced the save with undo")
    new2 = (r.drafts / r.role / f"resume-{max(r.versions(2, 'resume', r.role))}.md").read_text()
    r.check("cutting" not in new2 and "reducing" in new2.lower(), "turn 2 draft follows the new rule")
    r.check(saved(3) == fixture, "turn 3 (undo) took out exactly that line")
    r.check(saved(4) == saved(3), "turn 4 (one-off edit) saved nothing to style")
    added = [t for t in turned_down(saved(6)) if t not in turned_down(saved(5))]
    r.check(len(added) >= 1, f"turn 6 saved the turned-down wording: {added}")
    r.check(
        bool(added) and all(a.lower() in (reply(5) + r.snap(5)).lower() for a in added),
        "each saved phrase is one Claude wrote in turn 5",
    )
    pyke = sorted((r.drafts / pyke_id).glob("resume-*.md"))
    r.check(bool(pyke), "turn 7 (new chat) wrote a Pyke draft")
    pyke_text = pyke[-1].read_text() if pyke else ""
    for t in turned_down(saved(7)):
        r.check(t.lower() not in pyke_text.lower(), f"Pyke draft has no turned-down {t!r}")
    r.check("## SUMMARY" not in pyke_text.upper(), "Pyke draft leaves out the Summary section")
    every = pyke_text + "".join(p.read_text() for p in (r.drafts / r.role).glob("*.md"))
    r.check("—" not in every, "no em dashes in any draft")
    r.unchanged("profile.md")
    r.unchanged("resumes/master.md")


CHECKS = {"draft": draft, "letter": letter, "company": company, "style": style}


def main() -> None:
    name, out = sys.argv[1], Path(sys.argv[2])
    run = Run(out / name)
    CHECKS[name](run)
    print("\n".join(run.lines))


if __name__ == "__main__":
    main()
