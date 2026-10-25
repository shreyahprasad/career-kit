"""An LLM judge reads a finished run's chat and drafts against its rubric.

    python judge.py <run> <out>

Writes <out>/<run>/judge.md: PASS or FAIL per rubric item with evidence, then "Overall: PASS" or
"Overall: FAIL". The rubric is rubrics/<run>.md; the style run has none (its checks are scripted).
"""

import subprocess
import sys
from pathlib import Path

from common import FIXTURES, OWNER, RUBRICS

INPUTS = [OWNER / "resumes/master.md", OWNER / "examples/resumes/everything.md", OWNER / "profile.md"]


def main() -> None:
    name, out = sys.argv[1], Path(sys.argv[2])
    d = out / name
    parts = []
    for t in sorted((d / "turns").glob("[0-9][0-9].txt")):
        parts.append(f"=== Turn {t.stem}\n{t.read_text()}")
        parts.append(f"--- drafts after turn {t.stem}\n{(d / 'turns' / (t.stem + '.drafts.txt')).read_text()}")
    inputs = "\n".join(f"--- {p.relative_to(FIXTURES)}\n{p.read_text()}" for p in [*INPUTS, FIXTURES / "posting.txt"])
    prompt = (
        "You judge a run of a resume tailoring skill on made-up data (Arya Stark). The owner turns are scripted. "
        "For each rubric item give PASS or FAIL and one or two sentences of evidence, quoting the transcript or "
        "drafts. Be strict: a FAIL needs a concrete example. End with a line 'Overall: PASS' or 'Overall: FAIL'.\n\n"
        f"Rubric:\n{(RUBRICS / f'{name}.md').read_text()}\n\nInputs:\n{inputs}\n\n" + "\n".join(parts)
    )
    # An empty folder and no tools: the judge sees only the prompt.
    empty = out / ".judge"
    empty.mkdir(exist_ok=True)
    done = subprocess.run(
        ["claude", "-p", prompt, "--setting-sources", "local", "--tools", ""],
        cwd=empty, capture_output=True, text=True, timeout=900,
    )  # fmt: skip
    (d / "judge.md").write_text(done.stdout)
    print(done.stdout)


if __name__ == "__main__":
    main()
