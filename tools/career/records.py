"""
The changes writer.py makes to career.db: add a role, edit it, change its status, add or fix
what happened on its timeline, and keep your todos. Nothing is guessed: a request names the role, and the new id is
made from the company and title.

A change can carry the version of the row the page saw; a row changed since is refused rather
than written over. Deleting a role, an event or a todo hides it (deleted_on), so undo brings it
back as it was. A deleted role, and everything on it, cannot be changed until it is back, and
adding it again is refused with the way back (Recently deleted on the Career page).

Applying, an offer and a rejection are status changes, and each logs its event on the timeline
in the same change, so the status and the timeline never disagree. Values arrive checked by
writer.py; the schema's CHECKs are the backstop.
"""

import datetime as dt
import json
import os
import shutil
import sqlite3
import uuid
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, StrictInt, StringConstraints, ValidationError

import render
import store
from writekit.errors import NotFound, Refused, Rejected
from writekit.files import file_in
from writekit.forms import MAX_LINE, Form
from writekit.rows import check_fields, free_id, insert, restore, set_deleted, update, update_versioned

# The columns writer.py may set (check_fields guards them). id and role_id never change: an id is
# the role's page route. Status changes only through set_status, and sent_file and
# sent_cover_letter with it; posting_on only with the posting (_with_posting_day).
ROLE_FIELDS = (
    "company",
    "title",
    "location",
    "link",
    "applied_via",
    "comp",
    "referral_person_id",
    "resume_file",
    "notes",
    "posting",
    "notable",
    "approved_resume_draft",
    "approved_cover_letter",
)

# Approving a draft checks off the todo to review it, which the drafting skills add by this text.
REVIEW_TODO = {"approved_resume_draft": "Review resume draft", "approved_cover_letter": "Review cover letter"}
EVENT_FIELDS = ("date", "kind", "text", "prep_link")
TODO_FIELDS = ("text", "kind", "due_on")

# The kinds of todo in schema.sql's CHECK (test_writer.py holds it to it).
TodoKind = Literal["resume", "apply", "outreach", "prep", "follow-up", "other"]

# What every new role starts with, in this order: config/starter-todos.json, which each copy of
# career-kit makes its own, or CAREER_STARTER_TODOS. Read on every add, so an edit needs no restart.
DEFAULT_STARTER_TODOS = Path(__file__).resolve().parents[2] / "config/starter-todos.json"
MAX_DUE_IN_DAYS = 365
# A resume is sent as one page; a draft that runs over gets no PDF, so it can never be approved.
MAX_RESUME_PAGES = 1


class StarterTodo(Form):
    """One entry in the starter todos file. due_in_days 0 is the day the role is added."""

    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_LINE)]
    kind: TodoKind
    due_in_days: Annotated[StrictInt, Field(ge=0, le=MAX_DUE_IN_DAYS)]


def starter_todos() -> list[StarterTodo]:
    """The starter todos file, checked. A file that does not parse, or an entry that breaks a
    rule, refuses the add with the file and the entry named, so it can be fixed."""
    path = Path(os.environ.get("CAREER_STARTER_TODOS", DEFAULT_STARTER_TODOS))
    try:
        entries = json.loads(path.read_text())
    except FileNotFoundError:
        raise Refused(f"{path} is missing. It lists the todos a new role starts with; [] means none.") from None
    except json.JSONDecodeError as e:
        raise Refused(f"{path} is not valid JSON (line {e.lineno}): {e.msg}.") from None
    if not isinstance(entries, list):
        raise Refused(f"{path} must be a list of todos, like [] for none.")
    todos = []
    for number, entry in enumerate(entries, 1):
        try:
            todos.append(StarterTodo.model_validate(entry))
        except ValidationError as e:
            error = e.errors()[0]
            field = ".".join(str(part) for part in error["loc"]) or "the entry"
            raise Refused(f"{path}, todo {number}: {field}: {error['msg']}.") from None
    return todos


# The statuses that are an event on the timeline, and that event's kind.
STATUS_EVENT = {"applied": "applied", "offer": "offer", "rejected": "rejection"}


def _require_role(db: sqlite3.Connection, role_id: str, deleted: bool = False) -> sqlite3.Row:
    """The role, if it is there and not deleted; with deleted=True, deleted ones too."""
    row = db.execute("SELECT * FROM roles WHERE id = ?", (role_id,)).fetchone()
    if row is None or (row["deleted_on"] and not deleted):
        raise NotFound(f"No role {role_id}.")
    return row


def _require_event(db: sqlite3.Connection, event_id: int, deleted: bool = False) -> sqlite3.Row:
    """The event, if it and its role are there and not deleted; with deleted=True, a deleted event too."""
    row = db.execute(
        "SELECT e.*, r.deleted_on AS role_deleted_on FROM events e JOIN roles r ON r.id = e.role_id WHERE e.id = ?",
        (event_id,),
    ).fetchone()
    if row is None or row["role_deleted_on"] or (row["deleted_on"] and not deleted):
        raise NotFound(f"No event {event_id}.")
    return row


def _resume(name: str) -> Path:
    """The PDF in resumes/ by that name. writer.py has checked it is a plain PDF name. A link out
    of resumes/ is not followed, as in the read API."""
    path = file_in(store.resumes(), name)
    if path is None:
        raise Refused(f"There is no {name} in data/resumes.")
    return path


def _draft(role_id: str, name: str) -> Path:
    """The draft in drafts/<role>/ by that name. writer.py has checked it is a plain draft name. A
    link out of drafts/<role>/ is not followed, as in the read API."""
    path = file_in(store.drafts(role_id), name)
    if path is None:
        raise Refused(f"There is no {name} in data/drafts/{role_id}.")
    return path


def _copy_read_only(source: Path, copy: Path) -> None:
    """Copies source to copy, read-only. Raises FileExistsError rather than write over a file."""
    with open(copy, "xb") as out:
        try:
            with open(source, "rb") as original:
                shutil.copyfileobj(original, out)
            copy.chmod(0o444)
        except BaseException:
            copy.unlink(missing_ok=True)
            raise


def _stage_sent(staged: list[Path], source: Path) -> Path:
    """A read-only copy of source in sent/ under a hidden temporary name, made before the change
    that keeps it, so the copying is done outside the write lock. Added to staged, for the caller
    to remove whatever happens."""
    folder = store.sent()
    folder.mkdir(mode=0o700, exist_ok=True)
    staged.append(folder / f".{uuid.uuid4().hex}.part")
    _copy_read_only(source, staged[-1])
    return staged[-1]


def _keep_sent(role_id: str, staged: Path, date: str, ending: str = ".pdf", pdf: Path | None = None) -> list[str]:
    """Gives a staged copy its name in sent/, <role>-<date><ending> (then -2, -3 on the same day
    before the ending), never over an earlier copy, and a staged pdf the same name ending in .pdf.
    Returns the names, the copy's first. A hard link makes the name, so a name taken meanwhile is
    never written over; the staged file itself is removed by the caller."""
    folder = store.sent()
    n = 1
    while True:
        name = f"{role_id}-{date}{f'-{n}' if n > 1 else ''}{ending}"
        n += 1
        try:
            os.link(staged, folder / name)
        except FileExistsError:
            continue
        if pdf is None:
            return [name]
        pdf_name = Path(name).with_suffix(".pdf").name
        try:
            os.link(pdf, folder / pdf_name)
        except FileExistsError:
            (folder / name).unlink()
            continue
        return [name, pdf_name]


def _draft_pdf(role_id: str, name: str) -> Path:
    """The PDF of the draft by that name, made first if there is none or the draft changed since."""
    draft = _draft(role_id, name)
    pdf = draft.with_suffix(".pdf")
    if not (pdf.is_file() and not pdf.is_symlink() and pdf.stat().st_mtime >= draft.stat().st_mtime):
        make_pdf(role_id, name)
    return pdf


def make_pdf(role_id: str, name: str) -> dict:
    """Lays out drafts/<role>/<name> as <name>.pdf beside it (render.py), replacing that draft's
    older PDF and nothing else. Returns the PDF's name and its page count. A resume over one page
    is refused, saying about how far it runs over."""
    with store.db.reading() as db:
        _require_role(db, role_id)
    draft = _draft(role_id, name)
    kind = "resume" if name.startswith("resume-") else "cover-letter"
    try:
        pdf, pages, last_page_lines = render.render(draft.read_text(errors="replace"), kind)
    except render.RenderError as e:
        raise Refused(str(e)) from None
    if kind == "resume" and pages > MAX_RESUME_PAGES:
        over = (
            f"about {last_page_lines} line{'s' * (last_page_lines != 1)} over"
            if pages == MAX_RESUME_PAGES + 1
            else f"{pages} pages"
        )
        raise Refused(f"{name} runs over one page ({over}), so it has no PDF. Shorten it and make the PDF again.")
    # Written beside it under a temporary name, then renamed over the old one, so the page never
    # reads half a PDF, and a link where the PDF goes is replaced, not followed.
    target = draft.with_suffix(".pdf")
    part = target.with_name(f".{target.name}.part")
    part.unlink(missing_ok=True)  # a file or link left there is removed, never written through
    with open(part, "xb") as out:
        out.write(pdf)
    os.replace(part, target)
    return {"role_id": role_id, "name": target.name, "pages": pages}


def _attach_resume(role_id: str, pdf: Path) -> tuple[str, bool]:
    """Copies an approved resume draft's PDF into resumes/ as <role>-<draft>.pdf, or -2, -3 when
    that name holds a different file. Returns the name and whether the copy is new."""
    folder = store.resumes()
    folder.mkdir(mode=0o700, exist_ok=True)
    data = pdf.read_bytes()
    n = 1
    while True:
        name = f"{role_id}-{pdf.stem}{f'-{n}' if n > 1 else ''}.pdf"
        path = folder / name
        try:
            with open(path, "xb") as out:
                out.write(data)
            return name, True
        except FileExistsError:
            if path.is_file() and not path.is_symlink() and path.read_bytes() == data:
                return name, False
            n += 1


def _with_posting_day(fields: dict) -> dict:
    """fields, and when they set the posting, the day it was saved (none when it is cleared)."""
    if "posting" not in fields:
        return fields
    return {**fields, "posting_on": dt.date.today().isoformat() if fields["posting"] else None}


def add_role(fields: dict) -> dict:
    """Adds a role (ROLE_FIELDS, with company and title), interested, with the starter todos.
    Returns its id."""
    check_fields(fields, ROLE_FIELDS)
    starters = starter_todos()
    if fields.get("resume_file"):
        _resume(fields["resume_file"])
    with store.db.change("add-role") as db:
        name = f"{fields['company']} {fields['title']}"
        deleted = db.execute(
            "SELECT company, title, deleted_on FROM roles"
            " WHERE deleted_on IS NOT NULL AND company = ? COLLATE NOCASE AND title = ? COLLATE NOCASE",
            (fields["company"], fields["title"]),
        ).fetchone()
        if deleted:
            day = dt.date.fromisoformat(deleted["deleted_on"])
            raise Refused(
                f"You deleted {deleted['company']} {deleted['title']} on {day:%b} {day.day}."
                " Bring it back from Recently deleted on the Career page."
            )
        role_id = free_id(db, "roles", name)
        insert(db, "roles", {"id": role_id, **_with_posting_day(fields)})
        for todo in starters:
            due_on = (dt.date.today() + dt.timedelta(days=todo.due_in_days)).isoformat()
            insert(db, "todos", {"role_id": role_id, "text": todo.text, "kind": todo.kind, "due_on": due_on})
    return {"role_id": role_id}


def edit_role(role_id: str, changes: dict, version: int | None = None) -> dict:
    """Sets the ROLE_FIELDS in changes. A resume must be in resumes/, and an approved draft in
    drafts/<role>/. Approving a draft also checks off its open review todo, and approving a
    resume draft copies its PDF (made first if need be) into resumes/ and makes it the role's
    resume, in the same change."""
    check_fields(changes, ROLE_FIELDS)
    if changes.get("approved_resume_draft") and "resume_file" in changes:
        raise Rejected("Approving a resume draft makes its PDF the role's resume. Send one or the other.")
    if changes.get("resume_file"):
        _resume(changes["resume_file"])
    approved = [field for field in REVIEW_TODO if changes.get(field)]
    for field in approved:
        _draft(role_id, changes[field])
    pdf = changes.get("approved_resume_draft") and _draft_pdf(role_id, changes["approved_resume_draft"])
    copied = None
    try:
        with store.db.change(f"edit-{role_id}") as db:
            _require_role(db, role_id)
            update_versioned(db, "roles", role_id, _with_posting_day(changes), version)
            for field in approved:
                db.execute(
                    "UPDATE todos SET done_on = ?, version = version + 1"
                    " WHERE role_id = ? AND text = ? AND done_on IS NULL AND deleted_on IS NULL",
                    (dt.date.today().isoformat(), role_id, REVIEW_TODO[field]),
                )
            # Last, after every check: a refused change must leave no copy in resumes/.
            if pdf:
                name, new = _attach_resume(role_id, pdf)
                copied = name if new else None
                update(db, "roles", role_id, {"resume_file": name})
    except BaseException:
        if copied:
            (store.resumes() / copied).unlink(missing_ok=True)
        raise
    return {"role_id": role_id}


def delete_role(role_id: str) -> dict:
    """Hides the role, with its timeline and todos, until restore_role."""
    with store.db.change(f"delete-{role_id}") as db:
        _require_role(db, role_id)
        set_deleted(db, "roles", role_id, True)
    return {"role_id": role_id}


def restore_role(role_id: str) -> dict:
    with store.db.change(f"restore-{role_id}") as db:
        role = _require_role(db, role_id, deleted=True)
        restore(db, "roles", role, f"{role['company']} {role['title']}")
    return {"role_id": role_id}


def set_status(role_id: str, status: str, date: str, text: str | None, version: int | None = None) -> dict:
    """Moves the role to status. Applied, offer and rejected also log their event on date, with
    text; the others log nothing, so text with them is refused rather than lost. Applying also
    keeps a copy of the role's resume and of its approved cover letter in sent/, so the role
    always shows what that company got; with none chosen or approved, there is none of it. The
    letter is kept as text and as its PDF (made first if need be), under the same name but for
    the ending; sent_cover_letter names the text.

    The slow part, making the letter's PDF (up to render.TIMEOUT_SECONDS) and copying the files,
    is done before the change, so no other change waits on it. The copies get their names in the
    change, and are removed if it is refused or fails, so sent/ never keeps a copy of a change that
    was not saved."""
    kind = STATUS_EVENT.get(status)
    if kind is None and text is not None:
        raise Rejected(
            f"Moving to {status} logs nothing on the timeline."
            " Add what happened as a recruiter call, an interview or a note."
        )
    with store.db.reading() as db:
        role = _require_role(db, role_id)
    if role["status"] == status:
        raise Refused(f"{role['company']} {role['title']} is already {status}.")
    applying = status == "applied"
    resume_name = role["resume_file"] if applying else None
    letter_name = role["approved_cover_letter"] if applying else None
    resume = resume_name and _resume(resume_name)
    letter = letter_name and _draft(role_id, letter_name)
    letter_pdf = letter_name and _draft_pdf(role_id, letter_name)
    staged: list[Path] = []
    kept: list[str] = []
    try:
        resume_copy = resume and _stage_sent(staged, resume)
        letter_copy = letter and _stage_sent(staged, letter)
        letter_pdf_copy = letter_pdf and _stage_sent(staged, letter_pdf)
        with store.db.change(f"status-{role_id}-{status}") as db:
            role = _require_role(db, role_id)
            if role["status"] == status:
                raise Refused(f"{role['company']} {role['title']} is already {status}.")
            if applying and (role["resume_file"], role["approved_cover_letter"]) != (resume_name, letter_name):
                raise Refused(
                    f"The resume or cover letter for {role['company']} {role['title']} changed just now."
                    " Nothing was saved; try again."
                )
            # The version check first: a refused change must leave no sent copy behind.
            update_versioned(db, "roles", role_id, {"status": status}, version)
            if applying:
                sent = {"sent_file": None, "sent_cover_letter": None}
                if resume_copy:
                    names = _keep_sent(role_id, resume_copy, date)
                    kept += names
                    sent["sent_file"] = names[0]
                if letter_copy:
                    names = _keep_sent(role_id, letter_copy, date, "-cover-letter.md", letter_pdf_copy)
                    kept += names
                    sent["sent_cover_letter"] = names[0]
                update(db, "roles", role_id, sent)
            event_id = (
                insert(db, "events", {"role_id": role_id, "date": date, "kind": kind, "text": text}) if kind else None
            )
    except BaseException:
        for name in kept:
            (store.sent() / name).unlink(missing_ok=True)
        raise
    finally:
        for path in staged:
            path.unlink(missing_ok=True)
    return {"role_id": role_id, "event_id": event_id}


def add_event(role_id: str, event: dict) -> dict:
    """Adds an event (EVENT_FIELDS) to the role's timeline. The kinds a status change logs come
    only from set_status."""
    check_fields(event, EVENT_FIELDS)
    if event["kind"] in STATUS_EVENT.values():
        raise Rejected(
            f"Change the status to log {event['kind'].replace('-', ' ')}:"
            " that keeps the status and the timeline together."
        )
    with store.db.change(f"event-{role_id}") as db:
        _require_role(db, role_id)
        event_id = insert(db, "events", {"role_id": role_id, **event})
    return {"role_id": role_id, "event_id": event_id}


def edit_event(event_id: int, changes: dict, version: int | None = None) -> dict:
    """Sets the EVENT_FIELDS in changes, to fix what was logged. A status change on the timeline
    keeps its kind, and nothing else becomes one: both come only from set_status."""
    check_fields(changes, EVENT_FIELDS)
    with store.db.change(f"edit-event-{event_id}") as db:
        row = _require_event(db, event_id)
        kind = changes.get("kind", row["kind"])
        if kind != row["kind"]:
            if row["kind"] in STATUS_EVENT.values():
                raise Rejected(
                    f"A status change on the timeline keeps its kind ({row['kind']}). Change the status instead."
                )
            if kind in STATUS_EVENT.values():
                raise Rejected(f"Change the status to log {kind}: that keeps the status and the timeline together.")
        update_versioned(db, "events", event_id, changes, version)
    return {"role_id": row["role_id"], "event_id": event_id}


def delete_event(event_id: int) -> dict:
    """Hides the event until restore_event."""
    with store.db.change(f"delete-event-{event_id}") as db:
        row = _require_event(db, event_id)
        set_deleted(db, "events", event_id, True)
    return {"role_id": row["role_id"], "event_id": event_id}


def restore_event(event_id: int) -> dict:
    with store.db.change(f"restore-event-{event_id}") as db:
        row = _require_event(db, event_id, deleted=True)
        restore(db, "events", row, f"Event {event_id}")
    return {"role_id": row["role_id"], "event_id": event_id}


def _require_todo(db: sqlite3.Connection, todo_id: int, deleted: bool = False) -> sqlite3.Row:
    """The todo, if it and its role (when it has one) are there and not deleted; with deleted=True,
    a deleted todo too."""
    row = db.execute(
        "SELECT t.*, r.deleted_on AS role_deleted_on FROM todos t LEFT JOIN roles r ON r.id = t.role_id WHERE t.id = ?",
        (todo_id,),
    ).fetchone()
    if row is None or row["role_deleted_on"] or (row["deleted_on"] and not deleted):
        raise NotFound(f"No todo {todo_id}.")
    return row


def add_todo(role_id: str | None, todo: dict) -> dict:
    """Adds an open todo (TODO_FIELDS, with text), for role_id or, when None, for no role."""
    check_fields(todo, TODO_FIELDS)
    with store.db.change(f"todo-{role_id or 'general'}") as db:
        if role_id is not None:
            _require_role(db, role_id)
        todo_id = insert(db, "todos", {"role_id": role_id, **todo})
    return {"todo_id": todo_id, "role_id": role_id}


def edit_todo(todo_id: int, changes: dict, done: bool | None = None, version: int | None = None) -> dict:
    """Sets the TODO_FIELDS in changes. done=True checks it off today, unless it is already done
    (it keeps that day); done=False opens it again."""
    check_fields(changes, TODO_FIELDS)
    with store.db.change(f"edit-todo-{todo_id}") as db:
        row = _require_todo(db, todo_id)
        if done is not None:
            changes = {**changes, "done_on": (row["done_on"] or dt.date.today().isoformat()) if done else None}
        update_versioned(db, "todos", todo_id, changes, version)
    return {"todo_id": todo_id, "role_id": row["role_id"]}


def delete_todo(todo_id: int) -> dict:
    """Hides the todo until restore_todo."""
    with store.db.change(f"delete-todo-{todo_id}") as db:
        row = _require_todo(db, todo_id)
        set_deleted(db, "todos", todo_id, True)
    return {"todo_id": todo_id, "role_id": row["role_id"]}


def restore_todo(todo_id: int) -> dict:
    with store.db.change(f"restore-todo-{todo_id}") as db:
        row = _require_todo(db, todo_id, deleted=True)
        restore(db, "todos", row, "That todo")
    return {"todo_id": todo_id, "role_id": row["role_id"]}
