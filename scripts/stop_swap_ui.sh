#!/usr/bin/env bash
# Stops the swap UI and god_of_war_browser so the emulator can open the ISO.
pkill -f gow2_swap_ui.py 2>/dev/null || true
pkill -f "god_of_war_browser -iso" 2>/dev/null || true
pkill -f "go run . -iso" 2>/dev/null || true
sleep 1
if command -v lsof >/dev/null && lsof "$(dirname "$0")/../GoW2.iso" >/dev/null 2>&1; then
  echo "something still holds GoW2.iso:"; lsof "$(dirname "$0")/../GoW2.iso"
else
  echo "servers stopped, ISO free"
fi
