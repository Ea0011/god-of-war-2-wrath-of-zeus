#!/usr/bin/env bash
# Starts god_of_war_browser on :8000 (serving GoW2.iso) and the swap UI on :8787. Close the emulator first.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -e GoW2.iso ] || { echo "GoW2.iso not found in $(pwd); run scripts/setup.sh /path/to/GoW2.iso" >&2; exit 1; }
if ! curl -s -m 2 http://localhost:8000/json/pack >/dev/null 2>&1; then
  if [ -x bin/god_of_war_browser ]; then
    ( cd god_of_war_browser && ../bin/god_of_war_browser -iso ../GoW2.iso -ps ps2 -gowversion 2 >> ../server.log 2>&1 & )
  else
    ( cd god_of_war_browser && go run . -iso ../GoW2.iso -ps ps2 -gowversion 2 >> ../server.log 2>&1 & )
  fi
  for i in $(seq 1 90); do curl -s -m 2 http://localhost:8000/json/pack >/dev/null 2>&1 && break; sleep 1; done
fi
grep -q "trying ro mode" <(tail -n 50 server.log 2>/dev/null) && echo "WARNING: browser opened the ISO read-only (something else has it open); uploads will fail" >&2
exec python3 scripts/gow2_swap_ui.py "$@"
