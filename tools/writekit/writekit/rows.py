"""
Rows as a writer's records.py changes them: an id made from a name, and an insert or update of
columns from a known list. Column names go into the SQL as text, so a records.py checks them
with check_fields against its own list before calling insert or update.

A versioned table has `version INTEGER NOT NULL DEFAULT 1`, moved on by every change, so a save
made from an older copy of the row is refused instead of writing over a newer one. A table rows
can be deleted from with undo has `deleted_on`: a deleted row is hidden, never removed, and the
read API and records.py leave out rows that have it.
"""

import datetime as dt
import re
import sqlite3
import unicodedata

from .errors import Refused, Rejected

ID_LENGTH = 60  # before a "-2" for a second row of the same name

# A form keeps what you typed when this comes back; reloading would lose it, so it says to copy first.
STALE = (
    "This changed somewhere else since you opened it, so your edit was not saved."
    " Copy what you typed, then reload to see the latest."
)


def id_from_name(name: str) -> str:
    """'Zoë O'Brien' -> 'zoe-o-brien': ASCII letters and digits, lowercase, joined by dashes."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:ID_LENGTH].rstrip("-")
    if not slug:
        raise Rejected(f"An id can't be made from {name!r}. Add the name in English letters.")
    return slug


def free_id(db: sqlite3.Connection, table: str, name: str) -> str:
    """id_from_name(name), with -2, -3... if a row in table already has it."""
    base = id_from_name(name)
    taken = {r[0] for r in db.execute(f"SELECT id FROM {table} WHERE id = ? OR id GLOB ?", (base, f"{base}-[0-9]*"))}
    n = 1
    while (slug := base if n == 1 else f"{base}-{n}") in taken:
        n += 1
    return slug


def check_fields(row: dict, fields: tuple[str, ...]) -> None:
    unknown = set(row) - set(fields)
    if unknown:
        raise ValueError(f"unknown fields {sorted(unknown)}")


def _values(row: dict) -> list:
    return [v.isoformat() if isinstance(v, dt.date) else v for v in row.values()]


def insert(db: sqlite3.Connection, table: str, row: dict) -> int:
    """Inserts row and returns its rowid."""
    cursor = db.execute(f"INSERT INTO {table} ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})", _values(row))
    return cursor.lastrowid


def update(db: sqlite3.Connection, table: str, row_id, changes: dict) -> None:
    """Sets changes on the row with this id. Nothing to change is no query."""
    if changes:
        db.execute(
            f"UPDATE {table} SET {', '.join(f'{c} = ?' for c in changes)} WHERE id = ?", [*_values(changes), row_id]
        )


def update_versioned(db: sqlite3.Connection, table: str, row_id, changes: dict, version: int | None = None) -> None:
    """Sets changes on the row with this id and moves its version on. Given the version the page
    saw, the change is made only if the row is still at it; otherwise it is refused with STALE.
    The caller has checked the row is there."""
    sets = [*(f"{c} = ?" for c in changes), "version = version + 1"]
    check = "" if version is None else " AND version = ?"
    params = [*_values(changes), row_id, *([] if version is None else [version])]
    if db.execute(f"UPDATE {table} SET {', '.join(sets)} WHERE id = ?{check}", params).rowcount == 0:
        raise Refused(STALE)


def set_deleted(db: sqlite3.Connection, table: str, row_id, deleted: bool) -> None:
    """Hides the row (deleted_on today) or brings it back, moving its version on."""
    update_versioned(db, table, row_id, {"deleted_on": dt.date.today() if deleted else None})


def restore(db: sqlite3.Connection, table: str, row: sqlite3.Row, name: str) -> None:
    """Brings back a row set_deleted hid. One that is not hidden is refused, by name ("Acme FDE")."""
    if not row["deleted_on"]:
        raise Refused(f"{name} is not deleted.")
    set_deleted(db, table, row["id"], False)
