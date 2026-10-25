"""Paths and ports the skill harness shares. Stdlib only, so it runs on any Python 3.14."""

import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FIXTURES = HERE / "fixtures"
# The made-up owner's files (Arya Stark). Copied to the scratch copy's data/ (a folder named data
# here would be gitignored).
OWNER = FIXTURES / "owner"
RUBRICS = HERE / "rubrics"

# Scratch ports, never the live 8100 to 8140. Move them with SKILLS_API_PORT and so on.
PORTS = {
    name: int(os.environ.get(f"SKILLS_{name}", default))
    for name, default in [("API_PORT", 9100), ("NETWORKING_PORT", 9120), ("CAREER_PORT", 9140), ("WEB_PORT", 6180)]
}
RUNS = ["draft", "letter", "company", "style"]
