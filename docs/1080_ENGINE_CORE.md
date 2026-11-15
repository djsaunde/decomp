# 1080: libgdl engine core, game_libs_post0b.c 0x4C000-0x62F08 (area E2)

> agent-b run 449, 2026-11-15, 1080 branch agent-b (commits 61632b485 [rename, 166], f98dbad64 [include/gdl/mem.h],
> bd5d39c26 [rename, 6]). The lower half of post0b (0x34458-0x4C000) is agent-a's area E1.
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

## 2. Map

| range | subsystem | named |
|---|---|---|
| 0x4C190-0x4C928 | ScreenWindow (built by the GfxLib init at 0x445AC as "ScreenWindow"), node picking | ScreenWindow_ctor / _allocBuffers, gfx_pickNode |
| 0x4CCB4, 0x4E600-0x4EE44 | Window class: name "win", parm group "Window" | Window_ctor, _declParms, _display, _update (pure-virtual stub), _setupView, _updateAspect |
| 0x4D05C-0x4DCD4 | RcpMgr ("RCP Mgr"): RSP/RDP task queue, gfx + audio tasks | RcpMgr_ctor, _update, _service, _startTask, _initTask, _queueTask, _insertTask, _removeTask |
| 0x4DDF8-0x4DEF0 | DisplayMgr ("dispmgr") | DisplayMgr_ctor, _add |
| 0x4F2DC | screen point -> world ray | gfx_screenRaycast |
| 0x4F9E4-0x54144 | BasePolyShape: shape command stream, materials, normals, subdivision; ZoneShape | BasePolyShape_* (ctor, parse, parseCmd, parseMats, genNormals, genNormalsFast, ...), ZoneShape_build |
| 0x51694-0x52144 | materials: parm groups, GDL_MC command decoder | BaseMat_declParms, Mat_print, gfx_decodeMatCmd, gfx_texelBytes, gfx_declColourParm |
| 0x51448, 0x54A14, 0x54C6C | lights | LightTarget_ctor, BaseLight_declParms, LightTarget_declParms |
| 0x55264-0x5591C | ProcNodeList (node command lists) | ProcNodeList, nodelist_dispatch, nodelist_skipBlock, nodelist_check* |
| 0x55B44-0x55FB4 | crash/fault printer | sys_dumpMemory, fault_printThread, fault_printFlags |
| 0x56580-0x5A2C4 | display-list context + F3DEX GBI emitters | gfx_newDLContext, gfx_endDL, gfx_emit{RenderMode,CombineMode,Combine1,Combine2,GeometryMode,CycleType,Fog}, gfx_set{Color,Depth}Image, gfx_loadTexture, gfx_initRDPState, gfx_clearScreen |
| 0x5AFD4-0x5B90C | heap ("Mem::Alloc") | Mem_init, _allocLow, _allocHigh, _free, _checkAlloc, _checkFree, _freeAllOfType, _freeBytes, _largestFree, _countBlocks, _printFreeList, _dumpStats |
| 0x5BBEC-0x5FD20 | math: Vec3, quaternions, 4x4 matrices, gu*F-style projection | math_* (50 names), absrot_matrix4 (its own error string) |
| 0x5FE14-0x60370 | MemTracker / MemTrackerMgr (per-section memory accounting) | MemTracker_*, memtrack_begin/_end/_find/_walk, MemTrackerMgr_ctor |
| 0x60584-0x61A0C | text console: TextWin (NCC donor says `TextWin::draw`), ConsoleMgr, formatter | TextWin_ctor/_draw/_printf/_write, ConsoleMgr_ctor, console_createSystemWin, console_formatHex8 |
| 0x61478-0x6179C | fatal error + routine-name stack | sys_fatal (106 callers), sys_imin, sys_imout |
| 0x61E58-0x62E80 | animation: AnimDataMgr, Animator ("anim"), key unpack/blend | AnimDataMgr_*, Animator_ctor, AnimData_load, anim_createAnimator, anim_blendPose, anim_unpackKey, anim_formatId |

## 3. Structs

`include/gdl/mem.h`: `MemBlock` (16-byte block header {hdr: owner id << 24 | size in 16-byte units, next, prev,
magic}) and `MemHeap` (free-list sentinel, used-list sentinel at +0x10, id +0x20, usedSize +0x24), plus
`MEM_MAGIC_ALLOC` 0x12345678 / `MEM_MAGIC_FREE` 0x87654321. Used by Mem_allocLow/High, Mem_free,
Mem_checkAlloc/Free. The allocators keep the heap parameter typed `MemBlock *` (`p != h` operand order).

Next struct candidates: the DL context (0x7C: six {buf, count} sub-buffers for Gfx/Vtx/Light/Mtx/Vp, cursor
at +0xC, printed by gfx_printDLUsage); RcpMgr (0x50); BasePolyShape (0xB0: verts +0x60, tris +0x68 as
{u16 flags; u16 v[3]}, optional index table +0x4C/+0x70); MemTracker.

## 4. Held back and next

- `game_libs_func_000610F4` (itoa), `game_libs_func_000611E4` (pow10 scale), `gl_func_0006126C` (typed
  value formatter, "<BAD TYPE>"): also defined in src/match_imports/gl_func_00061478.c, so rename-symbol.py
  refuses them as ambiguous. Names ready: console_itoa, console_pow10Scale, console_formatValue.
- `gl_func_0004D05C` / `0004D224` / `0004D2A0` call sys_fatal with "vFP1" / "fastQ" / "NoC" (microcode
  names?); probably pure-virtual stubs of RcpTask variants. Not named.
- Unnamed: the Quad4/int "reader template" families (0x4DD64/4DDA0, 0x4E4E8/4E524, 0x515C0/515FC,
  0x55A7C/55AB8, 0x61DE0/61E1C/61F18; agent-a's Parms member-type read methods), the in:0 virtual methods,
  0x5AB84/0x5AD54 ctors, 0x4C5E4 (`Obj::run` NCC donor).
- The rest of run 443's area-B leftovers (strchr / _Genld / _Ldtob / viMgrMain hand edits, duplicate PI raw
  I/O naming, remaining libultra headers) were not reached in this run.
