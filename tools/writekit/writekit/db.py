"""
One writer's SQLite database: the one way to write it, backups, and migrations.

A write opens writing() and runs in one BEGIN IMMEDIATE ... COMMIT; change() does all of that
and takes the backup. migrate() leaves the database in WAL mode, so the dashboard keeps reading
while a write runs.

Migrations are migrations/NNN_name.sql, applied in order above PRAGMA user_version. schema.sql
builds a database that is already current, so it ends by setting user_version to the newest
migration (testing.assert_schema_current holds it to that).

Backups are "each" (before every change) or "daily" (before the first change of each day), for
a database that changes too often for a copy per change. Each
backup also thins out old ones (prune_backups): every backup from the last KEEP_EVERY_DAYS, then
the first of each day back to KEEP_DAILY_DAYS, then none. A migration's backup is always kept.
"""

import datetime as dt
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

Backups = Literal["each", "daily"]

KEEP_EVERY_DAYS = 7
KEEP_DAILY_DAYS = 90
# <stem>-YYYY-MM-DD-HHMMSS-ffffff-before-<label>.db, as backup() names them.
BACKUP_NAME = re.compile(r"-(\d{4}-\d{2}-\d{2})-\d{6}-\d{6}-before-(.+)\.db$")


class Database:
    def __init__(self, path: Path, migrations: Path, backups: Backups = "each"):
        self.path = path
        self.migrations = migrations
        self.backups = backups

    def _check_exists(self) -> None:
        # sqlite3.connect would quietly create an empty one.
        if not self.path.exists():
            raise FileNotFoundError(f"{self.path} not found.")

    @contextmanager
    def reading(self) -> Iterator[sqlite3.Connection]:
        """A read-only connection, always closed."""
        self._check_exists()
        db = sqlite3.connect(f"{self.path.as_uri()}?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def writing(self) -> Iterator[sqlite3.Connection]:
        """A connection with foreign keys checked and explicit transactions, always closed. A
        write that fails halfway is rolled back, so nothing is half saved and the database is
        never left locked."""
        self._check_exists()
        db = sqlite3.connect(self.path, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            yield db
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    @contextmanager
    def change(self, label: str) -> Iterator[sqlite3.Connection]:
        """One change, all or nothing: BEGIN IMMEDIATE, a backup named for label, and COMMIT
        when the block ends without raising. The backup is taken holding the write lock, so it
        is exactly the database before this change; a change that raises saved nothing, so its
        backup is deleted. With daily backups, only the day's first change takes one."""
        with self.writing() as db:
            db.execute("BEGIN IMMEDIATE")
            backup = None if self.backups == "daily" and self._backed_up_today() else self.backup(label)
            try:
                yield db
                db.execute("COMMIT")
            except BaseException:
                if backup is not None:
                    backup.unlink(missing_ok=True)
                raise

    def prune_backups(self, today: dt.date | None = None) -> None:
        """Deletes old backups of this database, as the module docstring says."""
        today = today or dt.date.today()
        folder = self.path.parent / "backups"
        if not folder.is_dir():
            return
        first_of_day: set[str] = set()
        for path in sorted(folder.glob(f"{self.path.stem}-*.db")):  # oldest first, by name
            match = BACKUP_NAME.search(path.name)
            if match is None or match[2].startswith("migration-"):
                continue
            age = (today - dt.date.fromisoformat(match[1])).days
            if age < KEEP_EVERY_DAYS:
                continue
            if age < KEEP_DAILY_DAYS and match[1] not in first_of_day:
                first_of_day.add(match[1])
                continue
            path.unlink(missing_ok=True)

    def _backed_up_today(self) -> bool:
        return any((self.path.parent / "backups").glob(f"{self.path.stem}-{dt.date.today():%Y-%m-%d}-*.db"))

    def backup(self, label: str) -> Path:
        """A copy of the database as it is now, in backups/ next to it, named for the change
        about to be made."""
        folder = self.path.parent / "backups"
        folder.mkdir(mode=0o700, exist_ok=True)
        path = folder / f"{self.path.stem}-{dt.datetime.now():%Y-%m-%d-%H%M%S-%f}-before-{label}.db"
        path.touch(mode=0o600)
        with sqlite3.connect(self.path) as src, sqlite3.connect(path) as dst:
            src.backup(dst)
        self.prune_backups()
        return path

    def _pending(self, version: int) -> list[Path]:
        return [m for m in sorted(self.migrations.glob("[0-9][0-9][0-9]_*.sql")) if int(m.name[:3]) > version]

    def migrate(self) -> list[str]:
        """Applies the pending migrations, each in its own transaction, after one backup.
        Returns the names applied."""
        with self.writing() as db:
            pending = self._pending(db.execute("PRAGMA user_version").fetchone()[0])
            if pending:
                self.backup("migration-" + pending[0].stem)
            for m in pending:
                # BEGIN inside the script: executescript commits any transaction opened outside it.
                db.executescript(
                    f"BEGIN IMMEDIATE;\n{m.read_text()}\nPRAGMA user_version = {int(m.name[:3])};\nCOMMIT;"
                )
            db.execute("PRAGMA journal_mode = WAL")
        return [m.name for m in pending]
