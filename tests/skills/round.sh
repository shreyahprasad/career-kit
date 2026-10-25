#!/bin/bash
# One full round: every scripted run, its checks, the judges, then a summary.
#   bash tests/skills/round.sh [out] [checkout]
# out defaults to tests/skills/results/<UTC time>. The runs share the scratch ports, so they go
# one after another; the judges run together at the end. Makes real Claude calls on your plan.
set -u
here=$(cd "$(dirname "$0")" && pwd)
out=${1:-$here/results/$(date -u +%Y%m%d-%H%M%S)}
checkout=${2:-$(cd "$here/../.." && pwd)}
mkdir -p "$out"
py() { uv run --quiet --no-project --python 3.14 python "$here/$1" "${@:2}"; }

for run in draft letter company style; do
  py run.py "$run" "$out" "$checkout" > "$out/$run.log" 2>&1
  py check.py "$run" "$out" > "$out/$run.check.txt" 2>&1
done
for run in draft letter company; do
  py judge.py "$run" "$out" > /dev/null 2>&1 &
done
wait

for run in draft letter company style; do
  echo "$run: $(grep -c ^PASS "$out/$run.check.txt") of $(grep -c -E '^(PASS|FAIL)' "$out/$run.check.txt") checks pass"
  grep -v ^PASS "$out/$run.check.txt"
  [ -f "$out/$run/judge.md" ] && grep -h Overall "$out/$run/judge.md"
done
echo "results: $out"
