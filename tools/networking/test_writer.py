"""writer.py over HTTP, on a throwaway networking.db built by seed.py from schema.sql. Made-up people.
What every writer does alike (the header, the size limit, backups, migrating) is tested in writekit."""

import datetime as dt
import re
import sqlite3
import typing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import seed
import store
import writer
from writekit.rows import ID_LENGTH, STALE, id_from_name
from writekit.testing import HEADERS, LOCAL, assert_fields_current, assert_schema_current

P = writer.PREFIX
TODAY = dt.date.today().isoformat()

# Ann has a tag and a talk; Bo has neither.
PEOPLE = [
    {
        "id": "ann-lee",
        "name": "Ann Lee",
        "company": "Acme",
        "tags": ["mentor"],
        "interactions": [{"date": "2026-05-01", "kind": "coffee", "next_step": "follow-up"}],
    },
    {"id": "bo-diaz", "name": "Bo Diaz"},
]


@pytest.fixture
def db(tmp_path, monkeypatch) -> sqlite3.Connection:
    path = tmp_path / "networking.db"
    conn = sqlite3.connect(path)
    with conn:
        seed.seed(conn, {"people": PEOPLE})
    conn.row_factory = sqlite3.Row
    monkeypatch.setattr(store.db, "path", path)
    yield conn
    conn.close()


@pytest.fixture
def client(db):
    with TestClient(writer.app, base_url=LOCAL) as c:  # `with` runs the lifespan: migrations
        yield c


def log(client, body):
    return client.post(f"{P}/interactions", json=body, headers=HEADERS)


def talks(db, person_id):
    return [dict(r) for r in db.execute("SELECT * FROM interactions WHERE person_id = ? ORDER BY id", (person_id,))]


def person(db, person_id):
    row = db.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
    return dict(row) if row else None


def tags(db, person_id):
    return [r[0] for r in db.execute("SELECT tag FROM person_tags WHERE person_id = ? ORDER BY tag", (person_id,))]


def count(db, table):
    return db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


# ── Logging a conversation with someone in the phonebook ─────────────────────


def test_only_the_person_is_needed_it_is_a_call_today_with_no_notes(client, db):
    r = log(client, {"person_id": "bo-diaz"})
    assert r.status_code == 200
    [talk] = talks(db, "bo-diaz")
    assert r.json() == {"person_id": "bo-diaz", "interaction_id": talk["id"]}
    assert (talk["date"], talk["kind"], talk["title"], talk["notes"], talk["next_step"]) == (
        dt.date.today().isoformat(),
        "call",
        None,
        None,
        None,
    )


def test_everything_about_the_talk_can_be_sent(client, db):
    body = {
        "person_id": "ann-lee",
        "kind": "video",
        "date": "2026-10-02",
        "title": "Catch up",
        "summary": "Short version.",
        "notes": "Brain flush.\nShe said the FDE loop is two days.",
        "next_step": "send-resume",
    }
    log(client, body)
    talk = talks(db, "ann-lee")[-1]
    assert {k: talk[k] for k in body if k != "person_id"} == {k: v for k, v in body.items() if k != "person_id"}


def test_an_id_not_in_the_phonebook_is_404_and_no_one_is_added(client, db):
    r = log(client, {"person_id": "ann-le"})
    assert (r.status_code, r.json()["detail"]) == (404, "No one with id ann-le is in your phonebook.")
    assert (count(db, "people"), count(db, "interactions")) == (2, 1)


# ── Logging a conversation with someone new ──────────────────────────────────


def test_someone_new_needs_only_a_name_and_gets_an_id_made_from_it(client, db):
    r = log(client, {"person": {"name": "Zoë O'Brien"}})
    assert r.json()["person_id"] == "zoe-o-brien"
    assert person(db, "zoe-o-brien")["name"] == "Zoë O'Brien"
    assert len(talks(db, "zoe-o-brien")) == 1


def test_someone_new_can_come_with_details_and_tags(client, db):
    body = {
        "person": {
            "name": " Raj Kumar ",
            "company": "Lumen",
            "met_how": "FDE meetup",
            "role": "",
            "tags": ["fde", "fde", " ai "],
        },
        "kind": "coffee",
    }
    raj_id = log(client, body).json()["person_id"]
    raj = person(db, raj_id)
    assert (raj_id, raj["name"], raj["company"], raj["met_how"], raj["role"]) == (
        "raj-kumar",
        "Raj Kumar",
        "Lumen",
        "FDE meetup",
        None,
    )
    assert tags(db, raj_id) == ["ai", "fde"]
    assert talks(db, raj_id)[0]["kind"] == "coffee"


def test_a_second_person_with_a_taken_name_gets_the_next_free_id(client, db):
    assert log(client, {"person": {"name": "Ann Lee"}}).json()["person_id"] == "ann-lee-2"
    assert log(client, {"person": {"name": "ann lee"}}).json()["person_id"] == "ann-lee-3"
    assert person(db, "ann-lee")["company"] == "Acme"  # the first is untouched


def test_a_name_with_no_letters_to_make_an_id_from_is_refused(client, db):
    r = log(client, {"person": {"name": "李"}})
    assert r.status_code == 400 and "English letters" in r.json()["detail"]
    assert count(db, "people") == 2


# ── Adding someone with no conversation ──────────────────────────────────────


def add(client, body):
    return client.post(f"{P}/people", json=body, headers=HEADERS)


def test_adding_someone_needs_only_a_name_and_logs_no_talk(client, db):
    r = add(client, {"name": "Zoë O'Brien"})
    assert (r.status_code, r.json()) == (200, {"person_id": "zoe-o-brien"})
    assert person(db, "zoe-o-brien")["name"] == "Zoë O'Brien"
    assert talks(db, "zoe-o-brien") == []


def test_adding_someone_keeps_their_details_and_tags(client, db):
    body = {
        "name": "Raj Kumar",
        "company": "Lumen",
        "phone": "(555) 010-0000",
        "about": "Friend.",
        "tags": ["fde", " ai ", "fde"],
    }
    raj_id = add(client, body).json()["person_id"]
    raj = person(db, raj_id)
    assert (raj["company"], raj["phone"], raj["about"]) == ("Lumen", "(555) 010-0000", "Friend.")
    assert tags(db, raj_id) == ["ai", "fde"]


def test_adding_a_taken_name_gets_the_next_free_id(client, db):
    assert add(client, {"name": "Ann Lee"}).json()["person_id"] == "ann-lee-2"
    assert person(db, "ann-lee")["company"] == "Acme"


@pytest.mark.parametrize("body", [{}, {"name": ""}, {"name": "Raj", "nickname": "R"}, {"name": "李"}])
def test_a_bad_person_is_refused_and_no_one_is_added(client, db, body):
    assert add(client, body).status_code in (400, 422)
    assert count(db, "people") == 2


@pytest.mark.parametrize(
    "field, value",
    [
        ("linkedin", "javascript:alert(1)"),  # would run when tapped
        ("linkedin", "ftp://linkedin.com/in/raj"),
        ("linkedin", "raj"),
        ("email", "raj"),
        ("email", "raj@example.com?cc=x@evil.example"),
        ("email", "raj @example.com"),
    ],
)
def test_a_link_or_email_that_is_not_one_is_refused(client, db, field, value):
    assert client.post(f"{P}/people", json={"name": "Raj", field: value}, headers=HEADERS).status_code == 422
    assert person(db, "raj") is None


def test_a_linkedin_link_and_an_email_are_kept(client, db):
    body = {"name": "Raj", "linkedin": " https://www.linkedin.com/in/raj ", "email": "raj.k+jobs@example.co.uk"}
    client.post(f"{P}/people", json=body, headers=HEADERS)
    assert (person(db, "raj")["linkedin"], person(db, "raj")["email"]) == (
        "https://www.linkedin.com/in/raj",
        "raj.k+jobs@example.co.uk",
    )


@pytest.mark.parametrize("typed", ["http://linkedin.com/in/raj", "linkedin.com/in/raj"])
def test_a_linkedin_link_typed_without_https_is_saved_with_it(client, db, typed):
    assert client.post(f"{P}/people", json={"name": "Raj", "linkedin": typed}, headers=HEADERS).status_code == 200
    assert person(db, "raj")["linkedin"] == "https://linkedin.com/in/raj"


@pytest.mark.parametrize(
    "name, person_id",
    [
        ("Jane Doe", "jane-doe"),
        ("  Jane   Doe ", "jane-doe"),
        ("José Núñez-Ruiz", "jose-nunez-ruiz"),
        ("Dr. A.B. Smith, Jr.", "dr-a-b-smith-jr"),
        ("x" * 70, "x" * ID_LENGTH),
    ],
)
def test_id_from_name(name, person_id):
    assert id_from_name(name) == person_id


# ── What a conversation must not be ──────────────────────────────────────────


@pytest.mark.parametrize(
    "body",
    [
        {},  # no one
        {"person_id": "ann-lee", "person": {"name": "Ann Lee"}},  # both
        {"person": {}},  # new, no name
        {"person": {"name": "  "}},  # new, blank name
        {"person": {"name": "Cy", "id": "cy"}},  # the id is made, never sent
        {"person": {"name": "Cy", "tags": [" "]}},  # a blank tag
        {"person_id": "Ann Lee"},  # not an id
        {"person_id": "ann-lee", "kind": "lunch"},  # not a kind
        {"person_id": "ann-lee", "next_step": "think about it"},  # not a next step
        {"person_id": "ann-lee", "date": "2026-02-30"},  # not a day
        {"person_id": "ann-lee", "sumary": "typo"},  # not a field
        {"person_id": "ann-lee", "transcript": "x"},  # transcripts come with uploads
        {"person_id": "ann-lee", "notes": "x" * 100_001},
    ],
)
def test_a_bad_conversation_is_refused_and_nothing_is_saved(client, db, body):
    assert log(client, body).status_code == 422
    assert (count(db, "people"), count(db, "interactions")) == (2, 1)


def test_empty_form_fields_are_saved_as_nothing(client, db):
    log(client, {"person_id": "bo-diaz", "title": "  ", "notes": ""})
    [talk] = talks(db, "bo-diaz")
    assert (talk["title"], talk["notes"]) == (None, None)


# ── Editing ──────────────────────────────────────────────────────────────────


def test_editing_a_person_changes_only_what_is_sent(client, db):
    r = client.patch(f"{P}/people/ann-lee", json={"role": "Staff Engineer", "company": None}, headers=HEADERS)
    assert (r.status_code, r.json()) == (200, {"person_id": "ann-lee"})
    ann = person(db, "ann-lee")
    assert (ann["name"], ann["role"], ann["company"]) == ("Ann Lee", "Staff Engineer", None)
    assert tags(db, "ann-lee") == ["mentor"]


def test_tags_sent_replace_theirs(client, db):
    client.patch(f"{P}/people/ann-lee", json={"tags": ["fde", "recruiter"]}, headers=HEADERS)
    assert tags(db, "ann-lee") == ["fde", "recruiter"]
    client.patch(f"{P}/people/ann-lee", json={"tags": []}, headers=HEADERS)
    assert tags(db, "ann-lee") == []


@pytest.mark.parametrize("name", [" ", None])
def test_a_name_cannot_be_cleared(client, db, name):
    assert client.patch(f"{P}/people/ann-lee", json={"name": name}, headers=HEADERS).status_code == 422
    assert person(db, "ann-lee")["name"] == "Ann Lee"


def test_editing_someone_not_there_is_404(client):
    assert client.patch(f"{P}/people/no-one", json={"role": "x"}, headers=HEADERS).status_code == 404


def test_editing_an_interaction_changes_only_what_is_sent(client, db):
    [talk] = talks(db, "ann-lee")
    r = client.patch(
        f"{P}/interactions/{talk['id']}",
        json={"notes": "Forgot: she runs a meetup.", "next_step": None},
        headers=HEADERS,
    )
    assert (r.status_code, r.json()) == (200, {"person_id": "ann-lee", "interaction_id": talk["id"]})
    [after] = talks(db, "ann-lee")
    assert (after["kind"], after["date"], after["notes"], after["next_step"]) == (
        "coffee",
        "2026-05-01",
        "Forgot: she runs a meetup.",
        None,
    )


@pytest.mark.parametrize("body", [{"date": None}, {"kind": None}, {"person_id": "bo-diaz"}, {"transcript": "x"}])
def test_an_interaction_keeps_its_date_kind_person_and_transcript(client, db, body):
    [talk] = talks(db, "ann-lee")
    assert client.patch(f"{P}/interactions/{talk['id']}", json=body, headers=HEADERS).status_code == 422


def test_editing_an_interaction_not_there_is_404(client):
    assert client.patch(f"{P}/interactions/999", json={"title": "x"}, headers=HEADERS).status_code == 404


# ── Saving from an older copy ────────────────────────────────────────────────


def test_an_edit_from_the_version_she_saw_is_saved_and_moves_the_version_on(client, db):
    assert client.patch(f"{P}/people/ann-lee", json={"role": "CTO", "version": 1}, headers=HEADERS).status_code == 200
    assert (person(db, "ann-lee")["role"], person(db, "ann-lee")["version"]) == ("CTO", 2)


def test_changing_only_tags_moves_the_version_on(client, db):
    client.patch(f"{P}/people/ann-lee", json={"tags": ["fde"]}, headers=HEADERS)
    assert person(db, "ann-lee")["version"] == 2


def test_a_person_saved_from_an_older_version_is_refused_and_unchanged(client, db):
    client.patch(f"{P}/people/ann-lee", json={"role": "CTO"}, headers=HEADERS)
    r = client.patch(f"{P}/people/ann-lee", json={"role": "CEO", "tags": [], "version": 1}, headers=HEADERS)
    assert (r.status_code, r.json()["detail"]) == (409, STALE)
    assert (person(db, "ann-lee")["role"], tags(db, "ann-lee")) == ("CTO", ["mentor"])


def test_a_talk_saved_from_an_older_version_is_refused(client, db):
    [talk] = talks(db, "ann-lee")
    client.patch(f"{P}/interactions/{talk['id']}", json={"title": "first", "version": 1}, headers=HEADERS)
    r = client.patch(f"{P}/interactions/{talk['id']}", json={"title": "second", "version": 1}, headers=HEADERS)
    assert r.status_code == 409 and talks(db, "ann-lee")[0]["title"] == "first"


# ── Deleting, with undo ──────────────────────────────────────────────────────


def test_deleting_someone_hides_them_and_keeps_their_talks_and_tags(client, db):
    assert client.delete(f"{P}/people/ann-lee", headers=HEADERS).json() == {"person_id": "ann-lee"}
    assert person(db, "ann-lee")["deleted_on"] == TODAY
    assert (len(talks(db, "ann-lee")), tags(db, "ann-lee")) == (1, ["mentor"])


def test_undo_brings_someone_back(client, db):
    client.delete(f"{P}/people/ann-lee", headers=HEADERS)
    assert client.post(f"{P}/people/ann-lee/restore", headers=HEADERS).json() == {"person_id": "ann-lee"}
    assert person(db, "ann-lee")["deleted_on"] is None


@pytest.mark.parametrize(
    "method, path, body",
    [
        ("patch", "/people/ann-lee", {"role": "x"}),
        ("post", "/interactions", {"person_id": "ann-lee"}),
        ("delete", "/people/ann-lee", None),
    ],
)
def test_someone_deleted_cannot_be_changed_or_talked_to(client, db, method, path, body):
    client.delete(f"{P}/people/ann-lee", headers=HEADERS)
    kwargs = {"json": body} if body is not None else {}
    r = getattr(client, method)(P + path, headers=HEADERS, **kwargs)
    assert r.status_code == 404 and len(talks(db, "ann-lee")) == 1


def test_bringing_back_someone_not_deleted_is_refused(client, db):
    r = client.post(f"{P}/people/ann-lee/restore", headers=HEADERS)
    assert (r.status_code, r.json()["detail"]) == (409, "Ann Lee is not deleted.")


def test_a_deleted_persons_id_stays_taken(client, db):
    client.delete(f"{P}/people/ann-lee", headers=HEADERS)
    assert client.post(f"{P}/people", json={"name": "Ann Lee"}, headers=HEADERS).json() == {"person_id": "ann-lee-2"}


def test_a_talk_can_be_deleted_and_brought_back(client, db):
    [talk] = talks(db, "ann-lee")
    r = client.delete(f"{P}/interactions/{talk['id']}", headers=HEADERS)
    assert r.json() == {"person_id": "ann-lee", "interaction_id": talk["id"]}
    assert talks(db, "ann-lee")[0]["deleted_on"] == TODAY
    assert client.patch(f"{P}/interactions/{talk['id']}", json={"title": "x"}, headers=HEADERS).status_code == 404
    client.post(f"{P}/interactions/{talk['id']}/restore", headers=HEADERS)
    assert talks(db, "ann-lee")[0]["deleted_on"] is None


def test_a_talk_with_someone_deleted_cannot_be_changed(client, db):
    [talk] = talks(db, "ann-lee")
    client.delete(f"{P}/people/ann-lee", headers=HEADERS)
    assert client.patch(f"{P}/interactions/{talk['id']}", json={"title": "x"}, headers=HEADERS).status_code == 404


# ── The schema ───────────────────────────────────────────────────────────────


def test_schema_sql_is_as_new_as_the_newest_migration():
    assert_schema_current(seed.SCHEMA, store.db.migrations)


def test_starting_migrates_a_db_from_before_notes(tmp_path, monkeypatch):
    path = tmp_path / "networking.db"
    old = sqlite3.connect(path)
    schema = seed.SCHEMA.read_text()
    for added in (
        r",\s*notes\s+TEXT",
        r",\s*version\s+INTEGER[^,\n]*",
        r",\s*deleted_on\s+TEXT[^\n]*",
        r"PRAGMA user_version = \d+;",
    ):
        schema = re.sub(added, "", schema)
    old.executescript(schema)
    old.execute("INSERT INTO people (id, name) VALUES ('ann-lee', 'Ann Lee')")
    old.commit()
    old.close()
    monkeypatch.setattr(store.db, "path", path)
    with TestClient(writer.app, base_url=LOCAL):
        pass
    db = sqlite3.connect(path)
    assert db.execute("PRAGMA user_version").fetchone()[0] == 2
    assert {"notes", "version", "deleted_on"} <= {r[1] for r in db.execute("PRAGMA table_info(interactions)")}
    assert db.execute("SELECT version, deleted_on FROM people").fetchone() == (1, None)
    db.close()


@pytest.mark.parametrize("column, allowed", [("kind", writer.Kind), ("next_step", writer.NextStep)])
def test_the_fixed_lists_match_the_schema(column, allowed):
    check = re.search(rf"{column}\s+TEXT[^,]*?CHECK \({column} IN \(([^)]*)\)\)", seed.SCHEMA.read_text()).group(1)
    assert re.findall(r"'([^']+)'", check) == list(typing.get_args(allowed))


def test_fields_json_lists_what_each_request_body_accepts():
    """The page's tests hold every change it sends to this file (web/src/plugins/networking/networking.test.ts)."""
    assert_fields_current(
        Path(writer.__file__).with_name("fields.json"),
        {
            "NewPerson": writer.NewPerson,
            "PersonEdit": writer.PersonEdit,
            "Conversation": writer.Conversation,
            "TalkEdit": writer.TalkEdit,
        },
    )
