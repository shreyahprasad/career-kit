# Engineering standards

How career-kit is built: security, reliability, code organization, shared code and testing.
Read this before changing a page or a writer. `docs/writers.md` has the detail on how anything
is saved; where it says more, it wins on the detail.

**Words used here:**

- **Read API:** the one process that reads every database and serves the built page. It has no
  write routes.
- **Writer:** the one process allowed to change its database (career, networking), over HTTP on
  127.0.0.1, behind the `X-Career-Kit-Write: 1` header.
- **Talk:** a call, coffee or message with someone, as the page says it. The API, table and
  fields call it an **interaction** (`POST /api/networking/write/interactions`).
- **Idempotency key:** the `Idempotency-Key` header a change is sent with, so a retry of the same
  change is made once.
- **Host app:** another app that runs career-kit's read API and writers for the owner, on the same
  ports (section 2).
- **Skill:** a Claude Code prompt in `.claude/skills/`, the way the owner works with career-kit
  from their phone.

## 1. What we are building for

One person, one Mac, reached from that Mac and, if they set it up, their phone over Tailscale.
That sets the scale of every choice:

- **Your data is the product.** Losing or corrupting it is the worst failure. Downtime is a
  nuisance; a lost role or talk is not.
- **Nothing is public.** This Mac is the only server. Everything binds to 127.0.0.1, and the page
  reaches the phone over Tailscale only. (Claude reaches the phone through Remote Control, which
  is Claude Code's, not ours.)
- **Simple over scalable.** SQLite files, a few local processes and one Vite build. No Docker, no
  Postgres, no queue, no account system.

## 2. The shape of the system

| Piece | Where | Does |
|---|---|---|
| Page | `web/src/plugins/<id>/`, listed in `registry.ts` | What you see. Never holds a secret |
| Shell | `web/src/shell/` | What two or more pages share: routing, `send()`, `useLoad`, `useSave`, folds, dates, undo. Pages import it as `@shell/...` (the alias in `vite.config.ts` and `tsconfig.json`), never by a relative path, so an app that hosts them gives its own |
| Site | `web/dist`, served by `vite preview` on 127.0.0.1:5180 (`start.sh`) | The page on this Mac; sends changes on to the writers, the rest to the read API |
| Read API | `api/<id>.py`, one process on 127.0.0.1:8100 | Reads every database, serves the built site to the phone through `tailscale serve`, has no write routes |
| Writer | `tools/<id>/writer.py`, one process per database | The only thing that changes its database |
| writekit | `tools/writekit/` | What every writer shares: database, app, forms, rows, errors, env, testing |
| Data | `data/` in the checkout | Gitignored, folder mode 700; `data/run/` has each server's pid and log |
| Running | `setup.sh` once, then `start.sh` and `stop.sh` | Ports move with `API_PORT`, `CAREER_PORT`, `NETWORKING_PORT`, `WEB_PORT`, in the shell or `.env` (shell wins) |
| Host app | Another app, optional | Can run the read API and writers for the owner on the same ports; its `/api/health` answers `"serves": ["career-kit"]`, and the skills then use it and never start career-kit's own (`CLAUDE.md`, "Hosted by another app") |

Reads and writes are split on purpose: a bug in a page or the read API cannot change data, and a
bug in one writer cannot touch another writer's database (`docs/writers.md`, "Why one process per
writer").

## 3. Security

Every new piece keeps all of these. Most come free from writekit and the shell; the point is not
to step around them.

- **Bind 127.0.0.1 only.** The phone reaches a service through `tailscale serve`, never a public
  bind, never a tunnel.
- **Who gets in.** Over the tailnet, only a login in `TAILNET_LOGINS`; from this Mac, no login.
  Requests must name this Mac or a host in `TAILNET_HOSTS`, which stops DNS rebinding
  (`writekit.identity`, used by the read API and every writer).
- **Every change** carries `X-Career-Kit-Write: 1`, has a body size limit checked before reading,
  and is a `Form` where an unknown key is refused. Text is a `Line` or `Long` with a length limit.
  Links are `WebLink` (https, no login in the URL), opened only through `shell/ExternalLink.tsx`.
- **Every writer answer is data,** never a page: `nosniff` and a CSP of `default-src 'none'`. The
  read API also serves the page, so every answer it sends, data and PDFs too, carries the page's
  headers (`web/security-headers.json`: its CSP, `frame-ancestors 'none'`, `nosniff`); `vite
  preview`, the page on this Mac, sends the same.
- **Nothing answers CORS.** The write header keeps other pages out only while no server answers a
  preflight, so the writers never do and vite has `cors: false`, even for pages on this Mac.
- **Settings** live only in the checkout's `.env`, read by `writekit.env`. It is gitignored.
- **Before every commit,** check the staged files for keys, tailnet addresses and names, emails,
  `.env` and `.db` files.

## 4. Reliability and your data

- **Every change is all or nothing, with a backup just before it:** `db.change(label)`. A refused
  change keeps no backup. Backups thin themselves (all of the last 7 days, then one a day to 90
  days); a migration's backup is always kept.
- **Nothing is guessed.** A request says exactly what to change. Anything unclear is refused with
  a reason you can read (`Refused` 409, `NotFound` 404, `Rejected` 400).
- **Saves survive a bad connection.** Writes are idempotent: `send()` sends an `Idempotency-Key`
  and retries with the same key, so a retried change happens once.
- **Edits from a stale screen are refused,** not merged: rows you edit carry `version`
  (`update_versioned`, 409 `STALE`).
- **Deleting hides** (`deleted_on`), with Undo for 10 seconds and a way back after that. Nothing
  you made is removed for good without you asking.
- **Schema changes are migrations.** `schema.sql` always builds a current database and ends with
  `PRAGMA user_version = N`; each change is also `migrations/NNN_name.sql`.
  `assert_schema_current` holds the two equal. Only the writer migrates, on start.

## 5. Where code goes

- **A page is a folder:** `manifest.ts`, the page and its parts, `data.ts` (what it reads and
  what each change `SENDS`), pure logic in `<id>.ts` and friends with tests next to them, and one
  `style.ts` for every number the page uses.
- **A writer is a folder:** `schema.sql`, `migrations/`, `store.py`, `records.py` (one function
  per change), `writer.py` (routes only), `test_writer.py`, `fields.json`, its own
  `pyproject.toml` and `uv.lock`. Follow `docs/writers.md`, "Adding a writer", step by step.
- **Reads** for a page are one file, `api/<id>.py`, with `test_<id>.py`.
- **Routes:** reads under `/api/<id>/`, changes under `/api/<id>/write`.
- **Logic out of components.** Rules (routing, matching, dates) are pure functions with tests.
  Components wire them to the screen.

## 6. Shared code

- **Move it on the second use, not before.** The first page writes it locally. The second page
  that needs it moves it to `shell/` or `writekit` and both use it from there. Never copy it a
  second time.
- **One way to do each thing.** Saving: `useSave` / `useSaveEach`. Loading: `useLoad`. Folding:
  `Fold`. Dates: `shell/dates.ts`. Changing data: `db.change()`. Restoring: `writekit.rows`. If you
  are about to write a second way, use the first or replace it everywhere in the same change.
- **A page imports from another page only when the thing truly belongs to that page,** like Career
  using networking's `PersonPicker` because a referral is a networking person. Anything else
  goes through `shell/`.
- **Writers never import each other.** What they share is writekit.
- **One list, one place.** Hosts come from `TAILNET_HOSTS` in `.env` (Vite reads it too); design
  values from `tokens.css`; page numbers from that page's `style.ts`.

## 7. Clean code

- No redundant code unless it reads better. No scattered magic numbers: colors, fonts, spacing
  and radii are tokens in `web/src/styles/tokens.css`; a page's own numbers are in its `style.ts`.
- One type scale (`--type-*`), one `.control` style. No size outside the scale.
- Names say what a thing is in your words (a role, a talk, a todo), not in framework words.
- Errors are sentences you can act on, shown as they come from the writer.
- Comments explain why, at the density of the code around them. Docs are plain, short sentences.
- Exact pins, committed lockfiles, Node 24 through fnm, Python through uv.

## 8. Dependencies

- Own the look, layouts, data model, routes and components. Do not hand-roll rendering,
  accessibility, HTTP, auth or crypto.
- Exact versions, committed lockfiles, no install scripts unless allow-listed.
- Few direct dependencies. Add one only when a change needs it, and say why.
- Update deliberately: read the changelog, bump, test. Never as a side effect.

## 9. Testing

- **Test first for logic,** not for pixels. Pure functions in the page get Vitest tests; writers
  get pytest over HTTP on a database built from `schema.sql`; the read API gets pytest, including
  that it refuses every write and never returns internal fields.
- **The page and writer agree:** `data.ts` `SENDS` is checked against the writer's `fields.json`.
- **Before a change is done:** every suite green (`pnpm test` in `web`, `uv run pytest` in `api`,
  each writer and writekit) and `pnpm build` clean.
- **End to end:** `tests/e2e` runs the real page and servers in a browser (Playwright), on a copy
  of the checkout with scratch ports 9100 to 9140 and 6180, made-up data, and `stop.sh` at the
  end: `cd tests/e2e && uv run pytest` (the first time, `uv run playwright install chromium`
  there). A flow there checks the page, then what was saved. Run it too before a change to the
  page or the scripts is done.
- **Lint and format:** `ruff`, one config (`ruff.toml`) for every Python folder, the version
  pinned there: `uvx ruff@0.17.1 check .` and `uvx ruff@0.17.1 format .` from the root.
- **CI** (`.github/workflows/ci.yml`) runs ruff, every Python suite, `pnpm test` and `pnpm build`
  on Linux for every push and pull request, and the e2e suite on macOS for pushes to main or when started by hand.
- **Skills:** `tests/skills` runs the drafting skills for real, a scripted owner talking to
  Claude on made-up data, then scripted checks and an LLM judge. It makes real Claude calls, so
  it is run by hand after a skill changes, never in CI (`tests/skills/README.md`).
