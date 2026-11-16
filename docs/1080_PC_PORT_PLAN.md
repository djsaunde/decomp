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
3. **Audio: reuse a CPU implementation of the OoT audio ABI.** The driver is OoT's (1080_AUDIO.md, "state
   for porters"). Ship of Harkinian already runs this exact synthesis-command ABI on the CPU. Keep the
   sequence player and synthesis code from the decomp. Replace the RSP task with a CPU mixer that consumes
   the same command list. Replace `osAiSetNextBuffer` with the host audio stream.
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

