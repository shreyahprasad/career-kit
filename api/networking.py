"""
Networking: the people you know, and every time they talked.

Reads networking.db (schema: tools/networking/schema.sql), opened read-only. Dates are YYYY-MM-DD.
The list carries only dates and kinds per interaction, enough for the phonebook and the
timeline; summaries, notes and transcripts come with one person. Changes go through the
networking writer (tools/networking/writer.py), never here. Rows deleted with undo (deleted_on) are
left out everywhere; someone deleted takes their talks with them. version goes to the page with
each row it can edit, and comes back with the edit.
"""

import os
import sqlite3
from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, HTTPException

from readonly import open_readonly
from writekit.forms import SlugPath

NETWORKING_DB = Path(os.environ.get("NETWORKING_DB", Path(__file__).resolve().parents[1] / "data/networking.db"))

router = APIRouter(prefix="/api/networking")


# What the list shows of everyone; one person's detail has every column.
LIST_FIELDS = ("id", "name", "company", "role", "location")


def connect():
    return open_readonly(NETWORKING_DB, "networking.db not found. Run ./setup.sh.")


def _tags(db: sqlite3.Connection, person_id: str | None) -> dict[str, list[str]]:
    by_person = defaultdict(list)
    for row in db.execute(
        "SELECT person_id, tag FROM person_tags WHERE :id IS NULL OR person_id = :id ORDER BY tag",
        {"id": person_id},
    ):
        by_person[row["person_id"]].append(row["tag"])
    return by_person


@router.get("/people")
def people() -> dict:
    """Everyone, by name, with their tags, the date and kind of each interaction (oldest first),
    and their open next step: the one on their latest interaction, or null."""
    with connect() as db:
        tags = _tags(db, None)
        talks = defaultdict(list)
        next_step: dict[str, str | None] = {}
        for row in db.execute(
            "SELECT person_id, date, kind, next_step FROM interactions WHERE deleted_on IS NULL ORDER BY date, id"
        ):
            talks[row["person_id"]].append({"date": row["date"], "kind": row["kind"]})
            next_step[row["person_id"]] = row["next_step"]  # the last row wins: the latest
        rows = db.execute(
            f"SELECT {', '.join(LIST_FIELDS)} FROM people WHERE deleted_on IS NULL ORDER BY name COLLATE NOCASE"
        ).fetchall()

    return {
        "people": [
            {**dict(r), "tags": tags[r["id"]], "interactions": talks[r["id"]], "next_step": next_step.get(r["id"])}
            for r in rows
        ]
    }


@router.get("/people/{person_id}")
def person(person_id: SlugPath) -> dict:
    """One person with every interaction in full, newest first."""
    with connect() as db:
        row = db.execute(
            "SELECT p.*, c.website AS company_website FROM people p "
            "LEFT JOIN companies c ON c.name = p.company WHERE p.id = ? AND p.deleted_on IS NULL",
            (person_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(404, f"No one with id {person_id}.")
        interactions = [
            dict(r)
            for r in db.execute(
                "SELECT id, date, kind, title, summary, notes, next_step, transcript, version FROM interactions "
                "WHERE person_id = ? AND deleted_on IS NULL ORDER BY date DESC, id DESC",
                (person_id,),
            )
        ]
        tags = _tags(db, person_id)[person_id]
    detail = dict(row)
    del detail["deleted_on"]
    return {**detail, "tags": tags, "interactions": interactions}
