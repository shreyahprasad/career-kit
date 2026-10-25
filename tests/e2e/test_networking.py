"""The Networking page: logging talks with someone new and someone known, fixing one, deleting a
person, and a role's referral from the phonebook."""

import re

from playwright.sync_api import expect

from conftest import unique


def find_person(app, name: str) -> dict | None:
    return next((p for p in app.read("/api/networking/people")["people"] if p["name"] == name), None)


def test_someone_new_is_added_with_their_first_talk_then_a_second_is_logged_from_their_card(page, app):
    name = unique("Syrio Forel")
    page.goto("/#/networking")
    page.get_by_role("button", name="+ Log a talk").first.click()
    log = page.get_by_role("region", name="Log a talk")
    log.get_by_role("combobox", name="Who was it with").fill(name)
    log.get_by_role("option", name=f"+ Add “{name}” as someone new").click()
    log.get_by_label("Title").fill("Intro chat")
    log.get_by_label("Notes").fill("Talked about water dancing and data pipelines.")
    log.get_by_role("button", name="Save").click()

    expect(page.get_by_role("status").filter(has_text=f"Added {name} to your phonebook")).to_be_visible()
    card = page.get_by_role("region", name="Person")
    expect(card.get_by_role("heading", name=name)).to_be_visible()
    person = find_person(app, name)
    talks = app.read(f"/api/networking/people/{person['id']}")["interactions"]
    assert [(t["kind"], t["title"], t["notes"]) for t in talks] == [
        ("call", "Intro chat", "Talked about water dancing and data pipelines.")
    ]

    card.get_by_role("button", name="+ Log a talk").click()
    log.get_by_label("Kind").select_option("coffee")
    log.get_by_label("Title").fill("Coffee near the docks")
    log.get_by_role("button", name="Save").click()
    expect(card.get_by_text("Talks · 2")).to_be_visible()
    talks = app.read(f"/api/networking/people/{person['id']}")["interactions"]
    assert [(t["kind"], t["title"]) for t in talks] == [("coffee", "Coffee near the docks"), ("call", "Intro chat")]
    assert [p["name"] for p in app.read("/api/networking/people")["people"]].count(name) == 1  # the same person


def test_a_talk_is_fixed_on_the_persons_card(page, app):
    name = unique("Jaqen Hghar")
    person_id = app.add_person(name)
    app.write("POST", "/api/networking/write/interactions", {"person_id": person_id, "title": "First call"})
    page.goto(f"/#/networking/{person_id}")
    card = page.get_by_role("region", name="Person")
    card.get_by_role("button", name=re.compile(r"^Edit call on")).click()
    form = card.get_by_role("form", name="Fix this talk")
    form.get_by_label("Title").fill("First call, about the Braavos role")
    form.get_by_role("button", name="Save").click()
    expect(card.get_by_text("First call, about the Braavos role")).to_be_visible()
    [talk] = app.read(f"/api/networking/people/{person_id}")["interactions"]
    assert talk["title"] == "First call, about the Braavos role"


def test_a_deleted_person_comes_back_with_undo(page, app):
    name = unique("Jaqen Hghar")
    person_id = app.add_person(name)
    page.goto(f"/#/networking/{person_id}")
    card = page.get_by_role("region", name="Person")
    card.get_by_role("button", name="Edit", exact=True).click()
    card.get_by_role("button", name="Delete person").click()
    undo = page.get_by_role("status").filter(has_text=f"Deleted {name}.")
    expect(undo).to_be_visible()
    assert find_person(app, name) is None
    undo.get_by_role("button", name="Undo").click()
    expect(card.get_by_role("heading", name=name)).to_be_visible()
    assert find_person(app, name)["id"] == person_id


def test_a_referral_links_a_role_to_someone_in_the_phonebook(page, app):
    name = unique("Syrio Forel")
    person_id = app.add_person(name)
    role_id = app.add_role(unique("Braavos Bank"), "Data Analyst")
    page.goto(f"/#/career/{role_id}")
    referral = page.get_by_role("region", name="Referred by")
    referral.get_by_role("button", name="+ Add referrer").click()
    referral.get_by_role("combobox", name="Referred by").fill(name)
    referral.get_by_role("option", name=name).click()
    link = referral.get_by_role("link", name=name)
    expect(link).to_be_visible()
    assert app.role(role_id)["referral"] == {"id": person_id, "name": name}

    link.click()
    expect(page.get_by_role("region", name="Person").get_by_role("heading", name=name)).to_be_visible()
