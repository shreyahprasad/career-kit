#!/bin/bash
# Stops what start.sh started, and says what it stopped.
set -euo pipefail
source "$(dirname "$0")/scripts/common.sh"

stopped=0
for pid_file in "$RUN"/*.pid; do
  [ -f "$pid_file" ] || continue
  name="$(basename "$pid_file" .pid)"
  if running "$pid_file"; then
    pid="$(pid_in "$pid_file")"
    kill "$pid"
    for _ in $(seq 1 20); do kill -0 "$pid" 2>/dev/null || break; sleep 0.25; done
    kill -0 "$pid" 2>/dev/null && kill -9 "$pid"
    say "  stopped $name"
    stopped=$((stopped + 1))
  fi
  rm -f "$pid_file"
done
[ "$stopped" -gt 0 ] && say "Stopped." || say "Nothing was running."
