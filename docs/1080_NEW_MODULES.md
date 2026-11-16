# 1080: the eight new code modules (set up 2026-11-16, agent-b run 617)

The "3288/3288 = 100%" figure covered only the segments the build config defined. Eight
code-bearing USO modules sat inside passthrough bins (`timproc_uso_inter34`, `timproc_uso_inter56`,
the carved `assets/game_uso.bin`, `bg8tex_uso`), so their Text was never split or decompiled.
They now have segments; the report reads **3288 / 3577** functions (code 762652 / 852412 bytes).

## Index
- Modules
- Layout and the 2-byte ROM offset
- How the asm was split
- Plumbing
- Notes for decomp agents

## Modules

| segment | module (id) | Info record | Text payload (ROM) | Text size | functions | what it is (strings / imports) |
|---|---|--:|--:|--:|--:|---|
| `trnproc_uso` | trnproc.uso (27) | 0x5B8CD2 | 0x5B90BA | 0x1CE0 | 40 | "TRAINRace Process": training mode process (Fader, PauseMenu, Process_*) |
| `viewrec_uso` | viewrec.uso (32) | 0x642312 | 0x64288A | 0x55B0 | 61 | "GENNewRecords Process": records / options screens (MainOptions, RecordOptions, EraseOptions, ReplayOptions; Backup_*) |
| `nameent_uso` | nameent.uso (33) | 0x64C68E | 0x64C89A | 0x1510 | 21 | "GENNameEnter Process": name entry (input_*, Backup_sessionSetNewNames); called from arcproc / mgrproc / timproc |
| `balloon_uso` | balloon.uso (47) | 0x7DECB2 | 0x7E2EDE | 0x570 | 11 | course object (SNode / PolyShape, fs_gdl load/save) |
| `heli_uso` | heli.uso (48) | 0x7E3D66 | 0x7F0A82 | 0x1B60 | 26 | helicopter course object (QNode, ItemType / ItemMgr, Sprite) |
| `fire_uso` | fire.uso (49) | 0x7F3E2A | 0x7F621A | 0x3B0 | 7 | fire course object (SNode, Sprite, gfx colour parms) |
| `checkpoint_uso` | checkpoint.uso (50) | 0x7F6D0E | 0x7FAC7A | 0x980 | 17 | checkpoint course object (CollObj cylinder / box, SNode) |
| `snoweffects_uso` | snoweffects.uso (60) | 0x90239E | 0x909926 | 0xA900 | 106 | snow effects (MorphPoly, CollShape, Parms, BaseMat) |

Total 289 functions, all `INCLUDE_ASM` (raw `.word` asm, `nonmatching` marker), so objdiff counts
them as unmatched. None of the eight is Yay0-compressed (flag bit 0x10000 clear on every record),
so there is no crunch64 block for them.

## Layout and the 2-byte ROM offset

Each module is `<m>_uso_pre` (Info record + header + Bss / RoData / Data records, up to the Text
payload) / `<m>_uso` (c segment, VRAM 0) / `<m>_uso_post` (Sym and reloc records). The c segment
starts at the Text **payload** (record + 12), so VRAM = USO Text offset and `<m>_uso_func_XXXXXXXX`
names equal the module's Sym values. (The older gui / h2hproc / arcproc segments start 4 bytes
earlier, at the record's flag word.) The containers keep their names for the part before the
first module and get a `_tail` bin after the last one; game.uso's region is linked from the
carved `assets/game_uso.bin` (now ending at 0x7DECB2) + the modules + the carved
`assets/game_uso_tail.bin` (0x7FC37A..0x84F6F8 = bg1tex.uso + bg2tex.uso), both in
`scripts/extract-derived-assets.py`.

**All eight Text payloads sit at ROM offsets = 2 mod 4**, not only checkpoint's: these files
follow modules whose sizes are not multiples of 4. No padding or instruction mechanism is
needed: the linker script's `AT(<seg>_ROM_START)` sets the section's load address exactly
(only the VMA, 0, is aligned), and `objcopy -O binary` writes the bytes there. The ROM layout
is unchanged and the ROM is byte-identical.

After pulling these commits an existing worktree must run `make setup` (splat `--modes bin`
regenerates the shortened container bins and the new pre/post bins; extract-derived-assets.py
re-carves game_uso.bin and adds game_uso_tail.bin).

## How the asm was split

`scripts/generate-uso-asm.py <seg> <text_rom> <size> --sym SYM_ROM:SYM_SIZE` (the Sym payload,
from the port extractor manifest: section rom_offset + 12). Function starts are:

- the module's Text symbols (Sym kind 2, section 5: exported functions);
- `addiu sp, sp, -N` prologues;
- leaf ends: a `jr ra` that no branch of the function jumps past, then zero padding;

minus **hoisted heads**: a non-Sym start whose preceding chunk has no `jr ra` and does not end
in a jump is dropped (22 cases: an exported entry whose `lui`/`lw` or float-constant loads were
scheduled above the stack adjust runs straight into the prologue). After that every function
contains a return and no branch leaves its function. Not checked: a Sym entry in the middle
of a function (a secondary entry), and jumptable targets (RoData relocs).

## Plumbing

- `objdiff.json`: one unit per module, `"complete": false`, one progress category each.
- `scripts/readability-gate.sh`: units marked `"complete": false` may hold unmatched functions;
  a new incomplete unit may be added whole. Everything else stays strict (a function at 100%
  must stay at 100%; counts may only change by the added units).
- `scripts/readability-census.py`: owner **n** = these eight segments. Their
  `<m>_uso_func_00000000` is a real function (Text offset 0), not a sentinel, and may be renamed.
- `scripts/name-placeholder-calls.py`: `src/<m>_uso` maps to module `<m>`.
- `scripts/uso-data-sites.py`: `--uso <m>` works for all eight (map Text, header
  `include/game/<m>_uso_data.h` when created); owner rule n.
- `scripts/uso-imports.py`: names their functions from the map; also finds snoweffects.uso and
  effects.uso, which store 0 where the other modules have the module magic.

## Notes for decomp agents

- Cross-module calls are `jal 0` placeholders with Text relocs; `scripts/uso-imports.py imports <m>`
  names every import (almost all go to bootup: Node / SNode / QNode, PolyShape, ColourItem,
  fs_gdlReadFile, hostio_*, Backup_*).
- The modules are probably C++ like the other mode USOs (their Data has `<Node>` / Process
  class strings; not verified per function): expect the NCC donor recipe
  (docs/MATCHING_WORKFLOW.md) for edg-only codegen.
- Data / RoData stay in the `_pre` bins; a function that needs its data matched against real
  relocs follows the existing mode-USO pattern (`uso-data-sites.py --uso <m>`).

## Decomp status (agent-b run 622)

3318 / 3577 after four commits on agent-b (f1df76db5, ea6f0b8a2, c0efb75a5, a8ff0ed81): 30 new
exacts, no NM wraps. Matched: fire 5/7, balloon 9/11, checkpoint 10/17, heli 3/26, trnproc 3/40.

- **Compiler: IDO 7.1 cfe -O2, as for game_uso.** The course objects are libgdl C++ (cfront
  `this == 0` allocating ctors, vptr at +0x28, 8-byte `{s16 delta, s16, fn}` vtable entries) but
  every member matched so far compiles from plain C in the module's own `.c`; no NCC donor yet.
- **Cross-USO templates are byte-identical** (.word for .word) across these modules: the gdl
  file int / float / Vec3 readers and writers (game_libs `fs_gdlWriteVec3_00037D48`,
  `fs_gdlWriteInt_0003D000`; game_uso `stream_readVec3_000001D4`, `stream_readS32_00000280`).
  Hash the `.s` words against matched functions first (heli 0/3C/AC and trnproc 268/2A4/338 were
  found that way); viewrec / nameent had none.
- **Spelling notes.** Local calls (`jal 0x60` in the ROM) are plain C calls to the module's own
  function; the .o holds 0 in the field and the link fills it (gate ROM check confirms).
  A RoData-base float (`lwc1 $f4, 0x1C(at)`) needs a different zero symbol from the Data-base
  vtable store in the same function, or uopt shares one `lui/addiu` (balloon 140 uses
  `gl_data_00000000`). `hostio_addFloat` takes floats in a3 / sp+0x10: call it through the typed
  alias `gl_func_00000000_ff`. hostioParms with the Node name: read `self->name` into a local
  first to get the target's `lw a1,12(a0)` before the s0 copy (balloon 32C).
- **Open: the template "create" shape** (fire 148, balloon 47C, likely checkpoint 6F0 / 7F4 /
  8E8): `new X(tmpl->sprite)`, a virtual handleMsg(19) through the vtable slot at +0x28, then a
  list link. The target keeps the new object in v1 (v0 reused for the vtable), frame 0x38 with
  the message at sp+0x2C, and leaves the `jalr` delay slot empty; cfe and NCC (real class + new)
  both give frame 0x30 and a filled slot (best 74%). The fire ctor 0 (inlined ItemType base +
  two `Colour::set(r, g, b, a) / 255.0f` inlines, divides not folded) reaches 78%: the target
  reloads 255.0f for the alpha dividend where cfe / NCC reuse the divisor register.
