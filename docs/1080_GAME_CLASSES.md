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

