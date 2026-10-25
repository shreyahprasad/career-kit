"""
Career: the roles you are looking at, and what happened with each.

Reads career.db (schema: tools/career/schema.sql), opened read-only. Dates are YYYY-MM-DD. A
referral is stored as a networking person id; its name is looked up in networking.db here,
since the career writer never opens that database. Changes go through the career writer
(tools/career/writer.py), never here. Rows deleted with undo (deleted_on) are left out everywhere
but /deleted, which lists them for Recently deleted; a deleted role takes its events and todos
with it. version goes to the page with each row it can
edit, and comes back with the edit.

It also serves the resume PDFs read-only: the ones you export into data/resumes, and the
copies the writer keeps in data/sent when you apply. And the drafts Claude writes for a role in
data/drafts/<role>, as text and as the PDF the writer makes of each, with the copy of the
approved cover letter kept in data/sent.
"""

import datetime as dt
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

import networking
from readonly import open_readonly
from writekit.career import CAREER_DB, CAREER_DIR, MAX_DRAFT_BYTES
from writekit.files import file_in
from writekit.forms import (
    DRAFT_NAME_PATTERN,
    PDF_NAME_PATTERN,
    DraftNamePath,
    DraftStemPath,
    PdfNamePath,
    SentLetterPath,
    SlugPath,
)

router = APIRouter(prefix="/api/career")

# A resume can be exported again under the same name, so the phone checks before reusing it. A
# sent copy is read-only and never replaced.
RESUME_CACHE = "no-cache"
SENT_CACHE = "private, max-age=31536000, immutable"

# What the list shows of every role; one role's detail has every column.
LIST_FIELDS = ("id", "company", "title", "location", "comp", "status")
EVENT_FIELDS = ("id", "date", "kind", "text", "prep_link", "version")
TODO_FIELDS = ("id", "text", "kind", "due_on", "done_on", "version")

# Open todos first, soonest due first and those with no day after; done ones after them, the
# latest done first. Every todo list here is in this order.
TODO_ORDER = "done_on IS NOT NULL, done_on DESC, due_on IS NULL, due_on, id"

LIVE_EVENT = "e.deleted_on IS NULL"
LIVE_TODO = "t.deleted_on IS NULL"


def connect():
    return open_readonly(CAREER_DB, "career.db not found. Run ./setup.sh.")


def _person_name(person_id: str) -> str | None:
    """Their name in networking.db, or None when they (or the database) are not there or were deleted."""
    if not networking.NETWORKING_DB.exists():
        return None
    with networking.connect() as db:
        row = db.execute("SELECT name FROM people WHERE id = ? AND deleted_on IS NULL", (person_id,)).fetchone()
    return row["name"] if row else None


@router.get("/roles")
def roles() -> dict:
    """Every role by company, then title, with the date it was applied to (its first applied
    event), the date and kind of its latest event, how many of its todos are done, and the next
    one to do."""
    with connect() as db:
        rows = db.execute(f"""
            SELECT {", ".join(f"r.{f}" for f in LIST_FIELDS)},
                (SELECT min(date) FROM events e
                    WHERE e.role_id = r.id AND {LIVE_EVENT} AND e.kind = 'applied') AS applied_on,
                (SELECT date FROM events e
                    WHERE e.role_id = r.id AND {LIVE_EVENT} ORDER BY date DESC, id DESC LIMIT 1) AS last_date,
                (SELECT kind FROM events e
                    WHERE e.role_id = r.id AND {LIVE_EVENT} ORDER BY date DESC, id DESC LIMIT 1) AS last_kind,
                (SELECT count(*) FROM todos t WHERE t.role_id = r.id AND {LIVE_TODO}) AS todos_total,
                (SELECT count(done_on) FROM todos t WHERE t.role_id = r.id AND {LIVE_TODO}) AS todos_done,
                (SELECT id FROM todos t
                    WHERE t.role_id = r.id AND {LIVE_TODO} AND done_on IS NULL
                    ORDER BY {TODO_ORDER} LIMIT 1) AS next_todo
            FROM roles r WHERE r.deleted_on IS NULL
            ORDER BY r.company COLLATE NOCASE, r.title COLLATE NOCASE
        """).fetchall()
        next_ids = [r["next_todo"] for r in rows if r["next_todo"] is not None]
        next_todos = {
            t["id"]: dict(t)
            for t in db.execute(
                f"SELECT id, text, kind, due_on FROM todos WHERE id IN ({', '.join('?' * len(next_ids))})", next_ids
            )
        }
    return {
        "roles": [
            {
                **{f: r[f] for f in LIST_FIELDS},
                "applied_on": r["applied_on"],
                "last_event": {"date": r["last_date"], "kind": r["last_kind"]} if r["last_date"] else None,
                "todos": {"done": r["todos_done"], "total": r["todos_total"]},
                "next_todo": next_todos.get(r["next_todo"]),
            }
            for r in rows
        ]
    }


@router.get("/roles/{role_id}")
def role(role_id: SlugPath) -> dict:
    """One role with every detail, its referral by name, its events newest first, and its todos."""
    with connect() as db:
        row = db.execute("SELECT * FROM roles WHERE id = ? AND deleted_on IS NULL", (role_id,)).fetchone()
        if row is None:
            raise HTTPException(404, f"No role {role_id}.")
        events = [
            dict(e)
            for e in db.execute(
                f"SELECT {', '.join(EVENT_FIELDS)} FROM events e"
                f" WHERE role_id = ? AND {LIVE_EVENT} ORDER BY date DESC, id DESC",
                (role_id,),
            )
        ]
        todos = [
            dict(t)
            for t in db.execute(
                f"SELECT {', '.join(TODO_FIELDS)} FROM todos t WHERE role_id = ? AND {LIVE_TODO} ORDER BY {TODO_ORDER}",
                (role_id,),
            )
        ]
    detail = dict(row)
    del detail["deleted_on"]
    # The PDF of the letter sent, kept beside its text since PDFs were made; none before that.
    letter = detail["sent_cover_letter"]
    detail["sent_cover_letter_pdf"] = bool(
        letter and file_in(CAREER_DIR / "sent", Path(letter).with_suffix(".pdf").name)
    )
    person_id = detail.pop("referral_person_id")
    referral = {"id": person_id, "name": _person_name(person_id)} if person_id else None
    return {**detail, "referral": referral, "events": events, "todos": todos}


@router.get("/todos")
def open_todos() -> dict:
    """Every open todo, soonest due first (TODO_ORDER for open ones), with the role it is for (null for none).
    A rejected role is done, so its todos are left out, as are a deleted role's."""
    with connect() as db:
        rows = db.execute(f"""
            SELECT t.id, t.text, t.kind, t.due_on, r.id AS role_id, r.company, r.title
            FROM todos t LEFT JOIN roles r ON r.id = t.role_id
            WHERE t.done_on IS NULL AND {LIVE_TODO}
                AND (t.role_id IS NULL OR (r.status != 'rejected' AND r.deleted_on IS NULL))
            ORDER BY t.due_on IS NULL, t.due_on, t.id
        """).fetchall()
    return {
        "todos": [
            {
                "id": t["id"],
                "text": t["text"],
                "kind": t["kind"],
                "due_on": t["due_on"],
                "role": _role(t),
            }
            for t in rows
        ]
    }


def _role(row) -> dict | None:
    return {"id": row["role_id"], "company": row["company"], "title": row["title"]} if row["role_id"] else None


@router.get("/deleted")
def deleted() -> dict:
    """What undo can still bring back, latest deleted first: deleted roles, and the events and
    todos deleted on their own. What went with a deleted role comes back with it, so it is not
    listed apart."""
    with connect() as db:
        roles = db.execute(
            "SELECT id, company, title, deleted_on FROM roles WHERE deleted_on IS NOT NULL ORDER BY deleted_on DESC, id"
        ).fetchall()
        events = db.execute("""
            SELECT e.id, e.date, e.kind, e.deleted_on, r.id AS role_id, r.company, r.title
            FROM events e JOIN roles r ON r.id = e.role_id
            WHERE e.deleted_on IS NOT NULL AND r.deleted_on IS NULL ORDER BY e.deleted_on DESC, e.id
        """).fetchall()
        todos = db.execute("""
            SELECT t.id, t.text, t.deleted_on, r.id AS role_id, r.company, r.title
            FROM todos t LEFT JOIN roles r ON r.id = t.role_id
            WHERE t.deleted_on IS NOT NULL AND r.deleted_on IS NULL ORDER BY t.deleted_on DESC, t.id
        """).fetchall()
    return {
        "roles": [dict(r) for r in roles],
        "events": [
            {"id": e["id"], "date": e["date"], "kind": e["kind"], "role": _role(e), "deleted_on": e["deleted_on"]}
            for e in events
        ],
        "todos": [{"id": t["id"], "text": t["text"], "role": _role(t), "deleted_on": t["deleted_on"]} for t in todos],
    }


def _serve(folder: str, name: str, cache: str) -> FileResponse:
    path = file_in(CAREER_DIR / folder, name)
    if path is None:
        raise HTTPException(404, f"There is no {name} in career/{folder}.")
    return FileResponse(
        path,
        media_type="application/pdf",
        content_disposition_type="inline",
        filename=name,
        headers={"Cache-Control": cache, "X-Content-Type-Options": "nosniff"},
    )


@router.get("/resumes")
def resumes() -> dict:
    """The PDFs in data/resumes to pick from, last changed first, with the day each changed."""
    folder = CAREER_DIR / "resumes"
    found = (
        [p for p in folder.iterdir() if re.match(PDF_NAME_PATTERN, p.name) and file_in(folder, p.name)]
        if folder.is_dir()
        else []
    )
    found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return {
        "resumes": [{"name": p.name, "modified": dt.date.fromtimestamp(p.stat().st_mtime).isoformat()} for p in found]
    }


@router.get("/resumes/{name}")
def resume(name: PdfNamePath) -> FileResponse:
    return _serve("resumes", name, RESUME_CACHE)


@router.get("/sent/{name}")
def sent(name: PdfNamePath) -> FileResponse:
    """The copy of a resume kept when you applied (roles.sent_file)."""
    return _serve("sent", name, SENT_CACHE)


def _text(folder: Path, name: str, where: str) -> dict:
    path = file_in(folder, name)
    if path is None:
        raise HTTPException(404, f"There is no {name} in {where}.")
    if path.stat().st_size > MAX_DRAFT_BYTES:
        raise HTTPException(413, f"{name} is too long to show here. Open it in {where}.")
    return {"name": name, "text": path.read_text(errors="replace")}


@router.get("/roles/{role_id}/drafts")
def drafts(role_id: SlugPath) -> dict:
    """The drafts Claude wrote for this role in data/drafts/<role>: each with its kind, its number,
    the day and time it last changed (so the page can show the one written last), and whether its
    PDF is there and made since (pdf), resumes first, then letters, newest first in each."""
    folder = CAREER_DIR / "drafts" / role_id
    found = (
        [p for p in folder.iterdir() if re.match(DRAFT_NAME_PATTERN, p.name) and file_in(folder, p.name)]
        if folder.is_dir()
        else []
    )
    listed = []
    for p in found:
        kind, number = p.stem.rsplit("-", 1)
        changed = dt.datetime.fromtimestamp(p.stat().st_mtime)
        pdf = file_in(folder, p.with_suffix(".pdf").name)
        listed.append(
            {
                "name": p.name,
                "kind": kind,
                "number": int(number),
                "modified": changed.date().isoformat(),
                "modified_at": changed.isoformat(timespec="seconds"),
                "pdf": bool(pdf and not pdf.is_symlink() and pdf.stat().st_mtime >= p.stat().st_mtime),
            }
        )
    listed.sort(key=lambda d: (d["kind"] != "resume", -d["number"]))
    return {"drafts": listed}


# Before the text route, which takes any name and would refuse a .pdf one.
@router.get("/roles/{role_id}/drafts/{stem}.pdf")
def draftfile_in(role_id: SlugPath, stem: DraftStemPath) -> FileResponse:
    """The PDF the writer made of a draft. Made again when the draft changes, so never cached. The
    writer never makes a link, so one there is not followed even within the folder."""
    if (CAREER_DIR / "drafts" / role_id / f"{stem}.pdf").is_symlink():
        raise HTTPException(404, f"There is no {stem}.pdf in career/drafts/{role_id}.")
    return _serve(f"drafts/{role_id}", f"{stem}.pdf", RESUME_CACHE)


@router.get("/roles/{role_id}/drafts/{name}")
def draft(role_id: SlugPath, name: DraftNamePath) -> dict:
    """One draft's text."""
    return _text(CAREER_DIR / "drafts" / role_id, name, f"data/drafts/{role_id}")


@router.get("/sent-letters/{name}")
def sent_letter(name: SentLetterPath) -> dict:
    """The copy of a cover letter kept when you applied (roles.sent_cover_letter)."""
    return _text(CAREER_DIR / "sent", name, "data/sent")
