import pytest
from fastapi.testclient import TestClient

import main
from writekit.testing import LOCAL


@pytest.fixture
def client():
    return TestClient(main.app, base_url=LOCAL)


# ── The built site ───────────────────────────────────────────────────────────


@pytest.fixture
def site(tmp_path, monkeypatch):
    """The app reloaded with a built site in WEB_DIST, then restored for other tests."""
    import importlib

    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>site</title>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    monkeypatch.setenv("WEB_DIST", str(dist))
    yield TestClient(importlib.reload(main).app, base_url=LOCAL)
    monkeypatch.delenv("WEB_DIST")
    importlib.reload(main)


def test_serves_the_built_site(site):
    assert "<title>site</title>" in site.get("/").text
    assert site.get("/assets/app.js").text == "console.log(1)"


def test_api_routes_win_over_the_site(site):
    assert site.get("/api/health").json() == {"ok": True, "app": "career-kit"}


def test_runs_without_a_built_site(client):
    # No WEB_DIST build in tests by default: the API still answers.
    assert client.get("/api/health").json() == {"ok": True, "app": "career-kit"}


def test_the_dashboard_is_only_for_its_owner_over_the_tailnet(client):
    """The same check the writers make (writekit.identity): from this Mac, no login is needed.
    Anyone else on the tailnet is refused, whether or not .env names the owner yet."""
    assert client.get("/api/health").status_code == 200
    r = client.get("/api/health", headers={"X-Forwarded-For": "100.64.0.3", "Tailscale-User-Login": "them@example.com"})
    assert r.status_code == 403


def test_the_dashboard_answers_only_to_its_own_names(client):
    """A page that points its own name at this Mac (DNS rebinding) is refused, even from here."""
    assert client.get("/api/health", headers={"Host": "evil.example:8100"}).status_code == 403
    assert client.get("/api/health", headers={"Host": "localhost:8100"}).status_code == 200


def test_every_answer_carries_the_page_security_headers(client):
    """Only the dashboard's own files run or load; it cannot be framed; nothing is sniffed; links
    out send no referrer."""
    headers = client.get("/api/health").headers
    csp = main.SECURITY_HEADERS["Content-Security-Policy"]
    assert headers["Content-Security-Policy"] == csp
    assert (
        "frame-ancestors 'none'" in csp
        and "script-src 'self'" in csp
        and "unsafe-eval'" not in csp.replace("wasm-unsafe-eval'", "")
    )
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Referrer-Policy"] == "no-referrer"
