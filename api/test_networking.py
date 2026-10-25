import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main
import networking
from writekit.testing import LOCAL

SEED = Path(__file__).parent.parent / "tools/networking/seed.py"
spec = importlib.util.spec_from_file_location("seed", SEED)
seed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed)

# Made-up people. Bo has no tags and no interactions; Ann's two talks are entered out of order.
# Acme has a website; Beta (Cy's company) does not.
COMPANIES = {"Acme": "https://acme.example"}
PEOPLE = [
    {
        "id": "ann-lee",
        "name": "Ann Lee",
        "company": "Acme",
        "role": "Engineer",
        "met_how": "meetup",
        "met_on": "2026-01-10",
        "about": "Knows infra.",
        "phone": "555 010 0000",
        "tags": ["mentor", "ai-infra"],
        "interactions": [
            {
                "date": "2026-05-01",
                "kind": "call",
                "title": "Second",
                "summary": "s2",
                "transcript": "hi",
                "notes": "raw",
            },
            {"date": "2026-01-10", "kind": "event", "title": "First", "next_step": "follow-up"},
        ],
    },
    {"id": "bo-diaz", "name": "bo Diaz", "company": None},
    {
        "id": "cy-wu",
        "name": "Cy Wu",
        "company": "Beta",
        "tags": ["recruiter"],
        "interactions": [{"date": "2026-03-03", "kind": "email", "next_step": "send-resume"}],
    },
]


@pytest.fixture
def client(tmp_path, monkeypatch):
    path = tmp_path / "networking.db"
    db = sqlite3.connect(path)
    with db:
        seed.seed(db, {"companies": COMPANIES, "people": PEOPLE})
    db.close()
    monkeypatch.setattr(networking, "NETWORKING_DB", path)
    return TestClient(main.app, base_url=LOCAL)


def people(client):
    return client.get("/api/networking/people").json()["people"]


def person(client, person_id):
    return client.get(f"/api/networking/people/{person_id}").json()


def test_people_sorted_by_name_ignoring_case(client):
    assert [p["id"] for p in people(client)] == ["ann-lee", "bo-diaz", "cy-wu"]


def test_people_carry_tags_and_interaction_dates_oldest_first(client):
    ann = people(client)[0]
    assert ann["tags"] == ["ai-infra", "mentor"]
    assert ann["interactions"] == [{"date": "2026-01-10", "kind": "event"}, {"date": "2026-05-01", "kind": "call"}]
    assert ann["company"] == "Acme"


def test_people_list_leaves_out_summaries_and_private_fields(client):
    ann = people(client)[0]
    assert "about" not in ann and "met_how" not in ann and "phone" not in ann
    assert set(ann["interactions"][0]) == {"date", "kind"}


def test_open_next_step_is_the_one_on_the_latest_interaction(client):
    by_id = {p["id"]: p for p in people(client)}
    assert by_id["ann-lee"]["next_step"] is None  # the follow-up was on the older talk, so it is closed
    assert by_id["cy-wu"]["next_step"] == "send-resume"
    assert by_id["bo-diaz"]["next_step"] is None


def test_seed_rejects_a_next_step_not_on_the_list(tmp_path):
    db = sqlite3.connect(tmp_path / "x.db")
    with pytest.raises(sqlite3.IntegrityError):
        seed.seed(
            db,
            {
                "people": [
                    {
                        "id": "a",
                        "name": "A",
                        "interactions": [{"date": "2026-01-01", "kind": "call", "next_step": "send-thanks"}],
                    }
                ]
            },
        )


def test_seed_rejects_free_text_after_a_next_step(tmp_path):
    db = sqlite3.connect(tmp_path / "x.db")
    with pytest.raises(ValueError, match="next_note"):
        seed.seed(
            db,
            {
                "people": [
                    {
                        "id": "a",
                        "name": "A",
                        "interactions": [
                            {"date": "2026-01-01", "kind": "call", "next_step": "follow-up", "next_note": "call back"}
                        ],
                    }
                ]
            },
        )


def test_person_without_tags_or_interactions_gets_empty_lists(client):
    bo = people(client)[1]
    assert bo["tags"] == [] and bo["interactions"] == []
    detail = client.get("/api/networking/people/bo-diaz").json()
    assert detail["tags"] == [] and detail["interactions"] == []


def test_person_detail_has_everything_newest_first(client):
    ann = client.get("/api/networking/people/ann-lee").json()
    assert ann["about"] == "Knows infra."
    assert ann["met_on"] == "2026-01-10"
    assert ann["phone"] == "555 010 0000"
    assert ann["tags"] == ["ai-infra", "mentor"]
    assert [i["title"] for i in ann["interactions"]] == ["Second", "First"]
    assert ann["interactions"][0]["transcript"] == "hi"
    assert ann["interactions"][1]["next_step"] == "follow-up"
    assert ann["interactions"][1]["transcript"] is None
    assert [i["notes"] for i in ann["interactions"]] == ["raw", None]


def test_person_detail_links_the_company_website_when_known(client):
    assert person(client, "ann-lee")["company_website"] == "https://acme.example"
    assert person(client, "cy-wu")["company_website"] is None
    assert person(client, "bo-diaz")["company_website"] is None


def test_seed_rejects_a_website_that_is_not_https(tmp_path):
    db = sqlite3.connect(tmp_path / "x.db")
    with pytest.raises(sqlite3.IntegrityError):
        seed.seed(db, {"companies": {"Acme": "acme.com"}, "people": []})


def test_unknown_person_is_404(client):
    assert client.get("/api/networking/people/nobody").status_code == 404


def test_bad_person_id_is_rejected(client):
    assert client.get("/api/networking/people/Ann_Lee").status_code == 422


def test_missing_db_is_404(tmp_path, monkeypatch):
    monkeypatch.setattr(networking, "NETWORKING_DB", tmp_path / "nope.db")
    res = TestClient(main.app, base_url=LOCAL).get("/api/networking/people")
    assert res.status_code == 404
    assert "./setup.sh" in res.json()["detail"]


def test_writes_are_refused(client):
    assert client.post("/api/networking/people", json={}).status_code == 405
    assert client.delete("/api/networking/people/ann-lee").status_code == 405


def test_seed_rejects_unknown_fields(tmp_path):
    db = sqlite3.connect(tmp_path / "x.db")
    with pytest.raises(ValueError, match="nickname"):
        seed.seed(db, {"people": [{"id": "a", "name": "A", "nickname": "x"}]})


def test_seed_rejects_unknown_kind(tmp_path):
    db = sqlite3.connect(tmp_path / "x.db")
    with pytest.raises(sqlite3.IntegrityError):
        seed.seed(db, {"people": [{"id": "a", "name": "A", "interactions": [{"date": "2026-01-01", "kind": "fax"}]}]})


def test_seed_rejects_a_person_without_an_id_and_says_where(tmp_path):
    db = sqlite3.connect(tmp_path / "x.db")
    with pytest.raises(sqlite3.IntegrityError, match="people.id") as e:
        seed.seed(db, {"people": [{"name": "No Id"}]})
    assert e.value.__notes__ == ["in person None"]


def test_seed_names_the_person_a_bad_interaction_is_in(tmp_path):
    db = sqlite3.connect(tmp_path / "x.db")
    with pytest.raises(ValueError, match="mood") as e:
        seed.seed(
            db,
            {
                "people": [
                    {"id": "a", "name": "A", "interactions": [{"date": "2026-01-01", "kind": "call", "mood": "x"}]}
                ]
            },
        )
    assert e.value.__notes__ == ["in person 'a'"]


def test_example_seed_file_loads(tmp_path):
    example = json.loads((SEED.parent / "example.json").read_text())
    db = sqlite3.connect(tmp_path / "x.db")
    seed.seed(db, example)
    assert db.execute("SELECT COUNT(*) FROM people").fetchone()[0] == len(example["people"])
    assert db.execute("SELECT COUNT(*) FROM companies").fetchone()[0] == len(example["companies"])


# ── Versions and deleted rows ────────────────────────────────────────────────


def hide(table: str, where: str):
    db = sqlite3.connect(networking.NETWORKING_DB)
    with db:
        db.execute(f"UPDATE {table} SET deleted_on = '2026-10-08' WHERE {where}")
    db.close()


def test_a_person_and_their_talks_carry_their_versions_for_the_edit_forms(client):
    ann = person(client, "ann-lee")
    assert ann["version"] == 1 and [i["version"] for i in ann["interactions"]] == [1, 1]
    assert "deleted_on" not in ann and "deleted_on" not in ann["interactions"][0]


def test_someone_deleted_is_left_out_and_their_page_is_404(client):
    hide("people", "id = 'cy-wu'")
    assert [p["id"] for p in people(client)] == ["ann-lee", "bo-diaz"]
    assert client.get("/api/networking/people/cy-wu").status_code == 404


def test_a_deleted_talk_is_left_out_and_the_next_step_comes_from_the_latest_left(client):
    hide("interactions", "title = 'Second'")
    ann = people(client)[0]
    assert ann["interactions"] == [{"date": "2026-01-10", "kind": "event"}]
    assert ann["next_step"] == "follow-up"
    assert [i["title"] for i in person(client, "ann-lee")["interactions"]] == ["First"]
