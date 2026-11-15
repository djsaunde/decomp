# 1080 Snowboarding: courses and the world (for port authors)

How a course is described, loaded and laid out for a race. Types are in include/game/course.h (1080 repo);
names are the current repo names. Written by agent-g run 480 from the matched code and the ROM data.
"Probably" marks a reading that no code path proves yet.

## Index
- [1. The pieces](#1-the-pieces)
- [2. World registry and the course list](#2-world-registry-and-the-course-list)
- [3. Course descriptors (the command stream)](#3-course-descriptors-the-command-stream)
- [4. game_createMap: what a race scene is made of](#4-game_createmap-what-a-race-scene-is-made-of)
- [5. Items (rom/*_item.bin)](#5-items-romitembin)
- [6. Markers and the AI path (rom/*_mark.bin)](#6-markers-and-the-ai-path-rommarkbin)
- [7. Race gates and progress](#7-race-gates-and-progress)
- [8. Props: MapProp, Mountain, BGBox, U64BGWall](#8-props-mapprop-mountain-bgbox-u64bgwall)
- [9. Open questions](#9-open-questions)

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

(The table is the course descriptors decoded; the order of registration is the WorldRegistry_create order.)

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
  marker still counts).
- Forks: a marker's `ext` is the type index of the other branch (SnowAI_steer copies it to altNode); the per-level
  `bj` / `bt` / `bd` / `bu` parms decide the branch, or `SnowAI_pickFork` keeps whichever of targetNode /
  altNode is nearer the rival.
- Flags: `MARKER_F_FINISH` 0x400 marks the finish (SnowAI_isAtFinish -> SnowAI_enterFinish; the linked marker
  is tested too); `MARKER_F_REDIRECT` 0x10 makes pickFork use the linked marker instead.

## 7. Race gates and progress

`RaceTracker_findGates` (game_libs) looks up, for each rider, the nearest item of type `chk` (the next gate,
`RaceEntry.gate`) and the nearest `gtl` and `gtr`. When both fork gates exist, `gateA` / `gateB` hold them
nearest first, ordered by `RaceGate.progress` (+0x64) relative to the rider. A gate's +0x84 is the next gate. The
rider's progress (`RaceEntry.progress` / `pct`) is a course coordinate measured from the MapProp's start z to
the goal z (RaceTracker courseStart / courseLength). The gate item class itself (instance layout beyond +0x64 /
+0x84) is not typed yet.

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

- settings +0x68 (the ENV_LT2 / EQ2 / EQ3 selector) and the SUN op's two ints are not proven.
- `RaceGate`: the gate item class and the rider +0xE4 that findGates subtracts.
- The ItemMgr / item file binary format (ItemMgr_Load, ItemType_load) belongs to game_libs (area E); only the
  ColourItem position read (three ints) is described here.
- WorldRegistry 0x98..0x104 (world +0x98 is what RaceTracker reads; probably the MapProp, not stored by
  game_init itself).
