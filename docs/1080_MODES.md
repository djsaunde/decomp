# 1080 Snowboarding: mode / process USOs (area H)

## State for porters: the select screens (genproc) (agent-c run 574, final wave)

**What it is.** genproc.uso (module 28) is the shared character / board / course / level select
step. It is the splat segment `timproc_uso_b5`, not timproc: Text at ROM 0x5BD2C2, 0xE620 bytes.
All 193 real functions are exact; the 194th is the `_00000000` sentinel. The code is cfront C++
lowered to C. Most bodies are IDO C. The rest are edg (NCC) `.cpp` donors and IDO cfe donors
(`_8FC8.c` SelItemsMgr_ctor, `_4118.c` SelectWin_ctor), spliced over placeholders. There are also
separate sub-TUs: `_D884` / `_DF14` (the course / level createItem) and `_o2_5FC0`
(SelectWin_update). The class / vtable table is in H1 "genproc" below.

**Flow.** GenSelectChar_ctor (the Process) runs `gen_createScene`, which builds the "MainGame" /
"bg" / "fg" nodes, the GenRoom and one or two GenCameras. It then creates the SelItemsMgr (the
four stage lists, three Tesuri items and the CommonInfo) and the SelectionMgr, which makes one
SelectWin per player. Each SelectWin runs the 11-state machine in `SelectWin_update`
(`SelectWin_state0..10`, stage bits 1 / 2 / 4 / 8). The machine handles cursor and accept input,
the cheat sequences (`SelectWin_charCheatIndex` / `boardCheatIndex`), the camera lerps between
items and the 2-player split slide (SelectionMgr_setSplit / _update). `SelectWin_commitSelection`
writes the chosen items' `id` (and the board `flags`) through `SelectWin.out[5]`, then fades the
process out. Those five words are the screen's whole output contract to the caller.

**Typed (include/game/select.h, offsets asserted for C builds).** The full layouts are SelectWin
(0x4F0), SelectWinParms, SelectionMgr (0x58), SelItemsMgr, SelItemList and SelCommonInfo. Also
typed: SelItem / SelItemEx and the five item classes; SelItemParms / SelItemInfo (the HostIO parm
records, named by their 3-letter tags); SelItemVtbl (slots 10..27 by role); the display models
(SelModel and the Character / Board / Course / Tesuri / Level models, plus SelCharAnim);
GenCamera, GenRoom, GenScene, RoomModifier and GenSelectChar. Settings and cheat marks come from
gdl/backup.h. The gdl node types (Node / MNode / QNode, VT_SLOT) come from include/gdl, and
camera / window from game/camera.h and gdl/window.h.

**What stays raw, and why.** 36 census sites are left in the segment, 22 casts + 5 accessor uses
of them in timproc_uso_b5.c:
- **RoData float-pool reads through pinned symbols.** These are SelItemsMgr_ctor's five
  `FF(&import_..., K)` and SelectWin_update's five reads (o2 donor). The pinned symbol / relocation
  is what matches. On a port they are float constants: read them from the RoData listing.
- **gen_createScene's three game_libs globals are gGfxLib** (run 585): `import_8005C2CC` / `_w` /
  `import_8005C39C` / `import_8005EBA4` all relocate to bootup Bss+0x3C168 (Sym 154), so they are typed
  `extern GfxLib` and read `.flags &= ~GFX_FLAG_MAPPARMS`, `.fog.colour[0..3] = 0`, `.fog.colour[3] = 0`.
  The distinct-alias and pointer-mutate spellings stay as matching levers. Also identified in run 585:
  genproc Bss 0 / 4 = GenMenuPick {menu, owner} (select.h; GenCourse_update saves them, the row
  callback timproc_uso_b5_func_00000000 reads them), import_000A5D38 = PauseMenu_create (GuiMenu),
  SelectWin_state0's pad = input_getPad -> InputPad, GenItemType_create = ColourSubItem. The genproc
  RoData floats / Data tags are named offsets in select.h (kRoF_gen_*, kTag_gen_*).
- **The state functions' `arg0 + stage * 4` cluster offsets**, kept as char * arithmetic. This is
  a matching lever, explained at the SELWIN macro in select.h.
- **The edg donors.** They see the gdl bases as opaque bytes because edg rejects the gdl headers'
  asserts, so their few raw sites are inside those bases. `_ncc_8FC8_nm.cpp` is not compiled.

**Porting.** The screen is plain code on the gdl scene graph. It needs Node / QNode / MNode,
list_append, PolyShape, MCamera and Window. It also needs gui sprites and fonts, the input
manager (`input_checkPressed`) and bootup's sound events. Each call goes through a `gen_imp_*` or
`import_*` symbol, so the dependency list is genproc's import list (`scripts/uso-imports.py`,
1080_GAME_CLASSES.md section 8). Layout and tuning come from data files, not code:
- rom/1psel.bin, rom/2psela.bin / rom/2pselb.bin and rom/selinfo.bin (GenSelectChar);
- rom/selwin1.bin / rom/selwin2a.bin / rom/selwin2b.bin (the SelectWin Parms: cwt, msp, lfw, the
  colours and the offsets).

Each one loads into the HostIO Parms records that select.h names. A port can keep the module
as-is on top of a gdl port. Or it can rewrite the screen against SelectWin.out[] and the item ids.

## State for porters: mode USOs, race flow, GUI menus, title / attract, boot module (agent-h run 576, final wave)

Scope: everything in area H except the select screens (genproc, previous section). That is bootup.uso's
game-side code (bootup_uso*.c), game_libs.c / game_libs_tail.c (the race process base, RaceTracker, the HUD
gadgets, Backup), and the mode modules titproc, h2hproc, arcproc, mgrproc, timproc (b1), trkproc (b3), plus
the module-skeleton notes for eddproc / n64proc / gui. All functions in these segments are exact; the
`*_00000000` sentinels are the only unnamed symbols. Census at the end of the phase (run 576): 171 raw
`*(T *)(p + K)` sites left in area H (220 before this run, 231 before run 572), 20 of them in
bootup_uso.c, 17 in titproc, 14 each in game_libs_tail.c and mgrproc, 10 / 8 in trk / tim, 9 arc, 7 h2h.

### What is typed

| header | types | what they cover |
|---|---|---|
| include/game/input.h | `InputMgr` (= GameFlow), `InputPad` (= PadCtl), `FlowUso` | the flow object at bootup Bss 0xF8: flow mode, procMain states, player rider / board / course / level choices, pads, the session / save pointers, replay buffers, the music request. Every mode module imports it as one symbol (`INPUT_MGR(sym)` / `GAMEFLOW(p)`) |
| include/game/course.h | `WorldRegistry`, `WorldCourse`, `WorldPlayer`, `RaceGate`, `CourseItemTmpl` | the "World Registry" the game_setup* functions fill: og / fg / bg / eg roots, MainGame node, the two lights, the course map, players[8], camera windows |
| include/gdl/race.h | `RaceProcess` (+ `RaceProcessVt`, 38 slots), `RaceTracker` (= `DataManager`), `RaceEntry`, `TimRace`, `TimDataManager`, `RaceSprite`, `RaceColourParms` | the race process base (game_libs 0x6900..) and the race-progress / HUD object (game_libs 0xC784). RaceEntry.gate / gateA / gateB are `struct RaceGate *` since run 576 |
| include/game/modeproc.h | `ArcRace` / `MgrRace` / `H2HRace`, `ArcDataManager` / `MgrDataManager` / `H2HDataManager` / `TrkDataManager`, `ArcCourseList` / `MgrCourseList`, `ModeFlowProc`, `H2HWinsDisplay`, `GameDemoProcess`, `TitleDemoProcess`, `MainLogo`, `KeyMessage`, `WhiteFader` | the per-mode subclasses and the title / attract objects |
| include/game/guimenu.h, modemenu.h, nameentry.h | `GuiMenu`, `GuiRow`; `MenuProcess`, `TimMenu`; `NameEntry`, `ModeNameEntry`, `MgrNameEntry` | the pause / post-race / mode menus (rows with a callback at +0x90, stride 40) and the initials entry |
| include/gdl/gadget.h, include/game/fader.h, include/gdl/hud.h | `Gadget` and the Time / CountDown / Points / Cool / Course / Boards / TrickPoints gadgets, `PointsPopup`, the gadget Parms (over `GdlParmBase`), the Fader | the 2D HUD (hud_add<X>Gadget builds them under the RaceTracker) |
| include/gdl/backup.h | `Backup`, `BackupSession`, `BackupOptions`, `BackupCourse` / `BackupCourseRecord`, `BackupArcade`, `BackupGhost`, time / score entries | the 0x8000-byte SRAM image and the per-mode record session |

Every struct has offset asserts for C builds (the `#ifndef __cplusplus` blocks; edg rejects them). The
headers are C++-safe so the NCC donors can include them.

### Entry points

- **Boot** (PORTING_GUIDE 2.1): kernel `uso_load`s bootup.uso, `boot_entry_00066C30` -> `boot_main_00066850`
  (threads, pad thread) -> `App_main` -> `SnowBoard_InitInstance` (rom/version.bin, rom/anims.bin) ->
  `GameFlow_create` (the InputMgr object; gui.uso, rom/flowimgs.bin) -> `GameFlow_startMode` -> `app_run`.
- **Mode start.** `GameFlow_startMode` maps `InputMgr.nextFlowMode` (bootup Data 0xC450 table: 0 N64DEMO,
  1 TITLEDEMO, 2 HEAD2HEAD, 3 MULTIGAMERACE, 4 TIMEATTACK, 5 ARCADEMODE, 6 TRICKMODE, 7 TRAINING, 8 EDITORS)
  to a `ModeFlowProc`, `GameFlow_loadProcUso_000117FC` loads the mode .uso, and the module's 1-slot entry
  object calls `<pfx>_procMain(app, state)` (tit / n64 / h2h / mgr / arc / tim / trk / edd). procMain is a
  switch over `InputMgr.procState` (+0x40) that loops until a state launches something: a select screen
  (`app_launchGenProc(app, players, 7, stageBit)`), a race (`app_createGame_*` + `<Mode>Race_ctor` +
  `app_runProcess`), name entry (`app_launchNameEnt`), the replay viewer (`app_launchViewRec`), a menu
  process or the QuitProcess. The per-module state lists are in H2 (runs 460, 466).
- **Race build.** `game_init` -> `game_setupMode(registry, gameMode, arg)`: the TrickTable ("rom/tricks.bin")
  under bg, the geometry-mode bits, then `game_setupSolo` / `VsGhost` / `Replay` / `VsCpu` / `Vs2P` /
  `Empty` / `DemoSolo` / `DemoRace` / `DemoSplit` (riders, pads, cameras), `game_createLights` (ambient /
  infinite / shadow lights + the LightTarget) and `game_createMap` (course scene). `InputMgr.gameMode`
  (+0x3C) keeps the GAME_MODE value.
- **Per frame.** The running Process is a Node: `Process_update` calls slot 12 (`*_handleInput`) while not
  fading, updates the children, and calls slot 11 when the fade ends; `Process_display` draws the scene and
  then slot 13 (`*_drawGui`). For races, `RaceProcess_handleInput` runs the phase machine (`unk4E0`: 0
  delay, 1 countdown, 2 racing, 3 finished, 4 / 5 other ends, 7 over) and dispatches the 38 vtable slots
  (onPause 16, onCountdownStart 17, onRaceOver 20, onEndTimerDone 21, onPauseSelect 25, drawIntro 29, ...;
  names in H2 run 471). The RaceTracker (DataManager) updates the timer and progress, runs
  `RaceTracker_passCheckpoints` (checkpoint hits reported through vtable +0x60 / +0x64) and
  `RaceTracker_passGates` (fork gates: `RaceTracker_onGateCleared` / `onGateMissed`, +2000 score per
  bonus) and feeds the gadgets; each mode's `<Mode>DataManager_update` adds its HUD logic.
- **Mode transitions.** Menu rows and pause rows write `InputMgr.procState` / `nextProcState` /
  `thenProcState` (or, on the title menu, `nextFlowMode` +0x34) and start a fade; when the fade ends,
  `Process_exit` returns to GameFlow, which re-enters procMain (same module) or `GameFlow_restart_000116C8`
  / `GameFlow_startMode` (new module).
- **Title / attract.** titproc's procMain state 0 sets `InputMgr.titleFlags` (flag bits choose the
  overlays) and runs a GameDemoProcess: a RaceProcess subclass (0x6C8) that plays an attract race
  (`game_setupDemo*`, ghost input) under the title overlays: MainLogo, the pulsing KeyMessage
  ("press start" sprite), the title menu (`menuState` 0 logo, 1 menu, 2 language) and a WhiteFader.
  TitleDemoProcess (0x78) is the same overlay set on a plain Process with a timed state machine.
  `InputMgr.demoIndex` picks the next demo. The title menu rows (`tit_menu*`) write `nextFlowMode`.
  n64proc (flow mode 0, N64DEMO) is the other attract module.

### What stays raw, and why

- **Matching levers.** Spellings documented next to each body: K&R `int` / `char *` parameters and locals
  that carry register allocation (passGates's `e = arg0; arg0 = 0;` split, tit_procMain's
  `d = (int)&import_00020098`, the Tim / Trk ctors' `char *`), `*(int *)&p->field` where the member form
  changes bytes, distinct extern aliases of one import (`D_2DA4_obj` / `_rd`, the `*_cfg` geometry-mode
  aliases) that keep separate %hi / %lo pairs, `if (1) {}` / volatile pads, and the -O0 donors' extern-struct
  module globals (tim / trk main's `TimProcState`). Changing them changes bytes, so they stay.
- **Fields of classes defined outside the area.** RaceGate +0x5C / +0xC8 (checkpoint.uso is not split),
  SnowBoarder child objects (+0x818 / +0x81C), the TitleDemoProcess's game_libs objects, the gGfxLib
  sub-objects. They are read raw at the one or two sites that touch them.
- **Pool and import reads.** RoData float pools pinned as symbols (`kRo_*`, `bu_b520_k*`) and
  `(char *)&D_00000000 + K` import addends (the relocation carries the offset); a port reads these as
  constants or as the named field of the imported object.
- **NM-only and edg donors.** RaceTracker_findGates / passCheckpoints NM bodies keep `FW()` (not compiled
  in the matching build); edg donors see gdl bases as bytes.
- **Not yet named:** the `unk*` / `pad*` fields in InputMgr (0x70..0x88), RaceEntry 0x2C / 0x44 / 0x50 /
  0x5C, RaceProcess's state words, and the mode-specific tails of the DataManagers (they agree on nothing
  past 0xB8).

### What a PC port replaces

- **USO loading.** `GameFlow_loadProcUso_000117FC` / `GameFlow_unloadUso_00011A34` (`InputMgr.procUsoPath`,
  `usoList`), `app_loadUso`, `game_loadUso`, and the `app_launch*` helpers that load genproc / nameent /
  viewrec. Link every mode statically and make the entry object a table of `<pfx>_procMain` pointers keyed
  by flow mode. Cross-module calls go through `CALL(name)` / `gl_func_00000000` placeholders that this repo
  names; a port binds them to the named function directly. The RaceProcess / Process / DataManager
  vtables are Cfront tables (`VT_SLOT`, this-adjust deltas): either keep them as function-pointer structs
  or make the classes real C++ with the slot names from H2.
- **Save data.** Backup (backup.h) reads and writes the SRAM image through `fs_gdl*` kind 2. The mode code
  only sees `InputMgr.backup` / `.session` (`Backup_openSession` per mode, `*_closeSession`) and
  `InputMgr.options` (BackupOptions: unlocks, levels, cheat marks). Replace the SRAM path with a file
  holding the same 0x8000-byte image; keep or drop the checksums.
- **Controller.** The pad thread (`pad_threadLoop_00066EEC`) fills PadCtl objects (`InputMgr.pads[]`,
  `racePads[]`); the modes read them with `input_checkPressed / Held / Released` and riders through
  `RiderInput` (stick floats, held / pressed bits, stick direction). Replays are recorded / played back as
  InputFrame streams (`InputMgr.recordBuf`, `replayData[2]` / `replayLen[2]`, `pad_startRecord` /
  `pad_startPlay`), so a port must feed host input into the same PadCtl fields for ghosts and demos to
  stay deterministic. Rumble goes through `pad_updateMotor_00067084`.
- **2D.** The HUD, menus and title screens draw with gui.uso (fonts, sprites over the resource manager,
  fill rects); replace the gui_* emitters, or keep them on an F3DEX interpreter.
- **Data files** the modes load: rom/version.bin, rom/anims.bin, rom/flowimgs.bin, rom/tricks.bin, the
  per-mode sprite / font images opened through `gui_spriteLoad`, and the gadget Parms records.

## H2. Mode / process modules: titproc, h2hproc, arcproc, mgrproc, eddproc, n64proc, gui, boarder1-5 (agent-h run 460)

> agent-h run 460, branch agent-h on 8239918e8: efb3336fb (78 names) and 16f7cbcb8 (110 names), both pure
> rename batches, gate PASS each. Placeholders left: tit 5, arc 36, mgr 35, h2h 15, gui 2, edd 4, n64 2,
> boarder 1 each (the `*_00000000` sentinels cannot be renamed).

**Tools** (scratch, /tmp/claude-1000/h460/): `mods.py` finds **every** USO by its outer header
(`0x12345678, module id, 1, "<name>.uso"`) and parses the sections from the next marker, so it also picks
up the modules g451's finder missed (boarder1-5, n64proc, the data-only USOs). It writes `mods.pkl` keyed by
**module id**: 0 bootup, 4-11 boards (tahoe151 ...), 12 penguin, 13-17 boarder1-5, 18 gui, 19 n64proc,
20 titproc, 21 eddproc, 22 mgrproc, 23 arcproc, 24 h2hproc, 25 timproc, 26 trkproc, 27 trnproc, 28 genproc,
29 gamegfx, 30 charsel, 31 charsps, 32 viewrec, 33 nameent, 34 charfir, 35 charmap, 36-45 map1-10_data,
46 game, 47 balloon, 48 heli, 49 fire, 50 checkpoint, 51-58 bg1-8tex, 60 snoweffects, 61 effects.
`dis.py MOD START END` / `dis.py MOD --funcs` is g456's annotator generalised to any module: every import
(kind 1) is followed to the exporting module's Sym entry and printed with the current report name (`B.` =
bootup/game_libs, `gui:` / `nameent:` / `game:`). `vt.py MOD` lists a module's DataReloc words resolved the same
way (vtables, string tables). **Splat offset = Text offset + 4** for gui, n64proc, eddproc, arcproc,
h2hproc (the c segment starts one word before Text); titproc, mgrproc, boarder1-4 are +0; boarder5's names are
+4 against boarder1-4's.

**Module shape.** Every proc module has the same skeleton:
- an **entry object**: a 1-slot vtable (titproc's and n64proc's sit after the class vtables, the others at
  Data 0x18) whose slot is `<pfx>_procMain(app, state)`, a loop over `state = cfg+0x40` (cfg = the bootup
  input manager, Bss 0xF8). h2h: 0 init, 1-4 gl 0x8AE4(app, 2, 7, k) (another USO), 5 create H2HRaceProcess
  and run it (gl 0x93DC), 6 QuitProcess. eddproc's procMain (0x144) is **empty**: EDITORS is a stub in retail.
- a **Process** subclass (bootup Process vtable 0xC3A0, node name "<X> Process"). Slots: 2 display = gui
  begin (`gui_beginFrame_000016A4`) + **slot 13** + Node_display; 3 Process_update = **slot 12** while not
  fading, Node_update, then **slot 11** once the fade is done (base F7D0 sets the next-proc callback).
  Names: slot 12 `*_handleInput`, slot 13 `*_drawGui`.
- the race modes' process derives from a game_libs race-process class (slots 12-37: gl 0x76F0 / 0x7FF4 /
  0x7344 base entries). Overrides that agree across modules: 17 release (frees the gui sprites), 20
  setupRace (fade, "Poop end"/"Poop start", cameras, DataManager, pause menu), 23 newReplay
  ("new replay please %d"), 25 checkFade, 29 drawOverlay. Other slots kept as `*_func_<addr>`.
- a **DataManager** (game_libs class 0xC784, node "DataManager"): `<pfx>_DataManager_init` adds the HUD
  gadgets the mode needs, slot 3 `<pfx>_DataManager_update` feeds them.
- an **ItemType** subclass (vtable slot 10 = `<pfx>_ItemType_create_<addr>`, base gl 0x3D5BC, Data 0x75A0) and
  four 1-slot **parm** vtables whose read slot reads a tag int then an int / float / quad / vec3 into +0x10
  (`<pfx>_read{Int,Float,Quad,Vec3}Parm_<addr>`), plus the TU's dead inline `fs_gdlRead*_<pfx>_<addr>` copies.
- the name-entry screens (arc 0x199C, mgr 0x2940) subclass nameent.uso's process (import nameent Data 0x80);
  most of their vtable is nameent Text.

**Flow.** The title menu rows (`tit_menu*`) write the next flow mode into cfg+0x34, indexing bootup's
table at Data 0xC450 (0 N64DEMO, 1 TITLEDEMO, 2 HEAD2HEAD, 3 MULTIGAMERACE, 4 TIMEATTACK, 5 ARCADEMODE,
6 TRICKMODE, 7 TRAINING, 8 EDITORS), send sound event (12, row) and fade out. The h2h pause rows write the
h2h_procMain state into cfg+0x40 (5 retry, 6 quit, 2/3/4 not yet identified).

**gui.uso** (module 18) is the shared 2D layer: fonts (`gui_fontCreate` scans a glyph atlas into 20-byte
glyph records; `gui_drawString` / `gui_stringWidth` / `gui_centerStringX` / `gui_rightAlignStringX`, a second
font family at 0x1514/0x15BC/0x15F4/0xF04), colour/combiner emitters (`gui_setColor_00001A5C` precedes almost
every sprite draw, `gui_setFillColor` + `gui_fillRect` draw WhiteFader), sprite handles `{+0x10 data,
+0x14 id}` over the resource manager at *(bootup Bss 0x248)+0x150 (`gui_spriteInit/Load/Refresh/Release`),
`gui_drawSprite` (tiled), scaled / scrolled variants, tile loaders (RGBA32/RGBA16/IA8), `gui_setScissor`.
The gui context is gui Bss+8 (procs pass it as arg 0).

**mgrproc** also carries the **staff credits** (Data 0x1F8.. string table, "0" = heading, "1" = name,
"2 " = blank line: EXECUTIVE PRODUCER HIROSHI YAMAUCHI ...) and the "Congratulations!" screen
(MgrNameEntry_drawCongrats), so it is the multi-race championship mode with its ending.

**boarder1-5** (modules 13-17) are character data USOs; their only code is two TUs' inline reader copies
(readInt / readQuad / a quad-parm read slot), named with a per-module suffix.

**Run 466 (agent-h, branch agent-h on 42f08ef0b).** 73dd5108b (75 names, pure rename), 361628c34
(include/game/input.h), 6429b0b3b (field conversions). Gate PASS each.
- **Race vslots** come from the base state machine gl 0x76F0 (the race object's `unk4E0` state:
  0 pre-start delay, 1 countdown, 2 racing, 3 finished, 4/5 other end states, 7 after the end).
  16 onPause (START with a pause menu), 17 countdown start (modes free their intro sprites: the
  `*_release_*` names), 18 / 19 tick tests in state 3 / 4-5 (base returns 1), 20 every frame in
  state 7 (`*_raceOver_*`: fade, then name entry / results; was misnamed setupRace), 21 onFinish
  (state 3 -> 7), 22 / 23 the `unk4F4` timer expiry (flag bit 20 set / clear), 24 state 4/5 -> 7,
  25 runPauseRow (`pauseMenu->rows[sel].fn`, +0x7C sel, stride 40, fn at +0x90; was misnamed
  checkFade), 26 A/B/START while flag bit 19, 27 once `unk500`, 28/29 from gl 0x7FF4, 30/31 from
  gl 0x7344, 33-36 per frame by view mode `unk4D8` 0..3. Unknown roles are `*_vfuncN_<addr>`.
  TimRace / TrkRace use the same slot numbering (their names are agent-c's role guesses).
- **Session course list** (session+8). arc (0x38): retries +0, idx +4, count +8, courses[5] +0xC
  ({2,0,3,1,4}), times[5] +0x20, total +0x34. mgr: courses from +0xC, the rider for each course
  from +0x24 (`list[idx + 9]`). `mgr_initMatchRace(level)`: 3 retries; level 1/2/3 = 4/5/6 courses
  (ids 2..7; only 3 if the word at 0xA0000284 is not 0x240B17D7, a cart check); the 4 CPU rivals
  from `mgr_pickRivals` ((playerRider + 1 + rand*3.9) % 5, distinct, never the player's own rider), then
  the player's own rider, and an expert boss 5/6/7 picked by the unlock word (Bss 0x24C)->+2.
- mgr / arc procMain states: arc 0-2 select (gl 8AE4 flags 1/1/2), 3 open session, 4 init courses,
  5 race, 6 name entry, 7 replay, 8 ARCMenu, 9 close, 10 quit. mgr 0/1 select, 2 open, 3 initMatchRace,
  4 race, 5 replay, 6 close -> 1, 7 close -> 8, 8 quit. Pause rows go to the replay state first when
  gl B3B0 (a replay exists).
- `mgr_startEnding_00001BE4` (view mode 2, per-course params Data 0x5F0 / 0x5FC for courses 5..7,
  music 11) is the ending flyover; the credits text itself is drawn by `MgrNameEntry_drawCongrats`.
- gl 0x8AE4 = load genproc + select USOs, then `GenSelectChar_ctor(0, players, 7, flags)` and run it
  (agent-a's file; not renamed). The h2h pause rows 2/3/4 pass flags 1/2/4 to it. Naming them needs
  the flag meaning inside GenSelectChar / SelectionMgr (genproc, agent-c's names).
- `gui_drawSpriteIA8Clip_00002BB0`: an IA8 sprite's first `width` pixels in 32-px strips.
- **include/game/input.h**: `InputMgr` (bootup Bss 0xF8) and `InputPad` with offset asserts. It is one
  big exported object: +0x138 DataManager*, +0x148 / +0x14C the session (Bss 0x240 / 0x244),
  +0x154 unlock ptr, +0x170, +0x17D.., +0x190 Fader* are all relocs against it (not yet in the struct).
  Converted: arc_procMain, tit_procMain, n64_procMain + N64DemoProcess update.

**Next.** Unnamed: arc 14C8 / 1C74 / 2884 (draw helpers), mgr B20 (a continue row that first calls
race gl 6F90), 1A64 / 1AD0 / 1B58 (camera setup), 23FC / 2850 / 2E3C (draw), h2h 49C / 8EC / 944 (win
bookkeeping: gl 6DC8 / 6DF8 / 6EE0 / 6F60, which agent-a is naming). When agent-a's 0x6900 names land, rename
the `*_vfuncN_*` slots to match. Convert more users: the h2h / mgr procMain bodies use per-offset
`import_800200xx` externs (would change symbols, so not byte-safe as a pure edit); bootup's own
input_* bodies (agent-g's files) can take `InputMgr *` (input_checkPressed/Held/Released in
bootup_uso_ncc_11E00.cpp, input_addPad / replay_addInput in o0_11C70.c, input_setActivePad /
input_clearActivePad in o0_1207C.c).

**Run 487 (agent-h, branch agent-h on 9dcd5ce48).** e695bbe88 (hand edit: README "Readability status" ->
docs/1080_PORTING_GUIDE.md, the new top-level guide), 51d91f5cc (hand edit: race.h `RACEPROC(p)` /
`TIMRACE(p)` cast macros, 103 timproc / trkproc accesses onto RaceProcess / TimRace fields; objects identical).
Gate PASS each. Next: the same macros in arcproc_uso_tail1.c (ArcRace ctor: +0x6A8 courseList / +0x6AC dataMgr),
mgrproc / h2hproc race ctors, and a TimDataManager struct (0xE0: race 0xB8, session 0x4C, colour 0xC0..0xCC,
alpha 0xD0) for TimDataManager_init / update; the `&D_00000000 + K` InputMgr reads in titproc / h2hproc are
import relocs and stay.

**Run 471 (agent-h, branch agent-h on 19f8e0b6f).** eeead0f35 (56 names, pure rename), b67b6884a
(38 names, pure rename), 99f0e46c8 (hand edit: input.h + conversions). Gate PASS each.
- **Race overrides = base slot names.** Every Tim/Trk/ARC/MGR/H2HRaceProcess and GameDemoProcess override
  is now `<Class>_<base slot name>` (agent-a's RaceProcess table, 1080_SYSTEM_LAYER.md s10), no address
  suffix. Replaced role guesses: setupRace / raceOver / checkRecord -> onRaceOver (20), onFinish ->
  onEndTimerDone (21), runPauseRow / checkFade -> onPauseSelect (25), quit -> onQuitButton (26),
  drawOverlay -> drawIntro (29), drawHud -> drawResultExtra (30), release -> onCountdownStart (17),
  startHud / isHudBusy / mgr onResult -> endTimerEnabled (18), setMenuState -> onTimeoutExit (22),
  showMessage / newReplay -> onTimeout (23), unreachable -> onAltEndTimerDone (24), Trk showHud ->
  onPause (16), Trk startHud / arc onResult -> onLeave (27). The mgr vfuncs became onEndRaceAlt,
  drawHud, updateSub0-3, onMessageBounce. **agent-c's TimRace / TrkRace (timproc_b1 / b3) were renamed
  in the same batch** (with TrkDataManager slot 8 = loadData and the Tim/Trk pause / menu change rows
  below), so H1's role names for those slots are superseded.
- **Change-stage rows.** `app_launchGenProc(app, players, 7, k)`: 7 goes to SelectWin->stageMask (0x3C0),
  k to SelectWin->stageBit (0x3C8), the stage the select screen opens on (1 character, 2 board,
  4 course). The procMain jump tables give the states: h2h 1-4 = 1/1/2/4, arc 0-2 = 1/1/2, tim / trk
  0-3 = 1/1/2/4. So the old exit rows are `*ChangeCharacter / *ChangeBoard / *ChangeCourse`
  (h2h_pauseChange*, ARCMenuProcess_rowChange*, Tim/TrkRace_pauseChange*, Tim/TrkMenu_rowChange*).
- **h2h results.** `h2h_winByFinish(race, p)` (wins[p]++; result 0 if p is 0, else 3) runs when one
  rider's finish flag is set (both at once = endResult2, a draw, winner -1). `h2h_winByRetire(race,
  p)` (wins[p]++; result 5 if p is 0, else 4) runs when the other rider's meter (gadget +200) is <= 0,
  and from the pause row `h2h_pauseForfeit` (p = pausing player 0x6B4 ^ 1). After the race,
  onRaceOver runs `h2h_startReplay` (RaceProcess_restart, both pads pad_startPlay(replayData[p],
  replayLen[p]), timeout (u16)(min len + 0xF)) behind the post-race menu; onTimeout loops it.
  `mgr_startReplay` is its 1-player twin; `mgr_pauseRetire` ends the race with result 4 (endResult4_6F90).
- **Helpers named:** arc_drawResultScore (slots 30 / 31 share it), Arc/MgrNameEntry_drawBlinkBanner,
  arc_drawMenuBackground (5x7 tiles), mgr_drawResults, mgr_drawSpriteStack, mgr_switchToView2 (moves
  window flags 8|4 from +0x51C to +0x520), mgr_restartForEnding, mgr_DataManager_display, edd_procMain
  (empty), edd_EditorsProcess_handleInput, tit_open/closeSession, n64 / edd nops.
- **include/game/input.h**: InputMgr +0x138 dataMgr, +0x148 backup, +0x14C session, +0x168
  replayData[2], +0x170 replayLen[2], +0x190 fader (asserted). `INPUT_MGR(sym)` views a shared
  placeholder (`extern char D_00000000`, import_00020098, import_80020228) as InputMgr with the same
  symbol and offset. 43 sites converted in h2h / tit / mgr / arc after checking each function's
  relocation targets bootup Bss 0xF8; tit_nextDemo's `backup + 4` and GameDemoProcess_ctor's chained
  dataMgr store were left raw.

**Next (H2).** Placeholders left: only the Arc/Mgr/Tim/Trk NameEntry slots 17 / 18 (nameent.uso
overrides; need nameent's base roles, module 33 has no code segment). Once agent-c's include/gdl/race.h
lands: retype `dataMgr` (RaceTracker / DataManager) and move the race overrides onto RaceProcess fields
(0x4E0 phase, 0x4F4 timeout, 0x4F8 result, 0x6A8 DataManager, 0x6B4 pausing player, 0x6B8 winner).
InputMgr +0x134 (Bss 0x22C, a game object: +0xC4 / +0xCC per-player, +0x108 active window) and +0x154
(unlock ptr) still raw. tim / trk Fader uses (agent-c's TUs) can take INPUT_MGR too.

**Run 473 (agent-h, branch agent-h on a9f6f0192).** Four hand-edit commits, no renames, gate PASS each
(3288/3288, objects identical): 0f51980b5 (include/game/modeproc.h + race.h DataManager + input.h + h2hproc
conversions), dbdba757e (arcproc), 0b1091cd5 (mgrproc), 6c9f345e6 (titproc).
- **include/game/modeproc.h** (sizes = the ctors' outer alloc; offsets asserted):
  `ArcRace` 0x780 (courseList 0x6A8 = `ArcCourseList` 0x38 {retries, idx, count, courses[5], times[5], total},
  dataMgr 0x6AC, finalTime / recordRank 0x6B0 / 0x6B4, retry 0x6B8, sprites[8] 0x6BC, resultFade 0x77C);
  `MgrRace` 0x7F0 (courseList 0x6A8, dataMgr 0x6AC, sprites[10] 0x6B0, retriesX/Y 0x7A8/0x7AC, retries 0x7C8,
  lastResult 0x7D0, exitStep 0x7D4, nameEntryMode 0x7D8, creditLine / creditScroll / endingPhase / endingTimer /
  endingFrame 0x7DC-0x7EC); `H2HRace` 0x6BC (wins 0x6A8 = s32[2] ctor arg 3, postMenu 0x6AC, dataMgr 0x6B0,
  pausePlayer 0x6B4, winner 0x6B8); `Arc/Mgr/H2HDataManager` 0xD8 / 0xE0 / 0xF0; `GameDemoProcess` 0x6C8
  (dataMgr 0x6AC, keyMessage 0x6B0, mainLogo 0x6B4, langMenu 0x6B8, whiteFader 0x6BC, menu 0x6C0, menuState
  0x6C4) and `TitleDemoProcess` 0x78 (a plain Process with the same overlays at 0x50-0x64).
  **Correction to the run 471 note:** the DataManager is at 0x6AC in arc / mgr / GameDemo and 0x6B0 in h2h;
  0x6A8 is the course list (arc / mgr) or the win tally (h2h), not the DataManager (tim / trk: 0x6A8 is).
- **DataManager** = `typedef RaceTracker DataManager` in race.h: "DataManager" is the node name of the
  RaceTracker class itself, and the mode subclasses share nothing past 0xB8 (arc / mgr: 0xB8 course list,
  0xBC owner; tim / h2h: 0xB8 owner). It is an addition at the end of race.h (no existing line changed), for agent-c to merge with the Backup session structs.
- **InputMgr**: +0x134 `game` (boot Bss 0x22C; +0xC4 / +0xCC players, their +0x800 the pad; +0x108 / +0x10C
  camera windows), +0x154 `unlocks` (+0 u16 unlock bits, +4 u16 option bits, +0x12..0x14 u8 settings),
  `dataMgr` typed `struct RaceTracker *`.
- **Converted:** h2h winBy*, onPause, pauseForfeit, onEndTimerDone, onRaceOver, onTimeout; arc loadSprites /
  releaseSprites, onCountdownStart, end-timer pair, onPause / resumePlayers, onEndTimerDone / onAltEndTimerDone,
  onRaceOver, onLeave; mgr loadSprites / releaseSprites, endTimerEnabled, onTimeout, onRaceOver, onQuitButton,
  startEnding, startReplay; GameDemoProcess buildMenu, onTimeoutExit, onQuitButton, handleInput.
  **Byte traps found:** the course-list `p->count == p->idx + 1` test swaps t6 / t7 against `p[2] == p[1] + 1`
  (kept the int array in arc / mgr loadSprites); mgr onRaceOver case 4 needs `list[list[1] + 4]` (an s32 field
  cast to char * flips the addu operands).
- **Left raw:** all the race ctors (alloc-cascade levers; they hold the only derived-class vtable calls, so
  the typed `vt->slot[]` form was not applied here), mgr onEndTimerDone / updateSub2 (int-array and BB-count
  levers), h2h onPauseSelect / setupCameras, the DataManager init / update bodies, the .cpp TUs (their own
  local structs), and the per-offset `import_800201xx` users (mgr_switchToView2, mgr_restartForEnding).

**Next (H2).** Convert the DataManager init / reset / update bodies onto Arc/Mgr/H2HDataManager (+ RaceTracker
base fields). Retype courseList as `ArcCourseList *` where no test depends on the array form. Name MgrRace
0x7A0 / 0x7A4 / 0x7B8 (drawHud floats) and GameDemoProcess 0x6A8. The NameEntry slots 17 / 18 still need
nameent's base roles.

**Run 477 (agent-h, branch agent-h on 5a8efa2ab).** Gate PASS on each commit (3288/3288, ROM identical).
a131aa7e7 (**pure rename**, 32: RaceTracker), 0f8b4268d (**pure rename**, 45: sys_ / coll_ / NameEntry
17-18), then hand edits 249e0aa65 (InputMgr.session), 3b9c3e40a (DataManager bodies), 5ec3595a4 (arc
courseList pointer), 68236b3d5 (MgrRace / GameDemoProcess fields).
- **Caller map tool:** /tmp/claude-1000/h477/callers.py walks every module's TextReloc through dis.py and
  prints each import/internal call of a weak name with its calling function (88 sites); that is the
  evidence for most names below.
- **RaceTracker** (game_libs 0xCA30..0xE368): addEntry / findEntry; passCheckpoints ("chk" list of entry 0,
  checkpoint.uso hit test, then slot 11 = onCheckpoint) and passGates ("gtl" / "gtr" pair: onGateCleared =
  snd 0x2C, score += 2000, bonus += 100 capped 500; onGateMissed = snd 0x2F, bonus = 0); tricks from
  game.uso RiderAnim: startTrick (TrickTable lookups, showTrickName, snd 0x24, slot 12 onTrickStart),
  addTrickPoints (pendingPoints), endTrick(rider, landed, combo) (popTrickPointsCombo snd 0x27 /
  popTrickPoints snd 0x22, slot 13 onTrickEnd), showComboBonus / popComboBonus, endAllTricks (arc / trk
  finish), popFinalScore (arc / trk: the 0xA0 value at 160,140; in arc 0xA0 is the countdown time,
  50000 / 30000 ms by InputMgr.course, decremented by 0x21 per frame). SnowBoarder_update feeds
  setEntrySpeed (0x348 / 2), setEntryHealth (0xA14), setEntryXZ (0xDC / 0xE4). **Rider result
  messages** (SnowBoarder handleMsg, bootup_uso_ncc_D900.cpp: raceResult 0xA54): 1000 win (1), 1001 lose
  (2), 1003 time up (3), 1002 (4), 1004 (5), 1005-1007 ending (6) -> sendWinResult / sendLoseResult /
  sendDrawResult / sendRetireResult / sendTimeUpResult / sendResult5_0000DE80 / sendEntryLoseResult;
  sendEndingMsg sends 1005 to the Bss 0x30 node (mgr_restartForEnding). toggleGhost (tim / trk, 2
  entries): button 0x20 toggles entry 1's rider flag 4 and unkB0 (the ghost). Address kept:
  flagReplayEnd_0000D090 (no reloc caller).
- **sys_ / coll_**: dbg_printfSink (_Printf callback -> TextWin_write), dbg_printfNop, sys_hang,
  pad_*Global (wrappers over the pad manager at Bss 0x3A4E8), sys_writebackDCacheAll, dma_waitAll
  (dma_wait 1..9), sys_getTime, sys_initHeap (Mem_init on Bss 0x3A210), sys_getResetType (0x8000030C),
  fs_set/getHandle (+0x20), sys_srand / randf / randFromSeed, sys_sumBytes; CollObjMgr_addStatic /
  addDynamic (+0x2C / +0x30 lists of CollObjMgr_update), CollObj_init / initCylinder / sendBump (msg 20),
  coll_contactPushOut, coll_offsetPointsByMtx, MemberCallback_invoke_0003A0C4, cam_isSphereInView.
  **Import addresses:** dis.py's `T<x>` for game_libs is splat + 0x1466C; nm of build/tenshoe.elf gives
  the same offsets except some post2 libultra copies, which sit 8 lower (T7E710 = gl_osSetIntMask 0x6A09C).
- **NameEntry slots 17 / 18:** nameent.uso (module 33, vtable Data 0x80) slot 13 = display switches on
  +0x60: 0 -> slot 17, 1 -> slot 18, 2 -> slot 19. Base 17 is empty, base 18 calls the owner race's
  slot 2 (draws it). Overrides are `<Cls>NameEntry_drawEntryOverlay` (17) / `drawExitOverlay` (18).
- **Hand edits:** InputMgr.session is `struct BackupSession *` (tag only: input.h cannot include
  backup.h because bootup_uso_ncc_11E00.cpp builds without u8 / s8); arc init / reset, mgr init / display,
  h2h init on the subclass structs; ArcRace / ArcDataManager courseList typed `ArcCourseList *`
  (mgr keeps s32: other layout); MgrRace overlayAlpha 0x7A0, fade7A4, retriesVel 0x7B8;
  GameDemoProcess unused6A8.

**Next (H2).** The DataManager update bodies (arc / mgr / h2h / edd: `p` / `a1` caches are levers; field
names can go on with casts). Name the RaceTracker head (0x0C is the node-name word every init writes,
race.h has it in unk00[0x10]) and entry fields unk08 / unk10 / unk28 now that setEntryXZ / Speed / Health
show them (x position, speed, health) - race.h is agent-c's file, coordinate. The mode race ctors and
mgr drawIntro / drawHud could take MgrRace fields (lever-heavy). genproc's SelectWin / SelItem `_func_` /
`vfuncN` / `stateN` names (timproc_b5) were left to agent-c (H1 owner).

## H1. timproc (time attack), trkproc (trick mode), genproc (select screens) (agent-c run 459)

agent-c run 459, branch agent-c on 8239918e8. Pure rename commits 60938d18f (timproc + trkproc, 119 names)
and e5cb31c8f (genproc, 193 names). Both gated (PASS, ROM identical). The only functions left
unnamed are the three `*_func_00000000` sentinels.

### Which module is which

The splat segments `timproc_uso_b1/b3/b5` are three *different* USOs that happen to sit in the
timproc ROM range. Each one is the Text section of a module:

| segment | module | inner header | Text (ROM) | size |
|---|---|---|---|---|
| timproc_uso_b1 | timproc.uso (TIMEATTACK) | 0x5AF114 | 0x5AF21E | 0x2EE0 |
| timproc_uso_b3 | trkproc.uso (TRICKMODE) | 0x5B3DE2 | 0x5B3EC6 | 0x30E0 |
| timproc_uso_b5 | **genproc.uso** (select screens) | 0x5BCA4E | 0x5BD2C2 | 0xE620 |

So b5 is not the replay. The replay viewer is viewrec.uso (0x642346), which has no splat code segment.

**Module ids** (Sym import `info >> 4`) follow the ROM file order. This is checked against bootup = 0,
gui = 18 and game = 46:
0 bootup, 1-3 audio_bank/seq/wave, 4-12 the nine character USOs (tahoe151 ... penguin),
13-17 boarder1-5, 18 gui, 19 n64proc, 20 titproc, 21 eddproc, 22 mgrproc, 23 arcproc, 24 h2hproc,
25 timproc, 26 trkproc, 27 trnproc, 28 genproc, 29 gamegfx, 30 charsel, 31 charsps, 32 viewrec,
**33 nameent**, 34 charfir, 35 charmap, 36-45 map1-10_data, 46 game.

Tool: /tmp/claude-1000/c459/dis.py (`dis.py gen|tim|trk|game|gui|boot [START END]`). It is agent-g's
g456 dis.py extended to these three modules and gui. Imports are resolved through bootup / gui / game
Sym tables, and other modules print by name (`nameent:69`, `charsel:20`). `data.py MOD START END`
dumps Data with DataReloc targets, which is how the vtables were read.

### timproc / trkproc (twins)

The two modules are almost identical, so trk names mirror tim names (`tim_`/`Tim*` vs `trk_`/`Trk*`).

- **`tim_main` / `trk_main`** (0xB0, the Data 0x18 entry table) runs the mode flow. It switches on the
  flow state at boot Bss 0x138 (inside the input-manager global at Bss 0xF8; +0x44 = the "next state"
  argument):

  | state | action |
  |---|---|
  | 0-3 | gl 8AE4(this, 1, 7, flags 1/1/2/4), then go to 4 (probably the genproc select step; 8AE4 is in the o0_8AE4 launcher family) |
  | 4 | open the session (`*_openSession`) |
  | 5 | game_loadUso, then the race: `TimRace_ctor` |
  | 6 / 7 | open the session with boot Bss 0x270, then gl 9100 + TimRace (the menu's "ghost" row; unconfirmed) |
  | 8 | close the session, then go to the stored next state |
  | 9 | close the session, then 10 |
  | 10 | `TimMenu_ctor` |
  | 11 | name entry (`app_launchNameEnt`) |
  | 12 | `app_launchViewRec` (replay) |
  | 13 | QuitProcess |

- **TimRace / TrkRace** ("TIMRace Process", 0x730 bytes) derive from the game_libs 0x6900 race-object
  base (Process-derived, vtbl ~34 slots). Overrides are named by role, and the slot is in the commit /
  tsv comment: 18 startHud, 20 checkRecord (compares the run with the stored record, then
  TimNameEntry), 21 onFinish (next state 12 / 9), 22 setMenuState, 23 showMessage, 24 unreachable
  ("Why is the code in here???"), 25 runPauseRow, 26 quit, 30 drawHud. Trk differs: vslot 16
  showHud, 18 isHudBusy, 27 startHud. Pause rows: continue, row1, exit1/2/3 (state 8 with 1/2/3),
  quit (8 with 13).
- **TimMenu / TrkMenu** ("TIMMenu Process"): seven rows, rowRetry (4), rowGhost (6), rowToggle (Bss 0x240
  A878 sets 2 / 1 into +0x50), rowExit1-3, rowQuit. Process vslot 12 = update, 13 = draw.
- **TimNameEntry / TrkNameEntry** (vtbl Data 0x138) derive from **nameent.uso export 69**. Its other
  slots are nameent exports 18-27.
- **TimDataManager / TrkDataManager** ("DataManager", 0xE0, game_libs C784 base, at race +0x6A8 and
  boot Bss 0x230) build the HUD. Tim adds Speed / Course / Time / Cool + BestTimeGadget. Trk adds
  PointsGadgetList / Speed / CountDown / Course / Points + BestScoreGadget.
- `ParmInt/Float/Quad/Vec3_read_ADDR` are the per-TU parm vtables (Data 0xD8..0x120: slot read = skip
  the tag, then read the value into +0x10). They sit on `*_streamRead{S32,F32,Quad,Vec3}` over
  fs_gdlReadFile(boot Bss 0x3C740). game_libs has the same family at 0x4104 (unnamed, area D).

### genproc (the select screens)

genproc is the shared "pick character / board / course / level" step. Its classes, with their vtables
(Data offsets):

| class | vtbl | ctor / create | notes |
|---|---|---|---|
| GenCourse | 0x18 | GenCourse_ctor 58 | "GENCourse Process"; pause-menu style rows |
| GenSelectChar | 0xD8 | GenSelectChar_ctor 478 | "GENSelectCharacter Process"; rom/1psel.bin or 2psela / 2pselb + selinfo.bin |
| SelectionMgr | 0xF70 | SelectionMgr_ctor 18B4 | one SelectWin per player (rom/selwin1 / 2a / 2b.bin) |
| SelectWin | 0xDEC | SelectWin_ctor 4118 | "SelectWin::Parms" (cwt voy ysp hxp ... tpy); update = 11-state switch (RoData 0x190) -> `SelectWin_state0..10`; state 3 = course ("track cheating %s"); startGame ("Cheat was on, choosing %d") |
| SelItemsMgr | 0xD84 | SelItemsMgr_ctor 8FC8 | "Common Info" (CommonInfo, 0xD24), "DispItems" (0xCC4), the four lists |
| Character / Board / Course / Level List | 0xB04 / 0xB74 / 0xBE4 / 0xC54 | `*List_createItem` (vslot 10) | base SelItemList (vfunc8 D06C, vfunc11 D0DC) |
| SelItem | 0x2F4 | (abstract) | "SelItem::Parms" / "SelItem::Info"; slots 10-20 pure, 21-26 empty, 27 = 3F18 |
| CharacterItem / BoardItem / CourseItem / TesuriItem / LevelItem | 0x5E4 / 0x6D4 / 0x7C4 / 0x8B4 / 0x9A4 | from the lists | overrides named `Class_vfuncN_ADDR` (slot N) |
| SelCharacter / SelBoard / SelCourseMap / SelTesuri | 0x57C / 0x444 / 0x514 / 0x4AC | QNodes | the 3D display models |
| SelCharAnim | 0x248 | in CharacterList_createItem | RiderAnim base (gl 62E80) |
| RoomModifier | 0x3E4 | RoomModifier_ctor 10EC | room scene; gen_buildRoom / createLights / createVRBox (charsel.uso walls) |

"Tesuri" is Japanese for handrail (the course list shows it next to the course maps).
`gen_createScene` builds the "MainGame" node with bg / fg children.

### Next

- The race-object base (game_libs 0x6900, vtbl slots 12-33) is area D's. Naming its slots would turn
  the `TimRace_*` role names into confirmed overrides. (Done: agent-a run 462 named the base, agent-h
  run 471 renamed the TimRace / TrkRace overrides to the base slot names; see H2 run 471.)
- The gl 8AE4 / 8E48 / 9100 launchers (area D o0_8AE4) take (this, 1, 7, flags). Confirm that 8AE4 loads genproc.
- The genproc import list of bootup is in 1080_GAME_CLASSES.md section 8 (BGBox_ctor, U64BGWall_ctor,
  2060, 2C94, 34E8, B1B4, B49C).

### Run 464 (agent-c): select.h, accessor and slot names

Commits on agent-c (base 42f08ef0b): deb2060be (pure rename, 70 names), 8bc75a093 (hand edit:
include/game/select.h and conversions), 294b1f461 (hand edit: audio.h SoundObj, see 1080_AUDIO.md),
0b8fe9fcc (pure rename, 12 bootup SndHandle wrappers). Each gated PASS.

**Vtable layout.** genproc classes are cfront Nodes (vptr +0x28). The function word of virtual slot N
is at **vtbl + 8*N + 0xC** (its s16 delta at +8). Checked three ways: SelItemsMgr calls list slots 8 / 11
at 0x4C / 0x64; slot 21 (0xB4) gets the other player's item, which matches CourseItem's two-argument
state copy; slot 26 (0xDC) gets (win, 8), and Character's arrow draw tests flags & 8.

**include/game/select.h** (offsets and sizes asserted):
- `SelItem` 0x2B8: x 0x44, y 0x5C, labelIndex 0x1AC, node 0x29C, alpha 0x2A0, enabled 0x2A4 (f32, 0 =
  locked), id 0x2B0 (written out by commitSelection), flags 0x2B4. `SelItemEx` adds model 0x2B8 (the
  per-class QNode state; its layout differs per class, so it stays `char *`) and the stat-bar counters
  0x2BC / 0x2C0.
- `SelItemList`: items[12] 0x3C, count 0x6C. `SelItemsMgr`: count 0x3C, lists[4] 0x40 (character,
  board, course, level = the stage index).
- `SelectionMgr`: numPlayers 0x30, wins[2] 0x34, busy 0x4C.
- `SelectWin` 0x4F0: player 0x3B8, numPlayers 0x3BC, stageMask 0x3C0, stage 0x3C4, stageBit 0x3C8,
  state 0x3CC (the update switch), curItem[4] 0x3D0, chosenItem[4] 0x3E0, prevStage / prevItem
  0x3F0 / 0x3F4, itemsMgr 0x40C, scene 0x414, owner 0x41C, fade 0x480, blink / frame 0x48C / 0x490,
  busy 0x4B4, camPos 0x4C4, eventFlags 0x4D4, centerX 0x4D8, out[5] 0x4DC.

**Converted** (object bytes identical): SelectWin_curItem / prevStageItem / chosenItem / chooseCurrent /
prevFocusItem / itemCount / listCount / saveFocus / beginTransition / func_8D90,
SelectionMgr_otherWin, and 35 item virtuals. The in-TU forward declarations of converted functions
became unprototyped `f()`, so the many `(int *)scr` callers did not have to change. Left raw (lever
bodies): findItem (8988), canScrollPrev / Next, next / prevStageBit, the state functions, the
updateHighlight family, CourseItem_update.

**Names.** `SelectWin_finish / _func_1CF0 / _1D1C` take SelectWin->owner, so they are now
`SelectionMgr_*`. Item slots: 10 updateHighlight, 11 focus, 12 unfocus, 15 setChosen, 16 clearChosen,
20 confirm, 21 copyState, 22 setAlpha, 23 drawLabel, 25 drawStats, 26 drawArrows. Slots 13 / 14 / 17-19
/ 24 stay `vfuncN`: 13 is beginTransition's mode-2 unfocus, 17 toggles a flag bit (Character 0x20000,
Board 0x20), and 18 / 19 are Character animation changes.

### Next (H1)

- Per-class model structs (SelCharacter / SelBoard / ...: focused / chosen / highlight / alpha
  fields at different offsets per class) would let the `it->model + K` accesses go.
- SelectWin state functions and display: convert onto the struct (lever-heavy, so check them one at a time).
- Slots 13 / 14 / 17-19 / 24; SelectWin_func_8D90 / 894C / 8C44 / 8D38 (save-flag bit scan) / 38B0 / 396C / 3A28.
- Area 3 of run 464 was not reached: the 25 non-audio placeholders in game_libs_post.c and about 20
  kernel placeholders (kernel_056 / kernel_000, rmon).

### Run 469 (agent-c): include/gdl/race.h, race data model

Commits on agent-c (base 19f8e0b6f), all hand edits, each gated PASS (3288/3288, objects identical):
4902c9a23 (race.h + hud.h), 0e3ef6fc4 (game_libs.c RaceProcess conversions), 5291c3b6d (game_libs_tail.c
RaceTracker conversions), 4611aed41 (TimRace + timproc / trkproc conversions). No renames.

**include/gdl/race.h** (offsets and sizes asserted):
- `RaceProcess` 0x6A8 (size = where TimRace's own fields start). Node head (name 0x0C = the init arg
  "TIMRace Process", children 0x10), `vt` 0x28 (`RaceProcessVt`: slot N fn at vtbl + 0xC + 8N, `RACEVT_*`
  indices for 14 / 15 / 28 / 29 / 32 / 37), parms 0x50 (loadData), colour[6] 0x68..0x11C (sprite colour
  pairs), then the race state: subState 0x4D8, raceState 0x4DC (`RACE_STATE_*`), phase 0x4E0
  (`RACE_PHASE_*`), timer 0x4E4, countStep 0x4E8, flags 0x4F0 (`RACEF_*`), timeout 0x4F4, result 0x4F8
  (`RACE_RESULT_*`), leave 0x500, leftOnce 0x510, endCounter 0x518, replayCam / savedCam 0x51C / 0x520,
  session 0x528, scaleX/Y 0x534/0x538, countAlpha 0x540, msgAlpha / msgX / msgY / msgVel / msgFloor
  0x544-0x554, spriteSet 0x568, handler 0x56C, sprites[12] 0x588 (RaceSprite 0x18; slot order = ids
  0x60000, 3, 4, 5, 1, 2, 6, 7, B, 8, 9, A).
- `TimRace` 0x730 (tim and trk identical): race, dataManager 0x6A8, finalTime 0x6AC, recordRank 0x6B0,
  labels[5] 0x6B4, recordFade 0x72C.
- `RaceTracker` 0xB8 (RaceTracker_ctor alloc; vtable Data+0xD678). **It is the HUD object**: `Hud` in
  include/gdl/hud.h is now `typedef RaceTracker Hud`, because RaceTracker_update dispatches the hud gadget
  slots 0x70 / 0x78 / 0x8C / 0x98 with their value pointers. Fields: active 0x2C, elapsed 0x30 (ms),
  timeLimit 0x34 (600000), course floats 0x38-0x40, entries 0x44, numEntries 0x48, session 0x4C, the gadget
  slots 0x54-0x9C, score 0xA0, bonus 0xA4, hudFlags 0xB4 (`RTF_*`; bit meanings are from the gated users).
- `RaceEntry` 0x60 (8 per tracker): rider 0x00 (the key of the find function), flags 0x04 (bit 0 active),
  progress 0x0C, time 0x14, pendingPoints / pending 0x1C / 0x24, pct 0x30, finished 0x34, rank[3] 0x38,
  gate 0x4C, gateA / gateB 0x54 / 0x58. `RACE_ENTRY_AT(t, off)` covers the loops that step a byte offset.
- **The race session** is one object seen from two sides: RaceProcess.session (0x528) and
  RaceTracker.session (0x4C). Its +0 is the course record table (0x30 bytes per course, indexed by the game
  global +0x64; records are compared on bytes 5-7 in TimRace_checkRecord), and +0x14 holds the mode bits
  (bit 0 / 1 / 2 select which rank lists hud_loadRecords fills). It comes from `*_openSession`
  (Backup_openSession). Its own struct belongs with the Backup records (BackupCourse etc.), not yet typed.

**Converted:** 16 RaceProcess_* bodies (all but handleInput / drawResult, which are splices, and the empty
stubs), 21 RaceTracker / hud bodies, and 9 + 1 Tim / Trk bodies. Virtual calls are written
`vt->slot[RACEVT_X].fn((char *)self + vt->slot[RACEVT_X].delta)` and compile to the same lh / lw / jalr t9.
Typed `entries[i]` indexing compiled identically wherever it was tried (CA30, DB80 family, CE38).

**Left raw:** the NON_MATCHING bodies (RaceTracker_update with its private CBF0_Self, findGates, D288), the
int ** / int-param bodies (DDE0 family, D418, E118, handleMsg), TrkRace_checkRecord (`saved = a0` alias),
both runPauseRow (`self[(0x48/4)^0]`), the Tim / Trk ctors (inlined Node -> Process -> RaceProcess chain),
and the arc / mgr / h2h race processes.

### Next (run 469)

- arc / mgr / h2h race processes: they use the same RaceProcess base; each needs its derived struct (sizes from
  their ctors) and the same conversions.
- RaceTracker vtable slots (10 handleMsg path 0x58, 11 = vslot11_0000D318, 12 / 13 the E044 / E050 stubs,
  0x68 / 0x70 slots called by E05C / E118) and the DataManager subclasses (0xE0).
- The genproc items (per-class SelItem model structs, slots 13 / 14 / 17-19 / 24, SelectWin state
  conversions) and the game_libs_post.c non-audio placeholders (134 placeholder-named definitions still
  match `(gl|game_libs)_func_`, most of them audio) were not reached this run.

### Run 474 (agent-c): backup.h, genproc slots and item models

Commits on agent-c (base a9f6f0192), each gated PASS (3288/3288, ROM identical): b9207cb69 (hand edit:
include/gdl/backup.h + Backup / session conversions), ca5180a9b (**pure rename**, 27 genproc slot names),
6a1079b0a (hand edit: select.h item models + 35 item virtual conversions).

**include/gdl/backup.h** (offsets and sizes asserted):
- `BACKUP_SRAM_*`: every chunk offset, its checksum and the mirror pair (1080_SYSTEM_LAYER.md section 4);
  `BACKUP_CHUNK_KEY` 0xDEADBBAD, `BACKUP_HEADER_KEY` 0xD1265205.
- Records: `BackupTimeEntry` (8: flags with `BACKUP_ENTRY_VALID` 0x80, extra, name[3] as letter - 'a',
  time[3] = min / sec / hundredths), `BackupScoreEntry` (8: flags, name[3], s32 score),
  `BackupCourseRecord` (0x30: times[3] then scores[3]), `BackupCourse` (8 courses, 0x180),
  `BackupArcadeEntry` (0x20: flags word, count, name[3], stages[5], score), `BackupArcade` (3 entries),
  `BackupOptions` (0x18), `BackupGhost` (0x10: bits = mode 0-1 / course 10-13 / three more fields, count,
  data, unkC), `Backup` (8).
- `BackupSession` (0x18) = the record session: course / arcade / ghost (Backup_readCourse / readArcade /
  readGhost), unkC, backup (openSession arg 1), modes. `BACKUP_MODE_TIME` 1 (tim_openSession), `TRICK` 2
  (trk), `ARCADE` 4. openSession keeps the saved ghost only if its mode and course match.
  RaceProcess.session / RaceTracker.session are now `BackupSession *`.
- Converted: openSession / closeSession, the session-level B208..B710 family, read / write / check of every
  chunk (macros + sizeof, the 384 / 96-byte copies are now BackupCourse / BackupArcade), the entry
  accessors (9978..9D00), the ghost bitfield accessors (A878..A96C, A990, AA7C), hud_loadRecords,
  RaceProcess_restartCameras / restartWithTimeout, TimRace / TrkRace mode tests.
- Kept as int reads (load-bearing): `FW(m, 0x0)` in hud_loadRecords and `*(int *)s2->race.session` in the
  Tim / Trk checkRecord (a `(s32)m->course` cast renumbers the multu temps); `~0x80` cannot replace the
  `&= 0x7F` clears (andi 0xFF7F). Left raw: the record-list helpers with loop levers (99DC / 9B60 / 9C5C /
  9D24 / 9DB8 / 9EBC / A00C..A540 / A670 / A7B4 / AAEC..AD9C, resetOptionsData) - they still take char * /
  int *; their record types are documented in backup.h.

**genproc slots** (fn word at vtbl + 0xC + 8N): 13 `onStageLeave` (accept, state 7), 14 `onStageReturn`
(cancel to state 6 / state8 scroll), 17 `toggleVariant` (L / R toggles the flags bit), 18 `playPickAnim`
(state4 accept into zoom state 5), 19 `playAcceptAnim` (after confirm unless cancelled), 24 `drawSubLabel`
(SelectWin draw, states 6 / 7, previous-stage item id or 5 / 6 / 7).

**select.h item models:** `SelCharModel`, `SelBoardModel`, `SelCourseModel`, `SelTesuriModel`,
`SelLevelModel` (common idea: view[4] copied by update, alpha, highlight faded by updateHighlight, focused
forces the highlight, chosen; Board / Course add `lit`), and `SelCharacterItem` ... `SelLevelItem` =
SelItemEx with the typed model.

### Next (run 474)

- SelectWin state / display functions (state0..10, updateHighlight family, the 0x6394 draw): convert onto
  SelectWin / the typed items one at a time; they are lever-heavy (`FW` chains, `if (1)` blocks).
- The item updateHighlight / update bodies onto the model structs (levers: `if (1) { v = ... + 0x130 }`).
- The Backup record-list helpers onto BackupTimeEntry / ScoreEntry / ArcadeEntry (check each; loop shapes
  are levers). InputMgr.session could become `BackupSession *` (titproc assigns it from an int).
- SoundObj conversions (run-464 leftovers) were not reached.

### Run 478 (agent-c): weak names (Backup, genproc, nameentry, sound) and record-helper types

Commits on agent-c (base 5a8efa2ab), each gated PASS (3288/3288, ROM identical):
1349b1c39 (**pure rename**, 63 Backup helpers), ff130a997 (**pure rename**, 31 genproc / nameentry),
aff387302 (**pure rename**, 45 sound names, see 1080_AUDIO.md), 21ccb8f7d (hand edit: backup.h
`BACKUP_ENTRY_NEW` + record helpers typed), a212eeccf (hand edit: SelectWin cheat fields).

**Backup**: see 1080_SYSTEM_LAYER.md section 4 "Record helpers". Every `Backup_func_` is named. The
record-list helpers now take BackupCourse / CourseRecord / TimeEntry / ScoreEntry / Arcade / ArcadeEntry.
Typed `p++` walks and `&rec->times[k]` compiled identically. The `(char *)a0 + idx * 8` callee arguments
in the Insert functions did not, so they stay as they were.

**genproc** (call sites from `scripts/emu-symdump/timproc_uso_b5.reloc-sites.json`; `resolved - tbase` =
callee offset):
- **Cheat input.** On the character stage (state3) and the board stage (state6), SelectWin matches pad
  sequences: Data 0xF60[step] = word lists ending in 0x100, with sound 0x27 on success.
  `SelectWin_charCheatIndex_8C44` picks the sequence for the focused character (1-2 from the table at Data
  0xF1C, 3 for item 4 with unlock bytes FC FF 07). `boardCheatIndex_8D38` returns 3 when all 24 bits at
  InputMgr.unlocks +6 are set. `resetCheat_8D90` clears the result. Fields: `cheatChar` 0x4A4,
  `cheatBoard` 0x4A8, `cheatStep` 0x4AC, `cheatTimer` 0x4B0. SelectionMgr_ctor's state names include
  "CrystalGuy" / "MetalGuy" / "Panda", which are probably what these cheats unlock.
- Camera: `lerpCamToItem_38B0` / `lerpCamToItemZoom_396C` (update; the state-5 zoom uses the item 0x184
  offset, the others 0x164) and `setCamToItem_3A28` (ctor).
- `SelectionMgr_canCommit_1D1C` gates commitSelection: in 2P, both windows must be on the same stage.
  `setSplit_1DB0` divides the 240 lines between the windows. `onFadeDone_0470` is the empty Process slot 11.
- SelItem sprite helpers: `drawStatBar` / `drawStatBarRight` / `drawSpritePlain` / `White` / `Color` /
  `ColorEx`.
- Slot 8 is `loadData` (SelectWin, SelItem, SelItemsMgr, SelItemList, CommonInfo). SelItem slot 27 is
  `loadInfo` (the SelItemInfo at +0x194), forwarded by SelItemList slot 11 and SelItemsMgr slot 10.
- NameEntry slot 17 `showRecord` (Tim / Trk / Arc: the base call, then the race helper at y 0x8C with the
  final time or score) and slot 18 `fadeRecord` (Mgr: `fadeOut`).

**Tried, reverted:** typing SelectWin_state6 onto `SelectWin *` renumbers the t-registers in its
0x100 / 0x200 rows, even with the byte-offset `curItem` form. state6 stays `FW()`.

### Next (run 478)

- SelectWin state0..10 and the display: bisect state6's t-register renumbering (convert one row at a
  time; the eventFlags / curItem loads were the first differing pair) before trying the others.
- Item `updateHighlight` / `update` onto the Sel*Model structs (run 474 levers).
- Remaining SoundObj conversions (1080_AUDIO.md Next 3).
- Kept weak: `SelCharAnim_vfunc10_0000ABB4`; AnimPlayer slot 10 (`AnimPlayer_vfn10_00063704`, empty) is
  unnamed.
- The ghost Bits2 / Flag5 / Bits6 meanings: read the game global +0x181..0x183 users (game_uso).

### Run 484 (agent-c): SelectWin field conversions, item models, ghost fields

Commits on agent-c (base db64f9963), each gated PASS (3288/3288, ROM identical): 0a680ee86 (hand edit:
select.h `SELWIN` + SelectWin state / display conversions), 64952d446 (hand edit: item updateHighlight /
update onto the Sel*Item / Sel*Model structs), d8d943852 (hand edit: SoundObj, see 1080_AUDIO.md),
305390099 (**pure rename**, 6 ghost accessors), 691970d5b (hand edit: input.h / backup.h ghost and
player-select fields).

**state6 bisected.** The only field whose struct-member form renumbers the t-registers is `eventFlags`
(0x4D4), wherever it is an `|` operand (`elem | eventFlags`, `(id + 1) | eventFlags`): the member load
takes its temp later (t8 instead of t6). Swapping the operands, an `(int)` cast or turning the pad before it
into a word did not help. The same holds in state0 / 3 / 4 / 7 / 8 / 9, so eventFlags stays
`FW(w, 0x4D4)`; every other scalar field converted with identical bytes.
- `SELWIN(p)` (select.h) = `((SelectWin *)(p))`. The state functions keep their `char *` parameter,
  because their `arg0 + stage * 4` cluster offsets and `(&D_...)[stage]` spellings are matching levers.
- Converted (field by field, each object-identical): state0..10, display, init, startGame,
  commitSelection, moveCursorPrev, canScrollPrev / Next, next / prevStageBit (stage, stageBit, state,
  player, numPlayers, busy, blink, frame, fade, unk484, camPos, scene, cheat*, unk4BC / 4C0 / 4A0 ...).
  Left raw: eventFlags, the curItem cluster offsets, pointer fields other than `scene` (itemsMgr / owner
  are read as `char *` / `int`), and the bodies that index with `((int *)a0)[N]` / Row structs
  (skipDisabled, findItem).
- Items: the five updateHighlight bodies take their typed item (`it->base.enabled`, `it->model`,
  `st->focused`, `st->highlight`; the `if (1) { v = (float *)((char *)v + K); }` lever stays), and the five
  update bodies store `p->view[0..3]` through the typed model. The item-side +0x25C / 0x260 / 0x264 /
  0x294 floats they copy are still unnamed.

**Ghost fields (InputMgr, include/game/input.h).** The game global the select screens write is the
InputMgr: SelectionMgr_ctor passes SelectWin_init the out pointers +0x68 level, +0x4C rider, +0x50 flags,
+0x54 board, +0x64 course (player 2: +0x58 / 0x5C / 0x60). replay_beginRecord* copies course / rider /
flags / board into the bytes +0x178..0x17B, replay_saveGhost passes them to Backup_ghostSetHeader, and the
BackupGhost bits are 2-4 rider, 5 the board flag (0x20, BoardItem's toggleVariant bit), 6-9 board. titproc's
vs-ghost states copy them back (Backup_ghostGetRider / BoardFlag / Board = titproc callees 0x1EF10 /
0x1EF44 / 0x1EF94) into +0x181..0x183, which game_setupVsGhost uses for the ghost rider exactly as
+0x4C / 0x50 / 0x54 for the player. Accessors renamed; InputMgr fields added (playerFlags, playerBoard,
rider2 / flags2 / board2, rec*, ghostRider / ghostFlags / ghostBoard).

### Next (run 484)

- titproc `*(char *)(d + 0x181..0x183)` writes and its `titproc_uso_func_01EF10 / 44 / 94 / C8`
  placeholders (= Backup_ghostGetRider / BoardFlag / Board / Course) belong to the titproc owner; the
  bootup replay_* (o0 files) and game_setupVsGhost / game_setupReplay can take the InputMgr fields
  (check each: the -O0 files and the CFG array spellings are levers).
- SelectWin: name unk3F8 / 400 / 404 / 484 / 488 / 4BC / 4C0 from their users (unk484 = 1.0 / 0.0 at the
  stage transitions, unk400 = 0x37 in state4); type itemsMgr / owner accesses where the reads are
  `char *`; SelItem +0x25C..0x294.
- SelectWin_update in timproc_uso_b5_o2_5FC0.c (separate TU) is unconverted.

### Run 490 (agent-c): replay path, titproc ghost imports, SelectWin fields

Commits on agent-c (base 9dcd5ce48), each gated PASS (3288/3288, ROM identical): 391b5617c (**pure rename**,
41 audio names, 1080_AUDIO.md), 99089df64 (hand edit: InputPad replay fields, InputFrame, InputMgr
recordBuf / recordCap, Backup.ghostMaxFrames; bootup replay_* and game_setupSolo / VsGhost / Replay
typed), dad315573 (**pure rename**, titproc_uso_func_01EF10 / 44 / 94 / C8 -> tit_imp_Backup_ghostGetRider /
BoardFlag / Board / Course: titproc import T = game_libs + 0x1466C), e8eee189b (hand edit: tit_procMain
states 7 / 9 write ghostRider / Flags / Board), 89d5eb92c (hand edit: SelectWin prevItemActive, idleTimer,
transition, fovTarget / fovBase / fovFrom; SelectWin_update donor on SELWIN).

The replay / ghost format for port authors is docs/1080_REPLAY.md (4-byte InputFrame per frame,
pad_update RECORD / PLAY, the bootup replay_* API, which game_setup* records or plays, the SRAM ghost).

Next:
- Who calls replay_saveGhost with which mode (symbolize the timproc / trkproc TextRelocs as
  /tmp/claude-1000/c478/buxref.py does for bootup); `replay_addInput` (0x11CA4) adds the race pads
  (+0x100), "race pad" may be the better name; InputMgr +0x184.
- SelectWin: unk3FC / 400 / 404 / 484 / 4B8 / 494 users are known (see select.h comments) but not their
  meaning; the item +0x25C..0x294 floats; eventFlags stays raw.
- Not started: the genproc / select-screen ctors' vtable stores via agent-a's `_vtbl` aliases.

### Run 492 (agent-h): race / DataManager field conversions in the mode modules

Commit a1a61e1b5 on agent-h (base 07b9b8571; hand edit, gate PASS 3288/3288, ROM identical, every
touched .o identical in the matching and NON_MATCHING builds).

- Cast macros: `NODE(p)` (gdl/node.h); `DATAMGR(p)`, `TIMDATAMGR(p)` (gdl/race.h, which now includes
  node.h); `ARCRACE / MGRRACE / H2HRACE(p)`, `ARCDATAMGR / MGRDATAMGR / H2HDATAMGR(p)` (game/modeproc.h).
  They join RACEPROC / TIMRACE (run 487) for bodies whose untyped parameters / locals are levers.
- New struct `TimDataManager` (race.h, 0xE0): race 0xB8, rankLabel 0xBC, colour[4] 0xC0, alpha 0xD0,
  unkD4, beepTimer 0xD8, unkDC (1 after init; with 2 entries mirrors entries[1].rider->0x800->0x4C, and
  a 1 -> 0 edge calls (this, 1)). TimDataManager_init / _update are fully typed. TrkDataManager shares
  the 0xB8..0xD7 tail (TIMDATAMGR is used there with an offset whitelist) but its 0xD8 is a once-flag.
- New field names: RaceProcess dropX / dropY / dropVel / dropFloor (0x558..0x564, mgr's second
  bouncing sprite, sprites[11]); RaceTracker shownScore (0xA8), blinkTimer (0xAC), owner (0x50),
  ghostFlag (0xB0); MgrRace lostX / lostY / lostVelX / lostVelY / lostFalling (0x7B0..0x7C4, the used
  retry icon); H2HDataManager beepTimer (0xD4).
- Census of `*(T *)(p + 0xNN)` (regex in /tmp/claude-1000/h492/census.py), before -> after:
  arcproc_uso_tail1.c 198 -> 61, mgrproc_uso.c 249 -> 50, timproc_uso_b1.c 173 -> 108,
  timproc_uso_b3.c 242 -> 117, h2hproc_uso.c 49 -> 15, game_libs_tail.c 56 -> 46.
  Converter: /tmp/claude-1000/h492/conv.py (per-function base -> macro list, header-parsed layouts,
  type-checked, lvalue-aware; configs *.cfg next to it).
- Kept raw on purpose: ARCRaceProcess_drawIntro's `count == idx + 1` (the ArcCourseList member form
  swaps the two loads' registers); TrkDataManager_update's int and char ** reads of 0xB8 (two load
  chains are its lever). MGRRaceProcess_drawHud: `x = v + x` became `x = x + v` for lostX / lostY /
  dropY, because with members IDO loads a commutative pair in the opposite order.
- What is left raw: Node vtable-slot calls (`*(short *)(vt + 0x58)` / `+0x5C`), the name-entry
  overlay objects (0x10C / 0x174, no struct), sprite internals (`*(char **)(race + 0x6E4)` = a
  RaceSprite's +0x10 image), int reads of f32 RaceEntry fields (posX / progress / pct as bits),
  entries[1] reads at +0x60.. (beyond one RaceEntry), the score pop-up slot objects that
  RaceTracker_pop* fill (+0x44 y, +0x5C, colour +0x64..0x70, +0x78 alpha, +0x9C life, +0xA0 font sprite =
  pointsList + 0x108 / 0x138 / 0x150, +0xA4..0xAC), the Tim / Trk / Arc menu processes (arg0 + 72 ...).

Next:
- A struct for the pop-up slot object (built by PointsGadget_ctor_00003138's 8 slots; GlSlot3B1C in
  game_libs.c already has 0x78..0xB4) would take game_libs_tail's RaceTracker_pop* (~60 sites).
- NameEntry overlay structs (Tim / Trk / Arc 0x10C, Mgr 0x174: +0x60 mode, +0xD4 owner race,
  +0xD8..0xEC positions, +0x108 / +0x168 fade) and the Tim / Trk / Arc menu process layout.

### Run 496 (agent-h): bootup_uso / titproc / pop-up field conversions

Commits on agent-h (base 9306a6ed3; all hand edits, no renames; gate PASS 3288/3288, ROM identical,
every touched .o identical in the matching and NON_MATCHING builds, objdump -d -r compare):
c0f5a23e8 (bootup SnowBoarder / WorldRegistry / Node), b6ceccaeb (bootup lights / cameras),
fdd6f7ea7 (PointsPopup), 02b9e0f9a (titproc TitleDemoProcess).

- **WorldRegistry is the game_* scene object** (InputMgr +0x134 `game`, course.h): game_setParams fills
  ogRoot / fgRoot / bgRoot / egRoot / mainGame; new fields unk98 (two floats at +0xC4 / +0xCC go to every
  rider build), numPlayers 0xC0, players[8] (`WorldPlayer {rider, arg}`, 0xC4), windows[4] (0x108).
  `WORLDREG(p)`.
- **SnowBoarder** (snowboarder.h): `SNOWB(p)`; unk814 / 818 / 81C (ctor's bu_90cc_fz words; update writes
  landImpact to +0x94 of 818 / 81C by unk8B8 bits 4 / 1), bodyNodes[7] (0x820..0x838, the node-registry
  model nodes that SnowBoarder_update jitters by shake), unk8B8, camera (0x8DC: the race camera every
  game_setup* stores; SnowBoarder_update hands it to the sound update).
- **PointsPopup** (gadget.h, 0xD4, PointsGadget_ctor_00000ED0): the score pop-up the RaceTracker_pop*
  functions colour. x 0x44, y 0x5C, colour[4], alpha 0x78, state 0x94, value 0x98, timer 0x9C, font 0xA0,
  velX / velY, arg 0xB0, text 0xB4. game_libs.c's private `GlSlot3B1C` (PointsGadget_allocSlot_00003B1C)
  is the same object and can move onto it.
- **TitleDemoProcess** (modeproc.h): timer 0x3C, state 0x40, keyDelay 0x68; `TITLEDEMO / GAMEDEMO(p)`.
- Converter: /tmp/claude-1000/h496/py/conv2.py + layout.py (field leaves from gcc -m32 -malign-double
  DWARF of the headers, so nested structs and 2-D arrays resolve; access kind checked; `=` stores of a
  pointer into an int field, or the reverse, cast the right-hand side). Configs *.cfg next to it.
- Census of `*(T *)(p + 0xNN)` (h492 regex), before -> after: bootup_uso.c 526 -> 246,
  titproc_uso.c 102 -> 39, game_libs_tail.c 46 -> 30.

Left raw: SnowBoarder_update's int reads of lastPos.x / z (0xDC / 0xE4, random seed bits) and the
short store to hitFlags (u16 field); game_addPlayer / addWindow index arithmetic (rule 4a); the
BaseLight colour parm floats (light.h types the 0x10C parm group as s32 words; agent-b's header).

Next:
- bootup: game_init's `scene` (+0x3C, +0x134: probably InputMgr, unproven), Tv1Tmpl / FogTmpl /
  SnowTmpl / TreeTmpl (their parms are CourseParm records: `c + 0xC / 0x10 / 0x14`), SnowBCollider
  (+0x170 / 0x174), FallingSnow, ShpNode_func_00008FA8, U64BGWall_ctor, EnvSettings_ctor.
- NameEntry overlay structs (0x10C, mgr 0x174) and the Tim / Trk / Arc menu processes (not reached this run).
- titproc: MainLogo / KeyMessage fields, GameDemoProcess_onQuitButton's menu object (+0x7C).

### Run 499 (agent-c): uso-imports.py, SelectWin fields, genproc conversions

Commits on agent-c (base 4b1c38048), each gated PASS (3288/3288, ROM identical; every touched .o
identical by objdump -d -r -z in the matching and NON_MATCHING builds): b98c196e8 (tool
`scripts/uso-imports.py`), 3af837898 (hand edit: select.h + genproc conversions), f7dd3f3b2 (hand
edit: audio cue queues, 1080_AUDIO.md), d7872181c (**pure rename**: input_setRacePadsActive,
snd_soundObjSetPan_00000B2C).

- **scripts/uso-imports.py** (static, no emulator): `list` (module ids, Info / header / Text ROM),
  `sites <module> [--type jal|hi|lo|word] [--imports] [--from M]`, `imports <module>`,
  `callers <regex>`. Kind-1 Sym imports are resolved through the exporter's Sym table; both ends are
  named from the build (tenshoe.map load addresses for uncompressed Text, the Yay0 block objects for
  mgrproc / timproc / trkproc / genproc / game). Needs a full make. Version-6 module headers
  (n64proc, gamegfx, character / data USOs) are not parsed.
- **SelectWin fields:** transCountdown 0x3FC / transCountdownInit 0x404, zoomTimer 0x400 (state5's
  auto-accept countdown), fadeProc 0x418 (Process_fadeOut by commitSelection), fadeTarget 0x484,
  fovInit 0x494, stageLock 0x4B8 (board-stage accept; the other window's state7 reads it).
  Macro `SELITEM(p)`.
- **Census** (`*(T *)(p + 0xNN)`, h492 regex): timproc_uso_b5.c 532 -> 430; FW() sites 367 -> 333
  (b5.c) and 98 -> 72 (_4118.c donor). Converter: /tmp/claude-1000/c499/py/conv2.py (agent-h's, plus
  FW() matching, an EXCL offset set, and `*FIELD = x` treated as a store through the field).
- Reverted (bytes changed): SelectWin_canScrollNext (t-regs), state8 (branch layout), the
  SelectWin_update donor (f16 / f18). setSplit's base is not a SelectionMgr (its ctor-like body
  stores the "MetalGuy" / "Panda" strings): not converted.

Next (H1):
- SelectWin 0x420..0x47C: SelectWin_init writes ~24 floats there (two camera / light blocks?);
  0x408, 0x4D0, Parms reads (+0xD4 / 0xEC / 0x104). unk410 = ctor arg 8 (the object whose +4 is the
  scene).
- SelItem +0x25C / 0x260 / 0x264 / 0x294: inside the SelItem::Parms records (Parms at +0x2C,
  records at +0x254 / +0x278 per SelectWin_display); the order copied into `view` differs per class.
- The remaining genproc raw sites are mostly scene / light / VR-box builders (gen_createLights,
  gen_createVRBox, gen_buildRoom), the list createItem bodies and BoardItem_drawStats.

### Run 501 (agent-h): bootup environment objects, InputMgr.gameMode, PointsPopup

Commits on agent-h (base db4f056b6; hand edits, no renames; gate PASS 3288/3288, ROM identical, every
touched .o identical in the matching and NON_MATCHING builds): 0b34f0d64 (envobj.h + conversions),
c0c8b013c (PointsPopup in game_libs.c).

- **include/game/envobj.h** (new): U64BGWall (0x4C), EnvSettings (0x44: clipNear / clipFar go to the gfx
  near / far +0xAC / +0xB0 when flags & 2; EnvSettings_load sets far 800 for game modes 6 / 11), FogItem
  (0x90: ColourItem pos, "fin" 200 / "rng" 300 parms, `inside`), SnowItem (0x74), FallingSnow (0x134, built
  into the snow template's +0x40; enabled 0x48), Tv1Tmpl (model 0x40, 3-state scroll / state / timer,
  displayCount), SnowBCollider (0x178, PHYSICS layout), ShpNode (DNode: pos / orient saved to lastPos /
  lastOrient, life 0x3D4). Cast macros ENVSET / FOGITEM / SNOWBCOL / SHPNODE.
- **InputMgr +0x3C = gameMode** (input.h): game_init stores its arg 2 there and game_createMap /
  EnvSettings_load read Sym 272 +0x3C; game_init's `scene` is the InputMgr (writes 0x3C, reads 0x134).
- Vtable aliases fixed: MapProp_ctor = MNode_vtbl then MapProp_vtbl; EnvSettings_ctor = EnvSettings_vtbl
  (the run-496 merge re-apply had put EnvSettings_vtbl on MapProp_ctor).
- game_libs.c GlSlot3B1C dropped: PointsGadget_allocSlot_00003B1C uses PointsPopup.
- Census before -> after: bootup_uso.c 246 -> 181 (others unchanged).
- Gotcha: converting FogTmpl_create's (NM C) parm stores grows the NON_MATCHING bootup_uso.c.o .text tail by
  8 bytes with every function identical; left raw.

Next (not reached): GameFlow / SnowBoard app / Process / PauseMenu / QuitProcess / Fader, HUD gadget parms,
the -O0 island objects; TreeTmpl / Tree (0xC8, +0x88 sub, +0xA0 copy of +0x5C); NameEntry overlays (0x10C,
mgr 0x174) and Tim / Trk / Arc menu processes; game_libs.c / game_libs_tail.c raw sites; titproc MainLogo /
KeyMessage; SnowBCollider_onContact's dead old decode (#ifdef BOOTUP_8BD4_OLD_DECODE).

### Run 505 (agent-h): InputMgr is GameFlow; dead old-decode cleanup

Commits on agent-h (base 974eada26; hand edits, no renames; gate PASS 3288/3288, ROM identical, every
touched .o identical by objdump -d -r -z + data in the matching and NON_MATCHING builds): 53804e207
(GameFlow fields), 303f4c896 (BOOTUP_8BD4_OLD_DECODE deleted).

- **The InputMgr (bootup Bss 0xF8) is the GameFlow object.** GameFlow_create names its Node "GameFlow"
  and stores every word up to 0x190; GameFlow_startMode / restart / loadProcUso / unloadUso / addPads,
  input_initDefaults, snd_playSeq and the settings_* functions all take it as `this`. input.h now has
  the Node base (as `char node[0x2C]`: NCC .cpp users cannot include node.h), procUsoPath 0x2C (the loaded
  mode .uso path: loadProcUso compares it, unloads the old module), flowProc 0x30 (the per-mode object
  startMode builds, vptr at +4, slot +0xC called), flowMode 0x38 (9 = none; the guard against
  nextFlowMode), unk70..unk88, order90[5] = {4,3,1,2,5} / orderA4[5] = {5,1,2,3,4} (initDefaults; meaning
  unknown), ctrls[2] 0xC0 (two 0x80-byte controller objects, ctor arg 1 / 2; addPads adds them or sets
  `locked`), app 0x12C (gSnowBoard), usoList 0x130 (`FlowUso {handle, next}`), seq / seqArg 0x13C / 0x144,
  flowImgs 0x150 (rom/flowimgs.bin), initials[3] 0x158 ('*' x 3), unk15C. Macro `GAMEFLOW(p)`.
- **The unlocks record (+0x154)** is the settings block: +0 u16 unlock bits (settings_setBit), +2 u16
  sequence step (settings_stepSequence), +4 u16 options (& 3 sound mode, & 4 flag 4, 8 language menu),
  +6..+0xD the 8 bytes settings_get8 copies, +0x12 / +0x13 / +0x14 the three u8 volumes
  (settings_vol1 / vol0 / vol2 Up / Down). Not yet a struct: `unlocks` is a `char *` that titproc /
  mgr / arc index by byte offset.
- Converted: GameFlow_create / startMode (plus NODE() for the child-attach idiom and the name),
  GameFlow_addPads / unloadUso / loadProcUso, input_initDefaults, snd_playSeq, settings_save / setBit,
  the six settings_vol* functions, settings_applySoundMode / setFlag4 / get8 / stepSequence, the stick
  readers. Left raw: initDefaults' `*(a0 + i + 0x158)` initials loop (index form, rule 4a), the stick
  readers' `(float **)(a0 + 0xE0)` pad table (InputPad is not float-first).
- **Dead code:** the BOOTUP_8BD4_OLD_DECODE block (100 lines + its stale cap history) is gone; nothing
  defines the macro. Still in the tree, all never compiled (no -D in the Makefile, no #define anywhere),
  not deleted this run because the Edit-only rule makes each a full-text Edit: bootup_uso.c
  `#if 0` after the cam_create placeholder (121 lines), BOOTUP_55A0 (318), BOOTUP_90CC (1060),
  BOOTUP_B75C (254), BOOTUP_C234 (311); titproc_uso.c `#if 0` after TitleDemoProcess_handleInput (302);
  game_libs.c `#if 0` after RaceProcess_handleInput (376); gui_uso.c five `#if 0` cfe bodies after the
  splice hosts gui_drawStringScaled / drawSpriteScaledF / drawSpriteScaled / drawSpriteScroll /
  texRect (100 / 89 / 93 / 145 / 167). The #ifdef ones keep their placeholder in an `#else` branch.
- Census (`*(T *)(p + 0xNN)`, h492 regex): bootup_uso total 483 -> 383 (bootup_uso.c 181 -> 163,
  tail3a_10C8C 32 -> 22, o0_120A8 27 -> 0, o0_123F0 18 -> 0, tail3b 15 -> 4, small o0 files 18 -> 1).
  Others unchanged (game_libs.c 173, game_libs_tail.c 30, titproc_uso.c 39).

Next: the GUI menu object (gui_initRows / centerRows / addRow / getCurrentRow / PauseMenu_update: +0x2C,
0x34..0x48 colour, 0x6C / 0x70 x / y, 0x74 row height, 0x78 rows, 0x7C current row, 0x80, 0x84 rows[]
of 0x28); Fader (tail4: +0x40..0x74) and the TimeGadget / BestGadget parm block (+0x44..0x108); the
settings record as a struct; then the name-entry overlays (0x10C / mgr 0x174), Tim / Trk / Arc menu
processes, game_libs.c's 173 sites, titproc MainLogo / KeyMessage, and the remaining dead blocks above.
(The dead blocks were removed on main by the coordinator: 92c2495d9, 0a9c39978.)

### Run 507 (agent-h): gadget Parms, Fader, settings record, GUI menu, SnowBoarder_reset

Commits on agent-h (base 0a9c39978), each gated PASS (3288/3288, ROM identical; every touched .o identical
by objdump -d -r -z in the matching and NON_MATCHING builds): 535bf6de6 (gadget.h + fader.h), c9677f156
(settings record), e6964a2f3 (Data 0xCAE8 tag symbol), 2329ae344 (**pure rename**
SnowBoarder_func_0000CAE8 -> SnowBoarder_reset), 605dd337f (guimenu.h). All others are hand edits.

- **Parms objects** (gdl/gadget.h). A "<Class>::Parms" object is an 8-byte head (+0 its name string) and
  N `GdlParm`s of 0x18 (+0xC type vtable: Data 0xC764 int, 0xC83C float; +0x10 value), each built with a
  4-byte tag from the Data section ("xps", "yps", "lbx", ...: the words right after the Parms name).
  The tags are the HostIO names of the values. `TimeGadgetParms` (0x98, Data 0xCAAC; ctor
  TimeGadget_ctor_00013D40, which is the Parms ctor despite its name): xps / yps (text position), lbx / lby
  and l2x / l2y (offsets of the two label sprites). `CountDownParms` (0x68, Data 0xCB60; game_libs.c
  TimeGadgetParms_ctor): xps / yps / shx / shy. CoolGadgetParms_ctor builds the same six tags as
  TimeGadget (Data 0xCC38). TimeGadgetParms_ctor_0001438C is a third "TimeGadget::Parms" (Data 0xCAD8)
  with two float parms.
- **Gadget** (0x13C): parms 0x2C, colour 0xC4, alpha 0xD8 (text + label2), labelAlpha 0xDC (label1),
  font 0xE0 (ctor arg; draws text), text[0x20] 0xE4, label1 0x104 / label2 0x108 (= &sprite1 / &sprite0,
  set by TimeGadgetParms_set104_00014004 in every ctor). The draw order is in TimeGadget_display_000140C4.
  CountDownGadget: parms, alpha 0xA8; arg1 / arg2 are the two fonts (secs at xps, cs at xps + shx).
- **Fader** (include/game/fader.h, 0x78): the 32x32 fire-grid screen fade. key 0x40 (a repeated
  Fader_start key is ignored), state 0x44, progress 0x48 (1.0 = done), texture 0x4C (u16 32x32),
  screenIdx 0x54 (per-cell framebuffer index), grid 0x58 (f32 cells), cols / rows / cells, mode 0x68.
- **Settings record** = the Backup options chunk (gdl/backup.h BackupOptions, agent-c's header: only the
  unused head fields were renamed / retyped u16): unlocks 0x0, seqStep 0x2, flags 0x4 (& 3 sound mode,
  bit 2, bit 3 language menu), unk6[8] (settings_get8), newMark[3] 0xE (Backup_sessionSetNewNames passes
  &newMark[mode]), levels[3] 0x12 (settings_vol*). GameFlow's field is now `char *options` (was
  `unlocks`), viewed with `SETTINGS(p)`.
- **GuiMenu** (include/game/guimenu.h, 0x304 = PauseMenu_create's alloc): arg 0x2C, alpha 0x34, timer
  0x38, colour 0x3C, x / y / rowHeight 0x6C..0x74, numRows 0x78, cursor 0x7C, locked 0x80, rows[16] of
  GuiRow {label, enabled, id, arg, sub[0x18]} at 0x84.
- **SnowBoarder_func_0000CAE8 -> SnowBoarder_reset.** The Text symbol was also a data placeholder
  (Data 0xCAEC / 0xCAF0 = the "xps" / "yps" tags, used by TimeGadgetParms_ctor_0001438C's .s, NM body
  and match_import). Those now use `sFloatParmsTags_CAE8` (pinned 0xCAE8; the bindings .json key, origins
  .ld and expected tail4 .o symbol follow), then the function was renamed with the tool. The same
  pattern remains for `func_0000CACC` (a real function, and the Data 0xCACC..0xCAD8 tags / "TimeGadget::
  Parms" name in TimeGadget_ctor_00013D40 / 1438C).
- **Byte gotchas** (all reverted to raw, with a comment where it matters):
  - `(float)GADGET(s0)->alpha` changes fp register colouring in the gadget display functions.
    `(float)*(int *)(s0 + 0xD8)` stays.
  - A member addend pair loads in the opposite order from the raw pair. Write it `xps + lbx`; the raw
    form was `lbx + xps`. The same holds for the -O0 product in gui_centerRows.
  - The PARM() stores in TimeGadget_ctor_00013D40 change its branch layout.
  - PARMF() in the NM TimeGadgetParms_ctor_0001438C grows the NON_MATCHING .text tail by 8 bytes.
- Census (h492 regex) before -> after: bootup_uso total 376 -> 266 (tail4 134 -> 46, o0_1034C 19 -> 0),
  game_libs.c 173 -> 159, titproc_uso.c 22 (+ the two settings sites), game_libs_tail.c 30 (its settings
  sites were `&D_00000000 + 0x154` forms, outside the regex).

Next: CoolGadget (0x198, 79 sites in CoolGadget_ctor / display: TimeGadgetParms at 0x2C, seg 0xC4,
cur / target 0xC8 / 0xCC, alpha 0xD0, total 0xD4, colour 0xD8, Vec4 colours 0xE8 / 0xF8 / 0x108 / 0x118,
phase / step 0x128 / 0x12C, label1 / label2 0x130 / 0x134, sprites 0x138 / 0x150 / 0x168 / 0x180); gui_addRow / addRowSub
onto GuiRow; the Fader_ctor / buildTexture Node / vtable sites; name-entry overlays (0x10C / mgr 0x174);
Tim / Trk / Arc menu processes; titproc MainLogo / KeyMessage; mgrproc_uso_o0_19C.c's private
`{pad[0x154]; u16 *v}` settings view; the TimeGadgetParms_setPosF / setPos / gadget_slideStep object
(float xps / yps at 0x44 / 0x5C, 0x88 / 0x8C, speed 0xA8, string 0xB4).

### Run 514 (agent-h): named placeholder calls in agent-h's files, RaceProcess.menu, CourseGadget

Commits on agent-h (base a87a00fff), each gated PASS (3288/3288, ROM identical): 268d6034c (806
bootup_uso CALLs), eee892767 (717 game_libs.c / game_libs_tail.c), 0b0b15f82 (900 arc / mgr / h2h / tim /
trk / titproc), e9c939ed3 (hand: ATTACH6808 takes the callee), 7eea7d412 (63 game_createMap), 9ed305d18
(hand: RaceProcess.unk048 -> GuiMenu *menu), c6e37156b (hand: CourseGadget). The CALL commits are
name-placeholder-calls.py output only (titproc_uso.c's include moved by hand, see below); no renames.tsv
lines this run.

- **Placeholder calls**: 2486 named (bootup_uso 869 incl. game_createMap 63, game_libs.c 388, game_libs_tail.c
  329, arcproc 183, h2hproc 124, mgrproc 55, timproc_b1 227, timproc_b3 240, titproc 71). Left 275: 224
  "no jal" (NON_MATCHING reference bodies), 38 in donor-splice / recipe bodies (bootup ItemType_create /
  TreeTmpl_create / ColourItem_create / edgeGrip, the arc / tim / trk / h2h open / closeSession o0 bodies),
  13 callees with no symbol name (nameent sym24 / sym30, mod60 sym120 / 122 / 179 / 180, heli sym121, fire
  sym47: exporters uso-imports cannot name). .cpp donors are not handled by the tool.
- **Tool gotchas**: (1) `add_include` puts `#include "uso_call.h"` after the LAST #include in the first 20000
  chars; in titproc_uso.c that was inside the mid-file `#ifdef NON_MATCHING #include "titproc_uso_5DC.c"`
  block, so the matching build failed (cfe: gui_spriteInit undefined). Moved by hand; the tool should take
  the first include block. (2) A placeholder call inside a function-like macro body is not a site, so its
  expansions leave the function's jals uncovered and the whole function is refused (game_createMap: 58 sites
  vs 65 jals). Fix: pass the placeholder as a macro argument (`ATTACH6808(func_00000000, list, x)`), then each
  expansion is its own site (all 7 = list_append).
- **RaceProcess.menu** (race.h 0x48, `struct GuiMenu *`): PauseMenu_create(0) in every mode's race init; its
  unk30 gets spriteSet; h2h's gui_setY moves it.
- **CourseGadget** (gdl/gadget.h, 0x2FC) + CourseGadgetParms (0x194, 16 tags) + GdlParmRGBA (0x24 colour
  parm): pct[2] / marker[2][2] / originX, originZ, extent are fed from RaceEntry[0 / 1] and the RaceTracker
  course frame. Byte gotcha again: `xps + mx0` / `yps + my0` (field order swaps the loads).
  game_libs.c census 84 -> 64.

Next: the NM update / handleInput bodies (TimMenu_update, ARCMenuProcess_handleInput, ArcNameEntry_update),
the name-entry ctors' typed-chain lever, TrickPointsGadget_reset / PointsGadget_ctor_00003138 (the 0x168
points-list object: 8 PointsPopup slots at +0x2C, colour ints 0x8C..0x98), the RaceProcess_* raw sites in
game_libs.c, Fader_ctor / buildTexture Node / vtable sites, gadget_decodeStringB4_00014598.

### Run 519 (agent-h): TrickPointsGadget, WhiteFader, VT_SLOT, menu / name-entry chains, flipDigits

Commits on agent-h (base e105ff4dc), each gated PASS (3288/3288, ROM identical; every touched .o identical
by objdump -d -r -z in the matching and NON_MATCHING builds, except the renamed symbols): 99ceb2d7e
(TrickPointsGadget + game_libs.c conversions), 83aa5fcd8 (Fader / GdlVtEnt + VT_SLOT), 4a5c7db39 (menu
update / handleInput, ArcNameEntry_update, name-entry ctors), 0dfb42519 (**pure rename**, 2 names),
8a3d4ca4c (WhiteFader, titproc GameDemoProcess), 051454e15 (comments). All others are hand edits.

- **TrickPointsGadget** (gdl/gadget.h, 0x168 = RaceTracker.pointsList; PointsGadget_ctor_00003138): slots[8]
  PointsPopup at 0x2C; font 0x50 (ctor arg 3), popupArg / popupArg2 0x54 / 0x58 (the PointsPopup.arg of the
  3B1C / 3DB8 pop-ups); a 4-entry message ring: text[4] 0x5C, points[4] 0x6C (-1 = text only), head 0x7C,
  tail 0x80, count 0x84, scroll 0x88 (+16 per push, -2 per frame), age[4] 0x8C (reset 0xFF, counts to
  0x80), alpha[4] 0x9C, x[4] 0xAC (160), y[4] 0xBC; colour / pointsColour (GadgetRGBA 0xCC / 0xDC:
  255,102,80 and 102,255,80), allIdle 0xEC, sprite0..4 0xF0..0x150. allocSlot_00003B1C / 3DB8 dropped
  their private GlOwn / GlSlot views. Byte gotcha: TrickPointsGadget_push's `head == tail` (written
  tail == head the bne operands swap).
- **GameFlow** (game/input.h): unk7C (RaceProcess_leave: 1 -> win seq variant 2). RaceProcess_leave uses
  nextFlowMode / course / dataMgr and RaceTracker entries[0].time.
- **BoardsGadget.parms** is a TimeGadgetParms (icons at xps + 4i, yps - 4i).
- **GdlVtEnt moved to gdl/node.h** + `VT_SLOT(vt, n)` (slot n of a `char *` / s32 vtable: fn at vt + 0xC + 8n,
  delta at vt + 8 + 8n). Used by Fader_buildTexture (slot 11, the GfxLib palette) and titproc
  GameDemoProcess (slot 10 on the menus / logo; slot 11 on import_0001FFF8). Same bytes.
- **WhiteFader** (game/modeproc.h, 0x40; tit_ / h2h_WhiteFader_ctor): colour[4] 0x2C, alpha 0x3C.
- **Menu rows**: Tim / TrkMenu_update and ARCMenuProcess_handleInput keep their IXA / permuter levers; the
  row is read through the menu shifted by cursor rows (`GUIMENU(slot)->rows[0].arg / enabled`).
  `&menu->rows[cursor]` costs an extra addiu there; in titproc onQuitButton (base = obj + 0x90) the plain
  `rows[cursor].arg` is byte-identical.
- **Name-entry typed-chain lever = the real field chain**: `((TimRace *)MODENAMEENT(arg0)->race)->recordRank`
  (ArcRace for arc) replaces Tim16F8_A / Tim1660_A / Arc199C_A; same bytes.
- **NM bodies and CALL()**: name-placeholder-calls.py check fails on CALL() in a NON_MATCHING reference
  body whose matching build is INCLUDE_ASM (the .s jals carry no names: "not among the ROM callees").
  Name those callees in comments (ArcNameEntry_update_00001B04 does).
- **gadget_decodeStringB4 / E4 -> PointsPopup_flipDigits_00014598 / Gadget_flipDigits_00014010**: c -> 0x69 - c
  except 'a', 'b', ' ' = nine's complement of the digit string in text (0xB4 / 0xE4). No static caller in
  any module (uso-imports.py callers / sites).
- Census (h492 regex) before -> after: game_libs.c 64 -> 26, titproc_uso.c 17 -> 5, bootup_uso_tail4.c
  38 -> 33, h2hproc_uso.c 15 -> 14. Untouched: bootup_uso.c 156, timproc b1 61 / b3 71, mgrproc 39,
  arcproc_tail1 38, game_libs_tail.c 30.

Next: the RaceProcess_restartCameras / restartWithTimeout `state + 0xC4` chain (game object players =
SnowBoarder, +0x800 input; InputPad +0x34 unnamed; the shared q temp is a lever); CoolGadget_display's
`m[0] + xps` and CountDownGadget's (float)alpha stay raw (fp colouring); PointsGadget_update donor
(game_libs_o2_3430.c FW forms -> TPOINTS / POPUP); bootup_uso.c SnowBoarder_update (14) and the Tmpl
helpers; mgrproc MGRRaceProcess_drawIntro (9) / mgr_DataManager_update (7); h2h_createPauseMenu (4).

### Run 541 (agent-h): GfxLib sites, RaceColourParms, EnvSettings.fallingSnow, pause-callback Bss

Commits on agent-h (base 5f5cf425b), each gated PASS (3288/3288, ROM identical, 6050 named calls / 0
mismatches, 87 INPUT_MGR uses / 0 mismatches; every touched .o identical by objdump -d -r -z, non-empty dumps,
matching and NON_MATCHING): 0cad1b3c6 (GfxLib sites), 9c0890bce (RaceColourParms), 7868a8165
(identifications), **6bc074744 (pure rename: func_00007620 -> EnvSettings_setSnow, import_8001FFC0 ->
gEnvSettings_6808)**, ee74f55a2 (mgr / h2h / tim alias + Bss sites). The rest are hand edits.

- **GfxLib** (agent-b's gdl/gfxlib.h, now included by bootup_uso.c with gdl/window.h): BGBox / EnvSettings_display
  write `curWindow->win.flags` bit 2 and `win.clearColour` (BGBox draws while the fog alpha is low, else
  clears with the fog colour), EnvSettings_display `win.near / far`; Fog / Snower_display use
  `worldScale[2] * camera world[3][2]`. **GfxLib +0x294 is the scene FogParms** (every `gGfxLib_*_src` alias is
  pinned at 0x294; FogParms_emit / lerp take it; gfxlib.h still has unk294[6]); +0xE8 is a 4x4 matrix
  game_initDdm sets to diag(worldScale) (unk0E8[16]); +0x160 is a table SnowBoarder_ctor fills (unk160);
  +0x1C4 flags bit 3 = the map has parms (game_createMap, alias pinned at 0x188 + 0x3C). The per-site
  aliases pinned at nonzero values (0x23C, 0x240, 0x1FC) keep their spelling: Tv1Tmpl's `[6]` is curWindow,
  Fader_buildTexture's root is mainWindow, U64BGWall's E68_MGR is staticDL. Both Tv1 and Fader call VT_SLOT
  11 of a window (Fader indexes the result as the frame buffer). BOOT_SELF_PTR is gone.
- **RaceColourParms** (gdl/race.h): RaceProcess 0x50..0x4D8 is the ColourParms ColourParms_ctor builds
  (head 8, 14 P / E RGBA pairs: rd, 32, go, gl, ls, rt, to, rn, rs, nr, ad, cs, gr, dw, then ctt / cnm /
  ccl / clg; loaded from rom/racecol.bin). The old colour[6] were parm values; the arc / mgr result screens'
  +0x260 / +0x284 and +0x380 / +0x3A4 are pair[RACECOL_RN] and pair[RACECOL_CS]. The mode ctors pass
  `&RACEPROC(o1)->colours`.
- **EnvSettings.fallingSnow** (+0x40): gEnvSettings is bootup Bss+0x20 (game_createMap stores the ctor result;
  SnowTmpl_create / Snower_display pass it). FallingSnow_create skips nextFlowMode 8 (EDITORS) and attaches
  to game->egRoot (gInputMgr_74e8_g / _h both relocate to InputMgr, pinned at +8 / +0xF0). Snower parms
  `rng` (zone depth) / `sta` (the value given to EnvSettings_setSnow).
- **CourseCamItem** (envobj.h): the "cam" item CamDirector_update polls; pos 0x30, kind 0x3C; RiderCam_command's a2.
- **MemberCallback_invoke_00007BF4**: a cfront PMF {s16 delta, s16 index, fn / vptrOff} (local CbPmf_7BF4;
  sun.h's MemberCallback has a Pair2).
- **Pause-callback Bss**: h2hproc Bss +0 / +4 and timproc b1 Bss +0x208 / +0x20C hold the race and its pause
  menu for the menu-row callbacks (H2HPauseBss / TimPauseBss). mgr onEndTimerDone's `_b` / `_c` tokens are
  GameFlow (level, nextProcState); gameflow-import-sites.py check does not count those uses (28 of 33 in
  mgrproc_uso.c), so the proof is the uso-imports.py reloc listing.

Census (readability-census.py) before -> after: owner h 834 -> 768; all raw casts 2382 -> 2317; bootup_uso 311
-> 261, h2hproc 24 -> 14, mgrproc 65 -> 62, timproc b1 18 -> 16; bootup_uso.c 107 -> 56.

Next: ask agent-b for GfxLib fields fog (0x294, FogParms), worldMtx (0xE8), unk160 table and the 0x1C4 bit 3
meaning; ColourParms_ctor (game_libs.c, 85) can now be written on RaceColourParms; trk / arc row callbacks
(the TimPauseBss twins in b3 / arcproc); MGRRaceProcess_drawIntro (match_import) colour pairs; the largest
remaining functions (task 6 not reached): mgr_initMatchRace_00000700, MgrNameEntry_drawCongrats, tit_procMain.

### Run 576 (agent-h): RaceEntry gates, passGates / RaceTracker_ctor, game_createLights / setupMode, tim / trk main

Commits 1ea9d605b and fc787d5bc on agent-h (base ef0d6b540), all hand edits, no renames. Clean rebuild:
all 1268 .o files (matching and NON_MATCHING) dump-identical to the base (objdump -d -r -z + .data /
.rodata, non-empty), ROM OK, cfe warnings identical apart from line numbers. Gate PASS: 3288/3288,
verify-blocks 6/6, 6089 named calls / 0, uso-data-sites 0, INPUT_MGR 0.

- race.h: RaceEntry gate / gateA / gateB are `struct RaceGate *` (forward-declared; course.h unchanged).
- RaceTracker_passGates over RaceTracker / RaceEntry / RaceGate; the register levers (`e = arg0; arg0 = 0`,
  the `e | arg0` call argument, `if (tmp) {}`) are kept. Gate +0x5C / +0xC8 stay raw (not in course.h).
- RaceTracker_ctor's clear loop: `RACE_ENTRY_AT(t, v1)[0..3].rider / flags`.
- game_createLights: `BaseLight.parms.col[0..3]`. game_setupMode (in-unit body and the o2_2DA4 donor):
  `WORLDREG()->bgRoot`, `NODE()->parent / unk04`, the geometry-mode alias as `int[]`.
- SnowBoarder_limitSpeed: `RiderInput.held`; tim_main / trk_main (-O0 donors): `NODE(s0v)` attach.

Census raw sites: h 220 -> 171. Next: SnowBoarder_ctor (5, bootup_uso_90CC.c), game_createMap (5; the
+0x3C site waits on agent-g's EnvSettings.bgBox), titproc's TitleDemoProcess game_libs objects.

### Run 572 (agent-h): gadget.h parms over GdlParmBase, RaceProcess.name, this-adjusts, BackupOptions defaults

Commits 717a44e93 and a3de2d001 on agent-h (base 9799250ab). Each was gated PASS after a clean rebuild:
3288/3288, ROM identical, verify-blocks 6/6, 6089 named calls / 0 mismatches, uso-data-sites 0, INPUT_MGR 0.
All 1278 .o files (matching and NON_MATCHING) are identical to the base by objdump -d -r -z plus .data /
.rodata, with non-empty dumps. The cfe warnings are identical (590 lines, 291 x 712); the edg 3262 lines
differ only by interleaving. All hand edits; no renames.

- **gadget.h / parm.h** (agent-b's request). gadget.h now includes gdl/parm.h.
  - GdlParm / GdlParmF / GdlParmRGBA: `char head[0xC]` is GdlParmBase's first three members, spelled out
    (`GdlParmBase *next`, `GdlParmTag tag`, `s32 unk08`). The base is not embedded: about 120 parm type
    stores write `->type`, 13 of them in agent-b's post1b. To embed `GdlParmBase base` instead, those stores
    become `->base.type`, and agent-b would edit post1b.
  - GdlParmRGBA.type was already `void *`.
  - The `s32 unk04` in GdlParms, TimeGadgetParms, CountDownParms, FloatPosParms and CourseGadgetParms is
    now `GdlParmBase *first`, as in GdlParmList. The 7 `= 0` stores follow.
- **RaceProcess.name** (race.h) is `const char *`, and RaceProcess_init's arg2 is `const char *`. Every
  caller already passed `(char *)&D + K`. match_imports/context_game_libs.h (not mine) still declares arg2
  as s32; no TU sees both declarations.
- **Pattern A**:
  - The Cfront this-adjusts are `(char *)&gSnowBoard + delta`, all the same bytes. They are in
    GameFlow_restart (2 sites), settings_setFlag4, Backup_resetOptionsData and RaceTracker_sendEndingMsg.
    sendEndingMsg's prototyped cast now takes `char *`. GameDemoProcess_handleInput's `import_0001FFF8`
    adjust is the same idiom.
  - tit_procMain's GameDemoProcess_ctor argument (flags mask + ghost count) is `(char *)mask + count`.
    An int sum swaps the addu operands in either operand order, so the char * is the lever. Typing `d` as
    `InputMgr *` or `char *` re-allocates the whole function, so `d = (int)&import_00020098` stays.
  - mgrproc 1693 passes `&self->base.elapsed` and `(char *)self->base.entries + K` to the K&R callee.
  - Kept as levers:
    - U64BGWall_ctor's `*(s32 *)(int)&import_8001FFA0_h[1]`. The plain `[1]`, `*(s32 *)&h[1]`, char + 4 and
      `*(&h[0] + 1)` spellings all change bytes.
    - mgr_openSession's dead `v3 = (int)&D`: a register int that reuses s0.
- **Pattern D, game_createMap** `*(char **)(gEnvSettings_6808 + 0x3C) = o`: EnvSettings +0x3C is not a
  mode. It is the BG box (game_createBGBox's result). EnvSettings_ctor clears it, and EnvSettings_display
  sets the clear flag / colour only while it is 0. The fix is envobj.h `EnvSettings.mode` ->
  `struct Node *bgBox`, which is agent-g's this run, so the site stays raw for now.
- **Census**: Backup_resetOptionsData_0000AFC4 (10 sites, the largest) writes through SETTINGS(arg0):
  unlocks, seqStep, flags, levels[], newMark[] / unk11. The unk6 loop keeps its walking `char *`. The 3
  resetOptions / writeOptions calls pass `.options` without `(int)`.

Port audit (h): A 27 -> 18 (all 126 -> 117); B 3, C 1, D 9 unchanged. Census raw sites: h 231 -> 223
(all 1064 -> 1056).

Next:
- RaceTracker_passGates (8) and RaceTracker_ctor (7). passGates needs RaceEntry.gate / gateA / gateB typed
  `struct RaceGate *` (race.h; RaceGate is in course.h) and RaceGate +0x5C / +0xC8 (course.h, not mine).
  Its int * locals carry register levers, so retype the locals only.
- game_createLights (8), game_setupMode (6 + 6 in the o2_2DA4 donor).
- agent-g: EnvSettings +0x3C bgBox (above), then game_createMap's D site.
- agent-b: whether to embed GdlParmBase and convert post1b's 13 `->type` stores.

### Run 581 (agent-h): raw-site closeout for owner h (165 -> 0 unjustified)

Commits on agent-h (base 01b36397d), each gated PASS (3288/3288, ROM identical, verify-blocks 6/6, 6089 named calls /
0 mismatches, uso-data-sites 0, INPUT_MGR 0); all 1278 .o (matching + NON_MATCHING) identical by objdump -d -r -z +
.data/.rodata: 7d7b08a3e (conversions), b465fd4ca (conversions, `*(T *)&` lever), 492250b32 (RAW: comments only).

- **ProcessHead / PROCESS()** (modeproc.h): the bootup Process head, +0x2C fadingOut, +0x30 paused, +0x38 padState,
  +0x48 pauseMenu. TitleDemoProcess carries fadingOut / pauseMenu.
- **GuiSpriteTable** (guimenu.h): titproc Bss 0 (the ROM reloc target of every titproc D_*_A / import_00263D30 site);
  menuOwner at +0xA8 is the process the tit_menu* callbacks fade out.
- **RaceGate** (course.h, agreed with agent-g): +0x5C x, +0xC8 flags (bit 0 = pass on the left).
- **VT_SLOT works in the -O0 embedded-assignment dispatch bodies**: `VT_SLOT(m, n).fn(VT_SLOT(m = NODE(a0)->vptr, n).delta + a0)`
  gives the same bytes as the raw `(*(fn *)(m + 0xC + 8n))(*(short *)((m = ...) + 8 + 8n) + a0)` form.
- gui_centerAt_000102A4 needs `*(float *)&` / `*(int *)&` on rowHeight / numRows (plain members reorder the lwc1).
- Left (justified): 28 data-table, 29 unknown-object, 7 donor-mirror, 3 byte-lock. Next struct candidates: PointsGadget
  +0x80 / +0x84 / +0xA0 (TrkDataManager_init), RaceProcess.unk524 object (+0x60 state), ScreenWindow +0x70 / +0x1B8,
  BGBox +0x3C, U64BGWall cfg.

### Run 567 (agent-h): TitleDemoProcess pointer fields, vptr / name stores, item structs, the 116C +0xA8 store

Commit fb7f786e1 on agent-h (base 664b7a58e), gated PASS (3288/3288, ROM identical, verify-blocks 6/6, 6089
named calls / 0 mismatches, uso-data-sites 0, INPUT_MGR 0) after a clean rebuild. All 1278 .o files (matching
and NON_MATCHING) are identical to the base by objdump -d -r -z plus .data / .rodata (non-empty dumps). The cfe
warnings are unchanged (132 x 712 before and after; the edg 3262 lines differ only by parallel-build interleaving).
All hand edits; no renames.

- **TitleDemoProcess** (modeproc.h): +0x54 `struct KeyMessage *keyMessage`, +0x58 `struct MainLogo *mainLogo`, +0x5C
  `struct GuiMenu *menu`, +0x60 `struct Node *langMenu` (no LangMenu struct yet), +0x64 `struct WhiteFader *whiteFader`.
  **GameDemoProcess.dataMgr** (+0x6AC) is `struct RaceTracker *` (no C users). TitleDemoProcess_ctor casts the ctor
  results to those types. Its raw `mainLogo + 0x2C` store is `mainLogo->alpha`. TitleDemoProcess_buildMenu's
  `menu + 0x128` store is `menu->rows[4].enabled = 0` (0x84 + 4 * 0x28 + 4: with pad 2 not connected, row 4 is
  disabled). The 116C donor's TitleDemoProcess mirror uses the same pointer types. Same bytes.
- **116C donor +0xA8 store**: import_00263D30 (game_libs 0x80263D30) is the shared gui sprite table (KeyMessage
  +0x0 / +0x18, MainLogo +0x60 / +0x78 / +0x90). The word after seven 0x18-byte sprites, at +0xA8, gets the
  TitleDemoProcess just before a picked row's callback runs. The donor writes it through a local
  `GuiSpriteTable { char sprites[7][0x18]; char *menuOwner; }` view.
- **RaceTracker.name** (race.h) is `const char *`. TrkDataManager_init (b3) and h2h_DataManager_init store
  `&D + K` without the int cast. RaceProcess.name stays s32: RaceProcess_init takes it as an s32 arg2.
- **Pattern A**:
  - 19 Node vptr stores (`*(int *)(p + 0x28) = (int)&X`, `p[0x28 / 4] = ...`, `p[10] = ...`) in titproc
    (GameDemoProcess_ctor, LangMenu_ctor, tit_WhiteFader_ctor, MainLogo_ctor, the 619 block) and bootup_uso.c
    (ColourItem types, CamDirector_ctor, item_createHem / Fog / Snow) are `NODE(p)->vptr = (char *)&X`.
  - SnowBoard_InitInstance and MapProp_ctor store `NODE(p)->name`.
  - RaceProcess_init / RaceProcess_drawGui pass `&arg0->sprites[n]` (and the plain sprite id) to the K&R
    gui_sprite* callees without the int casts.
- **Pattern D**:
  - item_createBal / Ba2 / Chk store through `BootItemType` (bootup_uso.c: ItemType + `char *vptr2` at
    0x48, size 0x4C). item_createGtr / Gtl use `BootGateItemType` (ItemType + `s32 side` 0 / 1 + `vptr2` at
    0x4C, size 0x50). A pointer after the subclass's own word is Cfront's layout for a second base's vptr,
    hence the name. bootup_uso.c now includes gdl/item.h.
  - FallingSnow_create reads `ENVSET(a0)->fallingSnow`. Tv1Tmpl_func_000077D0 reads `->scroll` / `->state`.
  - ARCMenuProcess_ctor's `D_arc251C_h + 400` is `INPUT_MGR(D_arc251C_h).fader`: the same link-the-shared-fader
    sequence TitleDemoProcess_ctor does. The INPUT_MGR check counts it, 0 mismatches.
- **Tried and reverted**: item_registerTemplates' 11 `0 * ((int)&v0 + ...)` address-escape terms (the 55A0
  donor). Neither `(&v0 != 0)` nor char-pointer differences keep the frame. With `!= 0`, edg folds the
  terms and the escape is lost; the differences reorder the homes. The lever stays. Its other 3 A sites are
  `TREETMPL(obj)->shapeData = (int)&D_55A0_o48_N`, which needs envobj.h TreeTmpl.shapeData typed as a pointer.

Port audit before -> after:

| pattern | agent-h | all owners |
|---|--:|--:|
| A | 63 -> 27 | 173 -> 137 |
| B | 3 -> 3 | 46 (unchanged) |
| C | 1 -> 1 | 12 (unchanged) |
| D | 18 -> 9 | 172 -> 163 |
| H | - | 9 (unchanged; TitleDemoProcess was not in the H list) |

Census: owner h raw sites 255 -> 235. All owners 1265 -> 1245. Accessor uses unchanged.
bootup_uso 106 -> 92, titproc 22 -> 18, arcproc 13 -> 11.

Next:
- A (27 left):
  - item_registerTemplates' 14: the escape lever, plus TreeTmpl.shapeData (envobj.h, not mine).
  - The `delta + (int)&gSnowBoard` this-adjusts in GameFlow_restart / settings_setFlag4 / Backup_resetOptionsData /
    RaceTracker_sendEndingMsg: try `(char *)&gSnowBoard + delta` one site at a time.
  - tit_procMain's `d = (int)&import_00020098` and its `(int)&mask[...]` ctor arg.
  - WorldRegistry_create's s32 vptr.
  - U64BGWall_ctor, mgr_openSession and the mgrproc 1693 block.
- D (9 left):
  - envobj.h owner: Tv1Tmpl.unk64 as `u16 *` (Tv1Tmpl_func_000077D0's tbl) and Tv1Tmpl.model as a pointer
    whose +0x84 table holds the two screen nodes (Tv1Tmpl_func_00007D04).
  - game_setupVs2P Window +0x1B8: window.h, with agent-a.
  - game_createMap's gEnvSettings_6808 + 0x3C.
  - Fader_display, ScreenThumbMat_grab and SnowBoard_ctor are agent-g's.
- RaceProcess.name could become `const char *` if RaceProcess_init's arg2 does (every race ctor passes a
  string).

### Run 565 (agent-h): mgr_drawResults session / dataMgr, GdlParmRGBA.type, GuiRow callback, B / D sites

Commits on agent-h (base 4731bbcb0), each gated PASS (3288/3288, ROM identical, verify-blocks 6/6, 6089 named
calls / 0 mismatches, uso-data-sites 0, INPUT_MGR 0) after a full clean rebuild with all 1268 .o files
(matching + NON_MATCHING) identical to the base by objdump -d -r -z plus .data / .rodata (non-empty dumps):
bd0dac023 (mgr_drawResults, GdlParmRGBA.type), 4e2e7d65b (GuiRow.arg, B / D sites). All hand edits; no renames.

- **SnowBoarder_ctor's last site** was already done on main by agent-a (050e438f7, CollObj.vptr `char *`).
  The never-built bootup_uso_ncc_90CC_nm.cpp keeps its raw `+ 0x30` store.
- **mgr_drawResults** (NCC donor mgrproc_uso_ncc_23FC.cpp) includes gdl/backup.h directly (it needs an `s8`
  typedef). race.h still forward-declares BackupSession for C++, because other donors include race.h without
  `s8`. The reads are `race.session->modes & BACKUP_MODE_TIME`, `GAMEFLOW(&import_800201D0)->dataMgr->elapsed`
  and `dataMgr->entries->rank[0] < 3`.
- **ColourParms_ctor**: these 32 sites were port-audit pattern **B**, not A. GdlParmRGBA.type (gadget.h) and
  RaceColourParm.type (race.h) are now `void *`, so the stores read
  `PARMRGBA(var_a0)->type = (char *)&D_00000000_cd58_uN + 0xCD58;`. The other GdlParmRGBA store, at game_libs.c
  line 1193 (`PARMRGBA(mf)->type = &gl_ref_0000CA34_1C54`), also changed. bd0dac023 missed it, so a new cfe 712 warning appeared;
  4e2e7d65b fixes it.
- **GuiRow.arg** is `GuiRowFn` (`void (*)(void)`, guimenu.h). gui_addRow and gui_addRowSub take it as GuiRowFn.
  The call sites call `rows[cursor].arg()` with no cast (h2h onPauseSelect, titproc, and the h2h 1204 /
  titproc mp72_116C donors, whose GuiRow mirrors follow). arc's `!= ((0, 0))` is now `!= 0`. The bytes are the
  same at every site. The callers pass data symbols through CALL(), so the prototypes don't matter there.
- **D sites**:
  - The -O0 Cfront dispatches (Process_update / display, QuitProcess_onQuit, GameFlow_restart,
    settings_setFlag4) use `NODE(x)->vptr` in the embedded assignment; the lever survives.
  - GameFlow_unloadUso and game_isUsoLoaded walk `FlowUso *`.
  - settings_set8 uses `GAMEFLOW(a0)->options[i + 6]`.
  - b3 uses `INPUT_MGR(..).dataMgr` (store, and `->entries->rank[1]`, the trick rank) and `NODE(a3)->vptr`.
- **B sites**: arc_DataManager_init / h2h_WhiteFader_ctor use `NODE(x)->name` / `vptr`. TitleDemoProcess.dataMgr
  (modeproc.h) is `struct RaceTracker *`, and import_000B6C40 is declared to return it.

Port audit before -> after:

| pattern | agent-h | all owners |
|---|--:|--:|
| A | 65 -> 63 | 183 -> 181 |
| B | 38 -> 3 | 81 -> 46 |
| C | 1 -> 1 | 12 (unchanged) |
| D | 32 -> 18 | 204 -> 190 |
| H | - | 9 (unchanged) |

Census: owner h raw sites 280 -> 255; all raw `*(T *)(p+K)` 1209 -> 1191; accessor uses 120 -> 113 (the 23FC
donor's FW macro is gone).

Next:
- The remaining agent-h B sites are not real pointer truncations:
  - RaceProcess_createReplayCam's camera int;
  - callGlobalSlot11's this-adjust;
  - h2h's `(int)(flags << 15)`, an audit false positive.
- The remaining D sites:
  - item_create{Bal,Ba2,Chk,Gtr,Gtl} `obj + 0x48 / 0x4C`: needs an item struct;
  - game_setupVs2P Window +0x1B8: window.h is not mine, ask its owner for a `Window *` field;
  - FallingSnow_create +0x40, Tv1Tmpl +0x64 / model +0x84, ARCMenuProcess_ctor +0x190, MapProp_ctor name;
  - the .cpp donors (Fader_display, ScreenThumbMat_grab, SnowBoard_ctor, TitleDemoProcess_handleInput's
    0xA8 store).
- item_registerTemplates (14 A) and RaceProcess_init (12 A) are the biggest A lists.
- TitleDemoProcess 0x54-0x64 and GameDemoProcess.dataMgr (+0x6AC) are still s32.

### Run 559 (agent-h): race.h / gadget.h pointer fields, menu-row and course-list sites, SnowBoarder_ctor

Commits on agent-h (base 2fe63c692), each gated PASS (3288/3288, ROM identical, verify-blocks 6/6, 6089 named
calls / 0 mismatches, uso-data-sites 0, INPUT_MGR 0) after a full clean rebuild with all 1268 .o files
(matching + NON_MATCHING) identical to the base by objdump -d -r -z plus .data / .rodata (non-empty dumps), and
no new cfe warnings: de9e883bd (race.h pattern H), 3b3b82b2d (H2HRace.dataMgr), 8e01409f6 (gadget.h pointers),
c42e5143e (onPauseSelect / o0_19C), c9a29421a (SnowBoarder_ctor). All hand edits; no renames.

- **race.h pattern H**: RaceProcess.parent is `Node *`, TimRace.dataManager `struct RaceTracker *`,
  RaceTracker.vptr `char *` (as Node.vptr), RaceTracker.owner `RaceProcess *`; H2HRace.dataMgr (modeproc.h)
  `struct H2HDataManager *`. Only six stores needed a cast; the readers already went through `(char *)` /
  DATAMGR().
- **gadget.h**: GdlParm.type / GdlParmF.type are `void *` (the parm-type vtable), so the ~90 typed stores read
  `PARM(m)->type = &gl_ref_...;` with no cast (SnowBoarder_ctor 43, game_libs.c 31, agent-b's DNode_ctor 13);
  every Parms `name` is `const char *` (`->name = &sStr_...`); Gadget / CoolGadget label1 / label2 are `char *`.
  snowboarder.h's C++ GdlParmF mirror follows; dnode.h's GdlParmV3.type / DNodeParms.name (agent-b) are still s32.
  game_libs.c's sStr_Colour_Parms_CF80 extern is now `char`.
- **Menu rows**: H2HRaceProcess_onPauseSelect reads `((GuiRow *)((char *)menu->rows + menu->cursor * k))->arg`
  (k = the shared 0x28 multiplier lever). With char * arithmetic the pointer must be written FIRST: the
  `cursor * k + (char *)rows` order swaps the addu operands (the old int form wanted the opposite order).
- **mgrproc_uso_o0_19C.c** includes game/modeproc.h: procMain state 4 is `FLOWPROC(a0)->courseList->courses[idx]`
  / `riders[idx]`, mgr_pickRivals fills `courseList->riders[]`. At -O0 the member forms gave the same bytes as
  the `list[idx + 3]` / `+ 0x24 + i * 4` spellings.
- **SnowBoarder_ctor**: the func_000000F0 + 0x44 alias is GameFlow.game (+0x134): `FLOW_90CC =
  GAMEFLOW((char *)gInputMgr_90cc_dF0 - 0xF0)` (as FLOW_74E8_H), and the spray / trail nodes attach under
  `((WorldRegistry *)FLOW_90CC->game)->egRoot` / `bgRoot`. The fn-typed gProcNodeList base keeps its addiu
  through `((BuW90 *)gProcNodeList_41700_90cc_fz)->f00 / f08 / f04`.

Port audit before -> after: A 314 -> 227 (h 143 -> 69, b 60 -> 47), C 20 -> 16 (h 5 -> 1), D 246 -> 232
(h 46 -> 32), H 39 -> 34 (include/game 16 -> 15, include/gdl 23 -> 19); B unchanged (157, h 38).
Census: owner h raw sites 316 -> 295, all raw casts 1370 -> 1349, accessor uses 176 (unchanged).

Next: SnowBoarder_ctor's last site is `COLLOBJ(var_s0)->vptr = (s32)&bu_90cc_imp30` (coll.h's owner would
retype CollObj.vptr); ColourParms_ctor (32 A sites, the RaceColourParms sub-object addresses: needs a lever or
a typed parm-ctor argument); GuiRow.arg is the row callback (could become a function pointer); dnode.h's
GdlParmV3.type / DNodeParms.name to match gadget.h (agent-b); since main 24749e1ce backup.h is C++-guarded, so
mgr_drawResults' `session->modes` reads can convert; the remaining agent-h pattern B (38) and D (32).

### Run 556 (agent-h): pause-menu Bss twins, GuiMenu colours, MgrRace.courseList

Commits on agent-h (base e10de4848), each gated PASS (3288/3288, ROM identical, 6089 named calls / 0
mismatches, uso-data-sites 0, INPUT_MGR 0; every touched .o identical by objdump -d -r -z plus .data /
.rodata, non-empty dumps, matching and NON_MATCHING): **55455c3b2 (pure rename: the pause-menu Bss
aliases)**, 18e76bb85 (GuiMenu selColour / rowColour, MgrCourseList pointers), d2c447b61 (Arc / MgrRace.dataMgr pointers, TimPauseBss.proc). The rest are hand edits.

- **Pause-menu Bss pair** (tim / trk / arc): the menu process's handleInput / update stores
  `MENUPROC(a0)->menu` (the GuiMenu) and `a0` (the menu process itself, not the race) into its own
  Bss, then calls the row callback; the rows Process_stop the GuiMenu, set GameFlow.procState
  (`gInputMgr_procState_40`, bootup Bss+0xF8 + 0x40) and Process_fadeOut the menu process. tim (b1)
  and trk (b3) use Bss+0x208 / +0x20C (`sTimPauseMenu_208` / `sTimPauseProc_20C`, one symbol pair
  shared by both), arc Bss+0x70 / +0x74 (`sArcPauseMenu_70` / `sArcPauseProc_74`); the per-site
  aliases are `s{Tim,Trk,Arc}Pause{Menu,Proc}_<site>`. TimPauseBss.race is really the TimMenu
  process (field renamed `proc`). h2h's H2HPauseBss is different: +0 is the race (onPauseSelect).
- **GuiMenu.selColour / rowColour** (+0x4C / +0x5C, f32 rgba): PauseMenu_create's 119/117/229/255
  and 192/194/229/255 over 255; PauseMenu_display (o0_10540, local Quad540 q4C / q5C) copies one
  of them into colour (+0x3C) per row. The FC28 donor now uses them (agent-g owns it).
- **MgrRace.courseList / MgrDataManager.courseList** are `MgrCourseList *` (MGRRaceProcess_ctor /
  mgr_DataManager_init take it as such). mgr_pauseRetry uses courses[0], onRaceOver's state 4
  courses[idx + 1] (the next course), the ctor retries. mgr_loadSprites needs
  `*(int *)&q->count == *(int *)&q->idx + 1` (the plain member form swaps t6 / t7); drawIntro and
  its match_import keep the `(char *)` + offset form noted in run 552.
- **ArcRace.dataMgr / MgrRace.dataMgr** are ArcDataManager * / MgrDataManager * (port-audit pattern H;
  the ctor stores cast the mem_new result; the existing `(char *)` / DATAMGR() reads are unchanged).

Census before -> after: owner h raw sites 338 -> 337, all raw casts 1406 -> 1405 (this run was mostly names and
pointer types, which the census does not count); port-audit pattern H in agent-h headers 7 -> 5 (the two
dataMgr fields); the 14 gl_ref_ / D_ pause aliases are now named.

Next: race.h pattern H (RaceProcess.parent, TimRace.dataManager -> RaceTracker *, RaceTracker.vptr /
owner); the gadget.h GdlParm.type / GdlParms.name / Gadget.label1-2 pointer retypes (55 pattern-A sites
in SnowBoarder_ctor alone; this touches agent-b's post1b and snowboarder.h's own GdlParmF, so it needs
coordination); H2HRace.dataMgr; the H2HRaceProcess_onPauseSelect / mgr o0_19C pattern-D sites
(menu->rows[cursor].arg); SnowBoarder_ctor (13 raw). Since main 0b77ceb96, Node.vptr / name
take `(char *)` / `(const char *)` casts, not `(s32)`.

### Run 588 (agent-h): owner-h RAW sites 41 -> 0

Commit bd21b3803 on agent-h (base e48ba4cc3), gate PASS; every changed .o identical in both builds.
- **Mode-USO data offsets:** `include/game/mode_uso_data.h` names section offsets of arcproc / mgrproc /
  timproc / trkproc the game_uso_data.h way (per-site symbol + `kRoF_` / `kData_` / `kBss_` offset).
  uso-data-sites.py does not read the mode modules; the values are checked by hand from
  `scripts/uso-imports.py sites <module>` (the reloc is "RoData(base)" etc.) and
  `scripts/uso_original.py modules()` (the section payload words). A named offset in a cast is not
  counted raw by the census (TAIL_OFF wants a literal).
- **Most "data-table" sites were GameFlow fields:** a mode site whose reloc is `bootup:Bss+0xF8` is the
  GameFlow import, so `base + 0x4C / 0x54 / 0x58 / 0x60 / 0x64` = playerRider / playerBoard / rider2 /
  board2 / course (the rider / board / course sprite ids). `bootup:Data+0xC510` is gProcUsoPaths.
- **mgrproc Bss+0x30** is the running MGRRaceProcess (MGR_STATE_PTR; onPauseSelect stores this there).
- **Tv1 screens are BaseMats:** Tv1Model +0x84 = BasePolyShape.mats, the screen word +0x1C =
  BaseMat.texels (the frame image is blitted into the TV screen textures).
- **WorldRegistry.windows[3]** (+0x114) is the ProcessWindow (game_createProcessWindow).
- Volatile trap: a `volatile int *base` read spelled `((volatile InputMgr *)base)->course` changes the
  timproc block bytes (ROM check passed, verify-blocks failed); the target read is the non-volatile
  `((InputMgr *)base)->course`.

### Run 584 (agent-h): object identification for the unknown-object / data-table RAW sites

Owner-h raw sites: 70 -> 41 (byte-lock 4, data-table 28 -> 26, donor-mirror 7, unknown-object 31 -> 4).
Commits 63a55c030, 25be2e4da (hand edits; every changed .o identical in both builds; gate PASS).
- **GameFlow.game (InputMgr +0x134) is the WorldRegistry** (game/course.h): players[0 / 1].rider at
  +0xC4 / +0xCC, windows[] at +0x108; **+0x114 = windows[3] = the "ProcessWindow"**
  (game_createProcessWindow stores it, GameFlow_startMode links under it). The type stays `char *` in
  input.h; sites use `WORLDREG(GAMEFLOW(p)->game)->windows[3]`.
- RaceProcess +0x524 renamed `nameEntry` (each mode's NameEntry overlay; mgr sets NameEntry.phase 1 / 2).
- envobj.h: BGBox (0x40; clearWindow +0x3C = ctor arg 2, BGBox_func_00000D94 copies it into the window
  clear bit) and BGWallTex (bgNtex.uso face record: timg +8, tlut +0xC; s32, the edg donors lack u32).
- mgrproc import_000A7B90 = input_getPad_00011D40 (PadCtl rawStickX / rawStickY at +8 / +9),
  import_00096228 = snd_setPlayer3FreqScaleFromStick. h2h flowProc +8 = the s32[2] H2HRace.wins tally.
  The "mrk" type's items are CourseMarkers. ShpNode +0x198 = dnode.parms.suc.value. Tv1Tmpl_func_000077D0's
  arg0 is the Tv1Tmpl (frameImage). GameFlow +0x34 (Snower_display, RaceProcess_drawGui) = nextFlowMode.
- Left: MapProp_ctor shape +0xA0 (pGrid, agent-b's BasePolyShape), the Tv1 screen nodes' +0x1C word, the F81C
  donor (agent-g: `((WorldRegistry *)ptr44)->windows[3]` once it includes course.h). The 26 data-table sites
  are mode-USO data tables (arc / h2h / mgr / tim / trk: GL_DATA / kRo_ are bootup.uso-only), the
  kRo_SnowBoarder_ctor_8B8 / _8BC +4 / +8 linker-alias addends (both aliases are 0x8B4) and C++ donor aliases.

### Run 552 (agent-h): ModeFlowProc, MgrCourseList, C++-safe race / modeproc / nameentry headers

Commits on agent-h (base 2acd57ec4), each gated PASS (3288/3288, ROM identical, 6089 named calls / 0 mismatches,
uso-data-sites 0, INPUT_MGR 0; every touched .o identical by objdump -d -r -z plus .data / .rodata, non-empty
dumps, matching and NON_MATCHING): 72024ebc1 (MgrCourseList / ModeFlowProc, initMatchRace donor), b9504de6d
(GameFlow_startMode), acc008c00 (tit_procMain), 657d8737a (headers C++-safe), 3d1445bda (mgr NCC donors),
0e1472b74 (ColourParms_ctor), cabb03c91 (MGRRaceProcess_drawIntro). All hand edits; no renames.

- **ModeFlowProc** (game/modeproc.h) = GameFlow.flowProc, the per-mode entry object: GameFlow_startMode allocates
  8 or 0xC (flow modes 2 / 3 / 5) and the inlined ctor cascade stores the base vtable (bootup Data 0xC550) and
  the mode's vtable at +4 (`vptr`, void *); it then calls VT_SLOT(vptr, 0) = `<pfx>_procMain(this + delta,
  state)`. +0 is the record session (<pfx>_openSession stores it: tit / mgr / arc), +8 the course list.
- **MgrCourseList** (0x3C, mgr_openSession's mem_new(0x3C)): retries, idx, count, courses[6], riders[6]. riders
  0..3 = mgr_pickRivals, [4] = GameFlow.playerRider, [5] = the boss 5 / 6 / 7 by options->seqStep; procMain's
  race state reads `list[idx + 3]` / `list[idx + 9]` (courses / riders). MgrRace.courseList is still s32 (the
  drawIntro `count == idx + 1` member form swaps registers; mgr onRaceOver's int-array form is a lever).
- **C++-safe headers**: gdl/race.h, game/modeproc.h, game/nameentry.h guard their `&((T *)0)->f` asserts and
  include relatively ("node.h", "../gdl/race.h"); under C++ race.h forward-declares BackupSession instead of
  including gdl/backup.h (not agent-h's; its asserts are C-only), so a donor cannot reach `session->modes`.
  The three mgr NCC donors (700, 23FC, 2B7C) now include modeproc.h / nameentry.h. game/input.h's C++
  `struct RaceTracker` mirror would now clash with race.h in a donor that includes both (owner: decide whether
  the mirror goes).
- **Colours**: MgrNameEntry_drawCongrats's credit glyph colours are RaceColourParms ctt / cnm / ccl / clg values;
  mgr_drawResults uses the RS / NR / AD pairs, drawIntro RN / CS. ColourParms_ctor's 32 sub-object addresses are
  `&((RaceColourParms *)arg0)->pair[RACECOL_*][0 / 1]` / ctt..clg.
- tit_procMain's a0 is the titproc ModeFlowProc (session->ghost for the vs-ghost states); the five game_init
  results use the Node child-attach idiom.

Census before -> after: owner h raw sites 511 -> 361; all raw casts 1599 -> 1500, accessor uses 282 -> 220.
mgr_initMatchRace 51 -> 0, MgrNameEntry_drawCongrats 32 -> 0, tit_procMain 32 -> 1 (GameFlow +0x8C, an unnamed
pad of game/input.h), GameFlow_startMode 22 -> 2, mgr_drawResults 22 -> 6 (session modes, GameFlow.dataMgr),
MGRRaceProcess_drawIntro 14 -> 2.

Next: the trk / arc pause-Bss twins (TimPauseBss in b3 / arcproc, not reached); port audit pattern A (only
ModeFlowProc.vptr done); MgrRace.courseList -> MgrCourseList * where the bytes allow; ask the input.h owner for
a name at GameFlow +0x8C (titproc stores 0x820000) and about the C++ RaceTracker mirror; SnowBoarder_ctor (13).

### Run 533 (agent-h): WinsDisplay, TreeTmpl, RaceSprite, RaceEntry score, GameFlow alias sites

Commits on agent-h (base 90d27efd3), each gated PASS (3288/3288, ROM identical, 6012 named calls / 0
mismatches, gameflow-import-sites.py check 0 mismatches; every touched .o, donors included, identical by
objdump -d -r -z in the matching and NON_MATCHING builds): bb18709d3 (H2HWinsDisplay bodies), aa4463dbe
(TreeTmpl), 9a948d1a7 (RaceEntry score / shownPending, TrkDataManager_update), bfbc96500 (RaceSprite,
arcproc_tail1), c2b97f488 (mgr drawIntro, bootup_uso_tail4), e52c235d9 (bootup_uso.c), a7bc7b16c (timproc
b1 / b3), eb8a61fb0 (h2hproc), 26c36cbe2 (titproc), c465427e3 (game_libs.c / tail / mgrproc). All hand
edits; no renames, no renames.tsv lines.

- **RaceSprite** (gdl/race.h, 0x18) is the gui_uso sprite slot: image 0x10 = BinFileMgr_getAcquire(fileId),
  fileId 0x14 (gui_spriteLoad / Refresh / Release); **RaceSpriteImage.width** (s16 +0x20) is what every
  overlay reads to place the next sprite (arc / mgr drawIntro, h2h WinsDisplay, CoolGadget bar). H2HWinsDisplay
  .sprites is RaceSprite[4] (the GuiSprite of bb18709d3 was folded into it in bfbc96500).
- **H2HWinsDisplay bodies**: the NM display body (frame, fader + VT_SLOT 2, race spriteSet / winner / wins,
  sprites) and the matching update NCC donor (layout mirrors: H2HWinsDisplay, WhiteFader, RaceProcess
  .timeout, GuiMenu cursor / rows; NCC donors build without -I include, so modeproc.h can't be included).
  H2HRace.wins is a pointer to s32[2] (`((int *)wins)[i]`).
- **TreeTmpl** (envobj.h, 0x74): the "tr1".. SNodeItemType item_registerTemplates builds (bootup_uso_ncc_55A0
  .cpp): ItemType head, items 0x34 (Trees via SNode.next), shape 0x40 = the PolyShape TreeTmpl_create builds
  once with PolyShape_ctor(0, "tree", shapeData, 0) (callee from the bootup.uso TextReloc), shapeData 0x48,
  colour 0x4C, fog 0x5C (FogParms).
- **RaceEntry** 0x18 score / 0x20 shownPending (stepped toward pendingPoints by 50 / 5 / 1 with
  snd_sendEvent(0x20, step) in tim / trk / arc update; points94 shows it). **TimDataManager 0xDC
  ghostReplayMode** (the TrkDataManager 0xD8 twin). **H2HDataManager 0xE8 / 0xEC health1 / health2** (the two
  CoolGadgets showing entries[0 / 1].health; a player retires at cur 0).
- **Int-load lever check (TrkDataManager_update)**: yes, it applies to the entry floats passed to the course
  gadget (`*(int *)&entries->pct / posX / progress`, same loads). points94 is a PointsPopup (alpha 0x78), +0x18
  of both gadgets is Node.doFlags. Arm 3 keeps `fl = (int *)entries; fl[8]` (the field form changes the code).
- **New general byte fact**: `*(int *)&p->field` is NOT the same tree as `p->field` under IDO cfe; it is the
  same as the raw `*(int *)((char *)p + K)`. Every "the member spelling recolours the fp regs / swaps the
  loads" site tried this run (CountDownGadget / Time / BestGadget alpha, CoolGadget `m[0] + xps`, the Parm
  cascade's `*(char **)&PARM(m2)->type = &D`) was byte-identical in that spelling, while `(s32)&D` stores and
  plain members changed the code. Also `entry->score != finalTime` vs `finalTime != entry->score` swaps the
  two loads (write the field whose load comes first on the left).
- **GameFlow via per-site aliases**: many `D_<mod>_<addr>_x` / `D_00000000` / `import_00020098` tokens are
  GameFlow (bootup Bss+0xF8); they are now `INPUT_MGR(tok).field` / `GAMEFLOW(base)->field` (procState,
  nextProcState, nextFlowMode, seq, demoIndex, backup, dataMgr, fader, unk184, locked, unk84 / 88). Proof per
  function: a throwaway reloc mapper (obj relocs aligned to `uso-imports.py sites <mod>` rows by the first
  jal) showed each token's ROM TextReloc target. gameflow-import-sites.py does not cover these (check: only
  0x8002xxxx tokens; plan crashes on titproc_uso.c with KeyError '' in scan, agent-a's tool).
- Other: VT_SLOT 10 for every `vt + 0x5C / 0x58` call in the mode ctors; BackupArcadeEntry.score /
  BackupTimeEntry.time[] / BackupScoreEntry.score record reads; WorldRegistry players[i].rider / windows[0]
  in the replay starts (h2h, titproc demo); func_000003F8 (sound pan) on CamWindow->cam world[3] / view rows;
  BaseLight.flags RMW levers; TrickPointsGadget.allIdle; CoolGadget seg / cur.

Census (readability-census.py raw casts) before -> after: arcproc 44 -> 14, bootup_uso 362 -> 311, h2hproc
68 -> 24, timproc b1 60 -> 18, b3 54 -> 23, titproc 84 -> 54, mgrproc 72 -> 65, game_libs (segment) 1408 ->
1398; owner h 1084 -> 839; all 3453 -> 3208. Files (census, compiled code): bootup_uso.c 134 -> 107,
game_libs.c 95 -> 89, game_libs_tail.c 38 -> 34. Whole-file `+K` casts (NM bodies and comments included):
h2hproc_uso.c 108 -> 42, titproc_uso.c 58 -> 27, timproc_uso_b1.c 60 -> 18, timproc_uso_b3.c 51 -> 20,
arcproc_uso_tail1.c 51 -> 21, bootup_uso_tail4.c 33 -> 9, mgrproc_uso.c 39 -> 24.

Next: game_libs.c ColourParms_ctor (85, all data tag / kRo_ sites: agent-a's data spelling); bootup_uso.c's
Snower / Fog / EnvSettings / BGBox / Tv1Tmpl gGfxLib sites (agent-b's GfxLib); BaseLight colour parm
(0x10C = Parms head + a GdlParmRGBA, value at 0x124: gdl/light.h is not mine); FallingSnow_create's owner
(+0x40 of an unknown object, gInputMgr_74e8_g / _h aliases: check their relocs); MemberCallback_invoke
_00007BF4 (sun.h's MemberCallback has Pair2 pmf: needs s16 delta / index fields); RiderCam_command's a2 +
0x30 (the course "cam" item: a ColourItem?); mgrproc import_8002xxxx_b sites the gameflow tool skips;
h2h / tim / trk / arc *_a Bss aliases (+4 / +0xA8: each mode's own Bss process pointer, a per-module struct);
the RaceProcess colour blocks at 0x260 / 0x284 / 0x380 / 0x3A4 (inside unk140: more RaceColour pairs).

### Run 529 (agent-h): SnowBoarder_ctor, TitleDemoProcess_handleInput, TrkDataManager, Tree, H2HWinsDisplay

Commits on agent-h (base cf7d7758f), each gated PASS (3288/3288, ROM identical, 6012 named calls / 0
mismatches; every touched .o, donors included, identical by objdump -d -r -z in the matching and NON_MATCHING
builds): 644be219e (SnowBoarder_ctor + snowboarder.h), 953cb325a (titproc 116C), 7fa0c2d82 (TrkDataManager),
6b2b8fbe4 (Tree), c83d3217b (H2HWinsDisplay). All hand edits; no renames, no renames.tsv lines.

- **SnowBoarder_ctor** (bootup_uso_90CC.c cfe donor, 309 -> 13 raw, the rest are data / list-walk reads):
  the 50 parm cascades write `PARMF(p)->type / value / unk14` (gdl/gadget.h, reached through dnode.h);
  **twt, bdm, cdm are int parms** (type Data 0x8060, defaults 25 / 10 / 15: `PARM`); the two Parms heads
  `PARMS()->name / unk04`; rider fields via SNOWB(arg0); child attach / vptr via NODE(); the trail emitters'
  draw is VT_SLOT(vt, 10); the "lighttarget" node is a LightTarget (mask, scale, unk108); the 0x878 member's
  vptr is COLLOBJ()->vptr. The donor now includes common.h / snowboarder.h / coll.h / light.h instead of
  private typedefs. Whole-file mechanical conversion kept every statement on its own line (as1 orders
  equal-ready instructions by source line) and was byte-identical first time.
- **snowboarder.h additions** (agent-g's header, additive only): 0x868 dispTrails / 0x86C dispSpray / 0x870
  trails (Node names "DispTrails" / "DispSpray" / "Trails"); 0x878..0x8B8 is a 0x40 **CollObj built in
  place** (coll_boxCtor_0003CAA0): collHitMask 0x88C / collCategory 0x88E (4 / 2 with flags & 8, else 5 / 1),
  and prevPos / prevVel are its pos / vel; 0x8BC initFlags (arg7 | 0x4800, SnowBoarder_reset copies it back
  into flags); 0x904 board (s16 ctor arg 3).
- **titproc 116C** (MIPSpro donor, 93 -> 2): edg can't take the gdl headers' asserts, so the donor carries
  layout mirrors (TitleDemoProcess, WhiteFader, GuiMenu cursor / rows, Node vptr + VT_SLOT, DataManager
  entries[0].finished). `GUIMENU(v1)->rows[cursor].arg` is byte-identical under MIPSpro too.
- **TrkDataManager** (modeproc.h, 0xE0): TimDataManager-shaped tail + 0xD8 ghostReplayMode (loadData 1;
  update mirrors entries[1].rider's PadCtl replayMode, a 1 -> 0 edge sends sendEntryLoseResult(this, 1)).
  `race` is `char *`; **byte lever**: the first three shownScore-arm raceState reads were int-typed loads
  and are written `*(int *)&TRKDATAMGR(arg0)->race` (all-pointer loads let IDO merge the arms).
- **Tree** (envobj.h, 0xC8) = SNode + CollCylinder at 0x88. Tree_handleMsg (msgs 7 / 19) copies snode.pos
  into coll.obj.pos; TreeTmpl_create sets snode.scale 10, coll vptr, coll.obj.flags |= 1. envobj.h includes
  gdl/coll.h now.
- **H2HWinsDisplay** (modeproc.h, 0x9C; H2HRace.postMenu): Node, race 0x2C, menu 0x30 (GuiMenu, unk30 =
  font), fader 0x34, sprites[4] 0x38, frame 0x98. h2h_createPauseMenu and onTimeout's fader wait use it.

Census (readability-census.py) before -> after: bootup_uso 667 -> 362, titproc_uso 175 -> 84, h2hproc_uso
88 -> 68, timproc_uso_b3 79 -> 54; owner h 1541 -> 1100; all raw casts 4336 -> 3895. Top files:
bootup_uso_90CC.c 309 -> off the list, titproc_uso_mp72_116C.cpp 93 -> 2, h2hproc_uso.c 71 -> 51,
timproc_uso_b3.c 71 -> 46, bootup_uso.c 143 -> 134.

Next: h2h_WinsDisplay_display / update (NM bodies) on H2HWinsDisplay; TreeTmpl (arg0 + 0x40 shape, +0x48);
TrkDataManager_update's entries + 0x20 / 0x30 and points94 + 0x18 / 0x78 (PointsGadget fields; check the
int-typed-load levers first); arcproc_tail1 (42), bootup_uso_tail4 (24), MGRRaceProcess_drawIntro (9) were not
reached; the gGfxLib +0x254 / +0x130 sites wait for agent-b's GfxLib struct; SnowBoarder_ctor's remaining
reads are GameFlow / InputMgr data sites (agent-a's aliases).

### Run 599 (agent-h): last unnamed calls in agent-h's files named or `UNNAMED:`-tagged

Commits 541300e15 (hand: 20 CALL names + 8 `&gSysLib` args) and 84fbefd83 (hand: 50 tags + D_00000050), both
gated PASS (3288/3288, ROM identical, check 6353 named calls / 0 mismatches). Census: 0 unjustified unnamed
calls / functions / globals in agent-h's files (calls overall 311 -> 233 unjustified).

- **Named from relocs** where name-placeholder-calls.py plan refuses (donor splice / SUFFIX recipe hosts):
  tim / trk_closeSession = Backup_closeSession (mod0 sym25, like arc's donors), h2h_closeSession = mem_delete
  (its only import), ColourItem_create_0000C5B0 + boot_ItemType_create_0000EBE8 / EE8C = mem_new,
  ColourItem_ctor, list_append; TreeTmpl_create's 8 (XCALL on the _087A4 aliases).
- **fs_gdlRead* readers** (game_libs.c / game_libs_tail.c) passed the bare `gl_func_00000000` token as the
  stream: it is gSysLib (Bss+0x3C740 Sym 73), now spelled `&gSysLib`.
- **Callees no tool can name** (unknown-role): nameent.uso Text+0x18 (bind the mode NameEntry to the
  session, right after its ctor) and Text+0x718 (on exit-fade done) in arc / mgr / tim / trk; heli.uso
  Text+0x1D4 and fire.uso Text+0x0 (item_createHel / Cfr); import mod60 sym120 / 122 (SnowBoarder_ctor) and
  sym179 / 180 (game_createMap, the "MapLighter" create): module id 60 is past the 59-entry USO table.
- **Gotchas:** (1) arcproc_uso_func_00000000's jal is fs_gdlReadFile, but CALL() fails the check: the
  PREFIX_BYTES entry-0 function owns no reloc site in the check's view (uso-imports prints `Text+0x1C`), so it
  is tagged `sentinel`. (2) An NM-only .cpp donor (SnowBoarder_handleMsg, h2h_WinsDisplay_display_00001360)
  cannot take CALL names (the .cpp check uses only functions whose bytes are the ROM); their tags name the
  ROM callee per site in TextReloc order. (3) A function-address store (Process_exit: &GameFlow_restart_000116C8,
  hi/lo) is not a jal, so CALL cannot spell it.

### Run 524 (agent-h): Parms ctor fields, WorldRegistry map / players, restart chain, PointsGadget_update donor

Commits on agent-h (base 57b2ad9b3), each gated PASS (3288/3288, ROM identical, 5457 named calls / 0
mismatches; every touched .o identical by objdump -d -r -z in the matching and NON_MATCHING builds):
736a7dfc9 (game_libs.c + gadget.h + PointsGadget_update donor), 41814745d (bootup_uso.c / game_libs_tail.c /
mgrproc), 0a9018c36 (timproc b1 / b3 stand-ins). All hand edits; no renames, no renames.tsv lines.

- **GdlParms** (gdl/gadget.h): the 8-byte head of every "<Class>::Parms" (name string, 0) + `PARMS()`;
  `PARMRGBA()` for the 0x24 colour parm. The four game_libs.c Parms ctors (TimeGadget / CoolGadget /
  CourseGadget / ColourParms) write PARMS / PARM / PARMRGBA fields (182 sites). ColourParms_ctor's
  remaining 60 are the `*(s32 *)((char *)&sTag_xxx_CFxx + 0xCFxx)` / kRo_ tag reads (data spelling, agent-a).
- **WorldRegistry.unk98 is the MapProp** game_createMap returns (game_init: unk98 = createMap(game,
  getCourse(game, a1), a2); the NM game_init body mis-reads it as the timer value). `WORLD_MAP(w)` (local
  macro in bootup_uso.c and game_libs_tail.c, #ifndef-guarded): game_setup* pass start[0] / start[2]
  (st0 x / z, +-500 for the 2-rider modes); RaceTracker_reset: courseStart = start[0], courseZ = start[2],
  courseLength = goal[2] - courseZ. **Ask agent-g** to type course.h `char *unk98` as `struct MapProp *map`
  and move WORLD_MAP there (or drop it).
- **restartCameras / restartWithTimeout** (and mgr_startReplay_00001AD0): state = GameFlow.game as
  WorldRegistry; q = players[0 / 1].rider; the pad = SNOWB(q)->input as a PadCtl (pad_reset gets
  pad->port, 0x34); pad_startRecord(pad, replayData[0], recordCap, &replayLen[0]); startPlay(pad,
  replayData[0], replayLen[0]). The shared `int *q` (q = v0, state = v1) is kept: q holds the rider
  pointers and the ghost.
- **RaceProcess_createReplayCam**: players[0].rider / input, windows[0] (savedCam; replayCam replaces it),
  Window.camera (0x70), fgRoot, bgRoot; savedCam doFlags &= ~8 (DoUpdate) and ~4 (DoDisplay).
- GameFlow fields in game_libs.c: dataMgr->hudFlags (endResult* / finishCourse / timeUp), nextFlowMode == 2
  (endRace / endRaceQuiet / drawGui, RaceTracker_sendWinResult), course (CourseGadget_ctor).
- VT_SLOT users: PointsGadget_display_000038F4 (slot 2 on each pop-up), RaceProcess_callGlobalSlot11
  (gSnowBoard slot 11), RaceTracker_sendEndingMsg (gSnowBoard slot 5, msg 0x3ED), send*Result (rider
  slot 4), SnowBoarder_update (slots 4 / 3).
- **PointsGadget_update donor** (game_libs_o2_3430.c): TPOINTS / POPUP fields; the fade-out adds the
  pop-up's value to dataMgr->entries->unk18 (player 1's score). **Byte gotcha**: with struct fields
  `x = d + x` loads d first; the FW / FF form loaded x first. Write `velY = velY + accelY`, `xps = xps +
  velX`, `yps = yps + velY` (same add.s operand order, same load order).
- MCamera.fov (cam_create results: 85 replay, 55 split screen), SNOWB(r)->camera, WorldRegistry
  windows[idx] / players[idx] (game_addWindow / addPlayer keep their same-line levers), RaceEntry[0 / 1]
  in mgr_DataManager_update (float fields passed as int: `*(int *)&e[1].pct`), CoolGadget seg / cur.
- tim_main / trk_main in-TU stand-ins (bytes from the -O0 donors): GAMEFLOW(d) procState / nextProcState /
  thenProcState / course / replayLen[0] / recCourse.

Census (scripts/readability-census.py, cast + accessor) before -> after: game_libs.c 325 -> 95,
game_libs_o2_3430.c 110 -> 0, game_libs_tail.c 59 -> 36, bootup_uso.c 184 -> 143, mgrproc_uso.c 53 -> 41,
timproc_uso_b1.c 80 -> 52, timproc_uso_b3.c 99 -> 71. Segments (casts / accessor uses): bootup_uso 712 /
149 -> 671 / 149, game_libs 1821 / 1530 -> 1662 / 1326, mgrproc 100 -> 88, timproc b1 88 -> 60, b3 107 -> 79;
all 4984 / 2619 -> 4716 / 2415. Untouched: arcproc_tail1 42, bootup_uso_tail4 24, h2hproc 71.

Next: TrkDataManager_update's 14 `*(char **)(arg0 + 0xB8)` (a Tim / Trk DataManager struct with race at
0xB8 in modeproc.h, like H2HDataManager); the game_setup* `+ 0x1B8` window link (game_create3DWindow
result: confirm the type first); Tree_handleMsg (SNode.pos -> Tree +0xA0 saved pos: needs a Tree struct in
envobj.h, agent-g); Snower / Fog / EnvSettings / BGBox gGfxLib +0x254 / +0x130 (needs a GfxLib struct,
GRAPHICS section 2); arcproc_tail1, h2hproc (h2h_createPauseMenu), bootup_uso_tail4; mgrproc's
import_800200D8 / 800200DC / 80020100 sites are GameFlow seen through per-offset import symbols (needs
the import-alias tool, not hand edits).

### Run 509 (agent-h): CoolGadget, GuiRow users, name entry, menu processes, title logos, PointsPopup

Commits on agent-h (base 6336bd167), each gated PASS (3288/3288, ROM identical; every touched .o identical
by objdump -d -r -z + data in the matching and NON_MATCHING builds, except where a reloc symbol name was
renamed on purpose): 2676464ac (CoolGadget), 94c673bb6 (gui_addRow / addRowSub on GuiRow), 59c62af87
(nameentry.h / modemenu.h), 53086561a (KeyMessage / MainLogo), 0d22975e7 (PointsPopup float Parms, Data
0xCACC tag symbol, mgr settings view), f8cbf138e (**pure rename**, 7 names). All others are hand edits.

- **CoolGadget** (gdl/gadget.h, 0x198; game_libs.c): Node + TimeGadgetParms, seg / cur / target /
  labelAlpha / total (0xC4..0xD4), colour 0xD8 (the unlit bar), GadgetRGBA lowColour / midColour /
  pulseLo / pulseHi (0xE8..0x118: seg < 4 / 4..11 / >= 12 pulses red .. yellow), phase / step, label1 /
  label2, bar / cap / label1 / label2 sprites. Renamed CoolGadget_setLabels / setLabelPos.
- **GuiRow**: gui_addRow_00010AB0 / gui_addRowSub_00010B6C use GuiMenu rows[numRows] (the -O0 member-array
  form is the lever and survives).
- **include/game/nameentry.h**: NameEntry (0xD4, nameent.uso export 69: entry 0x50, phase 0x60 = the slot
  17 / 18 / 19 selector, frame 0x68), ModeNameEntry (Tim / Trk / Arc 0x10C: race, pos[3][2], banner,
  alpha 0x108), MgrNameEntry (0x174: five sprites, alpha 0x168, panelY 0x170).
- **include/game/modemenu.h**: MenuProcess (0x54, "ARCMenu Process"; menu 0x48 = a GuiMenu whose
  rows[cursor].arg is the row callback; state 0x50) and TimMenu (0x6C, "TIMMenu Process": choice 0x58,
  blink 0x5C, promptY 0x68 of the save-ghost prompt). The race processes' unk048 is a GuiMenu too
  (RaceProcess init stores spriteSet into its +0x30 = GuiMenu.unk30; race.h is not mine, left).
- **KeyMessage / MainLogo** (modeproc.h): KeyMessage 0x3C (alpha 65..250, fading, x / y); MainLogo 0x74
  (alpha, hold, phase, colour, pos, part1 / part2 offsets, main logo pos).
- **PointsPopup +0x2C is a FloatPosParms** (0x38, the float "TimeGadget::Parms", ctor renamed
  FloatPosParms_ctor): x / y are parms.xps / yps.value; scaleX / scaleY 0x88 / 0x8C, accelY 0xAC. The
  bootup helpers are PointsPopup_setPosScale / setScale / slideStep (all callers pass popups).
- **Data 0xCACC tags**: `sTimeGadgetParmsTags_CACC` ([0..2] lby / l2x / l2y, [3] = 0xCAD8 the float Parms
  name), pinned 0xCACC like sFloatParmsTags_CAE8; the Text function is now SnowBoarder_toggleNudge (health
  1000000, toggles SNOWB_FLAG_NUDGE).
- mgr_initMatchRace's import_800201EC view (NCC donor .cpp) reads GameFlow options->seqStep.
- **Byte gotchas** (same rule as run 507): member addend pairs load in the opposite order, so sums are
  written `phase + step`, `pulseLo + ...`, `xps + lbx`, `posX + part1X`. CoolGadget_display's two
  `m[0] + xps` sums stay raw: every member spelling swaps their registers.
- Census (h492 regex) before -> after: game_libs.c 159 -> 84, timproc_uso_b1.c 108 -> 61, timproc_uso_b3.c
  117 -> 71, arcproc_uso_tail1.c 61 -> 38, mgrproc_uso.c 50 -> 39, titproc_uso.c 22 -> 17, bootup_uso total
  266 -> 251 (tail4 46 -> 38, o0_10AB0 7 -> 0).

Next: the NM update / handleInput bodies with array-index levers (TimMenu_update, ARCMenuProcess_handleInput,
ArcNameEntry_update); TimNameEntry / Arc ctors' typed-chain levers (`Tim16F8_A`: race +0x6B0); game_libs.c's
remaining 84 sites; RaceProcess.unk048 -> a GuiMenu (agent-c's race.h); Fader_ctor / buildTexture Node /
vtable sites; gadget_decodeStringB4_00014598 (PointsPopup text cipher; no static callers found).

### Run 503 (agent-c): genproc Parms records, GenRoom, gen_imp_ imports

Commits on agent-c (base c519196e2). Each was gated PASS (3288/3288, ROM identical), and every genproc
.o was identical by objdump -d -r -z in the matching and NON_MATCHING builds:
- 21471dc5e (hand edit): select.h Parms records, SelectWin colours / font / sceneSet / forceAccept,
  and conversions.
- 63848a140 (**pure rename**): 49 `gen_imp_*` import aliases.
- 1c480c86b (hand edit): GenRoom.
- fa70d1b0a (**pure rename**): snd_soundObjSetReverb.
- 0dabd7733 (hand edit): audio.h reverbOn.
- 638a22724: 873 lines of `#if 0` dropped with deadblocks.py.

- **HostIO parm records** (include/game/select.h, `SelParmI / F / V3 / RGBA`): value at +0x10, named
  by the 3-letter tags the ctors pass (Data name tables).
  - `SelectWinParms` (SelectWin +0x2C, 0x38C) holds cwt, voy, ysp, hxp, hyp, msp, zsp, lsp, lfw,
    sfw, cc0..cc8, c12, cc9, c11, c10, clx, cly, cox, coy, cff, cdf, ctf and tpy.
    - msp = the transition step;
    - zsp / lsp = the fade steps;
    - lfw = the idleTimer reload;
    - ysp = the stat row spacing;
    - cc8 / c12 = the two colours passed to the item draw slot (win 0x254 / 0x278).
  - `SelItemParms` (SelItem +0x2C) holds xpn ypn (label position), jnx jny, xp0 yp0 (stat bars),
    xfp yfp, xfc yfc, cfv cf2, and off / of2 (camera offsets).
  - `SelItemInfo` (SelItem +0x194) holds ixn (label row), am0..am4 (stat values), pos, rot, chy
    and scl.
- **Item +0x25C..0x264 / 0x294** = info.rot.v / info.scl.value. All five item classes copy
  view[0..3] = {rot.z, rot.x, rot.y, scl}; only the statement order differs, and that order is a
  matching lever.
- **SelectWin**:
  - 0x408 `forceAccept`: state3 treats it as an accept press (button 0x100); never set in
    genproc;
  - 0x410 `sceneSet` = SelectionMgr +0x2C (+4 / +8 = the per-player scene, stored at 0x414);
  - 0x420 `colors[6][4]`: RGBA / 255 from SelectWin_init (90 grey, 255/145/58 orange, white,
    13 near-black, 161/91/35 brown, 70 grey); no reader in genproc;
  - 0x4D0 `font` = gui_fontCreate(0, font, 0x48, 0xDD, 3, 13).
- **GenRoom** (gen_buildRoom, 0x60):
  - world 0x2C;
  - three BaseLights 0x38..0x40: "Ambient Light" (mask 1), "Local Light" (mask 2), and a second
    "Ambient Light" (mask 4, colour 174/113/61);
  - walls[6] 0x44: U64BGWall sky-box faces under the "BGBox2" BGBox (gen_createVRBox);
  - modifier 0x5C (RoomModifier).
- **Imports.** genproc's `timproc_uso_b5_func_XXXXXX` aliases are imports. The suffix is the
  bootup address + 0x1466C, or the bootup_uso address itself. They are now `gen_imp_<target>`
  (e.g. gen_imp_list_append, gen_imp_mem_new, gen_imp_Parms_addParm), resolved with
  `scripts/uso-imports.py imports genproc`.
- **Census** (conv2 PAT + FW patterns, incl. donors): 1711 -> 1587. timproc_uso_b5.c 963 -> 851,
  CEB4 12 -> 3, o2_5FC0 38 -> 35.
- **Reverted** because the bytes changed:
  - SelectWin_display `tpy` (load order);
  - canScrollNext (t-regs);
  - state8;
  - the 5FC0 donor's transition / fade operands (f16 / f18).

Next (H1):
- The match_imports donors' own context types (`B5TimingScreen` field_xxx in
  context_timproc_uso_b5.h) could take the SelectWin names: a field rename only.
- The SelItemsMgr_ctor / *List_createItem bodies (largest raw blocks).
- gen_createScene {room, cam, cam2}.
- CourseItem_update's model offsets (lever-sensitive int-cast forms).
- Names for the 0x1CDD0 heap-size block's first word.

### Run 513 (agent-c): donor context names, SelItemsMgr / SelItemList / GenScene

Commits on agent-c (base 856a0476b). Every one was gated PASS (3288/3288, ROM identical), and every
genproc / donor .o was identical by objdump -d -r -z in the matching and NON_MATCHING builds:
- 8cb77668c (hand edit, field rename only): context_timproc_uso_b5.h's `B5TimingScreen` / Panels / Row /
  Entry / Vtable and `TimB5EntryFields` take the select.h names (SelectWin out / cheatChar / curItem /
  chosenItem / itemsMgr / colors / font / scene / idleTimer / transition, the flattened parm values ysp /
  lfw / cc0..cc4 / cc7; SelItemsMgr lists; SelItemList items / count; SelItem vt / enabled / id / flags;
  vtable slots 11 focus / 15 setChosen; SelItemEx xp0 / yp0 / cfv / am0..am4 / node / model / barCount).
  CharacterItem_drawStats keeps its raw yp0 read: `a0->yp0` changes the bytes.
- f05e0b820 (hand edit): select.h SelItemsMgr (0x60): vptr, the three CommonInfo words 0x2C..0x34
  (0x30 = the node DispItems hangs under), dispItems 0x38, commonInfo 0x50, tesuri[3] 0x54 (the three
  "Tesuri Item"s; [2] only when game mode != 2). SelItemList gets the same head + dispItems 0x38.
  SelItem.listIndex 0x2AC (LevelList_createItem stores the list count; LevelItem_drawStats lights that
  slot). Converted: SelItemsMgr_ctor's self / tesuri accesses, Course / LevelList_createItem (item and
  model fields, list dispItems / count), LevelItem_drawStats.
- aee0ed8be (hand edit): `GenScene` {room, cam, cam2} (gen_createScene; = SelectionMgr.sceneSet; cam /
  cam2 are the SelectWin scenes). gen_createScene and SelectionMgr_ctor converted (NODE() attach idiom,
  numPlayers / sceneSet / wins). gen_createScene builds "MainGame" with "bg" / "fg".
- 16d3a74ae (hand edit): CourseItem_update on SelCourseModel through CMODEL(); the arm-local int-cast
  re-def `(float *)((int)CMODEL(a0) + 0x128)` stays (it is the lever).
- Node names come from the genproc Data block (Yay0 at ROM 0x5BCEB6, decompressed 0x1790 bytes):
  0x1334 "MainGame", 0x1340 "bg", 0x1344 "fg", 0x1350 "SelItemsMgr", 0x1364 "Common Info", 0x1378
  "DispItems", 0x138C / 0x147C / 0x1518 "Tesuri Item", 0x1428 / 0x1440 / 0x1454 / 0x1468 the four lists.
- Census (c503 PAT + FW patterns, incl. donors): 2132 -> 2062. timproc_uso_b5.c 823 -> 792, 8FC8 83 -> 79,
  D884 47 -> 31, DF14 49 -> 33, CEB4 3 -> 0.

Next (H1):
- SelectionMgr_ctor's split layout (0x3C..0x54, set per stageBit then SelectionMgr_setSplit_00001DB0).
- The S70 list ctors (NEWS70 in 8FC8) onto SelItemList; the QNode model heads (0xB4 pos, 0xDC..0xE4,
  0x108 lighttarget kid) as a shared SelModel base.
- The match_imports Character / BoardList_createItem donors onto the context names.
- Names for the 0x1CDD0 heap-size block's first word.

### Run 522 (agent-c): SelectionMgr split screen, stage-list ctors

a5e71bace on agent-c (hand edit; gate PASS 3288/3288; timproc_uso_b5.c.o, _8FC8.c.o and every
select.h includer identical by sections, relocations and objdump -d -r):
- `SelectionMgr` (0x58, asserted) 0x3C..0x54, from SelectionMgr_update (ncc_1F14), setSplit
  (ncc_1DB0), finish and the ctor: waitMask 0x3C (bit 0 / 1 = wins[0] / wins[1] in SelectWin state 8,
  rebuilt every update), prevWaitMask 0x40, split 0x44 (= wins[0]->centerX; wins[1] gets 0xF0 - split;
  0x78 is the even split), zoomWin 0x48 (was unk48; 1 / 2 = the window sliding to full screen, the one
  finish reports), busy 0x4C, shownMask 0x50 (bit per window with nonzero centerX), splitT 0x54 (0..1,
  +0.05 per frame; split = 120 +- splitT * 120, also the fov / aspect blend). The ctor's two arms
  (stageBit != 4: even split; == 4: wins[0] full screen, then setSplit) and finish are converted.
- 8FC8 NEWS70 (Character / Board / Course / LevelList 0x70 ctors) writes SelItemList vptr / cfg2C /
  parent / cfg34 / dispItems / count; VT = the SelItemList base vtable (Data 0xA94).
- Census (F[WPF]( macro sites): timproc_uso_b5.c 365 -> 353, 8FC8 161 -> 154.

Not done this run (next):
- The ncc_1F14 / ncc_1DB0 donors still use raw SelectionMgr / SelectWin offsets (C++ units with their
  own typedefs; including select.h there is untested under edg).
- A shared select-model base (the five Sel*Model heads: pad to 0x10C, view / alpha / highlight /
  focused / chosen at class-specific offsets, so only the 0x10C QNode head is common).
- The match_imports Character / BoardList_createItem donors onto the context names.
- timproc_uso_b5.c's remaining raw sites (the SelectWin_update / state bodies, SELWIN() users).

### Run 525 (agent-c): SelModel base, Window view, the split-screen and createItem donors

Two hand-edit commits on agent-c (base 0c969f011), each gated PASS (3288/3288, ROM identical,
placeholder check 0 mismatches). Every rebuilt object, in both trees, is identical to a fresh
pre-run build: sections and relocations match, and so does `objdump -d -r`. The rebuilt objects
are every select.h includer, ncc_1DB0 / ncc_1F14, all ten context_timproc_uso_b5.h users and
their linked / stripped objects, and o2_5FC0.
- f59d12716: **select.h**
  - **`SelModel` (0x10C)** = QNode (0x104) + unk104 + `inner` (0x108). It is the head of all five
    Sel*Model types. Every createItem builds the model with QNode_ctor(model, name, 0, 0, 0). It
    then allocates a 0x16C child QNode (QNode_ctor; +0x108 / 0x10C / 0x110 get one RoData
    constant, +0x124 = 1.0), stores it at +0x108, MNode_addChild's it, and sets
    inner->vqs.trans. SelectWin_ctor passes the three Tesuri models' `inner` to the 0.5f setup
    calls.
  - SelCharModel gains unk124 / unk128 / unk134 (createItem's initial values).
  - **C++ (edg) and select.h:**
    - The NCC donors include it by relative path (`../../include/game/select.h`).
    - As agent-g did in snowboarder.h, the SELECT_ASSERT block is `#ifndef __cplusplus`. edg
      rejects the `&((T *)0)->f` form (error 3153 / 3267); the C builds still check the offsets.
    - In C the header includes gdl/mnode.h + gdl/window.h. In C++ it gets an opaque
      `char qnode[0x104]` head and a Window mirror (aspect / width / height / originX / originY /
      vpW / vpH / vpX / vpY).
  - **`SELWIN_VIEW(w)`** = `*(Window **)(w->scene + 0xC)`, the window's screen Window
    (scene +0xC +0x70 = the camera, fov at +0x14C).
  - **The two-player split is vertical.** Of the run-522 fields, `split` and `SelectWin.centerX`
    are pixel heights, not x positions. setSplit writes wins[0] height = vpH = split
    (originY = vpY = 0), and wins[1] height = vpH = 0xF0 - split at originY = vpY = split. The
    aspect blend is 1.333 + 1.3333 * t, so 0xF0 = the 240-line screen. `centerX` is therefore a
    misnomer (rename candidate: viewH). It was left as is this run.
  - **Donors converted:**
    - ncc_1DB0 (setSplit) and ncc_1F14 (SelectionMgr_update) use SelectionMgr / SelectWin /
      Window members only (census 60 / 284 casts -> 0).
    - match_imports CharacterList_createItem / BoardList_createItem use SelItemList,
      SelCharacterItem, SelChar / BoardModel and SelItem. The board model's 0xDC..0xE4 are
      head.qnode.cvqs.trans.
    - context_timproc_uso_b5.h includes select.h and drops TimB5UiOwner / TimB5UiPanel.
- 3ca2ac228: **SelectWin_update donor (o2_5FC0) and state0..9**
  - Now members: owner, itemsMgr->tesuri[0..2], the other window's stageBit / stageLock,
    SELITEM id / flags, owner->busy, the otherWin / canCommit / finish arguments, and
    itemsMgr->lists[2]->count.
  - **Byte traps (kept raw, commented):**
    - In SelectWin_update, the item's zoom-fov reads (`sp2C + 0x14C` = parms.cf2.value,
      `+ 0x134` = parms.cfv.value) stay raw: as members, the two mul.s swap their operands.
    - In state8, `FW(e, 0x4B4)` (the other window's busy) and `FW(owner, 0x48)` (zoomWin) stay
      raw: as members, both swap their lw registers.
- **Census** (`scripts/readability-census.py`, raw `*(T *)(p+K)` / accessor uses):
  - Segments: timproc_uso_b5 880 / 502 -> 530 / 472, match_imports 498 -> 467.
  - Files: timproc_uso_b5.c 368 + 191 -> 362 + 172; ncc_1F14 284 -> 0; ncc_1DB0 60 -> 0.

Next (H1):
- Rename `SelectWin.centerX` -> `viewH` (and SelectionMgr.split's comment) as a field edit.
- The scene's +0x10 camera node (camPos copies from +0x60..0x68 = MNode mtx[3]) and
  SELWIN_VIEW()->camera fov reads in state3 / state4 / beginTransition.
- The board item's extra word at 0x2C4 (BoardList_createItem clears it; SEL_ITEM_CLASS is 0x2C4).
- The vtable slot calls (`FW(FW(e, 0x28), 0x8C)` etc.) through a typed SelItem vtable.

### Run 530 (agent-c): viewH, GenCamera, the SelItem vtable, SelBoardItem.blink

Two commits on agent-c (base 100406707), each gated PASS (3288/3288, ROM identical, placeholder
check 0 mismatches). Every select.h includer (genproc C / C++, o2_5FC0, the match_imports donors
and their linked objects) is identical to a fresh pre-run build in both trees: sections,
relocations and `objdump -d -r`.
- 080318e83 (hand edit, field rename only): `SelectWin.centerX` -> **`viewH`** (0x4D8, the window
  height in lines: 0x78 / 0xF0). SelectionMgr.split / shownMask comments follow.
- 58875304c (hand edit): **select.h**
  - **`GenCamera` (0x20)** = gen_createCamera_0000283C's rig = GenScene.cam / cam2 =
    `SelectWin.scene` (now `GenCamera *`): world / unk04 / unk08 (app +0x134 +0x84 / +0x80 /
    +0x8C), view 0xC (the 3D Window), **target 0x10** (the MCamera's look-at MNode,
    MCamera_ctor(0, target, 0, 0, 0), moved to (0, 0, -400); camPos copies its mtx[3]), anchor
    0x14 (the first MNode; SelectWin_init passes target / anchor to setCamToItem), **camera 0x18**
    (MCamera; state6 turns pitch / yaw while rotEnable). The ctor's arg 3 is the fov (0x3C one
    player, 0x29 two). `SELWIN_VIEW(w)` = w->scene->view; `SELWIN_CAMERA(w)` = the Window's
    MCamera (same object). select.h includes game/camera.h in C.
  - **`SelItemVtbl` (0xE8)** of `SelVEntry {short delta; short pad; void *fn}` (slot N at
    vtbl + 8 + 8N). Slot names from the BoardItem / SelItem overrides: 10 updateHighlight,
    11 focus, 12 unfocus, 13 onStageLeave, 14 onStageReturn, 15 setChosen, 16 clearChosen,
    17 toggleVariant, 18 playPickAnim, 19 playAcceptAnim, 20 confirm, 21 copyState, 22 setAlpha,
    23 drawLabel, 24 drawSubLabel, 25 drawStats, 26 drawArrows, 27 loadInfo. SelItem.vptr is
    `SelItemVtbl *`; `SELVT(v)` views a raw vtable local. 52 slot calls converted (state0..9,
    display, init, beginTransition, the 5FC0 donor), plus their vptr loads. No byte lever
    appeared: `(GP)SELVT(v)->slot.fn)(SELVT(v)->slot.delta + o, ...)` is the same code as the
    FW form.
  - **`SelBoardItem` (0x2C8)** is its own type: `blink` 0x2C4 (BoardItem_drawStats counts it up
    per draw; bit 3 shows the extra (233, 247, 0) sprite).
  - Converted besides: gen_createCamera's self stores (GCAM), the camPos / fovFrom reads in
    state3 / state4 / beginTransition, state6's rotEnable / pitch / yaw, SelectWin_display's view
    height, the drawLabel originY + height sum.
- **Census** (readability-census.py, casts / accessor uses): timproc_uso_b5 segment 530 / 472 ->
  438 / 362; timproc_uso_b5.c 362 + 172 -> 276 + 71; owner c total 1468 -> 1182 (with the audio
  commit, 1080_AUDIO.md run 530).

Next (H1):
- GenSelectChar_initLabels_00000778 (48 casts, the top genproc function), gen_createVRBox (21),
  gen_buildRoom (15), SelItem_drawStatBar / Right (12 / 14).
- GenScene.cam / cam2 can become `GenCamera *` (gen_createScene / SelectionMgr_ctor users).
- The C++ donors (ncc_C310 BoardItem_drawStats, ncc_2B74 / 32C8 / BDEC / 8AFC) still use raw
  offsets; they can include select.h now (the edg path has SelVEntry / SelItemVtbl, no MNode).
- gen_createCamera's Window flags (+0x78, the `if (1)` lever) and clearColour (+0xDC same-line
  store lever) stay raw.

### Run 535 (agent-c): GenSelectChar, GenScene cameras, initLabels

7910d265e on agent-c (hand edit; gate PASS 3288/3288, placeholder and gameflow checks 0 mismatches;
every b5 C / C++ object identical to the pre-run build by `objdump -d -r`, data and relocations,
matching and NON_MATCHING).
- **select.h `GenSelectChar` (0x58)**: a 0x50 Process base (the ctor's inlined base ctors allocate
  0x50 / 0x2C; the +0x10 child list gets the SelItemsMgr(s), the SelectionMgr and the Fader),
  **twoPlayer 0x50** (0 when the ctor's player count, gen_createScene's a1, is 1, else 1: one
  SelItemsMgr vs two), unk54. GenSelectChar_initLabels_00000778 takes `GenSelectChar *self`.
- **Lever (initLabels):** the 48 n reads are spelled `*(int *)&self->twoPlayer`. A plain member
  load recolours the t-registers from the 0x14 group to the end. So does a
  `((GenSelectChar *)arg0)->` macro with the char * param, and so does swapping the `g + n * 2`
  operands. The address-deref form keeps the target's. Dropping the cast on
  `*(int *)&import_8002022C` (already `extern int`) also recolours, so leave it. import_8002022C
  is bootup Bss+0x28C (READABILITY_PLAN 9.1.11). Its label-id use (g * 5, g * 12, g + 8,
  g + 0x23) suggests a language / region index, but that is not proven, so it stays unnamed.
- **GenScene.cam / cam2 are `GenCamera *`.** gen_createScene: cam2's view gets
  `unk1B8 = cam->view`. +0x1B8 is past Window (0x144), so the view is a ScreenWindow (cast there).
- **Census:** timproc_uso_b5.c 259 + 70 -> 208 + 70; timproc_uso_b5 segment 406 -> 355 raw.

Next (H1):
- gen_createVRBox (21), gen_buildRoom (15), SelItem_drawStatBar / Right (12 / 14).
- The C++ donors (C310 34, BDEC 20, 8AFC 13, 2B74 11, 32C8 10) including select.h by relative
  path (the edg mirror exists). Not started this run.

### Run 539 (agent-c): Node child-attach idiom, GenRoom world roots, stat bars, the five edg donors on select.h

df4eecbf4 and addf6fb8e on agent-c (hand edits, no renames; each gated PASS 3288/3288,
placeholder and gameflow checks 0 mismatches). Every build/ object, matching and NON_MATCHING,
is identical to the pre-run build by `objdump -d -r -s` (.mdebug excluded).
- **Child-attach idiom** (b5.c, _8FC8 macros, _D884, _DF14): `list_append(&NODE(p)->children, c);
  if (NODE(c)->parent) NODE(c)->unk04 = 1; NODE(c)->parent = (int)p;`. **Trap:** in
  SelectWin_ctor (b5.c and _4118) the `spA8 + 0x14` stores are on 0x18-byte SelParm records, not
  Nodes, so a blind regex on `+ 0x14` is wrong there. Convert only inside the idiom.
- **GenRoom / GenCamera world roots:** GameFlow.game is the WorldRegistry (game/course.h).
  GenRoom world / unk30 / unk34 and GenCamera world / unk04 / unk08 are renamed to
  bg / fg / mainGame (bgRoot 0x84, fgRoot 0x80, mainGame 0x8C), read through WORLDREG().
  SelItemsMgr / SelItemList cfg2C / parent / cfg34 are the same three words (CommonInfo copy)
  and can take the same names next.
- **Stat bars (3A4C / 3C8C):** arg7 is the SelectWin. The offsets are its Parms values cox / coy /
  clx / cly / cff / cdf. The sprite derefs (`+0x10` image, `+0x20` s16 width, which looks like
  an ImageFile) are left raw because the sprite type is unproven.
- **The edg donors** C310 / BDEC / 8AFC / 2B74 / 32C8 include select.h, with no lever needed:
  - C310 is on SelBoardItem / SelBoardModel (lit, spin) and SelectWin cc[0..4] / cc[7].rgba,
    ysp, numPlayers;
  - BDEC uses scene->view->originY, hxp / hyp, unk4A0 (an alpha scale: `denom * unk4A0` is the
    sprite alpha);
  - 8AFC (named RoomModifier_resetScale, but `scr` is a SelectWin) walks
    itemsMgr->lists[g]->items[i] and calls vtable slot updateHighlight;
  - 2B74 / 32C8 build each parm at &SELF->field through SelParmI / F / V3.
- **Census:** timproc_uso_b5.c 208 + 70 -> 156 + 49. Segment 355 -> 220 raw. C310 34, BDEC 20 and
  8AFC 13 are now 0; 2B74 51 -> 3 and 32C8 38 -> 2. Owner c 923 -> 667.

Next (H1):
- SelItemsMgr_ctor (_8FC8, 64: its ADD macros' FP / FW parm writes), LevelList / CourseList
  createItem (27 / 26), SelectWin_ctor (_4118, 113: the SelParm records via PI / PF / PV
  as in 2B74).
- 8AFC's name: RoomModifier_resetScale_00008AFC takes a SelectWin. Rename it with
  rename-symbol.py once the role is settled.
- SelectWin.unk4A0 -> an alpha name (BDEC and the other draw slots multiply 255 by it).

### Run 544 (agent-c): SelectWin_ctor parms, SelItemsMgr_ctor, Course / LevelList createItem, world roots, acceptAlpha

Commits on agent-c (base bcc816ae4), each gated PASS (3288/3288, ROM identical, placeholder /
data-site / GameFlow checks 0 mismatches). Every b5 / game_libs / match_imports object, matching
and NON_MATCHING, is identical to the pre-run build by `objdump -d -r`, `-r` and `-s` (.mdebug
excluded; the rename commit differs only in the symbol name).
- b8a0e85dc (hand edit):
  - **SelectWin_ctor** (_4118 donor and the b5.c NM copy, kept in step): each parm is built at
    `&WPARMS(var_s0)->tag` and written through PI / PF / PC (SelParmI / F / RGBA), as in 2B74.
    Node name / vptr, eventFlags, the fov read (`((MCamera *)((GenCamera *)arg9)->view->camera)->fov`)
    and `tesuri[k]->model->head.inner` are members. No lever needed. The cfront null checks
    `var_s0 != (char *)-0x2CC` stay as they are.
  - **SelItemsMgr_ctor** (_8FC8): SelTesuriModel is now 0x168 (unk120, unk128, unk12C,
    numShapes 0x13C, unk140, unk144, shapes[8] 0x148). The 0x16C inner node is a LightTarget
    (unk108[], mask = 1, scale). The parm V3 / F writes, the vqs zeroes, and the list calls
    go through VT_SLOT(v, 10) (createItem: the signature of the four *_createItem overrides)
    and VT_SLOT(w, 3).
    **Lever:** `NODE(p)->vptr = (int)&sym` (or `->name`) hoists the address lui / addiu above
    the preceding Node_ctor call and grows the function by 2 words. `*(char **)&NODE(p)->vptr = &sym`
    keeps the target's order. This is the same address-deref form as agent-h's
    `*(int *)&p->field`.
  - **CourseList / LevelList createItem**: SelCourseModel / SelLevelModel gain unk120, unk13C
    and unk140 (level also unk128 and unk134). Both are 0x144. The items[] store is
    `LIST->items[n]`.
  - SelItemsMgr / SelItemList **cfg2C / parent / cfg34 -> bg / fg / mainGame** (char *, as
    GenRoom / GenCamera). CommonInfo_init_0000A928 is on them.
  - **SelectWin.unk4A0 -> acceptAlpha**: set to 1 on an accept press in game mode 2
    (state3 -> state 4), faded by RoData 0x1D0 per frame in state5, and it scales the BDEC
    sprites' alpha.
- 5604e46c5 (**pure rename**, rename-symbol.py): RoomModifier_resetScale_00008AFC ->
  **SelectWin_dimOtherItems_00008AFC**. Every item except the current one gets
  updateHighlight(1 - fade * 0.9), and the current one gets 1.0.
- **Census:** timproc_uso_b5 segment 220 raw + 258 accessor -> 179 + 90. _4118 113 -> 0,
  _8FC8 64 -> 18, DF14 27 -> 1, D884 26 -> 2. Owner c 696 -> 467 (with the audio commit).

Next (H1):
- _8FC8's last 18: the gPolyGeomMode / f8fc8_* flag-word chain (FW(&sym, 4), a global's
  second word), the CommonInfo `+0x2C = this` store, FF(import_80807FB8, ...) RoData reads.
- b5.c's top functions: SelectionMgr_setSplit (16), SelectWin_display (14), state8 (13),
  SelectionMgr_update (12). SelCharacter_display (B624, 12).
- RoomModifier_display_0000117C calls SelectWin_dimOtherItems on its field_38[field_34].
  RoomModifier may be a SelectionMgr-side name too, so check it.

### Run 548 (agent-c): SelCharAnim, SelCharModel animTimer / visible, the b5.c display / state8 / placeholder sites

Commits on agent-c (base 2acd57ec4), each gated PASS (3288/3288, ROM identical, placeholder /
data-site / GameFlow checks 0 mismatches). Every b5 / match_imports object that includes select.h,
matching and NON_MATCHING, is identical to the pre-run build by `objdump -d -r`, `-r` and `-s`
(.mdebug excluded).
- 4780413dc (hand edit):
  - **select.h SelCharAnim** = SelCharModel.anim: an AnimPlayer (0xB0) + `keyHit` (0xB0). Its
    onKey (SelCharAnim_vfunc10_0000ABB4 = vtable slot 10) sets keyHit and parks eventKey at
    ANIM_NO_KEY; every CharacterItem anim change clears keyHit (eventKey -1000, or 2 on confirm).
  - **SelCharModel.unk134 -> visible** (SelCharacter_display: 1 when the model faces the camera
    and is drawn, else 0). **animMode -> animTimer**: the 8 / 0x10 / 0x20 values set by
    onStageLeave / confirm / unfocus are frame counts. Display keeps updating the model while
    animTimer or focused is set, counts animTimer down, and at 0 a pending keyHit restarts the
    idle anim (animSet, 0, 2, 2, 1).
  - SelCharacter_display (ncc_B624): the donor's local Obj mirrors SelCharModel (edg sees no gdl
    headers). 12 -> 1 raw (the RoData f64 compare).
  - SelectionMgr_setSplit / SelectionMgr_update placeholders in b5.c (rodata only; the splice
    drops their text): `stateNames[i]` / `dbl[8..9]` and `fv` / `dv` pointers. The same rewrite
    of SelectWin_update_00005FC0's placeholder grows it 0xEC -> 0xF0 and loses a trailing
    alignment nop in timproc_uso_b5.c.o, so it was reverted. **The ROM check still said OK**:
    compare the .o, not only the ROM, for placeholder edits.
  - SelectWin_display: scene->view height / originY, parms.tpy.value, the stage table as an
    array, `parms.cc[5] / cc[6] / cc[8] / c12 / cc9 / c11 .rgba` arguments.
    **Lever:** `originY + parms.tpy.value` as plain members swaps the two lw;
    `*(int *)&SELWIN(arg0)->parms.tpy.value` keeps the order.
  - SelectWin_state8: the other window's busy, owner->zoomWin and eventFlags via
    `*(int *)&member` (run 525 left the first two raw because the plain members swap their
    registers); curItem[stage]; itemsMgr->lists[2]->items; parms.cwt.value. 13 -> 0. The
    select.h "eventFlags stays raw" note may now be obsolete for the other state functions
    too (untested there).
- 5f8e36979 (**pure rename**): RoomModifier_applyScale_0000896C -> **SelectWin_setGlobalFade_0000896C**.
  Its argument is a SelectWin (RoomModifier_display passes wins[count]), and it stores fade * 0.4
  into a genproc global. **RoomModifier_display_0000117C is not misnamed**: its a0 is the
  RoomModifier node (ctor 10EC, vtbl 0x3E4, windows at 0x38 / 0x3C, index 0x34 reset by update).
  Per window render it calls setGlobalFade / dimOtherItems on that window, then shows that
  window's DispItems (`itemsMgr->dispItems` +0x18 doFlags |= 4) and hides the other's.
- **Census:** timproc_uso_b5 segment 179 raw + 90 accessor -> 140 + 61; timproc_uso_b5.c
  156 + 49 -> 117 + 31. Owner c 453 -> 375 (with the audio commit).

Next (H1):
- _8FC8's last 18 (the gPolyGeomMode / f8fc8_* flag-word chain, CommonInfo +0x2C = this,
  the FF(import_80807FB8, ...) RoData reads).
- port-audit `--owner c` top: SelectWin_ctor (_4118, 34, pattern B), SelItemParms_ctor (2B74, 15),
  SelItemInfo_ctor (32C8, 11), SelectionMgr_finish (6), Course / LevelList_createItem (6 each).
- RoomModifier_display (NM) on SELWIN / SelItemsMgr members: dispItems doFlags bit 4.
- gen_createCamera_0000283C (11).

### Run 574 (agent-c): setCamToItem, canCommit, DispItems camera axis

1ba066e5c on agent-c (base da8d26426; hand edit, no renames; gate PASS 3288/3288, ROM identical,
source checks 0 mismatches; every build/src object identical by objdump).
- **SelectWin_setCamToItem_00003A28:** `((QNode *)item->node)->cvqs.trans` into
  `((MNode *)cam)->mtx[3]`, which snaps the camera node onto the item.
- **SelectionMgr_canCommit_00001D1C:** `wins[a1]` / `wins[a1 ^ 1]`, `stageBit`, `state`. The
  three defs stay on one source line (the as1 tie-break lever).
- **DispItems_display_0000E5D8:** the state global is a CamWindow. The three floats are
  `cam->view[0..2][2]` (the camera's look axis), copied into an imported vec3.
- **Not converted (byte-locked):** SelItemsMgr_ctor's five FF() RoData reads (pinned float
  pool) and gen_createScene's three unidentified game_libs globals (distinct-alias /
  pointer-mutate levers).
- **Census:** timproc_uso_b5 segment 39 -> 36 raw (b5.c 25 + 5 -> 22 + 5).

### Run 569 (agent-c): commitSelection PICK, display sprite widths, camera window, cheat index

fdca02565 + e4639db81 on agent-c (base 3f4755e0b; hand edits, no renames; gate PASS 3288/3288 before
each commit, ROM identical, the three source checks 0 mismatches). All 1149 objects of the full
build, matching and NON_MATCHING, identical to the pre-run build by `objdump -d -r`, `-r` and `-s`.
- **SelectWin_commitSelection_00006C00:** the E6C00 offset macro is gone. `PICK(s)` =
  `*(curItem[s] + itemsMgr->lists[s]->items)`: written index-first, which keeps the old
  `idx * 4 + base` operand order (the t-reg ring position of the loads). The flags row's first
  term stays base-first as the array form `lists[0]->items[curItem[0]]->flags`. The outputs are
  plain `*out[k] = PICK(s)->id` (the old `(s32 *)` casts were spurious).
- **SelectWin_display_00006394:** the four sprite-width reads are `((RaceSprite *)x)->image` /
  `RaceSpriteImage.width`; its local FW define is gone (no FW use is left in b5.c; the other
  `#ifndef FW` defines are dead too).
- **SelBoard_display / SelCourseMap_display (AC20 / B368 NCC donors):** they include
  game/camera.h; import_80087DA8 is the active CamWindow *, so the transposed matrix is
  `(*(CamWindow **)&import_80087DA8)->cam->view` (game_uso_ncc_BB8C.cpp's Glob view has the same
  0x70 camera slot).
- **SelectWin_charCheatIndex_00008C44:** `SETTINGS(options)->seqStep` and `newMark[0..2]` (b5.c
  includes gdl/backup.h), `SELITEM(curItem())->id`.
- **SelItemParms_ctor / SelItemInfo_ctor (rodata placeholders):** `*(volatile float *)arg0`, the
  `+ 0` dropped (12 of the census drop; the bodies are splice placeholders).
- gen_createScene's B site was already gone (not on the run-569 port-audit list).
- **Census / port-audit:** owner c raw sites 202 -> 138 (timproc_uso_b5.c 60 + 9 accessor uses ->
  35 + 5, game_libs_post.c 95 -> 63; SelectWin_display 8 -> 0). port-audit `--owner c` 21 -> 10
  (A 4 -> 3, B 6 -> 5, C 1, D 10 -> 1). Audio details in 1080_AUDIO.md run 569.

Next:
- b5: SelectWin_setCamToItem_00003A28 (6), SelectWin_update_00005FC0 (6, o2 donor: the five RoData
  float reads), SelItemsMgr_ctor (5, _8FC8), SelectionMgr_canCommit_00001D1C (4),
  DispItems_display_0000E5D8 / gen_createScene_00008DB4 (3 each).
- Remaining port-audit c sites: snd_SoundObjUpdate (2 B) / snd_SoundObjUpdateChannel (2 A: the
  load-bearing u32 table bases), sys_fatalSwapBuffer_00034180 (D), snd_CueQueueSet (B).

### Run 564 (agent-c): canScroll item walks, RaceSprite stat bars, vtable walks, match_imports

4b447e239 on agent-c (base 04a1501e8; hand edit, no renames; gate PASS 3288/3288, ROM identical,
the three source checks 0 mismatches). All 420 b5 / game_libs_post / match_imports objects,
matching and NON_MATCHING, identical to the pre-run build by `objdump -d -r`, `-r` and `-s`.
- **SelectWin_canScrollPrev / Next:** `itemsMgr->lists[stage]` and `items[i]->enabled`
  (Prev keeps its shifted cursor: `((SelItemList *)cursor)->items[0]`). The array-index forms
  give the same `addu base, scaled` operand order as the old flat arithmetic.
- **SelItem_drawStatBar / drawStatBarRight:** b5.c includes gdl/race.h (not edited) for
  RaceSprite / RaceSpriteImage: `dp = (char *)((RaceSprite *)obj)->image; dw =
  ((RaceSpriteImage *)dp)->width`. The objB blocks hold the image in dw and the width in dp;
  swapping the two locals swaps v0 / v1, so they keep `dw = *(int *)&((RaceSprite *)objB)->image`.
- **Vtable walks:** CommonInfo_loadData (VT_SLOT(vt, 10) = SelItemsMgr_loadInfo, the mgr as
  `delta + (char *)p1`), SelItemsMgr_loadData / loadInfo (VT_SLOT 8 / 11 on lists[i]),
  SelItemList_loadData / loadInfo (SELVT base[8] / loadInfo on items[i]); NODE(v1)->vptr.
- **match_imports BoardList_createItem:** NODE vptr / name / parent / unk04, GEOMMODE() =
  SelPolyGeomMode.geomMode for the seven d550 aliases. The multi-statement lines must stay on one
  line each: splitting them moved three loads / stores in the schedule ("native linked body
  changed"; IDO's scheduling follows source line numbers).
- **match_imports CourseItem_drawLabel_0000C98C:** SELITEM / SELWIN_VIEW members (the
  C98CObject / C98CContext views left the context header), INPUT_MGR(import_80020098).backup /
  nextFlowMode (game/input.h included by the .c). jny keeps `(unsigned int)`: the old field
  was u32 and the signed add swaps t1 / t2. The b5.c NM body got the same INPUT_MGR reads.
- **Census / port-audit:** see 1080_AUDIO.md run 564 (owner c 267 -> 202; D 36 -> 10).

Next:
- SelectWin_commitSelection (2 D, the E6C00 macro: its operand orders are levers),
  gen_createScene (B), SelBoard_display / SelCourseMap_display (D: import_80087DA8 + 0x70).
- SelectWin_display (8 raw sites).

### Run 561 (agent-c): plain Node stores, typed sprite / colour parameters, SelectWin_update members

897eb38ee + 7f07b45df on agent-c (base 75a598f4d; hand edits, no renames; gate PASS 3288/3288 before
each commit, ROM identical, the three source checks 0 mismatches). Every timproc_uso_b5 /
game_libs_post / match_imports object (420 dumps), matching and NON_MATCHING, is identical to the
pre-run build by `objdump -d -r`, `-r` and `-s` (.mdebug excluded).
- **Node stores (897eb38ee):** Node.vptr / name are `char *` / `const char *` on main, so the 54
  `*(char **)&NODE(p)->vptr|name = ...` stores and one read in b5 (b5.c 23, _4118 2, _8FC8 18,
  _D884 6, _DF14 6) are plain `NODE(p)->vptr = (char *)&sym`. No lever: the bytes are the same.
- **Sprite colour call:** import_0024E608 is prototyped `(void *ctx, s32 alpha, f32 *rgba)` (the
  shape of gui_setColor_00001A5C, which SelItem_drawSpriteColor calls). SelectWin_display passes
  the nine `parms.cc[k].rgba` / cc9 / c11 / c12 arrays directly.
- **SelItem draw helpers typed:** drawStatBar (3A4C) / drawStatBarRight (3C8C) are
  `(char *item, x, y, char *sprite, count, f32 *col, f32 *col2, char *win)`; drawSpriteColor
  (4068) is `(char *item, x, y, f32 *rgba, char *sprite, alpha)`. BoardItem_drawStats (C310 donor;
  ptrs[] / q are now `f32 *`), LevelItem_drawStats (CEB4), the CharacterItem_drawStats NM body and
  its match_import (plus context_timproc_uso_b5.h) pass pointers. The sprite records are the gui_uso
  0x18-byte sprite slot (image at +0x10, its s16 width at +0x20: race.h RaceSprite has the same
  layout); they stay `char *` here.
- **CommonInfo_init:** `WORLDREG(INPUT_MGR(D_00000000).game)` for the three GameFlow +0x134 reads
  (the gameflow-import check counts them: shared tokens 109 -> 112, 0 mismatches).
- **SelectWin_update_00005FC0 (o2 donor):** NODE(v)->vptr for the five item vptr reads,
  `*(int *)&SELWIN(arg0)->fade` for the setAlpha argument, `*(f32 *)&SELWIN(arg0)->transition` /
  `->fade` inside the fsin operands (the byte lever keeps run 490's lwc1 order), camPos, and the
  item's `parms.cf2` / `cfv` through `*(f32 *)&SELITEM(sp2C)->...`. Checked by .o comparison (the
  donor .o and the spliced b5.c.o): identical. FW is gone; only the five RoData float reads
  (`&D_00000000 + 0x1BC..0x1CC`) stay raw.
- **Census:** owner c raw sites 299 -> 267 (timproc_uso_b5 segment 116 + 26 -> 109 + 16; game_libs_post.c 142 -> 127; _o2_5FC0 7 + 10 -> off the per-file list). port-audit `--owner c` A 20 -> 4, B 10, C 10 -> 7, D 36 (76 -> 57): SelectWin_display 9 -> 0, BoardItem_drawStats 4 -> 0, LevelItem_drawStats 3 -> 0, CommonInfo_init 3 -> 0.

Next:
- SelectWin_canScrollPrev / Next (the item-list walk through itemsMgr->lists[stage] + 0x3C +
  0x2A4, pattern C), SelItem_drawStatBarRight (3 D: the sprite's image `*(char **)(arg3 + 0x10)`;
  a shared gui sprite-slot type in a header both b5 and the race overlays can include would clear
  these and RaceSprite's twin).
- CommonInfo_loadData / SelItemsMgr_loadData / loadInfo / SelItemList_loadData / loadInfo (2 D each:
  the vtable walks).
- match_imports BoardList_createItem, CourseItem_drawLabel_0000C98C.

### Run 554 (agent-c): typed SelParm vptrs, RoomModifier, SelCommonInfo, gPolyGeomMode words, eventFlags

18176448e on agent-c (base e10de4848; hand edit; gate PASS 3288/3288, ROM identical, the three
source checks 0 mismatches). Every b5 / game_libs_post / match_imports object (397 dumps), matching
and NON_MATCHING, is identical to the pre-run build by `objdump -d -r`, `-r` and `-s` (.mdebug
excluded).
- **select.h vptrs are `void *`:** SelParmI / F / V3 / RGBA, SelItemParms, SelItemInfo and
  SelectWinParms. The 90 `vptr = (s32)((char *)&sym + K)` stores drop the int cast: 32 in
  SelectWin_ctor (_4118), 32 in its b5.c NM copy, 15 in SelItemParms_ctor (2B74) and 11 in
  SelItemInfo_ctor (32C8). (The commit message says 58; 90 is the right count.) No
  lever needed; the .cpp donors take the pointer store as is.
- **Node vptr / name stores** (Course / LevelList_createItem, GenCourse / GenSelectChar /
  SelectionMgr / RoomModifier ctors, gen_createCamera, GenItemType_create, SelectWin_ctor) are
  `*(char **)&NODE(p)->vptr = &sym`. That form compiles under both the old s32 and main's new
  `char *` Node.vptr (0b77ceb96); after the merge it can become `NODE(p)->vptr = (char *)&sym`.
- **RoomModifier** (select.h, 0x40): showItems 0x2C (1 from the ctor; 0 = display hides both
  windows' DispItems), unk30, pass 0x34 (update: 0, display: ++), wins[2] 0x38 (SelectionMgr_ctor
  stores its windows there; `RMOD(room->modifier)->wins[k]`). The ctor, update and the NM
  RoomModifier_display body are on the members: display reads `SELWIN(w)->owner->shownMask` and
  `NODE(SELWIN(w)->itemsMgr->dispItems)->doFlags`. The NM body's `((R1 *)b)[k][14]` IXA spelling
  is not needed: `RMOD(b)->wins[k]` gives the same NON_MATCHING bytes.
- **_8FC8:** SelCommonInfo (0x30, +0x2C = the owning SelItemsMgr) and SelPolyGeomMode (bootup
  gPolyGeomMode's two words: mode0, geomMode). The b5 aliases gPolyGeomMode_3EEC8_8005EE6C,
  f8fc8_ee6c_sb1..3 / _r3, import_80063D04 / 800664C4 are typed SelPolyGeomMode, so the flag chain
  is `alias.geomMode`. 18 -> 5 accessor uses. The 5 left are RoData float reads through the
  import aliases (`FF(&import_80807FB8, 0x23C)` and so on). A DF_ extern changes the reloc symbol
  in the .o, so they stay.
- **SelectionMgr_finish:** `wins[i]` and
  `SELWIN(r)->itemsMgr->lists[2]->items[SELWIN(r)->curItem[2]]->id` (the chosen course's id goes
  to snd_sendEvent 7). The comment's "base-first text" lever was not needed.
- **gen_createCamera:** MNode mflags / mtx, Window flags (|= 6: the Z and colour clears) and
  clearColour[0..3], and `*(int *)&INPUT_MGR(import_8001EA70).game`.
- **eventFlags:** all 14 raw `FW(w, 0x4D4)` / `*(int *)(scr + 0x4D4)` reads in the state functions
  are `*(int *)&SELWIN(w)->eventFlags`. The plain member still differs in state0 / 3 / 4 / 6 / 7 /
  8 / 9, so the select.h note now names the lever.
- **Census:** timproc_uso_b5 segment 140 raw + 61 accessor -> 116 + 26; timproc_uso_b5.c
  117 + 31 -> 93 + 9; _8FC8 0 + 18 -> 0 + 5. Owner c 375 -> 299 (with the audio commit).
  port-audit `--owner c`: SelectWin_ctor 34 -> 0, SelItemParms_ctor 15 -> 0, SelItemInfo_ctor
  11 -> 0, SelectionMgr_finish 6 -> 0, Course / LevelList_createItem 6 -> 0, SelectionMgr_ctor
  5 -> 0, GenCourse / GenSelectChar_ctor 4 -> 0.

Next (H1):
- port-audit `--owner c`: SelectWin_display (9 A: the `(int)&parms.cc[k].rgba` call arguments;
  type the callee parameters), BoardItem_drawStats (C310) / LevelItem_drawStats (CEB4) sprite
  arguments, CommonInfo_init (the GameFlow +0x134 reads), SelItem_drawStatBar(Right) +0x10.
- match_imports BoardList_createItem (raw +0x28 / +0xC Node stores) and
  CourseItem_drawLabel_0000C98C.
- SelectWin_update_00005FC0 (o2_5FC0, 17), SelectWin_canScrollPrev / Next.
