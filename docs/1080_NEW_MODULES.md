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

### agent-b run 634 (3395 / 3577, +3 exact; checkpoint 16/17)

Commits on agent-b: cf4671b3b (E0, 58C, 2AC EXACT), 85ae105dd (episodes), f8fdf28fd (31 renames, pure).

- **CheckpointCyl_ctor (E0) frame fix:** only the inline CollObj ctor's `p` is a named local; the
  CollObj addresses are plain `self + K` expressions (uopt CSE temps, spilled at sp+0x30 / 0x2C).
  Named `c1` / `c2` locals each keep a dead home word (frame 0x40 instead of 0x38). Generally, a
  named scalar that uopt keeps in a register can still own a frame home: when the frame is one or two
  words too big, turn named temporaries back into repeated expressions. **CheckpointBox_ctor (58C)**
  has the same shape with one CollObj and matched on the first try.
- **CheckpointCyl_handleMsg (2AC)** places the gate posts at (-/+ 117 / worldScale, 0, 0) through the
  SNode Mtx plus pos. It needs `z = 0.0` (a double literal; with `0.0f` the `m * z` terms fold away)
  and right-nested sums `m[12] + (m[8] * z + (m[4] * z + m[0] * x))` (IDO evaluates the right operand
  first). `float *m` declared before the two Vec3 temps puts their homes at sp+0x5C / 0x50.
- **45C is still open.** It is a leaf predicate (frame 0x90): `(p - postA)` and `(p - postB)` in the
  XZ plane, dot < 0, so p lies between the posts. Its shape is C++. Each `*p - post` is built in a
  V3 temp, copied by words to a return temp (sp+0x54), then to sp+0x1C. The first result is
  float-copied into u (sp+0x84) with a user `operator=`. The second is read from sp+0x1C directly.
  The dot is `u.x * w.x + Z * Z + u.z * w.z` with Z an `mtc1 zero` that is not folded, and the post
  base is held in v0 (`addiu v0, a0, 0xA4`). An NCC donor gets the copy chain and the `bc1f; b; li 1`
  tail, but its post loads fold into a0 offsets and the y = 0 vectors spill. Best result: 85
  word diffs. cfe C gets the copy chain too, but folds the post base. Next try: a `const V3 &`
  local for the post, and the XZ dot as an inline taking the two vectors by value.
- Renames (fire / balloon / checkpoint): FireTmpl_create / _declColourParms / _display,
  Fire_ctor / _display / _hostioParms, Balloon_ctor / _display / _saveData / _loadData /
  _hostioParms / _handleMsg, BalloonTmpl_create, CheckpointCyl_* and CheckpointBox_* (ctor, loadData,
  saveData, hostioParms, handleMsg), CheckpointCylTmpl_create, CheckpointBoxTmpl_create,
  CheckpointColourItemType_create, plus the per-TU gdl helpers `balloon_gdl*_<addr>` and
  `checkpoint_gdl*_<addr>`. The `*_00000000` functions (FireTmpl ctor, the balloon / checkpoint gdl
  writers) are refused by rename-symbol.py as zero-address names.

### agent-b run 640 (3474 / 3579, +4 exact; checkpoint 17/17)

Commits on agent-b: 3d2acf56d (checkpoint 45C), 200bd12fd (snoweffects 5FD4 / 6144 / 6248), c6013172d
(episodes), 2b76bdf85 (rename-symbol.py module-zero exception + Fire comment fix), 8c64a9f05 (3 renames, pure).

- **Checkpoint 45C EXACT** (NCC donor `checkpoint_uso_ncc_45C.cpp`): `u = pos - *a; w = pos - *b;
  w.y = u.y = 0.0f; f32 d = u * w; return d < 0`. V3 with a ctor-temp `operator-`, a by-value
  `V3 &operator=(V3 v) { set(v); return *this; }` and a dot `operator*`. Three edg / uopt levers:
  (1) `operator=` returning `V3 &` instead of `void` moves the first ctor temp 4 bytes up (0x40 -> 0x44);
  (2) `const V3 &pos = *p` then `pos - *a`: the binary operator on `*p` itself gives a different temp
  layout (as do `(*p).sub(*a)` and `p->operator-(*a)`, which also match); (3) the dot in a named `d`:
  uopt colours d (f16) and the zero (f18), which removes both from the FP temp ring, so the z loads
  reuse f4 / f6. The kept post pointers are the 3B01C `if (0) { a = 0; }` lever.
- **snoweffects 5FD4 / 6144 / 6248 EXACT** (NCC donor `snoweffects_uso_ncc_b.cpp`, own Makefile block
  `SNOW_B_DONOR`): SnowEffect::init / createA / createB. `lnk(childA = new SnowChildA, grpA); lnk(childA,
  grpB); childA->v11(8);` with a free inline `lnk(Node *q, Node *s)`. Putting the `new` inside the first
  attach's full-expression gives the inline ctor's `this` and q separate edg pool words (as two statements
  they share one, and the ctor's this is coloured a2). list_append goes through a void-typed alias
  (`gl_func_00000000_snowb_v`): v0 is forbidden through a value-returning call's block, and the target
  keeps the group in v0. The SnowNode base ctor is inline (edg's this == 0 protocol around the
  out-of-line Node ctor); vtables / Node ctor renamed by objcopy to 0 pins.
- **rename-symbol.py** now renames `<seg>_func_00000000` when it is a module's own offset-0 function
  (defined as code only in src/<seg>, not pinned, not a uso_call.h token, no object or tracked file
  outside the segment uses it). Renamed FireTmpl_ctor, balloon_gdlWriteVec3, checkpoint_gdlWriteInt.
  Placeholders (gl_func_00000000, game_uso_func_00000000) are still refused.

### agent-b run 646: viewrec.uso 0x3000..0x47FF (3506 / 3579, +3 exact, 1 NM)

Commits on agent-b: 60626bf48 (36B4, 4518 EXACT; 4354 NM 84%), d1fad96a6 (3364 EXACT), e7a3d33de (episodes).
No renames.

- **Screen ctors 0x36B4 (erase, 200 bytes) / 0x4518 (replay, 0x9C)**: cfe C, the trnproc / h2h cfront
  chain Node (0x2C) -> Process (0x50) -> screen, each level `if (o != 0 || (o = mem_new(N)) != 0)`.
  Lever: `CALL(Node_ctor)(o2, name); NODE(o2)->vptr = vt;` on ONE source line. On two lines the vptr
  lui/addiu are split by the o1 reload (1 word off). Vtables are 0-pinned per-site externs
  (`vr_vtNode_*`, `vr_vtProc_*`, `vr_vtErase_36B4`, `vr_vtReplay_4518`). The other screen ctors (0x1748,
  0x1B4C, 0x4854, 0x5200) should be the same shape.
- **0x3364 (arcade records draw) EXACT**, cfe C. (1) The divisor `d` is declared first, so its home sits
  above the three colour arrays (sp+0x74 / 0x84 / 0x94). Use int numerators over `d`. (2) Use do-while
  loops: the outer one gives the loop-end increment order, and the inner one is
  `j = 0; if (n > 0) do {...} while (j < n);`. (3) `show = 1` goes after the entry read. (4) Spell the
  row-counter updates on the array element: a named temp costs one more frame home and moves the frame
  by 8.
- **0x4354 (erase pad handling) NM 84%**: the logic is right. Pad: 0x10001 / 0x4002 pick yes / no
  (+0x70). A erases the set in proc+0x70: 0x100000 course times, 0x200000 course scores, 0x400000
  arcade, 0x800000 ghost, 0x1000000 all (procState = nextProcState, unk84 = 0, unk88 = 1, resetAll,
  fadeOut). The target colours the switch value v0 and the reloaded proc v1; ours gets v1 / a2, with
  the &GameFlow lui hoisted into the last beq slot. Tried with the same result: switch, if-chain,
  default:, a proc local, a switch-value local, every store order, `if (1) {}`, a separate GameFlow
  symbol, and an NCC version of the same body.
- **0x319C (course scores draw) is still INCLUDE_ASM**. The best body is 92%, but it is 2 words
  longer than the target, and an NM wrap that changes length pushes 0x55A4 past the non-matching
  TRUNCATE_TEXT (the gate then reports 55A4 at 33%). Decode: `d` first, colour 40 / 100 / 255 / 255
  over d; `course = self+0x98`; gui_setCombine(&gui Bss+8); 0x1488(proc, course, 83); 3 entries with
  e = Backup_courseRecordGetScore(*session + course*48, i); show = !(Backup_scoreEntryIsNew(*session +
  course*48 + 24 + i*8) && proc flags & 8); rank = (prev == e->score) ? -1 : i; then 0x29B0(self, rank,
  38, y, e->b0 & 7, (e->b0 & 0x78) >> 3), 0x2AE4(self, 132, y, e + 1), 0x2D9C(self, 196, y, e->score,
  col); y = 123 + 34 * i. Open problem: in a structured loop, uopt hoists &col into s8 and spills
  course*48, but the target keeps course*48 in s8 and does not CSE the second course*48. Next tries:
  course*3*16 spellings, and the 0x3364 levers (do-while, `show = 1` after the call).
- **Not started:** 0x3878 (records draw, 431 lines) and 0x3F24 (erase-select pad handling, 272 lines).

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
- Run 635 (agent-h, commits 26a45c247 2a2fcfa1a, renames 46edeea35): +7 EXACT, 3399 / 3577:
  0x718 SnowPool_remove, 0xA7C SnowPool_spawn, 0x3620 SnowFall_copyCamRot, 0x374C
  SnowFall_buildFrustum, 0x544C SnowRing_update (cfe C); 0xB44 SnowPool_update and 0x27A8
  SnowFall_moveFlakes (NCC donors in snoweffects_uso_ncc.cpp). NM: 0x97C SnowPool_spawnRandom (63 / 65,
  the p reload after the first sys_randf sits one slot above the mul.s). 27 renames (reader / Parm
  read families, SnowPool / SnowFall / SnowPlane). Range split: agent-h < 0x6000, agent-e >= 0x6000.
- Levers found in run 635:
  - **The particle code is C++:** `pos += vel` integrations only schedule like the target through a
    user `SnowV3::operator+=` (NCC), C's three statements put y before z (0xB44, 0x27A8).
  - **Loop-invariant float literal** (`lui at; lwc1 f,K(at)` hoisted above the loop, K = RoData
    offset): a pinned extern / `&D + K` is not hoisted (aliasing). Write the literal in an NCC/cfe
    donor and pin `<func>_rodata = K` (0x27A8: 0.0015f at RoData+0xC). RoData+0 is -0.02f (0x97C
    gravity), dumped with uso-imports.py's Module(rom, 0x9023aa, ..).secs['RoData'].
  - Calls to in-module globals with a float argument need a typed 0 alias, or the K&R double takes
    the outgoing-arg area +8 (gl_func_00000000_snow_35b0, 0x374C).
  - 0x374C: `pl++` inside the call argument gives the target's spilled first pointer plus the s0
    walker; one unused `int pad;` moves the spill slot to sp+0x34; signed `(char *) diff / 16`.
  - 0x544C: the outer counter bump between `j = 0` and the inner for (`for (k = 0; k < n;) { ..
    j = 0; k++; for (; j < ..`).
  - 0x718: a `last` local for the compare (CSE of the first copy), frame from `int pad[2]; Vec3 t;
    int pad2[2];`.
  - sys_randf `* 2.0f` keeps mul.s as `r * 2` (int 2); `(0, 10.0f) + r * 2` puts the constant first.
- Leads (below 0x6000): 0x4188 (DL setup: E7 / BA001402 / B900031D / FC409881 packets, guMtxIdentF,
  guMtxF2L into Bss+0, G_MTX 0x01020040 with osVirtualToPhysical, BA001001 / BA001301 / BB000001):
  NCC with `next() { return &dl->buf[dl->count++]; }` (no named locals: each named inline local takes a
  frame word), `if (1) {}` after packet 3 and `int pad[2]; (void)pad;` after the matrix is 3 diffs (packet
  3's slot register v0 vs a3). Draft in the run-635 report. 0x5FD4 is the 0x6144 / 0x6248 shape (ctor
  with inlined child `new`), leave with agent-b's pair. 0x97C: try a permuter on the 2-word swap.
- Open: 0x6144 / 0x6248 (`new` of an SNode-derived child with an inlined base ctor (this == 0
  protocol), attached to the groups at +0x238 / +0x234, then virtual slot 10 (arg 8 / 16). Best NCC: 15
  diffs. The target spills the attach parameter at sp+0x2C, but the parent test and the unk04 store go
  through the new-result register s0), and every function above 60 words.

- Run 644 (agent-h, no commits, no exacts): findings for the next pass.
  - **0x4188 (3 diffs) is a live-unit boundary, not a priority tie.** Instrumented uopt
    (`/tmp/claude-1000/h414/u/out/NCC -Wo,-zdbug:5`, then h384/t/lre.py + h414/t/ord.py; wrapper
    /tmp/claude-1000/agent-h/iu/tr.sh) shows packets 1-2 fill live unit 0 and unit 1 starts right before
    packet 3's `&buf[n]` result. The target's packet-3 a3 needs that result defined in unit 0 and stored in
    unit 1 (then it is forbidden v0 / a0 from packets 1-2, a1 from the parameter, and v0 from packet 4).
    Removing ANY one store from packets 1-2 gives exactly that layout, so the original packets 1-2 carry one
    fewer counted memory op than ours. Flat (all 3-6 diffs): `if (1) {}` at every 1-3 statement positions,
    next() body spellings, put()/Gfx::set()/pk() emitters, comma / chained stores, named and reused
    packet locals, `& 0` phantoms via t (edg folds them: no unit effect), the header's two-local next()
    on 0-2 packets with 0-2 pad words. Next: find a code-identical spelling of packet 1 or 2 with one fewer
    ucode memory op (try a gbi macro with a `(Gfx *)` cast pkt, `*g = gfx_const` struct copies, a
    file-static `Gfx` template copied by value).
  - **0x97C**: a manual permuter scratch (`nonmatchings/p97`: minimal base.c, cc compile.sh, target.o
    assembled from the .word .s with ~/.local/bin/mips-linux-gnu-as and glabel / endlabel / nonmatching
    macros; run with /home/danjs/code/decomp/.venv/bin/python, which has toml) plateaus at score 25 in
    2 x 100 s (that is the 2-word swap). The NCC SnowV3 draft (/tmp/claude-1000/agent-h/t97.cpp) is
    11 diffs, worse than the C.
  - **0x39C4** = SnowFall fill: unk98[3] = camera pos * worldScale (scale loaded first), then for
    i < this->unk40 (+0x40): p = alloc(this); if (p) { d = randf*100, a = (randf-.5)*60,
    b = (randf-.5)*60; pos = unk98 - camRotT[2]*d; pos += camRotT[1]*b; pos += camRotT[0]*a; unk38 1,
    unk40 0, unk44 0, unk3C 1, unk24 RoData+0x14, unk28 -1, unk2C randf*360, vel.x / vel.z (randf-.5)*0,
    vel.y -(randf*2.5)-1, accel.y 0, accel.x / .z (randf-.5)*RoData+0x18 / +0x1C, unk34 / 50 / 54 0,
    col 251,251,251,0, unk30 256; count++ }. cfe draft (/tmp/claude-1000/agent-h/se_39c4_draft.c):
    shape right, but pinned RoData externs get hoisted into s4-s6 (frame 104 vs 88) and the `+=` adds
    come out product-first. Next: NCC donor with the RoData floats as literals (`<func>_rodata` pin, as
    0x27A8) and `x += v.x * s` member statements.

### snoweffects.uso 0x6000+ (agent-e run 639)

- +2 EXACT (commit feb67fb6a on agent-e): 0x8C60 and 0x9FE8, both IDO 7.1 NCC. Own donor
  `src/snoweffects_uso/snoweffects_uso_ncc_e.cpp` + header `snoweffects_ncc_e.h` (includes agent-h's
  `snoweffects_ncc.h`), Makefile `SNOW_NCC_E_FUNCS` block at the end of the Makefile.
- **0x8C60** = SnowRing_draw (0x40B4) twin in the third TU with a 4th packet (B9 SetOtherMode_L
  0x031D / 0x404A50; B7 is 0x2205 here). The target colours the first append ctx v0 / head v1 /
  count a0 (the opposite of 0x40B4): first append `me(me(t->dl))->nextr()` (two zero-code inline
  levels + unnamed-index append), the rest an inline `put(w0, w1)` emitter. A random per-site search
  over ~15 append spellings (scratch script, 100 s) found it; greedy alone plateaued at 5 diffs.
- **0x9FE8** = a light's colour contribution: bootup Bss+0x3C168 is gGfxLib (scale Vec3 at +0x128, the
  camera root at +0x254, as balloon_uso_ncc_1A8.cpp); v = pos (+0x5C) field-wise, `v *= scale`, n = v,
  normalize(n), d = dot(module Bss+0x50, n); d > 0 adds d * colour (+0x288, the Parm<Colour> value of
  SnowTarget) to *out. Frame / slot levers: declare both Vec3 locals up front and assign `n = v`
  (`Vec3 n = v` puts n 8 bytes low); reach the scale through `Vec3 *gp = ..; const Vec3 &g = *gp;`
  (frame 0x48 -> 0x50 and the separate lui/addiu base).
- Open, best so far:
  - **0x9768** (SnowTarget dirty check, 71 words): if colour.rgb / f98 / f9C / drawPos differ from
    the parm values and pos, flag (Data+0xA30, 0 pin) = 2 and copy them (9F44's copy set). NCC, 4 diffs:
    compare `t->pos.x != t->drawPos.x` order matches; only the drawPos copy loads come out z, y, x
    (target x, y, z in f4 / f6 / f8). Tried: statement orders (120 perms), temps, reference / pointer
    locals, me() per component, user / default operator=, set(): all z-first.
  - **0xA760** (cull pass over the ItemType named by Data+0xA80: `ItemMgr_findType(*D_bu_776C, Key)`,
    Key by value (sw a1 to sp+0x5C and the 4(sp) home), Iter {cur, nxt} walk, cam_isSphereInView(root,
    3, pos, 0, 0.0f) sets f234 |= 4 when f22C && f2AC): 14 diffs. Key as `Key k; k.w = *(int *)..`,
    `while (it.next())` with the body reading `it.get()` (cur->obj) three times gives the right
    instruction stream; left: Iter slot at sp+0x50 vs target sp+0x44 (12 bytes of unexplained locals
    above it) and the `or s0,v0` placement.
  - **0x9E10** (NM 98%): NCC inline attach() reproduces the target's a2 -> a1 copy but swaps item / head
    (a2 / v1 vs v1 / a2); cfe forms give no copy (4 diffs). Not landed.

### snoweffects.uso 0x6000+ (agent-e run 645)

- +3 EXACT on agent-e (3499 -> 3502): 43f357ec5 0x9C48 (cfe C), a0d94b6a5 0x9768 (NCC donor in
  snoweffects_uso_ncc_e.cpp), cfb37324f 0xA760 (cfe C). 9f171435a: 0x9E10's NM body is better (26/30).
  No renames (renames cancelled by the user).
- **0x9C48** (flicker colour pass): timer +0x238 / period +0x2C4 / step +0x23C over a sequence from
  the pointer table at Data+0x958[+0x2AC] (0 pin `snow_flickerTbl_958`); brightness / 255 scales each
  vertex's alpha into an int k, `rgb += colour(+0x288) * k`, clamped to 255, into the mesh colours
  (+0x50) at vertex +0xAC[i], then MorphPoly_applyUpdateList. Levers: `(unsigned int)` on the alpha
  (the target's cvt fix-up), `int k` with `r += c * k` (from 64 diffs to 8), and a typed struct
  (SnowGlow) in place of `char *` offsets puts the `vals` load before the step load.
- **0x9768**: a pointer local for the copy (`SnowVec3 *p = &t->pos; t->drawPos.x = p->x; ..`) gives the
  x, y, z load order (agent-g's heli lever). `const V3 &a = t->pos` works too. Named float locals
  colour f0 / f2 / f12, and a struct copy or a temp gives the z-first order. New 0 pin
  `snowDirtyFlag_A30` (Data+0xA30; 0x9F44 and 0xA10C store to it too).
- **0xA760** is cfe C, not NCC: the hud_findMarkers_000029F8 iterator macro. Frame: the iterator is
  **block-scoped inside `if (type)`**, so it sits below the struct-argument copy of the by-value key;
  one `char padA[8]` sits between the key and the iterator. `item = it[0]->data;` comes before tests
  that read `it[0]->data` again (the target's v0 -> s0 copy). Pins: `snow_itemMgr`, `snow_gGfxLib`,
  `gl_func_00000000_snow_cull`.
- **0x9E10** NM 26/30: `if (head != 0)` on the local gives item v1 / head as the target. Left: the
  target loads head into a2 and copies it to a1 in the beqz delay slot.
- **0x8D70** (168 words; two CollShape probes through 0x52D4 for the +0x120 / +0x12C points, pushing
  each back by -d * normal when 0 < d < +0x15C; +0x148 = -dot(+0x114, +0x108); +0xD4 = +0xC4): NCC,
  best 40 diffs (76 %, not wrapped). Draft: /tmp/claude-1000/agent-e/draft_8D70_ncc.cpp. It uses
  `SV operator=(SV)` by value, `operator+=(SV)` by value, and an operator* that builds `SV r` through
  `set()`. The instruction stream is right apart from colouring. The residual is the frame: target
  168, draft 144. Target slots: n 0x9C, shared temp 0x84, if-1 r 0x60 / param 0x70, if-2 r 0x28 /
  param 0x34. So each if has its own by-value parameter word (the draft shares one) and 4- / 8- /
  32-byte unused words. Next: find which inline shape materializes per-expansion parameter words
  (MATCHING_SUMMARY §5; the -O0 -g2 mdebug oracle names them).
- Not started: 0x64B8, 0x6B28, 0x718C, 0x7960, 0x7FE0, 0x9328, 0x9884, 0xA10C.

### snoweffects.uso 0x6000+ (agent-e run 650)

- No new exacts. Commit 004e8b58d on agent-e: NCC near-miss drafts for 0x7960 and 0x9884 in
  `src/snoweffects_uso/ncc_drafts/snoweffects_nm_e.cpp` (not built; pointer comments above both
  INCLUDE_ASMs). The draft calls callees by real name, so the gate's placeholder-call check skips it
  (a `#ifdef` block in a built donor is still scanned and fails the gate).
- **0x9884** (203 / 217 words; snow light vertex list rebuild): restore the saved colours, free the
  update list, p = pos (+0x5C) field-wise, `p *= g` (g through `SV *gp; const SV &g = *gp;`, gGfxLib
  +0x128), p.y += +0x270, then for unsigned i < mesh +0x40: vf = PolyShape_getVertex shorts, `SV dd = p - vf`
  (operator- returns `SV(a.x - b.x, ..)`), len = dd.length(); 0.1 (RoData+0xF0) < len < radius (+0x258)
  stores the index (+0xAC) and alpha (1 - len / radius) * 255 (+0x12F), 64 caps it (`i = count`).
  Levers: the named dd gives the target's copy at sp+0x90; computing `f` before the vtx store gives the
  f12 radius colouring. Left (14 words): p sits at the top slot (0xD0) but the target has p at 0xB8 under
  vf (0xC4) with 16 unreferenced bytes at 0xD0..0xE0. Unused pads are dropped; `(void)pad` pads and
  `SV q` reshuffle the temps. Next: find which inline temporary the original allocated first (an
  operator returning SV by value whose result is discarded?).
- **0x7960** (194 / 219; trail head update): +0x148 = -dot(+0x114, +0x108), angle = acosf of it, negated
  when dot(cam +0x318, cam +0x3C8) < 0; +0x144 = 0; |+0x4C| >= RoData+0xB4 then d = 0x52D4(this, +0x138,
  &n, +0xD4); 0 < d < +0x15C: `pos += n * -d`, +0x144 = 2, a = (cos * +0x3C, 0, sin * +0x40) and b with
  the negated widths, each transformed by the +0x30 matrix. The transform is three float locals stored
  after all three are computed (z' spills to the stack: no FP register left). Left: frame 168 vs 176
  (target normal at 0xA0, push temps 0x68 / 0x74 / 0x84) and zero / fabs register swap.
- **0x9E10**: NCC with an inline `attach()` member and a named head local is 4 diffs, the same as the
  cfe NM (head lands in a1 with beqzl; the target keeps it in a2 and copies to a1 in the beqz delay
  slot). Tried: child-side link(), reference parameter, copy local in attach, free attachTo(): all 4+.
- **0x6B28** decoded only to the first third (flag 0x820000 picks one of two RoData default sets for
  +0x1B0..+0x1C4; counters +0x1C8 / +0x1CC driven by the course state at cam +0x9A0..+0xA20; then the
  camera-relative spawn with sys_randf and SnowPool_alloc / _oldest). 0x9328 is the SnowTarget Cfront
  ctor (SNode_ctor, Parms at +0x240 with 5 inline Parm ctors, names read from Data+0xA44..+0xA54 by value);
  the timproc_uso_b5_ncc_2B74.cpp SelItemParms_ctor donor is the model.
- Not started: 0x64B8, 0x718C, 0x7FE0, 0xA10C.

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

## trnproc.uso / nameent.uso progress (agent-c run 636)

- trnproc 35 / 40 EXACT + 1 NM, nameent 17 / 21 EXACT + 1 NM (report.json; run 631's nameent
  count was 2 high). Commits on agent-c: ed668e58f,
  12b3ee9ec, bcba1ad57, 6e1684c8e, 2152c5e83 (3432 -> 3441).
- New exacts: trnproc 10 (procMain), 3A8 (ctor), 6CC, A2C, 1098, 16C8, 1A98; nameent 150
  (was NM), 5B4. NM: trnproc 1778 (32/37), nameent 2F4 (84/89).
- **USO C switch table at RoData+0:** pin the unit's `.rodata` NOLOAD at VMA 0 in tenshoe.ld
  (`.trnproc_uso_10_jtbl`, the arcproc 240 recipe). Only the table may live in that .rodata:
  float literals go through 0-pinned per-load symbols (`trn_ro_20` .. `trn_ro_2C`, addend =
  RoData offset; RoData pads the table to 0x20, so C literals would land 0x14 too low).
- **procMain:** every GameFlow access as inline `*(int *)((char *)&D_00000000 + off)` keeps &D
  CSE'd in s1 (a named base local is const-propagated into `lui at; sw`).
- **Void-typed placeholder alias** (`trn_func_00000A2C_v`, `ne_func_00000000_v`) on a call whose
  int result is dead frees v0: the ctor's vtable base and nameent 150's phase then colour v0.
- **Function addresses passed as data** (the pause-row callbacks) are Text relocs with in-place 0:
  spell them through 0-pinned `_ref` aliases, or the ROM gets the linked address.
- ctor: the TrnDataManager +0xB4 = 17 store goes through the reused `o1` local (TrkRace's
  per-arm o1 form); a dedicated InputMgr alias (`trn_gInputMgr`) for the dataMgr store.
- Open:
  - trnproc B78 (lesson HUD: NM draft at ~37 %, the target multiplies the sprite index by a held
    24 (`multu`) and homes three words between `col` and `buf`), DD4 (results), 13C4, 188C;
  - nameent 760 (entry ctor), 9BC, E44 (input, 435 words);
  - 1778 (t-ring order of the spilled mask reload) and 2F4 (object / vtable v1 / v0) NM residuals.

## heli.uso progress (agent-g run 632)

- 22 / 26 EXACT, 3 NM wraps (0x4C0 90.7, 0x8A8 99.4, 0x980 94.7) after run 637 (agent-g
  922cfde7a 0x3F4 exact + 0x8A8 NM, 4bff028e9 0x980 NM). Open: 0xB08 (943-word update: fsin /
  atan2s / acosf path flight, not started).
  - 0x3F4: read the axis through a `HeliVec3f *` temp (`x = a->x, y = a->y, z = a->z`). That
    colours x f0 / z f12 with the target's z, y, x load order; direct member reads colour the
    first-loaded value f0 whatever the statement order (630 orders probed).
  - 0x8A8: the +0x120 zero is a second constant web, spelled `(float)0`. Written before the 400 / 2000
    stores it colours f8 (right) but schedules first; written after, 400 takes f8. A statement-move
    hill climb plus 7 zero spellings found nothing better.
  - 0x980: the ItemMgr pointer is bootup Data+0x776C (alias heli_itemMgr). The loop is the
    hud_findMarkers_000029F8 cursor / next iterator. The RoData+0x78 add only hoists into the
    preheader when it goes through a float local in a hand-rotated do-while. Residual: the first
    iterator result goes to v1 directly where the target uses v0 plus a copy.
  - 0x4C0: the main-rotor zero colours f2 where the target has f0, because the tail rotor's
    RoData+0x58 scale web takes f0 first. Moving the scale chain above the main euler call fixes
    the colour but not the load position. Zero spellings and chains (63 combinations) don't change it.
- **0xB08 Heli update (agent-g run 642), decoded, not committed** (best 77.1 %, under the 80 %
  NM threshold). Drafts are in /tmp/claude-1000/agent-g/b08_keep/ (c1.cpp is the NCC version).
  - Structure: the course state is bootup Bss+0xF8 +0x138, and the player is
    `**(state + 0x44)`, position +0xA0. The mode is +0x170 when that is set, else +0x16C.
    The +0x16C path:
    - player state +0xA54 == 6 calls 0x980 and sets +0x170 = 8;
    - the "mrk" type (Data+0xCBAC) slot-12 virtual gives the nearest marker into +0x168;
    - the marker advances to the next one (+0x2C) while next+0x38 < player z;
    - +0x16C = marker +0x3C.
  - The 8-way switch dispatches through a jump table at RoData+0x7C. Table order 1..8 =
    E04 FA4 C74 CAC ED0 1130 D68 C5C; the RoData payload sits at heli_uso_pre.bin +0x44.
    Mode 2 calls ItemMgr_queryType (Data+0x7768, tag Data+0xCBB0, &pos) and eases the
    target 0.2 per frame toward the marker.
  - Tail:
    - dir = target(+0x114) - pos(+0xDC); dist = sqrt(dir^2) * gGfxLib+0x128;
    - normalise dir and the heading +0x138, then slerp the heading by t = +0x164 (acosf / fsin);
    - speed +0x154 against +0x150 / +0x158 / +0x15C / +0x160; pos += heading * speed;
    - yaw +0x14C (atan2s, wrap at pi, clamp 0.3, x0.06), roll +0x144 (side . dir * -1.5,
      x0.07 smoothing), pitch +0x148 (fwd . vel / 200 + fwd.y * 0.1, x0.2, clamp pi/8);
    - three quatRotateAxisAngle calls about z / x / y, then QNode_update.
  - **It is C++.** The target multiplies by 2.0 with `mul.s` (cfe and cfront C strength-reduce
    `x*2` to `add.s`, edg does not), and it has the edg Vec3 temp chains (op- result ->
    return temp -> by-value operator= param).
    - cfe C draft: 66 %.
    - The same C compiled with NCC: 71 %. With a Vec3 class (by-value operator=, operator-,
      operator*, operator+=), 77 % and the frame is exactly 0x170.
    - NCC lowers the switch to a beq chain, but the target has a jump table. That is the
      MIPSpro 7.2.1 edg rule (tools/ncc721.sh, run cpp first for includes). The same C++
      under mp72 gets the table but scores 73.5 %.
    - Next: tune under mp72 (jump table + mul by 2.0). Pin .rodata NOLOAD at 0x7C
      (`.heli_uso_B08_jtbl`, as trnproc 10), or use a donor `_rodata` pin.
- **0xB08 compiler (agent-g run 647): MIPSpro 7.2.1 edg is required.** IDO 7.1 NCC (EDG 2.19) never
  emits a jump table: probes with 8, 13 and 40 dense cases (int, unsigned, with or without default)
  all give beq chains, and no matched `*_ncc_*.cpp` donor that has a switch contains a `jr` other than `jr ra`.
  So the target's 8-entry table rules NCC out. The mp72 draft is at 73.7 % (frame 0x170). NCC on the same
  source gets 77.1 %, because mp72 CSEs `&pp` (sp+356) into a3 while the target and NCC
  rematerialise it at each use. Slot map (target <- mp72): the operator= by-value temp is
  252 <- 140, mpos is 232 <- 268, the op- temp is 212 <- 124, dir 180 <- 84, ang / s 164 / 168 <- 240 / 244,
  sa 148 <- 224, key / key2 280 / 272 <- 296 / 292. In the target the temps sit between the
  outer named locals and the later ones. Declaration-order and block-scope hill climbs (750 evals)
  moved the score by less than 0.1. `Vec3 vel = ...` direct-init is worth +1 (74.65).
- 0x8A8 under NCC with a Vec3 class reaches 97.5 % at best, below the cfe NM at 99.4. One zero web is
  shared, frame 0x20 vs 0x28.
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

## viewrec.uso progress (agent-a run 648)

- +6 EXACT (3517 -> 3523 on the agent-a base, gate PASS): 0x2D0 (commit 033276f9c), 0x1068 / 0x18D4 /
  0x2AE4 / 0x2C08 / 0x2FC0 (5fb3078a6).
- **0x2D0 (process ctor), edg frame homes.** edg numbers a block's named locals first, then the inline
  temps expanded in that block, then the nested blocks; IDO lays homes out top-down in that order. The
  loop counter (case block) sat one home too high until the Fader child was declared in a block of its
  own wrapped around the mode switch (between the ctor-chain temps and the counter). A function-scope
  declaration anywhere goes above the inline temps instead. Own donor file viewrec_uso_ncc_2d0.cpp
  (Makefile VIEWREC_NCC_DONOR_2D0), .bss renamed viewrec_uso_func_000002D0_bss (0x858).
- **v0 / v1 swaps: void alias.** 0x1068 / 0x18D4 / 0x2FC0: an int-returning call before the swapped
  load leaves a dead $v0 def that pushes the next reload / CSE into $v1. `XCALL(gl_func_00000000_vrv,
  name)` on the void calls fixes it.
- **Early pseudo.** 0x2AE4: a dead `s32 h = 0` initialiser gives h $v0 ahead of the image pointer
  (permuter-found as `h = 2; col[h] = ...`, minimised). 0x2C08: the same, plus the image pointer as
  a named local declared first and buf[12] (as 0x2D9C).
- **0x0 (NM, 3/33 words in NCC; the cfe NM body is unchanged).** The tail is edg + a reference local:
  `{ VrProc *&p = sVrProc; p->mode = 0x10000; sVrMenu = p->menu88; }` gives the
  `lui v0; addiu v0,0x87C; lw 0(v0)` x2 CSE. The show part under NCC:
  `{ VrNode *s = sVrProc->mainMenu; sVrScreen = s; if (sVrScreen) {} sVrScreen->start(); }` gives
  `or v1,v0; lw v0,40(v0)`, but the &sVrScreen base lands in a0 (target a1). The cfe body has a1 but no
  tail CSE. Not tried yet: the permuter (it cannot parse C++ references, so it would need a C stand-in).
  Scratch: /tmp/claude-1000/agent-a/w648/v/r7.cpp.
- Not reached this run: 0x266C (74%, redo as C++) and 0x1488 (NCC donor).

## viewrec.uso progress (agent-a run 641)

- +16 EXACT (3497 -> 3511 on the agent-a base, gate PASS). Commits: c78cdd709 (2088 / 2190 / 2468,
  22A8 via NCC), 2ce0b79bb (718 / 8C8 / 11B4 / 12D4), 36e749b51 (1748 / 1A08 / 1B4C / 1D64 / 29B0 /
  2D9C; NM 2AE4 / 2C08 / 2FC0), 7bdce250e (2D0 near-match parked in the donor).
- **cfe sorts switch cases, edg (NCC) keeps the source order.** A compare chain out of value order
  (2D0: 0x10000, 0x20000, 0x2000, 0x4000, 0x8000) means the function is edg. That is how 0x2D0
  was identified as NCC; it reaches 4/274 words there (only the loop counter's spill slot).
- ctor recipe under edg: children attached through an inline MEMBER `addChild` (a free inline
  function or a function-scope `c` colours the child into s2), the Fader via a block-scope child.
- Row callbacks whose Text reloc addend is 0 (0x1A08) need 0-pinned `_ref` aliases, as trnproc 3A8;
  the real symbol links to its USO offset and breaks the ROM (vcmp of the .o does not show it).
- More separate sprite statics: sVrLabels_318, _3F0, _540 (a fixed index needs its own symbol
  when the target keeps &sprite in a0 for both the call and the .image load).
- Open below 0x3000: 0x0 / 0x1068 / 0x1488 / 0x18D4 (old NM residuals, not reworked this run),
  0x2D0 (spill slot), 0x266C (74%, INCLUDE_ASM; `old` in t9 vs v0 shifts case 1; try NCC),
  NM 0x2AE4 / 0x2C08 / 0x2FC0 (single v0/v1 or t-reg swaps).

## viewrec.uso progress (agent-a run 638)

- +10 EXACT this run (3465 -> 3475 / 3577); NM wraps left: 0x0, 0x1068, 0x1488, 0x18D4. Commits on agent-a: c6d9f5ab1 (0x84 / E8 / 14C / 1B0 /
  214), e9e330aa3 (2F1C), c4e361e09 (290), 9cf297c32 (1588), 3024308a7 (14DC), bde715149 (4698).
- **Screen switches** (0x84..0x214): cfe C, `Node *s = sVrProc->field; sVrScreen = s;` then code-free
  `if (sVrScreen) {}` on BOTH sides of the slot-10 call (`VR_SHOW_SCREEN`). The tests count as uses
  of &sVrScreen (base materialised in a1) and split the screen into a v1 copy with the vptr in v0.
  Found by a 792-variant brute force; one-sided levers give only part of the shape.
- **0x0 stays NM**: same show part, but the target keeps &sVrProc in v0 for the two loads after the
  0x1A08 call while the load before it is a plain `lui t8; lw`. 3k lever placements (if-tests,
  locals, volatile, NCC) never gave the tail CSE without also materialising the pre-call load.
- **Indexed sprite runs are separate statics.** A variable index into a run (0x2F1C from 0x378,
  0x1588 from 0x48 / 0x108 / 0x7B0) folds the run start into the reloc; `&arr[i + K]` never does
  under cfe or NCC (uopt keeps K apart; `&arr[K - i]` does fold, which is why 0x14DC's
  sVrLabels[57 - i] works). New pinned externs sVrLabels_378, sVrSprites_048, sVrSprites_108,
  sVrLabels_7B0.
- **0x2F1C**: the fire-ctor lever (local `d = 255.0f`, INT numerators) gives the separate 255.0f
  dividend register; the "8-byte gap" was declaration order (col first).
- **0x290**: NCC donor over `static float sPrimColour[4], sEnvColour[4]` with one block-scope
  reference per store gives the one-`lui at`-per-pair shape (kit LX); `.bss` reloc renamed to
  viewrec_uso_func_00000290_bss, pinned 0x858.
- **0x4698**: unused declared cfe locals still take frame homes (frame / home offsets fixed by
  `s32 unused; ... s32 unused2[3];`); the GameFlow import needs its own 0-pinned symbol
  (gInputMgr_vr4698) or uopt CSEs it with the gui import &D_00000000 into s0.
- Open: 0x1488 (frame 0x28 is reachable with a pad / extra local, but the target schedules
  `sw a2` before the jal and the sprite spill in its delay slot; every spelling tried gives the
  reverse), 0x1068 / 0x18D4 (v0 / v1), 0x2D0 ctor, 0x718 / 0x8C8 sprite tables, and the bodies
  above 0x1A08 not listed as exact.

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
