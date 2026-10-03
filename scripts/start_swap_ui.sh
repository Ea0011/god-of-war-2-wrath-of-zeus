#!/bin/bash
# Starts god_of_war_browser on :8000 (ISO) and the swap UI on :8787. Close PCSX2 first.
cd "$(dirname "$0")/.."
(cd god_of_war_browser && go run . -iso ../GoW2.iso -ps ps2 -gowversion 2 >> ../server.log 2>&1 &)
for i in $(seq 1 60); do curl -s -m 2 http://localhost:8000/json/pack >/dev/null && break; sleep 1; done
python3 scripts/gow2_swap_ui.py "$@"
