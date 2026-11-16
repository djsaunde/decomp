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

### agent-b run 627 (3325 / 3577, +7 exact, 1 NM)

Matched: fire 7/7, balloon 11/11, checkpoint 13/17 (E0 NM 99.97%; 2AC, 45C, 58C open).

- **The template "create" shape is plain cfe C** (fire 148, balloon 47C, checkpoint 6F0 / 7F4): the
  message is a 12-byte `NodeMsg` plus one unused `volatile int pad` (frame 0x38 / 0x40, tag at
  sp+0x2C / 0x34); a code-free `if (o) {}` right after the ctor call moves o off v0 (v1, or s0 when it
  lives across later calls), which also gives the empty jalr delay slot; `if (1) {}` after the
  `gPolyFlags |= 8` store (bootup TreeTmpl_create) keeps the flag luis ahead of the branch. Same
  template as game_libs SNodeItemType_newItem (3DD28, NCC donor there). Checkpoint 8E8 is
  byte-identical to edd_ItemType_create_000003BC (body ported).
- **Local ctor calls in these bodies are `jal 0` in the ROM** (filled by the TextReloc), unlike the
  `jal 0x60` locals noted above: call them through `CALL(...)`. Check the ROM word before choosing.
- **File-end pads**: balloon 47C and checkpoint 8E8 are the last fns; their alignment pad words are
  `SUFFIX_BYTES_FORCE` + `TRUNCATE_TEXT` (Makefile, as TreeTmpl_create). Makefile-only changes do
  not rebuild the .o: delete it first.
- **Fire ctor 0**: the divisor is a local `d = 255.0f` (a literal `x / 255.0f` is folded by cfe); the
  alpha is the int `255`, a separate constant, so it is reloaded as in the target; the inline base
  ctor's call + vptr store on one line; `if (1) {}` after the FireTmpl vptr store.
- **Balloon 1A8** (display) = SNode_display + bob: NCC donor `balloon_uso_ncc_1A8.cpp`, ported from
  `game_libs_ncc_39E24.cpp` (the `Cam &` reference / inline `Cam::mul` keeps the GfxLib+0xA0 base).
- **Checkpoint E0** (cylinder ctor): all slots and instructions right except frame 0x40 vs 0x38
  (named shared `p` for the two inline CollObj ctors). Without `p` the frame is right and every
  slot one word low. 58C (box ctor) is likely the same shape.

## snoweffects.uso progress (agent-h runs 621, 628)

- 58 / 106 functions EXACT, 1 NM wrap (0x9E10, 98.27: item / head colouring swap). Commits on
  agent-h: 3e41f58f4, 6055e92bd, 07fa47f12, ca7cd7fd1, 2bb0df5fc.
- **Four TUs in one Text.** Each TU repeats the static fs_gdlReadFile reader helpers (int / float /
  quad / vec3 at 0xCC, 0x3D70, 0x7E20, 0x9250; static, so in-TU calls are resolved `jal` words) and
  ends with its Parm read methods (tag into a local, value at +0x10). TU ends: 0x3D64 (3-word pad),
  0x7E1C and 0x924C (1-word pads), 0xA900. The pads are all-zero `SUFFIX_BYTES_FORCE` on the TU's
  last function plus `TRUNCATE_TEXT 0xA900` (`SNOW_SUFFIX` in the Makefile).
- Calls to the module's own **global** functions (0x0, 0x3EE4, 0x535C, 0x64B8, 0x6B28, 0x718C,
  0x9328) are blank reloc'd `jal 0`: spell them `CALL(snoweffects_uso_func_X)`, or through a typed
  0-pinned alias when floats are passed (`gl_func_00000000_snow_hit`, `gl_func_00000000_snow_3ee4`).
  0x0 itself (Vec3 dot) can be called directly.
- **Compiler:** most small functions match as IDO 7.1 cfe -O2 C, but the module is C++: 0x9F44
  only matches under NCC (inline `Parm<T>::get()` keeps the parm base pointer; Vec3 user
  operator=), donor `src/snoweffects_uso/snoweffects_uso_ncc_9F44.cpp`. The DL builders (0x40B4:
  B6 / B7 / B8 packets through ctx->dl) are the `c->next()` NCC family (game_libs_ncc_59E80.cpp).
- Classes seen: SnowPool (Node + items[0x58] / count +0x3C / max +0x40, vtable slot 11 after
  init), SnowRing cursors at +0x58..+0x70 (0x46BC / 0x535C / 0x53E8), two ColourItem-based
  ItemType creates (0x7D8C / 0x91BC = edd_ItemType_create_000003BC twins), an SNode subclass
  (0x9704 display with blend colour at +0x288, 0x973C loadData with Parms at +0x240).
- Run 628 (agent-h, commits 0900e6b68 a06434c4e 56eee9201 94f5b6125, renames 26a8204d8): +9 EXACT,
  67 / 106: 0x3EB0, 0x3EE4, 0x4714, 0x6420, 0x70C0, 0x7F60, 0x9010, 0x9E88 (cfe C) and 0x40B4 (NCC
  donor). Renamed: SnowRing_init / _draw / _setSlotState / _advance / _countSlots, SnowPoint_clear,
  SnowLink_ctor / _update, SnowPool_init.
- Levers found in run 628:
  - A second `mtc1 zero` register is the **int 0 of a chained assignment** (`z = y = x = 0` stores z
    first); a `0.0f` chain shares the first register.
  - **RoData floats** (0x3EE4 / 0x6420 / 0x70C0 / 0x9010) each take their own `lui at`, so give each
    constant its own pin (`snow_ro_<K>` in undefined_syms_auto.txt). `D_00000000 + K` CSEs the lui.
    Store order: hill-climb over the statement order (a 20-line generator plus diff count is enough).
  - **Vtable stores** carry the Data offset in the USO reloc (lo16 = 0 in the ROM), so they need a 0 pin
    (`snowLink_vtbl_9C4`); a name / string pointer (Data(base) + K) keeps K in the immediate. The .o
    diff against expected/ hides this: check the ROM bytes.
  - Cfront ctors (0x9E88) match in cfe as `if (this != 0 || (this = mem_new(N)) != 0) { .. } return this;`.
  - A vcall cast to a void return (`((void (*)(void *))VT_SLOT(..).fn)(..)`) frees v0 for a later
    constant (0x3EE4).
  - NCC `c->next()` packets (0x40B4): `Gfx *next() { int n = dl->count++; Gfx *g = &dl->buf[n]; return g; }`
    gives v1 = context, v0 = head. Shared class header `src/snoweffects_uso/snoweffects_ncc.h`, donor
    `snoweffects_uso_ncc.cpp`, list `SNOW_NCC_FUNCS` in the Makefile.
- Open: 0x6144 / 0x6248 (`new` of an SNode-derived child with an inlined base ctor (this == 0
  protocol), attached to the groups at +0x238 / +0x234, then virtual slot 10 (arg 8 / 16). Best NCC: 15
  diffs. The target spills the attach parameter at sp+0x2C, but the parent test and the unk04 store go
  through the new-result register s0), and every function above 60 words.

## trnproc.uso / nameent.uso progress (agent-c run 631)

- trnproc 28 / 40 EXACT, nameent 17 / 21 EXACT + 1 NM (0x150, 41/45 words). Commits on agent-c:
  9be01eee9, 8f968f793, 3b99ebf4d, 09f59fd23, 5600c6097 (3376 -> 3416).
- **Own-section relocs carry the offset in place.** A Bss-base / Data-base TextReloc site holds
  K (e.g. `lw a0, 0x1B0(a0)` for trnproc Bss+0x1B0). Spell it off a fresh symbol pinned at 0 in
  `undefined_syms_auto.txt` plus the offset: `trn_bss` (Bss+0x1B0 = gTrnRace, the running
  process), `trn_data` (trnproc Data), `ne_data` (nameent Data, name string at +0x140). A
  separate symbol also keeps uopt from sharing the lui with the D_00000000 imports.
- **trnproc is the timproc / trkproc sibling.** Ported as-is: stream readers 268 / 2A4 / 2E0 / 338,
  Parm reads 1B84..1CA4 (tit_read*Parm), ItemType create 1C14, onPauseSelect 858 (TimRace's body
  with its `if (1) {}` / `^ 0` / `new_var = 0x90` levers + a dataManager +0xFC guard), pause rows
  1B0 / 1E4 / 214. Its DataManager (RaceTracker subclass) runs the trick lessons: +0xF0 current
  lesson, +0xF4 armed, +0x114 trick done, +0x108 lesson count, done bits at race +0x6B0
  (1324 / 13A0; 180C picks the next lesson through 1778).
- trnproc .text pads: 1 zero word after 1A4 and 3 after 1CA4 (`TRN_SUFFIX` + `TRUNCATE_TEXT 0x1CE0`).
- nameent: phase (+0x60) dispatch through the own vtable (slots 14-16 update, 17-19 display);
  0x150 NM: cfe colours the phase v1 where the target uses v0 (0x204, same switch with self in s0,
  matched).
- Open: trnproc 10 (procMain, RoData jumptable), 3A8 ctor (0.82 to TimRace_ctor), 6CC (18
  gui_spriteInit), A2C, B78 / DD4 (HUD draw), 1098, 13C4, 16C8, 1778, 188C (update), 1A98; nameent
  2F4 (board draw), 5B4, 760 (entry ctor), 9BC, E44 (input, 435 words).

## heli.uso progress (agent-g run 632)

- 21 / 26 EXACT, 2 NM wraps (0x3F4 99.0, 0x4C0 90.7). Commits on agent-g: 2a7e04130, feedcaf7e
  (exacts), 403bded79 (NM wraps). Open: 0x8A8 (flight-state reset leaf, store scheduling), 0x980
  (walks the "hem" ItemType's items for id 8), 0xB08 (943-word update: fsin / atan2s / acosf path
  flight).
- Classes: HeliItemType (0x54, ItemType + body / blade PolyShapes +0x48 / +0x4C, Sprite +0x50),
  Heli (0x174 QNode, vtable Data+0xCA88, start position +0x108, flight state +0x114..+0x170),
  HeliRotor (0x118 QNode, spin speed +0x108, axis +0x10C), two 0x40 marker ColourItem creates.
- Levers that worked here:
  - global vs static local calls: 0x0 / 0x3C / 0xAC / 0xE8 are static in the original (resolved
    `jal` words: call them directly), 0x388 / 0x4C0 / 0x8A8 are global (blank `jal 0`: use
    `CALL(heli_uso_func_X)`). A direct call to a global gives a linked non-zero word that a
    reloc-blind .o compare misses; only the gate's ROM check catches it.
  - 0x274: one alias per gPolyFlags access, `if (1) {}` after the first RMW keeps the
    geometry-mode base out of the entry block; ctor args through locals in blades / body /
    sprite order give the target's a2 / a1 / a3 load order.
  - 0x1D4: the ItemType base ctor is inlined with its own this == 0 allocation and a by-value
    4-byte name tag (`sw a1, 4(sp)`), item_createBal recipe with one volatile pad.
  - 0x7B4: `beq 9; beql 7; b out` = `if (m == 9) goto A; if (m != 7) goto out; goto B;`.
  - RoData floats loaded `lui at; lwc1 K(at)` per site need a distinct zero symbol per load
    (a shared symbol, or a float[] extern, is CSE'd into an s-register).
  - A zero store that the target materialises in its own `mtc1 zero` (while call args share
    f20) is a separate constant web: `(float)0` int-cast literal.
- NM wraps spell the raw placeholder tokens: the named-call check cannot prove CALL() sites
  whose build path is INCLUDE_ASM.

## viewrec.uso progress (agent-a run 630)

- 15 / 61 EXACT, 9 NM wraps. Commits on agent-a: 83815e438, 93bf4f8b3 (3391 / 3577).
- **Every jal is a reloc'd `jal 0`**, local calls included: spell all of them `CALL(name)`.
  NM bodies use plain `gl_func_00000000(/* name */ ...)`; the placeholder-call check only reads
  the matching build, where an NM function is INCLUDE_ASM and has no relocs.
- **Bss statics are separate objects.** Each access has its own `lui`, and a static that is
  stored and then reused has its address folded into the `addiu` (`addiu v0,v0,0x87C; lw 0(v0)`).
  `(char *)&D_00000000 + K` cannot give that: uopt keeps `&sym` and the K apart. So each static is
  an extern pinned at its Bss offset in undefined_syms_auto.txt (sVrSprites 0x0, sVrLabels 0x1F8,
  sVrPrimColour 0x858, sVrEnvColour 0x868, sVrMenu 0x878, sVrProc 0x87C, sVrScreen 0x880).
  objdiff ignores relocated fields, so check the bytes with the pins applied (or the ROM). Gui
  Bss+0x8 (gui_setEnvPrimColor arg 0) is `&D_00000000` with no offset.
- Text ends at 0x55B0 with one zero word after 0x55A4: all-zero SUFFIX plus TRUNCATE_TEXT.
- **NCC donor** `src/viewrec_uso/viewrec_uso_ncc.cpp` (multi-function, `VIEWREC_NCC_DONOR`):
  0x1664 needs edg's virtual-call lowering (object in v1, vptr in v0). Add further C++ functions to
  the same file plus a `REPLACE_FUNC_BODY +=` entry.
- Open:
  - 0x0..0x214, the six screen switches: the target does `or v1,v0,zero; lw v0,40(v0)`, one move
    longer. Not reproduced by cfe, plain NCC `sVrScreen->start()` or an inline setter.
  - 0x290, the colour init: four `lui at` pairs over 0x858..0x874. This is as1 sharing `%hi` within
    one file-local static (IDO_CODEGEN kit LX), so it needs an NCC donor over a `static` object.
  - 0x2F1C: NCC `Colour(255,175,44,255) / 255.0f` is 1 word off. The target reloads 255.0f into a
    separate dividend register, the same open problem as fire's ctor.
  - 0x1488 (frame 0x28) and 0x2F1C (frame 0x38) both have an 8-byte gap below the sprite slot at
    sp+0x1C, which looks like an edg temp.
  - 0x14DC: sprite loop, sVrLabels[57 - i].
  - 0x1068 / 0x18D4: v0 / v1 swaps.
  - Untried: 0x2D0 (process ctor: mem_new 0xE0 / 0x50 / 0x2C, the cfront alloc chain), the sprite
    tables 0x718 / 0x8C8, and every function above 0x1A08 not listed above.
