# GoW2 Enemy Swap

This repository contains a Python script (`gow2_enemy_swap.py`) that can swap enemy
prototypes in any exported *God of War II* (PS2) level.  It reads the level WAD, the
sub‑WAD blobs that hold the enemy definitions, the RSRCS list that tells the engine
which enemies to load, and the ESC scripts that spawn them.  It then updates all of
those structures so that one enemy (e.g. **Satyr10**) is replaced with another
(e.g. **Orders02**).

## Prerequisites

* Python 3.11+ (the script uses only the standard library)
* A copy of the level files you want to edit (e.g. `ATLAS220.WAD`, `ATLAS230.WAD`)
* (Optional) God‑of‑War Browser if you want to test the resulting level in the game.

## Quick start

1. **Dump a level** – list the enemies, pools and spawners.
   ```bash
   python scripts/gow2_enemy_swap.py dump sample_levels/ATLAS220.WAD
   ```

2. **Swap enemies** – replace `Satyr10` with `Orders02`.  The script will:
   * replace the RSRCS entry, the enemy pool block, and all ESC script strings.
   * also update the `GODT` pool block and behaviours used by the new creature.
   ```bash
   python scripts/gow2_enemy_swap.py swap \
     sample_levels/ATLAS220.WAD \
     --old Satyr10 --new Orders02 \
     --donor sample_levels/ATLAS230.WAD \
     -o sample_levels/ATLAS220_swapped.WAD
   ```

3. **Verify** – run the self‑test to confirm the file can be round‑tripped.
   ```bash
   python scripts/gow2_enemy_swap.py selftest sample_levels/ATLAS220_swapped.WAD
   ```

4. **Install the swap in the game** – copy the new WAD back into the ISO
   (you can use `god_of_war_browser` in read‑write mode, or a hex editor).

## More advanced usage

* `--count N` – override the maximum number of simultaneous instances.
* `--rename BRA_SpawnCeiling=BRA_Spawn` – map additional behaviour strings.
* `--names` – provide extra WADs that help the tool resolve hash‑table names.

See the script’s help (`python scripts/gow2_enemy_swap.py --help`) for full
options.

## Testing

The repository ships with a GitHub Actions workflow that runs the
`selftest` command on every commit.  The script is fully self‑contained; no
external dependencies are required.

## License

MIT – see the [LICENSE](LICENSE) file.
