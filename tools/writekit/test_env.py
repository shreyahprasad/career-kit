""".env is read twice: by scripts/common.sh (the ports, before any Python runs) and by
writekit/env.py (the tailnet settings). These run both on the same file, so they never drift."""

import shutil
import subprocess
from pathlib import Path

import pytest

from writekit.env import env_value

COMMON = Path(__file__).resolve().parents[2] / "scripts/common.sh"

ENV = """\
PLAIN=value
  SPACED  =   spaced value
export EXPORTED=yes
export\tTABBED=tab
exportX=keep
DOUBLE="double # not a comment"
SINGLE='single'
COMMENTED=8100 # the API
HASHED=abc#def
BLANK=
BLANK=second
EMPTY_QUOTES=""
EMPTY_QUOTES=after
# COMMENTED_OUT=1
NO_EQUALS
UNCLOSED="open
CRLF=windows\r
"""

EXPECTED = {
    "PLAIN": "value",
    "SPACED": "spaced value",
    "EXPORTED": "yes",
    "TABBED": "tab",
    "exportX": "keep",
    "DOUBLE": "double # not a comment",
    "SINGLE": "single",
    "COMMENTED": "8100",
    "HASHED": "abc",
    "BLANK": "second",
    "EMPTY_QUOTES": "after",
    "COMMENTED_OUT": None,
    "NO_EQUALS": None,
    "MISSING": None,
    "UNCLOSED": "open",
    "CRLF": "windows",
}


@pytest.fixture
def checkout(tmp_path) -> Path:
    """A folder laid out like the checkout: scripts/common.sh, .node-version and the .env."""
    (tmp_path / "scripts").mkdir()
    shutil.copy(COMMON, tmp_path / "scripts/common.sh")
    (tmp_path / ".node-version").write_text("24\n")
    (tmp_path / ".env").write_bytes(ENV.encode())
    return tmp_path


def from_the_scripts(checkout: Path, name: str) -> str | None:
    done = subprocess.run(
        ["bash", "-c", 'source "$1" && env_file_value "$2"', "_", checkout / "scripts/common.sh", name],
        capture_output=True,
        text=True,
        check=True,
        env={"PATH": "/usr/bin:/bin"},
    )
    return done.stdout or None


@pytest.mark.parametrize("name", EXPECTED)
def test_the_scripts_and_writekit_read_env_the_same(checkout, name):
    assert from_the_scripts(checkout, name) == env_value(name, checkout / ".env") == EXPECTED[name]


def test_a_port_set_in_env_with_a_comment_after_it_is_used(checkout):
    (checkout / ".env").write_text("export API_PORT=9100  # moved off 8100\n")
    done = subprocess.run(
        ["bash", "-c", 'source "$1" && printf %s "$API_PORT"', "_", checkout / "scripts/common.sh"],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin"},
    )
    assert done.stdout == "9100"
