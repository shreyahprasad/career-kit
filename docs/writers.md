# Writers

A **writer** is the one process that changes one database. The read API in `api/` only reads,
and it keeps no write routes. Each page that saves something talks to its own writer.

| Writer | Database | Port | Routes |
|---|---|---|---|
| `tools/career/writer.py` | `data/career.db` (`CAREER_DIR` or `CAREER_DB` to move it) | 8140 | `/api/career/write` |
| `tools/networking/writer.py` | `data/networking.db` (`NETWORKING_DB` to move it) | 8120 | `/api/networking/write` |

Each writer's routes are listed in the docstring at the top of its `writer.py`. Besides
`career.db`, the career writer writes files under `data/`: the PDF of a draft beside it
(`POST /roles/{id}/drafts/{name}/pdf`), the approved resume's PDF in `data/resumes/`, and the
copies kept in `data/sent/` when you apply. A draft's PDF is made by `tools/career/render.py` in
a child process with a time limit, in a folder holding only the layout and the draft, so a draft
is never run as code and cannot hang the writer. A resume is one page: a resume draft that runs
over is refused (409, with about how many lines over) and gets no PDF, so it cannot be approved.

## Why one process per writer

- **Least access.** A writer can open only its own database, so a bug in one cannot touch the
  other.
- **Failures stay local.** A writer that crashes or hangs never takes the other one with it.
- **The shared parts live in `tools/writekit`,** so a writer is mostly its own domain code.

## What writekit gives every writer

| Module | What it does |
|---|---|
| `writekit.db.Database` | `reading()`, `writing()`, `change(label)` (write lock, backup, one transaction; a refused change keeps no backup), `backup()`, `migrate()`. `backups="daily"` backs up before the first change of each day only, for a database that changes very often. Each backup thins out old ones: every backup from the last 7 days, then the first of each day back to 90 days, then none; a migration's backup is always kept |
| `writekit.app.create_writer` | The FastAPI app: the `X-Career-Kit-Write: 1` header on every change, a body size limit checked before reading, pending migrations applied on start (then `on_start`, if given), and refusals returned as `{"detail": why}`. It answers only to this Mac's names and the names in `TAILNET_HOSTS`, so a page that points its own name at 127.0.0.1 (DNS rebinding) is refused. Over the tailnet only a login in `TAILNET_LOGINS` (`.env`) gets in; a request from this Mac needs none (`writekit.identity`, which the read API uses too). Every answer is marked as data (`nosniff`, a CSP of `default-src 'none'`). A change sent with an `Idempotency-Key` is made once and answered the same when sent again; the keys live in memory, so a writer that restarts forgets them. `reads=` names POSTs that change nothing (reading a posting), whose answers are not kept |
| `writekit.errors` | `Refused` (409), `NotFound` (404), `Rejected` (400). SQLite refusing a row is a 409 |
| `writekit.forms` | `Form` (an unknown key is a 422, never dropped), and `Line` and `Long`: text that is stripped, saved as nothing when blank, and limited in length. `WebLink` (https, a host, no login; typed as http:// or bare like `linkedin.com/in/x`, it is saved with https://) and `Email`, with `Optional...` forms where a blank is none. Every link a page opens is a `WebLink`, and the page links only those (`shell/ExternalLink.tsx`) |
| `writekit.rows` | `id_from_name` and `free_id` (a slug id, with -2, -3... when taken), `check_fields`, and `insert` and `update` of the columns a records.py allows. `update_versioned` moves a row's `version` on and refuses a save from an older one (409, `STALE`); `set_deleted` hides a row or brings it back (`deleted_on`) |
| `writekit.testing` | `HEADERS` for test clients, and `LOCAL`, the base URL they send from; `assert_schema_current(schema, migrations)`; `assert_fields_current(path, forms)`, which keeps `fields.json` (what each request body takes) up to date for the page's tests (`UPDATE_FIELDS=1` rewrites it) |
| `writekit.env` | `env_value(name)`: a setting from the checkout's `.env` (`CAREER_KIT_ENV` points elsewhere, e.g. from a worktree) |
| `web/src/shell/api.ts` `send()` | The page side: sends the header, a fresh `Idempotency-Key` and JSON; tries again with the same key when the change may not have arrived; throws a `Refusal` whose message is the writer's reason |
| `web/src/shell/undo.ts`, `UndoBar.tsx` | After a delete (or replacing a saved posting), "Deleted ... Undo" for 10 seconds; undo sends the restore. After that, Career's Recently deleted brings things back |

The rules every writer keeps:

- Every change is all or nothing, with a backup of the database just before it. Every writer
  gets both from `db.change(label)`.
- Nothing is guessed. A request says exactly what to change, and anything unclear is refused
  with a reason you can read.
- `schema.sql` builds a current database and ends with `PRAGMA user_version = N`, where N is
  the newest migration. A schema change is also a new `migrations/NNN_name.sql`.
- A row the page edits from a loaded copy has `version`; the edit sends it back. Deleting hides a
  row (`deleted_on`) so undo can bring it back; the read API leaves hidden rows out.
- The page's `data.ts` lists what each change sends (`SENDS`), and its test holds the lists to
  the writer's `fields.json`.

## Adding a writer

For a tool called `thing`:

1. **Schema.** Add `tools/thing/schema.sql` ending in `PRAGMA user_version = 0;`, and an empty
   `tools/thing/migrations/`.
2. **Project.** Add `tools/thing/pyproject.toml`: copy `tools/networking/pyproject.toml`, keeping
   the `writekit` path source, then run `uv lock`.
3. **Store.** Add `tools/thing/store.py`: `db = Database(Path(os.environ.get("THING_DB", ...)), migrations)`,
   defaulting to `data/thing.db`.
4. **Domain.** Add `tools/thing/records.py`: one function per change, each one `with store.db.change(...)`.
   Raise `Refused`, `NotFound` or `Rejected` with the reason in plain words.
5. **Routes.** Add `tools/thing/writer.py`: `app = create_writer("thing", store.db, MAX_BODY_BYTES)`,
   with request bodies as `Form`s under one prefix, `/api/thing/write/<route>`.
6. **Tests.** Add `tools/thing/test_writer.py`: over HTTP with `HEADERS`, on a database built
   from `schema.sql`, with `assert_schema_current`. The header, size limit and migration
   behavior are already tested in writekit.
7. **Page.** In the plugin's `data.ts`, call `send()` from `shell/api.ts`.
8. **Run it.**
   - Add it to `start.sh` and `stop.sh`, and a row to the table at the top of this file.
   - Add the prefix to the proxy in `web/vite.config.ts`.
   - With phone access, run `tailscale serve --bg --set-path /api/thing/write http://127.0.0.1:<port>/api/thing/write`.
     Serve strips the path, so the target repeats it.
   - Start the writer before reloading the page: it applies pending migrations, and the read
     API may already expect the new columns.

## Trying a change without touching your data

Point the servers at copies: copy `data/` to a scratch folder and start the writers and the read
API with `CAREER_DIR` and `NETWORKING_DB` set to the copies, on ports of their own.
