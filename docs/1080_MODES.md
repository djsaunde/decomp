# 1080 Snowboarding: mode / process USOs (area H)

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
  the `TimRace_*` role names into confirmed overrides.
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
