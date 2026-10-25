"""The Drafts viewer: Claude's drafts for a role, seen as PDFs or text, copied, approved; applying
keeps the approved letter and resume as sent."""

import os
import time
from pathlib import Path

import pytest
from playwright.sync_api import expect

from conftest import unique

LETTER_LINE = "I also write our carrier scorecard SQL models on Postgres."


class Drafted:
    """A role with the drafts the skills would have written for it, oldest first: resume-1.md,
    cover-letter-1.md, cover-letter-2.md, and the review todos they add."""

    def __init__(self, app):
        self.app = app
        self.id = app.add_role(unique("Acme Freight"), "Senior Analytics Engineer")
        self.folder: Path = app.data / "drafts" / self.id
        self.folder.mkdir(parents=True)
        testdata = app.root / "tools/career/testdata"
        letter = (testdata / "cover-letter.md").read_text()
        drafts = {
            "resume-1.md": (testdata / "resume.md").read_text(),
            "cover-letter-1.md": letter.replace(LETTER_LINE, "An earlier letter."),
            "cover-letter-2.md": letter,
        }
        an_hour_ago = time.time() - 3600
        for n, (name, text) in enumerate(drafts.items()):
            (self.folder / name).write_text(text)
            os.utime(self.folder / name, (an_hour_ago + n, an_hour_ago + n))  # the page shows the latest first
        for text in ("Review resume draft", "Review cover letter"):
            app.write("POST", "/api/career/write/todos", {"role_id": self.id, "text": text, "kind": "resume"})

    def text(self, name: str) -> str:
        return (self.folder / name).read_text()

    def pdf(self, name: str) -> bytes:
        return (self.folder / name).with_suffix(".pdf").read_bytes()

    def make_pdf(self, name: str) -> None:
        self.app.write("POST", f"/api/career/write/roles/{self.id}/drafts/{name}/pdf")

    def role(self) -> dict:
        return self.app.role(self.id)

    def open_todos(self) -> list[str]:
        return [t["text"] for t in self.role()["todos"] if not t["done_on"]]


@pytest.fixture
def drafted(app) -> Drafted:
    return Drafted(app)


def test_drafts_are_seen_as_pdfs_copied_approved_and_kept_on_apply(page, app, drafted):
    page.goto(f"/#/career/{drafted.id}")
    panel = page.get_by_role("region", name="Drafts")
    picker = panel.get_by_label("Draft")
    expect(picker).to_have_value("cover-letter-2.md")  # the latest first
    assert [d["name"] for d in app.read(f"/api/career/roles/{drafted.id}/drafts")["drafts"] if d["pdf"]] == []

    # Seen as the PDF that would be sent.
    expect(panel.get_by_text("No PDF of this draft yet")).to_be_visible()
    panel.get_by_role("button", name="Make PDF").click()
    expect(panel.get_by_role("img", name="Cover letter 2, page 1 of 1")).to_be_visible(timeout=20_000)
    assert drafted.pdf("cover-letter-2.md").startswith(b"%PDF")

    # Its text, copied exactly.
    panel.get_by_role("button", name="Text", exact=True).last.click()
    panel.get_by_role("button", name="Copy Cover letter 2").click()
    expect(panel.get_by_role("button", name="Copied Cover letter 2")).to_be_visible()
    assert page.evaluate("navigator.clipboard.readText()") == drafted.text("cover-letter-2.md")

    # Another version, picked.
    picker.select_option("cover-letter-1.md")
    expect(panel.get_by_text("An earlier letter.")).to_be_visible()
    picker.select_option("cover-letter-2.md")

    # Approved: the letter, then the resume, whose PDF becomes the role's resume.
    panel.get_by_role("button", name="Approve this cover letter").click()
    expect(panel.get_by_role("button", name="Unapprove")).to_be_visible()
    assert drafted.role()["approved_cover_letter"] == "cover-letter-2.md"
    assert "Review cover letter" not in drafted.open_todos()

    picker.select_option("resume-1.md")
    panel.get_by_role("button", name="Approve this resume").click()
    expect(panel.get_by_text("Its PDF is this role's resume")).to_be_visible(timeout=20_000)
    role = drafted.role()
    resume = f"{drafted.id}-resume-1.pdf"
    assert (role["approved_resume_draft"], role["resume_file"]) == ("resume-1.md", resume)
    assert (app.data / "resumes" / resume).read_bytes() == drafted.pdf("resume-1.md")
    assert "Review resume draft" not in drafted.open_todos()
    expect(page.get_by_role("region", name="Resume").get_by_label("Resume to send")).to_have_value(resume)

    # Applied on the page: the letter and resume that went are kept, read-only.
    status = page.get_by_role("region", name="Status")
    status.get_by_label("Status").select_option("applied")
    status.get_by_role("button", name="Save").click()
    expect(panel.get_by_text("Cover letter sent")).to_be_visible()
    expect(panel.get_by_role("img", name="The sent cover letter, page 1 of 1")).to_be_visible(timeout=20_000)
    role = drafted.role()
    sent = app.data / "sent"
    letter, letter_pdf = sent / role["sent_cover_letter"], sent / role["sent_cover_letter"].replace(".md", ".pdf")
    assert letter.read_text() == drafted.text("cover-letter-2.md")
    assert letter_pdf.read_bytes() == drafted.pdf("cover-letter-2.md")
    assert (sent / role["sent_file"]).read_bytes() == drafted.pdf("resume-1.md")
    assert all(f.stat().st_mode & 0o222 == 0 for f in (letter, letter_pdf, sent / role["sent_file"]))


@pytest.mark.parametrize("page", ["phone"], indirect=True)
def test_on_the_phone_drafts_draw_as_pdfs_that_fit_the_screen(page, drafted):
    for name in ("resume-1.md", "cover-letter-2.md"):
        drafted.make_pdf(name)  # as the skills do after writing one
    page.goto(f"/#/career/{drafted.id}")
    panel = page.get_by_role("region", name="Drafts")
    expect(panel.get_by_role("img", name="Cover letter 2, page 1 of 1")).to_be_visible(timeout=20_000)
    box = panel.bounding_box()
    assert box["width"] <= page.viewport_size["width"]
    assert all(canvas.bounding_box()["width"] <= box["width"] for canvas in panel.locator("canvas").all())

    panel.get_by_role("button", name="Text", exact=True).last.click()
    expect(panel.get_by_text(LETTER_LINE)).to_be_visible()
    panel.get_by_label("Draft").select_option("resume-1.md")
    panel.get_by_role("button", name="PDF", exact=True).last.click()
    expect(panel.get_by_role("img", name="Resume 1, page 1 of 1")).to_be_visible(timeout=20_000)


def test_a_draft_is_drawn_in_the_fonts_its_pdf_carries(page, drafted):
    drafted.make_pdf("resume-1.md")
    page.goto(f"/#/career/{drafted.id}")
    panel = page.get_by_role("region", name="Drafts")
    panel.get_by_label("Draft").select_option("resume-1.md")
    expect(panel.get_by_role("img", name="Resume 1, page 1 of 1")).to_be_visible(timeout=20_000)
    # pdf.js names each font it loads from a PDF g_d<doc>_f<n>. None loaded means it fell back to
    # a stand-in font, which drops letters ("Airfow").
    loaded = page.evaluate("[...document.fonts].filter(f => f.status === 'loaded').map(f => f.family)")
    assert any(family.startswith("g_d") for family in loaded), loaded


def test_a_resume_over_one_page_gets_no_pdf_and_the_page_says_why(page, app, drafted, watch):
    watch.allow(409)
    long = drafted.text("resume-1.md") + "".join(f"\n- Made-up bullet {n}" for n in range(40))
    (drafted.folder / "resume-2.md").write_text(long)
    page.goto(f"/#/career/{drafted.id}")
    panel = page.get_by_role("region", name="Drafts")
    panel.get_by_label("Draft").select_option("resume-2.md")
    panel.get_by_role("button", name="Make PDF").click()
    expect(panel.get_by_text("resume-2.md runs over one page")).to_be_visible(timeout=20_000)
    assert not (drafted.folder / "resume-2.pdf").exists()
