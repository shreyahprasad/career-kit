"""
The career writer: the only way career.db changes. A separate process from the read-only API in
api/. Built on writekit (docs/writers.md).

    cd tools/career && uv run uvicorn writer:app --host 127.0.0.1 --port 8140

Reached only from this Mac and your tailnet (tailscale serve sends /api/career/write here).

    POST  /postings/read          read a posting from its link, for the add-role form; saves nothing
    POST  /roles                  add a role
    PATCH /roles/{id}             fix a role's details, notes or resume, or approve a draft (which checks
                                  off its review todo); the Career page saves notes here
    POST  /roles/{id}/status      move it on, logging applied, offer or rejection on the timeline;
                                  applying keeps a copy of its resume and approved letter as sent
    POST  /roles/{id}/drafts/{name}/pdf
                                  make the PDF of a draft in data/drafts/<id> (resume-1.md), beside
                                  it; returns its page count. Approving a resume draft makes its PDF
                                  the role's resume, in data/resumes
    POST  /roles/{id}/events      add a recruiter call, interview or note to its timeline
    PATCH /events/{id}            fix a logged event
    DELETE /roles/{id}            delete a role, with undo: POST /roles/{id}/restore
    DELETE /events/{id}           delete an event, with undo: POST /events/{id}/restore
    POST  /todos                  add a todo, for a role or for none
    PATCH /todos/{id}             check it off or open it, or fix its text, kind or day
    DELETE /todos/{id}            delete it, with undo: POST /todos/{id}/restore

An edit or status change may send the version of the row the page saw (Versioned); a row changed
since is refused with 409.
"""

import datetime as dt
import logging
from typing import Annotated, Literal

from pydantic import Field, StrictBool, StringConstraints

import posting
import records
import store
from writekit.app import create_writer
from writekit.forms import (
    MAX_LINE,
    CoverLetterName,
    DraftNamePath,
    Form,
    Line,
    Long,
    PdfName,
    ResumeDraftName,
    Slug,
    SlugPath,
    Versioned,
    WebLink,
)

PREFIX = "/api/career/write"
MAX_BODY_BYTES = 2 * 1024 * 1024  # above the longest body the forms allow, even all in JSON escapes

# The fixed lists in schema.sql's CHECKs (test_writer.py holds them to it).
Status = Literal["interested", "applied", "screen", "interviews", "offer", "rejected"]
Kind = Literal["applied", "recruiter-call", "interview", "offer", "rejection", "note"]
TodoKind = records.TodoKind  # in records.py, which checks the starter todos with it

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_LINE)]
# A PDF in data/resumes, by name only: no folders, nothing hidden.

log = logging.getLogger("uvicorn.error")

# Reading a posting saves nothing, and its answer is long, so it is not kept by Idempotency-Key.
app = create_writer("career", store.db, MAX_BODY_BYTES, reads=[PREFIX + "/postings/read"])


# ── Request bodies ───────────────────────────────────────────────────────────


class RoleDetails(Form):
    """Everything about a role but its company, title, id and status."""

    location: Line = None
    link: WebLink | None = None
    applied_via: WebLink | None = None
    comp: Line = None
    referral_person_id: Slug | None = None
    resume_file: PdfName | None = None
    notes: Long = None
    posting: Long = None  # the posting's text; the writer keeps the day it was saved
    notable: Long = None


class PostingLink(Form):
    link: WebLink


class NewRole(RoleDetails):
    company: Name
    title: Name


class RoleEdit(RoleDetails, Versioned):
    """Only the fields sent change; null clears one. Company and title can change but not be cleared.
    A new role has no drafts yet, so only an edit approves one."""

    company: Name = None  # type: ignore[assignment]  (None only as "not sent"; null is refused)
    title: Name = None  # type: ignore[assignment]
    approved_resume_draft: ResumeDraftName | None = None
    approved_cover_letter: CoverLetterName | None = None


class StatusChange(Versioned):
    """Today, unless sent otherwise. text goes on the event it logs."""

    status: Status
    date: dt.date = Field(default_factory=dt.date.today)
    text: Long = None


class EventFields(Form):
    text: Long = None
    prep_link: Line = None


class NewEvent(EventFields):
    """Today, unless sent otherwise."""

    kind: Kind
    date: dt.date = Field(default_factory=dt.date.today)


class EventEdit(EventFields, Versioned):
    """Only the fields sent change; null clears one. date and kind can change but not be cleared."""

    date: dt.date = None  # type: ignore[assignment]  (None only as "not sent"; null is refused)
    kind: Kind = None  # type: ignore[assignment]


class NewTodo(Form):
    """Open, for the role named or, with none, for your search as a whole."""

    text: Name
    kind: TodoKind = "other"
    role_id: Slug | None = None
    due_on: dt.date | None = None


class TodoEdit(Versioned):
    """Only the fields sent change. done checks it off or opens it; due_on null clears the day.
    A todo stays with its role."""

    text: Name = None  # type: ignore[assignment]  (None only as "not sent"; null is refused)
    kind: TodoKind = None  # type: ignore[assignment]
    due_on: dt.date | None = None
    done: StrictBool = None  # type: ignore[assignment]  (None only as "not sent"; null is refused)


# ── Routes ───────────────────────────────────────────────────────────────────


@app.post(PREFIX + "/postings/read")
def read_posting(body: PostingLink) -> dict:
    """A draft role from the posting at the link (posting.read), for you to check before adding it."""
    log.info("reading a posting at %s", body.link.split("/")[2])
    return posting.read(body.link)


@app.post(PREFIX + "/roles")
def add_role(body: NewRole) -> dict:
    result = records.add_role(body.model_dump(exclude_none=True))
    log.info("added role %s", result["role_id"])
    return result


@app.patch(PREFIX + "/roles/{role_id}")
def edit_role(role_id: SlugPath, body: RoleEdit) -> dict:
    return records.edit_role(role_id, body.model_dump(exclude_unset=True, exclude={"version"}), body.version)


@app.delete(PREFIX + "/roles/{role_id}")
def delete_role(role_id: SlugPath) -> dict:
    result = records.delete_role(role_id)
    log.info("deleted role %s", role_id)
    return result


@app.post(PREFIX + "/roles/{role_id}/restore")
def restore_role(role_id: SlugPath) -> dict:
    result = records.restore_role(role_id)
    log.info("restored role %s", role_id)
    return result


@app.post(PREFIX + "/roles/{role_id}/status")
def set_status(role_id: SlugPath, body: StatusChange) -> dict:
    result = records.set_status(role_id, body.status, body.date.isoformat(), body.text, body.version)
    log.info("%s is now %s", role_id, body.status)
    return result


@app.post(PREFIX + "/roles/{role_id}/drafts/{name}/pdf")
def make_pdf(role_id: SlugPath, name: DraftNamePath) -> dict:
    result = records.make_pdf(role_id, name)
    log.info("made %s for %s, %s pages", result["name"], role_id, result["pages"])
    return result


@app.post(PREFIX + "/roles/{role_id}/events")
def add_event(role_id: SlugPath, body: NewEvent) -> dict:
    return records.add_event(role_id, body.model_dump())


@app.patch(PREFIX + "/events/{event_id}")
def edit_event(event_id: int, body: EventEdit) -> dict:
    return records.edit_event(event_id, body.model_dump(exclude_unset=True, exclude={"version"}), body.version)


@app.delete(PREFIX + "/events/{event_id}")
def delete_event(event_id: int) -> dict:
    return records.delete_event(event_id)


@app.post(PREFIX + "/events/{event_id}/restore")
def restore_event(event_id: int) -> dict:
    return records.restore_event(event_id)


@app.post(PREFIX + "/todos")
def add_todo(body: NewTodo) -> dict:
    return records.add_todo(body.role_id, body.model_dump(exclude={"role_id"}, exclude_none=True))


@app.patch(PREFIX + "/todos/{todo_id}")
def edit_todo(todo_id: int, body: TodoEdit) -> dict:
    return records.edit_todo(
        todo_id, body.model_dump(exclude_unset=True, exclude={"done", "version"}), body.done, body.version
    )


@app.delete(PREFIX + "/todos/{todo_id}")
def delete_todo(todo_id: int) -> dict:
    result = records.delete_todo(todo_id)
    log.info("deleted todo %s", todo_id)
    return result


@app.post(PREFIX + "/todos/{todo_id}/restore")
def restore_todo(todo_id: int) -> dict:
    return records.restore_todo(todo_id)
