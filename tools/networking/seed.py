# /// script
# requires-python = ">=3.14,<3.15"
# dependencies = []
# ///
"""
One-time seed of networking.db from a hand-written JSON file.

    uv run tools/networking/seed.py                 # reads NETWORKING_DIR/seed.json
    uv run tools/networking/seed.py path/to.json    # refuses if networking.db already exists

Writes NETWORKING_DIR/networking.db (SQLite, mode 600), default data/ in this repo.
Both live outside every git repo. This file is code only and never holds data; the shape of
the JSON is in example.json next to it (made-up people).

networking.db is the source of truth, changed only through writer.py. This script is not run again on your data.
"""

import json
import os
import sqlite3
import sys
from pathlib import Path

NETWORKING_DIR = Path(os.environ.get("NETWORKING_DIR", Path(__file__).resolve().parents[2] / "data"))
DB_PATH = NETWORKING_DIR / "networking.db"
SCHEMA = Path(__file__).with_name("schema.sql")


def _columns(db: sqlite3.Connection, table: str) -> list[str]:
    """The table's columns as schema.sql defines them, so no field list is kept here."""
    return [row[1] for row in db.execute(f"PRAGMA table_info({table})")]


def _insert(
    db: sqlite3.Connection, table: str, row: dict, fields: list[str], nested: frozenset[str] = frozenset()
) -> None:
    """Insert `row`'s fields; a key that is not a field (or a known nested list) is a typo."""
    unknown = set(row) - set(fields) - nested
    if unknown:
        raise ValueError(f"unknown fields {sorted(unknown)}")
    values = {f: row[f] for f in fields if f in row}
    db.execute(
        f"INSERT INTO {table} ({', '.join(values)}) VALUES ({', '.join('?' * len(values))})", list(values.values())
    )


def seed(db: sqlite3.Connection, data: dict) -> None:
    """data: {"companies": {name: website}, "people": [...]}, the shape of example.json.
    A bad entry raises with a note naming the person it is in."""
    db.executescript(SCHEMA.read_text())
    person_fields = _columns(db, "people")
    interaction_fields = [c for c in _columns(db, "interactions") if c != "id"]
    db.executemany("INSERT INTO companies VALUES (?, ?)", data.get("companies", {}).items())
    for p in data["people"]:
        try:
            _insert(db, "people", p, person_fields, nested=frozenset({"tags", "interactions"}))
            db.executemany("INSERT INTO person_tags VALUES (?, ?)", [(p["id"], t) for t in p.get("tags", [])])
            for i in p.get("interactions", []):
                _insert(db, "interactions", {**i, "person_id": p["id"]}, interaction_fields)
        except (sqlite3.Error, ValueError) as e:
            e.add_note(f"in person {p.get('id')!r}")
            raise


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else NETWORKING_DIR / "seed.json"
    if DB_PATH.exists():
        sys.exit(f"{DB_PATH} already exists. It is the source of truth now; not overwriting it.")
    data = json.loads(source.read_text())
    people = data["people"]

    # Private from the first byte: the folder, the db and SQLite's journal are created owner-only.
    os.umask(0o077)
    NETWORKING_DIR.mkdir(parents=True, exist_ok=True)
    NETWORKING_DIR.chmod(0o700)
    db = sqlite3.connect(DB_PATH)
    try:
        with db:
            seed(db, data)
    except Exception:
        db.close()
        DB_PATH.unlink()
        raise
    db.close()
    count = sum(len(p.get("interactions", [])) for p in people)
    print(f"Wrote {DB_PATH}: {len(people)} people, {count} interactions.")


if __name__ == "__main__":
    main()
