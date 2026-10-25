"""
One-time seed of career.db from a hand-written JSON file.

    uv run python seed.py                 # reads CAREER_DIR/seed.json
    uv run python seed.py path/to.json    # refuses if career.db already exists

Writes CAREER_DB (default data/career.db), mode 600. Both live outside
every git repo. This file is code only and never holds data; the shape of the JSON is in
example.json next to it (made-up roles).

career.db is the source of truth, changed only through writer.py. This script is not run again on your data.
"""

import json
import sqlite3
import sys
from pathlib import Path

import store
from writekit.rows import check_fields, insert

SCHEMA = Path(__file__).with_name("schema.sql")


def _columns(db: sqlite3.Connection, table: str) -> tuple[str, ...]:
    """The table's columns as schema.sql defines them, so no field list is kept here."""
    return tuple(row[1] for row in db.execute(f"PRAGMA table_info({table})"))


def seed(db: sqlite3.Connection, data: dict) -> None:
    """data: {"roles": [...]}, the shape of example.json. A bad entry raises with a note naming
    the role it is in."""
    db.executescript(SCHEMA.read_text())
    role_fields = _columns(db, "roles")
    event_fields = tuple(c for c in _columns(db, "events") if c not in ("id", "role_id"))
    for r in data["roles"]:
        try:
            role = {k: v for k, v in r.items() if k != "events"}
            check_fields(role, role_fields)  # a key that is not a column is a typo
            insert(db, "roles", role)
            for e in r.get("events", []):
                check_fields(e, event_fields)
                insert(db, "events", {**e, "role_id": r["id"]})
        except (sqlite3.Error, ValueError) as e:
            e.add_note(f"in role {r.get('id')!r}")
            raise


def main() -> None:
    path = store.db.path
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else store.CAREER_DIR / "seed.json"
    if path.exists():
        sys.exit(f"{path} already exists. It is the source of truth now; not overwriting it.")
    data = json.loads(source.read_text())

    # Private from the first byte: the db and SQLite's journal are created owner-only.
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.touch(mode=0o600)
    db = sqlite3.connect(path)
    try:
        with db:
            seed(db, data)
    except Exception:
        db.close()
        path.unlink()
        raise
    db.close()
    events = sum(len(r.get("events", [])) for r in data["roles"])
    print(f"Wrote {path}: {len(data['roles'])} roles, {events} events.")


if __name__ == "__main__":
    main()
