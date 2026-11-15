# 1080 Snowboarding: bootup_uso C++ classes (area F)

> agent-g run 447, 2026-11-15, 1080 branch agent-g (commits a3beae5d7..1a7acb638 on c14657cc9).
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
