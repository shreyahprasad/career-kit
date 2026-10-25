#!/bin/bash
# One-time setup, safe to run again: checks the tools, installs what the code needs, builds the
# page, and makes empty databases in data/. Never touches a database that is already there.
set -euo pipefail
source "$(dirname "$0")/scripts/common.sh"
cd "$ROOT"

missing=""
command -v uv >/dev/null || missing="$missing\n  uv:   brew install uv"
command -v fnm >/dev/null || [ "$(node -v 2>/dev/null | sed 's/^v\([0-9]*\).*/\1/')" = "$NODE_MAJOR" ] || missing="$missing\n  fnm:  brew install fnm"
command -v pnpm >/dev/null || missing="$missing\n  pnpm: brew install pnpm"
[ -z "$missing" ] || fail "$(printf "install these first, then run ./setup.sh again:$missing")"

use_node
say "Python packages"
for dir in api tools/career tools/networking; do (cd "$dir" && uv sync --frozen --quiet); done

say "The page (Node $(node -v))"
(cd web && pnpm install --frozen-lockfile --silent && pnpm --silent build >/dev/null)

if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
  say "Made .env from .env.example"
fi

mkdir -p "$RUN"
mkdir -p "$DATA/resumes" "$DATA/examples/resumes" "$DATA/examples/cover-letters" "$DATA/notes" "$DATA/drafts"
chmod 700 "$DATA" "$RUN"
empty="$(mktemp -d)"
trap 'rm -rf "$empty"' EXIT
if [ ! -f "$DATA/career.db" ]; then
  echo '{"roles": []}' > "$empty/career.json"
  (cd tools/career && .venv/bin/python seed.py "$empty/career.json")
fi
if [ ! -f "$DATA/networking.db" ]; then
  echo '{"people": []}' > "$empty/networking.json"
  (cd tools/networking && .venv/bin/python seed.py "$empty/networking.json")
fi

say "Set up. Start it with ./start.sh"
