# 1080 Snowboarding: the USO module format and the kernel loader

> agent-a run 442, 2026-11-15, 1080 branch agent-a (commits a3d9ef8a0, 1157dafde, bddb039a8).
> Updated by agent-a run 467 (commits 055f71ba0, 4c7809507): no kernel placeholders remain. See section 12.
> Updated by agent-a run 472: kernel globals named (sections 8, 12), Sym tag census (section 6).
> Sources: the kernel loader in `src/kernel/kernel_000*.c` (names below are the run-442 names),
> the kernel string/section tables in `src/kernel/kernel_026.c`, `include/uso.h`,
> `scripts/uso-sym-oracle.py` (a working parser) and ROM dumps. Where a field is inferred
> rather than read from code, the text says so.

## Index
- [1. Kernel addresses: link vs runtime (+0x400)](#1-kernel-addresses-link-vs-runtime-0x400)
- [2. ROM filesystem: devices and files](#2-rom-filesystem-devices-and-files)
- [3. Records (section headers)](#3-records-section-headers)
- [4. Section types](#4-section-types)
- [5. Module header and the directory (Info) record](#5-module-header-and-the-directory-info-record)
- [6. Sym entries](#6-sym-entries)
- [7. Reloc entries](#7-reloc-entries)
- [8. Runtime state: UsoModuleSlot and globals](#8-runtime-state-usomoduleslot-and-globals)
- [9. Loader flow](#9-loader-flow)
- [10. Function map](#10-function-map)
- [11. Open questions](#11-open-questions)
- [12. Kernel naming: k_ aliases and the libultra/rmon map](#12-kernel-naming-k_-aliases-and-the-libultrarmon-map)
- [13. Porting the USO system to PC](#13-porting-the-uso-system-to-pc)

---

## 1. Kernel addresses: link vs runtime (+0x400)

The kernel is numbered (linked, `func_8000XXXX`) from 0x80000000 but runs at **link + 0x400**
(the usual N64 load address 0x80000400). Consequences that matter when reading the loader:

- Every `jal X`, `%hi/%lo(X)` and C call of a kernel symbol `X` really targets the code at
  **X - 0x400**. Example: `uso_load` calls `func_800022C8`, which is `uso_loadSections` at 0x80001EC8.
  The bytes match only because the symbol linked at X encodes the right runtime address.
- Kernel data addresses in C (`D_8000A2E0`, the string pointers `D_8000A3xx`) are runtime
  addresses. `D_8000A314` is the string the table in kernel_026.c holds at link 0x80009F14.
- `scripts/rename-symbol.py` therefore renames only the definition side of a kernel symbol, and keeps
  call/address references spelled as the old name, pinned as an absolute alias in
  `undefined_syms_auto.txt`. See the tool's docstring.
- So once a plain SDK name is in use as such an alias pin (`__ull_div = 0x80002E78`), the real
  definition cannot take it. It gets the `k_` prefix instead (`k___ull_div`); see section 12.

## 2. ROM filesystem: devices and files

`gFsDeviceTable` (`D_8000A2E0`, set by `fs_setDeviceTable`) points at a NULL-terminated table of
0x14-byte device entries (kernel_026.c `KernelUsoEntry`, link 0x80009E60):

| name | romStart | romEnd | vram | +0x10 |
|---|---|---|---|---|
| "mainuso" | 0xD9FDB0 | 0xE984B0 | 0x8001FFA0 | 0 |
| "rom" | 0x00B7C0 | 0xD9FDB0 | 0 | 0 |

"mainuso" holds one module, bootup.uso (whose Text section is the `game_libs` segment), loaded at a
fixed address. "rom" holds every other `.uso` and the data files.

A path is `"device/file"`. `uso_splitPath` splits it at the first `/` (`uso_findSlash`) into
`gUsoPathDir` / `gUsoPathFile`. `fs_openDevice(file, dir, "rb")` finds the device by name
(`uso_strcmp`, which returns 0 when the names are equal), copies the entry into the file struct
(`fs_initFile`) and returns the device's per-device heap range from `D_80012C70[i]`. Its 0xC-byte
layout is inferred from `uso_load`, which reads `range[0]`/`range[1]` as heap start and end.

File struct (0x28 bytes, partly inferred from the fs_* bodies):

| off | field |
|---|---|
| 0x04 | pos (byte offset inside the device) |
| 0x08..0x1B | the copied device entry (+0x0C = romStart, the read base) |
| 0x1C | limit (`fs_read` clamps `size*n` to `limit - pos`) |
| 0x20 | window start (`fs_openFile`) |

`fs_read(buf, size, n, fp)` is fread: buf must be 8-aligned (else `gUsoErrno = -0x1C`), and it reads
through the context hook `gUsoCtx+0x80`, which is `fs_romRead` (PI DMA). `fs_skip` / `fs_seek` /
`fs_tell` move and report pos (`fs_tell` = romStart + pos).

## 3. Records (section headers)

Everything in a device is a stream of **records**: a 12-byte header followed by `size` payload bytes.

```
u32 type;   /* section type, section 4 */
u32 size;   /* payload bytes (uncompressed size for Yay0 sections) */
u32 flag;   /* see below */
```

- `flag & 0x10000` (seen as 0x1001xxxx): the payload is **Yay0**-compressed. The kernel decoder is
  in `src/handwritten/kernel/decode_yay0_setintmask.s`, and the log line is
  "USO: UnCompress %d to %d". The next header follows the compressed bytes and may be
  byte-misaligned (uso-sym-oracle.py scans for it).
- `flag & 1` (`uso_loadSections`): allocate the section from the loader heap (context hook +0x98);
  otherwise the section is located through hook +0x34. Bss (type 8) is cleared, not read.
- The high byte also carries 0x08/0x10/0x20 class bits (Info records 0x08xxxxxx, bootup's Text
  0x2000xxxx). Their meaning is not decoded.
- Bss records carry no payload: `uso_skip_to_end` and `uso_findDataSection` skip `size` bytes for every
  type except 8.

## 4. Section types

The kernel's name table (kernel_026.c, the two pointer arrays at link 0x80009EA0 / 0x80009EB0 are one
14-entry table) gives the type numbers. `include/uso.h` has them as `enum UsoSectionType`:

| type | name | notes |
|---:|---|---|
| 0 | Info | directory record of a file (section 5) |
| 1 | Sym | symbol table, 12-byte entries (section 6) |
| 2 | Text Reloc | 12-byte reloc entries against Text |
| 3 | Data Reloc | against Data |
| 4 | RoData Reloc | against RoData |
| 5 | Text | code |
| 6 | Data | |
| 7 | RoData | |
| 8 | Bss | no payload, cleared |
| 9 | EntrySym | entry symbol (`uso_callEntry`; inferred) |
| 10 | EndOfFile | ends a device's directory walk (`uso_file_open` returns 0) |
| 11 | End | ends a module's section list (`uso_skip_to_end`, `uso_loadSections`) |
| 12 | BinaryDataSection | not used by the code read so far |
| 13 | DiskInfo | not used by the code read so far |

`uso_loadSections` stores each loaded section in `slot->secData[type]` and adds its size to
`gUsoSectionBytes[type]`. `uso_printMemStats` prints those 11 counters by name, after "MemUsed = %d" (`gUsoMemUsed`).

## 5. Module header and the directory (Info) record

Each file on a device starts with an **Info record** (`type 0, size 0x2C`). Its payload, read by
`uso_file_open` (which checks the magic, returns -0x15 if it is wrong, and returns 0 on EndOfFile):

| off | field |
|---|---|
| 0x00 | magic 0x12345678 |
| 0x04 | module index (slot id; -1 for the `<null>` placeholder first entry) |
| 0x08 | ? (1 in every entry seen) |
| 0x0C | name, 0x20 bytes ("bootup.uso", "audi...", ...) |

The Info record's flag low bits look like the file length (bootup 0x8950, the second "rom" file 0x756C),
but this is unverified. `uso_scanRom` walks every device this way. For each record with idx >= 0 it
copies the name into `gUsoModuleSlots[idx].name` and the file's device offset into `.romOffset`.

The module proper follows (bootup.uso: Info at ROM 0xD9FDF4, module at 0xD9FE28):

```
u32 magic = 0x12345678;
u32 8;          /* header word count / version? */
u32 size;       /* module size (bootup: 0x452A0) */
u32 flag;
```

Then its section records follow, up to End (type 11). "USO Version: %s" prints "3.1" (`uso_printVersion`).

## 6. Sym entries

12 bytes, `[info:s16, pad:s16][value:s32][word3]`. `info` is the top half of the first word:

| bits | meaning |
|---|---|
| 0-2 | kind: 1 = import, 2 / 4 = defined in a local section, 3 = absolute (marked resolved as-is) |
| 3 | resolved |
| 4-15 | kind 1: the **module id** that exports it; kinds 2/4: the **section type** (5 = Text, so text exports show the tag 0x0052xxxx) |

- `uso_bindLocalSyms` (func_800021A4) adds `secData[info>>4]` to `value` for kinds 2 and 4 and sets the
  resolved bit. For kind 3 it only sets the bit.
- `uso_bindImports` (kind 1) looks up `gUsoModules[info>>4]`. If that module is not loaded, it marks the
  slot dirty (`unk99`) and increments `gUsoCtx.miss` (+0x18). If the module is loaded but has no Sym
  section, it prints "cross referenced symbol section not loaded" and returns -2. Otherwise it copies
  `value` from that module's Sym entry number `*(s16 *)(entry + 8)` (the top half of word3).
- `uso_unbindImports(mod, id)` clears the resolved bit of every import from `id` when `id` unloads.
- The low half of word 1 and the rest of word3 look like hash/ID data. That is the unsolved "Sym hash"
  (READABILITY_PLAN section 11).
- **Census of bootup.uso (agent-a run 472).** Kind 4 is a section's *base* symbol (value 0):
  sym 1 = RoData (tag 0x74), sym 2 = Data (0x64), sym 3 = Text (0x54), sym 4 = Bss (0x84).
  Kind 2 is a named object: 0x52 Text (1891), 0x62 Data (453), 0x72 RoData (2), 0x82 Bss (138),
  value = offset in its section. Kind 1 tags 0x?1 are imports from module ?. game_libs' HI16
  TextRelocs: 1950 to Bss objects, 778 to Data objects, 1255 / 387 / 159 to the Data / RoData /
  Bss bases. This is what `&D_00000000 + K` means in the source (READABILITY_PLAN 9.1):
  K is a section offset for base syms, a field offset for objects. Example: the DMA slot
  table is Bss object sym 1504 at Bss+0x3A240; its error strings are Data-base K = 0x1E2C0...

## 7. Reloc entries

12 bytes, `[info][offset][orig]` (Text/Data/RoData Reloc sections):

| field | meaning |
|---|---|
| info bits 0-2 | type: 1 = R_MIPS_26, 2 = LO16, 3 = HI16, 4 = R_MIPS_32 (from the ROM jump table jtbl_8000A63C) |
| info bit 3 | applied |
| info bits 4.. | symbol index into this module's Sym |
| offset | byte offset of the patched word from the section base |
| orig | receives the original word, so the patch can be undone |

- `uso_relocate(mod, base, rel, n)` applies relocs whose symbol is resolved. HI16 remembers its half
  and address, and the next LO16 folds `hi<<16 + lo + value` and rewrites the remembered HI16 with the
  carry-adjusted upper half. An unknown type prints "unkown reloc type %x" (sic) and returns -2.
- `uso_relocateSections(mod)` runs it for RoData, Data and Text with their reloc sections, then
  `uso_syncCache` (osWritebackDCacheAll + osInvalICache/DCache on the range). Failures return
  -0xE / -0xF / -0x10.
- `uso_unrelocate` / `uso_unrelocateSections(mod, id)` restore `orig` for applied relocs whose symbol
  is an import from module `id`, and clear the applied bit.

## 8. Runtime state: UsoModuleSlot and globals

`include/uso.h`: `gUsoModuleSlots` (`D_800130A0`) is 135 x `UsoModuleSlot` (0x9C bytes):

| off | field |
|---|---|
| 0x00 | `secSize[14]`: bytes per section type (Sym: entry count, used as the bind-loop bound) |
| 0x38 | `secData[14]`: loaded section by type (0x3C = Sym, 0x4C = Text) |
| 0x70 | `id` (s16) |
| 0x72 | `name[0x22]` |
| 0x94 | `romOffset` |
| 0x98 | `inUse` (`uso_allocSlot`) |
| 0x99 | `unk99` (set by `uso_initSlot`, cleared while imports are unresolved) |

| global | was | meaning |
|---|---|---|
| gUsoModules | D_80012D60 | `UsoModuleSlot *[135]`, the live modules by id |
| gUsoCtx | D_80012BC0 | loader context: +0x00 heap cur, +0x04 heap left, +0x18 unresolved-import count, +0x24 last entry result, +0x34 / +0x98 section placement hooks, +0x80 read hook (fs_romRead), +0x84 printf hook. `uso_init` fills it, `uso_getContext` returns it |
| gUsoHeapCur / gUsoHeapEnd | D_8000A2D8 / D_8000A2DC | bump heap for `uso_alloc` (func_800000B0) |
| gUsoMemUsed, gUsoSectionBytes | D_80012D5C, D_80012D30 | statistics (`uso_printMemStats`, `uso_clearMemStats`) |
| gUsoErrno | D_80013004 | last error (`uso_getErrno`) |
| gUsoEntryModule / gUsoEntryIndex | D_80012C68 / D_80012C64 | entry symbol for `uso_callEntry` (reset to -1 by uso_load) |
| gFsDeviceTable | D_8000A2E0 | device table |
| gFsDevices / k_gFsDevices | D_8000A260 / D_80009E60 | the device table itself: runtime alias used by kernel_boot (sets mainuso's +0x10 to RAM end) / its link-address definition in kernel_026.c |
| gFsDeviceHeaps | D_80012C70 | per-device heap range, 0xC stride (`fs_openDevice` returns `&[i]`) |
| gFsRomReadStatus | D_80013000 | PI status saved by `fs_romRead` |
| gUsoEntryResult / gUsoAllocHook / gUsoReadHook / gUsoPrintfHook | D_80012BE4 / BF4 / C40 / C44 | gUsoCtx +0x24 / +0x34 (uso_alloc) / +0x80 (fs_romRead) / +0x84 (uso_nullPrintf), referenced as their own symbols |
| gUsoModuleSlotsPtr | D_8001309C | set to &gUsoModuleSlots by uso_init |
| gBootUsoPath | D_8000A59C | "mainuso/bootup.uso" |
| gKernelBssStart | D_8000ABC0 | entry.s clears 0x153E0 bytes from here |

Interior addresses still spelled as `D_` on purpose (they are separate reloc symbols in the
target, inside a named object): D_80012D34/38/3C (gUsoSectionBytes+4..), D_80012D64/68/6C and
D_80012F7C (gUsoModules+4.. / end), D_80013112 (slot 0 name), D_80013138..D_80013274 (dead
externs inside gUsoModuleSlots), D_800182E4 (slot array end), D_8000A3D4 (osClockRate low word),
D_8000A454..D_8000A468 (__osPiDevMgr fields), D_8001B654..D_8001B660 (CartRomHandle fields),
D_800195D4..D_800195E0 (LeoDiskHandle fields). The function-address constants in uso_init
(D_80000BD4, D_80000CF0, ...) and exceptasm (D_80003270 preamble, D_80003FE0
__osCleanupThread, D_800055F0, D_80005AEC, D_80006060 thread entries) are +0x400 runtime
addresses of kernel code, not data.

## 9. Loader flow

**Boot:** `uso_init` fills `gUsoCtx`'s hook table and clears the slot arrays. `fs_setDeviceTable`
installs the device table, and `uso_scanRom` builds the name to slot directory.

**`uso_load(path)`**, "USO: loading %s":
1. Set the entry indices to -1, print, and split the path. `fs_openDevice` returns -0x11 for an unknown
   device and gives the heap range, which is copied to gUsoHeapCur/End.
2. Find the slot whose name equals the file. On a hit: `uso_initSlot`, `slot->id = i`; if the module is
   already live, return -0x13; else set `gUsoModules[i] = slot` and run `uso_loadSections(slot, header)`,
   seeking to `romOffset`. Return -0x14 if the name is not found.
3. Over every live module: `uso_bindLocalSyms` (-0xA on error), then `uso_bindImports` (-0xC), then
   `uso_relocateSections`. Because every pass runs over all modules, loading a module also resolves the
   imports that already-loaded modules had pending on it.
4. Return the slot id.

**`uso_unload(path)`**, "USO: unloading %s": find the live module by name, clear `inUse` and
`gUsoModules[i]`, then for every other live module run `uso_unrelocateSections(m, i)` and
`uso_unbindImports(m, i)`.

**Calls into a module:** `uso_callEntry` calls `Sym[gUsoEntryIndex].value` of
`gUsoModules[gUsoEntryModule]` with `&gUsoCtx` and stores the result at `gUsoCtx+0x24`.
`uso_addrToModule(addr)` maps a code address to (module name, Text offset) for debug output, and
`uso_printModules` prints "%s: Text=%x-%x".

**Static-build note:** the decomp links each USO segment at VRAM 0, so the ROM's pre-relocation words
(jal 0, `lui 0`) are what the source must reproduce (`gl_func_00000000`, `&D_00000000 + K`).
See N64_FORENSICS.md, "game_libs JAL targets", and READABILITY_PLAN section 9 rule 4e.

## 10. Function map

| link addr | name | role |
|---|---|---|
| 0x80000000 / 0x60 | kernel_entrypoint / kernel_boot | entry stub (clear BSS, sp, jump to runtime 0x80000460) / uso_init + uso_load(boot USO) + uso_callEntry |
| 0x800000B0 | uso_alloc | bump allocator (gUsoCtx slots +48/+52) |
| 0x80000118 | uso_syncCache | D-cache writeback, I/D-cache invalidate |
| 0x80000168 | uso_strcmp | 0 when equal |
| 0x800001DC / 0x20C / 0x260 | uso_strcpy / uso_findSlash / uso_splitPath | path helpers |
| 0x800003A8 | fs_romRead | PI DMA ROM to RAM |
| 0x80000474 / 0x480 / 0x4B8 | fs_setDeviceTable / fs_initFile / fs_openDevice | devices |
| 0x8000058C / 0x598 / 0x5DC / 0x688 | fs_close / uso_bcopy / fs_read / fs_skip | |
| 0x80000698 / 0x734 | uso_file_open / uso_skip_to_end | Info record / skip to End |
| 0x800007C4 | uso_returnOne_800007C4 | returns 1, no caller found |
| 0x800007D4 / 0x85C | uso_printModules / uso_printSlots | debug |
| 0x800008F0 / 0x9EC | uso_unload / uso_load | |
| 0x80000C88 / 0xD2C / 0xE58 / 0xE8C | uso_callEntry / uso_getModuleName / uso_printVersion / uso_addrToModule | |
| 0x800010B4 / 0x10E8 / 0x1184 | uso_getContext / uso_printMemStats / uso_clearMemStats | |
| 0x800010C0 / 0x10CC | uso_nop_800010C0 / uso_nullPrintf | gUsoCtx stubs: slot +144 / slots +132,+136,+140 (varargs no-op) |
| 0x800011D0 / 0x12AC / 0x12BC | uso_find_file / uso_getErrno / fs_openFile | |
| 0x80001348 / 0x1414 / 0x1460 / 0x1470 / 0x1494 | uso_findDataSection / fs_readChecked / fs_tell / fs_seek / fs_closeFile | |
| 0x8000149C | uso_returnZeroF_8000149C | returns 0.0f, gUsoCtx slot +148 |
| 0x800014A8 / 0x1594 | uso_scanRom / uso_init | |
| 0x800017B4 | uso_nop_800017B4 | no caller found |
| 0x800017BC / 0x18B0 | uso_allocSlot / uso_initSlot | |
| 0x800018F0 / 0x1ADC | uso_unrelocate / uso_relocate | |
| 0x80001CF4 / 0x1DD0 | uso_relocateSections / uso_unrelocateSections | |
| 0x80001EC8 | uso_loadSections | |
| 0x800021A4 | uso_bindLocalSyms | local Sym entries: type 2/4 add the segment base, 3 marks; sets bit 8 |
| 0x80002250 / 0x235C | uso_bindImports / uso_unbindImports | |
| 0x800023E0 | uso_decodeYay0 | Yay0 decoder; osSetIntMask (0x80002488) is an interior label (handwritten .s) |
| 0x800029A0 | kernel_nop_800029A0 | no-op at the end of kernel_000 |

## 11. Open questions

- Info word 0x08, the record flag class bits, and the module header's second word (8).
- EntrySym / BinaryDataSection / DiskInfo payloads.
- The Sym hash (word1 low half, word3).
- `D_80012C70[]` per-device state beyond the heap range.

## 12. Kernel naming: k_ aliases and the libultra/rmon map

(agent-a run 467.) Every kernel function now has a real name. Rules:

- **`k_<SDK name>`**: the kernel definition of an SDK function whose plain name is already
  used as a +0x400 runtime call alias (section 1). Those aliases stand for the function
  0x400 *below* their value, so the plain name at call sites is the right one; only the
  definition is prefixed. There are 12 of them:
  - `k___ull_rshift`, `k___ull_rem`, `k___ull_div`, `k___ll_lshift`, `k___ll_rem`,
    `k___ll_div`, `k___ll_mul`, `k___ull_divremi`, `k___ll_mod`, `k___ll_rshift`
    (libc/ll.c, 0x80002A10-0x80002CA4; game_libs has its own `gl___*` copies);
  - `k___osResetGlobalIntMask` (0x80006250);
  - `k___rmonSendHeader` (0x80006F60).

  Rule: before using a plain SDK name for a kernel definition, grep it in
  `undefined_syms_auto.txt`.
- **SDK file-statics** get a file prefix, so that names stay unique ROM-wide: `rmon_`
  (NotImplemented, strcpy, SetTempBreakpoint, ClearTempBreakpoint, IsJump, LoadStoreSU/VU,
  SetUpForRCPop, CleanupFromRCPop), `kdebug_` (kdebugserver.c string_to_u32, send_packet,
  clear_IP6, send) and `pimgr_ramromMain`. Statics that already start with `rmon` keep
  their own names (rmonMain, rmonSendBreakMessage, rmonFindFaultedThreads, rmonGetRcpRegister).
- **Handwritten splat pieces**: `__osProbeTLB_part2`, `exceptasm_rdbFront` (0x80002E78: the
  tail of the preamble, a 2nd vector stub and the rdb/KMC front end), and
  `exceptasm_rdbStore_part2` / `_part3`.

**rmon is linked** (the debug libultra). Its source is `references/ultralib/src/rmon`
(decompals/ultralib, cloned 2026-11-15). The rmoncmds.c `dispatchTable` is kernel data
at link **0x8000A0A0** (54 runtime pointers; subtract 0x400). It fixes these names:

| idx | name | link | idx | name | link |
|---|---|---|---|---|---|
| 0 | __rmonLoadProgram | 0x80006C58 | 14 | __rmonGetGRegisters | 0x80008E98 |
| 1 | __rmonListProcesses | 0x80006BD8 | 15 | __rmonSetGRegisters | 0x80008FF4 |
| 2 | __rmonGetExeName | 0x80006C64 | 16 | __rmonGetFRegisters | 0x80009148 (real start 0x80009144) |
| 3 | __rmonListThreads | 0x80007564 | 17 | __rmonSetFRegisters | 0x800091FC |
| 4 | __rmonThreadStatus | 0x8000798C | 18 | __rmonReadMem | 0x80006790 |
| 6 | __rmonStopThread | 0x800079F4 | 19 | __rmonWriteMem | 0x8000698C |
| 7 | __rmonRunThread | 0x80007B3C | 20 | __rmonSetBreak | 0x80008264 |
| 10 | __rmonSetFault | 0x80007EA0 | 21 | __rmonClearBreak | 0x80008430 |
| 12 | __rmonGetRegionCount | 0x80006D0C | 22 | __rmonListBreak | 0x80008424 |
| 13 | __rmonGetRegions | 0x80006D7C | 30 | __rmonSetComm | 0x80007FE8 |
| 49-52 | __rmonGet/SetSRegs, __rmonGet/SetVRegs | 0x80009314 / 9474 / 9584 / 969C | other | rmon_NotImplemented | 0x800065B0 |

The rest of rmon follows the ultralib file order. Link address ranges:
- rmonsio 0x800050C0-0x800052B4 (SendFault, IOflush, IOputw, IOhandler);
- rmoncmds 0x800065B0 (+ __rmonExecute 0x800065BC);
- rmonmem 0x80006650-0x80006F5C;
- rmonmain 0x80006F60-0x80007354 (SendHeader, SendReply, SendData, rmonMain);
- rmontask 0x80007360-0x80007DCC (__rmonMaskIdleThreadInts at 0x80007360: an earlier run had
  named it `__rmonSendHeader`, the call-site meaning);
- rmonmisc 0x80007EA0-0x8000802C;
- rmonrcp.s 0x80008030 (RCPrunning) and 0x80008054 (__rmonIdleRCP; StepRCP 0x80008098 and
  RunRCP 0x800080AC are interior labels);
- rmonbrk 0x800080D0-0x80008BAC;
- rmonregs 0x80008C30-0x80009824.

rdb / host I/O:
- `__osRdbSend` 0x800062F0;
- `osInitRdb` 0x800045C0;
- kdebugserver.c 0x800047B0-0x80004AB4;
- `osReadHost` 0x80004B10.

Other libultra:
- `osPiRawReadIo` 0x800029B0 (2.0I name; ultralib spells it `__osPiRawReadIo`);
- `__osLeoResume` 0x800044CC (leointerrupt.c static).

**Kernel data (agent-a run 472).** Kernel data references are spelled with their runtime
address, so data renames are full renames: `rename-symbol.py` now applies the definition-only
+0x400 rule to code symbols only (defined in an executable section), and folds an OLD into an
existing same-address SDK pin ("alias merge", used for `__osPiTable`). The libultra/rmon data
follows ultralib's definition order (runtime addresses):

| range | names |
|---|---|
| 0x80000300.. | osTvType, osRomBase (0x308), osResetType (0x30C), osMemSize (0x318), osAppNMIBuffer (0x31C) |
| 0x8000A3D0 initialize.c | osClockRate (u64), osViClock, __osShutdown, __OSGlobalIntMask (0x3E0) |
| 0x8000A3F0 exceptasm.s | __osHwIntTable, __osRdb_DbgRead_Ct (0x404), __osRdb_Mesg, __os_Kdebug_Pkt |
| 0x8000A410 thread.c | __osThreadTail, __osRunQueue (0x418), __osActiveQueue, __osRunningThread (0x420), __osFaultedThread |
| 0x8000A430.. | kdebug_numChars, readHostInitialized (0x440) |
| 0x8000A450 pimgr.c / piacs.c | __osPiDevMgr, __osPiTable (0x46C), __osCurrentHandle (0x470), __osPiAccessQueueEnabled (0x480) |
| 0x8000A490.. | __osRdb_IP6_Empty, rmon_dispatchTable (0x4A0), __rmonActive (0x580), __osRcpImTable (0x680), __osIntTable (0x700), gKmcExcCodeTable (0x744) |
| bss | leoDiskStack 0x80018300, __osThreadSave 0x80019320, kdebug_buffer, readHostMesgQueue/Buf, rmon_IOmq/IOmsgs, pimgr_* (piThread, piThreadStack, ramromThread, ramromThreadStack, getRamromQ/Buf, freeRamromQ/Buf, piEventQueue/Buf), piacs_piAccessBuf, rmon_* (somethingToDo, inbuffer, cmdinptr, cmdoutptr, state, inPointer, rmonIOThread, rmonMsgs, rmonIOStack, rmonPiMsgs, rmonPiMQ, breakpoints, altBreak(+_oldInstruction), RCPbreakpoints, RCPpc, oldIMEMvalue, DMEMbuffer) |

Not renamed: D_80019644 (`__osDiskHandle`) and D_800195D0 (`LeoDiskHandle`). The osLeoDiskInit
donor (kernel_ido53_4E50.c) *defines* both names in its own .bss, so the alias merge refuses them.
Retiring that donor's TU definitions is the way to free them.

**rmon packets:** `include/libultra/rmon.h` has KKHeader and the request/event structs from
ultralib dbgproto.h, with asserts. __rmonExecute, __rmonListProcesses, __rmonSetComm,
__rmonThreadStatus, __rmonStopThread, k___rmonSendHeader and __rmonSendReply use them. Other
rmon handlers still carry private packet typedefs (kernel_018_b/f/g, 022_e/f/g, 029, 030, 033,
054*): convert them the same way. Watch field widths: `KKThreadStatus.why` is s16, and the word
at +0x10 that StopThread tests is `status.flags`.


## 13. Porting the USO system to PC

(agent-a run 577.) How a PC port replaces the dynamic module system. Sources: sections 1, 2, 6, 8
and 9 above, include/uso.h, include/uso_call.h, include/gdl/sysapi.h, include/game/input.h,
`scripts/uso-imports.py`, and the bodies named below (all exact in the matching build).

### 13.1 What a USO is at runtime

A `.uso` is a relocatable module: an Info / directory record, a Sym table, Text / Data / RoData
reloc sections and the Text / Data / RoData / Bss payloads (sections 3-7). The kernel loader
(kernel_000.c, section 9) does four things with it:

1. **Load.** `uso_load("device/file")` finds the module's slot in `gUsoModuleSlots[135]`
   (`UsoModuleSlot`, include/uso.h), runs `uso_initSlot`, sets `gUsoModules[id] = slot` and
   `uso_loadSections` reads every section from ROM into the device heap. Bss is cleared, not read.
2. **Relocate.** Over every live module: `uso_bindLocalSyms` adds the section base to each kind-2 /
   kind-4 Sym value, then `uso_relocateSections` patches the R_MIPS_26 / HI16 / LO16 / 32 sites.
3. **Bind imports.** `uso_bindImports` copies a kind-1 Sym's value from the exporting module's Sym
   entry (`gUsoModules[info >> 4]`). A missing exporter marks the slot (`unk99`) and counts a miss;
   the pass runs over all modules, so loading the exporter later resolves the pending imports.
4. **Unload.** `uso_unload` clears `inUse` / `gUsoModules[i]`, then `uso_unrelocateSections` and
   `uso_unbindImports` on every other live module, so their sites that pointed into the
   unloaded module go back to unresolved.

The entry call is `uso_callEntry`: `Sym[gUsoEntryIndex].value` of `gUsoModules[gUsoEntryModule]`
is called with `&gUsoCtx` (the kernel boots bootup.uso this way, section 10).

**Who depends on it (game side).** Everything goes through the SysApi table (`gSysApi`,
include/gdl/sysapi.h), whose `usoLoad` (+0x40) / `usoUnload` (+0x44) / `usoPreLoad` (+0x74)
slots are the loader's services:

- `app_loadUso(&gSysLib, path)` / `app_unloadUso(&gSysLib, path)` (game_libs_post0b.c) call
  `SYSAPI->usoPreLoad` + `SYSAPI->usoLoad` / `SYSAPI->usoUnload` and `sys_fatal` on a negative
  result ("usoLoad() error loading file %s: %d", "cant unload %s (%d)").
- **Mode switches.** `GameFlow_startMode` maps `InputMgr.nextFlowMode` to a mode module and
  `GameFlow_loadProcUso_000117FC` (bootup_uso_o0_117FC.c) swaps it: if the new path differs from
  `InputMgr.procUsoPath` (+0x2C) it unloads the old module, calls `app_freeAllOfType(3)`, then
  loads the new one with heap mode 3 (`app_setHeapMode(3)`, `app_setCurrentHeap(&gSnowBoard, 1)`)
  and stores the path. The mode modules are n64proc, titproc, h2hproc, mgrproc, timproc, arcproc,
  trkproc, eddproc (each enters through `<pfx>_procMain`; 1080_MODES.md "Entry points").
- **Extra modules for the flow.** `game_loadUso` / `game_unloadUso` (bootup_uso_o0_118E4.c) keep a
  `FlowUso {handle, next}` list at `InputMgr.usoList` (+0x130) for modules loaded alongside the
  mode (callers: bootup_uso_o2_6808.c, and game_libs_o0_8AE4.c, which loads paths from a pool
  table); `game_unloadUso` / `GameFlow_unloadUso_00011A34` unload them. The `app_launch*` helpers
  load genproc / nameent / viewrec (1080_MODES.md).
- `boot_reloadMainUso` / `boot_usoLoadFatal` ("cant reload mainuso %d") in game_libs
  (game_libs_post1b.c, game_libs_ido53_669AC.c).

`scripts/uso-imports.py list` prints every module with its id (bootup.uso = 0, the audio banks
1-3, the board / rider data modules 4-12, boarder1-5 13-17, gui 18, the procs 19-28, game.uso ...); `imports <module>` shows
what each one binds.

### 13.2 Recommended PC strategy: one static executable

- **Link every module statically.** Each `src/<segment>/` becomes ordinary C in one program. The
  decomp already builds every segment from C; what a port drops is the VRAM-0 placeholder linking.
- **`uso_load` / `uso_unload` become a registry.** Keep the names (paths) as keys and map each to a
  per-module record `{ const char *path; void (*init)(void); void (*fini)(void); }`. `usoLoad(path)`
  looks the path up, runs `init` (reset the module's state, 13.3) and returns a fake slot id >= 0;
  `usoUnload(path)` runs `fini`. Install them in the SysApi table so `app_loadUso` /
  `app_unloadUso` / `GameFlow_loadProcUso_000117FC` keep working unchanged. The mode entry becomes a
  table of `<pfx>_procMain` pointers keyed by flow mode (1080_MODES.md "What a PC port replaces").
- **Import binding becomes direct symbol references.** The source spells every cross-module or
  self-relocated reference with a zero placeholder plus a documented name. In a port those macros
  expand to the name instead. A sketch, under a `PORT` build flag:

  ```c
  #ifdef PORT
  #define CALL(f)          f            /* uso_call.h: gl_func_00000000 on N64 */
  #define FCALL(f)         f            /* func_00000000 */
  #define GCALL(f)         f            /* game_uso_func_00000000 */
  #define XCALL(tok, f)    f            /* per-site alias token (gl_func_00000000_send ...) */
  #define GL_DATA_STR(off, text) ((char *)(text))   /* gl_data.h: the literal is the real data */
  #define INPUT_MGR(sym)   gGameFlow   /* the port's one InputMgr definition: every token is it */
  #endif
  ```

  The names are trustworthy: the readability gate re-proves every `CALL(X)` against the ROM's
  R_MIPS_26 relocs (`name-placeholder-calls.py check`), every `INPUT_MGR(tok)` against relocs into
  bootup Bss 0xF8 (`gameflow-import-sites.py check`) and every data alias / `GL_*` claim
  (`uso-data-sites.py check`). Two caveats:
  - A raw `GL_DATA(off)` / `GL_BSS(off)` / `&D_00000000 + K` (a section offset with no object
    name) has no PC meaning: each must become a named object first. The dashboard's "Data sites"
    table counts what is left, and `uso-data-sites.py` plans the conversions.
  - Placeholders are K&R (unprototyped) calls; a port needs a prototype per callee, and the
    argument types at the sites (names passed as `int`, 1080_PORTING_GUIDE section 8) must be
    widened to pointers.
- **Linker aliases.** The per-site alias macros of gl_data.h (`#define gInputMgr D_00000000`,
  `sStr_*`, `kRo_*`) exist only so the N64 build emits the placeholder relocation; in a port each
  alias is a real definition in the module that owns the object (the owner is the Sym entry's
  section: `uso-imports.py sites <module> --imports` names it).

### 13.3 Module state and its lifetime

- **bootup.uso is always resident.** It is the only module on the "mainuso" device (section 2),
  loaded at a fixed address by the kernel at boot, and never unloaded. Its Text is game_libs +
  bootup_uso, so everything in them (InputMgr / GameFlow at Bss 0xF8, gSysLib, gSnowBoard, the
  heaps, gGfxLib, the pad thread, the audio driver, gSysApi) lives for the whole run: in a port,
  ordinary globals.
- **Other modules are reloaded from ROM.** `uso_load` re-reads Text / Data / RoData and clears Bss,
  so a module's Data is back at its ROM initial values and its Bss is zero every time it loads.
  A mode USO is unloaded and reloaded on each mode change (`GameFlow_loadProcUso_000117FC`), so
  its module-local statics never survive a mode switch; a module reloaded with the same path is
  NOT reloaded (the path compare), so its state survives a restart of the same mode.
- **What persists across mode switches** is what lives in bootup.uso: the InputMgr fields
  (nextFlowMode, choices, `session` / `backup` save pointers, replay buffers), gSnowBoard and the
  heaps other than type 3. Heap type 3 allocations are the mode's (`app_freeAllOfType(3)` before
  the next load).
- **Port rule.** For every non-resident module, the registry `init` must restore its Data to the
  initial values and zero its Bss (keep a pristine copy of the initialised statics, or move them
  into a per-module state struct that `init` re-initialises), and `fini` must not free bootup-owned
  objects. Without that, a port behaves differently from the N64 on the second entry to a mode.

### 13.4 The `+0x400` kernel rule disappears

The kernel is linked at 0x80000000 but runs at +0x400 (section 1), so kernel symbols are spelled by
pinned link addresses (`func_8000XXXX`, `D_8000XXXX`, the `k_` prefixed SDK names, section 12) and
`UsoHook` slots hold runtime addresses (include/uso.h). On PC there is no load offset and no kernel
loader: the hooks are ordinary function pointers (or the registry above), the pinned aliases in
`undefined_syms_auto.txt` are not needed, and the kernel's libultra / rmon code is replaced by the
port's platform layer.

### 13.5 Duplicate-symbol hazards

On the N64 each module is a separate namespace (only Sym exports are visible, by module id), so the
same function or class can exist in several modules. Linked into one program these collide:

- **Cross-module twins.** game_libs and bootup_uso each define a TimeGadget (`TimeGadget_ctor` in
  game_libs.c, `TimeGadget_ctor_00013D40` in bootup_uso_tail4.c); the mode procs repeat skeletons
  (`*_procMain`, the `Process_*` / DataManager subclasses); timproc_uso_b1 / b3 / b5 share sources.
  The readability phase already keeps names ROM-wide unique (a duplicate global makes ld segfault):
  a recurring class gets a segment-qualified form or an address suffix, and module prefixes
  (`edd_`, `n64_`, `tim_`, `trk_` ...) separate the per-mode copies. Keep those names in a port.
- **Placeholder sentinels.** `gl_func_00000000`, `func_00000000`, `game_uso_func_00000000`,
  `D_00000000` and the per-site alias tokens are the same symbol in many modules; under `PORT` they
  must expand away (13.2) or the link merges unrelated objects.
- **Static (file-scope) duplicates** are fine; check `nm` of the port for duplicate globals after
  each module is added.

### 13.6 Checklist

1. Build every `src/<segment>/` (kernel excluded) as host C with `-DPORT`; drop INCLUDE_ASM and
   the NON_MATCHING-only paths per 1080_PORTING_GUIDE.
2. Define `CALL` / `FCALL` / `GCALL` / `XCALL` / `GL_DATA_STR` / `INPUT_MGR` / `GAMEFLOW` as in 13.2;
   declare prototypes for every callee they name.
3. Turn every remaining `GL_DATA(off)` / `GL_BSS(off)` / `&D_00000000 + K` into a named object
   (dashboard "Data sites"; `uso-data-sites.py` plans).
4. Replace the gl_data.h linker aliases by real definitions in the owning module.
5. Write the module registry: path -> `{init, fini}` for every module `uso-imports.py list` shows
   with code (procs, gui, boarderN, game, genproc ...); data-only modules (audio banks, course and
   rider data) become files read by the host.
6. Install `usoLoad` / `usoUnload` / `usoPreLoad` (and the other SysApi slots the kernel fills:
   memory range, file services) in the SysApi table before `boot_entry_00066C30`.
7. Make each non-resident module's statics resettable (13.3); verify a mode left and re-entered
   starts from the same state as a first entry.
8. Map the flow modes to `<pfx>_procMain` (GameFlow_startMode / 1080_MODES.md).
9. Resolve duplicate globals (13.5); keep the ROM-wide unique names from renames.tsv.
10. Drop the kernel (loader, `+0x400` pins, PI DMA `fs_romRead`) for a host file layer that serves
    "rom/..." paths from extracted files.
