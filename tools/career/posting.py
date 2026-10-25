"""
Reading a job posting from its link (writer.py POST /postings/read). Nothing here is saved: it
returns a draft that fills the add-role form, and you check it before anything is.

Where the facts come from, best first:
- A page's JobPosting data (schema.org JSON-LD, which job sites publish for search engines).
  Lever and Ashby pages have it, with the company's full name and, on Ashby, the pay.
- Greenhouse pages do not, so a Greenhouse link reads the site's public job feed instead.
- Else the page's title and its text, with no company.
With no pay in the job data, the first pay range written in the posting is taken, word for word.
A page is only parsed, never run, and no AI reads it. Sites that build the page in the browser
(Workday, LinkedIn often do) give nothing to read; you paste the text instead.

fetch() is guarded: https on port 443 only; every address the name resolves to must be public
(not this Mac, your LAN or the tailnet), and the connection goes to the address checked, so the
name cannot change underneath it; every redirect is checked again, MAX_REDIRECTS at most; TIMEOUT
seconds per step and DEADLINE for the whole fetch, so a page sent a trickle at a time is given up
on; at most MAX_BYTES read; every answer is closed.
"""

import codecs
import html
import http.client
import ipaddress
import json
import re
import socket
import ssl
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from writekit.errors import Refused
from writekit.forms import MAX_LINE, MAX_LONG

MAX_REDIRECTS = 5
TIMEOUT = 10  # seconds, for connecting and for each read
DEADLINE = 20  # seconds for the whole fetch, redirects included (a last read can take TIMEOUT more)
CHUNK = 64 * 1024
MAX_BYTES = 3_000_000  # above the largest job page seen (Workday's are about 1 MB)
MAX_TEXT = MAX_LONG  # the most of a posting a role can keep

PAGE_TYPES = ("text/html", "application/xhtml+xml", "application/json", "application/ld+json", "text/plain")
USER_AGENT = "career-kit/1 (reads one job posting, once, when you add the role)"
PASTE = "Paste the posting text instead."


class Unreadable(Refused):
    """Why the posting could not be read, ending with what to do instead."""


# ── The guarded fetch ────────────────────────────────────────────────────────


def check_link(link: str) -> tuple[str, str]:
    """The host and the path-and-query of a plain https link; anything else is Unreadable."""
    parts = urlsplit(link)
    if parts.scheme != "https" or not parts.hostname:
        raise Unreadable(f"Only https links are read. {PASTE}")
    if parts.username or parts.password:
        raise Unreadable(f"A link with a password in it is not read. {PASTE}")
    try:
        port = parts.port
    except ValueError:
        port = -1
    if port not in (None, 443):
        raise Unreadable(f"Only links on the usual https port are read. {PASTE}")
    return parts.hostname, (parts.path or "/") + (f"?{parts.query}" if parts.query else "")


def public_address(host: str) -> str:
    """An address host resolves to, once every address it resolves to is public."""
    try:
        found = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError:
        raise Unreadable(f"Could not find {host}. {PASTE}") from None
    addresses = [info[4][0] for info in found]
    for address in addresses:
        if not _inside(ipaddress.ip_address(address.split("%")[0])).is_global:
            raise Unreadable("That link leads inside your network, so it is not read.")
    return addresses[0]


# IPv6 forms that carry an IPv4 address in their last 32 bits: NAT64, where a gateway goes on to
# the address inside (on some phone hotspots and IPv6-only Wi-Fi), and two old forms.
CARRIES_IPV4 = [ipaddress.ip_network(n) for n in ("64:ff9b::/96", "::/96", "::ffff:0:0:0/96")]


def _inside(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    """The address a connection to ip ends up at: the IPv4 one inside it, if it carries one."""
    if ip.version == 6 and ip.ipv4_mapped:
        return ip.ipv4_mapped
    if ip.version == 6 and any(ip in net for net in CARRIES_IPV4):
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    return ip


class _PinnedHTTPS(http.client.HTTPSConnection):
    """An https connection to an address already checked, still verifying the certificate for host."""

    def __init__(self, host: str, address: str):
        super().__init__(host, 443, timeout=TIMEOUT, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        sock = socket.create_connection((self.address, 443), timeout=TIMEOUT)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def _ask(host: str, address: str, target: str) -> http.client.HTTPResponse:
    """GET target from host at address. The response closes its connection when read."""
    conn = _PinnedHTTPS(host, address)
    conn.request(
        "GET", target, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json;q=0.9,*/*;q=0.1"}
    )
    return conn.getresponse()


def fetch(link: str) -> tuple[str, str]:
    """The text of the page at link and its content type, through the guards above."""
    deadline = time.monotonic() + DEADLINE
    for _ in range(MAX_REDIRECTS + 1):
        host, target = check_link(link)
        address = public_address(host)
        try:
            answer = _ask(host, address, target)
        except (OSError, http.client.HTTPException) as e:
            raise Unreadable(f"Could not reach {host} ({e}). {PASTE}") from None
        try:
            if answer.status in (301, 302, 303, 307, 308) and answer.getheader("Location"):
                link = urljoin(link, answer.getheader("Location"))
                continue
            if answer.status != 200:
                raise Unreadable(f"{host} answered {answer.status}. {PASTE}")
            kind, _, params = (answer.getheader("Content-Type") or "").partition(";")
            kind = kind.strip().lower()
            if kind not in PAGE_TYPES:
                raise Unreadable(f"That link is not a web page. {PASTE}")
            body = _read(answer, deadline)
        except (OSError, http.client.HTTPException) as e:
            raise Unreadable(f"Could not reach {host} ({e}). {PASTE}") from None
        finally:
            answer.close()
        return body.decode(_charset(params), errors="replace"), kind
    raise Unreadable(f"That link redirects too many times. {PASTE}")


def _read(answer, deadline: float) -> bytes:
    """The body, a CHUNK at a time: at most MAX_BYTES, and done by deadline."""
    chunks: list[bytes] = []
    size = 0
    while chunk := answer.read(CHUNK):
        size += len(chunk)
        if size > MAX_BYTES:
            raise Unreadable(f"That page is too large to read. {PASTE}")
        if time.monotonic() > deadline:
            raise Unreadable(f"That page took too long to arrive. {PASTE}")
        chunks.append(chunk)
    return b"".join(chunks)


def _charset(params: str) -> str:
    """The charset the Content-Type names, when Python knows it; else UTF-8."""
    named = re.search(r"charset=\"?([\w-]+)", params)
    if named:
        try:
            return codecs.lookup(named[1]).name
        except LookupError:
            pass
    return "utf-8"


# ── Reading a page ───────────────────────────────────────────────────────────

BLOCKS = {
    "p",
    "div",
    "section",
    "article",
    "ul",
    "ol",
    "table",
    "tr",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "blockquote",
    "pre",
}
SKIPPED = {"script", "style", "noscript", "svg", "template", "nav", "footer", "head", "iframe", "button", "form"}


class _Page(HTMLParser):
    """A page's text (paragraphs apart, list items as "- "), its JSON-LD blocks, and its title."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.json_ld: list[str] = []
        self.title: str | None = None
        self.og_title: str | None = None
        self._skipping = 0
        self._in = ""  # "json-ld" or "title" while inside one

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and (attrs.get("type") or "").lower() == "application/ld+json":
            self._in = "json-ld"
            self.json_ld.append("")
        elif tag == "title":
            self._in = "title"
        elif tag == "meta" and attrs.get("property") == "og:title":
            self.og_title = (attrs.get("content") or "").strip() or None
        if tag in SKIPPED:
            self._skipping += 1
        elif tag in BLOCKS:
            self.parts.append("\n\n")
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "title"):
            self._in = ""
        if tag in SKIPPED:
            self._skipping = max(0, self._skipping - 1)
        elif tag in BLOCKS:
            self.parts.append("\n\n")

    def handle_data(self, data):
        if self._in == "json-ld":
            self.json_ld[-1] += data
        elif self._in == "title":
            self.title = (self.title or "") + data
        elif not self._skipping:
            self.parts.append(re.sub(r"\s+", " ", data))

    def text(self) -> str:
        return _tidy("".join(self.parts))


def html_to_text(markup: str) -> str:
    page = _Page()
    page.feed(markup)
    return page.text()


def _job_posting(blocks: list[str]) -> dict | None:
    """The first schema.org JobPosting in the page's JSON-LD."""

    def walk(node):
        if isinstance(node, list):
            for item in node:
                if (found := walk(item)) is not None:
                    return found
        elif isinstance(node, dict):
            kind = node.get("@type")
            if kind == "JobPosting" or (isinstance(kind, list) and "JobPosting" in kind):
                return node
            return walk(node.get("@graph"))
        return None

    for block in blocks:
        try:
            found = walk(json.loads(block, strict=False))
        except ValueError, RecursionError:  # not JSON, or nested deeper than anyone writes it
            continue
        if found is not None:
            return found
    return None


CURRENCY = {"USD": "$", "GBP": "£", "EUR": "€"}
PER = {"YEAR": "a year", "MONTH": "a month", "WEEK": "a week", "DAY": "a day", "HOUR": "an hour"}


def _pay(low, high, currency: str | None, per: str | None) -> str | None:
    """ "$150,000-$200,000 a year", from what the posting gives."""
    try:
        amounts = [int(float(v)) for v in (low, high) if v not in (None, "")]
    except TypeError, ValueError:
        return None
    if not amounts:
        return None
    sign = CURRENCY.get((currency or "").upper(), f"{currency} " if currency else "")
    band = "-".join(f"{sign}{a:,}" for a in dict.fromkeys(amounts))
    return f"{band} {PER[per]}" if per in PER else band


# A site's own word for how much of the job is remote, from its page data ("workplaceType":"Hybrid",
# as Ashby and others send it). schema.org has only TELECOMMUTE, which sites also use for hybrid.
WORKPLACE = {"hybrid": "hybrid", "remote": "remote", "onsite": "on site", "on_site": "on site", "on-site": "on site"}
WORKPLACE_IN_PAGE = re.compile(r'"workplaceType"\s*:\s*"([\w -]+)"', re.I)


def _location(job: dict, workplace: str | None) -> str | None:
    """The city, and how much is remote when the posting says: "San Francisco, California (hybrid)".
    Telecommute with no word from the site is "remote or hybrid"; with no city, just "Remote"."""
    places = job.get("jobLocation")
    place = (places[0] if places else None) if isinstance(places, list) else places
    address = place.get("address") if isinstance(place, dict) else None
    city = None
    if isinstance(address, dict):
        city = ", ".join(p for p in (address.get("addressLocality"), address.get("addressRegion")) if p) or address.get(
            "addressCountry"
        )
    telecommute = "TELECOMMUTE" in str(job.get("jobLocationType", "")).upper()
    how = workplace or ("remote or hybrid" if telecommute else None)
    if not city:
        return (
            "Remote"
            if telecommute and how in (None, "remote", "remote or hybrid")
            else (how.capitalize() if how else None)
        )
    return f"{city} ({how})" if how else city


def _from_job_posting(job: dict, workplace: str | None = None) -> dict:
    org = job.get("hiringOrganization")
    company = org.get("name") if isinstance(org, dict) else org if isinstance(org, str) else None
    location = _location(job, workplace)
    salary = job.get("baseSalary") if isinstance(job.get("baseSalary"), dict) else {}
    value = salary.get("value") if isinstance(salary.get("value"), dict) else {}
    comp = _pay(
        value.get("minValue", value.get("value")), value.get("maxValue"), salary.get("currency"), value.get("unitText")
    )
    description = job.get("description")
    return {
        "company": company,
        "title": job.get("title"),
        "location": location,
        "comp": comp,
        "posting": html_to_text(html.unescape(description)) if isinstance(description, str) else None,
    }


def _from_page(markup: str) -> tuple[dict, str]:
    page = _Page()
    page.feed(markup)
    job = _job_posting(page.json_ld)
    if job is not None:
        said = WORKPLACE_IN_PAGE.search(markup)
        draft = _from_job_posting(job, WORKPLACE.get(said[1].strip().lower()) if said else None)
        if not draft["posting"]:
            draft["posting"] = page.text() or None
        return draft, "page data"
    title = page.og_title or (page.title or "").strip() or None
    return {"company": None, "title": title, "location": None, "comp": None, "posting": page.text() or None}, "page"


# ── Job sites with public feeds ──────────────────────────────────────────────


def _greenhouse(board: str, job_id: str, get) -> dict:
    job = json.loads(get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}")[0])
    return {
        "company": job.get("company_name"),
        "title": job.get("title"),
        "location": (job.get("location") or {}).get("name"),
        "comp": None,
        "posting": html_to_text(html.unescape(job.get("content") or "")),
    }


# (host, path pattern, reader). The groups are the path parts the reader needs.
FEEDS = [
    ({"boards.greenhouse.io", "job-boards.greenhouse.io"}, r"^/([\w-]+)/jobs/(\d+)", _greenhouse),
]


def read(link: str, get=fetch) -> dict:
    """A draft role from the posting at link: company, title, location, comp, the posting's text,
    and where they came from (feed, page data or page). Unreadable says why not."""
    check_link(link)
    parts = urlsplit(link)
    for hosts, pattern, reader in FEEDS:
        match = re.match(pattern, parts.path)
        if parts.hostname in hosts and match:
            try:
                draft = reader(*match.groups(), get)
            except ValueError:  # not the JSON the feed sends
                raise Unreadable(f"{parts.hostname} sent something unexpected. {PASTE}") from None
            found = "feed"
            break
    else:
        body, kind = get(link)
        draft, found = (
            _from_page(body)
            if kind != "text/plain"
            else ({"company": None, "title": None, "location": None, "comp": None, "posting": body.strip()}, "page")
        )
    if not draft.get("posting"):
        raise Unreadable(f"That page shows no posting without a browser (Workday and LinkedIn often do this). {PASTE}")
    draft = {
        k: (v.strip()[:MAX_LINE] or None) if isinstance(v, str) and k != "posting" else v for k, v in draft.items()
    }
    text = _tidy(draft["posting"])
    return {**draft, "comp": draft["comp"] or _pay_in_text(text), "posting": text[:MAX_TEXT], "from": found}


# A pay range as postings write it: "$166,000 – $185,000 per year", "$120K-$150K USD", "$55 to $70 an hour".
_AMOUNT = r"\$\s?\d[\d,]*(?:\.\d+)?\s?[KkMm]?"
PAY_RANGE = re.compile(
    rf"(?P<low>{_AMOUNT})\s*(?:–|—|-|to)\s*(?P<high>{_AMOUNT})"
    r"(?:\s?(?:USD|CAD|EUR|GBP))?(?:\s*(?:per|an?|/)\s*(?:year|yr|annum|month|week|hour|hr)\b)?"
)


def _is_pay(amount: str) -> bool:
    """A yearly or hourly amount, not a funding round: under a million."""
    digits = re.sub(r"[^\d.]", "", amount)
    unit = amount.strip()[-1].upper()
    value = float(digits or 0) * {"K": 1_000, "M": 1_000_000}.get(unit, 1)
    return 10 <= value < 1_000_000


def _pay_in_text(text: str) -> str | None:
    """The first pay range written in the posting, exactly as written."""
    for match in PAY_RANGE.finditer(text):
        if _is_pay(match["low"]) and _is_pay(match["high"]):
            return match[0].strip()
    return None


def _tidy(text: str) -> str:
    """Plain text as sites send it, with no-break spaces as spaces and at most one blank line in a row."""
    lines = [line.strip() for line in text.replace("\xa0", " ").split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
