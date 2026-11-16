# ROM coverage audit (1080 Snowboarding)

`scripts/rom-coverage.py` (project root `projects/1080-decomp/`) puts every byte of `baserom.z64` into
exactly one category, and reports any byte it cannot place as a GAP. `--check` is step 6 of
`scripts/readability-gate.sh`, so a future gap fails the gate and CI.

## Index
- [Why](#why)
- [Categories](#categories)
- [How a byte is placed](#how-a-byte-is-placed)
- [What --check fails on](#what---check-fails-on)
- [The allowlist](#the-allowlist)
- [Results (2026-11-16, run 626)](#results-2026-11-16-run-626)
- [Findings](#findings)
- [Usage](#usage)

## Why

The project said "3288/3288 = 100%", but eight USO modules with code had never been split or
decompiled: snoweffects, viewrec, trnproc, heli, nameent, checkpoint, balloon and fire, about 108 KB
of code. The 100% only counted the segments that the build config defined. This audit starts from
the ROM's own structure, not from the config, so a module the config forgot shows up as a gap. As a
test, linking snoweffects as a plain bin again gives a 0xA900-byte gap plus the error
`snoweffects.uso Text: no code segment`.

## Categories

| category | what |
|---|---|
| code-c | instructions compiled from C / C++: plain, donor (REPLACE_FUNC_BODY) and match_import bodies; `port-sourcemap.py` decides which body ships |
| code-asm/src | hand-written `.s` and libultra asm (`src/libultra`, `src/handwritten`, via GLOBAL_ASM): the asm is the source |
| code-asm/undecomp | INCLUDE_ASM functions not yet decompiled, plus reviewed code that no unit holds |
| code-asm/vendor | IPL3 (0x40-0x1000): Nintendo boot code, not game code |
| data-c | data emitted by a C object (today only kernel_026's `.data`, 0x170 B) |
| data-asm | ROM header; splat bin data; USO Data / RoData records of code modules; USO metadata (record headers, Info, Sym, Text/Data/RoDataReloc, EntrySym) |
| asset | data-only USOs (audio bank / seq / wave, textures, map data, characters) and the rom/*.bin files (BinaryDataSection payloads) |
| ucode | RSP microcode: the `*ucode*` / `*_imem` / F3DEX bins, aspMain (`game_libs_rsp_ucode_31DF8` text and bootup Data +0x1D340 DMEM), and the reviewed RSP IMEM ranges |
| padding | zero / 0xFF fill: alignment, device tails, the ROM tail |

## How a byte is placed

1. **ROM filesystem** (the `port/tools/extract/extract.py` walker): the kernel device table, then
   devices, files and records. Each record payload gets a role: Text, code-module Data/RoData,
   asset (the Data of a data-only USO, or a BinaryDataSection), or metadata. Yay0 payloads are
   decoded.
2. **Linker map** (`build/tenshoe.map`): which object made each linked byte (C `.o` .text or
   data, `.s.o`, a `.bin.o`, or linker fill). The ROM is byte-identical, so the map describes
   the ROM itself.
3. **Functions**: every report.json function, at (unit `.o` .text ROM start from the map) +
   address. Its kind comes from a fresh `port-sourcemap.py` run into a temp dir: `c` / `cpp`
   give code-c, `asm` gives code-asm/src (all-zero `_pad.s` bodies give padding), and an
   unresolved function (INCLUDE_ASM) gives code-asm/undecomp.
4. **Record headers inside a function**: PREFIX_BYTES functions (`gui/n64proc/eddproc/arcproc/
   h2hproc/boarder5 *_func_00000000`) begin with the Text record's flag word, which was
   compiled as a fake `beq`. Those 4 bytes count as data-asm, not code.
5. **Unlisted words in a C/asm `.text`**: a word with an ELF symbol that report.json lacks gets
   that symbol's kind (by base name, or `c` if the object's source defines it, else undecomp).
   A word right after a `jr`/`j` is a delay slot and joins the previous word's category. Any
   other nonzero word stays a GAP.
6. **Yay0 code blocks**: the six compressed Text records are linked from the extracted
   baserom bins (`build/assets/%.bin.o: assets/%.bin` is the first matching pattern rule, and
   game_uso links the carved `game_uso.bin`). The C for them is proven only by
   `make verify-blocks`, which tolerates jal / lo16 reloc-field diffs. The audit parses the
   Makefile's block recipes (objects, `ld -r` alignment vs `cat`, drop-text-word offsets) and
   lays out every function inside the decompressed block. It word-compares each function
   against the block, needing at least 75% matching words. It then splits the compressed ROM
   bytes across categories in proportion to the decompressed content.
7. Header gets data-asm, IPL3 gets code-asm/vendor, and ucode ranges are applied. Leftover
   zero / 0xFF runs become padding. The reviewed allowlist ranges are applied last, and only to
   GAP bytes.

## What --check fails on

- any GAP byte;
- a USO Text record that no code segment's function covers (uncompressed), or a compressed
  Text record that no Yay0 recipe lays out (the 2026-11-16 class);
- a function placed past its block, two functions that overlap, or a block layout mismatch;
- a hidden-code shape in any Data / RoData / BinaryDataSection payload (decompressed when Yay0)
  or in a linked bin outside the filesystem. A shape is `addiu sp,sp,-N` with `sw ra,K(sp)`
  (K < N) within 9 words and a `jr ra` within 2000 words. Today there are 0 hits in any data
  payload; every Text record has 3-194;
- a unit whose object is neither linked nor in a Yay0 block;
- a stale allowlist entry.

## The allowlist

The allowlist is `rom-coverage.allow` in the project root. Each line is
`RANGE 0xSTART 0xEND <category> <reason>` or `HIDDEN <section-label> <reason>`. A reason is
required, in the spirit of the `RAW:` / `UNNAMED:` tags. Entries only re-categorise GAP bytes
and never override a real attribution. An entry that matches nothing fails `--check`, so
delete it when the split is fixed.

## Results (2026-11-16, run 626)

| category | bytes | % of ROM |
|---|---:|---:|
| GAP | 0 | 0.000% |
| code-c | 675,147 | 4.024% |
| code-asm/src | 9,548 | 0.057% |
| code-asm/undecomp | 89,912 | 0.536% |
| code-asm/vendor (IPL3) | 4,032 | 0.024% |
| data-c | 368 | 0.002% |
| data-asm | 2,477,876 | 14.769% |
| asset | 13,416,770 | 79.970% |
| ucode | 102,304 | 0.610% |
| padding | 1,259 | 0.008% |
| total | 16,777,216 | |

Honest decomp %:
- **87.16%**: C bytes / game code bytes in the ROM (IPL3 and ucode excluded);
- 88.39% if hand-written asm counts as done;
- **88.33%** when Yay0 Text is counted at its decompressed (instruction) size:
  753,096 / 852,556 B, with 89,912 B not decompiled.

As a cross-check, report.json has total_code 852,412 and matched 762,652. That total is 144 B
smaller than the audit's 852,556 B, because it lacks the hidden 0x90 function, the eddproc stub
and a few delay-slot / static words. Its matched figure equals C (753,096) + hand-written asm
(9,548) within 8 B.

Of the 3577 functions, 3288 have a source body and 289 are INCLUDE_ASM. The INCLUDE_ASM ones are
all in the 8 new modules: trnproc 0x1CE0, viewrec 0x55B0, nameent 0x1510, balloon 0x570,
heli 0x1B60, fire 0x3B0, checkpoint 0x980, snoweffects 0xA900.

## Findings

1. **A hidden CPU function in a bin.** At game_libs VRAM 0xEBF8 (ROM 0xDF3CD0..0xDF3D60), the
   first 0x90 bytes of the `game_libs_text2_pre` bin are a 36-insn CPU function: alloc 0x40,
   init, store the vtable, list-insert into arg0+0x40. It is an `ItemType_create` sibling (cf.
   `edd_ItemType_create_000003BC`). No unit contains it, so report.json never counted it. It is
   allowlisted as code-asm/undecomp. TODO: split it out of the bin and decompile it.
2. **text2_pre / mid / tail are RSP IMEM.** Apart from that function, the rest of text2_pre
   (from 0xEC94), and all of text2_mid and text2_tail, are RSP code: COP2 / lqv / sqv, and j / jal
   into 0x04001xxx. This is 0x8CF0 B (36,080 B) that no public ucode matches. It is allowlisted as ucode.
   The yaml's "half CPU code" note was really just the one function above.
3. **eddproc's last function is unlisted.** At Text+0x478 is a 2-insn `jr ra; sw a0,0(sp)` stub
   (the same shape as titproc's `TitleDemoProcess_drawGui`). Its jr ra comes from a symbol-less
   `_pad.s`, and its delay slot is in the eddproc_uso_post bin, because PREFIX_BYTES shifts the
   C segment 4 bytes early. It is allowlisted as code-asm/undecomp.
4. **The Yay0 code blocks in the ROM are the baserom bins, not the C build.** The ROM link uses
   `assets/<blk>_yay0.bin`, which the pattern-rule order selects, and the carved
   `game_uso.bin`. The C for all six blocks (mgrproc, timproc / trkproc / genproc, map5_data,
   game) lays out exactly, but only `make verify-blocks` proves it, modulo reloc fields. The
   byte-identical ROM check does not cover them.
5. **PREFIX_BYTES encodes metadata as code.** Six USOs compile the Text record's flag word as a
   fake `beq zero,zero,+0x6F00` / `+0x736F` first instruction of `*_func_00000000`. The audit
   counts those 24 B as data-asm.
6. No data or asset payload, including the decompressed Yay0 data blocks, contains a function
   shape.

## Usage

```
scripts/rom-coverage.py            # summary table + honest decomp %
scripts/rom-coverage.py --gaps     # list every unaccounted range (ROM range, size, record / section)
scripts/rom-coverage.py -v         # per USO-with-Text breakdown + notes
scripts/rom-coverage.py --check    # gate mode
  --sourcemap port/sourcemap.tsv   # skip the ~10 s port-sourcemap regeneration
```

It needs a full build (`build/tenshoe.map`, `build/**/*.o`) and runs in about 11 s.
