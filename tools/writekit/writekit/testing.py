"""What every writer's tests check the same way."""

import json
import os
import re
from pathlib import Path

from pydantic import BaseModel

from .app import WRITE_HEADER

HEADERS = {WRITE_HEADER: "1"}
# Where test clients send from: this Mac, by a name the identity check answers to.
LOCAL = "http://127.0.0.1"


def assert_schema_current(schema: Path, migrations: Path) -> None:
    """schema.sql builds a database as new as the newest migration, so migrate() never runs one
    on it that is already in it."""
    newest = max((int(m.name[:3]) for m in migrations.glob("[0-9][0-9][0-9]_*.sql")), default=0)
    found = re.findall(r"PRAGMA user_version = (\d+);", schema.read_text())
    assert found == [str(newest)], f"{schema.name} should end with PRAGMA user_version = {newest}; found {found}"


def assert_fields_current(path: Path, forms: dict[str, type[BaseModel]]) -> None:
    """path (fields.json, beside writer.py) lists the fields each request body accepts, for the
    page's tests to hold its changes to. UPDATE_FIELDS=1 rewrites it."""
    fields = {name: sorted(form.model_fields) for name, form in sorted(forms.items())}
    text = json.dumps(fields, indent=2) + "\n"
    if os.environ.get("UPDATE_FIELDS") == "1":
        path.write_text(text)
    found = path.read_text() if path.exists() else ""
    assert found == text, f"{path.name} is out of date with writer.py. Rewrite it: UPDATE_FIELDS=1 uv run pytest -q"
