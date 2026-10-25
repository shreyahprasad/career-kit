# Skill tests

The drafting skills (`tailor-resume`, `write-cover-letter`) are prompts, so a unit test cannot
check them. These tests run them for real: a scripted owner talks to Claude, one turn at a time,
on made-up data (Arya Stark), and the result is checked two ways.

**They make real Claude calls on your plan, and a full round takes about an hour.** Run them by
hand after changing a skill. They never run in CI.

## Running

From the repo root, with `claude` signed in and ports 9100, 9120, 9140 and 6180 free:

```
bash tests/skills/round.sh
```

That runs all four conversations one after another, then the judges, and prints a summary.
Results go to `tests/skills/results/<UTC time>/` (gitignored). To run one conversation:

```
cd tests/skills
uv run --no-project --python 3.14 python run.py draft results/try
uv run --no-project --python 3.14 python check.py draft results/try
uv run --no-project --python 3.14 python judge.py draft results/try
```

Each run copies this checkout's tracked files (no `data/`) to `<out>/<run>/app`, adds the files in
`fixtures/owner/` as its `data/`, and starts that copy on the scratch ports (move them with
`SKILLS_API_PORT`, `SKILLS_CAREER_PORT`, `SKILLS_NETWORKING_PORT`, `SKILLS_WEB_PORT`). It stops the
copy at the end, even when a turn fails. Your own data and your running career-kit are never
touched.

Claude runs with the shipped `.claude/settings.json` only, in the default permission mode, so a
command those settings do not allow is refused, the way it would be for an owner who taps "no".
Each refusal is written under the turn's reply.

## The four conversations

| Run | What the owner says | What it tests |
|---|---|---|
| `draft` | tailor, a small edit, "yes", "too vague", their own line, "thanks" | the first draft, edits shown before they are written, their words kept exactly |
| `letter` | write a letter, "too vague", their own first sentence, "thanks" | the letter's voice, sources, and the same edit rules |
| `company` | a second role at the same company, then a role at another company | a shared resume for one company, starting from the closest draft |
| `style` | a rule ("never 'cutting'"), undo, a one-off edit, a turned-down phrase, a new chat | what is saved to `style.md`, and that a new chat follows it |

The scripts are in `run.py` (`SCRIPTS`), and the posting and owner files in `fixtures/`.

## Reading the results

- `<run>.check.txt`: scripted checks (`check.py`), one `PASS` or `FAIL` line each. These are
  things a script can know for sure: which file a turn wrote, words that must never appear (the
  posting's PhD note, private facts, the posting's own phrasing), files that must not change.
  A `FAIL` here is a real regression.
- `<run>/judge.md`: an LLM judge reads the whole chat and the drafts against `rubrics/<run>.md`
  and gives `PASS` or `FAIL` per item with a quote, then `Overall:`. The judge is strict and
  sometimes wrong. On a `FAIL`, read its quote in `<run>/turns/` before changing a skill: if the
  quote does not show the problem, it is the judge's mistake.
- `<run>/turns/`: each turn's chat (`NN.txt`), the full event stream (`NN.jsonl`), and every draft
  and `style.md` after that turn (`NN.drafts.txt`).

A run's results vary from round to round. Judge a change by the checks and the judge's quotes,
not by rerunning until it passes.
