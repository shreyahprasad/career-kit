# career-kit

One person's job search tracker, run on this Mac: the roles they are looking at, each role's
status, timeline and todos, their resumes, and the people helping them. They mostly talk to you
from their phone through Remote Control; the web page is there when they want to see the board.

## The data

- Two SQLite databases in `data/`: `career.db` (roles, events, todos) and `networking.db` (people
  and every talk). They are the only copy of this person's search. `data/` is gitignored and
  never leaves this Mac.
- **Never open them with sqlite3 or edit them by hand, not even to read.** Every read goes through
  the read API and every change through a writer, over HTTP on 127.0.0.1. The writer checks the
  change, backs the database up first, and refuses anything unclear with a reason to pass on.

## Starting it

- `./start.sh` starts everything; `./stop.sh` stops it. If `./start.sh` says there are no
  databases, run `./setup.sh` first (safe to run again).
- **Ports first.** The ports below are the defaults; `.env` can move any of them (`API_PORT`,
  `CAREER_PORT`, `NETWORKING_PORT`, `WEB_PORT`). Once a session, before any other command, run
  `grep _PORT .env` on its own and read the answer; any set there replace the ports in this
  file and the skills.
- It is up when `curl -s http://127.0.0.1:8100/api/health` answers
  `{"ok":true,"app":"career-kit"}`. If it does not answer, run `./start.sh` before anything else.
  Logs are in `data/run/`.
- **Hosted by another app.** An app that runs career-kit's read API and writers for the owner,
  on the same ports, answers `"ok":true` with `"serves"` listing `"career-kit"` (like
  `{"ok":true,"app":"dashboard","serves":["career-kit"]}`). Then it is up too: use it exactly as
  above. Never run `./start.sh` or `./setup.sh` while it answers that way, and if it stops
  answering, tell the owner their app is down rather than starting career-kit's own.
- Anything else on that port is another program: do not read from it or write to it.
- The page is at http://127.0.0.1:5180 on this Mac.

## Reading

`GET http://127.0.0.1:8100` plus:

| Route | What |
|---|---|
| `/api/career/roles` | every role, with status, applied day, last event, todos done of total, and the next todo |
| `/api/career/roles/{id}` | one role: details, notes, posting, timeline, todos, referral |
| `/api/career/todos` | every open todo, for a role or for the search as a whole |
| `/api/career/deleted` | what was deleted, to bring back |
| `/api/career/resumes` | the PDFs in `data/resumes` |
| `/api/career/roles/{id}/drafts` | a role's resume and cover letter drafts |
| `/api/networking/people` | everyone, with company, tags, the day and kind of each talk, and the next step |
| `/api/networking/people/{id}` | one person and every talk with them |

## Changing

`POST`, `PATCH` or `DELETE` with JSON and the header `X-Career-Kit-Write: 1`:

- Career: `http://127.0.0.1:8140/api/career/write/...`
- Networking: `http://127.0.0.1:8120/api/networking/write/...`

The routes are listed in the docstring at the top of `tools/career/writer.py` and
`tools/networking/writer.py`, and the fields each body takes are in `tools/career/fields.json`
and `tools/networking/fields.json`. Read them there rather than guessing; an unknown field is
refused. An edit should send the `version` from the row you read, so a change made meanwhile on
the page is not written over (a 409 says to read again).

How things fit together:

- **A role from a link:** `POST /postings/read` with `{"link": ...}` returns a draft (company,
  title, location, pay, posting text) and saves nothing. Some sites (Workday, LinkedIn) give
  nothing to read; then ask them to paste the posting and send it as `posting`.
- **Status:** `POST /roles/{id}/status`. Applying, an offer and a rejection log their own event
  on the timeline, so do not add one separately. Calls, interviews and notes are
  `POST /roles/{id}/events`.
- **Todos:** `POST /todos` with `role_id`, or none for the search as a whole; check one off with
  `PATCH /todos/{id}` `{"done": true}`. A new role gets the starter todos from
  `config/starter-todos.json` on its own.
- **A talk:** `POST /interactions` with `person_id` for someone known, or `person` (at least a
  name) for someone new, never both. Look the person up in `/api/networking/people` first.
- **A referral:** `PATCH /roles/{id}` with `referral_person_id`, a networking person's id.
- **Resumes:** the owner exports a PDF into `data/resumes/`. Attach it with `PATCH /roles/{id}`
  `{"resume_file": "name.pdf"}`. When the role moves to applied, the writer keeps a copy in
  `data/sent/`, so the role always shows what that company got.
- **Profile:** `data/profile.md` holds their work history, stories, skills and voice, each fact
  with its source. The `career-interview` skill writes it (format in
  `.claude/skills/career-interview/profile-format.md`), going through their master resume,
  `data/resumes/master.md`, bullet by bullet when there is one. Example resumes and old cover
  letters go in `data/examples/resumes/` and `data/examples/cover-letters/`, and things they
  said before, to confirm in the interview, in `data/notes/`.
- **Style:** `data/style.md` holds how they want their resumes and letters to look and read:
  layout, wording rules, and phrasings they turned down. The drafting skills read it and save
  their corrections to it, one line at a time (format in
  `.claude/skills/tailor-resume/style-format.md`). Facts never go there; they go in the profile.
- **Drafts:** the `tailor-resume` skill writes a role's resume drafts, from
  `data/resumes/master.md` when there is one, to `data/drafts/<role-id>/resume-<n>.md`, and
  `write-cover-letter` its letters to `data/drafts/<role-id>/cover-letter-<n>.md`, each a new
  version beside the earlier ones. After writing one, the skill has the writer make its PDF
  beside it (`POST /roles/{id}/drafts/{name}/pdf`, which answers with its pages; a resume over
  one page is refused and gets no PDF). The owner sees each as that PDF, copies its text and
  approves it under Drafts on the role's page; `GET /api/career/roles/{id}/drafts` lists them,
  and the role's `approved_resume_draft` and `approved_cover_letter` name the approved ones.
  Approving a resume draft makes its PDF the role's `resume_file`, copied into `data/resumes/`.
  Applying keeps a copy of the approved letter, text and PDF, in `data/sent/`. Only the owner
  approves a draft: never set those two fields yourself.

## Rules

- **Confirm before deleting anything.** Say what will go. Deletes can be undone: right away with
  `POST .../{id}/restore`, and later from Recently deleted on the Career page.
- **Show the draft before adding a role from a link,** and add it only once they agree.
- **Never invent a company, title, pay, date, person or anything they said.** Leave a field out
  rather than guess it. Dates you work out ("Thursday") are said back as a date.
- **When it is not clear which role or person is meant, ask.** Show the close matches.
- Say back what changed in a line, in plain words.
- Do not change any code unless the owner asks. Do not commit or push unless they ask.

## Files that are the owner's own

This copy of career-kit is theirs; two files are meant to be changed by them, and updates
pulled from the original repo never touch them:

- `web/src/styles/theme.css`: the page's colors (the `customize-colors` skill).
- `config/starter-todos.json`: the todos every new role starts with (the `customize-todos` skill).

To get the latest career-kit, follow the README's "Getting updates" step by step, starting
with `./stop.sh`, and say what each step did. Their asking for it is their OK to commit.

## For changes to the code

`docs/engineering.md` and `docs/writers.md` say how it is built. Tests: `uv run pytest` in
`api`, `tools/career`, `tools/networking` and `tools/writekit`; `pnpm test` and `pnpm build` in
`web` (Node 24: `eval "$(fnm env)"; fnm use 24`); `uv run pytest` in `tests/e2e` for the page and
scripts end to end (once first: `uv run playwright install chromium` there). Lint and format:
`uvx ruff@0.17.1 check .` and `uvx ruff@0.17.1 format .` from the root. After changing a
drafting skill: `bash tests/skills/round.sh` (real Claude calls, about an hour;
`tests/skills/README.md`).
