---
name: gow2-enemy-swap
description: God of War II (PS2) enemy swapping manual - level WAD / DC_WAD / RSRCS / ESC format, the swap tool, the per-encounter web UI (with god_of_war_browser), ISO injection and manual hex edits. Use for any GoW2 WAD, enemy swap, pool, spawner or ISO-patching question in this repo.
---

# GoW2 enemy swap

Read `manual.md` next to this file for the full manual (format, tool, UI, hex edits, file map).
Quick facts an agent needs before touching anything:

- A level references a creature in **three places** that must agree: `RSRCS` tag (names ->
  `R_<NAME>.WAD`), the `DC_WAD_<level>` pool tables (`tGOPool`/`tMemoryPool`, 8-byte
  `{hash, count}` entries, hash = `h*127+c` over the UPPER-CASED name), and `ESC_*` spawner
  scripts (`CRT_<Creature>` + `BRA_<behaviour>` strings). RSRCS-only edits do nothing.
- Tooling: `scripts/gow2_enemy_swap.py` (`dump` / `swap` / `selftest`, plus `apply_plan()` for
  per-entity plans), `scripts/gow2_swap_ui.py` + `gow2_swap_ui.html` (web UI on :8787),
  `scripts/start_swap_ui.sh` (starts god_of_war_browser on :8000 and the UI).
- Browser must hold the ISO read-write: close PCSX2 and detach hdiutil mounts first; stop both
  servers before launching the game.
- Backups live in `backups/<NAME>.WAD.orig`; restore = upload the backup. Outputs in `out/`.
- Ignore `scripts/{compare_groups,extract_embedded_wad,swap_enemy_instances,wad_*}.py` and
  `skills/*.skill`: they assume tags (GOFF/GOBJ) that do not exist.
- Verified in game 2026-10-03: RHOD10 Rhodes soldiers -> Satyr10 worked first try.
- Progression (doors opening after N kills) is driven by LevelData constants in type-12 "level
  data" entities, incremented by type-3 destruction sensors; `level_gates()`/`apply_gates()` in the
  tool and the UI's Progression gates card edit them in place (manual section 7). Never bulk-assign
  scripted entities (bosses, door soldiers) and never let a replacement's pool N drop below the
  original, or sensors stop firing and gates never open.
