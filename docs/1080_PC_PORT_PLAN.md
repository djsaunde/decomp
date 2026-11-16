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
  `--gc-sections`. It needs gcc-multilib, which this machine does not have yet.

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
5. **Link:** once gcc-multilib is installed, build with `-DPORT_LINK=ON`. The link errors should
   then equal `port/undefined.txt`.

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
6. **32-bit libc** (gcc-multilib) on the analysis machine, to link at all.
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
