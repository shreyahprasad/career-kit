import datetime as dt
import importlib.util
import os
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import career
import main
import networking
from writekit.testing import LOCAL


def _load(name: str):
    path = Path(__file__).parent.parent / f"tools/{name}/seed.py"
    spec = importlib.util.spec_from_file_location(f"{name}_seed", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


networking_seed = _load("networking")

# career's seed.py imports its store, which needs writekit; the schema alone is enough here.
CAREER_SCHEMA = Path(__file__).parent.parent / "tools/career/schema.sql"

# Made-up roles. Acme has two events entered out of order and a referral from Ann; Beta has none.
ROLES = [
    ("acme-fde", "Acme", "FDE", "Remote", "applied", "ann-lee", "Job ID 1."),
    ("beta-ds", "Beta", "Deployment Strategist", None, "interested", None, None),
    ("acme-ai", "acme", "AI Engineer", None, "rejected", "gone-person", None),
]
EVENTS = [
    ("acme-fde", "2026-08-01", "recruiter-call", "Phone screen booked.", None),
    ("acme-fde", "2026-07-24", "applied", None, None),
    ("acme-ai", "2026-06-01", "rejection", None, None),
]
# Acme FDE has two open todos with days, one with none and one done; one todo is for no role,
# and one is for the rejected Acme AI.
TODOS = [
    (1, "acme-fde", "Apply", "apply", "2026-10-12", None),
    (2, "acme-fde", "Ask Ann", "outreach", "2026-10-09", None),
    (3, "acme-fde", "Update resume", "resume", None, "2026-10-01"),
    (4, None, "Update base resume", "resume", None, None),
    (5, "acme-ai", "Message recruiter", "outreach", None, None),
    (6, "acme-fde", "Prep stories", "prep", None, None),
]


@pytest.fixture
def paths(tmp_path, monkeypatch):
    path = tmp_path / "career.db"
    db = sqlite3.connect(path)
    with db:
        db.executescript(CAREER_SCHEMA.read_text())
        db.executemany(
            "INSERT INTO roles (id, company, title, location, status, referral_person_id, notes)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            ROLES,
        )
        db.executemany("INSERT INTO events (role_id, date, kind, text, prep_link) VALUES (?, ?, ?, ?, ?)", EVENTS)
        db.executemany("INSERT INTO todos (id, role_id, text, kind, due_on, done_on) VALUES (?, ?, ?, ?, ?, ?)", TODOS)
    db.close()
    people = tmp_path / "networking.db"
    db = sqlite3.connect(people)
    with db:
        networking_seed.seed(db, {"people": [{"id": "ann-lee", "name": "Ann Lee"}]})
    db.close()
    monkeypatch.setattr(career, "CAREER_DB", path)
    monkeypatch.setattr(networking, "NETWORKING_DB", people)
    return {"career": path, "networking": people}


@pytest.fixture
def client(paths):
    return TestClient(main.app, base_url=LOCAL)


def roles(client):
    return client.get("/api/career/roles").json()["roles"]


def role(client, role_id):
    return client.get(f"/api/career/roles/{role_id}").json()


def test_roles_sorted_by_company_ignoring_case_then_title(client):
    assert [r["id"] for r in roles(client)] == ["acme-ai", "acme-fde", "beta-ds"]


def test_a_role_in_the_list_carries_when_it_was_applied_and_its_latest_event(client):
    acme = next(r for r in roles(client) if r["id"] == "acme-fde")
    assert acme == {
        "id": "acme-fde",
        "company": "Acme",
        "title": "FDE",
        "location": "Remote",
        "comp": None,
        "status": "applied",
        "applied_on": "2026-07-24",
        "last_event": {"date": "2026-08-01", "kind": "recruiter-call"},
        "todos": {"done": 1, "total": 4},
        "next_todo": {"id": 2, "text": "Ask Ann", "kind": "outreach", "due_on": "2026-10-09"},
    }


def test_a_role_with_no_events_has_none_of_either(client):
    beta = next(r for r in roles(client) if r["id"] == "beta-ds")
    assert (beta["applied_on"], beta["last_event"]) == (None, None)


def test_one_role_has_every_detail_and_its_events_newest_first(client):
    acme = role(client, "acme-fde")
    assert (acme["notes"], acme["link"], acme["applied_via"], acme["resume_file"], acme["sent_file"]) == (
        "Job ID 1.",
        None,
        None,
        None,
        None,
    )
    assert [(e["date"], e["kind"], e["text"]) for e in acme["events"]] == [
        ("2026-08-01", "recruiter-call", "Phone screen booked."),
        ("2026-07-24", "applied", None),
    ]
    assert set(acme["events"][0]) == {"id", "date", "kind", "text", "prep_link", "version"}


def test_a_role_with_no_todos_has_none_to_do(client):
    beta = next(r for r in roles(client) if r["id"] == "beta-ds")
    assert (beta["todos"], beta["next_todo"]) == ({"done": 0, "total": 0}, None)


def test_a_roles_todos_are_open_ones_soonest_due_first_then_done(client):
    assert [(t["id"], t["done_on"]) for t in role(client, "acme-fde")["todos"]] == [
        (2, None),
        (1, None),
        (6, None),
        (3, "2026-10-01"),
    ]
    assert set(role(client, "acme-fde")["todos"][0]) == {"id", "text", "kind", "due_on", "done_on", "version"}


def test_open_todos_across_roles_soonest_first_leave_out_done_ones_and_rejected_roles(client):
    todos = client.get("/api/career/todos").json()["todos"]
    assert [t["id"] for t in todos] == [2, 1, 4, 6]
    assert todos[0] == {
        "id": 2,
        "text": "Ask Ann",
        "kind": "outreach",
        "due_on": "2026-10-09",
        "role": {"id": "acme-fde", "company": "Acme", "title": "FDE"},
    }
    assert todos[2]["role"] is None


def test_a_referral_comes_with_the_name_from_networking(client):
    assert role(client, "acme-fde")["referral"] == {"id": "ann-lee", "name": "Ann Lee"}
    assert "referral_person_id" not in role(client, "acme-fde")


def test_a_referral_not_in_networking_keeps_its_id_with_no_name(client):
    assert role(client, "acme-ai")["referral"] == {"id": "gone-person", "name": None}


def test_no_referral_is_null(client):
    assert role(client, "beta-ds")["referral"] is None


def test_a_referral_without_networking_db_still_loads_the_role(client, paths, monkeypatch):
    monkeypatch.setattr(networking, "NETWORKING_DB", paths["networking"].with_name("gone.db"))
    assert role(client, "acme-fde")["referral"] == {"id": "ann-lee", "name": None}


def test_a_role_not_on_file_is_404(client):
    r = client.get("/api/career/roles/nope")
    assert (r.status_code, r.json()["detail"]) == (404, "No role nope.")


def test_a_role_id_that_is_not_an_id_is_422(client):
    assert client.get("/api/career/roles/Acme FDE").status_code == 422


def test_no_career_db_says_how_to_make_one(client, paths, monkeypatch):
    monkeypatch.setattr(career, "CAREER_DB", paths["career"].with_name("gone.db"))
    r = client.get("/api/career/roles")
    assert r.status_code == 404 and "./setup.sh" in r.json()["detail"]


def test_the_api_has_no_write_routes_for_career():
    methods = {m for r in main.app.routes if getattr(r, "path", "").startswith("/api/career") for m in r.methods}
    assert methods <= {"GET", "HEAD"}


# ── Versions and deleted rows ────────────────────────────────────────────────


def hide(paths, table: str, where: str, database: str = "career"):
    db = sqlite3.connect(paths[database])
    with db:
        db.execute(f"UPDATE {table} SET deleted_on = '2026-10-08' WHERE {where}")
    db.close()


def test_a_role_its_events_and_todos_carry_their_versions_for_the_edit_forms(client):
    acme = role(client, "acme-fde")
    assert (
        acme["version"] == 1
        and {e["version"] for e in acme["events"]} == {1}
        and {t["version"] for t in acme["todos"]} == {1}
    )
    assert "deleted_on" not in acme and "deleted_on" not in acme["events"][0]


def test_a_deleted_role_is_left_out_with_its_todos_and_its_page_is_404(client, paths):
    hide(paths, "roles", "id = 'acme-fde'")
    assert [r["id"] for r in roles(client)] == ["acme-ai", "beta-ds"]
    assert client.get("/api/career/roles/acme-fde").status_code == 404
    assert [t["id"] for t in client.get("/api/career/todos").json()["todos"]] == [4]


def test_a_deleted_event_is_left_out_of_the_timeline_and_the_board(client, paths):
    hide(paths, "events", "kind = 'recruiter-call'")
    acme = next(r for r in roles(client) if r["id"] == "acme-fde")
    assert acme["last_event"] == {"date": "2026-07-24", "kind": "applied"}
    assert [e["kind"] for e in role(client, "acme-fde")["events"]] == ["applied"]
    hide(paths, "events", "kind = 'applied'")
    assert next(r for r in roles(client) if r["id"] == "acme-fde")["applied_on"] is None


def test_a_deleted_todo_is_left_out_everywhere(client, paths):
    hide(paths, "todos", "id IN (2, 4)")
    assert [t["id"] for t in role(client, "acme-fde")["todos"]] == [1, 6, 3]
    assert [t["id"] for t in client.get("/api/career/todos").json()["todos"]] == [1, 6]
    acme = next(r for r in roles(client) if r["id"] == "acme-fde")
    assert (acme["todos"], acme["next_todo"]["id"]) == ({"done": 1, "total": 3}, 1)


def test_recently_deleted_lists_what_undo_can_still_bring_back_newest_first(client, paths):
    """What went with a deleted role comes back with it, so it is not listed apart."""
    db = sqlite3.connect(paths["career"])
    with db:
        db.execute("UPDATE roles SET deleted_on = '2026-10-05' WHERE id = 'beta-ds'")
        db.execute("UPDATE events SET deleted_on = '2026-10-07' WHERE kind = 'recruiter-call'")
        db.execute("UPDATE todos SET deleted_on = '2026-10-06' WHERE id IN (4, 5)")
        db.execute("UPDATE roles SET deleted_on = '2026-10-01' WHERE id = 'acme-ai'")  # takes todo 5 and its event
    db.close()
    acme = {"id": "acme-fde", "company": "Acme", "title": "FDE"}
    assert client.get("/api/career/deleted").json() == {
        "roles": [
            {"id": "beta-ds", "company": "Beta", "title": "Deployment Strategist", "deleted_on": "2026-10-05"},
            {"id": "acme-ai", "company": "acme", "title": "AI Engineer", "deleted_on": "2026-10-01"},
        ],
        "events": [{"id": 1, "date": "2026-08-01", "kind": "recruiter-call", "role": acme, "deleted_on": "2026-10-07"}],
        "todos": [{"id": 4, "text": "Update base resume", "role": None, "deleted_on": "2026-10-06"}],
    }


def test_a_referral_who_was_deleted_has_no_name(client, paths):
    hide(paths, "people", "id = 'ann-lee'", "networking")
    assert role(client, "acme-fde")["referral"] == {"id": "ann-lee", "name": None}


# ── Resume PDFs ──────────────────────────────────────────────────────────────

PDF = b"%PDF-1.7 made-up resume"


@pytest.fixture
def folders(tmp_path, monkeypatch):
    """data/resumes with two PDFs (base.pdf older) and a file that is not one; data/sent with one copy."""
    monkeypatch.setattr(career, "CAREER_DIR", tmp_path)
    resumes, sent = tmp_path / "resumes", tmp_path / "sent"
    resumes.mkdir()
    sent.mkdir()
    for name, mtime in (("base.pdf", 1_790_000_000), ("Acme FDE v2.pdf", 1_791_000_000)):
        (resumes / name).write_bytes(PDF)
        os.utime(resumes / name, (mtime, mtime))
    (resumes / "base.docx").write_bytes(b"not a pdf")
    (resumes / ".hidden.pdf").write_bytes(PDF)
    (sent / "acme-fde-2026-07-24.pdf").write_bytes(PDF)
    (tmp_path / "secret.pdf").write_bytes(b"outside")
    return {"resumes": resumes, "sent": sent}


def test_the_resumes_are_the_pdfs_in_resumes_newest_first(client, folders):
    assert client.get("/api/career/resumes").json() == {
        "resumes": [
            {"name": "Acme FDE v2.pdf", "modified": dt.date.fromtimestamp(1_791_000_000).isoformat()},
            {"name": "base.pdf", "modified": dt.date.fromtimestamp(1_790_000_000).isoformat()},
        ]
    }


def test_no_resumes_folder_is_no_resumes(client, tmp_path, monkeypatch):
    monkeypatch.setattr(career, "CAREER_DIR", tmp_path / "gone")
    assert client.get("/api/career/resumes").json() == {"resumes": []}


@pytest.mark.parametrize("url", ["/api/career/resumes/Acme%20FDE%20v2.pdf", "/api/career/sent/acme-fde-2026-07-24.pdf"])
def test_a_pdf_is_served_inline_as_a_pdf(client, folders, url):
    r = client.get(url)
    assert (r.status_code, r.content, r.headers["content-type"]) == (200, PDF, "application/pdf")
    assert r.headers["content-disposition"].startswith("inline")
    assert r.headers["x-content-type-options"] == "nosniff"


def test_a_resume_can_be_changed_so_is_checked_again_but_a_sent_copy_never_changes(client, folders):
    assert client.get("/api/career/resumes/base.pdf").headers["cache-control"] == "no-cache"
    assert "immutable" in client.get("/api/career/sent/acme-fde-2026-07-24.pdf").headers["cache-control"]


@pytest.mark.parametrize(
    "url",
    [
        "/api/career/resumes/gone.pdf",
        "/api/career/resumes/base.docx",
        "/api/career/resumes/.hidden.pdf",
        "/api/career/resumes/..%2Fsecret.pdf",
        "/api/career/sent/..%2Fsecret.pdf",
        "/api/career/sent/base.pdf",
    ],
)
def test_only_a_pdf_in_its_own_folder_is_served(client, folders, url):
    assert client.get(url).status_code in (404, 422)


def test_a_link_out_of_resumes_is_not_followed(client, folders):
    (folders["resumes"] / "link.pdf").symlink_to(folders["resumes"].parent / "secret.pdf")
    assert client.get("/api/career/resumes/link.pdf").status_code == 404
    assert "link.pdf" not in [r["name"] for r in client.get("/api/career/resumes").json()["resumes"]]


# ── Drafts ───────────────────────────────────────────────────────────────────


@pytest.fixture
def drafts(tmp_path, monkeypatch):
    """data/drafts/beta-ds with two letters, a resume draft and files that are not drafts;
    data/sent with one kept letter; another role's draft and a secret beside them."""
    monkeypatch.setattr(career, "CAREER_DIR", tmp_path)
    folder = tmp_path / "drafts/beta-ds"
    folder.mkdir(parents=True)
    for name, mtime in (
        ("cover-letter-1.md", 1_790_000_000),
        ("cover-letter-2.md", 1_791_000_000),
        ("resume-1.md", 1_790_500_000),
    ):
        (folder / name).write_text(f"Made-up {name}.")
        os.utime(folder / name, (mtime, mtime))
    (folder / "notes.md").write_text("not a draft")
    (folder / ".cover-letter-3.md").write_text("hidden")
    (tmp_path / "drafts/acme-fde").mkdir()
    (tmp_path / "drafts/acme-fde/cover-letter-1.md").write_text("Acme's letter.")
    (tmp_path / "sent").mkdir()
    (tmp_path / "sent/beta-ds-2026-10-09-cover-letter.md").write_text("Kept letter.")
    (tmp_path / "secret.md").write_text("outside")
    return folder


def test_a_roles_drafts_are_listed_resumes_first_then_letters_newest_first(client, drafts):
    def when(t):
        at = dt.datetime.fromtimestamp(t)
        return {"modified": at.date().isoformat(), "modified_at": at.isoformat(timespec="seconds")}

    assert client.get("/api/career/roles/beta-ds/drafts").json() == {
        "drafts": [
            {"name": "resume-1.md", "kind": "resume", "number": 1, **when(1_790_500_000), "pdf": False},
            {"name": "cover-letter-2.md", "kind": "cover-letter", "number": 2, **when(1_791_000_000), "pdf": False},
            {"name": "cover-letter-1.md", "kind": "cover-letter", "number": 1, **when(1_790_000_000), "pdf": False},
        ]
    }


def test_a_role_with_no_drafts_folder_has_none(client, drafts):
    assert client.get("/api/career/roles/acme-ai/drafts").json() == {"drafts": []}


def test_a_draft_is_its_text(client, drafts):
    r = client.get("/api/career/roles/beta-ds/drafts/cover-letter-2.md")
    assert (r.status_code, r.json()) == (200, {"name": "cover-letter-2.md", "text": "Made-up cover-letter-2.md."})
    assert r.headers["x-content-type-options"] == "nosniff"


def test_a_kept_letter_is_its_text(client, drafts):
    assert client.get("/api/career/sent-letters/beta-ds-2026-10-09-cover-letter.md").json()["text"] == "Kept letter."


@pytest.mark.parametrize(
    "url",
    [
        "/api/career/roles/beta-ds/drafts/cover-letter-3.md",
        "/api/career/roles/beta-ds/drafts/notes.md",
        "/api/career/roles/beta-ds/drafts/.cover-letter-3.md",
        "/api/career/roles/beta-ds/drafts/..%2F..%2Fsecret.md",
        "/api/career/roles/beta-ds/drafts/..%2Facme-fde%2Fcover-letter-1.md",
        "/api/career/roles/..%2Facme-fde/drafts/cover-letter-1.md",
        "/api/career/roles/acme-fde/drafts/resume-1.md",
        "/api/career/sent-letters/..%2Fsecret.md",
        "/api/career/sent-letters/beta-ds-2026-10-09.pdf",
    ],
)
def test_only_a_draft_in_its_own_roles_folder_is_served(client, drafts, url):
    assert client.get(url).status_code in (404, 422)


def test_a_link_out_of_the_drafts_folder_is_not_followed(client, drafts):
    (drafts / "cover-letter-9.md").symlink_to(drafts.parent.parent / "secret.md")
    assert client.get("/api/career/roles/beta-ds/drafts/cover-letter-9.md").status_code == 404
    assert "cover-letter-9.md" not in [
        d["name"] for d in client.get("/api/career/roles/beta-ds/drafts").json()["drafts"]
    ]


def test_a_draft_too_long_to_show_says_where_to_open_it(client, drafts):
    (drafts / "cover-letter-5.md").write_text("x" * (career.MAX_DRAFT_BYTES + 1))
    r = client.get("/api/career/roles/beta-ds/drafts/cover-letter-5.md")
    assert (r.status_code, r.json()["detail"]) == (
        413,
        "cover-letter-5.md is too long to show here. Open it in data/drafts/beta-ds.",
    )


def test_a_role_shows_its_approved_drafts_and_kept_letter(client, paths):
    db = sqlite3.connect(paths["career"])
    with db:
        db.execute(
            "UPDATE roles SET approved_resume_draft = 'resume-1.md', approved_cover_letter = 'cover-letter-2.md',"
            " sent_cover_letter = 'x-cover-letter.md' WHERE id = 'beta-ds'"
        )
    db.close()
    beta = role(client, "beta-ds")
    assert (beta["approved_resume_draft"], beta["approved_cover_letter"], beta["sent_cover_letter"]) == (
        "resume-1.md",
        "cover-letter-2.md",
        "x-cover-letter.md",
    )


PDF = b"%PDF-1.7 made-up draft"


def pdf_flags(client):
    return {d["name"]: d["pdf"] for d in client.get("/api/career/roles/beta-ds/drafts").json()["drafts"]}


def test_a_draft_has_a_pdf_only_when_one_was_made_since_it_changed(client, drafts):
    (drafts / "resume-1.pdf").write_bytes(PDF)  # made now, after the draft
    (drafts / "cover-letter-2.pdf").write_bytes(PDF)
    os.utime(drafts / "cover-letter-2.pdf", (1_790_900_000, 1_790_900_000))  # before the draft changed
    assert pdf_flags(client) == {"resume-1.md": True, "cover-letter-2.md": False, "cover-letter-1.md": False}
    assert "resume-1.pdf" not in pdf_flags(client)  # a PDF is not a draft of its own


def test_a_drafts_pdf_is_served_as_a_pdf_never_cached(client, drafts):
    (drafts / "resume-1.pdf").write_bytes(PDF)
    r = client.get("/api/career/roles/beta-ds/drafts/resume-1.pdf")
    assert (r.status_code, r.content, r.headers["content-type"]) == (200, PDF, "application/pdf")
    assert (r.headers["cache-control"], r.headers["x-content-type-options"]) == ("no-cache", "nosniff")
    assert r.headers["content-disposition"].startswith("inline")


@pytest.mark.parametrize(
    "url",
    [
        "/api/career/roles/beta-ds/drafts/resume-2.pdf",
        "/api/career/roles/beta-ds/drafts/notes.pdf",
        "/api/career/roles/beta-ds/drafts/.resume-1.pdf",
        "/api/career/roles/beta-ds/drafts/resume-0.pdf",
        "/api/career/roles/beta-ds/drafts/..%2F..%2Fsecret.pdf",
        "/api/career/roles/beta-ds/drafts/..%2Facme-fde%2Fresume-1.pdf",
        "/api/career/roles/..%2Facme-fde/drafts/resume-1.pdf",
    ],
)
def test_only_a_pdf_of_a_draft_in_its_own_roles_folder_is_served(client, drafts, url):
    (drafts.parent.parent / "secret.pdf").write_bytes(b"outside")
    (drafts.parent / "acme-fde/resume-1.pdf").write_bytes(b"Acme's")
    (drafts / "notes.pdf").write_bytes(PDF)
    r = client.get(url)
    assert r.status_code in (404, 422) and b"outside" not in r.content and b"Acme" not in r.content


@pytest.mark.parametrize("target", ["../../secret.pdf", "resume-1.pdf"])
def test_a_link_where_a_drafts_pdf_goes_is_not_followed(client, drafts, target):
    (drafts.parent.parent / "secret.pdf").write_bytes(b"outside")
    (drafts / "resume-1.pdf").write_bytes(PDF)
    (drafts / "cover-letter-1.pdf").symlink_to(target)
    assert client.get("/api/career/roles/beta-ds/drafts/cover-letter-1.pdf").status_code == 404
    assert pdf_flags(client)["cover-letter-1.md"] is False


def test_a_role_says_whether_its_sent_letter_has_a_pdf(client, paths, tmp_path, monkeypatch):
    monkeypatch.setattr(career, "CAREER_DIR", tmp_path)
    (tmp_path / "sent").mkdir()
    db = sqlite3.connect(paths["career"])
    with db:
        db.execute("UPDATE roles SET sent_cover_letter = 'beta-ds-2026-10-09-cover-letter.md' WHERE id = 'beta-ds'")
    db.close()
    assert role(client, "beta-ds")["sent_cover_letter_pdf"] is False  # kept before PDFs were made
    (tmp_path / "sent/beta-ds-2026-10-09-cover-letter.pdf").write_bytes(PDF)
    assert role(client, "beta-ds")["sent_cover_letter_pdf"] is True
    assert client.get("/api/career/sent/beta-ds-2026-10-09-cover-letter.pdf").content == PDF
    assert role(client, "acme-fde")["sent_cover_letter_pdf"] is False
