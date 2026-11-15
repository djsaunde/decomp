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
