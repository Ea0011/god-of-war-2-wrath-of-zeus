# God of War 2: Wrath of Zeus

Tools and documentation for swapping enemies between levels of **God of War II (PS2)** by
editing the level WADs inside the game ISO.

- `docs/GOW2_ENEMY_SWAP_MANUAL.md` – the manual: running the browser + UI, format reference,
  manual hex edits, troubleshooting.
- `docs/GOW2_DC_WAD_FORMAT.md` – long-form reverse-engineering notes on the `DC_WAD_*` tags.
- `scripts/gow2_enemy_swap.py` – WAD reader/writer, DC_WAD decoder, `dump` / `swap` / `selftest`
  CLI and the `apply_plan()` API used by the UI.
- `scripts/gow2_swap_ui.py` + `gow2_swap_ui.html` – local web UI for per-encounter swaps
  (http://localhost:8787), talking to god_of_war_browser for ISO access.
- `scripts/start_swap_ui.sh` – starts god_of_war_browser (:8000) and the UI.
- `.claude/skills/gow2-enemy-swap/` – Claude Code skill wrapping the same knowledge.

## Requirements

- Python 3.10+ (standard library only).
- [mogaika/god_of_war_browser](https://github.com/mogaika/god_of_war_browser) cloned next to
  the scripts as `god_of_war_browser/` (used unmodified, tested at commit `1bfc55c`), Go toolchain.
- Your own GoW2 ISO as `GoW2.iso` in the repo root. No game data is tracked here.

## Quick start

```bash
scripts/start_swap_ui.sh          # close the emulator first
# open http://localhost:8787, Scan, Load a level, pick replacements, Apply & upload
pkill -f gow2_swap_ui.py; pkill -f "go run . -iso"   # free the ISO before playing
```

The first confirmed swap: RHOD10 (the opening level) with Rhodes soldiers replaced by satyrs,
working in game on the first attempt.
