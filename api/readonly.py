"""How every router opens its database: read-only, rows by name, always closed. A missing file
is a 404 that says how to make it, never a new empty database."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi import HTTPException


@contextmanager
def open_readonly(path: Path, missing: str) -> Iterator[sqlite3.Connection]:
    if not path.exists():
        raise HTTPException(404, missing)
    db = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        yield db
    finally:
        db.close()
