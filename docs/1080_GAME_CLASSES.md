# 1080 Snowboarding: bootup_uso C++ classes (area F)

> agent-g run 447, 2026-11-15, 1080 branch agent-g (commits a3beae5d7..1a7acb638 on c14657cc9).
> Updated through run 465 (section 12).
> Scope: `src/bootup_uso/*` = bootup.uso Text 0x0-0x1464C (349 functions). 88 functions named,
> one layout header (`include/game/snowboarder.h`). Names are in `renames.tsv`.

## Index
- [1. Method: strings, vtables, ctors](#1-method-strings-vtables-ctors)
- [2. Base-class conventions](#2-base-class-conventions)
- [3. Classes and their functions](#3-classes-and-their-functions)
- [4. Layouts](#4-layouts)
- [5. Not yet assigned / next steps](#5-not-yet-assigned--next-steps)
- [6. Run 451: GAME_MODE setups, replay, CamDirector, Process base](#6-run-451-game_mode-setups-replay-camdirector-process-base)
- [7. game_uso (area G) first classes](#7-game_uso-area-g-first-classes)
- [8. Cross-USO import resolution](#8-cross-uso-import-resolution)
- [9. Run 452: snowai.h, SnowBoarder physics fields, SnowAI methods](#9-run-452-snowaih-snowboarder-physics-fields-snowai-methods)
- [10. Run 456: proc API, TrickTable, RiderAnim, SnowAI path following](#10-run-456-proc-api-tricktable-rideranim-snowai-path-following)
- [11. Run 461: SnowAI states, RiderAnim PMF state machine, SnowBoarder::Parms](#11-run-461-snowai-states-rideranim-pmf-state-machine-snowboarderparms)
- [12. Run 465: naming coverage sweep, game.uso camera, Sun / LensFlare, ground handling](#12-run-465-naming-coverage-sweep-gameuso-camera-sun--lensflare-ground-handling)
- [13. Run 470: DNode physics base, SnowBoarder orientation, input fields](#13-run-470-dnode-physics-base-snowboarder-orientation-input-fields)
- [14. Run 475: physics donors on fields, camera.h](#14-run-475-physics-donors-on-fields-camerah)
- [15. Run 480: course.h (world / course data model), CourseCam](#15-run-480-courseh-world--course-data-model-coursecam)
- [16. Run 485: camera donors on fields, CamPath semantics, gates, anims.bin](#16-run-485-camera-donors-on-fields-campath-semantics-gates-animsbin)
- [17. Run 488: RiderAnim states named, anims.bin decoded, AnimPlayer base](#17-run-488-rideranim-states-named-animsbin-decoded-animplayer-base)
- [18. Run 494: RiderAnim helpers, TrickEntry, checkpoint.uso](#18-run-494-rideranim-helpers-trickentry-checkpointuso)
- [19. Run 494b: game_uso.c raw offsets, sun.h, spin fields](#19-run-494b-gameusoc-raw-offsets-sunh-spin-fields)
- [20. Run 502: SnowAI aim, DDM setters, the rider node list](#20-run-502-snowai-aim-ddm-setters-the-rider-node-list)
- [21. Run 506: game_uso cleanup, open meanings, readability status](#21-run-506-game_uso-cleanup-open-meanings-readability-status)
- [22. Run 512: last placeholder calls, parm builders, field names](#22-run-512-last-placeholder-calls-parm-builders-field-names)
- [23. Run 516: SnowBoarder and ShpNode on DNode](#23-run-516-snowboarder-and-shpnode-on-dnode)
- [24. Run 523: game_uso raw sites, GameFlow import, AnimDataMgr_lookup](#24-run-523-game_uso-raw-sites-gameflow-import-animdatamgr_lookup)
- [25. Run 528: WorldRegistry.map, C++-safe rideranim.h, game_uso int-index sites](#25-run-528-worldregistrymap-c-safe-rideranimh-game_uso-int-index-sites)
- [26. Run 532: RiderAnim state fields settled, donors on headers, GameFlow.winVariant](#26-run-532-rideranim-state-fields-settled-donors-on-headers-gameflowwinvariant)
- [27. Run 538: game.uso data sites in uso-data-sites.py, RiderAnim state PMFs named](#27-run-538-gameuso-data-sites-in-uso-data-sitespy-rideranim-state-pmfs-named)
- [28. Run 543: bootup C++ donors on headers, game.uso strings / tags / constants](#28-run-543-bootup-c-donors-on-headers-gameuso-strings--tags--constants)
- [29. Run 551: bootup donors 485C / 11B5C / 7328, game.uso RoData constants, U64BGWall_display](#29-run-551-bootup-donors-485c--11b5c--7328-gameuso-rodata-constants-u64bgwall_display)
- [30. Run 555: U64BGWall fields, Tv1, ScreenThumbMat, input.h on race.h, GameFlow.titleFlags](#30-run-555-u64bgwall-fields-tv1-screenthumbmat-inputh-on-raceh-gameflowtitleflags)
- [31. Run 558: Tv1Callback, game.uso marker tags / rumble patterns / parm tags, the C234 marker query](#31-run-558-tv1callback-gameuso-marker-tags--rumble-patterns--parm-tags-the-c234-marker-query)
- [32. Run 563: C234 CollShape.shape, SnowBoarder.boardBin, Sun / CourseMarker data constants, pattern H](#32-run-563-c234-collshapeshape-snowboarderboardbin-sun--coursemarker-data-constants-pattern-h)

---

## 1. Method: strings, vtables, ctors

bootup.uso inner header is ROM 0xD9FE28. Its sections (flags 0x10000001 / 0x2000xxxx / 0x0800xxxx; none has the 0x10000 Yay0 bit):

| section | ROM data | size |
|---|---|---|
| RoData | 0xD9FE44 | 0x25A0 |
| Data | 0xDA23F0 | 0x2E670 |
| Text | 0xDD0A6C | 0x89910 (bootup_uso = 0x0-0x1464C, game_libs = 0x1464C+) |
| Sym | 0xE5A388 | 0x7D58 |
| TextReloc / DataReloc / RoDataReloc | 0xE620EC / 0xE8F98C / 0xE95950 | |

- **String xrefs.** For each TextReloc LO16 whose symbol is a Data/RoData section symbol, the target is
  `sym.value + (hi16 << 16) + sext(lo16)` taken from the pre-relocation instruction words (pair the LO16
  with the last HI16 of the same symbol). 252 string refs land in bootup_uso.
- **Call graph.** TextReloc R_MIPS_26 targets: `sym.value + (insn & 0x3FFFFFF) << 2`. Targets
  >= 0x1464C are game_libs (`gl_` + (target - 0x1466C) gives the game_libs splat offset).
- **Vtables.** DataReloc R_MIPS_32 entries whose symbol is Text. Cfront vtables are runs of 8-byte
  entries `{s16 delta, s16 index; fn}` preceded by an all-zero entry; the vtable symbol the ctor
  stores is 8 bytes before the first function (so "vtbl 0x83D0" below is the label, slot 0 is at +8).
- **Ctors.** NCC/Cfront protocol: `if (this == 0) this = new(SIZE)`, base ctor (game_libs 0x3800C =
  Node ctor, takes the node name; `<Node>` / `<MNode>` / `<QNode>` are the defaults), then the vptr at
  `this + 0x28`. The class name is the node name, or the name string stored into the object right after.
- **Perf sections.** game_libs 0x4DD14 / 0x4DD1C are begin/end of a named profiler section;
  game_libs 0x600A4 / 0x601D4 push/pop a named heap section. Their string arguments name the code between them.

The scratch scripts that did this (`uso.py`, `table.py`, `strcall.py` in /tmp/claude-1000/g447/) are
~100 lines of Python over the ROM; the same can be rebuilt from `scripts/uso-sym-oracle.py`.

## 2. Base-class conventions

| vtable shape | meaning |
|---|---|
| 10 slots `gl_38360 gl_38598 gl_3863C gl_38728 gl_38830 gl_38964 gl_38A28 gl_38B6C gl_38B74 gl_38B7C` | the Node base; classes override slot 0 (parms reader: "Mountain", "Map", "Snower"), 2, 3 and 8 |
| 16 slots `gl_3D48C ... func_00000C10 (slot 10) ...` | template base; **slot 10 = create an instance** (allocs and stores the instance vptr). Emitted once per TU (copies at 0x64A8, 0x6760, 0x6F48, 0x8078, ...) |
| 12 slots `gl_65D64 gl_40E90 ... E5F0 (7) E610 (8) ... E5E8 (11)` | the QNode/shape object base (ctor 0x8F18, `<QNode>` + "shp"); SnowBoarder derives from it |
| 11/14 slots with slot 10 = `func_0000F434` (vtbl 0xC338) | window/process base of PauseMenu, Fader, QuitProcess |

Item-type table, Data 0x7B6C: `{RoData tag, create fn, flags}` x14 (hel, hem, bal, ba2, chk, gtr, gtl,
cfr, snw, fog, sn2, fo2, sn3, fo3).

## 3. Classes and their functions

| class | function (new name) | addr | evidence |
|---|---|---|---|
| **SnowBoarder** (0xA8C, vtbl 0x83D0, node "SnowB") | SnowBoarder_ctor | 90CC | new(0xA8C), "SnowBoarder::Parms" (hpf/snf/.../tch keys) |
| | SnowBoarder_func_0000CFA0 | CFA0 | slot 2 |
| | SnowBoarder_update | D440 | slot 3; perf SnowB > SnowBai, SnowBDyn, SnowBAnm, SnowBChild |
| | SnowBoarder_checkRaceEnd | D900 | slot 4; "win"/"lose"/"timeout"/"player got ending" |
| | SnowBoarder_func_0000E4DC | E4DC | slot 8 |
| | SnowBoarder_updateDyn | BF8C | the call inside the "SnowBDyn" section (same `this`) |
| | SnowBoarder_procColl | C234 | "SBProcColl", inside the "SnowBCol" section of updateDyn |
| | SnowBoarder_func_0000B520 / _B75C | | updateDyn helpers |
| | SnowBoarder_func_0000CAE8 | | "HANDICAP %s: ON" |
| | SnowBoarder_func_0000CCE0 / DDCC / DF04 / E014 / E124 | | SnowBoarder fields (0xA58 flags); E124 = mirror flip |
| (audio) | snd_updatePlayer | 0610 | "NA_UpdPl", end of SnowBoarder_update |
| **game setup** | game_init | 27E8 | "MainGame", InitGame/CreateMap/CreatePlayers timings |
| | game_setupMode | 2DA4 | "unknown GAME_MODE" switch -> 3734/38C0/39D8/3B78/3D3C/3F00/411C/43D4 |
| | game_createLights / game_create3DWindow / game_createPlayers / game_createMap / game_createBGBox / game_createProcessWindow | 2F90 / 34E8 / 3638 / 6808 / 5F34 / F81C | "Lights", "3DWindow", "Players", course groups, "BGBox", "ProcessWindow" |
| | game_loadUso / game_unloadUso / game_isUsoLoaded / game_loadUsoOnce | 118E4 / 1195C / 8920 / 8980 | list of loaded .uso paths at holder+0x130 |
| **camera** | cam_create | 31C0 | "snowlookat", cam_info/cam_ca/lookat_ca*.bin, "LookAtChase" |
| | cam_func_00004948 / _00004914 | | camera vtbl 0x7120 slots 3 / 12 |
| **EnvSettings** (0x44, vtbl 0x76A8) | EnvSettings_ctor / EnvSettings_func_00007288 / EnvSettings_load | 7150 / 7288 / 7328 | "EnvSettings"; slot 8 "Env Load: %s" |
| **items** | item_createHel/Hem/Bal/Ba2/Chk/Gtr/Gtl/Cfr/Snow/Fog | 5068..553C | item-type table tags |
| | item_registerTemplates | 55A0 | "register %s"; pyr/tr1-3/tv1/light01/lig/gol/st0/en1/en2/cam |
| **Fog** (template vtbl 0x78D8, instance 0x7878) | FogTmpl_create; Fog_func_00008078/7EC8/80B4/80EC | 8124 | "Parms"/"fin"/"rng" |
| **Snow** (template 0x79C8, instance "Snower" 0x7968) | SnowTmpl_create; Snower_func_000083D0/82F8/8448/8474; FallingSnow_create | 84A0, 74E8 | "Snower"/"Snow", "FallingSnow" |
| **Tree** (template 0x7AB8, instance 0x7A58) | TreeTmpl_create; TreeTmpl_func_00008744/86C0; Tree_func_00008664 | 87A4 | "tree"; tr1/tr2/tr3 |
| **Mountain** (vtbl 0x7038) | Mountain_func_0000477C / _485C | | "Mountain" Pos.Y/Scale.Y/Scale.XZ |
| **MapProp** (0xDC, vtbl 0x7C20) | MapProp_ctor; MapProp_func_000063B4 / _6734 | 6254 | `<MNode>`, assert in mapprop.cpp; slot 0 "Map"/"end"/"add"/"angle" |
| **BGBox** (0x40, vtbl 0x65E8) | BGBox_ctor; BGBox_func_00000D94 | CA0 | name "BGBox" |
| **U64BGWall** (0x4C, vtbl 0x6648) | U64BGWall_ctor; U64BGWall_func_00001A44 | E68 | "U64BGWall" |
| **SnowBoard** app (vtbl 0x8BA8) | SnowBoard_func_0000E800 / E9FC / EA2C (15) / EAF8 (14) / F3D4 (12) / F404 (13) | | "SnowBoard", version.bin, anims.bin, audio .uso files; creates GameFlow |
| **GameFlow** | GameFlow_create / GameFlow_func_00010FEC | 10C8C / 10FEC | "GameFlow"/"Flow", gui.uso, flowimgs.bin; "FLOW: free blocks > 1" |
| **PauseMenu** (0x304, vtbl 0xC47C) | PauseMenu_create; PauseMenu_func_00010540 (2) / 1034C (3) / 10260 (10) / 1024C (11) | FEE8 | "PauseMenu" |
| **QuitProcess** (0x50) | QuitProcess_func_0000FC28 / _0000FD4C | | "Quit Process" |
| **Fader** (0x78, vtbl 0xC6C8) | Fader_ctor; Fader_func_0001304C | 12E00 | "Fader" |
| **TimeGadget** | TimeGadget_ctor_00013D40 (0x98; suffixed because game_libs owns TimeGadget_ctor); TimeGadget_func_0001438C (0x38) | 13D40 / 1438C | "TimeGadget::Parms" xps/yps/lbx/lby/l2x/l2y |

Note on SnowBDyn / SnowBCol / SnowBai / SnowBAnm: in this code they are **profiler section labels inside
SnowBoarder_update**, not separate objects. updateDyn and procColl take the SnowBoarder itself as `this`, so
they are named SnowBoarder_*. The AI and anim steps are virtual / game_libs calls (jalr, gl 0x6337C,
gl 0x61824); their bodies are not in bootup_uso.

## 4. Layouts

`include/game/snowboarder.h` (asserted with the os_thread.h idiom, sizeof == 0xA8C):

| off | field | evidence |
|---|---|---|
| 0x028 | (vptr, not typed yet) | ctor |
| 0x800 / 0x804 / 0x808 | (sub-objects, not typed yet) | SnowBoarder_update decode |
| 0x844 | `char *unk844` child A (transform at +0x30) | E124 |
| 0x864 | `char *unk864` child B (nullable) | E124 |
| 0x8C4 | `u32 state` (6, 7 skip) | DDCC |
| 0x8F4 | `SnowBRec3 *unk8F4[3]` | DDCC/DF04/E014 |
| 0x900 / 0x902 | `s16 unk900 / unk902` table indices | E014 |
| 0x978 | `f32 unk978` spin/axis, negated on flip | E124 |
| 0xA38 | `f32 unkA38` cleared on flip | E124 |
| 0xA58 | `u32 flags` (0x80 = SNOWB_FLAG_MIRROR, 0x08, 0x20) | E124, everywhere |

Converted bodies: SnowBoarder_func_0000DDCC / DF04 / E014 / E124 (bootup_uso.c). Byte-identical first try.

## 5. Not yet assigned / next steps

- **Parms readers**: func_00000008 / 0044 / 0080 / 00F0 read int / float / Vec3 / ? from a parms file, and the
  0x30-byte B50/B80/BB0/BE0 (and the per-TU copies 1C10.., 22E0.., 89C0.., E8BC.., EC80.., EF20..) are the
  parms-type handlers in the 0x18-byte records. Not renamed: those function symbols are also used as
  USO data-base symbols (`func_00000008 + 0x2C`), so a function name there would mislead.
- Per-mode setups called by game_setupMode (3734, 38C0, 39D8, 3B78 x2, 3D3C, 3F00 "Player1/2", EDC0,
  411C, 43D4): map the switch cases to GAME_MODE values to name them (`game_setupTimeAttack`, ...).
- Classes still without a name: vtbl 0x6FD8 (ctor 2420, slots 24B8 "cam", 27C0), vtbl 0x7788 (tv1;
  7C74 / 7E70 / 7E50 / 7D04), vtbl 0x8108 and vtbl 0x8698 (SnowBoarder children, ctors inside 90CC / 8B44),
  the QNode/shape base (8F18), vtbl 0xC338 window base (F434).
- The -O0 island (F1F0-12DB8) is mostly GameFlow / GUI glue: walk its callers from GameFlow_create.
- More SnowBoarder fields: SnowBoarder_ctor (90CC, cfe donor bootup_uso_90CC.c) writes most of the
  object; its sub-object cascade (+0x3EC 0x154-byte child etc.) gives the next layer. SnowBoarder_update
  gives 0x800 (input?) / 0x804 / 0x808 / 0xA10-0xA28.
- Gadgets: only TimeGadget's Parms are in bootup; BestTime/CountDown/Points/Speed/Cool/Course gadget
  strings are referenced from game_libs or other modules (check their DataReloc).

## 6. Run 451: GAME_MODE setups, replay, CamDirector, Process base

agent-g run 451 (commits 6d10cff76, 91b983a6b, c8a5911cf on 4b67f8fe3; all three are pure rename batches).

**GAME_MODE switch** (game_setupMode, jumptable RoData 0x4F4, cases 1..12; 7 and 8 hit the default
"unknown GAME_MODE"). The values are game_init's 3rd argument; titproc (the only importer of game_init)
passes 9, 10, 11 and 4. No string names the values, so the setups are named by what they build:

| mode | function | builds |
|---|---|---|
| 1 | game_setupEmpty (EDC0) | nothing; game_setupMode then sets flag 4 on the scene obj +0x18 |
| 2 | game_setupSolo (38C0) | one pad rider, 1 cam, 1 window, recorded |
| 3 | game_setupVsGhost (39D8) | pad rider recorded + rider played from the replay table cfg+0x14C |
| 4, 12 | game_setupReplay (3B78) | rider played from the recorded buffer cfg+0x168; CamDirector; FOV 85 |
| 5 | game_setupVsCpu (3D3C) | pad rider + input-0 rider, linked through +0x908, +-500 start offsets |
| 6 | game_setupVs2P (3F00) | "Player1"/"Player2", 2 cams, 2 windows, both recorded |
| 9 | game_setupDemoSolo (3734) | one non-pad rider (flags 0x58005), CamDirector |
| 10 | game_setupDemoRace (411C) | two non-pad riders, random characters (rand * k % 3), 1 window |
| 11 | game_setupDemoSplit (43D4) | the same with 2 windows (FOV 55) |

Separate from these: the flow-mode tables at Data 0xC450 (names N64DEMO, TITLEDEMO, HEAD2HEAD,
MULTIGAMERACE, TIMEATTACK, ARCADEMODE, TRICKMODE, TRAINING, EDITORS, NONE) and 0xC4EC (the matching
proc USOs n64proc, titproc, h2hproc, mgrproc, timproc, arcproc, trkproc, trnproc, eddproc, then genproc,
nameent, gamegfx, charsel), both read by GameFlow_func_00010FEC.

The race procs (arc/tim/trk/h2h/mgr) do **not** import game_init: h2hproc imports CamDirector_ctor,
cam_create and game_create3DWindow and builds its own scene. Where they create the players is still open.

**Replay / input manager** (a global cfg: +0x100 input list, +0x124 count, +0x14C ghost table,
+0x168 / +0x16C record buffers, +0x170 / +0x174 positions, +0x184 cursor): replay_addInput (11CA4),
replay_beginRecordWithGhost (128AC), replay_beginRecord2P (129A0), replay_beginRecord1P (12AC4),
replay_beginPlayback (12B7C). The 0x80-byte input objects are built with ctor(o, 1) for a pad and
ctor(o, 0) for playback/AI. func_00012818 copies 8 bytes into cfg+0x154 and checks the word at
0xA0000200 against 0xAC290000.

**CamDirector** (vtbl 0x6FD8, `<Node>`): ctor 2420, update 24B8 (every 60 frames picks the nearest
"cam" map node and switches between the two cams at +0x30 / +0x34; in manual mode zooms FOV 45..120),
onMessage 27C0 (msg 0x3ED clears enable flag 8), setActiveCam 2774.

**Other classes:** Tv1Tmpl (vtbl 0x7788, "tv1" item: create 7C74, slots 7E70 / 7E50, helpers 7D04 /
77D0) and its instance Tv1 (vtbl 0x7818, slot 2 76F4); SnowBCollider (vtbl 0x8698, 0x178 bytes, ctor
8B44, onContact 8BD4); ShpNode (vtbl 0x81E0, `<QNode>` + "shp", ctor 8F18; 8FA8, E5E8, E5F0, E610,
inherited by SnowBoarder's 0x83D0).

**Process base** (vtbl 0xC3A0; QuitProcess 0xC2B8, Fader 0xC6C8 and PauseMenu derive from it, and every
mode proc imports it): Process_start F434 (Node flags +0x18 |= 4 | 8), Process_stop F4CC, Process_update
F6C4 (slot 3), F76C / F7D0 / F7F4 (slots 2 / 11 / 12). Node flag bit 8 = update enabled (CamDirector
checks it); bit 4 is still unnamed (Node_setFlag4_0000F66C and friends).

Not named: vtbl 0x8108 (the 0x154-byte SnowBoarder child at +0x3EC, with a 0x128-byte sub-object at +0x2C;
slot 8 E720 forwards to it). The rest of the -O0 island (F1F0-12DB8): see section 8 for who imports what.

## 7. game_uso (area G) first classes

game.uso inner header ROM 0x7CC900 (Text data 0x7CCF86, size 0x11B30; the splat offset equals the Text
offset). 240 functions, 18 with string xrefs. Named in run 451:

| class | vtbl (Data) | functions |
|---|---|---|
| SnowChaseActorCam | 0x1F8 | ctor 1D30, readParms 18FC, update 1DDC, 249C (slot 8) |
| SnowChaseActorLook | 0x258 | ctor 2814, readParms 2744, update 28C0, 2CA8 |
| SnowChaseActor | 0x2B8 | ctor 34A4, readParms 3018, update 3558, 3948 |
| CourseMarker | tmpl 0x4B8, inst 0x578 | CourseMarkerTmpl_create 41C0, CourseMarker_registerTemplates 3AC0 (mrk, mk1..mk5), 44C8 |
| SnowAI | 0x5D8 | ctor 44F4, update 57D8, 57B8, and 591C / 7ACC / 9B88 / A0E8 / A3C4 (snowai.cpp asserts) |
| LensFlare | | LensFlare_create B8D4 |

**The "0x4E0 main object" is SnowAI.** SnowAI_ctor allocates 0x4E0 bytes and a 0x3E0-byte child, so the
READABILITY_PLAN's "MainGame object (0x4E0)" is the AI rider controller. The "MainGame" string is
bootup's game_init (and genproc's). The planned include/game/maingame.h should therefore be
include/game/snowai.h. Still unnamed: the "sun" parms (AE1C), the C48C class (vtbl 0x115C, keys
lnc/jct/jht/jot/jca: trick or jump parms), the `<Node>` class C2D4 (vtbl 0x10FC).

Tools (scratch, /tmp/claude-1000/g451/): `mods.py` finds every USO inner header (including the
byte-misaligned Yay0 ones: trkproc 0x5B3DE2, trnproc 0x5B8D06, genproc 0x5BCA4E, viewrec 0x642346) and
decompresses their sections; `gu.py` / `gtab.py` / `gvt.py` print the game_uso string / call / vtable tables.

## 8. Cross-USO import resolution

An import Sym entry (kind 1) names the exporting module (`info >> 4`) and that module's Sym index
(`word3 >> 16`). bootup is module 0 and gui.uso is module 18, so every proc's imports from bootup
can be resolved to bootup functions:

| importer | bootup_uso functions it imports |
|---|---|
| all procs | Process_start F434, Process_update F6C4, F76C, F7D0, 100F0, 1016C, 10B6C, 11E00, 1207C, 139B0, 2DC, 2FC |
| titproc | game_init 27E8 (modes 9, 10, 11, 4), F954, FEE8, 120A8, 126EC, 11CD8 |
| h2hproc | CamDirector_ctor 2420, cam_create 31C0, game_create3DWindow 34E8, 12C10 |
| tim/trk proc | 12C64, 13FE0, 144B4 (trk, arc) |
| genproc | 2060, func_00002C94, 34E8, B1B4, B49C, BGBox_ctor CA0, U64BGWall_ctor E68 |
| game.uso | 85C, 888, 8B4, 8D4, 8F4, 940, 98C, 9D8, A24, E124 (mirror flip), E270 |

That table is the starting point for naming the -O0 island: e.g. 2DC / 2FC / 100F0 / 1016C are part of
the shared proc API.

## 9. Run 452: snowai.h, SnowBoarder physics fields, SnowAI methods

agent-g run 452 (branch agent-g on 430cf6b79): 2e8f5a55d + 028ce8c05 (headers), 42ed0fdb9 + 22c8f1827
(field conversions), 7793cdbb7 (pure rename batch, 22 names). Every commit gated (PASS, ROM identical).

**include/game/snowai.h.** SnowAI (0x4E0): Node base, vptr 0x28 (Data 0x5D8), `level` 0x2C (1..3),
`rider` 0x30 (SnowBoarder *), `modeFlags` 0x68 (1 / 2 / 4 = A3C4 / A604 / A7F8 instead of steering), the
embedded **SnowAIParms** at 0xE4 (0x3E0 = name "SnowAI::Parms" + list head + 41 x 0x18 SnowAIParm), unk4C4.
The parms block is the "0x3E0 child" of the plan: its 41 entries are float parms built by game_libs
0x35B1C(parm, owner, tag, 1) from 4-char tags in Data 0x6E8..0x788:
de0-2 bd0-2 bt0-2 bu0-2 bj0-2 cf0-2 dd0 dd5 dd6 dd1 dd7 dd8 dd2 dd3 dd4 dp0-2 se0-2 ms1-8.
Each triple is one value per difficulty: 591C picks `parm[base + level - 1]`. The tag is passed **by value**
as a 4-byte struct, which is why SnowAI_ctor has the `$s2` marshalling slot. SnowAIParm: +0xC vtable
(Data 0x3C8 float parm; 0xF78 / 0xFC0 are the float / int parm vtables of the C48C class), +0x10 value.

**SnowBoarder physics** (include/game/snowboarder.h, from SnowBoarder_limitSpeed = old B520 and the ctor):
pos 0xB4 (node position), vel 0x318, speed 0x348 (|vel|), startPos 0x3A4 (ctor x / z + ground height),
dir 0x3C8 (unit forward), dragXZ 0x6C0, baseMaxSpeed 0x768, input 0x800 (ctor arg 4), sub808 (0xC member),
rival 0x908, unk938 (drag only while 0), unk8C0 = 1 << state, tint[4] 0x8E0, maxSpeed 0xA78.
SNOWB_FLAG_NUDGE 0x100, SNOWB_FLAG_CATCHUP 0x20000 (maxSpeed +-k when the rival leads / trails in z:
the CPU rubber band). `state` 0x8C4 is ctor arg 2 (unk8C0 is its one-hot mask): it may be a rider slot,
not a state; the name was kept.

Converted bodies: SnowAI_func_0000591C (the cfe donor game_uso_591C.c; the two `unsigned int` level
reads stay raw) and SnowBoarder_limitSpeed. The ctors (SnowAI_ctor, SnowBoarder_ctor) are left raw: their
bodies do pointer arithmetic on the untyped `this` that carries the levers.

**Names (7793cdbb7):** Sun_ctor (AE1C), SnowAI_reset (5728), SnowAI_dtor (5780), 14 SnowAI_func_* (the
591C callees), SnowBoarder_limitSpeed, snd_sendEvent_000002FC (-> gl 0x2FB74), snd_unmuteAll_000002BC,
gui_initRows_000100F0 / gui_centerRows_0001016C. bootup 0x1C8..0x3A0 is a run of audio wrappers:
1D4/1E4 -> gl 0x309AC, 204 -> snd_SetSoundOutputMode_2D6C8, 224 / 244 / 264 -> 2D70C / 2D748 / 2D784,
284 -> 30A20, 2A4 -> 2D618, 2C4 -> 2D670, 2E4 -> 2FB54, 304 -> 2FB74 (jal sites). **func_000001FC is not
renamed**: the same symbol is a USO reloc base (`func_000001FC + 0x18` in bootup E68).

**Still open:** the C2D4 class (vtbl 0x10FC, 0x2C bytes, slot 8 = C3F8 reads a count and N 0x40-byte
records from a stream into Bss 0x0 / 0x4; C344..C3CC are its accessors), the C48C class (0x444 bytes,
vtbl 0x115C, 32 float / int parms lnc jct jht jot jca jlt jli rfc tkt b1f b2f xf1 f1f-f4f l1f-l3f r1f r2f
dm1-4 st1-3 sl1 sl2 slm stm; no class-name string, the base is import 0x10D33C); converting
SnowAI_reset / the A3C4 family to snowai.h fields (5728 writes 0x34..0x78, 0xA4, 0x4D8, not yet in the
header); the rest of the proc API (10B6C, 11E00, 1207C (+0x128 = a1), 139B0, F954, 120A8, 126EC, 11CD8,
12C10, 12C64, 13FE0, 144B4).

## 10. Run 456: proc API, TrickTable, RiderAnim, SnowAI path following

agent-g run 456 (branch agent-g on 0eab7ffa2). Pure rename batches: 5a6952091 (25 names), b6049040f (26),
431ec65d6 (6). Hand edits: d4650bff0 (snowai.h fields), 51b19406a (SnowAI_reset + scan family on fields).
Every commit gated (PASS, ROM identical). Tool: /tmp/claude-1000/g456/dis.py (`dis.py game|bootup START END`
= objdump of a module's Text with every TextReloc resolved to a name, string or section offset; imports
from bootup are resolved through bootup's Sym table).

**Proc API (bootup).** The global at bootup Bss 0xF8 (the "replay cfg" of section 6) is the **input
manager**: pads at +0xE0 (count +0x120), replay inputs at +0x100 (count +0x124), active pad +0x128
(-1 = any), pause flag +0x188. Pad objects (game_libs 675A4 fills them) keep +0x10 held, +0x14 previous,
+0x18 pressed (cur & ~prev), +0x1C released (~cur & prev). Names: input_pauseAll / unpauseAll / setActive /
addPad / checkPressed / checkHeld / checkReleased / setActivePad / clearActivePad (all with address suffix).
Other proc-API names: gui_clearRows / gui_addRow / gui_addRowSub (rows are 0x28 bytes at +0x84, count +0x78),
snd_playSeq_000120A8 ("Poop start" wrapper = snd_HandleSeqEvent), settings_applySoundMode_0001266C and
settings_setFlag4_000126EC (settings word at cfg +0x154, +4: bits 0-1 sound output mode, bit 2 unknown option
mirrored into Bss 0x28C and broadcast as message 0x15), replay_freeRecord / replay_saveGhost (Backup_writeGhost),
Process_fadeOut_0000F954 (pause input, Fader_start(gFader, 3, 0), "Poop end").
**Fader** (vtbl 0xC6C8, gFader = Bss 0x288): Fader_start (mode +0x40, direction +0x68, seeds a 32x32 float
grid), Fader_buildTexture (grid -> 32x32 RGBA16 texture +0x4C through a palette), Fader_checkDone (progress
+0x48 == 1.0, gfx_viBlack after a fade-out), Fader_isDone. TimeGadgetParms_setPos / setLabelPos / setPosF
write the parm values (0x18-stride records: xps 0x44, yps 0x5C, lbx 0x74, ...).
`func_00000148` / `func_00000188` ("Poop start" / "Poop end") are **not** renamed: both are USO reloc bases.

**TrickTable (game_uso C2D4, vtbl 0x10FC).** No class string, Node_hostioParms not overridden, so named by
role. bootup game_setupMode creates it with "rom/tricks.bin" inside the "ImgFileMgr" memtrack section (import
46:267; module 46 = game.uso; the instance pointer is game.uso export 266). Slot 8 reads a count (Bss 4) and
0x40-byte records (Bss 0). Accessors are static (the `this` arg is unused): getEntry, getEntry10 (+0x10),
getField2C / 30 / 34 / 38, getCount. game_libs E05C (trick display / scoring, area D) calls getField30 and
getEntry. C194..C27C are generic fs_gdlReadFile helpers (stream_readS32 / F32 / Vec3 / 16).

**RiderAnim (game_uso C48C, vtbl 0x115C, 0x444 bytes).** Created by SnowBoarder_ctor (import 46:275). Its
base (game_libs 62E80, vtbl Data 0x21F58) is the keyframe animation player ("StartAnim", "BadKeyFrame",
update = gl 6337C, which is the call in SnowBoarder_update's "SnowBAnm" section). The 32 parms are anim timing
(jump crouch / hang / out, trick, damage, stand, slide ...). Methods: update (slot 3; reads the rider at +0xB4
and the pad), selectAnim D9CC (rider speed 0x348, buttons 0xA10, 0xA1C), setAnim / setNextAnim /
setDefaultNext (anim ids are 8-byte pairs at +0xC0 / +0xC8), endTrick D63C (combo count +0x100, game_libs trick
scorer E118 / E1DC), flipStance D6E4 (toggles rider flag 0x40 = stance, then SnowBoarder_func_0000E124; anim
set 0x50000 / 0x10000), readParms (slot 8), reset (slot 10), init D458. Export hashes are not class names
(C48C's is 0x424E4E50).

**SnowAI path following** (snowai.h now covers 0x34-0x7C, 0xA0/0xA4, 0x4D8/0x4DC). The AI steers toward
`targetNode`, an index into the course-node table (game.uso Data base + 0x548). At a fork SnowAI_steer (591C)
loads `altNode` from the node's +0x6C and switches to it according to the per-level bj / bt / bd / bu parms
(branch parms), or sets modeFlags 1 so SnowAI_pickFork (A3C4) keeps whichever is nearer the rival.
SnowAI_startNodeScan / scanNodes (modeFlags 2) and startSegmentScan / scanSegments (modeFlags 4) test ten nodes,
one per frame (`scanIndex`, `scanBestDist`), to re-acquire the path. `aiState` 0x64 selects SnowAI_update's step:
0 SnowAI_steer, 1 6A30, 2 6CF0, 3 71E0 (unnamed). `initPending` 0x4D8: SnowAI_reset sets it; the next update,
for a CPU rider (+0x848 == 2) racing a human, writes rider +0x758 from **ms1..ms8 chosen by the rival's 0x8C4**.

**SnowBoarder 0x8C4 is probably the character id**, not a state: SnowAI_update maps its values 1..7 (default 8)
to the eight ms parms, and the ctor takes it as arg 2. Rename `state` once a second use confirms it.

**Next:** name 6A30 / 6CF0 / 71E0 (aiState 1..3) and 7538 (AI stick input: 0x44 / 0x4C / 0x50 / 0x58 drive a
table of stick (x, y) at Data 0x638); RiderAnim fields (0xB4 rider, 0xC0 / 0xC8 anim ids, 0x100 combo, 0x13C
parms) into a header; SnowBoarder 0x758 / 0x848 / 0xA10 / 0xA1C from RiderAnim_selectAnim; the rest of the
game_uso RiderAnim helpers (D74C, D7F4, D8A8, D8EC, EDCC, EDD4) and the 0xE000+ classes.

## 11. Run 461: SnowAI states, RiderAnim PMF state machine, SnowBoarder::Parms

agent-g run 461 (branch agent-g on 8239918e8). Pure rename batches: 3c2e2c3eb (17 names), 1ec395bf6 (56).
Hand edits: 6ef639515 (snowboarder.h + new include/game/rideranim.h), 9474d27f2 (field conversions).
Every commit gated (PASS, ROM identical). Scratch tools in /tmp/claude-1000/g461/: `dptr.py` (every game.uso
Data word that relocates to Text), `gimp.py` / `gimp2.py` (which module, and which bootup call site, imports
each game.uso function: import Sym entries with `info >> 4 == 46`, resolved through game.uso's Sym index).

**SnowAI states.** aiState 0 SnowAI_steer, 1 SnowAI_finishRun (6A30), 2 SnowAI_timeoutRun (6CF0), 3
SnowAI_recoverStuck (71E0); every step ends in SnowAI_applyStickInput (7538). Entry points: SnowAI_enterFinish
(71A4; steer calls it when the current node has flag 0x400, i.e. SnowAI_isAtFinish), SnowAI_enterRecover
(7424; after 75 frames below speed 30), and the three hooks bootup's SnowBoarder_handleMsg (old
SnowBoarder_checkRaceEnd = vtbl slot 4, the Node_handleMsg override) calls on rider->ai: SnowAI_onWin (msg
1000), SnowAI_onLose (1001; not for CPU riders), SnowAI_onTimeout (1003). The other msgs: 20 = bumped by an
object (pos / vel push, hitFlags |= 0x1F0, wobble), 9, 6, 1002 / 1004, 1005..1007 = ending ("en1" / "en2"
marker by controller). SnowAI_scaleRiderParms / restoreRiderParms / scaleRiderMax (7448 / 74D8 / 751C)
save the rider's max / nts / dts / nbf parm values in SnowAI 0x4C8..0x4D4 and scale them by dd2 / dd3 / dd4
while the 0x4C4 countdown runs (the dp / dd0 / dd1 parms gate it): the catch-up boost.

**RiderAnim is a PMF state machine.** The "anim id pairs" at +0xC0 / +0xC8 are Cfront pointers to member
functions: Data 0xDB0..0xF60 is a table of {0x0000FFFF, method} (delta 0, index -1 = non-virtual) and 0xDC8 is
the null PMF. Renamed: setState_0000D5F8 (old setAnim), setNextState_0000D5BC, clearNextState_0000D5DC, and
the 53 table-only functions to RiderAnim_state_<addr> (kind known; individual states not named yet: their
calls to the game_libs anim player 0x6366C / 0x635D8 give the anim numbers ORed into animSet).
Other RiderAnim facts: parms at 0x13C are 32 parms by tag; dm1..dm4 (ints) are the damage per hit kind that
RiderAnim_applyDamage_0000EDD4 subtracts from rider->health (0xA14, the match-race damage meter;
game_setupVsCpu gives the CPU rider 10000000); st1..st3 / sl1 / sl2 with limits stm / slm drive rider +0x960
in game_uso ECEC by hitKind (0x10C, set by EDCC). RiderAnim_clearRiderSpin_00011868 zeroes rider->spin.

**SnowBoarder layout (snowboarder.h).** SnowBoarder::Parms is embedded at +0x540 (0x2C0, 29 float parms in
ctor order hpf snf dsf icf tfc edf bdf ure mro mpi mdr axr ayr azr tlt wfr sfr dts nts trt twt min max jmp
djp ufs bdm cdm tch). The old dragXZ (0x6C0) is parms.wfr.value and baseMaxSpeed (0x768) is parms.max.value.
The 0x154-byte child at +0x3EC (vtbl 0x8108) has its own "Parms" at +0x2C (= rider 0x418): ied ifr ded dfr
efr nbf nel dbf del res flx sta (not typed yet; nbf = rider 0x498). New fields: ai 0x804, anim 0x840,
controller 0x848 (0 pad, 2 CPU; 1 unproven), **character 0x8C4 confirmed** (game_createPlayers passes index + 1
as ctor arg 2; 1..8 select ms1..ms8), spin 0x970 (Vec3), hitFlags 0xA10 (u16), health 0xA14, unkA1C (lateral
wobble: msg 20 adds the bump along the side axis 0x3BC), raceResult 0xA54. 0x758 is the `max` parm, 0x848 the
controller; 0xA10 / 0xA1C are what RiderAnim_selectAnim tests for the stumble anims.

**Next:** name the RiderAnim states from their anim numbers (map anims.bin indices); type the +0x3EC child
and its Parms; SnowBoarder_updateDyn (BF8C) and its callees for orientation / board angles / ground contact
(0x938 is probably the ground-contact flag: B520's drag, the SnowAI run-out tail and RiderAnim D74C gate on it; unproven; 0x3BC / 0x3C8 are the side /
forward axes); the game_uso 0xA000+ classes (AC78 / 11A94 template creates, AD10..ADE0 parm-type readers,
B274..BFDC = LensFlare / Sun methods via Data 0xC50..0xD34) and bootup's remaining placeholders.

## 12. Run 465: naming coverage sweep, game.uso camera, Sun / LensFlare, ground handling

agent-g run 465 (branch agent-g on 42f08ef0b). Pure rename batches: 11c65f6ba (109 names), cd2a1e9d2 (176),
f565cc583 (7). Hand edit: 7214d8e29 (snowboarder.h). Every commit gated (PASS, ROM identical). Scratch tools in
/tmp/claude-1000/g465/: `summ.py` (game.uso: callers / Data refs / cross-module importers / callees / strings per
function), `bsumm.py` (the same for bootup), `dd.py` / `bdd.py` (annotated Data dumps for vtables), `dis.py`
(now also resolves `game_libs_func_` names).

**Coverage.** game.uso: every function now has a class / subsystem prefix (only the `game_uso_func_00000000`
sentinel is left). bootup: 38 `func_` names remain; 26 of them are deliberately kept because the symbol doubles as
a USO data-reloc base in the source (`func_X + K` or `&func_X`; list: 0, 8, 44, 80, F0, 148, 188, 1FC, 23C, 27C,
29C, 3F8, 57C, 8B4, 8F4, 940, 98C, C10, 7620, 7A48, 89FC, 8A38, 8A40, 8A7C, 8AEC, CACC). Genuinely open: 6204
(MapProp vtbl slot 12), 7204 (game_createMap helper), 7BF4 (one-slot vtbl Data 0x7770), E270, 12110, 122C4,
127CC, 12818, 14004, 14010, 144F4, 14598.

**Per-TU copies.** Every NCC TU re-emits the stream readers (`fs_gdlReadFile(gStream, buf, n)`: S32 / F32 /
Vec3 / Quad (16 bytes)), the parm loaders (`tag = readS32(); read<T>(&parm->value)`: Float / Vec3 / Quad / Int)
and the template "create instance" slot 10 (`new ColourItem(0x40)`, vptr Data 0x75A0, link into the type's list).
Names: `stream_read<T>_<addr>`, `game_read<T>Parm_<addr>` / `boot_read<T>Parm_<addr>`,
`game_ItemType_create_<addr>` / `boot_ItemType_create_<addr>` (the edd_ / tit_ / h2h_ precedent).

**game.uso camera (TU 0x0-0x1800).** `cam_ctor_00000858` (0x27C bytes, vtbl Data 0x184, base gl 32E18 =
MNode "camera") is what bootup cam_create builds from rom/cam_info.bin (modes 0 / 2; mode 1 builds a plain camera
named "LookAtChase" with a SnowChaseActor). It holds camPath records (0x7C, header + camKey list of 0x38-byte keys:
3 Vec3, F32, S32, Vec3) and camList index lists, both read in slot 8 (cam_readParms_00001644). Slot 3 cam_update
runs cam_updateView (B3C: cubic B-spline over 4 keys via math_dot4 / math_blendVec3x4), slot 4 handleMsg (msg 8 / 9
reset both chase actors and pick the view by the target rider's raceResult: cam_pickResultView), slot 12
cam_command (commands 3..18 select views). No class string exists, so the prefix is the subsystem `cam_`.
The SnowChaseActor* `*_readParms` names were the Parms-object constructors (renamed `*Parms_ctor`); their vtbl
slot 8 is now `*_loadParms` (a freed name must not be reused: the gate folds renames.tsv chains).

**Sun / LensFlare (game.uso 0xAE1C-0xC0E8).** Sun (0x178, vtbl 0xC5C, node "sun", Parms rot / ele / scl / mat /
col): display (projects the sun, size * visibility 0xCC), update (position from rot 0x11C / ele 0x104),
readParms, and Sun_measureVisibility: a member-function callback (16-byte object at +0xDC: vptr Data 0xC44, obj,
PMF {0, -1, B4B8}) registered with the renderer by display (gl 4E1BC); it samples 9 depth-buffer texels around
the sun's screen position (value 0xFFFC = clear) and eases 0xCC toward the visible fraction. LensFlare (vtbl 0xCEC,
"LensFlare::Parms" fin / dlv / dfm): display draws N LensFlareElem records (0x24: pos, color quad, size, sprite,
flags, F32) along the sun-to-centre axis; readParms reads the count and the records.

**SnowBoarder ground handling (snowboarder.h).** SnowBoarder_updateDyn = limitSpeed, B75C (orientation), the
"SnowBCol" section (procColl), then three game_libs physics steps (gl 65448, 64DEC, 65148). Each frame it rebuilds
`friction` 0x360, `edgeGrip` 0x9FC, `edgeFriction` 0x9F8 and `turnRate` 0xA00 from the +0x3EC child's Parms
(SnowBChildParms: ied ifr ded dfr efr nbf nel dbf del res flx sta) and SnowBoarder::Parms (edf, bdf, nts / dts, sfr):
n* = normal set, d* = while `useDParms` (input bit 0x400 held), * ied, ifr on surface 'c' and * ded, dfr on 'b'
(`surface` 0x9A2, 0 off the ground: edge terms zeroed, friction + k), `crouch` 0x990 (stick y < -0.75) adds
|spin.x| * k, `slowdown` 0x960 (percent; 100 + speed < 30 stops the rider). procColl clears `contactCount` 0x938
(the old unk938: so limitSpeed's wfr drag applies only with no contacts, i.e. in the air) and the
contactNormal / contactDepth sums that SnowBCollider_onContact accumulates; `groundSurface` 0x9A0, `groundFlags`
0x9A8 and `groundDist` 0x9D0 come from its ground query.

**Next:** the 12 open bootup functions above; SnowBoarder_func_0000B75C (orientation: quatRotateAxisAngle over
the axr / ayr / azr parms) and the three game_libs physics steps; convert the updateDyn / procColl NM bodies to
the new fields; RiderAnim states: agent-b run 463 named the game_libs player (AnimPlayer_start 635D8,
AnimPlayer_startIfChanged 6366C) on its branch, but the anim ids they pass still need an anims.bin index -> name map.

## 13. Run 470: DNode physics base, SnowBoarder orientation, input fields

agent-g run 470 (branch agent-g on 19f8e0b6f). Pure rename batch: 0d55dfaff (22 names). Hand edits: 89d8cdfa6
(snowboarder.h + updateDyn / procColl reference bodies), 3cfd6de6b (input.h conversions). Every commit gated (PASS,
ROM identical). The physics overview for port authors is docs/1080_PHYSICS.md.

**DNode (game_libs, area E code; names agreed with agent-b).** SnowBoarder's first 0x3D4 bytes are the game_libs
DNode ("DNode::Parms" at +0x108, tags imp spd spl spw gvt suc vsc usc tsc cog unc dsc csc rad cts at bootup Data
0x223D0; game_libs Data offsets are bootup Data offsets). DNode_update = QNode_update, DNode_solveContacts,
DNode_applyAccums_00065448, DNode_integrate_00064DEC (was integrateRot), DNode_resetAccums_00065148. Two 0x34-byte
force accumulators (SnowBAccum: weight, pointSum, force, torque, origin): impulseAcc +0x294 feeds angVel 0x2FC (quat)
and vel 0x318, moveAcc +0x2C8 feeds orient 0xCC and pos 0xB4 directly; DNode_addImpulseAt_00065250 /
DNode_addMoveAt_000652D8 add a force at a world point (relative to worldCog 0x324); DNodeAccum_apply_00064388 /
reset_00064170 / addForce_000641DC are the accumulator methods. The comments in game_libs_post1b.c that call gl
0x62F64 "AnimPlayer_update" for DNode_init / 65250 / 652D8 are stale (dis.py resolves them to 65148 / 65B40 / 641DC);
left for area E.

**SnowBoarder_updateOrient (B75C).** See docs/1080_PHYSICS.md section 3. New snowboarder.h fields: edge / edgeSteer /
edgeSlope (0x970..0x978, the old `spin` Vec3), localUp 0xA04, shake 0xA5C, spinHold 0xA6C, airSpin 0xA70, unkA18 (air
trick rotation gate), the DNode part, and procColl's contact block (prevPos, impactScale, penetration, impactVel,
lastContactNormal, noGroundFrames, airFrames, groundNormal, groundPlaneD, onGround, groundGentle, groundColor, bump*).
0x808 is a sound object (`sound`), 0x850 a light (procColl eases unk91C and passes it to light_setF124_000550A0).
The NCC donor of B75C (bootup_uso_ncc_B75C.cpp) is still raw offsets: it compiles without -I, would need the header
by relative path and a non-C++ guard on the asserts (as done for input.h).

**Bootup open functions, all named:** boot_staticInit_00006204, map_addEntry_00007204, MemberCallback_invoke_00007BF4,
SnowBoarder_yawPiOver_0000E270, GameFlow_releaseFiles_00012110, settings_stepSequence_000122C4, settings_get8_000127CC /
settings_set8_00012818, TimeGadgetParms_set104_00014004 (class from neighbours only), gadget_decodeStringE4_00014010 /
gadget_decodeStringB4_00014598, gadget_slideStep_000144F4. Only the 26 reloc-base `func_` names remain in bootup.

**Input (agent-h include/game/input.h).** input_checkPressed / Held / Released (NCC donor, includes the header by
relative path), input_addPad, replay_addInput, input_setActivePad / clearActivePad now use InputMgr / InputPad. input.h's
assert typedefs are under `#ifndef __cplusplus` (edg rejects them).

**Next:** RiderAnim states by anim id; the SnowBChild class (+0x3EC) methods; SnowBCollider_onContact (NCC 8BD4) and
SnowBCollider_func_0000E2D0 (edge-grip response) on fields; 0x8B8 / 0x8DC / 0x9E8..0x9F4 / 0xA40 / 0xA44 (display);
the B75C / C234 NCC donors on fields; groundFlags bits 1 and 0x400.

## 14. Run 475: physics donors on fields, camera.h

agent-g run 475 (branch agent-g on 98fd6c22f). Hand edits: e140bc633 (physics donors), 8410c8ad2 (camera.h +
game.uso chase camera), 584f363af (MCamera / RiderCam / CamDirector / FreeCam / CamFollow). Pure rename: 406098216
(SnowBCollider_func_0000E2D0 -> SnowBCollider_edgeGrip_0000E2D0). Every commit gated (PASS, ROM identical); each
converted donor .o was also compared with objdump -dr against the pre-edit object before the gate.

**Physics donors.** snowboarder.h's asserts are under `#ifndef __cplusplus`, so NCC donors include it by relative
path (`#include "../../include/game/snowboarder.h"`, after the donor's own s32 / f32 / u8 / u16 / u32 typedefs).
bootup_uso_ncc_B75C.cpp (updateOrient) and _C234.cpp (procColl) now read rider-> fields; an access whose width
differs from the field stays `*(T *)&rider->field` (e.g. pos.x passed as an int). A scratch converter
(/tmp/claude-1000/g475/conv.py: offset -> field map, raw `*(T *)((char *)(v) + K)` -> field) did the bulk. New
snowboarder.h fields: RiderInput (0x800: stickX / stickY / held), light 0x850. SnowBCollider_onContact (8BD4) keeps
its C++ views (the inline V3 operators are part of the match) with snowboarder.h member names: SnowBCollider
(pointVel 0x114, worldPoint 0x120, hitTri 0x14C, rider 0x170, flags 0x174) and RiderView. Its per-site import aliases
resolve to BasePolyShape 52A4C (surface code), SnowBCollider_edgeGrip_0000E2D0, Friction_vfn11_00063F34 and
DNode_addImpulseAt_00065250. E2D0 (-O2 C) takes SnowBoarder * and named parameters. docs/1080_PHYSICS.md section 5.

**Camera (include/game/camera.h, docs/1080_CAMERA.md).** game.uso SnowChaseActorCam (0x124, Parms cof mxz txz cxz
miy toy ty2 chy), SnowChaseActorLook (0x64, ch0), SnowChaseActor (0x138, off xxz mxz txz mxy miy toy cxz chy): all
three move their parent CamMNode by math_mtxAddTranslation (game_uso_func_072EE8) on its local matrix. Their C bodies
in game_uso.c (ctors, resets, setMode, loadParms, cam_toTargetLocal) and the five NCC donors (1DDC / 24BC / 28C0 /
2CC8 / 3558, member names only) are converted. game_libs MCamera (gl 32E18, 0x150), bootup RiderCam (0x15C) and
CamDirector (0x50; ctor and setActiveCam converted), and game_libs FreeCam (renames.tsv CamMan_*: the matching C++
calls it FreeCam::update) / CamFollow (a debug orbit controller) are typed; FreeCam / CamFollow bodies are agent-b's
file and left raw.

**Next:** CamDirector_update and cam_create (31C0 donor) on camera.h; the game.uso camera object (0x27C: rider 0x150,
chase component 0x154, p4 0x274) as a struct and the B3C donor on it; MCamera ctor / lookAt in game_libs_post.c
(area E file); the course / world data model (WorldRegistry, the SnowAI course-node table, CourseMarker, Mountain /
MapProp); RiderAnim states by anim id (agent-b's AnimPlayer names).

## 15. Run 480: course.h (world / course data model), CourseCam

agent-g run 480 (branch agent-g on f304648ad). Hand edits: 0264481d6 (new include/game/course.h), c57b79a18
(conversions), 5919dc6c9 (camera.h CourseCam + conversions). Pure rename: a38fb9ae0 (3 names). Every commit gated
(PASS, ROM identical); each converted object's `objdump -dr .text` was compared with the pre-edit build.
The port-author overview is docs/1080_COURSE.md.

- **course.h:** the course descriptor stream (COURSE_OP_*), WorldCourse / WorldRegistry (0x118: course list +
  og / fg / bg / eg / MainGame roots), CourseItemTmpl (bootup Data 0x7B6C), RaceGate (+0x64 / +0x84), CourseMarker
  (0x8C) + CourseMarkerParms (wid / ext / flg) + MARKER_* types and flags, MapProp (0xDC), Mountain.
- **game_createMap's case labels were wrong.** The donor's `case N:` values were source-order numbers; the
  donor's own jump table is dropped for the pinned ROM table (RoData 0x5B4), so .text matched anyway. The labels
  are now the real ops (bootup_uso_o2_6808.c).
- **The "course-node table" (game.uso Data 0x548) is the marker type-name table** (mrk mk1..mk9 mkl mkr):
  SnowAI.targetNode / altNode are marker TYPE indices; the marker is found by type + nearest z.
- **Converted:** game_createMap donor, WorldCourse_ctor / WorldRegistry_create / addCourse / getCourse x2,
  Mountain_hostioParms, MapProp_ctor / hostioParms (bootup); SnowAI_isAtFinish / pickFork / scanSegments,
  cam_ctor_00000858 / cam_reset_000008FC / cam_setView_00000AEC (game.uso).
- **Renames:** WorldRegistry_ctor_00001D8C -> WorldCourse_ctorEmpty_00001D8C; game_getNthChild_00001FC8 / 00002014
  -> WorldRegistry_getCourse_*.

**Next:** CamDirector_update and the 31C0 cam_create donor on camera.h; the B3C donor on CourseCam fields (EDG
2.29 front end: verify per field); the gate item class (chk / gtl / gtr instance layout) and the rider +0xE4;
RiderAnim states by anim id (agent-b's AnimPlayer names); agent-a's gl_data.h accessors for the course data sites.

## 16. Run 485: camera donors on fields, CamPath semantics, gates, anims.bin

agent-g run 485 (branch agent-g on db64f9963). Hand edits c6f65fa53 (CamDirector_update, cam_create donor classes
renamed + Makefile objcopy names, RiderInput rawX / rawY / pressed, SnowBoarder.camSource 0x874, chase-component
ctor arg 4 = parmsFile), d3913335e (B3C MIPSpro donor on CourseCam / CamPath / CamKey fields, CamPath helpers
typed, CourseCam.pad = RiderInput *), b69b691d3 (RaceGate.z, the rider +0xE4 = lastPos.z; course doc section 7).
Pure rename 21ff8f4ba: camPath_isRelative_00000674 -> camPath_hasSpline_00000674. All gated (PASS, ROM identical).
Camera details: docs/1080_CAMERA.md sections 2 / 2a; gates: docs/1080_COURSE.md section 7.

**anims.bin (for the RiderAnim state names, not done yet).** rom/anims.bin is ROM 0x923BBA: an Info record
(file id 0x56, "anims.bin") then one 0x2660EC-byte data record. Inside, every animation has a header followed by
its name and a "<n>-0.dsc" source file name, e.g. boarder_bump_l_break, boarder_normalposition, boarder_turn_normal_b66,
boarder_brake_b / _f, boarder_landing_s, boarder_crashing_f_1rot / 2rot, boarder_bump_r / _l (+ _break),
boarder_pre_jump_A(Z), open_norm_fk_F02, new_hop07, 01_15_180..1080_air_open / _blind, 01_16_1260 / 1440_air_*,
normal_front_flip3, normal_back_flip3, knee_cushion06, boarder_yoroke_a02 / b02 / c01 (stumbles), landing_a02,
the grabs (method_7, mute_grab_6, tail_grab5_1, indy5, stalefish_6, nose_grab_6, lien_6, melonchollie_8_1,
tweaked4_1, indynb_6, stiffy_6, shifty_6, normal_Jtear_air, normal_BS_handplant, normal_McTWIST,
normal_alley_McTWIST, One_foot2, fakie_mystery, panda_trick_X03), the character select poses (select_KIMATI_05,
DION, AKARI, RICKY, ROB), then a fakie set (boarder_fk_*, 360_fk_fk_360_B01 / F01, swith_stanceFN, knee_cushion05,
boarder_yoroke_fk*, landing_fk02), crash / DEAD sets (crash_f_1rot_DEAD5, DEAD2_crash_bside / fside_1rot,
new3_bump_r_break_d, new4_bump_l_break_d), and start_a, turn_slow_b / f, boarder_goal_w3 / l2 / n_r5, goal_spin,
boarder_time_up6, ending_WIN_480d, ending_LOSE_475b, start_A..E_type02, HP_OM_goal_WIN5_2. Two kinds of entries
(header words ..00000004 00000020 = a pose / blend entry whose name's first byte is 0, and ..00040000 = a keyed
anim). The RiderAnim anim ids are 0x1xxxx / 0x2xxxx (0x10011, 0x10025, 0x10028 / 29, 0x10068, 0x10094, 0x100B8 /
C0 / D8 / F0 / F8, 0x20002..0x20008), so the low half is not a plain entry index into this list (0x100F8 > 170
entries): the id -> entry map needs the AnimPlayer loader (game_libs 62E80.. / 635D8) decoded first.

**Next:** decode the anims.bin entry header (AnimPlayer load path) to map anim ids to names, then name the 53
RiderAnim_state_<addr> by the anims they start; the gate item instance class; the rider body at camSource.
(Done in run 488, section 17; the anims.bin id list above was a misread.)

## 17. Run 488: RiderAnim states named, anims.bin decoded, AnimPlayer base

agent-g run 488 (branch agent-g on 9dcd5ce48). Pure rename 9ea04f99c (53 states). Hand edits bb6158407 (new
include/game/rideranim_anims.h; RiderAnim embeds AnimPlayer; 45 anim-id literals in game_uso.c and the F060 /
F13C / 10840 / 10A0C donors as RANIM_*), 3dcc072b9 (MCamera_ctor MNode_vtbl + MCamera_vtbl, CamFollow_ctor,
CamDirector_ctor vptr stores on the gl_data.h aliases), 26d9c7873 (gate class home; camSource). All gated
(PASS, ROM identical). Scratch: /tmp/claude-1000/g488/anims.py (anims.bin parser), an.py (per-state call
arguments from the reloc-resolved disassembly).

**rom/anims.bin.** The data starts at ROM 0x923C02 (after the 0x2C-byte Info record, file id 0x56, and the
data record header): the AnimDataMgr_loadFile stream of docs/1080_GRAPHICS.md section 11, version 0x128, 9
groups. Every anim record opens with cmd 4 (skip 0x20 bytes) and those bytes are the name plus the "<n>-0.dsc"
source. An entry whose name starts with a 0 byte (or is all 0xFF) has numFrames 0. **Run 485's ids 0x100F8 etc.
were misreads; every id RiderAnim uses is in range.** Note 0x30001 (boarder_ollie_arm, the stateOllie* anim) is
one of the empty entries in the retail file. Listing (index hex, name, kN = keys, fN = frames; parentheses =
empty):

- group 0 (2): 0 (oarder_bump_l_break); 1 (oarder_normalposition)
- group 1 (48): 0 boarder_row k3 f10; 1 (oarder_normalposition); 2 boarder_turn_normal_b66 k2 f13; 3 boarder_turn_normal_f55 k2 f13; 4 boarder_brake_b k2 f16; 5 boarder_brake_f k2 f16; 6 (oarder_weight_f); 7 (oarder_weight_b); 8 boarder_up_down k2 f6; 9 (oarder_landing_s); A new01_17_crashing_f_slide k3 f28; B boarder_crashing_f_1rot k3 f44; C boarder_bump_r k2 f21; D boarder_bump_l k2 f21; E boarder_crashing_bside_slip k3 f58; F boarder_crashing_fside_slip k3 f58; 10 (oarder_pre_jump_A); 11 boarder_pre_jump_AZ k2 f6; 12 boarder_crashing_bside_1rot k3 f57; 13 boarder_crashing_fside_1rot k3 f52; 14 boarder_crashing_f_bottocks k2 f16; 15 boarder_crashing_f_2rot k3 f63; 16 boarder_bump_r_break k2 f36; 17 boarder_bump_l_break k2 f36; 18 open_norm_fk_F02 k5 f11; 19 new_hop07 k6 f22; 1A blind_norm_fk_B02 k5 f14; 1B front_360_norm_fk_360_F01 k5 f28; 1C blind_360_norm_fk_360_B01 k5 f28; 1D swith_stanceNF k2 f11; 1E 01_15_180_air_open k5 f16; 1F 01_15_180_air_blind k5 f21; 20 01_15_360_air_open k5 f26; 21 01_15_360_air_blind k5 f26; 22 normal_front_flip3 k5 f19; 23 normal_back_flip3 k5 f21; 24 deep_pos_sw_stNF k2 f11; 25 knee_cushion06 k2 f17; 26 boarder_turn_n_preJ_b k2 f6; 27 boarder_turn_n_preJ_f k2 f6; 28 boarder_turn_dp_preJ_b k2 f2; 29 boarder_turn_dp_preJ_f k2 f2; 2A F_flip_crash4 k3 f22; 2B normal_B_flip_crash3_1 k3 f21; 2C boarder_yoroke_a02 k2 f16; 2D boarder_yoroke_b02 k2 f16; 2E boarder_yoroke_c01 k2 f16; 2F landing_a02 k2 f16
- group 2 (19): 0 boarder_crashing_f_bottocks k2 f16; 1 (oarder_deepposition); 2 turn_deep_b2 k2 f4; 3 turn_deep_f1 k2 f4; 4 boarder_brake_dp_b k2 f7; 5 boarder_brake_dp_f k2 f7; 6 (oarder_weight_f_deep); 7 (oarder_weight_b_deep); 8 boarder_up_down_dp k2 f6; 9 boarder_landing_s k2 f12; A -; B -; C boarder_bump_dp_r k2 f21; D boarder_bump_dp_l k2 f21; E -; F (elect1_ok); 10 (elect2_ok); 11 (elect3_ok); 12 (ead_crashing_f_slide_d)
- group 3 (37): 0 (oarder_hop); 1 (oarder_ollie_arm); 2 method_7 k5 f27; 3 mute_grab_6 k5 f26; 4 tail_grab5_1 k5 f27; 5 indy5 k5 f27; 6 (oarder_taipan); 7 stalefish_6 k5 f26; 8 nose_grab_6 k5 f25; 9 lien_6 k5 f26; A melonchollie_8_1 k5 f19; B (oarder_heel_edge_grab); C tweaked4_1 k5 f31; D indynb_6 k5 f26; E stiffy_6 k5 f19; F shifty_6 k5 f36; 10 (oarder_w_hand_g_01); 11 (oarder_w_hand_g_02); 12 normal_Jtear_air k5 f21; 13 normal_BS_handplant k5 f21; 14 normal_McTWIST k5 f26; 15 normal_alley_McTWIST k5 f26; 16 01_15_540_air_open k5 f31; 17 01_15_720_air_open k5 f36; 18 01_15_900_air_open k5 f43; 19 01_16_1080_air_open k5 f51; 1A 01_15_540_air_blind k5 f31; 1B 01_15_720_air_blind k5 f36; 1C 01_15_900_air_blind k5 f43; 1D 01_15_1080_air_blind k5 f51; 1E One_foot2 k5 f31; 1F fakie_mystery k5 f26; 20 01_16_1260_air_open k5 f61; 21 01_16_1440_air_open k5 f66; 22 01_16_1260_air_blind k5 f61; 23 01_16_1440_air_blind k5 f66; 24 panda_trick_X03 k5 f26
- group 4 (5): 0 select_KIMATI_05 k4 f100; 1 select_DION_05 k4 f140; 2 select_AKARI_04_1 k4 f91; 3 select_RICKY_04 k4 f106; 4 select_ROB_02 k4 f120
- group 5 (48): 0 boarder_row k3 f10; 1 (oarder_normalposition); 2 boarder_fk_turn_norm_b k2 f13; 3 boarder_fk_turn_norm_f k2 f13; 4 boarder_fk_brake_b k2 f16; 5 boarder_fk_brake_f k2 f16; 6 (oarder_weight_f); 7 (oarder_weight_b); 8 boarder_fk_up_down k2 f6; 9 (oarder_landing_s); A new01_20_fk_crashing_f_slide k3 f28; B boarder_fk_crashing_f_1rot k3 f41; C boarder_fk_bump_r k2 f21; D boarder_fk_bump_l k2 f21; E boarder_crashing_bside_slip k3 f58; F boarder_crashing_fside_slip k3 f58; 10 -; 11 -; 12 boarder_fk_crash_bside_1rot k3 f51; 13 boarder_fk_crash_fside_1rot k3 f51; 14 boarder_fk_crash_f_bottocks k2 f16; 15 boarder_fk_crash_f_2lot k3 f58; 16 boarder_fk_bump_r_break k2 f36; 17 boarder_fk_bump_l_break k2 f36; 18 blind_fk_norm_B02 k5 f14; 19 new_fk_hop06_1 k6 f22; 1A open_fk_norm_F02 k5 f11; 1B 360_fk_fk_360_B01 k5 f28; 1C 360_fk_fk_360_F01 k5 f28; 1D swith_stanceFN k2 f11; 1E (akey_180_air_B); 1F (akey_180_air_F); 20 (akey_360_air_B); 21 (akey_360_air_F); 22 (akey_front_flip); 23 (akey_back_flip); 24 deep_pos_sw_stFN k2 f11; 25 knee_cushion05 k2 f15; 26 -; 27 -; 28 -; 29 -; 2A -; 2B -; 2C boarder_yoroke_fka02 k2 f16; 2D boarder_yoroke_fkb01 k2 f16; 2E boarder_yoroke_fkc01 k2 f16; 2F landing_fk02 k2 f16
- group 6 (44): 0 -; 1 -; 2 -; 3 -; 4 -; 5 -; 6 -; 7 -; 8 -; 9 -; A crash_f_1rot_DEAD5 k2 f46; B crash_f_1rot_DEAD5 k2 f46; C new3_bump_r_break_d k2 f27; D new4_bump_l_break_d k2 f27; E DEAD2_crash_bside_1rot k2 f76; F DEAD2_crash_fside_1rot k2 f76; 10 -; 11 -; 12 DEAD2_crash_bside_1rot k2 f76; 13 DEAD2_crash_fside_1rot k2 f76; 14 new3_bump_r_break_d k2 f27; 15 crash_f_1rot_DEAD5 k2 f46; 16 DEAD2_crash_fside_1rot k2 f76; 17 new4_bump_l_break_d k2 f27; 18 -; 19 -; 1A -; 1B -; 1C -; 1D -; 1E -; 1F -; 20 -; 21 -; 22 -; 23 -; 24 -; 25 -; 26 -; 27 -; 28 -; 29 -; 2A crash_f_1rot_DEAD5 k2 f46; 2B crash_f_1rot_DEAD5 k2 f46
- group 7 (16): 0 start_a k2 f6; 1 turn_slow_b k2 f21; 2 turn_slow_f k2 f13; 3 boarder_goal_w3 k2 f31; 4 boarder_goal_l2 k2 f31; 5 boarder_goal_n_r5 k2 f36; 6 (oal_spin); 7 boarder_time_up6 k2 f26; 8 ending_WIN_480d k5 f481; 9 ending_LOSE_475b k5 f476; A start_A_type02 k3 f46; B start_B_type02 k3 f46; C start_C_type02 k3 f46; D start_D_type02 k3 f46; E start_E_type02 k3 f46; F HP_OM_goal_WIN5_2 k2 f56
- group 8 (8): 0 (ormal_180_air_F); 1 (ormal_180_air_B); 2 (ormal_360_air_F); 3 (ormal_360_air_B); 4 (akey_180_air_F); 5 (akey_180_air_B); 6 (akey_360_air_F); 7 (akey_360_air_B)

Groups 1 and 5 share their layout (regular / switch stance; RiderAnim.animSet holds 0x10000 or 0x50000), group 2 is
the crouched ("dp") version of the same indices, group 3 holds the ollie and the TrickTable trick anims (entry
+0x20; +0x24 / +0x28 alternates, +0x38 bit 1 = spin), group 6 the selectAnim DEAD crashes (`| 0x60000`), group 7
start / goal / ending. Macros: include/game/rideranim_anims.h (RANIM_ID, RANIM_GROUP_*, RANIM_*).

**State machine.** States are PMFs (section 11). setState(pmf, key) stores key in AnimPlayer.eventKey (0x64), so
the state changes when playback passes that key; key -1 goes to blendEvent (0x68) and the change happens when
the ANIM_BLENDIN cross-fade ends. setNextState is the state the current one falls back to. Table (address,
name, anim and keys started, next state):

| addr | state | evidence |
|---|---|---|
| EE74 | stateStopped | init's held-at-start state: rider slowdown = 100 |
| EE84 | stateSwitchStance | start(animSet|0x1D swith_stanceNF / 0x24 deep_pos_sw_stNF), key 1 -> stateSwitchStanceEnd |
| EF20 | stateFlipToRide | flipStance, next = stateRide |
| EF70 | stateSwitchStanceEnd | flipStance + yawPiOver, then ride / ride deep / hop air |
| F060 | statePreJump | startIfChanged(0x10011 boarder_pre_jump_AZ, blend-in parm 0x16C) -> statePreJumpHold |
| F13C | statePreJumpHold | setBlend(0x10028 / 0x10029 boarder_turn_dp_preJ_b / f) or 0x10011; after parm 0x184 frames -> statePreJumpCancel |
| F284 | statePreJumpCancel | startIfChanged(animSet|8 boarder_up_down / 0x20008 boarder_up_down_dp), back to ride |
| F424 | stateTrickAir | per-frame trick air step (no anim), next of stateTrickStart |
| F49C | stateTrickEnd | trick done -> stateHopAir |
| F514 | stateTrickWindup | trick anim keys 4..2 (spin flag 2); grab held -> stateTrickHold |
| F5A8 | stateTrickRelease | chain the queued trick (stateTrickStart) or play trick anim 3..1 -> stateTrickEnd |
| F664 | stateTrickHold | trick anim keys 2..3 -> stateTrickRelease |
| F6D4 | stateTrickStart | RaceTracker_startTrick, start(TrickTable entry +0x20 anim) -> windup / release |
| F8E8 | stateRowIn | startIfChanged(animSet|0 boarder_row, blend-in 5) -> stateRow |
| F948 | stateRow | boarder_row keys 0..2 -> stateRowOut |
| FA54 | stateRowOut | boarder_row keys 2..1 -> stateRide |
| FABC | stateResumeRide | clear edge, next = stateRide |
| FB04 | stateCrashRecover | after animSet|0xA crashing_f_slide: selectedAnim keys 2..1 -> stateRide |
| FD04 | stateOllieTakeoff | 0x30001 boarder_ollie_arm keys 2..3 -> stateOllieRise |
| FDCC | stateOllieRise | 0x30001 keys 6..6 (-> stateOllieLand) or 3..4 (-> stateOllieHang) |
| FEC8 | stateOllieHang | 0x30001 keys 4..5 looping -> stateOllieDrop |
| FF48 | stateOllieLand | 0x30001 keys 6..1 -> stateRideBlendIn |
| FFB8 | stateOllieDrop | 0x30001 keys 5..6 -> stateOllieLand |
| 10068 | stateHopStart | startIfChanged(animSet|0x19 new_hop07, keys 0..2, blend-in 10) -> stateHopRise |
| 10128 | stateHopRise | new_hop07 to key 3 -> stateHopAir |
| 102CC | stateHopAir | new_hop07 keys 3..4 looping; -> stateHopDrop / stateHopLand / stateCushionIn |
| 10408 | stateHopDrop | new_hop07 keys 4..5 -> stateHopLand |
| 104A4 | stateHopLand | on contact: endTrick, new_hop07 keys 5..1 -> stateRideBlendIn |
| 1056C | stateCushionIn | startIfChanged(0x10025 knee_cushion06, blend-in 5) -> stateCushion |
| 105DC | stateCushion | knee_cushion06 keys 0..1 -> stateCushionEnd |
| 10648 | stateCushionEnd | next = stateHopLand |
| 10694 | stateRide | setBlend(animSet|2 / 3 boarder_turn_normal_b / f by edge) or animSet|8 up_down |
| 10840 | stateRideDeep | setBlend(0x20002 / 3 turn_deep_b2 / f1): crouched (useDParms) riding |
| 1094C | stateBrake | setBlend(animSet|4 / 5 boarder_brake_b / f by edge) |
| 10A0C | stateBrakeDeep | setBlend(0x20004 / 5 boarder_brake_dp_b / f) |
| 10AC8 | stateRideBlendIn | turn blend with blend-in 10 -> stateRide |
| 10B38 | stateRideDeepBlendIn | turn_deep blend with blend-in 5 -> stateRideDeep |
| 10CF0 | stateBrakeBlendIn | brake / brake_dp blend with blend-in 10 -> stateBrake / stateBrakeDeep |
| 10E8C | stateGoalNormal | 0x70005 boarder_goal_n_r5 (won, input-mgr +0x7C set) |
| 10EC8 | stateGoalWinOM | 0x7000F HP_OM_goal_WIN5_2 (won, input-mgr +0x64 < 2) |
| 10F04 | stateGoalWin | 0x70003 boarder_goal_w3 |
| 10F40 | stateGoalLose | 0x70004 boarder_goal_l2 (raceResult != 1) |
| 10F7C | stateTimeUpLose | 0x70004 boarder_goal_l2 after stateTimeUp |
| 10FB8 | stateStand | 0x70000 start_a keys 0..1, next = itself |
| 11124 | stateTimeUp | startTimeout's state: stand, then stateTimeUpLose |
| 11168 | stateFinish | startFinish's state: stand, then a goal state by raceResult |
| 11368 | stateEnding1 | ending anim (0x70008 ending_WIN_480d / 0x70009 ending_LOSE_475b) keys 2..3 |
| 113C8 | stateEnding2 | ending keys 3..4 |
| 11428 | stateEnding3 | ending keys 4..1 |
| 11460 | stateStartIntro | start(0x7000A + character: start_A..E_type02, keys 0..2) |
| 114FC | stateStartIntroEnd | start anim keys 2..1 -> stateStartWait |
| 1155C | stateStartWait | animSet|8 boarder_up_down loop + ping-pong until the start |
| 115DC | stateIdle | empty state |

Entry points: RiderAnim_init picks stateStartIntro (Data 0xDB0), stateStartWait (0xDB8) or stateStopped (0xDC0);
startFinish / startTimeout set stateFinish / stateTimeUp; startEnding / startEndingCpu start 0x70008 / 0x70009
then stateEnding1..3. stateFinish: raceResult (0xA54) != 1 -> GoalLose; else input manager (bootup Bss 0xF8)
+0x7C set -> GoalNormal, +0x64 < 2 -> GoalWinOM, else GoalWin. Non-table helpers that start sequences:
0xFB7C (crash slide -> stateCrashRecover), 0xFC34 (ollie, -> stateOllieTakeoff), 0x10BAC / 0x10C4C (weight blend
animSet|7/6, 0x20007/6), 0x10DC8 (animSet|9 landing), 0x1001C (-> stateHopStart).

**RiderAnim fields.** RiderAnim now starts with `AnimPlayer player` (stateArg / unk68 became player.eventKey /
blendEvent). Not yet typed: 0xF0 queued trick, 0xF4 current TrickTable entry (anim id +0x20), 0x114, 0xE4 / 0xE6
(pre-jump counters vs parm 0x184).

**Gates.** The gate class is in checkpoint.uso (module / file id 50, ROM Info 0x7F6D1A), which is not split.
bootup item_createChk (0x4C) / Gtr / Gtl (0x50) store SNodeItemType_vtbl then checkpoint.uso exports (vtables
Sym 418 chk, 420 gtr + gtl; +0x48 descriptors 417 / 419 / 421). See course.h RaceGate.

**camSource (0x874)** is slot 22 of the 40-slot shape-file node registry (bootup Bss 0x3C058, Sym 550: shape
cmd 0x67 stores the current node in a slot, cmd 0x66 parents to one; Node_doCommand). SnowBoarder_ctor copies
14 slots into 0x820..0x874 after the rider model is built (slot -> field: 27 0x824, 34 0x820, 2 0x828, 7 0x830,
1 0x82C, 6 0x834, 20 0x838, 28 0x844, 33 0x860, 29 0x854, 30 0x85C, 31 0x858, 32 0x864, 22 0x874). Which body
part slot 22 is needs the rider shape stream (cmd 0x65 names the node). (Resolved in section 20: the head.)

**Next:** name the 0xFB7C..0x116D4 non-table helpers (crash slide, ollie, weight, landing, hop entry); type
RiderAnim 0xF0 / 0xF4 (TrickTable entry struct) and convert the raw a0[0xFC / 4] accesses to RA(a0)->animSet
function by function; decode the rider shape stream for the registry slot names; split checkpoint.uso for the gate class.

## 18. Run 494: RiderAnim helpers, TrickEntry, checkpoint.uso

agent-g run 494 (branch agent-g on 4b8811979). Pure rename 806436965 (31 names). Hand edit adea6fdf0 (new
include/game/tricktable.h; RiderAnim trick fields; conversions in game_uso.c and the E35C / F6D4 donors). Both
gated (PASS, 3288/3288, ROM identical); game_uso.c.o and the two donor objects' .text were also compared with
the pre-edit build. Scratch: /tmp/claude-1000/g494/ (pre.dis = reloc-resolved D204..EE74, tricks.txt, ck2.py).

**Helpers named** (renames.tsv carries the one-line evidence): startCrashSlide FB7C, blendTurn FBF8, startOllie
FC34, startHop 1001C, blendWeight / blendWeightDeep 10BAC / 10C4C, startLanding 10DC8, restartRide 10E2C,
playHitAnim 115EC, startHitAnim 11624, crashRecover 116D4; and the per-state checks the state bodies call:
trickCrash D74C (contact during a trick), checkReverseBrake D7F4, checkBrake D8A8, checkJump D8EC, checkRow
E1FC, holdJumpLift E2D0, startQueuedTrick E35C, playSpinSound E564, readTrickInput E5C8, checkGroundSpin E91C,
readStickSpin EAF4, updateSlowdown ECEC, addTrickPoints EE30, jumpTakeoff F360, checkBackwardSwitch 11750,
clearTricks 11888, hitFeedback 1189C (pad_set rumble + SndHandle_triggerEvent per hit kind). FB7C, FBF8,
FC34, 10BAC, 10C4C, 10DC8, 10E2C and 116D4 have no caller in game.uso Text or Data; they are exported (Sym
328..339), so they are either called from another module or dead.

**rom/tricks.bin** (Info record 0x91F90E, file id 0x43; count 29 at ROM 0x91F94E, records from 0x91F952). TrickEntry
(tricktable.h): name[16], 16 bytes at +0x10 (same in every entry), anim +0x20 (written at trick start from
animSwitch when the rider is in switch stance and animSwitch != 0, else animRegular), animRegular +0x24,
animSwitch +0x28, inputMask +0x2C (grab bits low; 0x1000 / 0x2000 = 180 each way, 0x4000 / 0x8000 = 360, 0x10
/ 0x20 / 0x40 / 0x80 ... from readTrickInput, 0x100000 / 0x200000 extra spin), points +0x30, riderMask +0x34
(picked only when riderMask & rider +0x8C0), flags +0x38 (1 = half turn: stance flips; 2 = grab; 4 =
ground-only), mirrorIndex +0x3C (the entry reported while rider flag 0x20 is set). readTrickInput picks the
entry whose inputMask equals the gathered trickButtons once they have been held longer than the tkt parm.

| # | name | animRegular | animSwitch | inputMask | points | riderMask | flags | mirror |
|---|---|---|---|---|---|---|---|---|
| 0 | MELANCHOLY | 0x3000A | 0x3000A | 0x2 | 100 | 0xFECD | 2 | 0 |
| 1 | LIEN AIR | 0x30009 | 0x30009 | 0x2 | 100 | 0xFFFFFF33 | 2 | 1 |
| 2 | METHOD | 0x30002 | 0x30002 | 0x12 | 200 | 0xFF4F | 2 | 2 |
| 3 | SHIFTY | 0x3000F | 0x3000F | 0x12 | 300 | 0xFEB1 | 2 | 3 |
| 4 | INDY | 0x30005 | 0x30005 | 0x22 | 200 | 0xFF57 | 2 | 4 |
| 5 | TWEAK | 0x3000C | 0x3000C | 0x22 | 300 | 0xFEA9 | 2 | 5 |
| 6 | NOSE GRAB | 0x30008 | 0x30008 | 0x42 | 200 | 0xFFFF | 2 | 6 |
| 7 | TAIL GRAB | 0x30004 | 0x30004 | 0x82 | 200 | 0xFEFF | 2 | 7 |
| 8 | STIFFY | 0x3000E | 0x3000E | 0x52 | 250 | 0xFFFF | 2 | 8 |
| 9 | MUTE GRAB | 0x30003 | 0x30003 | 0x62 | 250 | 0xFFFF | 2 | 9 |
| 10 | STALEFISH | 0x30007 | 0x30007 | 0x92 | 250 | 0xFFFF | 2 | 10 |
| 11 | INDY NOSEBONE | 0x3000D | 0x3000D | 0xA2 | 250 | 0xFFFF | 2 | 11 |
| 12 | 180AIR | 0x1001E | 0x1001F | 0x1004 | 100 | 0xFFFFFFFF | 1 | 13 |
| 13 | 180AIR | 0x1001F | 0x1001E | 0x2004 | 100 | 0xFFFFFFFF | 1 | 12 |
| 14 | 360AIR | 0x10020 | 0x10021 | 0x4004 | 200 | 0xFFFFFFFF | 0 | 15 |
| 15 | 360AIR | 0x10021 | 0x10020 | 0x8004 | 200 | 0xFFFFFFFF | 0 | 14 |
| 16 | 540AIR | 0x30016 | 0x3001A | 0x101004 | 250 | 0xFFFFFEFF | 1 | 17 |
| 17 | 540AIR | 0x3001A | 0x30016 | 0x102004 | 250 | 0xFFFFFEFF | 1 | 16 |
| 18 | 720AIR | 0x30017 | 0x3001B | 0x104006 | 300 | 0xFFFFFFFF | 0 | 19 |
| 19 | 720AIR | 0x3001B | 0x30017 | 0x108006 | 300 | 0xFFFFFFFF | 0 | 18 |
| 20 | 900AIR | 0x30018 | 0x3001C | 0x201006 | 500 | 0xFFFFFFFF | 1 | 21 |
| 21 | 900AIR | 0x3001C | 0x30018 | 0x202006 | 500 | 0xFFFFFFFF | 1 | 20 |
| 22 | 1080AIR | 0x30019 | 0x3001D | 0x204007 | 3000 | 0xFFFFFFFF | 0 | 23 |
| 23 | 1080AIR | 0x3001D | 0x30019 | 0x208007 | 3000 | 0xFFFFFFFF | 0 | 22 |
| 24 | FRONT FLIP | 0x10022 | 0x10022 | 0x20004 | 100 | 0xFFFFFF01 | 0 | 24 |
| 25 | BACK FLIP | 0x10023 | 0x10023 | 0x10004 | 100 | 0xFFFFFF01 | 0 | 25 |
| 26 | PANDA TWEAK | 0x30024 | 0x30024 | 0x101004 | 300 | 0xFFFFFF01 | 0 | 27 |
| 27 | PANDA TWEAK | 0x30024 | 0x30024 | 0x102004 | 300 | 0xFFFFFF01 | 0 | 26 |
| 28 | ONE FOOT | 0x3001E | 0x3001E | 0x82 | 400 | 0xFFFFFF01 | 2 | 28 |

(The file's own +0x20 values (sometimes -1) are never read: trick start overwrites them.) Group-3 anim numbers are the grab / spin names of
section 17 (0x3000A melonchollie_8_1, 0x30009 lien_6, ...); 0x1001E..0x10023 are the group-1 180 / 360 airs and
flips.

**RiderAnim fields typed:** jumpCharge 0xE4 (s16), unkE6, trickButtons 0xE8, trickInputFrames 0xEC,
queuedTrick 0xF0, curTrick 0xF4, lastTrick 0xF8 (all TrickEntry *).

**Rider node-registry slots (not resolved).** Node_doCommand cmd 0x67 / 0x66 / 0x65 take one argument word from
the command record's argument pointer; a scan for `0x67, n < 40` (and `op & 0xFFFF == 0x67`) found no
instance in the raw ROM, in any of the 29 Yay0 blocks (decompressed), in boarder1..5.uso / penguin.uso Data
(per-character data: anim weights, no node stream) or in any parsed USO's Data / RoData. rom/player1..8.bin are
parm files (hpf / snf tags). So the stream that registers slots 0..39 is built in a form other than a flat
word array (most likely the node-list interpreter, ProcNodeList 0x55264, reading a tokenised / differently
encoded asset). Next step: decode nodelist_dispatch's input format, or trace which file SnowBoarder_ctor's
model load reads, then re-scan for that encoding.

**checkpoint.uso:** split write-up in docs/1080_COURSE.md section 7a (no config change).

**Next:** the node-list format for the registry slots; convert the remaining raw RiderAnim accesses
(readTrickInput E5C8 NM body, stateTrickWindup / Hold, the 0x110 / 0x114 / 0x118 / 0x124..0x130 spin fields)
on rideranim.h; name 0x110 (crash-recover flag) / 0x114 (trick phase: set 2 by stateTrickEnd); the SnowBoarder /
SnowAI / camera / course `_func_` names.

## 19. Run 494b: game_uso.c raw offsets, sun.h, spin fields

agent-g run 494b (branch agent-g on 8ee4c61a9). Hand edits d8799a9f7 and 1b158be15; pure rename 453152058 (5
names). All gated (PASS, 3288/3288, ROM identical); `objdump -d -r` plus .data / .rodata of every game_uso and
bootup_uso object, in both the matching and the NON_MATCHING build, was identical to the pre-run baseline after each
batch. Scratch: /tmp/claude-1000/g497/ (chk.sh = rebuild game_uso.c.o in both trees and diff against base/;
region.py = census split into compiled / NM / dead code).

**Census** (h492 census.py on game_uso.c): 715 -> 405. By region: compiled code outside NM wraps 192 -> 111,
NON_MATCHING bodies 189 -> 43, dead history (#if 0 / OLD_DECODE: cam_updateView cfe body 133, SnowAI 8CD8 / 7C1C /
steer old decodes, LensFlare BB8C old cfe) 251 unchanged. Most of the remaining compiled sites are comments and the
SnowAI_ctor / Parms-ctor marshalling bodies (parm-node stores through `s0 + K` alloc cursors).

**include/game/sun.h (new).** Sun (0x178): CamMNode base, sprite 0xC4 (Sprite: scaleX / scaleY = scl * fade,
unkC0 = mat), fade 0xC8, visibility 0xCC, screenX / screenY 0xD0 / 0xD4, depthImage 0xD8, visCallback 0xDC
(MemberCallback: vptr, obj, PMF), SunParms 0xEC (rot 0x104, ele 0x11C, scl 0x134, mat 0x14C int, col 0x164 four
floats). Correction to section 12: the tag order is rot, ele (Data 0xD5C / 0xD60), so rot is value 0x104 and ele is
0x11C. LensFlare (0x278): sprite 0xB4, LensFlareElem elems[10] 0xB8 (0x24: pos, color[4], size, image, flags (bit 0
= squared fade), minDot), sun 0x220 (create arg 2), LensFlareParms 0x224 (fin 0x23C, dlv 0x254, dfm 0x26C), numElems
0x274.

**RiderAnim fields:** spinAnim 0xB0, slowCrash 0x110, trickPhase 0x114 (1 trick, 2 ended / init, 0 riding),
jumpRepress 0x118, unk11C (f32, 1.0), lastStickDir 0x124, spinFrames 0x126, spinSteps 0x128, spinKind 0x12C (0 none,
1 / 2 = 180 / 360 one way, 3 / 4 the other, 5 / 6 stick flick up / down), backHits 0x130. **RiderInput.stickDir
0x7C** (pad_update: direction code 1..8 from the held direction bits 0x2000 up / 0x4000 right / 0x8000 down /
0x10000 left). **SnowAI** savedMax / savedNts / savedDts / savedNbf 0x4C8..0x4D4.

**Byte-safety notes.** rider->flags is u32: in RiderAnim_checkGroundSpin the u32 AND web became a different CSE
expression from the original int one (fixed with an (s32) cast). RiderAnim_checkJump read rider both as int and as a
pointer; a partial conversion changed regalloc, converting the whole function restored it. In SnowAI_scaleRiderMax a
member read of savedMax swapped the two lwc1, so that read stays char-based. SnowChaseActorCam_update's cfe body is
replaced by the 1DDC donor splice in both trees, so its conversion is compile-checked only.

**Renames:** SnowBoarder_mirrorFlip_0000E124, SnowBoarder_createColliders_0000CCE0 (8 jal SnowBCollider_ctor),
SnowAI_getRider_000097EC, RiderCam_update_00004948 / RiderCam_command_00004914.

**Next:** the remaining weak names (SnowAI 6FA8 / 7C1C / 8CD8 / 9B88 / A0E8, SnowBoarder DDCC / DF04 / E014 (three
SnowBRec3 slots from an imported table by mirror flag), E740 (a 2D u16 unswizzle, maybe not SnowBoarder),
SnowBoarder_func_0000CAE8 (also used as a data placeholder in bootup_uso_tail4.c / TimeGadgetParms_ctor: rename by
hand), the game_libs cam_func_0003xxxx); RiderAnim 0xD0..0xE0 (a third PMF at 0xD0, 0xD8 flag, 0xDC = 1 from init);
the SnowAI_ctor / Parms ctors through parm-node casts; the node-list interpreter (ProcNodeList 0x55264) for the rider
body-part registry slots (not started this run).

## 20. Run 502: SnowAI aim, DDM setters, the rider node list

**Renames** (renames.tsv has the evidence): SnowAI_pickFinishBranch (6FA8), SnowAI_aimAlongSegment (7C1C),
SnowAI_aimWeave (8CD8), SnowAI_isInSegmentWidth (9B88), SnowAI_isAboveSegmentFloor (A0E8),
SnowAI_isRivalInPath_000097EC (corrects run 494b's getRider: it is a meeting test, it does not return the rider),
SnowBoarder_setDefaultDdms / setReflectionDdms / setRiderDdms (DDCC / DF04 / E014: three `gfx_getDdm(&gGfxLib, id)`
records copied into the rider's DDM slots 0x8F4; DF04 runs right after light_setMirrorMatrix in SnowBoarder_display,
E014 restores after the reflection pass), SnowBoarder_grabScreenThumb_0000E740 (SnowBoarder vtable 0x83D0 slot 14:
a 64x32 u16 thumbnail, every 4th pixel of every 5th row of a 320-wide image from byte 0x9140, out of the main
ScreenWindow (gGfxLib + 0x240) buffer through its virtual slot 11, into this + 0x1C). The AI behaviour is written up
in docs/1080_PHYSICS.md section 8.

**Fields.** snowai.h: aimMode 0x74, weaveAim / weavePrev / weavePhase 0x84..0x9C, the ctor tunables 0xA0..0xE0
(leadLimit, sideBlock, lookAhead, turnGain, turnSpeedRef, minSpeed, aimRange, weaveLead, weaveLeadTime,
weaveSideScale; the rest unk with their ctor values). SnowAI_ctor's finalize stores and its 41 parm builds now go
through the struct (`parm[SNOWAI_PARM_*]`, SnowAIParm vptr / unk14 / value). rideranim.h: pendingState 0xD0
(startFinish / startTimeout queue stateFinish / stateTimeUp there; stateRide enters it when it is not the null
PMF), unkD8 (no game.uso writer; 0 lets blendWeight / blendWeightDeep fall back to stateRide / stateRideDeep),
rideContacts 0xDC (rider->contactCount sampled by stateRide, 1 from init). Byte-identical first try.

**The rider node list (ProcNodeList).** `SnowBoarder_loadBoardModel_0000B1B4` loads the boarder and board USOs and
then calls `ProcNodeList(list, a4, a3, &req)` on a static list at **bootup Data 0xABBC** (Sym 564). The format,
read from nodelist_dispatch / nodelist_skipBlock / nodelist_walk:
- a list is a word stream; each command word is `(nargs << 16) | op`, followed by nargs argument words
  (pointers are DataReloc words). The first word must be op 1000 (else the assert at Data 0x211C8).
- interpreter ops: 1003 = call a node-def function (arg 0) with the rest as its arguments (MNode_def,
  shape_cmdShape_00051520, skin_cmdSkinMgr / SkinShape / SkinAnim, anim_createAnimator); 1017 = run a sub-list;
  1010 / 1011 = run the block only if the arg equals the request's character (cat, +0x40) / board index (idx,
  +0x44); 1012 = only if (mask +0x48 & arg); 1014 ends a block, 1015 skips to the end of the block (else);
  1016 sets +0x38, 1008 a global, 1004..1007 set / clear bits in two global flag words, 1018 prints.
- any other op goes to the current node's virtual slot 7 (Node_doCommand): op 0 closes the current node (one per
  1003), 100 the node name (a RoData string), 103 registers the current node in registry slot N (the 40-slot
  shape-file registry, bootup Bss 0x3C058), 108 / 109 / 111 / 114 node parameters.
The earlier scan for `0x67, n` missed it because the word is `0x00010067` (nargs 1 in the high half).

Registry slots the list fills (MNode names from op 100; nesting from op 0):

| slot | node | SnowBoarder field |
|---|---|---|
| 28 | "top" (model root) | 0x844 |
| 27 | "board_a" | 0x824 (bodyNodes[1]) |
| 32 | unnamed MNode under board_a holding the board shape (board index 1..9: board USOs mod4..mod12) | 0x864 |
| 29 | a bootup-data shape (Data 0xA42C), mask bit 8 | 0x854 |
| 24 | "ikbase_a" | - |
| 20 / 21 | "waist_jnt_1" / "chest_jnt_1" | 0x838 (bodyNodes[6]) / - |
| 22 | **unnamed MNode under "chest_jnt_2": the head** | **0x874 camSource** |
| 31 | per-character shape on the head (characters 2..5 and 8) | 0x858 headShape |
| 10..13 | "armL_jnt_1".."armL_jnt_3", "armL_eff" | - |
| 15..18 | "armR_jnt_1".."armR_jnt_3", "armR_eff" | - |
| 0 / 1 / 2 | "legL_jnt_1" / "legL_jnt_2" / "legL_jnt_3" | - / 0x82C / 0x828 |
| 5 / 6 / 7 | "legR_jnt_1" / "legR_jnt_2" / "legR_jnt_3" | - / 0x834 / 0x830 |
| 34 | "boarder_a" (the skinned body) | 0x820 (bodyNodes[0]) |
| 30 | per-character SkinShape (mask bit 1; boarder USOs mod13..17) | 0x85C bodySkin |
| 33 | a bootup-data SkinShape (Data 0xC104, mask bit 2) | 0x860 |

The SkinMgr sub-list (Data 0xA924) builds one or two SkinMgrs per character; every joint gets SkinAnims for the
mask bits 1 / 2 / 4. A port can rebuild the rider skeleton from this table (joint names, parenting, the per-
character and per-board shapes) without the interpreter. The dump came from a throwaway script over
uso-data-sites.py's Census (DataReloc + RoData strings).

**Notes for other owners.**
- agent-b (post0b): proposed names for the game_libs camera helpers: cam_func_00036074 ->
  BallRotator_reset_00036074 (next to BallRotator_update_0003604C; identity quat, zeroed state, 200.0 radius);
  cam_func_00036694 -> math_projectOnPlaneNorm_00036694 (p projected onto the plane with normal n, normalised;
  degenerate -> a unit vector perpendicular to n); cam_func_00036A48 -> math_bestAlignedIndex_00036A48 (index of
  the arr[i] whose callback result has the largest dot with dir); cam_func_000372D4 -> cam_placeAttached_000372D4
  (copies a Vec3 to the attached object's node position, resets rot to (-90, 180, 0), virtual slot 3). Also the
  ProcNodeList arg struct Gl5591CArg could take the field meanings above (+0x0C / +0x10 / +0x14 = a1 / a1 / a2,
  +0x38 = 1, +0x40 cat, +0x44 idx, +0x48 mask).
- agent-h (bootup_uso): SnowBoarder_func_0000CAE8 is still a weak name, but it doubles as a data placeholder in
  bootup_uso_tail4.c (`SnowBoarder_func_0000CAE8[1] / [2]`) and in the TimeGadgetParms match_import, so it needs a hand
  rename. The SnowBoarder 0x844 / 0x864 fields (unk844 / unk864, used in bootup_uso.c mirrorFlip) can become
  `top` / `boardNode`.

**Next:** RiderAnim unkD8 writer (search bootup / game_libs for a +0xD8 store through rider->anim); SnowAI unkB8..unkD4
semantics (steer out flags); the 1008 / 1004..1007 global flag words of nodelist_dispatch; node ops 108 / 109 / 111 / 114.
(All four answered in section 21.)

## 21. Run 506: game_uso cleanup, open meanings, readability status

agent-g run 506 (branch agent-g on e6043cf4d). Commits: 694808660 (dead code removal), f7ea7f882 (field conversions
and meanings); both hand edits, no renames. Gate PASS after each (3288/3288, ROM identical); `objdump -d -r` plus
.data / .rodata of all 208 game_uso (both trees) and bootup_uso objects identical to the run baseline. Scratch:
/tmp/claude-1000/g506/ (chk.sh, dump.sh, region.py, live2.py = comment-stripped census that also counts the
`*(T *)((char *)p + K)` form).

**Dead code removed.** Every game_uso.c block no build path compiles: the cam_updateView cfe reference body,
SnowChaseActor_update's pre-NCC body, GAMEUSO_591C_OLD_DECODE (SnowAI_steer) and GAMEUSO_7C1C_OLD_DECODE
(SnowAI_aimAlongSegment), the SnowAI_aimWeave cfe NM body, LensFlare_display's old decode, the
RiderAnim_stateHopStart wrap doc, the NM-era histories and NON_MATCHING-only externs that served only those bodies,
and the unbuilt donor game_uso_ncc_7C1C_nm.cpp. Neither macro was defined anywhere. Each site has a one-line pointer
to e6043cf4d. game_uso.c 11190 -> 8612 lines.

**Census.** h492 census.py (all text): game_uso.c 381 -> 126 (dead 251 -> 0, compiled outside NM 87 -> 83, NM bodies
43 -> 43). Comment-stripped live2.py (counts `((char *)p + K)` too): compiled game_uso.c 171 -> 113, NM 37 -> 37;
`FW(p, K)` macro sites 59 -> 54. Donors unchanged (591C 24, mp72_B3C 8, ncc_D9CC 4).

**Meanings.**
- **RiderAnim.unkD8 has no writer.** A scan of every built object for `lw r, 0x840(x)` (rider->anim) followed by an
  access at 0xD8(r) found nothing in bootup, game_libs or any other USO; inside game.uso only blendWeight /
  blendWeightDeep read 0xD8(this). RiderAnim_init's clear of 0xBC..0x138 zeroes it, so both always fall back to
  stateRide / stateRideDeep: a dead hook (rideranim.h).
- **SnowAI 0xB8..0xD4** (snowai.h, with the out-flag bits of SnowAI_steer -> SnowAI_applyStickInput: 1 jump sequence,
  2 button 0x400 = useDParms, 4 stick up, 8 stick down / crouch, 0x10 finished, 0x20 / 0x80 table gestures, 0x40 a
  13-frame 0x100 press): crouchSteerRef 0xB8, stallYaw 0xBC, reachTime 0xC0, dParmsSteer / dParmsSteerScale 0xC4 /
  0xC8, rivalPathTime / rivalPathDist 0xD0 / 0xD4 (the 97EC donor's k / lim). Also unk70 -> **finishTimer**.
- **Node ops.** The SkinMgr vtable (Data 0x2C490) has Node_doCommand in slot 7, and Node_doCommand's case 108 (0x6C)
  just returns: **op 108 is ignored** (the list writes the mask bit 1 / 2 / 4 after each SkinMgr, a leftover tag).
  The MNode ops (MNode_doCommand, callees from `uso-data-sites.py calls`): **109 = scale** (cmd_readFixedVec3 ->
  math_mtxScaleRows), **110 = rotate** (math_mtxRotateEuler), **111 = translate** (math_mtxAddTranslation), 112 = copy
  a 4x4 matrix, 113 = flags |= 2, **114 = a short transform record** (pos s[0..2], quat s[3..6] / 32767, scale
  s[7..9] * 0.01; math_quatScaleToMtx4 into +0x30, copied to +0x70). The vectors read as fixed point / 10000 (inferred from the values, cmd_readFixedVec3 not read): on "top",
  character 1 gets scale 1.1 and +30 in y, characters 6 / 7 scale 1.2 and +50, character 3 scale 0.9 and -40.
- **The global flag words.** 1006 / 1007 set / clear bits of `gPolyFlags_3EEC4` (Bss 0x3EEC4), 1004 / 1005 of
  `gPolyGeomMode_3EEC8` word 0 (Bss 0x3EEC8). Every ShapeNode_ctor copies gPolyFlags into the new shape's +0x30
  (the bits BasePolyShape_doCommand ops 106 / 107 set / clear per shape) and the 8-byte gPolyGeomMode into +0x34:
  they are the render-flag defaults for the shapes built next. SnowBoarder_ctor sets gPolyFlags |= 8 and
  geomMode[1] |= 0x20000, &= ~0x80002 before the rider list and restores {0, 0x2A003} after. 1008 writes the word
  at Data 0x1EBD8 (sym 288; `bu_2c94_mode`, 6 from game_initDdm): MNode_addChild copies it into a flag-2 child's
  parent +0xB0 when that is 0, so it is the default DDM id new MNodes inherit.

**Readability status (5 functions, pre-readability 3e2ae9d53 vs now).**

| function | before | now | still reads badly |
|---|---|---|---|
| SnowAI_onLose (6ECC) | `game_uso_func_00006ECC`; `*(int*)(*(int*)((char*)a0 + 0x30) + 0x848) != 2`, stores to `a0 + 0x80` / `+ 0x40` | `if (AI(a0)->rider->controller != 2)`, `AI(a0)->unk80 = v; AI(a0)->targetNode = ...` | the three calls are `gl_func_00000000` placeholders; unk80 has no name |
| SnowAI_enterFinish (71A4) | `SnowAI_func_000071A4`; four raw stores | `aiState = 1; finishTimer = 0; if (unk4C4 > 0) ...` | unk4C4 (the scaled-parms countdown) and the placeholder call (probably SnowAI_restoreRiderParms: the steer donor has the same `restore; unk4C4 = 0` pair; not checked) |
| RiderAnim_stateTrickAir (F424) | `game_uso_func_0000F424`; `*(int*)(*(char**)((char*)a0 + 0xB4) + 0xA18) = 0; a0[0x114 / 4] = 1;` | `rider->unkA18 = 0; trickPhase = 1;`, named callees holdJumpLift / readTrickInput, `groundFlags & 1` | the `w + 0x170 / 0x698 / 0x31C` float pointers (kept for regalloc; comments name them) |
| RiderAnim_init (D458) | `FW(arg0, 0x114) = 2; FW(arg0, 0xFC) = 0x10000; FW(arg0, 0xDC) = 1; ...` | `trickPhase = 2; animSet = RANIM_GROUP_REGULAR; rideContacts = 1; unk104 = -1; hitKind = 0; unk11C = 1.0f` | the 0xF10 ROM probe after it (sp30 magic words) and the import_ calls |
| SnowAI_steer (591C) | 1000+ lines of NM decode history and an OLD_DECODE body in game_uso.c | a 5-line header and the splice placeholder; the logic is in game_uso_591C.c with named tunables | the donor keeps ~24 raw rider reads (`*(float*)(sub + 0x348)` = speed) and cfront-style temporaries; converting them needs a per-site regalloc check |

What still reads badly across game_uso.c: 259 `gl_func_00000000` / `game_uso_func_00000000` placeholder calls (the
callee is only in the reloc table: `uso-data-sites.py calls` names them); 19 stale NM-era comments ("NATURAL CEILING",
"Default build is INCLUDE_ASM", "No episode") on functions that are now exact; the SnowChaseActor*Parms_ctor /
camKey_init / game_ItemType_create parm-node stores (`o + 0x10` etc. through alloc cursors, 40 sites); the
three copies of the `head + 0x14` list-append idiom; 37 sites in NON_MATCHING bodies (Sun_display, readTrickInput).

**Next:** retarget the placeholder calls in game_uso.c to their real callees where the call is not a lever (the
report is name-blind; check each per .o); prune the 19 stale NM comments; a ParmNode struct for the
SnowChaseActor / camKey / ItemType parm builders; name SnowAI.unk80 / unk4C4 and RiderAnim.unk104 / unk11C / unk120.

## 22. Run 512: last placeholder calls, parm builders, field names

agent-g run 512 (branch agent-g on 856a0476b). Commits, all hand edits (no rename-symbol batches): 6dbfc6b94
(snowboarder.h unk844 -> top, unk864 -> boardNode, for agent-h; user SnowBoarder_mirrorFlip_0000E124), a8c098bdb
(game_uso placeholder calls, parm-builder fields, stale comments), 8db7533d2 (SnowAI / RiderAnim field names, 591C
rider fields). Gate PASS before each (3288/3288, ROM identical; name check 2023 -> 2033 named calls, 0 mismatches).
Scratch: /tmp/claude-1000/g512/ (chk.sh, dump.sh; py/jals.py prints a function's placeholder jals and their ROM
callees through name-placeholder-calls.py's Rom class).

**The 10 calls the tool left are named.**
- cam_readParms_00001644 (the verify compile differs from the real object, so the tool refused it): the six jals are
  camPath_new_00000608 / camPath_init_00000634 / camPath_read_00000724 and mem_new(40 = sizeof(CamList)) /
  camList_init_000007E0 / camList_read_000007EC. Each jal's a0 setup (zero, v0, the paths[i] reload; 40, v0, lists[i])
  ties it to one source site.
- SnowAI_ctor (4 sites, 86 jals): mem_new(0x4E0), Node_ctor, mem_new(0x3E0), mem_new(8). The INIT_ITER macro's two
  calls are named too (mem_new, Parms_addParm): the 82 macro jals are 41 x that pair in the ROM TextRelocs.
  `name-placeholder-calls.py check` masks #define bodies, so these two names are not machine-checked (said in the
  macro's comment).

**Parm builders.** SnowChaseActorCamParms_ctor / SnowChaseActorParms_ctor now store through the existing camera.h
CamParm / CamVec3Parm (vptr, value, unk14 / unk1C) and the *Parms name / unk04 heads; SnowAI_ctor's head through
SnowAIParms. No new ParmNode type was needed: CamParm / CamVec3Parm are the per-area parm node (same layout as
SnowBParm / SnowAIParm / CourseParm / SelParmF). SnowChaseActorLookParms_ctor is documented as cfront's inlined
ctor chain; its `arg0 == -8` is the null test of the member address `this + 8`. Not done: camKey_init_000003F8
onto CamKey, game_ItemType_create x3 (the head + 0x14 list append; XCALL(game_uso_func_051C28, ColourItem_ctor)
would name its absolute-placeholder calls).

**Stale comments pruned** (NM status / INSN_PATCH history on functions that are exact): math_dot4,
SnowChaseActor{Cam,Look,}Parms_ctor, SnowChaseActor_update, SnowAI_isRivalInPath (its "ground-contact" structural
decode was also wrong), SnowAI_scanNodes, the tail of SnowAI_ctor, RiderAnim checkJump / applyDamage /
stateSwitchStance / stateTrickEnd / stateTrickWindup / stateCrashRecover / startCrashSlide / startOllie / stateHopRise /
stateHopAir / stateFinish / stateStartIntro / hitFeedback. Still there: SnowAI_ctor's ~390-line archeology block
(game_uso.c above `extern char D_44F4_iterA_t`); it is flagged "historical" at its top but still says the default
build is INCLUDE_ASM. It needs a scripted delete (too long for Edit).

**Field names.**
- SnowAI 0x80 **atFinish**: SnowAI_isAtFinish's result, stored by onWin / onLose; no reader in game_uso C.
- SnowAI 0x4C4 **scaleTimer**: SnowAI_steer's rider-parms boost: 0 normal; dp < metric -> scaleRiderParms, 0x10000
  (armed); armed and metric < dd0 -> scaleRiderMax and dd1 frames of countdown; 0 / steer flag 8 / enterFinish ->
  restoreRiderParms.
- RiderAnim 0x104 **loadedAnim**: RiderAnim_update calls 0x76E78(player.mgr, player.anim) when anim != 0 and latches
  anim here (-1 from init).
- RiderAnim 0x11C **hitScale**: selectAnim scales the rider's 0xA1C..0xA24 hit vector by it; lnc parm in
  stateCushionIn, 1.0 from init / after a hit / stateCushionEnd.
- RiderAnim 0x120 **endTrickFlag**: set by endTrick, cleared by update when rider->pos.z < D+0x1F4; while set,
  update ORs 3 into the word at (import_80020098 + 0x138) + 0xB4 (what that object is, not known).
- game_uso_591C.c: rider->rival and rider->useDParms on fields. **rider->speed (4 sites) stays raw**: the field form
  moves FP registers (a struct member and `*(float *)(p + K)` are not the same expression to IDO here).

**DNode.** agent-b's include/gdl/dnode.h landed on main (e084d70f9) mid-run, after this run's base. Not switched
yet, for three reasons. (1) agent-g's tree cannot build it: dnode.h needs main's gadget.h (GdlParmF), and that gadget.h
renames PointsPopup fields whose users are also only on main; taking either means merging main. (2) The change can't be
made with compatibility macros: DNode stores vectors as `f32[3]` / AnimPose, and the users read SnowBVec3 members
(`rider->pos.z`, `vel.x`, `dir.y`), so the member type changes too. Field-name macros such as `#define pos ...` would also
hit every other struct with a `pos` field. (3) About 200 sites need conversion (in the 23 files that include
snowboarder.h / snowai.h / rideranim.h / camera.h: pos 65, vel 47, up 19, dir 17, side 14, angVel 9, orient 8, lastPos
6, ...). Each changed .o needs a byte check, because a member access and an array index are not always the same
expression to IDO (see the speed sites above). Plan: run from a base that has dnode.h, then
`SnowBoarder { DNode dnode; ... }`, with users moved to `dnode.vqs.trans[i]` / `dnode.vqs.quat` / `dnode.cvqs.*` /
`dnode.axes[0..2]` / `dnode.unk3A4`. Do it per file, checking each .o.

**Next:** the SnowAI_ctor archeology delete; camKey_init onto CamKey; ItemType_create x3 (struct + XCALL names);
snowboarder.h's DNode base onto gdl/dnode.h; the 0x76E78 callee name (anim data manager load) and what
import_80020098 + 0x138 is.

## 23. Run 516: SnowBoarder and ShpNode on DNode

**SnowBoarder.** include/game/snowboarder.h now starts with `DNode dnode;` (include/gdl/dnode.h) in place of the
run-470 SnowB* mirror fields. Old name -> field: pos / orient -> `dnode.vqs.trans` / `.quat`; lastPos / lastOrient ->
`dnode.cvqs.trans` / `.quat`; dparms -> `dnode.parms`; up / side / dir -> `dnode.axes[0]` / `[1]` / `[2]`; startPos ->
`dnode.unk3A4`; vel, speed, angVel, velDir, lastVel, friction, surfImp / surfSpd / surfVsc, unk38C keep their names
under `dnode.`. The rider-specific meanings moved into the `dnode` member comment. SnowBQuat, SnowBAccum,
SnowBVec3Parm and SnowBDNodeParms are deleted (no other users). docs/1080_PHYSICS.md section 1 has the map as a table.

- **The edg donors.** bootup_uso_ncc_B75C.cpp (updateOrient), bootup_uso_ncc_C234.cpp (procColl) and
  game_uso_mp72_B3C.cpp include snowboarder.h by relative path, with no -I include, and edg rejects the gdl
  headers' `&((T *)0)->f` asserts. Under `__cplusplus` the header therefore defines a layout mirror of DNode (AnimPose,
  GdlParmF / V3, DNodeParms, DNodeAccum, DNode; same member names, MNode base opaque, sizeof-checked). The C build
  checks the real offsets. If dnode.h changes a member name, change the mirror too.
- **Sites.** About 120 field uses in 7 files: bootup_uso.c (limitSpeed, updateDyn, update, the E2D0 twin, the cam
  node search, the r2 reset), bootup_uso_o2_E2D0.c, game_uso.c, game_uso_591C.c, and the three donors. The compiler
  found every typed use (the old names no longer exist). **No site had to stay raw for this change.** The 591C
  `*(float *)(sub + 0x348)` speed reads were already raw (run 512) and stay raw. Every touched object is
  objdump -dr identical: the 4 C TUs on both build paths, and the 3 donors built from HEAD and from the new tree.
  The "about 200 sites" estimate from run 512 counted every `pos` / `vel` / `dir` token, including other structs'
  fields and comments.
- **Not converted:** raw-offset rider accesses (`st + 0xDC`, `FF(r, 0x3A4 ...)` in bootup_uso_ncc_31C0.cpp,
  `I(0x3DC)` in bootup_uso_ncc_CAE8.cpp, bootup_uso_90CC.c's startPos stores). bootup_uso_ncc_8BD4.cpp keeps its
  own V3 rider view (`b->rider->pos`), which is not snowboarder.h. The bootup_uso.c comment lines 1356 / 1917 still say
  `rider->pos` / `rider->startPos` (agent-h's file; field-access lines only were in scope).
- **startPos stays `unk3A4` in dnode.h.** No game_libs DNode function reads or writes 0x3A4. Only SnowBoarder code
  does (the ctor stores the spawn point; the reset at bootup_uso_ncc_CAE8.cpp passes `st + 0x3A4` to a call), so
  the name belongs to the rider, not to DNode.

**ShpNode** (include/game/envobj.h) = `{ DNode dnode; s32 life; }`. ShpNode_func_00008FA8 copies dnode.vqs (trans,
scale and quat) into dnode.cvqs. The ctor's old `unk260 = 50` store is **dnode.parms.rad.value** (0x108 + 0x148 +
0x10; the DNode default is 150).

**game_uso.c.**
- The SnowAI_ctor history comment (397 lines) is now a 7-line summary. The D_44F4_iter*_t / _p / _f externs above
  the body are unused leftovers; they are mirrored in match_imports/context_game_uso.h and pinned in
  undefined_syms_auto.txt.
- camKey_init_000003F8 takes `CamKey *`. The old comment had look and eye swapped.
- game_ItemType_create x3: XCALL names (mem_new, ColourItem_ctor, list_append), checked by the gate (2936 named
  calls). arg0 is typed through ITEMTYPE() (gdl/item.h is now included in game_uso.c), and the attach is written
  with NODE(): the type's unk40 node becomes the new ColourItem's child.

**Absolute-token placeholders.** game_uso.c still has about 230 calls spelled with game_uso_func_0XXXXX tokens
(game_uso_func_055750 99, _04A188 51, _077C44 8, _071028 8, ...). They carry relocs, so the gate's check verifies
an XCALL name on them, but scripts/name-placeholder-calls.py `plan` only proposes names for `*func_00000000*`
tokens (PH_RE). Extending plan to the absolute tokens would name them all in one pass.

**Next:** that plan extension (or hand XCALLs; 055750 is mem_new at the three ItemType_create sites); a DNode view for the
.cpp raw-offset sites (31C0 RIDER_START, CAE8); the 0x76E78 callee and import_80020098 + 0x138 (run 512 list).

## 24. Run 523: game_uso raw sites, GameFlow import, AnimDataMgr_lookup

Census (compiled code, `*(T *)(p + K)` casts / accessor uses): game_uso 273 / 227 -> 125 / 212; bootup_uso 714 / 149
-> 710 / 139 (the two donors). Commits a0d7483f4, 16a0b554d, befe7756c, all hand edits, every changed object
objdump -dr identical.

- **import_80020098 is GameFlow** (include/game/input.h InputMgr). Every offset game.uso reads fits: +0x34
  nextFlowMode, +0x40 procState, +0x64 course, +0x138 dataMgr (RaceTracker), +0x148 backup (the match_imports
  CourseItem_drawLabel). The other import names are the same object named base + addend: import_800200CC = +0x34,
  import_80020110 = +0x78, import_800201D0 = +0x138. In C they are read as `INPUT_MGR(import_X).field` (same symbol,
  same addend). **`import_80020098 + 0x138`** is therefore GameFlow.dataMgr; RiderAnim_update (D204) sets
  RTF_FLUSH | RTF_POINTS in its hudFlags (+0xB4) while endTrickFlag is set and course == 0 (the trick-points HUD),
  and RiderAnim_endTrick passes dataMgr to the two score calls. GameFlow +0x7C (cam_pickResultView's win view 11) is
  still unnamed (input.h pad7C, not my header).
- **0x76E78 is AnimDataMgr_lookup** (game_libs 0x6280C). game_uso address tokens are game_libs offsets + 0x1466C
  (055750 = mem_new 0x410E4, 04A188 = the parm ctor 0x35B1C). The call stays a token for agent-a's CALL tool.
- **New fields:** SnowBoarder marker / markerLink / linkDir (0x954 / 0x958 / 0x9B8, SnowAI_updateMarker), unkA68
  (stateTrickWindup writes 1; no reader), child.parms.sta documented; camera.h LookAtNode (snowlookat + chase).
- **Converted:** RiderAnim state functions (ollie / hop / switch stance / trick windup / endings / crash recover),
  SnowAI updateMarker / rivalLeadZ / isAtFinish / isInSegmentWidth / timeoutRun, the Node vptr / name stores of 12
  ctors (`NODE(p)->vptr`), cam_reset / cam_command / cam_pickResultView, SnowAI_steer (591C donor: CourseMarker flg /
  ext / link, rival, flags, vel, pos, parms.nts, every dnode.speed read), the B3C donor's look-at and result-view
  reads, RiderAnim_selectAnim's rider reads (D9CC donor includes snowboarder.h), and in the bootup donors
  RIDER_START = dnode.unk3A4 (31C0) and SnowBoarder_reset's rider fields (CAE8).
- **Byte traps:** `x * member` products where the member is the second operand move FP registers; write them
  member-first (591C `dnode.speed * reachTime`). SnowAI_scaleRiderMax's savedMax resists both orders.
  SnowAI_steer's `*(unsigned int *)(self + 0x2C)` (level) must stay an unsigned raw read (the member, even cast,
  moves the code by 10 words). The `0 * (int)p` / `(int)p + 8` levers in 591C and the `p += 0x318` / `src += 0x70`
  bumps stay.
- **Left (125):** about 106 are data-symbol sites (`&game_uso_D_807FFxxx + K` Pair2 / parm-tag / double constants,
  the SnowAI_ctor `D_44F4_iter*` tag reads), not struct offsets. Struct sites left: CourseCam readParms' walking
  pointer (p + 0x1D4 / 0x158 = paths[i] / lists[i]), the 0x40-byte ColourItem subclass (+0x3C) in the three
  ItemType_create twins, the 8-byte {vptr, 0} member headers in Sun / LensFlare ctors, MemberCallback_invoke,
  savedMax, level, 591C's nts value read, the B3C `ob` store and the 43D8 / 7C1C rodata reads. About 50
  `a0[0xNN / 4]` int-index forms are not counted by the census but are still raw.

**Next:** a C++-safe rideranim.h (mirror like snowboarder.h) so D204 / D9CC / the other NCC RiderAnim donors can drop
FW / FF on `arg0`; the `a0[K / 4]` forms; GameFlow +0x7C (with input.h's owner); name the data-symbol sites
(Pair2 state tables) once the data-alias tooling covers game_uso.

## 25. Run 528: WorldRegistry.map, C++-safe rideranim.h, game_uso int-index sites

Census (compiled code, casts / accessor uses): game_uso 125 / 212 -> 115 / 87 (owner g 337 -> 202);
game_uso.c 107 -> 97, D9CC 6 / 89 -> 6 / 1, D204 1 / 23 -> 1 / 4, F13C 0 / 12 -> 0 / 3, F060 0 / 9 -> 0 / 2,
10A0C 0 / 4 -> 0 / 2. No compiled `a0[0xNN / 4]` int-index site is left in game_uso.c (comments only).
Commits 4d78ff5ee, 974491915, 2ba08a6da, ef44c768b, 792e449ab, 592f06809: all hand edits (no renames.tsv
lines), every changed object objdump -dr identical, gate PASS before each.

- **WorldRegistry.map** (course.h, 0x98, `struct MapProp *`): game_createMap's result (agent-h run 524).
  WORLD_MAP(w) now lives in course.h as `WORLDREG(w)->map`; the local guarded copies in bootup_uso.c /
  game_libs_tail.c are gone and bootup's game_init store is `WORLDREG(g)->map = (MapProp *)m`.
- **rideranim.h is C++-safe**: a `__cplusplus` branch with same-directory includes, an AnimPlayer mirror of
  gdl/anim.h (Node base opaque) and the ANIM_* constants; asserts are C-only; RA(p) is in the header. Donors
  include it after the s32 / f32 typedef line (copy D9CC's). D9CC, D204, F060, F13C, 10A0C use it.
- **RiderAnim per-frame dispatch is on 0xC8.** D204 (RiderAnim_update) calls the PMF at +0xC8 every frame
  (`struct H : A { pad2[200 - 44]; PM pm; }`), i.e. the field rideranim.h calls `nextState`, while
  setState (D5F8) stores +0xC0 together with the key that onKey waits for. So 0xC8 is the running state
  handler and 0xC0 the one entered at the key; the field names (state / nextState) may be the wrong way round.
  Not renamed this run: check AnimPlayer onKey (vtable slot 10 of RiderAnim) before swapping.
- **New / renamed fields:** RiderAnim.holdFrames (0xE6, was unkE6: statePreJumpHold counts it against the jht
  parm, statePreJump clears it), SnowAI.lastMarker (0x78, was unk78: the marker updateMarker found last),
  SunParms / LensFlareParms .head (was unk04). course.h ColourSubItem (0x40): the ColourItem subclass the three
  game_ItemType_create factories build (vptr import_8006ED80, +0x3C cleared).
- **The Sun / LensFlare "8-byte {vptr, 0} headers" are the inlined Parms base**: {name, list head}, name =
  "Parms" (Data 0xD54) / "LensFlare::Parms" (Data 0xD78). Written as SunParms / LensFlareParms .name / .head.
- **Byte notes (all verified):** `CamPath.keys[i]` / `CourseCam.paths[i]` in a loop strength-reduce to the old
  walking word pointer, and `keys[cnt + 1] = keys[cnt]` keeps camPath_read's base-first addu. CourseCam's list
  loop does not: indexing lists[i] after the read call rebuilds the pointer from i (extra sll / addu), so it
  keeps a walking `int *p` written `((CourseCam *)p)->lists[0]`. In F060 / F13C the second held test must read
  `*(u32 *)&input->held` (edg reloads; a plain second member read is CSEd). MemberCallback_invoke's virtual
  branch keeps `*(int *)(pair + 2)` for pmf.b (the member read reorders the block). `&rider->flags` replaces
  the startTimeout / startFinish `(char *)p + 0xA58` pointer bumps with the same bytes.
- **Left in game_uso (115 casts):** about 100 data-symbol sites (Pair2 PMF tables, parm tags, doubles, the
  SnowAI_ctor D_44F4_iter* reads), cam_pickResultView's GameFlow +0x7C (input.h pad7C, not my header),
  savedMax, MemberCallback's pmf.b, the D204 GameFlow import reads (input.h is C-only), rider +0x3DC (a
  SnowBoarder pad) in D9CC, and the camPath_read rotMode `a0 + new_var` lever.

**Next:** settle state / nextState (onKey); the remaining NCC donors on their headers (10694 RiderAnim_stateRide 21
and the F6D4 / E35C byte-offset views on rideranim.h; 57D8 SnowAI_update 19 on snowai.h, which needs the same
C++ treatment; B750 LensFlareElem_draw 17 on sun.h); a C++ mirror of the GameFlow fields in input.h (with its owner)
so D204 / B3C can drop the import offsets; name SnowBoarder +0x3DC.

## 26. Run 532: RiderAnim state fields settled, donors on headers, GameFlow.winVariant

Census (compiled code, casts / accessor uses): game_uso 114 / 83 -> 108 / 21 (owner g 197 -> 129). Commits on
agent-g (base 90d27efd3): 07d308feb (field swap), **9639698d3 (pure rename)**, eb41c7354, 4487fe8a2,
b37639091, 036f25cb8, 1b0a83cc2, 272e1c843. Every changed object objdump -dr / .data / .rodata identical; gate PASS
before each commit.

- **RiderAnim state / nextState were swapped; now `queuedState` (0xC0) / `state` (0xC8).** Evidence: the RiderAnim
  vtable (game.uso Data 0x115C, read from the ROM Data section + Data relocs; slot fn = vtable + 8 * slot + 0xC) has
  D438 at +0x5C, the slot AnimPlayer calls as onKey (game_libs_post1b.c: +0x58 delta / +0x5C fn). D438 disarms
  eventKey / blendEvent and copies 0xC0 into 0xC8; RiderAnim_update (D204) runs the PMF at 0xC8 every frame.
  Pure rename commit (4 renames.tsv lines): RiderAnim_reset_0000D438 -> RiderAnim_onKey_0000D438,
  setNextState_0000D5BC -> enterState_0000D5BC (writes the running state now), setState_0000D5F8 ->
  queueState_0000D5F8 (writes queuedState and arms the key, -1 = at blend-in end), clearNextState_0000D5DC ->
  clearState_0000D5DC. Other vtable slots: 2 display D634, 3 update D204, 8 readParms D418.
- **SnowBoarder.riding (0x3DC):** 1 from SnowBoarder_reset, stateRide, stateRideDeep; 0 when D9CC starts a hit /
  crash anim. No .s loads +0x3DC from a rider (write-only).
- **C++-safe headers:** snowai.h (same-directory include, C-only asserts), sun.h (plus a Sprite mirror of
  gdl/sprite.h), input.h (InputMgr already compiled under edg; added a RaceTracker prefix mirror with hudFlags and the
  RTF_* bits, since gdl/race.h is C-only). Donor include recipe unchanged: the s32 / f32 typedef line, then
  `#include "../../include/game/<h>.h"`.
- **Donors on headers:** 10694 stateRide (21 -> 3), 10840 stateRideDeep, F6D4 / E35C (byte-offset view macros gone),
  57D8 SnowAI_update (19 -> 0), B750 LensFlareElem_draw (17 -> 4; params named elem / sprite / sunPos / dir / fade),
  D204 (GameFlow course / dataMgr->hudFlags via INPUT_MGR; the running state read as `PMF(RA(a3)->state)`, the H pad
  struct gone), F060 / F13C child() on rider->input.
- **GameFlow +0x7C = `winVariant`:** RaceProcess_leave (flow modes 4..6: 1 -> victory seq variant 2) and
  cam_pickResultView (win -> result view 11); RaceProcess_reset clears it. No other store found in any built object
  (scan: sw imm 124 in every function that references a GameFlow token) - the setter may be in a mode USO through a
  register base; open.
- **LensFlareElem.flags** LFELEM_FLAG_*: 1 squared fade, 2 size *= fade, 4 pos += fade * 400, 8 use fade (else 1.0).
- **Byte notes:** 57D8 needs `(u32)rider->controller == 2` (the s32 compare colours the const 2 into a2 and loses the
  branch-likely delay fills). `*(T *)&obj->field` (address form) keeps the bytes where the plain member read moved
  them: SnowAI_scaleRiderMax savedMax, 591C self->level. MemberCallback pmf.b reads as `((Pair2 *)pair)->b`. 591C's
  `*(float *)((int)axis_src + 16)` (rider->parms.nts.value) still moves the code as a member: kept raw.
- **Left in game_uso (108 casts / 21 macro uses):** data-symbol sites (Pair2 PMF records `AT(PM, &D_807FFxxx, K)`,
  RoData doubles / floats, the SnowAI_ctor D_44F4_iter* reads, 6FA8 Handle pointers, 43D8 FLT_MAX pair),
  B3C's `*(char **)((char *)ob + 0)` store (edg lever), 591C axis_src, the vtable-entry reads in MemberCallback_invoke,
  and NON_MATCHING-only bodies (not counted).

**Next:** name the data-symbol sites (the Pair2 state table 0xDB0..0xF60 as per-state PMF aliases, so
`AT(PM, &game_uso_D_807FF4B0, 0xEC0)` reads as the state it enters; needs uso-data-sites.py support for game_uso);
find GameFlow.winVariant's setter; bootup's SnowBoarder_reset `I(0x3DC)` (agent-h) can use rider->riding.

## 27. Run 538: game.uso data sites in uso-data-sites.py, RiderAnim state PMFs named

Census (compiled code, casts / accessor uses): game_uso 108 / 21 -> 79 / 21. Commits on agent-g (base dc60769de):
acf1b9889 + 5295c7939 (tool changes: uso-data-sites.py), b78a15d48 (tool output: game_uso_data.h + `spell`),
c1830919d (hand edit: macro-hidden callees as macro arguments), d4159e75e (tool output: name-placeholder-calls
plan). Gate PASS before each; every changed object objdump -dr identical.

- **uso-data-sites.py `--uso game`**: game.uso inner header 0x7CC900; its Text is
  build/assets/game_uso_block1_yay0.lnk.o (game_uso.c.o after drop-text-word 0xC0F0; the .c.o itself is 4
  bytes off past 0xC0F0). Base Syms: 1 Text, 2 RoData, 3 Data, 4 Bss (bootup: 3 / 1 / 2 / 4; now found by kind).
  Named Data objects (kind 2): 20 (sym 5, 97..102, 155..159, 198, 201..206, 344); Bss objects 199 / 200 / 266.
  `sites` / `census` / `object` work; e.g. `--uso game object D:0xCE8`.
- **Named section offsets** live in include/game/game_uso_data.h as integer constants
  (`#define kPmf_RiderAnim_stateRide 0xE40 /* Data+0xE40: PMF -> RiderAnim_stateRide */`). The per-address zero
  symbol stays (it is part of the matched spelling); only K gets the name, so sites read
  `AT(PM, &game_uso_D_807FF4B0, kPmf_RiderAnim_stateTrickWindup)`. `check` (bootup output unchanged plus one
  game.uso line) verifies every constant use has a Data-base site with that K, and the `PMF -> FUNC` target
  against the DataReloc at K + 4. `pmf-table` emits the defines; `spell FILE.. --write` respells the literals
  (handles `extern "C"` donor definitions).
- **RiderAnim state table** Data 0xDB0..0xF60: 54 PMF records {s16 delta = -1, s16 index = 0, fn}; 0xDC8 is the
  all-zero null PMF (`kPmfNull_DC8`). Order (by K): StartIntro, StartWait, Stopped, null, HopStart, HopRise,
  CushionIn, HopDrop, HopAir, HopLand, CushionEnd, Cushion, RideBlendIn, OllieRise, OllieTakeoff, OllieLand,
  OllieHang, OllieDrop, Ride, RideDeepBlendIn, Row, RowOut, RideDeep, RowIn, BrakeBlendIn, BrakeDeep, Brake,
  CrashRecover, ResumeRide, SwitchStanceEnd, SwitchStance, PreJumpCancel, PreJumpHold, PreJump, TrickWindup,
  TrickRelease, TrickAir, TrickHold, TrickStart, TrickEnd, FlipToRide, StartIntroEnd, Idle, Ending2, Ending3,
  Ending1, Finish, GoalNormal, GoalWinOM, GoalWin, GoalLose, TimeUp, TimeUpLose, Stand.
- **Macro-hidden placeholder calls fixed** (coordinator item): game_uso_7C1C.c's eight Vec3 XZ macros take
  NEW (mem_new), 3AC0's BLK takes ADD, bootup_uso_ncc_4948.cpp's SNAP takes SETPOS
  (math_mtxAddTranslation); then plan --write named 22 + 12 + 5 calls.
- **GameFlow.winVariant setter: none found ROM-wide.** Scan over every module's TextRelocs to bootup Bss 0xF8:
  no LO16 site with imm 0x7C; the only store at +0x7C through a register loaded from a GameFlow site (+-0x400
  bytes) is RaceProcess_reset's clear. The other hits (titproc demo ctors, viewrec 0x1C70 / 0x4620 / 0x4968,
  gui rows) are other objects. Unless it is written by a bulk copy (Backup restore / struct assignment) or
  through a pointer returned by a getter, it is always 0 (the variant-2 victory sequence and result view 11 are
  dead paths).

**Next:** the other game.uso data (Parms name strings 0xD54 / 0xD78, parm-tag words, RoData doubles) as
checked constants (a `"text"` / value claim in the comment, like GL_DATA_STR); the bootup ncc donors
(D900 41, 55A0 40, CFA0 39, 1A44 24, FC28 24, 4948 18, now owned by g) on snowboarder / gdl headers.

## 28. Run 543: bootup C++ donors on headers, game.uso strings / tags / constants

Census (compiled code, casts / accessor uses): bootup_uso 311 / 134 -> 237 / 67, game_uso 79 / 21 -> 33 / 21;
C++ donors 828 -> 684 sites (83 -> 81 files with any). Commits on agent-g (base 9f341164f): e4006e31e (hand edit:
six donors + headers), 5e22d234a (tool change: uso-data-sites.py const-table / value claims), 53f11baf3 (tool output:
79 constants + 79 respelled sites). Gate PASS before each; every changed object (main and non_matching) dumped with
~/.local/bin/mips-linux-gnu-objdump -dr / -s (non-empty) and identical.

- **Donors on headers:** D900 SnowBoarder_handleMsg 41 -> 0 and CFA0 SnowBoarder_display 39 -> 2 (snowboarder.h,
  `self` typed `SnowBoarder *`; CFA0's position words passed as int args read as
  `*(int *)&st->dnode.vqs.trans[i]`); 4948 RiderCam_update 18 -> 2 (camera.h RiderCam + rider->dnode.vel; the mode
  compares stay unsigned via `*(unsigned *)&obj->mode`); 1A44 24 -> 4 (gdl gfxlib / window / dlctx + camera.h:
  curWindow->dl, gfx.cur / mtx.cur, worldScale[], CamWindow cam->mnode.world[3]); FC28 24 -> 11 and 55A0 40 -> 28
  (NODE(p)->vptr / ->name; onQuit's call through VT_SLOT(p, 11) keeps its -O0 DAG-share bytes).
- **snowboarder.h:** shade[4] (0x9E8, groundColor / 2 / 255 + alpha 112 / 255 for a gfx colour call), unkA40
  (display's context query result), unkA44 (1 on the lit path).
- **C++-safe gdl headers:** node.h and window.h offset asserts under `#ifndef __cplusplus`; window.h includes
  "node.h" by relative path under __cplusplus (donors build without -I include).
- **uso-data-sites.py `--uso game const-table [--write]`:** names the strings (kStr_<text>_<K>: "Parms" groups incl.
  Data 0xD54 / 0xD78 "LensFlare::Parms", class names, assert texts), 3-letter parm tags (kTag_<tag>_<K>) and the
  float / double constants a site casts (kRoD_0p1_158 = RoData f64 0.1, kRoF_FLT_MAX_110, kDataF_60_1098); the type
  comes from the site's own `*(f64 *)` / `AT(double, ..)` cast. `check` verifies the value claim (`"text"`,
  `f32 V`, `f64 V`) bit-exact against the section bytes. The block between the const-table markers in
  game_uso_data.h is generated; `spell --write` then respells the sites.
- **Left:** 1A44's a0 +0x2C..0x38 (int position + DL word: does not fit envobj.h's U64BGWall mesh / arg30, so the
  owner class is doubtful); FC28 QuitProcess +0x44 / 0x48 and PauseMenu colours / locked (guimenu.h is C-only, h's);
  55A0's TreeTmpl / Tv1Tmpl fields (envobj.h is C-only, includes dnode.h / coll.h by -I path); game_uso data sites
  without a cast type (D204 `F(&D_00000000, 0x1F4)`, the pi at RoData 0x90) and the "?" sites whose placeholder
  token does not match the reloc's (macro-built: Sun_display, CourseMarkerTmpl_create, SnowAI_ctor).

**Next:** the next C++ donors (485C 11, C234 10, B1B4 8, 11B5C / 7328 7); envobj.h / guimenu.h C++ guards with
their owner (h) for 55A0 / FC28; the remaining game_uso Data words (0x548 node table, 0x1098.. rumble records).

## 29. Run 551: bootup donors 485C / 11B5C / 7328, game.uso RoData constants, U64BGWall_display

Census (compiled code, casts / accessor uses): bootup_uso 185 / 37 -> 172 / 27, game_uso 33 / 21 -> 7 / 21;
C++ donors 378 -> 353 sites (73 -> 70 files with any); weak names 50 -> 49. Commits on agent-g (base 1149e6ece):
d4f813c35 (hand edit: three donors), 16e056df7 (tool change: uso-data-sites.py), b27516760 (tool output: 26
constants + 26 respelled sites), 6adcf7dea (pure rename). The gate passed on the tree before each batch was
committed. ~/.local/bin/mips-linux-gnu-objdump showed identical .text and relocs for each changed donor .o, and
identical -dr / -s output for bootup_uso.c.o in both the main and non_matching builds.

- **55A0 / FC28 after the coordinator's landing:** 55A0 has 5 sites left (DROOT +0x34 and the n2 / n3 / n4 node
  records it builds). FC28 has 8, all PauseMenu_create's two colour quads at GuiMenu +0x4C / +0x5C. They need
  `f32 selColour[4]` / `rowColour[4]` in place of guimenu.h's `unk4C[0x20]` (h's header).
- **485C Mountain_display:** `Mountain *` (course.h) plus the root alias as `CamWindow *` (->cam->mnode.world[3] =
  the eye). gGfxLib.worldScale has to stay base + offset (`GFX_WORLDSCALE(i)`). Every member spelling
  (`.worldScale[i]`, `*(float *)&->worldScale[i]`, a `GfxLib *` local, base + offsetof) either folds 0x128 into
  the lui / addiu pair or re-bases each load. The `*(int *)&p->field` lever does NOT cover a member of a global
  ARRAY object read at constant indices.
- **11B5C** input_pauseRacePads / unpauseRacePads are on GAMEFLOW() (0 left). **7328** EnvSettings_load is on
  ENVSET() (needs course.h before envobj.h under C++). The `func_00000008 + 0x34` read is GameFlow.gameMode
  (alias value 8 + 0x34 = 0x3C), so INPUT_MGR() would change the addend.
- **uso-data-sites.py:** GSITE_RE now also accepts per-site zero aliases `D_<hex>_<name>` (SnowAI_ctor's
  D_44F4_iter*, 43D8's D_43D8_fmin / fmax); the reloc placeholder must still be that token. `const-table --write`
  now keeps the lines an earlier --write generated. Before this fix a second --write rewrote the block with only
  the new constants, which dropped all 79 old ones. -FLT_MAX is now named kRoF_mFLT_MAX_<K>.
  `--uso game selftest` already failed on main ("USO_FORMAT.md census changed?" in the bootup half); this run did
  not touch that, and the gate does not run it.
- **SnowAI_ctor:** the 24 parm-default RoData floats are named (kRoF_m10000_9C .. kRoF_m100000_F8). Still left:
  the 41 tag-pointer reads `*(char **)(&DB + 0x6E8 + 4 * IDX)`, which are inside the INIT_ITER macro and reach
  Data object sym102 (+0x110..), not a section base.
- **U64BGWall_display** (was U64BGWall_func_00001A44): it sits in vtable slot +0x1C (display) of Data 0x6648,
  which U64BGWall_ctor stores as its vptr. The body is guPosition(rot 0x2C / 0x30 / 0x34 in degrees, 1, eye *
  worldScale) followed by gSPDisplayList(+0x38). game_createBGBox calls `U64BGWall_ctor(0, tex, 0, 90, 0)` ...
  `(0, tex, -90, 0, 0)`, so envobj.h's `mesh` / `arg30` / `arg34` are really rotX / rotY / rotZ (s32 degrees), and
  `unk38` is the display list the ctor builds. That header is h's, so the fix goes to h. Once fixed, the donor's 4
  sites can switch over.

**Next:** C234 SnowBoarder_procColl (10 sites). Its collision-world global `*(s32 *)&D + 0x84` and
gInputMgr_c234_g8 + 0x2C need their owners proven first, and the frozen-home levers make the body fragile.
After that: B1B4 (Bb4Bank's ctor stores are class-local W() / H(), so it needs a real class), 76F4 Tv1_display
(the 0x88 Tv1 instance has no struct yet), CAE8, and the game_uso 0x548 node table and 0x1098 rumble records
(not started this run).

## 30. Run 555: U64BGWall fields, Tv1, ScreenThumbMat, input.h on race.h, GameFlow.titleFlags

Census (compiled code, casts / accessor uses): bootup_uso 151 / 27 -> 136 / 22, game_uso 7 / 21 (unchanged);
C++ donors 230 -> 211 sites (67 -> 65 files with any). Commits on agent-g (base e10de4848): fa101a552 (hand edit:
input.h), 9b8e2ff8c (hand edit: envobj.h + five donors), 67822c50a (pure rename). Gate PASS before each commit
batch; every changed object (donors, titproc_uso_5DC.c.o, bootup_uso.c.o main + non_matching) dumped with
~/.local/bin/mips-linux-gnu-objdump -dr / -s (non-empty) and identical to the pre-run build.

- **NCC donors have no header dependencies in the Makefile:** after a header edit, `rm` the donor .o's before
  `make <obj>`, or the comparison runs against the stale object (it "passes").
- **envobj.h U64BGWall:** rotX / rotY / rotZ (s32 degrees, ctor args 2..4) and displayList (+0x38, the Gfx list
  the ctor builds). 1A44 U64BGWall_display takes `U64BGWall *self` (needs course.h before envobj.h). 4 -> 0.
- **envobj.h Tv1** (0x88 instance from Tv1Tmpl_create): the SNode layout spelled flat (edg cannot include
  gdl/mnode.h), C-asserted `sizeof(Tv1) == sizeof(SNode)` plus pos / radius offsets. 76F4 Tv1_display on it: the
  cull query's int words are `*(int *)&self->pos[0]` / `[1]`; 6 -> 0.
- **ScreenThumbMat** (was "Bb4Bank"): B1B4's lazily built object is a Mat subclass. Bb4Base = BaseMat
  (BaseMat_init_000517E4 ctor, BaseMat_vtbl Data 0x20640), Bb4Mid = Mat (Mat_vtbl 0x1FBEC), own vtable at Data
  0x8440 (inside the span gl_data.h attributes to SnowBoarder_vtbl): slot 0 = ScreenThumbMat_grab_0000E740 (renamed
  from SnowBoarder_grabScreenThumb_0000E740), then BaseMat_hostioParms, Mat_print, gfx_decodeMatCmd,
  BaseMat_vslot4. The registry `{tbl[5]; n}` at gGfxLib + 0x148 is GfxLib.frameStartCbs / nFrameStartCbs, so
  gfx_start refreshes the 64x32 RGBA16 texture (texels = mem_new(0x1000), WRAP_S | WRAP_T, geomFlags 0x402C4B)
  every frame. The ctor stores are BaseMat fields now; the class names stay Bb4* because `__vtbl__7Bb4Bank` etc.
  are pinned symbols.
- **C234 SnowBoarder_procColl (10 -> 6):** Bss+0x50 = gCourseColl (the CollShape *); its +0x84 reads (4) are
  CollShape.shape but gdl/coll.h is C-only (includes gdl/node.h by -I path, unguarded asserts) - needs its owner.
  gInputMgr_c234_g8 is pinned at 8 and its reloc is GameFlow + 0x34, so `if (nextFlowMode != 2)` (the light
  easing is skipped in flow mode 2) is spelled `INPUT_MGR(gInputMgr_c234_g8[-8]).nextFlowMode`. Left: Data
  0x8A78 (the by-value 4-byte arg, just before "Player Pos Reset"), Data sym302 (+0x7768, 4 bytes, unnamed) and
  the returned record's +0x30 position.
- **CAE8 SnowBoarder_reset (6 -> 1):** shade[4], riding, localUp.z = 1, flags = initFlags, SNOWB_FLAG_20. Left: the
  node name +0xC (the DNode mirror has no Node fields) and the s16 table at +0x8C6 indexed by board.
- **input.h** includes ../gdl/race.h under C++ (the RaceTracker prefix mirror is gone); C++ includers need the full
  s16 / f32 typedef line (11E00 had only s32).
- **GameFlow +0x8C = titleFlags:** only store is tit_procMain state 0 (0x820000 = bits 23 | 17, the
  GameDemoProcess_ctor flag layout). No load in any built object: write-only.

**Next:** game.uso Data: the 0x548 node table, the 0x1098 rumble records, SnowAI_ctor's 41 INIT_ITER tag-pointer
reads (not started this run); C234's +0x84 once coll.h is C++-safe (ask its owner); 55A0 / FC28 still wait on
envobj.h / guimenu.h fields from h.

## 31. Run 558: Tv1Callback, game.uso marker tags / rumble patterns / parm tags, the C234 marker query

Census (compiled code, casts / accessor uses): bootup_uso 136 / 22 -> 124 / 19, game_uso 7 / 21 -> 4 / 21, ROM-wide
1370 / 176 -> 1355 / 173; C++ donors 211 -> 194 sites (65 -> 62 files with any). Commits on agent-g (base 2fe63c692):
6dde93b50 (hand edit: envobj.h + FC28 / 55A0), 0eeb60915 (hand edit + `--uso game spell --write` output:
game_uso_data.h + 15 respelled sites + INIT_ITER), 6d4b1c4ba (hand edit: C234 / CAE8 + two pins). No renames. The
gate passed on the tree before each commit; `--uso game check` 0 mismatches.

- **FC28 PauseMenu_create:** the colour quads are GuiMenu.selColour / rowColour (h run 556). The target keeps
  `addiu s0,a0,0x4C` and stores at 0..12(s0), so `s` stays the quad pointer: `((f32 *)s)[i]`. FC28 has no sites
  left. QuitProcess.unk4C is the Process tail word (RaceProcess.unk04C = init arg 3); unknown, so it keeps its name.
- **envobj.h Tv1Callback / Tv1Tmpl.stepCallback (+0x48):** 55A0 builds a 16-byte member-function callback in place
  as a 3-level cfront cascade: base vptr Data 0x7528 (slot 1 `__pure_virtual_called`), obj = the Tv1Tmpl,
  pmf = Data 0x7520 {0x0000FFFF, Tv1Tmpl_func_00007D04}, then the concrete vptr Data 0x7770 (slot 1
  MemberCallback_invoke_00007BF4). It is the bootup twin of sun.h's MemberCallback. To read the Data words plus
  their DataReloc targets, load scripts/uso-data-sites.py as a module and walk `Census(...).secs['Data']` /
  `['DataReloc']` (the venv python is needed for crunch64).
- **55A0's last site:** `OI(DROOT, 0x34)`. D_55A0_root is Data 0x776C, the ItemMgr pointer (course.h), so the
  store is ItemMgr.unk34 (ctor arg 2) = the item-class mask item_registerTemplates computes. gdl/item.h includes
  gdl/node.h by -I path, so the donor cannot include it until item.h's owner makes it C++-safe.
- **game_uso_data.h, hand constants (outside the const-table block):** kMarkerTypeTags_548 (12 DataReloc pointers
  to RoData 0x60..0x8C: mrk, mk1..mk9, mkl, mkr in MARKER_* order; the readers load the tag word through the
  pointer and pass it by value), kMarkerTypeTag_mkl_570 / _mkr_574 (6FA8), the rumble patterns
  kRumble_hit1_109C .. hit5_10DC (0xFF-terminated per-frame motor bytes, PadCtl.rumble), kSnowAIParmTags_6E8
  (the 41 parm tags are the 4-byte STRINGS themselves at Data 0x6E8..0x788, not pointers; INIT_ITER reads tag IDX
  at `kSnowAIParmTags_6E8 + 4 * IDX`, so the TMPL_OFF argument is gone) and kVtbl_FloatParm_3C8. `spell` does not
  see sites inside a #define or behind a placeholder token that differs from the reloc's (INIT_ITER, the
  CourseMarkerTmpl_create 0x3C8 site), so those were edited by hand; `check` still verifies them per function.
- **C234:** Data 0x8A78 is the string "mrk": the 151-frame airborne reset calls
  ItemMgr_queryType(MarkerMgr = Data 0x7768 Sym 302, "mrk", pos, 0) and moves the rider 200 above the returned
  CourseMarker.pos. Pins: sTag_mrk_8A78 = 0x8A78 and D_C234_markerMgr = 0. The tag site's .o reloc changed from
  func_00008A40 + 0x38 to sTag_mrk_8A78 + 0 (lo16 immediate 0x38 -> 0 in the unlinked .o). The linked ROM and the
  objdiff report are unchanged. C234 has 4 sites left, all CollShape.shape (+0x84); coll.h is not C++-safe in this
  base.
- **CAE8:** NODE(st)->name (gdl/node.h, relative include) and RIDER(st)->board. Left: `((short *)(st + 0x8C6))[board]`.
  0x8C6 is the low half of `character` (u32 at 0x8C4), so the per-board s16 table overlaps the character
  word. The real layout (s16 fields at 0x8C4?) needs the ctor's stores checked.

**Next:** C234's 4 CollShape.shape reads once coll.h has its C++ guard (agent-b); 55A0's ItemMgr.unk34 (needs
item.h C++-safe; ask its owner); CAE8's 0x8C6 table. Then the census donor table for g's files: game_uso B750 (4
accessor), 10694 / E35C / F6D4 (3), 10840 / 10A0C / F13C / 6FA8 (2). Also the remaining "?" game.uso sites
(Sun_display, CourseMarkerTmpl_create's tag words +0x6B0 / +0x6C4).

## 32. Run 563: C234 CollShape.shape, SnowBoarder.boardBin, Sun / CourseMarker data constants, pattern H

Census (compiled code, casts / accessor uses): bootup_uso 124 / 19 -> 120 / 19, game_uso 4 / 21 (unchanged), ROM-wide
1252 / 130 -> 1245 / 130; C++ donors 194 -> 190 sites (62 -> 61 files with any). Port audit: H 14 -> 9 (A 286, B 81,
C 19, D 218 unchanged). Commits on agent-g (base 953efeb95): 28f4408ee (hand edit: C234 / CAE8 / snowboarder.h),
5ddb61fce (hand edit: game_uso_data.h + Sun_display respell), 87d756f76 (hand edit: pattern H). No renames. Gate PASS
before each commit; `--uso game check` 0 mismatches.

- **All-object check without .mdebug:** a clean HEAD build vs a clean edited build (main + `make
  non_matching_objects`, 1268 .o) can be compared with `objdump -dr -s` only after dropping the `.mdebug` /
  `.comment` contents: edg donors embed per-compile ids and timestamps there (`__edg_..._6afaf927`), so two builds of
  the SAME source differ. .mdebug also carries line numbers, so adding a line to a donor shows up there only (the
  linked ROM never contains .mdebug). Keeping the donor's line count (C234 merged a two-line comment) keeps even
  that identical.
- **C234:** `#define COURSE_COLL (*(CollShape **)&gCourseColl)` + gdl/coll.h by relative path; the four +0x84 reads
  are `COURSE_COLL->shape`. 0 sites left.
- **snowboarder.h boardBin (0x8C8, s16[10]):** no ctor store touches 0x8C8..0x8DB. SnowBoarder_readParms
  (bootup_uso.c, h's) reads a stream count n and then n s16s at 0x8C8; SnowBoarder_reset's `lh 0x8C6(st + board*2)`
  is boardBin[board - 1] (board is 1-based), so nothing overlaps `character`. CAE8 is on
  `RIDER(st)->boardBin[RIDER(st)->board - 1]` (same bytes). 10 is the span to `camera`, not a proven count.
  readParms could use `SNOWB(a0)->boardBin` (h).
- **game_uso_data.h, hand constants** for the "?" sites (token differs from the reloc's, so const-table / spell
  skip them): kRoD_0p98_120 / kRoD_0p7_128 / kRoD_0p3_130 / kRoD_0p1_138 (Sun_display: hidden above 0.98, fade
  eased over 0.7..1.0 / 0.3, drawn above 0.1), kStr_CourseMarker_Parms_6B0, kTag_wid_6C4 / kTag_ext_6C8 /
  kTag_flg_6CC, kVtbl_IntParm_410 (DataReloc 0x41C = game_readIntParm_000039F8; the float / vec3 / quad parm
  vtables are 0x3C8 / 0x3E0 / 0x3F8). Respelled: match_imports/Sun_display.c and the NON_MATCHING Sun_display /
  CourseMarkerTmpl_create bodies in game_uso.c. CourseMarkerTmpl_create.c (a) can switch its 0x6B0 / 0x6C4 /
  0x6C8 / 0x6CC / 0x410 / 0x3C8 sites to these names.
- **Pattern H (5 of g's 8):** sun.h Sprite.children (void **), envobj.h Tv1.next (struct SNode *), TreeTmpl.next
  (struct ItemType *), course.h ColourSubItem.vptr and CourseMarker.vptr (char *). Each verified alone by a clean
  rebuild + all-object diff. Left: CourseParm / CourseFParm .vptr and WorldRegistry.vptr. Retyping them makes cfe
  warn (712 / 709) at stores in other owners' files: CourseMarkerTmpl_create.c 42 / 51 / 60 (a), bootup_uso.c 1115
  / 4685 / 4695 (h). They need those `(s32)` / `(int)` casts changed to `(char *)` at the same time.
- **Donor table (B750 / 10694 / E35C / F6D4 / 10840 / 10A0C / F13C, 21 accessor uses):** every site except B750's
  three is `AT(PM, &tok, kPmf_X)` or `AT(double, &tok, kRoD_X)`. That is the documented game_uso_data.h spelling: a
  per-site zero token plus a named K. There is no raw offset left to name. Respelling it as `*(PM *)(&tok + K)` would
  only dodge the census regex, so it was not done. Census should not count AT uses whose offset is a k* constant.
  B750's `AT(float, (int)&import_8005C1A8 + 0xA0, 0x30..0x38)` writes a vec at import_8005C1A8 + 0xD0
  (gGfxLib_8005C108 + 0x170 if the import is inside GfxLib, i.e. unk160[4..6]). Not proven; Sun_display and B274
  write the same vec. 6FA8 has no sites in this census.

**Next:** 55A0's ItemMgr.unk34 once gdl/item.h is C++-safe (not in this base); the three CourseParm / WorldRegistry
vptr retypes together with a / h; the import_8005C1A8 object (B750 / B274 / Sun_display); a census rule for the
named-K AT uses.


## 33. Run 570: ItemMgr.classMask, the import_8005C1A8 object (GfxLib.modelView), port-audit g sites, envobj retypes

Port audit (owner g, A+B+C+D): 23 sites in 12 functions -> 8 in 5 (A 8 -> 4, B 14 -> 3, C 0, D 1). H: TreeTmpl.shapeData,
Tv1Tmpl.unk64 / model retyped (envobj.h). Census game_uso raw / accessor 4 / 21 -> 4 / 18. Every changed object
`objdump -dr -s` identical (.mdebug / .comment excluded), main and NON_MATCHING builds.

- **import_8005C1A8 = gGfxLib, its token named for the +0xA0 site** (the same naming as import_800200CC = GameFlow
  + 0x34): 0x8005C1A8 - 0xA0 = 0x8005C108 = gGfxLib_8005C108, and +0xA0 is GfxLib.modelView. The vec the three
  sites write (+0xA0 + 0x30..0x38) is **modelView[3][0..2], the translation row**: LensFlareElem_draw and
  Sun_display place the flare / sun sprite by writing its position straight into the current model-view matrix
  before the sprite's draw virtual. Sun_display's other GfxLib reads: +0x254 curWindow (063734's projection
  target, also stored as Sun.depthImage), +0x2A0 fog.colour[3] (the 0.98 / 0.7 / 0.3 fade thresholds).
  - B750 donor: `GFXLIB(&import_8005C1A8)->modelView[3][i] = ...` is byte-identical to `AT(float, (int)&tok + 0xA0,
    0x30 + 4i)`: edg forms the array base (`lui/addiu tok+0xA0`) and stores at +0x30. A `float *` row local folds
    the base to +0xD0, a `GfxLib *` local to +0, a `float (*)[4]` local moves the Q temp (all tested).
  - game_uso.c NON_MATCHING Sun_display body: typed (GFXLIB(s1)->fog.colour[3] / ->curWindow, dst = modelView[3]).
  - B274 donor (NON_MATCHING only): left. Dropping `int di` keeps every instruction but moves r's slot 60 -> 64;
    any pointer local adds an instruction. match_imports/Sun_display.c (owner a) can use the same modelView[3] spelling.
- **55A0:** `ITEMMGR(D_55A0_root)->classMask = var_s0` (gdl/item.h by relative path).
- **game_uso sites:** SnowChaseActorLookParms_ctor stores through SnowChaseActorLookParms / CamParm; Sun_ctor's two
  MemberCallback vptr stores; RiderAnim_ctor's Parms name; the (int) casts dropped at K&R call sites
  (RiderAnim_startTimeout x2, SnowAI_findNearestMarker x2, dma_read); 591C's `->link == 0`.
  Left: scanNodes / scanSegments `t` / `cnt` hold link and are reused as ints (a pointer type fails to compile
  later: `t = scanIndex + 1`); scanSegments' `(Vec3 *)(unsigned)&b1 / &b4` (cfront placement-new null check);
  MemberCallback_invoke's sel multi-def; B3C's `*(char **)ob` (D).
- **envobj.h (agent-h's request):** TreeTmpl.shapeData `void *` (55A0's three A sites gone); Tv1Tmpl.unk64 ->
  `u16 *frameImage` (7D04's VT_SLOT 11 call cast to `u16 *(*)(char *)`); Tv1Tmpl.model -> `Tv1Model *` with
  `char **screens` at +0x84. 7D04 reads it as `k = *(int *)&...->model; ((Tv1Model *)k)->screens`: k must stay the
  one int variable (a `Tv1Model *` local swaps v0 / v1). Tv1Tmpl_create's `link[5] = (int)ret` (h) is the model's
  list word.
- PHYSICS.md section 2 "Frame order" already covers the per-frame flow.

**Next:** the B274 donor slot (find another escaping local to hold r at 60); scanSegments' placement-new spelling;
match_imports/Sun_display.c to modelView[3] (a).
