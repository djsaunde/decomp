# 1080° Snowboarding: PC port plan

Status: plan (2026-11-16). Starting point: the decomp is byte-identical at 3288/3288 functions, and the source
is named and typed. See READABILITY_PLAN 12b / 12c: 3 raw sites, 0 unexplained names. This document says how
to get from that source to a native PC build. It builds on 1080_PORTING_GUIDE.md (architecture, frame loop,
data formats, the N64 pieces to replace) and USO_FORMAT.md section 13 (the USO system on PC). Read those
first; this plan does not repeat them.

## Index
1. Goals and non-goals
2. Approach: source port, matching build stays the reference
3. Key decisions
4. Architecture of the port
5. Milestones
6. Verification strategy
7. Risks and open questions
8. How the work is organised
9. M0 results: timing, RNG and determinism
10. M0 results: extractor and audio
11. M0 results: graphics coverage
12. M0 results: source map and compile census
13. M1: build skeleton
14. M2 prep: libultraship patch series
15. M1: audio mixer
16. M1: link plumbing (CALL names, bound placeholder calls, data blobs / aliases, port/uso)
17. M1: libultra shim and main loop (17.8: SysApi, port/fs, boot-path trace)
18. M1/M2: byte order (USO blob type map + swap, rom/*.bin readers, bitfield audit)
19. M2: graphics transport (feasibility on WSL2, PORT_GFX_DUMP / DLMP, dlreplay; 19.6: Fast3D in f3dreplay, golden tests; 19.7: 7 more scenes, patches 0006-0008, in-process Fast3D)
20. M5 prep: saves (the SRAM file is the N64 image: format rule, port_backup, test_backup, the gate's saves step)
21. M6: 64-bit (the gap census, the design: the low-address model with the game in the x32 data model, the libc boundary, varargs)

---

## 1. Goals and non-goals

**Goals**
- A native executable for Linux and Windows (macOS later) that plays the full game: every mode, all
  courses, saves and ghosts, and two-player split screen.
- The player supplies the ROM. Assets are extracted from it at first run. No Nintendo data is in the repo
  or in the release.
- Faithful by default. The same physics, the same AI, and the same frame-by-frame behaviour at the
  original update rate, checked against an emulator (section 6).
- The matching N64 build keeps working from the same source tree, byte-identical, gated as today.

**Later goals (after a faithful 1.0)**
- Widescreen, higher internal resolution, high-frame-rate rendering through interpolation (the simulation
  stays at the original rate), modern controller rebinding and rumble.

**Non-goals**
- Changing gameplay, or "fixing" bugs that affect how the game feels. Any such fix goes behind an option.
- Emulating the RDP pixel-for-pixel. We render the display lists with a modern GPU backend.
- The 64DD (Leo) and HostIO / rmon debug paths. They are stubbed out.

## 2. Approach: source port, matching build stays the reference

**Recompile the decompiled C / C++ natively**, with N64 services replaced by a host layer. This is the
approach of the SM64 port, Ship of Harkinian and the Perfect Dark port. The alternative is static binary
recompilation (N64Recomp). It is rejected as the main path:
- We already have readable, typed source.
- Recompilation would not let us change logic cleanly.
- The runtime-relocated USO modules make static recompilation awkward.

One source tree, two builds:

| build | compiler | output | purpose |
|---|---|---|---|
| matching (today) | IDO 7.1 / 5.3 / NCC / MIPSpro, asm-processor | `tenshoe.z64`, byte-identical | the reference: proves the source is the shipped game |
| port (new) | clang / gcc / MSVC, `-DPORT` | native executable | the game on PC |

**Rule:** every port-only change is either behind `#ifdef PORT` or in new port-only files under `port/`.
The matching gate must stay green on every commit, as it is today.

## 3. Key decisions

These are the recommended defaults. Each one is a decision the user should confirm before M0.

1. **Target 32-bit first, then 64-bit.** The source still has int-held pointers: port audit
   A 28 / B 33 / D 1 (1080_PORTING_GUIDE section 8). More importantly, ROM data structures contain 32-bit
   pointers. Shape assets have pre-relocated array addresses (GRAPHICS 7.1), and USO Data has relocated
   words. A 32-bit host build (`-m32` / Win32) lets those structs keep their layout, so M1-M5 don't depend on
   the pointer-width work. M6 does the 64-bit conversion: loader-side deserialisation of pointer-bearing
   assets, plus the remaining audit sites.
2. **Graphics: a Fast3D-family F3DEX interpreter.** The game emits F3DEX 1.23 display lists
   (`RcpTask_setUcodeF3DEX`). Use the libultraship / sm64-port Fast3D renderer with the F3DEX (GBI 1)
   command set, rendering through OpenGL or D3D11 / Vulkan. Do not hook `PolyShape_display` directly: the
   display-list path keeps the game code unchanged and gives one place to fix rendering. The first spike
   (M0) must confirm that Fast3D covers every command the game emits.
3. **Audio: our own CPU implementation of the OoT audio ABI** (decided 2026-11-16). The driver is OoT's
   (1080_AUDIO.md, "state for porters"). Keep the sequence player and synthesis code from the decomp.
   Replace the RSP task with a CPU mixer, written from scratch in `port/audio/`, that decodes and executes
   the game's own command list. Replace `osAiSetNextBuffer` with the host audio stream.
   - **Licence:** the SoH / sm64-port mixer.c has no clear licence, so we do not copy it. It may be read
     only to cross-check behaviour.
   - **Graphics:** builds on libultraship (MIT), pinned.
4. **USO system: static link** (USO_FORMAT section 13). One executable. `uso_load` / `uso_unload` become a
   registry of per-module init / fini. `CALL()` / `XCALL()` / `GL_DATA*()` / `INPUT_MGR()` become plain
   symbols under `PORT`. Mode-module Bss is re-zeroed when the module is "loaded", so its lifetime matches
   the original. Data-only USOs become extracted assets.
5. **Threads: one simulation thread plus an audio thread.** The N64 graphics, audio and pad threads become:
   - the main loop: poll input, then `app_run` one iteration, then submit the frame;
   - an audio callback thread that runs the synthesis.

   libultra message queues get a small host implementation. Most of them collapse into direct calls.
6. **libultra is replaced, not ported.** The kernel and the `gl_` copies of libultra are not compiled for
   the port. A `port/ultra/` shim provides the subset the game calls: OS messages / threads (thin),
   VI / SI / PI / AI, the cache no-ops, and `osVirtualToPhysical` as an identity. The 80-plus kernel
   globals named in run 598 show which ones matter.
7. **Timing.** There is no dt anywhere (1080_PORTING_GUIDE 2.2). Run the simulation at the original
   update rate and decouple rendering from it. Answered statically in section 9 (run 607): VI-locked, one
   update per 2 retraces (30 Hz NTSC), dropping to 20 / 15 Hz when a frame overruns, with no compensation;
   all clocks count updates (33 ms each). The port runs a fixed 30 Hz step (9.6).
8. **Build system.** CMake for the port, kept separate from the matching Makefile. A generated
   **source map** decides which body of each function the port compiles (section 4.1).

## 4. Architecture of the port

```
port/
  main.c              window, main loop, fixed-step scheduler, config
  sourcemap.cmake     generated: the source file of each function's port body (4.1)
  ultra/              libultra shim: os_thread / os_message (thin), vi / si / pi / ai, cache no-ops
  uso/                static module registry: per-module init / fini, Bss reset, CALL / GL_DATA mapping
  fs/                 ROM filesystem from the extracted asset tree, byte-swapping readers
  gfx/                Fast3D (F3DEX GBI 1) + backend, framebuffer-read emulation (4.3)
  audio/              CPU audio ABI mixer, host audio stream
  input/              SDL gamepad / keyboard -> PadCtl / RiderInput, rumble
  save/               SRAM image <-> save file (0x8000 bytes, checksums kept)
tools/extract/        ROM -> assets: Yay0 decode, USO split, data-only USOs, rom/*.bin, byte order kept
```

### 4.1 Which body each function compiles to

The matching build gets some functions' code from places other than their plain C definition:
- **REPLACE_FUNC_BODY donor splices:** 226 C++ `.cpp` donors and many -O0 / -O1 / IDO 5.3 C donors.
- **`src/match_imports/` native ports.**
- Hosts whose plain body exists only as an `#ifdef NON_MATCHING` reference.

For each function the port must compile the body that is **the shipped code**: the donor or the native
port, not the host placeholder. A host placeholder can be a code-free stand-in.

- **Deliverable (M0):** `scripts/port-sourcemap.py`. It reads the Makefile's REPLACE_FUNC_BODY / donor
  rules and the match_imports bindings, and emits one row per function: the authoritative source file and
  the compile mode (C or C++). The port's CMake consumes it.
- **Check:** for every function, the map points at the file whose matching-build bytes are the shipped
  bytes. Verify this by building that file with the matching toolchain and comparing against expected/.

### 4.2 C++ donors on a modern compiler

The libgdl C++ is Cfront-style:
- manual vtables (`VT_SLOT`, vptr at +0x28);
- pointer-to-member records (`GdlPmf`);
- placement-new idioms;
- local mirror structs.

The donors compile with the 1997 edg front end and avoid `-I include`. For the port:
- compile them as C++ with relaxed flags (`-fpermissive` where needed, no RTTI or exceptions);
- add `-I include` under PORT, so the real headers replace the local mirrors where possible. The headers
  are already C++-safe.

Expect a batch of mechanical fixes:
- int / pointer casts;
- old-style declarations;
- `asm` / pragma uses.

Keep them under `PORT` so the matching build is untouched.

### 4.3 Graphics specifics

- **Matrices and viewports:** fixed-point Mtx and Vp are converted by Fast3D. The game's own
  `guMtxF2L`-style conversions run unchanged.
- **Framebuffer reads:** `Mat_fromFrameBuffer`, `ScreenThumbMat_grab` (a 64x32 thumbnail copied every
  frame), the debug text and the splash all read the colour buffer. Emulate them with a GPU read-back into
  the CPU-visible "framebuffer" those functions expect, at reduced resolution. This is the known-hard area
  for Fast3D ports.
- **Microcode:** `RcpTask_setUcodeF3DEX` selects the microcode, with F3DLP.Rej as the alternate. Map both
  to the same interpreter.
- **Texture formats:** the game uses RGBA32 / 16, IA8, I8, I4, CI8 + TLUT (GRAPHICS 6.1). All of them are
  standard Fast3D formats.

### 4.4 Data

- **Byte order:** everything on the cartridge is big-endian (1080_PORTING_GUIDE section 4). Two choices:
  - keep assets big-endian in memory and byte-swap at the read sites (the `fs_gdlRead{Int,Float,Quad}`
    readers, the parm readers, shape parsing);
  - convert at extraction time.

  Recommendation: **swap in the readers** for parsed formats (parms, items, markers, camera paths). For the
  bulk binary blobs (shape assets, anims, audio), a typed swap at extraction time is simpler, because they
  are walked by many functions.
- **Unknown layouts:** the item file and collision grid layouts are still open (COURSE 5,
  ENGINE_CORE / SYSTEM_LAYER 7). Swapping them needs their exact layout. They are blocking items for M3.

## 5. Milestones

Each milestone ends with a demo and a check from section 6.

**M0: Spikes and scaffolding (de-risk)**
- **Source map:** port-sourcemap.py (4.1), plus a CMake skeleton that compiles every file in the map for a
  32-bit host. Linking is not required yet; this step counts compile errors by category.
- **Emulator measurements:** the original simulation rate and the frame pacing. Capture a few reference
  traces with the game's own pad record / playback (section 6).
- **Fast3D coverage check:** dump a few frames of display lists from an emulator and run them through
  Fast3D offline. List any unsupported commands.
- **Extractor v0:** ROM → USO / asset tree, with Yay0 decoded.

**M1: Headless boot**
- Link the full game with the ultra / uso / fs shims and stubbed gfx / audio.
- Boot through `boot_main`, `App_main`, `SnowBoard_InitInstance`, then GameFlow into the title flow mode,
  logging the Node tree and the GameFlow states.
- **Exit check:** the title demo's GameFlow state sequence matches the emulator trace.

**M2: Graphics**
- Fast3D wired to RcpMgr's gfx task.
- The N64 logo, the title screen and the attract demo render.
- **Exit check:** screenshots side by side with the emulator for a fixed set of frames.

**M3: A playable race**
- SDL input → PadCtl / RiderInput.
- Course loading (shape, collision, items, markers, env, cameras).
- Time attack on one course, start to finish.
- **Exit check:** a recorded run reproduces the emulator's rider position trace frame-by-frame (section 6).

**M4: Audio**
- The CPU audio ABI mixer.
- Sequences, sound effects and the rider sound (`snd_updatePlayer`).
- **Exit check:** audio-thread command streams match the emulator's for a recorded run, and listening
  tests pass.

**M5: The whole game**
- All flow modes: title, time attack, trick attack, match race, versus 2P split screen, training, and the
  select screens (genproc).
- Name entry, the replay viewer, saves (SRAM image) and ghosts.
- **Exit check:** every mode completes, and saves round-trip.

**M6: 64-bit**
- The port-audit lists (A / B / D) are fixed under PORT.
- Pointer-bearing assets are deserialised into native structs at load.
- USO-style data words are relocated into native pointers.
- **Exit check:** the M3 / M5 traces are identical on 64-bit.

**M7: Enhancements (1.x)**
- Widescreen (camera FOV and HUD anchoring), internal resolution.
- High-fps rendering by interpolating Node transforms between simulation steps.
- Rebinding, settings UI.
- HostIO parm groups as an optional debug UI. They are already a structured parameter system.

## 6. Verification strategy

The game has a built-in, deterministic input recorder: `pad_startRecord_000679BC` /
`pad_startPlay_00067A10` and the ghost / replay system. Use it as the backbone of differential testing.

1. Record input sessions in an emulator, from the real ROM, using the game's own recorder or the
   emulator's input log.
2. Log per-frame state at fixed points in both the emulator and the port:
   - GameFlow state;
   - each rider's `dnode.vqs` position and quaternion, speed and RiderAnim state;
   - the camera eye and target;
   - the RNG state.
3. Play the same input in the port and diff the traces. The first diverging frame and field point at the
   bug.
4. Run traces in CI headless (after M1), plus a few screenshot comparisons (after M2).

**Floating point:** the N64 uses single-precision floats with flush-to-zero behaviour that differs from
x86 SSE. Compile with strict single-precision settings (no x87, no FMA contraction, SSE flush-to-zero /
denormals-are-zero to match). Treat trace drift beyond 1 ULP as a bug to explain, not to tolerate.

## 7. Risks and open questions

| risk | impact | mitigation |
|---|---|---|
| ROM data with embedded 32-bit pointers | 64-bit build | 32-bit first (decision 1); deserialise at load in M6 |
| Framebuffer reads (thumbnail, render-to-texture, debug text) | visual bugs | GPU read-back path (4.3); low-res is fine |
| Fast3D gaps for F3DEX 1.23 specifics | missing geometry or effects | M0 offline display-list check |
| Original simulation rate and pacing unknown | feel, physics drift | measure in M0; fixed-step scheduler |
| C++ donor compile breakage on modern compilers | M0 / M1 effort | PORT-only fixes; real headers replace mirrors |
| Item / collision-grid binary layouts not fully known | M3 | finish those decodes first (COURSE 5, SYSTEM_LAYER 7) |
| FP behaviour differences | trace drift | strict FP flags (section 6) |
| NON_MATCHING-only reference bodies that differ from the shipped code | subtle bugs | the source map always picks the shipped body (4.1) |
| The ~13 contrived matches (MATCHING_SUMMARY section 10) | readability only | plain-C versions under PORT, written when the port first reaches each function |

**Open questions to settle in M0:**
- ~~The simulation rate.~~ Answered in section 9 (30 Hz, frame-counted clocks); confirm in an emulator.
- Whether retail uses the controller pak at all.
- Exactly which libultra calls survive past the shim.
- Audio output rate and buffer size (from `osAiSetFrequency`).

## 8. How the work is organised

- **New ownership areas for agents:**
  - `port/ultra + port/uso + port/fs` (system)
  - `port/gfx` (graphics)
  - `port/audio`
  - `port/input + port/save`
  - `tools/extract`
  - game-side PORT fixes, by the existing area owners: a / b / c / g / h keep their files.
- **Gates:**
  - **Matching gate, unchanged:** every commit keeps the ROM byte-identical.
  - **Port gate, new:** the port must build for 32-bit (and 64-bit from M6) and pass the headless trace
    tests.
- **Rough size:** M0-M1 about 2-3 agent waves, M2-M4 about 3-5 waves each, M5 about 3 waves, M6 about
  2-3 waves. The biggest unknowns are Fast3D coverage, the framebuffer effects and the asset
  deserialisation for 64-bit.
- **Legal:** no ROM-derived data in git or in releases. The extractor runs on the user's ROM. Credit the
  reused projects (Fast3D / libultraship, the SoH audio mixer) under their licences.

## 9. M0 results: timing, RNG and determinism

agent-g run 607, static analysis of the decomp source (no emulator on the analysis machine). Paths are
under `projects/1080-decomp/`. "post0b" = `src/game_libs/game_libs_post0b.c`. The answers below settle
decision 7 and the "simulation rate" open question in section 7. An emulator run in M0 should still confirm
the numbers in 9.1 (the expected result is stated so it can be checked).

### 9.1 Simulation rate: one update per 2 VI retraces (30 Hz NTSC), slowing to 20 / 15 Hz under load

**The loop.** `app_run` (`src/game_libs/game_libs_ncc_34EB4.cpp`) does one simulation step per iteration of
its inner loop, in this order:
1. `pad_update` for every PadCtl on the SysLib list (:41);
2. `gfx_start` (:49);
3. App vtable slot "Update()" `a1->v4()` (:54);
4. slot "Display()" `a1->v3()` (:59);
5. `gfx_end` (:63);
6. `snd_FrameUpdate` (:69);
7. `SysLib.frameCount++` (:72), then the one-shot callback.

The perf label strings at Data 0x1E494..0x1E4D0 confirm that v4 is Update and v3 is Display. There is one
extra Update (:37) before the loop starts, with no Display. There is no dt and no step count: one iteration
is one tick of everything.

**The retrace source.** `GfxLib_init` (`src/game_libs/game_libs_ncc_445AC.cpp:50`) calls
`osViSetEvent(gSysLib.msgQueue, 100 /* 'd' */, 1)`, so the VI posts a message on every retrace (60 Hz NTSC,
50 Hz PAL). The RcpMgr thread's `RcpMgr_service` (`src/game_libs/game_libs_ncc_4D688.cpp`, `case 'd'` at
:183) handles each one:
- **every retrace:** `snd_AudioUpdate` (:208, so the audio driver frame is per VI), then
  `RcpMgr.retraceCount++` (:213);
- **every other retrace** (`n & 1`): `pad_waitIdleGlobal` + `pad_requestGlobal` (:187), so the controllers
  are read at 30 Hz.

**The pacing.** Three places in the frame use `retraceCount`:
- `gfx_start` (post0b:12078) stores the retrace count at frame start.
- `gfx_end` (post0b:12156) does four things:
  1. It spins until the RCP queue is idle, so the frame's RDP work counts inside the frame.
  2. It runs MorphUpd / ADrawUpd.
  3. It spins `while (rcp->retraceCount == frameStartRetrace)` (:12208), so at least one retrace must pass
     since `gfx_start`.
  4. It calls `gfx_swapBuffer` (:12211).
- `gfx_swapBuffer` (post0b:12757) calls `osViSwapBuffer`, then `gfx_waitRetrace` (post0b:12489). That waits
  for one more retrace, so the swap has happened before the other buffer is reused. The frame buffers are
  double-buffered (`fbIndex ^= 1`).

Start at retrace R, with work W (CPU plus RDP, in VI periods):
- W < 2 VI: the next iteration starts at R+2. This is the normal case: **30 Hz NTSC** (59.94 / 2 = 29.97 Hz),
  25 Hz PAL.
- 2 <= W < 3: R+3, 20 Hz.
- 3 <= W < 4: 15 Hz, and so on.

So the update period is `max(2, floor(W) + 1)` retraces. The rate is VI-locked and capped at half the VI
rate. It drops in whole retraces when a frame is heavy.

**No slow-frame compensation.** Nothing in game code reads the retrace count or a clock to scale the
simulation:
- The only `retraceCount` readers are the three above, plus the hostio status print in
  `src/match_imports/GfxLib_hostioParms.c:62`.
- `SysLib.frameCount` (the iteration count, not retraces) has two readers:
  - `gfx_setEvery4thFrameFlag` (post0b:16786), used by display code only (`Mat_draw`);
  - `SkinMgr_update`'s once-per-frame guard.
- `GfxLib.frameTime` (the measured "OneFrame" VI period at init, `game_libs_ncc_445AC.cpp:55-61`) is read
  only by `sys_timeInFrames_00033444`. That is exported to the kernel through SysApi +0x94, with no game
  caller.

A slow frame therefore slows the game (and its clock, 9.2) in real time. The emulator check for M0: the
title / race should show `retraceCount` advancing by 2 per `frameCount` step, with occasional 3s in heavy
scenes.

**The game is authored for 30 updates per second.**
- The race clocks add 33 ms per update (9.2).
- Title timers are `seconds * 30` frames (`src/titproc_uso/titproc_uso.c:527`, :530).
- The ghost cap is 6400 frames = 213 s at 30 Hz (1080_REPLAY.md).
- The VI-mode choice `gfx_setVideoMode(0x202)` picks the PAL mode table entry when `osTvType != 1`
  (`src/game_libs/game_libs_o2_44B78.c:57`). A PAL console would run the same code at 25 Hz with the same
  33 ms clock step. The ROM analysed is the NTSC release (header "NTEA").

### 9.2 Timers count updates, not retraces or osGetTime

Every race clock is a per-update add of 0x21 = 33 ms, guarded by "race running" (`RaceProcess flags & 0x10000`
and `raceState == 1`):

| clock | site |
|---|---|
| time attack elapsed | `TimDataManager_update_00001BCC`, `src/timproc_uso_b1/timproc_uso_b1.c:1010` |
| trick attack elapsed / score countdown | `src/timproc_uso_b3/timproc_uso_b3.c:1137`, :1139 |
| match race (mgr) elapsed | `src/mgrproc_uso/mgrproc_uso.c:1754` |
| 2P (h2h) elapsed | `h2h_DataManager_update`, `src/h2hproc_uso/h2hproc_uso.c:1525` |
| arcade elapsed and countdown (`fieldA0 -= 0x21`, 50000 / 30000 ms) | `src/match_imports/arc_DataManager_update.c:12`, :15 (`src/arcproc_uso/arcproc_uso_tail1.c:1369`) |

All other gameplay timers are plain frame counters:
- the Process / title `timer`, fades and logo holds (1080_MODES);
- the SnowAI countdowns (`include/game/snowai.h:65`);
- the rumble pattern position (`pad_update`).

`osGetTime` / `osGetCount` reach the game in two places, neither of them gameplay:
- `sys_getTime` (post0b:938). Its callers are `game_init`'s load-time profiling prints
  (`src/match_imports/game_init.c`, `bootup_27E8_func_0497D0` → `bootup_27E8_func_048E7C`) and
  `sys_timeInFrames`.
- libultra internals: `osContInit`'s power-on delay, `__osRepairPackId`'s random id, and the audio RNG (9.3).

The `prof_timer*` calls are debug profiling. Their results feed only hostio and debug text.

**Consequence.** The game clock is "frames × 33 ms", even at full speed: 29.97 updates/s × 33 = 989 ms per
real second. A port that runs the simulation at a fixed 30 Hz step reproduces the game exactly. Times,
records and ghosts are frame-exact by construction.

### 9.3 RNGs and seeding

| RNG | code | state | seed | users | affects the simulation? |
|---|---|---|---|---|---|
| game RNG `sys_randf` | post0b:26033 | u32 at bootup Data 0x21E04 | static initial value **0x0A6B99CD** (read from the ROM's bootup.uso Data). `sys_srand` (post0b:26013) exists but has **no caller** in bootup.uso's TextReloc table, and no module source names it | `x = ((4x+2)(4x+3)) >> 2`, returns `(x & 0xFFFF) / 65535.0f` (RoData 0x2074) | see below |
| stateless hash `sys_randFromSeed` | post0b:26006 | none | its argument | `SnowBoarder_update` rider shake: seed `((int)x ^ (int)z) >> 5 ^ 0x12345678` from the rider position (`src/match_imports/SnowBoarder_update.c:94`) | deterministic function of the state |
| audio `audioRandom` | `AudioThread_Update`, `src/game_libs/game_libs_o2_26214.c:177` | `gAudioCtx.audioRandom` | `(r + totalTaskCount) * osGetCount() + aiBuffer sample`, every audio frame: **not deterministic** | seq-script rand (`game_libs_o2_2C7A4.c:235`, `2BB7C.c:479`), note velocity / gate variance (`2B5F4.c:108`, :128), sfx channel variation (`src/match_imports/snd_SoundObjUpdateChannel.c:59`) | no: it stays inside the audio thread |

**`sys_randf` callers.** From bootup.uso's TextReloc (`scripts/uso-data-sites.py calls --to sys_randf`) and
the module sources:

| use | callers | gameplay effect |
|---|---|---|
| attract-demo rider picks | `game_setupDemoRace`, `game_setupDemoSplit` | before the race |
| screen-transition grid | `Fader_start` | visual |
| title TV effect | `Tv1Tmpl_blitFrame_000077D0`, `Tv1Tmpl_stepPicture_00007D04` | visual |
| HUD points float | `PointsGadget_allocSlot_00003C0C` (`game_libs_o2_3C0C.c:86`) | visual |
| random point on a triangle | `BasePolyShape_sampleTri` (`game_libs_ncc_54264.cpp:33`) | probably particles / spray; to be confirmed |
| opponent selection | mgrproc (`mgrproc_uso_o0_19C.c:205`) | before the race |
| title random selection | titproc (`titproc_uso.c:240`) | before the race |

`game.uso` (SnowAI, RiderAnim) and the boarder modules make no RNG calls, so the riders, the AI and the
physics are deterministic given the input. Because the game RNG is never reseeded, its state at a race
start depends on every call since boot: fades, demos, HUD and particles. Log it in the trace, but it should
not move a rider unless `sampleTri` turns out to feed collision; check that in M3.

**Port:**
- Keep `sys_randf` and its 0x0A6B99CD initial value.
- Give `osGetCount` a deterministic shim in trace mode: virtual cycles = frame × 1562500 at 46.875 MHz /
  30 Hz. That makes `audioRandom` reproducible for the M4 audio-command diffs.

### 9.4 The input recorder

**What is recorded.** `pad_update` (`src/game_libs/game_libs_o2_675A4.c`) runs once per simulation update
for each pad, from `app_run`, not from the pad thread. When `replayMode != 0` it does:
1. `replayFrame++` (:72);
2. RECORD (:77) stores `{s8 rawStickX, s8 rawStickY, s16 held & recordMask & 0x1700}`;
3. PLAY (:83) ORs the stored buttons into `held` and replaces the raw stick bytes.

All of this happens before the /80 scaling, the 0.2 dead zone and the direction-bit derivation (:91-:135),
so playback goes through the same path as live input. Further details:
- `pad_startRecord_000679BC` / `pad_startPlay_00067A10` (`src/game_libs/game_libs_post1b.c:3339`, :3351)
  only set the buffer, length and mode.
- Frame index 0 is never written; data starts at index 1.
- Paused pads (`input_pauseRacePads`) skip the whole block, so the pause menu consumes no replay frames.
- The format is in 1080_REPLAY.md (4 bytes per frame, cap 6400).

**Is it enough to reproduce a race on its own?** For the rider physics of a solo race (time / trick attack,
vs-ghost, and the post-race replay), yes, with these conditions:
- **The same start state.** The course, rider, board and mirror flag are kept in InputMgr `rec*`; the run
  starts at `game_setupSolo` / `game_setupReplay` and counts every unpaused update, including the intro and
  the 3-2-1.
- **No input beyond the recorded bits.** Only the buttons in 0x1700 and the stick are stored. Anything else
  pressed live is not replayed: C-button camera / view changes, START, and the 0x20 ghost toggle
  (`RaceTracker_toggleGhost`). Camera and HUD traces can therefore differ between a live run and its replay,
  even though the rider trace matches.
- **The same frame alignment.** No race-phase transition may wait on asynchronous work: audio or DMA load
  completion. The source shows no retrace or clock reads, but whether any intro phase polls a load flag
  has not been audited. Check this in M1 / M3.
- **Match races.** Here CPU riders also race. They are deterministic (no RNG in SnowAI), and
  `h2h_startReplay` / `mgr_startReplay` restart the race and replay both pads.

**For the port's differential tests,** do not rely on the in-game recorder alone. Hook the input one level
lower, at `pad_decodeButtonMap_00034CC8`'s output inside `pad_update`. Log and inject the **full** `held`
word plus both raw stick bytes for every pad on every update. That covers the camera buttons and menus too,
so whole sessions (boot → title → race) replay. The emulator side needs the same thing: an
emulator-level input log at 30 Hz pad-read granularity, because the pads are read every other retrace and
the game consumes at most one new sample per update. The game's own recordings remain useful as
ready-made, long, physics-only test vectors, and saved ghosts are portable test inputs.

#### 9.4.1 Scripted headless input: `--input` (agent-a, run 843)

Commit 6ea217c19 (branch agent-a). `tenshoe --input FILE` drives the headless build with a text
script (`port/host/input_script.c`; example `port/host/time_attack.input`):

- `PADS n`, `RUMBLE p` (boot-time: osContInit / pad_probePaks see them through `host_boot_pads`);
- `F <when> [P<n>] <buttons> [STICK x,y]`, where `<when>` is `N`, `N-M`, `N:len`, or `+D...`
  (relative to the previous F line). The buttons are A B Z START L R DU DD DL DR CU CD CL CR or `0xNNNN`.
  The stick takes raw bytes.
- A step is SysLib.frameCount (state.log `F`). A state held on step N reaches pad_update on N+1 (the
  pad thread snapshots during the step's retraces). Use 3-step presses.
- The pads take the live path: HostPad -> port_si_set_pads -> osContStartReadData -> the pad thread ->
  pad_update. In the title and menus only 2 PadCtl objects exist (ports 1 and 2), so P3 / P4 reach the
  SI but nothing reads them there.
- `PORT_GFX_DUMP_STEPS=a,b-c` dumps only those steps' gfx tasks. `<dump>/steps.txt` maps each task
  to its step. `capture.sh -i SCRIPT -F STEPS` labels the tiles by step. Each step has 2 tasks: the
  3D scene, then the 2D overlay. capture.sh no longer deletes anything, so `-o` must be a fresh directory.

**Scripted run (time_attack.input):**

| step | screen |
|---|---|
| 480 | START on "Press START" |
| 485 | English / Japanese |
| 560 | A, main menu |
| 620 | DD, Time Attack |
| 680 | A: Select Rider (flow 0,4,1 -> 0,4,4) |
| 950 | A |
| 1050 | A: Select Board |
| 1150 | A: Select Course |
| 1300 | DR: the next course (the minimap and best time change: 1'30"00 -> 2'00"00, but the name label stays "Air Make": a stale course-name sprite, gfx side) |
| 1360 | A: flow 4,4,4, then 5,4,4 at 1379 ("Ready"), race state 1 at 1441 ("GO!") |
| later | the timer runs and the rider moves along the course (r0 changes, stick steers) |

The 3D scene is black and camera fields are NaN (`cam=ffc00000`) through the race (agent-g, projection).
The km/h readout shows 0.

**Crash (agent-c, audio).** [Resolved: the 0xB5 byte-order fix 755392718 was not on this branch's base; plan 20.1.] On the clean tree the race load segfaults at step ~1380:
- `AudioSeq_SequenceChannelProcessScript` (`src/game_libs/game_libs_o2_2BB7C.c:541`), case 0x98:
  `(*channel->dynTable)[value]` with `dynTable == NULL`;
- called from AudioSeq_SequencePlayerProcessSequence (2C7A4.c:340), AudioSeq_ProcessSequences
  (post.c:11625), AudioSynth_Update (post.c:212), AudioThread_UpdateImpl (26214.c:183),
  port_audio_frame (port_audio.c:167), RcpMgr_portDrain (4D688.cpp:306/358), app_runOneFrame
  (34EB4.cpp:166).

On the N64 the same read would TLB-miss, so the race-start sequence's set-dyntable command
is probably being missed or mis-decoded in the port. A local, uncommitted `if (dynTable == NULL) break;`
gets through to the race.

**Determinism.** The same script run twice gives byte-identical state.log (2000 frames, through the
race start) and `--record` logs. `--replay` of that record log, with no script, reproduces state.log
byte for byte (0 missing inputs, 0 replayFrame mismatches). The game's own recorder (9.4) runs from
race start: replayFrame counts 0.. from step 1442. Its post-race playback was not reached, because it
needs a finished race.

**SRAM is not deterministic** (save side, plan 20). With no input, two runs write SRAMs that differ
in ~35 bytes: the header words 0..7 (checksums) and 0x20C-0x22F (mirrored at 0x7FDC-0x7FFF). Those
bytes hold i386 stack addresses (`0xfffda208`, `0xffb31c08`). With `setarch -R` (no ASLR) the files
are identical. Some save struct is written with stack pointers or uninitialised stack bytes in it.
state.log is unaffected.

#### 9.4.2 Run 846 (agent-a): parm tags, menus, input scripts

**Cause of the stale "Air Make" label: byte order of the parm tags, not a texture cache.**
`CourseItem_drawLabel` picks the label sprite row from `SelItem::Info.ixn`, and `ixn` was 0
(its ctor default) for every item. Parms_load compares each stream record's 4-byte tag, read
unswapped by `fs_gdlReadInt_00035AA4`, with the parm's tag word ("ixn\0") from the USO Data.
port-gen-blob-types' access pass had typed those words u32 (they are loaded with `lw`), so the
blob build swapped them. No tag matched, and every Parms_load in genproc / bootup / game / heli /
snoweffects (330 tag words) skipped its records. The objects kept their ctor defaults: the
course labels, the SelectWin colours, the rider, board, camera and item parms.

Fix (d999a0486): `port-gen-blob-types.py` step 4c types a word that is lw-typed u32 and holds
three letters / digits + NUL as `str` (source `tag`). ItemMgr_Load drops its run-822 tag swap,
which had been matching the swapped ItemType tags; both sides are now in cartridge order.

The fix reaches well past the label:
- the course names change with DR (Crystal Lake -> Crystal Peak);
- the stat bars and headings take their colours, and "Ready" / "3" are red;
- **the camera is no longer NaN, and the 3D renders** (the title flyover, the lodge select
  room, the course). The smoke run reports camera NaN fields 0. agent-g, run 841: please
  re-check the projection on top of this.

**Other fixes:**
- **km/h readout** (game side): SpeedGadget_setSpeed's 10..99 and >= 100 arms called sprintf
  with no value. The ROM sets a2 = a1 once, in a delay slot, so i386 printed stack garbage
  ("12292108"). The C now passes a1 in every arm; the bytes are the same.
- **Options segfault** (MainOptions_buildMenu / mgr_initMatchRace): `*(s32 *)0xA0000284 ==
  0x240B17D7`, an IPL3 word in KSEG1. Under PORT the test compares `PORT_N64_WORD_A0000284`
  (port.h), taken to be the retail value. This is not verified on hardware; it enables the
  Replay row and the 4th course of the level-1 match race.
- **cfront layout misses:** viewrec_uso_ncc.cpp, viewrec_uso_ncc_2d0.cpp and
  nameent_uso_ncc.cpp declared `virtual`s, so g++ put its vptr at +0 and shifted every member
  by 4: the Options screen crashed in list_append. They now use port_cfront.h (`char *vptr`
  at +0x28, CF_V0 dispatchers).
- **main.c:** SIGSEGV / SIGBUS / SIGFPE / SIGILL now print `PORT: signal N at step S` and a
  backtrace, then exit 128 + N.

**Input scripts (port/host/):**

| script | what it covers |
|---|---|
| `title_idle.input` | no input: the title and the attract demo |
| `time_attack.input` | the race to the finish of the first 2000 steps |
| `options_tour.input` | DU wraps to Options; the rows; Records; back |
| `trick_attack.input` | DD timing not verified: it reached mode 3, Match Race |
| `match_race.input` | Match Race: level, rider, board (fresh dir) |
| `vs2p.input` | PADS 2; the split rider / board / course selects |

**Screen verdicts:**

| screen | verdict |
|---|---|
| title | OK |
| language | OK |
| main menu | OK (2P VS greyed with one pad) |
| select rider | name, flag and coloured stat bars OK; the rider model is 3D (now visible) |
| select board | board name, stats and the portrait box OK |
| course select | labels now follow the cursor |
| Ready / 3 | red, plausible |
| race HUD | time, damage bar, km/h and minimap OK |
| Options / Records | OK |
| 2P selects | OK |

**Open:**
- **GO!** is drawn dark maroon with a pink rim. Its sprite is RGBA32 (no TLUT), so a CI
  palette byte-order bug is ruled out; the colour comes from the texels or from prim / env. Not
  verified against hardware.
- **Match Race select crash (agent-c run 845's item 5): fixed.** In mode 3, app_launchGenProc loads
  genproc, charsel, charsps and charfir, but not charmap (+0x18 of the bootup Data 0xC510 path
  table). CourseList_createItem's cases 0 / 1 still take their charmap arm (MODE != 2), and the
  item loop always runs i = 0..7. The ROM jump table (genproc RoData 0x3C0) matches the C cases,
  and both mode reads are gInputMgr + 0x34.
  On the N64, uso_bindImports leaves an import from an unloaded exporter unresolved. The site's
  lui / addiu keep their in-place addend, which is 0, so PolyShape_ctor gets NULL and BasePolyShape
  skips the parse (`if (a2 != 0)`). The port's static XDATA handed out the unloaded blob instead.
  The fix is `port_uso_importData(file, addr)` (port/uso/uso.c: addr while the module is loaded,
  else NULL), applied to the 8 charmap sites through the CMAP() macro in timproc_uso_b5_D884.c.
  **Any other XDATA into a mode-optional USO has the same hazard.** match_race.input now reaches
  Select Level (Normal, 4 courses), the rider and the board.
- Contest and Training were not visited.

Contact sheet: the scratchpad's final846/sheet846.png.

### 9.5 FP environment

- **Boot.** `osInitialize` calls `__osSetFpcCsr(0x01000800)`: in the kernel at
  `src/kernel/kernel_000_ido53_2530.c:78`, and in game_libs' own copy at
  `src/game_libs/game_libs_ido53_6C484.c:93`. **FS = 1** (flush denormal results to zero), **EV = 1** (the
  invalid-operation trap is enabled) and **RM = 0** (round to nearest).
- **Threads.** Every thread gets the same FCSR: `osCreateThread` stores `context.fpcsr = 0x01000800`
  (`src/kernel/kernel_038.c:30`, `src/game_libs/game_libs_o1_6BF34.c:58`), and `__osDispatchThread`
  restores it with `ctc1` (`src/libultra/game_libs/dispatchthread.s:73`).
- **Nothing else changes the mode globally.** The ~230 other `cfc1` / `ctc1 $31` sites are IDO's
  float → unsigned conversion idiom, which temporarily sets RM = 1 (truncate) around `cvt.w.s` and then
  restores it. Examples: `Fader_display`, the gfx / gui colour packers and `AudioHeap_*`. That is C cast
  semantics, so a host compiler's cast is equivalent.
- **No FMA.** The VR4300 has no fused multiply-add.
- **Math functions.** `fsin` / `fcos` are libultra's own (`game_libs_ido53_6A144.c:34`), and `sqrtf` is the
  `sqrt.s` instruction (`src/libultra/game_libs/sqrtf.s`).

**Port flags:**
- SSE2 scalar math, including on the 32-bit build (`-msse2 -mfpmath=sse`; plain `-m32` defaults to x87,
  which is wrong);
- `-ffp-contract=off`;
- no `-ffast-math`;
- MXCSR FTZ = 1 and DAZ = 1 on the simulation thread, round to nearest;
- compile the game's own `fsin` / `fcos` and math helpers, and never call host libm for them.

Leave the invalid-op trap off on the host. A NaN that would have trapped on the N64 shows up as NaN in the
trace instead, which is easier to debug. IDO evaluates `double` literals and `(f64)` comparisons in real
double precision (for example `pad_update`'s `< 0.2`), and SSE2 doubles match that.

### 9.6 Scheduler design for port/main.c

1. **Fixed step: 30 Hz, decoupled from the display.**
   - `STEP = 1/30 s` by default. An "authentic" option uses 1001/30000 s (29.97 Hz).
   - The game measures nothing, so the step only sets real-time speed. The in-game clock stays 33 ms per
     step either way.
   - A PAL option (25 Hz) is not needed.
2. **Restructure `app_run` under `PORT`.** Its inner-loop body becomes `app_runOneFrame()`: pad_update for
   each pad → gfx_start → Update → Display → gfx_end → snd_FrameUpdate → frameCount++ → callback. The
   PreNMI test and the `flags & 4` yield also move into it. Keep the one pre-loop Update in an
   `app_runInit()`. The `main.c` loop is then:

   ```
   acc += now - last;
   while (acc >= STEP && steps < 4) {   /* catch-up cap */
       input_poll();
       app_runOneFrame();
       acc -= STEP;
       steps++;
   }
   present_latest_frame();
   ```

   Display and `gfx_end` must run **every** step, even when catching up, because `gfx_end` runs the
   MorphUpd / ADrawUpd updates and display code grabs the thumbnail every 4th frame. Only the host GPU
   submit of a skipped step may be dropped. In headless / trace mode the loop runs steps back to back with
   no sleeping.
3. **Retrace waits.** VI time is virtual, with 2 retraces per step:
   - `gfx_waitRetrace` under `PORT` does `rcp->retraceCount++` and returns;
   - `gfx_end`'s spin becomes a no-op, since `gfx_start` stored the count and the swap's wait advances it;
   - `osViSwapBuffer` → "frame ready" for the Fast3D backend.

   This keeps the counter's meaning (2 per frame), and `GfxLib_init`'s three waits terminate. Set
   `GfxLib.frameTime` to its NTSC value; that removes the "zero v frame time" warning. `RcpMgr_service`'s VI
   handler is not run:
   - the audio update moves to the host audio callback at the driver's refresh rate (60 Hz NTSC); this is
     decision 3;
   - pad requests become `input_poll()` once per step.
4. **Trace logger hooks** (port and emulator, keyed by `SysLib.frameCount` plus the pad `replayFrame`):
   - **input**, in `pad_update` after `pad_decodeButtonMap_00034CC8`: per pad, the full `held` and both raw
     stick bytes. These are logged on record and injected on replay;
   - **end of `app_runOneFrame`**:
     - the GameFlow state (InputMgr +0x40, next mode +0x34);
     - the RaceProcess `raceState` / flags;
     - each rider's `dnode` position and quaternion, speed and RiderAnim state;
     - the camera eye / target;
     - the DataManager `elapsed`;
     - `sys_randf`'s state (Data 0x21E04);
     - optionally the virtual `retraceCount`;
   - **excluded:** audio state, unless the deterministic `osGetCount` shim is on.
5. **High-fps rendering (M7).** Interpolate Node transforms between the last two steps at present time. The
   simulation stays at 30 Hz.

## 10. M0 results: extractor and audio

agent-c run 606. Extractor committed on agent-c (gate PASS); this section is uncommitted.

### 10.1 Extractor v0 (`port/tools/extract/extract.py`)

Python 3, standard library only. `python3 port/tools/extract/extract.py [--rom R] [--out D] [--no-write]`.
It refuses a ROM whose SHA-1 is not `79cd1166...5db3a` (US 1.0, tenshoe.yaml) unless `--skip-sha1`,
and a byte-swapped (.v64 / .n64) image. Default output `port/assets/extracted/` (gitignored, 34 MB, 0.6 s).
Tests: `python3 -m unittest discover -s port/tools/extract` (Yay0 unit tests always; the ROM test only
when baserom.z64 exists).

Output tree:
- `fs/<device>/<file>`: each file's raw record stream (Info .. End), as on the ROM. This is the ROM
  filesystem the port's `fs/` layer serves.
- `uso/<file>/NN_<Type>.bin`: every section of every USO, Yay0 decoded, big-endian, not swapped
  (NN = the record's position in the file).
- `bin/<file>`: the payload of each `rom/*.bin` (its BinaryDataSection), as-is.
- `manifest.json`: per file: name, device, path, kind (`uso-code` / `uso-data` / `bin`), module id,
  ROM and device offset, size, compressed flag, SHA-1, symbol / reloc counts; per section: type, ROM
  offset, record size, flag, compressed, decoded size (Bss: `bss_size`), SHA-1, output file.

**Results on the US ROM.** Self-check problems: 0.
- Devices are read from the kernel table (`k_gFsDevices`, ROM 0xAE60; name pointers are runtime
  addresses, ROM = ptr - 0x7FFFF400): mainuso 1 file, rom 130 files (each device also starts with a
  `<null>` id -1 entry).
- 131 files: 26 code USOs, 35 data-only USOs, 70 `.bin`.
  - Code USOs (have Text): bootup, boarder1-5, gui, n64proc, titproc, eddproc, mgrproc, arcproc, h2hproc,
    timproc, trkproc, trnproc, genproc, viewrec, nameent, game, balloon, heli, fire, checkpoint,
    snoweffects, and map5_data (Text 0xD0).
  - Data-only USOs: audio_bank / seq / wave, the 9 character banks (tahoe151 ... penguin), gamegfx,
    charsel / charsps / charfir / charmap, map1-4 / 6-10_data, bg1-8tex, effects.
- Module ids: 0-58, 60, 61, 63-132 (131 ids, unique). **All of 0-46 are present.** Ids 59 and 62 are
  not on the cartridge (the directory is contiguous, so nothing is skipped).
- 29 Yay0 sections in 23 files (0x26B466 -> 0x527330 bytes). Every one decodes to its Yay0 header size,
  its stream ends inside its record, and the output is identical to crunch64's.
- Every Sym value lies inside its section, and every Text / Data / RoData reloc offset lies inside its
  target section. That is the cross-check on the decoded sizes: the module records carry no separate
  uncompressed size (next point).

**Format corrections to USO_FORMAT sections 3 and 5** (verified by the walk; the doc should be fixed by
its owner):
- For a Yay0 record, `size` is the **compressed** record length (the next record starts at
  payload + size). The uncompressed size is only in the Yay0 header. The Yay0 stream can be 1 byte
  shorter than `size`, which is why the next header can be byte-misaligned.
- The "module header" `[0x12345678, 8, size, flag]` is not a header. The 0x12345678 is the last word of
  the Info record's 0x20-byte name field (stack garbage after the NUL), and `[8, size, flag]` is the
  module's **Bss record** (type 8, no payload). bootup: Bss 0x452A0. A file is simply Info followed by
  its section records up to End.
- The flag's low 16 bits are garbage too (0x6F00, 0x736F "so", 0x7573 "us" are leftover string bytes).
  The meaningful bits are 0x10000000 (a loaded section), 0x08000000 (metadata: Sym / relocs / Info /
  BinaryData), 0x20000000 (bootup's Text), 0x10000 (Yay0) and 1 (allocate).

### 10.2 Audio facts (open question "audio output rate and buffer size": answered)

All from the matched code: `AudioHeap_Init` (game_libs_post.c), `AudioLoad_Init`, `AudioThread_UpdateImpl`
(game_libs_o2_26214.c) and `RcpMgr_service` (game_libs_ncc_4D688.cpp).

- **Spec table** `gAudioSpecs` = bootup Data +0x1CC10, 8 x 0x38-byte specs. The spec in use is 0:
  `AudioLoad_Init` sets `specId = 0`, and the only reset callers pass 0 (`AudioThread_PreNMIInternal`,
  `snd_StopAudioCmds`). Spec 0: samplingFreq 32000, specUnk4 (updates per VI) 1, 20 notes, 3 sequence
  players, 2 reverbs. Spec 4 is the only 24000 Hz one; it is never selected.
- **Output rate:** `osAiSetFrequency(32000)`. The AI really runs at osViClock / dacRate: 32006 Hz on NTSC
  (dacRate 1521), 31995 Hz on PAL. **Host stream: 32000 Hz stereo s16.** The port can treat 32000 as exact.
  `refreshRate` = 60 (NTSC / MPAL) or 50 (PAL), from osTvType in `AudioLoad_Init`.
- **Samples per frame (NTSC):** samplesPerFrameTarget = (32000 / 60 + 15) & ~15 = **544**. min / max
  AI buffer length = **528 / 560** frames. updatesPerFrame = 560 / 208 + 1 = **3**. samplesPerUpdate =
  (544 / 3) & ~7 = **176** (min 168, max 184). PAL: 640, 624 / 656, 4 updates of 160.
  These are exactly SoH's numbers (`SAMPLES_HIGH 560`, `SAMPLES_LOW 528` in OTRGlobals.cpp).
- **Per-frame length:** aiBufLengths[i] = ((544 - samples still queued in the AI) + 0x80) & ~0xF) + 0x10,
  clamped to 528..560. That is AI-queue feedback; on PC, pick 528 or 560 from the host queue depth, as
  SoH does.
- **Buffers:** **3** AI buffers of **0xB00 bytes** (704 stereo frames; the max used is 560), allocated
  from the init pool. `osAiSetNextBuffer(aiBuffers[idx], len * 4)` queues the buffer of two updates ago
  (curAiBufIndex + 1 mod 3). Two RSP task / ABI command buffers alternate (`rspTaskIndex ^= 1`).
- **How the audio is driven: there is no audio thread.** `AudioThread_Update` runs inside the RcpMgr
  thread. `RcpMgr_ctor` binds the VI to message 'd' (100) with `osViSetEvent(q, 100, 1)`, so every
  retrace. On each 'd', `RcpMgr_service`:
  1. starts the audio task built on the previous retrace (`pend = cur`; if a gfx task is running it calls
     `osSpTaskYield`, and the 'e' (SP done) handler then loads the audio task and later resumes gfx with
     `osSpTaskYielded`);
  2. calls `snd_AudioUpdate` (-> `AudioThread_Update` -> `AudioThread_UpdateImpl`), which processes the
     audio command queue, sequences and notes, builds the next ABI list (`AudioSynth_Update`) and
     returns the task (`cur`);
  3. increments the retrace counter (+0x24), and on every second retrace sends 'd' to the client queue
     at +0x44: the 30 Hz game tick (section 9.1).

  So audio runs at the VI rate (60 Hz), one update per retrace, and its RSP work trails by one retrace.
  On PC: call the audio update once per 1/60 s from the host audio callback or the main loop, run the
  ABI on the CPU, and write `aiBufLengths[i]` stereo frames to the host stream.
- **Port gotcha:** `AudioThread_UpdateImpl` sets `gWaveSamples[8]` to `(u8 *)AudioThread_Update +
  (audioRandom & 0xFFF0)`. That is a noise waveform read from the **code** bytes. Under PORT, point it at
  a 4 KB copy of game_libs Text from 0x26xxx (from the extracted bootup Text), or at a random buffer.

### 10.3 CPU audio ABI: the SoH mixer vs 1080's command set

**Where it is:** Shipwright `soh/soh/mixer.c` / `mixer.h` (846 lines, read at HEAD cbfcd827,
2026-11-16). It descends from the sm64-port mixer.c. It is **not a command-list interpreter**: mixer.h
redefines the `aXxx(pkt, ...)` macros to call `aXxxImpl()` immediately, and SoH's audio_synthesis.c
uses those macros. Its state is `rspa` (a 0xC00-byte DMEM image based at 0x3C0, the ADPCM table, the
filter, the envelope state).

**1080's command set.** 1080's `AudioSynth_*` (game_libs 0x1C9E4-0x1F6B4) is OoT's synthesis.c with
OoT's ABI numbering and the same DMEM map (DMEM_TEMP 0x3C0, UNCOMPRESSED_NOTE 0x580, COMB_TEMP 0x760,
ADPCM / LEFT_CH 0x940, RIGHT_CH 0xAE0, WET 0x3E0 / 0xC80 / 0xE20). It emits these opcodes (the macros and
raw words in game_libs_post.c, and the wrapper functions that ProcessNote calls):

| op | 1080 builder | SoH Impl | notes |
|---:|---|---|---|
| 1 | aADPCMdec (flags, \|4 for CODEC_SMALL_ADPCM) | aADPCMdecImpl | 2-bit (flag 4) decode supported |
| 2 | aClearBuffer, AudioSynth_ClearBuffer | aClearBufferImpl | |
| 3 | AudioSynth_UnkCmd3 (bookOffset 2) | aUnkCmd3Impl | **no-op in SoH**; same as SoH plays OoT |
| 4 | aAddMixer | aAddMixerImpl | |
| 5 | raw 0x05 words (reverb resample, FinalResample) | aResampleImpl | |
| 6 | aResampleZoh | aResampleZohImpl | |
| 7 | AudioSynth_LoadFilterBuffer / LoadFilterSize (0x0702) | aFilterImpl | flags 2 = load filter |
| 8 | aSetBuffer, AudioSynth_SetBuffer, raw 0x08 | aSetBufferImpl | |
| 9 | aDuplicate | aDuplicateImpl | |
| 10 | aDMEMMove, AudioSynth_DMemMove | aDMEMMoveImpl | |
| 11 | aLoadADPCM | aLoadADPCMImpl | |
| 12 | aMix, AudioSynth_Mix, raw 0x0C | aMixImpl | |
| 13 | aInterleave | aInterleaveImpl | |
| 14 | AudioSynth_HiLoGain | aHiLoGainImpl | |
| 15 | aSetLoop | aSetLoopImpl | |
| 17 | AudioSynth_InterL | aInterlImpl | |
| 18 | aEnvSetup1, AudioSynth_EnvSetup1 | aEnvSetup1Impl | |
| 19 | aEnvMixer | aEnvMixerImpl | OoT bit layout (swap, 4 negate bits) |
| 20 | aLoadBuffer, AudioSynth_LoadBuffer | aLoadBufferImpl | |
| 21 | aSaveBuffer, AudioSynth_SaveBuffer | aSaveBufferImpl | |
| 22 | aEnvSetup2, AudioSynth_EnvSetup2 | aEnvSetup2Impl | |
| 23 | AudioSynth_S8Dec | aS8DecImpl | |
| 25 | AudioSynth_UnkCmd19 (bookOffset 3) | aUnkCmd19Impl | |

**Coverage: all 23 opcodes 1080 emits have an Impl in SoH's mixer.** No 1080 command is missing. The one
semantic gap is op 3, a no-op in SoH as in its OoT port. SoH also has aDMEMMove2 (16) and aOPUSdec; 1080
uses neither.

**Integration choice (for port/audio, M4).** The matched `AudioSynth_*` write raw Acmd words, including
K0-to-physical addresses (`ptr + 0x80000000`), so SoH's call-through macros cannot be dropped in as they
are. Two options:
1. **Recommended: a word interpreter.** A ~150-line `audio_abi_run(Acmd *list, int n)` decodes each
   word pair with the bit layouts of the 1080 macros above and calls the SoH `aXxxImpl`. Map a physical
   address back with `| 0x80000000` on the 32-bit build; on 64-bit (M6), give the PORT build a
   pointer-sized Acmd. `AudioThread_UpdateImpl` calls it instead of building the OSTask. This leaves
   the matched synthesis code untouched, and the command stream stays comparable with the emulator's
   (the M4 exit check).
2. Under PORT, replace each builder with SoH's macros. That needs a PORT body for every raw-word site
   (the 15 wrappers and the reverb / FinalResample raw words).

**Follow-up:** 1080 runs a 1998 aspMain. The ucode data image is at game_libs 0x31DF8 (0xF7C bytes).
Before trusting op-for-op equivalence with OoT's ucode, check ops 3 / 19 / 25 against an emulator
command-stream capture (M4 exit check). Licence: the Shipwright repo has no top-level LICENSE file, and
mixer.c comes from sm64-port. Settle the attribution before reusing it (section 8, "Legal").

## 11. M0 results: graphics coverage

> agent-b run 605, 2026-11-16, static (no emulator capture). Tool: `scripts/port-gbi-census.py` (agent-b
> 8be45c44e). It runs constant propagation over the exact ROM words of every function and lists each Gfx word
> pair the game stores. `--detail OPC` lists the sites. `--rom` / `--scan` search the ROM and every Yay0 blob
> for static lists that end in G_ENDDL. Each row below was then checked against the emitter's source.
> Comparison bases: libultraship 759b134 (2026-09-02, `src/fast/interpreter.cpp`) and sm64-port 2b17d08
> (`src/pc/gfx/gfx_pc.c` built with `F3DEX_GBI`). Clones are in /tmp/claude-1000/ext/ (not vendored).

**Summary.**
- The game uses 39 F3DEX 1.x opcodes, all as stock GBI 1 macros. Static data holds only two display lists.
  Everything else is built at run time.
- libultraship (LUS) handles all of them except **G_LINE3D**. It also has the framebuffer and depth read-back
  API that the game's five CPU-side buffer readers need.
- sm64-port's Fast3D misses about ten features the game relies on (11.3).
- **Recommendation: LUS** (11.5).

### 11.1 What the game emits

Static lists. The ROM, plus every one of the 29 Yay0 blobs once decompressed, holds exactly **two**:
- bootup Data at ROM 0xDC48C0 (`B6 -1; BB off; B7 SHADE|SMOOTH; B8`): the RSP init list;
- ROM 0xDC48E0 (15 commands): the RDP init list. It sets every othermode field: 1CYC, 1PRIMITIVE, TL_TILE,
  TT_NONE, TD_CLAMP, TP_PERSP, TF_BILERP, TC_FILT, CC SHADE, CK_NONE, AC_NONE, RM 0x0F0A4000 (OPA_SURF in
  both cycles) and CD 0.

gfx_initRDPState calls both lists through G_DL. Shapes, materials and sprites are compiled at run time:
materials and shapes into MainStaticDL, the rest into per-frame DLContexts.

Run-time emitters (opcode, GBI 1 name, emitters, notable parameters):

| op | name | emitted by | parameters / notes |
|---|---|---|---|
| 01 | G_MTX | PolyShape_display, U64BGWall_display, gfx_emitProjection, Shadow_display | `0x01020040` (modelview, LOAD, no push) and `0x01030040` (projection, LOAD). Shadow_display uses `(flags \| LOAD)`. There is **no G_POPMTX**: the matrix stack lives on the CPU (GRAPHICS 4) |
| 03 | G_MOVEMEM | ScreenWindow_display / dbg_screenOverlay (0x80 VIEWPORT), Mat_draw (0x82 / 0x84 LOOKATY / X, three each), gfx_emitLights / gfx_emitOneLight (0x86 / 0x88 L0 / L1) | length 0x10. LookAt feeds the texgen reflection materials. Vp is quarter-pixel (GRAPHICS 4) |
| 04 | G_VTX | PolyShape_emitTriBatch, gfx_emitLineBatch, U64BGWall_ctor | F3DEX 1 form `04 \| v0*2<<16 \| n<<10 \| n*16-1`. U64BGWall can load more than 32 vertices at once (n*4 per row band; check against the F3DEX 1.23 32-vertex buffer in M2). Both Fast3Ds hold 64 |
| 06 | G_DL | 13 functions (gfx_callStaticDL, PolyShape_display, Sprite_display, ScreenWindow_display, gfx_submitFrame, ...) | push form `0x06000000`. One branch, `0x06010000` (NOPUSH), in PolyShape_clipRows_00043D38 (below) |
| B3 / B4 | G_RDPHALF_2 / _1 | every TEXRECT site | F3DEX 1 `gSPTextureRectangle`: E4, then B4 (s, t), then B3 (dsdx, dtdy), back to back |
| B5 | **G_LINE3D** | gfx_emitLineBatch_000488A0 (line shapes) | `gSPLineW3D`: w1 = v0*2 << 16 \| v1*2 << 8 \| width; width 1 is emitted as 0 |
| B6 / B7 | G_CLEAR / SETGEOMETRYMODE | gfx_emitGeometryMode, gfx_initRDPState, gfx_setupMatTextures, gfx_drawText, U64BGWall_ctor, dbg overlay | clear -1, then set from ZBUFFER, SHADE, SHADING_SMOOTH, **CULL_FRONT** (mirror pass) / CULL_BACK, FOG, LIGHTING, **TEXTURE_GEN + TEXTURE_GEN_LINEAR** (0xC0000) |
| B8 | G_ENDDL | gfx_endDL, PolyShape_clipRows, U64BGWall_ctor | |
| B9 | G_SETOTHERMODE_L | gfx_emitRenderMode (table), Sprite_ctor, gfx_initRDPState, gfx_drawText, Fader, U64BGWall, gui | RENDERMODE `B900031D`; ZSRCSEL `B9000201` = **G_ZS_PRIM** for sprites; ALPHACOMPARE `B9000002 0` (AC_NONE, the only setting used). Render modes below |
| BA | G_SETOTHERMODE_H | gfx_emitCycleType, gfx_initRDPState, Sprite_ctor, gfx_loadTexture, gfx_drawText, Fader, gui | CYCLETYPE: 1CYC; **2CYC** for fog, multi-texture and the Fader; FILL for clears. Also TEXTPERSP, TEXTFILT (point for the font, else bilerp), TEXTLUT (NONE / RGBA16), TEXTLOD (TILE: **no mip-mapping**), ALPHADITHER, RGBDITHER (Fader: 0xC0, disable) |
| BB | G_TEXTURE | gfx_setupMatTextures (`BB040801`, level 1, plus a nonzero byte 16 that is ignorable), Sprite / gui / text (`BB000001 0x80008000`), off (`BB040000` / `BB000000`, w1 0xFFFFFFFF) | scale 1984 / 1984 (3968) under texgen (GRAPHICS 6.1) |
| BC | G_MOVEWORD | gfx_emitLights (NUMLIGHT `0x80000040` = 1 light + ambient), gfx_emitFog (FOG fm / fo), gfx_emitPerspNorm (PERSPNORM), gfx_initRDPState (SEGMENT 0 = 0; CLIP RNX / RNY / RPX / RPY = FRUSTRATIO_3) | segments are never used beyond seg 0 = 0 |
| BE | G_CULLDL | U64BGWall_ctor | per 64x32 background tile (vs..ve) and once for the head (0..3) |
| BF | G_TRI1 | PolyShape_emitTriBatch, U64BGWall_ctor | indices * 2 in w1. **No G_TRI2 / G_QUAD / G_MODIFYVTX / G_BRANCH_Z / G_LOAD_UCODE / G_POPMTX anywhere** |
| C0 | G_NOOP | PolyShape_init (placeholder rows), PolyShape_clipRows, gfx_emitPerspNorm (`C0000000 0x69`, a marker) | LUS reads byte 16 (0 here), so it is harmless |
| E4 | G_TEXRECT | Sprite_display, gfx_drawText, Fader_display, gui_* (6) | Sprite_display draws **billboard sprites as TEXRECT at G_SETPRIMDEPTH (EE)** with Z compare. Fader: full screen in 2-cycle |
| E6 / E7 / E8 / E9 | load / pipe / tile / full sync | everywhere | ignorable |
| ED | G_SETSCISSOR | gfx_clearScreen, gui_setScissor, dbg overlay | split-screen windows |
| EE | G_SETPRIMDEPTH | Sprite_display | `(z & 0x7FFF) << 16`, used with G_ZS_PRIM |
| F0 / F5 / F2 / F3 / F4 / FD | TLUT / tile / size / block / tile load / timg | gfx_loadTexture, U64BGWall_ctor, Fader, gfx_drawText, gui_loadTile* | formats RGBA32, RGBA16, IA8, I8, I4, CI8 + 256-entry RGBA16 TLUT at TMEM 0x100 (GRAPHICS 6.1). Loads use **LoadBlock as 16b with an 8b / 4b render tile**, and **LoadTile of a sub-rectangle at (uls, ult) != 0** (the image-record path, U64BGWall, gui). Multi-texture puts the second texture at TMEM != 0 (tile 1) |
| F6 / F7 / FE / FF | FILLRECT / SETFILLCOLOR / SETZIMG / SETCIMG | gfx_clearScreen, gfx_fillRect, gui_fillRect, gfx_setColorImage / setDepthImage | Z clear = CIMG pointed at the Z buffer, fill colour 0xFFFCFFFC, FILL mode. **Per window**, so split screen gets partial Z clears. CIMG / ZIMG w1 = `addr & 0xFFFFFF` |
| F8 / F9 / FA / FB | fog / blend / prim / env colour | gfx_emitFog, gfx_setBlendColour, gfx_initRDPState (blend 0x00FF00FA), gfx_drawText (blend 0x80), gfx_setPrimColour / emitStateAndPrimColour, gfx_setEnvColour, gui | blend colour is set, but alpha compare stays AC_NONE |
| FC | G_SETCOMBINE | gfx_emitCombine1 (13 modes), gfx_emitCombine2 (10), gfx_initRDPState, gfx_drawText, Fader, U64BGWall, gui (7) | inputs used: TEXEL0, **TEXEL1**, PRIM, SHADE, ENV, PRIM_ALPHA, **COMBINED**, 1, 0. Never NOISE, LOD_FRAC, K4 / K5 or key. 1-cycle modes are identical in both cycles. 2-cycle modes put COMBINED in cycle 2, except `FC257E04 1FFCF3F8` = lerp(T0, T1, PRIM_A), then * SHADE in cycle 2 (multi-texture), and the Fader's T0 colour with T1 (I8 mask) alpha |

**Render modes** (gfx_renderModeWord / gfx_renderMode2Word, 26 + 17 keys).
- 1-cycle words set **cycle-1 blender bits only**; cycle 2 stays 0. Examples:
  - AA_ZB_OPA_INTER 0x442478, RA_ZB_OPA_INTER 0x442438, AA_ZB_TEX_EDGE 0x443078;
  - AA_ZB_XLU_DECAL 0x404DD8, AA_ZB_XLU_INTER 0x4045D8, ZB_XLU 0x404A50;
  - XLU_SURF without Z 0x404240 (the gui).
- Fog is a 2-cycle mode: cycle 1 `G_RM_FOG_SHADE_A` (0xC8000000), cycle 2 the mode's "2" word.
- Multi-texture uses cycle 1 G_RM_PASS (0x0C080000).
- Three unusual cycle-1 blenders to verify against an LLE renderer:
  - mode flag 0x40000 gives 0x0C4C3078 (IN*0 + MEM*0, a Z-only / invisible write);
  - the mode bit 0x80 variants (keys 139 / 143 / 155 / 159 / 203) set P1 = MEM and B1 = 1 (MEM*A_IN + MEM*1).

  Their users are not identified yet.

**Self-modifying list.** PolyShape_clipRows_00043D38 rewrites rows of a compiled MainStaticDL list in place
every frame: hidden rows become G_NOOP, the head becomes a branch, a row becomes G_ENDDL. Fast3D re-interprets
each frame, so this works. It rules out any decoded-DL cache in the port.

### 11.2 Framebuffer and Z-buffer access from the CPU

Background for the table:
- Slot 11 of the ScreenWindow vtable is `ScreenWindow_getCurBuffer_0004D014` = `fbOwner->colorBuf[fbIndex]`.
  gfx_swapBuffer toggles fbIndex and then shows that buffer.
- So a reader in the Node update / display pass sees the last completed frame (at most 1-2 frames old) as
  320x240 RGBA5551.
- The format is 16-bit big-endian in N64 memory.

| site | reads | size / format | when | port mapping |
|---|---|---|---|---|
| **ScreenThumbMat_grab_0000E740** (bootup; slot 0 of a Mat in GfxLib.frameStartCbs, run by gfx_start) | mainWindow buffer: the 256x160 region at (32, 58), every 4th pixel and every 5th row | 64x32 RGBA16 texture (0x1000 bytes, wrap S / T) used as a material | every frame while board-model category 6 or 7 is loaded (SnowBoarder_loadBoardModel; probably CrystalGuy / MetalGuy, the reflective riders) | read back the region downscaled to 64x32 into `pix`. An async PBO with one frame of latency is fine. Then invalidate that texture address. Later optimisation: blit on the GPU into an FB texture and bind it when the Mat's texels address is loaded |
| **Fader_buildTexture** (bootup; Fader_display and the fade-start path) | mainWindow buffer at 1024 precomputed screen indices (`screenIdx[i]`) | 32x32 RGBA16 (`tex0`), drawn with a 32x32 I8 mask (`tex1`, CPU-made) as a full-screen 2-cycle TEXRECT | every frame while a fade is active | read back the last frame at 320x240 RGBA5551 (150 KB) once per frame while a Fader runs, and keep the CPU sampling as is. Invalidate tex0 / tex1 |
| **Tv1Tmpl_stepPicture_00007D04 + Tv1Tmpl_blitFrame_000077D0** (bootup "tv1" course item) | curWindow buffer: 64 columns (every 5th pixel). Rows every 3rd line, rolling with `scroll`, or random noise in state 1 | 64x32 RGBA16 into the two screen nodes' Mat texels | every step while a tv1 instance exists | same 320x240 read-back as the Fader (shared, one per frame). Invalidate both screen textures |
| **Sun_measureVisibility** (game_uso, a Sun PMF) | **Z buffer** (mainWindow->fbOwner->zBuffer): 9 pixels around the sun's projected position, counting `== 0xFFFC` (the clear value) | 9 x u16 | every frame per Sun | LUS `GetPixelDepthPrepare` / `GetPixelDepth`, the batched depth read SoH uses for the same lens-flare test. Scale 320x240 coordinates to the internal resolution. "Clear" means depth at the far plane |
| gfx_drawFbChar_00046790 / gfx_drawText (CPU-draw flag GfxLib +0x28C) | **writes** 8x8 glyphs (0xFFFE / 0) into the main buffer | 320-wide RGBA5551 | debug only: sys_sprintf_00061B30 and TextWin_draw(big) (HostIO consoles) | a CPU overlay buffer (320x240, 0 = transparent) composited before present. Low priority |
| gfx_clearFbRect_00043468 (gfx_fillRect CPU path) | **writes** a zero rectangle | as above | debug (CPU-draw flag) | same overlay |
| gfx_drawFbSplash_00048184 | **writes**: clears all 320x240, then blits a centred 128x128 image | RGBA5551 | no static caller found (boot or fatal path) | same overlay, shown full screen |
| GfxLib_hostioSendFbB_0004247C | reads the whole main buffer for hostio_sendImage (fmt 0x110) | 320x240 | HostIO only | drop, or reuse as a screenshot |
| Mat_fromFrameBuffer_0004F85C | makes a texture whose texels **are** a Window's colorBuf[0] (GPU render-to-texture) | window size, RGBA16 | no static caller found | when it is reached: windows that own buffers render into an LUS framebuffer (`SetFrameBuffer`). A G_SETTIMG of that buffer's address binds the FB texture (`SelectTextureFb`). Log it in M2 if it is ever called |

Port notes that apply to every row:
1. **Byte order.** The raw copies (ScreenThumbMat, Tv1, the Fader's palette remap) then go back to the GPU
   as RGBA16 textures, and the Fast3D importers read texels big-endian. So read-backs should produce the
   N64 memory image: big-endian RGBA5551, which LUS `ReadFramebufferToCPU` produces with `bswap`. The few
   sites that do arithmetic on pixels need a PORT swap:
   - Sun's `== 0xFFFC`;
   - the Fader's fill value 1;
   - drawFbChar's 0xFFFE.
2. **Texture cache.** LUS keys textures by address (palette by address too). Every CPU-rewritten texture
   above must call `TextureCacheDelete(addr)` (or `G_INVALTEXCACHE`) after its write. The general hook is
   `gfx_flushTexture`, the osWritebackDCache site.
3. **Resolution.** Every reader assumes 320x240. Read-backs downscale from the internal resolution, and Z
   lookups scale their coordinates up.
4. **Addresses.** G_SETCIMG / G_SETZIMG mask w1 to 24 bits. Under PORT, drop the mask in
   gfx_setColorImage / gfx_setDepthImage. The Z-clear test (`color image == z image`) works either way, but
   the FB-texture mapping needs real pointers. G_DL / G_VTX go through osVirtualToPhysical (identity). LUS
   treats odd w1 values as segmented; every w1 here is aligned.

### 11.3 Coverage: LUS vs sm64-port Fast3D, for an F3DEX (GBI 1) ucode

| feature 1080 uses | LUS (`ucode_f3dex` handlers + RDP table) | sm64-port gfx_pc.c (`F3DEX_GBI`) |
|---|---|---|
| G_VTX / G_TRI1 F3DEX 1 encodings, G_MTX, G_DL push / branch, G_ENDDL, othermode H / L, set / clear geometry mode | yes | yes |
| **G_LINE3D (0xB5)** | **no**: 0xB5 is registered as F3DEX `G_QUAD` (same opcode value), so lines are drawn as garbage triangles | **no**: dropped |
| G_CULLDL | stub (draws everything, correct) | dropped (correct) |
| G_MOVEMEM LOOKATX / Y (texgen reflection) | yes (lookat from movemem) | **no** (`#if 0`; a fixed lookat is used) |
| G_TEXTURE_GEN_LINEAR | yes | no |
| G_MOVEWORD NUMLIGHT (F3D form), FOG, SEGMENT; CLIP / PERSPNORM ignored | yes | NUMLIGHT / FOG only (segments unused, so that is fine) |
| TEXRECT + RDPHALF_1 / 2 | yes (consumes the next two words) | yes, but the RDPHALF_2 case falls through into G_SETTIMG (missing `break`) |
| G_SETPRIMDEPTH + G_ZS_PRIM (sprite billboards) | yes | **no** (sprites lose depth) |
| 2-cycle combiner, TEXEL1, COMBINED | yes | **cycle 1 only** (FC257E04 loses its * SHADE) |
| tile descriptors 0-7, second texture at TMEM != 0 | yes (8 tiles, 2 texture slots) | one tile descriptor (wrong clamp / mask / size for tile 1) |
| LoadTile with uls / ult != 0 (image records, BG wall, gui) | yes | **no** (`SUPPORT_CHECK(uls == 0)`) |
| LoadBlock 16b with an 8b / 4b render tile, CI8 + TLUT | yes | yes |
| fog: 2-cycle FOG_SHADE_A with G_MW_FOG | yes | yes |
| blend colour, partial (per-window) Z clear, scissor | yes | blend colour no; Z clears ignored (one glClear per frame) |
| decal (ZMODE_DEC), CULL_FRONT | yes | yes |
| "invisible" blender (IN*0 + MEM*...) | detected only in **cycle-2** bits; 1080 sets cycle 1 | no |
| framebuffer objects, FB as texture, CPU read-back, depth read-back | yes (`SetFrameBuffer`, `SelectTextureFb`, `ReadFramebufferToCPU`, `GetPixelDepth`) | no |
| texture cache invalidation | yes (`TextureCacheDelete`, `G_INVALTEXCACHE`) | no (address + format key, never invalidated) |
| 32-bit host / Gfx = 8 bytes | `F3DGfx {uintptr_t w0, w1}`: 8 bytes on 32-bit, so the game's lists can be read in place (decision 1) | `Gfx` is the game's own |

### 11.4 Things M2 must still confirm with a capture

- The ordering of the two cycles: 1080 relies on the 1-cycle blender reading cycle-1 bits only. Every
  translucent mode would be opaque otherwise, so this is near-certain. Check it once on ParaLLEl-RDP or
  angrylion.
- The three unusual blender words (11.1) and which shapes use them. The same for the line-shape assets
  (which objects draw G_LINE3D).
- U64BGWall's vertex count per G_VTX against the 32-entry buffer (11.1).
- Whether Mat_fromFrameBuffer and gfx_drawFbSplash are ever reached.

### 11.5 Recommendation: libultraship's Fast3D

Use **libultraship**, pinned to a commit, with its Fast3D interpreter selected as `ucode_f3dex`.
`RcpTask_setUcodeF3DEX` and F3DLP.Rej both map to it. The reasons:
- It already covers 38 of the game's 39 opcodes, the 2-cycle combiner, multi-tile TMEM, LoadTile
  sub-rectangles, prim depth, lookat texgen and partial Z clears.
- It is the only one of the two with the framebuffer, FB-texture and depth read-back APIs that the five CPU
  readers need (SoH and 2Ship use them for the same tricks).
- MIT licence: the libultraship and fast/ LICENSE files are both MIT.

Costs:
- C++20, plus the Ship framework dependencies (SDL2, spdlog, ImGui, the resource manager). port/gfx can drive
  the interpreter on raw pointers, as SoH does for code-built lists, without using the OTR resource paths.
- Fork it or patch it locally. sm64-port's gfx_pc.c is smaller and plain C, but it would need most of the
  LUS features re-implemented (11.3).

Renderer changes needed (an LUS fork or patch set, about 200-400 lines in all):
1. **G_LINE3D for the F3DEX table.** Give 1080 its own ucode entry, or a flag on `ucode_f3dex`, that maps
   0xB5 to a line handler. Draw a screen-space quad of width `max(1, wd / 2)` pixels, in F3DEX 1 half-pixel
   units, between two loaded vertices, with their colours.
2. **Blender detection in 1-cycle mode reads the cycle-1 fields:**
   - the `invisible` test;
   - the unusual 0x0C4C3078 / P1 = MEM words, after they are verified;
   - check `use_alpha` / `use_fog` against the 26 render-mode words above (a unit test over the table).
3. **A small read-back API for port/gfx:**
   - `gfx_readback_rgba5551(region, w, h, dst, big_endian)`: async, with one frame of latency;
   - `gfx_depth_at(x, y)` in N64 units (0xFFFC = clear).

   Both wrap `ReadFramebufferToCPU` / `GetPixelDepth`, keep the game's 320x240 coordinate space, and are
   called from PORT bodies of ScreenThumbMat_grab, Fader_buildTexture, Tv1Tmpl_stepPicture and
   Sun_measureVisibility.
4. **Texture-cache invalidation hooks:**
   - `gfx_flushTexture` and the CPU-written textures above call `TextureCacheDelete`;
   - palettes rewritten in place, if any, are covered by the same hook.
5. **A CPU overlay plane** for the debug framebuffer writers (drawFbChar / clearFbRect / drawFbSplash),
   composited before present. Optional for M2.
6. **Framebuffer registry (deferred):**
   - G_SETCIMG with a non-main window buffer starts an LUS framebuffer;
   - G_SETTIMG of a registered buffer address binds its texture.

   Needed only if Mat_fromFrameBuffer is reachable.
7. Game-side PORT edits (not renderer changes):
   - drop the 24-bit mask in gfx_setColorImage / gfx_setDepthImage;
   - byte-swap the constant pixel compares (11.2);
   - for M6 (64-bit), the emitters write 8-byte `{u32, u32}` Gfx through `base + n * 8`. Either give the
     PORT DLContext a pointer-sized Gfx (all the emitters in GRAPHICS 3 change), or keep every pointer the
     lists reference inside a 4 GB arena and let `SegAddr` add the arena base. The arena is less churn.

## 12. M0 results: source map and compile census

Run 604 (agent-a), on main 1ce4fd5f6. Tools: `scripts/port-sourcemap.py` and `scripts/port-compile-census.py`.
Output: `port/sourcemap.tsv` and `port/sourcemap-placeholders.tsv`. The census writes only to a scratch dir.

### 12.1 Source map (section 4.1 deliverable)

`scripts/port-sourcemap.py [--verify]` reads report.json (3288 functions in 191 units) and parses the Makefile
statically. It reads the global `VAR := ...` lines and the target-specific `REPLACE_FUNC_BODY` / `POST_COMPILE`
assignments on the matching `build/src/...` targets, plus the `objcopy --redefine-sym` lines in the explicit donor
recipes. The `--redefine-sym` forms include the `$$(nm ... __sti__)` static-initialiser idiom.

Each source file is then preprocessed with host cpp in the matching configuration (no NON_MATCHING, no PORT,
IDO-like predefines) and scanned for top-level definitions, including K&R and `extern "C" { }`, and for
`GLOBAL_ASM` includes. Donor chains are followed.

**Rows: one per function. 3288 rows, each function exactly once, 0 unresolved.**

| kind | how | functions |
|---|---|---:|
| c | plain (definition in its own unit) | 2740 |
| c | donor (-O0 / -O1 / -O2 split / IDO 5.3 .c) | 181 |
| cpp | donor (NCC `.cpp`) | 230 |
| c | import (`src/match_imports/`) | 94 |
| asm | asm (GLOBAL_ASM: 39 libultra .s = 20 game_libs copies + 18 os + 1 libc, and 4 handwritten kernel .s) | 43 |

- **Selected files:** 693 in total: 650 C / C++ files and 43 asm files.
- **Renames:**
  - 30 `.cpp` donors ship under an objcopy-renamed name. The cfront-mangled name is in the source, for example
    `__ct__1GFi` -> `CoolGadget_ctor` and `perp__3ObjF2V3T1` -> `math_projectOnPlaneNorm_00036694`. The port has
    to give these functions their shipped names under PORT, or alias them.
  - 1 C donor is renamed by POST_COMPILE (`osCreateMesgQueue` -> `gl_osCreateMesgQueue`).
  - 5 symbols are sub-symbols that `add-elf-func-symbol.py` cuts out of one C body, for example
    `gl_strchr_tail_0006F1FC` inside `gl_strchr`.
- **Verification (`--verify`, needs a full make):** for every row, the function's bytes in the object built from
  the mapped source are compared with expected/:
  - 2886 identical;
  - 369 identical except for relocated immediates (USO expected/ objects hold link-time values);
  - 29 identical except for zero padding (st_size includes the nop tail or pad);
  - 4 not named in expected/ (the timproc_uso_b5 `gen_streamRead*`);
  - **0 different.**

  So the map points at the shipped body everywhere it can be checked.

**Bodies the port must NOT compile** (`port/sourcemap-placeholders.tsv`, 3628 rows):

| host_body | rows | meaning |
|---|---:|---|
| c | 397 | host C placeholder, compiled in the matching build, then replaced by the splice |
| nm | 107 | the host has the body only as an `#ifdef NON_MATCHING` reference (a near-miss of the shipped code) |
| none | 1 | no body in the host (`tit_procMain`, shipped from titproc_uso_5DC.c) |
| extra | 3123 | another selected file also defines the function |

The `extra` rows break down as:
- 3091 come from 107 `src/match_imports/*.c` files. Each one includes a `context_*.h` with about 86 bodies of
  its segment.
- The rest are donor helper copies (for example `RcpMgr_*` in game_libs_ncc_4D688.cpp, `console_*` in
  match_imports/sys_fatal.c, `dbg_*` in game_libs_o2_34548.c) and the kernel / game_libs libultra twins under their
  C names.

**Consequence for the port build:** compiling whole files does not work. The port must compile each selected body
once, and exclude the placeholders and extras. There are two options:
- (a) a generated per-function include / `#if` guard (`PORT_BODY(fn)`) driven by sourcemap.tsv;
- (b) PORT-only split files that hold exactly the mapped bodies.

The match_imports files should be compiled against the real headers, not their context_*.h. The context headers
are m2c-style context dumps, and some contain asm-processor `_asmpp_large_func*` stubs.

### 12.2 Compile census (M0 "compile counts")

`scripts/port-compile-census.py [--extra FLAGS]` compiles the 650 selected C / C++ files. It uses gcc 11.4:
- C: `-m32 -c -std=gnu89 -DPORT -Iport/include -Iinclude -Isrc -I<dir>`;
- C++: `-std=gnu++98 -fpermissive -fno-exceptions -fno-rtti`.

The 43 asm files are not compiled; the libultra shim replaces them.

| flags | OK | failing |
|---|---:|---:|
| `-m32` | 585 (363 C + 222 C++) | 65 (all C) |
| `-m32 -malign-double` | 638 (416 C + 222 C++) | 12 (all C) |

Error categories (the counts are the same with and without `-malign-double`, except the layout row):

| category | errors | files | notes / example |
|---|---:|---:|---|
| struct layout asserts (i386 alignment) | 406 (0 with `-malign-double`) | 58 (0) | `include/libultra/os_thread.h:53` OSThread offset asserts. i386 aligns u64 / f64 to 4 in structs. **Use `-malign-double`** (or `aligned(8)` u64 / f64 typedefs under PORT) for the 32-bit build. |
| asm-processor / GLOBAL_ASM / pragma | 28 | 9 | Bare `GLOBAL_ASM("src/libultra/...s")` lines (the `#pragma GLOBAL_ASM` form is only a warning). The parser takes the next declaration as part of it, which cascades into errors such as `DqThread` / `__osExceptionVector` / `UsoSegDesc0` "unknown type". |
| IDO-specific syntax | 172 | 3 | 170 in `game_libs_ido53_6E224.c` (`_Printf`): IDO's `va_arg` uses `__builtin_classof`. 2 in kernel_018_f / g: a block-scope `extern s32 func_80008430();` after a prototyped file-scope declaration (IDO accepts the call with no arguments). |
| missing headers | 0 | 0 | |
| int / pointer | 0 | 0 | gcc 11 reports these only as warnings: 126 int-conversion, 52 incompatible-pointer-types, 2 int-to-pointer-cast. |
| C++ issues | 0 | 0 | **All 222 `.cpp` donors compile** with `-fpermissive`. |
| multiple definitions (compiled objects) | 284 symbols (125 without `-malign-double`, where fewer objects compile) | 318 | Breakdown below. |

The multiple-definition symbols break down as:
- 260 are shipped functions whose extra copies are all listed in sourcemap-placeholders.tsv;
- 22 are `_asmpp_large_func*` stubs from the match_imports context headers;
- 2 are other symbols: `Obj::run` in two NCC donors, and `gl_storage_66B64_threadRegion` defined in several
  match_imports files.

- **The 12 failures are all in kernel / libultra code:**
  - The 9 GLOBAL_ASM files are game_libs_post1b / 1b2c / 1c / 2b_d (mixed game + libultra-copy hosts) and
    kernel_000 / 000_b / 000_entry / 002 / 014. All 9 compile with 0 errors once `-D'GLOBAL_ASM(x)='` is added.
  - The other 3 are IDO-isms in libultra / rmon code (game_libs_ido53_6E224 `_Printf`, and kernel_018_f / g).
    Decision 6 drops those from the port anyway.

  So **every USO segment and the game_libs engine compile today with `-m32 -malign-double` plus an empty
  `GLOBAL_ASM`.**
- **Warnings worth tracking for M6:**
  - 11048 "variably modified at file scope": the offset-assert typedefs. gcc does not fold
    `(int)&((T*)0)->f` to a constant. Harmless in C, but these asserts should become `offsetof` under PORT.
  - the int / pointer warnings listed in the table above.
- **No shim headers were needed.** `port/include/` does not exist yet; the census already passes it as `-I`.

### 12.3 Next steps

1. **PORT_BODY selection:** generate the per-function guards from sourcemap.tsv, so that each function is
   compiled once. Re-run the census multi-def count: it should drop to the 2 non-report symbols.
2. **Port flags:** add `-malign-double` to the port flags. Under PORT, define `GLOBAL_ASM(x)` as empty, or drop
   the kernel and libultra hosts per decision 6.
3. **CMake skeleton:** consume sourcemap.tsv (cmake via `pip install cmake` in a venv; there is no system cmake
   or 32-bit link here).
4. **Names:** give the 30 renamed `.cpp` donors their shipped names under PORT (`extern "C"` wrappers or
   `asm` labels).

## 13. M1: build skeleton

Run 608 (agent-a), on main a0e51fe6b. This builds on section 12. Files:
- `scripts/port-gen-build.py` (generator);
- `port/tools/cc-select.py` (compiler launcher);
- `port/CMakeLists.txt`, `port/main.c` (empty `main`), `port/include/port.h`;
- generated: `port/gen/sources.cmake`, `port/gen/tu/*.h`, `port/gen/excluded.tsv`;
- `scripts/port-undefined.py`, which writes `port/undefined.txt`.

src/ is untouched, and the gate passes.

```
scripts/port-sourcemap.py && scripts/port-gen-build.py
cmake -S port -B <build> -G Ninja && cmake --build <build>      # -> libgame.a
scripts/port-undefined.py <build>/libgame.a                       # selection check + port/undefined.txt
```

### 13.1 Per-function selection (12.3 step 1): at the assembly level, src/ untouched

`port-sourcemap.py` now writes a 7th column `note` holding the rename / sub-symbol information.
`port-gen-build.py` turns the source map into one forced-include header per translation unit that
needs one: 153 of the 462 units, in `port/gen/tu/<src path with / -> __>.h`. Each header has:
- `#pragma weak SYM` for every body this unit must not supply. gcc then treats the placeholder as
  interposable, so it never inlines it, clones it or propagates IPA facts from it.
- `/* port-drop: SYM */` directives. `cc-select.py` is set as `CMAKE_<LANG>_COMPILER_LAUNCHER`. It
  compiles such a unit with `-S`, renames the unit's own definition of SYM to a local
  `__port_dead_SYM`, drops its `.weak`, and assembles the result. Every reference in the unit keeps
  the name SYM and binds at link time to the one shipped body. The dead copy is unreferenced, and
  `--gc-sections` drops it. Units without a header compile unchanged.
- `/* port-alias: NEW TARGET */` for the C++ renames, and `/* port-noinit */` / `/* port-local */`
  (below).

Why not the alternatives:
- `PORT_SKIP_<fn>` guards in src/ would mean about 3400 edits.
- objcopy cannot do it. `--strip-symbol` / `--remove-section` refuse a symbol that relocations
  name, and `--redefine-sym` also renames the unit's references.

| drop reason | bodies |
|---|---:|
| helper copy (`extra`: match_imports context headers, donor helpers) | 3110 |
| host placeholder (`c`) | 295 |
| an excluded function inside a kept unit (13.2) | 6 |
| **total** | 3411 |

The other two directive kinds:
- **`port-local`:** the 1242 asm-processor `_asmpp_large_func*` stubs in the match_imports context
  headers are made file-local. They cannot be dropped: gcc's ICF folds them into tail calls to one
  another.
- **Tentative definitions:** `gl_storage_66B64_threadRegion`, defined in 7 match_imports units, is
  merged by `-fcommon`. This matches IDO's common-symbol semantics.

**The 31 renames** (30 cfront-mangled C++ donors plus `intern`) become global aliases (`.set NEW,
TARGET`). The generator finds TARGET by compiling the donor with g++ and matching the cfront name
`meth__<n>Class...` against the demangled gcc symbols. A constructor maps to its C1 symbol, for
example `__ct__1GFi` -> `_ZN1GC1Ei` = `CoolGadget_ctor`.
- A mangled TARGET is made local. Several donors each define their own `Obj` class, so
  `_ZN3Obj3runEv` appears in both `RcpMgr_service` and `ScreenWindow_display`.
- The 4 `__sti__` static initialisers map to gcc's `_GLOBAL__sub_I_*`:
  - `app_staticInit_000412E8`
  - `Window_staticInit`
  - `boot_staticInit_00006204`
  - `SnowBoard_staticCtor_0000E9FC`

  Their `.init_array` entry is removed (`port-noinit`), so they run when port/uso "loads" the
  module (decision 4), not before `main`.

### 13.2 What is compiled

The source map has 3288 functions. The port compiles **2931 of them, from 462 files (243 C, 219
C++)**. `port/gen/excluded.tsv` lists the 357 it does not compile (decision 6):

| excluded | functions | provided by |
|---|---:|---|
| kernel segment (libultra core, USO loader, ROM fs, rmon) | 174 | port/ultra, port/uso, port/fs |
| game_libs libultra copies (`gl_os*`, `__osPfs*`, `__ll_*`, ...) | 126 | port/ultra |
| asm (GLOBAL_ASM .s) | 43 | port/ultra / libm (`sqrtf`, `bcopy`, cache ops) |
| game_libs libc copies (`_Printf`, `gl_sprintf`, `memcpy`, `strchr`, ...) | 14 | host libc wrappers |

The gu functions (`guMtxF2L`, `guOrtho`, `guPosition`, `fsin` / `fcos`) are kept, per 4.3.

**Flags** (`port/CMakeLists.txt`):
- common: `-m32 -malign-double -msse2 -mfpmath=sse -ffp-contract=off -fno-strict-aliasing -fno-pie
  -fno-stack-protector -ffunction-sections -fdata-sections -DPORT -include port/include/port.h`;
- C: `-std=gnu89 -fcommon`;
- C++: `-std=gnu++98 -fpermissive -fno-exceptions -fno-rtti`.

Notes on the flags:
- `port.h` defines an empty `GLOBAL_ASM(x)`. CMake drops function-like `-D` definitions.
- `-fno-stack-protector` is needed because Ubuntu's gcc otherwise adds `__stack_chk_fail` (534
  references).
- `-fno-pie` matches a `-no-pie` link.
- `PORT_LINK=ON` adds the `tenshoe` executable: `port/main.c` plus `--whole-archive libgame.a` and
  `--gc-sections`. It needs a 32-bit libc: gcc-multilib, or the no-sudo sysroot in 13.5.

**Result (gcc 11.4, cmake 4.4.5 + ninja from a uv venv):**
- **462 / 462 objects built, 0 compile failures**, giving `libgame.a`.
- `port-undefined.py` checks the selection against the archive:
  - all 2931 kept functions are present: 2897 are defined exactly once as globals, and 34 are
    `static` in their source and are local or inlined (the `stream_read*` / `fs_gdlRead*_mgr`
    readers);
  - 0 kept functions are missing or defined twice;
  - 0 excluded functions are defined;
  - **0 global symbols are defined twice** (2920 globals).

### 13.3 What libgame.a needs from outside: `port/undefined.txt`

`port-undefined.py` computes the list with `ld -m elf_i386 -r --gc-sections --gc-keep-exported
--whole-archive` (no 32-bit libc needed). Every exported symbol is a root, so the dead placeholder
copies drop out. Each undefined symbol is listed with whether it is referenced as a call, as data,
or both.

| group | symbols | call / data |
|---|---:|---|
| USO / CALL plumbing: import and placeholder call targets (`gl_func_*`, `*_import_*`, `gl_ref_*`, `<seg>_func_*`) | 917 | 801 / 116 |
| USO / CALL plumbing: match_imports binding names (`scripts/match-bindings-*.json` renames) | 603 | 264 / 339 |
| data aliases (`undefined_syms_auto.txt` `= 0`, `D_*` / `DF_*` / `DS_*`, `*_vtbl_*`, per-site aliases) | 2125 | 0 / 2125 |
| libultra os* | 3 | data (`gl_osViModeTable_*`, `gl___osActiveQueue_*` aliases) |
| gu* | 0 | |
| libc | 3 | `memcpy`, `memmove`, `memset` (calls) |
| other: C++ cross-donor references | 40 | ctors of mirror classes such as `SnowChaseActor::SnowChaseActor(char*, char*, char*)` and `BB::BB(void*)` |
| other | 8 | `glv_2a44`, the `tim_imp_*` / `trk_imp_*` import aliases, `timproc_uso_b5_func_06970C_i` |
| **total** | **3699** | |

What this shows:
- **The game reaches libultra only through placeholders today.** `CALL(gl_osRecvMesg)` expands to
  `gl_func_00000000`, so no `os*` call is visible in the object files. Counting the `CALL` / `XCALL`
  names in the compiled sources gives the shim's real surface: **69 excluded functions**.
  - 59 libultra:
    - messages / threads: `gl_osSendMesg` / `RecvMesg` / `CreateMesgQueue` / `SetEventMesg` /
      `CreateThread` / `StartThread` / `SetThreadPri` / `YieldThread`, plus the
      `__osDequeueThread` / `__osPopThread` / `__osDispatchThread` asm;
    - PI / EPI DMA, plus `osCartRomInit` / `osDriveRomInit`;
    - SI / controller: `osContInit` / `StartReadData` / `GetReadData`, `osPfsInitPak` /
      `osPfsIsPlug`, `osMotorInit` / `Start` / `Stop`;
    - SP tasks: `osSpTaskLoad` / `StartGo` / `Yield` / `Yielded`;
    - VI: `osCreateViManager`, `osViSetMode` / `SetEvent` / `SwapBuffer` / `Black` /
      `SetSpecialFeatures` / `SetX/YScale` / `GetCurrentLine` / `GetCurrentField`;
    - `osAiSetFrequency`, `osGetTime`, `osSetTimer`, `gl_osVirtualToPhysical`, `osInitialize`,
      `gl_rmonPrintf`.
  - 3 libc: `_Printf`, `gl_sprintf`, `memcpy`.
  - 7 asm: `bcopy`, the cache invalidates, `__osRestoreInt`, `sqrtf`.

  The other 1164 `CALL` names are game functions that the library already defines.
- **Turning CALL into names is the next M1 step, and it is the plumbing work.** Decision 4 says
  `CALL(f)` -> `f`. Measured with a forced-include `uso_call.h` replacement (`CALL(f) f`,
  `XCALL(tok, f) f`): **136 of the 462 units then fail.**
  - C++: 118 units. The callees are undeclared, because the NCC donors avoid `-I include`. Examples:
    `mem_new`, `sys_fatal`, `dbg_printf`, `math_vec3Normalize`.
  - C: 18 units, 157 errors. The errors are 90 "too many / too few arguments", 34 "conflicting
    types", and 25 "void value not ignored": K&R placeholder calls against real prototypes, as the
    section 13.2 caveat in USO_FORMAT.md predicts.

  Fixing these needs PORT prototypes per callee, plus an `#ifdef PORT` in `include/uso_call.h`.
  Once CALL expands to names, the 917 + 603 plumbing symbols mostly collapse into references the
  library already defines.
- **Data is the biggest group.** There are 2125 data aliases plus the data halves of the plumbing
  groups. The game's initialised data lives in the asm data sections, which the port does not
  compile, and every per-site alias is `= 0` in the matching link. Each alias needs a real
  definition in its owning module, as USO_FORMAT 13.2 describes under "Linker aliases":
  `uso-imports.py sites <module> --imports` names the owner.
  - Option 1: emit the data sections as C / binary objects in M1, with the extractor providing the
    initial bytes.
  - Option 2: generate an alias table (`--defsym alias=owner+off`) from the USO relocations.

### 13.4 Next steps (M1)

1. **CALL -> names:** add `#ifdef PORT` to `include/uso_call.h`, and give the 118 C++ units the real
   headers or prototypes under PORT. Then fix the 157 C prototype conflicts and re-run
   `port-undefined.py`.
2. **Data:** decide between data sections as objects and an alias table, then generate the
   definitions for the 2125 aliases and the data-side plumbing.
3. **Shim surface:** the 69 functions above, plus `memcpy` / `memmove` / `memset` from host libc.
4. **C++ cross-donor references (40):** map each mirror-class constructor or method to the shipped
   C symbol (`extern "C"` declarations under PORT), or alias it at link time.
5. **Link:** build with `-DPORT_LINK=ON` (toolchain in 13.5). The link errors should then equal
   `port/undefined.txt`.

### 13.5 Linking without gcc-multilib: the i386 sysroot (runs 807 / 808)

Linking (`PORT_LINK=ON`, the shim tests) needs a 32-bit libc, libgcc and libstdc++. With root that
is `sudo apt install gcc-multilib g++-multilib`, and the plain commands above work. Without root,
run `scripts/setup-i386-sysroot.sh` in the monorepo (idempotent, about 10 s and 9 MB). It
`apt-get download`s `libc6-i386 libc6-dev-i386 lib32gcc-s1 lib32gcc-11-dev lib32stdc++6
lib32stdc++-11-dev lib32quadmath0 lib32atomic1` (the gcc major follows the host gcc), unpacks
them with `dpkg -x` into `tools/i386-sysroot/root/`, fixes them up (usrmerge `lib32 -> usr/lib32`,
absolute symlinks made relative, the `libc.so` ld script pointed into the tree, an in-tree
`lib/ld-linux.so.2`), writes the `gcc32` / `g++32` / `run32` wrappers and `toolchain-i386.cmake`,
creates `tools/cmake-venv/` (cmake + ninja) if missing, and self-tests a C, a C++ (iostream,
exceptions) and a `-static` hello world plus a cmake + ninja build. Then:
```
PATH=<monorepo>/tools/cmake-venv/bin:$PATH cmake -S port -B <build> -G Ninja -DPORT_LINK=ON \
    -DCMAKE_TOOLCHAIN_FILE=<monorepo>/tools/i386-sysroot/toolchain-i386.cmake
cmake --build <build>
<monorepo>/tools/i386-sysroot/run32 <build>/tenshoe        # or any test binary
```
The binaries' interpreter `/lib/ld-linux.so.2` does not exist on a non-multilib host, so they run
through `run32` (the toolchain sets it as `CMAKE_CROSSCOMPILING_EMULATOR`, so ctest uses it too),
or are linked with `-static`, or with `-Wl,--dynamic-linker=<sysroot>/root/usr/lib32/ld-linux.so.2
-Wl,-rpath,<sysroot>/root/usr/lib32 -Wl,--disable-new-dtags` to run directly. The `libc.so` script
holds absolute paths, so after moving the sysroot rerun the script with `FORCE=1`. In run 807 the
port configured and built with it; `test_ultra` and `test_fs` linked and passed under `run32`, and
`tenshoe` failed only on 81 game-side undefined symbols (no libc / libm / libgcc gaps).

## 14. M2 prep: libultraship patch series

> agent-b, run 611, 2026-11-16. The patches are in `port/third_party/libultraship-patches/` (README: the pin,
> what each patch does, how it was checked). How LUS is pulled in, and its licence, are in
> `port/third_party/README.md`.

**Pin:** libultraship `759b13401cd6903daa67a00a753066f791622e78` (2026-09-02, the commit section 11 was
measured against). Decision: a **git submodule** at `port/third_party/libultraship`, kept pristine, with the
series applied by the port's CMake at configure time. `FetchContent` with `PATCH_COMMAND` is the documented
fallback. The submodule is not added yet; the command is in `port/third_party/README.md`.

### 14.1 The series (renderer changes 1-4 of 11.5)

The four patches change only `src/fast/` and `include/fast/`, adding 260 lines and removing 10.

| # | patch | 11.5 item | API for port/gfx |
|---|---|---|---|
| 1 | G_LINE3D for F3DEX 1.x | 1 | `gfx_set_target_ucode(ucode_f3dex_line3d)`: the F3DEX table with 0xB5 decoded as G_LINE3D. `GfxSpLine3D` draws a screen-space quad 1.5 + wd / 2 native pixels thick (the gbi.h definition), never culled |
| 2 | 1-cycle blender reads the cycle 1 fields | 2 (invisible test only) | none. 0x0C4C3078 becomes a Z-only draw; the other 37 render words are unchanged (tested) |
| 3 | deferred read-back | 3 | `gfx_readback_rgba5551(x, y, w, h, dst, bswap)`, `gfx_readback_depth_request(x, y)`, `gfx_readback_depth_get(x, y, &z)` |
| 4 | texture-cache invalidation | 4 | `gfx_texture_cache_invalidate_range(addr, size)`, `gfx_texture_cache_delete(addr)` |

**Read-back semantics (patch 3).**
- A request is queued before `Run()` and served at the end of that `Run()`, after the frame is drawn and before
  it is resolved or presented.
- The data is therefore the frame just rendered, ready for the next update. That is one frame of latency, the
  same as the N64, where a reader sees the last completed buffer (11.2).
- The colour comes from the native-aspect centre of the game view, blitted down to 320x240 (nearest) and read
  as RGBA5551. With `bswap` it is stored big-endian, like the N64 framebuffer image.
- Depth is batched into one `GetPixelDepth` per frame. Its units put the far / cleared value at **0xFFFC**, so
  Sun_measureVisibility's `== 0xFFFC` test works on the returned value with no N64 depth encoding, as long as
  the PORT body compares the value it got back, not a byte-swapped buffer.

**Port-side callers (PORT bodies, M2):**

| site | call |
|---|---|
| ScreenThumbMat_grab | Read rows 58..217 (every 5th) and columns 32..287 (every 4th) through one `gfx_readback_rgba5551(32, 58, 256, 160, tmp, 1)` request, sampled on the CPU as before. Then `gfx_texture_cache_invalidate_range(pix, 0x1000)` |
| Fader_buildTexture, Tv1Tmpl_stepPicture / blitFrame | One shared full-frame request, `gfx_readback_rgba5551(0, 0, 320, 240, fb, 1)`, per frame while either is live. The CPU sampling code is unchanged. Invalidate tex0 / tex1 and the two Tv1 screen textures |
| Sun_measureVisibility | 9 x `gfx_readback_depth_request`; read last frame's answers with `gfx_readback_depth_get` (miss = treat as not visible) |
| gfx_flushTexture | `gfx_texture_cache_invalidate_range(addr, size)`: the general hook at the osWritebackDCache site |

### 14.2 Verification (run 611)

What was checked:
- `git am` of the series onto a fresh clone at the pin applies cleanly and reproduces the development tree.
- `interpreter.cpp` compiles to an object with g++ 11.4 `-std=c++20 -Wall -Wextra` after each patch. There are
  no new warnings against the unpatched file.
  - The compile used local header-only copies of json, spdlog and ImGui, plus two stubs.
  - LUS's real dependency set (SDL3, tinyxml2, ...) is not installed here.
- `check_logic.cpp` (in the patch directory) tests copies of the new expressions:
  - the blender test over all 38 render-mode constants;
  - the G_LINE3D decode;
  - the line thickness and parallelism under perspective (w != 1);
  - the region clip and big-endian store;
  - the invalidation range.

What could not be checked:
- Nothing was linked or rendered.
- `DisplayListFactory.cpp` (patch 1 adds one `case` label) was not compiled, because tinyxml2 is missing.
- No `-m32` C++ build: the host has no 32-bit libstdc++.

### 14.3 Open items

1. **What does real hardware do with 0xB5 under F3DEX 1.23?**
   - LUS registers 0xB5 as G_QUAD for its F3DEX table, which is how the F3DEX tri microcodes read that opcode.
     L3DEX, the line microcode, reads it as G_LINE3D.
   - 1080 only ever loads F3DEX or F3DLP.Rej (GRAPHICS 5); no L3DEX setter exists. So on the N64,
     gfx_emitLineBatch's packets may draw as quads (byte 24 = 0, v0, v1, wd / 2), that is, as garbage
     triangles, or the line shapes may never be drawn in retail.
   - This turns the 11.4 item "which objects draw G_LINE3D" into a gate for patch 1. Capture it on ParaLLEl-RDP:
     - if lines appear, keep `ucode_f3dex_line3d`;
     - if they never appear, select plain `ucode_f3dex` and drop patch 1;
     - if they are drawn as quads on hardware, also select `ucode_f3dex` (faithful).
2. **Line near clip.** GfxSpLine3D drops a line with an endpoint at w <= 0. Real L3DEX clips. Fix this only if
   item 1 keeps the patch and a capture shows lines crossing the near plane.
3. **Read-back orientation and alpha.**
   - Row 0 = top was reasoned from the GL `invertY` flags, as in SoH's `gN64ResFrameBuffer` path. It was not
     run, and D3D11 / Metal are unchecked.
   - `ReadFramebufferToCPU` sets the 5551 alpha bit from the destination alpha. Where the game reuses a
     read-back as an RGBA16 texture with alpha (ScreenThumbMat), the port may need to force bit 0 to 1.
     Confirm against a capture.
4. **Read-back cost.**
   - The read is a synchronous `glReadPixels` of 320x240 at the end of the frame, only on frames that queued a
     request.
   - If profiling shows a stall, switch to a PBO ring. That moves to two frames of latency, still invisible for
     a 64x32 thumbnail.
   - Later optimisation: render ScreenThumbMat on the GPU through LUS's existing `RegisterFbTexture`
     (11.2 table).
5. **Threading.** Read-back results are written into game memory at the end of `Run()`. That is safe with the
   single simulation thread of decision 5. A separate render thread would need a hand-off.
6. **The other blender words (11.1):** the `P1 = MEM, B1 = 1` variants and the 26 + 17-word `use_alpha` /
   `use_fog` check. Patch 2 only fixes the invisible test. Extend it once a capture shows which shapes use
   these words.
7. **Deferred renderer items 5-6 of 11.5** (the CPU overlay plane, the framebuffer registry for
   Mat_fromFrameBuffer). They are not in this series.
8. **Dependency licences.** LUS is MIT (two notices to ship; see `port/third_party/README.md`).
   - Keep `ENABLE_SCRIPTING` off, because TinyCC is LGPL.
   - prism-processor's licence is not yet checked.

## 15. M1: audio mixer

agent-c run 609. Code committed on agent-c (24289f7dc, plus a2c82424e for comments only; gate PASS on both); this section is uncommitted.
Run 616 (wiring, byte order, gWaveSamples[8]) is 15.6.
It carries out decision 3: our own mixer, and no SoH / sm64-port code. SoH's mixer.c was read only to
cross-check behaviour, and where it disagrees with 1080's ucode the ucode wins (15.3).

### 15.1 What is in `port/audio/`

| file | contents |
|---|---|
| `mixer.h` / `mixer.c` | `Mixer`: 4 KB DMEM image plus the ucode's non-DMEM state (SETBUFF in / out / count, codebook, loop address, filter count and coefficients, the envelope lanes and rates), a host `translate(addr)` for command-word addresses, and diagnostic counters. One `mix_*` function per opcode. The resample LUT is the 64 x 4 table from 1080's own ucode data image. |
| `abi_decode.c` | `mixer_exec(w0, w1)` decodes one command with the bit layouts of 1080's builders (game_libs_post.c macros and AudioSynth_* wrappers, which are OoT's abi.h). `audio_abi_run(m, words, n)` walks a list. Opcode = `(w0 >> 24) & 0x7F`, as the ucode indexes it. |
| `test_mixer.c`, `Makefile` | `make -C port/audio test` (C99, no dependencies, 64-bit host). |

**Model.** DMEM is a byte array. s16 data in it is in host byte order (memcpy in and out), so the
game's s16 buffers (AI buffers, reverb rings, ADPCM / resample / filter states, wave tables) move through
LOADBUFF / SAVEBUFF unchanged. Byte streams (VADPCM frames, S8 samples) are read byte by byte and stay in
ROM byte order. **Integration requirement:** codebooks and filter coefficients must be host-order s16, so
the font loader swaps them (the test does this for the book it loads). Addresses are passed to
`translate` whole: the ucode masks them to 24 bits, but a host pointer would not survive that.

### 15.2 1080's aspMain, located and disassembled

To check the uncertain opcodes I disassembled the game's own ucode (scalar ops with
mips-linux-gnu-objdump, vector ops and LWC2 / SWC2 with a small decoder in the scratchpad).
- **Text:** ROM 0xE16EDC, 0xF70 bytes, loaded at IMEM 0x1000. The splat blob
  `game_libs_rsp_ucode_31DF8` starts 0xC bytes early (3 zero words), so `aspMainTextStart` =
  game_libs 0x31E04. `AudioThread_UpdateImpl` uses it as both `ucode_boot` (size 0x1000) and `ucode`.
- **Data image:** ROM 0xDBF730 = bootup Data +0x1D340, 0x2E0 bytes. It contains:
  - DMEM 0x00 constants (0, 1, 2, -1, 0x20, 0x800, 0x7FFF, 0x4000);
  - DMEM 0x10 the jump table;
  - 0x40.. nibble masks, one-hot lane selectors, and the resample LUT at 0xE0.
  The "7 aspMain variants" in tenshoe.yaml's bootup_uso_ucodes comment are gfx ucodes ("RSP SW Version
  2.0D / 2.0H" with the SGI gfx team string). The audio data is this one.
- **Dispatch:** at IMEM 0x1068: `lh v0, 0x10((w0 >> 23) & 0xFE); jr v0`. **The table has 24 entries
  (ops 0-23).** Handlers are listed in 15.3. Op 16's handler (0x1780) is never emitted.

### 15.3 Opcodes

V = verified against the 1080 ucode handler; P = implemented from the documented ABI and the OoT usage,
not yet checked against the ucode. "do-while" means the ucode always runs at least one block, so a
count is rounded up to the block size and a 0 count still does one block (except where noted).

| op | name | ucode | status | behaviour (where it is not obvious) |
|---:|---|---|---|---|
| 1 | ADPCM | 0x122C | P | 16 history samples written first (zero / loop state / saved state), then 32 output bytes per 9-byte frame (5-byte with flag 4); order-2 VADPCM, Q11, truncating `>> 11`, clamp |
| 2 | CLEARBUFF | 0x1148 | V | count 0 = nothing; else 16-byte blocks |
| 3 | UNK3 | 0x1EE8 | V | **not a no-op** (SoH: no-op). Per 16 samples, x = A[k] signed, y = A[8+k] **unsigned**: B[8+k] = low16(y·x) (VMUDN), B[k] = VMADN-clamp(2·y·x). VMADN-clamp: ACC[15:0] if ACC >> 16 fits s16, else 0 (negative) / 0xFFFF (positive). Do-while, 32 bytes |
| 4 | ADDMIXER | 0x1DFC | V | saturating add; the 0x7FFF in w0 is ignored; do-while 64 bytes |
| 5 | RESAMPLE | 0x14F0 | V (taps) | each tap is a VMULF ((2ab + 0x8000) >> 16), then **pairwise** saturating VADDs: sat(sat(t0+t1) + sat(t2+t3)). LUT row = fraction >> 10; step pitch·2 in Q16. State: 4 samples + fraction (32 bytes written back). History is written into DMEM before `in` (4 samples; flag 2: s0 s2; flag 4: each sample doubled) |
| 6 | RESAMPLE_ZOH | 0x1E6C | V | byte position in << 16 \| accu, step pitch << 2, sample at (pos >> 16) & ~1; no state |
| 7 | FILTER | 0x1CAC | P | flags > 1: count + 8 coefficients. Else 8-tap FIR in place with 32-byte state (8 history samples + last coefficients); coefficients = (old + new) >> 1; (Σ + 0x4000) >> 15 |
| 8 | SETBUFF | 0x1178 | V | flags byte ignored |
| 9 | DUPLICATE | 0x17C8 | V | writes **N** copies of 128 bytes, minimum 1 (SoH writes N + 1) |
| 10 | DMEMMOVE | 0x11E4 | V | count 0 = nothing; forward copy in 16-byte blocks |
| 11 | LOADADPCM | 0x1AA0 | P | count bytes of book |
| 12 | MIXER | 0x1B30 | V | (2·out·0x7FFF + 2·in·gain + 0x8000) >> 16, clamp; no special case for gain -0x8000 (SoH has one); do-while 32 bytes |
| 13 | INTERLEAVE | 0x118C | V | count = number of output s16 (L + R), do-while 8 |
| 14 | HILOGAIN | 0x1C58 | V | in place at w1 >> 16 (w1 low half ignored): clamp((s·g) >> 4), g UQ4.4; do-while 32 bytes |
| 15 | SETLOOP | 0x121C | V | |
| 17 | INTERL | 0x182C | V | out[k] = in[2k], do-while 8 |
| 18 | ENVSETUP1 | 0x1A1C | V | zeroes the whole volume vector; wet lanes = wet << 8 and that + rateWet |
| 19 | ENVMIXER | 0x1880 | V | d = (s·vol) >> 16 XOR neg (bits 1 / 0 = -1); dry += d; w = (d·wet) >> 16 XOR (bit 3 → -4, bit 2 → -2); wet L / R += w (bit 4 swaps). The lanes hold vol for samples 0-7 and vol + rate for 8-15, and advance 2·rate per 16 samples. **The ucode doubles its rate registers in place** (`add s5,s5,s5`), so a second ENVMIXER without a new ENVSETUP1 ramps twice as fast; emulated. Count = samples, do-while 16 |
| 20 / 21 | LOADBUFF / SAVEBUFF | 0x1A80 / 0x1A90 | V (fields) | (w0 >> 12) & 0xFF0 bytes |
| 22 | ENVSETUP2 | 0x1A44 | V | |
| 23 | S8DEC | 0x1B9C | P | as ADPCM, with byte << 8 |
| 25 | UNK19 | none | V | **No table entry.** Op 25 reads table word 0x42 = 0x0F00 and jumps to IMEM 0x1F00, which is in the middle of op 3's loop, with whatever s2 / s3 / s4 / v28 / v29 the previous command left. That is undefined, so the port makes it a counted no-op (`n_unk19`) |

Ops 0 (0x1F38, writes a trace record), 16 and 24+ are counted no-ops.

### 15.4 Tests (`make -C port/audio test`)

**147 checks pass, 0 fail** (gcc, x86-64).
- **Hand vectors for every opcode:**
  - saturation edges in ADDMIXER / MIXER / HILOGAIN;
  - the VMUDN / VMADN clamps in op 3;
  - envmixer negate / swap / ramp;
  - DUPLICATE with 0 and 2 copies;
  - resample, from zero history into a constant, and the half-speed row;
  - ZOH;
  - FILTER, load and crossfade;
  - LOAD / SAVE, and an unmapped address.

  Two of my first vectors were wrong by hand and were recomputed, not adjusted to fit. One of them
  shows a real ucode effect: at half speed the pairwise VMULF rounding turns a constant 1000 into 1001 on
  odd outputs.
- **ADPCM:** a known 4-bit frame (zero book: the output is the nibbles; scale 2), a predictor book
  (hand-derived 1, 2, ..., 3, 2), continuation from the saved state, 2-bit crumbs, and the loop flag.
- **The decoder end-to-end:** a list of LOADBUFF / HILOGAIN / INTERLEAVE / SAVEBUFF words plus ops 25
  and 16.
- **A real sample:**
  - The test reads the font table at bootup Data +0x1D620 and the sample-bank table at +0x1DFF0.
  - Sample: font 0, instrument 1, codec ADPCM, 53298 bytes at bank 0 +0x4FD0, book order 2 x 2.
  - It decodes 400 frames through the command list (LOADADPCM, then per 4 frames: LOADBUFF / SETBUFF /
    ADPCM / SAVEBUFF).
  - The output matches an independent reference VADPCM decoder in the test (0 mismatches). Peak 16695,
    mean square 2.3e7: not silent, not clipped.
- **Not run:** `-m32`. This host's gcc has no 32-bit libc headers. The code has no width
  assumptions besides `uint32_t` addresses.

### 15.5 Open questions (for the M4 emulator capture)

1. **ADPCM (op 1) rounding.** The code uses the standard truncating `>> 11` with a 64-bit accumulator.
   The ucode (0x122C) does it with VMUDN / VMADH chains. Disassemble the handler, or compare 1 frame
   against an emulator.
2. **FILTER (op 7)** averaging and rounding are unverified. Handler 0x1CAC is next to disassemble.
3. **Op 3** is read straight off the disassembly. Its output (low 16 bits of a product) is a harsh
   distortion, so confirm with a capture of a bookOffset-2 note, if the game has one.
4. **Op 25:** does 1080 ever emit it (bookOffset 3)? If it does, the original's output depends on
   stale RSP registers. Count `n_unk19` in a play-through.
5. **RESAMPLE flags 2 / 4:** the history shapes are read off the ucode, but whether the stepping changes
   is not. 1080's synthesis passes only 0 / 1 for the final resample. Check the reverb `resampleFlags`.
6. **S8DEC (op 23)** and **LOADADPCM (op 11)** are not yet checked against handlers 0x1B9C / 0x1AA0.
7. ~~Fix the `game_libs_rsp_ucode_31DF8` comment and the tenshoe.yaml "7 aspMain variants" note~~: done in
   run 616 (c948e5bf5, 76dfd2c78).

**Next (M4 integration):** call `audio_abi_run` from `AudioThread_UpdateImpl` under PORT in place of the
OSTask. Use `translate = addr | 0x80000000` on the 32-bit build. Swap books / filters at font load, and
SAVEBUFF into the AI buffer for the host stream (10.2).

### 15.6 Wiring: driver + mixer, byte order, gWaveSamples[8] (run 616)

agent-c run 616. Commits on agent-c: c948e5bf5 (comments only), 76dfd2c78 (port/audio glue, swaps, PORT hooks).
Gate PASS before each (ROM byte-identical, 3288/3288). This section is uncommitted.

**Driving it (`port/audio/port_audio.{c,h}`).**
- `port_audio_frame()` = one VI retrace of audio, i.e. what RcpMgr_service's 'd' case does for audio.
  It calls `AudioThread_UpdateImpl()` (the donor body the port compiles) and, when that returns a task,
  runs the task's Acmd list (`data_ptr`, `data_size / 8` commands) through the mixer at once.
  **Call it once per retrace: 2 per 30 Hz step** (section 10.2: 60 Hz, 1 update per retrace, specUnk4 = 1).
- Running the list immediately instead of one retrace later gives the same samples. The update fills
  `aiBuffers[curAiBufIndex]` and queues the buffer of two updates ago. The CPU never reads synthesized
  data, and every DRAM state the list writes (ADPCM, resample, filter, reverb rings) is read only by the
  next list.
- **Delivery:** the game's own `osAiSetNextBuffer(aiBuffers[(cur + 1) % 3], len * 4)` reaches
  `host_audio_queue` through the shim (17.2). There is no extra hook. The headless `osAiGetLength` = 0
  makes every buffer 560 frames (the clamp).
- **Addresses:** the builders store `OS_K0_TO_PHYSICAL(p)` = p - 0x80000000. So the mixer's translate is
  `addr + 0x80000000` (mod 2^32). That is not `| 0x80000000`, which 15.5 said: an OR is wrong for a host
  pointer below 0x80000000.
- **For agent-g (RcpMgr):** call `port_audio_frame()` where `snd_AudioUpdate` was, and do not also start
  the audio task. If RcpMgr still calls `osSpTaskStartGo` with it, the `rcpTask` hook should call
  `port_audio_rcp_task_is_audio(task)` and drop the task when it returns 1.
- **For agent-a (CMake):** add `port/audio/{mixer,abi_decode,audio_swap,port_audio}.c` to the port
  sources (not libgame.a's excluded list). `port_audio.c` uses `port_bootup_data` (uso_modules.c) and
  `port_ultra_cfg` (ultra_int.h).

**gWaveSamples[8]** (game_libs_o2_26214.c, PORT): `port_audio_noise_base() + (audioRandom & 0xFFF0)`.
- The buffer is a copy of the ROM bytes after `AudioThread_Update`. AudioThread_Update is at game_libs
  0x261F4; game_libs VRAM 0 = ROM 0xDE50D8, so the copy starts at ROM 0xE0B2CC. It is 0x10000 + 20 x 0x800
  bytes, converted to host s16, so the noise samples have the N64's values.
- Without a ROM image it is an LCG fill.
- AudioSynth advances the pointer by `numSamplesToLoad * 2` elements per noise note (OoT's spelling),
  hence the 40 KB tail.

**Byte order (`port/audio/audio_swap.{c,h}`).** Byte streams stay as they are: sequences, VADPCM frames,
and S8. On the US ROM there is no PCM16 sample data (codecs: 504 ADPCM, 147 small ADPCM). Every
multi-byte field the driver or the mixer reads is converted once, where it enters RAM. Each swapped
field goes into a set, so a shared sample, book or envelope swaps once.

| where | hook (PORT) | fields |
|---|---|---|
| every font load (sync, async, preload: all go through AudioLoad_RelocateFont before anything reads the font) | `port_audio_swap_font` at the top of `AudioLoad_RelocateFont` | drum / sfx list offsets, instrument offsets; Drum / Instrument envelope offsets; TunedSample `sample` offset + f32 `tuning`; Sample word 0 (**re-packed to host bitfield order**), `sampleAddr`, `loop`, `book`; AdpcmLoop start / end / count / pad + `predictorState[16]` (only when count != 0: a non-looping loop record is 0x10 bytes); AdpcmBook order / numPredictors + `order x npred x 8` s16; envelope points {s16 delay, s16 arg} up to the first delay <= 0 |
| bootup Data, once | `port_audio_swap_static` at the top of `AudioLoad_Init` | +0x17D50 wave tables s16 (8 x 256, gWaveSamples[0..7]); +0x18D74 / 0x19174 bend f32[256] x2; +0x19574 gPitchFrequencies f32[128]; +0x19794 gDefaultEnvelope; +0x197E4 gHaasEffectDelaySizes u16[64]; +0x19868 zero book; +0x198E8 / 0x19AE8 / 0x19CE8 headset / stereo / default pan f32[128]; +0x19EE8 filter s16[16][8], +0x19FE8 gLowPassFilterData s16[31][8], +0x1A1D8 gHighPassFilterData s16[15][8]; +0x1A2D0 sEnvMixerOp + 3 Haas dest words; +0x1CC10 gAudioSpecs (8 x 0x38: u32, 4 x u8, ptr, u32, u32, u16, 8 x u32) and their ReverbSettings (0x12: u8 u8 u16 x4 s8 pad u16 s16 s16; targets from the spec relocs); +0x1CDD0 gAudioHeapInitSizes; the AudioTables at +0x1D620 (fonts, 30), +0x1DA40 (sequences, 90), +0x1DFF0 (sample banks, 13); +0x1D810 gSequenceFontTable u16 offsets; gDefaultNoteSub byte 0 (bit-reversed: MSB-first enabled / needsInit -> LSB-first) |

- **Sample word 0.** Re-packing for the host compiler's bitfield order puts codec in bits 0-3, medium in
  4-5, unk_bit26 in 6, isRelocated in 7 and size in 8-31 (gcc / clang, little-endian). Then every
  bitfield view declared MSB-first for IDO reads it correctly unchanged: include/audio.h `Sample`,
  `gl_258C0_Sample`, `Desc25BFC`, `Desc258`, and the reverb's fake sample `gl_21498_Bits`. SoH's way
  (bswap32 + reversed declarations) would need every view edited.
- The one raw shift / mask reader is `AudioLoad_SlowLoadSample`. Its expressions now go through
  `GL2495C_MEDIUM / CODEC / SIZE` macros, which expand to the original text off PORT (gate PASS).
- `AUDIO_SAMPLE_*` (audio_swap.h) are the host-order accessors.

**Not covered, for the M2 typed swap list (4.4 / 16):**
- the audio functions' **RoData** constants read through pinned externs: 22 `kRo*_Audio*` names in
  aliases.ld (`Audio_AdsrUpdate`, `Audio_BuildSyntheticWave`, `AudioHeap_InitAdsrDecayTable`, ...), and
  `gl_24378_rodata + kRoF_maxTempo{Pal,Mpal,Ntsc}`. These need a type (f32 / f64) per entry. C float
  literals are not affected, since gcc emits them itself.
- bootup Data 0x1A2E0..0x1A2F0 (4 words `7fffd001 ...`, no symbol yet) and 0x1CDE0..0x1D340 (u16 table,
  `0540 0540 ...`): who reads them is unknown.
- **The general bitfield problem** (not audio data): a runtime bitfield word that one TU reads through a
  bitfield view and another through masks or byte loads disagrees on a little-endian host, because the
  views are declared MSB-first for IDO. The audio driver's runtime flag words (SequencePlayer /
  SequenceChannel / SequenceLayer / NoteSubEu bitField0) have several per-TU views. They have not been
  checked for mask or byte-load readers yet. This needs an audit per struct before audio is trusted (M4).
- The M2 swap-list owner must **exclude** the ranges above; a second swap would undo them.

**Tests.** `make -C port/audio test ASSETS=<extract dir>` (64-bit):
- `test_mixer`: 147 checks.
- `test_audio_swap`: **263 checks, 0 failures**, on the real ROM data:
  - spec 0 = 32000 Hz / 20 notes / 3 players / 2 reverbs, and spec 4 = 24000 Hz;
  - the reverb records;
  - pitch ratios increasing up to entry 117, where OoT's table also wraps to the octave below;
  - pan volumes in [0, 1];
  - the default envelope {1, 32000} {1000, 32000} {-1, 0};
  - filter rows;
  - all table entries inside their USO;
  - all 30 fonts swapped (29513 fields; 651 samples, 404 books, 651 loops, 517 envelopes, field set
    never full), then walked in host order: every sample inside its bank, ADPCM books of order 2,
    loops start <= end, tunings in (0, 16), every envelope terminated, and the audio.h-style bitfield
    view equal to the `AUDIO_SAMPLE_*` accessors;
  - font 0's sample decoded by the mixer straight from the swapped codebook = the reference decoder on
    the ROM bytes (400 frames, 0 mismatches).
- Compile check, port flags (`-m32 ... -DPORT`): port/audio/*.c clean (`-ffreestanding` plus a
  string.h stub for mixer.c on this machine). `game_libs_post.c` (with its tu header) and
  `game_libs_o2_26214.c` compile, and their objects reference `port_audio_swap_font` / `_static` /
  `port_audio_noise_base`.
- **Not done: a headless driver + mixer render of a sequence.** The driver cannot run on a 64-bit host:
  fonts hold u32 pointer slots that RelocateFont fills with host pointers, and the builders cast pointers
  to u32. It needs the 32-bit link (agent-a's CMake, plus an i386 libc, which this machine lacks). Once
  `game` links: `snd_Init` + `AudioLoad_Init`, start sequence N with the audio command queue, call
  `port_audio_frame()` 2 x frames times, and capture `host_audio_queue`. The `PortAudioStats` counters
  (`badAddr`, `unknownOps`, `unk19`) are the first checks.

### 15.7 Run 829: seqrender, the first audible output (agent-c)

agent-c run 829, branch agent-c on main c134a6aa0. Commits f13fc66d2 (case labels + audit tool),
275d61e26 (seqrender, host AI hooks, translate). Gate PASS before each (ROM byte-identical,
3579/3579, verify-blocks 6/6, clean build OK). This section is uncommitted.

**The harness (`port/audio/tools/seqrender.c`, CMake target `seqrender` with `PORT_LINK=ON`).**
Same objects as tenshoe (whole-archive game / uso / ultra / audio, aliases.ld), own main, no boot:
1. ROM -> port/ultra, `osInitialize`, `port_uso_init` + `port_sysapi_install` (as port_game_boot).
2. SnowBoard_ctor's audio part: `fs_gdlFileInfo` of rom/audio_seq.uso / audio_wave.uso /
   audio_bank.uso (0x1E978 / 0x3F2A8 / 0xB848), `snd_Init(seq, bank, wave)` -> AudioLoad_Init.
3. 4 settle steps, app_runInit's `snd_PlayPlayer0Seq0` (seq 0 on player 0).
4. `--seq N` = `snd_PlayPlayer1SeqDefault(N)`; `--event M[:S][@SEC]` (up to 8) =
   `snd_seqEventDbg_00000148(M, S, 0)` (what n64proc / titproc / timproc's snd_playSeq call);
   `--sfx K [--sfx-at SEC]` = `snd_PostEvent(K)`.
5. Per 30 Hz step `snd_FrameUpdate` (snd_UpdateTimers -> ScheduleProcessCmds) then two
   `port_audio_frame` (app_runOneFrame's order). AI buffers -> 16-bit stereo 32000 Hz WAV.
6. A modelled DAC (osAiGetLength = frames queued minus 32006 / 60 per retrace, through the new
   `host_headless_set_audio_clock`): the driver's feedback then picks 528..544-frame buffers as on
   hardware. With the headless 0 every buffer is 560 frames and the output runs 5 % long
   (10.5 s of WAV per 10 s of game).
Prints peak / RMS / clipped samples, PortAudioStats (badAddr, unknownOps, unk19, rawPointers),
and the music player's tempo (`--tatums N` overrides gAudioHeapInitSizes.tatumsPerBeat for
experiments; `SEQRENDER_DEBUG=1` dumps the command ring).
```
run32 <build>/seqrender --rom baserom.z64 --event 1 --seconds 60 --out title.wav
run32 <build>/seqrender --rom baserom.z64 --seq 6 --seconds 60 --out seq06.wav
```

**Bugs found and fixed.**
1. **Switch case labels vs pinned jump tables** (new class; `port/tools/jumptable-audit.py`). A donor
   whose table is pinned to the USO's (`<func>_rodata`) matches whatever its labels say, as long as
   the bounds and the arm order agree. gcc builds the table from the labels. The audit compares each
   game_libs donor's own .rodata table with the ROM words: 27 donors, **5 wrong, all one entry off**.
   `AudioThread_ProcessGlobalCmd` (0x82 INIT_SEQPLAYER ran SyncLoadSeqParts: **no sequence ever
   started**; 0xF9 spec change did nothing), `AudioThread_ProcessCmds` (OoT's 0x47..0x4E),
   `snd_SoundObjEventIndex` (bits 1..32), `dbg_threadStateName` (OS_STATE 1/2/4/8),
   `Node_doCommand` (0x64 name, 0x65 parent, 0x67 global, 0x6C handle: **boot path, agent-g**).
   Relabelled in place, except Node_doCommand (#ifdef PORT: its true labels change IDO's table
   density and so the bytes; the audit keeps reporting it for the ROM build, expected).
   dbg_threadStateName needed phantom `case 3: case 5: case 6: case 7:` for the same density reason.
2. **FILTER addresses**: AudioSynth_ProcessNote / AudioSynth_FilterReverb put the pointer itself in
   the 0x07 words (OoT's aFilter does too; the RSP keeps 24 bits), not K0 - 0x80000000. The mixer
   added 0x80000000 and crashed in mix_filter on the first note with a filter. translate_k0 now
   uses an address that is already inside the port image (__executable_start .. sbrk(0)) as it is.
3. **Gate hole (not fixed, for the gate owner)**: `make all` did not rebuild a changed donor
   (game_libs_o2_26790 / 26D64 / 2E290 / 343F4 objects stayed at their 07:34 build), so the first
   gate run PASSed on stale donors. Rebuilding them by hand showed dbg_threadStateName's relabel
   changed bytes. Donor .o files need their source as a prerequisite of the spliced object.

**Verification (WAVs in /tmp/claude-1000/c829/).**

| file | request | seq | sequence tempo | measured |
|---|---|---:|---|---|
| title_seq02.wav (60 s) | `--event 1` (n64proc's snd_playSeq mode 1; the title runs on) | 2 | 176 bpm | 141.2 tatums/s = 176.5 bpm; onset AC at the beat 0.042, at the bug's rate -0.016 |
| seq06.wav (60 s) | `--seq 6` | 6 | 130 bpm | 104.2 tatums/s = 130.3 bpm; onset AC beat 0.050, bug rate -0.013 |
| race_start_seq14.wav (40 s) | `--event 4:2 --event 5:0@1` (course 2, then mode 5) | 14 | 160 bpm | 128.3 tatums/s = 160.3 bpm; **onset-AC peak exactly at 0.375 s = the beat** |
| seq05.wav (60 s) | `--seq 5` | 5 | 160 bpm | 2 clipped samples in 60 s |
| seq04.wav | `--seq 4` | 4 | 176 bpm | silent: player enabled (muteBehavior 0xA0), no notes; not investigated |
| seq2_tatums1400_bug.wav (10 s) | `--seq 2 --tatums 0x1400` | 2 | (clamped to 100) | 180 tatums/s = 225 bpm; onset AC peaks at the bug rate (0.064), beat -0.010 |

All renders: no NaN path (s16 output), clipping 0 except seq 5 (2 samples), badAddr 0,
unknownOps 0, unk19 0 (op 25 never emitted: 15.5 question 4 answered for these sequences), AI
underruns 0, DC under 35, L / R correlation 0.16..0.70 (real stereo). 0.3 % fast against the
nominal bpm is the driver's own rounding (tempoInternalToExternal 10770, not 10800).
**Tempo verdict:** with tatumsPerBeat fixed the tempo is the sequence's; the old 0x1400 made it
too FAST (18.13 corrected).

**Game music state machine (snd_HandleSeqEvent modes), as far as seen.** Mode 1 (n64proc) ->
spec 0 + seq 2. Mode 0 (titproc) and mode 4 (timproc, sub = course) change the spec
(snd_StopAudioCmds(1 / 3 / 4 / 6) -> 0xF9) and start nothing by themselves; 4 stores
gl_cmd = course + 4. After mode 4: mode 2 -> seq 16, 3 -> 3, 5 -> 14, 8 -> 16, 9 -> 17, 11 -> 19;
mode 10 -> 18. Which event starts a course's own music (seq course + 4?) was not found: the
timer path (snd_ScheduleSeqDefault, 210 steps) is reached from snd_dispatchEvent; seq 4 was silent.

**Next.** Listen to the WAVs. Find the race-music trigger (snd_dispatchEvent / timproc); seq 4's
silence (channel mask / IO?). Run seqrender over all 24 music sequences (non-silent, no clip
storm, badAddr 0) as an M4 regression test. agent-g: Node_doCommand's labels change under PORT.

### 15.8 Run 833: course music, seq 4, the K0-pointer tests, the regression sweep (agent-c)

agent-c run 833, branch agent-c on main 3d569b3. Commits: 74fc4f792 (snd_dispatchEvent byte order), 541243c38
(K0-pointer tests, port_audio_is_ptr / premix hook), f228570c4 (seqrender, regress), 7b775daeb
(--spec, seqs 7 / 9 / 19 in spec 3, write watch). Gate PASS on the
tree (ROM byte-identical, verify-blocks 6/6, 3579/3579, lost none, check --order 0 wrong, clean build OK;
build/src + build/non_matching/src removed first). This section is uncommitted.

**1. Course music: what starts it.** Not an snd_HandleSeqEvent mode. The chain, all in the race code:
1. title menu (`tit_menuMultiRace` .. `tit_menuTraining`): `snd_sendEvent(12, G)` ->
   snd_dispatchEvent case 12 stores the game type G in bootup Data 0x1C0B4 (0 match race,
   1 time attack, 2 trick, 3 arcade, 4 head-to-head, 5 training; boot value -1).
2. race load (timproc_uso_b1 / b3, titproc ghost runs): `snd_playSeq(d, 4, course, x)` ->
   snd_HandleSeqEvent mode 4: spec change (`snd_StopAudioCmds` 3; 6 for course 0; 4 for game type 4)
   and the music command word (Data 0x1C0AC, gl_cmd_30AF4 = D_2FB74_chan) = **course + 4**; game
   type != 0 and course 6 -> 7; game type 4 (2P) -> course + 18. Mode 4 right after mode 0 only
   sets the mode word to 12. (snd_playSeq's 4th argument is dropped: it calls snd_seqEventDbg(seq, arg, 0).)
3. `RaceProcess_handleInput` countdown (20 frames per count after 120): posts 0x12 + 0x10 ("3"),
   0x12, 0x12, then **0x11 ("GO")**: snd_dispatchEvent case 17, with mode word == 4 and Bss 0x314 == 0,
   calls `snd_ScheduleSeqAfter(cmd & 0xFF, 22)`: snd_UpdateTimers starts it on player 1 22 frames later.

**Bug (fixed, donor game_libs_o2_2FB74.c, `#ifdef PORT`):** cases 17 and 512 read the command word's
low byte as `p->b[3]` through a union; the word is a native u32 under PORT, so b[3] was its high
byte: GO scheduled **sequence 0** (silence on player 1) for every course. `CHAN_B3(p)` = `(u8)p->w`.

seqrender `--course N [--gametype G]` replays 1..3 (event 4:N, the countdown posts, GO at 6.03 s,
music at 6.77 s). Mapping (game type 0; the sequence table aliases 11 -> 8, 24 -> 21, 25 -> 22):

| course | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| sequence (game type 0) | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 (= 8) |
| bpm (header) | 176 | 160 | 130 | 145 | 177 | 176 | 167 | 177 |

Course 6 plays seq 7 for any game type but 0; 2P (type 4) plays course + 18 (seqs 18..25).
Which course number is which slope is not traced here.

**2. Silent `--seq 4`: a port bug, not a placeholder.** Seq 4 is course 0's music: 8 channels of
long legato notes (short-note mode, 2-bit "small" ADPCM samples, codec 3). Its notes were allocated
with valid samples, but never synthesised (no ADPCM command at all). Cause: OoT's
`AUDIO_RELOCATED_ADDRESS_START` tests, which tell a relocated K0 pointer from an offset by value:
- `Audio_ProcessNotes`: `if ((u32)parentLayer < 0x7FFFFFFF) continue;` -- every port pointer is below
  that, so **every note that still had its layer was skipped**: only release tails were ever heard
  (a note sounded only after its layer let it go). Held / legato notes (all of seq 4) never sounded.
  The 15.7 renders were made with this bug: their tempo results stand (onsets), their sound did not.
- `Audio_GetDrum` / `Audio_GetSoundEffect`: `tbl < 0x80000000U -> return 0`: **no drum and no sound
  effect** could be found.
- `AudioLoad_RelocateSample`: `sample <= 0x80000000` = "not relocated yet": a second relocation of
  the same TunedSample would have added the font base again.
Fixed in game_libs_post.c (`#ifdef PORT`, `AUDIO_IS_RELOCATED_PTR` -> `port_audio_is_ptr`, the
port image range port_audio's translate already uses). Seq 4 now renders (RMS ~6000, 176.5 bpm).
After the fix the mix is much denser and louder: 13 of 24 sequences clip (seq 13: 0.42 % of samples,
seq 5 0.09 %). Whether the N64 clips the same way needs the emulator capture (15.5); the race path
(`--course 1`) clips less than `--seq 5` (the volume-level calls after mode 4 are not in --seq).

**3. Regression sweep (`make -C port/audio regress SEQRENDER=<build>/seqrender`;
`port/audio/tools/regress.py`, golden hashes `port/audio/tools/regress-golden.tsv`).** 53 cases, each
rendered twice (~18 s in all): seq 0..25 (40 s), course 0..7 (game type 0, 30 s), 19 sound events (4 s).
Checks: non-silent (unless golden marks it silent), badAddr / unknownOps / unk19 / AI underruns 0,
tempo = header tempo command x 48 (clamped to tempoInternalToExternal) and the tatums the player
advanced (per tick tempoAcc += tempo, a tatum per 10770) within 1 % of it, the two runs' PCM hashes
equal, the hash equal to the golden one. Result: **all 53 pass**; deterministic everywhere.

| case | seq | bpm hdr / measured | peak / RMS | clipped samples | note |
|---|---|---|---|---|---|
| seq00, seq01 | 0, 1 | 225 / 225.0 | silent | 0 | sound-effect sequences: wait for player IO |
| seq02 | 2 | 176 / 176.49 | 32768 / 8969 | 2673 | title |
| seq03 | 3 | 105 / 105.31 | 32768 / 7334 | 286 | |
| seq04 | 4 | 176 / 176.49 | 23354 / 5965 | 0 | course 0 (was silent) |
| seq05 | 5 | 160 / 160.45 | 32768 / 12190 | 7191 | course 1 |
| seq06 | 6 | 130 / 130.36 | 32768 / 6333 | 40 | course 2 |
| seq07 | 7 | 145 / 145.40 | 32768 / 5832 | 19 | course 3 (`--spec 3`) |
| seq08 = seq11 | 8 | 177 / 177.49 | 32768 / 6473 | 2 | course 4 / 7 (11 is a table alias) |
| seq09 | 9 | 176 / 176.49 | 32768 / 9562 | 3565 | course 5 (`--spec 3`) |
| seq10 | 10 | 167 / 167.45 | 32768 / 8270 | 766 | course 6 |
| seq12 | 12 | 132 / 132.36 | 32767 / 4839 | 3 | |
| seq13 | 13 | 166 / 166.45 | 32768 / 13999 | 33971 | loudest |
| seq14 | 14 | 160 / 160.45 | 32768 / 7888 | 188 | mode 5 |
| seq15 | 15 | 160 / 160.45 | 32768 / 9139 | 9069 | |
| seq16 | 16 | 105 / 105.31 | 32767 / 7603 | 198 | modes 2 / 8 |
| seq17 | 17 | 163 / 163.48 | 32768 / 8772 | 9988 | mode 9 |
| seq18 | 18 | 133 / 130.95 (changes its tempo) | 32768 / 7111 | 118 | mode 10 / 2P |
| seq19 | 19 | 176 / 176.49 | 32768 / 14906 | 109395 | mode 11 (`--spec 3`) |
| seq20 | 20 | 130 / 130.36 | 32768 / 9028 | 9342 | |
| seq21 = 24 | 21 | 145 / 145.40 | 32768 / 6740 | 501 | |
| seq22 = 25 | 22 | 177 / 177.49 | 32768 / 7827 | 436 | |
| seq23 | 23 | 176 / 176.49 | 32768 / 9541 | 3849 | |
| course0..7 | 4,5,6,7,8,9,10,11 | as above | | | music at 6.77 s every time |
| sfx 12, 19, 1A, 1B, 1D, 1E, 1F, 33, A3, BC | | | | | sound |
| sfx 0E, 0F, 10, 11, 14, 15, 16, 18, 1C | | | silent | | controls (player-2 IO cues, race state); 18 / 1C untraced |

The measured bpm is the header's x 10800 / 10770 (+0.28 %, the driver's own rounding) everywhere.

**4. Seq 9 crash = the boot spec's sequence cache, not a port bug.** `--seq 9` straight after boot
crashed in the mixer (`dmem_copy_in` from a LOADBUFF with 0x990C4FCA): the first frame's reverb
LOADBUFFs / FILTER words were garbage. A write watch on gAudioCtx's head page (SEQRENDER_WATCH:
read-only page, single-step re-arm) caught `AudioLoad_SyncLoad` -> SyncDma -> the PI copy writing the
sequence over gAudioCtx: the boot spec's temporary sequence cache is **0x2E00** bytes
(seq.temp pool 0x08AF07A0 .. 0x08AF35A0, then the session pool's end, then gAudioCtx at +0x110), and
`AudioHeap_AllocCached(temporary)` does not check the size. Seqs **7 (0x3440), 9 (0x3350) and
19 (0x32B0)** are bigger, so their loads run 0x300..0x440 bytes into gAudioCtx (the synthesis-reverb
structs, numSynthesisReverbs). The layout is the N64's (bootup Bss, asserted struct sizes), so the
N64 would corrupt the same bytes; the game only plays these in race spec 3 (timproc's mode 4).
seq 7 / 19 "worked" in the boot spec with a corrupted reverb (different hash). seqrender `--spec N`
(snd_StopAudioCmds(N), 30 steps) renders them in spec 3, and warns when a --seq load would overrun.
The regression renders 7 / 9 / 19 with `--spec 3`. Clipping: the `--seq` renders do not get the game's
volume-level calls (snd_ApplyPlayer*VolumeLevel after a mode change); `--course 5` (seq 9, RMS 5421,
33 clipped) against `--spec 3 --seq 9` (RMS 9562, 3565 clipped) shows how much they lower the mix.

**seqrender additions.** `--post K[:V][@SEC]` (snd_dispatchEvent), `--course N [--gametype G]`, `--spec N`,
`--list` (the sequence table: ROM, size, cache policy, header bytes and tempo, aliases),
`--summary` (one RESULT line), `--out -` (no WAV), a log of the music state after every request
(mode / course / command word / game type / timer) and of player 1's starts and stops, the PCM hash,
a SIGSEGV report (step + eip), SEQRENDER_WATCH (logs writers of gAudioCtx's head), and the debug envs SEQRENDER_TRACE (per-step player 1 + channels /
layers / notes), SEQRENDER_NOTES (enabled notes + the whole command list before each mix,
through the new `port_audio_premix_hook`), SEQRENDER_DUMP (seq bytes). The tempo figure now comes
from scriptCounter / tempoAcc (the old delay-counter estimate over-counted on legato sequences).

**Open.**
- port_audio's host_mapped (__executable_start .. sbrk(0)) includes the gap between the image's end
  and the heap start: a garbage address there faults instead of counting as badAddr.
- Clipping level (above, with the volume-level calls) wants the emulator capture.
- Which slope each course number is, and whether game type -1 (boot, no menu) can reach a race.

### 15.9 Run 837: the volume path, the clipping verdict, --title, the address gap, tenshoe --audio-out (agent-c)

agent-c run 837, branch agent-c on main 853081eb5. One commit, 4978044e3 (port/audio + port/main.c hook; gate PASS on the agent-c
tree, `make -C port/audio regress` 54/54, unit tests 147 + 264). This section is uncommitted.

**1. The game's volume calls.** Every music start in the game goes through the option levels:
- GameFlow_create (bootup_uso_tail3a_10C8C) reads the options (Backup_readOptions; defaults from
  Backup_resetOptionsData: levels 8 / 8 / 8, flags 8) and calls snd_SetPlayer1VolumeLevel(levels[0]),
  snd_SetPlayer0VolumeLevel(levels[1]), snd_SetPlayer2VolumeLevel(levels[2]) and
  snd_SetSoundOutputMode(flags & 3 = 0, stereo). The setters store the level (bootup Data 0x1C0D4 / D8 / DC) and
  queue AUDIOCMD 0x41 (fadeVolumeScale) for player 1 / 0 / 2 with the float table at Data 0x1C128
  (0.0, 0.1 .. 1.0): **level 8 = 0.8**. The options menu (settings_vol*Up/Down, 0x123F0..) moves them 0..10.
- snd_HandleSeqEvent's flag == 1 tail (modes 0, 1, 2, 3-after-race, 4, 10, 11) and snd_UpdateTimers' scheduled
  start (snd_PlayPlayer1Seq, then gl_ref_00041ED4) re-apply them (snd_ApplyPlayer1 / 0 / 2VolumeLevel): a spec
  change re-initialises the players (fadeVolumeScale 1.0), so the game always applies the level after one.
- snd_PlayPlayer1SeqDefault / snd_PlayPlayer1Seq set the channels' volumeScale (0x0101FF00) to 1.0, and
  seqPlayer->fadeVolume starts at 1.0. Channel volume = volume * volumeScale * appliedFadeVolume, **squared**
  (OoT's appliedVolume = SQ(...)), so level 8 plays the music at 0.64 of a bare `--seq`.
- **Title music trigger:** since 07a21b011 (another agent's snd_HandleSeqEvent case relabel from the ROM tables)
  mode 1 is n64proc's (spec 1, F8, PostEvent 0xA3 = the logo sound) and **mode 0 is titproc's: spec 0 +
  snd_PlayPlayer1SeqDefault(2)**. `--event 1` alone starts no music, correctly. tenshoe's boot posts mode 1 at
  retrace 1 and mode 0 at retrace 445 (7.42 s). The same relabel changed the course 0 / 1 race path (the second
  switch's mode-4 arm calls snd_SetChannel8Mode(2 / 1)), which is why course0 / course1 no longer matched their
  run 833 goldens on main.

seqrender now does GameFlow_create's step after the boot (`--levels M,S,V`, default 8,8,8; `--raw` = the old bare
driver), applies the levels after `--spec` (as the flag == 1 tail does), and has `--title [--title-at SEC]`
(mode 1 at 0, mode 0 at 7.4 s). It logs the three players' fadeVolumeScale and the synthesis reverbs.
Goldens updated (stated reason: the levels, and 07a21b011 for course 0 / 1); new case `title`.

**2. Clipping verdict: inherent, no mixer gain bug.** With the game's levels:

| render | peak | RMS | clipped |
|---|---:|---:|---:|
| `--title` (30 s) | 31276 | 4958 | 0 |
| tenshoe boot + title demo, 60 s of game (`--audio-out`) | 32768 | 5537 | 9 samples (0.0002 %) |
| `--seq 2` (was 8637 RMS, 1522 clipped) | 31147 | 5532 | 0 |
| `--course 0 / 2 / 3 / 4` | 19793..26875 | 3305..4088 | 0 |
| `--course 1` (seq 5, race spec 3) | 32768 | 9626 | 2157 (0.11 %) |
| `--spec 3 --seq 19` (credits, mode 13) | 32768 | 10005 | 7888 (0.31 %) |

Race spec 3 is louder than the boot spec for the same sequence (seq 5: RMS ~11000 in spec 3 against 7809 in
spec 0: more notes, so fewer voices stolen). The checks against the ucode: ENVMIXER is VMUDM (s16 x u16 >> 16:
the note's 0xFFF0 envelope = unity, so no hidden x2), the dry / wet sums and MIXER are saturating per voice as
on the RSP (there is no separate final clamp: every voice add saturates), the reverb parameters are the ROM's
(spec 3's reverb 1: window 0x1800, volume 0x77FF, decay 0x5800, leak 0x3000 / 0xD000, read at run time and
found byte for byte at ROM 0xDBEF50; leakLtr 0xD000 is a negative MIXER gain, from the ROM). The residual
clipping is in the two loudest sequences, at the game's own levels: the N64 saturates the same sums.

**3. Bad addresses.** port_audio's valid-address test is now the mapped ranges: every /proc/self/maps
mapping inside [__executable_start, _end) plus [heap start, sbrk(0)) (fallback without /proc: the old span).
The gap between _end and the randomised brk start no longer passes. `SEQRENDER_GAPTEST=1`: a LOADBUFF from the
page after _end (K0 and raw spellings) counts badAddr +2 and does not fault.

**4. Events 0x18 / 0x1C: silent in the ROM's data, not a port bug.** Both are mode 4's per-course cues
(game types 1 / 3: course 7 -> 0x18, course 5 -> 0x1C). snd_dispatchEvent's default arm writes the event to
player 0 channel 0's IO; seq 0's channel 0 dyncalls table 0xAC, whose entries 0x18..0x1F start channel 14 at
0xAFC..0xB1E: `ldi note; rjump` to a common tail (0xB40 `vol 100`, 0xB42 `stseq` the note into layer 0's script
at 0xB69 and layer 1's at 0xB74), layers play font 2 instrument 0x7F (drums).
- 0x1C: note 0x2C. **Font 2's drum 0x2C is an empty entry** (offset 0 in the ROM table, audio_bank +0x1540 +
  0x20F0 + 4 x 0x2C), so Audio_GetDrum returns NULL and the layer mutes. Its siblings 0x2B / 0x2D / 0x2E / 0x30
  / 0x29 exist and sound.
- 0x18: `cc 3c f4 44` jumps to 0xB44, two bytes past the stseq at 0xB42 (its siblings land on 0xB40 / 0xB42),
  so it runs `0B` (delay 11) and `69` (ldio 9, past seqScriptIO[8]: channel byte 0xDD, a byte of the filter
  pointer, NULL here on both machines) and never stores 0x3C: layer 0 plays the script's default note 0x2A,
  and **drum 0x2A is empty too**. Channel 14 does start (SEQRENDER_TRACE0 shows it with both layers).
Debug aids: `SEQRENDER_TRACE0=1` (player 0's channels per step), `SEQRENDER_SFXTAB=font` (that font's drums).

**5. tenshoe `--audio-out FILE.wav`.** port/main.c: one option, a weak call to `port_audio_capture_open` before
port_game_boot and `port_audio_capture_close` after the run (agent-g's file; the hook is 12 lines). port_audio.c
appends every AI buffer to the WAV, logs the music mode / command word when they change, and prints peak / RMS
/ clipping and the mixer counters at close. Title demo, 1800 steps (60 s):
`run32 <build>/tenshoe --rom baserom.z64 --frames 1800 --audio-out title.wav` ->
/tmp/claude-1000/c837/tenshoe_title.wav (63 s: 2014752 frames, badAddr 0, unknownOps 0).
Open:
- **The DAC model faults in tenshoe.** With `PORT_AUDIO_DAC=1` (osAiGetLength = frames queued - 32006 / 60
  per retrace, seqrender's model) tenshoe dies in AudioSeq_SequenceChannelProcessScript (address 0x1, via
  AudioSynth_DoOneAudioUpdate -> AudioSeq_ProcessSequences) a moment after mode 0 starts seq 2; seqrender with the
  same model and the same events does not. Default is off, so the WAV runs 5 % long (560-frame buffers).
  Next: a write watch / trace on player 1's channels at that update.
- **The N64 logo sound is missing in tenshoe** (the WAV is silent until the title music at 7.8 s), while
  seqrender's `--title` plays 0xA3 at 0.44 s. In the boot, mode 1 runs at retrace 1, possibly before
  app_runInit's snd_PlayPlayer0Seq0 or while spec 1 is still loading; trace the order.

### 15.10 Run 840: the DAC-model fault (0xB5 byte order), DAC model on by default, the logo sound, demo SFX (agent-c)

**1. Title demo "Out of DMA slots" (main fabb4f8ce, every run, ~step 230).** Not audio: run 836's
`PORT_BE_SWAP16S` in AnimData_readFrames' streamed path sits between fs_gdlReadFileAsync and the bare
`return;`. On the N64 that `return;` hands back v0 = the DMA slot (AnimDataMgr_getSlot stores it as
`pending`, AnimData_waitFrames -> fs_gdlWaitFile -> dma_wait frees it); on i386 the swap call left eax
garbage, so no slot was ever freed and the 9 slots ran out in SnowBoarder_update. Fix (PORT only):
keep the slot, swap, `return slot`. Title demo runs 1800 steps again.

**2. The DAC-model fault: a byte-order bug in channel command 0xB5 (and 0xB2).**
AudioSeq_SequenceChannelProcessScript read the dyntable / sequence u16 natively:
`unk_22 = ((u16 *)dynTable)[value]`. Sequence data stays big-endian on the host (ScriptReadS16 builds
its words from bytes), so the offset came back byte-swapped. Path: player 2 plays seq 26 (= seq 1,
the rider-sound sequence; snd_PlayPlayer2Seq(0, 0) = cmd 0x82021A00); its channel at 0xEB does
`C2 0154` (dyntable), `60` (ldio 0), `F2` (rbltz), `B5`, `CF 010C` (stptrtoseq) and `2F xxxx`
(startchan 15). Table entry `02 9A` read as 0x9A02: channel 15 started at seqData + 0x9A02 (past the
0x320-byte sequence, in sample data), executed `4F 29 FB AA FA 7E FA ...` (a startchan 9 at 0xFBAA,
a branch to 0x7EFA), ran a few thousand bytes of zeros and garbage and hit `B6` with dynTable NULL
-> read at address 0x1. **It happened in both timing modes** (the garbage channel starts in the
default run too, at the same moment); whether the garbage faults depends on what the audio heap
holds there, which the DAC timing changes. seqrender never plays seq 26 on player 2, so it never
ran 0xB5. Fix (PORT only, game_libs_o2_2BB7C.c): 0xB5 and 0xB2 compose the u16 from bytes.
Debugging recipe: a per-channel ring of (pc - seqData, cmd) in ProcessScript plus a log in
AudioSeq_SequenceChannelEnable of offsets past the sequence (a channel started outside its seq is
the tell).

**3. The DAC model is on by default** with `--audio-out` (PORT_AUDIO_DAC=0 turns it off). Title demo,
1800 steps: 1919424 frames = 59.98 s for 3598 retraces (59.97 s), was 62.96 s; peak 32768, RMS 5704,
clipped 199 (0.005 %), badAddr 0, unknownOps 0. Without --audio-out the headless host still reports
osAiGetLength 0 (560-frame buffers), so plain runs and traces are unchanged.
WAV: /tmp/claude-1000/c840/tenshoe_title.wav (default) and tenshoe_title_nodac.wav (PORT_AUDIO_DAC=0,
with the fix: 62.96 s, RMS 5656).

**4. The N64 logo sound (0xA3): the game's own command order, not a port bug.** Boot order (traced
with a backtrace in AudioThread_QueueCmd): App_main -> GameFlow_startMode -> n64_procMain -> mode 1:
snd_StopAudioCmds(1) (ResetAudioHeap: the F9 commit), F8, player setup + 0x82000000 (player 0 seq 0),
F8, snd_PostEvent(0xA3) (0x06000001 = 0x23); N64DemoProcess_ctor posts 0xA3 again; then App_main ->
app_run(Init) queues its own snd_PlayPlayer0Seq0 (0x82000000). snd_UpdateTimers commits nothing while
the spec change runs (D_2D37C_mode == 1 -> AudioThread_CheckSpecChange), so the first commit (frame
10, after the reset's 18 updates) carries all of it; after the second F8 the IO writes and the second
0x82 are processed in one ProcessCmds call, and the restarted player 0 clears channel 0's IO before
its script reads it. The order and the gating are the ROM's, independent of timing, so the N64 should
behave the same. seqrender's `--title` plays 0xA3 at 0.44 s only because it issues app_runInit's 0x82
before the mode-1 event (proof: skipping app_runInit's 0x82 in tenshoe gives the sound at 0.4 s and
channel 0 IO1 = 35 at retrace 23). Left as is; if real hardware does play it, the difference is not
in the command stream.

**5. Demo SFX: none in the title demo, by the game's gate.** The whole 60 s title run queues 57 audio
commands. snd_updatePlayer runs every demo frame with a live SoundObj, but snd_SoundObjUpdate returns
at once when the music-mode word (bootup Data 0x1C0A8, D_cfg_E354) is 0, and the attract demo keeps
mode 0 (the title music); the race SFX need mode 4 (timproc's snd_playSeq(4, course) at a real race
load). Checking scrape / wind / landing needs a race run (a replay through the menus), not the demo.

## 16. M1: link plumbing

Run 612 (agent-a), on main e58ff9d67, commits f46b22b3d and cc6a576df on agent-a. The goal is a
`port/undefined.txt` that holds only what the shim provides. src/ changes are `#ifdef PORT` only;
the gate passes on both commits.

### 16.1 CALL names under PORT (`include/uso_call.h`)

- **C++ (the 219 NCC donors):** `CALL(f)` / `FCALL` / `GCALL` / `XCALL(tok, f)` expand to `f`.
  `scripts/port-gen-decls.py <libgame.a>` writes `port/gen/decls_cpp.h`, which holds `extern "C"`
  prototypes of the 243 callees the donors name. Every C++ unit force-includes it.
  - **Source of each prototype: DWARF.** It comes from the shipped body's definition (the
    sourcemap's unit wins over placeholder copies). Excluded shim functions get theirs from their
    own sources, compiled once just for this. 3 are written by hand (`sqrtf`, `gl_sprintf`,
    `gl_osSpTaskYield`).
  - **ABI rules:**
    - every pointer is `void *`;
    - integer widths, float, double and long long are exact;
    - K&R definitions get the promoted types;
    - every prototype ends in `...`, because IDO-era callers pass extra arguments and i386 cdecl
      ignores them;
    - void callees are declared `int`, because donors read the v0 a void call leaves behind;
    - by-value struct callers use `(...)`.
  - **Units that declare a callee themselves:** 28 units get `-DPORT_NODECL_<name>`
    (`port/gen/decls_skip.tsv`).
- **C:** `f` is called through **the placeholder token's in-scope type**:
  `(*({ extern __typeof__(tok) __port_call_N __asm__("f"); &__port_call_N; }))`. This is the type
  the matched call was compiled against, so the arguments are passed as in the ROM. No prototype of
  `f` is needed, and the 157 C prototype conflicts of 13.3 do not arise.
  - **Implicit tokens:** some units rely on an implicit or block-scope `int tok()`. They get a
    file-scope K&R `int tok();` in their tu header. `port-gen-build.py` adds it only when every
    declaration of the token in that unit is exactly that.
- **Source fixes (3 C++ donors, `#ifdef PORT`):**
  - casts in 38C98 / 4D688;
  - 34A78 calls `console_createSystemWin()` with no arguments. IDO passes its live `a0` through
    `$a0`, so the port passes `a0` explicitly.
- **Not detected by this scheme:** a C call with too few arguments compiles silently. Such a call
  worked on N64 because the register still held a value (34A78 is one). The error list from the
  naive `CALL(f) f` build (13.3: 90 "too many / too few") is the review list for M2.

Result: **462 / 462 units build.** The excluded functions the library references are exactly the
69 of the shim surface (13.3).

### 16.2 Unnamed placeholder calls, bound per function from the ROM

About 2000 call sites still spell a placeholder token without a CALL name, for example
`timproc_uso_b5_alias(0x4F0)`, `func_00000000(self)` or `game_uso_func_055750(8)`.

`scripts/port-gen-binds.py` runs after a full matching make:
1. For every kept function whose shipped object is the ROM code (name-placeholder-calls' byte
   guard), it resolves each jal reloc against a token the port leaves undefined, through the
   module's TextReloc.
2. It subtracts the CALL-named sites.
3. A self-relocation through an address-pinned token (`gl_ref_00038174 = 0x38174`) resolves to
   the function at that Text offset.
4. If all of a function's remaining calls through one token reach one callee, it writes
   `port-bind: FUNC TOK TARGET` into the unit's tu header. `cc-select.py` then renames TOK to
   TARGET inside FUNC's assembly and its gcc clones.

Results:
- **1054 (function, token) pairs bound, covering 1915 sites** (`port/gen/binds.tsv`).
- Left over (`port/gen/binds-left.tsv`):
  - **104 ambiguous pairs.** One token reaches several callees, so these need CALL names: 83 are
    `gl_func_00000000`, mostly in host units.
  - **43 mid-entry jals.** About 30 are `Text+0x0` trampolines. The rest are libultra entry points
    one or two instructions into a build symbol: `gl___osDisableInt+0x4`, `gl_osSetIntMask+0x8`,
    `gl_osGetCount+0x8`, `gl_bzero+0xC`. These become shim entry points (`__osDisableInt`, ...).
  - **7 sentinels**, which go to the module's Text+0 stub.

Still unresolved call references:
- `timproc_uso_b5_alias` (205): in the 4118 donor and in units whose functions gcc inlined, or
  where the token is ambiguous;
- `gl_func_00000000` (164): C++ donors' raw calls and the ambiguous pairs;
- `gl2FB74_snd` (31), `glv_2838` (28), `gl_func_emit*` (44), `bu_cfa0_v` (19).

Next: a C++ variant of the subtraction (per file), and binding sites that gcc inlined. Both are
cheaper than naming the sites in the source.

### 16.3 Measured: `port/undefined.txt` by group

| group | 608 (13.3) | after 16.1 | after 16.2 |
|---|---:|---:|---:|
| plumbing: import / placeholder tokens (call / data) | 917 (801 / 116) | 664 (547 / 117) | **157 (40 / 117)** |
| plumbing: match_imports binding names (call / data) | 603 (264 / 339) | 596 (257 / 339) | **346 (7 / 339)** |
| data aliases | 2125 | 2213 | 2214 |
| libultra os* + gu + libc (shim) | 6 | 74 | 76 |
| C++ cross-donor (mangled) | 40 | 40 | 40 |
| other | 8 | 8 | 1 (`glv_2a44`) |
| **total** | **3699** | **3595** | **2834** |

**Shim target list:** the 71 excluded names in `port/undefined.txt`.
- These are the 69 of 13.3 (59 libultra, 3 libc, 7 asm) plus `osAiSetNextBuffer` and
  `gl_osAiGetLength`. The binds found these two as real ROM callees.
- Host libc must also provide `memmove` and `memset`.
- The host hooks still to add are the mid-entry entries above.

Data is now 92% of what is left (2214 aliases, plus 456 data-half plumbing symbols).

### 16.4 Data: decision (implemented in 16.5)

**Choice: (b), a variant of (a).**
- **Blobs:** each module's Data / RoData / Bss becomes one host blob at the original layout
  (`char <mod>_data[]` etc.). The extractor writes it from the ROM image (the module's own
  sections, the same bytes the matching build links).
- **Code references** to data aliases are bound **per (function, token) from the ROM HI16 / LO16
  relocations**, exactly as 16.2 binds calls. The target is written as `<mod>_data+0xK` (gas
  accepts `sym+off` operands), or as the import's symbol.
- **Plain data symbols** (`D_*` / `DF_*` / `*_vtbl_*` with a single owner) get
  `--defsym alias=<mod>_data+off` / `.set` in a generated assembly file.

This reuses the proven reloc machinery: `uso-imports.py` already names every Data / Bss target.

**Pointers inside the blobs are relocated at startup by port/uso**, which applies each module's
DataReloc / RoDataReloc to its blob in memory, with the 32-bit host addresses. Why at startup
rather than at link time:
- The ROM reloc tables are the ground truth, and `uso_load`'s reloc pass is the reference
  implementation.
- Decision 4 already has port/uso re-initialise a mode module's Data / Bss on "load". The same
  pass then restores pristine relocated data each time.
- Link-time emission would need every blob split into per-word `.long sym+off` objects: more
  generated code, and only useful for a 64-bit build. That build (M6) needs loader-side
  deserialisation anyway.

### 16.5 Data plumbing and port/uso (run 613)

Run 613 (agent-a), on main af2525ad1, commit 5c0116e0b on agent-a. src/ untouched; gate PASS.

```
make                                                   # matching build (names, objects)
scripts/port-gen-binds.py && scripts/port-gen-uso.py && scripts/port-gen-build.py
cmake -S port -B <build> -G Ninja && cmake --build <build>       # libgame.a + libuso.a
scripts/port-undefined.py <build>/libgame.a --extra <build>/libuso.a
```

**Binds and aliases (`scripts/port-gen-binds.py`).** Every reloc of a proven function against a
symbol libgame.a does not define (the token universe now comes from `nm libgame.a`, not from
undefined.txt, so a rerun is stable) is resolved through the module's TextReloc:
- **Data** (HI16 / word; LO16 is the pair's second half): to `port_<mod>_<sec>+0xK`, K = the
  Sym value (0 for a section-base Sym) + the token's matching-link value. The port asm keeps the
  source's own addend, which is exactly what the ROM immediate holds beyond the token's value.
- **jal:** the target is the Sym value + the instruction's field << 2. This resolves the
  section-base self-relocations that 16.2 listed as `Text+0x0` mid-entries and most sentinels.
- **Global aliases:** a token whose every site in every proven function (calls and data
  together) reaches one target gets `tok = target;` in `port/gen/aliases.ld`, an implicit linker
  script (the final link and port-undefined pass it to ld; gas `.set` cannot alias an undefined
  symbol, it drops it silently). **3708 aliases: 1040 call, 2668 data.** Per-function binds
  (`port-bind`) remain only for shared tokens: **121 pairs, 159 sites**.
- **Mid-entry host hooks:** a jal into an excluded libultra copy binds to a host entry point
  that port/ultra must implement: `gl_osSetIntMask_plus8` (4 sites + `gl_4DC44_word`),
  `gl_osGetCount_plus8`, `gl_bzero_plusc`. (`gl___osDisableInt+0x4` no longer appears: those
  sites were Text-base relocations.)
- The C++ variant of the CALL-name subtraction is the same lexical scanner run on `.cpp` units.

Left (`port/gen/binds-left.tsv`): 120 ambiguous (48 `gl_func_00000000`), 26 `unnamed` (targets
in modules the build has no names for: nameent, viewrec, trnproc, and `Text+0x18` / `+0x718`
callees), 15 unresolved, 1 sentinel.

**Blobs.** `scripts/port-gen-uso.py` writes `port/gen/uso_modules.c` and
`port/gen/uso_blobs.tsv` (names, sizes and offsets only). At build time CMake runs
`port/tools/extract/extract.py` on `PORT_ROM` (default `../baserom.z64`; or `-DPORT_EXTRACTED=`
an existing extract) and `port/tools/gen-uso-blobs.py`, which emits per section a read-only
`port_<mod>_<sec>_init` (`.incbin` of the extracted section) and a zeroed writable
`port_<mod>_<sec>` of the same size, plus `port_<mod>_bss`. 28 modules: the 25 code USOs with
data, plus charfir / charsel / charsps, which code sites reference. 1.1 MB pristine, 1.4 MB
writable.

**Relocation table.** Each DataReloc / RoDataReloc R_MIPS_32 entry becomes `{offset, host
address}`: `port_<mod>_<sec> + K` (K = Sym value + the word's addend), or a function name for a
Text target. Counts: 3161 Text targets bound (vtables, callbacks), 707 Data, 496 RoData, 3 Bss;
**1116 jump-table words** (`func+0xK` labels: the ROM's switch tables, never read by the host
code), 143 Text targets in modules without port code (nameent 41, viewrec 35, heli 24, trnproc
20, checkpoint 10, balloon 6, fire 5), 80 into data-only modules not kept (bgNtex, mapN_data,
the rider banks), 14 unresolved Sym. Unbound words are written as 0.

**port/uso** (`port/uso/port_uso.h`, `uso.c`): `port_uso_load(path)` looks the file name up,
returns -0x13 if live / -0x14 if unknown (uso_load's codes), else copies `_init` to Data /
RoData, writes the relocated words (host order: 32-bit host), zeroes Bss and runs the module's
static initialisers (bootup: `app_staticInit_000412E8`, `Window_staticInit`,
`boot_staticInit_00006204`, `SnowBoard_staticCtor_0000E9FC`, in Text order); returns the ROM
module id. `port_uso_unload`, `port_uso_init` (loads bootup.uso). No libc headers (the machine
has no 32-bit libc yet); `memcpy` / `memset` come from the host libc at link.

**Byte order.** The blobs stay big-endian, as on the cartridge, except the relocated words
(host order, since the code dereferences them). Every other multi-byte read of USO data needs
the 4.4 swap; that is M2 work (a typed swap list per module).

**Measured: `port/undefined.txt` (libgame.a + libuso.a + aliases.ld)**

| group | after 16.2 | after 16.5 |
|---|---:|---:|
| plumbing: import / placeholder tokens | 157 | **20** (17 call, 3 data) |
| plumbing: match_imports binding names | 346 | **5** |
| data aliases | 2214 | **67** |
| libultra os* + gu + libc (shim) | 76 | 75 (incl. the 3 `_plus` hooks) |
| C++ cross-donor (mangled) | 40 | 40 |
| other | 1 | 2 (`glv_2a44`, `gl_bzero_plusc`) |
| **total** | **2834** | **209** |

**Open issues found:**
- **C++ objects defined twice.** libgame.a defines 17 data globals, mostly the objects the
  static initialisers construct (`gGfxLib_412E8_a`, `gSysLib_412E8_i`, `gHostio_412E8_m`,
  `gWindowDefaults_4E584_arr`, `gSnowBoard_func_0000E9FC_arg1`), and one unit defines
  `D_00000000`. The game code reaches the same objects through the blob aliases, so the
  initialiser and the readers see different memory. Fix: `port-drop` those data definitions
  (cc-select) and alias them to the blob offset, like the tokens; and stop excluding the
  defined `D_00000000` from the token universe.
- **Unproven / inlined sites.** An alias is proven only on proven functions' sites. A token also
  used in an unproven function (6 functions) or in a gcc-inlined copy follows the alias.
- **Data references from data** (C initialisers naming a token) are not bound yet; they show in
  the 67 data aliases.

**Next:** the 120 ambiguous pairs need XCALL names in the source (gate-checked); the 40 C++
cross-donor references; the 26 unnamed targets (modules with no port code: nameent, viewrec,
trnproc, heli, balloon, fire, checkpoint have no src/ yet, a gap in the plan); the one
sentinel left (GenCourse_ctor's `timproc_uso_b5_D_807EF230` -> genproc Text+0: the other 6 of
16.2 were Text-base relocations and now bind); and the shim (port/ultra, agent-g) for the 75 + 3 hooks.

### 16.6 Link readiness (run 614)

Run 614 (agent-a), on main 9a58fab11, commits 2d64d8459, 51248853d and 6799f5dc7 on agent-a. src/
untouched; gate PASS on each.

**CMake.** `port/CMakeLists.txt` builds `libultra.a` (port/ultra) and the `porthost` objects
(`main.c`, `host_headless.c`, `trace.c`). With `PORT_LINK`, `tenshoe` links game + uso + ultra
whole-archive plus `aliases.ld` and `-lm`, and `test_ultra` (shim + headless host) is its own
executable. Without `PORT_LINK` the shim and the host compile with `PORT_LIBC_DECLS_ONLY`, so the
`undefined` target checks the whole link (`--extra libultra.a --extra-objects <porthost>`) on a
machine with no 32-bit libc. Every `provided.tsv` shim / host / drop row was already in
`excluded.tsv`.

**Shim names win.** `port-gen-binds.py` never aliases a name the shim defines with `PORT_ALIAS`
(`gl_26214_os*`, `gl___osActiveQueue_34458_head`); `port-undefined.py` refuses an `aliases.ld`
name that an input also defines. **The `_plus` entry points are gone:** a jal into an excluded
libultra `.s` copy at exactly its leading alignment padding is the function itself
(`gl_osSetIntMask+0x8`, `gl_osGetCount+0x8`, `gl_bzero+0xC` -> the shim's `gl_osSetIntMask` /
`gl_osGetCount` / `gl_bzero`).

**Static-initialiser objects.** The B / D objects libgame.a defines are tokens too. 7 resolve to a
blob (`port/gen/dropdata.tsv`): `gGfxLib_412E8_a`, `gSysLib_412E8_i` / `_l`, `gHostio_412E8_m`,
`gWindowDefaults_4E584_arr`, `gSnowBoard_func_0000E9FC_arg1`, and the `D_00000000` that
bootup_uso_ncc_6204 defined, which every `D_00000000` reference in the port had bound to. cc-select
`port-dropdata` renames the definition to a local `__port_dead_SYM`, and the name is aliased or
bound to the blob. The 2 C rodata objects (`mgrproc_uso_rodata_credits`,
`game_uso_B274_original_rodata_prefix`) stay port-owned: read-only, and already host-order.

**Per-addend data binds.** A data token that reaches several objects in one function is bound per
addend: `port-bind: FUNC TOK+N TGT`, where N is the ROM site's full addend (HI16 << 16 + the paired
LO16, read from the REL `.o`). This gives 228 pairs. A data reference into Text (a callback address)
takes its function from the addend, and the port spelling cancels the addend (`f-N`). These were
silently wrong before: dbg_printf's prout pointed at bootup `func_00000000` instead of
`dbg_printfSink`.

**Bug fixed:** cc-select's bind regex never matched `$tok`, the AT&T immediate. Every data bind of
an address taken as an immediate (`pushl $tok+N`, `movl $tok, ...`) had been left unbound since
16.5.

Other fixes: the last sentinel (GenCourse_ctor's `timproc_uso_b5_D_807EF230` =
`timproc_uso_b5_func_00000000`) now binds, `_Znwj` = cfront `__nw__FUi`'s target (`mem_new`), and
gamegfx's Data is now a blob (29 modules).

**Measured: `port/undefined.txt` (libgame + libuso + libultra + porthost + aliases.ld)**

| group | 16.5 | 16.6 |
|---|---:|---:|
| plumbing: import / placeholder tokens | 20 | 19 |
| plumbing: match_imports binding names (incl. `D_00000000`, 538 refs) | 5 | 5 |
| data aliases | 67 | 24 |
| shim (os* / gu / libc) | 75 | 0: the shim, or host libc |
| host libc / libm (`fopen`, `vsnprintf`, `memcpy`, `sqrtf` ...) | | 26 |
| unreferenced (only in sections `--gc-sections` drops; not link errors) | | 27 |
| weak hooks (`app_runOneFrame`, `port_game_boot`, `port_game_frame_count`, `gInputMgr`) | | 4 |
| C++ cross-donor (mangled) | 40 | 39 |
| other | 2 | 1 (`glv_2a44`) |
| **total** | **209** | **145** |

**Still blocking a 0-undefined link: 88 symbols** (19 + 5 + 24 + 39 + 1).
- **Ambiguous pairs that need source names** (`port/gen/binds-left.tsv`):
  - `gl_func_00000000`: 48 functions, 392 sites;
  - `D_00000000`: 56 functions, 222 sites, where two objects share one addend in a function;
  - `timproc_uso_b5_alias`: 6 functions, 176 sites (SelectWin_ctor alone has 69);
  - and about 10 single pairs.

  These need XCALL / per-site alias tokens in the source, which the gate checks. Not started this
  run.
- **`D_00000000` beyond those 222 sites (538 refs in all):** unproven functions (6) and gcc-inlined
  copies of bound functions. The bind follows the function label, not the inlined body. Next: bind
  inlined copies per (caller, token, addend) from the callee's own bind.
- **39 C++ cross-donor references:**
  - 18 `_ZTV*` vtables of mirror classes. The ROM vptr store names a blob vtable
    (`MNode_vtbl_40070_vta` in the matching `.o`), so alias `_ZTVx = blob - 8`. This is only
    correct if the donors' virtual calls read the cfront layout, which is an M2 question.
  - 21 constructors / methods. Pair them with the matching `.o`'s calls, by order within the
    function.
- **`unnamed` (26):** targets in modules with no port code (nameent, viewrec, trnproc, heli,
  balloon, fire, checkpoint) and ucode Text addresses (`D_4D16C_a`, `gl_26214_aspMainTextStart`).
  The ucode ones belong to the RSP / Fast3D side (M2).
- **Side note for the game-side owners:** game_libs_ncc_40070's `operator new` calls
  `dbg_printThreads(n)`, a misnamed placeholder for `mem_new`, so QNode_ctor references
  `dbg_printThreads` three times.

### 16.7 Naming the ambiguous sites (run 618)

Run 618 (agent-a), on main 2a1ec167d, commits 0f26a1ab5, 5cc61957a, 8ddc2abc8 (tool output),
2f97f2c26 and 6ea9066f4 on agent-a. Gate PASS on each source state.

**The `dbg_printThreads` "bug" (item 4).** Not a misnaming in the matching build: eight game_libs
NCC donors (34890, 3E5E0, 40070, 41D40, 46050, 48510, 4B0A8, 4C5E4) used `dbg_printThreads` as a
generic placeholder and renamed it in the object with `objcopy --redefine-sym
dbg_printThreads=<tok>`. The matching bytes and relocs were right. The port compiles the `.cpp`
without the objcopy, so each of those calls went to the real `dbg_printThreads`. The gate did
not catch it because `check` compares only CALL / XCALL names; a bare token is never checked,
and the objcopy pointed the object's reloc at the placeholder anyway. Fix: the source now
spells the post-objcopy token (`gl_func_00000000` / `gl_*_c34458`), and the redefine is gone
(same bytes). Then every site got its proven name: QNode_ctor's `operator new` -> `mem_new`,
the inline Base ctor -> `MNode_initMatrices`, `zero()` -> `math_mtxAddTranslation`, the last
call -> `math_quatScaleToMtx4` (the ROM relocs, in order).

**Scanner gaps fixed (`name-placeholder-calls.py`, also used by `port-gen-binds.py` and
`gameflow-import-sites.py`).** These sites were silently skipped before:
- functions inside `extern "C" { }`;
- inline member functions in struct / class bodies (their verify declarations go before the
  outermost class);
- K&R definitions (`T f(a) T1 a; {`: the header was cut at the parameter declarations);
- `_c34458` tokens: the donors' zero-pinned blank-jal tokens.

**Macro-spelled names.** `macro_named()` counts the CALL / XCALL names in a `#define` body once
per use in a function (honouring `#undef`; uses inside `CALL(name)` are skipped). The gate's
`check` now verifies them (6695 named calls, 0 mismatches), and `port-gen-binds` subtracts
them. SnowAI_ctor's 82 INIT_ITER sites had been listed as ambiguous only because of this. The
audio files' `#define Audio_GetDrum (Drum *)gl_func_00000000` aliases now read
`CALL(Audio_GetDrum)` (24 macros, 3 files).

**C++ subtraction.** A donor's named sites form one pool per file, because a site's source block
is an inline or a class name, never the object function. Before this, no donor's CALL names were
subtracted at all.

`plan --write --funcs port/gen/binds-left.tsv` named **169 sites** (proven per site). Two
donors needed `#ifdef PORT` fixes once named: 34890's recursive void call is read as a value,
and 116C calls `tit_nextDemo()` with no argument.

**Also fixed (from agent-g run 619):**
- `port-gen-uso.py` read `port_defined()`'s tuple as the name set, so every code target in
  `uso_modules.c` was 0. 3161 Text targets now bind.
- CMake adds `sysapi.c` and `fs/fs.c` to the host sources, and builds `test_fs` under
  `PORT_LINK`, each only when the file exists (they are on main, not in this tree yet).
- **Not added:** port/audio (agent-c). It includes `<stdint.h>`, which fails without a 32-bit
  libc. It needs `PORT_LIBC_DECLS_ONLY`-style headers first. Until then, `port_audio_*` (3) show
  up as undefined (`other`).

**Measured.**
- binds-left: ambiguous `gl_func_00000000` went from 48 functions / 392 sites to
  **16 / 69**. All ambiguous pairs: 120 -> 103.
- `port/undefined.txt`: 145 -> 143 symbols. `gl_func_00000000` refs went from 151 to 68;
  `gl_578b4_c34458` and `gl_func_00000000_116c_v` are gone.
- Blocking: 17 plumbing + 5 match_imports + 24 data aliases + 39 C++ + `glv_2a44`, plus 3
  `port_audio_*` that are new from main.

**Left (`gl_func_00000000`):**
- the 5 `-O0` NCC donors `app_createGame_*` and `ColourItem_create`: their verify compile
  differs, so they need the o0 recipe in `compile_verify_cpp`;
- PolyShape_display (48AEC, 13 sites);
- the 6 `gl_osSetIntMask+0x8` / `gl_osWritebackDCache*+0x4` functions: plan needs the padding
  rule that `port-gen-binds` already applies (`sym+pad` -> `sym`);
- `Text+0x0` / `+0x18` / `+0x718`: modules with no names;
- AudioHeap_DiscardSampleCaches (a nested macro).

**Not started this run:**
- `D_00000000` (56 functions / 222 sites, via `uso-data-sites.py`);
- `timproc_uso_b5_alias` (6 / 176);
- the 39 C++ cross-donor references (21 ctor pairs; the vtable decision);
- the 24 data aliases;
- `glv_2a44`.

## 17. M1: libultra shim and main loop

agent-g run 610, branch agent-g. Files (all new, under `projects/1080-decomp/port/`):

| file | what |
|---|---|
| `ultra/ultra.h` | the shim's API: the libultra calls (canonical names) and the port side (`port_ultra_init`, `port_vi_retrace`, services, SI pads, SRAM) |
| `ultra/thread.c` | threads, the active-thread list, services, the pump, blocking waits, `osYieldThread` |
| `ultra/message.c` | message queues, `osSetEventMesg` / event posting, `osSetIntMask` |
| `ultra/vi.c` | VI on virtual time |
| `ultra/pi.c` | PI / EPI DMA from the in-memory ROM image, SRAM save file |
| `ultra/si.c` | controllers, controller pak (absent), rumble pak |
| `ultra/ai_sp.c` | AI (host audio stream hooks), SP tasks (`rcpTask` hook) |
| `ultra/misc.c` | boot globals, cache no-ops, `osVirtualToPhysical`, virtual time, timers, `_Printf` / `gl_sprintf` / `gl_bcopy` / `gl_bzero`, init |
| `ultra/ultra-census.py` -> `ultra/provided.tsv` | what the port does with every libultra row of sourcemap.tsv, and the game bodies that call each one |
| `ultra/test_ultra.c` | self-test of the shim (separate executable; no game code, no ROM) |
| `host.h`, `host_headless.c` | the host layer (window / input / audio device / clock / files / log) and its headless implementation |
| `main.c` | entry point, fixed-step scheduler (9.6), input poll, FP setup, stand-in frame |
| `trace.h`, `trace.c` | trace logger: input record / replay, per-frame state dump |
| `port_libc.h` | host libc access for port code (`PORT_LIBC_DECLS_ONLY`: prototypes only, for compile checks without i386 libc headers) |

`port/main.c` replaces agent-a's stub `main` from e58ff9d67 (an add/add conflict when both land: take this one).
Nothing else in the tree is touched; the matching build is unchanged.

### 17.1 Model

- **One host thread runs the simulation** (decision 5). N64 threads are never run as host threads.
  `osCreateThread` fills the game's own OSThread (priority, id, state, `context.pc` / `a0` / `sp`, FCSR
  0x01000800) and links it into `__osActiveQueue` (tail = priority -1), so `dbg_printThreads`
  (`gl___osActiveQueue_34458_head`) still works.
- **Services.** `port_ultra_register_service(entry, step, name)`: when the game starts a thread with that
  entry, the pump calls `step(arg)` at every blocking point, highest priority first. A started thread with no
  service is **parked** (logged, counted). Today every game thread is parked: idle (`boot_halt`), main,
  RcpMgr, pad, fault. The main loop drives what they did (9.6.3).
- **Blocking never deadlocks silently.** `osRecvMesg` / `osSendMesg` / `osJamMesg` with `OS_MESG_BLOCK` on an
  empty / full queue go through `port_ultra_wait`:
  1. run the services (`port_ultra_pump`); repeat while any makes progress (capped);
  2. otherwise advance **one idle VI retrace** (what a blocked N64 thread waits for is the next interrupt:
     the retrace message, a timer, ...) and retry;
  3. after `maxIdleRetraces` (600 = 10 s of virtual time) report a **DEADLOCK** naming the queue; fatal
     by default (`deadlockFatal`), else the call returns -1.

  `osYieldThread` pumps; a yield loop with no activity at all (no message, event or DMA since the last
  yield) advances idle retraces and ends in the same deadlock report. That catches the flag spins
  (`gfx_waitRcpIdle`, `pad_waitIdle`) until their PORT restructure lands. Idle retraces are counted
  separately (`PortUltraStats.idleRetraces`); in a correct port run they stay 0.
- **Queues** keep libultra's ring arithmetic and the game's OSMesgQueue layout (`validCount` / `first` /
  `msgCount`), because game code tests `validCount` directly. The thread lists in the queue stay NULL.
- **Events**: `osSetEventMesg` table of 15; `port_ultra_post_event(e)` posts with NOBLOCK and drops when full,
  as the interrupt handler does.

### 17.2 Virtual time and devices

- **Time**: `osGetCount` = retraces x 781250 (46.875 MHz / 60). The main loop does 2 retraces per step,
  so during step N `osGetCount` = N x 1562500: the deterministic shim of 9.3. Nothing advances inside a
  step. `osGetTime` is the same 64-bit count; `osSetTime` offsets it. Timers (`osSetTimer` / `osStopTimer`)
  use the game's OSTimer next / prev and fire at retrace granularity.
- **VI**: `port_vi_retrace()` latches the swapped buffer, posts the `osViSetEvent` message every N retraces,
  and fires timers. `osViSwapBuffer` calls `host_frame_ready(fb)` (the Fast3D present in M2). `osViSetMode`
  reports the mode width to the host; `osViBlack`, `SetSpecialFeatures`, `SetX/YScale` are stored.
  `osViGetCurrentLine` = 0 (debug perf meter only); `osViGetCurrentField` = retraces & 1.
- **PI**: libultra's address rule (`osRomBase | devAddr`, or `handle->baseAddress | devAddr`), then the
  physical address picks the device:
  - 0x10000000.. ROM (read-only; the big-endian .z64 image in memory, copied as-is, swapping stays in the
    readers per 4.4);
  - 0x08000000.. SRAM;
  - anything else (64DD from `osDriveRomInit`) reads zeros and is logged once.

  Every DMA completes at once and posts its OSIoMesg to the return queue, so the `osRecvMesg(BLOCK)` that
  follows never waits. `osPiReadIo` returns the big-endian word as the CPU sees it.
- **SRAM save** (fs_gdl kind 2): `app_initSystem` builds the handle (baseAddress 0xA8000000) and
  `fs_gdlReadFile` / `fs_gdlWriteFile` DMA through `osEPiStartDma` with the running offset as `devAddr`.
  The shim maps that to a 0x8000-byte image backed by the save file (`--sram`, default `1080.sram`),
  rewritten after every write. A missing file is a zeroed SRAM: the Backup checksums reject it and the game
  formats a new save.
- **SI**: `input_poll()` (main.c, once per step) copies `host_read_pads()` into the SI. `osContStartReadData`
  snapshots the pads and posts `OS_EVENT_SI` (the queue the pad thread registered); `osContGetReadData`
  returns the snapshot, with `CONT_NO_RESPONSE_ERROR` for unplugged ports. `osContInit` reports
  `CONT_TYPE_NORMAL` for connected pads. No controller pak (`osPfsInitPak` = `PFS_ERR_NOPACK`); a rumble pak
  where the host can rumble (`osPfsIsPlug` / `osMotorInit`; `osMotorStart` / `Stop` -> `host_set_rumble`).
- **AI**: `osAiSetFrequency` uses libultra's dacRate maths (32000 -> 32006 Hz). `osAiSetNextBuffer` ->
  `host_audio_queue`, `osAiGetLength` -> `host_audio_buffered_bytes` (headless: 0).
- **SP**: `osSpTaskStartGo` runs `PortUltraConfig.rcpTask(task)` synchronously (Fast3D in M2, the
  `port/audio` mixer in M4), then posts `OS_EVENT_SP`, plus `OS_EVENT_DP` for `M_GFXTASK`. Yield is a no-op,
  `osSpTaskYielded` = 0.
- **Caches** are no-ops; `osVirtualToPhysical` is the identity (display-list and DMA addresses stay host
  pointers, 32-bit build). `osSetIntMask` only stores the mask.
- **Boot globals**: `osTvType` = NTSC, `osResetType` = cold, `osMemSize` = 4 MB, `osRomBase`,
  `osAppNMIBuffer`, `osClockRate`, `osViClock`. The game reads `osTvType` at 0x80000300 under the names
  `D_00000000_tvtype` / `gl_24378_osTvType`; both are aliases of `osTvType`.
- **printf**: `_Printf` (IDO va_arg, uncompilable) is vsnprintf + the game's `prout` callback; `gl_sprintf` =
  vsprintf; `gl_osSyncPrintf` / `gl_rmonPrintf` -> the host log.
- **gl_ names**: the game calls most libultra functions under game_libs copy names. Each is a `PORT_ALIAS`
  (gcc `alias` attribute) of the canonical function: `gl_osRecvMesg`, `gl_osCreateThread`, ...,
  `gl_26214_osAiGetLength` / `gl_26214_osAiSetNextBuffer` / `gl_26214_osGetCount` (AudioThread_Update's
  private names), `gl___osActiveQueue_34458_head`.

### 17.3 Coverage (`port/ultra/provided.tsv`)

`ultra-census.py` takes the libultra rows of sourcemap.tsv: game_libs functions at offset >= 0x69E04
(`osSendMesg`), `src/libultra/*.s`, the mixed hosts post1b2*, post1c, post2b*, and os / __os / gu names. It
finds the game bodies that call them by preprocessing every selected game body with `CALL(f)` / `FCALL(f)` /
`GCALL(f)` / `XCALL(t, f)` defined as `f`.

| action | rows | meaning |
|---|---:|---|
| shim | 67 | port/ultra defines it |
| decomp | 9 | compile the decomp body (portable C): `guOrtho`, `guOrthoF`, `guMtxF2L`, `guMtxL2F`, `guMtxIdentF`, `gl_guMtxIdent`, `guPosition`, `guPositionF`, `fsin`; `fcos` is a game_libs o2 row anyway (9.5: never host libm) |
| host | 3 | host libc: `memcpy`, `strlen`, `sqrtf` (use `-fno-math-errno` so it is `sqrtss`, the same IEEE result as `sqrt.s`) |
| drop | 90 | libultra internals no game body calls (`__osPfs*`, `__osSi*`, `__ll_*`, the exception / dispatch asm, `_Litob`, ...) |
| MISSING | 0 | |

**53 libultra functions are called by game bodies, and all 53 are provided.** By group:
- messages / threads: `gl_osCreateMesgQueue`, `gl_osSendMesg`, `gl_osRecvMesg`, `gl_osSetEventMesg`,
  `gl_osCreateThread`, `gl_osStartThread`, `gl_osSetThreadPri`, `gl_osYieldThread`,
  `gl___osGetCurrFaultedThread`;
- PI: `gl_osCreatePiManager`, `gl_osPiStartDma`, `gl_osEPiStartDma`, `gl_osPiRawStartDma`, `gl_osPiReadIo`,
  `gl_osPiWriteIo`, `gl_osCartRomInit`, `gl_osDriveRomInit`, `gl_osEPiLinkHandle`;
- SI: `gl_osContInit`, `osContStartReadData`, `gl_osContGetReadData`, `osPfsIsPlug`, `osPfsInitPak`,
  `osMotorInit`, `gl_osMotorStart`, `gl_osMotorStop`;
- VI: `osCreateViManager`, `osViSetMode`, `osViSetEvent`, `osViSwapBuffer`, `osViBlack`,
  `osViSetSpecialFeatures`, `gl_osViSetXScale`, `gl_osViSetYScale`, `osViGetCurrentLine`,
  `osViGetCurrentField`;
- SP / AI: `osSpTaskLoad`, `gl_osSpTaskStartGo`, `osAiSetFrequency` (`osAiSetNextBuffer` / `osAiGetLength` /
  `osGetCount` through the `gl_26214_*` aliases);
- misc: `gl_osInitialize`, `osGetTime`, `gl_osVirtualToPhysical`, `gl_osInvalDCache`, `gl_osInvalICache`,
  `_Printf`, `gl_sprintf`, `gl_rmonPrintf`, `gl_bcopy`;
- decomp / host: `guOrtho`, `guMtxF2L`, `fsin`, `memcpy`, `sqrtf`.

The shim also provides calls that RcpMgr / the audio thread make through names the scan does not see:
`gl_osSpTaskYield` / `Yielded`, `gl_osJamMesg`, `gl_osGetThreadPri`, `gl_osDestroyThread`, `gl_osSetTimer`,
`osSetIntMask`, `osWritebackDCache(All)`, `gl_osGetCount`, `gl_osSyncPrintf`, `osContStartQuery` /
`GetQuery`, `osStopThread`, `osJamMesg`.

### 17.4 Not covered yet

1. **Calls spelled as bare placeholders.** Mid-entry `UNNAMED` calls (`gl_func_00000000(...)` with a
   comment naming `osSetIntMask` = `gl_osSetIntMask+0x8`, `osWritebackDCache(All)`, `bzero` = `gl_bzero+0xC`)
   in `AudioHeap_*` / `Audio_*Cache` (game_libs_post.c) and `app_initSystem`. The shim has all of those
   functions, but the call sites need names before they can bind (section 16 plumbing). The kernel-named
   `bzero` is host libc's.
2. **Data the game reads from libultra's side:** `gl_osViModeTable_42938_rec` / `gl_osViModeTable_44B78_modes`
   (the VI mode table in game_libs Data; it comes from the data plan, and the shim only reads `width` from the
   chosen mode).
3. **Game-side PORT changes the shim is waiting for** (not in port/, owned by the integration work).
   **Done in run 615, see 17.7**; the list below is what was asked for:
   - `app_run` split into `app_runInit` / `app_runOneFrame` (9.6.2), and `port_game_boot()` (boot_main's
     manager setup + `SnowBoard_ctor` + `app_runInit`). main.c references them **weak** and runs a stand-in
     frame while they are absent.
   - `gfx_waitRetrace` -> `rcp->retraceCount++`, `gfx_end`'s retrace spin removed (9.6.3). Unchanged, they spin
     on a counter only the parked RcpMgr thread advances: the shim reports that as a deadlock.
   - Parked threads: the RcpMgr thread's work (gfx / audio tasks) becomes direct calls through `rcpTask`;
     the pad thread's request / reply becomes `input_poll` plus a direct `osContStartReadData` /
     `GetReadData` in `pad_requestGlobal` / `pad_waitIdleGlobal`; the fault thread is dropped. Alternatively a
     thread can get a service step, if its loop is split into "handle one message".
   - The trace hooks: `port_trace_pad()` in `pad_update` after `pad_decodeButtonMap_00034CC8`,
     `port_trace_frame_end(SysLib.frameCount)` at the end of `app_runOneFrame`, `port_game_frame_count()`,
     and a strong `port_trace_collect()` for the RaceProcess / rider / camera / DataManager / `retraceCount`
     fields. The weak default fills only the GameFlow state (`gInputMgr` +0x40 / +0x34) and the
     `sys_randf` state (`gl_ref_00021E04`).
4. **The kernel's own libultra** (174 kernel rows) is not needed: the kernel is replaced as a whole
   (port/uso, port/fs).
5. **Determinism with real devices:** with an SDL host, `osAiGetLength` reports real buffered bytes, so the
   audio driver's sample counts depend on wall time. Trace runs use the headless host. If audio moves to its
   own host thread (decision 5), `osGetCount` there must read a retrace snapshot taken at the step boundary,
   not the live counter.
6. **Not implemented** (the game does not call them): controller pak file ops, 64DD, `osViModeTable`
   interpretation beyond the width, `osSpTaskYield` semantics, interrupts.

### 17.5 main.c and the trace logger

- **Scheduler** (9.6.1-2): `step()` = `input_poll()` -> `app_runOneFrame()` (or the stand-in frame) -> 2 x
  `port_vi_retrace()`. Real-time mode accumulates host time and runs up to 4 catch-up steps per host frame,
  then drops the backlog, then `host_present()` and sleeps. The headless host runs the steps back to back
  (`--realtime` paces it). `--authentic` uses 1001/30000 s. `--frames N` stops after N steps; a replay
  stops after its last recorded frame.
- **FP**: MXCSR FTZ | DAZ, round to nearest, exceptions masked, set once on the simulation thread (9.5).
- **Trace format** (`trace.h`): text lines, floats as IEEE hex, so a port trace and an emulator trace diff
  exactly:
  - `I frame pad replayFrame held rawX rawY` (record: written; replay: read and injected). `held` is
    the decoded 32-bit PadCtl.held word as hex8 (input log v2, run 615; v1 had a u16 and lost START,
    0x40000);
  - `F frame have=.. flow=.. race=.. rand=.. rt=.. vi=.. el=.. cam=.. r<i>=...`. The `have` bits say which
    groups the collector filled.
- **Usage**: `1080 [--rom baserom.z64] [--sram 1080.sram] [--frames N] [--record in.log] [--replay in.log]
  [--trace state.log] [--authentic] [--realtime]`.

### 17.6 Verification

- **Compile check:** every file compiles with `gcc -m32 -malign-double -msse2 -mfpmath=sse -ffp-contract=off
  -std=gnu99 -O2 -Wall -Wextra -DPORT -DPORT_LIBC_DECLS_ONLY -Iinclude -Iport -c`, against the game's
  libultra headers (offset asserts on), with 0 warnings apart from the headers' known "variably modified"
  ones. The analysis machine has no i386 libc, so nothing 32-bit links here.
- **Behaviour:** a 64-bit build with the header offset asserts neutralised (scratch copies only) is enough
  to test the logic. `test_ultra` PASSes:
  - queue ring order, `osJamMesg`, full / empty NOBLOCK;
  - a blocking receive satisfied by the `osViSetEvent` message after exactly 2 idle retraces, with
    `osGetCount` = 2 x 781250;
  - a service-fed blocking receive (3 pump rounds, 0 idle retraces);
  - the active-thread list (re-create without duplicates, destroy unlinks);
  - deadlock reporting after `maxIdleRetraces`;
  - PI ROM DMA plus the message, `osPiReadIo` = 0x80371240;
  - SRAM write / read-back through an 0xA8000000 handle, persisted and reloaded from the file; ROM write
    refused;
  - timer expiry at the 3rd retrace;
  - `osAiSetFrequency(32000)` = 32006;
  - SI read through the `OS_EVENT_SI` queue; rumble pak present / absent per port.

  `main` with the real ROM and the stand-in frame: 100 steps, 200 retraces, 0 idle, 0 deadlocks. Then
  `--record` followed by `--replay` gives byte-identical state traces.
- **Matching build:** untouched (port/ only); gate PASS before commit.

**For the CMake (agent-a):**
- Port sources: `port/main.c`, `port/host_headless.c`, `port/trace.c`, and `port/ultra/{thread,message,vi,
  pi,si,ai_sp,misc}.c`.
- `port/ultra/test_ultra.c` is its own executable (shim + `host_headless.c`).
- Exclude every `provided.tsv` row with action shim / host / drop from libgame.a; keep the `decomp` rows.
- The `PORT_ALIAS` names (`gl_*`) must not also be defined by libgame.a.

### 17.7 Game-side PORT changes (run 615)

agent-g run 615, branch agent-g, commits bf1d11808 (port/ only) and 094182c10 (src/, all under
`#ifdef PORT`). Gate PASS on both (ROM byte-identical, 3288/3288, 0 source-check mismatches). Compiled
with the port CMake flags (`ninja` on the six touched units, 0 new warnings) and main.c / trace.c with
the 17.6 command.

**Rule for new PORT functions.** They name callees directly, never through `CALL()`: the gate's
`name-placeholder-calls.py check` pins every `CALL(X)` to a ROM relocation of its function, and a new
function has none. For the same reason they never use `D_00000000 + K`: port-gen-binds binds a
placeholder per function from the ROM TextReloc, so in a new function it binds to nothing. They
reach bootup.uso globals through the blobs instead: `port/include/port_game.h` has
`PORT_GAMEFLOW` (Bss 0xF8), `PORT_PADDEV` (0x3A4E8), `PORT_GFXLIB` (0x3C168), `PORT_SYSLIB`
(0x3C740), `PORT_RANDSTATE` (Data 0x21E04), and the debug label strings are
`port_bootup_data + K`, the same words.

| change | where | what |
|---|---|---|
| app_run split | `game_libs_ncc_34EB4.cpp` | `app_runInit(sys, app)`: the `sys_imin`, hostio check, `flags &= ~1`, the pre-loop Update, `snd_PlayPlayer0Seq0`, one RcpMgr drain. `app_runOneFrame()`: `pad_portFrame` -> `pad_update` per pad -> pre-NMI hook (v15) -> the `flags & 4` yield -> gfx_start / Update / Display / gfx_end with the same profiling labels -> `snd_FrameUpdate` -> `RcpMgr_portDrain` -> `frameCount++` -> one-shot callback -> `port_trace_frame_end(frameCount - 1)`. The unreachable outer-loop v13 is dropped. app_run itself is unchanged and uncalled |
| App_main | `game_libs_post0b.c` | ends in `app_runInit(gSysLib_415A4_s6, self)` instead of `app_run`, so the boot chain returns |
| `port_game_boot` | `game_libs_ncc_34EB4.cpp` | registers `RcpMgr_portStep` as the service of the RcpMgr thread (entry `D_4D468_a2 = RcpMgr_update`), calls `port_uso_init` (weak) and `boot_main_00066850(0)` -> SnowBoard_ctor -> App_main -> `app_runInit`; logs if app_runInit was not reached |
| `port_game_frame_count`, `port_game_retrace_count` | same | SysLib.frameCount, RcpMgr.retraceCount |
| retrace | `game_libs_post0b.c` | `gfx_waitRetrace`: `rcp->retraceCount++`. `gfx_end`: the "a retrace since gfx_start" spin becomes one increment when the count still equals gfx_start's (`D_44EDC_g`). The counter keeps 2 per frame |
| RcpMgr thread | `game_libs_ncc_4D688.cpp` | `RcpMgr_portDrain(mgr)`: every pending SysLib.msgQueue message through run()'s switch, NOBLOCK, re-entry guarded; run()'s entry state (`preNmi` = 0, ...) on first use. 'e' / 'f' / 'g' / 'h' / 'l' as run(). **'d'** calls `port_audio_frame()` (once per VI retrace, as `snd_AudioUpdate` ran), forwards to `m44` NOBLOCK on every other one, and no longer counts retraces or reads pads; the audio-task yield / resume path is gone. The chain is synchronous: `osSpTaskStartGo` runs `rcpTask` and posts 'e' / 'f' at once, so one drain takes 'h' -> startTask -> 'e' -> next task ... to idle |
| RCP waits | `game_libs_post0b.c` | gfx_end's two queue / idle spins and `gfx_waitRcpIdle` drain instead of yielding; a wait the drain cannot advance calls `port_rcp_stuck` (main.c: log + fatal) |
| pad thread | `game_libs_post1b.c` | `pad_portDrain(dev)`: pad_threadLoop's switch per pending message (5 stop motors, 1 rumble + `osContStartReadData`, 2 `osContGetReadData` + `pad_initMotors`, readDone). `pad_portFrame()`: drain, `pad_request_000671E4`, drain = one completed read per frame before pad_update (the N64 read every other retrace = once per frame). `pad_waitIdle_00067220` drains instead of yielding |
| input trace hook | `game_libs_o2_675A4.c` | in pad_update right after `pad_decodeButtonMap_00034CC8` (port != 0): `port_trace_pad(port - 1, frameCount, replayFrame, &held, &rawStickX, &rawStickY)`, before mirroring and the game's own replay block |
| state collector | `game_uso.c` | strong `port_trace_collect`: flow (`procState`, `nextFlowMode`), rand, rt always; while game.uso is loaded (port/uso registry): el = `dataMgr->elapsed`, race = `dataMgr->owner->raceState / flags`, riders = `dataMgr->entries[i].rider` as SnowBoarder (`dnode.vqs.trans`, `vqs.quat`, `dnode.speed`, `anim->state.b`), cam = GameFlow.game +0x108 window's MCamera (`mnode.world[3]`, target `world[3]` or eye + lookDir * 10) |
| host hooks | `port/main.c` | `rcpTask` dispatches M_GFXTASK -> `port_gfx_task` (weak no-op; Fast3D, M2), M_AUDTASK -> `port_audio_task` (weak no-op); weak no-op `port_audio_frame` (agent-c's strong one replaces it) |

main.c's weak references (`port_game_boot`, `app_runOneFrame`, `port_game_frame_count`) now have
strong definitions in libgame.a (nm: `T` in game_libs_ncc_34EB4.cpp.o); with `--whole-archive` the
stand-in frame is no longer used. New undefined symbols libgame.a takes from the executable:
`port_trace_pad`, `port_trace_frame_end`, `port_audio_frame`, `port_rcp_stuck`
(port/main.c, port/trace.c), `port_ultra_register_service`, `port_ultra_log` (shim), `port_uso_find`,
`port_uso_isLoaded`, `port_uso_init` (weak) (libuso.a), `port_bootup_bss` / `port_bootup_data`
(blobs). **For the CMake:** game_uso.c includes `../../port/trace.h` and `../../port/uso/port_uso.h`
by relative path; nothing new to add to the source lists.

**Trace caveats.**
- `animState` is the RiderAnim state PMF's function word: a host address on the port, a ROM address
  in an emulator trace. Map both to names (nm of the port binary, the ROM symbol table) before
  diffing.
- GameFlow.dataMgr / .game are never cleared when a race ends, so the race groups are only read
  while game.uso is loaded. If game.uso stays loaded between races (title demo -> race), those reads
  can follow freed heap; confirm the module lifetime in M3, or clear dataMgr under PORT in the race
  dtors.
- Frame numbering: both hooks use SysLib.frameCount at frame start (`F` lines carry the frame that
  just ran). main.c's replay stop (`frameCount > last recorded frame`) matches.

**What still blocks a headless boot once linking works** (in boot order):
1. **No SysApi.** (**Done in run 619, see 17.8.**) `gSysApi` (bootup Bss 0x416A0) points at the kernel's SysApi; nothing on the port
   fills it. boot_main reads `usoWarnNum` / `usoErrNum` / `memStart` / `memEnd` and stores six hooks;
   the game then calls `usoLoad` / `usoUnload` (-> port/uso), `heapNew`, `symLookup`, `dmaRead`,
   `tempAlloc`, ... A port SysApi (kernel replacement: heap region, port/uso, ROM fs) has to exist
   before `port_game_boot`; it fits in port_game_boot or a `port/kernel.c`.
2. **No port/fs.** (**Done in run 619, see 17.8.**) `fs_gdlFileInfo` / `fs_gdlRead*` and `dma_read` of named files (SnowBoard_ctor
   reads the audio seq / wave / bank sizes first) need the ROM file system (17.4.4 names it; it does
   not exist yet). SRAM is done (17.2).
3. **Byte order.** The blobs stay big-endian except the relocated words (16.5); every boot-time read of
   USO data (parm files, tables, the VI mode table) needs the 4.4 swap list. Until then values are
   wrong, not missing.
4. **Link plumbing left from 16.5:** the 17 C++ objects defined twice (static initialiser and blob
   alias see different memory: gGfxLib_412E8_a, gSysLib_412E8_i, ...; the boot touches all of them),
   the unit that defines `D_00000000`, the 120 ambiguous per-function binds (GfxLib_init is one:
   its `gl_func_00000000` sites and the `D_445AC_ga / gb` window size), and data references from data.
5. **Audio.** `port_audio_frame` is a stub: no audio frames run. Whether `snd_Init` or the first
   sequence load waits on the audio driver (an `osRecvMesg(BLOCK)` the shim would report as a
   deadlock) is for agent-c's wiring to show.
6. **32-bit libc**, to link at all: gcc-multilib, or the no-sudo sysroot (13.5).
7. Harmless, noted: GfxLib_init measures `frameTime` across one `gfx_waitRetrace`, which no longer
   advances virtual time, so it reads 0 and prints the "zero v frame time" debug line (only
   `sys_timeInFrames` reads it, with no game caller); the pad and fault threads stay parked (counted
   in `parkedThreads`); hostio stays off (its flag word is 0).

### 17.8 The kernel's SysApi, port/fs, and the boot path (run 619)

agent-g run 619, branch agent-g on main 2a1ec167d, commits 2d4058ea7 and 44ca56523 (port/ only) and
170519893 (src/, `#ifdef PORT` only). Gate PASS before both (ROM byte-identical, 3288/3288, 6405 named calls
0 mismatches). Compiled with the 17.6 command (`port/sysapi.c`, `port/fs/fs.c`, `port/trace.c`: 0
new warnings) and the two src units with the port CMake (`ninja` on their objects).

**The SysApi IS the kernel's loader context.** `uso_callEntry` calls bootup.uso's entry with
`&gUsoCtx`, and `boot_entry_00066C30` stores that argument in gSysApi. So the slots are `UsoCtx`'s
(include/uso.h; `uso_init` in kernel_000_1594.c fills them), and the file services are the kernel
bodies in kernel_000.c:

| SysApi slot | kernel | port (`port/sysapi.c`) |
|---|---|---|
| +0x00 memStart | `heapCur` after bootup.uso loaded (0x8015D858) | a static host arena |
| +0x04 memEnd | `heapLeft`: **a size, not an end** (`App_main`: `sys_getRegion(&a, &b); Mem_init(heap, a, a + b)`) | 0x2A27A8 = 0x80400000 - 0x8001FFA0 (mainuso heap) - 0x13D8B8 (bootup.uso's section allocations) |
| +0x08..+0x1C | USO error / warning words | 0 |
| +0x30 / +0x34 heapNew | `uso_alloc`; boot_main installs `mem_heapNewThunk` | logging stub (only the kernel loader called it) |
| +0x40 / +0x44 usoLoad / Unload | `uso_load` / `uso_unload` | `port_uso_load` / `port_uso_unload` (below) |
| +0x48 fileInfo | `uso_findDataSection` | `port_fs_info` |
| +0x4C fileOpen | `fs_openFile` | `port_fs_open` |
| +0x50 fileRead | `fs_readChecked` | `port_fs_read` |
| +0x54 fileSeek | `fs_seek(file, whence, offset)` | `port_fs_seek` |
| +0x58 fileClose | `fs_closeFile` (no-op) | `port_fs_close` (returns the handle to the pool) |
| +0x5C fileError | `uso_getErrno` | `port_fs_errno` |
| +0x60 fileRomAddr | `fs_tell` = romStart + pos | `port_fs_tell` (a ROM address: the PI shim serves `dma_readAsync` from it) |
| +0x70 symLookup | `uso_addrToModule` (module name, Text offset) | `("host", addr)`: no module Text ranges on the port; nm names the address |
| +0x74 usoPreLoad | `uso_clearMemStats` (args ignored) | no-op |
| +0x80..+0x9C | kernel defaults, replaced by boot_main / app_initSystem | inert defaults (nullPrintf, nop, 0.0f) |
| +0x3C, +0x64..+0x7C, +0xA0 | init, callEntry, getModuleName, printVersion, printMemStats, printModules, printSlots | log "not implemented" (no game caller known) |

`port_game_boot` calls `port_sysapi_install()` (weak) after `port_uso_init` (which zeroes bootup Bss,
where gSysApi lives) and before `boot_main_00066850`.

- **usoLoad of a module port/uso does not carry** (`port_uso_load` = -0x14, but port/fs has the
  file: audio banks, course / rider data, the `*.bin` names): the load is accepted, logged, and
  tracked for -0x13 / unload. Whatever the game then reads from that module goes through fileInfo /
  DMA (ROM) or the blobs; references into data-only modules that are not blobs are the 16.5 "80
  into data-only modules not kept" words, a link-plumbing item.
- **K&R pass-through:** `fs_gdlSeekFile` called `SYSAPI->fileSeek(o->handle)`; the kernel's
  `fs_seek(file, whence, offset)` read a1 / a2 as they rode through from fs_gdlSeekFile's own
  arguments. Under PORT it passes them (game_libs_post0b.c). The other SysApi call sites pass every
  argument the kernel reads. `mem_heapNewThunk_00041258` (`return heap_new();`) has the same
  pass-through shape, which is one reason the port never calls the table's heapNew.
- **Handles:** on the N64 `fs_openFile` takes 0x28 bytes from the current heap through the +0x34
  hook (the game's heap after boot_main) and never frees them; the port uses a 64-entry pool. Heap
  addresses differ on the port anyway.
- **Reads** copy from the ROM image. On the N64 `fs_read` went through +0x80 (`dma_readChunked`
  after boot_main), i.e. PI DMA of the same bytes; skipping it avoids DMA-queue traffic.
- `boot_reloadMainUso` (usoUnload + usoLoad of the main module) would re-run bootup.uso's
  `module_reset` on the port: Bss zeroed, as the N64's reload. Only a debug path calls it.

**port/fs** (`port/fs/port_fs.h`, `fs.c`) has the kernel's semantics over the in-memory ROM image
(the PI shim's `PortUltraConfig.rom`). The extracted tree is not used: fileRomAddr hands the game
a ROM address that it DMAs from, so the image must be there anyway.
- Devices from the kernel's table at ROM 0xAE60 ("mainuso" 0xD9FDB0..0xE984B0, "rom"
  0xB7C0..0xD9FDB0). Directory = `uso_scanRom`: per Info record with module id >= 0, the name and
  the device offset just past the Info record (131 files).
- Lookup = `uso_find_file`: split at the first `/`; the device gives romStart; the file is found
  **by name only** (the N64's slot table is global). Unknown device or name: -0x11.
- Open = `fs_openFile`: read the first record's 12-byte header; the window is its payload (a
  `.bin`'s BinaryDataSection, a USO's first section). Read = `fs_read`: buf 8-aligned (-0x1C),
  clamped to the window, raw big-endian bytes (Yay0 stays compressed). Seek: whence 0 sets the
  device offset, else adds. Tell = romStart + pos.
- Info = `uso_findDataSection`: walk the records (Bss has no payload) to Data; returns the ROM
  address of its payload. Two deliberate differences from the kernel, both only on paths the
  kernel would turn into garbage: the walk stops at EndOfFile / the device end (-1000; the kernel
  wanders past it), and a read past the limit returns 0 bytes (the kernel's unsigned clamp wraps).
- `port/fs/test_fs.c` (host build, the user's ROM): 23 checks, 0 failures. A scratch cross-check of
  all 131 files (id, open window and size, first bytes, Data address) against extract.py's
  `walk_device`: 131 / 131 agree.

**gInputMgr (trace.c).** There is no `gInputMgr` symbol on the port: the game spells it
`D_00000000` (gl_data.h `#define gInputMgr D_00000000`), bound per site. trace.c's default
collector now reads `port_bootup_bss + 0xF8` (weak), so `gInputMgr` leaves port/undefined.txt and
nothing is needed in aliases.ld.

**For the CMake (agent-a):** add `sysapi.c` and `fs/fs.c` to the port host sources
(`PORT_HOST_SOURCES`, or a `portfs` library linked with `uso` / `ultra`). `sysapi.c` needs
`port_bootup_bss` (blobs), `port_uso_*` (libuso.a), `port_ultra_cfg` / `port_ultra_log`
(libultra.a). `port/fs/test_fs.c` is a host test needing only `fs.c` and the ROM.

**Static boot-path trace** (run 619; read from the sources the sourcemap selects, nothing run: no
i386 libc here). The actual chain, with the vtable slots worked out from the bootup Data relocs
(`VT_SLOT`, +8 bias):

`port_game_boot` -> `boot_main_00066850` -> `SnowBoard_ctor` -> vtable +0x5C = **App_main** ->
+0x6C **SnowBoard_restart** -> `App_restart` -> slot 13 `SnowBoard_softReset` -> **App_softReset**
(C++ donor 41820), then slot 15 **SnowBoard_InitInstance** -> `GameFlow_create` /
`GameFlow_startMode(0)` -> n64proc vtable slot 0 = **n64_procMain**; back in App_main ->
`app_runInit`. (`boot_startThread_00066B64` is the N64's real entry into boot_main: it starts the
main thread there and writes the stack canary; the port skips it.)

| step | external service / data read / wait | status |
|---|---|---|
| port_game_boot | RcpMgr service; port_uso_init (bootup.uso + static initialisers); **port_sysapi_install** | covered (app_staticInit's `mem_new` bind is ambiguous: 16.6) |
| boot_main | osCreateViManager, osCreatePiManager, osViSetMode (VI mode table, big-endian: `width` wrong, harmless headless), SetSpecialFeatures, osViBlack; dma_init (10 queues); SysApi warn / err / memStart / memEnd; the six hook stores | covered (shim, SysApi) |
| SnowBoard_ctor | `fileInfo` x3: rom/audio_seq.uso, audio_wave.uso, audio_bank.uso (data-only: fileInfo, no usoLoad); `snd_Init` -> AudioLoad_Init (queues, osCartRomInit / DriveRomInit, heap pools, `port_audio_swap_static`; no blocking receive, no DMA); App_ctor | covered |
| SnowBoard_ctor | `SNOWBOARD_E800->vptr = ...` = a store to `stream_readS32_00000008 + 0x20` | **BLOCKS**: on the port that symbol is a function in .text (SIGSEGV); the object is gSnowBoard (bootup Bss 0x58) + 0x28. The ROM spelling needs a PORT form (`port_bootup_bss + 0x80`) |
| SnowBoard_ctor, app_runInit / app_runOneFrame, App_softReset | C++ virtual calls (`root->f()`, `a1->v3 / v4 / v15`, `v12`) | **BLOCKS**: g++ reads the vptr at +0 with 4-byte entries; the game's objects hold a cfront vptr at +0x28 with 8-byte entries (16.6's `_ZTV` question, now on the boot path) |
| App_main | sys_getRegion + Mem_init (memEnd as a size); app_initSystem: console window, fault thread (parked), pad_initGlobal (osSetEventMesg SI, osContInit, osPfsIsPlug / InitPak, osMotorInit; pad thread parked), SRAM handle | covered |
| App_main | `sys_pollDevices` -> `boot_checkStacks_00066AF0` | **BLOCKS**: the canaries are never written (boot_startThread skipped) and the checker reads `gl_storage_66B64_threadRegion`, which match_imports' context defines as its own host array: sys_fatal ("mainThread stack overflow") and `for (;;)`. Runs twice before InitInstance |
| App_main | `pad_sendMsg` (osSendMesg BLOCK, queue of 4) twice before the first `pad_portFrame` | unknown, low: a full queue would be a DEADLOCK report |
| GfxLib_init | RcpMgr_ctor (`dma_read(0xB0000B70, 0x100)`: shim PI + immediate message), `gfx_waitRetrace` x3, osViSetEvent | covered (17.7); `gl_func_00000000` / `D_445AC_ga / gb` binds ambiguous |
| dma_read | `dma_writebackCache` callees are mid-function entries (`gl_osSetIntMask+0x8`, `gl_osWritebackDCacheAll+0x4`) | link (binds-left) |
| App_softReset | `import_80000310 != 0x17D7` -> sys_fatal | **BLOCKS**: osCicId (CIC-6103) is unresolved (undefined.txt, binds-left 132 / 167); the shim should define it = 0x17D7 and alias the token |
| App_softReset | dma_waitAll, gfx_waitRcpIdle (drain), GfxLib_reset | covered |
| SnowBoard_InitInstance | `fs_readRecord("rom/version.bin")`: fs_gdlOpenFile / ReadFile / CloseFile -> fileOpen / Read / Close; AnimDataMgr_ctor -> Node_Load("rom/anims.bin") | covered by port/fs; the fs_gdl* `D_00000000` sites are ambiguous (gSysApi 0x416A0 vs gHostio 0x3C768) |
| SnowBoard_InitInstance | `sys_getResetType` reads `D_35360_X` (osResetType) | link: unresolved; alias it to the shim's `osResetType` (0 -> mode 0 = N64DEMO) |
| GameFlow_create | `app_loadUso("rom/gui.uso")` (usoPreLoad + usoLoad; gui is in port/uso); pad_open x2; Backup_ctor / readOptions (SRAM); ImageFileMgr_ctor("rom/flowimgs.bin"); TextWin_ctor | covered |
| GameFlow_startMode(0) | `app_printHeapOfType != 1` -> sys_fatal ("FLOW free blocks") | unknown: depends on the heap state |
| GameFlow_startMode(0) | mode table (bootup Data 0xC52C, big-endian; entry 0 is 0 either way), `gModeUsoPaths[0]` = "rom/n64proc.uso"; loadProcUso -> usoLoad (in port/uso) | covered |
| GameFlow_startMode(0) | `VT_SLOT(vptr, 0).fn` = n64proc Data 0xA4 -> n64_procMain | **BLOCKS**: every Text target in the blobs' reloc tables is 0 (below) |
| n64_procMain | snd_playSeq, N64DemoProcess_ctor -> gui_spriteLoad x2 (big-endian sprite data), Fader_start, snd_postEvent, app_runProcess | covered (byte order: 16.5) |
| app_runInit / OneFrame | hostio off (flag word 0); snd_PlayPlayer0Seq0 (queued); `while (flags & 4) yield` (not restructured); RcpMgr / pad drains, gfx_end | covered / unknown (the flags & 4 loop) |

No blocking receive on this path waits on a parked thread's queue: each one follows a PI / SI action
the shim completes at once.

**Still blocks a headless boot, ranked:**
1. **Every Text target in `port/gen/uso_modules.c` is 0** (1 bound, 3303 written as 0; 16.5 had
   3161 bound): vtables and callbacks in every module blob are NULL. Cause: 785b18c0b made
   `port_defined()` (port-gen-binds.py) return `(defs, data)`; `port-gen-uso.py` line 49 still does
   `defined = pgb.port_defined(a.lib)`, so `nm in defined` is always false. Fix (agent-a):
   `defined, _ = ...` and regenerate.
2. **C++ virtual calls use the g++ layout** (vptr at +0, 4-byte entries); the objects hold a cfront
   vptr at +0x28 with 8-byte {delta, fn} entries. On the boot path: SnowBoard_ctor `root->f()`,
   app_runInit / app_runOneFrame `v3 / v4 / v15`, App_softReset `v12`. Needs a PORT spelling of
   these calls through `VT_SLOT` (as the C callers do) or a donor-wide answer (16.6).
3. **SnowBoard_ctor's vptr store** targets `stream_readS32_00000008 + 0x20` (a function on the port).
4. **Stack canaries:** boot_checkStacks fatals; port_game_boot should write the canaries the way
   boot_startThread_00066B64 does, into the array the checker reads (or the checker's region must be
   aliased to bootup Bss).
5. **osCicId** (`import_80000310`) and **osResetType** (`D_35360_X`) unresolved; App_softReset fatals
   unless osCicId = 0x17D7.
6. The ambiguous binds on this path (16.6): fs_gdl*, dma_writebackCache, GfxLib_init, App_softReset,
   app_staticInit, SnowBoard_InitInstance, GameFlow_create / startMode / loadProcUso.
7. Unknown: the "FLOW free blocks" heap check, the pad queue depth during boot, the `flags & 4` yield
   loop.
8. Byte order (17.7 item 3) and audio (15.6) as before; neither stops the boot by itself.

**Run 623 (agent-g, on main b8596e397): blockers 2-5 done.** Commits on agent-g: 12041903d (C++
donors) and 1d19c1716 (code-symbol data tokens, canaries, osCicId / osResetType). Both src/ edits
are `#ifdef PORT` only; gate PASS before each (ROM byte-identical, 3288/3288, 6405 named calls 0
mismatches). Port build (`cmake -S port`, `ninja`): game, uso, ultra, porthost compile.

- **C++ virtual dispatch (blocker 2): the cfront layout, class by class.** `port/include/port_cfront.h`.
  Under PORT, each donor class with virtuals is declared without `virtual`:
  - an explicit `char *vptr` member where cfront puts it, after the introducing class's own data.
    That is +0x28 for the Node prefix, +0x5C for BaseMat, +0x598 for the PolyShape Strip / Rec, +0x18
    for the SysLib pair in 412E8, and +0 for the data-less K / Base / O0;
  - one `CF_Vk(R, name, slot, args)` line per virtual. It defines an always-inlined member with the
    virtual's name that calls `VT_SLOT(vptr, slot).fn(this + delta, ...)`, so the call sites are
    unchanged;
  - the constructors write the NCC vtable stores explicitly, using the name the Makefile objcopy
    gives `__vtbl__*`. Where that name is a shared token, they use the bootup Data offset
    `uso-data-sites.py` reports instead: LookAtMNode 0x1EAA8, Bb4Base / Mid / Bank 0x20640 / 0x1FBEC
    / 0x8440, Rec 0x1F7A8;
  - BasePolyShape's `copy()` keeps the vptr, because the cfront `*this = *o` skips +0x28 (checked
    in the target).

  Before the change, the gimple of the 219 port C++ units had 56 virtual call sites (OBJ_TYPE_REF)
  in 30 units and g++ vptr stores in 26 classes in 14 units. Now there are 0 and 0, and `_ZTV*`
  (17 symbols) and `_ZN11LookAtMNode1gEv` have left the undefined list. The g++ slot index is the
  cfront slot index (declaration order), checked against every donor comment that names a vtbl
  offset. Rescan: dump `-fdump-tree-gimple` per unit, then grep `OBJ_TYPE_REF` / `_vptr.`.
- **Aliasing hazard found on the way (SnowBoard_ctor).** The vptr store went through one spelling
  and the virtual call's vptr load through `D_00000000`, which binds to the same object only at the
  asm level (cc-select). gcc treated them as distinct objects and **hoisted the load above the
  store**. Fixed by spelling both through `port_bootup_bss`. Any function that writes through one
  token and reads the same object through another (or through a direct `port_*` spelling) can be
  reordered the same way. A tool check would list the functions whose binds map two tokens onto
  overlapping blob ranges.
- **Code-symbol data tokens (blocker 3, generalised).** A scan of `objdump -dr libgame.a` for
  R_386_32 data operands against function symbols found 14 functions, all bootup.uso:
  - GameFlow_create / startMode;
  - Process_update / fadeOut;
  - Fader_display, ScreenThumbMat_grab, Mountain_display;
  - EnvSettings_load, QuitProcess_ctor, game_createProcessWindow;
  - RiderCam_update, gui_centerRows, item_registerTemplates, SnowBoarder_loadBoardModel.

  Each now has a PORT spelling of the site's blob address. **The same token means different
  addresses in different functions**: `stream_readQuad_000000F0` is Bss 0xF0 in GameFlow_create and
  GameFlow + 0x134 - 0x44 in game_createProcessWindow. So these are per-site, not aliases. Rescan:
  0 left, counting immediates with a nonzero addend as well.
- **Canaries (blocker 4):** `boot_checkStacks_00066AF0` returns at once under PORT (no N64 stacks).
- **osCicId / osResetType (blocker 5):** port/ultra/misc.c defines `osCicId = 0x17D7` and
  `PORT_ALIAS`es it to `import_80000310`; `osResetType` (0) is aliased to `D_35360_X`.

**Re-walk (static) after run 623.** SnowBoard_ctor now installs the vtable at Bss 0x80 and calls
slot 10 through it. App_main, app_runInit / OneFrame and App_softReset's v3 / v4 / v12 / v15 go
through the ROM vtable slots. The O44 node is built with its Data 0x1F748 vtable, and the CIC
check passes. GameFlow_create / startMode read the TextWin word at Bss 0xF0, and
Process_update / fadeOut and Fader_display read GameFlow / gGfxLib. **Still blocks, ranked:**
1. **Text targets in `port/gen/uso_modules.c`** (item 1 above; agent-a). Every slot that
   `CF_Vk` / `VT_SLOT` now reads is a NULL fn until it is regenerated. This is the first crash
   after the boot-time ctor (slot 10 of the SnowBoard vtable).
2. **Ambiguous / missing binds on the path** (16.6, agent-a): as listed above, plus two:
   - Process_exit stores `&func_00000000` (a defined placeholder body) where the ROM stores
     `GameFlow_restart_000116C8`. A non-call function reference is not bound by the binds;
   - PolyShape_init's `D_00000000+0` is ambiguous between gSysLib and the Rec vtable (the vtable
     use is now spelled out; the two gSysLib uses still need the bind).
3. **Mem block header bitfield** (18.3 item 6, `Bf5B5D8`): every heap's `Mem_setBlockType`
   corrupts sizes on x86. It is the first heap call in App_main (`Mem_init`).
4. **cfront pointers-to-member** (M3, not boot): game_uso keeps RiderAnim state PMFs (`Pair2`) as
   cfront `{s16 delta, s16 index, fn}` data. `RiderAnim_update_0000D204` runs them with
   `(a3->*pm)()`, which g++ decodes as its own `{ptr, adj}`. It needs a PORT spelling that decodes
   the cfront form, the same way CF_Vk does for virtuals. `A` in the game_uso donors is still a g++
   polymorphic class: it is only a PMF / pointer type there, with no member access, and must go
   when the PMF call is respelled.
5. The aliasing hazard above: audit the functions whose bound tokens overlap.
6. Unknown, as before: the "FLOW free blocks" heap check, the pad queue depth during boot, the
   `flags & 4` yield loop.
7. Byte order (18) and audio (15.6). Neither stops the boot by itself.

## 18. M1/M2: byte order (run 620)

agent-c run 620, on main 2a1ec167d. Commits on agent-c: 261bc1b15 (blob type map + swap hook,
tools only) and 9bc3fa3e7 (game_libs reader swaps under PORT). Gate PASS before each (ROM
byte-identical, 3288/3288). This section is uncommitted.

### 18.1 USO data blobs: swap at blob-build time, by type (option a)

Decision: **(a)**, a typed swap when the blob is built. Option (b), swapping at each read site,
would mean editing thousands of loads through `D_00000000 + K`, and every C++ vtable / table walk.

- **Generator:** `scripts/port-gen-blob-types.py [--report]` (needs `baserom.z64`, no build) writes
  `port/gen/blob_types.tsv`: `module, section, offset, size, type, source`. It contains no ROM bytes.
- **Hook:** `port/tools/blob_swap.py`. `gen-uso-blobs.py` calls `swap_section()` on each Data /
  RoData section and incbins the swapped copy (`<out>.swapped/port_<mod>_<sec>.bin`).
  - Runs typed u16 / u32 / f32 / u64 / f64 are reversed per element.
  - u8, str, zero, unknown, conflict, ptr and audio stay as on the cartridge.
  - CMake now depends on both files. agent-a: the only change to your tool is that hook call.
- **Typing sources.** All of them come from the ROM's own USO records, so modules with no `src/`
  are covered too:
  - **access:** every HI16/LO16 TextReloc pair in every module's Text, with imports followed to
    the exporter. The LO16 opcode gives the width (lb/lh/lw/lwc1/ldc1/ld and the stores).
  - **field / index:** an `addiu %lo` base is followed forward through the function. Loads off
    `base + k` type that field. Loads off `base + index` type one element, and the run is
    extended to the next symbol or pointer target. Float runs stop at an implausible exponent or
    at text: bootup RoData 0x2588 `"NaN\0Inf\0"` ends the powers-of-ten table.
  - **ptr:** DataReloc / RoDataReloc words. port/uso writes them in host order, so they are never
    swapped.
  - **shape:** shape command streams (GRAPHICS 7.1). On the cartridge each command word is
    `argc << 16 | op`, which makes the stream self-describing. Their arrays are typed too:
    - op 27 verts: s16 x 3 per vertex;
    - op 28 tris: PolyTri, u16 x 4;
    - op 26 triList; op 32 remap: u16;
    - op 34 normals: f32 x 3;
    - op 9 vertex colours: u32;
    - op 4: s8 x 3 per vertex (charsel 0x60CD8 = (0, -127, 0) x 4: byte normals);
    - op 7 / 8: bytes.
  - **mats:** GDL_MC material streams reached from op 29. The parseMats tokens are 100 / 101 / 0,
    and each material is commands up to 0. A material's op 203 types its texture:
    - texels stay **bytes**, because libultraship's Fast3D reads texels and TLUTs big-endian,
      byte by byte;
    - image records (`texFlags & 0x10`, 5 words) and CI records (4 words) are u32.
  - **str:** printable runs of 4 or more bytes ending in NUL. **zero:** runs of 8 or more zero
    bytes.
  - **audio:** bootup Data 0x17D50-0x1A2E0, 0x1CB00-0x1CDE0 and 0x1D620-0x1E0D0. These are
    excluded because `port_audio_swap_static` swaps them at run time (15.6).
- **Coverage (1,121,552 blob bytes):**

  | type | bytes | % |
  |---|---:|---:|
  | unknown | 585,197 | 52.2 |
  | u8 (texels, byte arrays) | 323,464 | 28.8 |
  | zero | 72,533 | 6.5 |
  | u16 | 54,312 | 4.8 |
  | str | 28,490 | 2.5 |
  | ptr | 22,812 | 2.0 |
  | u32 | 18,644 | 1.7 |
  | audio | 13,088 | 1.2 |
  | f32 / f64 | 2,240 / 768 | 0.3 |
  | conflict | 4 | 0.0 |

  So **47.8% is typed**. Code-module coverage is high:
  - every proc USO is at 0-1% unknown, except titproc 26%, genproc 32% and game Data 33%;
  - bootup RoData 8% unknown; bootup Data 34%;
  - the boarder banks 4-12%; heli, charfir and charsps 0-3%.
- **Unknown, by module:**

  | module | unknown bytes | % of the section |
  |---|---:|---:|
  | charsel | 393 K | 98 |
  | map5_data | 69 K | 96 |
  | bootup Data | 64 K | 34 |
  | gamegfx | 15 K | 80 |
  | fire | 9 K | 96 |
  | titproc | 5 K | |
  | n64proc | 4.5 K | |

  - **charsel:** 256x256 8-bit images, 0x200 TLUTs and 16-byte records {0x110, 0x100, image ptr,
    TLUT ptr}, which genproc code loads, not a material stream. Texels need no swap, so leaving
    them unknown (unswapped) is right. The records are 4 x 4 words, about 0.1% of the bytes.
  - **map5_data:** the course PolyShape and its collision grid (op 35 collGrid; layout open,
    ENGINE_CORE / SYSTEM_LAYER 7). Only 2 KB of shape arrays were found. The **course mesh is
    the biggest correctness gap** for M3.
  - **bootup Data 64 K:** game_libs tables reached only through pointers or C++ objects, such as
    vtables (ptr) and the data of objects the static initialisers build.
  - Known mis-typing: `osViModeTable` (bootup Data 0x2D71C, 0xD04 bytes) is typed u32 by an
    index run. Its first byte, `type`, is a u8 and would move. The port's VI shim does not read
    the table.
- **Conflicts:** 4 bytes at bootup Data 0x1C0AC-0x1C0AF, read as a u32 and as a u8 at +3. They are
  not swapped, and the reader must be fixed at the read site.
- **Rerun** the generator whenever `port/gen/uso_blobs.tsv` changes (agent-a's port-gen-uso.py).
  `--report` prints the per-module table and the conflicts.

**Still to do (M2):**
1. Type the charsel / gamegfx image records from the genproc readers.
2. The map / collision format (needs COURSE 5).
3. The skin / anim / node-list data inside the boarder banks. 4-12% of each bank is still unknown.
4. Feed the C declarations of `kRo*` and `D_*` objects in `src/` in as a further source, by array
   type and dims through aliases.ld. The ROM-access pass already catches every scalar they load.

### 18.2 rom/*.bin files: swap in the readers (implemented for game_libs)

| family | format | reader | treatment |
|---|---|---|---|
| parm streams (`board1-9`, `player*`, `racecol`, `selinfo`, `selwin*`, `1psel`, `2psel*`, `flare3/5`, `cam_ca`, `lookat_ca*`) | {tag char[4], size s32, int / float / quad / vec3}, ending with tag -1 | `Parms_load_00035C6C` (match_imports) and the per-class read slots | reader swap |
| env (`map0N*_env`, `halfpipe_env`, `onemake03_env`) | {tag, size, op payload} records up to 0, then flags and clip words | `EnvSettings_load` (donor bootup_uso_ncc_7328.cpp) via `stream_readS32_*` | reader swap (bootup copies: to do) |
| items / markers (`map0N_item` / `_mark`, ...) | ItemMgr stream: type tag, size, count, pos 3 x s32, parm stream | `ItemMgr_Load`, `ItemType_load`, `ColourItem_load`, `CourseMarker_readParms` | reader swap (the layout does not matter at the reader) |
| `cam_info.bin` | numPaths, then CamPaths (Quad modes, keys of 0x38 bytes, all 4-byte fields), then lists | `cam_readParms_00001644`, `camPath_read`, `camKey_read` (game_uso) | reader swap (game_uso `stream_read*`: to do) |
| `anims.bin` | {cmd, val} records; AnimKey 8 bytes; frame data s16 x 7 per node key | `AnimDataMgr_loadFile`, `AnimGroup_load`, `AnimData_load` | **at extraction**: bulk `fs_gdlReadFile` reads walked as s16 later; the stream describes itself |
| `flowimgs.bin` | ImageFile {cmd: 1 = w, h; 2 = format; 4 = size + texels; -1 = end} | `ImageFile_load_00068990` | reader swap for the cmds (done: 681F4 / 68280 / 682BC); texels stay bytes |
| `tricks.bin`, `version.bin` | 64-byte entries (name + mixed u16 / u32); AppVersion s32[17] + strings | `TrickTable_readEntry_0000C12C`, `fs_readRecord_00041F90` | at extraction, once the layouts are decoded |
| shape assets in `mapN_data.uso` | USO Data | (18.1) | blob swap |

- **No swap in `fs_gdlReadFile`.** It does not know field widths, and bulk reads have the same
  sizes as the templates (AnimData keys: n = val x 8).
- **The readers are a template copied 155 times.** Each copy reads 2 / 4 / 12 / 16 bytes through
  `fs_gdlReadFile` into a scratch buffer and assigns it.
- **Done (9bc3fa3e7):** the 51 game_libs copies that use the `CALL(fs_gdlReadFile)(&gSysLib, buf,
  N)` form (`fs_gdlRead{Int,Float,Quad,Vec3}_*`) now call `PORT_BE_SWAP32S(buf, N)` under PORT
  before the assignment. The macro lives in `port/include/port.h`, which every port TU
  force-includes.
- **Tag hazard: `fs_gdlReadInt_00035AA4` is left unswapped.** It is Parms_load's tag reader. Tags
  are compared against `*(s32 *)"ied"` loads from USO Data, which stay unswapped (`str`). An
  unswapped file tag compares equal on any host. The end marker -1 is the same in both orders.
  `fs_read_00066404` is also left alone (use unknown).
- **To do:** the FCALL / GCALL / XCALL copies:
  - `bootup_uso.c`, `bootup_uso_o0_F1F0.c`, `bootup_uso_tail4.c`: `stream_read{S32,F32,Vec3,Quad,16}`;
  - `game_uso.c`;
  - the `_edd_ / _h2h_ / _mgr_ / _tit_ / _arc_ / _boarderN_` copies.

  Same one-line insertion: `PORT_BE_SWAP32S`, and a 16-bit variant for `stream_read16_000089FC`.
  Before swapping any of them, check whether its caller reads a tag with it: `stream_readS32_00005EF8`
  in EnvSettings, and ItemMgr_Load's own 4-byte tag read must stay unswapped.

### 18.3 Bitfield audit

IDO allocates bitfields MSB-first, gcc / clang on x86 LSB-first. A bitfield word is a problem only
when (i) it comes from cartridge data, or (ii) one access goes through the bitfield and another
through masks, shifts or byte loads. If every access goes through the members, the word is
consistent on any compiler, **as long as every view agrees**. That last condition is the catch:
each audio flag word is redeclared in about 30 per-file local views. A reversal under PORT must
therefore cover every view at once, or none.

| struct (decl) | unit | data from | mixed access (evidence) | PORT treatment |
|---|---|---|---|---|
| `Sample` + 6 views (audio.h:136, post.c 6915 / 7061 / 3413 / 4074, ctx) | u32 | cartridge fonts | `GL2495C_*` (already PORT) | **done** (15.6 re-pack) |
| `NoteSampleState` (audio.h:692 + ~8 views) | u32 / u8 | runtime; template `gDefaultNoteSub` in bootup Data (byte 0 bit-reversed in 15.6) | post.c:276 `*(u8 *)elem & 0xFF7F` (clears `enabled` as bit 7) | accessor: `0xFFFE` under PORT |
| `SequencePlayer` (audio.h:419 + 9 views) | u32 (byte 0) | runtime | post.c:7646, 7949 `*(u32 *)p >> 31`; match_imports/AudioSeq_InitSequencePlayer.c:9-13 byte masks 0x80 / 0xDF / 0xF7 / 0xEF / 0xFE | **accessors**: keep the declarations; `AUDIO_FLAGBIT(n)` = `1 << (7 - n)` on IDO, `1 << n` on PORT; `>> 31` becomes `*(u8 *)p & 1` |
| `SequenceChannel` (audio.h:472 + views) | u32 (bytes 0-1) | runtime | post.c:7953, 9726 `>> 31`; 9584-5 `(w << 9) < 0`; 9581 / 9618 `changes \|= 0x80`; 10392-3 `& 0xFF7F`, `\| 0x40` | accessors (same macro, byte 1 for `changes`) |
| `SequenceLayer` (audio.h:547 + ~10 views incl. ctx `GlPooledFlags`, post.c:8707 plain `u8 bits0`) | u32 / u8 | runtime | post.c:7960 `>> 31`; 8732 `&= ~8`; 9623-7 `& 1`, `& 0xFFFE`; 10270-80 `\|= 0x80`, `&= ~0x40 .. ~0x01` | accessors |
| `Stereo` union (audio.h:394 + 3 views) | u8 | **sequence script bytes** (cartridge) | 2BB7C:352 `asByte = cmd & 0x7F`; 2AD1C:176 `asByte = ScriptReadU8`; 273B8:88 | **bit-reverse the byte** at the 3 `asByte =` writes (`port_bitrev8`), or reversed declarations in all 3 views |
| `AdsrState.action` (audio.h:632 + 4 views) | u8 | runtime | post.c:8192-4 `(f60 & ~0xF) \| 1`, 8223 `&= ~0x0F` | reversed declarations in all 5 views, or 2 accessor sites (`& ~0xF0`, `\| 0x10`) |
| `Bf5B5D8` Mem block header (post0b.c:22679, used at 22681) | u32 | runtime heap | Mem_* whole-word masks `& 0xFFFFFF`, `>> 24`, `(x & 0xFF) << 24` | **reversed declaration** under PORT (`low:24; top:8`): every other access is whole-word |
| `d14c_flags` (timproc_uso_b5.c:7629) | u32 | - | members never used (masks only) | safe |
| kernel / rmon bitfields (kernel_000_c.c:145, kernel_014.c:16, kernel_022_d.c:92, 119) | - | - | excluded from the port (port/ultra) | n/a |

None of the other bitfield structs is loaded from cartridge data. `include/libultra` and
`include/match_imports` have no bitfields.

**Riskiest, in order:**
1. **Liveness tests always fail.** The `>> 31` reads of player / channel / layer `enabled` read
   bit 7 of byte 3 on x86, so channels and layers are skipped or run when they should not.
2. **Channel change flags.** Volume and pan updates follow unrelated bits.
3. **Layer init.** `\|= 0x80` sets `notePropertiesNeedInit`, not `enabled`.
4. **Stereo from script bytes.**
5. **ADSR state nibble.** Envelopes never start or stop.
6. **Mem block headers** (every heap): `Mem_setBlockType` corrupts block sizes. It is **not
   audio-only**, and it is the first one to fix (M1 boot).

**Limits:**
- Not checked: every USO's code for byte loads of the Mem header type byte, and every
  match_imports copy for further views of the audio flag words.
- The accessor work is M4 (audio trusted), **except the Mem header, which is M1**.

### 18.4 Run 624: byte order part 2

agent-c run 624, on main b8596e397. Five commits on agent-c, gate PASS before each (ROM
byte-identical, 3288/3288); libgame.a and libuso.a build with the port flags, with no new warnings.

| commit | what |
|---|---|
| 12da847f5 | **Mem block header (M1):** `Bf5B5D8` is declared `{low:24; top:8}` under PORT, so `Mem_setBlockType` keeps `hdr & 0xFFFFFF` on x86 |
| d732434c3 | 124 more `stream_read*` / `fs_gdlRead*` copies swap under PORT. `PORT_BE_SWAP16S` is new (`stream_read16_000089FC`), and `fs_gdlRead24_00037CE0` (6 ints) is included |
| fd10f8156 | audio flag bits read in host order: `AUDIO_FLAGBIT(i)` / `AUDIO_WORDBIT(i)` at 23 mask / shift sites; ADSR state nibble; Stereo re-pack at 3 writes |
| 1b2f7f089 | `CMD_B3` read-site fix (0x1C0AC conflict); osViModeTable typed; generator `KNOWN` table |
| 283ba01f9 | charsel / gamegfx images and records typed; shape op 35 CollGrid typed (map5_data) |

**Mem header audit.** No built object, in any module (match_imports and the 8 new USOs
included), has an lb / lbu / sb / lh / lhu / sh at -16..-10. Grepping `:24` finds no other view
of the header. Every other Mem_* access is a whole-word mask (`& 0xFFFFFF`, `>> 24`), which is
order-independent.
- Not covered: a byte load at offset 0 of a block pointer held in a register. None is known.

**Readers.** The template copies now swap in every module:
- bootup: 37 + 4 (o0_F1F0) + 3 (tail4);
- game_uso: 20;
- arcproc, eddproc, h2hproc, mgrproc, titproc, timproc b1 / b3 / b5;
- boarder1-5;
- map4_data_uso_b2.

Kept unswapped:
- `stream_readS32_00005EF8`, EnvSettings_load's message-id (tag) read;
- `fs_gdlReadInt_00035AA4`, Parms_load's tag read;
- `fs_read_00066404`, whose use is unknown.

Every other S32 copy's callers read sizes, counts or fields. The `boot_read*Parm` slots discard
the size word.
- Not swapped: `fs_readRecord_00041F90` (68 bytes, layout open).

**Audio (port.h).** Field i of a flag word is counted in declaration order from the word's first
byte. `AUDIO_FLAGBIT(i)` = `1 << (i & 7)` within byte i / 8; `AUDIO_WORDBIT(i)` = `1 << i` in the
word. These are the host masks; IDO's are `0x80 >> (i & 7)` and `0x80000000 >> i`. Each site is
`#ifdef PORT host #else IDO #endif`:
- `enabled` (`>> 31`): GetChannelIO; GetLayerSamplesLeft x3 (and layer bit3, `<< 3 << 1`);
  SequencePlayerProcessSound;
- ChannelProcessSound: `CH_CHANGE_FREQSCALE` (byte 1), `CH_CHANGED_VOLUME` / `CH_CHANGED_PAN`
  (word bits 9 / 10), notePropertiesNeedInit `& 1` / `& 0xFFFE`;
- SeqLayerDecayRelease `bits0 &= ~8` (field 4);
- clears: DisableSampleStates (note enabled), InitSequencePlayers (layer enabled),
  SequenceChannelDisable (enabled / finished), and match_imports AudioSeq_InitSequencePlayer
  (5 clears; this is the body the port compiles);
- ADSR: `state:4` is the high nibble on the host. NoteInit `(b & ~0xF0) | 0x10`, NoteDisable
  `&= ~0xF0`.

`port_stereo_from_ido()` re-packs the Stereo byte field by field, so the 2-bit `bit2` keeps its
value. It is applied at `2BB7C` (`cmd & 0x7F`), `2AD1C` (script byte) and `273B8` (SET_STEREO
`arg.asUbyte`).

A host test checks the mapping against gcc bitfields.

Bitfield **views** of the same words need no change. Both compilers allocate every view in the
same direction, so a view stays consistent with the audio.h declaration. This covers
BF_000295BC, Fl_2978C, ElemFlags1CF68, GlPooledFlags (the SeqChannelSetLayer import),
Audio_AdsrUpdate's Env and the 2AD1C / 27804 Stereo views.

The post.c copy of SeqChannelSetLayer (`c |= 0x80` ...) is a mask site, but the port compiles the
import body, so it was left alone.

**Open:** `AudioCmdArg.asUbyte` / `asUShort` read from a word written as `asInt`. On LE they
read the low bytes, not the high ones. Check the QueueCmd writers (M4).

**Typing (port-gen-blob-types.py).** A new `KNOWN` table holds C-side layouts, applied last. Shape
op 35 is walked.

| data | layout |
|---|---|
| bootup Data 0x1C0AC | gl_cmd_30AF4, u32. `CMD_B3` (lb +3, the BE low byte) is `(u8)gl_cmd_30AF4` under PORT, in both copies |
| bootup Data 0x2D700 | osViModeTable: 42 x 0x50 records, types 0x00-0x29. Each is u8 type + 3 pad, then 19 u32 |
| charsel Data | 6 x 0x10220 blocks. Each holds texels (0x10010) and a TLUT (0x200), both u8, then the record {0x110, 0x100} u32 + 2 ptr |
| gamegfx Data | 5 images at its exports (0x0, 0x848, 0x1C50, 0x33B8, 0x3E10). Each has an 8-byte {0, 1} header (u32 x 2; reader not located), then texel bytes |
| CollGrid (op 35) | see below |

**Collision grid format** (gdl/coll.h `CollGrid`, BasePolyShape +0xA0, read by CollShape_query):
- `{s32 w, h, x0, z0; f32 cellW, cellH; s16 *lists; s32 *cells}`;
- `cells[z * w + x]` is an index into `lists`, or -1 for an empty cell;
- each list is a -1-terminated run of s16 triangle indices into the shape's tris (CollTri
  `tris[i]` pairs with `shape->tris[i]`).

map5_data:
- shape stream 0x9A4: op 35 grid; op 27 121 verts at 0x30; op 28 200 tris at 0x308; op 29 2
  mats at 0x948;
- grid at 0x11944: 128 x 128 cells from (-500, -500), cell 7.87 (about 1008 units square);
- cells 0x1944-0x11944, lists 0xA30-0x1942;
- the second export 0x9D4 is a non-shape stream (ops 1000 / 1003 / 100 / 109-111: a node or prop
  stream), and is 42 bytes unknown.

So map5_data holds a small mesh, not a full course. The other mapN_data modules are not blobs
yet, and the generator will type their grids the same way once they are.

**Coverage:** unknown 52.2% -> **9.7%**. u8 65.8%, u32 7.5%, zero 5.9%, u16 5.2%. 0 conflicts.
charsel, gamegfx and map5_data are 0% unknown. The largest remaining:
- bootup Data 64 K (34%);
- fire 9 K;
- titproc 5 K;
- n64proc 4.5 K;
- the boarder banks, 2.6-3.9 K each.

**Next:**
1. Find the gamegfx header reader and confirm u32.
2. Find the genproc charsel record reader and name the fields.
3. Type the mapN_data streams when they become blobs.
4. The AudioCmdArg sub-word reads.
5. `fs_readRecord_00041F90` (version.bin) layout.
6. fire Data, and the remaining 34% of bootup Data.

### 18.5 Run 806: the paused port branches on current main

agent-g run 806, branch agent-g on main ed68143d6 (3579 functions; the 8 new modules decompiled).
Gate PASS before every commit (ROM byte-identical, 3579/3579, 7940 named calls 0 mismatches).

| commit | what |
|---|---|
| 1a51d5147, 05899c9ac | port-wip-g 12041903d (cfront virtuals). Conflicts against main's CALL naming; B1B4 / 4FBA4 ctors now keep one named call, with only the vptr store under PORT |
| c6480c7e2 | port-wip-g 1d19c1716 (boot blockers), clean |
| 61032b873, fb93c60fb, 55d0b6e83, f9b99fb93, c9ae1e30a | port-wip-c 12da847f5 / d732434c3 / fd10f8156 / 1b2f7f089 / 283ba01f9, clean. ad6d0a069 dropped |
| fc2b908d6 | port-wip-a tools only: name-data-sites.py (XDATA), uso_call.h XDATA, port-gen-binds / -uso XDATA hooks, include_asm handling, port-gen-decls K&R fix. c531782ec's INCLUDE_ASM exclusion is inert now (0 such functions); a's generated files not taken |
| c850e4b03 | tools: (1) the call scanner blanks `#ifdef PORT` branches. fd10f8156's duplicated `if (...) {` heads had silently cut `check` from 7940 to 7669 named calls (game_libs_post.c 431 -> 160); (2) npc re-execs with `sys.orig_argv` (wrappers lost `--lib` under a python without pyelftools); (3) port-gen-decls takes its C++ units from sourcemap.tsv; `OPTIONAL_TAIL` for gui_fontAdjustAdvance |
| 9bac6243c | src PORT fixes: 40070's cherry-picked Base ctor still called `dbg_printThreads` (the pre-618 placeholder); viewrec ncc forward decl of vr_backToMainMenu; snoweffects 9328 `GdlParmBase_ctor` = Parms_addParm (Makefile objcopy rename the port does not apply; a scan of every `--redefine-sym` against aliases.ld finds no other) |
| 3c2b51d90 | port/gen, sourcemap and undefined.txt regenerated |

**Compile census** (gcc 11.4, `-m32 -malign-double`, port CMake): **480 / 480 units, 0 failures**
(252 C, 228 C++), 3222 kept functions (13.2: 462 units, 2931 functions). libgame.a: 0 missing,
0 defined twice, 0 duplicated globals. libuso.a, libultra.a, porthost build.

**Binds:** aliases 3879 (1072 call, 2807 data); 1893 pairs bound; left 146 (129 ambiguous,
16 unnamed, 1 unresolved). uso_modules.c: 30 modules, 3488 Text targets bound, 1 not in the port.
Blob types: 11.5% unknown; **snoweffects Data is 80% unknown** (24 K), fire 96%.

**undefined.txt: 143 -> 114** (plumbing 17 -> 13, match_imports 5, data aliases 24 -> 18, libc 26,
unreferenced 27, other 4, C++ cross-donor 39 -> 21).

**Link** (agent-e's i386 sysroot, `-DPORT_LINK=ON`): test_ultra PASS, test_fs 23 / 0. tenshoe:
**53 undefined** (main: 81): 18 plumbing tokens (`D_00000000`, `gl_func_00000000`,
`timproc_uso_b5_alias`, `glv_2838`, `gl_func_emit*`, ...), 15 data aliases, 16 C++ cross-donor
ctors / methods, 4 audio hooks (`port_audio_*` x3, `glv_2a44`).

**Not done:** applying `name-data-sites.py plan --write` to the source (the XDATA naming of the 129
ambiguous pairs); the new modules' binds-left entries.

### 18.6 Run 810: the C++ cross-donor ctors / methods (agent-a)

agent-a run 810, commit 28523ebaa on main af4cb2eee. Gate PASS (ROM byte-identical, 3579/3579,
check 7940 named calls 0 mismatches). **tenshoe link: 53 -> 37 undefined, 0 of them C++**;
libgame.a has no undefined `_Z*` symbol left (no `_ZTV*` was ever referenced: the cfront vtables
are explicit stores since run 623).

**Mechanism** (`port/include/port_cfront.h`, `CF_EXT`). A donor calling another class's
out-of-line ctor / method references the g++ mangled name; the matching build renames the cfront
reference to a token (`--redefine-sym __ct__1BFPc=func_00000000_ca0_base`) that the ROM relocation
binds. g++ ignores asm labels on constructors, so under PORT the member gets an always-inline
(`CF_INL`) body that calls the real body:

    CF_EXT(void *, ca0_Node_ctor, Node_ctor, (void *, char *));   /* local name + asm label */
    struct B { ...; char *vptr; CF_INL B(char *name) { ca0_Node_ctor(this, name); } };

The local name keeps the donor's parameter types without clashing with port/gen/decls_cpp.h.
CF_INL matters: donors reuse class names (`B`, `M`, `BB`, `Base`) with different bodies, and an
out-of-line COMDAT copy would merge across units. The inline bodies always pass a live `this`:
for `new T(..)` of an out-of-line-ctor class (cfront: `ctor(0, ..)`, the ctor allocates), T is
given the C ctor's own allocation size under PORT so the donor's operator new (mem_new) allocates
the same block.

| donor | member | real body (ROM reloc) |
|---|---|---|
| bootup 31C0 | MNode / MCamera | Node_ctor / MCamera_ctor |
| bootup 31C0 | `new` CourseCam / SnowChaseActorCam / SnowChaseActorLook / SnowChaseActor | cam_ctor_00000858 / SnowChaseActorCam_ctor / SnowChaseActorLook_ctor / SnowChaseActor_ctor (sizes 0x27C / 0x124 / 0x64 / 0x138) |
| bootup CA0, gl 15FC, 40070, 41820 | B / B / BB / B44 | Node_ctor |
| gl 15FC | M | CoolGadgetParms_ctor |
| gl 4B620 | BB(char *, void *, int) | BasePolyShape_ctor (the 526D0 donor) |
| gl 526D0, 4B0A8 | Base(void *) / Base(char *) | ShapeNode_ctor_000521F8 |
| gl 412E8 | El (the `__vec_new` ctor argument) | GfxDdm_ctor |
| bootup 6204 / E9FC (`__sti__`) | Bu6204Ob / BuE9FCBas | FogParms_setDefault_00043EAC / App_ctor |
| gl 500EC | Mesh::adj | Mesh_facesConcave (the 4FD00 donor) |
| gl 54E78 | M4::ident | math_mtx4Identity |
| gl 525F0 | `new` Foo / Sub::add | Node_ctor (Foo sized 0x2C, class operator new = mem_new) / list_append |
| gl 41820; bootup B1B4, game 3AC0 | operator new[]; global operator new | mem_new (were libstdc++ `_Znaj` / `_Znwj`) |

The last five rows were not link errors yet (`--gc-sections` dropped their callers, or libstdc++
supplied `_Znwj` with malloc) but would have been once reachable. A future donor with a
cross-donor member: find the Makefile rename of the reference, the ROM target (port/gen/aliases.ld,
binds.tsv, or the TextReloc at the jal), and add one CF_EXT line plus the inline body.

### 18.6 Run 811: the audio hooks linked, the 8 new modules typed

agent-c run 811, branch agent-c on main af4cb2eee. Gate PASS before each commit (ROM
byte-identical, 3579/3579). This section is uncommitted.

| commit | what |
|---|---|
| 98ecac319 | port/CMakeLists.txt: `audio` static library (port/audio mixer, abi_decode, audio_swap, port_audio), linked whole-archive into tenshoe and passed to the `undefined` target |
| 83f9891cd | port-gen-blob-types.py: shape uv fix, material-only streams, image headers, cfront vtable slots, short strings, 2 KNOWN layouts; blob_types.tsv regenerated |

**Audio hooks.** The three `port_audio_*` symbols were already written (run 616). They were
undefined only because no CMake target built port/audio. Their behaviour is unchanged (15.6):
- `port_audio_swap_static`: the bootup Data audio tables to host order, once;
- `port_audio_swap_font`: each font to host order at AudioLoad_RelocateFont;
- `port_audio_noise_base`: gWaveSamples[8], the ROM bytes at 0xE0B2CC as host s16 (an LCG fill
  without a ROM).

The real `port_audio_frame` now replaces main.c's weak stub. tenshoe: **53 -> 50 undefined**. The
mixer / swap tests pass at -m32 through run32: 147 and 263 checks, 0 failures.

**`glv_2a44` is not an audio hook.** It is the placeholder callee token of `TrkMenu_draw_00002A44`
(timproc_uso_b3), the byte-twin of `glv_2838` in `TimMenu_draw_00002838`. Both are in
binds-left.tsv as "ambiguous" (7 distinct gui / TrkMenu callees across 28 calls). port-undefined.py's
classifier puts glv_2838 under plumbing only because it is listed in undefined_syms_auto.txt; glv_2a44
is not listed there, so it landed under "other". It belongs with the plumbing (agent-g):
it needs per-call names (`CALL(...)` / XDATA), the same fix as glv_2838. No symbol is defined for it.

**Typing (port-gen-blob-types.py):**
- **Shape op 4 is the uv array** (+0x64, s16 (s, t) per vertex; `BasePolyShape_addPoints` names it).
  18.1 / 18.4 had it as "s8 x 3 normals", typed u8, so every shape's UVs were left big-endian. It is
  now u16 x 2 * nv: 5,236 bytes in balloon, boarder1-5, bootup, charfir, charsel, charsps, checkpoint
  and heli. **Op 25** (palette +0x5C, 3 bytes per vertex: RGB888 or s8 normals) is typed bytes.
- Shape streams that are only a material list (op 29 + op 2, e.g. fire 0x227C) are walked. The
  addresses Text takes with `addiu` are now stream starts too (heli 0xCA10, game Data). Their GDL_MC
  words are u32.
- **tex:hdr:** every image symbol is preceded by a symbol holding `{0, 1}` (166 of them, in every
  module that has textures). It is typed u32 x 2, and the texels after it are typed bytes up to the
  next symbol or pointer target (a zero tail of 16+ bytes is dropped). This covers the textures that
  only code reaches, such as snoweffects `*_buildTexDL`'s built G_SETTIMG. The header's reader is
  still unknown.
- **vtbl:** in cfront vtables (`{s16 delta, s16 index, fn}`, read as s16 by VT_SLOT / CF_Vk), the
  slot's head word is typed u16 x 2. The rule: the head of a relocated Text pointer, index 0, a small
  delta, and part of an 8-byte table (not a jump table). 3055 slots. All of them are 0 on this ROM,
  so the swap changes no bytes; the typing keeps any nonzero delta correct.
- **Strings:** 1-3 chars at a referenced start are now typed (parm tags "he1" / "d00" / "Env",
  "%s", viewrec "fff").
- **KNOWN:** snoweffects `SnowFlicker` sequences (u8 at 0x910 / 0x938 / 0x944; s32 counts at
  0x930 / 0x93C / 0x950) and viewrec `vr_sndTbl_4990` (s32 x 4 at Data 0x318).

**Unknown bytes, before and after**, for the 8 new modules. The "non-zero" columns count the unknown
runs that contain a non-zero byte, which are the only ones a missing swap can break.

| module / section | size | unknown before | after | non-zero unknown before | after |
|---|---:|---:|---:|---:|---:|
| balloon Data | 16816 | 1275 (7.6%) | 15 (0.1%) | 1168 | 0 |
| balloon RoData | 32 | 28 (87.5%) | 0 | 28 | 0 |
| checkpoint Data | 16128 | 416 (2.6%) | 26 (0.2%) | 158 | 0 |
| checkpoint RoData | 16 | 16 (100%) | 0 | 16 | 0 |
| fire Data | 9120 | 8778 (96.2%) | 6 (0.1%) | 8676 | 0 |
| heli Data | 52160 | 1683 (3.2%) | 18 (0.0%) | 1386 | 0 |
| heli RoData | 256 | 88 (34.4%) | 8 (3.1%) | 80 | 0 |
| nameent Data | 400 | 135 (33.8%) | 11 (2.8%) | 0 | 0 |
| snoweffects Data | 29728 | 23892 (80.4%) | 20 (0.1%) | 23144 | 0 |
| trnproc Data | 848 | 277 (32.7%) | 10 (1.2%) | 10 | 0 |
| viewrec Data | 1200 | 409 (34.1%) | 29 (2.4%) | 19 | 0 |

The RoData of nameent, snoweffects, trnproc and viewrec was already at 0%. Across all blobs, unknown
went from 11.5% to **6.0%** (68,960 bytes), with 0 conflicts. The largest remaining are bootup Data
(about 55 K) and n64proc / titproc.

Ownership: the generator is agent-c's. `port/gen/blob_types.tsv` is its output: rerun
`scripts/port-gen-blob-types.py` after a port/gen regeneration, and do not hand-merge the tsv.

**Next:**
1. Name the `glv_2838` / `glv_2a44` call sites (agent-g, binds).
2. The image-header reader.
3. bootup Data's remaining 55 K.
4. Run a sequence headlessly once tenshoe links (15.6, "Not done").
### 18.7 Run 809: XDATA / XCALL naming of the ambiguous binds (agent-g)

agent-g run 809, branch agent-g on main af4cb2eee (before agent-a 810 / agent-c 811 landed; not rebased).
Gate PASS before each src commit (ROM byte-identical, 3579/3579, check 8225 named calls 0 mismatches,
XDATA 328 sites 0 mismatches).

| commit | what |
|---|---|
| 5c31a6160 | tools: `name-placeholder-calls.py plan --tok T` (another zero-pinned token: `bu4948_ff`, `glv_2838`, `timproc_uso_b5_alias` ...); cc-select applies a `port-bind` inside the `port-alias` target label (a C++ donor's bound function compiles as `_ZN3Obj3runEv`: every such bind was silently dropped, e.g. RcpMgr_service's 20 `D_00000000`); C units `-fno-inline` (a bound static function inlined into its caller kept the placeholder) |
| 3937de051 | src (tool output): 328 XDATA sites (`name-data-sites.py plan --write`: D_00000000 298, D_arc251C_f / D_1E08_d / import_00000000 14, per-addend functions 16) and 267 XCALL sites |
| 39b71d163 | port/gen + undefined.txt regenerated |
| 2463f21d0 | tools: `Rom.jal_target` maps `sym+pad` (a jal past a libultra `.s` copy's leading nops) to `sym`, so plan / check handle `gl_osSetIntMask+0x8` |
| 51d5966ca | src (tool output): 18 such sites (AudioHeap_Init, Audio_WritebackDCache, dma_writebackCache, sys_writebackDCacheAll, fs_piRead/WriteWord) |
| d6de37406 | port/gen + undefined.txt regenerated |

**Measured.** binds-left 146 -> 80 (ambiguous 129 -> 62, unnamed 16, unresolved 2). undefined.txt
114 -> 104. tenshoe link 53 -> 42 undefined on this branch (C++ 16 and audio 3 are fixed on main
by runs 810 / 811, so after a merge this branch should be at about 23, all plumbing / data).
Gone: `timproc_uso_b5_alias`, `glv_2838`, `gl2FB74_snd`, `bu_cfa0_v`, `bu4948_ff`, `h2h_void_1204`,
`gl_proto_1c68`, `gl_25C54_AllocSampleCache`, `gl_func_00000000_21498v`, `import_00000000`,
`D_1E08_d`, `D_arc251C_f`. `D_00000000` refs 168 -> 41.

**Per-addend data binds and gcc addends (found, not fixed).** A `port-bind: F TOK+N` matches only
when gcc's symbol addend equals the ROM site's. gcc folds field / element offsets into the
addend (`gDmaSlots + 1` .. `+10` gives `D_00000000+680`; a struct copy from `&D+0x4A0` reads
`+0x4A4`..), while IDO keeps them in the instruction. Where the site is spelled in the `.c` the
fix is XDATA (done for 16 sites). A "nearest ROM addend at or below" rule in cc-select was
tried and **rejected**: it binds RaceProcess_drawGui's `new_var->nextFlowMode` (`D+52`, the
GameFlow in Bss+0xF8) to the Data table at +0xCF64, and SnowBoarder_ctor's `+0x34/+0x4C/+0x58`
fields of the ambiguous +0 object to the +4 object. Sites hidden in header macros
(`gDmaSlots`, `GL_DATA`) need a PORT spelling of the macro or of the site.

**Left (this branch):**
- `D_00000000` (41 refs, ~14 live functions): verify bytes differ (o0 / donor splice:
  SnowBoarder_ctor, SnowBoarder_createBoardShape, GameFlow_restart, settings_setFlag4, app_run,
  heap_new, RiderAnim_stateFinish); header-macro sites (dma_allocSlot / startRead / startWrite,
  Sprite_ctor, Shadow_ctor, PolyShape_init, item_registerTemplates, CollShape_height); one source
  site reaching two objects (RaceProcess_drawGui `new_var`, h2h_createPauseMenu); mgr_openSession
  (no ROM target found).
- `snd_HandleSeqEvent_30AF4` (match_imports donor; verify differs): `gl_func_emit` 23,
  `gl_func_emit_30AF4v` 8, `gl_state_30AF4` 12.
- `glv_2a44` (TrkMenu_draw_00002A44, twin of `glv_2838`): not pinned in undefined_syms_auto.txt,
  so `--tok` (which requires the 0 pin) skips it. Next: let `--tok` accept a token that is
  merely undefined in the object.
- `gl_32e18_blank` (MCamera_ctor), `gl_25504_AllocSampleCache`, `gl_func_00000000` 10
  (PolyShape_display 48AEC: "no jal in the build", nameent / snoweffects / heli macro-hidden).
- Data aliases (15): `D_b1_21D4_d1` / `D_b3_23E4_d1` (timproc b1 / b3: the verify compile
  fails, "Non-function name referenced in function call"), `D_76F0_fade*` (mp72 donor),
  `D_445AC_ga/gb` (GfxLib_init donor), `D_2DA4_obj` (game_setupMode), `D_349E0_b`,
  `D_00000000_a/_i/_j`, `D_4D16C_a`-type unnamed ucode, `gl_26214_aspMainTextStart`,
  `game_uso_D_807FF458`, `D_b3_23E4_17D7`.


### 18.7 Run 812: cfront pointers-to-member, the aliasing-hazard audit (agent-a)

agent-a run 812, branch agent-a on main dd5d48ed5: ec3964bc5 (PMF), cc507aef0 (audit tool + boot
fixes). Gate PASS before the commits (ROM byte-identical, 3579/3579). tenshoe link unchanged
(37 undefined). Items 4 and 5 of the run-623 "Still blocks" list.

**PMFs (item 4).** The ROM's PMF records are 8 bytes, `{s16 delta, s16 index, fn | vptrOff}`. The
dispatch (edg's, in RiderAnim_update_0000D204; the same as the C MemberCallback_invoke /
_00007BF4) works like this:
- `index < 0`: call `fn(this + delta)`;
- otherwise: the vptr is at `(this + delta) + vptrOff`, or `+ 0x28` when vptrOff and delta are
  both 0. The slot is the `{s16 delta, fn}` entry at `vptr + 8 * index` (1-based), called with
  `this + delta + slot.delta`.

Equality is a 2-word compare. A ROM scan (Data words with a Text reloc at +4 and a head index < 0)
finds 59 PMFs, all non-virtual `{0, -1, fn}`:
- game Data 0x840 (Sun) and 0xDB0..0xF58 (RiderAnim states; the null PMF `{0,0,0}` is at 0xDC8);
- bootup Data 0x7520 (Tv1), 0x1EA38 / 0x1EA40 (Node_Save / Load), 0x1EEC0 / 0x1EEC8 (ItemMgr),
  0x20638 (BaseMat_sendImage).

`port_cfront.h` now has `PortCfPmf`, with that `==` / `!=` and an `operator->*` that decodes
the record. The 8 game_uso donors that use PMFs take `typedef PortCfPmf PM;` and a
non-polymorphic `A` (explicit cfront vptr) under PORT: D204, 10694, 10840, 10A0C, E35C, F060,
F13C and F6D4. Their call and compare sites stay as written. No other donor uses `->*`, `.*` or a
PMF type.

**Open, blob typing (agent-c's generator):** port-gen-blob-types.py types each PMF head as **u32**
(a "field" from the word copies), so on the host it reads delta = -1, index = 0, which is a
virtual call through garbage. This breaks the new decoder and the existing C
MemberCallback_invoke (Sun's visCallback, Tv1) alike. Checked in uso_blobs.swapped: game 0xDB0 is
`ff ff 00 00`. Only game 0xF38 ("unknown", unswapped) happens to be right. The fix is in the
generator: an 8-byte Data record with a Text reloc at +4 and a head index of -1 (the vtbl rule,
extended past index 0) gets its head typed **u16 x 2**, overriding the u32 field. That covers the
59 heads listed above.

**Aliasing hazard (item 5).** `-fno-strict-aliasing` is already in PORT_ARCH_FLAGS, and it does not
cover this hazard. gcc's decl-based disambiguation assumes that two distinct extern objects never
overlap, and no flag turns that off. I tested gcc 11 `-m32 -O2` with each of:
- `-fno-strict-aliasing`;
- `weak` decls;
- `-fno-tree-pta`;
- `-fno-tree-fre -fno-tree-pre -fno-gcse`.

In every case gcc still reuses a load of `tokB+0x80` across a store to `tokA+0x80`. Even two
decls with the same asm label but different C names stay distinct. Only one C object, at known
offsets, makes gcc see the overlap.

`scripts/port-alias-audit.py BUILD [--boot] [--all] [--emit FUNC..] [--reuse]` works like this:
1. It recompiles each cc-select unit to `.s` without the rename (compdb from ninja; about 3 min
   at -j8).
2. It resolves each data reference through the unit's port-bind lines, aliases.ld and direct
   `port_*` spellings.
3. It lists the pairs in one function that overlap at run time but not to gcc, with a write
   (HAZARD).

`--emit` prints the fix as a scoped `#ifdef PORT` `#define T (*(__typeof__(T) *)(port_x + 0xK))`
before the function and an `#undef` after it. A per-addend bind token that lands on the same
bytes becomes the spelling instead. Boot set: the App_main call closure, the title-flow roots,
and n64proc / titproc.

- **Fixed (boot, 10):** App_main, app_initSystem, BasePolyShape_initGeomGlobals_00052674,
  fs_gdlSeekFile, gfx_end, hostio_start, snd_HandleSeqEvent_30AF4, snd_UpdateChannel10Emitter,
  snd_UpdateTimers, snd_dispatchEvent. Boot HAZARD rows: 73 -> 0.
- **Listed, not fixed (32):**
  - bootup: BalloonTmpl_create, TreeTmpl_create, Tv1Tmpl_display, game_initDdm_00002C94,
    SnowBoarder_ctor (12), item_registerTemplates (14), SnowBoarder_reset, game_setupMode,
    game_createMap (35);
  - checkpoint: CheckpointBox/CylTmpl_create;
  - game_libs: snd_TickChannel8Fade (11), hostio_dispatch (5), `_GLOBAL__sub_I_gGfxLib_412E8_a`,
    AudioThread_UpdateImpl, AudioThread_ProcessCmds (6), AudioLoad_DiscardFont,
    snd_SetLevelRampTarget;
  - match_imports: BasePolyShape_genPointNormals, BoardList_createItem (15),
    CharacterList_createItem (16), snd_SetPlayer1Channel15IO_2D910 (136), snd_SoundObjUpdate,
    snd_SoundObjUpdateChannel;
  - other modules: heli HeliItemType_create, mgrproc MGRRaceProcess_updateSub2 / onEndTimerDone,
    timproc_b5 gen_createScene_00008DB4, GenSelectChar_ctor, SelItemsMgr_ctor (30),
    CourseList_createItem (25), LevelList_createItem (25).

  For each one, `--emit FUNC` gives the block. None of them needs a per-addend bind. In
  game_setupMode and AudioLoad_DiscardFont, `D_00000000` is a plain bind there, so it is
  `#define`d for that function only.
- **Blind spots:**
  - accesses through a register pointer (only the `&T+N` / `lea` form is visible; `--all` lists
    address-taken pairs within 0x100 bytes for review);
  - an asm-label decl next to a plain decl of the same name (XDATA; src/ has none today).

### 18.7 Run 813: bootup Data typed (blob byte order part 3)

agent-c run 813, branch agent-c on main 26d9acb8b. Gate PASS before the commit (ROM
byte-identical, 3579/3579, clean build OK). This section is uncommitted.

| commit | what |
|---|---|
| 95e428846 | port-gen-blob-types.py: op 32 remap count fix, indexed direct accesses, static display lists, node command streams + SkinBone tables, 9 bootup KNOWN layouts; blob_types.tsv regenerated |

**Typing bug fixed: shape op 32.** The remap array (+0x70, 3 u16 per entry) has its own count:
the command's arg 0 (+0x74, BasePolyShape_parse case 32). The generator used nVerts. boarder3
0x4094 has 231 entries for 155 vertices, so the tails of the remap arrays in boarder1-5 were left
big-endian (0x22E-0x390 bytes each).

**New rules:**
- **Indexed direct access.** A LO16 load / store whose base register gets an `addu` between the
  HI16 and the LO16 (`lui; addu; lw %lo(sym)(r)`) is an indexed element. It is extended forward
  like "index". This covers snd_SoundObjUpdate's f32 curves (0x1C330 / 0x1C3B0 / 0x1C430) and the
  genproc / titproc / mgrproc s32 tables (205 sites).
- **Static display lists.** An address the code takes that parses as immediate GBI1 commands
  (opcode >= 0xAF) up to G_ENDDL is typed as a display list. Example: gfx_initRDPState's RDP init
  lists at 0x224D0 / 0x224F0. Before, only DLs holding a relocated address word were found.
- **Node command streams.** These are the streams of Node / MNode / QNode_doCommand:
  `{argc << 16 | op, args}`, with no end op.
  - The rider node list (bootup Data 0xA924..0xBBF0, the one SnowBoarder_loadBoardModel uses)
    parses exactly to its end, so it is typed u32. Relocated args stay ptr.
  - Op 114 targets are s16[10] transforms (pos, quat / 32767, scale; QNode case 0x72).
  - Op 1003 with fn = skin_cmdSkinMgr (Text 0x7D280) gives its SkinBone table: `{s16 count,
    s16 pad, SkinWeight *}`, with weights `{s16 vert, s16 weight}` (gdl/skin.h). These are at
    0xC12C and 0xBC30..0xBD34.
- KNOWN layouts no longer retype relocated words (ptr / audio).

**KNOWN layouts (bootup Data)**, with evidence in the script:
- the RSP ucode DMEM images 0x11990..0x17D50 (RcpTask_setUcode*'s ucode_data) and aspMain's data
  image 0x1D340 (0x2E0): bytes. Only the RSP reads them; the port's mixer has its own copy of the
  resample LUT.
- gfx_drawFbSplash's 128x128 u16 splash at 0x22A30. It was 32 K of "unknown" with false strings.
- math_atanLookup's 1025 u16 at 0x2AA60, and math_acosf's 2049 u16 at 0x2C650.
- __osViInit's 3 OSViMode records at 0x2E530.
- the course descriptors 0x67F0..0x6E30 (s32 COURSE_OP_* streams, game_createMap).
- the record / options defaults 0xD268..0xD430 (s32), from Backup_resetCourseData /
  Backup_resetArcadeData and the per-course times / scores.
- the 34 op-114 transforms that tile 0xA0F8..0xA3A0 (the stream reaches 20 of them).

**The {0, 1} image header has no reader on the ROM.** Of the 159 relocated references to the 149
tex:hdr images (142 R_MIPS_32, 17 HI/LO addiu, in every module, imports followed), all point at
header + 8, the texels. None point at the header word or at +4. The header is never read
through a reference. Typing it as two u32 is a no-op for any s32 reader and harmless otherwise.

**Unknown bytes, before and after.** "non-zero run" counts the bytes of unknown runs that hold a
non-zero byte; "nz bytes" counts the non-zero bytes themselves. game_libs has no Data of its own:
bootup.uso's Data / RoData serve both game_libs and bootup_uso, so its row is the bootup row.
"game" is game.uso.

| module / section | size | unknown before | after | non-zero run before | after | nz bytes before | after |
|---|---:|---:|---:|---:|---:|---:|---:|
| bootup (+ game_libs) Data | 190064 | 54625 (28.7%) | 4083 (2.1%) | 52943 | 2413 | 34442 | 984 |
| bootup (+ game_libs) RoData | 9632 | 432 | 405 | 58 | 31 | 34 | 23 |
| game Data | 4880 | 231 | 191 | 176 | 136 | 84 | 65 |
| game RoData | 640 | 86 | 86 | 78 | 78 | 61 | 61 |
| boarder1 / 2 / 4 / 5 Data | | 2630 / 2200 / 2192 / 2121 | 6 / 2 / 14 / 17 | | 0 | | 0 |
| boarder3 Data | 32848 | 3390 | 1400 | | 1388 | | 993 |

All blobs together: 68,960 (6.0%) -> **7,067 (0.6%)**, 0 conflicts. The fresh port build
generates the blobs from the new map. tenshoe's link still stops on the known undefined symbols
(18.6).

**Left in bootup Data (984 non-zero bytes)**, all small:
- the snd float tables 0x1C24D / 0x1C76C (prefix bytes before the indexed runs);
- game_initDdm 0x71A4;
- SnowBoarder 0x8170 / 0x84E4..0x8660 (mixed f32 / s32 records);
- the audio 0x1BC5A;
- 0x20D2C, 0x21AD0, 0x20598, 0x203B0, 0x1F984;
- 0x1A2E0 (4 words, no reader).

None of these is on the boot path before the title. boarder3 0x3B28 (231 x s16[3], an unreferenced
sibling of its remap array) is the largest run left in any module.

**Next:**
1. The remaining SnowBoarder / snd records, by their readers.
2. Scan the other modules for node command streams (only the bootup rider list is wired).
3. bootup RoData's 31 bytes, and game.uso Data / RoData.

### 18.7 Run 816: XDATA-aware alias audit, the remaining hazards fixed (agent-a)

agent-a run 816, branch agent-a on main 49db5f0c6: 2ebc64be6 (tool), 4315b0f99 (src). Gate PASS
(ROM byte-identical, 3579/3579, check 8225 calls / 328 XDATA sites 0 mismatches). tenshoe link:
22 undefined, all on run 809's "Left" list.

**XDATA in the audit.** Under PORT an XDATA site is its own block-scope decl `__port_xdata_N`
with the blob's asm label: it prints as `port_x+K`, so run 812's tool took it for the plain blob
decl, but to gcc it is distinct from that decl and from every other XDATA site. The audit now
compiles with `-fverbose-asm` and attributes a reference whose operand comment names
`&__port_xdata_N` to the object `BLOB@xN`. (An address-only `$port_x+K` operand has no comment,
so it stays the plain blob; that is only an escape, see below.) New hazards it found:
GameFlow_startMode (boot: a read and a write of bootup Data +0xC478 through two sites),
TitleDemoProcess_handleInput (boot: two writes of GameFlow +0x34), nodelist_dispatch (two RMWs
each of bootup Bss +0x3EEC4 / +0x3EECC). `--emit` fixes such a function by redefining `XDATA`
around it as `(*(__typeof__(tok) *)((char *)&sym + (off)))` (the plain blob decl, declared for
every blob the function names) and restoring the uso_call.h form after it.

**Fixed.** HAZARD rows 365 -> 13; functions 35 -> 1. All 33 `--emit` functions (run 812's 32
less SnowBoarder_ctor, plus the 3 above) and, by hand:
- gen_createScene_00008DB4: its block-scope `extern GfxLib import_...` decls move to file scope
  under PORT (`#ifndef PORT` around the originals), so the #defines can respell them;
- MGRRaceProcess_updateSub2: the block went in by hand (the definition follows a
  backslash-continued macro);
- `_GLOBAL__sub_I_gGfxLib_412E8_a`: gSysLib_412E8_i and _l are one object
  (port_bootup_bss+0x3C740), but both definitions are port-dropdata and so cannot be respelled.
  L's PORT ctor starts with `__asm__ __volatile__("" ::: "memory")`, so I's vptr store stays
  first. The static audit cannot see the barrier and still lists the pair.

**Deferred (agent-g run 814 owns it):** SnowBoarder_ctor, 12 HAZARD pairs (gPolyGeomMode +4 /
gPolyFlags / gNodeGlobals / gGfxLib `_90cc_*` tokens). After agent-g lands,
`port-alias-audit.py BUILD --emit SnowBoarder_ctor` gives the block. Rerun the audit after their
XDATA spellings too: new XDATA sites can pair with each other.

**Address-taken review (`--all`).** An address that is only pushed or stored to memory is now
class `escape`: gcc reaches it again only through a loaded pointer, which it must assume may
point anywhere. That leaves `addr` (taken into a register) for 6 functions. On the boot path
there are 0 `addr` rows: all 5 boot functions (SnowBoard_ctor, app_initSystem, App_main,
GfxLib_reset, TitleDemoProcess_handleInput) only pass the address to a call or store it. I
checked the 6 non-boot functions by hand, and none is a hazard:
- RiderCam_update_00004948, game_initDdm, item_registerTemplates: reads only through the pointer;
- Shadow_display_0004B2F4: the matrix loop writes 0x3C208..0x3C248, and its reads are outside
  that range;
- the 412E8 static init: a vec_new loop end bound, never dereferenced;
- SnowBoarder_ctor: deferred.

**Applying blocks.** The insertion helper I used is not checked in. It puts the open block before
the definition line and the close block after the matching brace. Watch out for block-scope
extern decls of a respelled token, and for a definition that follows a `\` macro.

### 18.7 Run 815: cfront PMF heads typed u16 x 2; bootup Data part 4 (agent-c)

agent-c run 815, branch agent-c on main 49db5f0c6: d09254f33 (PMF heads), 3c09f4dec (bootup
Data). Both are `scripts/port-gen-blob-types.py` + `port/gen/blob_types.tsv` only. Gate PASS
before each commit (ROM byte-identical, 3579/3579, verify-blocks 6/6, clean build OK).

**The PMF bug (from run 812).** Each cfront PMF head `{s16 delta, s16 vslot}` was typed as one
u32, because the code copies the records with `lw` (the "field" source). On the host the
swapped head read delta -1 / index 0: a virtual call through garbage in PortCfPmf and in the C
`MemberCallback_invoke` (Sun, Tv1). Swapped game Data 0xDB0 was `ff ff 00 00`; it is now
`00 00 ff ff`.

The new `pmf` rule sits next to the vtable-slot rule:
- A record is a `{small delta, -1}` head before a relocated pointer to Text, where the code
  accesses the head (the copy). The decode readers themselves go through the heap copies, so the
  copy is the static reader. The head is forced to u16 x 2 over the copy's u32. The fn word stays
  `ptr`.
- The null record `{0, 0, 0}` is a zero record the code takes the address of, next to a PMF head.
  Vtable `{0, 0}` headers (followed by a `vtbl` slot) are excluded; four of them would match
  otherwise: 0x848, bootup 0x7528 / 0x1EA48 / 0x20640.

Result: **60 non-virtual records + 1 null**.
- game Data: 0x840, 0xDB0..0xF58 (null at 0xDC8).
- bootup Data: 0x7520, 0x1EA38 / 40, 0x1EEC0 / C8, 0x20638.

The game list equals the 55 `kPmf*` constants in include/game/game_uso_data.h exactly. Run 812's
"59" is one short: 0xF58 (`kPmf_RiderAnim_stateStand`) is a real record. Only PMF lines change
in the tsv.

**bootup Data.** A new array-argument rule handles a reader that takes `{array, count}` in
argument registers: the caller's addiu and its `addiu reg, zero, n` type the array.
`snd_FindNearestF32_2F1B8(f32 key, f32 *arr, s32 n)` gives snd_SoundObjUpdate's curves 0x1C250
(16) and 0x1C290 (32), and snd_SoundObjSetAngle's 0x1C744 (8) and 0x1C76C (16), all f32. They
were `unknown`, so they were not swapped.

Known layouts, each cited to its reader in the script:
- 0x7198: game_initDdm {id, packed};
- 0x7280: item_createSnow f32 x 4;
- 0x7290: the camera viewport records, 5 x 7 s32;
- 0x7B4C: item_createFog f32 parms;
- 0x7B6C: item_registerTemplates records;
- 0x8170: the rumble bytes;
- 0x8478: SnowBoarder_ctor's tint list {key, slot, f32 rgba[4]} x 22.

bootup Data non-zero unknown bytes: **984 -> 478**. All blobs: 7,127 -> 6,005 unknown bytes.

**Left** (non-zero unknown):
- boarder3 993 (0x3B28, the unreferenced s16[3] run);
- bootup Data 478, mostly 1-3 byte gaps. Runs of 8+ bytes: 0x1A2E0, 0x1BC5A (audio), 0x1C320
  (u8 order table?), 0x1E9E0 (BallRotator parms), 0x1F984 (gfx screen), 0x203B0 / 0x203CA,
  0x20598, 0x20D2C, 0x21AD0 (math), and the fault_printThread {mask, off} records from 0x211EC;
- game Data 63 (0x106F..0x10E8, next to the rumble patterns);
- game RoData 61;
- genproc 33 + 20;
- bootup RoData 23;
- map5_data 22.

**Next:**
1. Node command streams in other modules. Not started this run: only the bootup rider list is
   wired.
2. fault_printThread's 8-byte records and the remaining bootup runs above.
3. game Data / RoData.

### 18.8 Run 814: the last D_00000000 sites, sentinel calls, absolute boot globals (agent-g)

agent-g run 814, branch agent-g rebuilt on main 52fd5f980 (after agent-a 816 / agent-c 815; the commits cherry-picked, port/gen and blob_types regenerated). Gate PASS before the commits
(ROM byte-identical, 3579/3579, verify-blocks 6/6, clean build OK; XDATA check 387 sites 0
mismatches, CALL check 8225 0 mismatches).

| commit | what |
|---|---|
| c58901fb7 | tools: `RomTargets.absolute()` (a USO import of bootup's ABSOLUTE Sym, kind 3, value 0x8000030x, is the libultra boot global: osCicId / osTvType / osResetType ...; name-data-sites checks `XDATA(tok, osCicId, 0)`); `check` finds a C++ member (`Mgr::run`) under its shipped name via the tu `port-alias`; cc-select binds inside the `.set` target of a bound label (a ctor's C1 is `.set` to C2, so Shadow_ctor / Sprite_ctor's binds were silently dropped) and points a dropped object's DWARF location at the dead copy; port-gen-decls treats `#ifdef PORT /* .. */` as a PORT branch (a regen made B1B4's `CF_EXT(.., mem_new, ..)` a "declaration" and broke the build) |
| a87daaa81 | src: `GL_DATA/GL_RODATA/GL_BSS` and `gDmaSlots` PORT spellings (the section / the Bss+0x3A240 table: the per-addend folding is fixed at the source, `gDmaSlots + 1` no longer becomes `D+0x44`); hand XDATA (comments cite the reloc offsets) in GameFlow_restart, SnowBoarder_ctor / createBoardShape, settings_setFlag4, item_registerTemplates, RiderAnim_stateFinish, heap_new, app_run, Mgr::run (PolyShape_init), mgr_openSession (osCicId); two-object sites split under PORT (RaceProcess_drawGui new_var; h2h_createPauseMenu `base` = ten objects, `H2H_AT(XDATA(..))`); CollShape_height K() = gGfxLib fields; new `SCALL(tok, f)` for calls to a module's Text+0 sentinel (edd / boarder5 / gui readers), the three Text+0 int readers call fs_gdlReadFile(gSysLib) under PORT |
| 21ff3221a | src: SnowBoarder_ctor one-object PORT spellings (`port-alias-audit.py --emit`, 12 hazard pairs); audit rerun: SnowBoarder_ctor clean, 1 hazard left ROM-wide (`_GLOBAL__sub_I_gGfxLib_412E8_a`, not touched) |
| 0e4502707 | port/gen, blob_types.tsv (generator rerun, unchanged from main), undefined.txt regenerated |

**Rule learned:** when a function's XDATA names a target, port-gen-binds removes that target from
the function's bind set (`xdata_named`), so **every** site of that target in the function must be
XDATA'd. Naming only the folded-addend site (`GFXLIB(DB)->rcp`) left `gfx_start(DB)` to be bound to
the *other* target (Data+0). Check the regenerated tu header after a partial XDATA.

**Measured.** tenshoe link 22 -> 19 undefined (D_00000000 38 refs -> 0, gl_func_00000000 10 -> 0,
D_b3_23E4_17D7 -> osCicId by the regular binds). binds-left 80 -> 72.

**Left (19), handed off by the coordinator (agent-a: the snd donor tokens, gl_32e18_blank, gl_25504, glv_2a44 / --tok; agent-c: the 12 data aliases):** snd_HandleSeqEvent_30AF4 donor (`gl_func_emit` 23 / `_30AF4v` 8 / `gl_state_30AF4`
12: hand XCALL / XDATA in ROM order); `glv_2a44` (`--tok` on merely-undefined tokens);
`gl_32e18_blank` (MCamera_ctor), `gl_25504_AllocSampleCache`; data aliases `D_b1_21D4_d1`,
`D_b3_23E4_d1`, `D_76F0_fadeB/C`, `D_349E0_b`, `D_2DA4_obj`, `D_00000000_i/_j/_a`,
`gl_26214_aspMainTextStart`, `D_445AC_ga/gb`, `game_uso_D_807FF458`. Most are per-site aliases in
ambiguous functions: the same hand-XDATA recipe (relocs-per-site dump, then XDATA each site).
Boot run not attempted (link not at 0).


### 18.9 Run 817: the snd 30AF4 donor, glv_2a44, the two blank calls (agent-a)

agent-a run 817, branch agent-a on main f208db9c0 (agent-g's run 814 as landed). Gate PASS
(ROM byte-identical, 3579/3579, verify-blocks 6/6, clean build OK); CALL check 8314 named calls
0 mismatches (was 8225), XDATA check 398 sites 0 mismatches (was 387).

| commit | what |
|---|---|
| b79f5d075 | tools: `name-placeholder-calls.py plan --tok T` accepts a token that is merely undefined in the object (a relocatable USO object such as timproc_uso_b3 never pins its blank-jal tokens in undefined_syms_auto.txt) |
| 357a0285a | src: snd_HandleSeqEvent_30AF4 donor 43 XCALL + 11 XDATA; TrkMenu_draw_00002A44 28 `glv_2a44` XCALLs (plan --tok); MCamera_ctor 14 `gl_32e18_blank`, AudioLoad_RelocateFontAndPreloadSamples 4 `gl_25504_AllocSampleCache` |
| 0618ceb94 | port/gen + undefined.txt regenerated |

**Donor recipe (snd_HandleSeqEvent_30AF4).** The tools do not plan a match_imports donor, but
the call side is easy to prove by hand: a verify copy of the donor with each call token spelled
uniquely (`gl_func_emit__sN`, declared like the original) compiled with the donor's own Makefile
recipe gives IDENTICAL .text and reloc offsets (a jal's symbol does not affect codegen), so each
source call maps to one jal and its bootup TextReloc target. Renaming the DATA token per site does
NOT work (IDO CSEs `&gl_state_30AF4` across sites; 493 words differ): read the data token's
HI16/LO16 pairs off the real object instead and pair them with the source by hand (6 pairs for 11
source refs: lines that share a CSE'd base share its ROM object). `name-placeholder-calls.py check`
does cover the donor's XCALLs once spelled (8225 -> 8314 includes its 43).

**Macro-hidden tokens.** `#define gl_func_0001CA10 gl_32e18_blank` / `#define
AudioHeap_AllocSampleCache gl_25504_AllocSampleCache` hide the sites from `plan` ("no jal");
spelling the token directly at the sites (no byte change) and rerunning `plan --tok .. --funcs
port/gen/binds-left.tsv --write` names them.

**Measured.** tenshoe link 19 -> 13 undefined; binds-left 72 -> 66. Left (13, all data aliases,
agent-c's area): `D_b3_23E4_d1` 5, `D_b1_21D4_d1` 5, `D_76F0_fadeB/C` 4+4, `D_349E0_b` 3,
`D_2DA4_obj` 3, `D_00000000_j` 3, `gl_26214_aspMainTextStart` 2, `D_445AC_ga/gb` 2+2,
`D_00000000_i/_a` 2+2, `game_uso_D_807FF458` 1.

### 18.10 Run 818: the 13 data aliases, port_bootup_text for the RSP ucode (agent-c)

agent-c run 818, branch agent-c on main f208db9c0 (agent-g's run 814 as landed; NOT on top of
agent-a's run 817). Gate PASS (ROM byte-identical, verify-blocks 6/6, 3579/3579, clean build OK);
XDATA check 435 sites 0 mismatches (was 387), CALL check 8225 0 mismatches.

| commit | what |
|---|---|
| 77d95c9c1 | tools + port: `port_bootup_text` (port/uso/uso.c, bootup Text as an address space); port-gen-binds `text_data()` and name-data-sites `site_targets` resolve a data address in bootup Text outside every function to `port_bootup_text+0xK` (was "unnamed"); name-data-sites `check` maps a token through the object's Makefile `objcopy --redefine-sym` |
| f6c89a2b0 | src: hand XDATA at every site of the 13 aliases (each function's sites from the ROM relocs, below) |
| 8034fbf16 | port/gen + undefined.txt regenerated (blob_types.tsv unchanged) |

**Per-site targets (ROM TextRelocs, function order).**
- `D_b1_21D4_d1` / `D_b3_23E4_d1` (TimMenu_ctor / TrkMenu_ctor) are not data: the 4th argument of
  the seven `gui_addRowSub` calls is each row's callback (rowRetry, rowGhost, rowToggle,
  rowChangeCourse, rowChangeBoard, rowChangeCharacter, rowQuit), `XDATA(tok, f, 0x0)`. The plan's
  verify compile fails on these ("Non-function name referenced in function call"); hand XDATA does
  not need it.
- `D_76F0_fadeB/C` (RaceProcess_handleInput): the two names swap objects between the two halves
  (fadeB = Data +0xC75C then +0xC760, fadeC the reverse). Per-site XDATA objects on the same bytes
  are an alias hazard (two `__port_xdata_N` decls never alias); the function gets the
  `port-alias-audit.py --emit` redefinition of XDATA onto the one `port_bootup_data` decl. **Rule:
  after hand XDATA that writes, rerun the alias audit** (only the existing 412E8 static-init hazard
  remains).
- `D_349E0_b` (hostio_start): Bss +0x3C768, +0x3C79C (the sendNodeTree value), +0x3C768.
- `D_2DA4_obj` (game_setupMode): the store is game.uso Bss +0x8, the releaseFrames argument bootup
  Bss +0xD8, the case-1 read bootup Data +0x7768 (three objects under one name).
- `D_00000000_i/_j` (PolyShape_display donor, objcopy-renamed `D_48AEC_mt` / `gGfxLib_48AEC_src`):
  Bss +0 (+0x3C8A0 in the source) and Bss +0x3C168 (+0xA0). gcc folded the source addend into the
  token, so the per-addend binds missed. The `_i` site is inside `#define mt`, which `check`
  does not see (preprocessor lines are masked); verified by hand (LO16 at +0x190, lui 4 / addiu
  0xC8A0 on Bss +0).
- `D_445AC_ga/gb` (GfxLib_init): Data +0x1F974 / +0x1F978, then +0x1FC8C / +0x1FC90.
- `game_uso_D_807FF458` is **module-relative, not a KSEG0 address**: RiderAnim_checkRow reads
  game.uso RoData +0 (+0x208, the f64 0.1) and Data +0 (+0xE68, the PMF) through it.
- `D_00000000_a` (RcpTask_setUcode*, 5 functions), `D_4D16C_a` / `D_4D188_a` / `D_4D1F4_a` and
  `gl_26214_aspMainTextStart`: RSP ucode text in bootup Text (+0x23300, +0x26700, +0x27B00,
  +0x28F10 F3DEX_NoN, +0x2AE00 F3DEX, +0x2D4A0 F3DLP_Rej, +0x2E870 F3DLX_Rej, +0x2FC40 Sgi20HFifo,
  +0x46470 aspMain = ROM 0xE16EDC, 15.2). Only `OSTask_t.ucode / ucode_boot` hold them; Fast3D and
  port/audio never read the bytes, so `port_bootup_text` is a zero image of the section (0x89910
  bytes, bss) that gives each its ROM offset. The bind tool now also binds these globally
  (aliases.ld) where every site agrees.

**Measured.** tenshoe link 19 -> 6 on this branch (left = exactly agent-a run 817's six:
`gl_func_emit` / `gl_func_emit_30AF4v` / `gl_state_30AF4`, `glv_2a44`, `gl_32e18_blank`,
`gl_25504_AllocSampleCache`), so after both land the link should be at 0 (regen to confirm:
both runs edit timproc_uso_b3.c, different functions, and both regenerate port/gen).
binds-left 72 -> 55 (unnamed 16 -> 7, the Text+0 sentinel calls). undefined.txt 184 -> 170.

### 18.9 Run 819: the first headless boot (agent-g)

agent-g run 819, branch agent-g on main bde103ad0 (tenshoe links, 0 undefined). Gate PASS before
each commit (ROM byte-identical, 3579/3579, verify-blocks 6/6, clean build OK; check 8314 named
calls / XDATA 446 sites, 0 mismatches). test_fs 24 / 0.

| commit | what |
|---|---|
| 9069673c5 | `PORT_TRAP_UNDEFINED` (CMake option, **debug only, default OFF**, needs `PORT_LINK`): a probe link with `--warn-unresolved-symbols`; `port/tools/gen-port-traps.py` reads its unversioned `nm -u` and writes one trap per symbol; `port/trap/trap.c`: a code symbol (R_386_PC32 from .text) prints `PORT TRAP: <sym>` + backtrace and aborts; a data symbol sits in a PROT_NONE region (2 pages each), the SIGSEGV handler names it (`PORT TRAP: <sym> (data, +off)`). Nothing is stubbed. The probe and tenshoe both use `--export-dynamic` (same gc roots, symbolised backtraces). Any other SIGSEGV is reported with a backtrace too. |
| bec9275e3 | `KR_ARG / KR_ARG0 / KR_PARAM / KR_PARAM0` (uso_call.h, empty in the ROM build); AudioHeap allocator wrappers, AudioSeq_ResetSequencePlayer, the 9 bootup snd_* wrappers; `scripts/port-kr-passthrough-audit.py`; port/fs drops the kernel's 8-alignment check; SRAM path `SRAM_DMA_MISALIGNED` = 0 under PORT; `sys_fatal` -> `port_sys_fatal` (message, backtrace, exit) |
| bdfa6a9b0 | vtable-call evaluation order (8 bootup sites), BinFileMgr_getAcquire / getRelease / checkVoid and Node_Load pass-throughs, FogParms_emit byte order |

**How far.** `run32 tenshoe --rom baserom.z64 --frames 120 --trace t.log`:
port_game_boot -> boot_main -> SnowBoard_ctor (snd_Init / AudioHeap_Init OK) -> App_main (Mem, console,
pads, GfxLib_init, RcpMgr) -> SnowBoard_InitInstance (rom/version.bin, anims.bin, Node_ctor) ->
GameFlow_create (gui.uso, pads, Backup / SRAM options, flowimgs.bin) -> **GameFlow_startMode(0)**
(N64DEMO, n64proc.uso) -> n64_procMain -> N64DemoProcess_ctor (sprites from flowimgs.bin) -> back in
App_main -> main loop -> **app_runOneFrame frame 1**: App_Display (FogParms OK) -> gfx_end ->
gfx_submitFrame -> gfx_queueGfxTask -> RcpMgr_queueTask -> RcpMgr_removeTask: **SIGSEGV at 0x3f800054**
(a task / list pointer is 1.0f: `gGfx->rcp` or the RcpMgr list head is wrong, layout or bind; not
diagnosed). The trace is still empty (the F line is written after the first step).

**Bug classes found (each will recur):**
1. **K&R argument pass-through.** The matched C calls with fewer arguments than the callee reads;
   on MIPS the rest ride in $a0..$a3. On i386 the callee reads stack garbage. Fix with `KR_ARG(x)`
   / `KR_ARG0(x)`, and for a ROM `(void)` / `()` wrapper `KR_PARAM0(decl)` / `KR_PARAM(decl)` (or
   `#ifdef PORT` for a K&R `()` definition, which `KR_PARAM0` would turn into `(void)`).
   `scripts/port-kr-passthrough-audit.py` lists the CALL-family sites (98 left; some are
   harmless, the callee ignoring the parameter). Direct calls (not CALL/XCALL) are not scanned, and
   VT_SLOT calls passing only `this` (Node_Load's slot 8 loadData(this, path)) are not either.
2. **Unsequenced callee vs argument.** `VT_SLOT(p, N).fn(.. VT_SLOT(p = o->vptr, N).delta ..)`:
   IDO's argument-first order is not gcc's. Under PORT assign p first. The 8 sites found by a
   regex are all in bootup; C++ donors use other spellings (not scanned).
3. **Host alignment.** N64 frames / heaps 8-align buffers that the kernel's DMA checks require;
   i386 does not: port/fs and the SRAM path no longer check.
4. **Byte order of sub-word reads of int fields** (FogParms: shorts at +0x12 / +0x16 of int
   words). The blob typing cannot fix these: they are in code.
5. `sys_fatal` was a silent hang headless; it now reports and exits.

**Tools.** No gdb on this machine: `apt-get download gdb` + 5 libs (libbabeltrace1, libipt2,
libsource-highlight4v5, libdebuginfod1, libboost-regex1.74.0) extracted with `dpkg-deb -x`, run with
`LD_LIBRARY_PATH` = the extracted lib dir; `gdb --args <run32 root>/usr/lib32/ld-linux.so.2
--library-path <root>/usr/lib32 tenshoe ...` plus `add-symbol-file tenshoe` (non-PIE). Interrupt a
hang with `kill -INT $(pgrep -x gdb)`.

**Next:** the RcpMgr_queueTask fault (print `gGfxLib` + 0x218 and the RcpMgr list head at the first
gfx_queueGfxTask); then title flow. Sweep the audit list on the title / race paths before they are
hit.

### 18.11 Run 821: node streams from the data, bootup / game remainders, the last reader templates (agent-c)

agent-c run 821, branch agent-c on main bde103ad0: 1c79f3f3e (`scripts/port-gen-blob-types.py` +
`port/gen/blob_types.tsv`), 569eedbb1 (`#ifdef PORT` reader swaps). Gate PASS before each commit
(ROM byte-identical, 3579/3579, verify-blocks 6/6, clean build OK).

**Node command streams.** ProcNodeList has exactly one caller in the ROM
(SnowBoarder_loadBoardModel, bootup Text 0xB47C), and nodelist_walk / dispatchList / dispatch are
called only from inside the interpreter, so the streams cannot be found from call sites. They are
now found from the data. A word `1000` at a symbol / pointer target is parsed with the grammar:
- known ops (0, 100..120, 1000..1019) with argc <= 16;
- 1003 opens a walk, and that walk's own 0 word closes it;
- the list ends at a depth-0 0 word;
- 1017 targets are followed.

Result: the two rider lists (bootup 0xA924 and 0xABBC; the closing 0 at 0xBBF0 was untyped
before) and **map5_data 0x9D4**: an MNode with a name, scale (10000 x 3), rotate and translate,
around a 1003 shape. No other module (title, gui, map4, boarder1-5, charsel / charfir / charsps)
has a 1000-headed stream. A scan of every module for op words 1000..1019 finds only coincidental
values outside bootup and map5. Those modules' assets are shape / material / texture streams,
which were typed already.

**Shape op 30** (BasePolyShape +0x48 count, +0x6C table): the table holds PolySeg
`{s32, u16 v[2]}` records. PolyShape_makeEdgeVtxs reads v[] as u16. The table was not typed
before (bootup 0x20CBC).

**bootup Data (the run-815 list), with the readers:**
- 0x1A2E0: OoT synthesis.c `D_801304B0` u16[8] (unreferenced in OoT too).
- 0x1BC60: OoT seqplayer `sSeqInstructionArgsTable`, bytes.
- 0x1C128: snd_ResetVolumeLevels' 11 f32 volume steps.
- 0x1C320: a byte permutation.
- 0x1E21C: sys_fatalHaltLoop's `gl_fatalHaltExitCombo`, s32.
- 0x1E9A4: f32 identity and vec4.
- 0x1F984: 4 x u16[10]. Typed by the values only; the reader is not located.
- 0x20350: 12 f32 vec3. The str rule had typed 0x203C8's `0.5f` as the string "?".
- 0x20598: 3 f32 vec3.
- 0x20D2C and 0x21130: flag-only shape streams, u32.
- 0x211E0: the fault_printFlags `{mask, bits, name}` tables, 82 records.
- 0x21AC8: math_mtxChain series f32.
- 0x21AF0: math_mtxToQuat `next[3]`.
- 0x2D690: `__osThreadTail`.
- 0x70E8 / 0x1FC74: table heads.
- RoData 0x24E0: f64 1.0.

**game Data:**
- 0xCC4: s16 pairs (lh 0xCC4 / 0xCC6).
- 0x1068: an s32 table.
- 0x109C: rumble bytes.

**genproc:** the s32 tables. **boarder3 0x3B28:** s16[3] x 231.

**New rules:**
- RoData literal-pool words that no access typed become f32 when the value is a plausible float
  near 1 (6 words).
- A string may now start with `\n` if it has at least 3 printable characters.

**Unknown blob bytes, before / after (0 conflicts both):**

| module / section | before | after |
|---|---:|---:|
| all blobs | 6,005 | **3,019** |
| bootup Data | 2,961 | 1,774 |
| bootup RoData | 405 | 389 |
| boarder3 Data | 1,400 | 14 |
| genproc Data | 323 | 191 |
| game Data | 189 | 55 |
| map5_data Data | 42 | 0 |

The rest of the unknown bytes are almost all 1-3 byte gaps: string tails, single-`\n`
strings, and RoData pads. Non-zero unknown runs of 4 bytes or more:
- bootup Data: about 12 gaps between strings;
- bootup RoData: 0x2371, a u8 table (bytes either way);
- game RoData: 0x1BA (`\nNULL\n` tags, bytes).

**Reader templates (18.2).** `PORT_BE_SWAP32S` is now in 29 more copies:
- balloon (2), checkpoint (2), heli (4), trnproc (4);
- snoweffects (15, four families);
- game_libs fs_gdlReadInt_00032D84 / fs_gdlReadQuad_00032DC0 (hostio_readQuadParm).

Every int-reader caller either stores the value or skips the Parm tag. None compares a tag.

Still unswapped, on purpose:
- AnimData_load, TrickTable_readEntry, ImageFile texels, Backup_read: bulk reads, handled at
  extraction or kept as bytes;
- stream_readS32_00005EF8: the EnvSettings tag;
- fs_read_00066404.

The title path readers (titproc, flowimgs ImageFile cmds, gui, n64proc via game_libs) were
already swapped. **The 18.2 to-do list is closed.**

**Next:**
- The port build was not run in this run. Regenerate the blobs, rebuild, and check the
  run-819 boot gets no further byte-order faults from the data.
- 0x1F984's reader.
- Sub-word reads of int fields in code (run 819's bug class 4): an audit, not blob typing.

### 18.11 Run 823: the K&R and evaluation-order sweeps (agent-e)

agent-e run 823, branch agent-e on main 2f16f6e23: 32bf2f384 (evaluation order) and 1f9805c30
(K&R). Gate PASS before the commits (ROM byte-identical, 3579/3579, verify-blocks 6/6, clean build
OK; `check` 8314 named calls, 0 mismatches). tenshoe links.

**Class 2, callee vs argument order.** `scripts/port-evalorder-audit.py` scans the PORT-active text
of every unit the port compiles (C and C++) for a call whose callee expression reads a variable that
its own argument list assigns (FWD), or the reverse (REV). A gcc -E pass over all 480 units found
the same set, so no macro spelling hides one. 11 sites: agent-g's 8 plus Process_pause_0000F9E8
(`vt[0x5C / 4]`), settings_setFlag4_000126EC and the C++ donor copy of QuitProcess_onQuit. No
function-pointer, PMF or REV site exists. 0 left.

**Class 1, K&R pass-throughs.** `scripts/port-kr-passthrough-audit.py` now:
- reads the SHIPPED body (sourcemap `source`: donors, imports, C++), not the host placeholder, and K&R
  definitions (Node_handleMsg, the OoT audio code);
- scans direct calls (declarations, #define bodies and strings skipped);
- scans this-only virtual calls (`VT_SLOT(p, N).fn(this)`, CF_Vk). The slot's arity comes from the ROM
  cfront vtables (DataRelocs typed `vtbl`): the max over the tables holding a `<CallerClass>_`
  function, else the arity most tables agree on (a plain max over all tables is noise);
- with `--rom`, prints the caller's register at the jal (`in:aN`, including the
  `lw aN, frame+4N(sp)` home reload; `call:<f>` = garbage left by an earlier call; or the instruction
  that set it) and whether the callee names the parameter. The walk is linear, so a jal reached by a
  branch has to be checked by hand (MCamera_doCommand, fs_gdlSeekFile, Friction_handleMsg,
  BasePolyShape_handleMsg, QNode_handleMsg).

Counts: 98 before (CALL sites only, host files). The extended scan gives 115 (call 98, direct 8,
vt 9), and the K&R definitions add more (Node_handleMsg ...). About 85 were fixed (KR_ARG / KR_ARG0;
26 callers got KR_PARAM / KR_PARAM0, or an `#ifdef PORT` header for a `()` definition). 24 are left
and assessed:
- harmless (the callee overwrites or ignores the parameter): 9 Node_handleMsg (tag), 6
  gui_fontAdjustAdvance (a2), gl___osSpSetPc (flag), AnimGroup_load (a1 only reaches
  fs_gdlReadInt), Node_Load slot 8 (BinFileMgr_loadData's a1 goes to fs_getHandle, which ignores it)
  and Window_setDefaults slot 10;
- **for agent-g (gfx_* / RcpMgr_*, not touched):** gfx_thunk_00046B44 -> gfx_vcall_0004E150 (a0 =
  its own a0), gfx_listAppend_0004E214 -> list_append (a1 = its own a1), and the this-only slot-0
  calls in gfx_end (x2) and gfx_vcall_0004E150. Their tables were not resolved (slot 0 of the material
  tables is BaseMat_onFrameStart(this, a1)).

**A new bug class found on the way: swapped call names.** NameEntry_updateEntry called
`CALL(Backup_writeCourseArcadeOptions_0000B3DC)(session, name, rider, board)` and then
`CALL(Backup_sessionSetNewNames)(session)`, but the ROM relocs are the other way round. The ROM build
cannot see the CALL names, and `check` did not flag it, so the order is not checked within a
function. On the port each call went to the wrong function. A per-function comparison of the ordered
jal targets against the ordered CALL names would find the rest.

**Boot.** Under run32 in a fresh directory, both this build and a build of 2f16f6e23's sources fault
the same way: a jump to 0x40012 during SnowBoard_InitInstance / GameFlow_create (once
`sys_fatal: BinFile Group out of range`). So that fault is not from these commits. agent-g's frame-1
runs used `/tmp/claude-1000/agent-g/run`, with its 1080.sram present.

### 18.12 Run 825: partial reads of wider fields (agent-c)

agent-c run 825, branch agent-c on main aa4397bb6. Gate PASS (ROM byte-identical, 3579/3579,
verify-blocks 6/6, clean build OK). The changed units compile under the port flags.

| commit | what |
|---|---|
| b39cfbeef | `scripts/port-partial-read-audit.py` (below) |
| b84d7948b | AudioCmd queue packing (QueueCmd op word, QueueCmdS8 / U16 value position); SnowBCollider_ctor contactFlags; `PORT_BE_BYTES32` / `PORT_BE_HI16` / `PORT_BE_LO16` in port.h |

**The tool.** It works from the ROM-exact objects (build/src/**/*.o). For each function, a forward dataflow over basic blocks gives every base register a symbolic root:
- the incoming a0..a3 / s*;
- a %hi/%lo symbol, or a KSEG constant;
- a call result;
- a loaded pointer chain (`[[&gGfx]+0x10]`, up to 4 deep);
- a tracked frame slot.

Roots are compared at three levels:
- within one function;
- across the segment, for roots built on a global symbol;
- across functions that declare a parameter of the same named struct type, or share a `Class_` prefix for a0.

Not compared: excluded functions (port/gen/excluded.tsv), the second copy of a donor, and the IDO argument home slots.

Classes:
- narrow-in-word: a lh / lb inside a word that is also accessed as a word;
- word-over-narrow: a lw spanning two or more narrow sub-fields;
- byte-in-half;
- harmless: lw→sw copies, lwl / lwr memcpy, stores of byte-symmetric constants.

`--csrc` lists the C re-views (`*(s16 *)&x`, `((u8 *)&x)[n]`, `union`), `--boot` keeps the boot / title closure, and `--all` adds the harmless windows.

**Counts (all modules, port-compiled functions only):**

| class | windows | functions |
|---|---|---|
| narrow-in-word | 9 | 11 |
| word-over-narrow | 5 | 5 |
| byte-in-half | 0 | 0 |
| harmless | 4 | 7 |

The C scan found 119 lines.

**Triage of the object hits:**
- FogParms_emit +0x12 / +0x16: already fixed (run 819). It is the tool's positive control.
- 12 hits are audio-driver bitfield containers:
  - SequenceChannel / SeqPlayer / Note / NoteSubEu / Sample: a `u32 x:1` run next to u8 fields;
  - AdsrUpdate / SeqLayerProcessScript / InitSampleState sp+0x2c.

  They are consistent C (members on both sides) on runtime-built state, so harmless here. Their mask / shift sites belong to plan 18.3 (AUDIO_FLAGBIT).
- The harmless windows:
  - BoardTrail [this+0x2c]+0xA30: an lwl copy of RGB bytes;
  - RecordOptions_drawCourseTimes sp+0x74: a string initialiser;
  - Audio_NotePortamentoInit: a copy;
  - AudioLoad_FinishSlowLoad.

**Triage of the C scan:**
- Fixed (b84d7948b):
  - **AudioCmd queue.** `AudioThread_QueueCmd` stores the op word 0xOOAABBCC, and ProcessCmds / ProcessGlobalCmd / ProcessChannelCmd read it back as u8 op / arg0 / arg1 / arg2. On x86 every queued command decoded with op = arg2. QueueCmdS8 / U16 put the value in the top byte / half, read back as the arg union's asSbyte / asUShort (0 on x86). Every snd_* / title-music command passes through these three functions (67 S8, 35 S32, 25 F32, 5 U16 call sites).
  - **SnowBCollider_ctor** `((u16 *)&a2)[1]`: the race path. The object audit cannot see it, because it is an argument home slot.
- Harmless (same width as the declared field: regalloc-lever lvalue casts): AnimData_load numNodes (s16), AudioSynth reverb resampleFlags / unk_0E / volume, AudioHeap_Init tatumsPerBeat, numSequences (s16), snd_SoundObjUpdate pan[3] / unk1A / kind. The two dead `while (0)` Node handle reads are harmless too.
- Same-width unions (float / int, pointer / s32, Vec3 / f32[3], Gfx / long long): harmless on i386.
- Excluded by the port: kernel uso_allocSlot / kdebugserver, and the libultra unions.
- Already handled: CMD_B3 (run 624).
- **Open:** Node_handleMsg FIND_SERIAL reads `v.serial` as an s16 at payload +4, but the union also has an `s32 on` there. Check the sender: if it stores an int, the receiver reads the high half on BE and the low half on x86. Also open: the audio-driver bitfield-union `asByte` mask sites (plan 18.3).

**RcpMgr / gfx (for agent-g):** no hits. An early run aggregated `.bss` section symbols across objects and showed a false RcpMgr_ctor `sw 0x12345678` vs guPositionF window. Section symbols are now per object.

**Coverage limits:** see the tool's docstring. A narrow access whose wide twin is in an unrelated function (calls go through placeholder relocs, so there is no interprocedural link) is not seen, and neither are `D_00000000`+0 data references (one root per site). The 56 "lone sub-offset" narrow fields (no access at +0 of their word) are a review list: a sample was checked (MorphPolyShade s16[3], PolyShape / Sprite +0x1E s16, GameFlow settings bytes, SnowBoarder +0x9A2 lh in 4 functions), and all were declared narrow; the rest are unchecked.

### 18.13 Run 827: bitfield audit finished, FIND_SERIAL, the narrow-read review list (agent-c)

agent-c run 827, branch agent-c on main 65e5004b6. Gate PASS before each commit (ROM byte-identical,
3579/3579, verify-blocks 6/6, clean build OK). The changed units compile under the port flags with no
new warnings; `make -C port/audio test`: 147 + 264 passed, 0 failed.

| commit | what |
|---|---|
| 49d13aa00 | audio flag bits in host order at 9 more IDO-mask sites (below) |
| adf111315 | port/audio: gAudioHeapInitSizes +0..+4 swapped as two s16 (was s32): tatumsPerBeat |

**Bitfield inventory.** Every bitfield declaration in include/, src/ and port/ (C and C++), grouped by struct:

| struct(s) | storage | status |
|---|---|---|
| audio.h `Sample` + views (gl_258C0_Sample, Desc25BFC, Desc258, gl_21498_Bits, B22398) | u32 word 0, cartridge fonts | done (15.6 re-pack); FinishSlowLoad `medium` fixed now |
| audio.h `SequencePlayer` + views (gl_201B8_Obj, gl_235E4_Rec, Fl_2978C, BF2A7D8, gl_27E24 / gl_28604 / gl_26790 / gl_2B5F4 SeqPlayer, 26D64's u8 `flags`) | u32, runtime | views consistent; masks: 624 + 3 sites in ProcessCmds now |
| audio.h `SequenceChannel` + views (BF1_000295BC, BF_000295BC, gl_2B09C / gl_2B5F4 Channel) | u32 bytes 0-1, runtime | 624 + SequenceChannelEnable, InitSequencePlayerChannels now. InitSequenceChannel clears all 8 bits of byte 0 (order-free) |
| audio.h `SequenceLayer` + views (AA30, ObjFlags2AB34, GlPooledFlags, gl_27E24 / gl_2ABC0 / gl_291C0 / gl_2AD1C / gl_2B09C / gl_2B5F4 Layer) | u32 / u8, runtime | 624 + SeqLayerDisable now; the post.c SeqChannelSetLayer mask copy is not compiled (import body uses GlPooledFlags) |
| audio.h `NoteSampleState` + views (gl_1CC98_Elem, ElemFlags1CF68, gl_dcb4 / gl_aud SampleState, gl_27804 bitField0/1, gl_28604_Note, 8356 union) | u32 bytes 0-1, runtime + gDefaultNoteSub (bit-reversed in 15.6) | 624 + NoteSetResamplingRate `hasTwoParts` now |
| audio.h `AdsrState.action` + views (gl_27E24 / gl_28604 AdsrBits, 29CCC Env, Gl29000Obj f60) | u8, runtime | 624 (NoteInit / NoteDisable) |
| audio.h `Stereo` + views (2AD1C, 27804) | u8, **script bytes** | 624 (`port_stereo_from_ido` at the 3 byte writes); the other asByte uses are `= 0` / `== 0` |
| `Bf5B5D8` Mem header (post0b) | u32, runtime | 624 (reversed under PORT) |
| `d14c_flags` (timproc b5) | - | members never used; its function is ported from the match_imports copy |
| kernel / rmon (kernel_000_c, 014, 022_d) | - | excluded (port/ultra) |

No other C / C++ file has a bitfield; match_imports has only context_game_libs_post.h's audio views.
All views of one word declare the same fields in the same order, so the member accesses agree on
both compilers. Only mask / shift / byte spellings and ROM data were at risk.

**Method (mask sites).** A C-level scan of the audio driver (post.c up to snd_UpdateTimers, the 17
audio o2 donors, the 3 audio match_imports, the ncc donor), filtered to the body the port compiles
(port/sourcemap.tsv): every `& | ^` with a constant, every shift, every `< 0` sign test, and every
constant store to a container byte. 354 + 12 lines reviewed by hand. New fixes (all `#ifdef PORT`):
- AudioThread_ProcessCmds (donor 26D64): `recalculateVolume` (|= 4), `applyBend` (&= ~1 / |= 1) and the
  `enabled` test (`>> 31`) that gates every channel command. On x86 that test read bit 31 (byte 3).
- AudioSeq_SequenceChannelEnable: `enabled = 1` / `finished = 0` (0x80 / 0xBF): channels never started.
- AudioSeq_SeqLayerDisable (`enabled = 0`, `finished = 1`); AudioSeq_InitSequencePlayerChannels
  (`enabled = 0`).
- Audio_NoteSetResamplingRate: `hasTwoParts` (byte 1 mask 2) set / clear.
- AudioLoad_FinishSlowLoad: `medium = MEDIUM_RAM` (byte 0 `&= ~0x0C`; the font swap re-packs Sample
  word 0, so on the host this cleared codec bits).
The 18.3 / 18.4 lists had missed these. The remaining hits are value arithmetic (GBI packing,
script command bytes, table indices), already-guarded sites, or bitfield-member spellings.

**FIND_SERIAL: clear.** The only sender of tag 0xE in any built object (scan of every `li 14; sw sp`
next to a call) is `Node_sendMsg14` (post0b): payload = &req.buf and payload +4 = `short a1_save`, an
s16 store. Sender and receiver (Node_handleMsg's s16 read at +4) agree on both byte orders.

**The narrow-read review list.** Rebuilt from `port-partial-read-audit.py --dump`: windows with only
narrow accesses, none at the word's +0, at least one read used. 95 windows (run 825 quoted 56 for a
narrower filter):
- 20 stack locals (a narrow local or struct field in one function): safe.
- 26 audio globals / AudioContext aliases: each offset resolves (DWARF of audio.h, -m32) to a narrow
  AudioContext member (samplesPerFrameTarget, specId, numSynthesisReverbs, the font cache ids, ...).
- The rest read declared narrow members (Backup time / name bytes, InputMgr ghost and options bytes,
  SoundObj, Note / Layer / Channel bytes, AnimData.numFrames, AudioTableHeader.unkMediumParam
  (swapped s16), Instrument byte 3). InputMgr +0x17D (pad17C) is written by mgrproc with an `sb`.
- **One real bug**: `gAudioHeapInitSizes` (+0x1CDD0) was swapped as s32[4], but AudioHeap_Init
  reads the s16 tatumsPerBeat at +2, so the host read the other half (0x1400 for 48). Fixed in
  audio_swap.c (adf111315) and covered by test_audio_swap.
- The same check over the other audio_swap ranges (bootup Data globals with code accesses) finds
  only word accesses on the word ranges.

**Open.**
- ~~Commit adf111315's message says "about 107x too slow"~~ **Wrong direction (measured in run 829,
  15.7):** tatumsPerBeat 0x1400 makes tempoInternalToExternal 107x smaller (10770 -> 100), and
  ProcessSequence clamps every tempo to it (`tempo = bpm * 48`, clamped), so the player advanced one
  tatum per update: 180 tatums/s for every sequence = 225 bpm. That is too FAST for every sequence
  under 225 bpm (seq 2, 176 bpm: 1.28x), and all music ran at one tempo.
- The mask scan is C-level and covers only the audio driver, because no other file has bitfields. If a new
  bitfield view is added, re-run the scan.

### 18.14 Run 826: every CALL name proven per site (agent-e)

agent-e run 826, branch agent-e on main 65e5004b6: 14265fde4 (tool + readability gate); monorepo
8aa37aa (gate-landing-tree.sh). Gate PASS (ROM byte-identical, 3579/3579).

**How the old `check` matched.** As a multiset per (function, placeholder token): a function's
CALL / XCALL names had to be contained in the ROM jal targets of its relocs against that token. That
proves each name is *a* callee of the function, not the callee of *its* jal, so 18.11's
NameEntry_updateEntry swap passed. (`--strict` re-derived each site, but was not in the gate, left
175 sites unprovable, and did not see names inside `#define` bodies.)

**`check --order` (the gate mode now; ~60 s).** Per (function, token) group:
- every ROM jal goes to one callee: the containment check proves each site (2177 names);
- 2+ callees: each site is placed on its own jal(s) by the verify compile (site N spelled `npc_uc_N`,
  so branches, loop tests, nested calls are in the compiler's emitted order), the donor-flag compile
  or the donor-source mirror for REPLACE_FUNC_BODY hosts; the derived callee must be the written name
  (6137 names);
- a CALL inside a `#define` body is a site of its own (`npc_ucm_K`): every jal of every expansion
  must call that name (SnowAI_ctor's INIT_ITER, post0b's DET3, the audio cache macros);
- an inlined site (C++ `inline operator new`) is proven in each function it lands in and must
  resolve to one callee;
- an unprovable site fails like a wrong name.

**Result.** 8314 named calls, 0 wrong, 0 unproven. No new swaps: run 823's NameEntry fix was the only
one in the tree. Getting to 0 unproven took tool fixes, not source edits (mirror skipped already-named
host sites; a thread race in asm_pad; zero-pad tails; header float decls in the C++ verify copy;
target-specific NCC_CFLAGS; collapsed call-free statements in the donor skeleton). The selftest now
re-creates both the cam_reset swap and the NameEntry swap and requires `--order` to fail them.

**Not covered.** Two port-only CALLs (in `#ifdef PORT` branches) have no ROM jal: FogParms_emit's
gfx_emitFog (same name as its #else) and game_libs_ncc_41820.cpp's `operator new[]` -> mem_new.
Both were checked by hand.

### 18.15 Run 831: every switch's case labels against the ROM's jump table (agent-e)

agent-e run 831, branch agent-e on main 56552e795: 724e7ad27 (port/tools/jumptable-audit.py, tree-wide),
7ae536d6b (labels), f7681ce59 (readability gate step 5); monorepo 189b0a8 (gate-landing-tree.sh, exit 10).
Gate PASS (ROM byte-identical, 3579/3579, verify-blocks 6/6, `check --order` 0 wrong).

**The bug class (run 822 Node_doCommand, run 829 audio).** A switch whose jump table is ROM data
(a `<func>_rodata` pin, a discarded or NOLOAD-pinned USO .rodata, a match_imports link) is checked
on .text only, and IDO lays the arms out in source order, so any permutation of the labels matches.
gcc builds its table from the labels.

**The audit (agent-c's game_libs donor tool, extended to every module).** C side = each build/src
object's own compiled tables (R_MIPS_32 runs into .text, split per table load; case base from the
`addiu` before the `sltiu`). ROM side without per-module constants: the function's masked .o bytes
are found in the baserom (all four byte alignments; the new USOs are 2 mod 4) or a decompressed
Yay0 block; S = function address in its module's text space, D = S - code offset and E = table
offset - the code's own `lui`/`lw` address are bootstrapped by vote; every table is then read where
its code loads it. 102 tables: 97 OK, Node_doCommand PORT-ONLY (the ROM never reaches its
`case 0x6C: return` arm, so the true labels let IDO drop that arm; NDC_* under PORT stays), 3 host
placeholder tables superseded by donors, 1 `_lay` layout function. ~10 s; reads build/src objects,
so `rm -rf build/src build/non_matching/src` before gating a label change (make does not rebuild a
donor when only its source changed).

**Fixed (labels only; arms keep their order, ROM identical).**
- tit_procMain (title flow): 3 empty, 4 demo flags, 5 / 6 the two attract demos, 8 -> 10 and 7 -> 9
  the ghost replays. The old labels sent 6 / 8 to an empty state 10 / 9 (endless loop).
- arc_procMain: 6 menu, 7 name entry, 8 view record.
- gl___osDevMgrMain: libultra 2.0 types as the kernel copy (10 LOOPBACK, 11/12 DMA, 15/16 EDMA).
- dbg_threadStateName (the 34548 unit-head replica): agent-c's 343F4 labels.
- RiderAnim_applyDamage_0000EDD4 (0 empty, 1..4 dm1..dm4), RiderAnim_hitFeedback_0001189C (2 / 3
  swapped), SnowAI_aimWeave (weave 0, +side, 0, -side).
- snd_HandleSeqEvent_30AF4: both mode switches (match_imports and the game_libs_post NM body).
- LevelList_createItem: as CourseList_createItem (11..13 the mode-3 arms, 0..7 the charmap arms).

**Not covered.** Switches IDO compiled as compare chains (no table: the labels are in .text, so
already checked), and NON_MATCHING bodies (their code is not in the ROM; the 30AF4 NM copy was
relabelled by hand to match its match_imports twin).

### 18.11 Run 822: frame 1 to the title demo's game_init (agent-g)

agent-g run 822, branch agent-g on main 2f16f6e23 (run 819 as landed). Gate PASS on the
committed tree (ROM byte-identical, 3579/3579, verify-blocks 6/6, clean build OK); CALL check
8314 / 0 mismatches, XDATA check 447 sites / 0 mismatches (+1: Process_exit).

| commit | what |
|---|---|
| 59c1e27e2 | tools: port-gen-binds donor pins; port-gen-uso data-only USO closure; port_cfront.h `CF_CTOR_NEW` + port-gen-build / cc-select ctor entries |
| 07d30c55a | src (PORT only): K&R pass-throughs, Process_exit XDATA, 6 `port_ctor_*` entries, Node_doCommand ROM table, ItemMgr_Load tag swap |
| e65085da2 | port/gen regenerated |
| ca1b9c0ef | src (PORT only): fresh-SRAM path, full-size Backup reset buffers (class 8 below) |

**How far.** `tenshoe --frames 3000 --trace state.log`: the frame-1 RcpMgr fault is gone; the
N64 logo (n64proc) runs, fades and quits; GameFlow_restart starts the title mode (titproc):
tit_procMain -> game_init loads game.uso, effects.uso, map7_data.uso ("Slalom Course"),
bg4tex.uso, builds the BGBox, the map, the items, then game_setupDemoSolo -> SnowBoarder_ctor
-> the rider anims -> SnowBoarder_loadBoardModel -> ProcNodeList -> skin_cmdSkinShape ->
MNode_updateChildren: **SIGSEGV at 0xa6635** (not diagnosed: a node child / matrix pointer
read from the board data). state.log (flow = procState, nextFlowMode):

```
F 0..197    flow=0,0  rand=228889ec   N64 logo (N64DEMO procState 0)
F 198..220  flow=1,0  rand=396d392b   procState 1: Process_fadeOut, Fader runs (sys_randf moves)
F 221       flow=0,1                  QuitProcess -> GameFlow_restart -> title mode; crash in game_init
```
The trace is written every frame now (the F line is after the step; nothing to fix).

**Fixes, by class.**
1. **K&R pass-through** (run 819 class 1): `math_orthoF` called `math_mtx4Identity()` with
   mf riding in a0; on i386 it took a stack word, the RcpMgr, and wrote the identity over it
   (RcpMgr.unk00 = 1.0f: the 0x3f800054 fault). Also gfx_listAppend_0004E214 (the light in
   a1), gfx_thunk_00046B44, AnimPlayer_getKeyFrame / getKeyTime (AnimDataMgr_lookup's a1:
   "Missing AnimGroup 16662"), AnimDataMgr_loadFile (AnimGroup_load a1 = self, left by the
   leaf AnimGroup_init), AnimData_waitFrames. **agent-e: skip these 7 audit rows.**
2. **A code address stored as data through a placeholder token** (no jal, so CALL never named
   it): Process_exit's `D_00000030 = func_00000000` is &GameFlow_restart_000116C8; spelled
   `XDATA(func_00000000, GameFlow_restart_000116C8, 0x0)`. Without it the logo never left
   procState 1. Grep found no other such site.
3. **match_imports donor pins.** A donor is linked alone with its tokens at the
   match-origins-<f>.ld values, then bind-native-relocations.py renames each reloc symbol to a
   carrier whose undefined_syms value the ROM link adds. port-gen-binds used the token's own
   undefined_syms value (usually absent, 0), so 36 aliases were wrong: game_init's
   `bootup_27E8_ref_7334` etc. (the rom/game.uso path: "usoLoad() error loading file") at Data+0,
   the GfxLib scale words at +0 instead of +0x1FC, SnowBoarder_update's desc / root words,
   bu_d900 descs, D_E354_1C73C_c (was +0, now +0x1C73C). Pin = origins value + carrier value
   (32-bit wrap: snd_updatePlayer's -0x44 + 0x44 = 0).
4. **Data-only USOs** (bgNtex, mapN_data, the board models, effects) had no port module: the
   course table's words into bg4tex were 0 (U64BGWall_ctor read cfg = 0). port-gen-uso now
   keeps every data-only module a kept module's Data / RoData relocs reach (26 -> 58 modules,
   ~6 MB of blobs); blob_types.tsv types them (agent-c: please review the new modules' rows).
5. **cfront ctors called with this == 0** (BGBox_ctor(0, ..), Sprite / Shadow / QNode /
   BasePolyShape / CoolGadget ctors): the port aliased the name to gcc's C1 ctor, which neither
   allocates nor returns this. Each donor now has `extern "C" Cls *port_ctor_<name>(Cls *self,
   ..) { return CF_CTOR_NEW(self, Cls, (..)); }` (placement new, else `new Cls`: the class's
   operator new), and port-gen-build aliases the name to it, keeping the binds on the mangled
   body via `port-alias: NEW port_ctor_NEW C1`.
6. **Pinned donor jump tables.** Node_doCommand's donor (REPLACE_FUNC_BODY, its jump table
   renamed onto the ROM's at RoData 0x1A1C) matched .text only; its case labels were wrong.
   The ROM table: 0x64 name, 0x65 attach, 0x66 default, 0x67 set-global, 0x6C handle (the
   skinmgr streams carry `0x0001006C <handle>`). The port spells the ROM arms (`NDC_*` under
   PORT; the ROM labels unchanged). MNode_doCommand / QNode_doCommand tables look consistent
   with source order (not proven). Other `*_rodata`-pinned donors deserve the same check: the
   port compiles their C tables.
7. **Byte order (agent-c):** ItemMgr_Load read the file's 4-char type tag raw while the
   ItemTypes' tags come from bootup Data words typed u32 (swapped): "no st0". The tag read is
   now swapped under PORT (18.2's "ItemMgr_Load's tag read must stay unswapped" predates the
   u32 typing of 0x7E50..). Any other tag compare between a file and a blob word needs the
   same care.

8. **Frame-layout overflow** (deterministic boot): Backup_resetOptions / Course / Arcade / Ghost
   build the whole record at `&scratch` and let it run into `int pad_arr[N]` above it in the IDO
   frame; gcc orders locals its own way, so with no 1080.sram (the game's fresh-save path, as on
   new hardware) the reset smashed the return address (the jumps to 0x8080000 / 0x40012 /
   0x3a98 seen from clean directories; the earlier runs had a 1080.sram). Under PORT each uses
   one buffer of the record type. Any `pad_arr` + `&scratch` pair written past its size is
   the same bug (`grep -n "int pad_arr\["`: these 4 were all in src/).

**Run command (reproducible).** From an empty directory (the first run writes 1080.sram
through the fresh-save path; a second run reads it back and reaches the same point):
```
mkdir run && cd run
tools/i386-sysroot/run32 <pbuild>/tenshoe --rom <1080-decomp>/baserom.z64 --frames 3000 --trace state.log
```
Both runs: SIGSEGV 0xa6635 in MNode_updateChildren at frame 221, state.log as above.

**Not done (agent-e's handoff):** the `this`-only slot-0 vcalls in gfx_end (x2) and
gfx_vcall_0004E150 (the GfxLib +0x134 object, vtable unknown); not on the faulting path yet.
gfx_thunk_00046B44 / gfx_listAppend_0004E214 are fixed (07d30c55a).

**Next:** the MNode_updateChildren fault under skin_cmdSkinShape (board model node stream,
boarder1.uso data now loaded: check the blob typing of the stream and the skin shape's child
links), then the title demo's first race frame.

### 18.16 Run 830: the title demo runs headless, 3000 frames (agent-g)

(Numbered 18.16: agent-e's run 831 took 18.15 in the working copy.) agent-g run 830, branch
agent-g on main f5c1119b4. Gate PASS on the committed tree (ROM byte-identical, 3579/3579,
verify-blocks 6/6, check --order 8314 named calls / 0 wrong, clean build OK).

| commit | what |
|---|---|
| 2e4e49bf1 | tools: port-sourcemap `$(foreach)`; port-gen-decls C++ prototypes + 2 BYVALUE callees; cc-select folded member addends; trace `flow=state,next,mode`, line-buffered |
| f55d9942a | src (PORT only / ROM-neutral macros): PORT_FBITS, PORT_SRET_NOPOP, snow trail donor cfront layout, boot-code check swap, SnowBoarder_reset bzero, trace collector |
| 882b400c5 | port/gen + source map regenerated |

**How far.** `tenshoe --frames 3000 --trace state.log` exits normally (rc 0, 5777 RCP tasks).
The run-822 MNode_updateChildren fault was already gone after the regen; what followed, in order:
trace collector on dataMgr->owner = -1, then six game bugs. state.log (flow = procState,
nextFlowMode, flowMode at +0x38):

```
F 0..197      flow=0,0,0   N64 logo (N64DEMO procState 0)
F 198..220    flow=1,0,0   Process_fadeOut
F 221         flow=0,1,0   GameFlow_restart -> title mode (titproc), game_init
F 222..2532   flow=0,1,1   title demo running: rider moves (r0 pos / quat / speed change, sys_randf moves)
F 2533..2566  flow=4,1,1   procState 4 (the demo's end / fade)
F 2567..2999  flow=0,1,1   procState 0 again (next demo pass or title loop)
```

**Fixes, by class.**
1. **Donor splices written with `$(foreach)`** were invisible to port-sourcemap.py: 40 shipped
   bodies (snoweffects, heli, nameent, trnproc) compiled as their EMPTY host placeholders. The
   symptom was BoardTrail_init_00005FD4 (vtable slot 10 of the board trail) doing nothing, so
   SnowRing_emit read cam = 0xFFFFFFFF. Check after any Makefile change: `port-sourcemap.py`
   donor count (now 284 cpp + 181 c).
2. **C++ ABI across the C boundary.**
   - (a) gcc emits no DW_AT_prototyped for C++, so port-gen-decls promoted an extern "C" C++
     definition's float to double (CollShape_nearestHit: the hit pointer arrived shifted).
   - (b) An int holding f32 bits passed to a prototyped float in a C++ caller converts the
     value: `PORT_FBITS(x)` (5 sites).
   - (c) A struct-by-value return: g++ on i386 pops the hidden pointer in the callee, but the
     C side takes an out-pointer and does a plain `ret`. `PORT_SRET_NOPOP` (callee_pop_aggregate_return(0))
     is on the 6 C++ declarations of C callees and on the one C++ definition with C callers
     (SnowAI_aimWeave). The drift had overwritten applyMode's return address.
   - Found with a DWARF scan: C++ declarations returning a struct vs C definitions. All are fixed.
3. **Newly shipped C++ donors need the cfront treatment.** snoweffects_uso_ncc_b.cpp is done
   (explicit vptr, CF_V1, ROM vtable stores through the snowb_vtbl_* binds). **nameent_uso_ncc.cpp
   still declares `virtual`** (g++ vptr at +0: wrong layout); it is not on the title path.
4. **Per-addend binds and folded members:** g++ folds `->y` into the addend (D+0x12C). The
   bind now uses the nearest bound addend below, within 0x100 (MapLighter_*, 8 refs).
5. **Bare `func_00000000(...)` in a donor** calls a real, empty function on the port.
   SnowBoarder_reset's mid-entry bzero (gl_bzero+0xC) never ran, so edge / edgeSteer /
   edgeSlope kept Mem_allocHigh's 0xFF fill. That is a NaN: the rider's position went NaN on
   its first integrate. The other UNNAMED mid-entry sites are bound or are libultra.
   **Audit candidate:** bare `game_uso_func_00000000(...)` at game_uso_mp72_B3C.cpp:252
   (cam_updateView) also hits a defined function.
6. **Byte order (agent-c FYI):** RiderAnim_init_0000D458 dma_reads ROM 0xF10 (the boot-code
   check: 0x04080040, 0x02081040), and on a mismatch it puts the rider in stateStopped. The raw
   ROM words are now swapped under PORT. No blob typing rule changed this run.

**Renders** (f3dreplay, default ucode): run/png/f000120.png, the trademark screen, is still
correct. The title-demo frames are wrong:
- f000600.png: a white rectangle and a bar, from an 8.9 MB dump.
- f001000.png and f001500.png: grey rectangles, from 180 KB dumps.
- f000280 / f000440: 880-byte dumps (near-empty lists).

f3dreplay reports "5 lists widened, 0 unresolved G_DL" on every frame, so the 3D course and
rider are missing from the dumps or from the replay. That is the next lead (agent-a: the dump
may capture only one RCP task per frame; 5777 tasks / 3000 frames).

**Next:**
- Why the race view does not render: dump contents per task, ucode per task.
- nameent_uso_ncc.cpp cfront layout.
- The B3C bare-token audit.
- A ROM-side trace (emulator) to compare the procState 4 at 2533 against the real demo length.

### 18.17 Run 836: sweeps of run 830's bug classes (agent-e)

agent-e run 836, branch agent-e on main 3998bae47: d973a1ece (tool), 99e2c21cf (src, PORT only /
ROM-neutral XCALLs), 83d432c58 (port/gen/decls_cpp.h). Gate PASS (ROM byte-identical, 3579/3579,
verify-blocks 6/6, check --order 8339 named / 0 wrong, 0 defined-token calls, clean build OK).
Note: `gate-landing-tree.sh` gates `$LAND_WT` (default projects/1080-agent-d): pass
`LAND_WT=<your worktree>`.

**Class 1, bare calls through a token the port defines.** port-gen-binds binds only tokens the
port library leaves undefined, so a bare token that the port defines keeps its own definition.
Method: every jal reloc of every proven function (object bytes = ROM) against a name in
port/sourcemap.tsv, resolved to its ROM TextReloc callee and compared to the token; the
CALL-named sites are taken out; a function whose PORT view has no bare site left is fine.
- `tim_drawTime_00001340` / `trk_drawScore_000013B8` (timer / score HUD): ALL their calls were
  spelled `tim_main(...)` / `trk_main(...)`, real functions on the port. 25 sites named per site
  (`plan --tok tim_main --tok trk_main`).
- SnowBoarder_reset (fixed in 830), the cfront ctors in 6204 / E9FC (PORT ctors) are clean.
- **cam_updateView's `game_uso_func_00000000(...)` (B3C:252) is correct**: its ROM callee IS
  game_uso's Text+0 function. Same for boarder1-4 / map4b2 readQuadParm and SnowFall_rotateNormal /
  setPlaneDist (their module's Text+0 functions). agent-g: nothing to do there.
- Gate: `check --order` now runs `check_port_defs` (~5 s, 520 functions); the selftest un-names
  tim_drawTime's sites and requires a failure.

**Class 2, float bits / float types across the call.** Method: a `-Wconversion` port build (int ->
float at a call argument) intersected with the gimple dumps' call-argument conversions, a
float-literal scan (a float constant whose integer value is f32 bits), and a DWARF scan of the
linked tenshoe: every DW_TAG_call_site's caller-side declaration (call_origin) against the
callee's definition found from the call instruction (return type class, parameter classes,
struct returns). Found and fixed:
- `math_vec3Length_0005BBCC` was a K&R pass-through `void f(void) { sqrtf(); }`; port-gen-decls gave
  the C++ callers `int f(...)`: they pushed a double and read eax (9 sites: RiderCam_update x2,
  SnowChaseActorCam_update, game_uso 3558, heli x2, 3B9C0, 5F5F0, 5F984 x2, 64388). PORT body
  `float f(float)`; decls_cpp.h regenerated. (C callers worked only because gcc compiled the body
  to a tail jmp.)
- PORT_FBITS: absrot_matrix4's `o->x138` / `x134` (game_libs_ncc_33094) and gfx_calcPerspNorm's
  `nearWord` / `farWord` (ScreenWindow::run, game_libs_ncc_4C5E4: perspNorm).
- Left as harmless: int vs float prototype mismatches with no conversion (same 4 bytes on the
  stack), struct4 vs int, QNode_ctor's `(f64 0.0, f32 0.0f)` vs `(f, f, f)` (same 12 zero bytes).

**Class 3, struct returns.** The DWARF scan covers both directions (any caller declaration vs
any definition, C or C++), with the callee's `ret $4` read from the code. Note gcc's C ALSO pops
the hidden pointer (`ret $4`): the drift comes from an out-pointer spelling against a by-value
definition, not from the language. Two more were wrong (now called by value under PORT):
SnowAI_steer -> SnowAI_aimAlongSegment (game_uso_591C, the AI steering; C definition in 7C1C
pops) and BallRotator_applyArcball -> math_arcballPoint. The 6A30 / 71E0 callers expect the pop
(their PORT_SRET_NOPOP has no effect there, and the definition pops: consistent). The other 830
sites are consistent.

**Class 4, raw ROM / file bytes read as words.** Method: every shipped call of the DMA / PI /
fs read primitives, minus the reader templates. Fixed: AnimData_load (AnimKey {s32, f32} swap32,
resident frame data s16 x 7 swap16), AnimData_readFrames (streamed frames swap16), fs_readRecord's
rom/version.bin word 0. anims.bin was listed as "at extraction" in 18.2, but extract.py swaps
nothing. Checked and left: RcpMgr_ctor's 0xB0000B70 DMA (the rspboot ucode, never parsed on the
port), fs_piReadWord (SRAM / host-io words written and read by the same shim), Backup_read (SRAM
the port writes itself). **Still open:** TrickTable_readEntry (tricks.bin, layout not decoded),
ImageFile texels (agent-a's byte-order work).

**Next:** run the title demo again (the chase camera's distance, the anims and the timer HUD
all changed); fold the DWARF ABI scan into a gate step (it needs a linked port build).

### 18.18 Run 839: the port gate (agent-e)

agent-e run 839, branch agent-e on main bc3b36ee2: f42944519 (src, PORT only), 2e7ceb2a3 (tool);
monorepo d3e4726 (gate-landing-tree.sh, not pushed).

**`LAND_WT=<wt> scripts/port-gate.sh [--regen] [--update-baselines]`** (1080 repo). Needs the
matching build in the tree. ~85 s; one line per step; exit = number of failed steps; logs in
`$PORT_GATE_TMP` (default `$TMPDIR/port-gate-<wt>`). Times on this machine:

| step | s | checks |
|---|---|---|
| gen-map | 10 | port-sourcemap.py + port-gen-build.py reproduce the committed sourcemap*.tsv / port/gen |
| build | 9 | fresh `-DPORT_LINK=ON` i386 build: 0 compile errors, 0 undefined symbols, no gated warning beyond `port/tools/port-gate-warnings.tsv` |
| gen-lib | 17 | port-gen-decls / binds / uso (from the built game objects, as agent-g's regen.sh) + port-gen-blob-types.py reproduce port/gen |
| test_ultra, test_fs | 0 | |
| gfx | 21 | `make -C port/gfx test`: 19 golden scenes (llvmpipe) + test_dlump |
| audio | 18 | `make -C port/audio regress` (53 cases) |
| smoke | 1 | `tenshoe --frames 2000` from a clean dir: rc 0, 2000 trace lines, no NaN / Inf in r<N>= |
| abi | 4 | `port/tools/abi-scan.py` (18.17's DWARF scan) vs `port/tools/abi-baseline.tsv` |

- The generators write in place: the gate snapshots port/gen + sourcemap*.tsv and restores them
  (default), or keeps them and rebuilds (`--regen`; commit the result as tool output).
- Gated warning classes (the build adds `-Wreturn-type -Wimplicit-function-declaration
  -Wimplicit-int`, no codegen change): -Wreturn-type, implicit declarations / int, int <-> pointer
  casts, incompatible pointer / int conversion, builtin-declaration-mismatch, C++ -fpermissive.
  Key = file, function, class, message (no line numbers), with a count: a new key or a higher
  count fails. Baseline today: 308 keys / 498 warnings (230 -fpermissive, 57 return-type,
  19 implicit declarations, 2 int-to-pointer).
- ABI baseline: 104 accepted findings (P 62 int / float same-size pairs, SRET 4 = 28C0_rotate x3
  and SnowAI_aimWeave, SRETPOP 4, UNPROTO 34). A new one fails; a fixed one is reported.
- `gate-landing-tree.sh` runs it last (after the clean-checkout build), on by default,
  `PORT_GATE=0` skips it, exit 11.
- **test_ultra's argument is an SRAM image it WRITES (32 KB)**. Run 839 passed it the ROM path
  once and truncated the shared projects/1080-decomp/baserom.z64 (restored within ~1 minute from
  the sha1-checked tenshoe.z64, 79cd1166). The gate passes a scratch file.

**Results on main (bc3b36ee2) + f42944519:** all PASS except **audio: course0 / course1** hashes
differ from regress-golden.tsv (BE17F822 / 4DBB67AF vs EF99C528 / 991FD7AE). Same at c63d1fe2a,
the commit that wrote the golden list, so the golden came from a pre-rebase tree: agent-c to
re-check and `make regress-update` if intended. Until then landings need `PORT_GATE=0` or fail
with exit 11.

**Found and fixed (f42944519):**
- Run 836 broke the boot: tenshoe died at frame ~231, `sys_fatal: Out of DMA slots`. Bisected to
  79cdd106c. AnimData_readFrames' streamed path ends in a bare `return;` in an int function: the
  ROM returns fs_gdlReadFileAsync's slot in v0, AnimFrameCache keeps it as `pending` for
  AnimData_waitFrames. With the PORT_BE_SWAP16S after the read, eax was garbage, so no slot was
  ever waited. PORT returns the slot. 2000 frames now run (rc 0).
- mgr_initMatchRace_00000700 (C++ NCC donor) had no return statement: g++ -O2 emitted no `ret`
  (it falls into `.cold`). PORT `return 0`.
- port/undefined.txt is not gated: `cmake --target undefined` on a PORT_LINK tree rewrites it
  (178 -> 72 symbols, libc now listed). It is a report, not a generator input.

**Open (not gated):** the camera target goes NaN at frame 1619 (`cam=` fields 3-5 = 0xffc00000
from a camera cut, the eye jumps). Before run 836 it went NaN at 2380 and SIGSEGV'd at 2625: likely
the same bug as agent-g's crash. The smoke line prints the count. The 47 C "control reaches end
of non-void" and 3 bare `return;` warnings in the baseline are the same class as the
AnimData_readFrames bug when a caller uses the value: worth one audit pass.

### 18.19 Run 842: missing returns (agent-e)

agent-e run 842, branch agent-e on main bcf38948a: 17de0dfa3 (tool), 23ceb93ea (src, PORT only).

**The class.** A ROM function that ends without `return` still returns `$v0`: in the matched C,
usually the last callee's result. On i386, eax is whatever is left there (often the same value by
luck, since gcc keeps the last call's eax through a pop-only epilogue, but not after any later
arithmetic: AnimData_readFrames, 18.18). In C++, g++ treats the fall-off as unreachable and may
emit no `ret` (mgr_initMatchRace, 18.18).

**Census (fresh `-DPORT_LINK=ON` build, `-Wreturn-type`):**

| class | hits | outcome |
|---|---|---|
| C "control reaches end of non-void" | 47 | 29 in dropped copies (the shipped body is a C++ / o0 donor); 18 shipped |
| C bare `return;` in a non-void function | 2 | input_getStickX/Y: dead (after `return x;`) |
| K&R implicit int ("return type defaults to int") | 8 | each paired with its fall-off line; 2 in dropped copies |
| C++ (`-Wreturn-type`, 241 units) | 0 | after 18.18's mgr_initMatchRace |
| void definition, int caller declaration, caller reads eax (abi-scan VRET, new) | 5 | all real; fixed |
| function ending in a call gcc assumes never returns (objdump: last insn not ret / jmp) | 9 | all port-side (host_fatal, port_sys_fatal, sys_fatal -> port_sys_fatal); all genuinely exit |

Of the 18 shipped fall-offs, $v0 from the matching objects: **2 used, fixed** (AudioHeap_AllocPermanent:
the allocation, read by AsyncLoadInner / SyncLoad; SelectWin_callPrevStageBit_0000894C: prevStageBit's
result, tested by 3 state handlers). The other 16 are reviewed in `port/tools/return-type-allow.tsv`:
VOIDLEFT 8 ($v0 is a void callee's leftover, so the original was void), UNUSED 3 (AudioLoad_SyncLoadInstrument,
SyncInitSeqPlayerInternal ($v0 = 16), AnimPlayer_reset), DEAD 5 (not linked: dbg_printThreads,
nodelist_display/updateFlagged, func_00000000; and the 2 bare returns).

**VRET fixes (callee defined void, caller uses eax):** AudioLoad_SyncLoadSeq (SyncLoad's RAM address,
stored by InitSeqPlayerInternal as the sequence data), pad_getFlagGlobal (pad flags, pad_isConnected),
gfx_childName_00056084 (str_dup'd name, gfx_newDLChild), gfx_newPolyShape_00046F80 and
SnowBoarder_createBoardShape_0000B49C (the new PolyShape; shape_cmdShape, BoardList_createItem).
New ROM-neutral macros in include/uso_call.h: `PORT_V0_RET` ("return" / nothing) and
`PORT_V0_TYPE(t)` ("t" / "void"). name-placeholder-calls.py's header parser skips PORT_V0_TYPE.

**Gate (port-gate.sh build step):** return-type hits are no longer baselined (57 keys removed from
port-gate-warnings.tsv). A hit in a shipped body fails unless `return-type-allow.tsv` lists it (file,
function, message prefix, verdict, evidence); hits in dropped copies (sourcemap ships the function from
another unit) are exempt. The line reads `return-type: 55 hits (24 reviewed, 31 dropped copies,
0 UNREVIEWED)`. A removed allow line was checked to fail. abi-scan's VRET class is gated through
abi-baseline.tsv (0 findings now).

**Not covered:** `return voidfn();` in a non-void caller (11 sites, e.g. snd_PostEvent,
dbg_printStarLine, math_acosf's sys_fatal arm). These pass on the same leftover $v0 the ROM had, so
they are VOIDLEFT by construction. Also not covered: an indirect caller (vtable / proc entry) that
reads a value; the verdicts above checked the dispatch type by hand.

### 18.20 Run 841: Parms tags, the course camera's NaN, the 3D demo renders (agent-g)

(Asked for as 18.18; 18.18 / 18.19 were taken by agent-e.) agent-g run 841, branch agent-g on main
cd860366b: **a0bac7a1d** (game_libs, PORT only). Gate PASS (ROM byte-identical, 3579/3579, verify-blocks
6/6, check --order 0 wrong, jumptable-audit 0 WRONG, clean build OK, port gate PASS: smoke 2000 frames, ABI 0 new).

**Frames.** `tenshoe --frames 10000` from a clean dir: rc 0 (about 5 s), 22061 RCP tasks, no NaN / Inf
in any rider or camera trace field (before: camTarget NaN in frames 1619-1982, 3757-4590, 6243-6604,
7026-9313). Flow (procState, nextFlowMode, flowMode): 0..197 0,0,0 (N64 logo); 198 1,0,0 (fade);
221 0,1,0; 222 0,1,1 (title + attract demo 1); 2533 4,1,1 (demo end); 2546 0,1,1 (next demo);
6994 4,1,1; 7006 0,1,1. Name entry (nameent.uso) is never loaded in 10000 frames, so its cfront
conversion is still not on the path.

**What the frame-2565 crash and the frame-231 stop were** (both fixed on main by others while this run
was on them): AnimData_readFrames returned garbage instead of its DMA slot (43694bcff, agent-e), and the
audio channel commands 0xB2 / 0xB5 read big-endian sequence halfwords natively (755392718): seq 26
(started at the demo's end) ran a swapped offset (pc 0x9E09) as a channel script.

**The camera NaN (a0bac7a1d).** `fs_gdlReadInt_00035AA4` (Parms_load / Parms_skipRecords: the record
TAG) read the tag word unswapped, but each parm registers its tag as a host-order word taken from the
blob (Parms_addParm; "fin\0" = 0x66696E00 on the host, 0x006E6966 from the file). No tag ever matched,
so **every Parms object in the game kept its ctor defaults** (this affects every parms file, not only the
camera). The course camera's chase parms (cam_ca.bin: mxz, txz, cxz, miy, toy, ty2, chy) stayed 0, and
SnowChaseActorCam_applyMode (game_uso_ncc_24BC.cpp) computes `vel / cxz`: the eye went -inf on the
CourseCam's first update, and NaN spread to the look-at body through SnowChaseActorLook_update. The
title demo shows that camera (view 19, path 10) from frame 1619. The fix swaps the tag under PORT; the
-1 end sentinel is order-free. Found with stderr prints in cam_updateView / the chase updates (gdb under
run32 loses the symbol file once the program starts; addr2line on the trap backtrace still works).

**Projection.** In a demo 3D task now (dump gfx_001031) the G_MTX 0x01030040 matrix (gfx_emitProjection,
guMtxF2L of the float matrix at gfx D+0x60) is a proper view x perspective: x scale 1.809, y scale
2.414 (ratio 0.75 = 4:3, cot(fov / 2) = 2.414, fov 45), the w column the unit view forward
(-0.037, 0.549, -0.835), translation (-155, -12179, -9262, -9228), in range. The -32768 / -12.8 / 1.7
matrix agent-a saw was built from the NaN / inf camera.

**Renders.** The 3D view is the ODD gfx task of each frame (the even one is the title overlay: logo,
"Press START"), so capture with an odd `-f` and an even `-e` (or `-e 1`). With
`port/tools/capture.sh -b <build> -n 5000 -f 601 -e 400`: /tmp/claude-1000/agent-g/cap841c/sheet.png;
the course (snow, trees, the lake, mountains, sky) and the red rider with its snow spray render, e.g.
png/t004201.png, t003001.png, t005801.png, t000601.png. Per-task run: /tmp/claude-1000/agent-g/cap841b/sheet.png.

**Next lead: spike polygons.** Large dark / red triangles cross most views. In gfx_004201 every course
G_VTX chunk (140 of them, contiguous at 0x0888CC70..) has vertices 1 and 2 replaced by the same 32 bytes
(`00000000 6e720e08 5055a708 ffffff00 / 07000800 5055a708 00000000 ffffff00`: v1 = (0, 0, 29294), alpha
0), and the first TRI1 of each chunk uses them. The vertex data is not a plain ROM copy (the v0 bytes are
not in the ROM aligned), so it is built at load / run time: find the writer of chunk+0x10..0x2F (a
watchpoint on 0x0888CC80, or a print in the course mesh builder).

### 18.21 Run 847: spike polygons, course rows, the board's NaN matrices (agent-g)

agent-g run 847, branch agent-g on main 5ad5a6743: 51400992a, b59d1ccf5, 6064c6faa. Each gated (ROM
byte-identical, 3579/3579, verify-blocks 6/6, check --order 0 wrong, clean build OK, port gate PASS).
Three game-side root causes; after them the attract
demos render the course (slope, fences, cliffs, houses, lake, sky) and the full rider (body, jacket,
board, shadow, reflection) with no NaN model matrix in 10000 frames (before: 2-3 per frame in 10 of
48 sampled 3D tasks).

**1. Spike polygons: Vtx locals assumed contiguous (51400992a).** PolyShape_shade_00049DBC (NCC donor)
builds a face's three Vtx in the separate locals sp50 / sp60 / sp70 and passes `&sp50` to
PolyShape_addFace / gfx_findFaceVtxs, which index v[0..2]. IDO lays the three out back to back; the
host compiler does not, so v[1] / v[2] were read from unrelated stack (a stale gfx_texImageBytes frame:
`0x0808b57e` is its return address into gfx_texelBytes, `0x08a0b530` the BaseMat it pushed). Every course
G_VTX batch therefore carried the same two junk vertices ((0, 0, -19074), alpha 0) and its first
triangle became a spike. PolyShape_makeEdgeVtxs (sp48 / sp58 to gfx_findFaceVtxs) had the same shape.
Under PORT both now declare one array and name its elements with macros.

**2. Course rows dropped: an alias token pinned at 0 (b59d1ccf5).** port-gen-binds' load_pins read only
numeric `tok = 0x...;` lines of undefined_syms_auto.txt, so `bu_63b4_c57c = snd_soundObjCreate_0000057C;`
(MapProp_display's RoData base, 0x57C in the matching link) got pin 0 and aliases.ld bound it to
`port_bootup_rodata+0x0`. Its degrees-per-radian constant (RoData+0x5B0) was then read from +0x34
(0.0f): angle / 0 = inf, fcos(inf) = 0 (the |x| >= 2^28 "give up" path), the row-window vector went
inf / NaN and clipRowLo / clipRowHi came out 127 / 7 (empty), so PolyShape_clipRows dropped nearly every
course row: the black areas and missing slope. Alias tokens now take their value from build/tenshoe.elf
(the only such line today); aliases.ld regenerated (one line). Found by printing MapProp_display's A / B
/ fn (they were inf / NaN) and then fcos's argument (inf).

**3. NaN board matrices: AnimPose written across two locals (6064c6faa).** anim_blendPose (NCC donor game_libs_ncc_62A2C.cpp) calls
`anim_unpackKey(o, key1, &p.v)`, which writes a whole 0x28-byte AnimPose: trans and scale land in
`Pair p` (0x18), the quaternion in `q[4]`, which IDO places right after p. On the host q was elsewhere,
so key1's quaternion was stack garbage and math_quatSlerp(&x.quat, q, frac) produced a huge y: board_a's
local matrix had -inf on its diagonal and ±1e31 off it (translation still sane), its child DefMNodes went
NaN, and MNode_display (mtxMode 6, the shadow / mirror pass) emitted G_MTX all -32768: the orange /
red / dark slabs across the view (the board, its shadow and its reflection). Under PORT p and q are one
struct. Found with a NaN check in gfx_loadMatrix / gfx_multMatrix (return address -> MNode_display),
then node names (board_a under "top", DefMNode under board_a / chest_jnt_2), then the local matrices.

**Bug class.** 1 and 3 are the same hazard: IDO-era code passing the address of one local to a callee
that reads or writes past it into the next declared local(s). It survives every byte-match check (IDO's
layout is the matching one) and abi-scan cannot see it. Grep for it when a donor passes `&local` of a
struct-sized object to a function taking an array or a bigger struct.

**Frames** (`port/tools/capture.sh -b <build> -n 10000 -f 601 -e 400`), in /tmp/claude-1000/agent-g/r847/frames:
before_spikes_t004201.png / after_spikes_t004201.png (fix 1), before_rows_sheet.png /
after_rows_before_anim_sheet.png (fix 2), before_anim_t002601.png / after_anim_t002601.png (fix 3),
after_all_sheet.png (all three; 54 tasks to step ~10000).

**Still open.**
- Black regions remain in a few camera fly-ins (tasks 1001 / 10201: steps 612 / 5212, demo starts). Not
  row clipping (forcing rows 0..127 changes nothing), not culling (cull bits cleared changes nothing); a
  software transform of the dump finds no triangle covering those pixels, even clipped. So the game emits
  no geometry there: either the camera looks past the course strip (backdrop missing / not loaded) or a
  camera-path / LOD bug. Next: the course's backdrop shapes and the fly-in camera path.
- Demo 3 (from step ~7006) is a split-screen race: each half is its own gfx task, so a per-task replay
  shows the other half black (replayer / capture behaviour, not the game; agent-a: carry the framebuffer
  between the two tasks of a frame, or composite odd + even tasks).
- Task 2601: arch-shaped rock / tree-textured course geometry in the sky over the lake; course shape,
  identity model matrix. Unverified whether it is legit cliff geometry seen from a rolled camera.

### 18.22 Run 849: one tag convention; whole-frame capture (agent-a)

agent-a run 849, branch agent-a on main 1d727331e: dbb00bc2d (revert of 5ad5a6743), 473c59edd (tag typing,
was d999a0486), f903ce883 (km/h), 0dad08891 (crash backtraces, input scripts), b8f22f98c
(port_uso_importData), 9d2a948e2 (f3dreplay --then, capture.sh -M). Run 846's b9f38d8f7 was dropped: agent-c's
1d727331e covers it (nameent / viewrec cfront, the boot-word checks).

**Tag convention: cartridge byte order everywhere.** A 4-char tag stays as its bytes: blob words typed `str`
(port-gen-blob-types step 4c, source `tag`, 330 words), and the readers do not swap (fs_gdlReadInt_00035AA4,
ItemMgr_Load). 5ad5a6743 (swap the Parms reader, blob tags host-order ints) is reverted; the two together cancel.
Evidence (title demo, TAGLOG prints in Parms_load / ItemMgr_Load, not committed):
- host-order convention: ItemMgr 31 misses, among them hel / hem / tv1 with an ENABLED descriptor (the descriptor's
  tag word was never typed u32, so it stayed cartridge order while the file tag was swapped): the heli items never
  load. And EnvSettings (a third reader: COURSE_OP_SUN registers sun / len / lt0 / lt1 with map_addEntry, then
  Node_Load of the env file) never matches: the Sun / LensFlare Parms (rot ele scl mat col / fin dlv dfm) load 0
  times in 2500 frames.
- cartridge convention: every ItemMgr miss is flag-gated (chk 2, gtr / gtl 1, sn3 0x400 vs mode 0x13C), as the ROM
  behaves; Parms 0 misses; the Sun / LensFlare / colour parms load.
- an unrecognised tag word defaults to unswapped (= file order); the host-order convention needs every tag word
  recognised as an int, and 2-char tags like "tv\0\0" (bootup Data 0x7E40) are typed str.
- the game prints tags as strings: "Parm '%s' ignored", "Dup parm '%s'", "Loading ItemType '%s'", "ItemType not
  found '%s'".
- no code immediate is a tag: no lui / ori pair in any built object forms 3 letters + NUL (only 'KMC\0' in
  osInitialize and a gfx combine word).

**Verified (merged tree):** time_attack.input: course names follow the cursor (Crystal Lake -> Crystal Peak), the
stat bars are coloured, km/h shows (117 / 37 km/h: the >= 100 arm prints). match_race.input reaches Select Level /
Rider / Board; options_tour.input reaches Options / Records and back to the title. Title demo: 3D on every sampled
step, 0 NaN / Inf in cam / rider fields.

**FIXED in run 852 (18.24: an sret pop mismatch in SnowAI_finishRun). Was OPEN, blocker for the title demo: SIGSEGV at step 2511** (end of attract demo 1, flow 4,1,1) on the merged tree
only: origin/main runs 10000 frames, and this convention before agent-c's c16a6b2e1 / 1d727331e ran 10000 frames.
eip = ecx = 0x089CE840, a HEAP address (inside sArena): a call / return into a data pointer. sp[0] = 0x0067696C
("lig\0", the snow-lights ItemType tag). The rider trace diverges from main's at step 225 (r0 velocity). Not the
item types (skipping hel / hem / bal / ba2 / tv1 / sn3 / sun / len in ItemMgr_Load still crashes) and not the Sun /
LensFlare parms (skipping rot..col / fin dlv dfm in Parms_load still crashes). Registers / stack came from a SA_SIGINFO
LD_PRELOAD handler (/tmp/claude-1000/agent-a/r849/segv/segv.c, built with tools/i386-sysroot/gcc32 -shared; it
also stubs signal() so main's handler doesn't replace it; the ELFCLASS32 warnings are from the 64-bit timeout).
The live stack is not a usable chain (Node_update / App_Update words are stale); a check in Node_update's slot-3
call (game_libs_ncc_38728.cpp) for a target past etext printed nothing, so it is another indirect call. Next: find the function that jumps to the heap pointer, then which object's vtable / callback
it read (the env lights lt0 / lt1 now load: check their consumers first).

**Whole frames (9d2a948e2).** `f3dreplay in.dlmp out.png --then in2.dlmp ...` runs one frame list that calls each
task's root in turn, so the colour / depth images carry across a frame's tasks. Each dump's lists are widened from
its own words (the game patches 23 shared DL bytes between the split-screen halves); other data is mapped once
(0 differing bytes at steps 1700..9900). `capture.sh -M` renders each step as one image (png/fNNNNNN_sSTEP.png).
Demo 3's split screen now renders whole with the 1080 logo overlay; the title demos show the overlay over the 3D.
Golden tests: 19 scenes match. Sheet: /tmp/claude-1000/agent-a/r849/cap_whole/sheet.png.

### 18.23 Run 851: EnvSettings tags, the charmap import, the six courses (agent-g)

(Asked for as 18.22; agent-a's run 849 took it.)

**Conflict with 18.22 (agent-a, the cartridge-order tag convention).** afcc46f50 follows the convention
on main today (a0bac7a1d: tag readers swap, blob tag words typed u32 = host-order ints). agent-a's
473c59edd reverts that (blob tags typed `str`, readers unswapped). Whichever lands second must drop the
other's reader change: under the cartridge convention stream_readS32_00005EF8 must NOT swap (drop
afcc46f50's hunk and 7e6ec91c7's comment); the EnvSettings tags then match because 0x7EE8 is `str`.
Either way the observable result is the same (sun / len / lt0 / lt1 load). On this branch (main +
the three commits) the title demo runs 10000 frames rc 0 with the env records loading, so 18.22's
SIGSEGV at step 2511 is not caused by the lights loading by itself.

agent-g run 851, branch agent-g on main 1d727331e: **afcc46f50** (bootup, PORT only), **504a89e79**
(genproc, PORT only), 7e6ec91c7 (port.h comment). Each gated (ROM byte-identical, 3579/3579, clean build OK, port gate PASS).
Frames in /tmp/claude-1000/agent-g/r851/frames.

**Fly-in black regions (tasks 1001 / 10201) and the arch over the lake (task 2601): gone, no change
needed.** Both were the camera under the course: in run 847's build the demo rider fell through the
ground (y 231775 -> 219884 between steps 500 and 600 there, the camera following), and agent-c's
gTriEdgeNext fix (c16a6b2e1) keeps it on the slope. With the same sampling as 18.21
(`-n 11000 -f 601 -e 400`, demos_now_sheet.png) every 3D task renders the course; steps 612 and 5212
show the slope and fences.

**1. EnvSettings record tags (afcc46f50).** stream_readS32_00005EF8 (EnvSettings_load's tag) read the
word unswapped, but game_createMap registers the handlers with `*(int *)&sStr_sun_7EE8` / len / lt0 /
lt1 from bootup Data 0x7EE8, a u32 blob block, i.e. host-order values. No tag matched, so every
course skipped its sun, lens-flare and both light records (the size word let the skip stay in sync,
so nothing crashed). Sun_readParms never ran (rot / ele 0: the sun at (0, 0, 16e6), on the +z
horizon), the flare kept its ctor elements, and lt0 / lt1 (lt1 is the shadow light,
gfx_setShadowLight) kept ctor defaults: the projected rider shadow fell along the default light as
long slabs beside the rider. After: Crystal Lake's records are sun 76 / len 404 / lt0 28 / lt1 28
bytes, each handler consumes exactly its size; Sun rot -36.72, ele -2.88, mat 8; the shadows sit
under the rider (before_env / after_env_race_sheet.png, *_t005177_s2700.png). port.h's comment on the tag
readers now says they swap (7e6ec91c7, comment only).

**2. charmap import while charmap.uso is not loaded (504a89e79).** Second launch with a save after a
race (here: steer1.input from an existing 1080.sram) died at step 572 with `sys_fatal: Invalid Shape
cmd 64853`, in CourseList_createItem (genproc 0xD884) <- SelItemsMgr_ctor <- GenSelectChar_ctor <-
app_launchGenProc, mode 3 (Match Race: the saved language skips the language menu, so A at 560
picks Match Race). app_launchGenProc loads charmap.uso (the course-map shapes) only when the mode is
not 3 or 5, but CourseList_createItem's arms 0 / 1 run when mode != 2 and use the genproc import
from charmap (Sym 347 etc., value 0 in the file). On the N64 that import is unresolved, so the shape
pointer is 0 and BasePolyShape_ctor skips the parse; the port bound it statically to
port_charmap_data + 0x1B4 (an unloaded, zeroed blob) and parsed garbage. Under PORT the 16 charmap
sites of CourseList_createItem and its sibling (timproc_uso_b5_DF14.c) now pass 0 while charmap.uso
is not loaded (port_uso_isLoaded). After: Match Race with that save runs (level, rider, Round 1
Crystal Lake, race to step 3000; after_charmap_matchrace_with_save.png). General point: a static
XDATA / alias bind to a module that can be absent is the port's version of an unresolved import;
other genproc imports (charfir 8 sites at 0x92D0.., charsps 0xDB28..) are guarded by the same mode
tests as their loads.

**Race frames** (`capture.sh -i steer1.input -F ...`, Crystal Lake, after both fixes):
- textures: snow detail, trees, rock faces, fences, houses, the balloons and the lake reflection
  (mountains mirrored) render; nothing missing found.
- fog: the course FogParms are min 996 / max 1000 (G_MW_FOG 0x7D00 / 0x8400), colour b7e0ff,
  alpha 0, loaded from the file (gfx_loadQuadIntInt, the reads swap): fog only at the far plane.
  The trees' TreeTmpl fog is 993..997, 0.17 grey, alpha 1. No game-side fog bug seen.
- sun / lens flare: the sun now has its parms but is never drawn in headless captures: in tenshoe
  without Fast3D nothing writes the depth image, so Sun_measureVisibility reads 0xFFFF (not the
  0xFFFC "far") at all 9 samples, count 0, visibility 0, fade < 0.1 and Sun_display returns. f3dreplay
  does serve the requested pixels (`fb depth: 9 far` in many race tasks) but cannot feed them back.
  **For agent-a:** a headless model of the depth clear (the G_FILLRECT of 0xFFFC on the Z image) or
  replay-to-game feedback is needed before the flare can show in captures.
- particles: snow spray (white dots behind the board) and the board trail render.
- shadow: the projected silhouette now has the lt1 direction (compact, under the rider). Its colour
  is G_SETPRIMCOLOR 0x00000070 after the fix (0x6C6C6C70 before, from default light values): black,
  alpha 0.44, drawn with the static DL at 0x0880EC90 (G_CC_PRIMITIVE, G_RM_AA_OPA_SURF 0x00442048,
  1-cycle, no Z), so the alpha is not used and the shadow is opaque black. That is what the display
  list says; whether the hardware shows it darker / lighter is a renderer question.
- far mountains: textured and banded only by their own texture at 3x (after_env_big3900.png); no
  game-side cause found.

**Courses** (time_attack-style inputs with N x DR; Mountain Village / Dragon Cave / Deadly Fall with
a save whose options unlocks = 0x00FF, seqStep = 5 (SRAM 0x1F8 / 0x7FC8, sums at 0x210 / 0x7FE0
adjusted): /tmp/claude-1000/agent-g/r851/unlock.sram). Each loads, races and renders to step 2800:
Crystal Lake, Crystal Peak, Golden Forest (sunset cliffs), Mountain Village, Dragon Cave (night,
moon), Deadly Fall, and Trick Attack's Half Pipe (to "Goal! New Record") and Air Make. No crash.
Sheets: courses_lake_peak_forest.png, courses_village_dragon_deadly.png, courses_halfpipe_airmake.png.
(Straight-stick inputs leave the rider against walls on Mountain Village / Dragon Cave; not a bug.)

**Still open.**
- Attract demo 1: from step ~1400 the demo rider runs into the rock wall left of the lake run and
  stays there at speed 4-13 until the demo ends (2533), every loop (6100.., 10500..; speed 155 at
  1300, 95 at 1400, 12 at 1500). The demo is not an input replay (pad_startPlay is never called in
  the first 400 frames of the attract loop), so the rider is CPU-driven: look at the CPU rider's
  path / course markers or a collision difference (the class of c16a6b2e1).
- The speed readout shows 0 or a garbage value (122870...) in races (agent-c's speedometer).
- Sun / flare in captures: see above (agent-a).

### 18.24 Run 852: the step-2511 crash was an sret pop mismatch; the convention lands (agent-a)

Branch agent-a = origin/main d83578d2f + the cartridge tag convention (473c59edd, dbb00bc2d cherry-picked)
+ two commits: the fix (30a053172) and the regenerated race script (2c9339811).

**Root cause of the SIGSEGV at step 2511 (closes the 18.22 OPEN item).** Not an item type or a Parms group:
the newly-loaded objects only change the physics, and with them the title demo's CPU rider (SnowAI) now
reaches the finish at step 2511, so SnowAI_update dispatches aiState 1 -> SnowAI_finishRun for the first
time. SnowAI_finishRun (game_uso_ncc_6A30.cpp) and SnowAI_recoverStuck (game_uso_ncc_71E0.cpp) declared
`PORT_SRET_NOPOP Vec3 SnowAI_aimAlongSegment(...)` (caller pops the hidden pointer), but the shipped
definition is the cfe donor game_uso_7C1C.c, a C function returning Vec3 by value, which ends `ret $4`.
Every call left esp one word high; the epilogue popped ebx / esi / edi one slot off and `ret` took the
next word: the function's own argument, the SnowAI object (eip = ecx = 0x089CE840, sp[0] = "lig\0" was
just the word above). Fix: drop PORT_SRET_NOPOP on those two declarations (empty in the ROM build).
How it was found: the 32-bit SA_SIGINFO handler (/tmp/claude-1000/agent-a/r852/segv/segv.c) printing
sp[-24..] showed the popped ebx / esi / edi at sp[-4..-2] and 0x089CE840 at sp[-1] (a `ret` one slot
high, not a call); dumping the object at eip gave its cfront vtable (slot 3 = SnowAI_update, aiState 1).
- Rule: PORT_SRET_NOPOP belongs only where the C side spells the sret as an explicit out-pointer
  (definition ends in a plain `ret`). Checked the other users: cam_toTargetLocal_000023D4 and
  SnowAI_aimWeave end in a plain `ret` (correct). abi-scan's SRETPOP rows list `def_pops=1` for these
  callers but cannot see the caller-side attribute; a check that reads the caller's post-call esp
  adjustment would have caught it (not done).
- Note for 18.23's "attract demo 1 rider stuck on the rock wall": on this tree (cartridge convention)
  the demo rider rides through (speed 0x43xxxxxx = 130..230 at steps 1300..2500) and finishes at 2511;
  the trace is identical to before the fix up to the crash, so the convention, not the fix, changed it.
  SnowAI_recoverStuck had the same drift: with the fix a stuck CPU rider's recovery reads its locals
  correctly.

**Verified on the merged tree (port build /tmp/claude-1000/agent-a/r852/pb):** title demo 10000 frames rc 0,
0 NaN / Inf (rider and camera). time_attack (race state 1 at the end), match_race, options_tour,
trick_attack, vs2p, title_idle: rc 0, 0 NaN.

**Race script regenerated** (port/tools/steer-search.py, 310 runs, 133 s): the race now starts at 1433;
Goal! at step 5121 (race time 3661 steps, about 2'00": not a top-3 time, so the script has no name
entry). race-check: goal / replay (3689 steps bit-identical) / ghost (reload bit-identical) PASS.
race_crystal_lake_ghost.input (menus only) unchanged.

**EnvSettings under this convention:** stream_readS32_00005EF8 reads the tag word unswapped (file
order) and EnvSettings_load compares it with the handler ids from the str-typed blob keys (cartridge
order): no swap needed there (agent-g's afcc46f50 is the host-order counterpart; drop it with this).

**Still open:** the grey name-entry board (needs a top-3 finish to reproduce; the new script is not
one: a faster steer line or a synthetic SRAM with slow records would reach it); sun visibility in
headless runs (no depth image: Sun_measureVisibility reads 0xFFFF).

### 18.25 Run 854: why the attract-demo rider rammed the wall; the CPU rider on every demo (agent-g)

(Asked for as 18.24; agent-a's run 852 took it.) agent-g run 854, branch agent-g on agent-a's run-852 tip
2c9339811 (the cartridge tag convention + the SnowAI sret-pop fix), one commit on top (the gate check
below). afcc46f50 (run 851's EnvSettings swap) is not on this branch: dropped, as 18.24 says.

**Root cause of 18.23's wall-ram: the CPU rider never steered.** SnowAI_steer returned at
`if (helper_ptr == 0) return;` on every frame, so SnowAI_applyStickInput never ran and the rider just
slid straight down the fall line into the rock wall left of the lake run. helper_ptr comes from
SnowAI_updateMarker -> SnowAI_findNearestMarker_0000A374 -> ItemMgr_findType_0003EA98 with the key
`*(int *)kMarkerTypeTags_548[targetNode]`, a 4-char string ("mrk", "mk1".."mk9", "mkl", "mkr") read as a word.
That string is str-typed in the blob (cartridge byte order: key 0x006b726d on the host), while on main
d83578d2f (host-order convention, a0bac7a1d) the course's 12 marker ItemTypes registered host-order tags
(0x6d726b00, 0x6d6b3100, ...). findType never matched. Printed per call (temporary AIDBG prints in
SnowAI_steer / A374 / findType, not committed): before, `tag=006b726d r=0` and the type list in host order;
on agent-a's tree, the types are cartridge order and `r` is the "mrk" ItemType from frame 1.
**So the fix is agent-a's convention (991d86f1c / bf1474d6a), no SnowAI change needed.** This is a third
tag reader class besides Parms / ItemMgr_Load / EnvSettings: game code that builds an ItemType key from a
Data string. Under the cartridge convention every such key and every registered tag are file-order bytes.

**AI correctness after the convention (checked by eye from per-frame prints of targetNode / altNode /
modeFlags / aimMode / marker flags / aim vector / yaw / unk3C / out flags):** the target marker advances
along the course, fork branches switch targetNode (tn 0 -> 3 / 8 / 5 / 1 / 2 / 11), out flags 1 / 4 / 8 /
0x20 / 0x40 / 0x80 fire, the pickFork / scanNodes paths run (mf 1 17x, mf 2 2x), no NaN / Inf in any AI
value, the finish marker (flg 0x400) triggers SnowAI_enterFinish. aimMode 1 (weave) never runs in the
demos or Match Race: weaveLead is RoData 0xF8 = -100000 (only far behind a rival), ROM behaviour.
ItemMgr_findType misses over 30000 title frames: only ItemMgr_Load's flag-gated types (gtr gtl chk hem
hel sn3 cfr tv1), as 18.22 says.

**30000-frame title-demo loop (agent-a's tree), rc 0:** 14 demo passes, every rider gets down its
course; no 120-step window with the rider moving < 1500 units. Max e0 pct per pass: demo 1 (Crystal
Lake) 100 (the goal at ~2511) on the first pass, 94-95 on later ones (the demo timer ends first); the
split-screen Crystal Lake race 90-94; the second course (start y 302726) 72-76 when its timer ends.
The 2-rider demos keep both riders moving (r0 / r1).

**Match Race AI opponent** (agent-c's /tmp/claude-1000/agent-c/r853/in/mr2.input menus + STICK 0,60 to
step 9000; the shipped match_race.input stops in the select menus on this tree): the CPU rider (r1)
reaches the finish marker at step ~4100 (rival lead -231453: the straight-stick human retired at 33 %),
then stops in SnowAI_finishRun; round 2 (7250..) starts and the CPU rider again rides at 170-233.

**Gate guard (6f00cae7d; landing gate + port gate PASS on it: 3579/3579, ROM byte-identical, race step PASS):** port-gate.sh smoke now also requires the attract demo's CPU rider to reach
60 % (trace e0 pct) when the run has >= 2000 frames: 74 % at 2000 with steering, ~35 % against the wall
without it.

**Still open:** match_race.input's menu steps on the current tree (agent-c run 853).

## 19. M2: graphics transport (agent-a, run 820)

> agent-a run 820, 2026-11-17, on branch agent-a: 7c91a2e27 (dumper, hook, tests, reader), e6bda5949
> (replayer) and 2b576cd84 (a comment fix). The gate passed before the commits. Code: `port/gfx/`.

### 19.1 Feasibility on this machine (WSL2 Ubuntu 22.04, no sudo)

What the machine has, measured:
- **64-bit runtime:** libGL / libGLX / libEGL (glvnd) and Mesa 23.2.1 DRI, including `d3d12_dri.so` (the
  GPU through WSLg, here an AMD Radeon) and llvmpipe. WSLg is up (`DISPLAY=:0`, `WAYLAND_DISPLAY`).
- **64-bit dev:** no GL / EGL / SDL2 headers, no SDL2 at all, no OSMesa, no zlib or libpng headers.
  `apt-get download` + `dpkg -x` works without root. `port/gfx/replay/setup-gl-dev.sh` fetches
  `libegl-dev libgl-dev libglx-dev libopengl-dev` (137 kB) into `tools/gl-dev/`.
- **A headless 64-bit GL context works:** EGL on `EGL_PLATFORM_SURFACELESS_MESA` with a pbuffer gives
  "D3D12 (AMD Radeon) / GL 4.2 compat", and with `LIBGL_ALWAYS_SOFTWARE=1` it gives
  "llvmpipe / GL 4.5 compat". No window or X is needed.
- **32-bit:** nothing. The i386 sysroot (13.5) is built from Ubuntu's amd64 `lib32*` multilib packages, and
  there are no `lib32` GL / SDL packages. True `:i386` packages need an i386 apt index, and that index
  can be built without root: a private `sources.list` with `[arch=i386]` plus `-o Dir::State::Lists=`,
  `Dir::Cache=`, `APT::Architectures::=i386` and `Dir::State::status=/dev/null`. `apt-get update`
  into that scratch state worked here (20 MB of indexes).
  - `libosmesa6` + `libsdl2-2.0-0` alone close over **66 i386 packages** (llvm15, X11 / wayland, pulse,
    and so on).
  - In 32-bit Mesa can only use llvmpipe. WSL ships `libd3d12.so` / `libdxcore.so` 64-bit only, so a
    32-bit process gets no GPU.
  - libultraship's C++20 dependency set (SDL2, spdlog, ImGui, nlohmann-json, tinyxml2, ...) would also
    have to be built `-m32` against that tree. Section 14.2 found it is not even installed for 64-bit.

**Verdict: (b) on this machine, and as the M2 test harness everywhere.** The game (32-bit) serialises each
gfx task to a DLMP dump, and a separate 64-bit renderer replays it to PNG.
- It needs no 32-bit GL and gets the real GPU through d3d12, or llvmpipe for deterministic screenshots.
- It gives headless golden-image tests that need neither the game nor a ROM: a dump is the test input.
- It decouples renderer work (Fast3D and the 14.1 patches) from the boot work: a renderer can be developed
  on dumps while the game still traps.
- It is proven end to end here (19.4).

(a), the in-process 32-bit Fast3D, stays the **shipping** configuration on machines that have multilib GL
(any normal distro or Windows), and M6 (64-bit) removes the problem for good. It is feasible here only
as a software-rendered 66-plus-package i386 sysroot plus an i386 build of LUS's dependencies, which is a
multi-session job for no capability that (b) lacks. The renderer is written once against the dump's
memory image (19.3), so the same code later links in process.

(c) Considered and parked: a live (b), meaning a shared-memory frame channel to a persistent 64-bit
presenter. It would make the game interactive on this machine. Read-backs (14.1 patch 3) would come back
over the same channel with one frame of latency, which is the semantics the game already has (11.2). Do
this only if interactive play on WSL is wanted before M6.

### 19.2 PORT_GFX_DUMP and the DLMP format (`port/gfx/dlump.h`)

**Hook.** `port_gfx_task(OSTask_t *)` in `port/gfx/port_gfx.c` is the strong definition of main.c's weak
hook. The call path is osSpTaskStartGo -> `PortUltraConfig.rcpTask` -> `rcp_task` -> `port_gfx_task`.
**No port/ultra or src/ change.** CMake adds `gfx/port_gfx.c gfx/dlump.c` to the host sources. The link
still fails only on the same 13 data symbols, with no new undefined or multiply defined symbols.

Environment:
- `PORT_GFX_DUMP=<dir>` writes `<dir>/gfx_NNNNNN.dlmp`, where NNNNNN is the gfx task number since boot.
- `PORT_GFX_DUMP_FIRST=n`, `PORT_GFX_DUMP_EVERY=n` and `PORT_GFX_DUMP_COUNT=n` select which tasks are dumped.

**File layout.** All integers are in the writer's host order; the header carries a byte-order mark.
- A 64-byte header: magic `1080DLMP`, version 1, BOM `0x01020304`, ptrSize, seq, rootAddr (data_ptr),
  rootSize, chunkCount, cmdCount, errorCount, flags (TRUNCATED, SEGMENTS) and dataBytes.
- Then the chunks, each `{kind, addr, size, aux}` plus its data padded to 4, and finally an END chunk.

| kind | data | aux |
|---|---|---|
| TASK | the 0x40-byte OSTask_t | task type |
| DL | list words. Adjacent runs are coalesced; the walk stops at G_ENDDL / branch, so dead tails are not copied | depth at first visit |
| VTX | F3DEX 1 G_VTX source, `(w0 & 0x3FF) + 1` bytes | vertex count |
| MTX | G_MTX source (0x40) | params byte |
| MOVEMEM | viewport / lookat / light block (`w0 & 0xFFFF`) | index byte |
| TEXTURE | LOADBLOCK / LOADTILE source bytes (sub-rectangle rows for LOADTILE) | the G_SETTIMG w0 in force |
| TLUT | LOADTLUT source | the G_SETTIMG w0 in force |
| IMAGE | none: a G_SETCIMG / G_SETZIMG target address (the frame buffers are not copied) | the command's w0 |
| ERROR | NUL-terminated text | (addr = the command's address) |

Rules:
- **Bytes are copied raw.** List words, Vtx, Mtx, Vp and lights are in host order as the port's game
  code wrote them. Texels stay in the N64 big-endian image that Fast3D's importers read. Nothing is
  rewritten, so a replayer interprets the original words at their original addresses.
- **Walk.** The writer follows the RSP: G_DL push / branch, a 10-deep stack, G_ENDDL, and
  G_MOVEWORD SEGMENT.
  - Shared sub-lists are **re-walked** on every call, because what a load list fetches depends on the
    caller's G_SETTIMG. The synthetic test covers this.
  - Data ranges are deduplicated on (kind, addr, size).
  - Limits: 4M commands, 8 MB per range.
- **Segments.** A host pointer's top byte is not a segment number, and 1080 only ever sets segment 0 = 0
  (11.1). So a segment is applied only when its base was set **nonzero** in the task; otherwise w1 is
  the pointer. The replayer uses the same rule.
- **Safety.** On Linux every range is checked with `mincore()` first. A bad pointer becomes an ERROR
  chunk and a `port_ultra_log` line, not a crash. The tests cover this.
- `DlumpOptions.arenaBase` (game address -> `arenaBase + addr`) lets the same writer run on a 64-bit
  host. It is the 4 GB-arena idea of 11.5 item 7.

**Reader.** `port/gfx/tools/dlump.py` has three modes:
- `FILE...`: a summary plus a command histogram, with any opcode outside the 39-opcode census of 11.1
  flagged.
- `--check`: an independent Python re-walk from the dump's own memory image. It fails if any referenced
  range is missing, unless the dump's own ERROR chunks explain the gap.
- `--list`: the walked command stream, indented by call depth.
- `--total DIR/*.dlmp` gives one histogram over a capture. This is the M2 confirmation of 11.4 once the
  game reaches the title.

### 19.3 Tests and the replayer

- `make -C port/gfx test` (64-bit) and `make -C port/gfx test M32=1` (gcc32 / run32) both **pass**.
  - `test_dlump` builds a synthetic 1080-style frame (`synth.c`): RSP init words, a colour clear and a
    Z clear (CIMG pointed at the Z buffer), a viewport, two G_MTX, one shared texture list called with
    two textures, a CI TLUT, G_VTX / G_TRI1, and a NOPUSH branch. It checks every chunk, the command
    count (42, with the dead ENDDL after the branch not walked), a bad root and a self-calling G_DL
    (stack overflow after 11 commands).
  - On -m32, `test_port_gfx` sends the frame at its real addresses through `port_gfx_task` with the env
    variables set. Tasks 1, 3 and 5 are dumped; task 5 has an unmapped root, which `mincore` refuses.
  - `dlump.py --check` validates the outputs. A corrupted dump (a VTX chunk retagged) is caught.
- **`port/gfx/replay/dlreplay`** (64-bit; `make -C port/gfx replay-test`):
  - It maps the chunks into a sparse memory image and interprets a **bring-up subset**: G_MTX
    load / mul / push, G_POPMTX, G_VTX, G_TRI1, the G_MOVEMEM viewport, ZBUFFER / cull geometry modes,
    FILL-mode colour and Z clears, and Gouraud vertex colours.
  - It renders through EGL surfaceless + a pbuffer and writes a PNG with a built-in stored-deflate
    writer (no zlib).
  - It is not the M2 renderer. Textures, the combiner, lighting, fog, blending and TEXRECT are Fast3D's
    job.

### 19.4 Render proof

The synthetic frame renders correctly with both D3D12 and llvmpipe: two Gouraud triangles (RGB plus white)
on the fill-cleared background, at the viewport-mapped screen positions (v0 (-120, -90) -> pixel (40, 210)).
The dump written by the **-m32** test binary renders **byte-identical** (`cmp` on the PNGs, llvmpipe) to
the 64-bit one. The 32-bit game -> DLMP -> 64-bit GL -> PNG path is closed.

### 19.5 Next (M2)

1. **Fast3D behind the dump.** Build libultraship's `src/fast/` (pinned, plus the 14.1 patches) as a
   64-bit library in the replayer.
   - Feed it a **converted** list: copy each DL chunk into a 16-byte `F3DGfx {uintptr_t w0, w1}` array,
     and rewrite pointer operands (G_DL, G_VTX, G_MTX, G_MOVEMEM, G_SETTIMG; the dumper's rules say
     which) to host pointers into the chunk copies.
   - Patch 3's read-back needs a return path. In the dump world it is "write a .rb file next to the PNG".
   - The dependencies still have to be fetched the 19.1 way (64-bit is enough): SDL2-dev, spdlog, ImGui
     and tinyxml2, or Fast3D isolated from the Ship context as SoH's code-built lists do.
2. **Golden tests.** Check in a few synthetic DLMPs, built from generator code (synth.c-style), not from
   ROM data. Render them on llvmpipe and compare against stored PNG hashes.
3. **The first real capture** as soon as agent-g's boot reaches the first gfx task:
   - `PORT_GFX_DUMP=... PORT_GFX_DUMP_COUNT=300`, then `dlump.py --total` against the 11.1 census;
   - answer the 11.4 questions statically: G_LINE3D users, U64BGWall's vertex count per G_VTX, and
     whether Mat_fromFrameBuffer is ever reached.
   - Note: per 11.2 item 4, G_SETCIMG / G_SETZIMG carry `addr & 0xFFFFFF` until the gfx_setColorImage
     PORT edit lands. The dumper only records them as IMAGE references, so this does not affect a dump.
4. **Dump cost.** The dumper is unmeasured on a real frame. Hash sets keep it linear. If whole-run
   dumping is too slow, use `PORT_GFX_DUMP_EVERY`.

### 19.6 Run 824: libultraship's Fast3D in the replayer, golden tests (agent-a)

> agent-a run 824, 2026-11-17, branch agent-a: bb0a2c56d (LUS patch 0005 + docs) and 41311fe73 (f3dreplay,
> golden tests). The gate passed before each commit. Code: `port/gfx/fast3d/`, `port/gfx/gold.c`,
> `port/gfx/golden/`.

**Build.** `port/gfx/fast3d/setup-lus.sh` fetches LUS at the pin and prism-processor (the GLSL template
preprocessor of the OpenGL backend, at the commit LUS pins; **MIT**, which closes 14.3 item 8 for it) into
`<monorepo>/tools/lus/`, and applies the patch series. There is no submodule yet; that stays the plan for the
in-process build (`port/third_party/README.md`).
- Only four LUS sources are compiled: `interpreter.cpp`, `backends/gfx_opengl.cpp`, `debug/GfxDebugger.cpp` and
  `resource/type/Texture.cpp`. They build against `fast3d/shim/` (headers named like the Ship / spdlog / ImGui /
  SDL3 ones they include) and `ship_shim.cpp`.
- The resource manager serves only the shader template (`shaders/opengl/default.shader.glsl` from LUS's
  `src/fast`); every OTR lookup misses. Console variables read `LUS_CVAR_<name>` from the environment.
- Host g++ 11.4 `-std=c++20`, the `tools/gl-dev` headers, libEGL / libGL.

**Feeding Fast3D (the conversion choice).** The dump is rebuilt **at its original addresses**: every chunk
goes into anonymous pages mapped `MAP_FIXED_NOREPLACE` at the same 32-bit address. A PIE 64-bit process
leaves the low 4 GB empty, so this works both for the synthetic arena (0x00200000) and for a real `-m32`
dump (0xF7xxxxxx: `test_port_gfx`'s dump renders). Every pointer operand (G_VTX, G_MTX, G_MOVEMEM,
G_SETTIMG, CIMG / ZIMG) is then a valid host pointer as it is.
- Only the lists change. Each DL chunk is widened to 16-byte `F3DGfx {uintptr_t w0, w1}`, and each G_DL operand
  (call or branch) is pointed at the widened target. Rewriting every pointer operand into the chunk copies
  would have needed a per-opcode table; this way only one opcode is rewritten.
- This is 11.5 item 7's 4 GB arena with base 0. The same idea serves the in-process M6 build.

**Fast3D gaps found (embedding and coverage):**
1. **Low addresses are dropped (fixed by patch 0005).** `gfx_set_timg_handler_rdp` ignores a G_SETTIMG at or
   below 0x0FFFFFFF unless `dladdr` finds it in a loaded module. That hit every texture and TLUT load in the
   replayer. It would also hit the in-process 32-bit game, whose brk heap follows the non-PIE executable at
   0x08xxxxxx. Patch 0005 adds `gfx_register_raw_address_range(start, size)`. The port must register its
   heap / arena; f3dreplay registers its mappings.
2. **`Interpreter::Init` resets the ucode to F3DEX2.** Call `gfx_set_target_ucode(ucode_f3dex_line3d)` after
   Init (and again after any re-init).
3. **No GUI means no view.** `ViewportMatchesRendererResolution()` compares against `mGameWindowViewport`,
   which only Fast3dGui (ImGui) sets. Left at 0x0, Fast3D draws into an offscreen game framebuffer, then
   clears the window at the end of `Run()`, so the frame comes out black. A port without the LUS GUI (the
   replayer, and possibly the shipping port) must set `mGameWindowViewport` to the window each frame.
4. **mask = 0 clamps.** LUS clamps texture coordinates past the tile when masks / maskt are 0. Real hardware
   reads on through TMEM. 1080's loads set masks wherever they wrap, so this is cosmetic. The golden
   `tex_rgba16` scene wraps with mask 4, which renders correctly.
5. **Checked, no gap:**
   - 1-cycle translucency in 1080's cycle-1-only render words (`XLU_SURF` 0x404240, a ZB_XLU form): it
     blends correctly, so the 11.4 / 14.3 item 6 worry about `use_alpha` does not apply to these words.
   - G_LINE3D (patch 1) draws both widths.
   - 2-cycle fog with `G_MW_FOG` and the 2-cycle `lerp(T0, T1, PRIM_A) * SHADE` multi-texture both work.
   - COPY and 1-cycle TEXRECT (the F3DEX 1 E4 / B4 / B3 triple) and partial scissors work.
6. **Not exercised yet:**
   - lighting (NUMLIGHT, lights movemem) and texgen / lookat;
   - LoadTile sub-rectangles;
   - G_SETPRIMDEPTH sprites;
   - CULL_FRONT;
   - the per-window partial Z clear;
   - the 14.1 read-back API (patch 3).

   These are the next scenes to add.

**Golden tests.** `gold.c` builds 11 scenes from generator code, in the GBI 1 forms of 11.1 (no ROM data):
`fill`, `shade`, `tex_rgba16`, `tex_ci` (CI4 / CI8 + TLUT), `tex_ia_i` (IA8 through XLU, I4), `combine`,
`multitex`, `fog`, `texrect`, `xlu` and `line3d`.
- Each scene goes through the real dumper (`dlump_task`) and is checked with `dlump.py --check`.
- Each is rendered by f3dreplay on llvmpipe and compared by PNG sha1 with `port/gfx/golden/golden.sha1`. Its
  header names the reference renderer (llvmpipe, LLVM 15.0.7, Mesa 23.2.1).
- `make -C port/gfx test` runs them on the 64-bit host and says SKIP when tools/lus or the GL headers are missing.
  `make -C port/gfx golden-update` rewrites the hashes; look at the PNGs in `<OUT>/golden-out/` first.
- The renders were checked by eye before the hashes were taken. Three consecutive runs gave identical hashes.

**Real frames: not yet.** The port build of this branch (main 89e0b3bd3 + these commits; `cmake -S port`
with `PORT_LINK=ON`, `run32 tenshoe --rom ... --frames 300` with `PORT_GFX_DUMP`) segfaults after the
second "video mode 320x240" line, before the first gfx task, so no capture exists. This matches agent-g's
run 822 crash in RcpMgr_queueTask on frame 1. Once the boot gets past it, the capture is
`PORT_GFX_DUMP=<dir> PORT_GFX_DUMP_COUNT=300`, then `dlump.py --total <dir>/*.dlmp`, then
`f3dreplay <dir>/gfx_000001.dlmp out.png`.

**Next.**
1. More scenes for the item 6 features.
2. A read-back round trip: f3dreplay writes the patch-3 colour / depth answers next to the PNG.
3. The first real capture as soon as the boot reaches a gfx task.
4. In process: the same f3dreplay core (arena registration, the widened lists, the viewport) behind
   `port_gfx_task` once the port links LUS (a). For M6 the widening goes away.

### 19.7 Run 828: more golden scenes, patches 0006-0008, in-process Fast3D (agent-a)

> agent-a run 828, 2026-11-17, branch agent-a: b73edb472 (scenes, read-back, patches 0006-0008) and 4754c3e68
> (in-process Fast3D). The gate passed before each commit (ROM byte-identical, 3579/3579 exact).

**Seven new scenes** (`port/gfx/gold.c`, 18 in all; the 11 run-824 hashes are unchanged), each copied from a named
emitter's command forms:

| scene | emitter | what it covers |
|---|---|---|
| `light` | gfx_emitLights_000454C4, gfx_emitOneLight_00045CB0 (as Mat_draw calls it) | G_LIGHTING; gSPLight per lit element (index 0x86 + 2i), then the ambient at 0x86 + 2n and the F3D NUMLIGHT word `(n + 1) * 32 + 0x80000000`; the one-light form (NUMLIGHT first, then L1 = record + 8, L0 = record, so light 0's direction bytes are the colour) |
| `texgen` | Mat_draw (LOOKATX = the LookAt, LOOKATY = + 0x10), gfx_setupMatTextures_00045E20 | B7 TEXTURE_GEN (0x40000) and + LINEAR (0xC0000), G_TEXTURE `BB040801` with scale 1984 / 1984 and 3968 / 1984 (64-wide); a second LookAt with no NUMLIGHT after it |
| `loadtile` | gfx_loadTexture_000578B4 (TexImage arms s1_110 / s1_304, plain arms s2_120 / s2_110) | LoadTile of a sub-rectangle at uls / ult != 0 (RGBA16; I4 loaded as I8 at half width), LoadBlock with dxt = (words + 0x7FF) / words (RGBA32, a 24-wide RGBA16 whose dxt is inexact) |
| `sprite` | Sprite_ctor's StartDL / EndDL, Sprite_display | 1-cycle, G_ZS_PRIM (`B9000201 4`), bilerp, persp off; per billboard G_SETPRIMDEPTH + a 1-cycle TEXRECT; AA_ZB_TEX_EDGE 0x443078 against a Z quad |
| `cull` | the mirror pass; U64BGWall_ctor | CULL_FRONT; G_CULLDL(0, 3) (`BE000000 6`) in G_DL sub-lists, one on screen, one off |
| `splitz` | gfx_clearScreen per window, ScreenWindow_display's Vp | two windows: scissor, partial Z clear + colour clear, per-window viewport; then a full-screen quad behind both |
| `fader` | Fader_display (bootup_uso_ncc_1304C.cpp), verbatim | 2-cycle, T0 colour / T1 (I8 mask at TMEM 0x100) alpha, XLU both cycles, bilerp, RGB dither off (`BA000602 0xC0`), TEXTLOD tile, full-screen TEXRECT |

Not covered because 1080 never emits them (11.1): G_BRANCH_Z, TT_IA16, mip-mapping. FILL / COPY / 1- / 2-cycle,
TT_RGBA16 and both filters were already in the 19.6 set.

**Read-back (patch 3) in every scene.** `f3dreplay --readback out.rb` requests the whole 320x240 frame as
big-endian RGBA5551 and the depth at a 16 x 12 grid before `Run()`. The pixels must equal the frame, each channel
being the 8-bit value >> 3, with row 0 at the top: they do, in all 18 scenes. The `.rb` files are hashed with the
PNGs in `golden.sha1`. In `splitz` the near quads read 0x4084, the mid quad 0x8000 and cleared pixels 0xFFFC.

**Fast3D gaps found and fixed (patch series now 8; README rows 6-8):**
- **0006, texgen LookAt (real game impact: every reflection material).** The F3D `G_MOVEMEM` handler stored
  LOOKATY (0x82) in `lookat[0]`, which drives S, and LOOKATX in `lookat[1]`. The env maps came out transposed:
  measured on `texgen`, red (S) followed the normal's y. Also, a new LookAt only reached the coefficients at the
  next `G_MW_NUMLIGHT`. Mat_draw re-emits the LookAt every frame without one, so the maps would have frozen on the
  previous LookAt. The patch maps X to `lookat[0]` and sets `lights_changed`.
- **0007, G_SETPRIMDEPTH flush (every billboard sprite).** The prim depth is a per-draw uniform set in `Flush()`.
  Consecutive prim-depth TEXRECTs batched into one draw at the last depth, so a far sprite followed by a near
  one was drawn over the geometry in front of it. The patch flushes on a depth change.
- **0008, depth read-back orientation (Sun_measureVisibility).** With no game framebuffer (no LUS GUI: f3dreplay
  and the in-process port) the window's rows run bottom-up, and `GetPixelDepth` read the mirrored row. The patch
  flips y when `!mRendersToFb`. Colour read-back was already right.
- Checked with no gap: both light paths, CULL_FRONT, G_CULLDL (an LUS stub that draws everything, which is
  correct), LoadTile sub-rectangles including I4-as-I8, LoadBlock dxt, the per-window Z clears, the Fader list
  and the 0x443078 texture-edge cut-out.

**In process, option (a)** (`port/gfx/fast3d/port_fast3d.{h,cpp}`, CMake `-DPORT_GFX_FAST3D=ON`, default OFF):
`port_gfx_task` calls `port_fast3d_task(data_ptr)` after the optional dump. The three 19.6 embedding gaps are
handled there:
1. Before each task, every writable mapping below 0x10000000 in `/proc/self/maps` that is not registered yet is
   registered with patch 0005. That covers the brk heap, USO images and anonymous mmaps. sysapi.c's arena is in
   `.bss`, which a module owns anyway. 1080 uses no segments, so no segmented address can pass.
2. The ucode is set after Init.
3. `mGameWindowViewport` is the whole window every frame.

Lists:
- **32-bit game:** the root goes over in place.
- **64-bit:** every reachable list is widened per task. They are re-widened each frame because PolyShape_clipRows
  edits lists in place.

Other pieces:
- `port_fast3d_invalidate` wraps patch 0004 for the CPU texture writers (11.2).
- The window is the EGL pbuffer. A desktop build swaps in LUS's SDL window.
- `PORT_GFX_PNG=<dir>` writes one PNG per task.

**Test:**
- `fast3d/test_inproc` rebuilds each DLMP at its own addresses and calls `port_fast3d_task`.
- `golden.sh` runs all 18 scenes in one process through one interpreter, invalidating the texture cache
  between dumps because the scenes reuse arena addresses. It requires f3dreplay's PNG byte for byte: **all 18
  identical**.
- Without the invalidation, `sprite` came out wrong (stale texels). This is the 11.2 texture-cache case, and it
  shows that patch 0004 works.

**Build status:**
- **64-bit:** `cmake -S port -DPORT_GFX_FAST3D=ON -DPORT_FAST3D_FLAGS=""` builds `libport_fast3d.a` and the hooked
  `porthost` (port_gfx.o references `port_fast3d_task`). The Makefile path (`make -C port/gfx test`) also links
  and runs it.
- **32-bit (-m32, the real game): not possible on this machine.** The library stops at the first libstdc++
  header (`bits/c++config.h`; there is no i386 libstdc++ or libc dev), and 19.1 found no i386 EGL / GL to link.
  On a machine with multilib g++ and i386 GL, configure with `-DPORT_GFX_FAST3D=ON -DPORT_LINK=ON`.
- Option (b) stays the default here.

**Real frames: still none.** origin/main has nothing past agent-g's run-822 frame-1 RcpMgr_queueTask crash. When
the boot reaches a gfx task, the capture recipe is in 19.6. On a multilib machine,
`PORT_GFX_FAST3D=ON PORT_GFX_PNG=<dir>` gives the frames directly.

**Next.**
1. Real captures, through both paths (needs agent-g's boot).
2. An SDL window backend behind the same `port_fast3d` API for a desktop multilib build.
3. Port the patch-3 / 4 callers (ScreenThumbMat_grab, Fader_buildTexture, Tv1Tmpl, Sun_measureVisibility,
   gfx_flushTexture) to `port_fast3d_invalidate` and the read-back. These are game-side PORT edits, outside
   agent-a's area.


### 19.8 Run 832: the first real frames, capture.sh, patch 0009 (agent-a)

> agent-a run 832, 2026-11-17, branch agent-a: 62c088f25 (dump directory, capture tool) and a249d6f9b (LUS
> patch 0009). The gate passed before each commit (ROM byte-identical, 3579/3579 exact).

**Capture in one command.** `port/tools/capture.sh -b <PORT_LINK build> -o <out> [-n frames] [-e every] [-f first]
[-S render scale]` runs `run32 tenshoe --frames N` in `<out>` (a fresh `1080.sram`) with `PORT_GFX_DUMP`, renders
every dump with f3dreplay (built into `<out>/gfx` unless `-x` names one; llvmpipe), and writes `sheet.png` (a
contact sheet labelled with gfx task numbers, `port/tools/contact_sheet.py`, stdlib only), `histogram.txt`
(`dlump.py --total`), `run.log` (with the exit code; a crash still processes the frames before it) and
`replay.log`. On main + this branch, 300 frames take about 20 s: tenshoe dumps all 223 tasks in 0.5 s (251 MB),
then crashes at task 222 (agent-g's title-demo bug); f3dreplay takes about 60 ms per frame.
- `PORT_GFX_DUMP=<dir>` now creates the directory (mkdir -p).
- `fast3d/Makefile` tracks header dependencies (-MMD). Before this, a patch that changed `interpreter.h` left
  stale objects with the old class layout, and f3dreplay crashed.

**What the 223 frames show** (each gfx task is one frame):

| tasks | content | verdict |
|---|---|---|
| 0-1 | N64 logo; the start-up Fader dissolve finishing | dark-green specks (the Fader bug below) |
| 2-83 | N64 logo, static, full alpha (81 identical frames) | correct |
| 84-98 | logo fades out, PRIM alpha -16 per frame | correct |
| 99-130 | Lamar / Tommy Hilfiger trademark screen fades in, PRIM alpha +8 per frame | correct |
| 131-197 | trademark screen, static | correct |
| 198-221 | Fader dissolve to the next process | **wrong: dark green instead of black** |

- **The N64 logo is 2D on hardware.** It is not a 3D model. The capture has no G_VTX or G_TRI1 at all: every
  frame is FILLRECT plus 1-cycle TEXRECTs, and that matches n64proc. N64DemoProcess_drawGui draws sprite 6
  (state 0) or sprite 3 (state 1) with `gui_drawSprite(.., 160, 120, 3)` at `gui_setColor(alpha)`.
  N64DemoProcess_handleInput gives the timing: 100 frames, the last 16 fading by 16; then +8 per frame from
  0 to 255 and a 100-frame hold, then `Process_fadeOut`. That matches the table frame for frame. The colours (the
  green / red / blue N with yellow tops, the grey "NINTENDO" with a white "64"), the Lamar disk's grey
  gradient, the navy / white / red Tommy flag and the text are all right at native resolution.
- The command census over the 223 frames has only 29 opcodes, all inside the 11.1 census. 4158 TEXRECTs come
  from 4132 LOADTILE + 52 LOADBLOCK. There is no G_LINE3D, lighting or triangle yet; the 11.4 questions wait
  for the title / race.

**Bug 1 (game side, for routing): the Fader colour texture is written in host byte order.**
Fader_buildTexture (`src/bootup_uso/bootup_uso_tail4.c`) fills `FADER(f)->texture[0..0x3FF]` (u16) with 1 when
`mode == 0`: RGBA5551 black, alpha 1. Fader_display then draws it as the T0 colour of a full-screen 2-cycle
TEXRECT (32x32 RGBA16 at 0x08852CA0, with an I8 dissolve mask in T1). On x86 the bytes are `01 00`, and Fast3D
reads texels big-endian, as the hardware's TMEM does, so it sees 0x0100: G = 4, which renders as dark green
(0, 33, 0). Evidence:
- every TEXTURE chunk at 0x08852CA0 in tasks 0-1 and 198-221 is 1024 x `01 00`;
- patching those bytes to `00 01` in tasks 199, 205 and 212 and replaying gives the expected dissolve to black.
Fix: under `#ifdef PORT`, store `0x0100` (or byte-swap the 0x800 bytes once after either loop, before the
patch-4 invalidate). The `mode != 0` path copies `pal[screenIdx[i]]` u16 to u16. That keeps the palette's byte
order, so it is right only if the window's slot-11 palette is big-endian; check it when that path first runs (it
is not reached in these 222 frames). The same applies to every CPU texture writer in the 14.1 list
(ScreenThumbMat_grab, Tv1Tmpl_blitFrame): their texels must end up big-endian.

**Bug 2 (Fast3D, fixed by patch 0009): seams in strip blits above native resolution.** The logo and the trademark
screen are drawn as 8-column LoadTile strips (`G_SETTILE ... masks 8`, a wrap mask of 256), each a 1:1 TEXRECT.
- At `--scale 3`, bilinear filtering blended each strip's last column with its first through GL_REPEAT: a grey
  line every 8 pixels, even on the black background.
- On the RDP a 1:1 rect from a whole texel samples texel corners, so it never blends.
- Patch 0009 clamps the sampler on any axis where a TEXRECT maps 1:1 from a whole texel and stays inside its
  texture. Scaled rects such as the Fader's stretched 32x32 keep the wrap: there the RDP really blends across it,
  and the `fader` golden scene caught the first, unconditional version.
- Results: native output is byte-identical (the 18 golden scenes, and all 223 real frames), and the seams are gone at
  scale 3.
- The patch applies cleanly after 0001-0008 on a fresh clone at the pin.
- Note: `tools/lus` is shared by all worktrees and now has 0009 applied, while its `.complete` stamp still names
  the 8-patch series. Native rendering is unchanged, so main's golden tests still pass against it. The first
  `setup-lus.sh` after 0009 lands refetches and re-applies.

**Fine at native resolution, nothing to do:** the fade arithmetic (PRIM alpha with `XLU_SURF` 0x404240 over the
fill-cleared black), the CI-free RGBA16 strips, and the I8 mask texture (bytes, no order issue). A mask
fragment shows near the logo in tasks 0-1 only because of bug 1.

**Next.**
1. Re-capture past task 221 once agent-g's title-demo fix lands: `capture.sh -n 900 -e 5`. That is the first
   3D (G_VTX / G_TRI1, lights, texgen) and the first CI textures.
2. Route bug 1 (bootup_uso_tail4.c is game code, outside agent-a's area).

### 19.9 Run 834: the byte order of RDP-visible memory (agent-a)

> agent-a run 834, 2026-11-17, branch agent-a on b23d0f38c: ef141b7a5 (PORT_RDP16 and the game sites),
> 14bf2b3c6 (splash blob typed as bytes), 04cf6f970 (golden scene `fader_cpu`), e7ce05725 (drops the RiderAnim
> duplicate of main's fix) and 60cd93a81 (f3dreplay seeds the Z address). The gate passed before the
> commits (ROM byte-identical, exact set unchanged, clean build OK).

**The convention (it was already in place; this writes it down).** Neither "(a) everything big-endian" nor
"(b) everything host order". The rule follows what libultraship's Fast3D reads, and the dumper (19.2), the blob
typing (18.1) and the golden scenes already follow it:

| memory | order | who reads it, and how | static copies (USO blobs) | CPU writers |
|---|---|---|---|---|
| display-list words | **host** | Fast3D: `w0` / `w1` as host u32 | typed u32 (`gfx`, `gfx:static`) | u32 stores (native) |
| Vtx | **host** | Fast3D: `Vtx_t` fields (s16 ob / flag / tc, u8 cn) | s16 x 6 + bytes (`gfx` G_VTX targets) | stores of each field's own width |
| Mtx (fixed point) | **host** | Fast3D `GfxSpMatrix`: 16 host s32 words, element j in the high half | u32 x 16 | guMtxF2L: whole words |
| Vp | **host** | Fast3D: `vscale` / `vtrans` s16 | (none static) | s16 stores |
| Lights / LookAt | bytes | Fast3D: u8 col / s8 dir | bytes | byte stores |
| texels, TLUTs | **N64 big-endian image** | Fast3D importers, byte by byte | bytes (`tex:*`, `mats`) | see below |
| colour / depth images | **N64 big-endian image** | the CPU readers (11.2); read-backs store big-endian (`bswap`) | bytes | see below |

So **RSP data is host order; RDP pixels are the N64 byte image.** For pixels:
- a copy u16 for u16 (or byte for byte) keeps the order and needs nothing (ScreenThumbMat_grab, Tv1Tmpl_blitFrame,
  the Fader's mode-1 remap, Mat_clone);
- a 16-bit pixel **value** that the CPU stores or compares goes through `PORT_RDP16(v)` (port/include/port.h:
  `bswap16`, the host u16 whose bytes are v's big-endian bytes);
- pixel data in a blob must stay typed bytes. A reader that loads it with `lhu` makes the access typing say u16,
  so such a blob needs a `known:` u8 entry.

**Sites fixed (all `#ifdef PORT`, ef141b7a5 / 14bf2b3c6):**
- **Fader_buildTexture** (bootup_uso_tail4.c): the mode-0 fill stores `PORT_RDP16(1)`. In the re-capture, tasks
  0-1 and 198-221 dissolve to black; frame 205 is the trademark half gone, 212 is black, and no frame is green.
- **gfx_drawFbChar_00046790** (game_libs_ncc_46790.cpp): glyph pixel `PORT_RDP16(0xFFFE)` (debug overlay).
- **Sun_measureVisibility** (match_imports): the depth test compares with `PORT_RDP16(0xFFFC)`, which is right once the
  depth read-back (11.2) stores big-endian. Today nothing writes the port's Z image, so the sun reads as hidden.
- **gfx_drawFbSplash_00048184**: its 128x128 image (bootup Data 0x22A30) was typed u16, `known:splash`, so it was
  swapped to host order. It is now u8; the copy is u16 for u16.
- **RiderAnim_init_0000D458**: this run found the same 0xF10 ROM-word check bug that agent-g fixed on main in
  3998bae47. e7ce05725 drops this branch's copy so the branch lands without a conflict.

**Audited and safe:**
- **Vtx:** gfx_makeVtx_00048104 (the only PolyShape / MorphPoly builder: s16 at 0-0xA, bytes at 0xC-0xF) and its
  colour feeders (PolyShape_shade, makeEdgeVtxs, gfx_copyBytes3 / floatToS8x3). Also Strip::add /
  PolyShape_addFace (whole 16-byte copies), MorphPoly_update / updateColours / applyUpdateList, U64BGWall_ctor and
  its static quad (bootup Data 0x65A8, typed u16), SnowRing_emit, BoardSpray_emit and LocalLight_buildLitVerts.
  No title, menu, font or HUD code builds Vtx: sprites and text are TEXRECTs.
- **Mtx:** every fixed-point Mtx comes from guMtxF2L (whole words): guMtxIdent, guOrtho, guPosition,
  gfx_emitProjection, PolyShape_display, Shadow_display and U64BGWall_display. MNode_doCommand copies whole words.
  No s16 store into an Mtx exists.
- **Vp:** dbg_screenOverlay and ScreenWindow_display (s16). **Lights:** gfx_emitLights / emitOneLight /
  setLightDirs / makeLookAt (bytes). gfx_calcHilite writes whole words.
- **Pixels:** the I8 Fader mask and the gui font scan are bytes; WhiteFader, NameEntry_clearScreen and
  gfx_clearScreen use FILL rects (DL words); dbg_fillFbRect stores 0xFFFF, which is the same in either order;
  gfx_clearFbRect stores 0. Tv1's state-1 noise reads u16 from bootup Data 0x0-0xFE, a shape blob typed u16, so the
  noise has different values but is still noise.
- Texel typing over every blob: all `tex:*` and `mats` texels are u8; no texel range is typed u16 / u32.

**Found, not fixed (routing): 40 donor functions are empty on the port.** `scripts/port-sourcemap.py`'s `expand()`
does not expand Makefile `$(foreach f,$(X_FUNCS),$(f)=$(X_DONOR))`. That is how 13 REPLACE_FUNC_BODY lines splice
the heli (2), nameent (4), trnproc (5) and snoweffects (29) donors. Those functions map to their empty host
placeholders, and the donors are never compiled. Among them are SnowRing_draw / setupDL / display, the
*_buildTexDL family, SnowFall_display / fill, SnowPool_display / update, BoardSpray_draw, the BoardTrail spawners
and Heli_update. **Snow, trails and the heli draw nothing on the port.**
- I tried a `foreach` expansion; a copy is at /tmp/claude-1000/a834/port-sourcemap.foreach.py. After
  `port-sourcemap.py && port-gen-decls.py <libgame.a> && port-gen-build.py`, three compile errors fall out (diff in
  /tmp/claude-1000/a834/donor-port-prep.diff):
  - the 4-byte tag structs `SKey` / `HeliTypeTag` passed where decls_cpp.h says int need an `operator int` under
    PORT;
  - SnowRing_setupDL needs a forward declaration.
- Then the link fails, because these donors have not had the port treatment: `D_00000000 + K` data sites (17.8
  uso-data-sites), cfront vtables (SnowMatB, SnowChild0/A/B, SnowBaseMatB) and `Node::Node(char *)`.
- That is a donor-porting task of its own (17.8 recipe), so I reverted it.

**Leads:** game_libs_ncc_4D468 / 4D688 `dma_read` 0x100 ROM bytes from 0xB70 into bootup Bss 0x3EB00. If a reader
compares words from that buffer, it has the RiderAnim bug.

**Race / title-demo frames (agent-g's lead), on main 3998bae47 plus this branch, captured with
`capture.sh -n 900 -e 1 -f 590`:**
- **Sampling.** `-e 50` sees only the 2D task: the gfx task count runs about 1.75 per step, so the race frames' 3D
  tasks fall between the samples. In `-e 1` from 590 there are about 490 3D tasks (1.32-1.37 MB, G_TRI1, G_CULLDL,
  lights, LOADTLUT) next to the 2D ones (180 KB, and 8.9 MB).
- **The 8.9 MB dumps are correct.** They hold 63 LOADTILE strips (4 texels x 155 rows) of a 240-wide RGBA32 image,
  and each strip's TEXTURE chunk covers its whole row span (147,856 bytes).
- **"5 lists widened" is not an error:** f3dreplay converts each DL chunk into F3DGfx (frame 0 has 5 too).
- **880-byte dumps:** only the colour image, scissor and empty lists; nothing is drawn.
- **White 3D frames: a replay artifact, fixed in f3dreplay (60cd93a81).**
  - 1080 clears Z with a FILLRECT (fill 0xFFFC) into a colour image set to the Z address 0x7BC140. It sends its
    G_SETZIMG later in the frame, so it relies on the Z address from the previous frame.
  - Fast3D treats a fill as a depth clear only when the colour image equals its Z address (interpreter.cpp 3174). A
    single-dump replay starts with that address unset, so the fill painted 0xFFFC as colour, RGBA5551 (255, 255, 248):
    the white screen. Cutting the list before any 3D still gave white.
  - f3dreplay now runs a prologue: the dump's first G_SETZIMG, then G_DL to the root.
  - The in-game interpreter keeps the Z address across frames, so only its first 3D frame would show this.
- **The 3D frames are now black (task 617)**, and the data looks byte-order-correct:
  - Vp is (640, 480, 511) x 2 in host s16;
  - lights are bytes (ambient 0x66, directional white along +z);
  - the modelview Mtx are clean rotations plus the camera translation (0, 10638.7, -6701.6);
  - texels are plausible big-endian RGBA16 / CI.
- **Suspect: the G_MTX projection (0x087E9140, PROJECTION | LOAD).** It decodes to
  `[[-12.83, 0, 0.153, 0.153], [0, 1.711, 0, 0], [0.196, 0, 10.03, 9.999], [1315, -18206, 32700, -32768]]`.
  - The -32768 is exactly the s15.16 minimum. On x86, guMtxF2L's float -> int conversion of an out-of-range value
    gives INT_MIN. MIPS gives 0x7FFFFFFF instead.
  - The x / y scales (-12.8 vs 1.7) and the sign of x look wrong for a 4:3 perspective.
  - So the float projection x view product is probably already wrong on the CPU side (camera / aspect /
    projection inputs: a game-side byte-order or float bug). **Route to agent-g** with gfx_emitProjection
    (game_libs_ncc_45178.cpp) as the place to dump the float matrix.
- **2D race frames (550-900, 1000+):** the white panels are RGBA32 images whose memory is 0xFF in every byte
  (0x089A5350 240x155 and 0x089A1E00 144-wide). This is not a renderer problem: the image's producer wrote 0xFF or
  nothing. The next step is to find who fills 0x089A5350 (probably a TexImage from gfx_loadTexture / ImageFile).

**Next.**
1. Port the 40 foreach donors (above); snow and trails are on the attract path.
2. Wire the 11.2 read-backs with `bswap` (big-endian), so the Fader mode-1 path, ScreenThumbMat, Tv1 and Sun see
   real pixels.
3. Re-capture past task 221 once agent-g's fix lands.

### 19.10 Run 838: the white panels (port/fs) and the framebuffer model (agent-a)

> agent-a run 838, 2026-11-17, branch agent-a on 853081eb5: 782c84181 (port/fs), 80ea2fd2b (port/gfx framebuffer
> model), 0d6ad6df8 (game `#ifdef PORT` hooks). The gate passed before the commits (ROM byte-identical, 3579/3579,
> named calls 0 wrong, jump tables OK, clean build OK); `make -C port/gfx test` (19 golden scenes, in process ==
> f3dreplay) and `test M32=1` pass; test_fs 107 / 0.

**The white panels were not a framebuffer reader. They came from port/fs (782c84181).** The 240x155 / 144x15 RGBA32
and 80x12 IA8 images are the title logo's gui sprites: ImageFile records (+0x20 w / h, +0x24 fmt, +0x28 data
offset, +0x2C size) read lazily by `ImageFile_acquire` from the ImageFileMgr's archive handle: `fs_setHandle`,
`fs_gdlSeekFile(0, dataOffset)`, `fs_gdlReadFile`. The game closes that handle after the directory pass and keeps
using it. On the N64 that works, because `fs_openFile` allocates a new struct and `fs_closeFile` is a no-op. The port
returned closed handles to a 64-slot pool, so the next open re-aimed the handle at another file. The seek (0xB99DEE)
then fell past the new window (limit 0x913F8E), `raw_read` returned 0 bytes, and the `mem_new` texels stayed 0xFF.
Handles are now never reused (static pool in order, then calloc). After the fix the title shows the "1080 TenEighty
SNOWBOARDING / (c) 1998 Nintendo / Press START" logo, full size and then small in the corner during the demo, with
"Press START" blinking (capture from task 590, `-e 1`).

**The framebuffer model (80ea2fd2b, `port/include/port_fb.h`).** The colour / depth image in game memory stays the
place the CPU reads and writes, in the N64 format (RGBA5551 / Z, big-endian per 19.9, 320 wide). The port keeps it
in step with the GPU on demand:

| hook (game side) | meaning | in process (`port_fast3d_task_fb`) | dump mode (option b) |
|---|---|---|---|
| `port_fb_read_color(img)` | the CPU reads this colour image this frame | patch 0003 read-back of the frame (320x240, `bswap`) queued before `Run()`; copied into `img` after it if the task's G_SETCIMG names it (low 24 bits); then the texture cache drops `img` | `DLUMP_FB_READ` chunk (no data); f3dreplay reads back, reports, `--fb-out` writes the image |
| `port_fb_read_depth(zimg, idx)` | the CPU reads Z pixel idx | `ReadbackRequestDepth` before / `ReadbackGetDepth` after; stored big-endian at `zimg[idx]` (0xFFFC = far) | `DLUMP_FB_DEPTH` (u32 indices); f3dreplay reports far / nearer |
| `port_fb_cpu_wrote(img, x, y, w, h)` | the CPU wrote a rectangle of a displayed image | **TODO**: composite over the window (logged once) | `DLUMP_FB_WRITE` (rect + pixels); f3dreplay composites it over the PNG |
| `port_fb_texture_written(addr, n)` | texels / palette rewritten by the CPU | `TextureCacheInvalidateRange` (patch 0004) | nothing (a dump renders from scratch) |

- Colour reads stay wanted for 4 tasks after the last request, which is one frame of latency, as on the N64: the
  readers read the buffer on screen. Depth reads and CPU writes are one-shot. They stay pending until a task whose
  G_SETCIMG / G_SETZIMG names their image has run: the 2D task between two 3D tasks does not consume the Sun's
  depth reads. The task's images come from the dump's IMAGE chunks, or from `mRdp` in process.
- **Game hooks (0d6ad6df8, all `#ifdef PORT`):** ScreenThumbMat_grab_0000E740, Fader_buildTexture (frame read only
  when `mode != 0`), Tv1Tmpl_stepPicture_00007D04 (both screens' texels invalidated after the blits) and
  Sun_measureVisibility are the readers. gfx_drawFbChar_00046790, gfx_clearFbRect_00043468, gfx_drawFbSplash_00048184
  and dbg_fillFbRect are the writers. Not hooked: GfxLib_hostioSendFbB (HostIO only) and Mat_fromFrameBuffer (no
  caller; 11.2).
- **What the capture needs** (`PORT_FB_LOG=1`, 5000 tasks: boot, title and attract demo): **0 colour reads, 0 CPU
  writes**, about 2 depth pixels per task, and 100 texture writes. The depth pixels are the Sun's 9 points, one Sun
  in the demo course. The texture writes are the Fader mode-0 fills. No ScreenThumb (board model 6 / 7), Tv1 or
  Fader mode-1 runs in this stretch. The in-process colour path is therefore exercised only by the unit tests
  (test_dlump's FB chunks, and f3dreplay on synth.dlmp: "fb read: drawn by this task, 42616 of 76800 pixels
  non-black"). In the real dumps (tasks 600-680), 21 3D tasks carry `FB_DEPTH`, and all 9 pixels are served each
  time (mixes of far and nearer while the 3D projection is still wrong, 19.9).

**Found, not mine:**
- `tenshoe --frames 3000` segfaults (no PORT TRAP line) on main's build without these changes too (run 834's build).
- `scripts/gate-landing-tree.sh` gates `projects/1080-agent-d` unless `LAND_WT` is set. `LAND_SCRATCH` must exist.
- The shared `projects/1080-decomp/baserom.z64` was rewritten (mtime 11:37) during one gate run, and the named-call
  check read a 32 KB file ("module not resolvable" for every file). The rerun passed.

**Next.**
1. In-process compositing of `port_fb_cpu_wrote` rectangles (a GL texture blit after `Run()`). Only debug paths and
   the uncalled splash write today.
2. In process, each task is its own StartFrame / Run / EndFrame. If the window is not preserved between the 3D and
   2D tasks of one frame, a colour read-back after the 2D task sees only the 2D layer. Check this when (a) first runs
   on a multilib machine.
3. Re-check the Sun's depth units (0xFFFC far) once agent-g's projection fix lands. Then capture a race with a
   CrystalGuy / MetalGuy rider (ScreenThumbMat) and a tv1 course item to exercise the colour path on real frames.

### 19.11 Run 856: the live presenter, option (c) of 19.1 (agent-g)

> agent-g run 856, 2026-11-17, branch agent-g. The game is now **playable in a window on this machine**: the
> 32-bit tenshoe runs as before, and a 64-bit presenter renders its gfx tasks live through Fast3D and sends
> the keyboard back. Command (from the game repo; needs an X display, WSLg gives `DISPLAY=:0`):
> ```
> port/tools/play.sh                       # builds what it needs on first use, then plays
> port/tools/play.sh -b <built port tree>  # an existing PORT_LINK=ON build (with this change)
> ```

**Architecture.**
```
 tenshoe (i386, PORT_LIVE=<name>, --realtime)            presenter (x86-64, X11 + EGL, LUS Fast3D)
   port_gfx_task -> build_task (= the PORT_GFX_DUMP          creates /dev/shm/<name> (live_shm.h)
     DLMP image, same bytes) -> port_live_task          ->   ring: 3 slots x 48 MB, one slot = one step
   main.c step end -> port_gfx_step_end -> publish           newest frame: chunks copied to their own
     (ring full: drop the frame, never wait)                 32-bit addresses (persistent 1 MB blocks),
   host_read_pads <- pads[4] in the header           <-      lists widened, tasks composited (--then),
   host_poll_events <- quit flag                     <-      Run, eglSwapBuffers; X keys / js0 -> pad 1
```
- **Transport:** `/dev/shm/<name>`, header + a single-producer / single-consumer ring (`port/gfx/live_shm.h`,
  4-byte fields only, the same layout in both ABIs). The game appends each task's DLMP image to the step's
  frame and publishes it at the step end (`port_gfx_step_end`, a weak hook in main.c's `step()`), labelled
  with the step of its first task (= steps.txt; SysLib.frameCount has already advanced at the step end). A
  full ring drops the frame, so the game keeps real time; the presenter renders only the newest frame when
  it falls behind.
- **Presenter** (`port/gfx/fast3d/presenter.cpp`, `make -C port/gfx/fast3d presenter`): f3dreplay's model kept
  alive. Data chunks are copied to their own addresses in a persistent arena (1 MB blocks mapped on first use,
  MAP_FIXED_NOREPLACE, registered for patch 0005). Fast3D's texture cache is keyed by address, so a TEXTURE /
  TLUT chunk whose bytes differ from the arena's invalidates [addr - 32 KB, end) (patch 0004) before the copy.
  The lists are widened per task each frame, the step's tasks are called from one frame list (f3dreplay
  `--then`) behind the SETZIMG prologue (19.9). Window: Xlib + EGL on the X display (`setup-x11-dev.sh`
  fetches the Xlib headers; libX11.so.6 is on stock WSL2), SDL was not needed. The window backend's
  SwapBuffersEnd is eglSwapBuffers, no vsync.
- **Input:** the presenter's key state -> `LivePad` pads[0] in the header -> `port_live_read_pads` in
  host_headless.c's `host_read_pads` (an `--input` script still wins). Keys: arrows / WASD stick (Shift
  half), X / Space = A, Z = B, C = Z, Enter = START, Q / E = L / R, IJKL = C, TFGH = D-pad, Esc quits. A
  Linux joystick (`/dev/input/js0`, Xbox layout) is read when present (not tested: WSL has none). Window close
  / Esc sets `quit`, which ends the game's run loop (`host_poll_events`); the game sets `gameExited`.
- **Pacing:** the game runs its fixed 30 Hz step with `--realtime` (play.sh passes it); the presenter shows
  frames as they arrive.

**Measured (WSLg, d3d12 on the AMD GPU, scale 2):** 30 frames/s from boot to the attract demo; frames 0.2 MB
(logos) to 9.9 MB (attract race, texture strips), render 5 - 9 ms per frame; 1 - 34 frames dropped per 600 to
850 steps, all at first-use shader compiles. No texture dedupe was needed (two memcpys of 10 MB per frame).

**Verified:**
- the presenter's frames are **byte-identical** to f3dreplay `--then` of the same steps' dumps (PNG `cmp`, steps
  300 and 580, PORT_GFX_DUMP_STEPS run alongside PORT_LIVE, scale 1);
- **input:** `--inject 600:Return:d,604:Return:u,650:x:d,654:x:u` sends synthetic X key events (XSendEvent to the
  window, back through the X server into the normal event loop): the title goes to English / Japanese and then to
  the main menu (Match Race / Time Attack / ...) in the presenter's frames;
- the M32 `make -C port/gfx test` (test_port_gfx links port_live.c) passes; the matching gate and port-gate pass.

**Limitations / next:**
1. **No live audio.** The machine has no libpulse / libasound (64-bit or 32-bit); WSLg's PulseServer is at
   `/mnt/wslg/PulseServer`. Next: carry the AI buffers in the frame (a LIVE audio record) and play them in the
   presenter through libpulse-simple fetched like the X headers (`apt-get download libpulse0 ...`).
2. **Framebuffer model (agent-a's 19.10 / run 855):** FB_READ / FB_DEPTH chunks travel in every frame but are not
   answered; the planned interface is a reply area in the shm header: the presenter serves them with patch 0003's
   read-back at the end of the frame's Run and writes the 320x240 RGBA5551 image / the depth pixels back, keyed by
   the frame seq; the game's port_fb copies them into the requested images before the next step (one frame of
   latency, the N64's). FB_WRITE (debug paths only) is not composited.
3. Fixed window size (scale x 320x240, no resize / fullscreen). Only pad 1 is driven.
4. A run with PORT_LIVE renders nothing in-process; with `-DPORT_GFX_FAST3D=ON` (option (a)) PORT_LIVE is
   unnecessary.

**Changes outside the new files (agent-a's port/gfx kept minimal):** port_gfx.c (dump_task split into
build_task + the file write; live_task; port_gfx_step_end), port/gfx/Makefile (test_port_gfx links port_live.c),
port/gfx/fast3d/Makefile (the presenter target), main.c (the weak port_gfx_step_end hook, port_live_close),
host_headless.c (pads / quit from the presenter), CMakeLists.txt (port_live.c). New: live_shm.h, port_live.[ch],
fast3d/presenter.cpp, fast3d/setup-x11-dev.sh, port/tools/play.sh.

---

### 19.12 Run 858: live audio (agent-g)

> agent-g run 858, 2026-11-17, branch agent-g. `port/tools/play.sh` now plays the game's sound through WSLg's
> PulseAudio (`unix:/mnt/wslg/PulseServer`), no sudo. `play.sh -m` mutes, `-l MS` sets the buffer (default 80).

**How it works.**
```
 tenshoe: AudioThread_UpdateImpl -> mixer -> osAiSetNextBuffer -> host_audio_queue
   -> port_audio.c audio_sink: --audio-out WAV (if open) + port_live_audio_write
   -> LiveAudio ring (live_shm.h: block at LIVE_AUDIO_HDR = 2048 in the header page, 128 KB data after the slots)
 presenter: live_audio.cpp thread: ring -> pa_simple_write (blocking, tlength = 80 ms) -> PulseAudio
```
- **Ring:** `LiveAudio` (magic "AUDO", rate 32000, 2 ch, power-of-two size, dataOffset, free-running byte
  head / tail, overruns / underruns / trimmed / state). It is a separate block in the header page, not new
  LiveShmHeader fields, so agent-a's reply area (19.11 item 2) merges independently: both only need the
  presenter's file size to cover their region and the game to map up to the larger offset (port_live.c does).
  A presenter without audio leaves the magic 0 and the game sends nothing. The game never waits: a full ring
  drops the AI buffer (overruns).
- **DAC model live:** with PORT_LIVE, osAiGetLength reports a **wall-clock** DAC (32000 frames/s drained
  since the last query, clamped at 0): the driver sizes its 528..544-frame buffers to real time whatever the
  step pacing does (late steps, catch-up bursts, `--authentic`). Without PORT_LIVE the retrace model of
  `--audio-out` is unchanged (deterministic); PORT_AUDIO_DAC=0 still turns the model off. Before, a live run
  had no model at all (560-frame buffers, 5 % too much audio).
- **Presenter thread** (its own; the video loop never blocks it): up to 10 ms per pa_simple_write, which
  blocks while PulseAudio holds the 80 ms; the ring stays at 0 - 40 ms. Backlog > latency + 100 ms (the boot
  burst, or a slow sound-card clock) -> skip down to 20 ms (trimmed). Underrun = ring dry while PulseAudio is
  under 5 ms. libpulse-simple is **dlopen'd**: no library / no server / write failure -> the ring is drained
  and the video runs on ("audio: ... silent"). `--mute` drains too.
- **Libraries:** `port/gfx/fast3d/setup-pulse-dev.sh` -> tools/pulse-dev (apt-get download + dpkg -x of
  libpulse-dev, libpulse0, libsndfile1, libasyncns0, libflac8, libogg0, libopus0, libvorbis0a, libvorbisenc2;
  checks `ldd` resolves). play.sh runs it (a failure means silent, not an abort) and gives the presenter
  LD_LIBRARY_PATH to it.
- **Gamepad:** `/dev/input/js0`, else the first evdev device with BTN_GAMEPAD + ABS_X/Y
  (`live_gamepad.cpp`, axes normalised from EVIOCGABS into the js layout). This WSL has no /dev/input, so
  it is untested on hardware and falls back silently.

**Verified (this machine, headless):**
- 600 and 900 steps with `--audio-out` in the same run and presenter `--audio-dump`: game-side FNV-1a 64 of
  every byte sent == presenter's hash of every byte received (88e0a2e4e2239f3f for 3 819 456 bytes, 29.84 s),
  and the dump is **byte-identical** to the WAV's data chunk (`cmp`).
- `pa_simple_new` connects to `unix:/mnt/wslg/PulseServer` ("PulseAudio ..., 32000 Hz x 2, 80 ms buffer"),
  29 s played, 0 game overruns; after the one boot trim (0.25 - 0.9 s of the boot burst) 0 underruns in the
  600-step run. 19.91 s of audio for 600 steps (20.0 s): no drift.
- fail-soft: `PULSE_SERVER=unix:/nonexistent` -> "pa_simple_new failed: Connection refused; silent", the
  video runs and the ring is still drained (hashes equal); no libraries -> "libpulse-simple.so.0: cannot open";
  `-m` -> muted, hashes equal.
- Not verifiable here: that it sounds right to a listener (the user should listen); the evdev pad.

**Next:** volume / mute toggle key; the presenter could report PulseAudio's real playback position back
for the DAC model instead of the wall clock (only matters for a sound-card clock far off 32 kHz).

---

## 20. M5 prep: saves (agent-c, run 844)

**Rule.** The save file (`--sram`, default `1080.sram`, 0x8000 bytes) is the N64 SRAM image byte for byte:
big-endian, the gdl/backup.h layout, the hardware checksums. An emulator `.sra` (32 KB SRAM dump of the
US ROM) loads as is, and the port's file loads in an emulator. Records in RAM are in host order; the
conversion is at the SRAM boundary only (`port/include/port_backup.h`, `port/fs/backup_sram.c`):

- `Backup_read` (PORT) converts the chunk it just read in place (`port_backup_from_sram`);
  `Backup_write` writes a big-endian COPY (`port_backup_to_sram`: the caller's record, often the live
  options record, stays host order). The SRAM offset names the record: every Backup_read / write
  addresses one whole chunk at its start (header 0, course 0x8 / 0x7DD8, arcade 0x190 / 0x7F60, options
  0x1F8 / 0x7FC8, ghost header 0x218 / 0x7FE8, ghost data 0x230, the 8 sums). Any other offset is
  logged once and left raw.
- `backup_checksum` / `backup_checksumOk` (PORT) sum the record's big-endian image
  (`port_backup_sum`): the length names the record (0x180 course, 0x60 arcade, 0x18 options; the 0x10
  ghost header and the 0x20 header input are all words, whose sum is order-independent).
- Field widths (from the matched loads / stores): time entries all bytes; score entry `score` s32 at +4;
  arcade entry `flags` s32 (word access: the NEW bit 0x80 is in byte 3 of the SRAM word), count / name
  bytes, stages[5] + score s32; options `unlocks` / `seqStep` / `flags` u16, the rest bytes; ghost header 4
  words (`data` is 0 in SRAM); ghost data = InputFrame {s8 stickX, s8 stickY, s16 buttons}: only the
  buttons half swaps.
- Ghosts: `replay_saveGhost` memcpys the recorded host-order InputFrames and `Backup_writeGhost` writes
  them through `port_backup_to_sram` (GHOST_DATA kind); `Backup_readGhost` converts them back, and every
  ghost playback (`replay_beginRecordWithGhost` / `beginPlayback`) plays `session->ghost->data` from
  there. No other path reads or writes SRAM (fs_gdl kind 2 is only Backup_read / write).
- Bytes the game never initializes: options `pad15[3]`, the ghost header's `bits` above bit 13 (the
  setters only clear their own fields) and `unkC` are stack garbage on a fresh save, on hardware too.

**Before this run** the port wrote host-order records with checksums over the host words: self-consistent
on the port, not loadable on an N64 / emulator and vice versa.

**Tests.** `port/fs/test_backup.c` (fs/backup_sram.c alone):
- unit (24 checks): every kind host -> SRAM -> host is the identity, the SRAM bytes are the big-endian
  fields, a port checksum of a converted record verifies the hardware way, the caller's record is untouched;
- `test_backup <save> <bootup 02_Data.bin> [<out.sra>]` (26 more): builds the ROM defaults' N64 image
  independently of the game code (the reset functions' logic over the big-endian bootup Data tables D268 /
  D388 / D3E8 / D430..D43A, hardware checksums, mirrors, header hash) and requires the game-written
  blank-SRAM save to be byte-identical (garbage bytes taken from the save); writes a synthetic `.sra` with
  non-default records (a course time and score, an arcade score / stage, options 0x3F / 4 / 9 / levels
  3,10,0) and a 3-frame time-attack ghost, and checks what `Backup_read` would hand the game.

The port gate's new **saves** step (scripts/port-gate.sh, ~1 s): unit; a 30-frame boot on a blank SRAM
(21 SRAM writes = 4 chunk resets + header) must equal the defaults image; reloading that save and the
synthetic `.sra` must each give exactly 1 SRAM write (the header rewrite, no chunk reset) and leave the file
unchanged; the `.sra` with one byte of the course and of the options primaries damaged must be restored
from the mirrors (5 writes) to the `.sra` exactly.

**Open.** A real recorded ghost round trip (play a time attack, save the ghost, reload, race it) needs
scripted input (agent-a run 843, `--input`): then check SRAM 0x230.. holds big-endian buttons and the
ghost replays identically after a reload. A cross-check against a real emulator `.sra` from the US ROM
would be the last word (none in the repo).


### 20.1 Run 845: the race-load audio crash, a deterministic save, the race with scripted input (agent-c)

**1. The 0x98 / NULL dynTable crash at race load (9.4.1): already fixed on main by 755392718 (the 0xB5 /
0xB2 byte order, 15.10).** agent-a's branch (6ea217c19) was cut from bcf38948a, before that commit. Proof:
- 6ea217c19 built as is, `--input time_attack.input --audio-out` with `PORT_AUDIO_DAC=1` (that tree's opt-in
  DAC model): segfault at step 853 in the same channel-script code; the same tree plus 755392718 only: runs
  2000 steps into the race.
- current main (with or without `--audio-out`, now DAC by default): no fault in 2000 / 6000 / 16000 steps;
  a temporary check at 0x98 / 0xB5 / 0xB6 logged no NULL-dynTable use in a 6000-step race run.
The mechanism is 15.10's: the byte-swapped 0xB5 offset starts a channel inside sample data; which garbage
command (0xB6 at address 0x1, or 0x98 through NULL) faults first depends on the heap, i.e. the timing.
No new audio change; seqrender --course never ran the 0xB5 path (15.10), the game's player-2 seq 26 does.

**2. SRAM determinism (plan 20, 9.4.1's ~35 bytes).** The two PORT scratch records in
`Backup_resetOptions` / `Backup_resetGhost` (game_libs_tail.c) were uninitialized host stack:
options `pad15[3]` (SRAM 0x20D-0x20F) and the ghost header's `bits` 14-31 + `unkC` (0x218-0x21B high
half, 0x224-0x227); the checksums at 0x210 / 0x228, the mirrors (0x7FDD.., 0x7FF5..) and the header hash
followed. The ROM never writes those bytes either (resetOptionsData / resetGhostData set only their own
fields), so the N64 saves stack garbage there too. Fix (PORT only): both scratch records are
zero-initialized, so a fresh save is a pure function of the ROM. test_backup now requires zeros there (it
used to copy them from the save). Two ASLR runs (30-step boot, and the 2000-step time-attack script):
SRAM and state.log byte-identical.

**3. The race with scripted input.** `time_attack.input` minus the course change (DR at 1300), so Crystal
Lake (the first course), plus `F 1460-20000 STICK 0,80`, 16000 steps (~6 s wall): no crash, race state 1
throughout. The rider descends from y 275600 to ~22000 by step ~6800, then **loops**: respawned at
(-16645, 22654, 161343) with speed ~5, falls straight down (x / z fixed) 8200 units in ~150 steps, respawned
again, forever. On course 2 (the script as committed) the same kind of loop starts at step ~2900 (respawn
at (-27600, 278000, -139000), an arc, respawn every ~175 steps). The stick x ±10 changes nothing (dead
zone); stick 0,0 stops the rider at step ~4450 in the same fixed-x/z fall loop. A respawn that never meets
the ground looks like a port collision / physics fault (the camera NaN of 9.4.1 may be related), not
missing steering; so the finish line, the results screen, the game's replay playback and a real ghost save
are NOT reached yet (the recorder runs: 9.4.1). Next: find why the respawned rider never collides
(ground query at the respawn point).

**4. In-race SFX: issued and audible.** A temporary log of AudioThread_QueueCmd from race load
(step 1381) to 4000: player 0 channels 1 / 3 get volume (0x01), pan (0x03), freq (0x04) and IO (0x06)
every frame (channel 3's freq scale follows the speed, 0.66..1.15, IO5 = a speed bucket; channel 1 stays
at volume 0 on this course), and player 2 gets one-shot SFX via channel 0 IO4 (ids 0x3C, 0x08, 0x0B,
0x09 ...; 0xFF stops them). With the course music muted (the 0x82 for player 1 dropped, debug only), the
race part of `--audio-out` still has a continuous rider bed (RMS ~1400-2000) with peaks of 22k-29k at the
player-2 one-shot steps (2207, 2447, 3196). Whether each is the scrape / wind / landing needs a listen.

**5. Crash outside audio: Match Race character select (any save).** Script `START@480, A@560, A@640`
(Match Race) -> `sys_fatal("Invalid Shape cmd 64853")` at step ~654. A second run of time_attack.input
in a directory whose 1080.sram came from a first run hits the same (the save clears the language-menu
flag, so A@560 lands on Match Race). Backtrace: BasePolyShape_parseCmd (game_libs_post0b.c) <-
BasePolyShape_parse (o2_52CD4.c:184) <- BasePolyShape_ctor <- PolyShape_ctor <- CourseList_createItem
(timproc_uso_b5_D884.c, the charmap arm) <- SelItemsMgr_ctor (8FC8.c:388) <- GenSelectChar_ctor <-
app_launchGenProc (o0_8AE4.c:33) <- mgr_procMain <- GameFlow_startMode. The shape stream is
`port_charmap_data + 0x1B4`, all zeros: charmap.uso is not loaded (app_launchGenProc loads it only when
gInputMgr mode != 3 && != 5; Match Race is mode 3 and loads charsps instead), yet CourseList_createItem's
case 0 takes the charmap arm when mode != 2, and SelItemsMgr_ctor creates the 8 course items for i = 0..7.
On the N64 the unresolved charmap import would not be a zero page either, so the port is diverging
earlier: the open question is which of (the mode value, the list's createItem vtable slot / arg2 in mode
3, the jump-table arm) differs. Not fixed in run 845.

### 20.2 Run 848: the fall-through root cause, the finish line, replay and ghost (agent-c)

**Root cause of the "respawn, fall, respawn" loop (run 845): the CollShape edge table's byte order.**
The four CollShape queries (game_libs_ncc_3B2EC / 3B6A0 / 3B9C0 / 3BE1C: height / below / raycast /
query, which CollShape_nearestHit uses) test point-in-triangle by walking the s16 table
`gTriEdgeNext` = {1, 2, 0} at bootup Data 0x1ED90 with a pointer (`nx++`). The access scan in
port-gen-blob-types.py typed only element 0 (a "field" access at +0), so element 1 stayed big-endian:
0x0200 = 512 on the host. The second edge test of every triangle read `f->vi[512]` (a garbage vertex)
and rejected the triangle at random, so the ground query found no ground for long runs. After 151
frames without ground, procColl puts the rider 200 above the nearest marker, and the rider fell
again. The title demo's rider fell through the course too. Fix (875b4e868): a KNOWN layout (6 bytes of
u16). On current main, after the Parms tag fix, the old script gave a damage "Retire" at step 2533
instead of the fall loop (the rider crashed through missing ground). With the fix, no-ground frames
after the race start drop from 2229 to 99 (the longest run from 65 to 21 frames: real jumps). Checked:
the course polyshape's s16 vertices are right (collision reads the same verts and now works), so
agent-g's spike-vertex writer is in the display Vtx build, not in the shared shape data. The
ground-query path (procColl, nearestHit, query, solveContacts) has no adjacent-locals hazard: all its
vectors are Vec3 structs.

**Finish line.** Steering came from a greedy offline search (/tmp/claude-1000/c848/bin/steer.py: per
60-step window, the stick x of {-80, -40, 0, 40, 80} with y 80 that gives the lowest rider y one window
later; 5 parallel runs per window, about 1 minute for the whole course). The script is
/tmp/claude-1000/c848/steer1.input (it reuses time_attack.input's menu steps, without DR). Crystal Lake
is finished at step 4857 with "Goal!" and a time of 1'52"06. Then name entry (5338) and TimMenu (5610).

**Crashes past the goal, fixed (commit 2):**
- NameEntry_drawBoard: NeNode used a g++ `virtual` (vptr read at +0). It is now the cfront layout
  under PORT (explicit vptr at +0x28, CF_V0 slot 11).
- The boot-integrity reads of N64 RDRAM: `*(int *)0xA0000200 == 0xAC290000` in TimMenu_ctor,
  settings_set8_00012818 and MGRRaceProcess_onEndTimerDone, and `*(s32 *)0xA0000284 == 0x240B17D7` in
  MainOptions_buildMenu and mgr_initMatchRace_00000700. These caused a SIGSEGV on the host. Under PORT
  they pass, as on a real cartridge. This also enables TimMenu's "Update Ghost" row, the Options
  "Replay" row and the 4th Match Race course of level 1.
- viewrec (Options / Records): VrNode used a g++ `virtual`, which shifted every VrProc / VrScreen field
  by 4. It is now the cfront layout under PORT. Options and Records now render.

**Replay and ghost.**
- View Replay (TimMenu row 2) plays from 5841 to 9250. The rider position matches the race bit for bit
  through the goal (frame 3399 of the race).
- Update Ghost -> "Save ghost data?" -> Yes: SRAM writes go from 26 to 32.
- Reload test: a new process with that 1080.sram (script /tmp/claude-1000/c848/re1.input: START,
  DD, A ... no language menu on a saved SRAM) starts Time Attack on Crystal Lake. The ghost (trace r1)
  matches the original r0 bit for bit through the goal (3398 frames).

**SFX.** The player-2 channel-0 IO4 one-shots in the race are ids 8 / 9 / 10 / 11 (17 in 3400 frames;
-1 stops them; 0x0602030x = 8 at the start, 3 at the goal). They fire both on landings (airFrames
6-26 before) and on contacts with non-snow surfaces 'd' / 'e' (0x64 / 0x65), with no clear split by id.
Likely the rider's voice variants. The continuous sounds (player 0 channels 1 / 3, frequency follows
speed) are the board / wind bed. Not checked by ear.

**Open issues seen:**
- the speedometer shows 0 km/h at speed 100-230 (a HUD read, not physics);
- slowdown 0x960 sits at 5 for most of the race;
- the name-entry board is a grey box without letters (2D, agent-a);
- the spike polygons (agent-g).

### 20.3 Run 850: the race gate, steer-search, the speedometer, slowdown (agent-c)

**Why the run-848 script stopped working.** agent-g's run 847 fixes (PolyShape_shade / makeEdgeVtxs /
anim_blendPose adjacent locals) changed the physics. /tmp/claude-1000/c848/steer1.input now rides to
~65 % and the rider retires at step 4987: health falls to -9 after repeated crashes. Inputs that worked
before do not fit the new physics.

**Trace field e0=** (port/trace.[ch], the PORT collector in game_uso.c): DataManager entries[0] gives
pct, speed, finished and health. A goal and a retire both end in race state 2. Use pct == 100 for
the goal and health <= 0 for a retire.

**port/tools/steer-search.py.** It replaces the scratch steer.py. Each 60-step window holds a stick x
from {0, ±40, ±80} (y 80), with one window of lookahead. Each candidate is re-run from boot (about 2 s),
5 in parallel. Score: pct + 0.1 x health. A retire is excluded. When every candidate in a window
retires, the search backtracks one window. After the goal, probe runs place the menu tail:
- name entry (flow 12) when the time is a top-3 record: A x5 = "AAA" + END, then Best Times -> A;
- TimMenu -> View Replay;
- after the replay: DD, DD, A, DL, A (Update Ghost -> Yes).

`--tail-only SCRIPT` rebuilds only the tail. On main 1d727331e the search took 65 s:
- Goal! at step 4621, 1'44"08 (3rd place);
- port/host/race_crystal_lake.input; the ghost reload script is race_crystal_lake_ghost.input.

**Gate step `race`** (port/tools/race-check.py, ~7 s, runs in the default gate). Each run starts in a
fresh dir. Checks:
- the goal happens at the script's `# GOAL` step;
- View Replay r0 is bit-identical to the race from start to goal (3154 steps);
- after a new process reloads the 1080.sram, the ghost r1 is bit-identical too.

A deliberately broken stick fails all three checks. On failure the gate prints the steer-search
command. A physics-affecting fix legitimately breaks the script, so regenerate it and commit it with
that fix.

**Speedometer: covered by agent-a's ca1db5292 (run 846/849).** The value fed to the gadget is right:
- e0 speed = rider dnode.speed / 2 (SnowBoarder_update -> RaceTracker_setEntrySpeed, a prototyped
  float);
- RaceTracker_update passes (int)speed.

The 0 / 3 km/h readout came from the two SpeedGadget_setSpeed arms (10..99 and >= 100) that called
sprintf without a value. With that patch applied locally, the HUD read 70 / 56 / 73 / 88 km/h at steps
1700 / 2200 / 2400 / 2900, against e0 speed 70.9 / 56.5 / 73.9 / 88.0. This rules out a units, float-ABI
or byte-order problem.

**Slowdown (rider +0x960): game behaviour, not a port bug.** A temporary probe on the race above found
slowdown 0 on 2652 of 3154 race frames. RiderAnim_stateRide clears it. On a hit (hitKind 1..5),
RiderAnim_updateSlowdown adds st1..3 / sl1..2 = 5 per frame. It stops once the value passes
stm 40 / slm 20 with the board in contact. Then slowCrash = 1 (the crash animation), and the value
resets when the ride resumes. The parms read sane: st 5,4,3, stm 40, sl 5,5, slm 20. The run-848
"sits at 5" came from the pre-847 / pre-fix physics.

**Pending:** agent-a run 849 (the parm-tag byte-order reconcile) may change rider parms and physics
again. If it does, re-run steer-search after rebasing.

### 20.4 Run 853: every game mode headless (agent-c)

Branch agent-c rebased onto fadd3a4b7 (agent-a run 852: cartridge tag order, SnowAI sret pops).

**Fixes.**
- **Tricks never registered:** TrickTable_readEntry_0000C12C copied the 0x40-byte rom/tricks.bin
  records raw, so the 8 words from +0x20 (anims, inputMask, points, riderMask, flags, mirrorIndex)
  stayed big-endian (inputMask 0x2 read 0x2000000). Swapped under PORT. Now hop + B + stick gives
  NOSE GRAB / METHOD / INDY / MELANCHOLY, scored on landing. This also changes the title demo (the
  AI's tricks) and so the rand state at the menu: race_crystal_lake.input regenerated (goal 4708).
- **Trace:** e0 gains score and pendingPoints; e1.. (pct, finished, health, score) for the other
  entries; tk= (trickButtons, trickInputFrames, queued / cur trick index); race= now also for Match
  Race / Contest (owner at DataManager +0xBC) and 2P VS (+0xB8): it was always 0 there.
- **steer-search.py:** --mode trick / contest (windows with a jump + grab variant; score = pct +
  points / 20; the countdown ends the run) and --mode match; RUN32 env for scratch checkouts.

**Per mode** (scripts in port/host/, all from a fresh dir):
| mode | script | how far |
|---|---|---|
| Trick Attack | trick_attack.input | flow mode 6; tricks score (~1000 points); the 30 s countdown is never extended (Time Up at ~25 %, step 2367), then TrkMenu. Open: RaceTracker_passCheckpoints sees an empty "chk" list in Trick Attack (entries->gate NULL), checked before 852; recheck on main |
| Match Race | match_race.input | level Normal, Crystal Lake; player goal 4525, the CPU (SnowAI) finishes 620 steps first -> "You Lose" -> retry -> Round 1 again. Winning needs a faster line than the greedy search finds |
| Contest | contest.input | flow mode 5; gates + tricks ~5000 points, countdown ends the run at ~45 % (step 3311) |
| Training | training.input | flow mode 7; lesson 1 MELANCHOLY done (100 PTS), TrnDataManager advances to 3 METHOD |
| 2P VS | vs2p.input | both pads ride; P2 retires (health -2) at 3679, result, next round at 4238 |
| Options | options_tour.input | opens / closes; no setting changed yet, SRAM persistence NOT checked |

**Name entry for agent-a:** no crafted save needed: race_crystal_lake.input's time is 3rd place.
Frames: /tmp/claude-1000/agent-c/r853/cap_name/png (5440 board, 5480 / 5540 / 5650 name entry,
5760 Best Times): the right-half panel is a plain grey box.

**Gate:** no new step (the race step covers the physics; the mode scripts are ~2-4 s each and could
become a "modes" step that checks: trick points > 0, training lesson advances, 2P VS result).
### 18.25 Run 855: the depth-clear model (sun / flare headless), render to texture (name-entry board) (agent-a)

agent-a run 855, branch agent-a on 79a5aa6: **863a455bb** (port_gfx.c Z-clear model), **3ff19825d**
(f3dreplay render to texture + port/tools/sram-slow-records.py). Both gated (ROM byte-identical,
3579/3579, clean build OK, port gate PASS incl. race: goal 5121, replay, ghost). Frames:
/tmp/claude-1000/agent-a/r855/frames.

**1. Sun / lens flare headless.** Sun_measureVisibility reads 9 Z pixels (0xFFFC = sky) of the
N64 Z image, which nothing wrote without an in-process renderer (read 0xFFFF: visibility 0,
Sun_display returned). port_gfx_task (not PORT_GFX_FAST3D) now walks a task that has pending
depth reads and applies the game's own Z clear to the image in memory, as the RDP does: G_SETCIMG
z (the game masks it to 24 bits, so the full pointer comes from the port_fb_read_depth request),
fill cycle, G_SETFILLCOLOR 0xFFFCFFFC, G_FILLRECT 0,0..319,239 (and the 192x96 replay pass's own
clear), big-endian, only into images some task named with G_SETZIMG. Approximation: no geometry,
so headless the sun is never occluded (it shows behind trees / mountains). PORT_FB_ZCLEAR=0 turns
it off. In-process Fast3D is unchanged (real depth read back). Game state: state.log over a 9700-
step race + replay is identical in every physics field; only the trace's r0 `/animState` field
differs (it prints a pointer-like value at attract step 222+; a trace oddity, not the model).
sun_before / sun_after_s8700.png (replay: sun + flare ring + elements), sun_after_s6900.png.

**2. The grey name-entry board.** Cause: render to texture. The replay 3D task draws into an
offscreen 192x96 RGBA16 image (G_SETCIMG width 192 at 0x9b8f80, scissor 192x96, its own 192-wide
Z clear) and the overlay task textures the board from it (G_SETTIMG fd1000bf 0x089b8f80, TEXRECTs);
Fast3D ignores G_SETCIMG, so the replay landed in the frame's top-left and the board showed the
image's never-written memory (grey). Not the cfront layout, not a texel byte order, not PORT_RDP16.
f3dreplay --then now renders tasks whose colour images are all < 320 wide in a pass of their own,
writes the pixels back (big-endian RGBA5551) into the arena where other tasks load that image,
and draws the frame from the remaining tasks; the board shows this frame's replay (N64: previous
frame's). The "no letters" part: the letter wheel / NAME ENTRY row appear only after A on the
"Nth place" board; they render correctly (nameentry_after_s6190.png: NAME ENTRY A_ _, wheel
SPC DEL END A B C D, the replay with the sun in the board). agent-c's run-853 dumps re-rendered:
agentc_s5540_after.png ("3rd place" board with the replay).
**Open:** in-process Fast3D has the same render-to-texture gap (each task is its own Run /
EndFrame; it would need the offscreen task's top-left region read back into the image's full
pointer + texture-cache invalidate, and not presented).
port/tools/sram-slow-records.py IN OUT: all course times -> 9'59"97..99, resealed (1 SRAM write on
boot). Not needed with main's regenerated race script (3rd place), kept for other courses / modes.

**3. GO!** Not settled. At step 1440 of this build the 3D GO! letters draw pink-red, translucent,
with a light rim (go_s1440.png), not the run-846 dark maroon (that predates run 851's lt0 / lt1
record fix, a plausible cause, unverified). The 32x32 RGBA32 texture in that task (0x09126ca8) is a
whitish chrome map modulated by shade (G_CC_MODULATERGBA); the GO! draw itself was not isolated.

### 19.12 Run 859: render to texture and read-back replies in the presenter and in process (agent-a)

agent-a run 859, branch agent-a on b414f29f1: **5ed411412** (presenter render to texture + the read-back
replies; live_shm.h, port_live.[ch], port_gfx.c), **5604caff6** (in-process render to texture, test_inproc -s).
Gate: ROM byte-identical, 3579/3579, clean build OK, port gate PASS (race / replay / ghost bit-identical).
Frames: /tmp/claude-1000/agent-a/r859 (board.png, ab.png, inproc.png, suncrop.png).

**Design (reply channel).** A second shm file, `/dev/shm/<name>-fb` (`LiveFbReply` in live_shm.h, appended as its
own section; `LiveShmHeader` unchanged, so agent-g's audio ring does not collide). The presenter creates it before
LIVE_MAGIC; after each rendered frame's Run it fills, under a seqlock (odd = writing): the frame's seq / step, up to
64 depth answers {Z image pointer, pixel index, N64 Z (0xFFFC far)} for the frame's DLUMP_FB_DEPTH pixels whose
image is Fast3D's last z_buf_address (low 24 bits), and up to 4 colour images (320x240 RGBA5551 big-endian) for the
DLUMP_FB_READ images the frame drew into. The game (port_live.c) maps it if present; `port_live_fb_apply(rq)`, called
by port_gfx.c after the depth-clear model at every gfx task, takes a new complete reply (a torn copy is dropped),
keeps its depth answers and writes them (big-endian) over the cleared pixels the game is still requesting, and
copies a colour answer into a requested colour image once. Every pixel no reply covers keeps the clear model.
Latency: one to two steps with --realtime. Without PORT_LIVE (the gate) the code is never reached; without a
reply file (an old presenter, or `--no-fb-reply`) the game logs it and keeps the clear model.

**Render to texture.** Presenter: per task, f3dreplay's offscreen_target (all colour images < 320 wide, 16-bit,
not the Z image; height from the scissor); with more than one task those are chained behind their own SETZIMG
prologue and run first, with a ReadbackRequestRgba5551(0, 0, w, h) (patch 0003 does the scale-down); the pixels go
into the arena at the onscreen tasks' TEXTURE / TLUT chunks over the image (base = chunk high byte | img24) and the
texture cache over them is invalidated; then the frame's Run. In process (port_fast3d.cpp): the same test from a raw
walk of the task's lists; after Run the region is written to the image's full pointer (the one registered writable
mapping, hi byte 0..15, holding the whole image) and the cache invalidated; the overlay task of the next frame
samples it (the N64's one-frame lag). test_inproc `-s` renders dumps as one step (one memory image).

**Verified.**
- Board: live (race script, steps 5535 / 5614) the board shows the replay with "3rd place" and NAME ENTRY;
  in process, `test_inproc -s gfx_010858 gfx_010857` (step 5540): grey before, replay after.
- Sun: race script live, --realtime, `--fb-log`: depth answers vary per frame (e.g. 1530-1556 4/5/6 far around
  tree tops, 2216-2276 all nearer against a cliff, z f540..f58c). A/B against `--no-fb-reply` (the headless model):
  at step 2250 the clear model draws the sun glow over the cliff, the replies hide it.
- Colour: Fader / Tv1 reads are answered (2560 replies taken, 167 colour images stored over a 5800-step run).
- Headless unchanged: smoke / race / replay / ghost bit-identical in the port gate.

**Open.**
1. At some sky positions (race steps 1642-1715, sun at x 69-73, y 16-20) Fast3D reads non-far Z (fd20..fd3c,
   smooth across x): something drawn in the sky writes Z there, so the flare stays off where the sun is drawn.
   Unverified whether the N64 writes Z there too (the sun's own billboard or a backdrop with Z_UPD); not settled.
2. The in-process path's offscreen task still shows the replay in its own frame's top-left (each task is its own
   Run / EndFrame there); harmless for the game, visible only in PORT_GFX_PNG.
3. **GO! colour: not settled.** The countdown models (Ready, 3, 2, 1, GO!) all draw the same pinkish red in the
   presenter (r859/go.png); GO! turns translucent as it flies to the camera (likely its fade). The 32x32 RGBA32
   material named in run 855 (0x0914d808 at step 1460) is G_CC_MODULATERGBA (shade x tex0, alpha tex0a x shadea)
   with G_LIGHTING cleared (geometry 0x2204), so run 851's light-record fix cannot change it; its vertices have
   colour d3dee7 and alpha 0..0x0d, so it is probably not the GO! draw. The GO! draw was not isolated.
4. FB_WRITE (debug paths) is still not composited in the presenter.

### 19.13 Run 861: depth-reply window, sky depth / GO! / win box settled, resizable presenter (agent-a)

agent-a run 861, branch agent-a on 34be13c8a: **7f573dfe1** (depth replies: a window around each asked pixel),
**19a679f72** (presenter resize / F11, f3dreplay F3D_ZLOG). Gate: ROM byte-identical, 3579/3579, port gate PASS. Frames:
/tmp/claude-1000/agent-a/r861 (strip3.png, sky/kcmp.png, sky/zoom.png, go/emucmp.png, go/tex_on_green.png,
win/box.png, win/neigh.png, F/small.png, M/sheet.png).

**0. fb-reply re-verify on main (after the 858 / 859 merge).** Replies arrive (2296 taken, 0 torn), but the
A/B at step 2250 showed the sun glow through the cliff WITH replies too (run 859's "replies hide it" was a lucky
frame). Cause: the reply is 1-2 steps old, the clear model resets the whole Z image each task, and
port_live_fb_apply only stored an answer where the game asked about the same pixel again; the sun moves about a
row a step, so its new 3x3 samples read the clear (far). Fix: the presenter answers each asked pixel's
+-6 window (LIVE_FB_DEPTH_R, up to 1024 answers, LIVE_FB_VERSION 2) and the game stores every answered pixel.
After: steps 2240-2254 no glow behind the cliff, it returns as the sun clears the edge (2256-2258);
`--no-fb-reply` draws it throughout (strip3.png: top with replies, bottom without). Depth pixels stored over
2300 steps: 2010 -> 189446. presenter `--png-steps A-B` limits PNGs to a step range.

**1. Sky depth (steps 1642-1715): Fast3D is right, no fix.** Headless dumps 1640-1720 (gfx 3061-3207) replayed
with f3dreplay (`F3D_ZLOG=1` prints each FB_DEPTH answer): (69,16..20) z fd20..fd3c. Bisecting the triangles
(NOOP-ing TRI1s in the dump) finds the writer: the forest band DL 0x08835920 (28 tris, tree-line billboards,
2-cycle FOG_SHADE / XLU blend, Z_CMP|Z_UPD, CVG_X_ALPHA). Their texel alpha at that pixel is >= 0.99 (a shader
threshold sweep: discards only at < 2.0), i.e. opaque trees: the sun sits behind the tree line, the glow is drawn
over it (sky/zoom.png: trees vs the band removed). The N64 writes Z there too (Z_UPD, full coverage), and its
compressed Z for z18 ~0x3F48C is ~0xD230, not 0xFFFC, so Sun_measureVisibility sees it as occluded on hardware
as well. The Fast3D <-> N64 Z encoding difference (linear 14-bit vs exponent / mantissa) cannot change the
`== 0xFFFC` test except for geometry within the last 1/4096 of the depth range.

**2. GO! colour: verified correct.** The GO! is not a 3D model: it is a 136x72 IA8 sprite (0x089f0470, chrome
GO! art with alpha) drawn by the overlay task as 5 TEXRECT strips at (92,84), combine
(PRIM-ENV)*TEX0+ENV, alpha TEX0A*ENVA, PRIM ff8b8e, ENV 621d38 alpha 0xab, blend IN*A + MEM*(1-A). A Python
emulation of that combine over the frame without the sprite matches Fast3D's output to 0.035 / 255 mean error
per channel over 3940 pixels (go/emucmp.png). Dark texels -> maroon 621d38, bright -> pink ff8b8e, at 67 %
opacity over the snow: the "pinkish red, translucent" look is what the game's own PRIM / ENV produce.

**6. f3dreplay crash on Trick Attack's after-goal overlay (agent-c run 860): fixed.** ImportTextureIA8 read
0x089ed5a6: the GOAL! sprite's LOADTILE pieces load rows 187..203 of the 72-wide IA8 image 0x08add1c8; the dump
holds only those rows, so the image's base page was unmapped / unregistered, patch 0005 rejected the G_SETTIMG,
and Fast3D loaded the PREVIOUS image (0x089eaca0, 56 wide) at the new offsets (0x089eaca0 + 56*187 + 30). Fix:
f3dreplay and the presenter map + register the page / block of every G_SETTIMG address in the lists. Open: Fast3D
itself keeps a stale texture_to_load after a dropped G_SETTIMG (a LUS patch; not done, it re-fetches the shared
tools/lus for every agent).

**3. Win-screen box: not renderer-side; agent-c confirms it is the intended Normal level sign.** The green box is a 32x64 RGBA16 TEXRECT at
(144,108) (overlay task, PRIM*TEX0, prim alpha 0xfe) of texture 0x089ae330 = flowimgs.bin +0xfc5ac: the
green-circle trail-difficulty sign (its neighbours in flowimgs are the blue square and black diamond,
win/neigh.png). It decodes correctly; it also shows on the Round 2 intro. Whether the N64 draws it there
(position / visibility) is game logic: agent-c to check the object that draws it (likely the next course's
difficulty sign).

**4. Upscaling at 3x:** race HUD, title logo, select rider / board / course frames checked (M/sheet.png,
M/title.png, M/board.png, hudcrop.png): no strip seams or filtering artefacts beyond patch 0009. The blocky
board-silhouette edges are texel-level alpha cut-outs (the N64 shows the same at 1x).

**5. Presenter resize / fullscreen:** the window is resizable (min 320x240); each frame renders straight into
the largest centred 4:3 rectangle (mGameWindowViewport + mCurDimensions; patch 0003's read-backs honour the
offset). F11 toggles EWMH fullscreen. Verified: `--inject 900:F11:d` -> 2560x1440 letterboxed frames, depth
replies still served (F/small.png).

### 19.14 Run 865: LUS patch 0010, scripted live play, presenter lifetime (agent-a)

agent-a run 865, branch agent-a on c1fce01a9: **944fb5092** (LUS patch 0010), **f8d87a3f9** (presenter --input in
lockstep, lifetime robustness, frame-time summary). Gate: ROM byte-identical, 3579/3579, clean build OK, port gate
PASS (golden 19 scenes), `make -C port/gfx/fast3d presenter` OK. Logs / frames: /tmp/claude-1000/agent-a/r865.

**Patch 0010 (19.13 item 6's open part).** A G_SETTIMG rejected by patch 0005's check now clears Fast3D's
texture_to_load; LoadBlock / LoadTile / LoadTlut skip while no valid image is set (TMEM keeps its contents),
each case logged once. G_SETCIMG / G_SETZIMG are never dereferenced by Fast3D (only compared; the port reads them
back as identifiers), so they are unchanged. Goldens byte-identical. Run 861's crash dump with the f3dreplay page
mapping disabled: "rejected address 0x8ADD1C8" + a skipped LoadTile, no stale read. It fires live too: title step
280 emits `fd18001f 00000000` (a 32-wide RGBA32 G_SETTIMG of NULL, list 0x08818998) then a LoadTile; the frame
is identical to the 9-patch render. **Shared tools/lus re-fetched 2026-11-17 15:53:46 EST** (10 patches, stamp
f3db85554656, from local mirrors of the pinned commits). agent-g's f3dreplay build in
/tmp/claude-1000/agent-g/r863/pg was mid-compile at that second (note in /tmp/claude-1000/coord/lus_refetch.txt).

**Scripted input through the presenter (`presenter --input SCRIPT`).** The presenter reads a port/host/*.input
script and answers each game pad read in lockstep (live_shm.h padScripted / padWant / padStep, from the reserved
words; the game waits only when the presenter sets padScripted). Keyboard --inject cannot reproduce the scripts'
analogue sticks and step timing; lockstep can. Results (scale 3, WSLg D3D12 on an AMD Radeon, load ~15 / 32 from
other agents):

| run | steps | state trace vs headless --input | rendered / skipped / dropped | render ms mean / p50 / p95 / p99 / max | > 33 ms |
|---|---|---|---|---|---|
| Crystal Lake race script (goal 4708, name entry, replay, ghost save) | 9842 | identical (all fields but vi) | 9840 / 2 / 0 | 8.77 / 8.67 / 13.23 / 16.51 / 94.3 | 22 |
| Trick Attack (goal 4524, after-goal overlay) | 4824 | identical | 4823 / 1 / 0 | 7.50 / 7.59 / 11.25 / 14.38 / 73.4 | 3 |

- Frames vs `f3dreplay --then` (headless dumps of the same steps, same scale): race steps 3000, 4700 (goal),
  7000, 9000 (replay) byte-identical; 1500, 2250, 4000 differ only by the sun glow (the depth replies): with
  `--no-fb-reply` all three are byte-identical; 5540 (name entry) differs by the board's replay image (the
  colour replies, run 859). Trick Attack 4540 / 4560 / 4600 / 4650 / 4700 / 4800 (GOAL! overlay): identical
  (4540: 61 px, all within 8 levels). No presenter crash in either run.
- fb replies: race 9833 taken, 0 torn, 1144227 depth pixels and 884 colour images stored; trick 4821 / 0 /
  774534 / 208.
- **Audio does not keep up (open, not a run-865 regression).** Race: 320.8 s received (hashes equal), only
  15.4 s played, 39.0 MB (305 s) trimmed, 3 underruns, 427 game overruns; trick: 3.95 s played of 73.5 s
  received. origin/main's presenter shows the same (title, 20 s: 1.50 s played of 5.52 s, 867 overruns), with
  llvmpipe too. A standalone pa_simple client with the presenter's spec and name plays 10 s in 9.94 s, also
  while a presenter runs, and also after a dry start. strace: the presenter's libpulse thread gets a server
  request only every ~0.6 s (poll timeouts 80 / 160 / 320 / 640 ms). Run 858 had 0 underruns, so something in
  the presenter process (or WSLg's server state for that stream) changed since; next: log pa_simple_get_latency
  per write, and try a dedicated pa_threaded_mainloop stream.
- One presenter death in 6 short runs: "D3D12: Removing Device." then exit at title step 18 (au1, not reproduced);
  the game ended itself (below).

**Lifetime (tested, /tmp/claude-1000/agent-a/r865/robust.sh).** Esc (--inject) -> game quits in 6.8 s, rc 0,
files removed. kill -9 of the presenter -> "the presenter (pid N) is gone: ending the game" (port_live.c checks
the pid about every 0.2 s, also inside the lockstep wait), rc 0, the game removes the shm files. kill -9 of the
game -> "the game (pid N) is gone", presenter exits 0. `--stay`: game 1 ends -> "waiting for a new game", game 2
attaches ("game pid N attached (game 2)") and renders, SIGTERM exits cleanly (the game clears gameExited on
attach). xkill of the window -> "lost the X display ...: telling the game to quit" (XIO handler), the game quits,
files removed. No display: the window now opens before the shm file exists; DISPLAY unset / :9 print what is
missing (the X socket, WSLg hints); EGL failures suggest software GL; play.sh stops with "the presenter could
not start" instead of starting a game that waits 10 s.

### 19.15 Run 867: the live-audio stall is WSLg, not the presenter (agent-a)

**Root cause.** Not a presenter commit. Any X window **mapped while a PulseAudio stream is playing**
stalls WSLg's whole PulseAudio server (its RDP sink -> weston -> msrdc path): `pactl info` itself takes
~12 s, and every client's `pa_simple_write` blocks, for as long as that window lives. Reproduced without
any presenter code: a 70-line libpulse + live_audio.cpp harness plays 8.04 s in 8 s; the same harness with
a 10-line `xmap` (XCreateSimpleWindow + XMapRaised, from the same or another process, drawing or not)
mapped at t = 3 s plays 4.6 s, then nothing for ~8 s until the window exits. An unmapped window is
harmless; a window mapped **before** the stream is harmless if the stream opens >= 2 s later (1 s: stalls).
The presenter maps its window and opened PulseAudio milliseconds later, so it stalled from boot. Bisect:
every buildable presenter since run 858 (fbda0cb2e, 9bc2d9fdc, c9250d020, c1fce01a9, HEAD) fails the same
way (the run-858 commit b6b9ddbc6 itself does not compile: mid-merge live_shm.h); run 858's 0 underruns was
a different WSLg / msrdc state. During one test weston itself aborted (window-manager.c:1387
`!window->shsurf`) and WSLg restarted it; the stall persisted after the restart. Recovery after a stall:
a new stream plays again once the server answers. Test hygiene: wait for `pactl info` < 0.3 s between runs
(a stall lingers after its window exits), and other agents' windows stall it too.

**Fix (live_audio.cpp / presenter.cpp).** PulseAudio opens `--audio-open-delay MS` (default 2500) after the
window is mapped; the ring is drained meanwhile (counted "before open"; the game's first 6 s are digital
silence, RMS 0, so nothing audible is lost). F11 (fullscreen, a remap in WSLg) first calls
`live_audio_suspend()`: the stream is closed (no drain), the ring drained, and the stream reopened 2.5 s
later. `--audio-stats` prints `presenter: audio-stats: output pulse, received R s, before open B s, played
P s, trimmed T s, ..., played/received-while-open X%`; the per-second status now shows played too.

**Check (needs a window, so not in the port gate):** `make -C port/gfx/fast3d audio-check` =
`port/tools/audio-check.sh [-f STEPS] [-m MIN] [-o DIR]`: play.sh with the Match Race script in lockstep,
3300 steps (menus + ~60 s of racing, fresh SRAM), pass if played >= 95 % of received-while-open (and >= 30 s
received). `AUDIO_CHECK_PRESENTER="--audio-open-delay 0"` reproduces the stall.

| run | received | played | trimmed | game overruns | played / received-while-open |
|---|---|---|---|---|---|
| title 600 steps, before | 4.47 s | 1.45 s | 2.0 s | 930 | 32 % |
| title 600 steps, after | 19.90 s (2.40 before open) | 17.49 s | 0 | 0 | 100.0 % |
| audio-check race 3300 steps, `--audio-open-delay 0` | 21.18 s | 2.24 s | 17.92 s | 5336 | 10.6 % (FAIL) |
| audio-check race 3300 steps, after | 109.75 s (2.37 before open) | 107.19 s | 0.19 s | 0 | 99.8 % (PASS) |
| title 900 steps, F11 x2 (4 key events), no suspend | 29.92 s | 14.07 s | 13.25 s | 0 | 51.1 % |
| title 900 steps, F11 x2, with suspend | 29.93 s (7.33 suspended / before open) | 22.60 s | 0 | 0 | 100.0 % |

- Not agent-c's `[heap]` / ASLR audio bug (run 869, abea07e2e): these runs had no `setarch -R`, the game's
  audio was non-silent after the boot, game and presenter FNV hashes agreed, and the harness reproduces the
  stall with no game at all.
- "D3D12: Removing Device" did not recur (0 in 8 windowed runs, incl. the 3300-step race); play.sh's help now
  names `-S` (software GL) as the fallback for it.
- Open: other apps' windows mapped during play still stall WSLg audio (outside our control); a window
  resize by drag was not tested; for the native single-process game (21.9), open its PulseAudio the same way
  (after the window, and suspend around fullscreen).

### 20.5 Run 857: checkpoints, the Match Race win, options persistence, the modes gate step (agent-c)

Branch agent-c on origin/main 384c40ad6: 2f9a83eed (trace cd= / trn=), 878be00f3 (steer-search,
scripts), 1e1a5d213 (modes-check, port-gate `modes` step). Gate (matching + port): PASS, 3579/3579,
ROM byte-identical; modes 2 s.

**Trick Attack countdown: not a port bug.** In a fresh dir the "chk" items load (ItemMgr class mask
0x13E: item_registerTemplates sets bit 2 when nextFlowMode == 6) and RaceTracker_findGates links 5
checkpoints. RaceTracker_passCheckpoints extends the countdown (RaceTracker_onCheckpoint: gate +0x88
seconds, 10 here) only when CheckpointCyl_isBetweenPosts says the rider crossed the gate's z between
its posts (XZ dot product); run 853's script crossed the first one at x -4518, posts at -2203 / -426.
The "empty chk list" of run 853 came from a run in a directory that held an earlier run's 1080.sram:
the saved language pick skips the language menu, so every scripted press lands one menu off and the
script rode Match Race (flow 3, mask 0x134). **Always run scripts from a fresh dir / --sram.**
Contest has no chk items (bit 2 is Trick Attack only, as in the ROM); its countdown grows by 2 s per
cleared slalom gate (gtl / gtr, bit 0: RaceTracker_passGates, flags & 1 = pass on the left).

**Trace (PORT only):** `cd=<DataManager.score (countdown ms)>,<chk gates left>,<chk x>,<chk z>,<slalom
x>,<slalom z>,<slalom flags>` and `trn=<TrnDataManager.lesson>` (flow mode 7).

**steer-search:** trick / contest score the countdown (2 per second) and the next gate's line;
Trick Attack backs out a window that crosses a chk line outside the posts and records `# CHECKPOINTS n`.
Match: 30-step windows, stick y centred, x in 0, +-17, +-24, +-32, +-48, +-80 (the CPU rider's own
stickX is mostly within +-0.15 and stickY 0, logged from SnowBoarder.input; full lean / crouch windows
lost by ~550 steps whatever the score terms: speed, crash penalty, the CPU's line).

| mode | before (853) | now |
|---|---|---|
| Trick Attack | Time Up 2367, 0 extensions, 25 % | 3 extensions, 62 %, Time Up 3730, 1575 pts (2 chk left: the greedy line is too slow for the 4th) |
| Contest | 45 %, Time Up 3311 | 53 %, Time Up 3432, 5340 pts |
| Match Race | You Lose (goal 4525, CPU ~3906) | **You Win** (3899 vs CPU 3959), "Advance to next round", "New Record 1'19"16", Round 2 Crystal Peak at 4401 |
| Options | not checked | Sound: BGM 9 / SE 7 / Mono saved (SRAM 0x1F8 + mirror 0x7FC8); a new process shows them and saves BGM 10 |

**Match Race progression / SRAM:** no SRAM write after the win or in Round 2: Match Race records are
written by Backup_closeSession(session, 3) from mgr_closeSession_000009A8 when the mode exits, which
the script does not reach. Round 2 ridden with a centred stick crashes out (damage) and retries Round 2.
Not checked: unlocks after a whole level. Open: the in-race pause (START) freezes the clock (el), but
the first D-pad down / stick down closes the menu (Continue) instead of moving the cursor, so Quit
was not reachable by script (Time Attack's pause also freezes; its menu not tried). The result
screen shows a green box with a circle in the middle of the "Advance to next round" text (frames:
/tmp/claude-1000/agent-c/r857/cap_win1/png).

**Gate step `modes`** (port/tools/modes-check.py, ~2 s in the gate, all six in parallel): trick (points,
>= `# CHECKPOINTS`), contest (points, an extension), training (lesson 0 -> 2), vs2p (race end 3679, next
round 4238), match (goal; `# WIN` -> before the CPU), options (save, reload in a new process). Each
failure prints the steer-search command or the script to edit.

### 20.6 Run 860: pause -> Quit, Match Race records in SRAM, the level sign, Trick Attack's goal (agent-c)

Branch agent-c on origin/main 34be13c8a. Commits: e00d7d8dd (Match Race pause -> Quit; the modes match
check reads the record back), ba8f5f4ce (Trick Attack to the goal). Gate (matching + port): PASS.

**The in-race pause menu works; run 857's "first down closes it" does not reproduce on main.** Frames
(capture.sh -F ... -M) of Match Race (arcproc menu: Continue / Retire / Restart / Quit) and Time Attack
(Continue / Retry / Change Course / Change Board / Change Rider / Quit) show the cursor moving on DD and
on the stick held down. It also moves on presses 6 steps after START and on 1-step presses. The cursor row
blinks (it is not drawn every frame), which can look like a missing row. The input chain is right:
- pad_decodeButtonMap: D-down 0x400 -> 0x8, A -> 0x100, START -> 0x40000;
- pad_update: stick y < -0.5 -> 0x8000;
- PauseMenu_update: 0x8008 moves the cursor down, 0x2004 moves it up;
- the race process: 0x100 / 0x40000 pressed then released selects the row (m26).

**Match Race records persist.** match_race.input now continues after the Round-1 win:
1. A, A: Round 2 (race state 1 at 4401).
2. START at 4600, then DD x3, then A: Quit (flow 5).
3. The session closes (mgr_closeSession -> Backup_closeSession(session, 3)), and the name entry follows
   (the 1'19"16 win time is a top-3 Crystal Lake time): A A A END = "AAA".
4. Best Times, A: the title at 5365.

The SRAM then holds records[2] (Crystal Lake) entry 0 = name AAA, 1'19"16 (bytes 00 00 00 00 00 01 13 10
at 0x68), and the mirror at 0x7E38 matches. A new process on that file shows Time Attack Crystal Lake's
HUD BEST TIME 1'19"16 (records_reload.input; capture -F 1600). That boot does 1 SRAM write (the header)
and leaves the file byte-identical: no chunk reset. Quitting from Round 2 returns to the title, not the
main menu. One won round changes no unlock: the arcade chunk (0x190) is unchanged. Unlocks after a whole
level (4 courses) are still not checked.
- `modes` match check: with `# RECORD m'ss"hh`, that time must be saved under AAA (primary = mirror), and
  records_reload.input in a new process must give rc 0 and leave the file unchanged. The run adds ~1 s.
- steer-search --mode match writes the same tail (MATCH_TAIL) and reads `# RECORD` back from its run's
  SRAM. `--tail-only` now covers match mode, and it reproduces the committed F lines.

**The win screen's "green box with a circle" is the game's level sign, not a bug.** It is mgr_loadSprites
sprite import_80263D30, id `(level - 1) | 0x200000`, a 32x64 RGBA16 image: a white trail sign with a green
circle. The Select Level screen's Normal card is the same "Green Circle PASS"; the circle is the ski-trail
difficulty mark. The game draws it:
- mgr_drawResults_000023FC (the NCC donor): at (0xA0, 0x8C), centred, whenever race.result != 2. It comes
  first in the overlay DL, under the "ADVANCE TO NEXT ROUND" sprite at (0xA0, 0x78).
- MGRRaceProcess_drawIntro: at (0xA0, 0x9C), on the "Round 2 / Crystal Peak" screen.

The texture decodes cleanly big-endian at 32 wide, and the renderer draws exactly that image.

**Trick Attack reaches the goal** (port/host/trick_attack.input, regenerated). The settings:
- STEER_TRICK_ACTS=fast: x 0 / +-20 / +-40 / +-80 at full lean; jumps only with x 0 / +-40.
- STEER_POINTS_W=0.2, STEER_POINTS_CAP=150, STEER_JUMP_UNTIL=1700: two early tricks (234 pts), then steering
  for speed.

All 5 checkpoints are passed, Goal at 4524 (run 857: 3 checkpoints, Time Up at 62 %). The search takes 116 s
and is deterministic. The greedy line is chaotic: late jumps cost the speed the 4th and 5th checkpoints
need. steer-search now writes `# GOAL` in trick mode, and the modes trick check then requires pct 100. Each
scored candidate in trick_main now carries its own action, so a backtrack across STEER_JUMP_UNTIL stays
correct.

**For agent-a: f3dreplay segfaults on Trick Attack's post-goal overlay task.** The 3D task renders, and
`dlump.py --check` passes. The overlay holds 51 IA8 / RGBA32 TEXRECTs, and nothing looks out of range.
Repro: `f3dreplay /tmp/claude-1000/agent-c/r860/f3dcrash/gfx_008838.dlmp out.png` (step 4530;
gfx_008978 = step 4600 also crashes; gfx_008837 is the 3D task, which is fine). Capture:
`capture.sh -i port/host/trick_attack.input -n 4800 -F 4530 -M`.

### 20.7 Run 864: the soak / fuzz harness, one crash class, the gate's soak step (agent-c)

**The harness: `port/tools/soak.py`.** Each seed produces a reproducible input script (`--script SEED`
prints it). The script covers:
- the title, plus the language A on a blank save;
- sessions that pick the main menu and selections at random (mostly A, some D-pad / B / START);
- for 40 % of the sessions, a directed walk instead: a mode, then D-pad steps on the rider, board and
  course screens;
- rides: stick segments, hop + grab / spin tricks, hands-off stretches, and pauses resolved with resume /
  retire / restart / quit and a confirm box;
- result presses and idle stretches.

Of the seeds, 15 % mash every button instead, 22 % plug in 2 pads and 5 % plug in 4. The seed also picks
the SRAM, which is one of:
- blank;
- match_race.input's save;
- race_crystal_lake.input's save (record + ghost), resealed with options unlocks 0x00FF and seqStep 5
  ("unlocked": every course).

Runs go in parallel (`-j`), each from a fresh directory, with `--audio-out /dev/null` so the mixer
counters are printed. The failure classes are:
- signal (class key = the top two game frames, from addr2line);
- sys_fatal / PORT TRAP / DEADLOCK;
- hang;
- short run;
- NaN / Inf in rider / e0 fields (camera NaN is soft unless `--strict-camera`);
- stuck retrace;
- audio badAddr / unknownOps;
- frozen rider (soft).

`--minimise` ddmin-shrinks the first run of each class: it cuts the run at the failing step, then removes
F lines with parallel complement tests. `--save-repro` writes the result to `port/host/repro/<class>.input`
(headers `# SOAK seed= steps= sram=` and `# END`). The coverage lines report:
- the racing share;
- runs per flow mode;
- distinct (mode, race start position) pairs, a proxy for courses (14 – 17 per batch);
- the music command words heard.

Usage: `soak.py -b <port build> -o <new dir> --seeds 0-499 --steps 6000 -j 14 [--saved-frac 0.4]
[--minimise --save-repro] [--keep]`. 150 runs × 6000 steps take ~100 s at -j 14 (about 5000 steps/s
per core with audio).

**Runs:** about 2070 in all. 304 were on the first build (2 crashes, below); the other ~1770 were on fixed
builds:
- ~1380 × 6000 – 15000 steps;
- 28 × 40000 steps (heap / leak check over many race loads);
- 60 × 8000 steps, with the traces kept for a dwell analysis;
- 300 runs on the final harness (seeds 20000-20299, 0 failures, one batch with `--strict-camera`).

**One crash class found and fixed: `signal:11:snd_SoundObjUpdate>snd_updatePlayer`.** Seeds 183 and 257
crashed in Trick Attack at the first grab (later also seeds 20 and 36 under the final generator, with the
pre-fix binary).
- **Root cause:** the trick gain-wobble read `*(f32 *)((char *)(i * 4) + kD_sndGainWobble_1C430)`. In the
  ROM, the lui / addiu pair is relocated against bootup Data. On the host it is the bare constant 0x1C430,
  so the read is a wild address. It is the one Data-offset constant site in src/ with no zero-symbol token
  (grep `+ kD_` / `kRoF_`).
- **Fix:** `#ifdef PORT` based at `port_bootup_data`. The table is f32-swapped in blob_types, and the
  matching build is unchanged.
- **Regression:** the minimised repro (13 F lines, 1830 steps) is
  `port/host/repro/signal_11_snd_SoundObjUpdate_snd_updatePlayer.input`.

Nothing else was found:
- no sys_fatal, trap, deadlock, hang, NaN or audio fault, across every mode, the unlocked courses, 2 / 4
  pads, button mashing, Options (Records / Erase Saved Data reachable) and 40000-step sessions;
- nothing for agent-a (the renderer is not exercised headless).

The long flow dwells the dwell analysis flagged are not stuck states:
- `flow=1,1,1` for 7000 steps is the Options / Records screens, waiting for B (capture.sh sheet, run 864);
- `flow=2,7,7 race=0` is Training.

**Gate:** `scripts/port-gate.sh` has a new `soak` step (~10 s). `soak.py --gate` runs 12 fixed seeds ×
5000 steps (blank / unlocked / saved, in rotation) plus every `port/host/repro/*.input`. Each run must be
free of hard classes. The pre-fix binary fails it on the repro.

**Next / ideas:**
- A screen-level stuck detector. The flow tuple does not change inside menus, so it needs an RCP / DL
  signature per step.
- A Match Race win path in the generator, to unlock rounds 2+ from a blank save.
- Run the soak on the 64-bit build once agent-g's boot runs past the title.

### 20.8 Run 869: the 64-bit soak, one 64-bit crash + a no-ASLR audio bug, the screen hash, Match Race rounds (agent-c)

**64-bit soak: `soak.py --build64 <PORT_64 build>`.** Every job also runs on the x86-64 build (plain exec,
no i386 loader). Its failures are tagged `x64:<class>`. When both runs are clean, the two state.logs (with
the `/N` host address dropped) and the final SRAMs must be equal: `diverge64:<first differing fields>`,
`:sram`, `:length`. Two more comparisons are soft for now: the screen hash (`x64-screen`) and, with
`--audio64`, the WAVs (`x64-audio`).

**Result: 400 seeds × 8000 steps on both builds.**
- **One 64-bit crash class: `x64:signal:11` at step 0, in port_main reading the ROM buffer (7/400).**
  - Root cause (strace): with ASLR, the non-PIE brk heap starts anywhere in the 1 GB after .bss, so it
    can start just below 0x40000000, which is where the MAP_32BIT game stack lands. brk cannot grow, so
    glibc falls back to an mmap above 4 GB, and the x32 code truncates the pointer.
  - Fix (host/main64.c): one re-exec with `ADDR_NO_RANDOMIZE` (`PORT64_ASLR=1` opts out), and a refusal
    to start with less than 256 MB of brk room. 0/400 startup crashes after it.
- **The re-exec exposed an audio bug in both builds (no ASLR: setarch -R, gdb).** The kernel labels the
  .bss mapping `[heap]` too. port_audio.c's read_maps kept the last `[heap]` line, so .bss fell outside
  host_mapped(), every AUDIO_IS_RELOCATED_PTR test failed and no samples loaded. It now keeps the lowest
  `[heap]` start.
- **After both fixes (400 more seeds × 8000 steps, both builds):** no x64 crash, no state.log or SRAM
  divergence in any run. The screen hash and audio do NOT agree yet (`x64-screen` in 398/400 runs):
  - Screen hash, title demo step 223: the projection G_MTX differs. This is Window_setupView ->
    math_perspectiveF (abi-scan --x64 X64P1-3: decl int, def float).
  - time_attack.input, from about step 710 (retrace 1420): the 64-bit driver DMAs other samples. This
    lines up with the snd_* / AudioThread_QueueCmdF32 X64KR / X64P findings.
  - Both are on agent-g's list. Once they are fixed, `x64-screen` / `x64-audio` can go hard: drop them
    from SOFT in soak.py.

**The screen hash: `PORT_TRACE_SCREEN=1` writes `scr=<hash>` to state.log** (port/trace.c). The hash is
dlump_screen_hash (port/gfx/dlump.c): the step's gfx tasks' command words without host addresses, plus the
G_VTX / G_MTX / G_MOVEMEM bytes. It is pointer-free, so it is comparable across builds, and a page cache
sits in front of mincore (the soak gate step costs +1.5 s). soak.py sets it and flags `stuck-screen`
(hard): 900 steps of an identical display list through 8+ presses, with B and at least 3 distinct
buttons among them.
- The first version (8 presses of any kind) hit seeds 111 and 268 on both builds. These were false
  positives: Options > Records (flow 1,1,1) ignores A / D-left / D-right, and a later D-down scrolled it.
- With the B requirement, both seeds are clean. No real stuck screen has been found so far.

**Gate:** port-gate.sh's build64 step runs `soak.py --gate64` (gate seeds 2 and 3 on both builds,
+~10 s). It needs no hard class and prints `soak64 N runs: H hard, S soft`.

**Match Race rounds: `steer-search.py --mode rounds [--from match_race.input] [--rounds 6]`.** It keeps
the won rounds of `--from`, presses A A into the next round, finds its race start, and searches the round
the way `--mode match` does. Each round is written as `# ROUND k GOAL g WIN|LOSE`. The script is saved
after every round, and on a budget cut, so a later call with `--from <out>` resumes.
- Round 2 (Crystal Peak) starts at step 4401. The greedy search trails the CPU rider by 1 – 4 % pct all
  the way (round 1's fine y-centred acts and `STEER_MATCH_ACTS=wide` alike); details below.
- Rounds 3 – 6 and the unlock checks (courses / boards / riders in SRAM and in the selects) need a round 2
  win first.
- Ideas: weight the lead over the CPU (pct − cpu pct) in the score; or longer lookahead windows on the
  CPU's line; or a deeper beam than greedy + 1-window backtracking.

### 20.9 Run 871: the fork-server beam search; Match Race Normal cleared, Hard 4 of 5; the progress gate step (agent-c)

**Fork server (port/main.c `--fork-at STEP --fork-dir DIR`, client port/tools/forksrv.py).** tenshoe runs to STEP and
parks; over two client-made FIFOs (cmd / ack) it forks children: `run SCRIPT UNTIL OUTDIR` (chdir OUTDIR, swap in
SCRIPT at the same step: host_input_script_reload, state trace from the fork step: port_trace_reopen_state, exit at
UNTIL), `spawn SCRIPT UNTIL NEWDIR` (the child parks again at UNTIL as a new server), `wait`, `quit`. The port is
deterministic, so a child equals a from-boot run with the same script (checked: identical state.log lines; and
steer-search replays every round's goal from boot before accepting it). A candidate now costs only its own steps.

**steer-search --mode rounds is a beam search** (beam_round): STEER_BEAM (12) lines, each a parked server; every
line forks one child per MATCH_ACTS stick, held STEER_LOOK (2) windows, scored as --mode match plus
STEER_LEAD_W (1) x (pct - the CPU's pct) and minus STEER_STALL_W (5) under 15 km/h; the best distinct
(STEER_DEDUP 300 units) children are spawned on as the next beam. A LOSE retries with a wider / longer beam and a
heavier lead weight; STEER_ACCEPT_LOSE=1 keeps a loss (the game offers the round again: MgrCourseList.retries 3).
`--levels N`: when a level ends it presses A through the result / ending / name entry / Best Times screens and the
main menu until Select Level (flow 0,3,3), then DR x level and A into the next level (`# LEVEL n START s`).
The run-869 CPU-line weight x10 made things worse (cpu_path keeps only z-increasing points: round 4 turns).
Round 2, which the greedy search lost by 1-4 % in 1200 s, is won in 56 s.

**Results (port/host/match_race_full.input, one script from a blank save, -w 20 STEER_LEAD_W=2 from round 8):**
| level | course | round | goal / CPU | |
|---|---|---|---|---|
| Normal | Crystal Lake, Crystal Peak, Golden Forest, Mountain Village | 1-4 | 3899/3959, 7554/7641, 11044/11161, 15049/15115 | all WIN |
| Hard | Crystal Lake, Crystal Peak | 5-6 | 20473/20598, 24126/24194 | WIN |
| Hard | Golden Forest | 7 | 27642/27588 | LOSE (kept; retries 3 -> 2) |
| Hard | Golden Forest (retry), Mountain Village | 8-9 | 31095/31159, 35023/35079 | WIN |
Still to ride: Hard course 5, then Expert (6 courses; riders[5] = the boss by seqStep). Resume:
`STEER_LEAD_W=2 steer-search.py -b <build> --mode rounds -w 20 --levels 3 --rounds 30 --from <copy of
match_race_full.input> -o <same>`, ~100 s calls (each round 2-4 calls). Normal's 4th course: this cart's
boot word gives count 4 (mgr_initMatchRace).

**Unlocks seen.** Normal cleared: options seqStep 1 -> 2 (settings_stepSequence), unlocks 0x1F -> 0x3F (bit 5,
already after Normal round 3; Time Attack's course list), newMark set. The Select Level screen then shows Hard's
"Blue Square PASS" card (Expert still a black card); capture frames /tmp/claude-1000/agent-c/r871/cap1 and
cap2 (DR -> the blue card, "Round 1 Crystal Lake" with the blue sign). Not yet seen: Expert open (seqStep 3),
seqStep 4 / 5 (Expert with the boss riders: step 4 -> 5 needs Expert again with options score + 1 ==
gSettingsStepTbl_C69C[0]), rider / board unlocks; Trick Attack / Contest score unlocks not looked at (no writer
of unlocks other than settings_setBit found by grep: its callers go through the bootup export table).

**Trace:** `ml=<retries>,<idx>,<count>,<course>,<rider>` in Match Race (MgrCourseList through GameFlow.flowProc
+8); `PORT_TRACE_RIDERX=1` adds `i<n>=flags,maxSpeed,stickX,stickY,held` per rider (RiderInput: the pad or the
SnowAI). Every rider seen so far has maxSpeed 228-230 and no SNOWB_FLAG_CATCHUP (player 0x55803, CPU
0x9806 / 0xD806): no rubber band in Normal / Hard.

**port/tools/progress-check.py.** Full mode runs the progression script to each level's end in fresh dirs and
checks the save (options primary == mirror, sums, header hash, seqStep = levels + 1) and its reload: a new
process presses Match Race, DR x the open levels, A ...; the trace's ml= count must be that level's (4 / 5 / 6),
one DR more must stay on it (locked card), and the save file must not change. `--sram SAVE --expect-levels N`
does the reload part only. **Gate step `progress`** (port-gate.sh, ~3 s): port/host/progress_level1.sram
(Normal cleared, from the script) -> PASS: unlocks 0x003F seqStep 2, DR x1 -> count 5 (Hard), DR x2 -> 5.
Add progress_level2.sram once Hard is cleared (the gate loop already looks for it).

## 21. M6: 64-bit (agent-g, run 862)

### 21.1 The gap, measured

A plain LP64 build (`-DPORT_64=ON` with the game compiled as ordinary x86-64; host gcc 11, no sysroot;
log kept from the first configure of run 862) gives:

| class | count | what |
|---|--:|---|
| layout asserts that fail | 411 unique lines (13 396 errors over 216 of 986 units) | 56 headers: input.h 33, race.h 28, audio.h 27, gadget.h 26, modeproc.h 21, gfxlib.h 19, window.h 16, course_objects.h 16, dnode.h 15 ... plus os_thread / os_message / os_pi / os_vi / os_task. Every typed pointer member is 8 bytes and shifts what follows; of the ~698 assert lines in the tree, 411 fire |
| `-Wint-to-pointer-cast` | 2 468 unique sites | int-held pointers read back: `(T *)CALL(mem_new)(n)`, `(T *)*(int *)(p + K)`, `(Vec3 *)(unsigned)&local` |
| `-Wpointer-to-int-cast` | 866 unique sites (plus 304 inside the asserts) | pointers stored as ints: vptr / slot stores, `(s32)&X` arguments, `(int)packed` cursors |
| `T **` casts in src | ~790 (108 files) | `*(char **)(p + K)`: an 8-byte read of a 4-byte slot |
| typed pointer members | ~630 in include/, ~2 600 in src/ local structs (+ ~200 function-pointer members) | each is 8 bytes on LP64 |
| hard-coded object sizes | every ctor | `mem_new(0x1CC)`, cfront `if (this == 0) this = new(0x58)` |
| ROM data with 32-bit pointers | all blobs | USO Data / RoData relocated words (port/uso relocate() writes 4 bytes), cfront vtables {s16, s16, fn32} (PortCfVtEnt), PMFs {s16, s16, fn32} (PortCfPmf), shape arrays, node streams |
| the display list | Gfx = 2 x u32 | `gsSPDisplayList(addr)`, segment bases, `G_SETTIMG` addresses: 32-bit words by definition |
| host / port | ~30 sites | sysapi.c SLOT stores `(int)fn`, the fs handles, seqrender |

So full pointer-width conversion (option (b)) means retyping every pointer-bearing struct, rewriting every
raw offset and hard-coded size behind it (the asserts and the census raw-offset count say these are mixed
in the same structs), deserialising every blob type and widening the display-list words: the whole source
twice over, against a matching build that pins the 32-bit spellings. Rejected.

### 21.2 The design: the low-address model, with the game in the x32 data model

Two separate facts make (a) work without touching those sites:

1. **Every address the game sees is below 2 GB.** The executable is non-PIE (text, data, bss and the
   blobs at 0x400000+), the heap is glibc's brk heap (`mallopt(M_MMAP_MAX, 0)`, which starts after
   .bss), the game's stack is mapped `MAP_32BIT`, and so are the shm / mmap regions it reads. The game's
   own arena (sysapi.c sArena) is .bss. Below 2 GB rather than 4 GB because the int-held pointers are
   signed (`(T *)(s32)x` sign-extends).
2. **Every pointer the game stores stays 4 bytes:** the game and every port unit that shares its structs
   are compiled with gcc's `-mx32`. x32 is x86-64 code (64-bit registers, SSE, the SysV register
   convention) with the ILP32 data model: `sizeof(void *) == sizeof(long) == 4`. Struct layouts,
   cfront vptrs, PMFs, the blob words and the Gfx words are the N64's, exactly as in the i386 build.

What is NOT used is the x32 *runtime*: no x32 libc, no x32 kernel syscalls (most distribution kernels have
them off). cc-select.py compiles each `-mx32` unit to assembly and assembles it as an ELF64 object
(`-m64`; a 32-bit address register gets the 0x67 prefix, `.long sym` becomes R_X86_64_32), so the
objects link into an ordinary x86-64 executable against the system's x86-64 glibc. The executable runs on
any x86-64 Linux, no sysroot.

Evidence (run 862):
- The game library compiles with **0 errors** under `-mx32` (all 698 layout asserts hold; the LP64
  build fails 411). One link error: `pi.c` let gcc fold `sSram - 0x8000000` into an immediate (a 32-bit
  wrap that ELF64's R_X86_64_32 rejects); fixed in the shim. No game site has one.
- `test_ultra`, `test_fs` (107 checks), `test_backup` (24) pass as 64-bit executables.
- `tenshoe` (ELF 64-bit) boots: the boot path, port/uso relocation (4-byte host words), SysApi,
  the kernel threads, the first GameFlow mode, until the varargs class of 21.5 (ScreenWindow_ctor).
- Option (a) without x32 (LP64 code in a low arena) would make the 3 300 cast sites correct but leave
  every typed member 8 bytes: the 411 asserts. clang / MSVC `__ptr32 __uptr` would narrow members per
  declaration (tested with clang 14 on Linux: data pointers become 4 bytes with zero-extension at each use;
  function-pointer members do NOT, they stay 8), at ~3 400 declarations plus every `T **`. x32 does all
  of that by the data model, with no source annotation.

Limits, for the platforms after Linux:
- x32 is a gcc / clang ELF target. Windows (COFF, MS x64 convention) and macOS (Mach-O; arm64 has no
  ILP32 mode and forbids mappings below 4 GB) need another mechanism: there `__ptr32` (clang / MSVC)
  on x86-64, or base-relative 32-bit pointers, is the fallback, and it pays the annotation cost above.
  The x32 build defines the work for that: the layout asserts are the checklist, and the libc boundary
  (21.4) is the same list.
- The 32-bit pointer values are host addresses, as on i386: the display list still holds host pointers
  (port_gfx / Fast3D read them), so nothing in the renderer changes.

### 21.3 The build (`-DPORT_64=ON`)

    cmake -S port -B <b> -G Ninja -DPORT_64=ON -DPORT_LINK=ON -DPORT_ROM=<rom>     # no toolchain file
    cmake --build <b>                                    # tenshoe, seqrender, test_* : ELF 64-bit

- PORT_ARCH_FLAGS: `-mx32 -fcf-protection=none -fno-stack-protector` for C / C++ (no `-malign-double`:
  x32 aligns u64 / f64 to 8 already); `-isystem port/include/x32` supplies an empty `gnu/stubs-x32.h` and
  `-isystem /usr/include/x86_64-linux-gnu` (PORT_X32_SYSINC) the multiarch headers, so the units that
  include libc headers parse them for x32. PORT_DEFS gains `PORT64`.
- cc-select.py: an `-mx32` unit is always compiled via assembly and assembled `-m64`; `.init_array` /
  `.fini_array` / `.ctors` / `.dtors` entries are widened from `.long` to `.quad`.
- `-fcf-protection=none`: the x32 `.note.gnu.property` is 4-byte aligned, which ELF64 ld reports as
  corrupt. `-fno-stack-protector`: the x32 canary is at `%fs:0x18`, glibc's x86-64 one at `%fs:0x28`.
- `host/main64.c` + `host/x32_glue.c` (porthost64) are the only LP64 units. main.c / the test mains are
  compiled `-Dmain=port_main`.
- The default 32-bit build is unchanged (PORT_M32 = -m32; every PORT64 edit is `#ifdef PORT64`).

### 21.4 The entry and the libc boundary

`host/main64.c` (LP64): `mallopt(M_MMAP_MAX, 0)` and `M_ARENA_MAX 1` (every malloc from brk, below 2 GB);
argv and environ copied into that heap (argv as an array of 4-byte pointers); stdout / stderr replaced by
`fdopen` FILEs from that heap (x32 code reads the low half of the 8-byte variables); a 64 MB `MAP_32BIT`
stack entered with `swapcontext` (x32 code computes `%esp` in 32 bits: on the kernel's stack at
0x7ffc... the first `sub $n, %esp` would truncate rsp); a fault reporter (rip / rsp / backtrace; no
gdb on this machine). Each step aborts with a message if an address is not low.

x32 code calls the x86-64 glibc directly. That is safe for integer / pointer arguments (they arrive
zero-extended), for returned pointers that are low (malloc / fopen / strdup from brk), and for the
kernel-facing structs x32 laid out like LP64 (`struct timespec`, `off_t`). The calls whose memory
layouts differ are wrapped at link time (`-Wl,--wrap=`, PORT64_WRAP; the list is the link's undefined
libc symbols of run 862, audited one by one):

| wrapped | why |
|---|---|
| `__vfprintf_chk`, `__vsnprintf_chk`, `__vsprintf_chk`, `vfprintf`, `vsnprintf`, `vsprintf` | va_list is {u32, u32, ptr, ptr}: 16 bytes on x32, 24 on LP64 (the register save area and the 8-byte overflow slots are the same psABI, so the conversion is exact) |
| `strtol`, `strtoul`, `strtod` | `char **endptr` would get 8 bytes in a 4-byte slot; the long result is 32-bit |
| `fseek`, `sbrk` | 32-bit long arguments (sign-extended) |
| `__errno_location` | the TLS errno is above 4 GB: a low copy refreshed at each call |
| `mmap` | an unhinted mapping (port_live's shm) lands high: `MAP_32BIT` |
| `sigaction` | 4-byte handler / restorer |
| `backtrace`, `backtrace_symbols_fd` | arrays of 4-byte pointers |

Not wrapped, by audit: memcpy / str* / qsort (pointers in, low pointers out), fopen / fread / fwrite /
fclose / fflush / fgets / fputc / setvbuf, printf / fprintf / snprintf / sprintf / sscanf (variadic:
pointers arrive zero-extended; no `%ld` / `%zd` store sites in the port), clock_gettime / nanosleep,
mkdir / open / close / write / getpid, mincore, exit / abort / _exit, sqrtf. A new libc call in an
x32 unit needs the same check: does it take or return a pointer-to-pointer, a long by reference, a
struct with pointers or longs, or a va_list?

### 21.5 Varargs: the one ABI difference inside the game

The game's varargs functions walk their arguments in memory, MIPS style: a cursor from the last named
parameter's home (`(((int)((char *)&a0 + 4)) + 3) & ~3`), 4-byte slots, doubles 8-aligned. i386 cdecl
puts every argument on the stack in order, so the walk works there by construction. On x86-64 the
variadic arguments arrive in registers and `&a0` is a spill slot: the walk reads garbage. 13 variadic
definitions are compiled (dbg_printf x2, gl_sprintf, gl_osSyncPrintf, gl_rmonPrintf, sys_fatal x2,
sys_sprintf_00061B30, TextWin_printf, sys_printStub_00067AE8, uso_nullPrintf, ScreenWindow_ctor,
snd_SetPlayer0ChannelParams_2F9D4), plus 4 `((int *)&aN)[-1]`-style neighbour reads.

The convention under PORT64 (`port/ultra/va_pack.c`):
- a printf-family function packs its arguments with the standard va_list into an IDO-layout buffer
  (`port_va_pack_printf`: the types come from the format) and passes the buffer as the cursor, as the N64
  did (dbg_printf, run 862);
- the shim's `_Printf` turns an IDO-layout cursor back into an x86-64 va_list (`port_va_from_ido`:
  each argument in an 8-byte overflow slot, gp / fp offsets exhausted) for vsnprintf;
- sys_fatal already used `__builtin_va_list` under PORT.

**Next (run 862 stops here):** ScreenWindow_ctor's command list (`Node_runCommandArgs_00038C70(a0, a1,
cursor)`: tag / value pairs, 0-terminated) needs a packer driven by the Node command arities (the
doCommand table: which tags take a float, which a pointer); then TextWin_printf, gl_sprintf (its
`((int *)&a2)[-1]`), sys_sprintf_00061B30, the snd varargs. The boot reaches `sys_fatal("no
ScreenWindow for zbuffer")` (the string also comes out word-swapped: the %s argument of the fatal path is a
blob string, to check when that path is fixed).

### 21.6 After the boot

- The gate: a `build64` step (configure + build + test_ultra / test_fs / test_backup as 64-bit) once the
  smoke run passes, then the M6 exit check: the race / modes / replay traces bit-identical to the i386
  build (same float code: both are SSE scalar with `-ffp-contract=off`; the i386 build's
  `-malign-double` is what x32 does natively).
- In-process presenter: a 64-bit game can link Fast3D / SDL / X11 directly (`-DPORT_GFX_FAST3D=ON`
  without `-m32`). Those libraries are LP64 and read game memory (display lists, textures, the framebuffer)
  through host pointers that are low; the port_fast3d entry points are the boundary and get the same
  audit as 21.4 (no structs with pointers passed by reference across it, or a converter).
- abi-scan.py reads DWARF: the x32 units' DWARF has address size 4 inside an ELF64 file (ld warns
  "mangled line number section" on a few units; addr2line still resolves functions). Check before
  pointing the ABI step at the 64-bit binary.

### 21.7 Run 863: the 64-bit tenshoe runs the title demo (2000 frames); the trace diverges at frame 223

State at the end of run 863 (agent-g): the `-DPORT_64=ON` tenshoe boots to the title, starts the attract
demo and runs the smoke's 2000 frames (rc 0, every frame in state.log). Its state.log equals the i386 one
through frame 222 (the boot, the title, the demo's setup); at frame 223, the first physics step, the rider's
quaternion differs (position equal), and the CPU rider then drifts (32 % of the course at 2000 instead of
~75 %). The M6 exit check does not hold yet.

The fixes, by class (all `#ifdef PORT64`, the ROM and the i386 build unchanged):

1. **The rest of the varargs (21.5).** `port/ultra/va_pack.c`:
   - `port_va_pack_cmds`: ScreenWindow_ctor's Node command list, driven by a small table of word counts
     per tag, taken from the handlers: Node_doCommand (the ROM's jump table: 0x64 / 0x65 / 0x67 / 0x6C,
     1 word each) and Window_doCommand (the ScreenWindow / Window vtable slot 6: 0x6D / 0x70 / 0x71 /
     0x73 / 0x74 / 0x75 one word, 0x6E origin and 0x6F size two). Every argument is int-class: the
     int-to-float arms read an int and convert it, and the three callers pass ints. A tag outside the
     table is reported and packed as one word. MNode_doCommand / QNode_doCommand are not on this path
     (Window_doCommand's default goes straight to Node_doCommand), and no other variadic takes a
     command list.
   - `port_va_pack_printf_after`: the printf packer with leading named int words, for
     `gl_sprintf(buf, fmt, a2, ...)` (its `((int *)&a2)[-1]` neighbour read is the format). TextWin_printf
     and sys_sprintf_00061B30 pack like dbg_printf.
   - The other variadics are empty stubs (gl_osSyncPrintf, gl_rmonPrintf, sys_printStub_00067AE8,
     uso_nullPrintf, dbg_printfNop), sys_fatal already used `__builtin_va_list`, and
     snd_SetPlayer0ChannelParams_2F9D4 is compiled from its non-variadic import.
   - The neighbour reads: ProcNodeList's `((NodeListState **)&a0)[3]` (it is `a3`).
   - **The word-swapped fatal ("no SeercWnnidow for zbuffer")** was not byte order: the bytes in the
     extracted Data are right; the garbage command list (a set-global / name tag with a stack word as the
     argument) had overwritten words of the string blob. Gone with the packer.
2. **By-value structs that the two sides size differently.** nodelist_dispatchList_000558A0 /
   nodelist_walk_0005534C declare a 16-byte `{pp, w, x, y}` and read the rest of the caller's 0x4C-byte
   NodeListState through `&s`. MIPS and i386 put the whole struct in memory either way; x86-64 passes a
   16-byte struct in two registers and a 0x4C-byte one in memory, so the callees declare the full size
   under PORT64.
3. **O32 float bits in integer registers.** On MIPS a float argument after an int one rides in an
   integer register, so the matched C declares it `int` and passes the bits; i386 cdecl puts both in the
   same stack slot. x86-64 passes a float in a vector register whatever its position. `include/uso_call.h`
   gains `PORT64_FT` (the parameter type, `float` under PORT64, `int` otherwise), `PORT64_F(x)` (int
   bits passed to it) and `PORT64_I(x)`. Fixed: math_det3x3 (all floats under PORT64: the
   "Non-singular matrix" fatal), cam_ctor_00000858 + its MCamera_ctor alias, cam_isSphereInView's three
   int-declared callers, SnowBCollider_ctor + Friction_ctor, CollObj_initCylinder, the QNode_ctor
   `0.0` double (x and y in a2 / a3 on MIPS, three floats on x86-64), AnimPlayer_setBlend (every caller
   passes bits: the definition takes the int under PORT64), anim_blendPose, SnowBoarder_yawPiOver,
   CamFollow_update's absrot_matrix4 / math_mtxRotateAxis. A K&R `CALL(f)` cannot pass a float (it
   would be promoted to double): those sites call a prototyped asm-name alias
   (`extern void port64_absrot(void *, int, float, int) __asm__("absrot_matrix4")`), with the ROM's
   `CALL` kept in the `#else`, so the gate's named-call check still sees one call per site.
4. **Small struct returns.** x86-64 returns a struct of up to 16 bytes in registers (xmm0:xmm1 for
   three floats); i386 and MIPS use the hidden pointer. The C++ callers of cam_toTargetLocal_000023D4
   (whose C definition takes the explicit out-pointer) call it through an inline wrapper, and
   SnowAI_steer calls SnowAI_aimWeave (C++, returns XZ by value) by value, as it already did for
   SnowAI_aimAlongSegment. Structs over 16 bytes are the hidden pointer in rdi, which is the C side's
   explicit out-pointer: no change.

**`port/tools/abi-scan.py --x64`** (new): the x86-64 version of the ABI check. It drops the i386-only
classes and adds X64Pn (a prototyped declaration's parameter class differs: int / pointer against float,
float against double, structs) and X64REG (the caller loads an argument register, from DWARF
`DW_TAG_call_site_parameter`, that the definition does not read; extra integer registers alone are
trailing K&R arguments and pass). SRET is kept only for structs of 16 bytes or less. At the end of run
863 (commit 776bdfb9d): 38 X64P + 12 X64REG + 2 VRET, counted by the gate step. Left: AudioThread_QueueCmdF32 (6 callers
pass a float, the definition takes the int bits), snd_SetPlayer0ChannelParams_2F9D4 / snd_ScheduleSeq /
snd_UpdateChannel10Emitter, the CourseGadget_setVec4 / setFloat2 DataManager family (5 USOs),
math_perspectiveF from Window_setupView, gui_drawStringScaled, hostio_addFloat, light_setF124,
Obj::setLights, math_arcballPoint (struct12 against floats), and a few false positives (a caller that
passes an extra pointer: math_quatRotateAxisAngle). The scan does not see indirect calls (vtable slots,
function pointers): a float passed through a slot typed `int` is invisible to it.

**The gate step** (`scripts/port-gate.sh`, `build64`): configure + build 64-bit from a fresh dir, run
test_ultra / test_fs / test_backup as 64-bit, the same smoke, compare its state.log with the i386
smoke's (the `/N` host address after r0's fields dropped), and run abi-scan --x64. It is **report-only**:
the line is INFO and never counts as a failure, until the traces match; then it becomes PASS / FAIL on
divergence (and on the race / modes scripts). `PORT_GATE_BUILD64=0` skips it (it adds a full build,
~15 s with a warm compiler cache, a few minutes cold). Commits: c980ff055 (abi-scan --x64, the
step), 776bdfb9d (the fixes); the landing gate passes (3579/3579, port gate PASS with build64 INFO).
Seen once: the gfx step failed in a fresh PORT_GATE_TMP (`No rule to make target .../f3d-obj/lus/gfx_opengl.o`,
port/gfx/fast3d/Makefile); it passed on the next run. A parallel-make race in a fresh dir, unrelated to M6.

**Next:** the frame-223 divergence. The rider's quaternion differs on the first physics step with the
position equal, so the orientation path (SnowBoarder_updateOrient, the QNode / DNode quaternion code,
the collider normals) receives a wrong float somewhere: finish the abi-scan --x64 list first, then hunt
the indirect calls (vtable slots with float parameters: the cfront `CF_V*` slot types and the
`VT_SLOT(...).fn` casts whose prototype says `int` where the method takes a float). A per-function trace
diff (state.log fields at a finer grain) would localise it faster than reading. Then the race / modes
scripts, then the in-process Fast3D path (21.6; not tried in run 863).

### 21.8 Run 866: the M6 exit check holds; build64 is a pass / fail gate step (agent-g)

The x86-64 tenshoe's state.log equals the i386 one line for line (the RiderAnim state method's `/N` host
address dropped) for the smoke (2000 frames), `race_crystal_lake.input` (race, View Replay, ghost reload)
and every modes script (trick, contest, training, vs2p, match + reload, options + reload): 11/11 logs.
Commits e31aa1899 (the tool), 6d7bba1ee (the fixes, the gate step).

**Float mode: no change needed.** The i386 build was already `-msse2 -mfpmath=sse -ffp-contract=off`
(PORT_ARCH_FLAGS), and x32 is SSE scalar too, so both builds do the N64's float32 IEEE arithmetic. The only
libm call left in either executable is `sqrtf` (correctly rounded). An i386 float return travels in x87
st(0) but a float load / store through it is exact. So the race / modes scripts did not need regenerating.
Every divergence was an ABI bug, never precision.

**The tool: PORT_TRACE_FN** (`cmake -DPORT_TRACE_FN=ON`, diagnostic only, off by default):
- The game library is built `-pg -mfentry`. `__fentry__` in port/trace.c is asm that saves every
  caller-saved register. For one frame (`PORT_TRACE_FN=<frame>`, file `PORT_TRACE_FN_OUT`, default fn.log)
  it logs each function entry with:
  - the stack depth;
  - an FNV hash of rider 0's SnowBoarder, with pointer-looking words (0x100000..0x10000000) skipped, or of
    the first argument of a chosen function (`PORT_TRACE_FN_OBJ=<addr>:<size>`);
  - the raw arguments: on i386 the first 6 stack words, on x86-64 rdi..r9 and xmm0-3.
- `port/tools/fn-trace-diff.py binA logA binB logB [--args]` names the addresses (nm) and prints the first
  entry where the call sequence or the hash differs, with its context.
- Why not `-finstrument-functions`, which was tried first:
  - Its exit hook's argument pops clobber eax. Matched `void` wrappers whose callers read the result their
    last call left in eax/v0 (item_createHel and family) then crash.
  - In C++, the instrumented inline members take their own address. g++ then emits or calls out-of-line
    copies whose placeholder tokens no port-bind covers, because binds are per function label.
- cc-select.py now treats a numeric local label (`1:\tcall __fentry__`) as part of the body.
- The workflow:
  1. Rebuild both builds incrementally.
  2. `PORT_TRACE_FN=<first divergent frame>`.
  3. Read the first differing entry.
  4. If the hash already differs at event 0, move the object (`PORT_TRACE_FN_OBJ`) or bisect the frame.
  Each step takes about 30 s.

**The divergences, in order found** (all `#ifdef PORT64`; ROM and i386 unchanged; matching gate 3579/3579):
1. **Frame 223, rider quaternion.** DNode_applyAccums_00065448 called DNodeAccum_apply_00064388 (an NCC
   donor taking `float`) through K&R `CALL` with `*(int *)&tsc.value`. The bits went in rcx, and the callee
   read xmm0. abi-scan's X64REG could not see it: DWARF `call_site_parameter` omits a register loaded from
   memory. The new **X64KR** class (a K&R call to a definition with a float parameter) lists 10 more.
   The fix uses the new `PORT64_CALLP(T, f)` in include/uso_call.h, which calls f through a prototyped
   asm-name alias.
2. **Frame 471, rand state.** Run 863 made AnimPlayer_setBlend take the weight's int bits under PORT64,
   but three C++ callers (RiderAnim_stateRide / stateRideDeep / statePreJumpHold, through
   `import_0010DB78`) pass a float. Under PORT64 they now pass the bits (`SETBLEND_ARG`). Also fixed:
   SNode_handleMsg's three absrot_matrix4 angles (bits to float).
3. **trick / contest crashed at step 1503.** PointsGadget_display passed gui_drawStringScaled's scaleX as
   bits: str_len got a garbage pointer.

**Gate:** `scripts/port-gate.sh` build64 now runs after modes. It covers the build, test_*, the 64-bit
smoke, and race-check / modes-check run 64-bit (`RUN32=env`; race-check now honours RUN32 like
modes-check). Every state.log must equal the i386 run's. It reports **PASS / FAIL**. The abi-scan --x64
count stays INFO: at the end of run 866 it is VRET 2, X64KR 10, X64P 33, X64REG 9. Landing gate: PASS
(3579/3579, port gate PASS including build64 PASS, 19 s).

**Left (no effect on any trace; render / audio / debug paths):** the rest of the abi-scan --x64 list:
- AudioThread_QueueCmdF32: the float-typed `_f` callers, while the definition takes the bits;
- the CourseGadget_setFloat2 / setVec3 / setVec4 HUD setters: callers pass the bits, some mixed with
  floats in one call;
- math_perspectiveF (Window_setupView), Obj::setLights (Mat_draw), gfx_selectLights, light_setF124 (x2);
- hostio_addFloat, math_arcballPoint;
- snd_ScheduleSeq / snd_UpdateChannel10Emitter / snd_SetPlayer0ChannelParams;
- the 2 VRETs.

These need per-site `PORT64_CALLP` edits (or `PORT64_I` for an int-bits definition). Wrong render floats
show in the gfx dump, not in state.log: a 64-bit `PORT_GFX_DUMP` against the i386 one would gate them.
Indirect calls (vtable slots with float parameters) are still invisible to the scan. PORT_TRACE_FN's
`--args` view shows them when a trace diverges.

### 21.9 Run 868: the native single-process 64-bit game (agent-g)

Commits on agent-g: 4d4860454 (render ABI fixes, dlump-cmp, the build64 gfx check), 2749af51d (the native
game). Landing gate: 3579/3579, clean build OK; port gate PASS (build64 PASS: 11/11 state.logs, gfx 8/8).

The `-DPORT_64=ON -DPORT_NATIVE=ON` tenshoe, run with `PORT_NATIVE=1`, is the whole game in one process.
It renders with Fast3D in process, opens its own X11 + EGL window, plays its own audio and reads the
keyboard / gamepad itself. There is no presenter, no shared memory and no i386 sysroot.

    port/tools/play.sh --native [-s SCALE] [-m] [-l MS] [-V] [-S] [-b BUILD] [-- tenshoe args]

play.sh configures and builds `tools/play/<worktree>/build-native` on first use. The presenter path is
still the default and the fallback. `-V` turns vsync on.

**Architecture.**
```
 x32 game (port_gfx.c, port_live.c)            | LP64 host (libport_native.a), u32-only calls (gfx/port_native.h)
   port_gfx_task -> native_task ---------------+-> port_native_task: the step's request snapshot; port_fast3d_queue
                                               |     (lists widened now, offscreen test, G_SETTIMG list, images)
   step end -> port_live_frame_end ------------+-> port_native_frame: port_fast3d_step = presenter Renderer::frame
                                               |     on game memory (offscreen pass + RTT store, one chained Run,
                                               |     depth / colour answers into a LiveFbReply), EndFrame = swap
   host_poll_events -> port_live_quit ---------+-> port_native_poll: live_pump (X events), pads -> header
   host_read_pads <- LiveShmHeader.pads   <----+   (the block: header + LiveAudio ring + LiveFbReply, MAP_32BIT)
   audio sink -> port_live_audio_write -> ring +-> live_audio.cpp thread (unchanged) -> PulseAudio
   port_live_fb_apply <- LiveFbReply      <----+
```
- **Shared, not duplicated.**
  - The presenter's window, Fast3D backend and input code moved into `gfx/fast3d/live_window.{h,cpp}`
    (LiveX11, LiveInput, live_pump) and `live_backend.h` (LiveWindow). presenter.cpp uses them
    (`using Win = LiveX11`).
  - live_audio.cpp and live_shm.h are untouched. The native host lays out a LiveAudio ring and calls
    `live_audio_start` as the presenter does, so agent-a's audio work applies to both.
  - port_live.c reads the native block with the same code that reads the presenter's files: pads, quit,
    the audio ring and `port_live_fb_apply`.
- **The boundary.** The game side is x32 and the host is LP64. The calls take only u32 values (a game
  address is below 2 GB). The request struct is read in its ILP32 layout, which port_gfx.c checks with a
  size assert. The shared memory is live_shm.h, whose fields are all 4 bytes.
  - The link's `--wrap` list (21.4) would send the host's own libc calls (strtol, mmap, __errno_location,
    ...) through the x32 converters. CMake therefore runs `objcopy --redefine-syms` on libport_native.a so
    that those references go to `__real_<f>`.
- **Frame model (port_fb.h).** The framebuffer model now runs in process. Each step's tasks are composited
  into one frame, because every Run clears the window, so one Run per task would show only the last
  task. The game's depth / colour read requests ride on that Run. Patch 0003 answers them:
  - each depth pixel together with its ±6 window;
  - the colour images the frame drew into.

  The answers land in the LiveFbReply, which the game takes at its next task, one step later (the N64's
  latency). Render-to-texture tasks are drawn first, read back, and stored at the full address that the
  onscreen tasks' G_SETTIMG gives (the presenter's rule). If no task gives one, the address is the single
  registered mapping that holds the image.
- **Pacing.** main.c's `--realtime` loop is unchanged: a fixed 30 Hz step, real time, catch-up cap 4.
  Every step that has tasks renders and presents. The swap interval is 0 by default (frames are shown as
  the step makes them); `PORT_NATIVE_VSYNC=1` / `play.sh -V` sets it to 1. Without `--realtime` the steps
  run back to back and each one still renders (verification runs).
- **Two process fixes (host/main64.c, PORT_NATIVE builds only).** The process re-executes itself once with
  `personality(ADDR_NO_RANDOMIZE)` and `GLIBC_TUNABLES=glibc.malloc.arena_max=1:glibc.malloc.mmap_max=0`.
  - Opening the window mallocs about 280 MB from the brk heap. With the 64-bit kernel's 1 GB brk
    randomisation, the heap could reach the MAP_32BIT region at 0x40000000. brk then failed and glibc fell
    back to mmap, which returns high memory. x32 code truncated that pointer and crashed in fgets on
    `fopen`'s FILE in port_audio.c read_maps: 1 run in 3 crashed, 0 in 12 after the fix.
  - The arena limit has to apply before the first malloc, so it is set as a tunable as well.
- **Exit.** If the audio thread is blocked in PulseAudio (19.14's open stall), `live_audio_stop` would hang
  in its join. The native close therefore stops the thread from a helper and waits at most 2 s; if the
  thread is still blocked, the process `_exit(0)`s at exit after the game's own teardown.

**Verified (WSLg, D3D12 on the AMD GPU).**
- **Frames.** The native window PNGs (`PORT_NATIVE_PNG`) are byte-identical to f3dreplay `--then` of the
  same run's PORT_GFX_DUMP for 11 steps:
  - attract demo: 300, 580, 1000, 1500, 1900;
  - Crystal Lake race script: 1500, 2250 (sun), 3000, 4700 (goal), 7000, 9000 (replay).

  The name-entry board shows the replay (render to texture in process: 489 RTT passes, 885 colour images
  served).
- **Scripted input.** `--input race_crystal_lake.input`:
  - native, 9800 frames: state.log identical to headless;
  - native `--realtime`, muted, 700 frames: identical except vi;
  - realtime with audio, 900 frames, `PORT_AUDIO_DAC=0` and default: identical.

  One unmuted realtime run diverged at frame 561 (flow 0,3,1 against 0,1,1). With the presenter's
  wall-clock DAC model (19.12) and PulseAudio stalling, the audio driver's buffer sizes follow real time,
  and the title flow waits on audio. This is not native-specific. Determinism checks use
  `PORT_AUDIO_DAC=0` or no `--realtime`.
- **Smoke state.log.** Native, 2000 frames: identical to the headless 64-bit run, which equals the i386
  run (build64).
- **Audio.** The audio reaches PulseAudio: the game-side and host-side FNV hashes are equal. Only
  1.45 s of 4.39 s played, though, because of the open PulseAudio stall that agent-a is working on (run
  867); the presenter has it too.
- **Frame times.**

  | run | render ms (mean / p50 / p95 / p99 / max) | frame interval ms (mean / p50 / p95 / p99) |
  |---|---|---|
  | 640x480, realtime race script, 1800 steps | 5.68 / 4.97 / 9.50 / 13.94 / 99.6; 8 over 33 ms | 33.26 / 33.30 / 36.02 / 40.22; 7 over 50 ms |
  | full race, 9800 frames as fast as possible | 5.67 / 4.73 / 14.28 / 20.01 / 86.7 | not paced |

**ABI fixes (render), all `#ifdef PORT64`, ROM / i386 unchanged.** The 64-bit attract demo drew upside down
(f3dreplay of the 64-bit dump against the i386 one). Fixed:
- `math_perspectiveF` from Window_setupView: fovy / aspect / near went as int words (X64P1-3), now
  `PORT64_CALLP` with floats;
- Obj::setLights from Mat_draw (`gfx_emitLights_000454C4`, k): an asm-name alias;
- gfx_selectLights_000478FC from LightTarget_display (scale);
- light_setF124 from SelCharacter_display (B624) and SelCourseMap_display (B368).

After these, the smoke's gfx at steps 300 / 1000 / 1500 / 1900 equals the i386 dump (8/8 tasks).

**Gate.** `port/tools/dlump-cmp.py A B` compares two PORT_GFX_DUMP dirs per task with the address operands
masked. The smoke (i386) and smoke64 runs now dump `PORT_GATE_GFX_STEPS` (default 300,1000,1500,1900), and
build64 fails if they differ. The native build itself is not gated (it needs tools/lus + x11-dev).

**Left.**
1. abi-scan --x64, not yet done: the CourseGadget_setFloat2 / setVec3 / setVec4 HUD setters (h2h / mgr /
   tim / arc / trk DataManagers, hud_addCourseGadget); AudioThread_QueueCmdF32 (the XCALL float callers:
   8 sites; the K&R CALL callers pass the bits correctly); snd_ScheduleSeq / snd_UpdateChannel10Emitter /
   snd_SetPlayer0ChannelParams; math_arcballPoint; hostio_addFloat. The HUD ones need a race / mode gfx
   step in the dlump comparison (the smoke has no HUD gadgets).
2. Make native the play.sh default once the audio stall is fixed.
3. FB_WRITE (CPU rectangles, debug only) is still not composited in process.

### 21.10 Run 870: native audio verified, native is the play.sh default, the float-ABI list closed (agent-g)

Commits on agent-g: c4fa8c492 (native audio check, play.sh default), 47d58a653 (the ABI fixes, the gate). Landing gate:
3579/3579, ROM byte-identical, clean build OK; port gate PASS (build64 PASS: 11/11 state.logs, smoke gfx 8/8, race
gfx 8/8, race audio identical to about step 6346 (INFO after), soak64 0 hard / 1 soft); presenter and native tenshoe
build.

**Native audio.** `port/tools/audio-check.sh --native` (`make -C port/gfx/fast3d audio-check-native`) runs the
Match Race script (3300 steps, `tenshoe --input`, realtime) in the native game with
`PORT_NATIVE_AUDIO_STATS=1` and applies the presenter check's verdict (played / received-while-open >= 95 %,
>= 30 s received while open). The native host opens its window, then `live_audio_start`; live_audio's
`openDelayMs` (2500, run 867) counts from there, so PulseAudio opens 2.5 s after the map, as WSLg needs.
`PORT_NATIVE_AUDIO_OPEN_DELAY=MS` overrides it.
- D3D12 (AMD) run: **PASS, 99.7 %**: received 109.42 s, 2.55 s before the open, 106.54 s played, 0.33 s
  trimmed, 1 underrun, 0 game overruns. Render mean 18.2 ms / p95 45 ms (the GPU was shared with other
  agents' runs; run 868 measured 5.7 ms).
- The first try came up on **llvmpipe** (Mesa fell back from D3D12 on that one start; the next 3 starts got
  D3D12). At 134 ms a frame the window traffic stalled WSLg's PulseAudio as a map does: 16.9 s of 99.6 s
  played, 80 s trimmed, and the audio thread was still blocked at exit. If a run is slow and silent, check
  the `native: ... EGL` line for llvmpipe and restart. The native close now prints the `audio-stats:` line
  itself when the audio thread is abandoned (`live_audio_stats_line()`), so the check always has a verdict.

**play.sh default = native.** `port/tools/play.sh` now runs the native game. `--presenter` is the fallback
(the 32-bit tenshoe + presenter; `-n` / `-p` apply to it only), and `--native` is still accepted.
audio-check.sh's presenter mode passes `--presenter`. Verified: frames and state.log (run 868), scripted
input (run 868 and this run's audio check: the script's 3300 steps), audio (above). HANDOFF step 9 updated.

**The abi-scan --x64 list (all `#ifdef PORT64` or identity outside it; ROM 3579/3579, i386 unchanged
except one C++ fix below).** Count on the native tenshoe: 55 lines -> 11. The 11 left are 8 prism / libstdc++
template SRET / VRET false positives, the 2 known VRETs (RaceTracker_onCheckpoint -> PointsPopup_setPosScale,
tim_drawTime -> gui_spriteRefresh), and SnowBoarder_updateOrient's trailing K&R argument (harmless).
- **New: `PORT64_BITS(t)` / `PORT64_BV(p)` (include/uso_call.h).** Under PORT64 (C only) the type is a GCC
  `transparent_union { int; float; }`. A parameter of that type is passed as its first member: in an integer
  register, with the bits, whether the argument is an int or a float.
  - **On a token's declaration**, it lets a float-passing site reach a callee that takes the bits, without
    touching the site.
  - **On a definition**, the callee reads the bits from the integer register. That suits a float setter
    whose O32 callers mostly pass `*(int *)&f` through K&R CALLs.
  - Outside PORT64 it is the given type, so the ROM build and i386 are unchanged.
- **`PORT_IBITS(x)`** is for C++, which ignores transparent_union. It passes a float's bits to a
  decls_cpp.h `int` parameter.
- **AudioThread_QueueCmdF32** (definition `(int, int)`, the bits). Every float-passing alias now takes
  `PORT64_BITS(float)`:
  - `gl_func_00000000_f` in game_libs_post.c (4 declarations) and game_libs_o2_2FB74.c;
  - gl_E354_setf, gl_2F288_emit_float, gl_2F9D4_float;
  - gl_E354_emitf's 4th argument (snd_SetPlayer0ChannelParams_2F9D4 takes the bits too).
  The two C++ sites (game_libs_ncc_307A8 / 308AC) passed a float to decls_cpp's `(int, int, ...)`, which
  converted the VALUE (0.73 -> 0) on i386 as well. They now pass `PORT_IBITS(f)`. This is the one change to
  i386 behaviour: a volume / level command. The audio regress cases still pass.
- **CourseGadget_setFloat2 / setVec3 / setVec4.**
  - The definitions take `PORT64_BITS(float)`.
  - The float-typed aliases take it too: gl_func_00000000_e84c2/4, gl_func_15f0, gl_proto_1c94,
    timproc_b1's gl_proto_1c68, arcproc_import_187/188, mgrproc_uso_func_016BEC.
  - timproc_b3's gl_proto_1c68 is shared with PointsPopup_setPosScale, which takes real floats, so its
    setVec4 site uses `PORT64_CALLP` with the bits.
  - Checked in the disassembly: setFloat2 stores esi / edx; hud_addCourseGadget passes ints.
- **snd_ScheduleSeq**: the definition takes `PORT64_BITS(float)`. Both callers are K&R with the bits:
  - snd_dispatchEvent case 50 (`0x3F333333`);
  - **snd_ScheduleSeqAfter** (`0x3F800000`). abi-scan never listed this one, because it is a tail call
    (`jmp`) and the scan only looks at call sites.

  Its a3 is stored to D_2DDBC_d, which is the same word as D_2DE24_c / D_00000000_324: player 1's volume.
  On x86-64 that word held garbage after the race goal (0x0157dc73 instead of 1.0f), so the music played
  differently from 158 s in.
  - Found by logging every AudioThread_QueueCmd (a temporary `#ifdef PORT` fprintf, not committed) on both
    builds and diffing the two streams: the only difference was `0101ff00 3f800000` against `0101ff00 0157dc73`.
  - Lesson: the scan's blind spots are tail calls and indirect calls. The command-stream diff finds what
    they hide.
- **snd_UpdateChannel10Emitter** (bootup_uso.c's snd_updateChannel10Emitter, snd_HandleSeqEvent_30AF4's 0.3f):
  `PORT64_CALLP` with `PORT64_F`.
- **math_arcballPoint**: BallRotator_applyArcball's PORT64 alias passes the two Vec3s as six floats (the
  definition's parameters; a 12-byte struct by value is not that on x86-64).
- **hostio_addFloat** (Spinner_hostioParms, `gl_proto_3787C`): the min is `PORT64_FT` / `PORT64_F(0xC0C00000)`.
- The context headers that now use these macros (context_game_libs_post / post0b / h2hproc_uso / mgrproc_uso /
  arcproc_uso_tail1.h) include `../../include/uso_call.h`.
- abi-scan does not judge a definition with a 1..16-byte struct parameter, so the transparent-union
  definitions drop out of its view. The gfx / audio comparisons below are what verify them.

**Gate (scripts/port-gate.sh build64).**
- race-check.py has new `--gfx-steps STEPS` (PORT_GFX_DUMP of the race run into race/gfx) and `--audio`
  (race/audio.wav) options.
- The i386 race step and build64's race64 both pass `PORT_GATE_RACE_GFX_STEPS` (default
  1800,3000,4700,7000: racing with the HUD, the goal, the View Replay) and `--audio`.
- build64 then requires the race gfx (dlump-cmp) and the race PCM (byte compare) to be identical.
- soak64 runs `--audio64`, and **x64-audio is a hard class** now.
- **x64-screen stays SOFT.** The gate64 seed 2 differs at step 842, flow 7's first frame. The cause is the
  light colours of 4 objects (ambient = diffuse: i386 ff / f7 / 7e, x64 50 / 43 / 49). Turning on
  PORT_GFX_DUMP flips the result in **both** builds (i386 with the dump gives the x64 hash, and the reverse),
  so this is an uninitialised read (stack contents), not a float ABI difference. Lead: Obj::setLights'
  ambient = `amb->col * s * 255 (* k)`, with s from gfx_selectLights' `scale * k`, on the first frame of
  flow 7.
- By hand (b32 / b64 of this tree):
  - race_crystal_lake.input to 3300 steps: identical WAV (f6210761); gfx at 1800 / 2250 / 3000, 6/6
    identical;
  - the full race-check run: gfx 8/8 identical;
  - the PCM is identical through the goal and into the View Replay, up to about step 6346. After that it
    differs, but the AudioThread_QueueCmd stream is identical through step 6500, so the cause is outside the
    command queue (seq-player / note state written directly, or a float in an indirect call).
  - agent-c's ~step-710 audio divergence is gone (the QueueCmdF32 sites).
  - The gate64 seeds' audio md5s are equal.
- So build64's race audio check **requires** identity through the goal + 60 steps. A later first difference
  is printed as INFO (`race audio: identical to about step N (goal 4708), then differ (INFO: after the
  goal)`).
- **The audio regress goldens (port/audio/tools/regress-golden.tsv): course0 and course1 are new.** These
  two cases render with the snd_TickChannel8Fade / 308AC fade. Before the PORT_IBITS fix, its level reached
  AudioThread_QueueCmdF32 value-converted (0 or 1 as float bits, i.e. silent), on i386 too.
  `make -C port/audio regress-update`; every other case is unchanged.

**Left.**
1. x64-screen: find the uninitialised light input on flow 7's first frame. PORT_TRACE_FN on the frame, or a
   watch on the LElem / scale fields.
2. The race PCM after about step 6346 (View Replay). The command queue is identical, so diff the seq
   players' / notes' float fields per step, or the soundObj calls (snd_SoundObjSetAngle(o, f32, s8),
   snd_calcEmitterDistPan) through PORT_TRACE_FN `--args`. Then make build64's race audio check whole-run.
3. The 2 VRETs.
4. abi-scan: follow tail calls (`jmp` to a function symbol) as call sites.
5. FB_WRITE in process (21.9).
