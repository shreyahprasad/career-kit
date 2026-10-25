"""writekit on a throwaway database with one table and one migration."""

import datetime as dt
import os
import sqlite3
import threading
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from writekit import app as app_module
from writekit.app import create_writer
from writekit.db import Database
from writekit.env import load_api_key
from writekit.errors import NotFound, Refused, Rejected
from writekit.forms import Form, Line
from writekit.testing import HEADERS, LOCAL, assert_fields_current, assert_schema_current

SCHEMA = "CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT NOT NULL CHECK (body <> ''));"


@pytest.fixture
def db(tmp_path) -> Database:
    (tmp_path / "migrations").mkdir()
    (tmp_path / "migrations/001_tag.sql").write_text("ALTER TABLE notes ADD COLUMN tag TEXT;")
    conn = sqlite3.connect(tmp_path / "data.db")
    conn.executescript(SCHEMA)
    conn.close()
    return Database(tmp_path / "data.db", tmp_path / "migrations")


def count(db: Database) -> int:
    with db.reading() as r:
        return r.execute("SELECT count(*) FROM notes").fetchone()[0]


def backups(db: Database) -> list[str]:
    return sorted(p.name for p in (db.path.parent / "backups").glob("*.db"))


# ── Database ─────────────────────────────────────────────────────────────────


def test_a_change_commits_after_a_backup_of_how_it_was(db):
    with db.change("add-one") as w:
        w.execute("INSERT INTO notes (body) VALUES ('hi')")
    assert count(db) == 1
    [name] = backups(db)
    assert name.startswith("data-") and name.endswith("-before-add-one.db")
    assert sqlite3.connect(db.path.parent / "backups" / name).execute("SELECT count(*) FROM notes").fetchone()[0] == 0


def test_a_change_that_fails_halfway_saves_nothing_and_leaves_it_unlocked(db):
    with pytest.raises(Refused):
        with db.change("half") as w:
            w.execute("INSERT INTO notes (body) VALUES ('first')")
            raise Refused("no")
    assert count(db) == 0
    assert backups(db) == []  # nothing changed, so nothing to keep
    with db.change("after") as w:  # not locked
        w.execute("INSERT INTO notes (body) VALUES ('ok')")
    assert count(db) == 1


def test_a_change_waits_for_another_and_backs_up_after_it(db):
    """Two changes at once: the second's backup holds the first's row, so it is the database
    right before the second change."""
    holding = threading.Event()

    def first():
        with db.writing() as other:
            other.execute("BEGIN IMMEDIATE")
            other.execute("INSERT INTO notes (body) VALUES ('first')")
            holding.set()
            time.sleep(0.2)
            other.execute("COMMIT")

    thread = threading.Thread(target=first)
    thread.start()
    holding.wait()
    with db.change("second") as w:  # waits for the first to commit
        w.execute("INSERT INTO notes (body) VALUES ('second')")
    thread.join()
    [name] = backups(db)
    assert sqlite3.connect(db.path.parent / "backups" / name).execute("SELECT body FROM notes").fetchall() == [
        ("first",)
    ]


def test_daily_backups_take_one_on_the_first_change_of_the_day(db):
    db.backups = "daily"
    with db.change("one") as w:
        w.execute("INSERT INTO notes (body) VALUES ('a')")
    with db.change("two") as w:
        w.execute("INSERT INTO notes (body) VALUES ('b')")
    [name] = backups(db)
    assert name.endswith("-before-one.db")


def test_a_failed_change_keeps_the_days_backup_it_did_not_take(db):
    db.backups = "daily"
    with db.change("one") as w:
        w.execute("INSERT INTO notes (body) VALUES ('a')")
    with pytest.raises(Refused):
        with db.change("two"):
            raise Refused("no")
    assert len(backups(db)) == 1


def stamp(day: str, label: str, n: int = 0) -> str:
    return f"data-{day}-1200{n:02d}-000000-before-{label}.db"


def test_old_backups_thin_out_and_migration_backups_stay(db):
    """Every backup from the last week; one a day, the day's first, back to 90 days; none older.
    A migration's backup is always kept."""
    folder = db.path.parent / "backups"
    folder.mkdir()
    names = [
        stamp("2026-10-07", "a"),
        stamp("2026-10-07", "b", 1),  # this week: both kept
        stamp("2026-09-01", "c"),
        stamp("2026-09-01", "d", 1),  # a month ago: the first kept
        stamp("2026-06-01", "e"),  # over 90 days: gone
        stamp("2026-01-01", "migration-001_tag"),  # a migration: kept
        "notes.txt",  # not a backup: left alone
    ]
    for name in names:
        (folder / name).touch()
    db.prune_backups(today=dt.date(2026, 10, 8))
    assert sorted(p.name for p in folder.iterdir()) == sorted([names[0], names[1], names[2], names[5], names[6]])


def test_a_backup_thins_out_old_ones(db):
    """A writer that calls backup() itself, so the thinning is there, not only in change()."""
    folder = db.path.parent / "backups"
    folder.mkdir()
    (folder / stamp("2020-01-01", "old")).touch()
    with db.change("new") as w:
        w.execute("INSERT INTO notes (body) VALUES ('a')")
    [name] = backups(db)
    assert name.endswith("-before-new.db")


def test_reading_cannot_write(db):
    with db.reading() as r, pytest.raises(sqlite3.OperationalError):
        r.execute("INSERT INTO notes (body) VALUES ('x')")


def test_a_missing_database_is_never_created_empty(tmp_path):
    missing = Database(tmp_path / "gone.db", tmp_path)
    with pytest.raises(FileNotFoundError):
        with missing.writing():
            pass
    assert not missing.path.exists()


def test_migrate_applies_what_is_pending_once_after_a_backup_and_turns_on_wal(db):
    assert db.migrate() == ["001_tag.sql"]
    assert db.migrate() == []
    with db.reading() as r:
        assert r.execute("PRAGMA user_version").fetchone()[0] == 1
        assert r.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert "tag" in [c[1] for c in r.execute("PRAGMA table_info(notes)")]
    [name] = backups(db)
    assert name.endswith("-before-migration-001_tag.db")


def test_a_migration_that_fails_is_rolled_back_whole(db):
    (db.migrations / "002_bad.sql").write_text("ALTER TABLE notes ADD COLUMN extra TEXT;\nNOT SQL;")
    with pytest.raises(sqlite3.OperationalError):
        db.migrate()
    with db.reading() as r:
        assert r.execute("PRAGMA user_version").fetchone()[0] == 1  # 001 kept, 002 not half applied
        assert "extra" not in [c[1] for c in r.execute("PRAGMA table_info(notes)")]


def test_assert_schema_current(tmp_path, db):
    schema = tmp_path / "schema.sql"
    schema.write_text(SCHEMA + "\nPRAGMA user_version = 1;\n")
    assert_schema_current(schema, db.migrations)
    schema.write_text(SCHEMA)
    with pytest.raises(AssertionError, match="user_version = 1"):
        assert_schema_current(schema, db.migrations)


def test_assert_fields_current(tmp_path, monkeypatch):
    path = tmp_path / "fields.json"
    with pytest.raises(AssertionError, match="UPDATE_FIELDS=1"):
        assert_fields_current(path, {"Note": Note})
    monkeypatch.setenv("UPDATE_FIELDS", "1")
    assert_fields_current(path, {"Note": Note})
    monkeypatch.delenv("UPDATE_FIELDS")
    assert_fields_current(path, {"Note": Note})
    assert path.read_text() == '{\n  "Note": [\n    "body"\n  ]\n}\n'


# ── The app ──────────────────────────────────────────────────────────────────


class Note(Form):
    body: Line = None


ME = "me@example.com"
TAILNET_HOST = "mini.tail0000.ts.net"


@pytest.fixture
def client(db):
    app = create_writer("test", db, max_body_bytes=1000, logins=[ME], hosts=[TAILNET_HOST], reads=["/look"])

    @app.post("/look")
    def look(note: Note) -> dict:
        return {"seen": note.body, "count": count(db)}

    @app.get("/notes")
    def notes() -> dict:
        return {"count": count(db)}

    @app.post("/notes")
    def add(note: Note) -> dict:
        with db.change("add") as w:
            w.execute("INSERT INTO notes (body) VALUES (?)", (note.body,))
        return {"count": count(db)}

    @app.post("/slow")
    def slow(note: Note) -> dict:
        time.sleep(0.2)
        return add(note)

    @app.post("/fail/{kind}")
    def fail(kind: str) -> dict:
        raise {"refused": Refused, "missing": NotFound, "rejected": Rejected}[kind](f"because {kind}")

    with TestClient(app, base_url=LOCAL) as c:  # `with` runs the lifespan: migrations
        yield c


def test_starting_the_app_migrates(client, db):
    with db.reading() as r:
        assert r.execute("PRAGMA user_version").fetchone()[0] == 1


def test_on_start_runs_after_the_migrations(db):
    seen = []

    def on_start():
        with db.reading() as r:
            seen.append(r.execute("PRAGMA user_version").fetchone()[0])

    with TestClient(create_writer("test", db, max_body_bytes=1000, on_start=on_start), base_url=LOCAL):
        pass
    assert seen == [1]


def test_reading_needs_no_header_and_a_change_does(client):
    assert client.get("/notes").json() == {"count": 0}
    r = client.post("/notes", json={"body": "hi"})
    assert (r.status_code, r.json()["detail"]) == (403, "Changes need the X-Career-Kit-Write header.")
    assert client.post("/notes", json={"body": "hi"}, headers=HEADERS).json() == {"count": 1}


def test_a_body_too_large_is_refused_before_it_is_read(client):
    r = client.post("/notes", content=b"{}", headers={**HEADERS, "content-length": "1001"})
    assert r.status_code == 413


@pytest.mark.parametrize("kind, status", [("refused", 409), ("missing", 404), ("rejected", 400)])
def test_each_refusal_comes_back_with_its_status_and_reason(client, kind, status):
    r = client.post(f"/fail/{kind}", headers=HEADERS)
    assert (r.status_code, r.json()) == (status, {"detail": f"because {kind}"})


def test_the_database_refusing_a_row_is_409_and_nothing_is_saved(client):
    r = client.post("/notes", json={"body": None}, headers=HEADERS)  # NOT NULL
    assert r.status_code == 409 and r.json()["detail"].startswith("data.db refused it: NOT NULL")
    assert client.get("/notes").json() == {"count": 0}


def test_an_unknown_field_is_a_typo_and_refused(client):
    assert client.post("/notes", json={"bdy": "hi"}, headers=HEADERS).status_code == 422


@pytest.mark.parametrize("sent, saved", [("  hi  ", "hi"), ("", None), ("   ", None)])
def test_text_is_stripped_and_a_blank_is_nothing(sent, saved):
    assert Note(body=sent).body == saved


@pytest.mark.parametrize(
    "value, ok",
    [
        ("https://jobs.example/1?a=b", True),
        (" https://jobs.example/1 ", True),
        ("javascript:alert(1)", False),
        ("ftp://jobs.example/1", False),
        ("localhost/x", False),
        ("https://me@evil.example/", False),
        ("https://", False),
        ("https://jobs example", False),
        ("https://" + "x" * 2000, False),
    ],
)
def test_a_web_link_is_https_with_a_host(value, ok):
    from pydantic import TypeAdapter, ValidationError

    from writekit.forms import WebLink

    try:
        TypeAdapter(WebLink).validate_python(value)
        assert ok
    except ValidationError:
        assert not ok


@pytest.mark.parametrize(
    "value, saved",
    [
        ("http://linkedin.com/in/richard-de-leon", "https://linkedin.com/in/richard-de-leon"),
        (" HTTP://jobs.example/1 ", "https://jobs.example/1"),
        ("linkedin.com/in/raj", "https://linkedin.com/in/raj"),
        ("www.linkedin.com", "https://www.linkedin.com"),
    ],
)
def test_a_web_link_typed_as_http_or_bare_is_saved_as_https(value, saved):
    from pydantic import TypeAdapter

    from writekit.forms import WebLink

    assert TypeAdapter(WebLink).validate_python(value) == saved


def test_a_link_that_is_not_one_says_so_plainly():
    from pydantic import TypeAdapter, ValidationError

    from writekit.forms import WebLink

    with pytest.raises(ValidationError, match="should be a web link, like https://"):
        TypeAdapter(WebLink).validate_python("javascript:alert(1)")


@pytest.mark.parametrize(
    "value, ok",
    [
        ("zoe-o-brien", True),
        ("acme-forward-deployed-engineer-2", True),
        ("2nd", True),
        ("-zoe", False),
        ("Zoe", False),
        ("zoe o", False),
        ("zoe/../x", False),
        ("", False),
        ("x" * 201, False),
    ],
)
def test_a_slug_is_an_id_made_by_id_from_name(value, ok):
    from pydantic import TypeAdapter, ValidationError

    from writekit.forms import Slug

    try:
        TypeAdapter(Slug).validate_python(value)
        assert ok
    except ValidationError:
        assert not ok


@pytest.mark.parametrize("name", ["Zoë O'Brien", "Dr. A.B. Smith, Jr.", "x" * 70, "2nd round"])
def test_every_id_from_name_is_a_slug(name):
    from pydantic import TypeAdapter

    from writekit.forms import Slug
    from writekit.rows import id_from_name

    TypeAdapter(Slug).validate_python(id_from_name(name) + "-2")


@pytest.mark.parametrize(
    "value, ok",
    [
        ("JaneDoe.pdf", True),
        ("Resume 2026-10 v2.pdf", True),
        ("resume.PDF", False),
        (".hidden.pdf", False),
        ("../career.db.pdf", False),
        ("sent/resume.pdf", False),
        ("resume.pdf.exe", False),
        ("x" * 197 + ".pdf", False),
    ],
)
def test_a_pdf_name_is_a_file_name_only(value, ok):
    from pydantic import TypeAdapter, ValidationError

    from writekit.forms import PdfName

    try:
        TypeAdapter(PdfName).validate_python(value)
        assert ok
    except ValidationError:
        assert not ok


@pytest.mark.parametrize(
    "sent, ok", [({}, True), ({"version": 3}, True), ({"version": 0}, False), ({"version": "x"}, False)]
)
def test_a_version_is_optional_and_counts_from_one(sent, ok):
    from pydantic import ValidationError

    from writekit.forms import Versioned

    try:
        Versioned(**sent)
        assert ok
    except ValidationError:
        assert not ok


def test_text_over_its_limit_is_refused():
    with pytest.raises(ValueError):
        Note(body="x" * 501)


# ── Who may change things ────────────────────────────────────────────────────
# tailscale serve sends a request on with X-Forwarded-For and the tailnet login of whoever sent it
# (Tailscale-User-Login, which it sets itself, never passing on one the sender made up). A request
# with neither came from this Mac.


def test_a_change_from_this_mac_needs_no_login(client):
    assert client.post("/notes", json={"body": "hi"}, headers=HEADERS).status_code == 200


def test_a_change_from_her_on_the_tailnet_is_made(client):
    tailnet = {**HEADERS, "X-Forwarded-For": "100.64.0.2", "Tailscale-User-Login": ME}
    assert client.post("/notes", json={"body": "hi"}, headers=tailnet).json() == {"count": 1}


@pytest.mark.parametrize("method, path", [("post", "/notes"), ("get", "/notes")])
def test_anyone_else_on_the_tailnet_is_refused_even_a_read(client, method, path):
    stranger = {**HEADERS, "X-Forwarded-For": "100.64.0.3", "Tailscale-User-Login": "them@example.com"}
    r = getattr(client, method)(path, headers=stranger)
    assert (r.status_code, r.json()["detail"]) == (
        403,
        "Changes come only from the owner. This came from them@example.com.",
    )
    assert count_after(client) == 0


def test_a_forwarded_request_with_no_login_is_refused(client):
    """A tagged device on the tailnet has no login: it cannot be the owner."""
    r = client.post("/notes", json={"body": "hi"}, headers={**HEADERS, "X-Forwarded-For": "100.64.0.4"})
    assert (r.status_code, r.json()["detail"]) == (
        403,
        "Changes come only from the owner. This came from a device with no login.",
    )


def test_with_no_logins_set_the_tailnet_is_refused_with_how_to_set_them(db, tmp_path):
    env = tmp_path / ".env"
    env.write_text("OTHER=1\n")
    with TestClient(create_writer("test", db, max_body_bytes=1000, logins=None, env_file=env), base_url=LOCAL) as c:
        r = c.get("/x", headers={"X-Forwarded-For": "100.64.0.2", "Tailscale-User-Login": ME})
    assert r.status_code == 403 and "TAILNET_LOGINS" in r.json()["detail"]


def test_logins_come_from_the_env_file(db, tmp_path):
    env = tmp_path / ".env"
    env.write_text(f"TAILNET_LOGINS={ME}, other@example.com\n")
    with TestClient(create_writer("test", db, max_body_bytes=1000, logins=None, env_file=env), base_url=LOCAL) as c:
        r = c.get("/x", headers={"X-Forwarded-For": "100.64.0.2", "Tailscale-User-Login": "other@example.com"})
    assert r.status_code == 404  # let through: no such route


def count_after(client) -> int:
    return client.get("/notes").json()["count"]


# ── The name it is reached by ───────────────────────────────────────────────
# A page on another site can point its own name at 127.0.0.1 (DNS rebinding) and reach a server
# here as if from this Mac. The Host it sends is still its own name, so only this Mac's names and
# the tailnet name are answered.


@pytest.mark.parametrize(
    "base",
    [
        "http://127.0.0.1:8120",
        "http://localhost",
        "http://[::1]:8100",
        f"https://{TAILNET_HOST}",
        f"https://{TAILNET_HOST}:8443",
    ],
)
def test_this_macs_names_and_the_tailnet_name_are_answered(client, base):
    assert client.get("/notes", headers={"Host": base.split("://")[1]}).status_code == 200


@pytest.mark.parametrize(
    "host", ["evil.example", "evil.example:8120", "127.0.0.1.evil.example", "mini.tail9999.ts.net"]
)
def test_any_other_name_is_refused_even_from_this_mac(client, host):
    r = client.post("/notes", json={"body": "hi"}, headers={**HEADERS, "Host": host})
    assert (r.status_code, r.json()["detail"]) == (
        403,
        f"This only answers to its own names, not {host.split(':')[0]}.",
    )
    assert count_after(client) == 0


def test_the_tailnet_names_come_from_the_env_file(db, tmp_path):
    env = tmp_path / ".env"
    env.write_text(f"TAILNET_HOSTS={TAILNET_HOST}, mini\n")
    with TestClient(
        create_writer("test", db, max_body_bytes=1000, logins=[], env_file=env), base_url=f"https://{TAILNET_HOST}"
    ) as c:
        assert c.get("/x").status_code == 404  # let through: no such route
        assert c.get("/x", headers={"Host": "mini:8443"}).status_code == 404
        assert c.get("/x", headers={"Host": "other.ts.net"}).status_code == 403


# ── Every answer ─────────────────────────────────────────────────────────────


def test_every_answer_says_it_is_data_not_a_page(client):
    """A writer answers JSON only: nothing in it may run, load anything or be framed."""
    for r in (client.get("/notes"), client.post("/fail/refused", headers=HEADERS)):
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        assert r.headers["Content-Security-Policy"] == "default-src 'none'; frame-ancestors 'none'"


# ── Saving once, however many times it is sent ───────────────────────────────
def test_a_body_with_no_length_is_refused_before_it_is_read(client):
    r = client.post("/notes", content=iter([b'{"body": "hi"}']), headers=HEADERS)  # sent chunked
    assert (r.status_code, r.json()["detail"]) == (411, "Send the change with a Content-Length.")
    assert count_after(client) == 0


@pytest.mark.parametrize("size", ["abc", "-1", "1e3", "²"])
def test_a_length_that_is_not_a_number_is_400_not_a_crash(client, size):
    r = client.post("/notes", content=b'{"body": "hi"}', headers={**HEADERS, "Content-Length": size.encode("latin-1")})
    assert (r.status_code, r.json()["detail"]) == (400, "Content-Length should be a number of bytes.")
    assert count_after(client) == 0


# The page sends each change with an Idempotency-Key and sends it again with the same key when
# the phone loses the answer. The writer answers a key it has seen with the first answer.


def keyed(key: str) -> dict:
    return {**HEADERS, "Idempotency-Key": key}


def test_the_same_change_sent_twice_is_made_once_and_answered_the_same(client):
    first = client.post("/notes", json={"body": "hi"}, headers=keyed("key-0001"))
    again = client.post("/notes", json={"body": "hi"}, headers=keyed("key-0001"))
    assert (again.status_code, again.json()) == (first.status_code, first.json()) == (200, {"count": 1})
    assert count_after(client) == 1


def test_a_refusal_sent_again_is_refused_again_the_same_way(client):
    first = client.post("/fail/refused", headers=keyed("key-0002"))
    again = client.post("/fail/refused", headers=keyed("key-0002"))
    assert (
        (again.status_code, again.json()) == (first.status_code, first.json()) == (409, {"detail": "because refused"})
    )


def test_a_new_key_is_a_new_change(client):
    client.post("/notes", json={"body": "hi"}, headers=keyed("key-0003"))
    client.post("/notes", json={"body": "hi"}, headers=keyed("key-0004"))
    assert count_after(client) == 2


def test_a_key_already_used_for_another_change_is_refused(client):
    client.post("/notes", json={"body": "hi"}, headers=keyed("key-0005"))
    r = client.post("/fail/missing", headers=keyed("key-0005"))
    assert r.status_code == 422 and "another change" in r.json()["detail"]


@pytest.mark.parametrize("key", ["short", "x" * 101, "has space here", "semi;colon-key"])
def test_a_key_that_is_not_well_formed_is_refused(client, key):
    assert client.post("/notes", json={"body": "hi"}, headers=keyed(key)).status_code == 400
    assert count_after(client) == 0


def test_the_same_change_sent_again_while_the_first_is_saving_waits_for_it(client):
    answers = []

    def post():
        answers.append(client.post("/slow", json={"body": "hi"}, headers=keyed("key-0006")).json())

    threads = [threading.Thread(target=post) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert answers == [{"count": 1}, {"count": 1}]
    assert count_after(client) == 1


def test_a_key_is_forgotten_after_a_day(client, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(app_module, "time", SimpleNamespace(monotonic=lambda: clock[0]))  # its clock only
    client.post("/notes", json={"body": "hi"}, headers=keyed("key-0008"))
    clock[0] += app_module.IDEMPOTENCY_HOURS * 3600 + 1
    client.post("/notes", json={"body": "hi"}, headers=keyed("key-0009"))  # keys are let go on a save
    assert client.post("/notes", json={"body": "hi"}, headers=keyed("key-0008")).json() == {"count": 3}


def test_only_the_newest_keys_are_kept(client, monkeypatch):
    monkeypatch.setattr(app_module, "IDEMPOTENCY_MAX", 2)
    for key in ("key-0010", "key-0011", "key-0012"):
        client.post("/notes", json={"body": "hi"}, headers=keyed(key))
    assert client.post("/notes", json={"body": "hi"}, headers=keyed("key-0012")).json() == {"count": 3}  # kept
    assert client.post("/notes", json={"body": "hi"}, headers=keyed("key-0010")).json() == {"count": 4}  # made again


def test_a_post_that_changes_nothing_is_answered_fresh_each_time(client):
    """Reading a posting saves nothing, and its answer is long, so it is not kept by key."""
    assert client.post("/look", json={"body": "a"}, headers=keyed("key-0007")).json() == {"seen": "a", "count": 0}
    client.post("/notes", json={"body": "hi"}, headers=HEADERS)
    assert client.post("/look", json={"body": "a"}, headers=keyed("key-0007")).json() == {"seen": "a", "count": 1}


def test_the_identity_check_names_what_it_guards():
    """The read API uses the same check, saying so in its own words."""
    from fastapi import FastAPI

    from writekit.identity import add_identity_check

    app = FastAPI()
    add_identity_check(app, frozenset([ME]), "This page is only for its owner.", hosts=[])

    @app.get("/x")
    def x() -> dict:
        return {}

    with TestClient(app, base_url=LOCAL) as c:
        assert c.get("/x").status_code == 200
        assert c.get("/x", headers={"X-Forwarded-For": "100.64.0.2", "Tailscale-User-Login": ME}).status_code == 200
        r = c.get("/x", headers={"X-Forwarded-For": "100.64.0.3", "Tailscale-User-Login": "them@example.com"})
    assert (r.status_code, r.json()["detail"]) == (
        403,
        "This page is only for its owner. This came from them@example.com.",
    )


# ── The API key ──────────────────────────────────────────────────────────────


def test_the_api_key_comes_from_the_env_file_unless_already_set(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("OTHER=1\nANTHROPIC_API_KEY='sk-test'\n")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    load_api_key(env)
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-test"
    env.write_text("ANTHROPIC_API_KEY=other\n")
    load_api_key(env)
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-test"
