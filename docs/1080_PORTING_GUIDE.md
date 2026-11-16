# 1080 Snowboarding: porting and reading guide (start here)

> agent-h run 487, 2026-11-15, written against 1080 main 9dcd5ce48. This is the entry point for anyone who
> wants to understand the decompiled game or port it off the N64. It ties the area docs together; the
> details live in those docs and are linked from every section. Function and type names are the current
> repo names (checked against `src/` and `include/` on main). Older names in the area docs are mapped by
> `renames.tsv` in the 1080 repo (old name, tab, new name).
> Addresses: game_libs offsets are splat offsets (`nm build/tenshoe.elf` value; bootup.uso Text offset =
> game_libs offset + 0x1466C); other USOs use their segment offset (USO VRAM 0); the kernel uses its link
> address (it runs at link + 0x400, USO_FORMAT.md section 1).

## Index
- [0. The area docs](#0-the-area-docs)
- [1. ROM and module architecture](#1-rom-and-module-architecture)
- [2. Boot and the frame loop, end to end](#2-boot-and-the-frame-loop-end-to-end)
- [3. Where is X](#3-where-is-x)
- [4. Data formats a port must load](#4-data-formats-a-port-must-load)
- [5. N64-specific pieces a port must replace](#5-n64-specific-pieces-a-port-must-replace)
- [6. Conventions and matching caveats](#6-conventions-and-matching-caveats)
- [7. Open questions (all areas)](#7-open-questions-all-areas)
- [8. 64-bit port readiness: pointer / int casts (scripts/port-audit.py)](#8-64-bit-port-readiness-pointer--int-casts-scriptsport-auditpy)

## 0. The area docs

| doc | covers |
|---|---|
| docs/USO_FORMAT.md | the USO module format, the ROM filesystem, the kernel loader, kernel/rmon names, the `k_` rule |
| docs/1080_SYSTEM_LAYER.md | game_libs 0x0-0xEBC8 (HUD gadgets, SRAM save, mode glue), the libgdl system layer (heap, files, DMA, HostIO, App loop), RaceProcess base, named data objects |
| docs/1080_ENGINE_CORE.md | game_libs post0b 0x4C000-0x62F08 + post1b: RcpMgr, shapes, materials, heap, math, console, AnimPlayer, DNode, pad / boot, skin |
| docs/1080_GRAPHICS.md | the render pipeline for a port author: frame flow, GfxLib global, DL building, windows, microcode, texture / material / shape formats, animation and skin formats |
| docs/1080_PHYSICS.md | one rider per frame: orientation, edge grip, ground contacts, DNode integration, AI steering |
| docs/1080_CAMERA.md | the race camera: chase components, scripted course camera, CamDirector |
| docs/1080_COURSE.md | courses: world registry, course descriptor stream, items, markers (AI path), gates, props |
| docs/1080_AUDIO.md | the OoT-family audio driver (game_libs 0x1C9E4-0x2D374) and 1080's sound glue |
| docs/1080_MODES.md | the mode / process USOs (title, h2h, arcade, match race, time attack, trick, select screens, gui) |
| docs/1080_GAME_CLASSES.md | bootup_uso and game_uso C++ classes: SnowBoarder, GAME_MODE setups, replay, SnowAI, RiderAnim, cross-USO imports |
| docs/READABILITY_PLAN.md | the readability phase itself: inventory, naming rules, the rename tool, the gate, the struct path, USO section-base accesses |

Matching (not porting) knowledge is in docs/IDO_CODEGEN.md, docs/PATTERNS.md, docs/MATCHING_WORKFLOW.md and
docs/N64_FORENSICS.md.

## 1. ROM and module architecture

1080 is a small kernel plus about 60 relocatable modules (**USOs**, "Universal Shared Objects": a custom
relocatable object format, some Yay0-compressed) loaded from a ROM filesystem. The engine is Giles Goddard's
**libgdl**, written in C++ (Cfront-style; compiled with IDO 7.1 NCC, a few functions with MIPSpro 7.2.1) with
C libraries linked in.

```
ROM
 0x1000    kernel (0x80000000)  libultra core, USO loader + ROM filesystem, Yay0 decoder, rmon debugger
 0xB7C0    device "rom"         every other .uso and every data file (rom/*.bin)
 0xD9FDB0  device "mainuso"     bootup.uso, loaded once at 0x8001FFA0 and never unloaded
              Text 0x0-0x1464C       = splat segment bootup_uso  (libgdl app layer, the game classes)
              Text 0x1464C-0x89910   = splat segment game_libs   (libgdl engine + libultra + libc + audio)
```

| module (splat segment) | what it is | doc |
|---|---|---|
| kernel | entry, USO loader (`uso_load`, `uso_relocate`, `uso_bindImports`), ROM fs (`fs_openDevice`, `fs_read`, `fs_romRead`), `uso_decodeYay0`, libultra threads / messages / exceptions / PI / TLB / Leo, rmon | USO_FORMAT.md |
| game_libs (part of bootup.uso) | libgdl **system layer** (heap `Mem_*` / `mem_new`, files `fs_gdl*`, DMA `dma_*`, HostIO, `App_*` / `app_run`), libgdl **engine core** (Node graph, GfxLib + RcpMgr, shapes, materials, lights, math, collision, DNode dynamics, AnimPlayer, skin), the race base (`RaceProcess_*`, `RaceTracker_*`, HUD gadgets), SRAM save (`Backup_*`), pad thread (`pad_*`), the **audio driver** + sound glue (`Audio*`, `snd_*`), a statically linked libultra (`gl_` copies) / libc / gu | SYSTEM_LAYER, ENGINE_CORE, GRAPHICS, AUDIO |
| bootup_uso (part of bootup.uso) | the game classes: `SnowBoard` (the App), `GameFlow`, `Process`, `SnowBoarder` (the rider), `game_init` / `game_setupMode` / `game_createMap` (race scene), `cam_create`, `CamDirector`, `WorldRegistry`, items, `MapProp`, `EnvSettings`, InputMgr / replay, `PauseMenu`, `Fader` | GAME_CLASSES, PHYSICS, CAMERA, COURSE |
| game_uso (game.uso, Yay0) | race-scene classes loaded with a race: `SnowAI` (CPU riders), `RiderAnim` (rider animation state machine), the chase cameras and the scripted `CourseCam`, `CourseMarker`, `Sun` / `LensFlare` | GAME_CLASSES 7-16, PHYSICS 8, CAMERA |
| titproc, n64proc, h2hproc, arcproc, mgrproc, eddproc | one **mode process** each: title + demos, N64 logo, 2P versus, arcade, match race (+ credits), editors (an empty stub in retail) | MODES H2 |
| timproc_uso_b1 / b3 / b5 | timproc.uso (time attack), trkproc.uso (trick attack), **genproc.uso** (the select screens) | MODES H1 |
| gui_uso (gui.uso) | the shared 2D layer: fonts, sprites, fills, scissor | MODES H2 |
| boarder1-5_uso | per-rider data modules (6 tiny reader functions each) | MODES H2 |
| map4_data_uso_b2 | the code part of one course-data USO (3 tiny functions) | COURSE 1 |
| data-only USOs (no splat code) | `mapN_data.uso` (course shape + collision), `bgNtex.uso` (sky / wall textures), the nine character USOs, audio bank / seq / wave, `gamegfx`, `charsel` / `charsps` / `charfir` / `charmap`, `viewrec` (replay viewer), `nameent` (name entry), `trnproc` (training) and effect USOs | MODES "Which module is which", COURSE 1 |

Module ids (the import `info >> 4` field): 0 bootup, 1-3 audio, 4-12 characters, 13-17 boarder1-5, 18 gui,
19 n64proc, 20 titproc, 21 eddproc, 22 mgrproc, 23 arcproc, 24 h2hproc, 25 timproc, 26 trkproc, 27 trnproc,
28 genproc, 29 gamegfx, 30-31 charsel / charsps, 32 viewrec, 33 nameent, 34-35 charfir / charmap,
36-45 map1-10_data, 46 game (1080_MODES.md H1).

**Linking between modules** is by Sym index, not by name: an import names the exporting module and that
module's Sym entry (GAME_CLASSES section 8). The decomp links every USO at VRAM 0, so cross-module calls are
written as calls to the `gl_func_00000000` / `func_00000000` placeholder and data as `&D_00000000 + K`
(section 6). Symbol names never reach the ROM (READABILITY_PLAN section 6).

**Flow modes and their USOs** (bootup Data 0xC450 / 0xC4EC, read by `GameFlow_startMode`): 0 N64DEMO
n64proc, 1 TITLEDEMO titproc, 2 HEAD2HEAD h2hproc, 3 MULTIGAMERACE mgrproc, 4 TIMEATTACK timproc,
5 ARCADEMODE arcproc, 6 TRICKMODE trkproc, 7 TRAINING trnproc, 8 EDITORS eddproc; helpers genproc, nameent,
gamegfx, charsel (+ charsps / charfir / charmap).

## 2. Boot and the frame loop, end to end

### 2.1 Boot

1. **Kernel** `kernel_entrypoint` / `kernel_boot` (0x80000000 / 0x80000060): clear BSS, set sp, `uso_init`,
   `fs_setDeviceTable`, `uso_scanRom`, `uso_load` the boot module (bootup.uso from "mainuso"), then
   `uso_callEntry` (USO_FORMAT.md sections 9-10).
2. **bootup.uso entry**: `boot_entry_00066C30` stores its argument and calls the boot routine;
   `boot_main_00066850` sets up the threads (`boot_startThread_*`, stack checks `boot_checkStacks_00066AF0`),
   the pad thread (`pad_init_00066C74`, `pad_threadLoop_00066EEC`) and the App object. The App subclass is
   **SnowBoard** (`SnowBoard_ctor`: audio USO file info, `snd_Init`).
3. **App start** `App_main` (0x415A4): heap stats, SysLib / GfxLib at 320x240 (`GfxLib_init`: frame
   buffers, "MainStatic" heap and display list, RcpMgr), then the App's InitInstance slot:
   `SnowBoard_InitInstance` reads rom/version.bin and rom/anims.bin, builds **GameFlow** (the object the mode modules import as the InputMgr, bootup Bss 0xF8; `GameFlow_create`:
   gui.uso, flowimgs.bin) and enters the first flow mode with `GameFlow_startMode`.
4. `app_run` (0x34EB4) never returns.

### 2.2 One frame

```
app_run (game_libs 0x34EB4, NCC donor game_libs_ncc_34EB4.cpp)             "RunApp"
 | (perf labels "gfx.Start", "app.Update", "app.Display", "gfx.End", "SndCPU")
 |-- gfx_start                      reset per-frame DLContexts                         GRAPHICS 1
 |-- App_Update  -> Node tree update (Node vtable slot 3, Node_update recursion)
 |     |-- the current mode Process (bootup Process, vtbl Data 0xC3A0)
 |     |     Process_update: slot 12 handleInput while not fading, Node_update children,
 |     |     slot 11 once the fade is done (next process / GameFlow_restart_000116C8)       MODES H2
 |     |     race modes: RaceProcess (game_libs, 38-slot vtable) on top of Process:
 |     |       RaceProcess_handleInput -> phase machine (intro, 3-2-1, racing, end, over),
 |     |       updateSub0-3 by view mode, the <mode>_DataManager_update HUD feed,
 |     |       RaceTracker_update (timer, progress, gates, gadgets)                 SYSTEM_LAYER 10-11
 |     |-- scene nodes created by game_init / game_setupMode (World Registry roots og / fg / bg / eg)
 |     |     SnowBoarder_update (bootup 0xD440, slot 3), per rider:                     PHYSICS 2
 |     |       "SnowBai"   AI: SnowAI_update (game.uso) writes the rider's RiderInput
 |     |                   (pad riders: the InputMgr pad, read by the pad thread)        PHYSICS 8
 |     |       "SnowBDyn"  SnowBoarder_updateDyn: friction / grip, SnowBoarder_limitSpeed,
 |     |                   SnowBoarder_updateOrient, SnowBoarder_procColl ("SnowBCol":
 |     |                   CollShape_nearestHit + DNode_solveContacts), DNode_applyAccums_00065448,
 |     |                   DNode_integrate_00064DEC, DNode_resetAccums_00065148              PHYSICS 3-6
 |     |       "SnowBAnm"  RiderAnim_update_0000D204 (game.uso) -> AnimPlayer advance / applyPose
 |     |                   -> anim_blendPose per Animator                              GRAPHICS 11
 |     |       "SnowBChild", then fwdSpeed, shake, snd_updatePlayer (rider sound)
 |     |-- cameras: chase components (SnowChaseActorCam / SnowChaseActorLook update), the
 |     |     CourseCam path player (cam_updateView_00000B3C), CamDirector_update,
 |     |     MCamera_updateLookAt (view matrix)                                       CAMERA 2-7
 |     |-- AnimDataMgr / SkinMgr_update (skinned meshes), MorphPoly updates           GRAPHICS 11-12
 |-- App_Display -> Node tree display (slot 2): per ScreenWindow                    GRAPHICS 1, 4
 |     ScreenWindow_display -> Window_display: lights, projection (Window_setupView), modelview;
 |     children's display(): MNode / QNode matrices, PolyShape_display / Sprite / MorphPoly emit F3DEX Gfx;
 |     Process_display: gui_beginFrame_000016A4 + the mode's drawGui (2D HUD / menus through gui.uso)
 |-- gfx_end -> gfx_submitFrame_0004CDB0 -> gfx_queueGfxTask_0004CEFC -> RcpMgr_initTask (F3DEX 1.23) + RcpMgr_queueTask
 |           -> gfx_swapBuffer (osViSwapBuffer, gfx_waitRetrace)
 |-- the App's one-shot callback (+0x30), frame counter++
RcpMgr thread  RcpMgr_service / RcpMgr_startTask: osSpTaskLoad / StartGo; gfx tasks yield to audio ("SndRSP")
Audio          the audio thread (AudioThread_Update, OoT thread.c) builds the synthesis task
               (AudioSynth_*), queued on the same RcpMgr; game code talks to it only through
               audio-thread command words (snd_* glue, AudioThread_QueueCmd*)               AUDIO
Pad thread     pad_threadLoop_00066EEC: osContStartReadData / osContGetReadData, rumble (osMotorStart / Stop),
               record / playback (pad_startRecord_000679BC / pad_startPlay_00067A10)      ENGINE_CORE 2
```

Notes for a port:
- There is **no dt** anywhere: physics, cameras and animation advance one fixed step per `app_run`
  iteration. The retail game runs this at the VI rate it achieves (gfx_waitRetrace), so a port should run
  the update at a fixed rate and decouple rendering.
- The Node graph is the scheduler. `Node` (include/gdl/node.h, 0x2C) has name +0xC, children +0x10, parent
  +0x14, display mask +0x20, Cfront vptr +0x28. Slots: 0 hostioParms, 1 updateChildren, 2 display,
  3 update, 4 handleMsg, 5 broadcastMsg, 6 doCommand, 7 saveData, 8 loadData; 10+ class-specific
  (ENGINE_CORE section 1). Node flag 0x8 (+0x18) enables update (`Process_start` sets 0x4 | 0x8); `Node_display` draws a child only
  if `child+0x20 & Node_getDisplayMask()` (SYSTEM_LAYER section 12).
- Within one rider the order is fixed (AI, dynamics, anim, child); across nodes it is tree order.

### 2.3 Mode flow (outside the race)

Each mode USO exports one entry object whose slot is `<pfx>_procMain(app, state)`, a state machine over the
InputMgr word +0x40 (bootup Bss 0xF8, include/game/input.h). States create a Process subclass and run it with
`app_runProcess` (game_libs 0x93DC) or launch helper USOs: `app_launchGenProc` (genproc select screens),
`app_launchNameEnt`, `app_launchViewRec` (replay viewer). A race is built by `game_init` with a GAME_MODE
value (`game_setupSolo`, `game_setupVsGhost`, `game_setupReplay`, `game_setupVsCpu`, `game_setupVs2P`,
`game_setupDemoSolo`, `game_setupDemoRace`, `game_setupDemoSplit`; GAME_CLASSES section 6), then
`game_createMap` builds the course scene (COURSE section 4). The title menu writes the next flow mode
(InputMgr +0x34) and fades out; `Process_exit` hands control back to GameFlow. MODES H2 lists every
module's states.

## 3. Where is X

| subsystem | files | headers | key functions | doc |
|---|---|---|---|---|
| USO loader, ROM fs | src/kernel/kernel_000*.c, kernel_026.c | include/uso.h (`UsoModuleSlot`) | `uso_load`, `uso_unload`, `uso_loadSections`, `uso_relocate`, `uso_bindImports`, `uso_callEntry`, `uso_decodeYay0`, `fs_openDevice`, `fs_read`, `fs_romRead` | USO_FORMAT |
| kernel libultra / rmon | src/kernel, src/o1, src/libultra | include/libultra/*.h | `osCreateThread`, `osSendMesg`, `__osSetFpcCsr`, `k___ull_div` | USO_FORMAT 12 |
| boot, threads | game_libs_post1b.c | | `boot_main_00066850`, `boot_entry_00066C30`, `boot_startThread_00066B64` | ENGINE_CORE 2 |
| App / main loop | game_libs_post0b.c, game_libs_ncc_34EB4.cpp, game_libs_ncc_41D40.cpp | include/gdl/node.h (`App`) | `App_main`, `app_run`, `App_Update`, `App_Display`, `app_runProcess`, `app_loadUso` | SYSTEM_LAYER 7, 12 |
| game app, flow | src/bootup_uso (bootup_uso_tail3a_10C8C.c, o0_*) | include/game/input.h: the InputMgr **is** the GameFlow object (GameFlow_create fills it; `GAMEFLOW(p)`: procUsoPath 0x2C, flowProc 0x30, flowMode 0x38, ctrls[2] 0xC0, usoList 0x130, seq 0x13C, flowImgs 0x150, unlocks 0x154; run 505) | `SnowBoard_ctor`, `SnowBoard_InitInstance`, `GameFlow_create`, `GameFlow_startMode`, `Process_update`, `Process_exit` | GAME_CLASSES 3, 6; SYSTEM_LAYER 12 |
| heap / memory | game_libs_post0b.c | include/gdl/mem.h | `Mem_init`, `Mem_allocLow`, `Mem_free`, `mem_new`, `heap_new`, `heap_tempAlloc`, `MemTracker_*` | ENGINE_CORE 2-3 |
| files, DMA, HostIO | game_libs_post.c, post0b.c | include/gdl/dma.h | `fs_gdlOpenFile`, `fs_gdlReadFile`, `fs_gdlReadFileAsync`, `dma_read`, `dma_readAsync`, `hostio_dispatch` | SYSTEM_LAYER 7 |
| Node graph | post0b.c | include/gdl/node.h | `Node_ctor`, `Node_update`, `Node_display`, `MNode_update`, `QNode_display`, `nodelist_dispatch` | ENGINE_CORE 1-2 |
| graphics | post0b.c 0x41F90-0x5A9D0, game_libs_ncc_*.cpp | include/gdl/{dlctx,rcp,window,polyshape,material,light,sprite}.h, gl_data.h (`gGfxLib`) | `GfxLib_init`, `gfx_start`, `gfx_end`, `ScreenWindow_display`, `Window_display`, `gfx_loadTexture`, `PolyShape_display`, `RcpMgr_service` | GRAPHICS |
| math | post0b.c 0x5BBEC-0x5FD20 | | `math_quatRotateAxisAngle`, `math_quatSlerp`, `math_mtxAddTranslation` | ENGINE_CORE 2 |
| collision | post0b.c 0x39EE4-0x3CF94 (`coll_*`) | | `CollShape_ctorPoly`, `CollShape_nearestHit`, `CollObjMgr_ctor` | SYSTEM_LAYER 7-8, PHYSICS 5 |
| dynamics | game_libs_post1b.c | include/game/snowboarder.h (`SnowBAccum`, `SnowBDNodeParms`) | `DNode_ctor`, `DNode_update`, `DNode_solveContacts`, `DNode_integrate_00064DEC` | PHYSICS 6 |
| animation, skin | post0b.c / post1b.c 0x61E58-0x69C94 | include/gdl/anim.h, skin.h | `AnimDataMgr_loadFile`, `AnimPlayer_start`, `anim_blendPose`, `SkinMgr_update` | GRAPHICS 11-12 |
| rider | bootup_uso.c, bootup_uso_ncc_{90CC_nm,B75C,C234,8BD4}.cpp | include/game/snowboarder.h (`SNOWB(p)`), envobj.h (`SnowBCollider`) | `SnowBoarder_ctor`, `SnowBoarder_update`, `SnowBoarder_updateDyn`, `SnowBoarder_updateOrient`, `SnowBoarder_procColl`, `SnowBCollider_onContact` | PHYSICS |
| CPU riders | src/game_uso (game_uso.c, game_uso_ncc_57D8.cpp) | include/game/snowai.h | `SnowAI_ctor`, `SnowAI_steer`, `SnowAI_applyStickInput`, `SnowAI_scanSegments` | PHYSICS 8, COURSE 6 |
| rider animation | src/game_uso (game_uso_ncc_D204.cpp ...) | include/game/rideranim.h | `RiderAnim_update_0000D204`, `RiderAnim_selectAnim_0000D9CC` | GAME_CLASSES 10-11 |
| camera | bootup_uso_ncc_31C0.cpp, game_uso | include/game/camera.h | `cam_create`, `CamDirector_update`, `cam_updateView_00000B3C`, `SnowChaseActorCam_setMode_00002714` | CAMERA |
| course / world | bootup_uso_o2_6808.c, bootup_uso.c, game_uso | include/game/course.h, envobj.h (U64BGWall, EnvSettings clip range, Fog / Snow / Tv1 items, FallingSnow, ShpNode; `WorldRegistry` = the game_* scene object, InputMgr +0x134: roots, lights, `players[]`, `windows[]`; `WORLDREG(p)`) | `WorldRegistry_create_00001E08`, `game_createMap`, `item_registerTemplates`, `EnvSettings_load`, `CourseMarker_registerTemplates` | COURSE |
| race rules, HUD | game_libs.c, game_libs_tail.c | include/gdl/race.h, hud.h, gadget.h (`PointsPopup`, the score pop-up, `POPUP(p)`) | `RaceProcess_init`, `RaceProcess_handleInput`, `RaceTracker_update`, `RaceTracker_findGates`, `hud_addCourseGadget` | SYSTEM_LAYER 3, 10-11; MODES run 469 |
| input, replay | bootup_uso o0_11C70.c / o0_1207C.c / ncc_11E00.cpp, game_libs_post1b.c (pad_*) | include/game/input.h (InputMgr = GameFlow: gameMode +0x3C, game +0x134, locked +0x18C, initials +0x158; input_initDefaults_00012188 sets the selection defaults) | `input_checkPressed_00011E00`, `replay_addInput`, `replay_beginPlayback`, `pad_threadLoop_00066EEC` | GAME_CLASSES 6, MODES run 466 / 484 |
| save | game_libs.c 0x97B4-0xC46C | include/gdl/backup.h | `Backup_ctor`, `Backup_openSession`, `Backup_writeCourse`, `backup_checksum` | SYSTEM_LAYER 4, MODES run 474 / 478 |
| audio | game_libs_post.c, game_libs_o2_*.c | include/audio.h | `AudioSynth_ProcessNote`, `AudioLoad_RelocateFontAndPreloadSamples`, `AudioThread_Update`, `snd_Init`, `snd_updatePlayer` | AUDIO |
| modes | src/{tit,arc,mgr,h2h,edd,n64}proc_uso, timproc_uso_b1 / b3 | include/game/modeproc.h (ArcRace / MgrRace / H2HRace, Arc / Mgr / H2HDataManager, TitleDemoProcess / GameDemoProcess), race.h (TimRace, TimDataManager) | `tit_procMain`, `arc_procMain`, `TimRace_checkRecord`, `TimDataManager_update_00001BCC`, `GameDemoProcess`, ... | MODES |
| select screens | timproc_uso_b5 (genproc) | include/game/select.h | `SelectWin_init`, `SelectionMgr_ctor`, `GenSelectChar_ctor` | MODES H1, run 464 / 484 |
| 2D / gui | src/gui_uso | | `gui_drawString`, `gui_drawSprite`, `gui_fillRect` | MODES H2 |

## 4. Data formats a port must load

Everything on the cartridge is big-endian: byte-swap s16 / u16 / s32 / f32 on a little-endian host.
Pointers inside USO data are relocated by the loader (section 5); pointers inside shape assets are
already-relocated addresses of arrays in the same asset (GRAPHICS 7.1).

| data | where | format doc |
|---|---|---|
| ROM filesystem (devices "mainuso" / "rom", 0x9C-byte file entries) | kernel `uso_scanRom`, `uso_find_file` | USO_FORMAT 2, 5 |
| USO modules: records, sections, Sym entries, reloc entries, Yay0 | kernel loader | USO_FORMAT 3-9 |
| course descriptors (command stream SHAPE / ITEMS / MARKERS / START / GOAL / MAP / BG / SUN / ENV*) | bootup Data 0x67F0-0x6E30 | COURSE 3 |
| course list (ten courses: shape USO, bg USO, item / marker / env files) | `WorldRegistry_create_00001E08` | COURSE 2 |
| course shape + collision (`mapN_data.uso`, a PolyShape export) | `game_createMap`, `CollShape_ctorPoly` | GRAPHICS 7 / 7.1; collision grid: open (ENGINE_CORE, SYSTEM_LAYER 7) |
| shape command stream (verts, tris, normals, palette, materials) | `BasePolyShape_parse` (donor game_libs_o2_52CD4.c) | GRAPHICS 7.1 |
| material commands (GDL_MC) | `gfx_decodeMatCmd` (donor game_libs_o2_51AD8.c), `BasePolyShape_parseMats` | GRAPHICS 6.2 |
| textures (RGBA32 / RGBA16 / IA8 / I8 / I4 / CI8 + RGBA16 TLUT, image records) | `gfx_loadTexture` (donor game_libs_ncc_578B4.cpp) | GRAPHICS 6.1 |
| node command lists in shape files (ProcNodeList: SkinMgr / SkinShape / SkinAnim, LightTarget, ...) | `nodelist_dispatch` | ENGINE_CORE 2, GRAPHICS 12 |
| animations (rom/anims.bin: groups of anims, AnimKey tables, 14-byte node keys) | `AnimDataMgr_loadFile`, `anim_unpackKey` | GRAPHICS 11; anims.bin names: GAME_CLASSES 16 |
| skin weights (bone tables, SkinWeight {vert, percent}) | `skin_cmdSkinAnim`, `SkinMgr_init` | GRAPHICS 12 |
| items (rom/*_item.bin: per type parms + instances) | `ItemMgr_Load`, `ItemType_load` | COURSE 5 (binary layout open) |
| markers / AI path (rom/*_mark.bin) | marker manager, `CourseMarker_registerTemplates` | COURSE 6 |
| environment (rom/*_env.bin: fog, colours, "sun" record) | `EnvSettings_load` | COURSE 1, 9 |
| camera paths (rom/cam_info.bin: CamList / CamPath / CamKey) | `cam_ctor_00000858`, `cam_updateView_00000B3C` | CAMERA 2a |
| **parms files** (`.bin` read through the HostIO parm system: 3-char tags, then int / float / quad / Vec3; rom/cam_ca.bin, lookat_ca*.bin, flare5.bin, rider / AI / anim parms) | `Parms_load_00035C6C`, the `*_read{Int,Float,Quad,Vec3}Parm_*` slots, `<Class>_hostioParms` | ENGINE_CORE 1 ("Parm read / write slots"), SYSTEM_LAYER 7; parm lists: PHYSICS 1 (SnowBoarder::Parms), CAMERA 3-5, GAME_CLASSES 9-11 (SnowAI::Parms, RiderAnim) |
| save data (SRAM: header + course / arcade / options / ghost chunks, mirrors, checksums) | `Backup_ctor`, `fs_gdl*` kind 2 | SYSTEM_LAYER 4, include/gdl/backup.h |
| ghost / replay records | `replay_beginRecord1P`, `Backup_ghostSetHeader` | GAME_CLASSES 6, MODES run 484 |
| audio banks / sequences / samples (audio USOs 1-3) | `AudioLoad_*` | AUDIO (OoT driver formats, 8-layer SequenceChannel) |
| fonts / 2D sprites (gui.uso glyph atlas, sprite ids 0x5xxxx / 0x6xxxx) | `gui_fontCreate`, `gui_spriteLoad` | MODES H2 |

## 5. N64-specific pieces a port must replace

| N64 piece | where in 1080 | what it maps to in a port |
|---|---|---|
| RSP graphics microcode (F3DEX 1.23; F3DLP.Rej as the alternative) and the RDP | `RcpMgr_*`, `RcpTask_setUcodeF3DEX`, `gfx_queueGfxTask_0004CEFC` | an F3DEX 1.x display-list interpreter (Fast3D-style renderer), or hook the `gfx_emit*` emitters / `PolyShape_display` and draw the shapes directly. Fixed-point Mtx / Vp / perspNorm / s8 normals become floats (GRAPHICS 9) |
| RSP audio microcode (the synthesis task from `AudioSynth_*`) | audio thread + RcpMgr audio task, `osAiSetNextBuffer` | a CPU implementation of the ABI commands (as in OoT / MM PC ports), or replace the synthesizer and keep the sequence player; AI buffer -> host audio stream (AUDIO) |
| RSP/RDP task scheduling, yield | `RcpMgr_service`, `RcpMgr_startTask`, `gl_osSpTaskYielded` | plain sequential calls; no yielding needed |
| VI (video modes, swap, retrace) | `gfx_setVideoMode`, `gfx_swapBuffer` (`osViSwapBuffer`), `gfx_waitRetrace`, `gfx_viBlack` | window / swapchain present and vsync; keep a CPU-readable frame buffer for the debug text, splash and `Mat_fromFrameBuffer` render-to-texture (GRAPHICS 9) |
| PI DMA (ROM reads) | kernel `fs_romRead`; game_libs `dma_*` (10 DmaSlots, "Out of DMA slots"), `fs_gdlReadFileAsync`, `fs_piReadWord_00066210` | file reads from a ROM image or extracted files; async reads can complete immediately |
| SI (controllers) | pad thread `pad_threadLoop_00066EEC`, libultra `osContStartReadData` | host gamepad polling into the same pad state (InputMgr / RiderInput: stick x / y floats, held / pressed bits) |
| controller pak, rumble pak | `osPfsInitPak`, `pad_probePaks_00066D54`, `osMotorInit`, `osMotorStart` / `osMotorStop`, `pad_updateMotor_00067084` | host rumble; the controller pak path is probed but the save goes to SRAM |
| SRAM save | `Backup_*` -> `fs_gdl*` kind 2 ("SRAM read %x, %d from %x") | a save file holding the same 0x8000-byte image (keep the checksums or drop them) |
| USO relocation / dynamic loading | kernel `uso_load`, `uso_relocate`, `uso_bindImports`, `uso_unload` | link everything statically and replace module loads (`app_loadUso`, `game_loadUso`, `GameFlow_loadProcUso_000117FC`) with direct calls; data-only USOs become plain assets. Cross-module imports are already resolved by name in this repo where proven (GAME_CLASSES 8) |
| caches, physical addresses | `osVirtualToPhysical` in every G_DL / G_VTX word, `osWritebackDCache`, `dma_writebackCache` / `dma_invalCache` | no-ops |
| threads / messages | libultra `osCreateThread`, `osSendMesg` / `osRecvMesg` | host threads or a single-threaded loop (graphics, audio and pad are separate threads on the N64) |
| HostIO, rmon, fault thread | `hostio_*`, kernel rmon, `dbg_faultThread` | drop, or map HostIO parm groups to a debug UI |
| Yay0 | `uso_decodeYay0` | decompress at extraction time |

## 6. Conventions and matching caveats

**Names** (READABILITY_PLAN section 4; `renames.tsv` is the ledger).

| prefix / form | meaning |
|---|---|
| exact SDK names (`osSendMesg`, `guMtxF2L`, `memcpy`) | libultra / libc / gu; the kernel copy keeps the plain name |
| `gl_` + SDK name (`gl_osCreateMesgQueue`, `gl___osRunQueue`) | the duplicate libultra copy statically linked into game_libs |
| `k_` + SDK name (`k___ull_div`) | a kernel definition whose plain name is already a +0x400 runtime alias pin; call sites keep the plain name (USO_FORMAT 1, 12) |
| OoT names (`AudioSynth_*`, `AudioLoad_*`, `gAudioCtx`) | the audio driver |
| `<Class>_<method>` (`SnowBoarder_update`, `Mem_allocLow`, `RaceProcess_onPause`) | C++ classes from the debug strings, Cfront-style; `_ctor`, `_hostioParms`, `_vfnN_<addr>` for an unnamed virtual slot |
| `<subsys>_<verbObject>` (`gfx_loadTexture`, `fs_gdlReadFile`, `uso_load`) | C-style code; prefixes `uso_ fs_ heap_ mem_ dma_ gfx_ snd_ pad_ cam_ coll_ anim_ math_ gui_ replay_ game_ app_ boot_ dbg_ sys_` and the mode prefixes `tit_ arc_ mgr_ h2h_ tim_ trk_ edd_ n64_` |
| `..._<addr>` suffix | the kind is known but not the exact role (e.g. `DNode_integrate_00064DEC`); also used to keep names ROM-wide unique (`TimeGadget_ctor_00013D40`) |
| `g<Name>` / `s<Name>` / `D_<addr>` | global / TU-static / unidentified data; `<Class>_vtbl` for vtables (include/gdl/gl_data.h) |
| `gl_func_<addr>`, `func_<addr>`, `<seg>_func_<addr>` | not yet named (none left in game_libs) |
| `*_00000000*` (`gl_func_00000000`, `func_00000000`, `D_00000000`, `gl_func_00000000_send` ...) | **never renamed**: USO import / section-base placeholders |
| `CALL(Callee)(args)`, `FCALL(f)`, `GCALL(f)`, `XCALL(tok, f)` (include/uso_call.h) | a USO placeholder call with its real callee named: expands to exactly `gl_func_00000000` / `func_00000000` / `game_uso_func_00000000` / `tok`, so bytes cannot change; `scripts/name-placeholder-calls.py check` (gate step 5) verifies each name against the ROM TextReloc of that jal; rename-symbol.py rewrites `CALL(OLD)` with the callee |
| `GL_DATA(K)` / `GL_RODATA(K)` / `GL_BSS(K)` (include/gdl/gl_data.h) | a bootup.uso section-base site, = `(char *)&D_00000000 + K` |
| `GL_DATA_STR(K, "text")` / `GL_RODATA_STR(K, "text")` | the same site where K starts a string; the literal documents it (`check` compares it with the ROM bytes) and is discarded by the macro |
| `sStr_<words>_<K>`, `sFmt_<words>_<K>`, `sTag_<tag>_<K>` | content-named per-site aliases of a string at section offset K (plain text / printf format, specifiers dropped / gdl parm tag); content-named, so they do not follow function renames |
| `kRo_<Func>` / `kRo_<Func>_<K>` | RoData constant pool of function `<Func>` (gl_data.h macro, = GL_RODATA(first K)) / one constant of it (a per-site linker alias); follow `<Func>` on a rename (rename-symbol.py, run 517) |

**Why the source looks the way it does** (all of it is deliberate; READABILITY_PLAN section 9):
- **Raw offsets kept on purpose.** `*(T *)((char *)p + 0xNN)` (`FW(p, off)` macros) remain wherever a typed
  field changes the bytes: a different load width or signedness, a moved multiply in index arithmetic, a
  pointer walk becoming `p++`, a struct copy, or IDO picking registers differently (e.g. SelectWin
  `eventFlags`, MODES run 484). Each area doc lists what is still raw and why.
- **Cast macros on untyped pointers.** Where a body's `char *` / `int` parameter or local is itself a lever,
  fields are reached through a cast macro instead of retyping it: `NODE(p)` (gdl/node.h), `RACEPROC(p)`,
  `TIMRACE(p)`, `DATAMGR(p)`, `TIMDATAMGR(p)` (gdl/race.h), `ARCRACE / MGRRACE / H2HRACE(p)` and
  `ARCDATAMGR / MGRDATAMGR / H2HDATAMGR(p)`, `TITLEDEMO / GAMEDEMO(p)` (game/modeproc.h), `SNOWB(p)`
  (game/snowboarder.h), `WORLDREG(p)` (game/course.h), `POPUP(p)` (gdl/gadget.h), `ENVSET / FOGITEM / SNOWBCOL / SHPNODE(p)`
  (game/envobj.h). `NODE(c)->parent` / `->unk04` is the
  child-attach idiom every ctor inlines. A member access can still reorder loads (IDO orders a commutative
  operand pair differently for members than for raw derefs), so each conversion is checked object-identical.
- **USO section-base accesses** are written `&D_00000000 + K` (or `(char *)&gGfxLib + K`, an alias at the
  same address): the ROM bytes carry HI16 / LO16 relocations against the section base, so the base symbol
  and offset must stay. Named objects are aliases in include/gdl/gl_data.h; per-site aliases
  (`gGfxLib_2c94_ctx`, `D_76F0_fadeB`) keep a distinct symbol where IDO needs one (READABILITY_PLAN 9.1).
- **Cross-module calls** go through `gl_func_00000000(...)` (a `jal 0` with an import reloc). Most are
  written `CALL(Callee)(...)` (uso_call.h; 2927 named, 3032 raw left at run 517, census in READABILITY_PLAN
  section 0): the macro drops
  the name, so the callee is documentation verified against the ROM relocs, not a real symbol reference.
  The raw ones left (mostly bootup_uso and the mode USOs) are named in comments or the area docs.
- **Codegen levers** survive in matched bodies: `if (1) {}`, `volatile int pad`, `register` locals, comma
  expressions, odd declaration orders, distinct alias externs. The comments explain them; do not tidy them.
- **Donors.** Many functions are compiled in a separate TU (`*_ncc_*.cpp` C++, `*_mp72_*.cpp` MIPSpro,
  `*_o2_*.c` / `*_o1_*.c` / `*_ido53_*.c` other compilers or flags, src/match_imports/) and spliced into the
  host object by `REPLACE_FUNC_BODY` in the Makefile. The host TU holds a placeholder body; **the readable
  code is in the donor**. The C++ donors also carry class layouts as local structs.
- **NON_MATCHING bodies.** `#ifdef NON_MATCHING { C } #else INCLUDE_ASM #endif` blocks hold a correct but
  not byte-identical C reference body; the build uses the asm. Read them as the reference; a port can
  compile them. Every function is matched (3288 / 3288), so these are alternates kept for readability.
- **Raw `.word` / GLOBAL_ASM** remain for handwritten asm (exception handlers, TLB), the RSP microcode
  blobs and pad / data sidecars, not for game logic.

## 7. Open questions (all areas)

Aggregated from each doc's open-items list (2026-11-15). The doc in brackets holds the details.

**Format and loader**
- The USO Sym hash (tag low 16 bits, word3): which function of the export name it is. Cracking it would
  verify every export / import name against the ROM [READABILITY_PLAN 11, USO_FORMAT 11].
- USO Info word 0x08, the record flag class bits, the module header's second word; EntrySym /
  BinaryDataSection / DiskInfo payloads; `gFsDeviceHeaps[]` (was `D_80012C70`) per-device state beyond the heap range [USO_FORMAT 11].
- The ItemMgr / item file binary format (`ItemMgr_Load`, `ItemType_load`); only the instance position is
  documented [COURSE 9].
- The CollShape grid format ("no pGrid data") [SYSTEM_LAYER 7].
- rom/anims.bin entry header and the anim id -> name map (the RiderAnim state names depend on it)
  [GAME_CLASSES 16].
- Texture format 0x608: accepted by the size code, rejected by the loader; probably dead data [GRAPHICS 10].

**Physics and camera**
- groundFlags bit 1 (air spin / yaw mode, 0.724 decay) and bit 0x400 (sound + light): which course
  attribute; unkA18 (air trick rotations) writer; the contact solver's use of surfImp / surfSpd / surfVsc and
  `friction` (`DNode_solveContacts`, donor game_libs_ncc_65494.cpp); `Friction_vfn11_00063F34`; the RoData
  k constants (bootup RoData 0x8C8..0x9A0) [PHYSICS 9].
- The counter-steer `pad_setIfNewer_00067A54` event (rumble or effect, unproven) [PHYSICS 3].
- CamPath unk08 / 0C / 18 / 1C / 24 / 2C, CourseCam 0x278 (camSource 0x874 is resolved: the rider's head node,
  GAME_CLASSES 20); the RiderCam
  fov tables' RoData addresses [CAMERA 9].

**Course and race**
- settings +0x68 (the ENV_LT2 / EQ2 / EQ3 selector; no C writer found) and the SUN op's two ints (unused by
  the matched code) [COURSE 9].
- `RaceGate`: the gate item class (base, bytes below +0x64); WorldRegistry 0x98..0x104 [COURSE 9].
- Checkpoints are tracked for entries[0] only in `RaceTracker_findGates` (as shipped) [COURSE 7].
- Race results 2-5 (`RaceProcess_endResult2_00006E78` ... `endResult5_00006F60`): name them from the result sprites 0x60000-0x6000B
  [SYSTEM_LAYER 10]. The Sym 858-860 fade floats' per-site aliases are crossed [SYSTEM_LAYER 12, run 482].
- h2h pause rows 2 / 3 / 4 (flags passed to `GenSelectChar_ctor`) [MODES H2].

**Graphics**
- Roles of the remaining `gfx_func_` (0x43D2C, 0x453A8, 0x46B44, 0x47AB4 / 0x47AD8, 0x47F68, 0x4E138),
  `gfx_setSizePairA_00044C9C` / `B_00044CB0` and the gfx empty stubs; their callers are unresolved imports [GRAPHICS 10].
- Window +0x100-0x144 and ScreenWindow +0x174-0x1C0 fields; BaseLight_ctor and the Sprite_ctor donor still
  raw; the anim / skin NM bodies not yet on anim.h / skin.h [GRAPHICS 10].
- Which SGI 2.0H ucode each `RcpTask_setUcodeSgi20H*_<addr>` setter installs (none is called) [ENGINE_CORE 4].

**Audio**
- More SequenceLayer / SequenceChannel fields; the remaining per-function `gAudioContext_345c0*` / `D_345c0_*` views onto AudioContext;
  SoundObj sign-mismatched reads and the two splice placeholders [AUDIO Next].

**Modes and data model**
- SelectWin unk3F8 / 400 / 404 / 484 / 488 / 4BC / 4C0, SelItem +0x25C..0x294, `eventFlags` stays raw
  (register renumbering) [MODES run 484].
- RaceTracker vtable slots; TrkDataManager (shares TimDataManager's 0xB8..0xD7 tail, but 0xD8 is a
  once-flag) has no struct of its own [MODES run 469, 492]. The score pop-ups are `PointsPopup`
  (gdl/gadget.h, run 496); game_libs.c PointsGadget_allocSlot_00003B1C uses it (run 501).
- Gadget setters with address suffixes (`CourseGadget_setFloat2_0000254C` ...), the `app_shiftAddLookup_00042400`
  table, ItemType slot 12 [SYSTEM_LAYER 12].
- Unnamed bootup Data objects Sym 256 (0x1C-byte rows used by `game_setupSolo`) and Sym 274 [SYSTEM_LAYER 12].
- About 100 weak `<prefix>_func_<addr>` names remain ROM-wide (gfx / graphics classes, camera, RiderAnim,
  SnowBoarder, SnowAI) [SYSTEM_LAYER 12].

## 8. 64-bit port readiness: pointer / int casts (scripts/port-audit.py)

`scripts/port-audit.py` (agent-a run 536; run it from the project root after a full build) lists the
spellings in compiled code that assume 32-bit pointers. It only reports; it changes nothing. It blanks
what the matching build does not compile, in the same way as the readability census. Patterns:

- **A** `(s32)&X` / `(int)&X` / `(u32)(&X)`: an address cast to a 32-bit int. A* = the cast is the right-hand
  side of a store, typically `NODE(p)->vptr = (s32)&Foo_vtbl` or `->name = (s32)&sStr_...`.
- **B** `(s32)((char *)p + K)`: an int cast whose operand starts with a pointer cast.
- **C** `*(int *)(p + K)` loads used as pointers, for example `(T *)*(int *)(...)` or as the base of a
  second raw access.
- **D** `*(T **)(p + K)`: a pointer loaded at a hard-coded byte offset. The offset assumes 4-byte pointers,
  so it moves on a 64-bit host where a struct field would not.
- **H** header struct fields declared `s32` / `int` / `u32` whose name (vptr, parent, next, owner, ...) or
  comment (`Foo *`, `char *`, pointer) says they hold a pointer. This is a lower bound, because many s32
  fields that hold pointers have no such hint (for example H2HWinsDisplay.race).

Owners are the census owner() table (a / b / c / g / h, section 0). hdr = include/ headers. Snapshot at
agent-a run 568 (main 3f4755e0b plus that run's commits; run 562 had A 270, B 81, C 16, D 208, H 13;
run 557 had A 310, B 157, C 20, D 239, H 22;
run 549 had A 323, B 158, C 23, D 285, H 40; run 536 had A 484, B 171, C 32, D 497, H 49). Run 549 typed
Node.name (const char *), Node.children (NodeLink *), Node.vptr (char *), Sprite.children and the skin.h
pointers. Run 557 typed the gdl headers: anim.h (AnimData.keys / mgr, AnimGroup.anims / mgr,
AnimFrameSlot.anim, AnimFrameCache.slots, AnimDataMgr.groups, AnimPlayer.animators / mgr), dnode.h
(PhysQNode.owner, Friction.owner: DNode *), coll.h (CollObj.owner: Node *), the CollObj / BinFile / BaseMat
vptr (char *), TexImage.pixels (char *), TextWin.owner (void *), and NodeMsg (arg is now a union {value,
payload}, reply a Node *). Run 562 typed backup.h BackupGhost.data (struct InputFrame *; Backup_ghostSetHeader's
parameter with it). Run 568 typed course.h CourseParm.vptr / CourseFParm.vptr / WorldRegistry.vptr
(char *; the six forced (s32) / (int) store casts, plus the three in game_uso.c's NON_MATCHING
CourseMarkerTmpl_create, dropped); H is now 0 (the other areas typed race.h and include/game between 562 and 568).
At run 562 gdl still had race.h only (RaceProcess.parent, TimRace.dataManager, RaceTracker vptr /
owner; agent-h's run); the other 9 are include/game. Between 557 and 562 the other areas cleared most of
timproc_uso_b5 (SelectWin_ctor, SelItemParms / SelItemInfo ctors) and part of post0b. No retype so far has
needed a `*(int *)&p->field` fallback; the one trap is a field used in pointer arithmetic (`p->mgr + 0x40`,
`(c)->slots + off`), which compiles silently scaled, so every retype is checked by an all-object objdump
diff, not by warnings. (The `*(int *)&` lever has been needed for raw-offset conversions, not retypes:
member reads that reorder loads or swap `and` operands, e.g. ncc_3D71C, SnowBoarder_update. Run 568: in
ncc_4BAF4 a typed read through a cast of an inline `me()` result -- even `*(f32 *)&((Sprite *)me(..))->depthBias`
-- moved edg spill slots / FP operand order, so F4B(cam, 0x30) / F4B(self, 0xC8) stay raw.)

| pattern | a | b | c | g | h | hdr | total |
|---|--:|--:|--:|--:|--:|--:|--:|
| A: `(s32)&X` address -> int | 63 | 29 | 4 | 9 | 62 | 0 | 167 |
| B: pointer expression -> int | 6 | 12 | 6 | 11 | 3 | 0 | 38 |
| C: `*(int *)` load used as a pointer | 1 | 3 | 1 | 0 | 1 | 0 | 6 |
| D: `*(T **)(p + K)` pointer at a fixed offset | 54 | 50 | 10 | 1 | 18 | 0 | 133 |
| H: header field: int that holds a pointer | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

A* (the `(s32)&X` is a store right-hand side): a 39, b 19, c 1, g 2, h 26; total 87.

Owners: the census owner() table (a / b / c / g / h); hdr = include/ headers (pattern H only).

Top 15 files (A+B+C+D):

| file | A | B | C | D | total |
|---|--:|--:|--:|--:|--:|
| `src/game_libs/game_libs_post0b.c` | 23 | 9 | 3 | 48 | 83 |
| `src/bootup_uso/bootup_uso.c` | 10 | 0 | 0 | 11 | 21 |
| `src/game_libs/game_libs.c` | 15 | 2 | 0 | 0 | 17 |
| `src/bootup_uso/bootup_uso_ncc_55A0.cpp` | 14 | 0 | 0 | 0 | 14 |
| `src/game_uso/game_uso.c` | 4 | 10 | 0 | 0 | 14 |
| `src/game_libs/game_libs_post.c` | 2 | 4 | 1 | 5 | 12 |
| `src/match_imports/GfxLib_hostioParms.c` | 12 | 0 | 0 | 0 | 12 |
| `src/titproc_uso/titproc_uso.c` | 12 | 0 | 0 | 0 | 12 |
| `src/game_libs/game_libs_post1b.c` | 6 | 3 | 0 | 2 | 11 |
| `src/eddproc_uso/eddproc_uso.c` | 4 | 0 | 0 | 2 | 6 |
| `src/game_libs/game_libs_o2_38A28.c` | 0 | 0 | 0 | 6 | 6 |
| `src/match_imports/RoomModifier_display_0000117C.c` | 0 | 0 | 0 | 6 | 6 |
| `src/kernel/kernel_006.c` | 5 | 0 | 0 | 0 | 5 |
| `src/match_imports/game_init.c` | 4 | 1 | 0 | 0 | 5 |
| `src/n64proc_uso/n64proc_uso.c` | 2 | 2 | 0 | 1 | 5 |

Top 15 functions:

| function | file | owner | sites |
|---|---|--:|--:|
| `item_registerTemplates` | `src/bootup_uso/bootup_uso_ncc_55A0.cpp` | h | 14 |
| `RaceProcess_init` | `src/game_libs/game_libs.c` | h | 12 |
| `GfxLib_hostioParms` | `src/match_imports/GfxLib_hostioParms.c` | a | 12 |
| `Node_doCommand` | `src/game_libs/game_libs_o2_38A28.c` | a | 6 |
| `RoomModifier_display_0000117C` | `src/match_imports/RoomModifier_display_0000117C.c` | a | 6 |
| `gfx_submitFrameTask_000469A8` | `src/game_libs/game_libs_post0b.c` | b | 5 |
| `osCreatePiManager` | `src/kernel/kernel_006.c` | a | 5 |
| `game_init` | `src/match_imports/game_init.c` | a | 5 |
| `N64DemoProcess_ctor` | `src/n64proc_uso/n64proc_uso.c` | a | 5 |
| `Col::side` | `src/game_libs/game_libs_ncc_4FD00.cpp` | a | 4 |
| `Parms_addParm` | `src/game_libs/game_libs_post0b.c` | b | 4 |
| `ZoneShape_build` | `src/game_libs/game_libs_post0b.c` | b | 4 |
| `arc_DataManager_update` | `src/match_imports/arc_DataManager_update.c` | a | 4 |
| `GameDemoProcess_ctor` | `src/titproc_uso/titproc_uso.c` | h | 4 |
| `edd_EditorsProcess_ctor_0000025C` | `src/eddproc_uso/eddproc_uso.c` | a | 3 |

Pattern H per header directory: none left.

Reading it: A and H are the bulk of the work, and both come from the same convention. Node / Parms /
gadget fields are declared `s32` because the ctors store addresses into them through int-cast bases
(`NODE(p)->vptr = (s32)&vtbl`). Many of those int casts are load-bearing for the matching build: an
int base colours a different register than a typed pointer (uso_init's CTX(f), run 536; IDO_CODEGEN.md
has more). So a 64-bit port types the fields first (H) and keeps the matching spellings behind a
PORT / NON_MATCHING path, instead of editing the casts one by one. Pattern D disappears as raw offsets
become struct fields (the census raw-offset count). `--list A|B|C|D|H` prints every site; `--owner X`
narrows to one area.
