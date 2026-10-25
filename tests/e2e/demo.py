"""
Records the README's demo video: the page on the phone, on a copy of this checkout, with made-up
data (Pyke Shipping, Asha Greyjoy). Same copy, scratch ports and stop.sh as the e2e tests
(conftest.py).

    cd tests/e2e && uv run python -I demo.py <out folder>

Each scene shows what you would say to Claude as a caption, then makes the same writer call
Claude would and reloads the page (it does not poll). The frames are screenshots at the phone's
full resolution, one per step (Playwright's video and Chrome's screencast are at CSS pixels, half
of it). Writes <out folder>/frames/,
<out folder>/frames.txt (an ffmpeg concat list with each frame's duration) and scenes.json (when
each scene starts, in seconds). To make the MP4:

    ffmpeg -f concat -i frames.txt -vf fps=30,format=yuv420p -c:v libx264 -crf 20 -map_metadata -1 demo.mp4
"""

import json
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from playwright.sync_api import sync_playwright  # noqa: E402

from conftest import LIVE, PORTS, App, Watch, answers, copy_checkout, set_ports  # noqa: E402

PHONE = {"width": 390, "height": 844}
SCALE = 2
BEAT = 1200  # ms to read a screen before the next step
FPS = 30
SCROLL_SPEED = 700  # px a second

CAPTION = """
(text) => {
  document.getElementById("demo-caption")?.remove();
  const box = document.createElement("div");
  box.id = "demo-caption";
  box.style.cssText = `position:fixed;pointer-events:none;left:16px;right:16px;bottom:24px;z-index:99999;
    padding:12px 14px;border-radius:16px;background:#1f6feb;color:#fff;
    font:500 15px/1.35 -apple-system,system-ui,sans-serif;box-shadow:0 6px 24px rgba(0,0,0,.35)`;
  const who = document.createElement("div");
  who.textContent = "You, to Claude";
  who.style.cssText = "font-size:11px;letter-spacing:.06em;text-transform:uppercase;opacity:.8;margin-bottom:4px";
  const said = document.createElement("div");
  said.textContent = text;
  box.append(who, said);
  document.body.append(box);
}
"""

POSTING = """Data Analyst, Pyke Shipping (Remote)

Pyke Shipping moves freight across the Iron Islands and beyond. We are looking for a data
analyst to own our on-time delivery reporting.

What you will do
- Build and maintain dashboards for route performance and delivery times.
- Write SQL against our warehouse and explain what the numbers mean to operations leads.
- Work with the routing team to test changes and measure the results.

What we are looking for
- 3+ years of analytics work with SQL and Python.
- Clear writing for people who are not analysts.
- Logistics or shipping experience is a plus."""


def seed(app: App) -> None:
    """A board that looks used: roles across statuses, a few events and open todos."""
    today = date.today()

    def ago(days: int) -> str:
        return (today - timedelta(days=days)).isoformat()

    def move(role_id: str, status: str, days: int) -> None:
        version = app.role(role_id)["version"]
        app.write(
            "POST",
            f"/api/career/write/roles/{role_id}/status",
            {"status": status, "date": ago(days), "version": version},
        )

    def log(role_id: str, kind: str, days: int, text: str) -> None:
        app.write("POST", f"/api/career/write/roles/{role_id}/events", {"kind": kind, "date": ago(days), "text": text})

    dragon = app.add_role("Dragonstone Freight", "Senior Data Analyst", location="Remote")
    move(dragon, "applied", 12)
    log(dragon, "recruiter-call", 8, "Recruiter call, went well")
    move(dragon, "screen", 8)
    log(dragon, "interview", 3, "First round with the analytics lead")
    move(dragon, "interviews", 3)
    braavos = app.add_role("Iron Bank of Braavos", "Analytics Engineer", location="New York")
    move(braavos, "applied", 6)
    app.add_role("Highgarden Foods", "Data Analyst", location="Remote")
    app.add_role("Oldtown Health", "Product Analyst", location="Boston")
    casterly = app.add_role("Casterly Capital", "BI Analyst", location="Chicago")
    move(casterly, "applied", 20)
    move(casterly, "rejected", 9)

    # The starter todos would crowd the board, so most are checked off as done.
    for role in app.read("/api/career/roles")["roles"]:
        for todo in app.read(f"/api/career/roles/{role['id']}")["todos"]:
            keep = (role["id"], todo["text"]) in {(dragon, "Message recruiter")}
            if not keep:
                app.write("PATCH", f"/api/career/write/todos/{todo['id']}", {"done": True, "version": todo["version"]})
    app.write(
        "POST",
        "/api/career/write/todos",
        {"text": "Prep a story about route data", "kind": "prep", "role_id": dragon, "due_on": ago(-1)},
    )
    app.write(
        "POST",
        "/api/career/write/todos",
        {"text": "Follow up with the Braavos recruiter", "kind": "outreach", "role_id": braavos, "due_on": ago(-2)},
    )

    # A phonebook that looks used: someone at most of the companies on the board.
    people = [
        (
            "Brienne Tarth",
            "Iron Bank of Braavos",
            "Recruiter",
            "call",
            6,
            "Next round is with the hiring manager",
            "follow-up",
        ),
        (
            "Missandei",
            "Dragonstone Freight",
            "Analytics Lead",
            "video",
            3,
            "Walked me through their route data",
            "catch-up",
        ),
        (
            "Margaery Tyrell",
            "Highgarden Foods",
            "Head of Data",
            "coffee",
            14,
            "Knows the hiring manager well",
            "ask-intro",
        ),
        (
            "Lyanna Mormont",
            "Oldtown Health",
            "Product Analyst",
            "message",
            8,
            "Said the team grows in spring",
            "send-resume",
        ),
    ]
    for name, company, role, kind, days, summary, next_step in people:
        app.write(
            "POST",
            "/api/networking/write/interactions",
            {
                "person": {"name": name, "company": company, "role": role},
                "kind": kind,
                "date": ago(days),
                "summary": summary,
                "next_step": next_step,
            },
        )


FIND_SCROLLER = """
(el, top) => {
  let box = el.parentElement;
  while (box && !(box.scrollHeight > box.clientHeight && /auto|scroll/.test(getComputedStyle(box).overflowY))) {
    box = box.parentElement;
  }
  box = box || document.scrollingElement;
  window.demoScroller = box;
  const most = box.scrollHeight - box.clientHeight;
  return [box.scrollTop, Math.max(0, Math.min(most, box.scrollTop + el.getBoundingClientRect().top - top))];
}
"""


def glide(page, shoot, begin: float, end: float) -> None:
    """Scrolls window.demoScroller from one place to another, a frame at a time, eased."""
    page.mouse.move(0, 0)  # off every card, so none lights up as it passes under
    steps = max(8, round(abs(end - begin) / SCROLL_SPEED * FPS))
    for i in range(1, steps + 1):
        t = i / steps
        eased = t * t * (3 - 2 * t)
        y = begin + (end - begin) * eased
        page.evaluate("(y) => { demoScroller.style.scrollBehavior = 'auto'; demoScroller.scrollTop = y; }", y)
        shoot()


def scroll_to(page, shoot, locator, top: int = 70) -> None:
    """Scrolls until the locator's top sits about `top` px from the screen's top, or the end."""
    begin, end = locator.evaluate(FIND_SCROLLER, top)
    glide(page, shoot, begin, end)


def scroll_home(page, shoot) -> None:
    begin = page.evaluate("demoScroller.scrollTop")
    glide(page, shoot, begin, 0)


def record(app: App, out: Path) -> None:
    marks: dict[str, float] = {}
    watch = Watch()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport=PHONE,
            device_scale_factor=SCALE,
            base_url=app.web,
        )
        context.route("**/favicon.ico", lambda route: route.fulfill(status=204, body=""))
        page = context.new_page()
        page.on("console", watch.console)
        page.on("pageerror", lambda e: watch.problems.append(f"page error: {e}"))
        page.on("response", watch.answer)

        frames = out / "frames"
        frames.mkdir()
        shots: list[tuple[Path, float]] = []  # each frame and how long it shows, in seconds

        def shoot(seconds: float = 1 / FPS) -> None:
            """A frame of what is on screen now. The video's clock is these durations, not the time a
            screenshot takes, so scrolling plays smoothly."""
            path = frames / f"{len(shots):05d}.png"
            page.screenshot(path=path)
            shots.append((path, seconds))

        def hold(ms: int) -> None:
            shoot(ms / 1000)

        def mark(name: str) -> None:
            marks[name] = round(sum(seconds for _, seconds in shots), 2)

        def caption(text: str) -> None:
            page.evaluate(CAPTION, text)

        def reload(text: str) -> None:
            """The page shows a change after a reload; the caption stays up across it."""
            page.reload()
            page.wait_for_load_state("networkidle")
            caption(text)

        # 1. The board.
        page.goto("/#/career")
        page.get_by_role("heading", name="Career", level=1).wait_for()
        page.wait_for_load_state("networkidle")
        mark("board")
        hold(BEAT)
        page.get_by_role("region", name="To do").get_by_role("button", name="To do").click()
        hold(BEAT * 2)
        scroll_to(page, shoot, page.get_by_role("region", name="Interviews"), 60)
        hold(BEAT)
        scroll_home(page, shoot)
        hold(BEAT // 2)

        # 2. Add a role.
        said = "Add this job: https://jobs.example.com/pyke-shipping/data-analyst"
        mark("add")
        caption(said)
        hold(BEAT * 2)
        pyke = app.add_role(
            "Pyke Shipping",
            "Data Analyst",
            location="Remote",
            link="https://jobs.example.com/pyke-shipping/data-analyst",
            posting=POSTING,
        )
        reload(said)
        card = page.locator(f'a[href$="/career/{pyke}"]')
        scroll_to(page, shoot, card, 200)
        hold(BEAT * 2)
        card.click()
        page.get_by_role("heading", name="Data Analyst", level=1).wait_for()
        page.wait_for_load_state("networkidle")
        caption(said)
        hold(BEAT * 2)
        scroll_to(page, shoot, page.get_by_role("region", name="To do"), 60)
        hold(BEAT * 2)
        posting = page.get_by_role("region", name="Posting")
        scroll_to(page, shoot, posting, 60)
        posting.get_by_role("button", name="words").click()
        hold(BEAT)
        scroll_to(page, shoot, posting.get_by_text("What you will do"), 60)
        hold(BEAT * 2)
        scroll_home(page, shoot)
        hold(BEAT // 2)

        # 3. Applied.
        said = "I applied to Pyke Shipping today"
        mark("applied")
        caption(said)
        hold(BEAT * 2)
        app.write(
            "POST",
            f"/api/career/write/roles/{pyke}/status",
            {"status": "applied", "version": app.role(pyke)["version"]},
        )
        reload(said)
        hold(BEAT * 2)
        scroll_to(page, shoot, page.get_by_role("region", name="Timeline"), 60)
        hold(BEAT * 2)

        # 4. A talk with Asha Greyjoy, who offers a referral: the phonebook before and after.
        said = "Had coffee with Asha Greyjoy from Pyke Shipping, she offered to refer me"
        mark("talk")
        caption(said)
        hold(BEAT * 2)

        def open_people() -> None:
            """The People list starts folded on the phone."""
            page.get_by_role("heading", name="Networking", level=1).wait_for()
            page.wait_for_load_state("networkidle")
            page.get_by_role("region", name="People").get_by_role("button", name="People").click()
            caption(said)

        page.goto("/#/networking")
        open_people()
        hold(BEAT * 2)
        talk = app.write(
            "POST",
            "/api/networking/write/interactions",
            {
                "person": {
                    "name": "Asha Greyjoy",
                    "company": "Pyke Shipping",
                    "role": "Data Lead",
                    "met_how": "Coffee",
                },
                "kind": "coffee",
                "summary": "Offered to refer me for the Data Analyst role",
                "notes": "Team is small and moving fast. Send her my resume so she can pass it on.",
                "next_step": "send-resume",
            },
        )
        asha = talk["person_id"]
        page.reload()
        open_people()
        hold(BEAT * 2)
        page.locator(f'a[href$="/networking/{asha}"]').first.click()
        card = page.get_by_role("region", name="Person")
        card.get_by_role("heading", name="Asha Greyjoy").wait_for()
        page.wait_for_load_state("networkidle")
        caption(said)
        scroll_to(page, shoot, card, 60)
        hold(BEAT * 3)

        # 5. Asha on the role as the referral (Claude links her in the same reply).
        app.write(
            "PATCH",
            f"/api/career/write/roles/{pyke}",
            {"referral_person_id": asha, "version": app.role(pyke)["version"]},
        )
        mark("referral")
        page.goto(f"/#/career/{pyke}")
        page.get_by_role("heading", name="Data Analyst", level=1).wait_for()
        page.wait_for_load_state("networkidle")
        caption(said)
        scroll_to(page, shoot, page.get_by_role("region", name="Referred by"), 120)
        hold(BEAT * 3)
        mark("done")
        context.close()
        browser.close()

    lines = ["ffconcat version 1.0"]
    for path, seconds in shots:
        lines += [f"file 'frames/{path.name}'", f"duration {seconds:.4f}"]
    lines.append(f"file 'frames/{shots[-1][0].name}'")
    (out / "frames.txt").write_text("\n".join(lines) + "\n")
    (out / "scenes.json").write_text(json.dumps(marks, indent=2))
    assert not watch.problems, "\n".join(watch.problems)


def main() -> None:
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    for port in PORTS.values():
        assert port not in LIVE, f":{port} is where your own career-kit runs"
        assert not answers(port), f"Something is already on :{port}. Stop it first."
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        copy_checkout(root)
        app = App(root)
        try:
            app.run("setup.sh")
            set_ports(root / ".env")
            app.run("start.sh")
            seed(app)
            record(app, out)
        finally:
            app.run("stop.sh", check=False)
            still = [port for port in PORTS.values() if answers(port)]
            assert not still, f"still answering after stop.sh: {still}"
    print(f"wrote {out / 'frames.txt'}")


if __name__ == "__main__":
    main()
