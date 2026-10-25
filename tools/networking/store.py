"""networking.db, written only through db (writekit.Database). Its schema is schema.sql."""

import os
from pathlib import Path

from writekit.db import Database

db = Database(
    Path(os.environ.get("NETWORKING_DB", Path(__file__).resolve().parents[2] / "data/networking.db")),
    Path(__file__).with_name("migrations"),
)
