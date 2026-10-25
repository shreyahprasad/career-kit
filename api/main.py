"""
Read-only data server for the career-kit dashboard (web/).

This process only reads a fixed set of files and has no write routes, no shell access, and no
credentials. Changes go through the writers in tools/.

It also serves the built site in web/dist (`pnpm build`), so one process is all the
phone needs through `tailscale serve`. Vite stays the dev server. It answers only to this Mac's
names and its tailnet names, and over the tailnet only to you: the same check the writers make
(tools/writekit/writekit/identity.py). Every answer carries SECURITY_HEADERS.

    uv run uvicorn main:app --host 127.0.0.1 --port 8100
"""

import json
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

import career
import networking
from writekit.identity import add_identity_check, tailnet_hosts, tailnet_logins

WEB_DIST = Path(os.environ.get("WEB_DIST", Path(__file__).resolve().parent.parent / "web/dist"))

app = FastAPI(title="career-kit api", docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(career.router)
app.include_router(networking.router)
add_identity_check(app, tailnet_logins(), "This page is only for its owner.", tailnet_hosts())

# The page's headers, the same wherever it is served (vite preview reads them too). Only the built
# site's own files run or load. Styles allow inline: React sets style attributes (colors, sizes).
# pdf.js runs its worker from our own file and may compile its WebAssembly image decoders; nothing
# may eval JavaScript. No other site may frame it.
SECURITY_HEADERS = json.loads((Path(__file__).resolve().parent.parent / "web/security-headers.json").read_text())


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.update(SECURITY_HEADERS)
    return response


# Names the app, so a check on a port another program holds (one answering {"ok": true} too)
# cannot pass for career-kit.
HEALTH = {"ok": True, "app": "career-kit"}


@app.get("/api/health")
def health() -> dict:
    return HEALTH


# ── The built site ───────────────────────────────────────────────────────────

# Mounted last, so every /api route above wins. Skipped until there is a build.
if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="site")
