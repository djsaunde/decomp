# 1080: game_libs 0x0-0xEBC8 ("area D") and where the libgdl system layer really is

> agent-a run 445, 2026-11-15, 1080 branch agent-a (commits 36069342e, be343a966, 2a66a143a, f95adc050).
> Scope: game_libs.c, game_libs_head/mid/tail.c, game_libs_o0_*. READABILITY_PLAN section 2
> guessed this range was the libgdl system layer (heap, file I/O, DMA, HostIO, App loop).
> **It is not.** The range is the race HUD, the SRAM save layer and some mode glue.

## Index
- [1. String-xref method](#1-string-xref-method)
- [2. Where the system layer lives](#2-where-the-system-layer-lives)
- [3. Map of 0x0-0xEBC8](#3-map-of-0x0-0xebc8)
- [4. Save (SRAM) layout](#4-save-sram-layout)
- [5. Structs](#5-structs)
- [6. Next](#6-next)
- [7. Area E1 (post0b 0x34458-0x4C000 + post.c DMA), run 448](#7-area-e1-post0b-0x34458-0x4c000--postc-dma-run-448)
- [8. Run 453: vtables, hostio kinds, readers, CollShape, Gadget](#8-run-453-vtables-hostio-kinds-readers-collshape-gadget)
- [9. Run 457: gadget structs, vtable-only classes, ItemType subclasses, GfxLib DDM](#9-run-457-gadget-structs-vtable-only-classes-itemtype-subclasses-gfxlib-ddm)
- [10. Run 462: RaceProcess base, app_launchGenProc, full-range sweep](#10-run-462-raceprocess-base-app_launchgenproc-full-range-sweep)

## 1. String-xref method

bootup.uso's inner header is at ROM 0xD9FE28. Walk it with `walk_dir` in `scripts/uso-reloc-symbolize.py`:
each section's payload starts **4 bytes after** the `(o+12)` that walk_dir returns. So Text is at
0xDD0A6C, Data at 0xDA23F0 and RoData at 0xD9FE44.

- **Text offsets.** A game_libs offset O is bootup Text offset O + 0x1466C. The TextReloc map (`build_relocmap`) is keyed by that offset.
- **Calls.** `kind 1` relocs, with symIdx resolved by `scripts/emu-symdump/bootup_uso.symnames.json`. A
  `func_<off>` value with off >= 0x1466C is game_libs `off - 0x1466C`. Below that it is bootup_uso code.
- **Data references.** Pair each `kind 3` (lui, by rt) with the next `kind 2` on the same base register and
  symIdx. The string is at **Data + (hi<<16) + lo**, which is the `&D_00000000 + K` constant written in the C.
  **Ignore the emu `D_xxxxxx` name.** It is the symbol's resolved base value, and adding it gives garbage.
- **Function pointers.** DataReloc entries use the same `[flag][(symIdx<<4)|kind][offset]` layout. Only one
  word in Data points into 0x0-0xEBC8 (Data+0xD564 -> 0xC8B8), so this range has no vtables.

## 2. Where the system layer lives

The same scan over all of game_libs:

| offset | file | string anchor | what |
|---|---|---|---|
| 0x334E8, 0x33BE4, 0x33EB8 | game_libs_post.c | "Write not at end", "Write() bad length", "Read() bad length" | buffered file write/read |
| 0x33880 / 0x33A8C | post.c | "write not aligned", "Out of DMA slots" | DMA queue |
| 0x349E0, 0x3EDBC, 0x3FC58 | post0b | "HostIO", "HostIO init error", "HostIO: unknown command" | HostIO |
| 0x34EB4 | post0b | "RunApp", "app.Update", "app.Display", "gfx.Start", "SndCPU" | the App main loop |
| 0x35268 | post0b | "TempBuffer busy", "TempHeap alloc fail" | temp heap |
| 0x35440 / 0x356FC | post0b | "SRAM read %x, %d from %x", "SRAM write ...", "ReadFile Error" | SRAM / file read/write (called by Backup_read/write) |
| 0x41148 (0x410E4 = its thin wrapper, the `new` every ctor here calls) | post0b | "New(): Cant allocate %dk", "%x = New(%d,%d, %d)" | heap New |
| 0x41A9C | post0b | "Memory Dump", "SysLinks %d*%d", "AppLinks %d*%d" | memory debug menu |
| 0x5B6E4 | post0b | "Bad Mem::Alloc %d,%x" | Mem::Alloc |

These belong to areas C (post.c) and E (post0b). Whoever owns post0b should take heap_/fs_/dma_/app_ from this table.

## 3. Map of 0x0-0xEBC8

| range | what | named (run 445) |
|---|---|---|
| 0x1CC-0x3430 | **HUD Gadget classes**. Each ctor: `new(size)` when this==0, a `<Node>` base (Node ctor gl_func_0003800C), the class-name string at +0xC, two sprite sub-objects at +0x10C/+0x124 (an import ctor with ids 0x5xxxx), colour floats /255 at +0xC4. Methods: `_release` (frees the two sprites), `_set<Value>` (sprintf with the class's format) | TimeGadget, BestTimeGadget, BestScoreGadget, CountDownGadget, PointsGadget (+ two more classes also named "PointsGadget": 0xED0 item, 0x3138 8-item list), SpeedGadget, BoardsGadget, CoolGadget, CourseGadget; `*Parms_ctor` for TimeGadget::Parms / Cool / Course |
| 0x3430-0x4140 | PointsGadget-list internals: the 8-slot state machine (0x3430), "%s %d pts" (0x38F4), the slot allocators 0x3B1C/0x3C0C/0x3DB8 | not yet |
| 0x4104-0x41D4, 0x8944-0x8A40, 0x9674-0x975C, 0xC644-0xC714 | 4-function families calling gl_func_00035440 (file/SRAM read) with int / Quad4 / float / Vec3 destinations. Probably the Parms member-type read methods | not yet |
| 0x4244 | Colour::Parms (32 colour params) | ColourParms_ctor |
| 0x6900 | builds a large race object (+0x4F0 flags; bit 0x10000 adds sprite sets), "rom/racecol.bin", an "Extensions" child | not yet |
| 0x6A8C-0x8884 | object/list glue, 0x76F0 = mp72 donor | not yet |
| 0x8AE4-0x93DC (o0_8AE4, mid) | -O0 mode launchers: load a .uso via bu_0118E4 and call its entry, common tail 0x93DC | app_launchNameEnt (nameent.uso), app_launchViewRec (viewrec.uso = replay) |
| 0x97B4-0xC46C | **Backup = SRAM save** (section 4) | Backup_*, backup_checksum* (24) |
| 0x9978-0xB710 | generic containers / iterators used by Backup and the race object (0x9DB8/0x9EBC/0xAAEC use string "ead") | not yet |
| 0xC784-0xE47C | race-object methods (0xD0D0 "chk"/"gtl"/"gtr" parms, 0xD318-0xE230 slot allocators shared with 0x3B1C/0x3C0C) | not yet |
| 0xE2A4-0xEAAC | the HUD object that owns the gadgets | hud_releaseGadgets, hud_add<X>Gadget, hud_initSprites_* (struct Hud) |

Held back: `game_libs_func_00000B94` (CountDownGadget set-count). It is also defined in
src/match_imports, so rename-symbol.py refuses it as ambiguous across segments.

## 4. Save (SRAM) layout

`Backup_ctor` (0xB77C) prints "BACKUP: checking individual chunks". For options, course, arcade and
ghost it runs `Backup_check<X>`. On failure it prints "resetting <x> data" and runs `Backup_reset<X>`.
It ends with `Backup_writeHeader` and "BACKUP: sizeof ROM %d bytes". A chunk is valid when its
`backup_checksum(out, data, len, 0xDEADBBAD)` pair matches. Otherwise the check falls back to the
mirror copy and restores the primary from it.

| SRAM off | chunk | len | checksum | mirror data / checksum |
|---|---|---:|---|---|
| 0x000 | header: the 4 chunk checksums hashed with key 0xD1265205 | 8 | | |
| 0x008 | course | 384 | 0x188 | 0x7DD8 / 0x7F58 |
| 0x190 | arcade | 96 | 0x1F0 | 0x7F60 / 0x7FC0 |
| 0x1F8 | options | 24 | 0x210 | 0x7FC8 / 0x7FE0 |
| 0x218 | ghost header (n at +4), data n*4 at 0x230 | 16 | 0x228 | 0x7FE8 / 0x7FF8 |

Structs and `BACKUP_SRAM_*` macros: include/gdl/backup.h (agent-c run 474; 1080_MODES.md "Run 474").

## 5. Structs

`include/gdl/hud.h`: `Hud` (0xA0) has the child list at +0x10, the sprite sets +0x58..+0x68, and the gadget
slots plus value pointers +0x6C..+0x9C. Fields are s32 wherever the bodies used int, and offsets and size
are asserted. It is used by 10 hud_* functions. `hud_addCourseGadget` stays raw: it reads +0x38..+0x40 both as f32 and as int.

Next struct candidates: the common Gadget layout (0x13C, shared by every ctor: name at +0xC,
colour f32[4] at +0xC4, +0xD4..+0xE0 ints, text buffer at +0xE4, sprites at +0x10C/+0x124); the save
chunks (`BackupCourse` 384, `BackupArcade` 96, `BackupOptions` 24; the bodies already have private
`B384`/`Buf60` typedefs); the Parms member (0x18: owner, tag, kind, vtable at +0xC, 0x1E at +0x10).

## 6. Next

1. The Gadget base struct, converting the ctors' `*(f32 *)(arg0 + 0xC4)` style stores.
2. Name the Parms member-type read family (0x4104 and its siblings). That needs the vtable at Data+0xC764
   (`gl_ref_0000C764_*`) to be decoded through DataReloc.
3. The race object (0x6900, 0xC784-0xE230): find its ctor and class string (bootup_uso callers).
4. Area E: take heap/HostIO/App names from section 2.

## 7. Area E1 (post0b 0x34458-0x4C000 + post.c DMA), run 448

> agent-a run 448, branch agent-a: commits 636b53f24, 3505460d0, 3b603bbce (pure renames,
> 96 names) and c80a15176, 759e1f21e, 25a57c017 (structs + field conversions). Gate PASS each time.
> Xref tool: /tmp/claude-1000/a448/xref.py (the run-445 script, with offsets taken from
> report.json unit base + function address, so renamed functions keep their offsets).

| subsystem | names |
|---|---|
| DMA (post.c 0x337AC-0x33B6C) | dma_startRead/startWrite/wait/read/write/allocSlot/readAsync/writeAsync/init, dma_rawRead, dma_writebackCache, dma_invalCache |
| buffered streams (post.c, vtable-only) | fs_bufWrite_334E8, fs_bufWrite_33BE4, fs_bufRead_33EB8 |
| gdl file layer (kind 0 = remote HostIO, 1 = local ROM via the system handler vtable, 2 = SRAM) | fs_gdlOpenFile/ReadFile/WriteFile/SeekFile/CloseFile/ReadFileAsync/WaitFile/FileInfo. `fs_gdl*` because the kernel owns fs_read/fs_seek/fs_close |
| heap | heap_new, heap_tempAlloc, heap_tempFree, heap_printStats; mem_new (operator new, 125 callers), mem_newAligned, mem_delete |
| debug / fault | dbg_printf (the libgdl printf), dbg_printThreads, dbg_faultThread, dbg_startFaultThread, dbg_printIndent, __pure_virtual_called |
| HostIO | hostio_start/init/send/recv/dispatch; messages are 0xA0 bytes with the type at +0: 2 addFloat, 5 beginGroup, 0xB endGroup, 0xF updateFloat |
| App | App_main (0x415A4: names itself "App", sets up SysLib/GfxLib 320x240, ends in app_run), app_run ("RunApp" loop), app_initSystem, app_loadUso/unloadUso, App_Reset/InitInstance/Update/Display/hostioParms, App_func_000417CC/00041820 |
| Node classes | Node_ctor (base of all 45 "<Node>" ctors), Node_Load/Save/doCommand/printContents/def, MNode/SNode/QNode _ctor/_def/_hostioParms, BallRotator_hostioParms, Parms_addParm |
| other classes | CollShape_ctor/ctorPoly, NullCollShape_ctor, CollObjMgr_ctor, ItemMgr_Load, ItemType_load, PolyShape_init/hostioParms, MorphPoly_genUpdateList/updateColours/update_4AAF0, FogParms_hostioParms, GfxLib_init/hostioParms |
| gfx / math | gfx_start, gfx_end (app_run's "gfx.Start"/"gfx.End"), gfx_setVideoMode, gfx_viBlack, gfx_swapBuffer, gfx_addWindow, gfx_assertTexAligned, math_arcballPoint |

**`<Class>_hostioParms` pattern.** Every engine class has a vtable slot that publishes its parms
to the HostIO PC tool: `hostio_beginGroup("<Class>")`, one `hostio_add*` per parm, `hostio_endGroup()`,
then the base class's slot (ending in `Node_hostioParms`). The class string in beginGroup is the
best class-name evidence in this range. 0x3EE1C-0x3FB6C are the other hostio_add* message kinds
(not yet named; read each body's type word).

**Structs (include/gdl/).**
- `dma.h` DmaSlot (0x44 x 10 at the data base): OSIoMesg +0, OSMesgQueue +0x18, msg +0x30, dram +0x34,
  len +0x38, busy +0x3C, invalidate +0x40. dma_init keeps its pinned `k*0x44` IV form.
- `node.h` Node (0x2C): name +0xC, children +0x10, parent +0x14, serial +0x1C, handle +0x20, Cfront vptr +0x28;
  App = Node + words at +0x2C/+0x30.
- `heap.h` HeapBlock (16-byte header: id<<24 | size/16, next, prev, magic 0x12345678) and Heap
  (id +0x20, used +0x24). The allocator at 0x5B070 (area E2) still uses its private Blk5B070/Heap5B070.

**Next.** hostio_add* kinds 0x3EE1C-0x3FB6C; the Parms member readers (0x35AA4/0x35AE0, 0x37C70-0x37E40,
0x3D000-0x3D114, 0x42570-0x42648 all wrap fs_gdlReadFile/WriteFile); CollShape grid (0x3B2EC/0x3BE1C
"no pGrid data"); the 0x42000-0x4C000 graphics block (lights 0x435FC, sprites 0x4B620 "SS StartDL");
migrate the 5B070 allocator to heap.h (E2 owner); convert Node-derived ctors to Node fields.

## 8. Run 453: vtables, hostio kinds, readers, CollShape, Gadget

> agent-a run 453, branch agent-a: commits 15f1d5e55 and a7a2aa8d2 (pure renames, 74 + 51 names);
> 99df6e671 and 15d4b2cba (hand edits). Gate PASS each time.
> Scripts in /tmp/claude-1000/a453/: `xref.py` (calls/strings per function; Data refs now add the Sym
> value, so a ctor's vtable store shows as `D+<vtable>`), `vt.py` (every DataReloc word resolved through
> the **decompressed Sym section** (Yay0, payload at walk_dir offset + 4), so local function symbols
> resolve; the emu symnames JSON alone leaves most as `symN`), `vtref.py` (functions that reference a
> vtable, with its first 12 slots), `body.py` (C body with `&D_00000000 + K` replaced by the string).

**Vtables.** A Cfront vtable at Data X has its first slot's function word at X+0xC, then one slot every
8 bytes. A ctor stores X at +0x28 right after the Node_ctor call. Node's slots:

| slot | Node | overridden by |
|---:|---|---|
| 0 | Node_hostioParms | every `<Class>_hostioParms` (ItemType, ItemMgr, PolyShape, MNode, ...) |
| 1 | 0x38598 (per-child mtx copy when flags +0x8 & 0x200) | MNode 0x38DC0 |
| 2 | Node_display (children with doFlags & 4) | App_Display, MNode/SNode/QNode_display, PolyShape_display, gadget *_display |
| 3 | Node_update (doFlags & 8) | App_Update, MNode/QNode_update, CollObjMgr_update, CamMan_update, 0x36C08, 0x37938 |
| 4 | Node_handleMsg (tags 2, 0xC, 0xD, 0xE) | MNode/SNode/QNode_handleMsg |
| 5 | Node_broadcastMsg (child->handleMsg, child->broadcastMsg) | |
| 6 | Node_doCommand | MNode/QNode_doCommand |
| 7-9 | 0x38B6C / 0x38B74 / 0x38B7C stubs | slot 8 = ItemType_load / ItemMgr_Load |

The HUD gadget vtables are in game_libs' own Data (D+0xC77C..0xCA4C), so "this range has no vtables"
in section 1 was wrong: the DataReloc words point into it through local Sym entries.

**HostIO message kinds** (0xA0 record: type +0, name +8, then kind-specific words from +0x48):
2 addInt/addFloat (range), 3/4/0x28 unknown, 5 beginGroup, 6 addHeading, 0xB endGroup, 0xC addBool,
0xD unknown, 0xE addFlag (ptr, mask), 0xF add{Short,Int,Float,Hex}Var / updateFloat, 0x10 addMatrix,
0x11 addText, 0x18 addButton (member callback), 0x1A addVQS, 0x1D-0x20 / 0x33 / 0x36 remote file
open/read/write/close/seek/size, 0x21 / 0x24 / 0x27 / 0x2A / 0x2F unknown, 0x22 askString, 0x23 fileDialog,
0x25 sendImage, 0x29 addLink, 0x30 / 0x31 begin/endTreeNode, 0x32 addColour, 0x35 (SNode).
Button/link callbacks are `new`ed {vptr, obj, PMF} objects invoked by MemberCallback_invoke (0x35A18).

**Inline file I/O copies.** 39 tiny `fs_gdlRead{Int,Float,Vec3,Quad,24}_<addr>` / `fs_gdlWrite*_<addr>`
(the four 0x0-0xEBC8 families included) are dead out-of-line copies of inline helpers, one set per C++
TU. They have no callers and no data refs anywhere, so they keep their addresses.

**CollShape** (+0x2C tris, +0x84 mesh with the grid at mesh+0xA0): CollShape_height / query ("no pGrid
data"), below, raycast, nearestHit (names from the NCC donors' `Obj::height/query/below`).

**Structs.** `include/gdl/node.h`: +0x18 is now `doFlags`; eight Node-derived ctors store `vptr`
through Node. New `include/gdl/gadget.h` (Gadget 0x13C), used by Time/SpeedGadget.

**Next.**
1. The other gadget ctors to Gadget fields (BestTime/BestScore/CountDown/Points/Boards/Cool/Course;
   check each lever comment first; BoardsGadget allocates 0x140).
2. Unnamed Node classes with a vtable but no class string: 0x36B9C (vt D+0x1E878), 0x378D0 (D+0x1E938,
   hostio "Speed" in 0x3787C), 0x3D5BC (D+0x1EF60, also used by game_libs 0x88B4/0x959C/0xC5B0), 0xC784
   (D+0xD508, its update 0xCBF0 sets the race HUD gadgets' values), 0x4A670 (PolyShape-derived, probably MorphPoly).
3. ItemType subclasses (vt D+0x1EFC0, D+0x1F050, D+0x1F228 = 0x3D7F8; ColourParms derives from the last).
4. The rest of the 0x42000-0x4C000 graphics block (0x42938 "Hold"/"X %d", 0x44918, 0x44CE8 GDL_MAX_DDM).

## 9. Run 457: gadget structs, vtable-only classes, ItemType subclasses, GfxLib DDM

> agent-a run 457, branch agent-a: d6a3cc917 (hand edit: gadget structs), 0422f0feb and 128432fa4
> (pure renames, 44 + 5 names). Gate PASS each time. Scripts in /tmp/claude-1000/a457/ (the a453 set,
> plus `gbi.py`: GBI opcodes from `lui` immediates in a raw-word .s; `dstr.py`: Data strings in a range).

**Gadget structs** (`include/gdl/gadget.h`). Gadget (0x13C) now covers Time, BestTime, BestScore,
PointsGadget (0xD5C) and Speed, plus their release/set methods. New: `BoardsGadget` (0x140, count +0x10C,
one sprite +0x110; `BoardsGadget_setCount` = 0x1354) and `CountDownGadget` (0xD4 on a 0xC4 base: colour
+0x94, two text buffers +0xB4/+0xBC, blink counter +0xC4; the 0xB94 NM body uses it). Not converted:
PointsGadget_ctor_00000ED0 (0xD4, colour at +0x64: a third layout), CoolGadget (0x198, NCC donor) and
CourseGadget (0x2FC). The base sub-object `+0x28` stores go through `((Node *)sub)->vptr`.

**Vtable-only Node classes** (no class string; names from behaviour):

| class | ctor | vtable | what |
|---|---|---|---|
| CamFollow | 0x36B9C (0x3C) | D+0x1E878 | target at +0x38; update orbits the parent camera round the target, d-pad bits 1/2/4/8 |
| Spinner | (none in game_libs) | D+0x1E818 | `Spinner_hostioParms` publishes "Speed" (+0x2C); update = math_mtxRotateEuler(parent mtx, (0, speed, 0)) |
| SeekNode | 0x378D0 (0x34) | D+0x1E938 | update = math_mtxAddTranslation(parent mtx, (target - parent) * rate) |
| RaceTracker | 0xC784 (0xB8) | D+0xD508 | 8 rider records x 0x60 at +0x44, elapsed +0x30, limit +0x34 (0x927C0 ms = 10 min); slot 10 reset, findGates ("chk"/"gtl"/"gtr"), update = course progress % then the Speed/Time/Points/Cool gadget values |
| MorphPoly | 0x4A670 | D+0x1F850 | PolyShape subclass: init, display, shade (slot 11), morph (0x4A84C), checkVtx |
| App | 0x41524 (0x80) | D+0x1F4CC | `App_ctor` |

Unnamed with the same shape: 0x37348 and 0x37540 (vt D+0x1E758 / D+0x1E7B8, no ctor in game_libs;
analog-stick input record at +0x2C drives the parent's matrix, debug fly controllers).

**ItemType subclasses.** The ItemType base vtable is D+0x1EED8. Slot 10 is newItem, slot 11 buildItems
(newItem once per list entry, chaining the results) and slot 14 getItem(n). Slots 7, 12, 13 and 15 are not
named yet.
- D+0x1F228 `ColourItemType` (ctor 0x3D7F8, 0x58): RGBA quad at +0x48 (default 1,0,0,1). Its display calls
  gfx_setPrimColour(+0x48). Its items are `ColourItem` (0x3D5BC, 0x3C): msg 7 sets the position +0x30, and
  load reads three ints.
- D+0x1EFC0 `SNodeItemType`: newItem builds an SNode, chained through +0x84.
- D+0x1F050: newItem = MNode_ctor (an MNode item type; no ctor in game_libs, so not named).
- The brief's "ColourParms derives from 0x3D7F8" is **not verified**. ColourParms_ctor (0x4244) never
  references D+0x1F228.

**GfxLib (0x42000-0x4C000).** `GfxLib_reset` (0x44918; called by GfxLib_init and the soft-reset path) clears the
50 DDM slots (+0x2AC) and waits for the RCP (`gfx_waitRcpIdle`). DDM = the gfxlib.c "GDL_MAX_DDM" (50) pool:
gfx_addDdm / initDdm / callDdm / getDdm. Also gfx_waitRetrace (frame counter at state +0x24),
gfx_setPrimColour / setEnvColour / setBlendColour (0xFA/0xFB/0xF9 packets from an RGBA float quad), gfx_fillRect,
gfx_drawText (font renderer), dbg_screenOverlay_00042938 ("Hold"/"X %d"/"Y %d", called from outside game_libs).

**Next.**
1. ItemType slots 7/12/13/15 (0x3D2C8 is shared by every ItemType, and slot 8 is load, so slot 7 is probably save; check
   against Node_Save's caller), and the 0x1F050 MNode item type.
2. 0x37348 / 0x37540 input-driven controllers. 0x41F90 reads a 68-byte record from a file into obj+60.
3. The rest of the 0x42000-0x4C000 placeholders (`gbi.py` lists GBI opcodes per function): 0x43654/0x43BEC
   (TRI2), 0x469A8 (FULLSYNC + RcpMgr_queueTask = the frame task submit), 0x45178 (guMtxF2L).
4. 426 placeholders are left in 0x0-0xEBC8 + 0x34458-0x4C000. Most are untouched-string-free helpers.

## 10. Run 462: RaceProcess base, app_launchGenProc, full-range sweep

> agent-a run 462, branch agent-a: 7935a1d27 (58 names) and a6edfbfbc (365 names), both pure rename
> batches, gate PASS each. Placeholders left in 0x0-0xEBC8 + 0x34458-0x4C000: 4 (0xB94 is held back as
> ambiguous across segments; 0x8674, 0x402A4, 0x410AC). Scripts in /tmp/claude-1000/a462/: the a457 set
> (`vtgl.py` = the old game_libs `vt.py`), plus `vtmod.py` / `dis.py` (agent-h's per-module tools, now also
> resolving `game_libs_func_` and the timproc segments), `racevt.py` (the race vtables of all six modes side by
> side), `vcall.py OBJ...` (virtual-call sites `lh off / lw off+4` -> slot, per function, from build objects),
> `xmod.py` (every other module's call sites of each game_libs function), `classify.py` (per placeholder:
> vtable slots, callers, cross-module callers, calls, strings).

**RaceProcess** (game_libs race-process base). Vtable bootup Data+0xCE18 (38 slots). There is no out-of-line
ctor: TimRace/TrkRace/ARC/MGR/H2HRaceProcess, trnproc's race and titproc's GameDemoProcess inline it
(Node -> C338 -> Process C3A0 -> CE18 -> own vtable), then call `RaceProcess_init` (0x6900) and `RaceProcess_restart`.
State: 0x4E0 phase (0 intro delay, 1 3-2-1 countdown, 2 racing, 3 end message, 4/5 alt end, 7 over), 0x4DC
(1 racing, 2 ended), 0x4F0 flags, 0x4F4 timeout, 0x4F8 result code, 0x500 leave, 0x510 left-once, 0x54C/0x550
message y / velocity. Base slots, named from where the base calls them:

| slot | default | called from |
|---:|---|---|
| 4 / 8 | RaceProcess_handleMsg / RaceProcess_loadData | Node msg / load slots |
| 12 / 13 | RaceProcess_handleInput / RaceProcess_drawGui | Process update / display hooks |
| 14 / 15 | onEndRace / onEndRaceAlt | RaceProcess_endRace / endRaceAlt |
| 16 / 17 | onPause / onCountdownStart | start button / intro delay over |
| 18 / 19 | endTimerEnabled / altEndTimerEnabled (return 1) | phase 3 / 4-5 timer gate |
| 20 | onRaceOver (Process_fadeOut) | every frame in phase 7 |
| 21 / 24 | onEndTimerDone / onAltEndTimerDone | phase 3 / 4-5 timer expired |
| 22 / 23 | onTimeoutExit / onTimeout | 0x4F4 expired, with / without flag bit 20 |
| 25 / 26 / 27 | onPauseSelect / onQuitButton / onLeave | pause row chosen / bit 19 button / 0x500 set |
| 28 / 29 | drawHud / drawIntro | drawGui (always / phase 0) |
| 30 / 31 / 32 | drawResultExtra / drawTimeUpExtra / drawResult | drawResult (results 0,2,5 / 6), drawGui phase 3 |
| 33-36 / 37 | updateSub0-3 / onMessageBounce | handleInput on 0x4D8 / dropMessage |

So the mode-side role names line up as overrides: Tim/Trk slot 18 (startHud / isHudBusy) is the phase-3
timer gate, slot 20 (checkRecord, arc/mgr setupRace) is onRaceOver, 21 onFinish = onEndTimerDone,
25 runPauseRow / checkFade = onPauseSelect, 26 quit = onQuitButton, 29 drawOverlay = drawIntro, 30 drawHud =
drawResultExtra, 17 release = onCountdownStart. Results (0x4F8): 0 = course finished (`RaceProcess_finishCourse`,
from every DataManager_update on the rider's finish flag), 6 = time up (`RaceProcess_timeUp`, after
RaceTracker_checkTimeLimit); 2/3/4/5 are named `RaceProcess_endResultN_<addr>` until the sprites (ids 0x6000x
at +0x588..+0x690) are identified.

**Launchers.** Bootup Data+0xC4EC is the flow-mode USO table (n64proc ... eddproc) and Data+0xC510 the
helper table (genproc, nameent, gamegfx, charsel, charsps, charfir, charmap). `app_launchGenProc` (0x8AE4)
loads genproc (+ charsel, and charsps / charfir / charmap by mode) and runs its entry through `app_runProcess`
(0x93DC), so the procMain states 1-4 (h2h) / 0-3 (tim/trk) are the select screens. `app_createGame_<addr>`
(0x8E48, 0x8FFC, 0x9100, 0x9204, 0x92F4) load gamegfx.uso and call game_init with mode 5 / 4 / 6 / 2.

**Other confirmed names.** Node slot 1 `Node_updateChildren` (MNode/QNode override it), slot 7
`Node_saveData`, slot 8 `Node_loadData` (SNode / ItemMgr / ItemType overrides); ItemType slot 10 `newItem`,
11 `buildItems`, 14 `getItem` (12/13/15 kept as `vslotN`); `Parms_load_00035C6C`; `Backup_openSession` /
`closeSession` (tim_openSession etc.); `gfx_submitFrameTask_000469A8`; `StickCtrlA/B_update` (0x37348 /
0x37540, the stick-driven debug controllers; no ctor in game_libs). Everything else got a TU or class prefix
with the address kept (`Backup_func_`, `RaceTracker_func_`, `gfx_func_`, `coll_func_`, ...).

**Next.** Read the result sprites (ids 0x60000-0x6000B) to name results 2-5; the Backup record helpers
(0x9978-0xB958) need the BackupCourse/Arcade/Ghost structs; the `*_func_<addr>` range names in post0b
0x42000-0x4C000 (gfx) and 0x39EE4-0x3CF94 (coll) are the next refinement targets.

## 11. Run 469 (agent-c): race structs

include/gdl/race.h now types RaceProcess (0x6A8, the section 10 vtable as `RaceProcessVt`), RaceTracker
(0xB8; the HUD object, so `Hud` = `RaceTracker`), RaceEntry (0x60) and TimRace (0x730). The session object
at RaceProcess +0x528 / RaceTracker +0x4C is the record session from Backup_openSession. Field list,
conversions and what is left: 1080_MODES.md "Run 469".
