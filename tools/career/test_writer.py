"""writer.py over HTTP, on a throwaway career.db built by seed.py from schema.sql. Made-up roles.
What every writer does alike (the header, the size limit, backups, migrating) is tested in writekit."""

import datetime as dt
import json
import os
import re
import sqlite3
import typing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import records
import seed
import store
import writer
from writekit.rows import STALE
from writekit.testing import HEADERS, LOCAL, assert_fields_current, assert_schema_current

P = writer.PREFIX
TODAY = dt.date.today().isoformat()

# Acme is applied with one event; Beta is only of interest.
ROLES = [
    {
        "id": "acme-fde",
        "company": "Acme",
        "title": "FDE",
        "status": "applied",
        "comp": "$150k-$200k",
        "events": [{"date": "2026-07-24", "kind": "applied"}],
    },
    {"id": "beta-applied-ai", "company": "Beta", "title": "Applied AI"},
]


# The starter todos as shipped, kept apart so editing config/starter-todos.json breaks no test.
STARTERS = Path(__file__).with_name("testdata") / "starter-todos.json"


@pytest.fixture
def db(tmp_path, monkeypatch) -> sqlite3.Connection:
    monkeypatch.setenv("CAREER_STARTER_TODOS", str(STARTERS))
    path = tmp_path / "career.db"
    conn = sqlite3.connect(path)
    with conn:
        seed.seed(conn, {"roles": ROLES})
    conn.row_factory = sqlite3.Row
    monkeypatch.setattr(store.db, "path", path)
    yield conn
    conn.close()


@pytest.fixture
def client(db):
    with TestClient(writer.app, base_url=LOCAL) as c:  # `with` runs the lifespan: migrations
        yield c


def role(db, role_id):
    row = db.execute("SELECT * FROM roles WHERE id = ?", (role_id,)).fetchone()
    return dict(row) if row else None


def events(db, role_id):
    return [dict(r) for r in db.execute("SELECT * FROM events WHERE role_id = ? ORDER BY id", (role_id,))]


def count(db, table):
    return db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


# ── Adding a role ────────────────────────────────────────────────────────────


def test_a_role_needs_only_company_and_title_and_starts_as_interested(client, db):
    r = client.post(f"{P}/roles", json={"company": "Gamma Co", "title": "Forward Deployed Engineer"}, headers=HEADERS)
    assert r.status_code == 200
    assert r.json() == {"role_id": "gamma-co-forward-deployed-engineer"}
    assert role(db, "gamma-co-forward-deployed-engineer")["status"] == "interested"


def test_a_role_can_come_with_its_details(client, db):
    body = {
        "company": "Gamma",
        "title": "DS",
        "location": "NYC hybrid",
        "link": "https://jobs.example/1",
        "comp": "$110k-$170k + RSUs",
        "referral_person_id": "ann-lee",
        "notes": "25-75% travel.",
    }
    role_id = client.post(f"{P}/roles", json=body, headers=HEADERS).json()["role_id"]
    assert {k: role(db, role_id)[k] for k in body} == body


def test_a_role_can_say_where_she_applied_apart_from_the_posting(client, db):
    body = {
        "company": "Gamma",
        "title": "DS",
        "link": "https://jobs.example/1",
        "applied_via": "https://www.linkedin.com/jobs/view/9",
    }
    role_id = client.post(f"{P}/roles", json=body, headers=HEADERS).json()["role_id"]
    assert (role(db, role_id)["link"], role(db, role_id)["applied_via"]) == (body["link"], body["applied_via"])


def test_the_same_company_and_title_again_gets_the_next_free_id(client, db):
    r = client.post(f"{P}/roles", json={"company": "Acme", "title": "FDE"}, headers=HEADERS)
    assert r.json() == {"role_id": "acme-fde-2"}


# ── Changing status ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("status, kind", [("applied", "applied"), ("offer", "offer"), ("rejected", "rejection")])
def test_a_status_with_a_timeline_kind_logs_it_today(client, db, status, kind):
    r = client.post(f"{P}/roles/beta-applied-ai/status", json={"status": status}, headers=HEADERS)
    assert r.status_code == 200
    [event] = events(db, "beta-applied-ai")
    assert r.json() == {"role_id": "beta-applied-ai", "event_id": event["id"]}
    assert role(db, "beta-applied-ai")["status"] == status
    assert (event["date"], event["kind"], event["text"]) == (TODAY, kind, None)


def test_a_status_change_can_say_when_and_what(client, db):
    body = {"status": "rejected", "date": "2026-10-01", "text": "Form email."}
    client.post(f"{P}/roles/acme-fde/status", json=body, headers=HEADERS)
    assert (events(db, "acme-fde")[-1]["date"], events(db, "acme-fde")[-1]["text"]) == ("2026-10-01", "Form email.")


@pytest.mark.parametrize("status", ["screen", "interviews", "interested"])
def test_a_status_with_no_timeline_kind_logs_nothing(client, db, status):
    r = client.post(f"{P}/roles/acme-fde/status", json={"status": status}, headers=HEADERS)
    assert r.json() == {"role_id": "acme-fde", "event_id": None}
    assert role(db, "acme-fde")["status"] == status
    assert len(events(db, "acme-fde")) == 1


def test_text_with_a_status_that_logs_nothing_is_refused(client, db):
    r = client.post(
        f"{P}/roles/acme-fde/status", json={"status": "screen", "text": "Recruiter emailed."}, headers=HEADERS
    )
    assert r.status_code == 400 and "recruiter call" in r.json()["detail"]
    assert role(db, "acme-fde")["status"] == "applied"


def test_the_status_it_already_has_is_refused(client, db):
    r = client.post(f"{P}/roles/acme-fde/status", json={"status": "applied"}, headers=HEADERS)
    assert (r.status_code, r.json()["detail"]) == (409, "Acme FDE is already applied.")
    assert len(events(db, "acme-fde")) == 1


def test_a_status_for_a_role_not_on_file_is_404(client, db):
    r = client.post(f"{P}/roles/nope/status", json={"status": "applied"}, headers=HEADERS)
    assert (r.status_code, r.json()["detail"]) == (404, "No role nope.")


# ── The resume ───────────────────────────────────────────────────────────────

PDF = b"%PDF-1.7 made-up resume"


@pytest.fixture
def resumes(tmp_path, monkeypatch) -> Path:
    """data/resumes/ with one PDF in it, base.pdf."""
    monkeypatch.setattr(store, "CAREER_DIR", tmp_path)
    folder = tmp_path / "resumes"
    folder.mkdir()
    (folder / "base.pdf").write_bytes(PDF)
    return folder


def test_a_role_can_be_given_a_resume_in_resumes_and_have_it_cleared(client, db, resumes):
    r = client.patch(f"{P}/roles/beta-applied-ai", json={"resume_file": "base.pdf"}, headers=HEADERS)
    assert r.status_code == 200
    assert role(db, "beta-applied-ai")["resume_file"] == "base.pdf"
    client.patch(f"{P}/roles/beta-applied-ai", json={"resume_file": None}, headers=HEADERS)
    assert role(db, "beta-applied-ai")["resume_file"] is None


def test_a_new_role_can_come_with_its_resume(client, db, resumes):
    r = client.post(f"{P}/roles", json={"company": "Gamma", "title": "DS", "resume_file": "base.pdf"}, headers=HEADERS)
    assert role(db, r.json()["role_id"])["resume_file"] == "base.pdf"


def test_a_resume_not_in_resumes_is_refused(client, db, resumes):
    r = client.patch(f"{P}/roles/beta-applied-ai", json={"resume_file": "gone.pdf"}, headers=HEADERS)
    assert (r.status_code, r.json()["detail"]) == (409, "There is no gone.pdf in data/resumes.")
    assert role(db, "beta-applied-ai")["resume_file"] is None


@pytest.mark.parametrize("name", ["../career.db", "../base.pdf", "/etc/base.pdf", "base.docx", ".pdf", "sub/base.pdf"])
def test_a_resume_that_is_not_a_pdf_name_is_422(client, db, resumes, name):
    assert client.patch(f"{P}/roles/beta-applied-ai", json={"resume_file": name}, headers=HEADERS).status_code == 422


def test_applying_keeps_a_read_only_copy_of_the_resume_as_sent(client, db, resumes):
    client.patch(f"{P}/roles/beta-applied-ai", json={"resume_file": "base.pdf"}, headers=HEADERS)
    r = client.post(
        f"{P}/roles/beta-applied-ai/status", json={"status": "applied", "date": "2026-10-09"}, headers=HEADERS
    )
    assert r.status_code == 200
    assert role(db, "beta-applied-ai")["sent_file"] == "beta-applied-ai-2026-10-09.pdf"
    copy = store.CAREER_DIR / "sent/beta-applied-ai-2026-10-09.pdf"
    assert copy.read_bytes() == PDF
    assert copy.stat().st_mode & 0o222 == 0
    (resumes / "base.pdf").write_bytes(b"%PDF-1.7 edited later")
    assert copy.read_bytes() == PDF


def test_applying_with_no_resume_chosen_keeps_no_copy(client, db, resumes):
    client.post(f"{P}/roles/beta-applied-ai/status", json={"status": "applied"}, headers=HEADERS)
    assert role(db, "beta-applied-ai")["sent_file"] is None
    assert not (store.CAREER_DIR / "sent").exists()


def test_applying_when_the_resume_has_left_resumes_is_refused(client, db, resumes):
    client.patch(f"{P}/roles/beta-applied-ai", json={"resume_file": "base.pdf"}, headers=HEADERS)
    (resumes / "base.pdf").unlink()
    r = client.post(f"{P}/roles/beta-applied-ai/status", json={"status": "applied"}, headers=HEADERS)
    assert (r.status_code, r.json()["detail"]) == (409, "There is no base.pdf in data/resumes.")
    assert (role(db, "beta-applied-ai")["status"], events(db, "beta-applied-ai")) == ("interested", [])


def test_applying_again_the_same_day_keeps_the_first_copy(client, db, resumes):
    client.patch(f"{P}/roles/beta-applied-ai", json={"resume_file": "base.pdf"}, headers=HEADERS)
    for status in ("applied", "rejected", "applied"):
        client.post(f"{P}/roles/beta-applied-ai/status", json={"status": status, "date": "2026-10-09"}, headers=HEADERS)
    assert role(db, "beta-applied-ai")["sent_file"] == "beta-applied-ai-2026-10-09-2.pdf"
    assert sorted(p.name for p in (store.CAREER_DIR / "sent").iterdir()) == [
        "beta-applied-ai-2026-10-09-2.pdf",
        "beta-applied-ai-2026-10-09.pdf",
    ]


def test_applying_from_an_older_version_keeps_no_copy(client, db, resumes):
    """Refused, the change saved nothing, so no sent copy is left behind either."""
    client.patch(f"{P}/roles/beta-applied-ai", json={"resume_file": "base.pdf"}, headers=HEADERS)  # now version 2
    r = client.post(f"{P}/roles/beta-applied-ai/status", json={"status": "applied", "version": 1}, headers=HEADERS)
    assert r.status_code == 409
    assert not any((store.CAREER_DIR / "sent").glob("*"))
    r = client.post(
        f"{P}/roles/beta-applied-ai/status",
        json={"status": "applied", "version": 2, "date": "2026-10-09"},
        headers=HEADERS,
    )
    assert role(db, "beta-applied-ai")["sent_file"] == "beta-applied-ai-2026-10-09.pdf"  # not -2


@pytest.mark.parametrize("status", ["screen", "offer", "rejected"])
def test_other_statuses_keep_no_copy(client, db, resumes, status):
    client.patch(f"{P}/roles/beta-applied-ai", json={"resume_file": "base.pdf"}, headers=HEADERS)
    client.post(f"{P}/roles/beta-applied-ai/status", json={"status": status}, headers=HEADERS)
    assert role(db, "beta-applied-ai")["sent_file"] is None


# ── Drafts ───────────────────────────────────────────────────────────────────

LETTER = "Hi Beta team,\n\nMade-up letter.\n\nCheers,\nSam\n"


@pytest.fixture
def drafts(tmp_path, monkeypatch, resumes) -> Path:
    """data/drafts/beta-applied-ai/ with a resume draft and two cover letters, and resumes/base.pdf."""
    folder = tmp_path / "drafts/beta-applied-ai"
    folder.mkdir(parents=True)
    (folder / "resume-1.md").write_text("Made-up resume.")
    (folder / "cover-letter-1.md").write_text("Older letter.")
    (folder / "cover-letter-2.md").write_text(LETTER)
    return folder


def open_todos(db, role_id):
    return [
        r["text"]
        for r in db.execute("SELECT text FROM todos WHERE role_id = ? AND done_on IS NULL ORDER BY id", (role_id,))
    ]


def test_approving_a_draft_saves_it_and_checks_off_its_review_todo(client, db, drafts):
    for text in ("Review resume draft", "Review cover letter"):
        add_todo(client, {"text": text, "kind": "resume", "role_id": "beta-applied-ai"})
    add_todo(client, {"text": "Review cover letter", "role_id": "acme-fde"})
    r = client.patch(f"{P}/roles/beta-applied-ai", json={"approved_cover_letter": "cover-letter-2.md"}, headers=HEADERS)
    assert r.status_code == 200
    assert role(db, "beta-applied-ai")["approved_cover_letter"] == "cover-letter-2.md"
    assert "Review cover letter" not in open_todos(db, "beta-applied-ai")
    assert "Review resume draft" in open_todos(db, "beta-applied-ai")
    assert "Review cover letter" in open_todos(db, "acme-fde")  # another role's is left alone
    client.patch(f"{P}/roles/beta-applied-ai", json={"approved_resume_draft": "resume-1.md"}, headers=HEADERS)
    assert open_todos(db, "beta-applied-ai") == []


def test_approving_another_draft_replaces_the_approval_and_null_clears_it(client, db, drafts):
    for name in ("cover-letter-1.md", "cover-letter-2.md"):
        client.patch(f"{P}/roles/beta-applied-ai", json={"approved_cover_letter": name}, headers=HEADERS)
    assert role(db, "beta-applied-ai")["approved_cover_letter"] == "cover-letter-2.md"
    client.patch(f"{P}/roles/beta-applied-ai", json={"approved_cover_letter": None}, headers=HEADERS)
    assert role(db, "beta-applied-ai")["approved_cover_letter"] is None


def test_approving_a_draft_that_is_not_there_is_refused_and_changes_nothing(client, db, drafts):
    add_todo(client, {"text": "Review cover letter", "role_id": "beta-applied-ai"})
    r = client.patch(f"{P}/roles/beta-applied-ai", json={"approved_cover_letter": "cover-letter-3.md"}, headers=HEADERS)
    assert (r.status_code, r.json()["detail"]) == (409, "There is no cover-letter-3.md in data/drafts/beta-applied-ai.")
    assert role(db, "beta-applied-ai")["approved_cover_letter"] is None
    assert "Review cover letter" in open_todos(db, "beta-applied-ai")


def test_a_draft_is_looked_for_only_in_its_own_roles_folder(client, db, drafts):
    r = client.patch(f"{P}/roles/acme-fde", json={"approved_cover_letter": "cover-letter-2.md"}, headers=HEADERS)
    assert r.status_code == 409


@pytest.mark.parametrize(
    "field, name",
    [
        ("approved_cover_letter", "resume-1.md"),
        ("approved_resume_draft", "cover-letter-1.md"),
        ("approved_cover_letter", "../beta-applied-ai/cover-letter-1.md"),
        ("approved_cover_letter", "cover-letter-1.txt"),
        ("approved_cover_letter", "cover-letter-0.md"),
        ("approved_resume_draft", "resume.md"),
    ],
)
def test_a_draft_name_of_the_wrong_kind_or_shape_is_422(client, db, drafts, field, name):
    assert client.patch(f"{P}/roles/beta-applied-ai", json={field: name}, headers=HEADERS).status_code == 422


def test_a_new_role_cannot_come_approved(client, db, drafts):
    r = client.post(
        f"{P}/roles",
        json={"company": "Gamma", "title": "DS", "approved_cover_letter": "cover-letter-1.md"},
        headers=HEADERS,
    )
    assert r.status_code == 422


def test_applying_keeps_a_read_only_copy_of_the_approved_letter_beside_the_resume(client, db, drafts):
    client.patch(
        f"{P}/roles/beta-applied-ai",
        json={"resume_file": "base.pdf", "approved_cover_letter": "cover-letter-2.md"},
        headers=HEADERS,
    )
    client.post(f"{P}/roles/beta-applied-ai/status", json={"status": "applied", "date": "2026-10-09"}, headers=HEADERS)
    row = role(db, "beta-applied-ai")
    assert (row["sent_file"], row["sent_cover_letter"]) == (
        "beta-applied-ai-2026-10-09.pdf",
        "beta-applied-ai-2026-10-09-cover-letter.md",
    )
    copy = store.CAREER_DIR / "sent/beta-applied-ai-2026-10-09-cover-letter.md"
    assert copy.read_text() == LETTER
    assert copy.stat().st_mode & 0o222 == 0
    (drafts / "cover-letter-2.md").write_text("Edited later.")
    assert copy.read_text() == LETTER


def test_applying_with_no_letter_approved_keeps_none(client, db, drafts):
    client.post(f"{P}/roles/beta-applied-ai/status", json={"status": "applied"}, headers=HEADERS)
    assert role(db, "beta-applied-ai")["sent_cover_letter"] is None


def test_applying_when_the_approved_letter_has_gone_is_refused_and_keeps_no_copy(client, db, drafts):
    client.patch(
        f"{P}/roles/beta-applied-ai",
        json={"resume_file": "base.pdf", "approved_cover_letter": "cover-letter-2.md"},
        headers=HEADERS,
    )
    (drafts / "cover-letter-2.md").unlink()
    r = client.post(f"{P}/roles/beta-applied-ai/status", json={"status": "applied"}, headers=HEADERS)
    assert (r.status_code, r.json()["detail"]) == (409, "There is no cover-letter-2.md in data/drafts/beta-applied-ai.")
    assert role(db, "beta-applied-ai")["status"] == "interested"
    assert not (store.CAREER_DIR / "sent").exists()


def test_applying_again_the_same_day_numbers_the_letter_like_the_resume(client, db, drafts):
    client.patch(f"{P}/roles/beta-applied-ai", json={"approved_cover_letter": "cover-letter-2.md"}, headers=HEADERS)
    for status in ("applied", "rejected", "applied"):
        client.post(f"{P}/roles/beta-applied-ai/status", json={"status": status, "date": "2026-10-09"}, headers=HEADERS)
    assert role(db, "beta-applied-ai")["sent_cover_letter"] == "beta-applied-ai-2026-10-09-2-cover-letter.md"


# ── Draft PDFs ───────────────────────────────────────────────────────────────


def make_pdf(client, name, role_id="beta-applied-ai"):
    return client.post(f"{P}/roles/{role_id}/drafts/{name}/pdf", headers=HEADERS)


def age(path: Path, seconds: int = 60) -> None:
    """Makes path look written seconds ago, so a draft saved after it is newer."""
    then = path.stat().st_mtime - seconds
    os.utime(path, (then, then))


def test_making_a_pdf_writes_it_beside_the_draft_and_says_its_pages(client, db, drafts):
    r = make_pdf(client, "cover-letter-2.md")
    assert r.status_code == 200
    assert r.json() == {"role_id": "beta-applied-ai", "name": "cover-letter-2.pdf", "pages": 1}
    pdf = (drafts / "cover-letter-2.pdf").read_bytes()
    assert pdf.startswith(b"%PDF-") and b"Made-up letter" not in pdf  # text is in the PDF's own encoding
    assert sorted(p.name for p in drafts.iterdir()) == [
        "cover-letter-1.md",
        "cover-letter-2.md",
        "cover-letter-2.pdf",
        "resume-1.md",
    ]


def test_making_it_again_replaces_that_drafts_pdf_only(client, db, drafts):
    make_pdf(client, "cover-letter-1.md")
    make_pdf(client, "cover-letter-2.md")
    first = (drafts / "cover-letter-1.pdf").read_bytes()
    (drafts / "cover-letter-2.md").write_text("Shorter.")
    make_pdf(client, "cover-letter-2.md")
    assert (drafts / "cover-letter-1.pdf").read_bytes() == first
    assert not any(p.name.startswith(".") for p in drafts.iterdir())


def test_making_a_pdf_replaces_a_link_where_it_goes_and_never_writes_through_it(client, db, drafts, tmp_path):
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"keep")
    (drafts / "resume-1.pdf").symlink_to(outside)
    assert make_pdf(client, "resume-1.md").status_code == 200
    assert outside.read_bytes() == b"keep" and not (drafts / "resume-1.pdf").is_symlink()


def test_a_pdf_of_a_draft_that_is_not_there_is_refused(client, db, drafts):
    r = make_pdf(client, "resume-2.md")
    assert (r.status_code, r.json()["detail"]) == (409, "There is no resume-2.md in data/drafts/beta-applied-ai.")
    assert make_pdf(client, "cover-letter-2.md", role_id="acme-fde").status_code == 409  # Beta's, not Acme's
    assert make_pdf(client, "resume-1.md", role_id="no-such-role").status_code == 404


def test_a_draft_that_is_a_link_out_of_its_folder_is_not_followed(client, db, drafts, tmp_path):
    """The read API refuses it too (writekit.files), so the writer never lays out a file from elsewhere."""
    elsewhere = tmp_path / "elsewhere.md"
    elsewhere.write_text("Not a draft.")
    (drafts / "resume-2.md").symlink_to(elsewhere)
    r = make_pdf(client, "resume-2.md")
    assert (r.status_code, r.json()["detail"]) == (409, "There is no resume-2.md in data/drafts/beta-applied-ai.")
    assert not (drafts / "resume-2.pdf").exists()
    r = client.patch(f"{P}/roles/beta-applied-ai", json={"approved_resume_draft": "resume-2.md"}, headers=HEADERS)
    assert r.status_code == 409 and role(db, "beta-applied-ai")["approved_resume_draft"] is None


def test_a_resume_that_is_a_link_out_of_resumes_is_not_followed(client, db, resumes, tmp_path):
    elsewhere = tmp_path / "elsewhere.pdf"
    elsewhere.write_bytes(PDF)
    (resumes / "linked.pdf").symlink_to(elsewhere)
    r = client.patch(f"{P}/roles/beta-applied-ai", json={"resume_file": "linked.pdf"}, headers=HEADERS)
    assert (r.status_code, r.json()["detail"]) == (409, "There is no linked.pdf in data/resumes.")


@pytest.mark.parametrize(
    "name", ["resume-1.pdf", "resume.md", "../acme-fde/resume-1.md", "notes-1.md", "resume-0.md", ".resume-1.md"]
)
def test_a_pdf_of_a_name_that_is_not_a_draft_is_422(client, db, drafts, name):
    assert make_pdf(client, name).status_code in (404, 422)  # a "/" in it is no such route
    assert not any(p.suffix == ".pdf" for p in drafts.iterdir())


def test_making_a_pdf_never_writes_through_a_link_left_in_its_place(client, db, drafts, tmp_path):
    elsewhere = tmp_path / "elsewhere.txt"
    elsewhere.write_text("not yours to write")
    (drafts / ".resume-1.pdf.part").symlink_to(elsewhere)
    assert make_pdf(client, "resume-1.md").status_code == 200
    assert elsewhere.read_text() == "not yours to write"
    assert (drafts / "resume-1.pdf").read_bytes().startswith(b"%PDF")


def test_a_draft_that_cannot_be_laid_out_is_refused_with_a_reason(client, db, drafts):
    (drafts / "resume-1.md").write_text(">" * 5000 + " x")
    r = make_pdf(client, "resume-1.md")
    assert r.status_code == 409 and r.json()["detail"].startswith("Could not make the PDF:")
    assert not (drafts / "resume-1.pdf").exists()


def test_a_resume_draft_over_one_page_is_refused_and_gets_no_pdf(client, db, drafts):
    (drafts / "resume-1.md").write_text("Sam Lee\n\n" + "\n".join(f"- Made-up bullet {n}" for n in range(120)))
    r = make_pdf(client, "resume-1.md")
    assert (r.status_code, r.json()["detail"]) == (
        409,
        "resume-1.md runs over one page (3 pages), so it has no PDF. Shorten it and make the PDF again.",
    )
    assert not any(p.suffix == ".pdf" or p.name.startswith(".") for p in drafts.iterdir())
    r = client.patch(f"{P}/roles/beta-applied-ai", json={"approved_resume_draft": "resume-1.md"}, headers=HEADERS)
    assert r.status_code == 409 and role(db, "beta-applied-ai")["approved_resume_draft"] is None


def test_a_resume_just_over_one_page_says_about_how_many_lines(client, db, drafts, monkeypatch):
    monkeypatch.setattr(records.render, "render", lambda markdown, kind: records.render.Rendered(b"%PDF-", 2, 3))
    assert (
        make_pdf(client, "resume-1.md")
        .json()["detail"]
        .startswith("resume-1.md runs over one page (about 3 lines over)")
    )
    monkeypatch.setattr(records.render, "render", lambda markdown, kind: records.render.Rendered(b"%PDF-", 2, 1))
    assert "(about 1 line over)" in make_pdf(client, "resume-1.md").json()["detail"]


def test_a_cover_letter_over_one_page_still_gets_its_pdf(client, db, drafts):
    (drafts / "cover-letter-2.md").write_text("\n\n".join(f"Made-up paragraph {n}." for n in range(80)))
    r = make_pdf(client, "cover-letter-2.md")
    assert r.status_code == 200 and r.json()["pages"] > 1


def test_approving_a_resume_draft_makes_its_pdf_the_roles_resume(client, db, drafts):
    add_todo(client, {"text": "Review resume draft", "kind": "resume", "role_id": "beta-applied-ai"})
    r = client.patch(f"{P}/roles/beta-applied-ai", json={"approved_resume_draft": "resume-1.md"}, headers=HEADERS)
    assert r.status_code == 200
    row = role(db, "beta-applied-ai")
    assert (row["approved_resume_draft"], row["resume_file"]) == ("resume-1.md", "beta-applied-ai-resume-1.pdf")
    assert (store.resumes() / "beta-applied-ai-resume-1.pdf").read_bytes() == (drafts / "resume-1.pdf").read_bytes()
    assert open_todos(db, "beta-applied-ai") == []


def test_approving_uses_the_pdf_there_unless_the_draft_changed_since(client, db, drafts):
    make_pdf(client, "resume-1.md")
    (drafts / "resume-1.pdf").write_bytes(b"%PDF-1.7 made earlier")
    client.patch(f"{P}/roles/beta-applied-ai", json={"approved_resume_draft": "resume-1.md"}, headers=HEADERS)
    assert (store.resumes() / "beta-applied-ai-resume-1.pdf").read_bytes() == b"%PDF-1.7 made earlier"
    age(drafts / "resume-1.pdf")
    (drafts / "resume-1.md").write_text("Edited by hand.")
    client.patch(f"{P}/roles/beta-applied-ai", json={"approved_resume_draft": None}, headers=HEADERS)
    client.patch(f"{P}/roles/beta-applied-ai", json={"approved_resume_draft": "resume-1.md"}, headers=HEADERS)
    assert (drafts / "resume-1.pdf").read_bytes().startswith(b"%PDF-1.7\n")  # made again
    assert role(db, "beta-applied-ai")["resume_file"] == "beta-applied-ai-resume-1-2.pdf"  # never over the first
    assert (store.resumes() / "beta-applied-ai-resume-1.pdf").read_bytes() == b"%PDF-1.7 made earlier"


def test_approving_the_same_resume_again_reuses_its_copy(client, db, drafts):
    for name in ("resume-1.md", None, "resume-1.md"):
        client.patch(f"{P}/roles/beta-applied-ai", json={"approved_resume_draft": name}, headers=HEADERS)
    assert role(db, "beta-applied-ai")["resume_file"] == "beta-applied-ai-resume-1.pdf"
    assert sorted(p.name for p in store.resumes().iterdir()) == ["base.pdf", "beta-applied-ai-resume-1.pdf"]


def test_unapproving_leaves_the_resume_chosen(client, db, drafts):
    client.patch(f"{P}/roles/beta-applied-ai", json={"approved_resume_draft": "resume-1.md"}, headers=HEADERS)
    client.patch(f"{P}/roles/beta-applied-ai", json={"approved_resume_draft": None}, headers=HEADERS)
    row = role(db, "beta-applied-ai")
    assert (row["approved_resume_draft"], row["resume_file"]) == (None, "beta-applied-ai-resume-1.pdf")


def test_approving_a_resume_and_choosing_one_at_once_is_refused(client, db, drafts):
    r = client.patch(
        f"{P}/roles/beta-applied-ai",
        json={"approved_resume_draft": "resume-1.md", "resume_file": "base.pdf"},
        headers=HEADERS,
    )
    assert r.status_code == 400
    assert role(db, "beta-applied-ai")["resume_file"] is None


def test_a_refused_approval_leaves_no_pdf_in_resumes(client, db, drafts):
    client.patch(f"{P}/roles/beta-applied-ai", json={"notes": "now version 2"}, headers=HEADERS)
    r = client.patch(
        f"{P}/roles/beta-applied-ai", json={"approved_resume_draft": "resume-1.md", "version": 1}, headers=HEADERS
    )
    assert r.status_code == 409
    assert sorted(p.name for p in store.resumes().iterdir()) == ["base.pdf"]
    assert role(db, "beta-applied-ai")["resume_file"] is None
    r = client.patch(
        f"{P}/roles/acme-fde", json={"approved_resume_draft": "resume-1.md"}, headers=HEADERS
    )  # not Acme's
    assert r.status_code == 409 and sorted(p.name for p in store.resumes().iterdir()) == ["base.pdf"]


def test_an_approval_that_fails_after_copying_its_pdf_takes_the_copy_back(client, db, drafts, monkeypatch):
    def update(*_args):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(records, "update", update)  # the last step, after the copy
    with pytest.raises(sqlite3.OperationalError):
        client.patch(f"{P}/roles/beta-applied-ai", json={"approved_resume_draft": "resume-1.md"}, headers=HEADERS)
    assert sorted(p.name for p in store.resumes().iterdir()) == ["base.pdf"]
    row = role(db, "beta-applied-ai")
    assert (row["approved_resume_draft"], row["resume_file"]) == (None, None)


def test_a_copy_that_fails_partway_leaves_no_half_file_in_sent(client, db, resumes, monkeypatch):
    client.patch(f"{P}/roles/beta-applied-ai", json={"resume_file": "base.pdf"}, headers=HEADERS)

    def copyfileobj(source, out):
        out.write(source.read(4))
        raise OSError("disk full")

    monkeypatch.setattr(records.shutil, "copyfileobj", copyfileobj)
    with pytest.raises(OSError, match="disk full"):
        client.post(
            f"{P}/roles/beta-applied-ai/status", json={"status": "applied", "date": "2026-10-09"}, headers=HEADERS
        )
    assert list(store.sent().iterdir()) == []
    row = role(db, "beta-applied-ai")
    assert (row["status"], row["sent_file"]) == ("interested", None)


def test_applying_keeps_the_approved_letter_as_a_read_only_pdf_beside_its_text(client, db, drafts):
    client.patch(f"{P}/roles/beta-applied-ai", json={"approved_cover_letter": "cover-letter-2.md"}, headers=HEADERS)
    client.post(f"{P}/roles/beta-applied-ai/status", json={"status": "applied", "date": "2026-10-09"}, headers=HEADERS)
    assert role(db, "beta-applied-ai")["sent_cover_letter"] == "beta-applied-ai-2026-10-09-cover-letter.md"
    copy = store.sent() / "beta-applied-ai-2026-10-09-cover-letter.pdf"
    assert copy.read_bytes() == (drafts / "cover-letter-2.pdf").read_bytes()
    assert copy.stat().st_mode & 0o222 == 0


def test_applying_again_the_same_day_numbers_the_letter_pdf_with_its_text(client, db, drafts):
    client.patch(f"{P}/roles/beta-applied-ai", json={"approved_cover_letter": "cover-letter-2.md"}, headers=HEADERS)
    store.sent().mkdir()
    (store.sent() / "beta-applied-ai-2026-10-09-cover-letter.pdf").write_bytes(b"a stray PDF with no text beside it")
    client.post(f"{P}/roles/beta-applied-ai/status", json={"status": "applied", "date": "2026-10-09"}, headers=HEADERS)
    assert role(db, "beta-applied-ai")["sent_cover_letter"] == "beta-applied-ai-2026-10-09-2-cover-letter.md"
    assert sorted(p.name for p in store.sent().iterdir()) == [
        "beta-applied-ai-2026-10-09-2-cover-letter.md",
        "beta-applied-ai-2026-10-09-2-cover-letter.pdf",
        "beta-applied-ai-2026-10-09-cover-letter.pdf",
    ]


def test_applying_with_a_letter_that_cannot_be_laid_out_is_refused_and_keeps_nothing(client, db, drafts):
    client.patch(
        f"{P}/roles/beta-applied-ai",
        json={"resume_file": "base.pdf", "approved_cover_letter": "cover-letter-2.md"},
        headers=HEADERS,
    )
    (drafts / "cover-letter-2.md").write_text(">" * 5000 + " x")
    r = client.post(f"{P}/roles/beta-applied-ai/status", json={"status": "applied"}, headers=HEADERS)
    assert r.status_code == 409 and r.json()["detail"].startswith("Could not make the PDF:")
    assert role(db, "beta-applied-ai")["status"] == "interested"
    assert not store.sent().exists() or not any(store.sent().iterdir())


def test_applying_makes_the_letters_pdf_without_holding_the_write_lock(client, db, drafts, monkeypatch):
    """Laying out a PDF can take seconds; no other change waits on it."""
    client.patch(f"{P}/roles/beta-applied-ai", json={"approved_cover_letter": "cover-letter-2.md"}, headers=HEADERS)
    laid_out = records.render.render
    rendered = []

    def render_while_another_change_saves(*args):
        other = sqlite3.connect(store.db.path, timeout=0)
        other.execute("BEGIN IMMEDIATE")  # "database is locked" if the change held the lock
        other.execute("ROLLBACK")
        other.close()
        rendered.append(args[1])
        return laid_out(*args)

    monkeypatch.setattr(records.render, "render", render_while_another_change_saves)
    r = client.post(
        f"{P}/roles/beta-applied-ai/status", json={"status": "applied", "date": "2026-10-09"}, headers=HEADERS
    )
    assert r.status_code == 200 and rendered == ["cover-letter"]
    assert role(db, "beta-applied-ai")["sent_cover_letter"] == "beta-applied-ai-2026-10-09-cover-letter.md"


def test_applying_that_fails_after_copying_leaves_nothing_in_sent(client, db, drafts, monkeypatch):
    client.patch(
        f"{P}/roles/beta-applied-ai",
        json={"resume_file": "base.pdf", "approved_cover_letter": "cover-letter-2.md"},
        headers=HEADERS,
    )
    saved = records.insert

    def insert(conn, table, fields):
        if table == "events":
            raise OSError("disk full")
        return saved(conn, table, fields)

    monkeypatch.setattr(records, "insert", insert)
    with pytest.raises(OSError, match="disk full"):
        client.post(
            f"{P}/roles/beta-applied-ai/status", json={"status": "applied", "date": "2026-10-09"}, headers=HEADERS
        )
    assert list(store.sent().iterdir()) == []
    row = role(db, "beta-applied-ai")
    assert (row["status"], row["sent_file"], row["sent_cover_letter"]) == ("interested", None, None)


def test_applying_while_the_letter_is_changed_is_refused_and_keeps_nothing(client, db, drafts, monkeypatch):
    client.patch(f"{P}/roles/beta-applied-ai", json={"approved_cover_letter": "cover-letter-2.md"}, headers=HEADERS)
    laid_out = records.render.render

    def render_while_the_page_approves_another(*args):
        with sqlite3.connect(store.db.path) as other:
            other.execute("UPDATE roles SET approved_cover_letter = 'cover-letter-1.md' WHERE id = 'beta-applied-ai'")
        other.close()
        return laid_out(*args)

    monkeypatch.setattr(records.render, "render", render_while_the_page_approves_another)
    r = client.post(f"{P}/roles/beta-applied-ai/status", json={"status": "applied"}, headers=HEADERS)
    assert (r.status_code, r.json()["detail"]) == (
        409,
        "The resume or cover letter for Beta Applied AI changed just now. Nothing was saved; try again.",
    )
    assert role(db, "beta-applied-ai")["status"] == "interested"
    assert list(store.sent().iterdir()) == []


def test_a_database_from_before_drafts_gets_their_columns(tmp_path, monkeypatch):
    """schema.sql as it was at version 0, migrated, has the same roles columns as schema.sql now."""
    old = re.sub(
        r"\n    (approved_resume_draft|approved_cover_letter|sent_cover_letter)\s+TEXT,", "", seed.SCHEMA.read_text()
    )
    old = old.replace("PRAGMA user_version = 1;", "PRAGMA user_version = 0;")
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(old)
    monkeypatch.setattr(store.db, "path", path)
    store.db.migrate()
    new = sqlite3.connect(":memory:")
    new.executescript(seed.SCHEMA.read_text())

    def columns(conn):
        return {r[1] for r in conn.execute("PRAGMA table_info(roles)")}

    with sqlite3.connect(path) as conn:
        assert columns(conn) == columns(new)
        assert {"approved_resume_draft", "approved_cover_letter", "sent_cover_letter"} <= columns(conn)


# ── The timeline ─────────────────────────────────────────────────────────────


def test_an_event_needs_only_its_kind_and_is_today(client, db):
    r = client.post(f"{P}/roles/acme-fde/events", json={"kind": "note"}, headers=HEADERS)
    event = events(db, "acme-fde")[-1]
    assert r.json() == {"role_id": "acme-fde", "event_id": event["id"]}
    assert (event["date"], event["kind"], event["text"], event["prep_link"]) == (TODAY, "note", None, None)


def test_an_event_can_say_when_what_and_where_the_prep_is(client, db):
    body = {
        "kind": "interview",
        "date": "2026-10-20",
        "text": "Round 1: decomposition.",
        "prep_link": "fde-prep/round-1.md",
    }
    client.post(f"{P}/roles/acme-fde/events", json=body, headers=HEADERS)
    event = events(db, "acme-fde")[-1]
    assert {k: event[k] for k in body} == body


@pytest.mark.parametrize("kind", ["applied", "offer", "rejection"])
def test_an_event_that_is_a_status_change_is_refused_with_the_way_to_do_it(client, db, kind):
    r = client.post(f"{P}/roles/beta-applied-ai/events", json={"kind": kind}, headers=HEADERS)
    assert r.status_code == 400 and "Change the status" in r.json()["detail"]
    assert events(db, "beta-applied-ai") == []


def test_an_event_for_a_role_not_on_file_is_404(client, db):
    r = client.post(f"{P}/roles/nope/events", json={"kind": "note"}, headers=HEADERS)
    assert r.status_code == 404 and count(db, "events") == 1


def test_an_event_can_be_fixed_and_a_field_cleared(client, db):
    event_id = events(db, "acme-fde")[0]["id"]
    r = client.patch(f"{P}/events/{event_id}", json={"date": "2026-07-25", "text": "Via referral."}, headers=HEADERS)
    assert r.json() == {"role_id": "acme-fde", "event_id": event_id}
    client.patch(f"{P}/events/{event_id}", json={"text": None}, headers=HEADERS)
    event = events(db, "acme-fde")[0]
    assert (event["date"], event["kind"], event["text"]) == ("2026-07-25", "applied", None)


def test_fixing_an_event_not_on_file_is_404(client, db):
    assert client.patch(f"{P}/events/999", json={"text": "x"}, headers=HEADERS).status_code == 404


# ── Editing a role ───────────────────────────────────────────────────────────


def test_notes_and_details_can_be_edited_and_cleared(client, db):
    r = client.patch(
        f"{P}/roles/acme-fde", json={"notes": "Recruiter is slow.\nFollow up Friday.", "comp": None}, headers=HEADERS
    )
    assert r.json() == {"role_id": "acme-fde"}
    acme = role(db, "acme-fde")
    assert (acme["notes"], acme["comp"], acme["title"]) == ("Recruiter is slow.\nFollow up Friday.", None, "FDE")


def test_every_detail_but_status_can_be_edited_at_once(client, db):
    body = {
        "company": "Acme Corp",
        "title": "Senior FDE",
        "location": "Remote",
        "link": "https://jobs.example/2",
        "applied_via": "https://acme.example/apply",
        "comp": "$180k",
    }
    client.patch(f"{P}/roles/acme-fde", json=body, headers=HEADERS)
    acme = role(db, "acme-fde")
    assert {k: acme[k] for k in body} == body
    assert acme["status"] == "applied"


def test_blank_notes_are_saved_as_nothing(client, db):
    client.patch(f"{P}/roles/acme-fde", json={"notes": "  "}, headers=HEADERS)
    assert role(db, "acme-fde")["notes"] is None


def test_editing_a_role_not_on_file_is_404(client, db):
    assert client.patch(f"{P}/roles/nope", json={"notes": "x"}, headers=HEADERS).status_code == 404


# ── Todos ────────────────────────────────────────────────────────────────────


def todos(db, role_id=None):
    where, args = ("role_id = ?", (role_id,)) if role_id else ("role_id IS NULL", ())
    return [dict(r) for r in db.execute(f"SELECT * FROM todos WHERE {where} ORDER BY id", args)]


def add_todo(client, body):
    return client.post(f"{P}/todos", json=body, headers=HEADERS)


def test_a_new_role_starts_with_the_usual_todos_open_and_due_tomorrow(client, db):
    role_id = client.post(f"{P}/roles", json={"company": "Gamma", "title": "FDE"}, headers=HEADERS).json()["role_id"]
    tomorrow = (dt.date.today() + dt.timedelta(days=1)).isoformat()
    assert [(t["text"], t["kind"], t["due_on"], t["done_on"]) for t in todos(db, role_id)] == [
        ("Update resume", "resume", tomorrow, None),
        ("Apply to role", "apply", tomorrow, None),
        ("Message recruiter", "outreach", tomorrow, None),
    ]


def add_with_starters(client, db, monkeypatch, tmp_path, text):
    """Adds Gamma FDE with the starter todos file holding text. Returns the answer."""
    starters = tmp_path / "starter-todos.json"
    starters.write_text(text)
    monkeypatch.setenv("CAREER_STARTER_TODOS", str(starters))
    return client.post(f"{P}/roles", json={"company": "Gamma", "title": "FDE"}, headers=HEADERS)


def test_a_new_role_starts_with_the_todos_in_the_file_each_due_its_own_day(client, db, monkeypatch, tmp_path):
    body = [
        {"text": "Research the team", "kind": "prep", "due_in_days": 0},
        {"text": "Ask Sam for a referral", "kind": "outreach", "due_in_days": 3},
    ]
    role_id = add_with_starters(client, db, monkeypatch, tmp_path, json.dumps(body)).json()["role_id"]
    in_days = lambda n: (dt.date.today() + dt.timedelta(days=n)).isoformat()  # noqa: E731
    assert [(t["text"], t["kind"], t["due_on"]) for t in todos(db, role_id)] == [
        ("Research the team", "prep", in_days(0)),
        ("Ask Sam for a referral", "outreach", in_days(3)),
    ]


def test_an_empty_starter_list_adds_the_role_with_no_todos(client, db, monkeypatch, tmp_path):
    role_id = add_with_starters(client, db, monkeypatch, tmp_path, "[]").json()["role_id"]
    assert role(db, role_id)["company"] == "Gamma"
    assert todos(db, role_id) == []


@pytest.mark.parametrize(
    ("text", "says"),
    [
        (
            '[{"text": "Lunch", "kind": "food", "due_in_days": 1}]',
            "todo 1: kind: Input should be 'resume', 'apply', 'outreach', 'prep', 'follow-up' or 'other'.",
        ),
        ('[{"text": " ", "kind": "prep", "due_in_days": 1}]', "todo 1: text: String should have at least 1 character."),
        (
            '[{"text": "Prep", "kind": "prep", "due_in_days": 1},'
            ' {"text": "Prep", "kind": "prep", "due_in_days": 400}]',
            "todo 2: due_in_days: Input should be less than or equal to 365.",
        ),
        (
            '[{"text": "Prep", "kind": "prep", "due_in_days": "2"}]',
            "todo 1: due_in_days: Input should be a valid integer.",
        ),
        ('[{"text": "Prep", "kind": "prep"}]', "todo 1: due_in_days: Field required."),
        (
            '[{"text": "Prep", "kind": "prep", "due_in_days": 1, "due": 2}]',
            "todo 1: due: Extra inputs are not permitted.",
        ),
        (
            '[{"text": "Prep", "kind": "prep", "due_in_days": 1},]',
            "is not valid JSON (line 1): Illegal trailing comma before end of array.",
        ),
        ('{"text": "Prep"}', "must be a list of todos, like [] for none."),
    ],
)
def test_a_bad_starter_file_refuses_the_add_naming_the_file_and_the_entry(
    client, db, monkeypatch, tmp_path, text, says
):
    r = add_with_starters(client, db, monkeypatch, tmp_path, text)
    assert r.status_code == 409
    assert r.json()["detail"] == f"{tmp_path / 'starter-todos.json'}{', ' if says.startswith('todo') else ' '}{says}"
    assert count(db, "roles") == len(ROLES)


def test_a_missing_starter_file_refuses_the_add(client, db, monkeypatch, tmp_path):
    monkeypatch.setenv("CAREER_STARTER_TODOS", str(tmp_path / "gone.json"))
    r = client.post(f"{P}/roles", json={"company": "Gamma", "title": "FDE"}, headers=HEADERS)
    assert (r.status_code, r.json()["detail"]) == (
        409,
        f"{tmp_path / 'gone.json'} is missing. It lists the todos a new role starts with; [] means none.",
    )
    assert count(db, "roles") == len(ROLES)


def test_a_todo_sent_with_no_kind_is_other_and_can_be_given_one(client, db):
    add_todo(client, {"text": "Read the 10-K"})
    add_todo(client, {"text": "Mock interview", "kind": "prep"})
    assert [t["kind"] for t in todos(db)] == ["other", "prep"]


def test_a_todos_kind_can_be_changed(client, db):
    todo_id = add_todo(client, {"text": "Ping Ann"}).json()["todo_id"]
    client.patch(f"{P}/todos/{todo_id}", json={"kind": "follow-up"}, headers=HEADERS)
    assert todos(db)[0]["kind"] == "follow-up"


def test_a_todo_needs_only_its_text_and_can_belong_to_no_role(client, db):
    r = add_todo(client, {"text": " Update base resume "})
    assert r.status_code == 200
    [todo] = todos(db)
    assert r.json() == {"todo_id": todo["id"], "role_id": None}
    assert (todo["text"], todo["due_on"], todo["done_on"]) == ("Update base resume", None, None)


def test_a_todo_can_be_for_a_role_and_due_on_a_day(client, db):
    add_todo(client, {"role_id": "acme-fde", "text": "Ask Ann for a referral", "due_on": "2026-10-10"})
    assert [(t["text"], t["due_on"]) for t in todos(db, "acme-fde")] == [("Ask Ann for a referral", "2026-10-10")]


def test_a_todo_for_a_role_not_on_file_is_404_and_nothing_is_added(client, db):
    assert add_todo(client, {"role_id": "nope", "text": "x"}).status_code == 404
    assert count(db, "todos") == 0


def test_checking_a_todo_marks_it_done_today_and_unchecking_opens_it(client, db):
    todo_id = add_todo(client, {"role_id": "acme-fde", "text": "Apply"}).json()["todo_id"]
    r = client.patch(f"{P}/todos/{todo_id}", json={"done": True}, headers=HEADERS)
    assert r.json() == {"todo_id": todo_id, "role_id": "acme-fde"}
    assert todos(db, "acme-fde")[0]["done_on"] == dt.date.today().isoformat()
    client.patch(f"{P}/todos/{todo_id}", json={"done": False}, headers=HEADERS)
    assert todos(db, "acme-fde")[0]["done_on"] is None


def test_checking_a_done_todo_again_keeps_the_day_it_was_done(client, db):
    todo_id = add_todo(client, {"text": "Apply"}).json()["todo_id"]
    db.execute("UPDATE todos SET done_on = '2026-10-01' WHERE id = ?", (todo_id,))
    db.commit()
    client.patch(f"{P}/todos/{todo_id}", json={"done": True}, headers=HEADERS)
    assert todos(db)[0]["done_on"] == "2026-10-01"


def test_a_todos_text_and_day_can_be_fixed_and_the_day_cleared(client, db):
    todo_id = add_todo(client, {"text": "Aply", "due_on": "2026-10-10"}).json()["todo_id"]
    client.patch(f"{P}/todos/{todo_id}", json={"text": "Apply", "due_on": None}, headers=HEADERS)
    assert (todos(db)[0]["text"], todos(db)[0]["due_on"]) == ("Apply", None)


def test_a_todo_can_be_deleted_and_brought_back(client, db):
    todo_id = add_todo(client, {"text": "Apply"}).json()["todo_id"]
    r = client.delete(f"{P}/todos/{todo_id}", headers=HEADERS)
    assert (r.status_code, r.json()) == (200, {"todo_id": todo_id, "role_id": None})
    assert todos(db)[0]["deleted_on"] == TODAY
    assert client.patch(f"{P}/todos/{todo_id}", json={"done": True}, headers=HEADERS).status_code == 404
    assert client.post(f"{P}/todos/{todo_id}/restore", headers=HEADERS).json() == {"todo_id": todo_id, "role_id": None}
    assert todos(db)[0]["deleted_on"] is None
    r = client.post(f"{P}/todos/{todo_id}/restore", headers=HEADERS)
    assert (r.status_code, r.json()["detail"]) == (409, "That todo is not deleted.")


@pytest.mark.parametrize("method", ["patch", "delete"])
def test_a_todo_not_on_file_is_404(client, method):
    kwargs = {"json": {"done": True}} if method == "patch" else {}
    assert getattr(client, method)(f"{P}/todos/999", headers=HEADERS, **kwargs).status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {},  # no text
        {"text": " "},  # blank text
        {"text": "x", "done_on": "2026-10-01"},  # done is set by checking it, not sent
        {"text": "x", "due_on": "soon"},  # not a day
        {"text": "x", "role_id": "Acme FDE"},  # not a role id
        {"text": "x", "kind": "errand"},  # not a kind of todo
    ],
)
def test_a_todo_that_is_not_well_formed_is_422(client, db, body):
    assert add_todo(client, body).status_code == 422
    assert count(db, "todos") == 0


@pytest.mark.parametrize(
    "body",
    [
        {"text": None},
        {"done": None},
        {"done": "yes"},
        {"role_id": "beta-applied-ai"},
        {"kind": None},
        {"kind": "errand"},
    ],
)
def test_a_todo_edit_that_is_not_well_formed_is_422(client, db, body):
    todo_id = add_todo(client, {"role_id": "acme-fde", "text": "Apply"}).json()["todo_id"]
    assert client.patch(f"{P}/todos/{todo_id}", json=body, headers=HEADERS).status_code == 422
    assert (todos(db, "acme-fde")[0]["text"], todos(db, "acme-fde")[0]["done_on"]) == ("Apply", None)


def test_deleting_a_role_takes_its_todos(db):
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("INSERT INTO todos (role_id, text) VALUES ('acme-fde', 'Apply')")
    db.execute("DELETE FROM events WHERE role_id = 'acme-fde'")
    db.execute("DELETE FROM roles WHERE id = 'acme-fde'")
    assert count(db, "todos") == 0


# ── The posting ──────────────────────────────────────────────────────────────


def test_a_new_role_can_keep_its_posting_with_the_day_it_was_saved(client, db):
    body = {"company": "Gamma", "title": "FDE", "location": "Remote", "comp": "$1", "posting": "About us.\n\n- Python"}
    role_id = client.post(f"{P}/roles", json=body, headers=HEADERS).json()["role_id"]
    assert (role(db, role_id)["posting"], role(db, role_id)["posting_on"]) == ("About us.\n\n- Python", TODAY)


def test_a_posting_can_be_saved_later_and_cleared_with_its_day(client, db):
    client.patch(f"{P}/roles/acme-fde", json={"posting": "Pasted."}, headers=HEADERS)
    assert (role(db, "acme-fde")["posting"], role(db, "acme-fde")["posting_on"]) == ("Pasted.", TODAY)
    client.patch(f"{P}/roles/acme-fde", json={"posting": None}, headers=HEADERS)
    assert (role(db, "acme-fde")["posting"], role(db, "acme-fde")["posting_on"]) == (None, None)


def test_editing_something_else_keeps_the_postings_day(client, db):
    db.execute("UPDATE roles SET posting = 'Old.', posting_on = '2026-01-01' WHERE id = 'acme-fde'")
    db.commit()
    client.patch(f"{P}/roles/acme-fde", json={"notes": "x"}, headers=HEADERS)
    assert role(db, "acme-fde")["posting_on"] == "2026-01-01"


def test_what_stands_out_is_hers_to_write(client, db):
    client.patch(f"{P}/roles/acme-fde", json={"notable": "Travel 25%\nTeam of 6"}, headers=HEADERS)
    assert role(db, "acme-fde")["notable"] == "Travel 25%\nTeam of 6"


def test_reading_a_posting_returns_a_draft_and_saves_nothing(client, db, monkeypatch):
    draft = {"company": "Acme", "title": "FDE", "location": None, "comp": None, "posting": "Text.", "from": "feed"}
    monkeypatch.setattr(writer.posting, "read", lambda link: {**draft, "seen": link})
    r = client.post(f"{P}/postings/read", json={"link": "https://jobs.example/1"}, headers=HEADERS)
    assert r.json() == {**draft, "seen": "https://jobs.example/1"}
    assert count(db, "roles") == 2


def test_a_posting_that_cannot_be_read_says_why_and_what_to_do(client, monkeypatch):
    def unreadable(link):
        raise writer.posting.Unreadable("That page shows no posting without a browser. Paste the posting text instead.")

    monkeypatch.setattr(writer.posting, "read", unreadable)
    r = client.post(f"{P}/postings/read", json={"link": "https://jobs.example/1"}, headers=HEADERS)
    assert r.status_code == 409 and r.json()["detail"].endswith("Paste the posting text instead.")


@pytest.mark.parametrize("body", [{}, {"link": "ftp://jobs.example/1"}, {"link": "jobs"}])
def test_reading_needs_an_https_link(client, body):
    assert client.post(f"{P}/postings/read", json=body, headers=HEADERS).status_code == 422


def test_the_postings_day_is_set_by_the_writer_not_sent(client, db):
    assert client.patch(f"{P}/roles/acme-fde", json={"posting_on": "2026-01-01"}, headers=HEADERS).status_code == 422


# ── Saving from an older copy ────────────────────────────────────────────────
# The page sends the version it saw. If the row changed since (on another screen), the save is
# refused rather than writing over the newer change. A save with no version is not checked.


def test_an_edit_from_the_version_she_saw_is_saved_and_moves_the_version_on(client, db):
    r = client.patch(f"{P}/roles/acme-fde", json={"notes": "x", "version": 1}, headers=HEADERS)
    assert r.status_code == 200
    assert (role(db, "acme-fde")["notes"], role(db, "acme-fde")["version"]) == ("x", 2)


@pytest.mark.parametrize(
    "method, path, body",
    [
        ("patch", "/roles/acme-fde", {"notes": "x"}),
        ("post", "/roles/acme-fde/status", {"status": "screen"}),
    ],
)
def test_a_role_saved_from_an_older_version_is_refused_and_unchanged(client, db, method, path, body):
    client.patch(f"{P}/roles/acme-fde", json={"comp": "$1"}, headers=HEADERS)  # another screen: now version 2
    r = getattr(client, method)(P + path, json={**body, "version": 1}, headers=HEADERS)
    assert (r.status_code, r.json()["detail"]) == (409, STALE)
    assert (role(db, "acme-fde")["notes"], role(db, "acme-fde")["status"]) == (None, "applied")


def test_a_status_change_moves_the_version_on(client, db):
    client.post(f"{P}/roles/acme-fde/status", json={"status": "screen", "version": 1}, headers=HEADERS)
    assert role(db, "acme-fde")["version"] == 2


def test_an_event_saved_from_an_older_version_is_refused(client, db):
    event_id = events(db, "acme-fde")[0]["id"]
    client.patch(f"{P}/events/{event_id}", json={"text": "first", "version": 1}, headers=HEADERS)
    r = client.patch(f"{P}/events/{event_id}", json={"text": "second", "version": 1}, headers=HEADERS)
    assert r.status_code == 409 and events(db, "acme-fde")[0]["text"] == "first"


def test_a_todo_saved_from_an_older_version_is_refused(client, db):
    todo_id = add_todo(client, {"text": "Apply"}).json()["todo_id"]
    client.patch(f"{P}/todos/{todo_id}", json={"done": True}, headers=HEADERS)
    r = client.patch(f"{P}/todos/{todo_id}", json={"text": "Apply now", "version": 1}, headers=HEADERS)
    assert r.status_code == 409 and todos(db)[0]["text"] == "Apply"


# ── Timeline kinds that are status changes ───────────────────────────────────


@pytest.mark.parametrize("kind", ["applied", "offer", "rejection"])
def test_an_event_cannot_be_fixed_into_a_status_change(client, db, kind):
    event_id = client.post(f"{P}/roles/acme-fde/events", json={"kind": "note"}, headers=HEADERS).json()["event_id"]
    r = client.patch(f"{P}/events/{event_id}", json={"kind": kind}, headers=HEADERS)
    assert r.status_code == 400 and "Change the status" in r.json()["detail"]
    assert events(db, "acme-fde")[-1]["kind"] == "note"


def test_a_status_change_on_the_timeline_keeps_its_kind(client, db):
    event_id = events(db, "acme-fde")[0]["id"]
    r = client.patch(f"{P}/events/{event_id}", json={"kind": "note"}, headers=HEADERS)
    assert r.status_code == 400 and "keeps its kind" in r.json()["detail"]
    assert client.patch(f"{P}/events/{event_id}", json={"kind": "applied"}, headers=HEADERS).status_code == 200


def test_other_kinds_can_be_fixed(client, db):
    event_id = client.post(f"{P}/roles/acme-fde/events", json={"kind": "note"}, headers=HEADERS).json()["event_id"]
    client.patch(f"{P}/events/{event_id}", json={"kind": "interview"}, headers=HEADERS)
    assert events(db, "acme-fde")[-1]["kind"] == "interview"


# ── Deleting, with undo ──────────────────────────────────────────────────────
# A deleted role or event is hidden (deleted_on), never removed, so undo brings it back exactly.


def test_deleting_a_role_hides_it_and_keeps_its_timeline_and_todos(client, db):
    add_todo(client, {"role_id": "acme-fde", "text": "Apply"})
    r = client.delete(f"{P}/roles/acme-fde", headers=HEADERS)
    assert r.json() == {"role_id": "acme-fde"}
    assert role(db, "acme-fde")["deleted_on"] == TODAY
    assert (len(events(db, "acme-fde")), len(todos(db, "acme-fde"))) == (1, 1)


def test_undo_brings_a_deleted_role_back(client, db):
    client.delete(f"{P}/roles/acme-fde", headers=HEADERS)
    assert client.post(f"{P}/roles/acme-fde/restore", headers=HEADERS).json() == {"role_id": "acme-fde"}
    assert role(db, "acme-fde")["deleted_on"] is None


@pytest.mark.parametrize(
    "method, path, body",
    [
        ("patch", "/roles/acme-fde", {"notes": "x"}),
        ("post", "/roles/acme-fde/status", {"status": "screen"}),
        ("post", "/roles/acme-fde/events", {"kind": "note"}),
        ("post", "/todos", {"role_id": "acme-fde", "text": "Apply"}),
        ("delete", "/roles/acme-fde", None),
    ],
)
def test_a_deleted_role_cannot_be_changed(client, db, method, path, body):
    client.delete(f"{P}/roles/acme-fde", headers=HEADERS)
    kwargs = {"json": body} if body is not None else {}
    r = getattr(client, method)(P + path, headers=HEADERS, **kwargs)
    assert (r.status_code, r.json()["detail"]) == (404, "No role acme-fde.")


def test_a_todo_of_a_deleted_role_cannot_be_changed(client, db):
    todo_id = add_todo(client, {"role_id": "acme-fde", "text": "Apply"}).json()["todo_id"]
    client.delete(f"{P}/roles/acme-fde", headers=HEADERS)
    assert client.patch(f"{P}/todos/{todo_id}", json={"done": True}, headers=HEADERS).status_code == 404
    assert client.delete(f"{P}/todos/{todo_id}", headers=HEADERS).status_code == 404


def test_bringing_back_a_role_that_is_not_deleted_is_refused(client, db):
    r = client.post(f"{P}/roles/acme-fde/restore", headers=HEADERS)
    assert (r.status_code, r.json()["detail"]) == (409, "Acme FDE is not deleted.")


def test_adding_a_role_she_deleted_says_to_bring_it_back(client, db):
    """Its id stays taken so undo can bring it back. Adding it again would make a second Acme FDE
    (acme-fde-2) beside the hidden one, so it is refused with the way back."""
    client.delete(f"{P}/roles/acme-fde", headers=HEADERS)
    r = client.post(f"{P}/roles", json={"company": "Acme", "title": "FDE"}, headers=HEADERS)
    day = dt.date.today()
    assert (r.status_code, r.json()["detail"]) == (
        409,
        f"You deleted Acme FDE on {day:%b} {day.day}. Bring it back from Recently deleted on the Career page.",
    )
    assert count(db, "roles") == 2


def test_adding_a_role_she_deleted_is_refused_whatever_its_id(client, db):
    """The deleted one was the second of its name (acme-fde-2); the name is what matches, any case."""
    client.post(f"{P}/roles", json={"company": "Acme", "title": "FDE"}, headers=HEADERS)
    client.delete(f"{P}/roles/acme-fde-2", headers=HEADERS)
    r = client.post(f"{P}/roles", json={"company": "acme", "title": "fde"}, headers=HEADERS)
    assert r.status_code == 409 and r.json()["detail"].startswith("You deleted Acme FDE on ")


def test_a_second_role_of_the_same_name_still_gets_the_next_id_when_the_first_is_there(client, db):
    assert client.post(f"{P}/roles", json={"company": "Acme", "title": "FDE"}, headers=HEADERS).json() == {
        "role_id": "acme-fde-2"
    }


def test_an_event_can_be_deleted_and_brought_back(client, db):
    event_id = events(db, "acme-fde")[0]["id"]
    assert client.delete(f"{P}/events/{event_id}", headers=HEADERS).json() == {
        "role_id": "acme-fde",
        "event_id": event_id,
    }
    assert events(db, "acme-fde")[0]["deleted_on"] == TODAY
    assert client.patch(f"{P}/events/{event_id}", json={"text": "x"}, headers=HEADERS).status_code == 404
    client.post(f"{P}/events/{event_id}/restore", headers=HEADERS)
    assert events(db, "acme-fde")[0]["deleted_on"] is None


def test_an_event_of_a_deleted_role_cannot_be_changed(client, db):
    event_id = events(db, "acme-fde")[0]["id"]
    client.delete(f"{P}/roles/acme-fde", headers=HEADERS)
    assert client.patch(f"{P}/events/{event_id}", json={"text": "x"}, headers=HEADERS).status_code == 404
    assert client.delete(f"{P}/events/{event_id}", headers=HEADERS).status_code == 404


# ── What a change must not be ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "path, body",
    [
        ("/roles", {"title": "FDE"}),  # no company
        ("/roles", {"company": " ", "title": "FDE"}),  # blank company
        ("/roles", {"company": "C", "title": "T", "id": "c-t"}),  # the id is made, never sent
        ("/roles", {"company": "C", "title": "T", "status": "applied"}),  # status changes on its own route
        ("/roles", {"company": "C", "title": "T", "link": "jobs"}),  # not a web link
        ("/roles", {"company": "C", "title": "T", "applied_via": "ftp://x.example"}),  # not https
        ("/roles", {"company": "C", "title": "T", "referral_person_id": "Ann"}),  # not a person id
        ("/roles/acme-fde", {"status": "offer"}),  # status changes on its own route
        ("/roles/acme-fde", {"company": None}),  # company can't be cleared
        ("/roles/acme-fde", {"sent_file": "x.pdf"}),  # the sent copy is made only on applying
        ("/roles/acme-fde/status", {}),  # no status
        ("/roles/acme-fde/status", {"status": "ghosted"}),  # not a status
        ("/roles/acme-fde/status", {"status": "offer", "date": "2026-02-30"}),  # not a day
        ("/roles/acme-fde/events", {}),  # no kind
        ("/roles/acme-fde/events", {"kind": "lunch"}),  # not a kind
        ("/roles/acme-fde/events", {"kind": "note", "txt": "typo"}),  # not a field
    ],
)
def test_a_change_that_is_not_well_formed_is_422_and_saves_nothing(client, db, path, body):
    method = client.patch if path == "/roles/acme-fde" else client.post
    assert method(P + path, json=body, headers=HEADERS).status_code == 422
    assert (count(db, "roles"), count(db, "events"), role(db, "acme-fde")["status"]) == (2, 1, "applied")


def test_a_role_id_in_the_path_that_is_not_an_id_is_422(client):
    assert client.patch(f"{P}/roles/Acme FDE", json={"notes": "x"}, headers=HEADERS).status_code == 422


# ── The fixed lists ──────────────────────────────────────────────────────────


def checked(column: str) -> list[str]:
    schema = Path(seed.SCHEMA).read_text()
    return re.findall(r"'([^']+)'", re.search(rf"{column}\s+IN\s*\(([^)]*)\)", schema)[1])


def test_the_writer_knows_the_lists_in_schema_sql():
    assert list(typing.get_args(writer.Status)) == checked("status")
    assert list(typing.get_args(writer.Kind)) == checked("kind")


def test_the_writer_knows_the_kinds_of_todo_in_schema_sql():
    todos_table = re.search(r"CREATE TABLE todos \((.*?)\n\);", Path(seed.SCHEMA).read_text(), re.S)[1]
    kinds = re.findall(r"'([^']+)'", re.search(r"kind\s+.*?IN\s*\(([^)]*)\)", todos_table)[1])
    assert list(typing.get_args(writer.TodoKind)) == kinds


def test_the_starter_todos_shipped_and_tested_are_the_same_and_load():
    import records

    assert json.loads(records.DEFAULT_STARTER_TODOS.read_text()) == json.loads(STARTERS.read_text())
    assert [t.kind for t in records.starter_todos()] == ["resume", "apply", "outreach"]


def test_every_status_that_logs_names_a_kind_in_the_list():
    import records

    assert set(records.STATUS_EVENT) <= set(checked("status"))
    assert set(records.STATUS_EVENT.values()) <= set(checked("kind"))


def test_schema_is_current():
    assert_schema_current(seed.SCHEMA, store.db.migrations)


def test_fields_json_lists_what_each_request_body_accepts():
    """The page's tests hold every change it sends to this file (web/src/plugins/career/career.test.ts)."""
    assert_fields_current(
        Path(writer.__file__).with_name("fields.json"),
        {
            "PostingLink": writer.PostingLink,
            "NewRole": writer.NewRole,
            "RoleEdit": writer.RoleEdit,
            "StatusChange": writer.StatusChange,
            "NewEvent": writer.NewEvent,
            "EventEdit": writer.EventEdit,
            "NewTodo": writer.NewTodo,
            "TodoEdit": writer.TodoEdit,
        },
    )
