"""posting.py: reading a job posting from its link, with the network replaced by made-up pages.
The guards are tested on their own, and through fetch() with the connection faked."""

import json
import socket

import pytest

import posting
from posting import Unreadable

# ── What a posting gives ─────────────────────────────────────────────────────


def pages(by_url: dict[str, str]):
    """A stand-in for posting.fetch: each URL's body, as text."""

    def get(url: str) -> tuple[str, str]:
        if url not in by_url:
            raise AssertionError(f"not expected: {url}")
        body = by_url[url]
        return body, "application/json" if body.lstrip().startswith(("{", "[")) else "text/html"

    return get


def test_a_greenhouse_link_reads_its_job_feed():
    job = {
        "title": "Forward Deployed Engineer",
        "company_name": "Acme",
        "location": {"name": "New York, NY"},
        "content": "&lt;h2&gt;About&lt;/h2&gt;&lt;p&gt;We build things.&lt;/p&gt;"
        "&lt;ul&gt;&lt;li&gt;Python&lt;/li&gt;&lt;/ul&gt;",
    }
    get = pages({"https://boards-api.greenhouse.io/v1/boards/acme/jobs/123": json.dumps(job)})
    draft = posting.read("https://job-boards.greenhouse.io/acme/jobs/123?gh_src=x", get)
    assert draft == {
        "company": "Acme",
        "title": "Forward Deployed Engineer",
        "location": "New York, NY",
        "comp": None,
        "posting": "About\n\nWe build things.\n\n- Python",
        "from": "feed",
    }


def test_plain_text_from_a_site_is_tidied():
    job = {"title": "FDE", "company_name": "Acme", "location": {"name": "Remote"}, "content": "&lt;p&gt;One&lt;/p&gt;"}
    job["content"] += "&lt;p&gt;\u00a0&lt;/p&gt;&lt;p&gt;Two\u00a0words&lt;/p&gt;"
    get = pages({"https://boards-api.greenhouse.io/v1/boards/acme/jobs/1": json.dumps(job)})
    assert posting.read("https://boards.greenhouse.io/acme/jobs/1", get)["posting"] == "One\n\nTwo words"


JOB_PAGE = """<html><head><title>Careers | Beta</title>
<script type="application/ld+json">{"@context": "https://schema.org", "@graph": [{"@type": "WebPage"}, {
  "@type": "JobPosting", "title": "Data Scientist",
  "hiringOrganization": {"@type": "Organization", "name": "Beta Corp"},
  "jobLocation": [{"address": {"addressLocality": "Austin", "addressRegion": "TX", "addressCountry": "US"}}],
  "baseSalary": {"currency": "USD", "value": {"minValue": 150000, "maxValue": 200000, "unitText": "YEAR"}},
  "description": "<p>Model things.</p><p>With &amp; care.</p>"}]}</script>
<script>var tracking = "never text";</script></head>
<body><nav>Menu</nav><p>Ignored when JSON-LD has it.</p></body></html>"""


def test_any_other_page_is_read_from_its_job_posting_data():
    draft = posting.read(
        "https://careers.beta.example/jobs/9", pages({"https://careers.beta.example/jobs/9": JOB_PAGE})
    )
    assert draft == {
        "company": "Beta Corp",
        "title": "Data Scientist",
        "location": "Austin, TX",
        "comp": "$150,000-$200,000 a year",
        "posting": "Model things.\n\nWith & care.",
        "from": "page data",
    }


def test_a_remote_job_says_remote():
    data = {
        "@type": "JobPosting",
        "title": "FDE",
        "jobLocationType": "TELECOMMUTE",
        "hiringOrganization": "Gamma",
        "description": "Work.",
    }
    page = f'<script type="application/ld+json">{json.dumps([data])}</script>'
    draft = posting.read("https://gamma.example/j", pages({"https://gamma.example/j": page}))
    assert (draft["company"], draft["location"]) == ("Gamma", "Remote")


@pytest.mark.parametrize(
    "text, comp",
    [
        ("We raised $50M. The base pay is $166,000 – $185,000 per year.\n\nApply.", "$166,000 – $185,000 per year"),
        ("Range: $120K-$150K USD", "$120K-$150K USD"),
        ("Pay is $55 to $70 an hour.", "$55 to $70 an hour"),
        ("We raised $50M and $20M before.", None),  # money, but not a pay range
        ("No pay given.", None),
    ],
)
def test_with_no_pay_in_the_job_data_the_first_pay_range_in_the_posting_is_taken_as_written(text, comp):
    data = {"@type": "JobPosting", "title": "FDE", "hiringOrganization": "Gamma", "description": text}
    page = f'<script type="application/ld+json">{json.dumps(data)}</script>'
    assert posting.read("https://gamma.example/j", pages({"https://gamma.example/j": page}))["comp"] == comp


SF = {"address": {"addressLocality": "San Francisco", "addressRegion": "California"}}


@pytest.mark.parametrize(
    "workplace, location",
    [
        ('"workplaceType":"Hybrid"', "San Francisco, California (hybrid)"),
        ('"workplaceType":"Remote"', "San Francisco, California (remote)"),
        ('"workplaceType":"OnSite"', "San Francisco, California (on site)"),
        ("", "San Francisco, California (remote or hybrid)"),  # telecommute alone does not say which
    ],
)
def test_a_telecommute_job_with_a_city_keeps_the_city_and_says_how_much_is_remote(workplace, location):
    """Ashby marks hybrid jobs as telecommute for search engines; its own page data says Hybrid."""
    data = {
        "@type": "JobPosting",
        "title": "FDE",
        "hiringOrganization": "Notion",
        "jobLocationType": "TELECOMMUTE",
        "jobLocation": SF,
        "description": "Work.",
    }
    page = (
        f'<script type="application/ld+json">{json.dumps(data)}</script>'
        f"<script>window.__appData = {{{workplace}}}</script>"
    )
    assert (
        posting.read("https://jobs.ashbyhq.com/notion/1", pages({"https://jobs.ashbyhq.com/notion/1": page}))[
            "location"
        ]
        == location
    )


def test_a_job_with_a_city_and_a_workplace_type_says_both():
    data = {
        "@type": "JobPosting",
        "title": "FDE",
        "hiringOrganization": "Acme",
        "jobLocation": SF,
        "description": "Work.",
    }
    page = (
        f'<script type="application/ld+json">{json.dumps(data)}</script>'
        '<script>x = {"workplaceType":"Hybrid"}</script>'
    )
    assert (
        posting.read("https://acme.example/1", pages({"https://acme.example/1": page}))["location"]
        == "San Francisco, California (hybrid)"
    )


def test_a_page_with_no_job_data_gives_its_title_and_text_and_no_company():
    page = """<html><head><meta property="og:title" content="Senior FDE"><title>x</title>
    <style>p { color: red }</style></head><body><h1>Senior FDE</h1><p>Line one.<br>Line two.</p>
    <script>alert(1)</script><noscript>Turn on JS</noscript></body></html>"""
    draft = posting.read("https://delta.example/j", pages({"https://delta.example/j": page}))
    assert (draft["company"], draft["title"], draft["from"]) == (None, "Senior FDE", "page")
    assert draft["posting"] == "Senior FDE\n\nLine one.\nLine two."


def test_a_page_with_nothing_to_read_says_so():
    with pytest.raises(Unreadable, match="no posting"):
        posting.read(
            "https://empty.example/",
            pages({"https://empty.example/": "<html><body><script>app()</script></body></html>"}),
        )


def test_long_details_are_cut_to_what_a_line_can_hold():
    data = {"@type": "JobPosting", "title": "T" * 900, "hiringOrganization": "C" * 900, "description": "Work."}
    page = f'<script type="application/ld+json">{json.dumps(data)}</script>'
    draft = posting.read("https://long.example/", pages({"https://long.example/": page}))
    assert (len(draft["title"]), len(draft["company"])) == (posting.MAX_LINE, posting.MAX_LINE)


def test_a_long_posting_is_cut_to_what_can_be_saved():
    page = "<p>" + "word " * 30_000 + "</p>"
    draft = posting.read("https://long.example/", pages({"https://long.example/": page}))
    assert len(draft["posting"]) == posting.MAX_TEXT


# ── The guards ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "link, why",
    [
        ("http://jobs.example/1", "https"),
        ("ftp://jobs.example/1", "https"),
        ("https://jobs.example:8443/1", "port"),
        ("https://jobs.example:abc/1", "port"),
        ("https://me:pw@jobs.example/1", "password"),
        ("https:///nohost", "https"),
    ],
)
def test_only_plain_https_links_are_read(link, why):
    with pytest.raises(Unreadable, match=why):
        posting.check_link(link)


def resolving_to(monkeypatch, *ips: str):
    def getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in ips]

    monkeypatch.setattr(posting.socket, "getaddrinfo", getaddrinfo)


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",  # this Mac
        "10.0.0.5",  # a LAN
        "192.168.1.20",
        "169.254.169.254",  # link-local
        "100.101.102.103",  # the tailnet
        "fd7a:115c:a1e0::1",  # the tailnet, IPv6
        "::1",
        "::ffff:127.0.0.1",
        "0.0.0.0",
        "64:ff9b::a00:1",  # NAT64: a gateway reaches the LAN address inside, 10.0.0.1
        "64:ff9b::7f00:1",
        "::127.0.0.1",  # IPv4-compatible, an old form
        "::ffff:0:a00:1",  # SIIT, another
    ],
)
def test_a_name_that_leads_inside_your_network_is_refused(monkeypatch, ip):
    resolving_to(monkeypatch, "93.184.216.34", ip)  # one bad address is enough
    with pytest.raises(Unreadable, match="inside your network"):
        posting.public_address("jobs.example")


def test_a_name_that_does_not_resolve_is_unreadable(monkeypatch):
    def getaddrinfo(*_args, **_kwargs):
        raise socket.gaierror("nodename nor servname provided")

    monkeypatch.setattr(posting.socket, "getaddrinfo", getaddrinfo)
    with pytest.raises(Unreadable, match="Could not find jobs.example"):
        posting.public_address("jobs.example")


def test_a_nat64_address_of_a_public_one_is_public(monkeypatch):
    resolving_to(monkeypatch, "64:ff9b::5db8:d822")  # 93.184.216.34 inside
    assert posting.public_address("jobs.example") == "64:ff9b::5db8:d822"


def test_a_public_name_gives_the_address_to_connect_to(monkeypatch):
    resolving_to(monkeypatch, "93.184.216.34")
    assert posting.public_address("jobs.example") == "93.184.216.34"


class FakeAnswer:
    """A response read in chunks; each read moves the clock on by seconds_per_read."""

    clock = [0.0]

    def __init__(self, status: int, headers: dict, body: bytes = b"", seconds_per_read: float = 0):
        self.status, self.headers, self.body, self.seconds_per_read = status, headers, body, seconds_per_read
        self.closed = False

    def getheader(self, name, default=None):
        return self.headers.get(name, default)

    def read(self, n: int) -> bytes:
        FakeAnswer.clock[0] += self.seconds_per_read
        chunk, self.body = self.body[:n], self.body[n:]
        return chunk

    def close(self):
        self.closed = True


@pytest.fixture
def web(monkeypatch):
    """Every name is public; answers come from the dict, by URL; asked lists the URLs asked."""
    resolving_to(monkeypatch, "93.184.216.34")
    answers: dict[str, FakeAnswer] = {}
    asked: list[tuple[str, str]] = []

    def ask(host, address, target):
        asked.append((f"https://{host}{target}", address))
        return answers[f"https://{host}{target}"]

    monkeypatch.setattr(posting, "_ask", ask)
    FakeAnswer.clock[0] = 0.0
    monkeypatch.setattr(posting.time, "monotonic", lambda: FakeAnswer.clock[0])
    return answers, asked


def test_fetch_connects_to_the_address_it_checked_and_returns_the_text(web):
    answers, asked = web
    answers["https://jobs.example/1?a=b"] = FakeAnswer(
        200, {"Content-Type": "text/html; charset=utf-8"}, "Café".encode()
    )
    assert posting.fetch("https://jobs.example/1?a=b") == ("Café", "text/html")
    assert asked == [("https://jobs.example/1?a=b", "93.184.216.34")]


def test_fetch_follows_a_redirect_checking_it_again(web, monkeypatch):
    answers, asked = web
    answers["https://jobs.example/1"] = FakeAnswer(302, {"Location": "https://other.example/2"})
    answers["https://other.example/2"] = FakeAnswer(200, {"Content-Type": "text/html"}, b"ok")
    assert posting.fetch("https://jobs.example/1")[0] == "ok"
    answers["https://jobs.example/3"] = FakeAnswer(301, {"Location": "http://other.example/2"})
    with pytest.raises(Unreadable, match="https"):
        posting.fetch("https://jobs.example/3")


def test_every_answer_is_closed_redirect_or_not(web):
    answers, _ = web
    hop = answers["https://jobs.example/1"] = FakeAnswer(302, {"Location": "/2"})
    page = answers["https://jobs.example/2"] = FakeAnswer(200, {"Content-Type": "text/html"}, b"ok")
    refused = answers["https://jobs.example/3"] = FakeAnswer(404, {})
    posting.fetch("https://jobs.example/1")
    with pytest.raises(Unreadable):
        posting.fetch("https://jobs.example/3")
    assert (hop.closed, page.closed, refused.closed) == (True, True, True)


def test_an_unknown_charset_is_read_as_utf8(web):
    answers, _ = web
    answers["https://jobs.example/1"] = FakeAnswer(
        200, {"Content-Type": "text/html; charset=x-made-up"}, "Café".encode()
    )
    assert posting.fetch("https://jobs.example/1") == ("Café", "text/html")


def test_a_page_that_trickles_in_is_given_up_on(web):
    """Each read is quick enough on its own, but the whole page takes too long."""
    answers, _ = web
    body = b"x" * (posting.CHUNK * 10)
    answers["https://jobs.example/slow"] = FakeAnswer(
        200, {"Content-Type": "text/html"}, body, seconds_per_read=posting.TIMEOUT - 1
    )
    with pytest.raises(Unreadable, match="too long"):
        posting.fetch("https://jobs.example/slow")


def test_fetch_stops_after_too_many_redirects(web):
    answers, _ = web
    answers["https://jobs.example/loop"] = FakeAnswer(302, {"Location": "/loop"})
    with pytest.raises(Unreadable, match="redirect"):
        posting.fetch("https://jobs.example/loop")


def test_fetch_refuses_a_page_too_large(web):
    answers, _ = web
    answers["https://jobs.example/big"] = FakeAnswer(200, {"Content-Type": "text/html"}, b"x" * (posting.MAX_BYTES + 1))
    with pytest.raises(Unreadable, match="too large"):
        posting.fetch("https://jobs.example/big")


@pytest.mark.parametrize(
    "answer, why",
    [
        (FakeAnswer(403, {}), "answered 403"),
        (FakeAnswer(200, {"Content-Type": "application/pdf"}, b"%PDF"), "not a web page"),
    ],
)
def test_fetch_says_why_a_page_is_unreadable(web, answer, why):
    answers, _ = web
    answers["https://jobs.example/x"] = answer
    with pytest.raises(Unreadable, match=why):
        posting.fetch("https://jobs.example/x")


def test_a_site_that_cannot_be_reached_is_unreadable(monkeypatch):
    resolving_to(monkeypatch, "93.184.216.34")

    def ask(*_):
        raise TimeoutError("timed out")

    monkeypatch.setattr(posting, "_ask", ask)
    with pytest.raises(Unreadable, match="Could not reach jobs.example"):
        posting.fetch("https://jobs.example/1")


def test_a_site_that_drops_the_page_partway_is_unreadable(web):
    class Dropped(FakeAnswer):
        def read(self, n):
            raise ConnectionResetError("connection reset")

    answers, _ = web
    answer = answers["https://jobs.example/1"] = Dropped(200, {"Content-Type": "text/html"})
    with pytest.raises(Unreadable, match="Could not reach jobs.example"):
        posting.fetch("https://jobs.example/1")
    assert answer.closed


# The real connection, with only the socket faked: it dials the address that was checked, never
# the name again, and checks the certificate against the name.


def test_the_connection_dials_the_checked_address_not_the_name(monkeypatch):
    resolving_to(monkeypatch, "93.184.216.34")
    dialled = []

    def create_connection(address, timeout=None, *args, **kwargs):
        dialled.append((address, timeout))
        raise ConnectionRefusedError("refused")

    monkeypatch.setattr(posting.socket, "create_connection", create_connection)
    with pytest.raises(Unreadable, match="Could not reach jobs.example"):
        posting.fetch("https://jobs.example/1")
    assert dialled == [(("93.184.216.34", 443), posting.TIMEOUT)]


def test_the_connection_checks_the_certificate_for_the_name(monkeypatch):
    sock = object()
    monkeypatch.setattr(posting.socket, "create_connection", lambda *args, **kwargs: sock)
    conn = posting._PinnedHTTPS("jobs.example", "93.184.216.34")
    assert (conn._context.verify_mode, conn._context.check_hostname) == (posting.ssl.CERT_REQUIRED, True)
    wrapped = []

    class Context:
        def wrap_socket(self, s, server_hostname):
            wrapped.append((s, server_hostname))
            return s

    conn._context = Context()
    conn.connect()
    assert wrapped == [(sock, "jobs.example")]


# ── Hostile or odd pages ─────────────────────────────────────────────────────


def test_a_broken_job_data_block_is_skipped_for_the_next_one():
    good = {"@type": "JobPosting", "title": "FDE", "hiringOrganization": "Gamma", "description": "Work."}
    page = (
        f'<script type="application/ld+json">{{"@type": "JobPosting", "title": </script>'
        f'<script type="application/ld+json">{json.dumps(good)}</script>'
    )
    draft = posting.read("https://gamma.example/j", pages({"https://gamma.example/j": page}))
    assert (draft["title"], draft["from"]) == ("FDE", "page data")


def test_pay_that_is_not_a_number_is_left_out():
    data = {
        "@type": "JobPosting",
        "title": "FDE",
        "hiringOrganization": "Gamma",
        "description": "Work.",
        "baseSalary": {"currency": "USD", "value": {"minValue": "lots", "maxValue": "more", "unitText": "YEAR"}},
    }
    page = f'<script type="application/ld+json">{json.dumps(data)}</script>'
    assert posting.read("https://gamma.example/j", pages({"https://gamma.example/j": page}))["comp"] is None


def test_job_data_with_no_description_takes_the_pages_text():
    data = {"@type": "JobPosting", "title": "FDE", "hiringOrganization": "Gamma"}
    page = f'<script type="application/ld+json">{json.dumps(data)}</script><p>The posting is here.</p>'
    draft = posting.read("https://gamma.example/j", pages({"https://gamma.example/j": page}))
    assert (draft["title"], draft["posting"]) == ("FDE", "The posting is here.")


def test_a_job_feed_that_does_not_send_json_is_unreadable():
    get = pages({"https://boards-api.greenhouse.io/v1/boards/acme/jobs/1": "<html>Down for maintenance</html>"})
    with pytest.raises(Unreadable, match="boards.greenhouse.io sent something unexpected"):
        posting.read("https://boards.greenhouse.io/acme/jobs/1", get)


def test_job_data_nested_too_deep_to_read_falls_back_to_the_page():
    page = f'<script type="application/ld+json">{"[" * 5000 + "]" * 5000}</script><title>FDE</title><p>The posting.</p>'
    draft = posting.read("https://deep.example/j", pages({"https://deep.example/j": page}))
    assert (draft["title"], draft["posting"], draft["from"]) == ("FDE", "The posting.", "page")
