"""
Settings from the checkout's .env: TAILNET_LOGINS, who may make changes over the tailnet,
TAILNET_HOSTS, this Mac's tailnet names (identity.py), and the Anthropic API key, for a writer that
calls Claude. The key is set into the environment, where the SDK reads it; it is never logged,
never sent to a page. CAREER_KIT_ENV points elsewhere, e.g. from a worktree, which has no .env of
its own, or from an app that runs these writers from its own checkout.
"""

import os
from pathlib import Path

ENV_FILE = Path(os.environ.get("CAREER_KIT_ENV", Path(__file__).resolve().parents[3] / ".env"))


def env_value(name: str, env_file: Path | None = None) -> str | None:
    """The first value of name in the .env file that is not blank, or None. Read exactly as
    scripts/common.sh reads it (a test runs both on the same file): `name=value` or
    `export name=value`, spaces around the name and value dropped; a value in quotes is what is
    inside them; otherwise a # ends it."""
    env_file = env_file or ENV_FILE
    if not env_file.exists():
        return None
    for line in env_file.read_text().splitlines():
        line = line.lstrip()
        if line.startswith("export") and line[6:7].isspace():
            line = line[6:].lstrip()
        key, equals, value = line.partition("=")
        if not equals or key.rstrip() != name:
            continue
        value = value.lstrip()
        if value[:1] in ("'", '"'):
            value = value[1:].split(value[0], 1)[0]
        else:
            value = value.split("#", 1)[0].rstrip()
        if value:
            return value
    return None


def load_api_key(env_file: Path | None = None) -> None:
    """Sets ANTHROPIC_API_KEY from the .env file, unless it is already set."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    key = env_value("ANTHROPIC_API_KEY", env_file)
    if key:
        os.environ["ANTHROPIC_API_KEY"] = key
