#!/bin/bash
# Runs local_only.py with career-kit's own Python (made by setup.sh), never the system one, so
# the check is the one that was tested. Before setup.sh has run, a command with curl is refused
# and anything else is left to the settings: the check must never fail open.
HERE="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$HERE/../../tools/career/.venv/bin/python"
if [ -x "$PYTHON" ]; then exec "$PYTHON" -I "$HERE/local_only.py"; fi
case "$(cat)" in
  *curl*) echo "career-kit refused this: curl is checked by career-kit's own Python, which ./setup.sh makes. Run ./setup.sh first." >&2; exit 2 ;;
esac
