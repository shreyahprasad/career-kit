"""
The networking writer: the only way networking.db changes. A separate process from the read-only
API in api/. Built on writekit (docs/writers.md).

    cd tools/networking && uv run uvicorn writer:app --host 127.0.0.1 --port 8120

Reached only from this Mac and your tailnet (tailscale serve sends /api/networking/write here).

    POST  /people                    add someone, with no talk
    POST  /interactions              log a talk (an interaction); the Networking page uses this
    PATCH /people/{id}               fix a person's details or tags
    PATCH /interactions/{id}         fix a logged talk
    DELETE /people/{id}              delete someone, with undo: POST /people/{id}/restore
    DELETE /interactions/{id}        delete a talk, with undo: POST /interactions/{id}/restore

An edit may send the version of the row the page saw (Versioned); a row changed since is refused
with 409.
"""

import datetime as dt
import logging
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

import records
import store
from writekit.app import create_writer
from writekit.forms import MAX_LINE, Form, Line, Long, OptionalEmail, OptionalWebLink, Slug, SlugPath, Versioned

PREFIX = "/api/networking/write"
MAX_BODY_BYTES = 2 * 1024 * 1024  # above the longest body the forms allow, even all in JSON escapes

# The fixed lists in schema.sql's CHECKs (test_writer.py holds them to it).
Kind = Literal["call", "video", "coffee", "event", "message", "email"]
NextStep = Literal["follow-up", "reach-out", "catch-up", "send-resume", "ask-intro", "schedule", "share-work"]

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_LINE)]
Tag = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]

log = logging.getLogger("uvicorn.error")

app = create_writer("networking", store.db, MAX_BODY_BYTES)


# ── Request bodies ───────────────────────────────────────────────────────────


class PersonDetails(Form):
    """Everything about a person but their name and id."""

    company: Line = None
    role: Line = None
    location: Line = None
    met_how: Line = None
    met_on: dt.date | None = None
    linkedin: OptionalWebLink = None
    email: OptionalEmail = None
    phone: Line = None
    about: Long = None
    tags: Annotated[list[Tag], Field(max_length=20)] | None = None


class NewPerson(PersonDetails):
    """Someone to add. Only the name is needed; the id is made from it."""

    name: Name


class PersonEdit(PersonDetails, Versioned):
    """Only the fields sent change; null clears one. A name can change but not be cleared."""

    name: Name = None  # type: ignore[assignment]  (None only as "not sent"; null is refused)


class TalkFields(Form):
    title: Line = None
    summary: Long = None
    notes: Long = None
    next_step: NextStep | None = None


class Conversation(TalkFields):
    """One talk, with someone in the phonebook (person_id) or someone new (person): exactly one.
    A call, today, unless sent otherwise."""

    person_id: Slug | None = None
    person: NewPerson | None = None
    date: dt.date = Field(default_factory=dt.date.today)
    kind: Kind = "call"

    @model_validator(mode="after")
    def one_person(self):
        if (self.person_id is None) == (self.person is None):
            raise ValueError(
                "send person_id for someone in the phonebook or person for someone new, not both or neither"
            )
        return self


class TalkEdit(TalkFields, Versioned):
    """Only the fields sent change; null clears one. date and kind can change but not be cleared."""

    date: dt.date = None  # type: ignore[assignment]  (None only as "not sent"; null is refused)
    kind: Kind = None  # type: ignore[assignment]


# ── Routes ───────────────────────────────────────────────────────────────────


@app.post(PREFIX + "/people")
def add_person(body: NewPerson) -> dict:
    result = records.add_person(body.model_dump(exclude_none=True))
    log.info("added %s", result["person_id"])
    return result


@app.post(PREFIX + "/interactions")
def log_conversation(body: Conversation) -> dict:
    """Logs a talk, adding the person first if they are new. Returns their id and the talk's."""
    result = records.log_conversation(
        body.model_dump(exclude={"person_id", "person"}),
        person_id=body.person_id,
        new_person=body.person.model_dump(exclude_none=True) if body.person else None,
    )
    log.info(
        "logged interaction %s with %s%s",
        result["interaction_id"],
        result["person_id"],
        " (new)" if body.person else "",
    )
    return result


@app.patch(PREFIX + "/people/{person_id}")
def edit_person(person_id: SlugPath, body: PersonEdit) -> dict:
    return records.edit_person(person_id, body.model_dump(exclude_unset=True, exclude={"version"}), body.version)


@app.delete(PREFIX + "/people/{person_id}")
def delete_person(person_id: SlugPath) -> dict:
    result = records.delete_person(person_id)
    log.info("deleted %s", person_id)
    return result


@app.post(PREFIX + "/people/{person_id}/restore")
def restore_person(person_id: SlugPath) -> dict:
    result = records.restore_person(person_id)
    log.info("restored %s", person_id)
    return result


@app.patch(PREFIX + "/interactions/{interaction_id}")
def edit_interaction(interaction_id: int, body: TalkEdit) -> dict:
    return records.edit_interaction(
        interaction_id, body.model_dump(exclude_unset=True, exclude={"version"}), body.version
    )


@app.delete(PREFIX + "/interactions/{interaction_id}")
def delete_interaction(interaction_id: int) -> dict:
    return records.delete_interaction(interaction_id)


@app.post(PREFIX + "/interactions/{interaction_id}/restore")
def restore_interaction(interaction_id: int) -> dict:
    return records.restore_interaction(interaction_id)
