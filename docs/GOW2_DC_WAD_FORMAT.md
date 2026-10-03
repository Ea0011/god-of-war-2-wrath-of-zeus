# God of War II (PS2) – level WAD enemy references and the DC_WAD tags

Reverse-engineered from ATLAS220 / ATLAS230 / ATLAS235 (plus 10 more levels pulled
through god_of_war_browser) and the enemy WADs R_ORDERS02.WAD / R_SATYR10.WAD.
Tool: `scripts/gow2_enemy_swap.py` (`dump`, `swap`, `selftest`).

## 1. WAD container (GoW2)

Sequence of records: 32-byte header `u16 tag, u16 flags, u32 size, char name[24]`,
then `size` bytes of payload, padded to 16 bytes. Tag `0x00` (`EntityCount`) has no
payload: its `size` field is the number of ESC entities in the level. Tags `0x02`/`0x03`
open/close groups, `0x01` is a server instance (model, texture, script, ...), `0x12` is
`RSRCS`, `0x0b`..`0x10` are the six `DC_WAD_<level>` tags.

## 2. Where an enemy is referenced in a level WAD (all three must agree)

| # | Tag | Content | Example (ATLAS230) |
|---|-----|---------|--------------------|
| 1 | `RSRCS` (0x12) | 24-byte zero-padded names of enemy WADs to stream in as `R_<NAME>.WAD` | `Captan10`, `Harpy20`, `Orders02` |
| 2 | `DC_WAD_*` 0x0c (+0x0d/0x0e/0x0f/0x10) | the level tweak container: **object pools and memory pools** for every creature | `goOrders02 x5`, `goStoneOrders00 x10`, ... `hfsmEnemy1 x5` |
| 3 | `ESC_*` scripts (`SCR_Entities`) | spawner entities push the strings `CRT_<Enemy>` and `BRA_<behaviour>` | `ESC_goceilingorders`: `CRT_Orders02`, `BRA_SpawnCeiling` |

Changing only RSRCS loads the other creature's assets, but the engine has no pool for
`go<NewEnemy>` (and its helper objects/systems) and the spawners still ask for
`CRT_<OldEnemy>`, so nothing (or a crash) happens. That is the "something in the WAD
itself" that has to change.

No hashed references to the enemy exist outside the DC tags (searched every u32 of all
three WADs for the hashes of `goX`, `CRT_X`, `X`, `R_X`).

## 3. DC_WAD tags ("tweak" container, same layout in level and enemy WADs)

| tag | name in browser source | meaning |
|-----|------------------------|---------|
| 0x0b | "unk 4 bytes" | constant `32 CB 08 4A` (format id) |
| 0x0c | "tweak templates" | raw data blob: concatenated typed objects |
| 0x0d | "map string → offset" | `u32 n; {u32 blobOffset, u32 strOffset} x n; strings` – **top-level named objects** (`WAD_Atlas230`, `IO_PLATCRANK`, `BRK_*`, and in enemy WADs `CRT_Orders02`, `BRA_Spawn`, `ORBE_*`) |
| 0x0e | "import/export" | same pair layout – **imports**: blob offset of a field + name of an external template to link (`ORBE_BREAK_SMALL`, `CSH_SMALL`, ...). `u32 0` when empty |
| 0x0f | "map hash → string" | `u32 n; {u32 hash, u32 strOffset} x n; strings`, **sorted by hash** – names of every hashed value used in the blob |
| 0x10 | "field description" | `u32 n; {u32 blobOffset, u32 strOffset, u32 typeId} x n; strings` – every field/sub-object of the blob with its type id |

String tables start right after the entry arrays, no dedupe, whole tag padded to 4.

### Hash

`h = 0; for c in NAME.upper(): h = h*127 + c  (mod 2^32)`  – the engine's usual
127-polynomial hash, but computed on the **upper-cased** string
(`GOORDERS02 -> 0x28b4020f`). Verified on all 88 names of the three levels.

### Field type ids seen

| typeId | object | size |
|--------|--------|------|
| 0xe5 | `WAD_<level>` object header | 8 |
| 0xe3 | `tGOPool_N` – object pool `{u32 hash(goXxx), u32 count}` | 8 |
| 0xe4 | `tMemoryPool_N` – memory pool `{u32 hash(system/type), u32 count}` | 8 |
| 0x69 / 0x6a / 0x66 | `IO_*` interactive object, `CrankSet*`, `Handle` | 28 / 8 / 52..92 |
| 0x71 | `BRK_*` breakable | 24 |
| 0xf5/0xf4/0xeb/0xf2/0xf3 | `FSE_*` full-screen effect | 58/10/24/8/32 |
| (enemy WADs) 0x5f, 0x06, 0x62, 0x20, 0x52, 0x1c, 0xaf ... | behaviour tree nodes (`tAction*`), `MOV_*`, `PFX_*`, ... | varies |

### `WAD_<level>` object (0xe5) and the pool arrays

```
u32 a = nGO ? (0x8000 | nGO) : 0
u32 b = (nGO << 15) | 0x4000 | nMem
tGOPool     entries x nGO   {u32 hash, u32 count}
tMemoryPool entries x nMem  {u32 hash, u32 count}
```
(holds for all 13 levels checked). The `_N` suffixes are one running index in
*generation* order, which is why they reveal the blocks:

```
ATLAS220:  0 MEM odbEffect x10 | 1 GO goChest x4 | 2-4 MEM hfsmIO_CSM,goIO_CSM,tHandleSystem
           5..27 GO  Rock01 objects (N=1)        28..42 MEM Rock01 systems
           43..51 GO Satyr10 objects (N=2)       52..64 MEM Satyr10 systems
           65,66 GO goRockHead, goBogSplash
```

Per creature the generator emits **GO block** (`go<Enemy>`, its stone/frozen variants,
spawn hole, death parts, FX/decap pieces) and **MEM block** (`odbEffect`, `hfsmEnemy1`,
`goSoldier`, `tAnimSystem`, `tMoveSystem`, `tFightSystem`, `tStandardEffectSystem`,
`hfsmBreakable`, `tHandleSystem`, `goIO`, `hfsmIO_Misc`, `tMove`, `fxBoneData`,
plus `tFlyingSystem`/`ConcussionInstanceData`/`odbArrow` for some). All counts are
multiples of N = max simultaneous instances (`fxBoneData` stays 1):

| creature | N | GO counts | MEM counts |
|----------|---|-----------|------------|
| Orders02 (ATLAS230) | 5 | 5, stone 10 | 15, 5..., breakable/handle/IO/misc/move 10 |
| Orders02 (ATLAS235) | 6 | 6, stone 12 | 18, 6..., 12 |
| Satyr10 (ATLAS220) | 2 | 2, stone 4, genericBlock 8 | 8, 2..., 4 |
| Harpy20 (ATLAS230) | 4 | 4, stone 8 | 12, concussion 8, flying 4, ... |

The enemy's own `R_*.WAD` DC data does **not** list these requirements (its blob only
references `goSpawnHole`/`goSatEyeGlow` from `PFX_*` nodes), so the reliable way to get
a creature's block is to copy it from a level that already uses it ("donor") and
rescale to the wanted N. The tool does exactly that.

## 4. ESC spawner scripts (`SCR_Entities`, header 0x24)

Entity record: `0x00 matrix[16]`, `0x44 u16 size`, `0x46 type`, `0x48 uid`,
`0x4e handlersCount`, `0x50 targetCount`, `0x52 streamSize`, `0x54 {u16 id,u16 start}
x handlers`, `u16 targets[]`, `u16 0`, opcodes, strings, entity name, pad to 4.
Opcode `0x0e <u16>` pushes a string at that offset relative to the opcode stream start;
operand sizes: `0x00/0x01` 4 bytes, `0x02..0x10` 2 bytes, `0x11..0x39` none, `>=0x3a`
exit. The spawner sequence is `push_string "BRA_Spawn"; push_string "CRT_Satyr10"; ...`.
Renaming `CRT_Satyr10 -> CRT_Orders02` means re-emitting the string area and fixing the
`0x0e` operands, `streamSize` and entity `size` (the tool does this; byte-identical
round trip on 387 entities).

The `BRA_*` behaviour must exist in the new creature's WAD top-level list (0x0d):
`R_SATYR10`: `BRA_Spawn, BRA_StonePose, BRA_DeathAir*`;
`R_ORDERS02`: `BRA_Spawn, BRA_SpawnJump, BRA_SpawnJumpWater, BRA_SpawnBogRope,
BRA_SpawnWall, BRA_SpawnCeiling, BRA_SpawnBog80, ...`. Use `--rename` to map one that
does not exist (e.g. `BRA_SpawnCeiling=BRA_Spawn` when putting satyrs into ATLAS230).

## 5. Swap procedure (what `swap` does)

1. RSRCS: replace the 24-byte name.
2. DC 0x0c: cut the old creature's GO+MEM block, insert the donor's block scaled to N,
   rewrite the `WAD_<level>` header words, shift everything after the pools.
3. DC 0x10: regenerate `tGOPool_N`/`tMemoryPool_N` entries, shift later offsets.
4. DC 0x0d / 0x0e: shift offsets that follow the pool arrays.
5. DC 0x0f: add the donor's hash→name entries, drop names no longer referenced, keep sorted.
6. ESC: rename `CRT_old -> CRT_new` (+ optional `--rename`), relocate strings.
7. Re-serialize the WAD (16-byte padded records). `EntityCount` is untouched (it is the
   number of ESC entities, not creatures).

Examples produced in `out/`:
`ATLAS220_Satyr10_to_Orders02.WAD` (donor ATLAS235, N=2) and
`ATLAS230_Orders02_to_Satyr10.WAD` (donor ATLAS220, N=5, `BRA_SpawnCeiling=BRA_Spawn`).

Untested in-game: PS2 memory budget. Orders02 is a bigger WAD (855 tags) than Satyr10
(445), and ATLAS220 also loads Rock01, so if the game runs out of heap pick a smaller
`--count` or a smaller creature.
