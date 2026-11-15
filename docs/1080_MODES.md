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
