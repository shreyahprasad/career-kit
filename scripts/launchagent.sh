#!/bin/bash
# Optional: starts career-kit when you log in to this Mac, so a restart does not leave it down.
#
#   scripts/launchagent.sh install    run ./start.sh at every login, and once now
#   scripts/launchagent.sh remove     stop doing that (the servers keep running until ./stop.sh)
#
# It writes a LaunchAgent for your user only (~/Library/LaunchAgents/<label>.plist) that runs
# start.sh once at login; start.sh leaves alone anything already running. setup.sh never installs
# it. It refuses while another app hosts career-kit on these ports, since that app starts the
# servers itself and the two would fight over them.
set -euo pipefail
source "$(dirname "$0")/common.sh"

LABEL="${CAREER_KIT_LABEL:-com.career-kit.start}"
AGENTS="${CAREER_KIT_LAUNCH_AGENTS:-$HOME/Library/LaunchAgents}"
PLIST="$AGENTS/$LABEL.plist"
DOMAIN="gui/$(id -u)"

xml() { printf '%s' "$1" | sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g'; }

case "${1:-}" in
  install)
    health="$(curl -s --max-time 2 "http://127.0.0.1:$API_PORT/api/health" || true)"
    case "$health" in
      *'"serves"'*'"career-kit"'*)
        case "$health" in *'"app":"career-kit"'*) ;; *) fail "another app hosts career-kit on :$API_PORT and starts it for you, so there is nothing to install." ;; esac ;;
    esac
    mkdir -p "$AGENTS" "$RUN"
    # launchd starts programs with a bare PATH; this one finds uv, node or fnm as your shell does now.
    cat >"$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$(xml "$LABEL")</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$(xml "$ROOT/start.sh")</string></array>
  <key>WorkingDirectory</key><string>$(xml "$ROOT")</string>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>$(xml "$PATH")</string></dict>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$(xml "$RUN/launchagent.log")</string>
  <key>StandardErrorPath</key><string>$(xml "$RUN/launchagent.log")</string>
</dict>
</plist>
PLIST
    chmod 600 "$PLIST"
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    launchctl bootstrap "$DOMAIN" "$PLIST"
    say "Installed: career-kit starts at every login ($PLIST). scripts/launchagent.sh remove undoes it."
    ;;
  remove)
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"
    say "Removed: career-kit no longer starts at login. What is running keeps running; ./stop.sh stops it."
    ;;
  *)
    fail "say install or remove: scripts/launchagent.sh install"
    ;;
esac
