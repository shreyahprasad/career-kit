"""writekit.rows on a throwaway table."""

import sqlite3

import pytest

from writekit.errors import Refused, Rejected
from writekit.rows import (
    ID_LENGTH,
    STALE,
    check_fields,
    free_id,
    id_from_name,
    insert,
    restore,
    set_deleted,
    update,
    update_versioned,
)


@pytest.fixture
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE things (id TEXT PRIMARY KEY, name TEXT, made_on TEXT)")
    conn.execute("CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT)")
    conn.execute(
        "CREATE TABLE cards (id INTEGER PRIMARY KEY, body TEXT, version INTEGER NOT NULL DEFAULT 1, deleted_on TEXT)"
    )
    yield conn
    conn.close()


@pytest.mark.parametrize(
    "name, slug",
    [
        ("Jane Doe", "jane-doe"),
        ("  Jane   Doe ", "jane-doe"),
        ("José Núñez-Ruiz", "jose-nunez-ruiz"),
        ("Acme, Forward Deployed Engineer", "acme-forward-deployed-engineer"),
        ("x" * 70, "x" * ID_LENGTH),
    ],
)
def test_id_from_name(name, slug):
    assert id_from_name(name) == slug


def test_a_name_with_no_letters_to_make_an_id_from_is_rejected():
    with pytest.raises(Rejected, match="English letters"):
        id_from_name("李")


def test_free_id_adds_the_next_free_number(db):
    assert free_id(db, "things", "Ann Lee") == "ann-lee"
    db.execute("INSERT INTO things (id) VALUES ('ann-lee'), ('ann-lee-2')")
    assert free_id(db, "things", "ann lee") == "ann-lee-3"


def test_free_id_is_not_fooled_by_a_longer_id_that_starts_the_same(db):
    db.execute("INSERT INTO things (id) VALUES ('ann-lee-smith')")
    assert free_id(db, "things", "Ann Lee") == "ann-lee"


def test_insert_returns_the_new_rowid_and_saves_dates_as_text(db):
    import datetime as dt

    note_id = insert(db, "notes", {"body": "hi"})
    insert(db, "things", {"id": "a", "made_on": dt.date(2026, 10, 8)})
    assert db.execute("SELECT body FROM notes WHERE id = ?", (note_id,)).fetchone()[0] == "hi"
    assert db.execute("SELECT made_on FROM things").fetchone()[0] == "2026-10-08"


def test_update_sets_only_what_is_given(db):
    insert(db, "things", {"id": "a", "name": "A", "made_on": "2026-01-01"})
    update(db, "things", "a", {"name": "B"})
    update(db, "things", "a", {})
    assert tuple(db.execute("SELECT name, made_on FROM things").fetchone()) == ("B", "2026-01-01")


def test_check_fields_refuses_a_column_not_on_the_list():
    check_fields({"name": 1}, ("name", "made_on"))
    with pytest.raises(ValueError, match="unknown fields"):
        check_fields({"name": 1, "id; DROP TABLE": 2}, ("name",))


# ── Versions and hiding ──────────────────────────────────────────────────────


def card(db):
    return dict(db.execute("SELECT body, version, deleted_on FROM cards").fetchone())


def test_a_versioned_update_moves_the_version_on(db):
    insert(db, "cards", {"body": "a"})
    update_versioned(db, "cards", 1, {"body": "b"}, version=1)
    update_versioned(db, "cards", 1, {"body": "c"})  # no version sent: no check, still moves on
    assert card(db) == {"body": "c", "version": 3, "deleted_on": None}


def test_an_update_from_an_older_version_is_refused_and_saves_nothing(db):
    insert(db, "cards", {"body": "a", "version": 2})
    with pytest.raises(Refused) as e:
        update_versioned(db, "cards", 1, {"body": "b"}, version=1)
    assert str(e.value) == STALE
    assert card(db) == {"body": "a", "version": 2, "deleted_on": None}


def test_hiding_a_row_marks_it_deleted_today_and_bringing_it_back_clears_it(db):
    import datetime as dt

    insert(db, "cards", {"body": "a"})
    set_deleted(db, "cards", 1, True)
    assert card(db) == {"body": "a", "version": 2, "deleted_on": dt.date.today().isoformat()}
    set_deleted(db, "cards", 1, False)
    assert card(db) == {"body": "a", "version": 3, "deleted_on": None}


def test_restoring_brings_back_a_hidden_row(db):
    insert(db, "cards", {"body": "a"})
    set_deleted(db, "cards", 1, True)
    restore(db, "cards", db.execute("SELECT * FROM cards").fetchone(), "Card 1")
    assert card(db) == {"body": "a", "version": 3, "deleted_on": None}


def test_restoring_a_row_that_is_not_hidden_is_refused_by_its_name(db):
    insert(db, "cards", {"body": "a"})
    with pytest.raises(Refused) as e:
        restore(db, "cards", db.execute("SELECT * FROM cards").fetchone(), "Card 1")
    assert str(e.value) == "Card 1 is not deleted."
    assert card(db) == {"body": "a", "version": 1, "deleted_on": None}
