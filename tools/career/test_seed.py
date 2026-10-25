"""seed.py as setup.sh runs it: an empty career.db, private, made once and never over one there."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def run_seed(data_dir: Path, source: Path) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "CAREER_DB"} | {"CAREER_DIR": str(data_dir)}
    return subprocess.run([sys.executable, "seed.py", str(source)], cwd=HERE, env=env, capture_output=True, text=True)


@pytest.fixture
def empty(tmp_path) -> Path:
    source = tmp_path / "career.json"
    source.write_text('{"roles": []}')  # what setup.sh sends
    return source


def test_setup_makes_an_empty_private_database_from_the_schema(tmp_path, empty):
    data = tmp_path / "data"
    result = run_seed(data, empty)
    assert result.returncode == 0, result.stderr
    db = data / "career.db"
    assert (data.stat().st_mode & 0o777, db.stat().st_mode & 0o777) == (0o700, 0o600)
    conn = sqlite3.connect(db)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"roles", "events", "todos"} <= tables
    assert conn.execute("SELECT count(*) FROM roles").fetchone()[0] == 0
    conn.close()


def test_a_database_already_there_is_never_written_over(tmp_path, empty):
    data = tmp_path / "data"
    run_seed(data, empty)
    before = (data / "career.db").read_bytes()
    result = run_seed(data, empty)
    assert result.returncode != 0 and "already exists" in result.stderr
    assert (data / "career.db").read_bytes() == before


def test_a_bad_seed_file_leaves_no_database(tmp_path):
    source = tmp_path / "career.json"
    source.write_text('{"roles": [{"id": "acme-fde", "company": "Acme", "title": "FDE", "typo": 1}]}')
    result = run_seed(tmp_path / "data", source)
    assert result.returncode != 0 and "acme-fde" in result.stderr
    assert not (tmp_path / "data/career.db").exists()
