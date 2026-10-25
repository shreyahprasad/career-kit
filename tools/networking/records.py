"""
The changes writer.py makes to networking.db: add someone, log a conversation (with someone in the
phonebook or someone new), and edit a person or a conversation. Nothing is guessed: a request names the
person, or says they are new and the id is made from their name.

The page logs; edits are for you, or a chat acting for you, to fix what was saved. Values arrive
checked by writer.py; the schema's CHECKs are the backstop.

An edit can carry the version of the row the page saw; a row changed since is refused rather than
written over. Deleting someone or a talk hides it (deleted_on), so undo brings it back as it was.
Someone deleted, and their talks, cannot be changed until they are back.
"""

import sqlite3

import store
from writekit.errors import NotFound
from writekit.rows import check_fields, free_id, insert, restore, set_deleted, update_versioned

# The columns writer.py may set (check_fields guards them). id and person_id never change: an id
# is the person's page route, made by id_from_name. Transcripts come later, with uploads.
PERSON_FIELDS = ("name", "company", "role", "location", "met_how", "met_on", "linkedin", "email", "phone", "about")
INTERACTION_FIELDS = ("date", "kind", "title", "summary", "notes", "next_step")


def _set_tags(db: sqlite3.Connection, person_id: str, tags: list[str]) -> None:
    db.execute("DELETE FROM person_tags WHERE person_id = ?", (person_id,))
    db.executemany("INSERT INTO person_tags VALUES (?, ?)", [(person_id, t) for t in dict.fromkeys(tags)])


def _require_person(db: sqlite3.Connection, person_id: str, deleted: bool = False) -> sqlite3.Row:
    """The person, if they are there and not deleted; with deleted=True, deleted ones too."""
    row = db.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
    if row is None or (row["deleted_on"] and not deleted):
        raise NotFound(f"No one with id {person_id} is in your phonebook.")
    return row


def _require_interaction(db: sqlite3.Connection, interaction_id: int, deleted: bool = False) -> sqlite3.Row:
    """The talk, if it and its person are there and not deleted; with deleted=True, a deleted talk too."""
    row = db.execute(
        "SELECT i.*, p.deleted_on AS person_deleted_on"
        " FROM interactions i JOIN people p ON p.id = i.person_id WHERE i.id = ?",
        (interaction_id,),
    ).fetchone()
    if row is None or row["person_deleted_on"] or (row["deleted_on"] and not deleted):
        raise NotFound(f"No interaction {interaction_id}.")
    return row


def _insert_person(db: sqlite3.Connection, new_person: dict) -> str:
    """Adds new_person (PERSON_FIELDS with name, and tags) under an id made from the name."""
    person = dict(new_person)
    tags = person.pop("tags", None) or []
    check_fields(person, PERSON_FIELDS)
    person_id = free_id(db, "people", person["name"])
    insert(db, "people", {"id": person_id, **person})
    _set_tags(db, person_id, tags)
    return person_id


def add_person(new_person: dict) -> dict:
    """Adds someone with no conversation. Returns their id."""
    with store.db.change("add-person") as db:
        person_id = _insert_person(db, new_person)
    return {"person_id": person_id}


def log_conversation(interaction: dict, *, person_id: str | None = None, new_person: dict | None = None) -> dict:
    """Logs one interaction (INTERACTION_FIELDS) with exactly one of: person_id, someone in the
    phonebook; or new_person (PERSON_FIELDS with name, and tags), added first. Returns both ids."""
    if (person_id is None) == (new_person is None):
        raise ValueError("log_conversation takes person_id or new_person, not both or neither")
    check_fields(interaction, INTERACTION_FIELDS)
    with store.db.change(f"log-{person_id or 'new-person'}") as db:
        if new_person is not None:
            person_id = _insert_person(db, new_person)
        else:
            _require_person(db, person_id)
        interaction_id = insert(db, "interactions", {"person_id": person_id, **interaction})
    return {"person_id": person_id, "interaction_id": interaction_id}


def edit_person(person_id: str, changes: dict, version: int | None = None) -> dict:
    """Sets the PERSON_FIELDS in changes; tags, when in it, replace theirs. Either moves their version on."""
    changes = dict(changes)
    tags = changes.pop("tags", None)
    check_fields(changes, PERSON_FIELDS)
    with store.db.change(f"edit-{person_id}") as db:
        _require_person(db, person_id)
        update_versioned(db, "people", person_id, changes, version)
        if tags is not None:
            _set_tags(db, person_id, tags)
    return {"person_id": person_id}


def delete_person(person_id: str) -> dict:
    """Hides them, with their talks and tags, until restore_person."""
    with store.db.change(f"delete-{person_id}") as db:
        _require_person(db, person_id)
        set_deleted(db, "people", person_id, True)
    return {"person_id": person_id}


def restore_person(person_id: str) -> dict:
    with store.db.change(f"restore-{person_id}") as db:
        row = _require_person(db, person_id, deleted=True)
        restore(db, "people", row, row["name"])
    return {"person_id": person_id}


def edit_interaction(interaction_id: int, changes: dict, version: int | None = None) -> dict:
    """Sets the INTERACTION_FIELDS in changes."""
    check_fields(changes, INTERACTION_FIELDS)
    with store.db.change(f"edit-interaction-{interaction_id}") as db:
        row = _require_interaction(db, interaction_id)
        update_versioned(db, "interactions", interaction_id, changes, version)
    return {"person_id": row["person_id"], "interaction_id": interaction_id}


def delete_interaction(interaction_id: int) -> dict:
    """Hides the talk until restore_interaction."""
    with store.db.change(f"delete-interaction-{interaction_id}") as db:
        row = _require_interaction(db, interaction_id)
        set_deleted(db, "interactions", interaction_id, True)
    return {"person_id": row["person_id"], "interaction_id": interaction_id}


def restore_interaction(interaction_id: int) -> dict:
    with store.db.change(f"restore-interaction-{interaction_id}") as db:
        row = _require_interaction(db, interaction_id, deleted=True)
        restore(db, "interactions", row, f"Interaction {interaction_id}")
    return {"person_id": row["person_id"], "interaction_id": interaction_id}
