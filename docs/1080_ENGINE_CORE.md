# 1080: libgdl engine core, game_libs_post0b.c 0x4C000-0x62F08 (area E2)

> agent-b run 449, 2026-11-15, 1080 branch agent-b (commits 61632b485 [rename, 166], f98dbad64 [include/gdl/mem.h],
> bd5d39c26 [rename, 6]). The lower half of post0b (0x34458-0x4C000) is agent-a's area E1.
> agent-b run 454 (commits 8e1fc49b3 heap.h folded into mem.h, 6155f05d1/142fbf08c DLContext, b83fbfcac/fe3aca6ab
> RcpMgr/RcpTask + libultra/os_task.h, 3a4aff57a/6a4f5b06a BasePolyShape, 4dafc55ab tool, 7aca920fd [rename, 3], 116f79f43 [rename, 6]).
> agent-b run 458 (commits dc8e4f437 [rename, 62: vtable methods, RcpTask, reader templates], 1293c072a [rename, 37:
> libultra/libc tail], b844a9296 include/libultra os_pi.h / os_timer.h / os_cont.h + 5 donor migrations).
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
| 0x51448, 0x54A14, 0x54C6C | lights | LightTarget_ctor, BaseLight_hostioParms, LightTarget_hostioParms; CMod_ctor / CMod_hostioParms (0x545BC/0x54668, class string "CMod", RGBA at +0x2C) |
| 0x55264-0x5591C | ProcNodeList (node command lists) | ProcNodeList, nodelist_dispatch, nodelist_skipBlock, nodelist_check* |
| 0x55B44-0x55FB4 | crash/fault printer | sys_dumpMemory, fault_printThread, fault_printFlags |
| 0x56580-0x5A2C4 | display-list context + F3DEX GBI emitters | gfx_newDLContext, gfx_endDL, gfx_emit{RenderMode,CombineMode,Combine1,Combine2,GeometryMode,CycleType,Fog}, gfx_set{Color,Depth}Image, gfx_loadTexture, gfx_initRDPState, gfx_clearScreen |
| 0x5AFD4-0x5B90C | heap ("Mem::Alloc") | Mem_init, _allocLow, _allocHigh, _free, _checkAlloc, _checkFree, _freeAllOfType, _freeBytes, _largestFree, _countBlocks, _printFreeList, _dumpStats |
| 0x5BBEC-0x5FD20 | math: Vec3, quaternions, 4x4 matrices, gu*F-style projection | math_* (50 names), absrot_matrix4 (its own error string) |
| 0x5FE14-0x60370 | MemTracker / MemTrackerMgr (per-section memory accounting) | MemTracker_*, memtrack_begin/_end/_find/_walk, MemTrackerMgr_ctor |
| 0x60584-0x61A0C | text console: TextWin (NCC donor says `TextWin::draw`), ConsoleMgr, formatter | TextWin_ctor/_draw/_printf/_write, ConsoleMgr_ctor, console_createSystemWin, console_formatHex8, console_itoa, console_pow10Scale, console_formatValue |
| 0x61478-0x6179C | fatal error + routine-name stack | sys_fatal (106 callers), sys_imin, sys_imout |
| 0x61E58-0x62E80 | animation: AnimDataMgr, Animator ("anim"), key unpack/blend | AnimDataMgr_*, Animator_ctor, AnimData_load, anim_createAnimator, anim_blendPose, anim_unpackKey, anim_formatId |

## 3. Structs

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
- Unnamed in 0x4C000-0x62F08: 0x4CFB8 (BaseMat vtable 0x1FBEC slot 0, empty), 0x51E98 (PMF parm callback
  of BaseMat), 0x551E0 / 0x5165C (CMod secondary-vtable slots), 0x4F85C / 0x4FBA4 (Mat factories: 0x4F85C builds
  from a ScreenWindow's frame buffer +0xF4 and size +0xB8/+0xBC; 0x4FBA4 clones and runs the GDL_MC command list),
  0x4DF90 (vtable 0x20400 helper), 0x521F8 (Node class sharing BasePolyShape_doCommand), 0x5AB84 / 0x5AD54 ctors,
  the 4-entry device-style vtable 0x21DA0 next to ConsoleMgr's (0x61ADC / 0x61AF0 / 0x61B04 / 0x61B10 return -1: read/write/... stubs).
- Area-B still unnamed: 0x6F144 / 0x6F160 (empty varargs print stubs), 0x6FAD4, 0x70FA0, 0x74894 / 0x75254 (int
  readers), 0x62E80 class (vtable 0x21F58: slots 3 0x62F64, 4 0x62F58, 10 0x63704), 0x690A8-0x69CC4 libgdl code.
