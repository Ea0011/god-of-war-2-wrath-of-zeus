# GoW2 (PS2) Enemy Swap Manual

Repo: `/Users/eavagyan/wadder`. Verified on the NTSC GoW2 ISO (`GoW2.iso`, 8.5 GB, dual layer,
files in `PART1.PAK`/`PART2.PAK` indexed by `GODOFWAR.TOC`).

## 1. File map

| path | what |
|------|------|
| `GoW2.iso` | the game. Only god_of_war_browser writes to it. |
| `god_of_war_browser/` | mogaika's browser (Go). Serves the ISO on :8000, can replace pack files. |
| `scripts/gow2_enemy_swap.py` | WAD reader/writer, DC_WAD decoder, swap tool, `apply_plan()` API. |
| `scripts/gow2_swap_ui.py`, `scripts/gow2_swap_ui.html` | per-encounter swap web UI on :8787. |
| `scripts/start_swap_ui.sh` | starts browser + UI. |
| `docs/GOW2_DC_WAD_FORMAT.md` | long-form format notes. |
| `sample_levels/*.WAD`, `cache/wads/*.WAD` | level WADs pulled from the ISO. |
| `cache/index.json` | scan result: creature -> `R_*.WAD`, spawn behaviours, donor pool blocks per level. |
| `backups/<NAME>.WAD.orig` | originals saved before the first upload of that level. |
| `out/*.WAD` | generated levels (`<LEVEL>.mod.WAD` from the UI, named files from the CLI). |
| `server.log`, `ui.log` | browser and UI logs. |

## 2. Running the browser and the UI

```bash
# 0. close PCSX2; make sure nothing has the ISO open
lsof GoW2.iso; hdiutil info | grep -A3 GoW2.iso   # detach with: hdiutil detach /dev/diskN
# 1. everything at once (browser :8000 + UI :8787)
scripts/start_swap_ui.sh
# or by hand
(cd god_of_war_browser && go run . -iso ../GoW2.iso -ps ps2 -gowversion 2 >> ../server.log 2>&1 &)
python3 scripts/gow2_swap_ui.py --browser http://localhost:8000 --port 8787
# 2. open http://localhost:8787
# 3. when done, stop both so the emulator can open the ISO
pkill -f gow2_swap_ui.py; pkill -f "go run . -iso"; lsof GoW2.iso || echo free
```

If `server.log` says `Failed to open iso in rw mode, trying ro mode`, something else has the ISO
open; uploads will fail until it is closed and the browser restarted.

Useful browser endpoints (all used by the UI):

| endpoint | purpose |
|----------|---------|
| `GET /json/pack` | list of files in the TOC |
| `GET /json/pack/<FILE>` | tag list of a WAD (Id, Tag, Size, Name) |
| `GET /dump/pack/<FILE>` | the whole file |
| `GET /dump/pack/<FILE>/<tagId>` | one tag payload |
| `POST /upload/pack/<FILE>` (form field `data`) | replace a file: written into free pak space, TOC updated |

### UI workflow

1. **Scan creatures & donor levels** (once; ~1 min; cached in `cache/index.json`). Reads every
   `R_*.WAD` top-level template list (creature name from `CRT_*`, behaviours from `BRA_*`) and
   every level's RSRCS + pool blocks (donors).
2. **Load** a level. The page shows RSRCS creatures with their N (pool size), and the encounters:
   every spawner entity grouped by `ESC_*` script with its creature and behaviours.
3. Pick a replacement per entity, or per whole script. Creatures without a donor block are
   disabled. Behaviours missing in the new creature are highlighted and mapped to the fallback
   (`BRA_Spawn`). Change N in the creature pills to rescale pools.
4. **Preview** (dry run), **Write .mod.WAD only** (to `out/`), or **Apply & upload into ISO**
   (backs up the original on first use, uploads, re-downloads and compares SHA-256).
5. **Restore original from backup** uploads `backups/<LEVEL>.orig`.

Creatures that still have at least one spawner stay in RSRCS; unreferenced ones are removed
unless the checkbox is cleared.

### CLI

```bash
python3 scripts/gow2_enemy_swap.py dump LEVEL.WAD [--names OTHER.WAD ...]
python3 scripts/gow2_enemy_swap.py swap LEVEL.WAD --old Rhsold00 --new Satyr10 --donor ATLAS220.WAD \
        [--count N] [--rename BRA_SpawnJump=BRA_Spawn ...] -o out/LEVEL_x.WAD
python3 scripts/gow2_enemy_swap.py selftest LEVEL.WAD ...        # byte-identical round trips
curl -F data=@out/LEVEL_x.WAD http://localhost:8000/upload/pack/LEVEL.WAD
```
`swap` replaces one creature everywhere; use the UI (or `apply_plan()`) for partial swaps.

## 3. Format reference

### 3.1 WAD container
Records of `u16 tagType, u16 flags, u32 size, char name[24]` (32 bytes) + payload padded to 16.
Tag types: `0x00 EntityCount` (no payload, `size` = number of ESC entities), `0x01` server
instance (models, textures, scripts...), `0x02/0x03` group start/end, `0x12 RSRCS`,
`0x0b..0x10 DC_WAD_<level>`, `0x15/0x13/0x16` WAD header/pop/footer.

### 3.2 RSRCS (tag 0x12)
Payload = N x 24-byte zero-padded creature names, e.g. `Colsus00`, `Rhsold00`, `Orders10`.
The engine streams `R_<NAME upper-cased>.WAD` for each.

### 3.3 DC_WAD tags (the "tweak" container)
| tag | content |
|-----|---------|
| 0x0b | 4 bytes `32 CB 08 4A` (format id) |
| 0x0c | data blob: typed objects back to back |
| 0x0d | `u32 n; {u32 blobOff, u32 strOff} x n; strings` top-level named objects (`WAD_<level>`, `IO_*`, `BRK_*`, in enemy WADs `CRT_*`, `BRA_*`, `ORBE_*`) |
| 0x0e | same pairs: field offset -> external template name to import (`CSH_*`, `FFB_*`, `ORBE_*`); `00000000` when empty |
| 0x0f | `u32 n; {u32 hash, u32 strOff} x n; strings`, sorted by hash. Debug only (RHOD10 ships a broken one). |
| 0x10 | `u32 n; {u32 blobOff, u32 strOff, u32 typeId} x n; strings` every field with its type |

Hash: `h = 0; for c in NAME.upper(): h = (h*127 + c) mod 2^32`.
Examples: `goSatyr10 -> 0x5cb60656`, `goRhsold00 -> 0x5b8941f2`, `goOrders02 -> 0x28b4020f`.

`WAD_<level>` object (typeId 0xe5), little endian:
```
u32 a = nGO ? 0x8000|nGO : 0
u32 b = (nGO<<15) | 0x4000 | nMem
nGO  x tGOPool     {u32 hash(goXxx),  u32 count}   typeId 0xe3
nMem x tMemoryPool {u32 hash(system), u32 count}   typeId 0xe4
```
`tGOPool_N` / `tMemoryPool_N` numbers in tag 0x10 are one running index in generation order,
which exposes each creature's block: `[go<Creature>, its stone/frozen variants, spawn hole,
death parts, FX...] [odbEffect, hfsmEnemy1, goSoldier, tAnimSystem, tMoveSystem, tFightSystem,
tStandardEffectSystem, hfsmBreakable, tHandleSystem, goIO, hfsmIO_Misc, tMove, fxBoneData]`.
All counts are multiples of N except `fxBoneData` = 1. The creature's own `R_*.WAD` does not
list this block; copy it from a donor level (the index knows donors for 98 creatures).

### 3.3.1 Creature blocks can be nested

The generator emits a creature as one or more `[GO run][MEM run]` pairs and closes it with the
systems run that contains `fxBoneData x1` (trailing creature-scaled entries such as Siren's
`ConcussionInstanceData` or Cerpup's `GrowCharInstanceData` may follow in the same run).
Medusa is the visible case: `goMedusa00 ... goEyePower | odbEffect, hfsmHeroBreak |
goStoneHero, goFreezeHero | hfsmBreakable ... MedusaEyeAttackData x3, hfsmEnemy1 ... fxBoneData`.
`enemy_block()` follows this rule; before 2026-10-03 evening it stopped at the first boundary,
which is why a ported Medusa had no beam (`MedusaEyeAttackData`) and no petrified-Kratos objects.
Validation: all 277 creature blocks in the 122 levels end with a run containing `fxBoneData`.

### 3.4 ESC spawner scripts (`SCR_Entities`)
Tag payload: 0x24-byte header (`04 00 01 00 "SCR_Entities"`), then entities:
```
0x00 float matrix[16]   0x44 u16 entitySize   0x46 type   0x48 uid   0x4a physObj
0x4e u16 handlersCount  0x50 u16 targetCount  0x52 u16 streamSize
0x54 {u16 id, u16 start} x handlers; u16 targets[]; u16 0; opcodes...; strings...; entityName; pad to 4
```
Opcode `0x0e <u16 off>` pushes the string at `off` relative to the first opcode byte.
Operand sizes: `0x00/0x01` 4, `0x02..0x10` 2, `0x11..0x39` none, `>=0x3a` exit.
Spawners push `"BRA_<behaviour>"` then `"CRT_<Creature>"`. `BRA_*` must exist in the creature's
WAD (tag 0x0d). Every creature has `BRA_Spawn`, `BRA_StonePose`, `BRA_DeathAir*`; extra ones
(`BRA_SpawnJump`, `BRA_SpawnCeiling`, `BRA_Door*`, `BRA_ColossusToss`...) are creature specific.

## 4. Manual hex edits

Only sensible when sizes do not change: same-or-shorter creature name and the same number of
pool entries. Otherwise every offset table after the change must be recomputed (use the tool).
Worked example on the original `backups/RHOD10.WAD.orig` (6,174,720 bytes), Rhsold00 -> Satyr10:

| what | file offset | edit |
|------|-------------|------|
| `RSRCS` payload (tag 6814) | `0x5CA860`, 72 bytes = 3 names | bytes `0x5CA878..0x5CA88F` hold `Rhsold00`; write `Satyr10` + 17 zero bytes |
| DC 0x0c payload (tag 6824) | `0x5E0560`, 4236 bytes | |
| `WAD_rhod10` object | `0x5E0F70` | header `27 80 00 00 2E C0 13 00` = nGO 39, nMem 46 (only touch if entry count changes) |
| Rhsold00 GO block | `0x5E1060..0x5E1098` (7 entries) | first entry `F2 41 89 5B 10 00 00 00` = goRhsold00 x16 -> `56 06 B6 5C 10 00 00 00` = goSatyr10 x16; replace the other 6 hashes with the satyr objects (goStoneSatyr10 `A1 82 A0 AB` x32, goFreezeSatyr10 `5F A4 30 37` x16, goSpawnHole `33 4A 25 5B`, goDeathParts `B4 4E 95 71`, goSatEyeGlow `60 5E B6 7D`, goSATdecapT `E1 07 DD D6` ...). Satyr has 9 GO entries vs 7, so a true in-place edit must drop two (decapV, goGenericBlockS) or you need the tool. |
| Rhsold00 MEM block | `0x5E1128..0x5E1198` (14 entries) | satyr needs 13 of the same systems (no ConcussionInstanceData); counts 16/32/48 stay. |
| 0x0f names | `0x5E18F0` | optional, debug only |
| spawner string | tag 654 `ESC_gotroomaistarters50`, payload `0xB6DE0`; `CRT_Rhsold00` at `0xB6E94` | overwrite with `CRT_Satyr10\0` (12 bytes incl. terminator; 1 byte shorter is fine). The `0x0e` operand at payload+0xB0 keeps pointing at the same offset. Repeat for every spawner (see `dump` output: 40 entities in 12 scripts). |

Rules of thumb for hand edits:
- Never change a tag's `size` unless you also move everything after it and keep 16-byte padding.
- Pool entry = 8 bytes; hashes are little endian; count is the max simultaneous instances.
- If a spawner's `BRA_*` does not exist in the new creature, overwrite it with `BRA_Spawn` (pad with zeros).
- After editing, run `python3 scripts/gow2_enemy_swap.py dump FILE` to confirm RSRCS, blocks and spawners agree.

## 5. Known data points

- Donors: Satyr10 in ATLAS220 (N=2), ISLE45; Orders02 in ATLAS230 (N=5), ATLAS235 (N=6);
  Harpy20/Captan10 in ATLAS230; Rhsold00 (N=16) + Colsus00 in RHOD10. Full list: `cache/index.json`.
- RHOD10 lists Orders10 in RSRCS and spawns `CRT_Orders10` twice without a goOrders10 pool.
- Enemy WAD sizes (payload): R_RHSOLD00 557 KB, R_SATYR10 809 KB, R_ORDERS10 862 KB, R_COLSUS00 3.0 MB.
- In-game result: RHOD10 Rhsold00 -> Satyr10 (N=16, soldier behaviours -> BRA_Spawn) worked first try.

## 6. Troubleshooting
- `no donor pool block known`: scan again or pull a level that uses the creature.
- Upload 500 / `Cannot find file`: wrong file name (case matters, e.g. `RHOD10.WAD`).
- Readback mismatch: the ISO was read-only; close the emulator, restart the browser.
- Game hangs on load after a swap: lower N (`--count`), or choose a smaller creature.

## 7. Progression gates (kill counts needed to progress)

Levels gate progress with **LevelData** variables, not with creature types:

- **Level-data entities** (entity type 12, e.g. `WayLevelData1/2/3`, `Rhod10CamsLEVELDATA`) have one
  handler per variable: `push_int N ; set_scope_int LevelData[v]`. That constant is the initial
  value: counters start at 0, thresholds at the required count.
- **Destruction sensors** (entity type 3, `*-DesMess1..4`) next to each spawner run
  `LevelData[c] = LevelData[c] + 1` when the spawned creature dies, for the wave that is active,
  and also bump the level total.
- **Event entities** (type 7, `FirstRoomMessages-EvtMess1..4`) compare counter vs threshold
  (`>=`, or `==` for the total) and set a flag (bool LevelData) that unlocks the next wave's
  sensors and the door's `*-DesOpen` targets.

So "N enemies must die" is one 4-byte constant. The tool extracts all of them:

```bash
python3 - <<'PY'
import sys; sys.path.insert(0,'scripts'); from gow2_enemy_swap import *
tags=read_wad('backups/RHOD10.WAD.orig')
for g in level_gates(tags):
    if g['role'] in ('threshold','counter'): print(hex(g['var']), g['role'], g['init'], g['entity'], g['compared_with'], g['incremented_by'][:3])
apply_gates(tags, {0xe:1, 0x10:2, 0x12:2, 0x14:6})      # patch in place, sizes unchanged
open('out/RHOD10_easy.WAD','wb').write(write_wad(tags))
PY
```
In the UI the same appears as the **Progression gates** card (thresholds editable, counters shown
with the sensors that increment them); values go into the plan as `gates: {var: value}`.

RHOD10 first room, original values and file offsets (in `backups/RHOD10.WAD.orig`):

| LevelData | init | set in | file offset | bytes |
|-----------|------|--------|-------------|-------|
| 0xd / 0xe | 0 / **3** | wave 1 counter / required (EvtMess1) | threshold at `0xB629F` | `03 00 00 00` |
| 0xf / 0x10 | 0 / **5** | wave 2 (EvtMess2) | `0xB62B3` | `05 00 00 00` |
| 0x11 / 0x12 | 0 / **5** | wave 3 (EvtMess3) | `0xB62C7` | `05 00 00 00` |
| 0x1c / 0x15 | 0 / **1** | wave 4 (EvtMess4, VisAIStop) | `0xB66D5` | `01 00 00 00` |
| 0xb / 0x14 | 0 / **21** | total kills, checked with `==` by DoorSpawn-SendDoorEvent, DoorSparkle, FirstDoor-VisOff, MagicGuys | `0xB66CB` | `15 00 00 00` |

Hex edit: overwrite the 4 little-endian bytes after the `01` (push_int) opcode. Nothing else
moves. Keep the total (`0x14`) consistent with the waves: it is an equality check, so set it to the
number of kills that will actually happen (wave thresholds plus whatever keeps spawning until the
flags flip). Lowering wave thresholds without lowering the total leaves the door shut; raising
pool N without raising the total can overshoot it.

Why a spawner that never spawns breaks a door: its `DesMess` sensors never fire, the counters
never reach the thresholds. That is what happened when Orders10 got pool N=9 in a room that
needs 16 slots, and when the Colossus spawner was reassigned (its scripted events never ran).

### 7.1 Spawn counts and the total gate

Each spawner entity (type 9) stores its own numbers as one-constant handlers: **h0 = how many
enemies it spawns in total, h1 = how many alive at once** (starters have neither: 1 each). The
room total is the sum of h0 over the spawners whose death sensors feed the counter:
RHOD10 first room = 3 starters + 3+3+2+2+2+2+2+2 = **21**, which is exactly `LevelData[0x14]`.
Every door entity checks `0xb == 0x14 && !doorOpened` and the `DesOpen` sensors additionally need
all wave flags, so:

- **total gate must equal the sum of spawn counts** (it is `==`; overshoot or undershoot locks the door);
- **sum of wave thresholds must be <= total**, otherwise the wave flags never flip.

Setting 0x14 = 3 with thresholds 3/5/5/1 left (18:06 upload) is why the door stayed shut: the
equality was true only at kill 3, before the waves were done.

Tool: `spawner_counts()`, `apply_spawns()`, `gate_report()`; UI: the "spawns / alive" column per
spawner and the consistency line under the gates table with a one-click "set gate to N".
Hex: the spawn count is the 4 bytes after the `01` opcode of handler 0 in the spawner entity.

### 7.2 Bypassing gates

`bypass_gates(tags, [vars])` (UI: "bypass" checkbox per threshold, or "Bypass all thresholds")
overwrites the first three bytes of every condition handler that compares the variable with
`11 38 3A` (`push_bool TRUE; pop_result; exit`). The handler then always passes, so e.g. the door
chain fires on the first destruction event. Use it (a) to progress while testing creatures and
(b) as a diagnostic: if the door still does not open with everything bypassed, the death sensors
are not firing for that creature at all.


## 8. Memory budget (confirmed in game)

The PS2 build has no slack. Symptoms of running out, in order: effects and secondary attacks
silently fail to spawn (a ported Medusa fought but never fired her gaze), then a TLB miss on load.
Both were reproduced on RHOD10 and fixed purely by lowering the budget:

| build | creature WAD payload | result |
|-------|---------------------|--------|
| shipped RHOD10 (Colsus00 + Rhsold00 + Orders10) | 4351 KB | baseline |
| Rhsold00 -> Satyr10 | 4597 KB (+6%) | worked |
| soldiers kept + Orders10 kept + Medusa00 added | 5662 KB (+30%) | no beam, then TLB miss |
| Colsus00 + Medusa00 only, pools N=6 | 4276 KB (-2%) | Medusas beam |

Rules: stay at or below the shipped creature payload (the UI's Memory card shows shipped / ISO /
planned); when adding a big creature, drop one rather than keeping it for a few scripted spawners;
keep pool N at the real concurrent demand, not the old N; pools and the level WAD add on top of
the creature payload. `R_*.WAD` sizes are in `cache/index.json` (`creatures.<name>.bytes`).
