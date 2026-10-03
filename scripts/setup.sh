#!/usr/bin/env bash
# One-shot setup for the GoW2 enemy-swap toolkit on a fresh machine (macOS / Linux / WSL).
#   git clone <this repo> && cd <repo> && scripts/setup.sh [/path/to/GoW2.iso]
# What it does: checks git, Go >= 1.18, Python >= 3.10, curl; clones mogaika/god_of_war_browser
# at the tested commit; builds it to bin/; creates cache/ out/ backups/; links or checks the ISO.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
BROWSER_REPO=https://github.com/mogaika/god_of_war_browser.git
BROWSER_COMMIT=1bfc55c0172e67c48c8e941c495333f583c721a0   # tested 2026-10-03
ISO_ARG=${1:-}

say(){ printf '\033[1;32m==>\033[0m %s\n' "$*"; }
die(){ printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }
need(){ command -v "$1" >/dev/null 2>&1 || die "$1 is required: $2"; }

need git  "https://git-scm.com"
need curl "install curl"
need go   "install Go 1.18+ from https://go.dev/dl (brew install go / apt install golang-go)"
need python3 "install Python 3.10+"
GOV=$(go version | sed -E 's/.*go([0-9]+)\.([0-9]+).*/\1 \2/')
set -- $GOV; [ "$1" -gt 1 ] || [ "$2" -ge 18 ] || die "Go >= 1.18 required, found $(go version)"
PYV=$(python3 -c 'import sys;print(sys.version_info[0]*100+sys.version_info[1])')
[ "$PYV" -ge 310 ] || die "Python >= 3.10 required, found $(python3 --version)"
say "toolchain ok: $(go version | cut -d' ' -f3), $(python3 --version)"

if [ ! -d god_of_war_browser/.git ]; then
  say "cloning god_of_war_browser"
  git clone --quiet "$BROWSER_REPO" god_of_war_browser
fi
say "pinning god_of_war_browser to $BROWSER_COMMIT"
git -C god_of_war_browser fetch --quiet origin
git -C god_of_war_browser checkout --quiet "$BROWSER_COMMIT"

say "building god_of_war_browser (first build downloads Go modules)"
mkdir -p bin
( cd god_of_war_browser && go build -o "$ROOT/bin/god_of_war_browser" . )
# the browser serves its web/ assets and hash tables relative to its working directory
say "built bin/god_of_war_browser"

mkdir -p cache/wads out backups
if [ -n "$ISO_ARG" ] && [ ! -e GoW2.iso ]; then ln -s "$ISO_ARG" GoW2.iso; fi
if [ -e GoW2.iso ]; then
  say "ISO present: $(ls -l GoW2.iso | awk '{print $5}') bytes"
else
  printf '\033[1;33mnote:\033[0m put your God of War II ISO at %s/GoW2.iso (or pass its path to this script)\n' "$ROOT"
fi

say "python self-test of the WAD tool"
python3 scripts/gow2_enemy_swap.py --help >/dev/null
cat <<MSG

Setup complete. Next:
  scripts/start_swap_ui.sh        # browser on http://localhost:8000 + UI on http://localhost:8787
  scripts/stop_swap_ui.sh         # stop both (the emulator cannot open the ISO while the browser holds it)
Read docs/GOW2_ENEMY_SWAP_MANUAL.md. No game data is ever committed to this repo.
MSG
