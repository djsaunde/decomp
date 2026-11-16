# 1080 Snowboarding: courses and the world (for port authors)

How a course is described, loaded and laid out for a race. Types are in include/game/course.h (1080 repo);
names are the current repo names. Written by agent-g run 480 from the matched code and the ROM data.
"Probably" marks a reading that no code path proves yet.

## Index
- [0. State for porters](#0-state-for-porters-agent-g-run-575-final-wave)
- [1. The pieces](#1-the-pieces)
- [2. World registry and the course list](#2-world-registry-and-the-course-list)
- [3. Course descriptors (the command stream)](#3-course-descriptors-the-command-stream)
- [4. game_createMap: what a race scene is made of](#4-game_createmap-what-a-race-scene-is-made-of)
- [5. Items (rom/*_item.bin)](#5-items-romitembin)
- [6. Markers and the AI path (rom/*_mark.bin)](#6-markers-and-the-ai-path-rommarkbin)
- [7. Race gates and progress](#7-race-gates-and-progress)
- [7a. Splitting checkpoint.uso](#7a-splitting-checkpointuso-investigation-agent-g-run-494-no-config-change-made)
- [8. Props: MapProp, Mountain, BGBox, U64BGWall](#8-props-mapprop-mountain-bgbox-u64bgwall)
- [9. Open questions](#9-open-questions)

## 0. State for porters (agent-g run 575, final wave)

- **Fully typed:** include/game/course.h: `WorldRegistry` (0x118, course list + scene roots og / fg / bg / eg),
  `WorldCourse` and the descriptor command stream (COURSE_OP_* ops), `CourseMarker` (+ its CourseParm /
  CourseFParm parm group: wid / ext / flg), `MapProp`, `Mountain`, `BGBox`, the gate items; include/game/envobj.h:
  `EnvSettings` (bgBox at +0x3C since run 575: the BG box node, the screen is cleared only while it is NULL),
  `FallingSnow`, `U64BGWall`, the tree / tv1 item templates; include/game/sun.h: `Sun` / `LensFlare`.
- **Entry points:** course load = `game_init` -> `game_createMap(world, course, mode)` (bootup 0x6808, donor
  bootup_uso_o2_6808.c; section 4): EnvSettings + ItemMgr, the descriptor command loop (section 3), then
  `item_registerTemplates`, the course PolyShape + collision (`CollShape_ctorPoly`), the item file, the
  marker file (`CourseMarker_registerTemplates`). Per frame the course objects are ordinary Node children
  of the WorldRegistry roots (PORTING_GUIDE 2.2); `EnvSettings_display` sets the clip range and screen clear.
- **Still unknown:** settings +0x68 (the ENV_LT2 / EQ2 / EQ3 selector) and the SUN op's two ints; RaceGate below
  +0x64; the ItemMgr / item file binary format (game_libs); WorldRegistry 0x98..0x104 (section 9).
- **Port hazards:**
  - *Endianness:* everything is big-endian. The descriptor is a stream of 32-bit words (`(argc << 16) | op`
    then argc words) inside bootup Data, and its pointer arguments are USO-relocated addresses: a port must
    relocate them (or rebuild the table) before reading strings / file names. Item, marker and env files are
    big-endian s32 / f32; item positions are read as three ints and converted to float.
  - *Fixed point:* course meshes are s16 vertex rows (BasePolyShape, GRAPHICS 7.1) (the collision grid format is still
    open, ENGINE_CORE / SYSTEM_LAYER 7); game logic (markers, gates, AI path) is f32.
  - *Frame-rate dependence:* falling snow, the sun / lens-flare easing (Sun_display: fade between the 0.98 /
    0.7 / 0.3 / 0.1 thresholds) and item animations step once per frame; RaceTracker progress uses positions,
    not time.
  - *Asset loading:* course shapes are separate USOs (rom/mapN_data.uso, bgNtex.uso), some Yay0-compressed
    (section 7a / USO_FORMAT); a port can pre-extract them but must keep the Sym-based exports the loader
    resolves.

## 1. The pieces

| piece | where | what |
|---|---|---|
| World registry | bootup, `WorldRegistry` (0x118) | course list + the scene root nodes |
| course descriptor | bootup Data 0x67F0..0x6E30 | a command stream per course (section 3) |
| course shape | `rom/mapN_data.uso` | the course mesh / collision (a USO; its export is the PolyShape) |
| background | `rom/bgNtex.uso` | sky / wall textures for game_createBGBox |
| items | `rom/<course>_item.bin` | placed objects: start, goal, gates, trees, cameras, weather (section 5) |
| markers | `rom/<course>_mark.bin` | the AI path (section 6) |
| environment | `rom/<course>_env.bin` | EnvSettings (fog / colours; EnvSettings_load) |
| camera paths | `rom/cam_info.bin` | the course camera (docs/1080_CAMERA.md section 2a) |

## 2. World registry and the course list

`WorldRegistry_create_00001E08` (called by GameFlow_create) builds one Node named "World Registry" and
registers ten `WorldCourse` records (0x48: 64-byte name, descriptor pointer, next) in this order (course index
= list position, `WorldRegistry_getCourse_00002014(world, n)`):

| # | name | shape | bg | items / markers | env |
|---|---|---|---|---|---|
| 0 | One Make | map6 | bg7 | onemake | onemake03 |
| 1 | HalfPipe | map1 | bg4 | halfpipe | halfpipe |
| 2 | Slalom Course | map7 | bg4 | map02 | map02 / 02a / 02b |
| 3 | Stunt Course | map4 | bg1 | map04 | map04 / 04a / 04b |
| 4 | Long Course | map3 | bg2 | map03 | map03 / 03a / 03b |
| 5 | New Course | map8 | bg3 | map05 | map05 / 05a / 05b |
| 6 | Night Course | map2 | bg5 | map06 | map06 / 06 / 06a |
| 7 | Black Diamond | map9 | bg6 | map07 | map02 |
| 8 | Practice | map10 | bg8 | map01 | map02 |
| 9 | Test Grid | map5 | bg1 | (none) | (none) |

(The table is the course descriptors decoded; the order of registration is the WorldRegistry_create_00001E08 order.)

The same object also carries the scene roots that game_init creates and passes to `game_setParams_00002060`:
`ogRoot` 0x7C ("og"), `fgRoot` 0x80 ("fg"), `bgRoot` 0x84 ("bg"), `egRoot` 0x88 ("eg"), `mainGame` 0x8C
("MainGame"), two lights at 0x90 / 0x94, and the window (0x104..) and player lists.

## 3. Course descriptors (the command stream)

Each command is a header word `(argc << 16) | op` followed by `argc` argument words. Pointers are USO
relocations (strings in bootup RoData, imports of the bg USO). The ops are game_createMap's jump table:

| op | name | args | effect |
|---|---|---|---|
| 0 | SHAPE | uso path, import | load the course-shape USO (memtrack "CourseShape"); the import is its shape |
| 1 | ITEMS | file | item file, loaded into the ItemMgr after the item types are registered |
| 2 | MARKERS | file | marker file, loaded into the MarkerMgr |
| 3 | START | x, y, z (ints) | default start position (item "st0" overrides; a missing st0 is fatal "no st0") |
| 4 | GOAL | x, y, z (ints) | default goal position (item "gol" overrides; "no gol" is fatal) |
| 5 | MAP | angle, end, add | MapProp parms (default 40, 20, 1; mode settings 6 / 11 force end 5, add 2) |
| 6 | BG | uso path, 7 args | background USO and the game_createBGBox args (size 0x100 / 0xC0, five imports, 0); skipped in mode 6 |
| 7 | SUN | 2 ints | create Sun ("sun"), LensFlare ("len", rom/flare5.bin) and lights "lt0" / "lt1". The two ints (-91, -41 on most courses) are not read by createMap (probably the sun's rot / ele) |
| 8 | ENV | file, weather | env file into EnvSettings; `weather` (0x100 / 0x200 / 0x400) selects the weather items (section 5) |
| 9 / 10 / 11 | ENV_LT2 / EQ2 / EQ3 | file, weather | ENV when settings +0x68 is < 2 / == 2 / == 3 (probably the snow-condition setting: courses have a plain, an "a" and a "b" env file) |
| 12 | END | | end of stream |

Example (Slalom Course): `SHAPE(rom/map7_data.uso) BG(rom/bg4tex.uso, 256, ...) ITEMS(rom/map02_item.bin)
MARKERS(rom/map02_mark.bin) START(0, 0, -175000) GOAL(0, 0, 163114) MAP(40, 12, 2) SUN(-91, -41)
ENV_LT2(rom/map02_env.bin, 256) ENV_EQ2(rom/map02a_env.bin, 512) ENV_EQ3(rom/map02b_env.bin, 1024) END`.
The z axis is the downhill direction: every course starts at negative z and ends at positive z.

## 4. game_createMap: what a race scene is made of

`game_createMap(world, course, mode)` (bootup 0x6808, donor bootup_uso_o2_6808.c) runs from game_init after the
course is picked. In order:
1. "Geometry": EnvSettings (attached to bgRoot), the item manager "ItemMgr" (bootup Data 0x776C).
2. The command loop (section 3). Ops only record their arguments except SHAPE / BG / SUN / ENV*, which load
   at once.
3. `item_registerTemplates(itemMgr, mode, weather)`: registers every item type (section 5), then attaches the
   item manager to egRoot.
4. "Map": the course PolyShape ("MorphShape" morphpolyshape, "ParseCmds" BasePolyShape_parse, "Colours",
   "Init"), the map lighter (game_libs imports, lights 0x90 / 0x94), the `MapProp` (section 8) and the
   course collision `CollShape_ctorPoly` (bootup Bss 0x50).
5. "ItemMgr": load the item file; the MapProp's start / goal come from items "st0" / "gol".
6. "Markers": the marker manager "MarkerMgr" (Data 0x7768), `CourseMarker_registerTemplates` (game.uso),
   load the marker file; in mode 1 the marker manager is attached to fgRoot (drawn).
It returns the MapProp. RaceTracker later reads the course extent from world +0x98 (+0xC4 start z / +0xD8 goal
z; include/gdl/race.h).

## 5. Items (rom/*_item.bin)

The item file is a libgdl ItemMgr stream: per item type, the type's parms and its instances. Every instance is a
ColourItem-derived Node with a position at +0x30 (stored as three ints). Types (3-char names):
- **registered in item_registerTemplates**: `pyr` (debug pyramid shape), `tr1` `tr2` `tr3` (trees), `tv1`,
  `l01` / `lig` (lights), `gol` (goal), `st0` (start), `en1` / `en2` (ending points used by the
  end-of-race messages 1005..1007), `cam` (camera points: CamDirector picks the nearest `cam` item every 60
  frames; its kind selects the camera, docs/1080_CAMERA.md section 7);
- **from the template table** at bootup Data 0x7B6C (`CourseItemTmpl {name, create, flags}`): `hel`, `hem`,
  `bal`, `ba2`, `chk` (checkpoint gate), `gtr` / `gtl` (right / left fork gates), `cfr`, and the weather sets
  `snw` / `fog` (flags 0x100), `sn2` / `fo2` (0x200), `sn3` / `fo3` (0x400). The ENV op's weather word is
  matched against these flags, so each env variant gets its own snowfall / fog items.

## 6. Markers and the AI path (rom/*_mark.bin)

**CourseMarker** (game.uso, 0x8C): ColourItem base (position 0x30, `link` 0x2C) + "CourseMarker::Parms":
`wid` (float), `ext` (int), `flg` (int). Twelve marker types are registered, in the order of the type-name table
at game.uso Data 0x548: `mrk`, `mk1`..`mk9`, `mkl`, `mkr` (indices 0..11, `MARKER_*`).

**How the AI follows them** (game.uso SnowAI; docs/1080_PHYSICS.md section 8):
- `SnowAI.targetNode` / `altNode` are marker TYPE indices, not marker indices. `SnowAI_findNearestMarker_0000A374
  (ai, typeName, pos)` finds the type in the MarkerMgr, then `CourseMarker_findNearestZ_000043D8` returns the
  instance of that type nearest in z ahead of the rider (smallest dz >= 0), else the nearest behind.
- A marker and its `link` form one path segment. `SnowAI_scanSegments` tests the ten types in turn (one per
  frame) and keeps the type whose segment passes closest to the rider (a rider up to 250 * wid behind the
  marker still counts). A segment is a corridor: `SnowAI_isInSegmentWidth` (left / right edges, half width
  250 * wid + 50 at the marker, growing by the link's wid) and `SnowAI_isAboveSegmentFloor` (the rider above the
  marker -> link slope minus 400); SnowAI_scanNodes needs both, scanSegments the second. The steering aim
  (`SnowAI_aimAlongSegment` / `SnowAI_aimWeave`) is in docs/1080_PHYSICS.md section 8.
- At the finish a trailing CPU rider takes the nearer of the `mkl` / `mkr` branches (`SnowAI_pickFinishBranch`).
- Forks: a marker's `ext` is the type index of the other branch (SnowAI_steer copies it to altNode); the per-level
  `bj` / `bt` / `bd` / `bu` parms decide the branch, or `SnowAI_pickFork` keeps whichever of targetNode /
  altNode is nearer the rival.
- Flags: `MARKER_F_FINISH` 0x400 marks the finish (SnowAI_isAtFinish -> SnowAI_enterFinish; the linked marker
  is tested too); `MARKER_F_REDIRECT` 0x10 makes pickFork use the linked marker instead.

## 7. Race gates and progress

`RaceTracker_findGates` (game_libs) looks up, for each rider, the nearest item of type `chk` (the next gate,
`RaceEntry.gate`) and the nearest `gtl` and `gtr`, around the rider's lastPos (SnowBoarder +0xDC). The **course
coordinate is world z**: RaceTracker courseZ / courseLength are the MapProp start.z / goal.z - start.z,
`RaceEntry.progress` is on that axis, and a gate's +0x64 (`RaceGate.z`) is its z. When both fork gates exist,
`gateA` / `gateB` hold them nearest first, ordered by `gate->z - rider->lastPos.z` (the rider +0xE4 that findGates
subtracts is lastPos.z). A gate's +0x84 is the next gate. `RaceTracker_passCheckpoints` moves entries[0].gate to
gate->next once gate->z <= entries[0].progress, then runs a gate test (gate, rider pos, entry) whose non-zero
result goes to the tracker's vtable. Note that findGates looks the `chk` gate up with entries[0]'s rider and
stores it in entries[0].gate on every pass (its lookup and that store use no entry offset), so checkpoints are
tracked for the first rider only; the fork pair is per entry. The gate item class itself is in **checkpoint.uso**
(module / file id 50, not split; section 7a): run 488 traced the bootup chk / gtr / gtl templates to its exported vtables
(course.h RaceGate comment; docs/1080_GAME_CLASSES.md section 17).

## 7a. Splitting checkpoint.uso (investigation, agent-g run 494; no config change made)

The gate class can only be typed once checkpoint.uso (module / file id 50) is a built segment. Facts from the
ROM (scratch parser /tmp/claude-1000/g494/ck2.py, crunch64 for Yay0):

- **Where it is.** It sits inside the splat slice `game_uso_inter12` (tenshoe.yaml, [0x7D6CF5, bin], the
  "153289-byte data gap"). That gap is not game.uso data: it holds four separate USO files of the same archive,
  each an Info record (`0000002C ... 12345678 <id> 00000001 <name>`) followed by its section records:

  | file (id) | Info | RoData | Data | Text (size, jr ra) | Sym | TextReloc | DataReloc | End |
  |---|---|---|---|---|---|---|---|---|
  | balloon.uso (47) | 0x7DECB6 | 0x7DECF6 +0x20 | 0x7DED22 +0x41B0 | 0x7E2EDE +0x570 (11) | 0x7E345A | 0x7E37DE | 0x7E3AF6 | 0x7E3D66 |
  | heli.uso (48) | 0x7E3D6A | 0x7E3DAA +0x100 | 0x7E3EB6 +0xCBC0 | 0x7F0A82 +0x1B60 (26) | 0x7F25EE | 0x7F2D3E | 0x7F3752 (+ RoDataReloc 0x7F3DBE) | 0x7F3E2A |
  | fire.uso (49) | 0x7F3E2E | - | 0x7F3E6E +0x23A0 | 0x7F621A +0x3B0 (7) | 0x7F65D6 | 0x7F6912 | 0x7F6B52 | 0x7F6D0E |
  | **checkpoint.uso (50)** | 0x7F6D12 | 0x7F6D52 +0x10 | 0x7F6D6E +0x3F00 | **0x7FAC7A +0x980 (17)** | 0x7FB606 +0x48C | 0x7FBA9E +0x474 | 0x7FBF1E +0x450 | 0x7FC37A |

  (offsets are the section payloads; each payload follows a 12-byte {type, size, flags} record header). No
  section is Yay0-compressed (flags 0x1000xxxx / 0x0800xxxx, bit 0x10000 clear). bg1tex.uso (id 51) starts
  at 0x7FC37E, so **the slices named game_uso_block2_yay0 / inter23 / block3_yay0 / post (0x7FC3BE..) belong
  to bg1tex.uso, not game.uso**; only block0 / block1 and the start of inter12 are game.uso.
- **Size.** 0x980 bytes of text, about 17 functions (17 `jr ra`), 0x48C / 12 = 97 symbols. The bootup chk /
  gtr / gtl templates import its Sym 417..421 (vtables 418 chk, 420 gtr + gtl; +0x48 descriptors 417 / 419 /
  421), so the class has C++ vtables; the compiler is probably the game.uso one (IDO 7.1, C plus NCC donors).
- **The blocker: alignment.** The text payload starts at ROM 0x7FAC7A, which is 2 mod 4 (so do balloon, heli
  and fire: 0x7E2EDE, 0x7F0A82, 0x7F621A). Every code segment split so far (gui / titproc / eddproc / arcproc
  / h2hproc ...) starts word-aligned. A plain splat `code` segment at 0x7FAC7A needs the linker to place a
  .text output section at an unaligned LMA (the .o's .text has alignment 4 or 16) and splat itself to
  disassemble from an unaligned ROM offset; neither has been tried in this repo.
- **What a split needs** (for the coordinator):
  1. tenshoe.yaml: cut game_uso_inter12 into `game_uso_inter12` [0x7D6CF5 .. 0x7DECB6) (the rest of game.uso
     after block1), `balloon_uso_all` / `heli_uso_all` / `fire_uso_all` bins (or later splits of their own),
     `checkpoint_uso_pre` [0x7F6D12, bin] (Info + RoData + Data + the Text record header), the code part
     [0x7FAC7A .. 0x7FB5FA), `checkpoint_uso_post` [0x7FB5FA, bin] (Sym + relocs + End), and a bin up to
     0x7FC3BE. Renaming the bg1tex slices is optional and separate.
  2. Either (a) a real `code` segment at the unaligned start, after proving ld + objcopy honour an unaligned
     `AT()` LMA and splat extracts it, or (b) the game_uso_block1 route: keep the code as a bin and splice the
     .text of an UNLINKED object (`checkpoint_uso.c.o`) into it at build time (a Makefile recipe like the Yay0
     block one, minus the crunch64 step). (b) avoids the alignment question and keeps every in-unit `jal` /
     `lui` at 0, which is what the ROM holds (USO relocations are applied by the loader from TextReloc).
  3. symbol naming: the module's Text / Data symbols as `checkpoint_uso_func_XXXXXXXX` /
     `checkpoint_uso_D_XXXXXXXX`; its imports (game_libs / bootup symbols through the Sym table) resolved the
     same way as game.uso's (dis.py desc()).
  4. objdiff.json + report units, expected/ objects, the readability gate's unit list, and
     scripts/agent-setups/1080.sh (asset copy) updated for the new unit; the 3288-function total grows by ~17.
  The ROM bytes do not change; the risk is only the layout / tooling, hence coordinator sign-off.

## 8. Props: MapProp, Mountain, BGBox, U64BGWall

- **MapProp** (bootup, 0xDC; MNode "Course"; mapprop.cpp): the course node. `shape` 0xB4 (asserts
  `shp->pGrid != NULL`), hostio group "Map" with `end` 0xB8 (0..127), `angle` 0xBC (0..89), `add` 0xC0 (0..127),
  then `start` 0xC4 and `goal` 0xD0. MapProp_display turns end / angle / add and the current view into two
  0..127 values in the gfx context (+0x10C / +0x110) every frame (probably the fog / depth-cue range).
- **Mountain** (bootup; hostio "Mountain": Pos.Y 0x2C, Scale.XZ 0x30, Scale.Y 0x34): a backdrop drawn with
  scale (xz, y, xz) and translated to the camera eye * global scale + (0, posY, 0), so it never gets closer.
- **BGBox** (bootup BGBox_ctor, 0xF4 alloc, vtbl Data 0x65E8) and **U64BGWall** (U64BGWall_ctor, "U64BGWall"):
  the sky box and the background wall built by `game_createBGBox` from the BG op's texture USO (size 0x100 or
  0xC0 and five texture imports); BGBox_func_00000D94 draws with a prim colour, U64BGWall_func_00001A44 with
  guPosition.

## 9. Open questions

- settings +0x68 (the ENV_LT2 / EQ2 / EQ3 selector) and the SUN op's two ints are not proven. Run 485: the SUN op
  handler reads neither int (createMap only builds the Sun / LensFlare / lights); the env files carry their own
  "sun" record (tags rot / ele / scl / mat / col ...; onemake03_env.bin: rot -32.4, ele -17.3, scl 2.0), so the
  op's (-91, -41) are not those angles either: unused data as far as the matched code goes. The only C reader of
  settings +0x68 (absolute 0x80020164) is createMap; no writer was found in C (a scan of every
  `import_800xxxxx + off` form), so it is written from asm or an unconverted alias.
- `RaceGate`: the gate item instance class (its base and the bytes below +0x64; +0x64 is z, so the position is
  probably a Vec3 at +0x5C).
- The ItemMgr / item file binary format (ItemMgr_Load, ItemType_load) belongs to game_libs (area E); only the
  ColourItem position read (three ints) is described here.
- WorldRegistry 0x98..0x104 (world +0x98 is what RaceTracker reads; probably the MapProp, not stored by
  game_init itself).
