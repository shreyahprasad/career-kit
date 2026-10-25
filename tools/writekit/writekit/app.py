"""
create_writer(): the FastAPI app every writer starts from.

- Every change (anything but GET and HEAD) must carry WRITE_HEADER: 1. A browser sends a custom
  header to another origin only after a CORS preflight, which a writer never answers, so a page
  on another site open in your browser cannot post to it.
- It answers only to this Mac's names and its tailnet names, and over the tailnet only to you
  (identity.py).
- Every answer is JSON, marked so nothing in it is sniffed, run, loaded or framed (DATA_HEADERS).
- A change sent with an Idempotency-Key is made once: sent again with the same key (the phone lost
  the answer and retried), it gets the first answer back, waiting for it if it is still saving.
  Keys are kept in memory for IDEMPOTENCY_HOURS, at most IDEMPOTENCY_MAX of them, so a writer
  that restarts forgets them: a retry that reaches the new process is made again. A POST in reads
  changes nothing (reading a posting), so its answer, which can be long, is never kept.
- A body over max_body_bytes is refused on its Content-Length, before it is read.
- Starting the app applies the database's pending migrations, then runs on_start if given.
- errors.Refused, NotFound and Rejected, and SQLite refusing a row, come back as JSON
  {"detail": why} with their status; web/src/shell/api.ts send() shows the reason.
"""

import asyncio
import logging
import re
import sqlite3
import time
from collections import OrderedDict
from collections.abc import Callable, Iterable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from .db import Database
from .errors import NotFound, Refused, Rejected
from .identity import add_identity_check, tailnet_hosts, tailnet_logins

WRITE_HEADER = "X-Career-Kit-Write"
SAFE_METHODS = frozenset({"GET", "HEAD"})

DATA_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}

IDEMPOTENCY_HEADER = "Idempotency-Key"
IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9-]{8,100}$")  # the page sends a UUID
IDEMPOTENCY_HOURS = 24  # far longer than a phone retries
IDEMPOTENCY_MAX = 1000  # far more changes than a day holds

log = logging.getLogger("uvicorn.error")  # uvicorn prints its own loggers only; this lands in the writer log

STATUS = {Refused: 409, NotFound: 404, Rejected: 400, sqlite3.IntegrityError: 409}


def _refuse(status: int, detail: str) -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=status)


class _Answers:
    """The answer to each Idempotency-Key, and the keys still being saved."""

    def __init__(self):
        self.done: OrderedDict[str, tuple[str, float, Response]] = OrderedDict()  # key: (method path, when, answer)
        self.saving: dict[str, tuple[str, asyncio.Event]] = {}

    def forget_old(self) -> None:
        oldest = time.monotonic() - IDEMPOTENCY_HOURS * 3600
        while self.done and (len(self.done) > IDEMPOTENCY_MAX or next(iter(self.done.values()))[1] < oldest):
            self.done.popitem(last=False)


def create_writer(
    name: str,
    db: Database,
    max_body_bytes: int,
    on_start: Callable[[], None] | None = None,
    logins: Iterable[str] | None = None,
    env_file: Path | None = None,
    reads: Iterable[str] = (),
    hosts: Iterable[str] | None = None,
) -> FastAPI:
    """logins are who may use it over the tailnet, and hosts its tailnet names; None reads
    TAILNET_LOGINS or TAILNET_HOSTS from env_file (the main checkout's .env when that is None).
    reads are the paths of POSTs that change nothing."""
    allowed = frozenset(logins) if logins is not None else tailnet_logins(env_file)
    names = frozenset(hosts) if hosts is not None else tailnet_hosts(env_file)
    reads = frozenset(reads)
    answers = _Answers()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        applied = db.migrate()
        if applied:
            log.info("migrated %s: %s", db.path.name, ", ".join(applied))
        if on_start is not None:
            on_start()
        yield

    app = FastAPI(title=f"career-kit {name} writer", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

    # Middleware runs last-added first: who it is from, then the header and size, then this
    # idempotency key check, added first so it runs last.
    @app.middleware("http")
    async def saved_once(request: Request, call_next):
        key = request.headers.get(IDEMPOTENCY_HEADER)
        if request.method in SAFE_METHODS or key is None or request.url.path in reads:
            return await call_next(request)
        if not IDEMPOTENCY_KEY.match(key):
            return _refuse(400, f"{IDEMPOTENCY_HEADER} should be 8 to 100 letters, digits and dashes.")
        change = f"{request.method} {request.url.path}"
        while key in answers.saving:  # the same change sent again while the first is saving
            await answers.saving[key][1].wait()
        if key in answers.done:
            first_change, _, answer = answers.done[key]
            if first_change != change:
                return _refuse(422, f"That {IDEMPOTENCY_HEADER} was already used for another change.")
            return Response(answer.body, answer.status_code, headers=dict(answer.headers))
        saved = asyncio.Event()
        answers.saving[key] = (change, saved)
        try:
            response = await call_next(request)
            body = b"".join([chunk async for chunk in response.body_iterator])
            answer = Response(body, response.status_code, headers=dict(response.headers))
            answers.done[key] = (change, time.monotonic(), answer)
            answers.forget_old()
            return answer
        finally:
            del answers.saving[key]
            saved.set()

    @app.middleware("http")
    async def changes_need_the_header(request: Request, call_next):
        if request.method not in SAFE_METHODS:
            if request.headers.get(WRITE_HEADER) != "1":
                return _refuse(403, f"Changes need the {WRITE_HEADER} header.")
            size = request.headers.get("content-length")
            if size is None and request.headers.get("transfer-encoding"):
                return _refuse(411, "Send the change with a Content-Length.")
            if size is not None and not (size.isascii() and size.isdigit()):
                return _refuse(400, "Content-Length should be a number of bytes.")
            if size is not None and int(size) > max_body_bytes:
                return _refuse(413, "That is too large to save.")
        return await call_next(request)

    add_identity_check(app, allowed, "Changes come only from the owner.", names)

    @app.middleware("http")
    async def data_only(request: Request, call_next):
        response = await call_next(request)
        response.headers.update(DATA_HEADERS)
        return response

    async def refusal(_: Request, e: Exception):
        detail = f"{db.path.name} refused it: {e}" if isinstance(e, sqlite3.IntegrityError) else str(e)
        status = next(code for error, code in STATUS.items() if isinstance(e, error))
        return _refuse(status, detail)

    for error in STATUS:
        app.add_exception_handler(error, refusal)
    return app
