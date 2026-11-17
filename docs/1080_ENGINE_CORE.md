# 1080: libgdl engine core, game_libs_post0b.c 0x4C000-0x62F08 (area E2)

> agent-b run 449, 2026-11-15, 1080 branch agent-b (commits 61632b485 [rename, 166], f98dbad64 [include/gdl/mem.h],
> bd5d39c26 [rename, 6]). The lower half of post0b (0x34458-0x4C000) is agent-a's area E1.
> agent-b run 454 (commits 8e1fc49b3 heap.h folded into mem.h, 6155f05d1/142fbf08c DLContext, b83fbfcac/fe3aca6ab
> RcpMgr/RcpTask + libultra/os_task.h, 3a4aff57a/6a4f5b06a BasePolyShape, 4dafc55ab tool, 7aca920fd [rename, 3], 116f79f43 [rename, 6]).
> agent-b run 458 (commits dc8e4f437 [rename, 62: vtable methods, RcpTask, reader templates], 1293c072a [rename, 37:
> libultra/libc tail], b844a9296 include/libultra os_pi.h / os_timer.h / os_cont.h + 5 donor migrations).
> agent-b run 463 (commits 973cf1d60 [rename, 130: AnimPlayer + post1b], be8429244 [rename, 164: post0b 0x4C000+],
> cd0bf1205 [rename, 30: pad / boot / str leftovers]). Scope now also covers game_libs_post1b.c (0x62F64-0x69CC4).
> agent-b run 468 (on 19f8e0b6f: e8c40fbf9 [rename, 50: the last game_libs placeholders], 8fbf9b82b [rename, 17:
> heap temp wrappers, agent-a's coll_/gfx_ position names], then 9 header-move commits b6f67ecbf..35a9a6469).
> agent-b run 476 (on 27eefe3af: f00df5e00 [rename, 52 gfx_], 9a27aa26d [include/gdl window.h / light.h / material.h /
> sprite.h, PolyShape + MorphPoly in polyshape.h], 54299fbde [DLMark / Window conversions], f15861371 [rename, 1]).
> The graphics pipeline now has its own port-author doc: docs/1080_GRAPHICS.md.
> Method: docs/1080_SYSTEM_LAYER.md section 1 (string xrefs through the bootup.uso reloc tables), plus the
> matched bodies' own decode comments, GBI command words and class-name strings.

## Index
- [1. Tooling notes](#1-tooling-notes)
- [2. Map](#2-map)
- [3. Structs](#3-structs)
- [4. Held back and next](#4-held-back-and-next)

## 1. Tooling notes

- agent-a's `xref_all.py` takes a function's offset from the `_XXXXXXXX` name suffix, so a renamed
  function drops out of the listing. For post0b, fall back to `0x34458 + report.json address`
  (the report address can be a few bytes off where a symbol starts on a merged head, so prefer the suffix).
- About 85% of this range is already decoded C with a descriptive comment above each function. Read
  the comment block before guessing from strings alone (the comments name matrix ops, GBI words, list shapes).
- Calls to `gl_func_000601D4` / `gl_func_0004DD14` in the xref are emu-symdump names of entries that
  sit 8 bytes before a merged symbol (memtrack_end, the 4DD0C pad). They are not separate C symbols.
- Very few game_libs vtables are visible through bootup DataReloc (only 3 words point into this range),
  so most `in:0` functions are virtual methods whose class has to come from the ctor that stores the vtable.
- **Vtable decoding (run 458).** The game_libs vtables live in the bootup.uso data section (DataReloc words
  resolved through the decompressed Sym section; agent-a's /tmp/claude-1000/a453/vt.py). Copy of the decoder
  with names taken from `mips-linux-gnu-nm build/tenshoe.elf` (game_libs symbol value = segment offset):
  /tmp/claude-1000/b458/vt.py + vtdump.py. Cfront layout: the ctor stores vtable address V at Node +0x28;
  slot k is {s16 delta at V+8+8k, fn at V+0xC+8k} (a call through slot k reads +0x18/+0x1C for k = 2).
  Node slots: 0 hostioParms, 1 0x38598 (list iterator), 2 display, 3 update, 4 handleMsg, 5 broadcastMsg,
  6 doCommand, 7-9 the 0x38B6C/74/7C empty stubs; 10+ are class-specific (named `<Class>_vfnN_<addr>`).
  Words at 0x20630/0x20638 are Cfront pointer-to-member triples (parm callbacks), not vtables.

- **jal relocs against bootup Sym 3 (run 468).** Sym 3 is the Text section base (tag 0x54, value 0; the
  emu-symdump calls it `func_000008`, which older xrefs printed as `bu_000008`). The target is the jal
  immediate (`(w & 0x3FFFFFF) << 2`) minus 0x1466C for game_libs. The C spells these as `gl_ref_<bootup off>`.
  Fixed in /tmp/claude-1000/b468/xref.py. Cross-USO callers of a game_libs function: h471's `xmod.py`
  (copy with paths fixed: /tmp/claude-1000/b468/xm/, output xmod.json maps callee name -> external callers).
- **Parm read / write slots.** A 0x2C-0x30 function that calls a per-TU `fs_gdlReadInt` (the tag) and then
  `fs_gdlRead{Int,Float,Quad,Vec3}(this + 0x10)` is a hostio parm read slot: `hostio_read<T>Parm_<addr>`
  (same pattern as boot_/game_/edd_read<T>Parm in the other modules).

- **Placeholder calls in -O0 NCC donors (run 801).** `name-placeholder-calls.py` missed target-specific flags on
  `$(VAR)` targets (`$(GAMELIBS_O0_9204_DONOR): OPT_FLAGS := -O0`), so the -O0 createGame / ColourItem donors
  verified at -O2 and stayed unnamed; fixed (c788fa119), 31 calls named. Placeholder calls in C++ inline members
  that are never instantiated (48AEC Ctx, 4BAF4 Ctx4B, 41820 Self::link) emit no jal: tag them
  `UNNAMED: no-reloc`, naming the instantiated twin's callee in the reason.
- **Run 802 (agent-g).** The same $(VAR)-target fix also unlocked the bootup -O0 NCC donors: ncc_FC28 (16),
  ncc_F81C (2), ncc_11B5C (2) are now fully named (donor .text byte-identical). The verify compare is now
  `same_code`: a word with an R_MIPS_26 reloc in both objects compares only its opcode. A smaller
  REPLACE_FUNC_BODY stand-in at the head of a unit (game_uso_func_00000000) shifts every later function,
  so in-file jals bake different targets. This fixed the selftest and took `check --strict` from 171 to 141.
  port_trace_collect (PORT only) reads `WORLDREG(game)->windows[0]` rather than `game + 0x108`.
- **Callers of static helpers (run 804).** The verify copy drops `static`, so a jal to a static callee is a
  symbol reloc with a zero field there but a `.text` reloc carrying the callee's offset in the real object. plan used
  to compare raw bytes and rejected every such caller as "verify bytes differ (donor splice)". Example: game_uso.c
  camPath_read_00000724 and TrickTable_load_0000C3F8, which call the static stream readers. `same_code()` now
  compares with the reloc fields masked (1ac43f0b8), and selftest passes again. Plan over all src still finds
  29 provable unnamed sites: arcproc ncc_o0_12C/B4 (2); bootup_uso.c, _90CC, _o2_6808 (2 each); bootup ncc_11B5C,
  F81C, FC28 (20); mgrproc_uso.c (1).

## 2. Map

| range | subsystem | named |
|---|---|---|
| 0x4C190-0x4C928 | ScreenWindow (built by the GfxLib init at 0x445AC as "ScreenWindow"), node picking | ScreenWindow_ctor / _allocBuffers, gfx_pickNode |
| 0x4CCB4, 0x4E600-0x4EE44 | Window class: name "win", parm group "Window" | Window_ctor, _hostioParms, _display, _update (pure-virtual stub), _setupView, _updateAspect |
| 0x4D05C-0x4DCD4 | RcpMgr ("RCP Mgr"): RSP/RDP task queue, gfx + audio tasks | RcpMgr_ctor, _update, _service, _startTask, _initTask, _queueTask, _insertTask, _removeTask; RcpTask_ctor/_init/_setData/_setUcode*/_setOutputFifo_*, vFP1_call |
| 0x4DDF8-0x4DEF0 | DisplayMgr ("dispmgr") | DisplayMgr_ctor, _add |
| 0x4F2DC | screen point -> world ray | gfx_screenRaycast |
| 0x4F9E4-0x54144 | BasePolyShape: shape command stream, materials, normals, subdivision; ZoneShape | BasePolyShape_* (ctor, parse, parseCmd, parseMats, genNormals, genNormalsFast, ...), ZoneShape_build |
| 0x51694-0x52144 | materials: parm groups, GDL_MC command decoder | BaseMat_hostioParms, Mat_print, gfx_decodeMatCmd, gfx_texelBytes, gfx_declColourParm |
| 0x51448, 0x54A14, 0x54C6C | lights | shape_cmdLightTarget (was LightTarget_ctor), BaseLight_hostioParms, LightTarget_hostioParms; CMod_ctor / CMod_hostioParms (0x545BC/0x54668, class string "CMod", RGBA at +0x2C) |
| 0x55264-0x5591C | ProcNodeList (node command lists) | ProcNodeList, nodelist_dispatch, nodelist_skipBlock, nodelist_check* |
| 0x55B44-0x55FB4 | crash/fault printer | sys_dumpMemory, fault_printThread, fault_printFlags |
| 0x56580-0x5A2C4 | display-list context + F3DEX GBI emitters | gfx_newDLContext, gfx_endDL, gfx_emit{RenderMode,CombineMode,Combine1,Combine2,GeometryMode,CycleType,Fog}, gfx_set{Color,Depth}Image, gfx_loadTexture, gfx_initRDPState, gfx_clearScreen |
| 0x5AFD4-0x5B90C | heap ("Mem::Alloc") | Mem_init, _allocLow, _allocHigh, _free, _checkAlloc, _checkFree, _freeAllOfType, _freeBytes, _largestFree, _countBlocks, _printFreeList, _dumpStats |
| 0x5BBEC-0x5FD20 | math: Vec3, quaternions, 4x4 matrices, gu*F-style projection | math_* (50 names), absrot_matrix4 (its own error string) |
| 0x5FE14-0x60370 | MemTracker / MemTrackerMgr (per-section memory accounting) | MemTracker_*, memtrack_begin/_end/_find/_walk, MemTrackerMgr_ctor |
| 0x60584-0x61A0C | text console: TextWin (NCC donor says `TextWin::draw`), ConsoleMgr, formatter | TextWin_ctor/_draw/_printf/_write, ConsoleMgr_ctor, console_createSystemWin, console_formatHex8, console_itoa, console_pow10Scale, console_formatValue |
| 0x61478-0x6179C | fatal error + routine-name stack | sys_fatal (106 callers), sys_imin, sys_imout |
| 0x62E10-0x63704 | **AnimPlayer** (ctor 0x62E80, 0xB0 bytes, vtable D+0x21F58; base of game_uso RiderAnim) | slot 3 update = advance (time +0x78 between keys +0x7C/+0x80, key event +0x64, blend flag 0x80 / 0x100) + applyPose (targets list +0x30, frames +0x34/+0x38, interval +0xA0/+0xA4); start ("StartAnim": anim +0x74, keys, flags +0x98, blend frames +0x6C), startIfChanged, setBlend (+0x8C/+0x90/+0x94), getKeyFrame / getKeyTime ("BadKeyFrame" / "BadKeyTime"), setKey, reset, handleMsg (slot 4), vfn10; AnimCmd_setTableEntry (animate.cpp) |
| 0x63884-0x65E64 | QNode dynamics: PhysQNode (vtable 0x222A8), Friction (0x22318, "Friction Limit"), **DNode** (ctor 0x64588, vtable 0x22208, "DNode::Parms"; bootup ShpNode derives) | DNode_ctor/_update/_handleMsg/_hostioParms/_solveContacts, DNode_func_* |
| 0x65EE4-0x66850 | fs_ PI word access + chunked dma, list / dlist / DynArr helpers | fs_piReadWord/_piWriteWord/_readBytes/_writeBytes, list_append (39 callers) |
| 0x66850-0x67AE8 | boot_ (main, mainuso reload, stack checks, thread start), pad_ controller thread (pad_init, probePaks, threadLoop, motor, Ctl pause / record / play) | |
| 0x67B04-0x68044 | str_ house string utilities (stpcpy = str_copyEnd, strncpy, strrchr, strdup, strtol-lite), math_atan2s | the libc strlen at 0x6F1B0 keeps its plain name |
| 0x682F8-0x68BF4 | BinFileMgr (vtable 0x2B2E8) / BinFile (0x2B2B0), ImageFileMgr (0x2B350) / ImageFile (0x2B278) | slot 10 of each Mgr = newFile |
| 0x68C14-0x69C94 | skin.cpp: SkinMgr (ctor 0x695F4 "skinmgr", vtable 0x2C490), skin_cmdSkinMgr / SkinAnim / SkinShape node commands | SkinMgr_init/_reset/_update/_bindPose/_skinVerts; math_acosf at 0x69CC4 |
| 0x61E58-0x62E80 | animation: AnimDataMgr, Animator ("anim"), key unpack/blend | AnimDataMgr_*, Animator_ctor, AnimData_load, anim_createAnimator, anim_blendPose, anim_unpackKey, anim_formatId |

## 3. Structs

Run 476 graphics headers (window.h, light.h, material.h, sprite.h, PolyShape / MorphPoly): see
docs/1080_GRAPHICS.md, sections 4 and 6-8.

`include/gdl/mem.h`: `MemBlock` (16-byte block header {hdr: owner id << 24 | size in 16-byte units, next, prev,
magic}) and `MemHeap` (free-list sentinel, used-list sentinel at +0x10, id +0x20, usedSize +0x24), plus
`MEM_MAGIC_ALLOC` 0x12345678 / `MEM_MAGIC_FREE` 0x87654321. Used by Mem_allocLow/High, Mem_free,
Mem_checkAlloc/Free. The allocators keep the heap parameter typed `MemBlock *` (`p != h` operand order).

`include/gdl/dlctx.h` (run 454): `DLBuf` {base (int address), count, max, cur} x6 = gfx/vtx/light/mtx/vp/hilite
(order and count/max from the gfx_printDLUsage format string), frameStart/frameStartCount +0x60/+0x64, name +0x70,
flags +0x78. 13 functions converted (ctor, reset, overflow, usage, all small emitters, endDL). Keep `base` an int:
the emitters' slot arithmetic is int and pointer arithmetic changes IDO's temp order.

`include/gdl/rcp.h` + `include/libultra/os_task.h` (run 454): `RcpTask` (0x78) embeds `OSTask_t` at +0x10 (type 1,
rspboot from cart 0xB0000B70, ucode sizes 0x1000/0x800, yield 0xC00), next/prev +0x50/+0x54; `RcpMgr` (0x50)
queue +0x4, active +0xC, rspBusy/rdpBusy +0x1C/+0x20, rsp/rdp task names +0x3C/+0x40, taskCount +0x28. 17 functions
converted. Gotchas: task.type is u32, so RcpTask.unk64 is s32 taking `1U` (0x4D0E4's typed-constant CSE lever);
RcpMgr_removeTask needs `node->prev == node->next` with pointer compares to keep the bnel operand order.

`include/gdl/polyshape.h` (run 454): `BasePolyShape` (0xB0) flags +0x8, nVerts +0x40, nTris +0x44 (u32),
faceNormals +0x54, vtxNormals +0x58, palette +0x5C, verts +0x60 (`s16 (*)[3]`, the triCentroid lever type), tris
+0x68 (`PolyTri` {u16 flags; u16 v[3]}), remap +0x70. 4 functions converted; getVtxNorm reads vtxNormals as
`*(int *)&` (a pointer-to-int cast re-colours it). Not yet converted: genNormals / genNormalsFast / genPointNormals /
parse* (FW-heavy, lever-dense), the 0x4C/0x64/0x98-0xAC fields.

The heap header is now only `include/gdl/mem.h` (agent-a's heap.h folded in; MEM_BLOCK_OWNER for heap_new).

Next struct candidates: MemTracker; TextWin / ConsoleMgr; the RcpTask unk58-unk74 (callbacks at +0x70/+0x74 read by
RcpMgr_startTask).

## 4. Held back and next

- Run 476: 53 graphics names (52 `gfx_func_` + MorphPoly_setVerts). Evidence per name is in commit f00df5e00.
  About 8 `gfx_func_` remain with unclear roles (listed in docs/1080_GRAPHICS.md section 10). New headers:
  window.h (DLMark 0xC, Window 0x144, ScreenWindow 0x1CC), light.h (BaseLight 0x138, LightTarget 0x16C),
  material.h (BaseMat 0x60, vptr +0x5C), sprite.h (Sprite 0xD8), polyshape.h (+PolyShape 0xC0, MorphPoly 0xDC).
  Converted: gfx_dlMark* (dlMarkStart needs an int-cast read of cur->base, or the registers swap) and
  Window_updateAspect. Next conversions: Window_setupView, ScreenWindow_allocBuffers, MorphPoly_init,
  BaseMat_init, LightTarget_ctor. The GfxLib global (fields in docs/1080_GRAPHICS.md section 2) stays as
  `D_00000000 + K`.
- Run 481 (agent-b): those five conversions are done (plus the ScreenWindow_display donor view and the
  Sprite_ctor reference body). Renames: gfx_texImageBytes / gfx_texRowBytes (0x520B8 / 0x52104),
  gfx_setCpuDraw (0x46788, gfx +0x28C), LightTarget_ctor -> shape_cmdLightTarget (0x51448, a GDL shape
  command, sibling of shape_cmdShape). docs/1080_GRAPHICS.md now has the texture-format table (6.1), the
  GDL_MC material commands (6.2) and the shape command stream (7.1).
- Run 486 (agent-b): include/gdl/anim.h (AnimPlayer 0xB0, AnimData 0x20, AnimGroup, AnimDataMgr 0x48,
  AnimFrameSlot / AnimFrameCache, Animator 0x130, AnimPose, AnimKey, AnimNodeKey, ANIM_* flags) and
  include/gdl/skin.h (SkinMgr 0x98, SkinAnim 0xA8, SkinWeight, SkinBone); 18 names (AnimData_init /
  readFrames / waitFrames, AnimGroup_init / load, AnimFrameCache_releaseAll / find / getPose,
  AnimDataMgr_releaseFrames / loadFile, AnimPlayer_onKey, skin_cmdSkinMgr / SkinAnim / SkinShape,
  SkinAnim_ctor / bind / skinVerts, SkinMgr_addAnim); 25 functions converted (AnimPlayer_*, the
  AnimData / frame cache family, AnimData_load donor, SkinMgr_ctor / init); gGfxLib on 43 game_libs
  sites. Formats: docs/1080_GRAPHICS.md sections 11 / 12. Map rows 0x61E58 / 0x62E10 / 0x68C14 still
  use the pre-486 names in places; the renames.tsv ledger maps them.

- Run 468: **no game_libs placeholders are left** (gl_func_ / game_libs_func_ except the `*_00000000*` sentinels).
  New in 0x27000-0x34400 (outside the old area): AudioThread_CheckSpecChange / ClearSpecChangeQueue / Noop1Cmd /
  Noop1CmdZeroed / WaitForAudioTask / GetLayerSamplesLeft (OoT thread.c order; 275B0 / 275BC set / clear an imported
  word, no OoT twin); MCamera (MNode-derived "camera", vtable D+0x1E0E8: ctor 32E18, hostioParms 33338, doCommand
  332B4, updateLookAt 33094 slot 11, vfn12 333A4); sys_assertFail, sys_fatalHaltLoop, dbg_threadName /
  dbg_threadStateName. libultra: gl_osSyncPrintf 6F144 / gl_rmonPrintf 6F160 (syncprintf.c order; the audio
  driver's RelocateFont calls the second), gl_osSpTaskYielded, gl_osPiGetCmdQueue, gl___osGetCurrFaultedThread,
  gl___osViGetCurrentContext. Still weak: RaceProcess_callGlobalSlot11_00008674 (the global is an import),
  sys_timeInFrames_00033444, gl_xldtob_stub_00073E6C, str_stubReturn0_00067D80.
- Run 468 header moves, all done: OSPiHandle (6C2A4, 730CC, 7369C, 6F088), OSIoMesg / OSDevMgr (o1_6D964, ido53_74EF4,
  which also takes OSMesgQueue / OSThread), OSMesgQueue (6F218), OSPfs (post2b.c, ido53_718C0). Still TU-local:
  `__OSViContext` (74EF4), the pfs internals `__OSInode` / `__OSDir` / `__OSInodeCache` (post2b.c, 718C0), PgsRls.
  Candidates for new shared headers: os_vi.h (__OSViContext) and a pfs-internal header.
- Weak-name backlog (milestone 2): about 370 `<subsys>_func_<addr>` names remain in game_libs (gfx 60, Backup 61,
  RaceTracker 29, sys 27, coll 13, app 15, ...). Run 468 did coll_ (8 of 21) and two gfx_; the rest need per-function
  reading. xmod.json shows few external callers for post0b names, so the evidence is mostly the bodies and vtables.

- rename-symbol.py now accepts a {host, match_imports/<OTHER>.c} pair when every match_imports definition of OLD is
  textually identical to the host definition (comments stripped, whitespace collapsed); otherwise still refused.
- RcpTask ucode setters (run 458): identified from the ucode_data blocks in bootup .data (the relocs
  resolve to D+0x11990.. / text func_023300..): 0x4D254 F3DEX 1.23, 0x4D338 F3DEX.NoN, 0x4D2D0 F3DLP.Rej,
  0x4D304 F3DLX.Rej; 0x4D16C / 0x4D188 / 0x4D1C0 / 0x4D1F4 are SGI "RSP SW Version: 2.0H" ucodes (Fast3D
  family; which one each is still open, so they keep address suffixes). Only 0x4D254 / 0x4D2D0 are called
  (RcpMgr_initTask). 0x4D224 / 0x4D2A0 are the "fastQ" / "NoC" unsupported-ucode stubs; 0x4D05C ("vFP1") is
  the base slot of a 2-entry functor vtable 0x1FC24 (derived 0x1FC3C slot = 0x4D084, calls fn(arg, this)).
- Area-B libultra tail (run 458): identified 37 more from libreultra source shape (see renames.tsv); all use
  the `gl_` prefix. 0x6CCD4 / 0x747F4 are the SI raw accessors (they call gl___osSiDeviceBusy and are
  osInitialize's PIF accessors), not PI; the PI pair is 0x6BA7C / 0x7307C. Motor: source order
  osMotorStop (0x6CDB4), osMotorStart (0x6CF54) is assumed for the word-identical twins; swap if the
  _MotorStopData / _MotorStartData relocs say otherwise.
- New libultra headers: os_pi.h (OSPiHandle, OSIoMesg, OSDevMgr, __OSTranxInfo), os_timer.h, os_cont.h
  (OSContStatus, OSContPad, OSPfs). Still private copies to migrate: OSPiHandle in ido53_6C2A4 / 730CC /
  6F088 / 7369C, OSIoMesg in o1_6D964 / ido53_74EF4, OSPfs in post2b.c / ido53_718C0, OSMesgQueue in
  ido53_6F218 / 74EF4. Those donors carry their own base typedefs (u32, s32) and some use `void *` or
  unprototyped fn-pointer fields, so migrate one at a time and gate each.
- Run 463: osMotorStop / osMotorStart CONFIRMED from the reloc pairing (see commit cd0bf1205): 0x6CDB4 uses
  _MotorStopData 0x62A00 + _motorstopbuf 0x62C00 (the buffer osMotorInit fills with 0).
- Run 463 leftovers: the `f(&local); g(a0 + 0x10)` thunks (0x4D02C, 0x4E3F4, 0x4F9AC, 0x551B0, 0x55B10, 0x6370C,
  0x65DDC, 0x65E0C, 0x65E84, 0x65EB4, 0x69C58; callee bu_000008, maybe Cfront static-init helpers), 0x67D80.
  Many run-463 names are `<subsys>_func_<addr>` (prefix only); refine as callers from other USOs are resolved
  (most `in:0` functions here are imported by bootup / game_uso). The header moves listed below were not started.
- (Before run 463) Unnamed in 0x4C000-0x62F08: 0x4CFB8 (BaseMat vtable 0x1FBEC slot 0, empty), 0x51E98 (PMF parm callback
  of BaseMat), 0x551E0 / 0x5165C (CMod secondary-vtable slots), 0x4F85C / 0x4FBA4 (Mat factories: 0x4F85C builds
  from a ScreenWindow's frame buffer +0xF4 and size +0xB8/+0xBC; 0x4FBA4 clones and runs the GDL_MC command list),
  0x4DF90 (vtable 0x20400 helper), 0x521F8 (Node class sharing BasePolyShape_doCommand), 0x5AB84 / 0x5AD54 ctors,
  the 4-entry device-style vtable 0x21DA0 next to ConsoleMgr's (0x61ADC / 0x61AF0 / 0x61B04 / 0x61B10 return -1: read/write/... stubs).
- Area-B still unnamed: 0x6F144 / 0x6F160 (empty varargs print stubs), 0x6FAD4, 0x70FA0, 0x74894 / 0x75254 (int
  readers), 0x62E80 class (vtable 0x21F58: slots 3 0x62F64, 4 0x62F58, 10 0x63704), 0x690A8-0x69CC4 libgdl code.
