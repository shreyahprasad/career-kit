"""What a page on another site or another local port can do with the page: nothing. It cannot
read or change anything through the page's server, and cannot show the page inside its own."""

import http.server
import threading
import urllib.request

import pytest
from playwright.sync_api import expect

from conftest import PORTS

SECURITY_HEADERS = ("Content-Security-Policy", "X-Content-Type-Options", "Referrer-Policy", "Permissions-Policy")


@pytest.fixture
def other_origin():
    """A page on another local port, as any other program on this Mac could serve; html is what
    it serves. Yields its address."""
    served = {"html": b""}

    class Page(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(served["html"])

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield served, f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def headers(url: str) -> dict:
    with urllib.request.urlopen(url) as answer:
        return {name: answer.headers.get(name) for name in SECURITY_HEADERS}


def test_the_page_on_this_mac_has_the_same_security_headers_as_on_the_phone(app):
    phone = headers(f"http://127.0.0.1:{PORTS['API_PORT']}/")  # tailscale serve sends the phone here
    assert all(phone.values())
    assert headers(f"{app.web}/") == phone


def test_a_page_on_another_local_port_can_neither_read_nor_change_anything(app, browser, other_origin):
    served, origin = other_origin
    served["html"] = b"<p>another program's page</p>"
    before = len(app.read("/api/career/roles")["roles"])
    page = browser.new_page()
    page.goto(origin)
    tried = page.evaluate(
        """async (web) => {
            const attempt = async (path, init) => {
                try { await (await fetch(web + path, init)).text(); return "got through"; } catch { return "refused"; }
            };
            return {
                read: await attempt("/api/networking/people"),
                change: await attempt("/api/career/write/roles", {
                    method: "POST",
                    headers: { "Content-Type": "application/json", "X-Career-Kit-Write": "1" },
                    body: JSON.stringify({ company: "Not Arya's", title: "Planted" }),
                }),
            };
        }""",
        app.web,
    )
    page.close()
    assert tried == {"read": "refused", "change": "refused"}
    assert len(app.read("/api/career/roles")["roles"]) == before


def test_another_page_cannot_show_the_page_inside_its_own(app, browser, other_origin):
    served, origin = other_origin
    served["html"] = f'<iframe src="{app.web}/#/career" width="800" height="600"></iframe>'.encode()
    page = browser.new_page()
    page.goto(origin)
    page.wait_for_timeout(2000)  # long enough for the board to draw, were it let in
    expect(page.frame_locator("iframe").get_by_role("heading", name="Career")).to_have_count(0)
    page.close()
