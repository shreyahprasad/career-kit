#!/bin/bash
# Starts the writers, the read API and the page in the background, each on 127.0.0.1, with its
# pid and log in data/run/. Safe to run again: a server already running is left alone.
set -euo pipefail
source "$(dirname "$0")/scripts/common.sh"
cd "$ROOT"
[ -f "$DATA/career.db" ] && [ -f "$DATA/networking.db" ] || fail "no databases in data/ yet. Run ./setup.sh first."
mkdir -p "$RUN"

# Whether anything is on the port: any HTTP answer counts, since writers have no GET routes, and so
# does a program that takes the call and says nothing for 2 seconds. Only a refused call (curl's 7)
# means the port is free.
answers() {
  local code=0
  curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$1/" || code=$?
  [ "$code" -ne 7 ]
}

# A log over this size is moved to <name>.log.1 when its server starts, so data/run keeps at most
# one old copy of each and never grows without end.
MAX_LOG_BYTES=$((5 * 1024 * 1024))

rotate_log() { # log file
  if [ -f "$1" ] && [ "$(wc -c <"$1")" -gt "$MAX_LOG_BYTES" ]; then mv -f "$1" "$1.1"; fi
}

start() { # name, port, command...
  local name="$1" port="$2"
  shift 2
  if running "$RUN/$name.pid"; then
    say "  $name already running (:$port)"
    return
  fi
  answers "$port" && fail "something else is using :$port. Stop it, or move career-kit off it: set $(echo "$name" | tr a-z A-Z)_PORT=$((port + 1000)) in .env, then ./start.sh again"
  rotate_log "$RUN/$name.log"
  nohup "$@" >>"$RUN/$name.log" 2>&1 &
  local pid=$!
  remember "$RUN/$name.pid" "$pid"
  for _ in $(seq 1 40); do
    kill -0 "$pid" 2>/dev/null || fail "$name stopped while starting. See data/run/$name.log"
    if answers "$port"; then
      say "  $name on :$port"
      return
    fi
    sleep 0.25
  done
  fail "$name did not answer on :$port. See data/run/$name.log"
}

say "Starting"
for server in $SERVERS; do
  IFS=: read -r name dir module app port <<<"$server"
  (cd "$dir" && start "$name" "$port" .venv/bin/python -m uvicorn "$module:$app" --host 127.0.0.1 --port "$port")
done

use_node
(cd web && CAREER_WRITER="http://127.0.0.1:$CAREER_PORT" NETWORKING_WRITER="http://127.0.0.1:$NETWORKING_PORT" \
  API_SERVER="http://127.0.0.1:$API_PORT" WEB_PORT="$WEB_PORT" start web "$WEB_PORT" node_modules/.bin/vite preview)

curl -sf --max-time 5 "http://127.0.0.1:$API_PORT/api/health" | grep -q '"app":"career-kit"' || fail "the read API on :$API_PORT is not career-kit's, or not healthy. See data/run/api.log"
say "Open http://127.0.0.1:$WEB_PORT  (./stop.sh stops everything)"
