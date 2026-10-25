# What setup.sh, start.sh and stop.sh share. Sourced, never run on its own.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA="$ROOT/data"
RUN="$DATA/run" # each server's pid and log

say() { printf '%s\n' "$*"; }
fail() { printf 'Stopped: %s\n' "$*" >&2; exit 1; }

# The first value of name in .env that is not blank, read exactly as writekit/env.py reads it (a
# test runs both on the same file): `name=value` or `export name=value`, spaces around the name
# and value dropped; a value in quotes is what is inside them; otherwise a # ends it.
env_file_value() { # name
  local line key value
  [ -f "$ROOT/.env" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line#"${line%%[![:space:]]*}"}"
    case "$line" in export[[:space:]]*) line="${line#export}" && line="${line#"${line%%[![:space:]]*}"}" ;; esac
    case "$line" in *=*) ;; *) continue ;; esac
    key="${line%%=*}"
    key="${key%"${key##*[![:space:]]}"}"
    [ "$key" = "$1" ] || continue
    value="${line#*=}"
    value="${value#"${value%%[![:space:]]*}"}"
    case "$value" in
      \"*) value="${value#\"}" && value="${value%%\"*}" ;;
      \'*) value="${value#\'}" && value="${value%%\'*}" ;;
      *) value="${value%%#*}" && value="${value%"${value##*[![:space:]]}"}" ;;
    esac
    if [ -n "$value" ]; then
      printf '%s' "$value"
      return 0
    fi
  done <"$ROOT/.env"
}

# A port, on 127.0.0.1: the shell's value for name, else the one in .env (where a moved port is
# kept, so every later start and Claude session finds it), else the default.
port() { # name, default
  local value="${!1:-}"
  [ -n "$value" ] || value="$(env_file_value "$1")"
  value="${value:-$2}"
  case "$value" in '' | *[!0-9]*) fail "$1 must be a port number, not \"$value\". Fix it in .env." ;; esac
  printf '%s' "$value"
}
API_PORT="$(port API_PORT 8100)"
CAREER_PORT="$(port CAREER_PORT 8140)"
NETWORKING_PORT="$(port NETWORKING_PORT 8120)"
WEB_PORT="$(port WEB_PORT 5180)"

# The Python servers: name, folder, app, port. Writers first: they migrate their database on start.
SERVERS="career:tools/career:writer:app:$CAREER_PORT networking:tools/networking:writer:app:$NETWORKING_PORT api:api:main:app:$API_PORT"

NODE_MAJOR="$(cat "$ROOT/.node-version")"

# Puts Node $NODE_MAJOR first on PATH, through fnm when the node already there is another version.
use_node() {
  if [ "$(node -v 2>/dev/null | sed 's/^v\([0-9]*\).*/\1/')" = "$NODE_MAJOR" ]; then return; fi
  command -v fnm >/dev/null || fail "Node $NODE_MAJOR is needed. Install fnm (brew install fnm), then run ./setup.sh again."
  eval "$(fnm env --shell bash)"
  fnm use --install-if-missing "$NODE_MAJOR" >/dev/null || fail "fnm could not switch to Node $NODE_MAJOR."
}

# A server's pid file holds its pid and when it started. After a restart the system can give that
# pid to another program, so a pid only counts as ours while it is the same process: same start.
started() { ps -o lstart= -p "$1" 2>/dev/null | sed 's/[[:space:]]*$//'; } # pid (ps pads it)
remember() { printf '%s %s\n' "$2" "$(started "$2")" >"$1"; } # pid file, pid
pid_in() { local pid _; read -r pid _ <"$1" && printf '%s' "$pid"; } # pid file

# Whether the server in a pid file is still running: that pid, started when the file says.
running() {
  [ -f "$1" ] || return 1
  local pid when
  read -r pid when <"$1" || return 1
  [ -n "$when" ] && [ "$(started "$pid")" = "$when" ]
}
