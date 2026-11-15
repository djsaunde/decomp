# 1080 Snowboarding: the USO module format and the kernel loader

> agent-a run 442, 2026-11-15, 1080 branch agent-a (commits a3d9ef8a0, 1157dafde, bddb039a8).
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
| 0x800000B0 | func_800000B0 | uso_alloc (bump allocator; not yet renamed, it also has a match_imports copy) |
| 0x80000118 | uso_syncCache | D-cache writeback, I/D-cache invalidate |
| 0x80000168 | uso_strcmp | 0 when equal |
| 0x800001DC / 0x20C / 0x260 | uso_strcpy / uso_findSlash / uso_splitPath | path helpers |
| 0x800003A8 | fs_romRead | PI DMA ROM to RAM |
| 0x80000474 / 0x480 / 0x4B8 | fs_setDeviceTable / fs_initFile / fs_openDevice | devices |
| 0x8000058C / 0x598 / 0x5DC / 0x688 | fs_close / uso_bcopy / fs_read / fs_skip | |
| 0x80000698 / 0x734 | uso_file_open / uso_skip_to_end | Info record / skip to End |
| 0x800007D4 / 0x85C | uso_printModules / uso_printSlots | debug |
| 0x800008F0 / 0x9EC | uso_unload / uso_load | |
| 0x80000C88 / 0xD2C / 0xE58 / 0xE8C | uso_callEntry / uso_getModuleName / uso_printVersion / uso_addrToModule | |
| 0x800010B4 / 0x10E8 / 0x1184 | uso_getContext / uso_printMemStats / uso_clearMemStats | |
| 0x800011D0 / 0x12AC / 0x12BC | uso_find_file / uso_getErrno / fs_openFile | |
| 0x80001348 / 0x1414 / 0x1460 / 0x1470 / 0x1494 | uso_findDataSection / fs_readChecked / fs_tell / fs_seek / fs_closeFile | |
| 0x800014A8 / 0x1594 | uso_scanRom / uso_init | |
| 0x800017BC / 0x18B0 | uso_allocSlot / uso_initSlot | |
| 0x800018F0 / 0x1ADC | uso_unrelocate / uso_relocate | |
| 0x80001CF4 / 0x1DD0 | uso_relocateSections / uso_unrelocateSections | |
| 0x80001EC8 | uso_loadSections | |
| 0x800021A4 | func_800021A4 | uso_bindLocalSyms (not yet renamed, match_imports copy) |
| 0x80002250 / 0x235C | uso_bindImports / uso_unbindImports | |
| 0x800023E0 | func_800023E0 | Yay0 decoder + osSetIntMask (handwritten .s) |

## 11. Open questions

- Info word 0x08, the record flag class bits, and the module header's second word (8).
- EntrySym / BinaryDataSection / DiskInfo payloads.
- The Sym hash (word1 low half, word3).
- `D_80012C70[]` per-device state beyond the heap range.
