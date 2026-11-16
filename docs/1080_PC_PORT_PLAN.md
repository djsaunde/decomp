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
   update rate and decouple rendering from it. The original rate (VI-locked 30 Hz, or variable) is an open
   question. Measure it in an emulator in M0.
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
- The simulation rate.
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
