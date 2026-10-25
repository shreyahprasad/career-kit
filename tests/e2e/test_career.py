"""The Career page: adding a role, editing it, its status, its todos, deleting and bringing back."""

import datetime as dt
import json
import re

import pytest
from playwright.sync_api import expect

from conftest import eventually, unique

TODAY = dt.date.today().isoformat()
POSTING = """Senior Analytics Engineer

You will own the models behind our carrier scorecards.

- SQL and Python
- Airflow"""


def role_on_page(page) -> str:
    """The role the page is on, from #/career/<id>."""
    return page.url.rsplit("/", 1)[1]


@pytest.mark.phone_too
def test_the_page_opens_on_the_board_and_both_tabs_load(page, app):
    assert app.read("/api/health") == {"ok": True, "app": "career-kit"}
    page.goto("/")
    expect(page.get_by_role("heading", name="Career", level=1)).to_be_visible()
    page.get_by_role("link", name="Networking").click()
    expect(page.get_by_role("heading", name="Networking", level=1)).to_be_visible()
    page.get_by_role("link", name="Career").click()
    expect(page.get_by_role("button", name="+ Add a role")).to_be_visible()


@pytest.mark.phone_too
def test_a_role_added_by_hand_opens_with_its_starter_todos(page, app):
    company = unique("Acme Freight")
    page.goto("/#/career")
    page.get_by_role("button", name="+ Add a role").click()
    form = page.get_by_role("form", name="Add a role")
    form.get_by_label("Company").fill(company)
    form.get_by_label("Title").fill("Analytics Engineer")
    form.get_by_role("button", name="Add", exact=True).click()
    expect(page.get_by_role("heading", name="Analytics Engineer", level=1)).to_be_visible()

    role = app.role(role_on_page(page))
    assert (role["company"], role["title"], role["status"]) == (company, "Analytics Engineer", "interested")
    starters = [t["text"] for t in json.loads((app.root / "config/starter-todos.json").read_text())]
    assert sorted(t["text"] for t in role["todos"]) == sorted(starters)
    for text in starters:
        expect(page.get_by_role("region", name="To do").get_by_text(text)).to_be_visible()


@pytest.mark.phone_too
def test_a_role_from_a_pasted_posting_keeps_its_text(page, app):
    page.goto("/#/career")
    page.get_by_role("button", name="+ Add a role").click()
    form = page.get_by_role("form", name="Add a role")
    form.get_by_label("Company").fill(unique("Northwind Shipping"))
    form.get_by_label("Title").fill("Senior Analytics Engineer")
    form.get_by_role("button", name="Paste the posting text").click()
    form.get_by_label("Posting text").fill(POSTING)
    form.get_by_role("button", name="Add", exact=True).click()
    expect(page.get_by_role("heading", name="Senior Analytics Engineer", level=1)).to_be_visible()

    role = app.role(role_on_page(page))
    assert (role["posting"], role["posting_on"]) == (POSTING, TODAY)
    posting = page.get_by_role("region", name="Posting")
    posting.get_by_role("button", name="18 words").click()  # folded until asked for
    expect(posting.get_by_text("You will own the models behind our carrier scorecards.")).to_be_visible()


def test_a_link_inside_your_network_is_not_read_and_says_why(page, app, watch):
    watch.allow(409)  # the writer refuses it, with the reason the page shows
    before = len(app.read("/api/career/roles")["roles"])
    page.goto("/#/career")
    page.get_by_role("button", name="+ Add a role").click()
    form = page.get_by_role("form", name="Add a role")
    form.get_by_label("Posting link").fill("https://127.0.0.1/jobs/1")
    form.get_by_role("button", name="Read").click()
    expect(form.get_by_text("That link leads inside your network, so it is not read.")).to_be_visible()
    assert len(app.read("/api/career/roles")["roles"]) == before


def test_an_edit_made_elsewhere_meanwhile_is_not_written_over(page, app, watch):
    watch.allow(409)
    role_id = app.add_role(unique("Northwind Shipping"), "Data Analyst")
    page.goto(f"/#/career/{role_id}")
    page.get_by_role("button", name="Edit", exact=True).click()
    form = page.get_by_role("form", name="Role details")
    form.get_by_label("Location").fill("Columbus, OH")
    app.write("PATCH", f"/api/career/write/roles/{role_id}", {"comp": "$90k-$110k"})  # Claude, from the phone
    form.get_by_role("button", name="Save").click()

    expect(form.get_by_text("This changed somewhere else since you opened it")).to_be_visible()
    expect(form.get_by_label("Location")).to_have_value("Columbus, OH")  # what was typed is kept
    role = app.role(role_id)
    assert (role["location"], role["comp"]) == (None, "$90k-$110k")

    page.reload()
    page.get_by_role("button", name="Edit", exact=True).click()
    form.get_by_label("Location").fill("Columbus, OH")
    form.get_by_role("button", name="Save").click()
    expect(page.get_by_text("Columbus, OH")).to_be_visible()
    role = app.role(role_id)
    assert (role["location"], role["comp"]) == ("Columbus, OH", "$90k-$110k")


def test_applying_logs_it_and_keeps_the_resume_that_was_sent(page, app):
    resume = unique("arya-stark").replace(" ", "-") + ".pdf"
    pdf = b"%PDF-1.7 Arya Stark, made up"
    (app.data / "resumes" / resume).write_bytes(pdf)
    role_id = app.add_role(unique("Acme Freight"), "Analytics Engineer", resume_file=resume)
    page.goto(f"/#/career/{role_id}")

    status = page.get_by_role("region", name="Status")
    status.get_by_label("Status").select_option("applied")
    expect(status.get_by_text("This adds “Applied” to the timeline.")).to_be_visible()
    status.get_by_label("Note").fill("Through the careers page")
    status.get_by_role("button", name="Save").click()
    expect(page.get_by_role("region", name="Timeline")).to_contain_text("Through the careers page")

    role = app.role(role_id)
    assert role["status"] == "applied"
    assert [(e["kind"], e["date"], e["text"]) for e in role["events"]] == [
        ("applied", TODAY, "Through the careers page")
    ]
    sent = app.data / "sent" / role["sent_file"]
    assert sent.read_bytes() == pdf
    assert sent.stat().st_mode & 0o222 == 0  # read-only


@pytest.mark.phone_too
def test_todos_are_added_checked_off_and_brought_back_after_a_delete(page, app):
    role_id = app.add_role(unique("Acme Freight"), "Analytics Engineer")
    text = unique("Ask Syrio for a referral")
    page.goto(f"/#/career/{role_id}")
    todos = page.get_by_role("region", name="To do")
    todos.get_by_role("button", name="+ Add a todo").click()
    todos.get_by_label("New todo").fill(text)
    todos.get_by_role("radio", name="Outreach").click()
    todos.get_by_role("button", name="Add", exact=True).click()
    expect(todos.get_by_role("checkbox", name=text)).to_be_visible()
    todos.get_by_role("button", name="Close").click()

    def saved():
        return next((t for t in app.role(role_id)["todos"] if t["text"] == text), None)

    assert (saved()["kind"], saved()["done_on"]) == ("outreach", None)

    todos.get_by_role("checkbox", name=text).click()  # it moves into Done, folded
    expect(todos.get_by_role("button", name="Done · 1")).to_be_visible()
    eventually(lambda: saved()["done_on"] == TODAY)

    todos.get_by_role("button", name="Done · 1").click()
    todos.get_by_role("checkbox", name=text).click()
    expect(todos.get_by_role("button", name="Done · 1")).to_have_count(0)
    eventually(lambda: saved()["done_on"] is None)

    todos.get_by_role("button", name=f"Delete “{text}”").click()
    undo = page.get_by_role("status").filter(has_text=f"Deleted “{text}”.")
    expect(undo).to_be_visible()
    assert saved() is None
    undo.get_by_role("button", name="Undo").click()
    expect(todos.get_by_role("checkbox", name=text)).to_be_visible()
    assert saved() is not None


def test_a_todo_for_the_whole_search_is_added_on_the_board(page, app):
    text = unique("Update LinkedIn headline")
    page.goto("/#/career")
    todos = page.get_by_role("region", name="To do")
    todos.get_by_role("button", name=re.compile(r"^To do")).click()  # folded until opened
    todos.get_by_role("button", name="+ Add a todo").click()
    todos.get_by_label("New todo").fill(text)
    todos.get_by_role("button", name="Add", exact=True).click()
    expect(todos.get_by_role("checkbox", name=text)).to_be_visible()
    todo = next(t for t in app.read("/api/career/todos")["todos"] if t["text"] == text)
    assert (todo["role"], todo["kind"]) == (None, "other")


def test_a_deleted_role_comes_back_with_undo_and_from_recently_deleted(page, app):
    company = unique("Northwind Shipping")
    role_id = app.add_role(company, "Data Analyst")

    def deleted() -> list[str]:
        return [r["id"] for r in app.read("/api/career/deleted")["roles"]]

    def delete_it():
        page.goto(f"/#/career/{role_id}")
        page.get_by_role("button", name="Edit", exact=True).click()
        page.get_by_role("button", name="Delete role").click()
        expect(page.get_by_role("heading", name="Career", level=1)).to_be_visible()  # back on the board
        assert role_id in deleted()

    delete_it()
    undo = page.get_by_role("status").filter(has_text=f"Deleted {company} Data Analyst.")
    undo.get_by_role("button", name="Undo").click()
    expect(page.get_by_role("heading", name="Data Analyst", level=1)).to_be_visible()
    assert role_id not in deleted()

    delete_it()
    page.get_by_role("status").get_by_role("button", name="Dismiss").click()
    bin = page.get_by_role("region", name="Recently deleted")
    bin.get_by_role("button", name=re.compile(r"^Recently deleted")).click()
    bin.get_by_role("listitem").filter(has_text=company).get_by_role("button", name="Bring back").click()
    expect(page.get_by_role("link").filter(has_text=company)).to_be_visible()  # its card, back on the board
    assert role_id not in deleted()
    assert app.role(role_id)["company"] == company
