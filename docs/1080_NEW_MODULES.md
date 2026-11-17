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

### agent-a run 743: viewrec 0x3878 EXACT (the function's own vtable slot is the extra jr edge)

Commits on agent-a: dc34903a2 + 2c21ca9f8 (one change split by a failed `git add`: the first carries only the
donor file move). No renames. Gate PASS (3572 / 3579), lost: none. Scratch /tmp/claude-1000/agent-a/w743/.
- **The mechanism.** as1 makes every text address named by a data word before the function's `.end` a target of
  each jump-table `jr` in that function (run 738). `.s` oracle sweep on the run-738 base: `.word`, `.half`,
  `.gpword`, `.word $40-$46` (no reloc), and a word in a custom `.section` all give the target (ndiff 5);
  `.dword`, a `.text` word and an external symbol do not. **`.word viewrec_uso_func_00003878` (the function's
  own address) also gives the target:** the entry block becomes a jr target, and the callee-saved registers are
  live there (the prologue saves them), so s5..s7 are live at the switch `jr` and as1 may no longer speculate
  the grid's `r = 0` / `li 2` / `li 1` above the `selFade > 0` bc1fl.
- **The ROM evidence.** viewrec Data+0x184 holds 0x3878 (and +0x178 holds 0x3818, the update): the erase
  screen's vtable at Data+0x118. The original TU emitted that vtable before the draw body.
- **The donor** (`src/viewrec_uso/viewrec_uso_mp72_3878.cpp`, was `_nm_`): the run-675 body plus
  `extern "C" void *vr_eraseDrawSlot_3878 = (void *)viewrec_uso_func_00003878;` above it (a `static` one is
  dropped by edg and does nothing). Spliced on both build paths; calls spelled `CALL(name)`;
  `viewrec_uso_func_00003878_rodata = 0` in undefined_syms_auto.txt (literals +0x0, table +0x10, in-place
  %lo). The 3F24 jtbl NOLOAD pin at 0x24 is unchanged (the .c unit's .rodata is still only 3F24's table).
- **Lever for other jtbl functions:** if a function with a jump table shows a register "dead at the jr" in ours
  but live in the target, and the function is a virtual method / callback, emit the vtable or a data word
  naming it before the body.

### agent-a run 738: viewrec 0x3878, uopt toys for a code-free register read after `$45` (no commits)

No commits, no renames (nothing to gate; `make` ROM OK on agent-a). 3878 is still NM 98.7 % (ndiff 11). Scratch
/tmp/claude-1000/agent-a/w738/ (`t/t.sh X.cpp` = toy compile + ugen listing; `v/r.sh name ANCHOR REPL ...` = 3878
variant + ndiff + any `$21..$23` read after `$45`; `v/o*.s` = `.s` oracles run with the run-733 `asm.sh`).
- **Self-copies cannot arise in uopt.** uopt live ranges are block-granular, so the source and the destination of a
  copy are both live in the copy's block and always interfere. Toys `x = r; while (x < 100) { g(x); x += 3; }` and
  `x = r; do { ...; x = h(x); } while (...)` give different registers (s0 / s1) or a spill, never `str R <- lod R`.
  This explains agent-b's scan of 300 outputs (run 693).
- **Every uopt-visible read of r after `$45` costs a word.** r has no reaching def on the B -> `$45` path, so uopt
  stores r at the grid exit (`sw $21,96(sp)`) and reloads it at `$45`. The reload is a DEF, so the pull stays
  legal; as1 deletes the now-dead reload, but the `sw` stays (+1 word, ndiff 12). This holds in small toys too (no
  register pressure needed), for `if (r) {}`, `f(r)`, `if (r == 3)`, and an empty loop `for (k = r; k < 4; k++) {}`.
  The constant-1 / constant-2 LRs are rematerialised (`li`) at `$45` the same way (run 670).
- **r defined on both paths (`r = 0;` before the if, and `for (r = 0; ...)` kept) plus `if (r) {}` after** (`y1`):
  426 words, no store or reload, and uopt drops the in-loop init as redundant. But `move s5,0` then sits in B,
  before the bc1f, and s6 / s7 are still pulled (ndiff 11). The target has the def after the bc1fl, in C. So at the
  uopt level r is NOT live at `$45` in the target: if it were, uopt would put a def or a reload on the B path. The
  as1-level read must be one uopt never saw.
- **Dead stores that uopt keeps:** only the init of an induction variable that LFTR removed (toy `for (r = 0; r < 4;
  r++) g(r * 2)` leaves a dead `move $2,$0` in the preheader). That init sits in the loop preheader, so it cannot be
  after `$45` without a loop there, and every loop emits code (even `for (k = 0; k < 1; k++)` and empty loops).
  Late-folded dead copies (`idx = r; rowIdx = 5; if (rowIdx == 4) ...`, an empty-trip loop) are removed; only
  the frame grows.
- **NEW as1 fact (`.s` oracle): every label named by a data `.word` seen before the function's `.end` is a
  target of EVERY jump-table `jr` in that function.** One extra `.word $40` (the outer grid head; or `$41`, the
  inner head) gives the target word-for-word (ndiff 5 = the reloc false diffs). That holds as a 6th table entry,
  as a separate `.rdata` word before `$46`, as a `.data` word inside the function, and as a `.data` word at the top
  of the file. After `.end` it has no effect. The live-in of `$40` among s0..s8 is exactly {s4, s5, s6, s7, s8},
  so this one edge explains all three bits. This extends kit CDLVI: the jr liveness is the union of the live-ins of
  all labels taken as data words, not only of this table's targets. **It does not explain the ROM:** the ROM
  table (RoData +0x10) is 0x3D30, 0x3D30, 0x3D48, 0x3D64, 0x3D94 (the case blocks), and no viewrec data word holds
  a grid address (0x3BB8..0x3CC4). ugen labels are unique per file, so an earlier function's table cannot alias
  `$40` either. A scan of every `.s` listing under /tmp/claude-1000 found label words only in switch tables.
- Also flat: `.alias` / `.noalias $21,$sp` at `$45` (11); a `$21` temp in the `trunc.w.s` macro after `$45`
  (11); ugen / as1 at -g1 / -g2 (556 words) and -g3 (= -g0); `.sdata` / `.rdata` / `.data` switches in C (11).
- **What is left.** as1 sees a register as live through only three things: a real read, a `.livereg` bit, or a
  jump-table edge. In the target none of these left a byte or a data word, and uopt did not see the read. The
  remaining candidates are a ugen artifact that has not been observed yet: a `.livereg` bit from a window `str`
  that emits nothing, or a jr target set taken from somewhere other than data words. Or a front end / compiler
  build whose as1 input differs from ncc721 + the 7.1 back end. The 7.2.1 as1 could not be rerun here
  (`tools/forensics/x_mipspro744` is gone; run 393 found every as1 from 5.2 on identical on mgrproc).

### agent-a run 733: viewrec 0x3878, the as1 liveness route narrowed (no commits)

No commits, no renames (nothing to gate). 3878 is still NM 98.7 % (ndiff 11, 426 vs 427 words). Scratch
/tmp/claude-1000/agent-a/w733/v/ (`c.sh X.cpp` = ncc721 keeping intermediates + ugen listing + ndiff + setColor mask,
`mk.py name ANCHOR REPL ...` variant maker, `dump.sh X [B]` ugen `-d` tree of the .O (or the edg .B at -O0),
`win.sh X` = register strs in the setColor `mst..cup` window, `asm.sh` = as0 + instrumented as1 oracle).
- **Reads AFTER setColor also block the pull (`.s` oracle `o2.s`).** Dead `move $8,$21 / $9,$22 / $10,$23` placed
  before the LAST call of the `selFade < 1` block (after the switch, many jals past `$45`) give ndiff 5 (= the reloc
  false diffs, i.e. the target). So as1's liveness carries s5..s7 through every jal to the epilogue restores; the
  setColor mask is only one of many places. Removing setColor's `.livereg` entirely changes nothing (ndiff 11): as1
  does not treat a missing mask as "all live".
- **The as1 trace (`as1i`, bi.tr):** B = bb33 (w1, stalls 6), C = bb34 (the grid preheader, **w4**), tried at count 2
  after bb48 ($45, w1) and bb73 (epilogue, w1). Accepted insts 1 / 3 / 4 / 7 / 8 (move s5, la, li s7, li s6). The
  cap is 100 (several loops), so no C4 route.
- **What the window can and cannot hold (dumps):** after uopt every call argument is `str R(a-reg)` + `rpar`; stack
  arguments are `str mtype=P`. No `par` nodes survive -O2, so the walk's `par offset2 / 4` branch (which in the -O0
  `.B` maps `lda M-16` to `$gp`) is unreachable at -O2. edg 2.29 emits every inline parameter and local store
  (`cvi(f)` with a local, `cvi(f, r)` writing the parameter, a `SC(0, 1, 2)` ctor temp in the argument) BEFORE the
  `mst` (`p1..p3`, ndiff 28 / 42 / 51), so pool-word sharing cannot place a store in the window.
- **Code-free self-assignments in the argument (`(r = (int)(unsigned)r, ...)`, `r << 0`, `~~r`, `-(-r)`):** all folded
  by uopt, window unchanged (`s1..s4`, ndiff 11).
- **Early-return forms of the `selFade < 1` test** (`if (!(..)) return;`, `>= 1.0f` return, `goto out`): no `.livereg`
  is emitted at the branch; ndiff 11 / 13 / 11 / 11.
- **Rechecked run 651's `&sVrLabels[21 + r * 2 + j]`:** on today's base it does not reproduce the target hoist
  (427 words, ndiff 13, the three defs are still pulled).
- **The 7.2.1 back end could not be rerun** here: `/tmp/claude-1000/r1/root72` uopt exits 1 under both qemu-irix
  builds (no message). Run 356 found it byte-identical to 7.1 on all donors anyway.
- **Where that leaves it:** the target's as1 saw a READ of $21 / $22 / $23 somewhere between `$45` and the epilogue
  (or the mask bits), and none of it survives as code. uopt-visible reads force a def at `$45` (run 670), and every
  ugen register read comes from uopt's R-mtype nodes. So the target's uopt output had an R84 / R88 / R92 reference that
  ugen or as1 erased: a self-copy (`str R84 <- lod R84`, which ugen / as1 erase, oracle mm5) or a dead move as1
  deletes after liveness. Next: build a uopt toy where two webs of one variable (or a variable and a copy) get the
  same colour across a copy (`x = r; ... x++` with r dead after the copy), and check if uopt keeps
  `str R <- lod R` there. If it does, the 3878 shape is a copy into r / the constant LRs on the `$45` path.

### agent-b run 705: snoweffects 0x9328 NM 99.63 -> 99.73 %; viewrec 0x3878 ugen 0x100 lead closed

Commit on agent-b: 96dbb1ef3 (0x9328 NM gain; gate PASS, no renames). 3878 unchanged (NM 98.7 %).

- **0x9328 store order fixed (line grouping).** ugen emits the five int stores in source order; as1 reordered them
  (568, 564, 556, ...) because all five sat in one `.loc` group. With each assignment on its own source line (or
  `0, 0` / `1` / `3, 0` split as three lines), as1 keeps 556, 560, 564, 568, 572 as in the target. The code shape is
  now exact (ndiff 139 standalone, all of it frame offsets + the reloc addends).
- **0x9328 frame: the temp order is the EDG 2.19 vs 2.29 pool-order difference (MATCHING_SUMMARY section 5).**
  - EDG 2.19 (IDO 7.1 NCC) `.B`: -4 = parms vreg, then the Parms9-ctor temps n5 -8, n4 -12, n3 -16, hi -32,
    lo -48, val -64, n2 -68, n1 -72 (reverse creation), then the inline pool from -76.
  - The same source through `tools/ncc721.sh` (EDG 2.29) homes n1 at frame-8, n2 -12, val -28, lo -44, hi -60, n3 -64,
    n4 -68, n5 -72: **exactly the target's temp layout**. But 2.29 marks an out-of-line ctor's `this` volatile (ucode
    `lod P lexlev=1`), so `this` lives in its arg home (`sw a0,184(sp); lw t6,184(sp)`) instead of s0 (toy
    `w705/toy/m1.cpp`: every out-of-line ctor does this, with or without operator new / vptr). So the target looks
    like the "EDG between 2.19 and 2.29" of the forensics notes: 2.29 pool order with 2.19 `this` handling.
  - 2.19 toys (`w705/toy/`, `d.sh` lists M offsets per function): temps in ONE scope are always reverse-allocated
    (ctor temps, implicit conversions, casts, comma / ?: wrappers, temps with dtors or copy ctors, nested `PName(PName())`).
    Forward order appears only with sibling or nested **block** scopes (`{ g(PName(x1)); } { g(PName(x2)); }`), with
    temps created inside an inline function body (sibling inline scopes, but then created after that ctor's
    this == 0 check, unlike the target), and with inline-function return temps (`mk(x)` returning PName / Colour, but
    those add a struct copy per temp). None of these fits a mem-initializer list. Reversed mem-initializer order, base-class
    chains (each level adds a this == 0 / new check), char * names converted inside the ctors, `const &` parameters:
    all worse or unchanged.
  - Next: a 2.29 donor needs a non-volatile `this` for the outer ctor, i.e. the out-of-line function not being a ctor.
    Placement new (`::new (p) T`) keeps the inline ctor's own check but adds a `beqz a0` result check in front.
- **viewrec 0x3878: the ugen 0x100 lead is closed.** The `.livereg` masks are MSB-first (bit 31 - n = $n; e.g.
  0x0F00000E = a0..a3 + gp/sp/fp, 0x0000FF0E = s0..s7 at the return). The flag-0x100 cup adds 0x5FFF0000 = $1, $3..$15
  (at, v1, a0-a3, t0-t7) and 0xFFFFF000 = $f0..$f19: caller-saved only, never the needed 0x00000700 ($21-$23).
  Probing direct, varargs, struct-return, function-pointer and cast-function calls gave plain 0x0C00000E masks; no
  0x5FFF mask appears in any listing under /tmp/claude-1000. Also from the walk: `par` (op 0x6f) marks register
  offset2 / 4 and `str` (op 0x7b) mtype R marks offset / 4, as run 693 found.
- Scratch: `.../scratchpad/agentb/w705/` (`c9.sh` NCC compile + ndiff vs target, `n71.sh` same keeping .B/.O/.s,
  `m9.sh` ncc721 variant, `sig.sh` frame / slot signature, `var.py` variant maker, `toy/` pool-order toys).

### agent-b run 697: snoweffects 0x9E10 EXACT, 0x9328 NM 95.7 -> 99.6 % (3565 / 3579, +1 exact)

Commits on agent-b (gate PASS before each, no renames): 5dea1bd50 (0x9328 NM gain), 04b111c85 (0x9E10 exact + episode).
My own 0x9328 wiring was discarded once agent-e's e9 donor landed; the gains are in `snoweffects_uso_ncc_nm_e9.cpp`.

- **0x9E10 EXACT (C, both build paths).** Two levers:
  - the null test re-reads the field (`if (*(int **)(type + 0x40) != 0)`) instead of testing the head local. This
    gives the target's `beqz aN; or a1,aN` delay-slot copy (the 0x7D8C sibling does the same);
  - the re-read value is passed to list_append as an extra, unused third argument
    (`list_append(item + 0x10, head, *(int **)(type + 0x40))`). That colours it a2 with the head copy in a1, and
    item goes to v1. Without the extra argument, item and the test value swap (a2 / v1). This is the "invisible
    extra arg" lever (IDO_CODEGEN kit II). The callee is bootup list_append (uso-imports.py), which takes 2 args,
    so a2 is ignored. C++ inline-member forms (attach / attach2 / a ListE::add hop) all keep the head in a1 with
    `beqzl`.
- **0x9328 (99.63 %, 247 / 247 words).**
  - ParmC's inline ctor takes its name AFTER the three Colours: `ParmC9(o, val, lo, hi, PName n, fl)`. The edg name
    temp is then created after the Colour temps, as in the target. The GdlParmBase call reloads it from its word
    (lw 0xA0 -> 0x84) instead of forwarding it.
  - The bodies store `f20 = 0` before `v = val` (ParmC) and `f14 = 0` before `v = val` (ParmI).
  - With offsets normalised, the only code difference left is the +0x234 / +0x238 store order (ours 568 before
    564). None of the 120 orders of the five int stores, or the 24 orders of the four body groups, changes it.
  - **Frame (192 vs 224).** Ours homes the edg temps bottom-up in creation order (n1 at 120 ... n5 at 184); the
    target homes them top-down (n1 216, n2 212, val 196, lo 180, hi 164, n3 160, n4 156, n5 152). The `-g3` mdebug
    shows edg declares them in reverse creation order (`__V` at M-8 is n5), so cfe's top-down decl-order homes come
    out mirrored. The target looks as if edg declared them in creation order. The pool area below is also 32 bytes
    bigger in the target.
  - No effect: inline empty destructors on PName / Colour, `char *` names converted inside the ctors, implicit
    `char *` -> PName conversion. Placement-new member construction gives frame 216 but changes the null-check
    shape (`beq`).
- **viewrec 0x3878: not worked** (budget went to the two above). One lead for next time, in ugen `f_eval` Umst
  (`/tmp/claude-1000/h384/u/ugen_i.c` L42df98): when the cup node's word at +44 has bit 0x100 set, ugen ORs
  0x5FFF0000 into the int mask. If that mask is register-indexed (bit n = $n) before `f_emit_regmask`, this covers
  s0..s7. Next: find which cup attribute sets 0x100, and whether a call spelling sets it.

### agent-b run 693: viewrec 0x3878, the edg pool-word route to the setColor `.livereg` (no commits)

No commits, no renames (nothing to gate). 3878 is still NM 98.7 % (ndiff 11).

- **The ugen mask walk, read in full** (`ugen.c` `L42d828`, the `Umst` case of `f_eval`). It walks the node list
  from the `mst` up to the first `cup` / `icuf` / `cia` / op 0x97. It ORs in the register of every `str` with
  mtype R (register = offset / 4, plus the next register for 8-byte stores), and of every `par` node (register =
  offset2 / 4, so argument registers only). At the `cup` (`L42df98`) it adds `| 0xE`, and a cup flagged 0x100
  adds 0x5FFF0000 / 0xFFFFF000. Neither ever covers s0..s8. **So the s5 / s6 / s7 bits can come only from a
  register `str` placed between setColor's `mst` and `cup`.**
- **uopt never emits a self-copy.** A scan of 300 uopt outputs under /tmp/claude-1000 (`ugen -d`, `w93/selfcp.py`)
  finds no `str Rn <- lod Rn`. Any register store in the window therefore emits code. The target's window has no
  s5 / s6 / s7 instruction, and its 427 words leave no room for one. The mask route needs a ucode shape that has
  not been observed.
- **MIPSpro pool words do alias across inlines, but nothing lands in the window.** Toy `w93/t/t1.cpp`, with
  `.B` dumped through `ugen -O0 -d`:
  - `grid(S *s, int r)` puts s at -24 and r at -28.
  - A later `sc(float *c, int x)` puts c at -24 and x at -28, so x is r's pool word.
  - edg emits the parameter store BEFORE the `mst`, and uopt copy-propagates it away. The window holds only the
    a0 / a1 / a2 stores.
  - `x = x;` and `r = r;` produce no ucode at all.
- **On 3878 itself:**
  - Grid loop moved into an inline (`vrGrid(self, col, blink)`, or with rows / cols parameters): ndiff 20. That is
    the base 11 plus frame slots; the window and mask are unchanged.
  - setColor through one- and two-hop `int` wrappers, and wrappers that take r / 1 / 2 as arguments
    (`vrSetColR2(col, a, r, 1, 2)`): byte-identical to the base.
  - Combining the inline grid with each of those wrappers: unchanged.
- **Other tries, all flat:**
  - `v = (int)(255.0f * askFade); setColor(.., v, ..)` for v = r / j / i / a: copy-propagated, identical.
  - An uninitialised `int u;` read after setColor (`if (u) {}`, `switch (u)`, `u == 1`, a block copy): uopt drops
    the read entirely, so only the frame changes.
- **What is left.** as1's `jal` defines only the caller-saved set (kit CDLVI), so s5 / s6 / s7 stay live through
  setColor. Any READ of $21 / $22 / $23 on the `$45` path before the epilogue restores would therefore block the
  pull, not only a read inside the window. The read must be one that uopt does not see as a use: a uopt-visible
  use homes r, or reloads the constant, at `$45`. It must also be one that as1 deletes after its liveness pass,
  such as a dead `move tN,$21` (run 670 mm7).
- Scratch: `.../scratchpad/agentb/w93/` (`run.sh` compile + ndiff + mask, `mk.py` / `v1.py` / `v2.py` variant makers,
  `t/` toys, `dump.sh`).

### agent-b run 686: snoweffects 0x559C EXACT; viewrec 0x3878 line joins flat (+1 exact)

Commits on agent-b: 2a76794b6 (559C NM 97.3 -> 99.0 %), 8683fba2f (559C EXACT, donor promoted to the matching
build: SNOW_NM_B_FUNCS -> SNOW_B_FUNCS, CALL / XCALL names, plain .c placeholder), e5c37a2b9 (episode). No renames.
Gate PASS before each (3561 / 3579 on agent-b, which lacks agent-h's 0x97C).

- **0x559C, s0 / s1 (pool-word membership).** The colouring trace (h414 instrumented NCC, `-Wo,-zdbug:5`,
  `h384/t/lre.py` + `h414/t/ord.py`) showed the member-ctor `this` (M8B / M4B at +0x34 / +0x58) alone in pool word
  M-188 (v1), while the target keeps it in s1 with the packet count. Routing every direct packet through
  `Gfx *n1() { return (this + 0)->next(); } Gfx *nx() { return (this + 0)->n1(); }` (two hops; one hop moves only
  the list pointer) shifts next()'s temps by two pool words, so the count shares the member-ctor word and the list
  pointer the BaseMat-ctor word. The final `ctx->put(0xBB..)` also has to go through `PKTB(ctx->nx(), ..)`.
  Plain `return next();`, `(&*this)`, casts, `(dl + 0)` and named-local wrappers either change nothing or add frame.
- **s2 / s3 / s4 (priority).** ctx (151.2) outranked the packet `_g` (150) and j (144). A trailing `if (ctx) {}`
  after Node_display extends ctx's LR, giving 140.5 (still above the 140 of s5's LR): packet s2, j s3, ctx s4, and
  &m (a late constant LR) falls into s2 as in the target. `ctx = ctx;` does nothing.
- **Last 19 words.** A line-join search (lj2.py) put `int prevTex = -1; int prevState = 2; int i0 = 0; int i1 = 1;`
  on one line: the as1 tie-break then stores i1 first, as in the target. The quad-loop preheader reloaded i0 / i1
  before the guard because of `int a = i0, b = i1;`. Writing the indices as `i0 + j` / `i1 + j` (no a / b) makes uopt
  build induction variables in the preheader after the guard: 0 diffs. This also fixed the spill slots and the v0 / a0.
- **viewrec 0x3878: the line-join lever is flat.** Joins of every 2-, 3-, 4-, 5-, 6- and 8-line window of the body
  (w70/base.cpp, ~600 compiles) give ndiff 11 or worse. As expected, the residual is as1 liveness (s5 / s6 / s7 dead
  at `$45`), not a scheduling tie, so source-line ties cannot reach it. Still open: a construct that leaves a
  zero-code use of r / 1 / 2 in gui_setColor's `.livereg` window (run 670 notes).
- Scratch: `.../scratchpad/agentb/s6/` (sc.sh posdiff scorer, trc.sh / pr.sh colouring-trace wrappers, lj2.py line-join
  search, mk.py / var.py variant makers); `.../scratchpad/agentb/lj/` (the 3878 join sweep).

### agent-b run 679: snoweffects 0x559C NM 97.3 % (3559 / 3579, +0 exact, +1 NM)

Commits on agent-b: d61cce602 (559C NM 93.0 %), 95dd87a77 (97.3 %). No renames. Gate PASS before each.

- **0x559C decoded whole**, in the NM section of `snoweffects_uso_ncc_b.cpp` (`SNOW_NM_B_FUNCS`); 654 words and frame 480,
  both equal to the target. It is the trail-ring draw:
  - a stack `Mat` (BaseMat ctor protocol, then the Mat vptr) with colour 1,1,1,1, passed to gfx_emitLights after a
    gSPDisplayList of +0xB0->+0x60;
  - per live slot: the stride points * gGfxLib world scale into s16 Vtx (+0.5f) plus alpha (clamped, `dead` count),
    then gSPVertex at ring index i0;
  - an RGBA32 32 x 32 texture load from the Data+0x588 table when the slot's texture changes;
  - from the third slot on, stride - 1 quads of two F3DEX gSP1Triangle, with indices masked by 2 * stride - 1.
  New 0-pinned aliases are in undefined_syms_auto.txt (`snowb_*_559C`, `snowb_texTbl_588`, typed `gl_func_00000000_snowb_lights`).
- **Levers that mattered** (scratch `.../scratchpad/agentb/s5/`; `cf.sh` compiles and diffs, `nd.sh` diffs with registers masked,
  `md.sh` dumps the -g3 slots):
  - `next()` as `&dl->buf[dl->count++]`. The named-local form costs 3 pool words per packet: frame 616 instead of 456.
  - The vertex scale comes from `scaled(const V &, float, float, float)` returning `V(x * sx, ..)`, which gives the
    target's f0 / f2 / f12 products. Pass the three scale words through three gGfxLib aliases: with one base (struct
    ref or the same symbol) uopt hoists `&gGfxLib` into a register for the whole slot loop (+4 words). This is
    agent-c's 0xC90 trick.
  - The texture test reads `t->slots[si].tex` directly (no `tex` local), so prevTex lives in t5 like the target.
  - **Edg slot order = a block's own declarations first (in order), then nested blocks.** The target has p, any, dead
    and j declared in the slot-loop body ahead of `mask` (k -236 / mask -256 / v -268 / scaled temp -296). A dead
    `{ int sc0[4]; sc0[0] = 0; }` before the loop fills the rest above k.
  - **Pool-word register sharing:** read the list address through an inline member `holder->phys()`. Its `this`
    reuses the BaseMat ctor `this` pool word, so uopt gives both one callee-saved register, as the target does
    (93.0 -> 97.3 %).
- **Left:** s0 / s1 and s2 / s3 / s4 are permuted against the target. In the target, s0 is the ctor this and the packet
  head; s1 is the member this, the gfx base and the packet count; s2 is &m and the packet; s3 is j; s4 is ctx. These
  did not move it: ctx through an inline accessor, a gfx `lights()` wrapper, or declaring ctx before m. Also left: the
  ugen t-register ring offset, and two uopt spill slots (ours 84 / 88, target 92 / 84).
- viewrec 0x3878 was not reached.

### agent-b run 675: viewrec 0x3878 NM, snoweffects 0x1E60 NM (3557 / 3579, +0 exact, +2 NM)

Commits on agent-b: be9d82da4 (3878 NM), 88889d286 (1E60 NM). No renames. Gate PASS before each.

- **viewrec 0x3878 NM 98.7 %** (objdiff): the run-670 body as a MIPSpro 7.2.1 NON_MATCHING-only donor
  `src/viewrec_uso/viewrec_uso_mp72_nm_3878.cpp` (built by the `viewrec_uso_mp72_%` rule; list block
  `VIEWREC_NM_B_DONOR` at the end of the Makefile). It is 426 words vs 427, and the shorter body passes the
  gate (the NM build only shifts the later functions by 4; objdiff pairs them by symbol). The NM donor calls
  `gl_func_00000000(/* name */ ...)`: name-placeholder-calls.py only maps matching-build splices, so a
  `CALL(name)` in an NM-only .cpp fails gate step 5 ("not among the ROM callees ... {}").
- **The 3878 residual, restated with the real diff:** the target has a nop after the FIRST `c.lt.s` (the
  `selFade > 0` grid test, 0x3BB0), and `or s5,zero,zero` / `li s7,2` / `li s6,1` sit after the bc1fl. Ours
  speculates those three into the hazard slot above the branch, which as1 may do only because s5 / s6 / s7
  are dead on the fall-out path. That path's first `.livereg` (gui_setColor) is the run-662 mask.
  The C++ inline-temporary hypothesis gave nothing in about 15 minutes:
  - inline `scol(d, a, c)` wrappers, with and without local copies of the parameters;
  - block-local copies of the three arguments;
  - `int rr = r; ... r = rr;` around the call;
  - a `{ int r = 1, j = 2; ... }` shadow block and an aggregate `{r, 1, 2}` temporary;
  - `int r = 0` at the declaration, with and without the for-init;
  - C++ `for (int r ...)` / `for (int j ...)` scoping.
  All of these are ndiff 11 (unchanged) or worse, and none sets the s5..s7 bits.
  Scratch: `/tmp/claude-1000/-home-danjs-code-decomp/843f1ac1-389e-4d4a-9ec1-9423b96b9705/scratchpad/agentb/w70/` (mk.py anchor edits, run1.sh).
- **snoweffects 0x1E60 NM 98.9 %** (objdiff), 300 words = target: agent-h's run-649 draft, moved into
  `snoweffects_uso_ncc_b.cpp` (renamed types `SnowTexB` / `SnowGCtxB`; NM list `SNOW_NM_B_FUNCS` at the end
  of the Makefile, spliced on build/non_matching only).
  - **The jr ra fill is not local:** the IDO epilogue `lw ra; lw s0; addiu sp; jr ra; nop` vs
    `...; jr ra; addiu sp` depends on the whole basic block's as1 schedule, even when the last 14 instructions
    are identical (siblings 15D0 / 1A18 / 2310 are unfilled, 1E60 is filled).
  - A `.s` oracle (as0 + as1 directly, without the driver's `-noglobal` for .s inputs, which adds a word)
    showed that a label right before the epilogue fills it. From C, a dead `switch (t->w) { case 1: break; }`
    does it: uopt keeps the switch-value load, ugen emits it, and as1 deletes it after scheduling.
  - Swept over the 18 statement positions, the fill comes at positions 3 and 14..17. The best is before
    the prim-colour packet: 60 diff lines, all a1 / a2 / a3 packet-pointer colouring.
  - No-ops that uopt removes do nothing: `if (x) {}`, `t->w;`, `(void)t->h`, while(0), and goto labels
    (labels change uopt colouring but ugen emits no label).
  - The old `return &dl->buf[dl->count++]` next() gets down to 39 lines but never fills (301).
  - Scratch: `/tmp/claude-1000/-home-danjs-code-decomp/843f1ac1-389e-4d4a-9ec1-9423b96b9705/scratchpad/agentb/se/` (cf.sh compile + diff, as.sh .s oracle, grid/ and grid2/ sweeps).
- **snoweffects 0x559C: not decoded (time).** Reloc map (uso-imports sites):
  - three mem_new calls (the 0x60 BaseMat with 8- / 4-byte members at +0x34 / +0x58, this == 0 protocol),
    then BaseMat_init_000517E4;
  - Data+0x1FBEC and Bss+0x3C168 (gfx context), gl_osVirtualToPhysical, gfx_emitLights_000454C4,
    SnowRing_countSlots_000053E8;
  - the slot loop: three more osVirtualToPhysical calls and Data+0x588 (hi 0x5970 / 0x5BEC, lo 0x59C4 / 0x5C44);
  - Node_display at the end.
  The frame is 480 (BaseMat on the stack at sp+0x150) and uses f20 / f22 and s0..s8.
  An m2c draft (380 lines) is `/tmp/claude-1000/-home-danjs-code-decomp/843f1ac1-389e-4d4a-9ec1-9423b96b9705/scratchpad/agentb/se/m559c.c`, from `m559c.s`, which was rebuilt from the expected .o
  with these relocs as names. Next: NCC transcription from that draft, in the
  `snoweffects_uso_ncc_b.cpp` NM block.

### agent-b run 670: viewrec.uso 0x3878, how ugen builds `.livereg`, and what the residual needs (no new exact)

No commits. 3878 is still at ndiff 11 (426 words; the target has 427, with the extra nop in the c.lt.s slot).

- **How ugen builds a call's `.livereg` mask** (read in the recomp `ugen.c`, `f_eval` around `L42d828`). At the
  `mst`, ugen walks forward over the ucode nodes until the call (`cup` / `icuf` / ...). Every register store
  (`str mtype=R`) in that window ORs its register's bit into the mask. Separately, `| 0xE` is always added
  (gp / sp / s8). Callee-saved registers that are merely live across the call are NOT marked (s4 = self never is).
  A bit appears only when uopt placed a register-variable store between the `mst` and the `cup`. Example: the
  grid's `a = 255` (source: after `spriteRefresh`) is hoisted into that call's window, which gives `0x0800800E`.
  Toy repros: w70/lr2.cpp, lr3.cpp. Use `ugen -d` on `<obj>.mp721.O` to see the post-uopt tree (w70/dump.sh).
- **as1 facts, from `.s` oracles on w38/base.s** (inserted right before the first `.livereg` after `$45`):
  - Dead defs of s5 / s6 / s7 with no bit are deleted, and the pull still happens (mm4).
  - Defs with the bits set are kept (+3 words, mm3).
  - Any **READ** of $21 / $22 / $23 there gives the target word-for-word, even with no bits: self-moves (mm5),
    dead moves into temps `move $8,$21` (mm7), or into other s-registers (mm8). as1 computes the xbb liveness
    first and deletes the dead reads afterwards. So the target needs either `str R21/22/23` in setColor's
    `mst..cup` window that emits no code, or any dead read of those registers between `$45` and that jal.
- **Why uopt-visible uses can't do it:** r (and the constant-1 / constant-2 LRs) are undefined on the B -> `$45`
  path. Any use that uopt sees at or after `$45` therefore makes uopt home r (`sw $21,96(sp)` at the grid exit,
  `lw $21,96(sp)` at `$45`) or re-load the constant (`li $23,1` at `$45`). Those are DEFS at `$45`, so the pull
  stays legal. Seen with `if (r) {}` before or after the call, `switch (r) {default:}`, `if (r == 1) {}`, the kit
  CDXCI compound-twice tests (`if (r*2+j != r) {} if (r*2+j != j) {}`, also with `self->gridY` and `r + 2`), and
  kept-dummy inline parameters (`setColK(r, j, ..)` with `z0 = z0;`, which costs frame words only).
- **Inert (byte-identical to the base):** `r = r;`, `r = 0; j = 2;`, `r = r * 1;` (before or after the call),
  `while (0) { r++; }`, `if (0) { r = r + j; }`, and `keep1(r)` (frame +8 only).
- A yes / no `for (r = 0; r < 2; r++)` loop is not unrolled by uopt (397 words). The target's two explicit
  59 / 60 blocks are written out in the source.
- **Next:** find a ucode shape that puts a register store into the setColor window and emits nothing:
  `str R84 <- lod R84`, i.e. two LR pieces with the same colour. Candidates are a uopt LR split (the target uses
  all nine s-registers) or an edg pool word shared with r. Or find a value r / j / 1 / 2 that IS defined on the
  B path. Neither the first loop's i (s0, not s5) nor any earlier constant qualifies in the target's colouring.
- Scratch: w70/ (`var.sh name ANCHOR REPL` = variant + ndiff + first `.livereg` after the `selFade < 1` test;
  `ugl.sh` = compile + ugen listing; `dump.sh`; the mm*.s oracles; the lr*.cpp toys).

### agent-b run 662: viewrec.uso 0x319C EXACT; 0x3878 residual traced to as1 liveness (3554 / 3579, +1 exact)

Commits on agent-b: 436d6097c (319C), a45f3ccaf (episode). No renames. Gate PASS.

- **0x319C (course scores page) EXACT, cfe C**, from the run-657 target-length draft in four steps. The
  colouring trace (h414 instrumented uopt `-Wo,-zdbug:5` + `h384/t/lre.py` + `h414/t/ord.py`, on a standalone
  copy of the function) shows uopt colouring saved registers in priority order (num / den), lowest free s-register
  first:
  - **Emission-free refs reorder the s-registers.** `y = y * 1` inside the loop adds two weighted refs (+20 num;
    `y = y`, `y += 0` and `(y + 34) - 34` fold earlier and add nothing). y then outranks i and show, but also
    self (s1). `self = (ViewRecScreen *)((s32)self * 1)` in the loop lifts self back above y. `course = course * 1`
    after the 0x1488 call lifts course (2.17 -> 2.5) above the hoisted course*48 (2.2), giving course s7 and
    course*48 s8.
  - **The void alias on the 0x2D9C call** drops the dead $v0 def that forbade v0 for e->score (v1 -> v0).
  - **as1 order: source-line groups.** `show = 1` moved after the GetScore statement fixes the loop head
    (`or a1,s3` before `addiu s4,1`). The preheader order (`sll s8,4` before `or s3,zero`) needs `i = 0; do {`
    on ONE line. A `.s` oracle showed no permutation of the preheader instructions reproduces the target
    when each sits under its own `.loc`, so this is line grouping (MATCHING_SUMMARY section 7), not ugen order.
- **0x3878: the residual is as1 liveness at the `selFade > 0` side exit, and it can be reproduced at the `.s`
  level with `.livereg` alone.** OR-ing the bits for $21 / $22 / $23 (r, the constant 1, the constant 2) into
  the FIRST `.livereg` after `$45` (the gui_setColor call in the `selFade < 1.0f` block) gives the target
  word-for-word (only the reloc-addend false diffs remain). All three bits are needed (each alone: 11 -> 9).
  ugen sets a callee-saved bit in a call's `.livereg` when uopt keeps that LR live across the call (see the
  0x0800800E mask at the grid loop's spriteRefresh, where s0 = a holds across it). So the target's uopt kept
  r / 1 / 2 live past that call, with no read left in the final code.
  - Tried (no gain): `.loc` regrouping of the if-body (9 layouts); an unreferenced label splitting the if-body
    (bb35 is still pulled); `bne $21,..; $L:` branch-to-next reads at `$45` (as1 deletes them before the xbb
    liveness: still pulled).
  - The C route is a code-free late use of r and of the two constants after that call. The kit CDXCV
    zero-byte copy guard does not exist under mp72 edg: `char c[0]` and `char c[]` are rejected, and an empty
    struct copies 1 byte (lbu / sb, +16 words, and r spills). Next: a C++ construct that uopt keeps as a use
    but ugen / as1 emit nothing for. Or find which uopt LR shape extends the constant-1 / constant-2 ranges:
    agent-a's while(0) ref multiplier, or a second loop after the if that reuses r and the bounds.
  - Scratch: `w38/` (`t38.sh` mp72 compile + ad.py, `.s` oracles lv*.s / z*.s / n*.s / m*.s). The `sa.sh` /
    `dz.sh` cfe colouring harness for 319C is under agentb/ too.

### agent-b run 657: viewrec.uso 0x4354 EXACT; 0x3878 / 0x319C analysed (3545 / 3579, +1 exact)

Commits on agent-b: 741fe25d8 (4354), 867b60986 (episode). No renames. Gate PASS.

- **0x4354 (erase pad handling) EXACT, cfe C** (was the 84 % NM). The only change: the `snd_postEvent(5)` before
  the switch goes through the void alias `XCALL(gl_func_00000000_vrv, snd_postEvent)(5)`. The int return left a
  dead $v0 def at the call, which pushed the switch value into v1 and the reloaded proc into a2. Without it, the
  switch value takes v0 and the proc v1. The same body under mp72 with the alias is also word-exact, so the
  front end was never the issue.
- **0x3878 (erase draw, mp72 draft): the 14-word residual is as1 xbb, not uopt.** In ugen's `.s` (run ugen with
  `-l x.s` on the ncc721 intermediates), the `selFade > 0` test block B is `l.s; li.s; c.lt.s; bc1f`, and the
  if-body C is `move s5,0; move v0,0; la v1,sVrLabels_3F0; sw v0,84; sw v1,80; li s7,2; li s6,1`. With `-noxbb`,
  everything stays in C. Our as1 pulls `la` + `move s5` + both `li` into B's c.lt.s stall (instrumented as1
  `/tmp/claude-1000/h410/as1/as1i`: CUR bb33, cand bb34 -> insts 1, 3, 4, 7, 8). The target pulled only the `la`.
  - `.s` oracle results: reordering C (5 orders), moving the `la` into B, an extra label at C's head, and
    `.alias` / `.noalias` in C all still pull. **A read of `$21` at the bc1f target `$45` (s5 live-in at the off-path
    successor) stops the `move s5` pull** (ndiff 11 -> 9). So the target's as1 saw s5 / s6 / s7 as live-in at the
    after-if block, or rejected them for another I5 / C3 reason.
  - The function has more than one loop, so the xbb candidate cap is 100: the kit CDXCV empty-block trick cannot
    reach it.
  - C variants tried (all ndiff 11 = the base, or worse): goto / `0.0f <` / `if (1) {}` / while / r declared in
    the block / `int r` in the for / `j <= 1` / `1 == phase` / `r != 4` / pre-increments; `sVrLabels[42 + ...]`,
    2-D arrays, row pointers, `g = sVrLabels_3F0` before the if, an inline grid helper, and a volatile 2.
  - Next: find a C construct that leaves s5 / s6 / s7 live at the after-if block (a code-free use after the if,
    which needs uopt to keep the LR); or read as1i's I5 path set for bb34 to see which reject the target took.
  - Scratch: `v3878/`, `ncck.sh` (ncc721 that keeps its intermediates; `AS1OPT`, `UOPTX`), `asm.sh` (as0 + as1i
    oracle), `ad.py` (aligned mnemonic diff), all under agentb/.
- **0x319C (course scores draw) is still INCLUDE_ASM. There is a target-length draft** (agentb/vr319C_best_d2.c,
  114 words). It is the run-646 body (struct-indexed `&rec[course]` and `.scores[i]`; `show = 1` before the
  GetScore call) plus a code-free `if (1) {}` as the first statement inside `if (show)`. That stops uopt hoisting
  `&col` into s8, so course*48 gets s8 and `&col` is rematerialised (`addiu t9,sp,116`), as in the target. Left:
  an s-register permutation (target y s2 / i s3 / show s4 / course s7 / course*48 s8; ours y s4 / i s2 / show s3 /
  course s8 / course*48 s7) and `e->score` in v1 instead of v0. The off / char-pointer spellings of the first
  course*48 are byte-identical to the base.

### agent-b run 651: viewrec.uso 0x3000..0x47FF + ctors 0x4854 / 0x5200 (3526 / 3579, +3 exact)

Commits on agent-b: cf358ba38 (4854, 5200), 5b2c6a5f0 (3F24), 1670d10ad (episodes). No renames.

- **Screen ctors 0x4854 (0x98 bytes) / 0x5200 (0x70 bytes) EXACT**, cfe C, in the 36B4 shape (levers
  from agent-g's drafts). In 4854 every constant store follows Process_stop. Call it through the void
  alias `gl_func_00000000_vrv`, so that no dead v0 def sits at the call and the shared constant 76
  colours v0. In 5200: `+0x68 = vr_gLanguage`; the white is `d = 255.0f; c = 255 / d;` (a local
  divisor and an int numerator keep the dividend and the divisor in separate mtc1s); and the 0x30 / 0x2C / 0x48
  flag stores come right after the call. Six new 0-pinned vtable symbols, `vr_vt{Node,Proc,Screen}_{4854,5200}`.
- **viewrec RoData layout:** 0x0..0xC = four separate 0.1f literals (0x3878), 0x10 = 0x3878's 5-entry
  table, 0x24 = 0x3F24's 5-entry table, then 0x4990's tables at 0x38 / 0x48.
- **0x3F24 (erase-select pad handling) EXACT**, cfe C: a switch on the phase (+0xA0), and inside it a
  switch on the set cursor +0xA4 (0 course times / 1 course scores -> phase 1; 2 arcade / 3 ghost (only
  if Backup_ghostGetMode) / 4 all -> proc mode 0x2000000, +0x70 = 1). Phase 1 moves the course +0xA8 on
  the 2 x 4 grid. Two levers: the case-0 `snd_postEvent(5)` goes through the void alias (it frees v0 for
  the +0xAC read), and the first phase-1 test reads `self+0xA8 > self+0xAC` rather than the saved `old`.
  For the table, the unit's .rodata (only that table, while 0x3878 stays INCLUDE_ASM) is pinned NOLOAD at
  **VMA 0x24 with `SUBALIGN(4)`** (tenshoe.ld `.viewrec_uso_3F24_jtbl`). Without SUBALIGN, the .o's
  16-byte .rodata alignment puts it at 0x30. Once 0x3878 is C, its literals and table come first, and the
  VMA goes back to 0.
- **0x3878 (erase screen draw) is still INCLUDE_ASM. It needs MIPSpro 7.2.1 (tools/ncc721.sh).** The
  target multiplies `64.0f * fade` and `blink * fade` with the constant / converted int as the first
  mul.s operand. cfe always puts the field load first: every operand order, int constants and a local
  copy all fail. IDO NCC gets the order right but lowers the 5-case switch to a beq chain. mp72 gets both
  right. The best mp72 draft is 98.1 % of words (`--raw --pins`, diffwords 14 -> 24, with only the
  scheduling below left).
  - Levers: `for` loops with the sprite as `&sVrLabels[29 + i]`, and the grid as `&sVrLabels_3F0[r * 2 + j]`
    (uopt strength-reduces them into the spilled row / index induction words at sp+80 / 84).
  - Declare `col` then `blink`, then an unused `volatile int pad[6]`: this gives frame 152, col at 136,
    blink at 132.
  - Compare `r * 2 + j == self->course`.
  - The one residual: uopt hoists the grid loop's `r = 0` and the constants 2 / 1 (s5 / s7 / s6) above the
    `selFade > 0` bc1fl. The target keeps them after it, with a nop in the c.lt.s slot. `if (1) {}`
    before or inside the if, and a do-while outer loop, do not help.
  - With `&sVrLabels[21 + r*2 + j]`, the hoist matches the target but the row base is wrong (+504 is added
    per row).
  - Draft: /tmp/claude-1000/-home-danjs-code-decomp/843f1ac1-389e-4d4a-9ec1-9423b96b9705/scratchpad/agentb/vr3878_mp72_best.cpp.
  - To land it, use an mp72 donor (`viewrec_uso_mp72_3878.cpp`, REPLACE_FUNC_BODY). Its .rodata reloc
    becomes `viewrec_uso_func_00003878_rodata`, pinned 0, so the in-place addends 0..0x10 stand. 3F24's NOLOAD
    VMA stays 0x24.
- Not reached this run: 0x319C (3364 levers at the target length) and 0x4354 (84 % NM; unchanged).

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

- Run 649 (agent-h, commits cdd4bb7de dfc76a980, no renames): +4 NM (objdiff 98.8-99.2 %), 0 exact.
  NON_MATCHING-only NCC donor `src/snoweffects_uso/snoweffects_uso_ncc_nm.cpp` (`SNOW_NM_FUNCS`, spliced on
  build/non_matching only; the name-placeholder-calls gate only maps matching-build splices, so NM donors
  call `gl_func_00000000` with a comment, not `CALL(name)`).
  - **0x15D0 / 0x1A18 / 0x1E60 / 0x2310 are texture-sprite inits** (one shape): name (+0xC), a 20-packet DL
    context at +0x2C (gfx_newDLContext + reset), PipeSync, w = h = 32 / 32 / 64 / 8 at +0x34 / +0x38, the stock
    2.0I gDPLoadTextureTile (I8 / I8 / IA8 / I8 of Data+0x6FD8 / 0x6BD0 / 0x5AC0 / 0x73E0, mask 5 / 5 / 6 / 5),
    gSPTexture, cycle / persp (/ textfilt / dither on 1E60), render mode, combine, prim colour, depth source,
    EndDL. 0x2310 first sets floats +0x98..+0xCC (RoData+0x8 at +0xA4, pin `snow_ro_8`) as separate
    statements (chained assignments shift the edg inline-temp numbering and swap head / n colours).
  - **Lever:** gfx_resetDLContext as a void-typed alias (`gl_func_00000000_snow_reset`): an int-returning
    call defines v0 in the first packet's live unit, so the inline next() context temp (u = 8 units,
    coloured first) cannot take v0 (lines 36 % -> 82 %). Left: per-packet pointers rotate a1 / a2 where the
    target has a2 / a3 (live-unit layout again, as 0x4188). 0x1E60 is 91 % lines but 301 words (the target
    fills the jr ra delay slot with the sp restore, ours does not; dropping a packet does not change it),
    so it is a draft in the donor, not spliced (a size change shifts 0xA8D0 past TRUNCATE_TEXT and the
    gate fails).
  - **0x4374** = basis rebuild (90 % lines): end points (+-len, 0, 0) and the origin through the world
    matrix (+0x30), dir = a - b normalized (+0x114, copy at +0xFC), cross(dir, camera +0x3B0, dir), +0x108 =
    camera +0x318 normalized, virtual slots 14 / 15. operator- through an inline `set()` (all subs before the
    stores), by-value `operator=(V3)` (the aggregate copy + field-wise store), vcall arg `(int)d + (int)t`.
    Left: the operator- temps 8 bytes low (frame 152 vs 160).
  - Not reached: 0x270, 0xC90, 0x28E0, 0x39C4, 0x47D4, 0x4E5C, 0x559C, then 0x4188 / 0x97C.
    Tools: /tmp/claude-1000/agent-h/r649/ (dis.py annotated target, cf.sh compile + diff, tex4.py, t43h.cpp).

- Run 656 (agent-h, commits 0603fe742 28cddb438, no renames): +1 EXACT (0x39C4), +1 NM (0x4E5C, objdiff 99.9 %).
  - **0x39C4 SnowFall fill EXACT** (NCC donor in snoweffects_uso_ncc.cpp, `_rodata` pin 0x10: donor .rodata
    +4 because 27A8's word comes first in the file). Levers: GfxLib through a local pointer
    (`SnowGfxLib *gl = (SnowGfxLib *)D_00000000`) keeps one &D base for worldScale (296(v0)) instead of a
    folded D+0x128 lui; **`if (1) {}` right after the third sys_randf** stops uopt sinking
    b = (r - 0.5) * 60 down to its first use (169 -> 22 diff lines); the constant-store block wants the
    gravity load first (720-permutation search) and accel.y between accel.x and accel.z (move-one search).
  - **0x4E5C** (NM donor snoweffects_uso_ncc_nm.cpp): every instruction matches; frame 192 vs 216. mdebug
    (`/tmp/claude-1000/c643/mdebug.py` on an `-O2 -g3` build): ours ang -4, hit -16, two pool words -20 / -24,
    xf nx..nz -28..-36. Target: xf's nz at -28, so it has no pool words there. Those words are pointer
    pool slots shared by the inline dot() refs and xf()'s params: removing both (explicit dot plus a macro
    xf) frees one, but changes code. The operator* chains are r -92 / ret -76 / param -60 and r -152 /
    ret -76 / param -140, with 4-byte gaps. Ours packs them (-76 / -60 / -108 shared). Named-`d`,
    by-value `a`, member operator* and ctor-return probes all change code or don't move slots.
  - 0x4374: the xf macro form also changes code (208 vs 210 words). The 8-byte gap under pa / pb is the
    xf param pool.
  - Not reached: 0x47D4 (418 words: slot-state update, Vec3 temps), 0x559C (~650 words), 15D0 family /
    4188 live-unit, 1E60, 97C. Tools: /tmp/claude-1000/agent-h/r656/ (md.sh = -g3 slot dump, vm.sh =
    variant + slots, abl.py = ablation batches, perm6.py / mv1.py statement-order searches).

- Run 660 (agent-h, commit 6f5340a26 NM only, no renames, no exacts):
  - **15D0 / 1A18 / 2310:** the named-index next() (`int n = dl->count++; Gfx *g = &dl->buf[n]; return g;`) is
    96 -> 66 / 100 -> 70 / 102 -> 72 diff lines. Packets 1-2 and the w / h constant 32 now match (a1, a2, K32 a3).
    The rest is the target's packet-pointer sequence `a1 a2 | a2 a3 a2 a3 a2 a3 a2 a3 a2 a3 | t0 | a1 a2 | v1`:
    from packet 3, a1 is busy in every unit, but no visible a1 value exists there. The last packet's v1 means the
    target's final unit starts after that packet's count store. Phantom greedy (`if (t->dl) {}` at statements
    6 / 10 / 15) gets down to 30 lines, but only by colouring a CSE'd t->dl range a1 (ctx loads then use a1, not
    v0), so it was not landed. Flat: 16 next() bodies (DList::next members, `if` inside next, split increment).
    1E60's draft gets worse with the named form (51 -> 75), but it is not spliced.
  - **4188:** the units come in whole statements. 1-23 `(c->w[k] & 0)` phantoms in one packet's w1 move the
    0|1 boundary by a whole statement or not at all: none before packet 3, and in packet 1 the boundary drops
    in front of packet 2. Packet 3's `_g = next()` statement has to fit in unit 0, which needs one fewer op
    before it, and phantoms can only add ops. Flat: register / const / reference / `_g[0]` / `unsigned *` packet
    locals, and the explicit `&c->dl->buf[c->dl->count++]` for any subset of packets 1-4 (edg makes no `this`
    temp for a parameter ctx).
  - **0x47D4 decoded** (draft /tmp/claude-1000/agent-h/r660/t47b.cpp, NCC, 431 vs 414 words). It is the
    emitter update: u4C = +-cam+0x970 (flag 0x80); p / q zeroed, len / u40 = u34 / u38; call 0x4374; u80 =
    hits <= 0; hits = 0 unless mode (cam+0x9A2) is 97 / 98 and speed (cam+0x348) >= 5; on = 0x46BC(t); a = u164,
    or u164 / (u160 - 5) * (speed - 5) when speed < u160; alpha = |u4C| * u168 * (255 - a) + a; slots[write].u4 =
    mode == 98; P = p, Q = q (by-value operator=); 0x4714(t, on, prev, alpha) (float in a3); alpha = 0 on slot
    state 2; for stride 4 in mode 98 the drop is u158 and dv = normalize(cam->v318) * u154, otherwise both are 0.
    When on, each i < stride gets w = lerp(P, Q, i / (stride - 1)), plus dv and minus drop for i == 1 / 2.
    That goes to points[writeOfs + i] (pos, w18 = 0, vel.set(0), u28 = 0, w1C = alpha, w20 = w1C / (size /
    u16C)), and vtx[writeOfs + i] gets tc.s = (int)((uA8 - 1) * i / (stride - 1)) << 6, tc.t =
    ((writeOfs & stride) >> 1) * 31U << 6, and rgb = cam+0xA30..A32. Then vslot 16, prev = on, prevMode = mode.
    Open: the target keeps 5.0f in f20 across the 46BC call, materialized in both arms of the hits test, and
    f20 is reused for the drop. A `lim` variable is constant-propagated (no change). alpha lives in f22. The
    frame is 184 vs 160: the Vec temps sit at sp100 (operator= param) / 160 P / 148 Q / 132 dv / 72 w.
  - Not reached: 559C, 1E60, 4374 / 4E5C frames, 97C. Tools: r660/cf2.py (NCC compile + diff with
    function-relative branch targets), gen.py / s3.py / s6.py (15D0 phantom greedy), s41.py / mk42.py (4188 packet
    kinds and phantom counts), pk.py (packet-pointer register sequence).

- Run 666 (agent-h, commits e7d64733b EXACT, 7a43984e0 NM only, no renames): +1 EXACT, 3554 / 3579.
  - **0x4E5C EXACT** (moved to the matching donor snoweffects_uso_ncc.cpp). The code already matched, only the frame
    did not (192 vs 216). Three levers: the inline point transform declares its results **z, y, x**
    (`float nz, ny, nx;`, then the assignments in x, y, z order), so the spilled z temp sits at vfp-28; agent-e's
    0x8D70 push shape (a named `push = hit * -d` in each if-block, member operator*, += by const reference);
    one `{ int sc[4]; sc[0] = 0; }` after the first push. The placement came from a one-block search script
    (r666/sc.py: every statement position x 1-6 words, scored by diff lines, about 0.06 s per compile).
  - **0x4374 NM** (40 -> 16 diff lines): the frame is now 160 with every slot right. Changes: no `pa` / `pb`
    pointer locals, the z, y, x transform, and one scratch word in operator- before `return r`. Left: the
    operator- return-temp address (sp+0x74) is scheduled into a1 at entry, where the target computes it in v0
    right before the copy. A `const SnowBV3 &d = a - b` binding is much worse (97).
  - **0x47D4** (draft r666/t47.cpp: 416 vs 414 words, 350 diff lines, was 605). Single copy `dv = cam->v318`,
    u154 read once, `hits <= 0` arm order. The open part is FP colouring. In the instrumented uopt
    (iu/tr.sh, F=snoweffects_uso_func_000047D4) the callee range costs 12.25 per register, alpha's
    caller-range cost is 3.0 (two calls), so alpha takes f18 and is spilled around the calls. The 5.0f
    constant is two LRs: bb14-17 (the hits test) and bb18-19 (after the 46BC call). In the target, alpha is in f22
    and one 5.0 LR runs across the call into f20; the target also reloads 5.0 on the bne-97 arm. No effect from:
    literal / variable / `const` / `static const` 5.0; four spellings of the hits condition; `lim` assigned in both
    arms; an `if (5.0f) {}` use. Next: find what pushes alpha's caller cost above 12.25, or what makes the 5.0
    LR live through the call block.
  - 0x559C read, not decoded. It is a lit textured strip draw: a stack BaseMat (mem_new / this == 0
    protocol, Data+0x20640 vtable, BaseMat_init_000517E4); gfx_emitLights; then a per-slot loop. The loop
    covers world-scale vertex positions (+0.5 trunc), alpha clamp, G_VTX 0x04 packets, and per-slot texture
    loads from the Data+0x588 table (FD18 / F518 / E6 / F4 / E7 / F518 / F2 packets, w = h = 32 at
    +0xA8 / +0xAC). Not started: 15D0 family / 4188, 1E60, 97C.

- Run 671 (agent-h, commit 325817be1 on agent-h, no renames): +1 EXACT (0x4374), 3557 / 3579.
  - **0x4374 EXACT** (moved to the matching donor snoweffects_uso_ncc.cpp, sharing 4E5C's SnowBasis / SnowBCam /
    SnowBV3, plus a by-value operator= and a free operator-). The run-666 residual was a **live-unit** effect:
    the instrumented uopt (iu/tr.sh) showed the result-temp address constant K-44 (sp+0x74) coloured in the same
    unit as the &t->b subtraction loads (e1450 = v0), so v0 was forbidden and it took a1, scheduled up to entry.
    An `if (1) {}` in operator- after the subtraction ends that unit, and the address takes v0 as in the target.
    The frame then drops to 152; a dead `{ int sc[2]; sc[0] = 0; }` anywhere after the first normalize restores 160.
  - **0x47D4** (draft r666/t47.cpp, 350 lines): the `* 1` lever on alpha / lim (any position) is 338 at best, and
    alpha is still caller-saved. Root cause, found from the target's loop: the target has **8 FP LRs in the loop**:
    w.x CSE f2, w.y / w.z CSE f0 (uopt-coloured), f f12, (float)i f14, zero f16, 1.0 f18. That leaves no free
    caller-saved FP register, so alpha goes to f22 and lim to f20. Ours has no uopt LR for the w.x / w.y loads
    (x.lr: M-116 / M-112 `sv=true`, not candidates; their reuse is a ugen tree temp), so f / i take f0 / f2 and
    alpha gets f18. Same code with no change: `+=`, `w.x + ..` first, dx / wx temps in blocks, member lerp().
    Worse: a free lerp() by value (669), f computed before `w = P` (413 words, 571). Next: find a spelling where
    w is not a M-variable (the target copies P to w with lw/sw, so w is still an aggregate copy), e.g. w as the
    by-value parameter of an inline emit(), or the lerp via a reference to points[..].pos.
  - **15D0 / 1A18** (NM, not landed): the `* 1` lever on the packet pointer **inside** the gbi macro (`Gfx *_g =
    (Gfx *)(pkt); _g = (Gfx *)((int)_g * 1);`) at sites 3 (tile LoadTile... 4th sub-packet of the texture tile),
    9, 11, 12 (counting PipeSync = 0, the 7 tile sub-packets 1-7, then the gDPWord packets) gives 15D0 66 -> 42 and
    1A18 70 -> 46 diff lines. The same `* 1` inside next() or on the pkt expression does nothing, and neither does
    `t * 1` / `t->dl * 1` at any statement. What's left is still the hidden a1 from packet 3 on (target a2 / a3 where
    ours has a1 / a2). Tools: r671/p15d.py (per-site N0 / N1 macro variants plus greedy), p15e.py (0/1/2 local
    search), ins2.py (insert a snippet at each line).
  - 0x559C / 0x1E60 were re-scoped to agent-b (559C was not started).

- Run 676 (agent-h, commits 8d7f3f118 + 6ad5629b3 on agent-h, NM only, no renames, no exacts; 3558 / 3579).
  - **15D0 / 1A18 / 2310 NM** (snoweffects_uso_ncc_nm.cpp): run 671's per-site `* 1` hooks landed (66 / 70 / 72 -> 42 /
    46 / 48 lines), then three zero-code counted loads `(*(int *)((char *)t + K) & 0)` (distinct K) in the FA (prim
    colour) packet's w0: 36 / 40 / 42 (objdiff 99.67 / 99.66 / 99.69). Found by a per-site greedy over hook count 0-2 x
    phantom count 0-8 x `if (1) {}` (r676/gen18.py, s19.py; ~40 ms per NCC compile). Left: packets 3, 5-9 take a1 / a2 /
    t0 where the target has a2 / a3, and the last packet a1 (target v1: its final live unit starts after the last count
    store). Flat or worse: inline-function emitters (`Gfx *eW(Gfx *, a, b)` returning the packet, discarded or `(void)`,
    or void; args become named temps, 346-464 lines); a `pk(Gfx *)` pass-through wrapper (edg gives the nested next() its
    own pooled `this` temp, so the outer one spans fewer units: 54-436); per-site mixes of 5 next() bodies (all edg
    inline temps are pooled by type, so renamed locals in a second next() change nothing); keeping packet 1's pointer
    live with `+ 0 * (int)head` (its LR then spans units and takes t1: 90-360).
  - **0x47D4**: the by-value-parameter emit helper (`emit(t, i, SnowBV3 w, ..)` with the lerp inside, or w = P passed
    by value) brings the frame to the target's 184 but the FP colouring is unchanged ((float)i f2 / f f0 vs the target's
    f14 / f12, w.x f2); operator chains `w = w + (Q - w) * f` keep their temps in memory (463-486 words). Draft stays
    r671/t47.cpp (350 lines); variants in r676/47/.
  - **0x97C** (2-word swap, cfe): the reload of p sits right after the jal in ugen's output (`cc -S`), so as1 puts it
    before the mul.s. All 120 orders of the post-call group x 8 spellings of `r * 2` are flat (4 lines). An
    address-taken p (`{ SnowParticle **pp = &p; }`) reloads at each use and lands the first reload one slot earlier
    still. Flat too: inline randf, r2, early return, top-level decls, register p, `if (1) {}`, a return copy.
    Next: something that makes ugen emit the reload lazily (after the 1.0f constant).
  - **0x4188**: run 671's `* 1` hook does nothing here (all 256 hook subsets x 4 `if (1)` positions x 2 pad positions;
    2187 random hook / phantom / `if (1)` mixes): still 3 words (packet 4's FC pointer v0 vs a3).

- Run 684 (agent-h, commit 5d93b128c on agent-h, no renames): +1 EXACT (0x97C), 3561 / 3579 (gate PASS).
  - **0x97C SnowPool_spawnRandom EXACT (cfe C, promoted from NM).** The 2-word swap (the p reload vs the `r * 2` mul.s)
    was the known as1 same-line tie-break (IDO_CODEGEN "as1 scheduler tie-break ... SINGLE source line"): ugen always
    emits the reload right after the jal (`cc -S`), and only as1 moves it. Putting `r = sys_randf(); p->unk38 =
    (0, 10.0f) + r * 2; p->unk3C = 1.0f;` on ONE line gives the target order; a line-join search over every 2-6 line
    window found that this 3-statement join is the smallest one that works. The `(0, 10.0f)` comma lever is still
    needed (plain `10.0f + r * 2` on the joined line: 16 diffs). Run 676's "120 orders x 8 spellings, all flat" never
    varied lines.
  - **0x4188 (still 3 words, packet 3's pointer v0 vs a3).** Per-site next / nextN / nextR / nextI (agent-c's
    named-result family) at all 4 front packets x 7 `if (1)` sets x pad: best 3, every named form is 6+ (r684/g41.py).
    The same with nextR / nextI on packets 3-4 x every 1-2 `if (1)` positions at statement granularity (3776 compiles):
    best 3 (g41b.py). Line layout does not move uopt's unit cut here (only the as1 schedule: 3 -> 5 / 7); a hill climb
    over joins x `if (1)` x kinds plateaus at 3 (h41.py). New confirmation of the run-644 diagnosis: storing packets 1-2
    as one 64-bit word each (`*(unsigned long long *)_g = 0xE700000000000000ULL`) removes one counted ucode store per
    packet, and packet 3 then takes **a3** exactly as in the target, but ugen materializes the zero low word
    (`addiu t1,zero,0`), so the code is wrong. The original had one fewer counted op before packet 3's
    `_g = next()`. uopt's unit limit is the global at 0x1001c43c (default 0x14 = 20, set in f_getop from an option);
    the counter 0x1001c430 is bumped in readnxtinst (h414/u/uopt_i.c around lines 81620 / 81795). Next: read which
    opcodes reach those two increments, to know which of packet 1-2's ops count (the str of the edg dl / count temps?).
    Flat: the `t` parameter unnamed / int / used (the a0 home store is ugen's, not counted); comma-joined packet 2 / 3
    statements; pre-increment, `+= 1`, and split-store next() bodies (n1-n7: code changes, 100-217).
  - **0xC90** (agent-c's NM donor, objdiff 82.85; cq9 frame-400 draft: 237 differing words after register
    normalisation, vs 328 for the donor). Line joins in the body have no effect (colouring / frame residual, not as1).
    The target reaches the world scale as `lwc1 296(at) / 300(at) / 304(at)` (immediates kept, one lui shared by the
    first two loads), so the scale is addressed as gGfxLib + 0x128.. in the target.
  - **0x47D4** (r671/t47.cpp, 354 raw / 196 normalised differing words). Trace (iu/tr.sh): alpha is M-24, caller cost
    2.0 at f18 against 12.25 for every callee-saved FP register, so it is not a cost tie: callee-saved can only win
    when all six caller-saved FP registers (f2 f12 f14 f16 f18 f20) are forbidden at alpha's pick, as in the target's
    loop. Pointer / reference / temp / P-read / one-line spellings of the w lerp compile to identical code (edg
    normalises them).
  - Tools: /tmp/claude-1000/agent-h/r684/ (sc.py parallel-safe NCC / cfe scorer, one.py positional diff, dd.py
    difflib diff with register normalisation, ss.sh ugen `cc -S` dump, lj.py greedy line-join search, g41*.py / h41.py
    4188 searches, t64.py the 64-bit store probe).

- Run 687 (agent-h, commits 9b25c3bc6 EXACT + 8b951067b NM, no renames): +1 EXACT (0x4188), 3562 / 3579 (gate PASS).
  - **What counts toward uopt's ~20-op live unit (read from the uopt recomp, readnxtinst).** The counter 0x1001c430
    is bumped at only two sites, both in the Ulod (op 82) case: a load of a VARIABLE whose value uopt cannot forward,
    meaning a parameter or never-assigned var (path A), or a temp holding an expression with an ilod / a bigtree /
    a killed tree (path B). Not counted: istr / ilod / ldc / ixa / str, loads of volatile vars, of globals, and of
    a var whose current value is a forwardable copy or constant (`r = a; .. r`, `q = &loc; .. *q`). The unit is cut
    once the count reaches the limit (0x1001c43c = 20) at the next statement op; a call resets it.
    Instrumented build: /tmp/claude-1000/agent-h/r687/u/ (uopt_x.c = h414 uopt_i.c + fprintf of each op, each
    increment and each reset; out/NCC; units.sh / cnt.py print per-source-line counts and the reset lines).
  - Under edg the inline `&dl->buf[dl->count++]` costs 8 counted loads per packet (ctx x2, dl temp x2,
    old-count temp x2, packet pointer x2); the named-result next() costs 6.
  - **0x4188 EXACT: a reference-bound copy of the ctx parameter** (`DLCtx &ctx = *c; DLCtx *dc = &ctx;`, all
    packets through dc). Loads of dc are forwarded copies, so each packet costs 2 fewer counted loads, and packet 3's
    buffer pointer lands in unit 0 as in the target (a3). The two pointer locals also give the 144-byte frame and the
    sp+44 spill slot (one local: sp+48). Needs the one-expression append (new DLCtx::append() / APKT in
    snoweffects_ncc.h). This is the "one fewer counted op" run 644 asked for. All other packet spellings (asg /
    ref / unsigned * / comma / [0]) are normalised by edg (same counts).
  - **0xC90 NM 82.90 -> 84.92** (objdiff). The scale words go through three 0-based gGfxLib aliases typed as the
    gGfxLib layout (`snow_gfx_scale_128.sx` ..): own lui + the +0x128 / +0x12C / +0x130 immediates as in the target.
    One shared alias (`*(float *)(&snow_gGfxLib + 0x128)`, a struct global, or a `const &` to one) is hoisted into
    a register (ra / s1). objdiff ignores the immediates (cq9 alone = 80.74 either way). Then scaled() reads the
    scale inside the inline into named x / y / z (products in f0 / f2 / f14, target f0 / f2 / f12) plus agent-c's
    cq9 frame levers with scratch[5] (frame 400). Flat: x / y / z declaration order, `= { x, y, z }`, by-value a
    (81.9), the scratch position / size (84.89-84.92), per-site next / nextN (raw-best texrect nextN = 83.75).
    Left: i in s2 and the return-temp address in s3 (ours ra / s1), float colouring after the projection.
  - **0x47D4** (no donor yet; r671/t47.cpp 354 raw / 196 normalised). The target holds the w.x / w.y / w.z loads in
    uopt colours (f2 / f0 / f0), with (float)i in f14 and f in f12; ours leaves them to ugen (f10) and gives
    (float)i f2, f f0. Flat (code identical): named x / y / z copies in any layout, a by-value `lerpf(a, b, t)`
    inline in both argument orders, a `float &` lerp. Not tried: a donor commit (objdiff unknown), w as a
    non-copy (fields assigned from P), and the 4188 copy lever on t inside the loop.
  - 15D0 (NM donor, 18 diff lines): the 4188 copy lever on `t` (`SnowTex &tr = *t; SnowTex *tc = &tr;`) at any
    1-2 packet sites or prefix / suffix sets is flat (18). Not yet traced with units.sh.

- Run 694 (agent-h, commits 9ae3b52bf + ee8e71bd8 on agent-h, NM only, no renames, no exacts; 3564 / 3579, gate PASS).
  - **0x47D4 NM 94.58 %** (objdiff; new donor src/snoweffects_uso/snoweffects_uso_ncc_nm_h.cpp, own Makefile block
    SNOW_NM_H, aliases gl_func_00000000_snow_46bc / _snow_4714). The r671 draft landed at 89.96; then **only the x
    component** goes through agent-g-style `float &` helpers that copy the old value
    (`lerpTo(float &a, float f, float b) { float c = a; a = (b - c) * f + c; }` and `addTo(w.x, dv.x)`,
    `addTo(w.y, -lim)`), y / z stay plain: w.x becomes a uopt LR in f2 as in the target, alpha moves to a
    callee-saved register and the frame is the target's 184 (94.58). Helpers on all three components make the three
    copies one-block LRs that all interfere (f2 / f12 / f14, worse). uopt's interference is per basic block, so the
    target's w.y / w.z sharing f0 means they are not one-block uopt LRs there.
  - Left on 0x47D4: f is f0 and (float)i f12 where the target has f12 / f14 (one more caller-saved LR in the loop), so
    lim stays caller-saved f18 (target f20, alpha f22). Flat or worse (objdiff, scorer r694/od.py): `if (1) {}` /
    `if (i) {}` / `if (f) {}` / `if (t) {}` between the lerps (432 combos); a shared `c` for y / z (block, loop or
    function scope, plain or via a `float &c` helper parameter); `const float &f`; `register f`; f before `w = P`;
    setf() on the point stores (w18 / w1C / vel; vel is 80.8); setf on lim.
  - Trace note: in iu/tr.sh (ord.py) the FP labels are shifted by one: trace "f2" = real f0, "f12" = f2, "f14" =
    f12 .. "f22" = f20 (the first callee-saved, cost 12.25).
  - **0xC90** (84.92, agent-c's donor file, not committed): `if (hgt) {} if (wid) {}` after the texrect gives 85.15
    and a few more code-free lines 85.23 (as1 line effects, not the registers). The target keeps hgt in s1 and wid
    in ra (callee-saved: the loop's GPR pressure fills t0-t5 / ra), which pushes i to s2 and the scaled() return-temp
    address to s3; ours keeps hgt / wid in t5 / t4, so i takes ra and the address s1. Next: find what extra
    caller-saved GPR LRs the target has across the texrect block (uopt trace: F=snoweffects_uso_func_00000C90).
  - Tools: /tmp/claude-1000/agent-h/r694/ (od.py = parallel-safe one-function objdiff scorer: NCC compile + a
    temp objdiff.json against expected/; tv.py variant runner; var3o.py / var6.py 47D4 searches; c1.py / c2.py C90).

- Run 699 (agent-h, commit 0c61a7bab on agent-h, NM only, no renames, no exacts; 3564 / 3579).
  - **0xC90 moved** from agent-c's snoweffects_uso_ncc_c.cpp (SNOW_C_NM_FUNCS) to agent-h's
    snoweffects_uso_ncc_nm_h.cpp (SNOW_NM_H_FUNCS), with run 694's code-free lines: objdiff 84.92 -> 85.23. agent-c's
    file keeps the snow_gGfxLib extern (0x28E0 uses it); 0x270 / 0x28E0 unchanged (100 / 88.89).
    Flat or worse on top: named x1 / y1 (84.41), named xs / ys shifts (84.09), a named packet `Gfx *g` (79.7), named
    ds / dt steps (69.8). The target puts hgt / wid in s1 / ra; the GPR trace is not done yet.
  - **0x47D4 (94.58, unchanged): the y / z half is found.** One `float c` shared by y and z inside ONE inline whose
    reference parameters are the destinations (`lerp2(float &a, float &a2, float f, float b, float b2) { float c = a;
    a = (b - c) * f + c; c = a2; a2 = (b2 - c) * f + c; }`) gives one uopt LR (num 60) coloured f0, which is the
    target's w.y / w.z in f0 (exact loop lines). A plain block `float c` is forwarded to the w.y load and gets no LR.
    So do `float &y = w.y` refs and pointer forms. Separate helpers give three LRs that interfere.
    The shared c still loses net (94.30): f (num 40 = def + 3 uses) outranks the x copy (num 30), so f takes f2 and
    c_x f12 (the target has c_x f2 and f f12). One more caller-saved LR also pushes lim off f18: alpha takes f20, lim is
    spilled (+16 frame, 200 vs 184).
    Priority ties go to the lower LR id (trace column 2; f = 159 < c_x = 166). `c = (b - c) * f + c; a = c;` gives c_x
    num 50 (f2, f f12, as the target), but the sum then lands in f2 instead of a ugen temp (92.5).
    Flat or worse: `* 1` / `+= 0` on c or f, block splits (`if (1) {}` / `if (i) {}` / labels) between the f definition
    and the lerps, (float)i via `fi`, f by `const &` (spills f), a separate f for x (recomputes the div), a
    ld / st helper pair (cx goes to memory).
    Next: give c_x one more counted reference without a register def, or f one fewer. Then fix lim vs alpha (target
    lim f20, alpha f22).
    Drafts: /tmp/claude-1000/agent-h/r699/ (l2.cpp shared-c, x2def.cpp, lp.py loop-window diff, mk*.py batches).

- Run 702 (agent-h, commits 13f250cda + 44226a86c on agent-h, NM only, no renames, no exacts; 3564 / 3579, gate PASS each).
  - **0x47D4 NM 94.58 -> 94.91 -> 99.25 %** (objdiff, snoweffects_uso_ncc_nm_h.cpp).
    - 94.91: run 699's shared-c lerp2 for w.y / w.z, plus a plain `w.x += dv.x`. The addTo copy for x had taken a uopt
      colour (f0) for the hoisted w.x reload; the target keeps that w.x in a ugen temp (f10).
    - 99.25, **callee-saved first-use cost via the BB count:** lim was spilled because uopt's fresh callee-saved
      cost is 0.25 x BBs (49 BBs = 12.25). lim's split pieces have num 12 / 10, and alpha has 13. Removing the
      empty `SnowBV3() {}` constructor (each inline default constructor is an edg BB, IDO_CODEGEN kit CCX) lowers
      the cost. lim then takes f20 and alpha f22, exactly as in the target: lim is picked first, and once f20 is
      used it is free for lim's other pieces.
    - The target's f0 temps are named block locals: `{ float d = t->u160 - 5.0f; a = t->u164 / d * (..); }` and
      `{ float k = ab * t->u168; alpha = k * (255.0f - a) + a; }`. On their own (with the constructor) they cost
      2.9 points, because the extra LRs split alpha.
    - Left:
      - The frame is 192 (target 184). Declaration changes don't move it (drop / v removed, d / k via drop,
        `register`).
      - The target has a second zero constant LR in f18 (p / q zeroing at the top and the dv zero stores); ours
        uses one zero, f16.
      - ab and the alpha temp are swapped (ours f2 / f12, target f12 / f2).
      - In the loop, f and the x copy are still swapped.
    - Small, not landed: `float r = ..; alpha = r;` (99.27, frame 200); `drop` for the u154 scale (99.29, frame 200).
  - **MIPSpro 7.2.1 check (agent-e's lead):** under tools/ncc721.sh, 47D4 compiles to the same code (99.25) and C90 to
    worse code (76.7, 607 words, target 592), with no s1 and no hgt / wid flip. Both stay on IDO 7.1 NCC.
  - **0xC90 (85.23, unchanged).** In the uopt trace, hgt (M-24, pri 5.0) and wid (a CSE temp) take t5 / t4 before
    the caller-saved registers are exhausted. In the target they colour after t0-t5, with wid in ra first and then
    hgt in s1. Flat or worse:
      - a single `if (1) {}` at every statement in the loop body (best: base);
      - `register` on hgt / wid;
      - declaration order;
      - extra `if (hgt / wid / i) {}`;
      - dropping the existing ones (84.92).
    Next: lower hgt's priority below the t-register users, or raise six other LRs across the texrect block.
  - Tools: /tmp/claude-1000/agent-h/r702/ (od72.py = od.py through ncc721.sh, trf.sh = FP rows of the uopt trace,
    sbs.py side-by-side vs expected, v*.py batches, c1.py / c2.py C90).

- Run 709 (agent-h, commits 4aa3bd66c NM 99.85 + 04e4d1373 EXACT, no renames; 3569 / 3579, gate PASS each).
  - **0x47D4 EXACT** (new matching donor src/snoweffects_uso/snoweffects_uso_ncc_47d4.cpp, own Makefile block
    SNOW_47D4_DONOR in both trees; the NM_H file now holds only 0xC90). Steps from 99.25:
    - **Frame 192 -> 184: no extra named temps.** The u160 - 5 (`d`), ab * u168 (`k`) and u154 (`s`) block locals
      each cost a word. Reusing function-scope floats for them costs none, and **which variable a piece reuses
      sets its uopt colour** (the piece joins that variable's LR). Final: `ab = t->u160 - 5.0f; a = .. / ab ..`,
      `|u4C|` into f, `ab = f * t->u168; alpha = ab * ..`, `f = t->u154`. That fixed the loop's f / x-copy swap and
      the ab / alpha-temp swap (u4C load f0, |u4C| f12, product f0). Searched as a d x abs x product x s matrix
      (r709/v3.py, v8.py, v17.py); most cells are 1-10 words off.
    - **Second zero constant without a frame word:** agent-g's `{ int z = 0; x = z; }` gives the separate zero
      (f18, apart from the f16 compare / loop zero), but the block z is a frame word. Reusing the function's int:
      `i = 0; t->p.x = i; ..` (p / q) and `i = 0; dv.set(i, i, i);` (dv) costs nothing.
    - **v0 / v1:** `void operator=(SnowBV3 o)` (no `return *this`) puts the vel.set pointer in v0.
    - **Frame order:** locals are laid out top-down in declaration order (`cam; alpha, lim; P, Q; i; dv; a, f, ab`
      gives P 160 / Q 148 / dv 132), then each inline's param / local words at the inline's FIRST expansion in
      source order (later expansions reuse them), then block locals as their blocks open. So `dv.scale(f)` and
      `dv.set(i, i, i)` before the loop move scale's / set's words ahead of the loop's `w` (sp+88 -> the target's
      sp+72); vel.set in the loop then reuses set's words.
    - Param words appear only when the inline needs a home for the param: a param used more than once with a
      non-variable argument (`fab(t->u4C)` adds one; `ratio(i, t->stride)` with n used once adds none), and
      `this` of a member called on a non-variable object.
  - **0xC90 (85.23, unchanged)**, probes (r709/c1-c4.py):
    - The target frame has v / __V / r at sp+220 / 204 / 192 (ours 236 / 220 / 196). Ours has 3 words between
      __V and r: scaled()'s named x / y / z. Dropping them gives the target's three offsets but 81.0 (the f0 / f2 /
      f12 products need them), and the frame top moves 16 down. So the target has 4 more words above the loop
      (function scope) and no inline locals in scaled(). Function-scope `float x, y, z` + an `mk3(x, y, z)`
      by-value builder: 85.19, frame 416 (the words don't land where expected).
    - Ours spills sy to its home slot (sp+368); the target spills 3 FP values to the bottom spill area (88-96).
      The target also has `self->tex` as a uopt LR (a1) at entry, and dl / count in a2 / v1 (ours v1 / a2);
      a local tex copy or a getDL() inline gives no change.
    - Ctors: `SnowV3c() {}` 83.2; + a copy ctor 82.6, but the normalised diff drops 824 -> 705 (597 words, target
      592) with the GPR picture unchanged (hgt / wid still t5 / t4, i ra). Worth a second look with the
      copy-ctor build as the base.
    - GPRs: the target has x0 / y0 / y0 << 2 / x0 + wid in t0 / t3 / t5 / a2 (ours a1 / a3 / t3 / a0), i.e. more
      interfering LRs in a0-a3 / t1-t2 across the texrect block; that is what pushes wid to ra and hgt to s1.
  - Tools: /tmp/claude-1000/agent-h/r709/ (fr.py = variant runner printing objdiff %, frame, sp offsets and the
    positional diff count; dd.py = branch-normalised opcode diff vs expected, `dd.py file.cpp [fn]`; fc.py = the
    C90 runner; md.py = -g3 local map for 47D4; b3-b7.cpp the 47D4 steps).

- Run 717 (agent-h, commits a422ef1ae + 773098895 on agent-h, NM only, no renames; 3570 / 3579, gate PASS each).
  - **0xC90 NM 85.23 -> 89.59 -> 90.99 %** (objdiff, snoweffects_uso_ncc_nm_h.cpp). All five callee-saved homes
    now match the target: self s0, hgt s1, i s2, the scaled() return-temp address s3, wid ra. Also x0 t0.
    - **Named depth int:** `int z = (int)(..* snow_ro_4); gDPWord(.., 0xEE000000, (z & 0x7FFF) << 16)`. The
      target keeps the truncated depth in a uopt register (a3); inline it is a ugen temp. Effect: 85.23 -> 89.57.
      Reusing `d` for it is worse (88.9).
    - **Constructed return in scaled():** `return SnowV3c(a.x * sx, a.y * sy, a.z * sz)` through a
      3-float constructor (no default ctor; `SnowV3c v = scaled(p->pos);`). The ctor parameters take
      f0 / f2 / f12 as in the target, with no frame words. Named x / y / z locals cost 3 words between __V and r.
      Effect: 89.59. With this, v / __V / r sit exactly 4 words above the target's offsets (236 / 220 / 208 vs
      220 / 204 / 192).
    - **The pooled edg temps decide the GPR picture.** next()'s dl / old-count temps (M-152 / M-148 in the trace)
      are function-wide edg temps. The prologue packet, every loop / tail packet and the texrect's MAX / MIN
      ternary results all reuse them. That makes count one 10-block LR (pri 26 < the pri-30 packet pointers),
      so it lands in a2 instead of the target's v0.
      - A different inline name with the same body changes nothing; neither does the count type
        (unsigned / long).
      - What works:
        - `nextN()` (`int n = dl->count++; return &dl->buf[n];`) on the first packet only. The prologue then gets
          its own count LR (a2 / v1 as in the target) and s2 appears.
        - An `inline int imax0(int a) { return a > 0 ? a : 0; }` for the w0 clamps (xh / yh only). The clamps
          get their own temps. Result: wid ra, hgt s0, self s1.
        - Dropping `if (hgt) {} if (wid) {}` then swaps self / hgt to the target's s0 / s1 (90.99).
    - **Flat or worse on top:**
      - imax0 on xl / yl as well (90.0 / 90.9);
      - imax0 taking `s16`, or an if / return body;
      - named xh / yl / (s16) ints, or `d` reused for them (bytes identical: uopt forwards them);
      - scratch[] > 1 (frame 408);
      - re-adding `if (wid / hgt / self / c) {}`.
    - **nextN() on the EE packet** gives the target's y0 t3 and z a3 and the exact length (592 words;
      positional diffs 476 -> 403), but objdiff drops to 89.4. Its EE count / dl are then a2 / v1 (target v0 / v1).
      This is probably the right direction if the loop's count can be made to take v0.
    - Left:
      - The loop count / dl / packet colours. The target has count v0, dl v1, EE packet a1, FB a0, E4 t4, B4 t3.
      - c in t4 (target t2).
      - self->tex is a uopt LR (a1) at entry in the target.
      - The FP side after the projection: the target keeps sy in f30 and spills 3 FP values to sp+88..96; ours
        spills sy to its home.
      - The frame: v / __V / r are 4 words high. scratch[] is down to 1 word, so the 4 missing words above v are
        real locals, not padding.
  - Tools: /tmp/claude-1000/agent-h/r717/:
    - fc.py: the runner; prints (normalised diff, positional diff, length, frame, objdiff);
    - md.sh: the -g3 local map for C90;
    - hc.py / hc2.py: the per-site next-form climb;
    - v*.py: the batches.

- Run 722 (agent-h, commits a6f101e79 + e8012b4fc on agent-h, NM only, no renames; 3570 / 3579, gate PASS each).
  - **Length rule:** the run-717 90.99 body was 593 words. That pushed 0xA8D0 past the non_matching
    TRUNCATE_TEXT (0xA900), and the coordinator reverted it. **C90's NM body must stay at 592 words (0x940).**
    Check `objdump -t build/non_matching/.../snoweffects_uso.c.o` for A8D0 at 0xA8D0 before committing.
  - **0xC90 NM 89.59 -> 92.58 -> 94.04 %** (objdiff), 592 words, frame 400.
    - **No h2 variable.** Write `halfH * 2.0f` inside both size expressions. The h2 variable was split into an
      expression LR (f2) plus a copy to f28, and that one extra caller-saved LR pushed k to f20 and sy to a spill.
      Without it, the CSE'd product takes f20 directly, k takes f18, and sx / sy get f28 / f30 through
      the target's `mov.s` in the branch delay slots. Effect: 89.98 -> 91.6. The whole float block 120..240 now
      matches apart from sp offsets.
    - The w0 clamp terms are written yh-first, so the target's xh-first evaluation comes out. imax0 is used on
      xh / yh / xl. **The OR order in w1 makes no difference** (uopt reassociates it); which clamps use imax0
      is what decides it.
    - **FB word alpha-first:** `((int)p->alpha & 0xFF) | (col[2] << 8) | (col[1] << 16) | (col[0] << 24)`
      gives the target's col[0]-first loads. Positional diffs 314 -> 243, objdiff 93.61 -> 94.04.
    - `if (y0) {}` before the FB packet and before drawn++ place the (s16)((x0 + wid) << 2) CSE right after x0,
      as in the target at word 243.
  - **Method:** a knob generator (g.py: per-packet next / nextN, a clamp form per term, term order, `if` sites,
    scratch size) and a climb (hc.py). Two objectives:
    - objdiff, under the 592-word and frame-400 constraints;
    - MODE=loop: positional mismatches in words 200..470, with branch targets and sp offsets normalised.

    Climbing on the loop-layout objective broke the objdiff plateau at 92.58, reaching 93.61.
  - Left:
    - w1 evaluates yl first. The target does xl first: x0 << 2 is computed late, y0 << 2 early and unsigned in
      t5, with its s16 conversion late.
    - Only one clamp-result preset (`or a1,zero,zero`) before FB; the target has two (a1 / a3).
    - Loop count in a2 (target v0); EE packet v0 (target a1).
    - GPR names x0 t4 / y0 a3 (target t0 / t3).
    - self->tex in t9 at entry (target a1); the prologue's count / dl in a2 / v1 are swapped.
    - Frame: m sits 1 word high (target has 10 words above m, ours 9). v / __V / r sit 9 / 8 / 8 words high:
      v to __V is 32 bytes in ours and 16 in the target.
  - Tools: /tmp/claude-1000/agent-h/r722/ (g.py, hc.py with MODE=loop, v*.py batches, tr.sh colour order,
    dump.py; final.cpp = the committed body with an absolute include).

- Run 731 (agent-h, commit 01675c0ce on agent-h, NM only, no renames; 3571 / 3579, gate PASS, exact set unchanged).
  - **0xC90 NM 94.04 -> 94.08 %**, 592 words, frame 400. The prologue's 0x06 packet now goes through a
    function-scope `Gfx *g` declared after c (`g = c->next(); g->words.w0 = ..; g->words.w1 = d;`). That is the
    target's 10th word above m: m, halfW / halfH, i, p and scratch now sit at the target's offsets. sp-offset
    mismatches 32 -> 10, positional diffs 243 -> 221. The declaration's position above m makes no difference.
  - **The clamp words (EDG word dump, `fl.py`).** With imax0, the imax0 return value reuses J-128, which is next()'s
    old-count word. The w1 MAX `?:` temp reuses it too. That is why count is one 7-8 block LR (pri ~25). It loses
    v0 to the pri-30 one-block packet `_g` LRs and lands in a2. The target's prologue count is v1 and its loop /
    tail count is v0, so the prologue is a separate LR in the target.
  - **The w1 order is set by the front end's lowering order, not the OR order.** A MAX `?:` is lowered in place, left to
    right. imax0 calls are lowered in reverse written order, and after any `?:` in the same expression. So iM always
    puts yl first, ii1 (yl | xl written) and MM0 (xl | yl) put xl first. Every xl-first variant breaks other things:
    - ii1: 590 words, homes move;
    - MM0 / standard all-MAX (S00): 590 words; the yl / xl s16 CSEs are computed early.
  - **One-statement texrect** (`_g = pkt, w0 = .., w1 = ..;`, all-MAX): all four clamp temps take fresh words
    (J-212..224). w1 is then xl-first with full arms like the target, and the w0 xh preset is hoisted, at 592 words.
    But count is still a2, and objdiff is 92.86.
  - **The best loop-layout climb score (148 -> 129) is at 93.11**: w0 + w1 in one statement, MAX(0, x) on w1. Its
    w1 branch sense is inverted (bgez vs the target's blez), so it was not committed.
  - An exhaustive grid found nothing above 94.04: 7500 builds over per-clamp forms
    {MAX(x,0), imax0, if-imax0, named-r imax0, `<= 0 ?`} x term order x 3 statement forms. Neither did objdiff climbs over
    next / nextN / nextB / nextI / nextP per packet.
  - **Frame, v / __V / r still 8-9 words high.** An `int pad[8]` before v (loop scope) plus the function-scope g on
    the tail and EE / FB packets (-8 words at the bottom) puts r and __V exactly on the target, with v 1 word high,
    at frame 400. But the register picture changes (loop diffs 148 -> 176), and the pad is not real. The target has
    8 real words in the loop scope before v, and fewer `_g` words at the bottom.
  - Next: find those 8 loop-scope words (candidates: the target's y0 / z / per-packet pointers declared at the top of the
    loop body), then the count LR (prologue separate; loop count above the packet `_g` priority).
  - Tools: /tmp/claude-1000/agent-h/r731/:
    - g2.py / g3.py: knob builders (clamp letters, sites, next spellings, statement form `mf`);
    - hc2.py / hc3.py: climbs;
    - en.py: the grid;
    - fl.py / ud.sh: agent-a's EDG word dump, ported;
    - spd.py: sp-offset mismatch census;
    - al.py: opcode alignment;
    - show.py: side by side.

- Run 737 (agent-h, commit 45619b2b2 on agent-h, NM only, no renames; 3571 / 3579, gate PASS, exact set identical).
  - **0xC90 NM 94.08 -> 94.41 %**, 592 words, frame 400. **The whole frame map now matches the target**: v / __V / r
    at sp+220 / 204 / 192 (were 256 / 236 / 224), sp-offset mismatches 7 -> 1.
    - **Loop-scope words:** `int y0, z; Gfx *ge, *gf, *gt, *g1, *g2; int x1, y1;` declared before `SnowV3c v`,
      with `float w` after v. The packets go through the named pointers: `gW(g, w0, w1)`, and a `gTR(g0, pkt, g1,
      pkt2, g2, pkt3, ..)` texrect whose RDPHALF packets use `gImmpV(g, pkt, ..)`. None of them declares a `_g` block
      word. x1 = x0 + wid and y1 = y0 + hgt are assigned after the FB packet.
    - With the loop words in place, w below v gives the target's 16-byte v-to-__V distance. The extra word
      between w and __V in the old layout goes away. With w above v, v is 1 word low.
    - The frame bottom must lose 2 words to stay at 400: the BB and the last BA tail packets reuse the function-scope
      `g` (`g = c->next(); gW(g, ..)`). A climb over all 15 tail pairs picked (1, 5).
    - Code is unchanged by the declarations themselves (94.08 with pointer variables and the old frame). The gain is
      the frame offsets plus nextN() on the E4 packet (94.12 -> 94.41).
  - **EDG word facts (NCC 7.1, `fl.py`):**
    - An inline with a named local declared *without* an initialiser (`int n; return &dl->buf[n = dl->count++];`)
      gets a fresh word per expansion, so each packet gets its own count LR. Frame +8 per use. nextN's
      initialised `int n = ..` reuses one pooled word.
    - Code-free `dumN(x..)` dummies (agent-g's mp72 trick, `a0 = a0;` bodies) do **not** lock words under NCC 7.1:
      the parameter words are freed after the statement. In 34 of 40 sites x arities nothing changed.
    - A fresh count word on the EE packet (+1 tail g to keep the frame) is 94.38: its count then takes v1 and dl v0.
  - **Why the count is still a2 (uopt trace, `tr.sh`):** the count (M-128) is pri 21.4 (171 / 8 blocks). Five pri-30
    one-block LRs (FB pointer, nextN's shared n for E4 / B3, g2, two CSEs) interfere with it and take v0 / v1 / a0 /
    a1 first. The target's EE packet is a1, so it is coloured after the camera CSE (a0, pri 21): its LR spans more
    than one block. `if (y0) {}` between `ge = c->next()` and the fill drops the EE pointer below 21, but costs
    objdiff (94.17), and count stays a2.
  - **Prologue self->tex:** the target has `lw a1,44(a0)`. `gl_func_00000000(self->tex->dl, self->tex)` gives a1,
    but then the t-ring starts at t6 instead of t7 (93.41). The target consumes one ugen t-register before c's lui
    with no code.
  - Next:
    - shorten the count LR to 5 blocks or fewer. Candidate: per-packet fresh-word counts at the right packets,
      with the frame kept by the tail g set;
    - the FB colour order (target: col[0], col[1], alpha, col[2]);
    - yl's late s16 (target keeps y0 << 2 unsigned in t5 until w1).
  - Tools: /tmp/claude-1000/agent-h/r737/:
    - r.py: runner printing (objdiff, words, frame, positional diffs, sp mismatches, loop layout diffs, sp addiu
      offsets);
    - g4.py: knob builder (clamp letters, term orders, x1 / y1 placement, `if` sites, per-packet next form incl.
      fresh nextF / nextG, tail g set, dummies);
    - hc4.py: climb under the 592-word / frame-400 / offsets constraint;
    - v*.py: the batches.

- Run 740 (agent-h, commits 9a01c60ca, 5327270cb, a56f8f4cf on agent-h, NM only, no renames; 3571 / 3579, gate PASS
  each, exact set identical, 592 words, frame 400).
  - **0xC90 NM 94.41 -> 96.17 -> 96.23 -> 96.73 %**. Loop-layout diffs 87 -> 16, sp-offset mismatches 1 -> 0.
    - **FB colour = the stock gDPSetEnvColor body.** `_SHIFTL(col[0], 24, 8) | _SHIFTL(col[1], 16, 8) |
      _SHIFTL(col[2], 8, 8) | _SHIFTL((int)alpha, 0, 8)` gives the target's load order col[0], col[1], alpha,
      col[2] (94.41 -> 96.17). None of the 24 plain-int term orders does; the u32 casts are what matter.
      `(unsigned char)alpha` costs 30 words; `(s16)` / `(unsigned int)(int)` are identical to `(int)`.
    - **Texrect E4 = the stock clamp form, as one comma statement** with the E4 assignment
      (`g0 = pkt, g0->w0 = .. MAX((s16)xh,0) | MAX((s16)yh,0), g0->w1 = .. MAX((s16)xl,0) | MAX(0,(s16)yl);`).
      In the comma statement the clamp temps take fresh edg words instead of next()'s pooled count word, so the count
      LR loses the clamp blocks. Plain stock MAX in separate statements is 590 words (no ra save, y0 << 2 not
      hoisted). The climb then picked EE nextBI(), FB nextN(), E4 nextI(), B4 / B3 nextN(), one `if (y0) {}`
      (before FB), tail g on E7 / BB / BA1301 / B9 / BA0602 (96.73).
  - **Count LR facts (uopt trace, `trp.py`):**
    - The count word (M-128) was forbidden v0 / a0 / a1 because its LR included block 1 (the prologue, with the
      calls): the prologue packet used the same pooled word. Separating the prologue (nextN) makes v0 legal.
    - The RDPHALF_1 `s` ternary result also reuses the count word and lives across the `t` ternaries (blocks
      42..53). gImmpV written as a comma statement gives it a fresh word: count den 8 -> 3..5, pri 21 -> 35..56.
      With both, count takes v0 (a2 before), but the variants are 590-591 words.
    - `ne = c->dl->count++` in a named loop word changes nothing (the ++ temp is the LR; ne is copy-propagated).
      `ne = c->dl->count; c->dl->count = ne + 1;` makes ne the LR, but it takes v1, with dl in v0.
  - Left (opcode alignment vs the target):
    - the two clamp presets (`or a1 / a3, zero, zero`) come after the FB count, not before it;
    - y0 + hgt is computed one slot early (a0 vs the target's v0 after the E4 count);
    - the yl clamp branch is bgez (MAX(0, x)) vs the target's blez;
    - one `or a3,a0,zero` in the RDPHALF_1 `s` arm is a nop in ours;
    - registers: loop count v1 / dl v0 (target v0 / v1), c in t4 (target t2).
  - Tools: /tmp/claude-1000/agent-h/r740/:
    - g5.py: g4 plus `imc` (gImmpV comma forms), `e4c` (texrect comma statement), `fbs` (FB form);
    - hc6.py: climb with the count register (v0) as a secondary key; hc7.py: objdiff climb over nb.neigh2 (next-form /
      pn / imc / e4c moves combined with a tail-g toggle, so frame-changing moves stay at 400);
    - trp.py: parallel-safe uopt trace (pri / den / colour / forbidden per LR);
    - v*.py: the batches (v5 FB forms, v9 / v10 named count words, v11 clamp grid).

- Run 746 (agent-h, commit a2d8724e9 on agent-h, NM only, no renames; 3574 / 3579, gate PASS, exact set identical,
  592 words, frame 400).
  - **0xC90 NM 96.73 -> 96.83 %**: a code-free `if (p) {}` after the texrect. That late use raises p's uopt priority
    (7.4 -> 8.07, 15 blocks) above y0 and the E4 pointer, so p takes t1 as in the target. A sweep of `if (v) {}` over
    every loop-body / tail line and 20 variables found nothing further. `if (y0) {}` / `if (x0) {}` after the texrect
    give 594 words.
  - Left: c is t4 (target t2) and y0 t2 (target t3). c's priority dropped to 6.76 (17 blocks), so it is still below
    y0 (8.0) and gt (7.5).
  - **Count -> v0 (plan item 2):** B4 written as a comma statement (`g1 = pkt, w0 = .., w1 = ..`; only B4 matters, B3
    makes no difference) plus a separate prologue word (nextN / nextI) puts the count in v0 at 6 sites. A climb then
    restores 592 words (FB / B4 / B3 nextI, yl `MAX(x, 0)`, blez sense right). The best result is 96.71 at frame 408..424.
    The prologue nextN `n` sits between m and v (m +8, frame +8). No single function-scope edit compensates:
    removing scratch, d, inv or g, or moving g, does not work. Even off-frame, these states score below 96.73.
  - **Stock tail packets:** six `gDPWord(c->nextN(), ..)` tail packets plus a `gDPWord` prologue give the target's
    tail pointer rotation (v0 / a0 / a1 / v0 / a0 / v0, i.e. the target's a0 / a1 / a2 / a0 / a1 / a3 shifted by the
    count) and the prologue pointer a3, at 592 words. But they cost 12 frame words: the six `_g` words plus the six
    nextN `n` words all land below r.
  - No constrained climb, all-pairs scan (1357 pairs) or random 2-4-move search (about 900 states at 592 / 400 /
    offsets) beats the committed body.
  - Tools: /tmp/claude-1000/agent-h/r746/:
    - g6.py: knob builder over the committed body (per-packet named pointer vs `_g` block, prologue / tail form, imc
      per packet, decl removals; G6B env picks the base file);
    - hc8.py / hc9.py: climbs (ok / free / v0 / soft keys);
    - pairs.py, rnd.py, sub.py: pair, random and subset scans;
    - ds.py: dummy-`if` site sweep;
    - al.py: register-normalised alignment;
    - sbs.py: side by side.

- Run 750 (agent-h, commit 5a9160b4b on agent-h, NM only, no renames; 3574 / 3579, gate PASS, exact set identical,
  592 words, frame 400).
  - **0xC90 NM 96.83 -> 97.09 %**: two code-free `if (c) {}` lines right after the EE packet, plus B4 appending through
    nextBI(). c's priority goes 6.76 -> 7.5 (135 / 18), above y0, so **c takes t2 as in the target**.
    - Use weights differ by nesting: one `if (c) {}` inside the inner `if` adds about 10 to num, one at the top of the loop
      body about 2.4. Several ifs on one source line change the code (576 words), so put each on its own line.
    - The two ifs sit inside y0's span, so y0 drops to 40 / 6 = 6.67 and now loses t3 to the E4 pointer gt (30 / 4 = 7.5).
      The target needs p > c > y0 > gt. c and gt tie at 7.5, and c wins on the lower LR index. A block inside gt's span is
      always inside y0's span too (y0 is used in w1), so y0 cannot be pushed between them this way. Pair scans over
      {c, y0, gt, p, x0, `1`} x every loop site (17k builds), 3000 random triples over 17 variables, and a colour-objective
      beam all stayed at 97.09. A `if (gt) {}` after the texrect sends gt to ra.
    - Per-packet next-form grid (4^5): EE nextBI / FB nextN / E4 nextI / B4 nextBI / B3 nextN is best. **E4 must stay
      nextI.** With nextN, the w0 clamp temps get fresh words (J-240 / J-244) instead of the count / dl words (J-132 /
      J-228). That is right in principle: the target's xh / yh clamp results are a3 / a1 with the presets hoisted before
      the FB count, while ours are v1 / v0 because they share the count / dl LRs. But it loses the s0 save and 2 words
      (590).
  - **Coordinator's levers (agent-e 64B8):**
    - Callee return types: the view-matrix call typed `void` through a `gl_func_00000000_snowh_view` alias, and the dl
      call typed as returning a pointer, give identical bytes. A `((void (*)(...))..)` cast gives jalr. This NCC has no
      namespaces.
    - The single-`return` inline rule: none of the C90 inlines takes a plain-variable argument that needs a word.
  - **Tail count (plan items 1 and 3):**
    - Any change to the tail's words alone takes the function to 590 words. Changes tried: an existing variable as the
      count (`d = c->dl->count; c->dl->count = d + 1;`), and `me()` hops.
      Reason: the tail count shares word -128 with the texrect's MAX temps (M-128, a3). Losing the tail blocks drops
      M-128 to 6.6, and the texrect recolours.
    - `c->me()->me()->next()` on all six tail packets, plus `c->me()->next()` in the prologue, with scratch[] removed:
      592 words, frame 400, offsets exact, loop-layout diffs 15, but 96.93. The tail count then shares the loop count's
      word (J-132; the target also has one v0 count for loop and tail). That word is forbidden v0 / a0 / a1 because the
      prologue's next() uses word -132 for `this`, which pulls the prologue's call block into the LR. Next step: a
      prologue form that keeps -132 out of the prologue. Then the shared count can take v0 (the target's loop / tail
      count) and dl v1.
    - Prologue written directly, with no inline (`g = &c->dl->buf[c->dl->count++];`, a `{ int n = ..; }` block, or
      `buf + count++`): the bytes are identical to next(). With depth-2 tail hops, these give 590 words again. In the
      96.93 state, the prologue's me() hop is what keeps the texrect's M-128 LR alive.
  - Tools: /tmp/claude-1000/agent-h/r750/:
    - cr.py: colour / pri / den of the key LRs;
    - sw.py, pr.py, rs.py, bm.py: site / pair / random / beam scans of `if (v) {}`;
    - one.py: a single variable at every site, with colours;
    - nx.py: per-packet next-form grid;
    - me.py / me2.py / me3.py: me()-depth grids, prologue form x tail depth x scratch;
    - v5.py / v6.py: callee-type probes.

- Run 754 (agent-h, commits 28fd034c1 and a925b44ca on agent-h, NM only, no renames; 3576 / 3579, gate PASS each,
  exact set identical (lost: none), 592 words, frame 400, offsets unchanged).
  - **0xC90 NM 97.09 -> 97.37 -> 98.01 %** with agent-a's constant-dummy lever: `Gfx *nextN_1(int d0) { d0 = d0;
    int n = dl->count++; .. }`, called `c->nextN_1(0)`. Each dummy takes the next pooled edg word, so the count /
    dl temps that follow move to later words. In a member inline the order is this, the dummies, the count temp,
    then the dl temp. Frame-neutral in the loop and tail (the free words below r absorb them). In the prologue
    every extra word shifts v / __V / r down, because nothing has been freed yet there.
  - **Word map (fl.py):** the three temp words between p and y0 (-124 / -128 / -132) are exactly the
    pre-loop words. `c->next()` alone uses only two (count -124, this -128; the dl is an expression, not a word).
    `c->me()->next()` uses three (this -124, dl -132, count -128), and -128 is also the loop count's word, which
    pulls the prologue's call block into the loop count LR (forbidden v0). **Fix: plain `c->next()` plus a code-free
    `dum3(0, 0, 0)` (or `dum1(0)`, same bytes) after it.** The dummy fills the third word, so the frame stays the same and the loop
    count's word is no longer live in the prologue. The loop count (M-132) then has no forbidden registers and takes v0.
  - Loop appends: EE `c->me()->nextI_3(0, 0, 0)`, FB `nextBI_1(0)`, E4 `nextI()`, B4 `c->me()->nextBI_1(0)`,
    B3 `nextN_1(0)`. Tail: six `c->me_1(0)->me()->me()->next()`. What matters is the number of words ahead of
    next's temps (4), not the hop shape: `c->me()->me()->next()` gives the same score here. Tail dl / count are
    v1 / v0 and the B4 / B3 counts are v0, all as in the target. scratch[] is gone.
  - Left (129 positional diffs):
    - the ugen t-ring is one register off in the prologue (t6 vs t7; target self->tex in a1);
    - y0 t4 / gt t3 (target t3 / t4);
    - FB clamp presets (`or a1/a3, zero, zero`) come after the count, not before it;
    - the E4 count is a1 (target v0);
    - the xh `(s16)((x0 + wid) << 2)` CSE is in a3 (target a2).
  - **y0 vs gt (plan item 2), not reached.** No set of `if (v) {}` lines gives y0 t3 / gt t4. Tried: `c` / `p` /
    `y0` / `1` at 15 sites (incl. after the inner and outer if closes), all singles and pairs (1830), and 1500
    random triples, filtered on the colours.
    Possible outcomes: y0 lands on t4, t0, s1 / s2 or t5, and t3 only when c is pushed off t2. Next: put gt or y0 on
    a pooled word (inline-parameter form) so its LR merges with another word's and its priority changes.
  - Tools: /tmp/claude-1000/agent-h/r754/:
    - gd.py: dummy inline defs plus `mk()`;
    - hc3.py: climb over per-site (form, dummies, me hops), tail form, prologue form and `if` sites;
    - rnd.py: random 2-3 move scan;
    - ts.py: tail-form sweep;
    - ifs.py / ifc.py / ifd.py: `if`-site scans with a colour filter;
    - apply.py: ports a variant into the tree file;
    - rt.sh: scores the tree file;
    - fw.sh: edg word map of the append lines.

- Run 757 (agent-h, commit 1ebfaafcb on agent-h, NM only, no renames; 3576 / 3579, gate PASS, exact set identical,
  592 words, frame 400, offsets unchanged).
  - **0xC90 NM 98.01 -> 98.05 %** (127 positional diffs): `extern "C" long long gl_func_00000000(...)`.
    - **The t-ring is set after each call, not at function entry.** No change before the first jal moves the
      ring after it. Tried: tex as the second argument (gives the target's `lw a1,44(a0)`, but cam's lui goes to
      t6), tex / c declaration order, a dummy function earlier in the TU, and `if (..) {}` lines.
    - Return-type probes on the first call: int / unsigned / short / char / enum / pointer / reference are all
      identical. long long (any cast) moves the ring by +1 onto the target's (count+1 t6, dl t9, sll t7). Side
      effect: d becomes the low word (v1; the target has v0). A `(long long)` cast of an int return moves it +3.
      float / double add cvt code. A struct return or `>> 32` (a libcall) adds code.
    - The ring after the **second** (view) call is still one register off (from word 41 on). Typing or using
      that call's result changes nothing.
  - **Why y0 / E4 do not move: the s-outer ternary word is the problem.** The RDPHALF_1 `s` outer ternary result
    reuses word -124. The prologue count uses the same word, so they form one LR (M-124, den 5: block 1 plus
    blocks 44..58). That LR is forbidden v0..t2 and takes t3, and gt shares t3 with it. In the target, the s-outer
    result is a3 and the prologue count is v1, so they are separate words there.
    - Prologue `c->me()->next()` (words: me this -124, next this -132, count -128) splits them: M-124 takes a3 as
      in the target. But -132 is then live in the prologue, so the loop count / dl swap to v1 / v0 (97.83).
      Shifting every loop / tail append by one dummy to compensate gives 588-590 words.
    - Free-function appends (`nxt(c)`, `nxtd(0, c)`): x is not substituted, and the prologue takes 4 words (590).
    - A dummy in the RDPHALF_1 w1 full-expression (`(dmK(0..), w1)`, K = 1..7) moves s-outer off -124, and
      M-124 then takes v1 (K = 3 / 4). But the inner ternary temps shift as well: 588-591 words, and s0 is lost.
      A comma-form gImmpV on B4 is 590 words or frame 416.
  - **agent-e's zero-code priority lever** (`zi(y0, 0)`, `z * (lo + .. + lo)`): each `lo` adds 10 / 6 to y0's
    priority, so 1 lo gives 8.33. y0 then takes t0, because it is coloured before p / c and the s-outer LR. Adding
    `if (c) {}` / `if (p) {}` lines (up to 3 each) gives t3 / t4 orders, but no state beats the base. Pointer
    versions (`(int)c`) add code. A gt lever across the ternaries extends gt to 11 blocks (594 words).
  - Next: a prologue form whose count avoids -124 **without** putting a real LR on -132 (the s-outer word must
    hold no prologue value), plus the second call's ring.
  - Tools: /tmp/claude-1000/agent-h/r757/:
    - rc.py: score plus colours (M-124 / 128 / 132 / 224 / y0 / gt / c);
    - pd.py: prologue diff count;
    - g7.py / hc.py: knob builder and climb (G7B env picks the base);
    - v*.py: the batches (v12-v15, v22 callee types; v16-v19 zi levers; v20 / v21 prologue forms;
      v6 w1 dummies).

- Run 762 (agent-h, commits c57226a6e, 76af8a2e5 and 7cb0f02e1 on agent-h, NM only, no renames; 3576 / 3579, gate PASS
  each, exact set identical (lost: none), 592 words, frame 400, offsets unchanged).
  - **0xC90 NM 98.05 -> 98.60** (127 -> 73 positional diffs). There are two edits, and the long long callee type is
    gone (int again, d in v0 as in the target):
    - **The EE w1 is the stock gDPSetPrimDepth body**, `_SHIFTL(z & 0x7FFF, 16, 16) | _SHIFTL(0, 0, 16)`. ugen gives
      the redundant `& 0xFFFF` a t-register ring temp, and as1 deletes it, so it is a hidden pop.
    - **The texture's dl call passes self->tex as a second argument.** The target loads tex into a1 before the jal
      (`lw a1,44(a0)`), so tex takes no ring temp.
  - **Key finding: the ugen t-ring is decided backward.** A block's t6..t9 choices depend on the ring temps that come
    **after** it in the function, not before. Evidence:
    - The long long move in the prologue shifted the cam load before it, but not the post-call block after it.
    - Adding one tail packet shifted the prologue, both post-call blocks and the loop head.
    - The hidden pop at the EE packet shifted every block before it (prologue to EE) by one, and nothing after.
    - Code before the first jal never moved the ring after it (run 757). That is consistent with this.
    - So for a ring offset over a prefix of the function, look for a hidden pop right where the offset ends.
      Here the offset ran from the prologue to the EE packet. Run 757's long long only "fixed" the prologue
      because its move sits after the cam load.
    - The ring is t6..t9 only (t0..t5 are all uopt-coloured somewhere). A double shift (`<< 8 << 8`, `<< 15 << 1`)
      or a redundant mask gives the same bytes as the stock macro. 3-4 extra shifts rotate the ring further.
  - **98.60 -> 98.62:** the E7 / BB tail packets go through gDPWord's `_g` (a0 / a1 as in the target) and the other
    four reuse g. The two `_g` words fill the two free words below r. A third `_g` makes the frame 408+. In the 64-way
    g / gDPWord grid, frame-400 states peak at 70 diffs.
  - **98.62 -> 98.78:** agent-e's run 760 z0 recipe (below; agent-e found it, agent-h applied it), with the c term
    in the BB tail packet's w1. On this tail form the c term scores 98.78 on any packet from BB on, and 98.76 on
    E7. With the c term in, tail packets 3 / 5 / 6 are back on a3, and no g / gDPWord form gets below 62 diffs.
  - **Prologue count (plan item 1), not reached.** Pre-dummies (dumK before next()) and dum1 / dum2 after it do
    not change the word map, and dum3 after next() stays needed. Neither do next_1 / nextN / nextI / nextN_1 /
    me() forms or named-variable counts (`i = c->dl->count++`, etc.). Words: each dumK statement reuses the same
    pooled words, and only the third word matters. Named `x = count; count = x + 1` forms give 590 words.
  - Left (62 diffs):
    - the prologue count (t3; the target has v1);
    - the xh CSE (a3; the target has a2);
    - the f10 load offset at 270;
    - z (a2; the target has a3);
    - the FB clamp presets come after the count;
    - the E4 count (a1; the target has v0) and the texrect clamp registers that follow;
    - tail packets 3 / 5 / 6 (the target has a2 / a1 / a3; ours are a3).
  - Tools: /tmp/claude-1000/agent-h/r762/:
    - g7.py, r.py, rc.py and trp.py are copies of the r757 tools, retargeted to r762;
    - v1-v3 and v7 are second-call ring probes;
    - v8 / v9 show the backward ring: `tail2` is the probe that revealed it;
    - v11 / v12 are the EE hidden-pop variants;
    - v4 / v5 / v13 are the prologue-form grids;
    - v14 / v17 are the tail g / gDPWord grids;
    - v15 / v16 apply agent-e's levers.

- Run 765 (agent-h, commit 1bf647294 on agent-h, NM only, no renames; 3576 / 3579, gate PASS, exact set identical,
  592 words, frame 400, sp offsets exact).
  - **0xC90 NM 98.78 -> 98.90** (62 -> 54 positional diffs): the xh / z swap (plan item 4) is fixed.
    - **Diagnosis.** The target has xh `(s16)((x1) << 2)` in a2, the xh / xl clamp results (M-128) in a3, and z in a3.
      Ours had M-128 coloured first (15.75) to a2, which left a3 for the xh CSE e802 (15.0) and the xl CSE e1014.
      The xh compute at word 243 is placed by as1, which hoists it above z. It can do that only when xh and z
      use different registers.
    - Raising e802 alone (any z0 use of xh: in the arm, in y1, or `if (y0 + z0(0) * xh) {}`) gives xh a2 and
      M-128 a3. But z, a named local on its own word, then takes a2 as well. as1 can no longer hoist xh, so it
      lands after the EE packet and the a3 preset hoists to word 210 instead (97.70, 127 diffs; every
      e802-raising edit gives this same state).
      z0 terms in the EE word / z expression / FB do not change e802 (the product folds before the CSE use is counted).
    - **Fix: the depth goes on M-128's word.**
      - `inline void primDepth(GCtx *c, int z) { Gfx *g = c->next(); gW(g, 0xEE000000, ..z..); }`, called as
        `primDepth(c, (int)(..depth..))`. The depth parameter reuses the pooled word -128, so z and the clamp temps
        form one LR, as in the target (M-128 goes 15.75 -> 20.75).
      - xh then needs **two** extra uses to outrank it:
        `(s16)(xh) > 0 ? (s16)(xh) + z0(0) * ((int)(s16)(xh) + (int)(s16)(xh)) : 0` gives 50 / 2 = 25. One use
        (20) is not enough.
      - Result: xh a2, depth / clamp a3, and as1 hoists xh to 243 as in the target.
      - Inline-parameter words do not copy-propagate the way named locals do. Moving x1 / y1, or putting xh in a
        named `s16` / `int` local before z, changes nothing (the CSE is placed at its use). Any `if` before EE
        costs 6-18 words.
    - **Frame.**
      - The old z / ge loop words are gone, so `int y0, pad0, pad1;` plus `pad0 = 0; pad1 = 0;` at the top of the
        loop restore v / __V / r at 220 / 204 / 192.
      - Inside primDepth only plain `next()` keeps frame 400. nextI / nextI_k / me()->nextI_3 / nextN / nextBI add
        2 pool words below r (frame 408 with the pads). Without the pads, frame 400 but every offset +8.
    - Alternative not committed: `me()->nextI_3(0, 0, 0)` inside primDepth with no pads (o/v16_m0_p2.cpp) scores
      objdiff **98.912**, above the committed 98.902. Its EE pointer is a1 as in the target (committed: v1), but it
      has 60 diffs, including 6 sp-offset ones (v / __V / r +8). Taking it needs 2 pool words below r moved to above
      v. No member / free / arg-order form tried (v16) does that.
  - Left (54):
    - the prologue (dl a3 / count t3 / g a2; the target has a2 / v1 / a3). M-128's prologue part is now a3.
    - the EE pointer (v1; the target has a1). The M-224 g lives in one block, forbidden only v0.
    - the FB / yh preset:
      - The yh clamp result (e1255, fb {a0}) takes v0, so its `or v0,zero,zero` stays after the FB count.
      - In the target it is a1, the preset hoists above the count (word 287), and the E4 count is then free to
        take v0.
      - This is plan item 1's root cause. y1 placement is irrelevant: it is copy-propagated, and all five
        placements give identical bytes.
    - the xl clamp result (v1; the target has a3);
    - the B4 pointer t4 / s-outer t3 (the target has t3 / a3);
    - tail packets 3 / 5 / 6;
    - f10 at word 270.
  - Tools: /tmp/claude-1000/agent-h/r765/:
    - v.py: score plus colours;
    - gd.py: dummy append defs;
    - v1 / v2 / v4 / v5: xh use probes;
    - v6 / v7: x1 / xh-local placement;
    - v8: `if` sites;
    - v9 / v10: depth-inline forms;
    - v11: xh use counts on the L form;
    - v12 / v14 / v15 / v16: frame and pad grids;
    - v17: y1 placement;
    - mkc.py: builds the committed body;
    - k/: the uopt trace of the committed state.

- Run 768 (agent-h, commit 24c6020db on agent-h, NM only, no renames; 3576 / 3579, gate PASS, exact set identical,
  592 words, frame 400, sp offsets exact).
  - **0xC90: 54 -> 53 positional diffs (objdiff stays 98.90, since it is reloc-aware).** Item 5 is fixed: the depth
    scale is RoData+0x4, read as `snow_rodata_C90.depthScale` through a 0-based RoData alias (new
    undefined_syms_auto.txt line). The lo16 then carries the +4, giving the target's `lwc1 f10,4(at)`. The old
    `snow_ro_4` (a symbol at +4) gave lo16 0.
  - **Corrected LR map, base 24c6020db.** lm.py prints each LR with its live blocks. In the uopt flow graph:
    - block 13 runs from the inner if to EE;
    - blocks 15-19 are the three `if (..) {}` lines;
    - 20 / 21 are FB, split by nextBI's `if (1)`; 21 also holds drawn++, the E4 count and the E4 pointer;
    - the clamp arms are 22/23 (xh), 25/26 (yh), 28/29 (xl) and 31/32 (yl);
    - 33-45 are the s ternaries (B4) and 46-58 are t / B3.
    - The words:
      - M-128 (a3): prologue, depth, xh clamp, s-middle.
      - **M-132 (v0): EE / FB / B4 / B3 counts *and* the yh clamp** (25/26/27), plus the s-inner MAX.
      - M-228 (v1): the dl temps, plus the **xl clamp** and the s-inner MIN.
      - M-240 (a1): the yl clamp plus t-outer.
      - M-236 (a1): the E4 count, block 21 only.
      - M-124 (t3): the prologue plus s-outer.
    - Run 765's "e1255 = yh clamp" was wrong. e1255 is the (s16)dsdx CSE (blocks 35/36/40, v0 in both builds).
  - **What the target's colours say about its word sharing:**
    - xh, xl, s-outer and depth are all a3, so they are probably one word.
    - yh, yl and s-middle are all a1, so they are probably one word.
    - The counts (FB / E4 / B4) are v0.
    - The yh preset can't hoist because the yh clamp sits on the count word (v0, busy until the FB `sll`). The E4
      count can't take v0 because M-132 is live in block 21 (the FB count's use).
  - **The separate-statement gTR (the stock gSPScisTextureRectangle shape) gives that sharing.** Use `g0 = (pkt);`,
    `w0 = ..;` and `w1 = ..;` as three statements (S1 = o/a3_sb_sw.cpp), and swap primDepth's parameters to
    `primDepth(int z, GCtx *c)` so the depth takes the first pooled word. Result:
    - M-124 a3 = {prologue, depth, xh, xl, s-outer}, as in the target;
    - M-128 = {prologue dl, yh, yl, s-middle};
    - prologue dl a2, as in the target.
    - It scores only 98.67 (107 diffs), and `c->me()->next()` in the prologue gives 98.69 (103). Two things are
      still wrong:
      1. M-128 takes a2, not a1. The prologue's call argument a1 (tex) is live in block 1, so M-128 is forbidden a1.
         In the target, the yh word must therefore not be a prologue word.
      2. M-132 (counts, 37.5) now ranks below M-228 (dl temps, den 3, 50.0), so count / dl come out v1 / v0, the
         reverse of the target.
    - An `if (1 + zq(0) * n)` fold in nextBI adds a uopt block (140 diffs), and the n terms count only once.
  - **Dead ends on the base:**
    - An `if (..) {}` between FB and E4 (to give the E4 count its own block) gives 591 words.
    - E4 forms: nextN / next / nextN_1 / nextBI give 590-591 words; nextI_2 / nextI_3 give 592 but the count goes
      to a0.
    - A semicolon only before w1 or only before w0 scores 97.0-98.5.
  - Next:
    - On S1, take the prologue off the yh word, i.e. a prologue form whose words are not reused by the w0 yh
      temp.
    - Then raise M-132 above M-228 with a fold that adds no block.
  - Tools: /tmp/claude-1000/agent-h/r768/:
    - lm.py SRC [blocks]: LR map with colours, priorities, live blocks and forbidden sets;
    - lri.py: a raw LR record;
    - fg.py: the flow graph;
    - kr.py: E4-count / yh-clamp registers;
    - vr.py: variant runner;
    - a1-a8.py: the batches;
    - S1.cpp: the separate-statement base.

- Run 772 (agent-h, commit 5e09a40ce on agent-h, NM only, no renames; 3576 / 3579, gate PASS, exact set identical
  (lost: none), 592 words, frame 400, sp offsets exact).
  - **0xC90 NM 98.90 -> 98.99** (53 -> 44 positional diffs), built on run 768's S1 (separate-statement texrect,
    `primDepth(z, c)`). Two levers:
    - **Folds in the buf index, not in an `if`.** `&dl->buf[n + zc(0) * n + zc(0) * (n + n)]` in the B4 / B3 appends
      (nextBIc_1 / nextNc_1; zc is z0 declared before GCtx) adds counted uses of the count with no code and no block.
      Each *distinct* fold is +1 use (`n + n` inside one fold still counts once). Two folds on each of B4 / B3 take
      M-132 (counts) 37.5 -> 52.5, above M-228 (dl temps, 50): counts v0 / dl temps v1 as in the target. A third
      distinct fold (`(n + 1)`, `(n - n)`, `(n * n)`, ...) emits code. Any fold on FB (nextBI_1) splits a block (bad).
    - **Comma dummies move one clamp temp to another pool word.** `(dmK(0, ..), _SHIFTL(MAX(yh), ..))` in the w0
      statement: the dummies take the next pool words (the xh temp keeps -124), so the yh temp lands K words deeper.
      dm1 on yh puts it on -132 (the count word, v0). dm3 on yl puts it on a loop-only pool word (M-240, with
      t-outer), which takes a1 as in the target. M-128 is then just {prologue dl, s-middle}.
  - Not reached (each tried on the committed body):
    - **yh to a1.** dm3 on yh too joins M-240 (30.0, picked before M-160 and given a0). A `z0(0) * (int)(g2)` fold in
      the B3 w1 raises M-160 to 40, and then yh / yl take a1. But the E4 count is then a1, so as1 hoists the xh
      `addu v0,t3,s1` into the FB block and fills a delay slot (591 words, 98.32). The E4 count needs v0, which means
      M-132 must not be live in block 21. No E4 form (22 tried), no FB form (18) and no `if (..) {}` between FB
      and E4 (24) keeps 592.
    - Dummies in the RDPHALF_1 s-middle (for its a1) need new pool words: frame 408+.
    - Prologue forms: named locals (`DList *l`, `int n`), `me_K` / `next_K` hops, and pad / dum3 trades. None keeps
      frame 400 with exact offsets and moves the count off M-124.
    - Tail packets 3-6 (target a2 / a0 / a1 / a3; ours t0): `putK(dummies.., g, w0, w1)` inlines need new pool
      words (frame 408+); put0 loses.
    - EE pointer (v1; the target has a1): `if (..) {}` inside primDepth costs 43 diffs; g folds do nothing.
  - Left (44): prologue count / g (a3 / t0; the target has v1 / a3), the EE pointer, the yh clamp and its preset
    (v0; the target has a1), s-middle (a2; the target has a1), tail packets 3-6.
  - Tools: /tmp/claude-1000/agent-h/r772/: vr.py (runner with the dummy defs and the prologue diff count),
    fo.py (forced-colour compile; forcing cascades here, so it is not useful), p1-p14.py (batches), C1.cpp (the
    committed body, absolute include).

- Run 776 (agent-h, commit c45391bdb on agent-h, NM only, no renames; 3576 / 3579, gate PASS, exact set identical,
  592 words, frame 400, sp offsets exact).
  - **0xC90 NM 98.99 -> 99.10** (44 -> 32 positional diffs). Tail packets 3-6 are fixed (12 diffs).
    - **The target's tail pointers (a0 a1 a2 a0 a1 a3) are six separate block words**, one gDPWord `_g` per packet.
      uopt splits the straight-line tail into blocks 64 / 65 / 66 by size. In the target, pkt3 spans 64-65 (so a0 /
      a1 are taken: a2) and pkt6 spans 65-66 (a3). With six `_g` and the 16-term `z0(0) * (c + ..)` counter on
      the BB packet, the split is one packet early (a0 a1 a0 a1 a2 a0). The same counter on the **last** packet
      moves the split to where the target has it. Uopt's block-size split is a lever: code-free fold terms move it.
    - **Frame budget (named-word rule):** frame = deepest allocated word + 132, rounded up to 8. Named block locals
      (inline locals too, e.g. `int n`) never share words; pooled edg temps (inline parameters, dummies) do. So the
      four new `_g` words were paid for with:
      - FB / B4 / B3 counts passed as inline parameters (`atBr(dl, dl->count++)`, member `atBcm(dl->count++)` /
        `atNcm(..)`). The code is byte-identical, and two named `n` words are gone (they were dead copies with no LR).
      - Loop pads removed, `int y0; dm3(0, 0, 0);`. Prologue `dum3` became `dum5`. Its five pooled words sit between
        p and y0, which is exactly where the pads were, and the loop then reuses them instead of allocating deep words.
    - Tried without success: E4's named `n` as a parameter (`atI(dl->count)`, 589 words, loses s3); primDepth's g as
      a parameter (`putw(c->next(), ..)`, frame 400 but 91 diffs).
  - **Prologue (6 diffs):** `putw(c->nextI(), 0x06000000, d); dum4(..); g = 0;` (g kept for the frame) gets the prologue
    exactly right (pd=0): pointer a3, count v1, dl a2. But the prologue dl then becomes the CSE temp e861, shared with
    block 21, and that disturbs the loop (50 diffs). The prologue dl has to stay a pool word. Next step: a putw form
    whose dl is a pooled word.
  - Left (32): prologue count / g; EE pointer (v1, target a1; the M-224 LR is block 14 only, and the target's
    must also be live in block 13 with the dl temp); the yh preset / FB-E4 block (287-295); the E4 count (a1) and yh
    clamp (v1); s-middle (a2).
  - Tools: /tmp/claude-1000/agent-h/r776/: sbs.py, md.sh (-g3 named frame map), lmall.py (LR map incl. FP),
    t5.py (tail forms), t7.py / t8.py (JSON variant batches), C2repo.cpp (committed body, absolute include).

- Run 779 (agent-h, commit b62bfaf5c on agent-h, NM only, no renames; 3576 / 3579, gate PASS, exact set identical,
  592 words, frame 400, sp offsets exact).
  - **0xC90 NM 99.10 -> 99.18** (32 -> 22 positional diffs). Plan items 1 (prologue) and 5 (s-middle) are fixed.
    - **Prologue:** `l = c->dl; putw(c->atIq(l, l->count), 0x06000000, d);` with
      `Gfx *atIq(DList *l, int n) { l->count = n + 1; return &dl->buf[n]; }` and `DList *l` declared in the old
      function-scope g's slot (so the frame stays 400 with exact offsets; dum5 is gone). The packet pointer is putw's
      first pooled word (M-124, a3), the old count the pooled parameter n (shares the loop dl-temp word, v1), and the dl
      the named l (a2), as in the target. The named l stops the prologue dl from being the c->dl CSE temp (e861) that
      nextI() shared with the E4 append (run 776's 50-diff loop break).
    - **s-middle a1:** `d = tcall1(0, self->tex);` with
      `inline int tcall1(int d0, SnowDLHolder *t) { d0 = d0; return gl_func_00000000(t->dl, t); }`. The texture lands
      on the second pooled word (M-128), which the s-middle temp reuses. M-128 is then live in block 0, where a0 is
      busy (self, then the dl argument) but a1 is not (the texture itself is the a1 argument), so M-128 is forbidden
      a0 and takes a1. Lever: **to give a pooled word a specific register, put an inline parameter on that word in a
      block where the unwanted registers are busy and the wanted one holds the same value.**
      (tcall(self->tex) puts t on M-124: no change. halfW through a `half1(0, v)` inline also gives a1, but v is a
      real LR there (lw a1 instead of t9).)
  - Left (22): EE pointer (277-285, v1; target a1); FB block (287-295: the target presets yh in a1 and xh in a3 at
    the top of FB; ours presets yh in v0 after the FB count); E4 count (target v0, ours a1) and yh temp / clamp
    (target v0 / a1, ours v1 / v0).
  - Tried, not working:
    - E4 count as a pooled parameter (nextP / nextPp (named pad keeps frame 400) / atNcm / atN0 / nextNc_1, x yh
      dummies 0-4): 589-590 words. With frame 400 kept, the FB and E4 counts do become one LR (M-132 21:3/1, as the
      target's v0 / v0 suggests) and xh's CSE e762 takes v0 as in the target, but uopt adds a block after E4 and the
      loop loses a callee-saved register (s3), so the whole loop body shifts.
    - FB with the `if (1)` after the index (atBr2(&dl->buf[dl->count++])): same bytes as atBr. Without the d0
      dummy and no yh dummy (B5_d0): M-128 (a1) = {tex, FB count, yh clamp, s-middle}, so the yh clamp is a1 as in
      the target, but the FB count is then a1 too and the E4 count a0 (99.16).
    - EE pointer: a pooled pointer (primDepthP(depth, c->next()), putw / pad forms) gives 589 / 593 words;
      `&c->dl->buf[c->dl->count++]` written in primDepth is byte-identical. Block 13 ends between the EE count store
      and the pointer (M-124 / M-132 13 -> 14, M-224 block 14 only); z0 terms on z (1-8) do not move that split;
      z0 terms on c / wid / hgt / i recolour other things.
  - Tools: /tmp/claude-1000/agent-h/r779/: pv.py (JSON variant runner: replacement lists or prologue strings),
    both.py (side-by-side range), C3repo.cpp (committed body, absolute include), v1-v21.json (batches), o/ (outputs).

- Run 783 (agent-h, research only, no commits; 0xC90 stays 99.18 / 22 diffs, 592 words, frame 400).
  - **Why the pooled E4 count adds a block: uopt's block-size split.** It is not the inline's structure. Block 21 is
    the straight line from the FB pointer through drawn++, x1 / y1 and the E4 append up to the xh ternary. Every
    pooled-parameter E4 form (atE / atN0 / next / xA / nR, with or without dummies and q pads) adds a few IR ops there.
    That pushes the block over the size limit, and uopt splits it inside E4: M-132 becomes 21:2/1 22:1/0, e762 22/23,
    and the extra block changes the loop's colouring, so s3 is lost (589-590).
    Proof: drop the y1 `+ z0(0) * ((int)p + (int)p + y0)` terms from those variants and the split goes away
    (M-132 21:3/1, one LR for both counts, v0).
    `if (1) {}` anywhere between FB and E4 gives the same 589 / s3 loss, so the target has **no** block boundary
    between the FB and E4 counts, and the two counts must be one LR (M-132).
  - **Budget lever (byte-identical on the committed body):** move the y1 terms out of block 21 into the `if (y0) {}`
    before FB, as `if (y0 + z0(0) * ((int)p + (int)p + y0)) {}`. `if ((int)c + ..) {}` also works. Moving them to
    the B3 / B4 / E4 w1 or to `if (p)` gives 595.
  - **With that budget, `c->atE1(0, c->dl->count)`** gives the E4 count on M-132 (v0), the dl on e861 (v1) and no
    extra block, all as in the target. The member is
    `Gfx *atE1(int d0, int n) { d0 = d0; dl->count = n + 1; return &dl->buf[n]; }`.
    The named n is gone, so the frame needs a named pad: `int q = 0;` in primDepth (or B4 / B3 / after `if (p)`)
    gives frame 400.
    The result is still 591 words (349 diffs). The old named E4 count (M-228) was what held a1 in block 21. Without
    it, the xh CSE e762 (pri 25) takes a1 instead of a2, and as1 then hoists xl into a2 early (one word lost).
  - **What is missing:** an LR coloured a1 that is live in block 21 / 22 and outranks e762. In the target that is yh:
    its preset `or a1,zero,zero` sits at the FB top only because a1 is free there; ours is v0, busy with the FB count.
    With no yh dummy (K0), yh lands on M-128 (tex / yh / s-middle, a1) at pri 21. But M-128 is not live in block 21,
    so e762 still takes a1. Next step: a form that makes M-128 (or yh's word) live through block 21 and raises it
    above 25 with no IR in block 21.
  - Dead ends:
    - `dmK(..)` as a statement, or `+ dmK(..)` in an expression: edg folds it completely (no effect).
    - `(dmJ(..), z0(0)) * v` steering in block 21: J has no effect.
    - `z0(0) * ((int)m ..)`: 595 / frame 408.
    - EE pointer as a parameter (primDepthP(depth, c->next() / nextN / me()->next)): 88-89 %.
    - Random climbs over E4 form x yh dummy x if-line counts x z0 sites x tail c-terms (8000 evaluations) stay at 22.
  - Tools: /tmp/claude-1000/agent-h/r783/:
    - pvb.py: JSON runner, which can start from a previous output via `@@BASE@@`;
    - srch.py / srch2.py + run_s*.py: random climb;
    - C5.cpp: base with the y1 terms moved and the atE* / pad defs;
    - lm: use ../r776/lmall.py.

### snoweffects.uso 0xC90 y0 t3 / E4 pointer t4 (agent-e run 760, research only, no commits)

- **Fixed, code-free: objdiff 98.598 -> 98.758 on agent-h's run-762 head (c57226a6e).** Positional diffs go from 73
  to 65, at 592 words, frame 400, sp offsets unchanged (0 mismatches). On the origin/main body (98.01) the same three
  edits give 98.007 -> 98.167. The proposed file is /tmp/claude-1000/agent-e/w760/snoweffects_uso_ncc_nm_h_e760.cpp,
  and e760.diff is its diff against c57226a6e.
- **Colours after the change:** yl (s16)(y0 << 2) t0, p t1, c t2, y0 t3, gt t4, the same as the target's
  `mfc1 t3` / `sll t5,t3,2` / `addu t4,..` / `sw ..,0(t4)` / `sw ..,4(t4)`.
- **Why `if (v) {}` could not do it:** y0 is 40 / 6 = 6.67, and the target order needs p > c > y0 >= gt (gt 7.5;
  y0 wins ties because its LR index is lower). Every in-loop use weighs 10, so den 6 only gives 6.67 or 8.33. At 8.33,
  y0 ties yl (e1096, 50 / 6) and wins it, so it takes t0. Duplicate `if (y0) {}` lines add neither uses nor blocks.
- **The recipe:** all three edits are needed; dropping any one of them scores lower than the base.
  1. **yl +1 use, so it stays first:** E4 w1 written as `((s16)(yl) > 0 ? (s16)(yl) + z0(0) * (int)(s16)(yl) : 0)`,
     giving 60 / 6 = 10.
     - The `> 0` sense is the target's (`blez t0`; ours was `bgez` from `MAX(0, yl)`).
     - The sense flip on its own (stock `MAX((s16)(yl), 0)`) is also a gain: 98.598 -> 98.716.
  2. **y0 and p, +1 use and +2 uses in the loop:** `y1 = y0 + hgt + z0(0) * ((int)p + (int)p + y0);`, giving y0 8.33
     and p 141 / 16 = 8.81.
  3. **c +16 uses outside the loop, where each use weighs 1:** E7 tail `gW(g, 0xE7000000, z0(0) * ((int)c + .. 16 terms));`,
     giving c 151 / 18 = 8.39 (above y0 8.33, below p). Anything from 16 to 20 terms gives the same bytes.
     - In the prologue (`g->words.w1 = d + ..`) the same terms change the code (591).
- **What adds code (avoid):**
  - Pointer terms alone or with a loop-invariant carrier, e.g. `z0(0) * (int)c`. The 0 product is hoisted out of the
    loop as `or t5,zero,zero`. Include a loop-variant term (y0 / p), or put the terms outside the loop.
  - Raising both c and p with in-loop terms (any carrier or split, and also ^ / | / * mixes) gives 591. An xl
    (s16)(x0 << 2) CSE then appears early, and p gets den 17.
  - Any extra term inside the RDPHALF_1 / _2 ternaries gives 594 words / frame 408 (s4 is saved). The same happens to
    a gt use there.
  - Terms on xh / xl inside the E4 w0 / w1 MAX arms keep 592 but change the layout (97.1).
- **Still open:**
  - B4 pointer: ours t4, target t3. M-124 (the prologue count plus the s-outer word) takes t3 in ours; it is a3 in
    the target (agent-h run 757).
  - The a-register swaps: xh a3 / a2, MAX temp M-128 a2 / a3, E4 count a1 / v0, y1 sum v1 / v0, z a2 / a3. The
    E4-count one is an order problem. Our y1 = y0 + hgt (IR before the E4 count) is live across the count, while the
    target computes it after `sll t7,v0,3`. Computing y1 inside the gTR argument instead gives 97.65.
  - A 200 s random climb of z0 terms at the x0 / y0 / z / x1 / y1 / drawn++ sites found nothing above this state.
- Tools, in /tmp/claude-1000/agent-e/w760/:
  - v.py: variant runner (base from the VB env) printing score plus the colours of yl / p / c / y0 / gt / M-124 / x0;
  - v2.py: the V5 recipe;
  - s1-s17.py: the batches;
  - trp.py / tr.py: uopt pick order with num / den;
  - keep.sh: keeps the uoptlist / x.lr / x.ord;
  - hc.py / hc2.py: z0-term climbs;
  - mkv.py: writes one variant.

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

### snoweffects.uso 0x6000+ (agent-e run 653)

- **0x9884 EXACT** (commit 168ede1fa on agent-e; NCC donor in `snoweffects_uso_ncc_e.cpp`, pins
  `gl_func_00000000_snow_sqrtf` and `snoweffects_uso_func_00009884_rodata` = RoData+0xF0).
  Read the frame with `-O2 -g3` + an mdebug dump (`/tmp/claude-1000/c418/py/mdsym.py`). Ours had
  p at vfp-16 and the `for (unsigned i ..)` counter at -40, and the target needs 3 named words above
  the vertex local. The fix: declare `SnowLV *gp; int i; unsigned j;` up front (the restore loop and
  the vertex loop each get their own function-scope counter), then `SnowLV vf; SnowLV p;` (vf first).
  Bind the reference as `const SnowLV &g = *(gp = (SnowLV *)(D_00000000 + 0x128));`. A plain
  `gp = ..;` assignment const-propagates 0x128 into the loads, and an initialised `gp` declared up
  front does the same.
- **0x7960** (draft 193 / 219, every instruction except frame offsets plus one FP swap). The layout
  levers put the operator* result, the copy and push exactly at the target's vfp -72 / -60 / -44:
  `float ang;` declared before `SnowV n;`; no named |speed| local; d in the outer if-block; a named
  `SnowV push = n * -d;` in the inner block; `operator+=(const SnowV &)`. Left: the xform x/y/z homes
  are 8 bytes high and the frame is 160 vs 176. Two more pool words in the push statement fix the
  homes, but only through a dummy-parameter lever: a `SnowV(a, b, c, k, k2)` ctor called from
  operator* with `s, s` keeps the code identical and puts the homes at -112 / -124, frame 168.
  That leaves 8 bytes below the second xform block, plus the |speed| / zero f12 / f2 swap.
  Did not move it: a nested `scaled()` (+4 words), a named result in operator*, a ctor through
  set(), xform as a member or with pointer params (changes the code), `set()` / ctor assignments
  for the side points.
- **0x9328** (draft 78 / 247): the SnowTarget ctor, written as real C++. edg's `this == 0 ->
  operator new` protocol comes out of the inline ctors by itself. The structure:
  - base: SNode, then vptr +0x28 = Data+0;
  - the Parms member at +0x240 is 0x8C bytes with an 8-byte head `{Data+0xA34, 0}` that has its own
    new(8) fallback (a field, not a vptr: a polymorphic base adds a new(4));
  - five inline Parm ctors over GdlParmBase (= Parms_addParm(this, owner, name by value, flag)):
    float 40 / 10, Colour value / min / max passed by value (only the value is stored), int 0
    (flag 0) and int 3;
  - body: name = Data+0xA58, plus the field defaults.

  Left: the target keeps the Parms `this` in a1 with sp+0xDC spills (only s0 saved), and each
  Parm's name copy has its own word. Frame 224 vs 168.
- Not started (no time this run): 0x64B8, 0x718C, 0x7FE0, 0xA10C, 0x6B28 (whole bodies), 0x8D70.

### snoweffects.uso 0x6000+ (agent-e run 659)

- **0x8D70 EXACT** (commit fe29e6fde on agent-e, 3545 -> 3546; NCC donor in `snoweffects_uso_ncc_e.cpp`,
  pin `gl_func_00000000_snow_52d4`). The run 645 draft had every instruction; only the frame was wrong
  (144 vs 168). From `-O0 -g2` .mdebug, each if-block holds a named `SV push = n * -d;` above the
  operator* result, with `+=` taking a const reference. Two dead scratch stores, each in a block of its
  own, fill the 8- and 12-byte gaps above the two if-blocks: `{ int sc[2]; sc[0] = 0; }` before the
  first if and `{ int sc2[3]; sc2[0] = 0; }` before the second probe. These are agent-c's run 643 lever
  placed by agent-a's run 648 block-order rule.
- **0x7960** (draft 212 / 219, `ncc_drafts/snoweffects_nm_e.cpp`). The same two levers make the frame
  exact (176): one scratch block before the side-point code, one after the second xform. Left: the
  zero / |speed| FP swap. The target has zero in f12 and |speed| in f2; ours is the reverse. The
  instrumented uopt (`/tmp/claude-1000/h414/u/out/NCC ... -Wo,-zdbug:5`, then `h384/t/lre.py` +
  `h414/t/ord.py`) shows the |speed| LR (pri 2.0) picked before the split zero-constant piece (pri 0.33).
  No effect from: fabs as an inline, member or reference; `>=`, `0.0f >` or int 0 spellings; a named
  zero (const-propagated); d reused for |speed|; a member dot. `if (1) {}` splits cost ang its f20 home.
- **0x9328** (draft): `if (&n) {}` in the ParmF ctor body moves the Parms `this` from s1 to a1 with the
  target's sp spills (register- and offset-normalised 213 / 247, up from 188). Still missing: a second
  name word per Parm. The target stores each name twice: a per-Parm word (0xD8 / 0xD4 / 0xA0 / 0x9C /
  0x98), then the pooled 0x84 copy that goes to a2. Tried: a non-POD PName (passes by address); an
  identity inline (gives one shared pool word); an inline GdlParmBase ctor (adds this == 0 checks).
- **0x9E10** (cfe NM 26/30). With head passed twice, `(item + 0x10, head, head)`, the beqz + delay-slot
  copy shape appears, but the registers are reversed (head in a1, copy in a2).
- Not reached (budget): 0x64B8, 0x6B28, 0x718C (whole-body decodes).

### snoweffects.uso 0x6000+ (agent-e run 664)

- No new exacts; gate PASS (3550 / 3579). Commit 515100e41 on agent-e (base f342b7d00, 8 behind origin/main):
  a new NON_MATCHING-only donor `src/snoweffects_uso/snoweffects_uso_ncc_nm_e.cpp` (Makefile `SNOW_NM_E_FUNCS`).
  Pins: `snow_ro_B4`, `snow_ro_50`, `snow_ro_54`, `gl_func_00000000_snow_pool` and `gl_func_00000000_snow_norm`.
- **0x7960 is spliced as an NM (objdiff 99.7 %).** The zero / |speed| swap is still open. These had no effect:
  - agent-g's int-zero lever: `int z = 0` in the compares turns them into int compares, and in blocks it
    costs frame words;
  - a named float zero, set at the declaration or before the dot test;
  - a separate int zero for the `.y = 0` stores or for `d != 0`;
  - a named |speed| (`if (s < 0) s = -s`, or ?: at function / block scope);
  - `>=` / `0.1f >` / `!(x < 0)` spellings.
  In the -zdbug:5 trace, ord.py's `f2` / `f12` labels are swapped against the output. The trace's `f12` is
  e195, the 3-use sin * h value, which is f2 in the binary. So |speed| (pri 2.0) takes the first FP colour
  (f12), and the zero piece (pri 0.33) gets f2. To match the target, the zero has to be coloured first.
- **0x64B8 decoded whole** (effect A spawn update; the structure is in the donor). It reaches 91.6 % but is
  **not spliced**: our body is 406 words against the target's 404, and a longer splice shifts 0xA8D0 (gate
  report FAIL).
  - Edg temp lever: the target's two shared return-copy slots (s3 = sp+244, s2 = sp+188) come from **one
    expression with two by-value operator results**: `n += cam->v318 * k * (f184 + spd);` and
    `SV u = vF0 + vFC * (f3C * 2.0f);`. Named intermediates give a single shared slot.
  - Use `operator*(float)` as `return SV(x * s, ..)`; `SV r; r.set(); return r;` does worse (129 exact
    words against 196).
  - Left:
    - the frame is 336 against 344, and the materialised operand temps are ordered the other way (target
      b above a);
    - the target forwards the lerped `u` into p->pos, where ours reloads u.y / u.z (that accounts for the
      2 extra words);
    - the xform's v.z load is scheduled differently.
- Not reached: 0x6B28 and 0x718C (both siblings of 0x64B8: same pool spawn, SnowPool_alloc / _oldest plus
  sys_randf; reuse this donor's SV / SPart model), 0x9328, 0x9E10.

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

## trnproc.uso / nameent.uso progress (agent-c run 643)

- **trnproc 40 / 40 EXACT; nameent 20 / 21 EXACT + 9BC NM (286 / 290).** Commits on agent-c:
  56c15842e, 50651595a (trnproc), aa6b242d1, 2eff5f3a0, aad000a81 (nameent); 3479 -> 3487.
- **Both modules are C++.** Every remaining function went EXACT only under IDO 7.1 NCC, as
  per-module donors `src/trnproc_uso/trnproc_uso_ncc.cpp` and `src/nameent_uso/nameent_uso_ncc.cpp`
  (REPLACE_FUNC_BODY over empty host placeholders; Makefile TRN_NCC_DONOR / NE_NCC_DONOR):
  trnproc B78, DD4, 13C4, 1778 (was NM), 188C; nameent 2F4 (was NM), 760, E44. The edg tells
  seen here: an `a[n++] = v` index kept in its own register at every store (13C4; cfe
  strength-reduces), the `&` left operand evaluated first (1778), a virtual call with the object
  in v1 and the vtable in v0 (2F4), float divisions `r / 255.0f` that stay at run time because
  they pass through an inline `set()` (DD4, 760: a Colour class with `set255(int..)`).
- **Float literals in a USO donor:** write the real literal (`0.8f`); the splice renames the
  donor's `.rodata` reloc to `<func>_rodata`, pinned in undefined_syms_auto.txt at
  (target RoData offset - donor .rodata offset). Donor .rodata is in file order with no
  cross-function merging (trnproc B78 0x20 / DD4 0x20; nameent 760 0x0 / E44 0xC). Real literals
  are what let uopt hoist the loads out of DD4's loop (f22 / f24); 0-pinned load symbols cannot.
- **USO address with an addend that edg would fold** (B78's second sprite table, Bss+0xF0, indexed
  `[v - 32]`): a separate symbol pinned at the address (`trn_sprites_F0 = 0xF0`) keeps
  `v * 24 - 768` apart from the `addiu 240`. That `* 24` is `multu` by s8 = 24, a hoisted loop
  constant, once the `!= 255` test comes first.
- **Typed 0-pinned aliases of the blank import:** `gl_func_00000000_void` (frees v0 after a void
  callee: 188C, B78, E44), `ne_input_getStickX` (float return), `ne_gui_drawSpriteScroll`
  (float scale arguments; through `...` they would be promoted to double).
- **Frame words:** NCC -O2 keeps a word for every named local that is assigned (even dead), in
  declaration order from the top; unreferenced locals get none. A dead one-element store
  (`scratch[0] = 0;`) is a code-free frame word (13C4, 2F4, E44). Read the layout with `-g3`
  `.mdebug` local symbols (vfp offsets; temporaries do not appear).
- Text end pads: nameent now uses the trnproc mechanism (all-zero SUFFIX on E44 + TRUNCATE_TEXT
  0x1510), since the spliced object is no longer the INCLUDE_ASM layout.
- Open: nameent 9BC (display), NM 286 / 290 through an NM-only splice. Every instruction
  matches except the two scale spill slots, 4 bytes high: the target has one more named word above
  them and one fewer edg temporary (a named `c = name2[i]` in the first loop plus one dead
  scratch word reaches 288 / 290, leaving only the loop-1 spill slot at 0x60 vs 0x64).

### snoweffects.uso 0x6000+ (agent-e run 668)

- No new exacts. Commit cef4d891c on agent-e: gate PASS (3553 / 3579, exact set unchanged).
- **0x64B8 spliced as an NM (94.3 %, 404 words and frame 344 = target).** The two-word excess was the
  reloaded spawn point. Two changes fix it:
  - read u into block locals before the lerp (`float x = u.x, y = u.y, z = u.z; u.x = (vF0.x - x) * r + x;`);
  - store pos and vel through `p->pos.set(u.x, u.y + f178, u.z)` and `p->vel.set(n.x, n.y, n.z)`. With set(),
    edg evaluates all the arguments before the stores, so the lerped values are forwarded.
  - Left: the edg temp slots (the second `operator*` result sits above the first in the target), and the
    target materialises `&t->vFC` for the scale (`addiu v0,a1,252`). These had no effect: `me(&vFC)`, a
    reference / pointer local, a free or float-first `operator*`, a `set()`-style `mul`, a precomputed scale.
    A by-value `mulv(SV, float)` copies v318 (wrong).
- **0x6B28 decoded whole and spliced as an NM (90.8 %).**
  - Sequence:
    - the game flags `snow_game_6B28 + 0x8C & 0x820000` pick RoData+0x58..+0x68 (with 26.0f) or +0x6C..+0x7C
      (with 41.0f) for +0x1B4 / +0x1C4 / +0x1B8 / +0x1B0 / +0x1C0 / +0x1BC;
    - `+0x1C8++` when cam f348 > 20, +0x80 != 0 and on != 1;
    - with the flags and cam s9A0 == 97: `if (0 < f1D8 && 0 == cam fA20) c1CC = 3; f1D8 = cam fA20`;
    - then, if c1CC != 0 or (on >= 2 and cam state == 97): c1CC = 3 when c1C8 >= 7 (state 97), c1C8 = 0 on
      state 97, c1CC-- if nonzero, copy the cam colour, a void call, and spawn when 0 < c1CC < 3.
  - Spawn: `n = v318 * f1C4; n += v3B0 * f1B8`; pool +0x9C (alloc / oldest); `s = |speed|`,
    `if (s < 0.5) s = 0.5f` (a double compare); `u = vF0 + vFC * (f3C * 2.0f * s)`; the same lerp as
    0x64B8. Colour bytes are copied one by one. Fields: 0x40 = sizeVel f1B0, gravity f1B4, decay f1BC,
    alphaVel f1C0, size = unk3C = 1.0, fadeAt = life = alpha = 256.
  - End: `if (+0x80 == 0) +0x1D0 = cam state`.
  - Frame lever: frame 232 = target once `float s` is declared at function scope (before `col`) and
    `float x, y, z` at the top of the `p != 0` block. Named locals that are used take their home there;
    unused ones take none.
  - Left: 357 words vs 358 (the same `&vFC` materialisation), and the inner temp slots are 4..12 bytes off.
    The shorter splice passes the gate.
- **0x7960** (still 99.8 %): the dead `while (0)` ref-multiplier (with uses of a named zero, or a dead
  |speed|) only spills `ang`. An inline `fab(x)` moves |speed| to f14 and speed to f12, but the zero stays in
  f2. The zero and the |speed| ranges share the basic block of the speed compare, so they interfere at block
  granularity.
- **0x9E10**: as NCC (frame 32), the body differs from the target only in the a1 / a2 swap (26 / 30 words).
  These did not change it: the arguments `&head->unk00`, `head + 0` or a copy local; inline attach() members;
  a 2-arg call. Only a real third parameter `N *a2` gets the variable into a2 (it adds home stores, so it is
  not the source).
- Not reached: 0x718C, 0x9328.

### snoweffects.uso 0x6000+ (agent-e run 673)

- Commits on agent-e (base 91633efb7): 6f1851f5e **0x7960 EXACT** (3557 -> 3558), bea11fde7 0x718C NM, 5533e64c1
  0x64B8 / 0x6B28 NM gains. Gate PASS each. No renames.
- **0x7960 EXACT (NCC, moved to the matching donor `snoweffects_uso_ncc_e.cpp`).** The zero / |speed| swap was an
  **edg temporary shared between two expressions**: `ang = acosf(t->dist = -dot(..))` and the `?:` of |speed| both
  used the edg temp M-28 (uopt `-zdbug:5` trace: M-28 has refs in bb1 (the acosf argument, f12) and bb5-7 (the
  ternary)). One LR, so |speed| inherited the call argument's f12. Splitting the store into its own statement
  (`t->dist = -dot(..); ang = acosf(t->dist);`) gives |speed| its own temp; uopt forwards the stored value, so no
  reload. **General lever: when a `?:` result colours like an unrelated nearby value, look for an edg temp shared
  with an embedded assignment / call argument (`lre.py` lists M-xx refs per bb).** The run 662 / 663 levers were
  not needed.
  - Trace harness for IDO 7.1 NCC: `/tmp/claude-1000/h414/u/out/NCC ... -Wo,-zdbug:5` (stderr = PICK trace,
    `uoptlist` in cwd), then `h384/t/lre.py` and `h414/t/ord.py`; script `w673/tr.sh` (FN=function). ord.py's FP
    names are one slot off: trace f2 / f12 / f14 / f16 / f18 = binary f0 / f2 / f12 / f14 / f16.
- **0x718C decoded whole, spliced NM 97.0 % (471 words, frame 368 = target).** Effect C spawn update: state 99 and
  +0x80 clear; a = 0 (cam f348 < 60 or |speed| < +0x214) / +-1 (|speed| > +0x218) / `(1 - f21C) * r + f21C` with
  r = (|speed| - lo) / (hi - lo), negated for speed < 0; `t->timer--; if (t->timer < 0)` with +0x204 reload; then
  `(a != 0)` through an int abs `?:`, a `for (i = 0; i < 1; i++)` pool +0xA0 spawn: u = +0x138 copied then lerped
  to +0xF0 by randf; `w = v318 * f208` (w declared first, assigned by the by-value operator=), `SV a1 = v3B0 * f20C
  * |a|`, `SV a2 = v114 * (1 + randf * RoData+0xB0) * f210; a2 *= |a|; if (0 < a) a2 *= -1`, w += a2, w += a1;
  fields +0x1DC..+0x1F8, `r = randf(); alphaVel = f1EC; alpha = 128 + r * 127`, colour bytes lerped from cam +0xA30
  to +0x224 by a local f = +0x220 with `(int)` casts (trunc.w.s; without the cast IDO emits the unsigned cvt
  sequence). Frame levers: `sp`, `r`, `i`, `n`, `go` at function scope, the `if (p != 0)` block body, one dead
  `{ int sc[2]; sc[0] = 0; }` before `w = ..`. Left: the operator* scalars and |speed| colour f12 where the target
  has f16 (heavy loop weighting; see `w673/d718j.ord`), the `u = t->pos` copy materialises &t->pos (target reads
  312(s1) directly; POD types, copy-ctor forms and by-value lerp helpers did not change it), and the inner edg
  temps sit 4..8 bytes off.
- **0x64B8 94.3 -> 97.0 %, 0x6B28 90.8 -> 93.8 % (both now the target's length).**
  - **The &vFC register comes from operator* built through set()** (`SVb r; r.set(x * s, ..); return r;`, struct
    SVb in the NM donor): the vector fields and u become SVb and uopt keeps `addiu v0,a1,252` like the target.
    The 0x6B28 run 668 operator* (`return SV(x * s, ..)`) shared its ctor-parameter temps across every expansion,
    so |speed| interfered with them and took f16, which also shifted the ugen FP temp ring for the whole
    function. (A `fc = (SV *)((int)fc * 1)` pointer local also materialises &vFC, but SVb alone does it.)
  - `t->timer--; if (t->timer < 0)` in place of `if (--t->timer < 0)`: the target's counter uses t-registers
    (also in 0x718C).
  - Left: 0x64B8 frame 352 vs 344 (the spawn-block temps are 4..12 bytes off), 0x6B28 frame 240 vs 232 and the
    lerp loads.
- Not reached: 0x9328 (the run 659 draft in `ncc_drafts/snoweffects_nm_e.cpp` is a real C++ ctor; it needs an
  extern "C" splice shape before it can be measured for length), 0x9E10.

### snoweffects.uso 0x6000+ (agent-e run 680)

- No new exacts (3559 / 3579). Commits on agent-e: 830af46a4 (0x64B8 / 0x6B28 NM gains, gate PASS), 1fb3e3617
  (restores report.json, which the gate rewrote), 494026148 (0x9328 draft). Gate PASS before each. No renames.
- **0x64B8 97.0 -> 97.8 %, 0x6B28 93.8 -> 95.2 %: both now have the target frame (344 / 232).** The frame excess was
  the spawn-block lerp, not a shared temp pair:
  - the lerp `float x, y, z` are declared in the loop body before `SPart *p` (0x64B8), or at the top of the `p != 0`
    block (0x6B28). That puts their 12 bytes above p, where the target has them;
  - the randf result goes into a float that is dead by then (`k` in 0x64B8, `s` in 0x6B28), not a new `float r`.
    The named r was the extra word between u and the operator* result;
  - `p->setLife(256.0f, t->f18C)` / `p->setAlpha(256.0f, t->f188)` are inline two-parameter setters on SPart
    (life / decay at +0x30, alpha / alphaVel at +0x50). They give the target's early `lwc1 $f0` loads of the
    velocity fields, because inline parameters are uopt-coloured. The plain field stores load them late into the
    ugen ring.
  - Left (both): the lerp loads u.x / u.y / u.z up front into f2 / f12 / f14 (uopt colours). Ours copy-propagates
    `x = u.x` into the uses and loads lazily into the ugen ring. An inline member `u.lerp(a, r)` with its own
    `float x = this->x ..` locals does give the up-front loads, because reads through `this` are not propagated.
    But its locals land at the bottom of the frame (+8) and its colours take f16 from ugen, so the xform spills.
    No effect: set() form, getters, chained `u.x = x = ..`, `+=` form, a reference-parameter lerp. 0x64B8 also
    keeps the `n += v318 * k * (f184 + spd)` operand temps swapped (target +300 / +312).
- **0x718C**: the same lerp shape (u.x into f2, reloaded per component). Neither `lerpf(u.x, ..)` nor a reused
  `sp` changed it (both copy-propagated). The f12 / f16 ring offset was not reached.
- **0x9328 measured in splice form** (`objcopy --redefine-sym __ct__11SnowTarget9Fv=snoweffects_uso_func_00009328`
  on the draft): **246 / 247 words** (a shorter splice fits), normalised 226 / 247, frame 192 vs 224. The levers
  are in the draft comment in `ncc_drafts/snoweffects_nm_e.cpp`:
  - the per-Parm name words come from rvalue names: `PName(char *)` and `NM9() = PName(*(char **)..)`;
  - ParmC's Colour member is a POD base (a user ctor adds a `this + 16 == 0 -> new(16)` check);
  - `col[3] .. col[0]` are stored in reverse.

  To splice it, add a donor rule with `--redefine-sym` for the ctor, the GdlParmBase / SNode ctors and the four
  vtables (the Makefile line 180 pattern).
- **0x9E10**: not reached.

### snoweffects.uso 0x6000+ (agent-e run 685)

- No new exacts (3560 / 3579). Commit 19ac0b825 on agent-e, gate PASS, no renames. It also carries the run 680 files:
  the run 680 commits 213dc4fee / 8dbf7760f were made on branch **agent-d**, not agent-e, and were never landed.
- **The up-front u.x / u.y / u.z loads are fixed.** objdiff: 0x64B8 97.8 -> 99.8 %, 0x6B28 95.2 -> 98.4 %. Diagnosis,
  from the instrumented uopt (`w685/tr.sh`, FN=function):
  - `x = u.x` is copy-propagated because u.x is a direct memory variable. Any spelling that keeps x as a variable
    (getters, a `const SVb &` alias, dead `if (1) {}` / `while (0)` anchors, a later code-free use) gives the up-front
    loads, but x / y / z then sit in the randf call's block, where f0 / f2 are forbidden. They take f14 / f16 / f18,
    which pulls f16 / f18 out of the FP ring for the whole function, and the frame grows by an f28 save.
  - In the target, x / y / z have the colours of the following `pos.set()` parameters (pool words M-120 / M-124 ...),
    so they are **inline parameters** that land on those pool words, not named locals.
  - Lever: `void lerpTo(const SVb &a, float r) { lerpComp(r, x, y, z, a); }` with `lerpComp(float r, float px,
    float py, float pz, const SVb &a)`. The order matters: (px, py, pz, a, r) is one word early (f14 / f2 / f12),
    and (r, px, py, pz, a) or (a, r, px, py, pz) hits f2 / f12 / f14. The reads go through `this`, so they are not
    propagated.
  - Frame: the lerped point is copied into the block's `float x, y, z` for `p->pos.set(x, y + f178, z)`. That gives
    them homes above p (frame 344 / 232, u at 104, p spill at 128 as in the target).
- **0x718C** loads each component into f2 right before its use: one materialised parameter per statement,
  `x = lerpF(x, a.x, r)` with `static float lerpF(float p, float q, float r) { ; return (q - p) * r + p; }`. The empty
  statement makes it a multi-statement inline, so p is materialised. A local `float v` / `d` adds a word and colours
  it, and `p = ..; return p;` colours the result. The lerp has the target's shape, but the score is unchanged
  (96.9 %), because the FP ring is one slot off and the run 673 residuals remain (|speed| f12 vs f16, `u = t->pos`
  materialising &pos so `beqzl .. addiu s5` becomes `beqz .. addiu v0`).
- Left in 0x64B8 (397 / 404 regmatch): the cam pointer for `n += cam->v318 * k * (f184 + spd)` is v0, where the target
  has v1. The operand temps of that statement sit at 312 / 300, where the target has 300 / 312.
- Left in 0x6B28 (336 / 358): `mtc1 zero` / `lwc1 2592(v0)` order near the start; the u copy goes through a0, where
  the target uses v0.
- **0x9328 not wired yet.** Plan: a donor rule for `ncc_drafts/snoweffects_nm_e.cpp` (or a copy of only the ctor),
  NON_MATCHING only, with `--redefine-sym` for `__ct__11SnowTarget9Fv`, `__ct__12GdlParmBase9FP6Parms95PNamei`,
  `__ct__6SNode9Fv`, `__nw__FUi`, `mem_new`, `D_00000000` and the four vtables. Add undefined_syms entries whose
  values are the target's lo16s: Data+0xA34 for the default colour, vtables at 0x0 / 0x838 / 0x850 (map them from the
  `lui/addiu` pairs at 0x9354 / 0x940C / 0x959C). The draft is 246 / 247 words, so it fits.
- 0x9E10: not reached.

### snoweffects.uso 0x6000+ (agent-e run 692)

- No new exacts (3561 / 3579 on agent-e). Commits on agent-e: 9ec27ab61 (0x9328 NM spliced, 95.7 %), eb771ab33
  (0x6B28 98.6 -> 99.1 %; the commit message says 98.9, the gate report says 99.13). Gate PASS before each, no renames.
  0x9328 / 0x9E10 were then re-scoped to agent-b.
- **0x9328 wired:** donor `src/snoweffects_uso/snoweffects_uso_ncc_nm_e9.cpp` (only the ctor from the draft), Makefile
  `SNOW_NM_E9_DONOR` (non_matching only), objcopy renames: ctor -> snoweffects_uso_func_00009328, SNode / GdlParmBase
  ctors, `__nw__FUi`, mem_new -> 0-pinned `snowe9_*`, vtables -> `snowe9_vtbl_*` pinned at **0x0 / 0x838 / 0x850 / 0x868**
  (the lo16s in the target; a 0-pinned vtable would be wrong here). 246 / 247 words, so the NM .text is 4 bytes
  shorter, which is fine (the existing NM donors already leave it 16 bytes short).
- **0x6B28:** `t->cam->fA20 == 0.0f` (not `0.0f == ..`) gives the target's `mtc1 zero,f16` before `lwc1 f18`. Putting the
  spawn statements in a nested `{ }` below `float x, y, z;` homes the op+ temporary (`t->vFC * ..` bound to
  operator+) below x / y / z (vfp-136, as in the target): edg places a block's temporaries ahead of its named
  locals, so the nested block moves the temporary under them.
  - Left: one inline word between the two n products. The target's r2 is at vfp-100, ours at -96; u, r and the op+
    r then follow it, one or two words lower. A `mul2(float s) { float k = s; .. }` for the second product adds that
    word (r2 / u / r / op+ r all land on the target) but also pushes the nested temporary down (to -140) and the frame
    to 240. The u-copy address is hoisted into a0 (target: `addiu v0` at the copy).
- **0x64B8 (unchanged, 19 diffs):** the block temporaries for `n += cam->v318 * k * (f184 + spd)`. The `this` temporary
  of the outer op* is always at vfp-32 and the += argument temporary at -44 (the target has them the other way round).
  None of these moved them: a non-member / friend / by-value op*, member `sc()`, `const SV` return, the
  `n.operator+=` / non-member += / `addv()` forms, a different class for the first product (the temporaries are
  grouped by type, but the SW group still went first), `(const SV &)` casts, a `const SV &d` local, zero-code
  `if (0)` / `SV();` statements in the block (these add temporaries, and none are reused), and padding declarations
  before the function. The cam pointer v0 / v1 did not move with `(t + 0)`, `me()` hops, `cam[0]`, or trailing
  `if (k) {}` / `if (spd) {}`. Next idea: find which statement in the target frees an SV temporary that edg then
  reuses (in r1, the duplicated-statement probe, reuse did happen: three temporaries, not four).
- 0x718C: not reached.

### snoweffects.uso 0x6000+ (agent-e run 698)

- No new exacts (3564 / 3579 on agent-e). Commit b4d7dfc02 on agent-e (NM donor `snoweffects_uso_ncc_nm_e.cpp` only), gate
  PASS, no renames. objdiff: 0x64B8 99.896 -> 99.906, 0x6B28 99.134 -> 99.182, 0x718C 96.989 -> 97.070.
- **Lever: edg float temporaries.** A multi-use scalar parameter of an inline operator gets a 4-byte edg temporary, and
  where that word lands moves every inline temporary below it.
  - 0x64B8: `SV::operator*=(float s) { float f = s; .. }` puts the v318 * k result at the target's sp+200 (was 204).
    The `(f184 + spd)` parameter of the outer operator* was the word between r1 and the return slot; with the named f
    it moves above r1, as in the target. 19 -> 15 positional diffs (2 of those are RoData relocations).
  - 0x6B28: a dead `if (0) n *= t->f1B8;` between `SVb n = v318 * f1C4` and `n += v3B0 * f1B8` gives the missing word
    between the products: r2 at sp+132, the later temporaries at 68 / 40, frame stays 232. It also moves x / y / z 4 bytes
    low (92..100 vs 96..104), so the gain is small. `mulk(float s) { float k = s; .. }` on either product, a single
    expression, `n.operator+=`, `{ }` / `if (1)` around the += and the `SVb n(..)` form are all worse.
  - 0x718C: `if (0) w *= t->f20C;` after `w = v318 * f208` (no other position or scalar did better).
- **0x64B8, still open (13 real diffs):**
  - The 300 / 312 swap of the two += temporaries. None of these moved it: the float-first friend operator*
    (`(f184 + spd) * (v318 * k)`), named `mulr` / `mulv` helpers (by-ref and by-value), base-class `SV0` parameters with
    `(const SV0 &)` casts (kit LXX), `(SV &)` / `(const SV &)` casts on the inner product, a `const float &` scalar, a
    `const SV &w` alias inside +=, an `add()` forwarder, and `const SV &` / `SV(..)` forms for v.
  - Dead SV statements (`if (0) n += ..`) add 24 to 48 bytes of new temporaries and none of them are reused. `?:`,
    `&&` and `sizeof` forms are folded away before any temporary is allocated.
  - cam v0 (target v1): `(*t->cam)`, `t[0].cam`, a member op-, a friend op*, a pointer op- argument and
    reordered statements all keep v0. `(this + 0)` hop accessors (c1 / cx on SnowEm, w1 / wx on the cam) and `me()`
    hops cost +8 frame (pointer temporaries get homes) and still give v0.
- Scratch: `/tmp/claude-1000/agent-e/w698/`: `t.py` (`score` / `runl` / `lay` print positional diffs, frame and the
  temporary slots), `od.py` (agent-h's objdiff scorer, pointed at agent-e), and `r*.py` (the probe batches).

### snoweffects.uso 0x6000+ (agent-e run 703)

- No new exacts, no commits (nothing beat the run 698 donor; 3564 / 3579 unchanged). No renames. Scratch
  `/tmp/claude-1000/agent-e/w703/`: `t.py` adds `score7` (the same scorer through `tools/ncc721.sh`) and `adiff`
  (difflib-aligned diff count, robust to length shifts); `r1..r13.py` are the probe batches.
- **0x64B8 `+=` temporary order: what the target is doing.**
  - Naming: A = the temporary bound to the outer `operator*`'s `this` (the inner `v318 * k` result, read back for
    the second product), B = the temporary bound to `+=`'s `const SV &` (the outer product). Ours A = sp+312,
    B = sp+300; target A = 300, B = 312.
  - Block temporaries are allocated last-created-highest: duplicating the statement (`n += X; n += X;`) puts the
    second statement's two temporaries ABOVE the first's (368 / 356 over 344 / 332, frame +56, no reuse). So ours
    creates B then A (top-down lowering: the `+=` argument binding first, then the outer call's object), and the
    target creates A then B (bottom-up).
  - **The IDO 7.1 front end is the right one.** Through `tools/ncc721.sh` (EDG 2.29) the same donor puts A below B
    (308 / 320, the target's order), but 2.29 also breaks the module's exact functions (0x4188 184 aligned diffs,
    0x8D70 44, 0xA10C 127, 0x9884 14, 0x7960 18), and 0x64B8 itself goes to frame 352 with two more s-registers.
    So the swap is a 2.19 construct, not a front-end difference.
  - Negatives under 7.1 (all keep 312 / 300, or rebuild the statement): `(b * (c * d))` is a different product;
    friend `operator*(float, const SV &)` with `d * (b * c)`, `(f184 + spd) * (k * v318)`, `k * v318 * ..`;
    `SV t = b * c; n += t * d;` (named, inside and outside `{ }`: 265+ diffs, the hops share one register);
    `const SV &a = b * c;` (same); `const SV &d = whole; n += d;` (79 diffs, frame 344, A still on top);
    `SV d = whole; n += d;` (81 diffs, frame 336: the same code shape, d below n); `SV d` declared at function /
    if / block scope and assigned (`d = X; n += d;`, `n += (d = X)`: +16..32 frame); `n = n + X`; by-value
    `operator+=(SV v)` (same code shape, B becomes an inline local at sp+148 and everything above shifts up 16);
    template `+=`; out-of-class `inline` definitions after the function (inlining is not parse-time); identity
    inlines `idv` / `idw` / `idx` / `idr` / `idf` around the inner product, the whole product or the scalar;
    a different class for the inner result (`SW mulw()`, with or without `operator SV()`); derived-to-base `SV : SV0`
    with a non-member `operator*(const SV0 &, float)`, `+=(const SV0 &)`, `(const SV0 &)` casts, `SV0` by value;
    converting-constructor classes `SX(const SV &)` (plain, `*this = (const SX &)v`, `SX : SV` base-init, `SX : SV`
    memberwise) through `mul()`, `operator*(const SX &, float)` and `operator+=(SV &, const SX &)`: all add 6..24
    words; `~SW() {}` / `~SV() {}` destructors rebuild the statement (+5..14 words).
  - Next: the creation order is decided in edg's lowering. A form whose outer call is lowered before the `+=`
    binding (bottom-up) is what is needed; none of the C++ spellings above does it. The cam v0 / v1 is a
    ugen-local pick (the cam load is not in uopt's LR table; v1 there would need v0 busy in that block).
- **0x6B28:** the 4-byte residual is the nested block's op+ binding temporary (target sp+96, ours 92: the
  `lwc1 104 / 100 / 96` loads at 0x271), not x / y / z; the `if (0) n *= t->f1B8;` word above it pushes it down.
  Real statements in its place, all worse than the dead statement (25 aligned diffs): none (43), `float f = t->f1B8`
  named (153), `(const float &)` (43), `if (0) {}` / `(void)t->f1B8` (43), `n *= 1.0f` (129), `SVb n(..)` (177),
  `SVb n, m` pair (80), one expression (232), `SVb n; n = ..` (123).
- **0x718C:** the |speed| colour (target f16 for all three `sp < 0 ? -sp : sp`, lo f12; ours the reverse) did not move
  with an `absf()` inline (three bodies), a named `as` assigned in each test, `0.0f > sp`, `t->lo > |sp|`, a `float lo`
  local, or code-free `if (t->lo) {}` / `if (sp) {}` / `if (lo != hi) {}` / `if (1) {}` tests at five positions.

### snoweffects.uso 0x6000+ under MIPSpro 7.2.1 (agent-e run 707)

- No commits, no renames (3568 / 3579 unchanged). The 7.1 donor `snoweffects_uso_ncc_nm_e.cpp` stays (64B8 13 real
  diffs). Scratch `/tmp/claude-1000/agent-e/w707/`: `v.py` / `rep.py` (score7 + aligned diff + an opcode-only diff +
  the copy-shape detector `tell2.py`), `e*.py` probe batches. Best 7.2.1 draft: `keep_64B8_mp72_s1.cpp` (also `s1.cpp`).
- **Verdict: 0x64B8 is a 7.2.1 (EDG 2.29) function.** The deciding feature is the `n += v318 * k * (f184 + spd)`
  temporary order (run 703): 2.29 lowers it bottom-up (A below B, the target's order) in every variant, 2.19 never
  does. Nothing else in 64B8 separates the two front ends once the classes are spelled 2.29-style (below): with
  POD classes both front ends give the same object except that A / B pair. 0x6B28 / 0x718C: not settled this run
  (same family and structs, so probably 7.2.1 too; their 7.2.1 drafts were not retuned).
- **Lever 1, struct copy shape (the reason 7.2.1 looked wrong):** under 2.29, ANY user-declared constructor on the
  class makes the chained by-value copies (op result -> return temp -> named / bound object) come out
  `lw 0; lw 4; sw 0; ..`; the target (and 2.19 with or without ctors) has `lw 0; sw 0; lw 4; lw 0(dst); sw 4; ..`.
  Make SV / SVb POD (no ctors at all) and all five 64B8 copies take the target's shape. Mini repro:
  `m2.py` / `m3.py` / `m4.py`. heli B08 shows the same thing: its target copies are all the 2.19 shape, and its mp72
  donor has 3 of 7 the wrong way round (B08 insns ~427 / 595 / 635). Its `Vec3` has ctors: try a POD Vec3 there.
- **Lever 2, ctor blocks without a ctor:** removing the ctors also removes the blocks that EDG's constructor
  `if (this != 0)` test creates. At -O2 uopt folds the test but keeps the block boundaries, and those split
  the float pool-word live ranges. Without them the set() pool words cross calls and go to f20-f30 (+16 frame,
  spd spilled). Fix, still POD: `static void ct3(SV *p, float a, float b, float c) { if (p != 0) { p->x = a; ..} }`
  (`SV r; ct3(&r, x * s, ..); return r;` for SV::operator*), and `template<class T> T *ct0(T *p) { if (p == 0)
  p = (T *)snow_nw(sizeof(T)); return p; }` with `ct0(&r)` in SVb::operator*, SVb operator+ and SV operator-. A
  test that leaves p possibly null (`if (p == 0) p = new; if (p != 0)`) keeps a real `beqz`; `if (p == 0) p =
  new;` alone, or no test, gives the f20+ colouring again. Result: the opcode-only diff goes 23 -> 0, length 404.
- Then the 7.1 levers must be undone or replaced. `float f = s` in SV::operator*= costs 8 bytes under 2.29 (drop it).
  The lerp factor goes in a named `float r` declared with x, y, z at the loop top (`float x, y, z, r;`) instead of
  reusing k. Draft s1: frame 344 = target, 15 real diffs (7.1 donor: 13).
- **Left in s1 (15):** the v318 * k product. The target has it in f0 / f2 / f12, stored at sp+200, with the cam
  pointer in v1. Ours has f2 / f12 / f14 at sp+204, cam in v0. The next operator* temporary is at 176 vs 172.
  So one word below sp+172 is extra and one between 212 and 300 is missing. These are the same words as the
  7.1 donor's cam v0 / v1 residual, but here the A / B pair is right. No effect: `if (0) n *= k;` before / after,
  a dead float in operator+=, `{ float q = k; .. }` (+8), dropping `ct0(&v)` on the xformB vector (no change, so
  it is gone from s1).
- Next: wire s1 as `snoweffects_uso_mp72_nm_e.cpp` (tools/ncc721.sh, NM-only; drop 64B8 from SNOW_NM_E_FUNCS) once
  it beats 13 diffs. Then port the POD + ct3 / ct0 class set to 6B28 and 718C. Under plain POD, 718C's |speed|
  already colours f16 (the target's). 7.1 gives the same on that POD source, so this is a class-shape lever for
  either compiler, not compiler evidence.

### snoweffects.uso 0x6000+ under MIPSpro 7.2.1 (agent-e run 713)

- **0x6B28 / 0x718C NM donor moved to 7.2.1** (agent-e 9692b0d1c; gate PASS, 3569 / 3579, no renames). New
  `src/snoweffects_uso/snoweffects_uso_mp72_nm_e.cpp` (Makefile `SNOW_MP72_E_*`, tools/ncc721.sh, NM-only).
  objdiff: 718C 97.07 -> 97.28 %, 6B28 unchanged at 99.18 %. 64B8 stays on the NCC donor (`SNOW_NM_E_FUNCS`).
- **Compilers.** 718C is 7.2.1: its chained op* temporaries (`v3B0 * f20C * |a|`, `v114 * .. * f210`) sit at
  sp+320 / sp+308 in the target, which is EDG 2.29's order; the 7.1 donor has them swapped. 6B28 has no chained
  temporary, and both front ends give the same frame and code. It sits between two 7.2.1 functions, so it is
  filed with them. The run 698 `if (0) x *= ..` float-temporary levers still pay under 7.2.1 in both functions
  (removing them: 6B28 +18 diffs, 718C +15), and so does 718C's `{ int sc[2]; sc[0] = 0; }`.
- **64B8: not beaten (s1 = 15 real diffs, NCC donor 13).** The cause is now known; the fix is not.
  - **Tools** (scratch /tmp/claude-1000/agent-e/w713/): `vm.py` lists uopt's `isvar` offsets with `v` for vreg
    words (via `d6.sh` = ncc721 + `-zdbug:6`). Unlike `-g3`, this shows the inline-parameter VREG words.
    `g3.sh` + `md.py` / `fv.py` give the `-O2 -g3` names. `/tmp/claude-1000/agent-g/r689/lrb.py uoptlist <bb>`
    (on a `-zdbug:5` dump) lists the LRs live in one block.
  - **Words in the `n += v318 * k * (f184 + spd)` statement** (vfp; sp = 344 + vfp):
    - op*1: s = -20, this = -16, r1 -140, ct3's a / b / c = -120 / -124 / -144 (-144 is NEW, after r1).
    - op*2: return slot -156 (sp 188), s = -144 again, r2 -168, ct3's a / b / c NEW at -172 / -176 / -180.
    - Target: -128, one extra word at -132, r1 -144, return slot -156, one word at -160, r2 -172.
  - **-20 is the function-scope `?:` temporary of `spd = speed < 0 ? -speed : speed`.** Every later float
    parameter reuses it first: op*='s s and op*1's s. That gives one uopt LR across 8 blocks (adj 29.7, coloured
    f0), so op*1's a / b / c get f2 / f12 / f14. The target has f0 / f2 / f12. The target's frame fits op*1's s
    taking a NEW word (-132) while a / b / c take -20 / -120 / -124: then a shares -20's f0, there is no new word
    after r1, and op*2's s is the new word after its return slot (-160). No spelling found so far does that.
  - **Flat or worse:**
    - op*= spelled as set() / ct3(this) / set4(.., s) / mulBy() / a comma return / const s / a block float;
    - op* via set(), named p, mulTo, a ct4 with s, `float q = s`, or `s * x`;
    - a friend `float * SV` in any operand order; `(n *= ..) += ..`;
    - `if (1) {}` / `do {} while (0)` between the statements. This does split the uopt block, but -120 / -124
      are shared with the op- statement, where -20 is live;
    - spd through if / else, or an inline fab() (which adds a -24 vreg, frame +4);
    - dead float-parameter inlines (no ucode, so no word).
  - Partial hits:
    - `set4(x * s, y * s, z * s, s)` in op*= puts r1 at the target's -144, but recolours the n *= products.
    - set() in op*= puts r2 / the -160 word at the target's place, but the frame is +8.
  - Next: find a front-end shape where op*1's s is not handed the free -20 word. Try a float parameter
    allocated while -20 is still held in the same full-expression, or a different dtype pool for s. Wire the
    7.2.1 64B8 into the mp72 donor once it reaches 13.

### snoweffects.uso 0x6000+ under MIPSpro 7.2.1 (agent-e run 718)

- No commits, no renames (3570 / 3579 unchanged). Nothing beat the committed donors (64B8 NCC 13 diffs, 718C 97.28 %,
  6B28 99.18 %). Scratch `/tmp/claude-1000/agent-e/w718/`:
  - `ud.sh` = ncc721 front end, then `ugen -O0 -d` on the raw `.B`. It prints edg's ucode tree with every pool word.
  - `al.py` prints one statement's word allocations: `R` / `A` = float / pointer vreg words, `l` = struct (memory) words.
  - `fl.py <src> <name> <fn index>` gives the same per source line for a whole function.
  - `toy*.py` are mini repros, and `p*.py` are the probe batches.
- **How EDG 2.29 allocates inline words** (read off the `.B` dumps):
  - Parameter words of statement-bodied inlines are pooled. Each one takes the OLDEST free word of its dtype.
  - A word reused from an earlier statement stays locked until the end of the current statement. A word first
    allocated in this statement is freed when its inline ends, and the same statement can reuse it.
  - Named locals of inlines (`float f = s`, xformB's x / y / z, a `{ float q; }`) always get a fresh word, and that
    word is never reused.
  - The front end substitutes a parameter whose argument is a plain variable, so the parameter gets no word, but
    only in a single-`return` inline that returns a scalar (`idf(q) { return q * q; }`). It never does this for
    an SV-returning or statement-bodied inline.
  - const / volatile / register / template parameter types and argument order do not change any of this.
- **64B8: the target's words are now pinned down.** The target allocates:
  - a fresh word for the scalar of the first `operator*` (vfp-132), before r1 (-144);
  - ct3's a / b / c in the three old free words (-20 / -120 / -124);
  - op*2's scalar fresh at -160, after its return slot (-156); r2 at -172.

  The products then colour f0 / f2 / f12, as in the target. Shown by:
  - `p5 c2`: the scalar as a derived wrapper `FST(k)` (agent-b's PNameT idea) bound to `const FS &`, read into a
    named `float f = s.v` in the operator;
  - `p6 d1`: `mulr(const float &s0) { float f = s0; .. }`.

  Both give exactly that allocation and the f0 / f2 / f12 products. The cost is a memory scalar: FST's temporary,
  or k itself once its address is taken (+8 frame, `swc1 f20` / `lwc1`). By-value FS with FST, even sliced, copies
  through `lw` / `sw`, and uopt does not forward it.
- **The colour needs op*1's scalar to stay off -20, not just the extra word.** `p8 f1`:
  - A dead `SV::ct4(0, k, k, k, k)` (four float parameters) after `n *= ..` makes the fresh -132 in the statement
    before.
  - With it, every op*1 / op*2 word is the target's relative layout, but the frame is +8 (op*2's ct3 / `+=` words).
  - op*1's scalar is still -20, so the products stay f2 / f12 / f14.
  - The lock rule above means a pooled float parameter cannot skip three free words. So op*1's scalar needs a
    non-pooled source that stays in a register. None found.
  - Flat or worse: `idf` / `idf2` wrappers on k (`idf2` shifts the statement by its named word); `float s = s0`
    in op*; `return mk3(..)`; `const` / `volatile` scalars; `+k` / `(float)k` into a `const float &`.
- **718C:** porting the cam / emitter vectors to the POD `SV` (ct3) class is worse (adiff 209 -> 309; h1 / h3).
  The remaining diffs are register renames (uopt |speed| colour, then the ugen FP ring), with no structural diff.
- **6B28:** dropping one or all of the x / y / z copies is worse (adiff 25 -> 77..83). `fl.py` shows the op+
  binding temporary at -140 with the extra `if (0) n *= ..` pointer word (-88) above it; the target has it at -136.
- Next for 64B8: look for a front-end construct that gives a float a fresh, non-pooled word while it stays a
  register value (for example a parameter-free inline that reads k from an enclosing inline's named local), or
  accept the memory scalar.

### snoweffects.uso 0x64B8 under MIPSpro 7.2.1 (agent-e run 744)

- **0x64B8 EXACT** (agent-e 0bcf74c92; gate PASS, 3573 / 3579, lost: none, no renames). Spliced in both build trees
  from `snoweffects_uso_mp72_nm_e.cpp` (`SNOW_MP72_E_EX_FUNCS`). The IDO 7.1 NCC donor `snoweffects_uso_ncc_nm_e.cpp`
  only served 64B8, so it and its Makefile block are gone. Scratch `/tmp/claude-1000/agent-e/w744/`: `s.py`
  (`fl` / `lset` / `show`: edg word layout of a variant, compared with the target's memory-word set `TGT`), `cp.py`
  (parallel compile + score), `c*.py` probe batches, `tr.sh` (instrumented-uopt colouring trace for 64B8 alone).
- **Search method:** filter on edg's memory-word (`l`) offsets first. The target's set is ours with r1 -140 -> -144
  and r2 -168 -> -172. Only variants with that exact set get compiled.
- **New edg rule (corrects run 718):** param substitution is not limited to scalar-returning inlines. Any inline whose
  body is declarations plus one `return` substitutes a plain-variable argument; that includes SV-returning ones,
  e.g. `SV f(float s) const { SV r; return (r.setIf(x * s, ..), r); }`. A statement in the body (`ct3(..); return r;`)
  turns it off. `return mk(..)` also substitutes but adds a third struct copy, so the comma form is the one to use.
- **The three fixes:**
  - `SV::scaled(k)`: k is substituted, so the products take the three oldest pooled float words, which are the target's
    f0 / f2 / f12 LRs. That was the run 713-736 blocker. A pooled scalar always took the oldest word (-20). An extra
    old word above it (e.g. `fab()` on spd) only moves the problem, because that word becomes every later
    statement's first pick and so takes f0. A `double` parameter (Q pool) also fixed the colours, but cost cvt code.
  - `const SV *q = this;` inside scaled: a named word, never reused. It is the one fresh word above r1, which puts r1 at
    sp+200 and makes s2 fresh, so r2 lands at sp+172. Loading through q (or this) keeps the dead `addiu v1,v1,792`
    store; with the loads in the caller (`mk3(v.x * k, ..)`) uopt drops it.
  - `SV::operator+=` as `x = x + v.x`: one compound-lvalue pointer word fewer below, so frame 344.
- **v1 vs v0 was the callee's return type.** `math_vec3Normalize` returns int (`context_game_libs_post0b.h`). With
  `void`, uopt colours the this-word LR (one block, right after the norm call) v0: nothing interferes and v0 is
  first. With an int / pointer return, the call's v0 result is forbidden to the next block's LRs, so it takes v1. 30+
  block / dummy / q spellings did not move it. Check a blank-jal callee's real return type before chasing a v0 / v1
  colour right after a call.

### snoweffects.uso 0x718C / 0x64B8 under MIPSpro 7.2.1 (agent-e run 736)

- **0x718C EXACT** (agent-e 465c3eedb; gate PASS, 3572 / 3579, lost: none, no renames). It is now spliced in both
  build trees from `snoweffects_uso_mp72_nm_e.cpp` (Makefile `SNOW_MP72_E_EX_FUNCS`; `SNOW_MP72_E_FUNCS` removed).
  Scratch `/tmp/claude-1000/agent-e/w736/`: `k.py` (`run` = score + objdiff + non-sp count + the frame-relative sp
  offsets), `d.py` `sim()` (edg word layout from `w718/fl.py` in ~0.4 s, no back end), `pi.py` / `pg.py` (parallel
  word-layout search, then compile only the layout hits), `pk.py` (the colB search).
- **Method: work in edg's M space, not in sp.** uopt keeps edg's frame layout: sp offset = frame + M offset, and the
  frame is round8(M length + 104) for this function (`def mtype=M length=N` in the `.ud` dump; 264 -> 368, 268 / 272
  -> 376). Every vreg word (R / A / J) takes a 4-byte hole even when it is coloured. So list the target's struct
  temporaries as M offsets (target sp - 368) and count the words between them.
- **The three fixes, each found from that count:**
  - Scalar region one word too many: `n` (the `a != 0` test) is a separate named int. Reusing `go` drops it
    (registers unchanged). This replaces run 732's `int sc[1]` pad, which had pushed everything the wrong way and only
    lined up the upper sp offsets through the frame growing by 8.
  - Lower region: `w.asg(t, t, <product>, t, t)`, an op= with code-free pointer parameters around the by-value copy
    `o`. Parameters of a call are allocated after its arguments are expanded, so the two leading ones are fresh words
    above o (copy 2 words lower) and the trailing ones fresh words below it (a1 / a2's temporaries 3 words lower).
    Leading R parameters reuse the freed product words instead (no shift); the type pattern decides which words are
    fresh. Statement-level `dm_X(..)` dummies changed nothing here: they took only old words.
  - M length 272 -> 264: the colour block's named c0 / c1 / c2 / f become `colB(q0, f, m0, c0, p, t)` with c1 / c2
    named inside. f and c0 are pooled parameter words (old words, no frame cost); q0 / m0 choose which old words, so
    f lands on a word that colours f2 and c0 on one that colours f14 (16 placements tried, one exact).
- **Rules confirmed:** pooled words are reused strictly oldest-first by offset (not by release order: a dummy
  statement that locks R-24 before a2 leaves a2's order unchanged). A param word can therefore never be younger than
  a word allocated later in the function, which is why a2's `z` product needs a fresh word unless the colour block
  gives one up.
- **0x64B8 (not beaten; NCC donor stays 99.91 %).** mp72 s1: 13 non-sp diffs, all in op*1 (`v318 * k`): products f2 /
  f12 / f14 vs target f0 / f2 / f12, `this` in v0 vs v1, r1 at sp+204 vs 200 and r2 176 vs 172.
  - M-space reading: the target has exactly one more word before r1 (r1 -144, ours -140) and none between r1 and the
    return slot l-156 (ours has op*1's fresh ct3 c at -144). That is run 718's allocation: op*1's s fresh, ct3's
    a / b / c all old.
  - `m1(q0, q1, q2, s)` with three R dummies gives s fresh at -132 and r1 at -144 (the target's r1), but ct3 then takes
    three fresh words (frame 352, 28 diffs). Under oldest-first + lock-until-statement-end there are only three old
    pool R words (-20 / -120 / -124) at that statement, so s cannot be fresh while ct3 reuses all three. s has to be
    a non-pooled word, and no source form found gives one without a memory scalar (k is in f20 from line 56 on).
  - v1 vs v0: nothing in the target holds v0 across 177..182 (no v0 use from 140 to 260), so it is a colour choice
    for op*1's `this` word, not a conflict. Leading A / R dummies on `+=` (addX) or op*2 do not move it
    (13 or worse); `+=` parameters are allocated after the op* expansions.
- Next for 64B8: a non-pooled float word for op*1's s that stays a register (e.g. a scalar single-return inline
  layer whose substituted parameter feeds a named local), or the A-word placement for op*1's `this`.

### snoweffects.uso 0x718C / 0x64B8 under MIPSpro 7.2.1 (agent-e run 732)

- **0x718C NM 98.14 -> 99.95 %** (agent-e 7cbaa7e2c 99.85 %, 37d75951b 99.95 %; gate PASS both times, 3571 / 3579,
  lost: none, no renames). Every register now matches; only frame offsets are left. Scratch
  `/tmp/claude-1000/agent-e/w732/`: `h.py` (`go2` = score + objdiff % + non-sp diff count, `ns` / `spd` / `offs`
  print the register-only diffs, the sp diffs and the sorted sp offsets of target vs ours), `p*.py` probe batches.
- **What fixed the registers.** Each lever was found by reading the non-sp diff, not by sweeping:
  - **Ramp: a named `float d = t->hi - t->lo;`** gives lo f12, d f14, r f2. Without it, hi - lo was a ugen temp
    (f8), so the FP temp ring was one register ahead for the rest of the function. That one temp was most of the
    "lerp / colour FP ring" leftovers. With d named, lerpF must drop its named d (the plain
    `(q - p) * r + p` form); otherwise the lerp takes coloured d's.
  - **Field copies through inlines.** In the target, the loaded fields sit in uopt-coloured registers (f1F8 / f1E8
    in f16, f1EC in f12), so they pass through edg pooled float parameter words:
    - `setSz3(s, u, f) { size = s; fadeAt = f; unk3C = u; }`. Body order fadeAt before unk3C gives the target's
      store order.
    - `setLife(256.0f, t->f1E8)`.
    - `setAlpha3(a, unused, v)` with a load (`t->f1EC`) as the dummy argument. The extra word moves alphaVel's
      word to f12 and f into f2.
    - Single-parameter member setters (`setSize(f)`) are bad: `this` (p) then takes a pooled pointer word, and p is
      spilled instead of living in s0.
  - **Colour section: three variables c0 / c1 / c2** (target f14 / f16 / f18). One `c` reused gives a single LR.
  - With the pooled setters in place, **pos / vel go back to plain `set()`**. Run 727's set5 dummy now costs 10
    diffs.
- **Frame.** `{ int sc[1]; sc[0] = 0; }` at function scope adds one dead word above the loop block. Everything from
  sp+224 up then matches (a1 / a2 temporaries 320 / 308, w 296, u 284, a1 272, a2 260), but the frame is 376
  (target 368). Below sp+236 the inline-expansion temporaries are 8..12 bytes high:
  - op= copy: 196 vs 188;
  - a1 op* r's: 180 / 164 vs 168 / 152;
  - a2 r's: 124..144 vs 116..136.

  Needed: dead words +2 between w's op* temporary (224) and the op= copy, +1 below the copy, -1 above a2's pair,
  and -2 at the bottom. The bottom dead words include the colour block's four named floats: moving them to the loop
  block moves the whole lower region down 16.
  - No effect on the lower region: `if (0)` statements (they add words at the top), zeroN dummy pointer params,
    setK / mulK extra dummy float params in the w / a1 operator* (they change colours).
- **0x64B8 (not beaten; NCC donor stays 99.91 % in the report).** Tried taking op*1's scalar out of an inline
  parameter on the mp72 s1 draft:
  - `const float &s` / `const float *s` (a member, or a global operator*) forces k into memory: 95 / 94 %.
  - `mf(x, s)` single-return float inlines inside op*1: identical bytes (the s word is still the method's).
  - An explicit `SV q; SV::ct3(&q, v.x * k, ..)`: 93 %.
  - `scl(s) { SV r = *this; r *= s; }`: 87 %.
  - set-built / field-store / `if (1) {}` / `mk(a, b, c)` bodies for op*1: no gain. An extra float dummy
    parameter before s rotates the colours (f12 / f14 / f2), so op*1's word choice really is pool rotation.
  - Both donors share a second leftover: target `lw v1,44(s0)` / `addiu v1,v1,792` (op*1's `this` pointer word in
    v1), ours v0. zeroN dummy pointer params (1..4, at three positions) do not move it.
- Also tried for the lower region, no gain: `SVb w = ..` initialisation (95.4 %), a `const SVb &` operator= (97.97 %),
  and a `(SVb)` cast on the w product (bytes unchanged).
- Next for 718C: the lower-region gaps above, one statement's inline at a time. Next for 64B8: the v1 / v0 pointer word (what conflicts with v0 in
  the target: the p / &vFC pointer words at 260..268?).

### snoweffects.uso 0x718C / 0x64B8 under MIPSpro 7.2.1 (agent-e run 727)

- **0x718C NM 97.28 -> 98.14 %** (agent-e 63d6a7ed4 + 7239f185a; gate PASS both times, 3571 / 3579, lost: none, no
  renames). 471 words, and the frame is 368 = target. Scratch `/tmp/claude-1000/agent-e/w727/`:
  - `pv.py`: probe batches with every `addiu x,sp,N` offset plus the |a| colours;
  - `od.py`: standalone objdiff %, which is what the report tracks. A positional diff count does NOT predict it:
    the run's first frame-exact draft had fewer positional diffs and a lower %;
  - `sd2.py`: diff that ignores sp offsets;
  - `p*.py`: the probe batches.
- **The target has the same uopt LR structure as ours. Only the colour order differs.** Every target colour fits
  our word LRs when the y-product word M-156 is coloured after the |a| word M-204:
  - M-152 f2, M-156 f12, M-160 f14 (the x / y / z products);
  - M-204 f0 (|a|, plus a2's first set() c);
  - M-220 f2, M-224 f12, M-228 f14, M-256 f0 (a1's second product and a2's second product);
  - M-28 f16 (|speed| and the scalars).

  Ours had M-156 at priority 50 (100 / 2) against M-204 at 35. The extra M-156 refs came from the pos / vel
  `set()` near the end, whose pooled c reused that word. Two changes fix it:
  - `set5(a, b, d1, d2, c)`: the two unused middle parameters take the next two pooled float words, so c lands in
    the |a| word (M-204 +2 refs, M-156 -2). A named `float cc = c` gives the same colours but costs two frame words.
  - `mulS()`: operator* with `if (1) {}` after set(), used only for a2's first product. The f210 load then starts a
    new block, so M-220 no longer shares a block with M-152 and can take f2. Putting `if (1) {}` in every
    operator* costs the 1.0f constant's callee-saved register (ops +16).
  - lerpF with a named difference `d`, and run 698's `{ int sc[2]; }` pad removed.
- **Frame-offset lever (not kept):**
  - `lerpF(const float &p, ..)` plus a dead `if (0) zero7(&t->cam->v318 x7)` puts every operator* temporary at
    the target's sp offset. A pointer parameter whose argument is a load takes a pooled A word; the four old ones are
    reused, the rest are new. The a1 statement then reuses a new one instead of allocating its own.
  - Arguments like `&w` / `&t->vF0` are substituted and take no word, and a single-expression body takes none either.
  - It lowered the objdiff % (97.21 vs 97.22 standalone), so it is not committed. With set5 the remaining offsets
    are w's temporary / copy (target sp+224 / 236, ours 216 / 228) and a1's (168 / 152 vs 172 / 156). zero6 on top
    of set5 fixes a1's pair only (+0.02 %).
- **Left in 718C:** the w / a1 temporary offsets above, the ramp's lo / r colours (target lo f12, r f2; ours f14 / f12),
  the lerp FP ring, the block-61 u.y / u.z colours, and the colour section (target f = f220 in f2 and the three c's in
  f14 / f16 / f18, so the target has three c LRs; ours has one c in f2).
- **0x64B8 (not beaten, NCC donor 13 diffs = 99.91 %; mp72 s1 99.75 % standalone):**
  - Lever 1 (block-scoped named locals) does not help. z, r, or all of x / y / z / r inside `if (p != 0)`: 17 -> 23
    adiff. A nested block around v's setup: no change. `SV n; n = v - t->pos;`: +9 ops. spd / k declaration order:
    no change.
  - The 718C dummy-parameter trick cannot help here. op*1's s is allocated before ct3's a / b / c, so any pooled
    s takes -20 before them. Locking -20 / -120 / -124 earlier in the statement also locks them for a / b / c. s has
    to be a non-pooled word: a named local whose parameter is substituted, which edg does only for scalar
    single-return inlines.
- Next for 718C: the colour section's three c LRs; the w / a1 offsets (a pointer-word lever that keeps the %);
  the ramp's lo / r colours.

### snoweffects.uso 0x6000+ under MIPSpro 7.2.1 (agent-e run 723)

- **0x6B28 EXACT** (agent-e b7545313f; gate PASS, 3571 / 3579, lost: none, no renames). It is now spliced in both
  build trees from `snoweffects_uso_mp72_nm_e.cpp` (Makefile `SNOW_MP72_E_EX_FUNCS`); 0x718C stays NON_MATCHING-only
  from the same donor. Scratch `/tmp/claude-1000/agent-e/w723/`: `q*.py` probe batches, `sh.py` / `sd.py` diffs,
  and `tr6.sh` / `tr7.sh` (agent-h's instrumented-uopt colouring trace for 6B28 / 718C alone).
- **Lever 1: EDG 2.29 allocates a block's statement temporaries before its named locals.** In the nested spawn
  block, the op+ temporary (vfp-140) was allocated before u (-152), though u is declared in the same statement. The
  target has the temporary at -136, a 4-byte word at -140, and u at -152. That is one word moved from above the
  temporary to between it and u. Declaring z inside the nested block (x / y stay outside) does exactly that. The
  run 718 "one statement must allocate one fewer word" reading was half of it: dropping a word above alone (e.g.
  `x = x + v.x` in op+=, which drops the compound-lvalue pointer word) fixes the temporary but moves u and
  everything below up by 4.
- **Lever 2: the hoisted u-copy address was a block-interference colour.** The trace (`tr6.sh`) showed
  K-180 (`lda` of op+'s return temporary) forbidden v0 / v1 by the &vFC / &vF0 ranges in the same uopt block, so
  it took a0, and as1 hoisted the `addiu a0,sp,52` to the block top. A code-free `if (1) {}` before `return r` in
  SVb operator+ ends the block after set(). The range then colours v0, and the `addiu v0,sp,52` stays after the
  last &vF0 use, as in the target. Also tried: ct0 after set (71 diffs), `return *ct0(&r)` (71), ct0 only after
  set (89).
- **0x718C (not beaten, 97.28 %).** `instrumented-uopt` reading, in actual registers (ord.py's FP labels are one
  register high: its `f2` is f0, `f14` is f12):
  - M-28 is one uopt LR over 16 blocks. It holds the three `|sp|` `?:` values, then (word reuse) the op* scalars of
    the w / a1 statements and lerpEach's r. Ours colours f12, forbidden {f0, f2, f14}. The target has the whole LR in
    f16 (|sp| at 0x37, f208 / f20C loads at 181 / 210), so f12 must also be held by an interfering earlier pick.
  - In the a1 statement, the `|a|` `?:` temporary takes a fresh word (-200). Set's c parameter then reuses it
    (first allocated in this statement, so it is freed). In the target, |a| is f0 and the three products are
    f2 / f12 / f14, so the target's |a| word is NOT set's c. That LR membership is the lead.
  - Flat or worse: lerpEach `const float &r` (|sp| still f12, lo f14); dead `if (0) u *= r` before / after lerpEach;
    a `float rr = r` copy; named `aa` for |a| (decl / assign / in-expression; +35 ops); dead `if (0) w *= |a|`,
    a duplicated `if (0) w *= f20C`, and `w = w * ..` (frame +16); a friend `float * SVb` (227..388);
    `as` |sp| locals (243); decl order of a / sp / r (no change).
- **64B8:** not attempted this run. Lever 1 (block temporaries before named locals) is untested there.

### nameent.uso 9BC + snoweffects below 0x6000 (agent-c run 655)

- **nameent 21 / 21 EXACT** (agent-c f56621038; 3539 / 3579). 9BC's two scale spill slots were one edg
  temporary word too many. Both the inline `Colour::set()` on `col` (its `this`) and the `+=` on `self->fD0` (the
  lvalue address) take an edg temporary, and they share one frame word. To find it, dump uopt's var list with
  `-Wo,-zdbug:6` (the `isvar M 20 <off>` lines after REDUNDANT STORES): it showed `-80` stored first with `&col`
  and later with `self + 0xD0`. Fix: four member stores, `x = x + k`, and a second dead `scratch2 = 0` word.
  9BC also moved ahead of E44 in the donor, so both `_rodata` pins are 0.
- **0x270 NM 245 / 260** (donor `src/snoweffects_uso/snoweffects_uso_ncc_c.cpp`, Makefile block `SNOW_C_DONOR` /
  `SNOW_C_NM_FUNCS` at the end, NM-only). It is the 0x15D0 texture-sprite family with the render state first.
  - The target loads the 32 for w / h inside the prim-colour packet, not at the entry. A `w = 32; h = 32` pair
    becomes a hoisted constant LR at the block start; one `if (1) {}` before the prim-colour packet plus
    `t->w = 32; t->h = t->w;` keeps it local. With that, the whole first half matches, including E7 in t1 and
    F568 in t2.
  - The two size statements must sit on separate source lines: on one line they come out h, w.
  - Left: five texture-load packet pointers (live-unit colouring, as agent-h's family).
  - Flat: next / named-local next / three more spellings per packet, `if (1) {}` anywhere else, setSize inlines.
    Any second block split changes the as1 schedule of the first half, which then loads each packet's constant
    one packet early.
- **0xC90 NM 82.9 %** (same donor): the particle sprite draw.
  - Sequence: texture DL call; view matrix from camera +0x30. Then per particle: pos * the gGfxLib world scale
    (+0x128) through column 3 of the matrix, cull against near / far +0xAC / +0xB0 and the half-screen box.
  - Packets: prim depth EE (RoData+0x4 scale), env colour FB (alpha +0x50), `drawn++` (+0x44), then the stock
    gSPScisTextureRectangle with steps `((texW << 10) - 1024) / w`. Render-state reset at the end.
  - The camera is `*(gGfxLib + 0x254)`. Each world-scale word is its own 0-pin (`snow_gfx_scale_128..130`), so
    every load keeps its own lui; the `&snow_gGfxLib + 0x128` spelling gets CSE'd.
  - Left: float colouring and the frame (384 vs 400).
- **0x28E0 decoded, draft only (objdiff 74 %, under the NM threshold, not spliced)**: the snowfall draw.
  - Integration: `p->pos += (cam - lastCam) * follow`, where cam is camera +0x70 pos * the world scale,
    lastCam +0x98, follow +0xA4.
  - Wrap in camera space (the rotation matrix from camera +0x70 + 0xB4): x / y to +-30, z to -100..0, along the
    box axes +0x50 / +0x5C / +0x68. A y wrap re-rolls alpha: `fadeChance < sys_randf()` sets it to `fadeIn ? 1 : 0`.
  - Draw: flakes with alpha > 0 (counted in +0xBC) are drawn with the 0xC90 projection as EE + texrect; size
    comes from +0x38, prim colour from +0xC0.., and the first call runs the 0x39C4 fill (+0xB4 flag).
  - Frame levers: put the function-scope scalars above the two matrices (m at vfp-116, rot at vfp-180), and
    write the motion as one expression with by-value `operator*` / `operator+=` parameters (the target's two
    three-word copy chains); mnemonics went 76.8 -> 82 %.
  - Left: frame 504 vs 520 (the temps' order) and float colouring.
  - Splicing it needs `snow_ro_10 = 0x10`. The body must stay <= 793 words, or 0xA8D0 passes TRUNCATE_TEXT and
    the gate fails.

### snoweffects.uso 0x28E0 / 0xC90 (agent-c run 667)

- **0x28E0 NM spliced: 74 -> 88.9 % (objdiff), frame 520 as the target** (commit 1d2827e48 on agent-c; gate PASS,
  3554 / 3579, no renames). Body 792 words. Three levers:
  - `SnowV3d &last = self->lastCam;` (a reference local) and `cam - last`. The target hoists `addiu t4,s1,152` out of
    the loop and spills it to the frame bottom across the randf call. A direct `self->lastCam` operand folds into
    `lwc1 152(s1)`. Effect: 74 -> 76.
  - operator- returns a constructed `SnowV3d(a.x - b.x, ...)` (a ctor added to SnowV3d) and `+=` takes a const
    reference. This gives the target's store / copy schedule for the op- chain. Effect: -> 78.
  - **Code-free uses keep values computed early:** `if (cz) {} if (cy) {} if (cx) {}` right after the three
    camera-space coordinates. Without them uopt sinks cy / cz into the branch blocks of the wrap tests, but the
    target computes all three before the first compare. Effect: -> 88.9 (mnemonics 87.5 -> 95.1).
    - The reverse order (z, y, x) is +0.7 over x, y, z.
    - Only one or two of the three: 80-82.
    - Not this: `if (cx || cy || cz) {}` (81.7), `if (cx + cy + cz) {}`, `do {} while (0)`, `if (1) {}`,
      `while (0) { cx += 1; }`, function-scope cx..cz.
    - A struct local `SnowV3d cp` (81.3) stays partly in memory.
  - Left:
    - c and halfW lose their s2 / f30 homes and spill. The target also keeps &gGfxLib in s3. The extra `if`
      blocks lengthen their live ranges, which lowers their priority.
    - The temps' slot order inside the frame. Target, top-down: += param, op* param, op- return, op- r, 4 words,
      op* return, op* r. Ours puts the op* / += copies lower.
    - `__V` ctor temps show up in the `-g3` .mdebug list as named locals of the block. A const-ref `+=` puts its
      bound temp first in the loop block, at vfp-212.
- **0xC90 frame 400 reached in a draft, not committed** (/tmp/claude-1000/c667/keep/cq9.cpp).
  - With these, every key slot lands where the target has it: m -104, halfW / halfH -108 / -112, v -180, scaled
    return -196, scaled r -208, bottom spill -312.
    - Hoist inv, k, h2, hgt, sx, sy, wid, x0 to function scope above m (w stays in the loop block, right after v).
    - Add a dead `int scratch[9]; scratch[0] = 0;` after p.
    - Drop the three float parameters of `scaled()`: read the scale words inside the inline.
  - Cost: the in-inline scale loads change the schedule (objdiff 82.85 -> 80.7, mnemonics 92.1 -> 90.2).
  - With the scale parameters kept (cp9.cpp), the frame is 416 and r sits 3 words low; objdiff stays at 82.85.
  - objdiff's fuzzy score did not move with frame offsets in any C90 probe.
  - The target also uses s3 for the hoisted &return-temp (sp+204) and `ra` as a scratch register; ours does not.
- **0x270 not worked this run** (still NM 245 / 260, objdiff 99.7).

### snoweffects.uso 0x270 / 0x28E0 (agent-c run 674, no commits)

- **0x270 (15 differing words, positional): not cracked. Best 14.**
  - **Invisible busy registers are copy-source LRs.** A named-result append (`Gfx *g = &dl->buf[n]; return g;`) makes
    a separate LR for g, with one def and one use. The use is the copy into the macro's `_g`, and that copy is
    folded away, so g's register never shows in the code. In one dump (stock macro + nextN on some sites) this LR
    was M-108, coloured t0, with the def in unit 7 and the use in unit 8. No t0 appears anywhere in the output.
    - This fits the target's 0x270, where E7 / F568 sit in t1 / t2 but no value uses t0.
    - It also fits agent-h's 15D0 report: a1 busy in every unit, with no visible a1 value.
    - What follows: choose next / nextN / nextR / nextI per site to place the hidden holders.
  - **Put phantoms in a data word, not in the packet pointer.** `(t->dl->next() + (t->q & 0))` drops one use of the
    pooled ctx temp (M-8: num 45 -> 44). That breaks the three-way v0 / v1 / a0 pool tie, and the whole function
    re-colours. Phantoms in a w1 or immediate argument leave the tie alone.
  - **The stock 2.0I `gDPLoadTextureTile` macro** (one pkt per sub-packet) changes the second-half sequence and moves
    E7 / F568 to t0 / t1.
  - **Search run.** A random hill climb, about 10k compiles, over:
    - per-site next / nextN / nextR / nextI;
    - 0-3 phantoms in each packet's data word;
    - the w / h position (before or after the `if (1) {}`) and `h = w` vs `h = 32`.

    Both the macro form and the hand-expanded form plateau at 14 / 15. Every 14 still has 3 packet pointers wrong
    and the constant pair swapped.
  - Tools in /tmp/claude-1000/c674/: dd.sh (NCC compile plus a positional word diff), tr.sh (instrumented colour
    order for one function), pk.py (packet-pointer sequence), and g/s3.py with tmpl3 / 4 / 5.cpp (the search).
- **0x28E0: c loses s2 because of a cost tie, not a priority problem.**
  - c (M-16) crosses the loop's randf call, so t1..t5 / ra each cost 15.
  - The s-register cost is 13.5 without the empty ifs. Each conditional block added in the loop raises it by 0.5:
    one `if` 14.3, two 14.8, three 15.0. With all three ifs it ties at 15, and the tie goes to t1, the first in
    register order. Without them c is s2 (run 655 draft).
  - A `* 1` priority lever cannot fix a cost tie. `c = (GCtx *)((int)c * 1)` does nothing, and `if (c) {}` adds
    0.5 more.
  - Next: remove one loop block somewhere else (s-cost 14.5), or find a block-free spelling that keeps cy / cz
    computed early.
  - halfW / halfH (M-20 / M-24) are split before colouring; their pieces are never coloured. `halfW = halfW * 1` emits a
    mul.s (+5 words, 87.07), because float `* 1` is not folded. The int lever does not carry over to floats.
  - **Flat** (objdiff 28E0):

    | Variant | objdiff |
    | --- | --- |
    | two-block forms, e.g. `if (cz != cy) {} if (cx) {}` / `if (cz == cy \|\| cx) {}` (cy / cz sink again) | 82.5-83.1 |
    | ternary wrap amounts | 81.1, or 85.1 with the ifs |
    | ternary fadeIn | 88.16 |
    | inline `snowWrap(cx, cy, cz, &wx, ...)` with by-value coordinates (c goes back to s2, but +9 words) | 78.7 |
- **0xC90: not reached.**

### snoweffects.uso 0x28E0: the `+=` temp order (agent-e run 753, research only, no commits)

- **Recipe (C* above C-, as the target).** Make the op* result a named `SnowV3d t` declared in a new block that
  wraps the loop, and assign it inside the `+=` full-expression with the implicit (trivial) copy assignment:

  ```cpp
  struct SnowV3d { ... SnowV3d &assign(SnowV3d o) { x = o.x; y = o.y; z = o.z; return *this; } };  /* was operator= */
  ...
      {
      SnowV3d t;
      for (i = 0, p = self->items; i < self->count; i++, p++) {
          p->pos += (t = (cam - last) * self->follow);
          ...
      }
      }
      self->lastCam.assign(cam);   /* byte-identical to the by-value operator= (checked) */
  ```
  - On the d17635bb7 donor: 793 words, frame 520. All six temp slots match the target: C* -268, C- -280, op- copy -292,
    op- ctor -304, op* copy -332; r stays at -348, which is the separate pooled-word issue. objdiff 94.997 -> 95.008.
    Draft: /tmp/claude-1000/agent-e/w753/keep/28E0_e10_tassign_793w_95.008.cpp.
  - On agent-c's c749/v/r1_2.cpp lead: 794 words, frame 520, M 400 (the t4 spill at 116 as the target), and all six
    slots match the target **including r -344**. Positional diffs 451 -> 443.
    Draft: /tmp/claude-1000/agent-e/w753/keep/28E0_r12u_tassign_on_r1_2_794w.cpp.
  - Still left in this area: the two hoisted copy addresses take swapped registers. Ours: ra = sp+228 (op- copy),
    t5 = sp+188. Target: t5 = 228, ra = 188.
- **Why no operator signature / body works (toy compiles + the ugen Build-tree dump):**
  - Within one full-expression, edg 2.19 allocates the reference-binding temps in post-order: an inner call's temp
    gets the higher address. A call's own arguments bind right to left: `g3(a, b, c)` puts c on top, then b, then a.
    So the nested `+=(op*(op-))` chain always puts C- above C*.
  - About 30 forms tried, all C- first:
    - member / friend / free operators;
    - const-ref / by-value / non-const-ref parameters;
    - a template op*, an op- returning a derived type, `const V` returns;
    - inlines defined after the function;
    - an empty dtor or a user copy ctor;
    - `(V)` / `(V &)` casts, `operator*(...)` call syntax, `-(last - cam)`, a `?:` operand.
  - Helpers such as `sc(cam, last, k)` do put C* first, but they add a return-copy chain.
  - Temps of later statements in a block get higher addresses than earlier ones (3-statement toy). A block's named
    variables come after its temps.
  - Inline return copies are pooled per type and reused across full-expressions. A two-statement form
    (`V d = cam - last; p->pos += d * k;`) therefore shares one copy slot between op- and op*.
- **Why each part of the recipe is needed:**
  - **Implicit assignment into a named object** copies op*'s return copy straight into t: two moves, the same as the
    caller-temp chain. The user `operator=(SnowV3d o)` hijacks `t = ...` and adds a copy chain (798 words, frame
    528), which is why it is renamed to `assign`.
  - **The wrapping block** places t after the pre-loop snowW / gDPWord inline blocks, at -268. A t declared in
    function scope, even just before the `for`, lands at -236 (the code is otherwise identical, but t reads at -236).
  - **One full-expression.** `t = ...; p->pos += t;` gives the right slots but loses 3 nested-inline pool words
    (M 396, frame 512). `p->pos += (t = ...)` keeps the target's pool depth (frame 520).
- Tools in /tmp/claude-1000/agent-e/w753/:
  - ud.sh: compile any .cpp and run the ugen tree dump;
  - sig.py: temp copy-chain signature;
  - slots.py: M-slot map;
  - roles.py: frame-relative op- / op* chain slots from the disassembly;
  - var*.py: the toy matrices;
  - ev.sh, fz.sh, vn.sh.

### snoweffects.uso 0x28E0: loop-top colours and the m offset (agent-e run 767, research only, no commits)

- **Draft (793 words, frame 520, objdiff 96.110 -> 96.198 against main's 8f75b8d5d donor):**
  /tmp/claude-1000/agent-e/w767/keep/28E0_e767_b3_793w_96.198.cpp (diff: `28E0_e767_b3.diff`). The code up to the
  draw block (rows 90-483) is now the target's except for sp offsets in the temp area. Three changes, none of them
  code:
  ```cpp
  static inline int zf1(float v, int z) { return z * (int)(v); }
  static inline int zf3(float v, int z) { return z * (int)(v + v + v); }
  ...
      if ((cy != 0.0f) + zf1(cx, 0)) if (cz) {}        /* was: if (cy) if (cz) {} */
      if ((cz < -100.0f) + zf3(cz, 0)) {                 /* was: if (cz < -100.0f) */
  ...
      SnowDLHolder2 *tex;                                /* declared last (after wx), not after d */
  ```
  - **Loop-top cx / cy / cz (issue 2) fixed: f0 / f12 / f2, computed in the cx, cy, cz order.** The loop-top values
    are copy-propagated expression temps (uopt LRs e7 = cx, e62 = cy, e1307 = cz), not the variables. `zf3(cz)`
    lifts cz from 7.5 to 15.0, which ties cx (15.0; cx wins on order), so cx takes f0, cz f2 and cy (13.3) f12.
    zf4 (17.5) gives cz f0 instead; zf1 / zf2 change nothing. The `zf1(cx)` in the first empty-if condition puts a
    cx use in the first test block, so cx is computed before cy, as in the target (before this, the sums came out
    cy, cx, cz). The fold has to be the whole if condition. `(a) + zf(..)` as the first operand of an `&&` changes the
    code (+4 words).
  - **m / rot offsets (part of issue 1) fixed.** The extra M word above m was `tex`, which run 759 added. Declared
    last, tex keeps its v0 code and m / rot land on the target's sp+404 / 340. Inner-block scope does not help: the
    word is still allocated.
  - **Still left in the frame:** the op- / op* temps (sp 164-256) and the t4 spill (108, target 116). Spill offset =
    frame - M - 4. Removing the tex word entirely (`lp = (SnowV3d *)self->tex; d = gl_func(((SnowDLHolder2 *)lp)->dl);`)
    gives M = 400 as in the target, but then the frame is 512, not 520. The target has 8 more bytes **under** the
    spill (sp 88-115, against our 88-107). So it needs M = 400 plus two more low temp words (uopt spilltemps), not a
    different M.
- **1/w f14 (issue 3): not solved.** Target draw colours are cx f0, depth-w f2, cy f12, 1/w f14. uopt interference
  is per block, and cy (blocks 45-49) does not overlap depth-w (blocks 42-44). So cy takes f2 whenever it is
  coloured before 1/w, and 1/w then gets f12. Sweeping the zf weights on the nearZ test, the sw / sz index, the
  offX / offY index (about 250 compiles, all 793 words) only permutes {f0, f2, f12}. cy needs an f2 neighbour, which
  means a cy reference in block 44 (with depth-w) that costs no code. A cy fold in the sz index adds about 19 words
  (812). Next: find a block-44 cy reference that costs no code.
- **Side findings:**
  - Moving the two row sums before sw / sz (`w = 1/w; cx = row0; cy = row1; sw; sz; ...`) is **791 words** (-2),
    but the schedule changes (93.1 %). It is a word budget, if one is needed later.
  - EE through gDPWord on the b3 draft: 793 words, mnemonic diffs 21 -> 18, but frame 528. It is frame 520 with
    the lp-for-tex trick (95.91 %). The w0 store is still early (the target stores w0 after the depth).
- **Draw-z note (before agent-c's run 763 fix):** in the all-z form, the draw cx / cy definitions are
  copy-propagated: `cx = E`, and E is all variables, so the compare uses become an expression temp, and the
  variable keeps only a dead `mov.s`. A dead second definition stops this. agent-c's two-step `cx = row; cx = cx *
  ..` is that second definition with no code. `if (zf1(w, 0)) w = 0.0f;` also works, but its block costs c's s2
  (+3 words).
- Tools in /tmp/claude-1000/agent-e/w767/:
  - ev.sh: compile + score;
  - mk2.py: builder with zg0..12;
  - col.py: draw-block div / cx / cy registers;
  - nr.py: positional diffs, ignoring sp offsets and branch targets;
  - t4-t14.py: sweeps.

### snoweffects.uso 0x28E0: the frame words and the snowW tail (agent-e run 775, research only, no commits)

- **Draft: 97.957 -> 98.077 (793 words, frame 520, mn 2 / reg 199 -> 176, positional 260 -> 237).**
  /tmp/claude-1000/agent-e/w775/keep/28E0_e775_o1_793w_98.077.cpp (diff against main: `28E0_e775_o1.diff`).
  Standalone NCC + objdiff only; check it in-tree before landing. Four edits on main's source:
  1. **tex goes through lp** (run 767's trick): `lp = (SnowV3d *)self->tex; d = gl_func_00000000(((SnowDLHolder2 *)lp)->dl);`.
     The tex declaration goes away. Edg M drops 404 -> 396, and the frame drops to 512 on its own.
  2. **B4 and BB go back to gDPWord** (from snowW). Each one adds an edg word, so the frame is 520 again. With
     both, the sp-offset set equals the target's everywhere except r and the spill: the ctor at 216, the op- copy
     at 228 (t5) and the op* copy at 188 (ra) now match. BA through gDPWord (98.048) or B4 alone (98.010) also
     help. Three of them push the frame to 528.
     Most of the reg gain is the v1 / v0 DList pair: the snowW sites put the dl pointer in a2 and the count in v1
     (rows 84-89, 632-635, 657-660, 756-759, 769-772). The gDPWord sites match the target.
  3. **Run 753's t-assign recipe** (`{ SnowV3d t; for (..) { p->pos += (t = (cam - *lp) * self->follow); .. } }`,
     operator= renamed to `assign`, `self->lastCam.assign(cam)`) now swaps C- / C* into place: C- at 240, C* at 252
     (98.077). On main's frame it was byte-inert, because there the slots were shifted anyway.
  4. **`operator*` as `{ SnowV3d r; r.set(..); return r; }`** (was the comma form). Same score, but edg M is now
     400, and the t4 spill moves 108 -> 112 (target 116).
- **The "8 bytes of low temp space" are uopt spilltemps, not ugen temps** (kit CCXCIII). Evidence:
  - `-S` shows no access in sp 88..115 except the t4 spill.
  - The FE's M (ugen dump `def mtype=M`) plus six spilltemps plus the 88 save bytes gives the frame.
    The six spilltemps come from `tm.sh` = `-zdbug:4` + a spilltemps simulation (`tw2.py`).
  - Main has 9 coloured items in 6 temps:
    - T0 = item 7, the SNOW_CAM2 load (`uilod &gGfxLib+0x254`), shared with 251 (the loop-top cx sum);
    - T1 = item 129 = &self->lastCam (lp, the t4 spill);
    - T2 / T3 = cy / cz sums with the draw-block w / cx sums;
    - T4 / T5 = -halfH / -halfW.
  - So **lp sits in T1 because item 7 comes first in bit order and overlaps it.** The target's spill at vfp-404
    needs one of:
    - M = 400 with lp in T0;
    - M = 396 with lp in T1 and 8+ temps;
    - M = 392 with lp in T2.
  - The target's r at -344 (ours -348 in the draft) points to M = 400. Then lp must be T0: item 7 must not be a
    coloured item, or it must come after lp / not overlap it.
  - On the draft the only sp differences left are r (172 vs 176: one word between r and the op* copy) and the
    spill (112 vs 116).
- **The draw-block cx row sum (agent-c's e45) is also the FP ring offset:** the target computes it in a ring temp
  (`add.s f8`), so every FP ring row after it is one off. `cy = .. * -halfH + zf1(cx, 0)` (which costs 3 words) adds
  ring temps that realign rows 568-625 completely (98.00 at 794 words). That confirms the ring map: remove e45 and
  the x0 / y0 / EE rows line up.
- **Negatives:**
  - The one-step cx / cy forms (g1 / k1 / k3: cy sinks into compare block 2, 792 words, mn 29). Neither
    `if (zf1(cy, 0))` nor a `(-halfW < cx) + zf1(cy, 0)` nested if (795 words) fixes it.
  - 1/w in a dead float (wz / wy / wx) with a `zf1(w, 0)` later (797 words).
  - op- as a named r, by-value op* (791 words, wrong).
  - The cz-first swap (agent-c run 773) on the draft: 97.82.
  - `p->pos.z` in both cx / cy rows is 98.17 but 794 words (z's mov.s returns).
- Tools in /tmp/claude-1000/agent-e/w775/:
  - q.py: replacement + score, with frame, spill, mn / reg and non-sp diffs;
  - sps.py: the sp-offset set against the target;
  - lo.sh: FE M from the ugen dump and the frame remainder;
  - tm.sh / tw2.py: the spilltemps map;
  - al.py: mnemonic alignment;
  - wv.py: the 1/w variable sweep.

### snoweffects.uso 0x28E0: the FA v0 block, BA and the r / spill word (agent-e run 786, research only, no commits)

- **Draft (793 words, frame 520), standalone objdiff 98.899 -> 98.916 on main's donor (deab5a229):**
  /tmp/claude-1000/agent-e/w786/keep/28E0_e786_ba_793w_98.916.cpp (diff: `28E0_e786_ba.diff`, one line).
  - The edit: the BA packet goes back through gDPWord (was snowW). BA's dl / count are then v1 / v0, as in the
    target (rows 756-760).
  - Cost: BA's `_g` is one more edg word, so the spill goes back 116 -> 112. Frame and r are unchanged (r is still
    172; the sp-offset set differs from the target only in {r 172 / 184, spill 112}).
  - The word should come back from operator*'s `a` param word (-336, sp 184, between r and the op* copy; agent-c
    run 782's lead). If that word goes, r moves to 176 and the spill to 116, both as in the target, with BA on
    gDPWord. So the target probably has BA's `_g` word and no `a` word.
  - Tried for the `a` word, all inert (same bytes, same 172 / 112):
    - `s` first (`self->follow * (cam - *lp)`);
    - op* as a member function, and as a `.mul(s)` member;
    - a named `mulv()`;
    - op- with a named r.
  - Tried for the `a` word, all broken: `const float &s` (796 words), by-value `a` (790), `return SnowV3d(..)` (791),
    `t = cam - *lp; t *= s` (774).
- **Draw-tail dl / count: who forbids v0 at FA.**
  - `-zdbug:5` LR dump: the precoloured **R2 LR is live through blocks 7..8** (`d=[2,4,7..8]`, use in block 6 = the
    06 packet). Blocks 7..8 hold the int-returning `gl_func_00000000(SNOW_CAM2->view, m)` /
    `(SNOW_CAM2->obj->rot, rot)` calls and the FA packet.
  - Fix: void-type the two calls (`extern "C" void gl_func_00000000_snow_v(...);`). R2 then shrinks to `d=[2,4]`,
    and v0 is free at FA. Alone, this is byte-inert on main.
  - With FA on `next()`, the FA count joins the draw-tail count word (M-228) and the dl joins M-232. At FA, M-232
    now spans blocks 8 and 47..56, and M-228 spans 8 and 48..56. The priorities are num/den with den ~ units/2:
    M-232 is 135/3 = 45 and M-228 is 105/3 = 35. M-232 is coloured first, takes v0, and the dl / count come out
    v0 / v1: swapped. With int calls, R2 forbids v0 for both, so you get v1 / a0 (agent-c's observation).
  - FA through `next()` also drops nextN's `n` word (frame 512). A referenced pad `int padw; (void)&padw;` restores
    520 / 116 at no code cost (unused pads are dropped), but it scores 98.61.
  - The target's FA (dl v1, count v0) needs the count word coloured before the dl word with R2 out of the way, or an
    FA-only dl word.
  - `nextS()` (`int n = dl->count; dl->count = n + 1; return &dl->buf[n];`) gives FA dl v1 with int calls, but count
    a0 (R2). An `if (1) {}` before `halfW` puts FA in its own block, out of R2. Its words are then single-block
    ties, so the dl expression wins v0.
  - **Side effect: SNOW_CAM2 (e881) is t0 only because nextN's / nextM's pooled word M-240 holds a2 at FA and E4.**
    Every FA / E4 form without it moves SNOW_CAM2 to a2 (rows 16-68, 490-574). In the target, x0 is a2 (row 602,
    ours a3), so the target's a2 block for e881 is probably x0. That also needs E4 off nextM.
- **x / -halfH (draw f16 / f18 swapped):** in the m2 dump, draw x (M-44, blocks 40 / 42 / 48) is pri 60/3 = 20, f16.
  -halfH is the CSE expression e381 (blocks 40 / 42 / 47), pri 50/3 = 16.7, f18. The fix needs e381 > 20 or x < 16.7.
  agent-c's `zf1(-halfH, 0)` works through a new pooled float word (M-284 = zf1's `v`), not through e381, which is
  why the loop-top x / wx move. Moving x's uses between `x` and `p->pos.x` (w / cx / cy / cz rows) breaks the code
  (789-800 words). Not solved.
- **Climbs:** per-site append (next / nextR / nextN / nextM / nextB / nextS / nextU) x gDPWord / snowW x void-call
  flags x pads. About 1000 compiles, greedy from 3 starts; the only gain is the BA line. Every gain that needs the
  pooled-word layout changed is masked by the frame / word coupling.
- Tools in /tmp/claude-1000/agent-e/w786/:
  - q.py / ev.sh: replace + score;
  - nd.py: positional diff (`1` = include sp rows);
  - tr.sh TAG: the `-zdbug:5` LR dump, giving `iu/TAG/x.lr` / `x.ord`;
  - hc3.py: the per-site climb;
  - u.py;
  - fbase.cpp: main + nextS..nextW + the `_snow_v` decl.

### snoweffects.uso 0x28E0 NM 98.94 -> 99.02 (agent-c run 787)

- **Two commits on agent-c**, gate PASS each, 3577 / 3579, exact set identical, no renames, 793 words, frame 520:
  - 13094d5af: 98.97 (r at sp+176; every sp offset now equals the target's);
  - 65f13a71f: 99.02 (all FP colours up to the draw tail match).

  Scratch: /tmp/claude-1000/c787/ (`q.py` / `ev.sh` / `nd.sh` = diff that ignores branch targets; `lm.sh TAG` =
  edg M map below -256; `st.py TAG` = the `+=` statement's word allocation sequence; `sps.py TAG` = sp-offset set
  against the target in M space; `tr.sh` / `tm.sh` as run 782).
- **r: edg releases an inner inline's fresh param words when the inline ends; old pool words stay locked.**
  `st.py` on the `+=` statement: op- takes the four old A pool words (a, b, the ctor's `this`, set's `this`), so
  op*'s `a` had to be fresh (-336), between the return copy and r. With the ctor calling a single-return
  `SnowV3d &set3(a, b, c) { return (x = a, y = b, z = c, *this); }`, set3's result takes the old -244 and its
  `this` a fresh -308 word; that word is released when set3 ends, so op*'s `a` reuses it and r lands at -344.
  The layout under -304 is then 3 R + 1 A word, which is run 749's "3 ctor R params and one unused word".
  M drops to 396; BA through gDPWord adds the `_g` word back (M 400, frame 520, spill 116). This is what agent-e
  run 786 predicted.
  - Ctor `{ x = a; y = b; z = c; }`: a reuses -244, but s goes fresh (the ctor's R params stay locked), frame 528.
- **x / wx: the draw-block x def put x's uopt LR into block 40, where the p->pos.x load item (e381) is also
  live, so they could never share a register.** The target has both in f18. Fix: carry the draw x in wx
  (`wx = p->pos.x; w = m[0][3] * wx + ..`); wx is dead in the draw block. x's LR then ends at the wrap blocks.
  With run 782's `zf1(-halfH, 0)` fold on the third compare, wx now outranks y / z (90/6 = 15.0 vs 14.29) and
  steals f20; `+ zf1(y, 0) + zf1(z, 0)` on the first loop compare lifts y / z to 15.7. Result: x f18, wy f16,
  wx f24, -halfH f16, draw x f18, as the target.
  - Other carriers: wy / wz / cz keep the loop-top swap; cx / w change the code (794 words, frame 512).
  - **Single-LR x (cx / cy / cz rows on plain x) with a dead-def copy-keep `if (zf1(x, 0)) x = 0.0f;` before the
    draw compare** stops cy's copy-propagation (agent-g run 781's lever) and also fixes x / wy (with zf4(wy) in
    the axis index), but it loses the e381 spilltemp item: 6 temps, frame 512 (98.13). The target has the e381
    item, so its x is not one LR.
- **Left:** the int draw-tail rotations (dl / count a2 / v1 vs v1 / v0 at rows 85-90 and 633-639; t8 / t9 for
  self->visible; a0..a3 / t0 in the packet appends and the tail packets, rows 633-780), the offX / offY index
  (`16(at)` vs `0(at)`, row 619) with the FP ring at rows 614-621, and the B3 div ordering at rows 683-699.

### snoweffects.uso 0x28E0: spill 116 (agent-c run 782)

- **One commit on agent-c: 76cd5df08, objdiff 98.939 -> 98.942** (793 words, frame 520, mn 2 / reg 104 -> 102).
  Gate PASS, 3576 / 3579, exact set identical, no renames. Scratch: /tmp/claude-1000/c782/ (`q.py` / `ev.sh`
  as run 778; `tm.sh` = agent-e's spilltemp map on this tree; `lo.sh` = FE M; `tr.sh` = the run-414 colouring
  trace; `cd.py` / `pair.py` = append-spelling descent; `hf.py` / `lt.py` = fold sweeps).
- **The spill is fixed (sp+116, target), confirming agent-e's run-775 model.** The spilltemps are handed out in
  uopt item-index order, and the item index is the order of first appearance in the code. `lp = &self->lastCam;`
  as the first statement (before `cam.x = SNOW_CAM2->..`) makes the lp address item 7 and SNOW_CAM2 item 14, so
  lp takes T0. M stays 400, ntemps 7.
  - Side effect: lp's pick now ties i's (both pri 2.583) and wins on index, so lp took t3 and i t4. A dead
    `i = 0;` before it gives i the lower index again (t3 / t4 as the target).
  - tex can no longer go through lp, so it goes through d: `d = (int)self->tex; d = gl_func(((SnowDLHolder2 *)d)->dl);`
    (v0 as the target; p / x0 / i as the carrier cost 11-13 reg).
  - Other routes, all worse: a separate SNOW_CAM2 item in the draw block (`(SnowCam2 *)*(int *)(..)`) also gives
    spill 116, but the top item loses the draw-block interference and moves t0 -> a1 (reg 116). A named
    `SnowCam2 *g` re-read at each site keeps t0 everywhere, but its home makes M 408 (spill 108); reusing d / y0 /
    sz / sw / x0 as the carrier drops a spilltemp (frame 512).
- **r (sp 172, target 176) is the op* `a` parameter.** In the ugen dump the op* expansion allocates the result temp
  (-332), then `a` (A, -336, a fresh word), then r (-348). `s` reuses the R pool word -308. The target has r
  directly under -332, so `a` must not get a fresh word before r. Not fixed by: a member `operator*(float) const`,
  swapped parameters, `const float &s`, a pointer copy of `a`, by-value `a` (790 words), op- in any of its forms,
  or splitting the statement.
- **x / -halfH:** a `zf1(-halfH, 0)` fold on the third compare (`(-halfH < cy) + zf1(-halfH, 0)`) or on the offX
  index gives the target's draw-block pair (x f18, -halfH f16). But the loop-top x and wy then swap (f18 <-> f24),
  so reg goes 102 -> 108. No second fold among about 200 (loop-top compares, wx / wy / wz ifs, axis index, the
  run-778 hc.py sites) repairs the loop top. The draft is /tmp/claude-1000/c782/b7.cpp.
- **Draw-tail int rotation:** pool-word identity, not priority. At FA (nextN) the pool words are -228 `this`
  (v0), -240 dl (a2), -232 count (v1). The target needs count in the v0 word and dl in the v1 word, which is the
  layout E7 / B9 get from `next()`. With `next()` (or a macro / free-function append) at FA, the -228 word holds
  the count, but its LR gains a unit where v0 is forbidden, so it gets a0 (reg 177). No single-site or
  06/FA-pair change among 11 spellings, including agent-h's C90 `n + zc(0) * n + zc(0) * (n + n)` forms, beats
  the base. The forcing uopt (h416) aborts when bp 0 is forced to v0..a0.

### snoweffects.uso 0x28E0 NM 97.96 -> 98.94, frame 520 (agent-c run 778)

- **Three commits on agent-c**, each with gate PASS, 3576 / 3579, the exact set unchanged, and no renames; all 793
  words, frame 520:
  - fd6cd4063: 98.50;
  - 20ebd80a3: 98.88;
  - 64de17b33: 98.94.

  Scratch: /tmp/claude-1000/c778/ (`q.py`, `sw.py`, `hc.py` fold hill-climb, `s*.txt` specs).
- **e45 and cy propagation are both solved with an ilod.** The draw-block cx / cy are now one statement each, as
  in the target (`cx = (row0) * w * halfW; cy = (row1) * w * -halfH;`), and the row sums are ugen temps (f8 / f4).
  - With plain variables, uopt copy-propagates cy's expression into the compare blocks (the 792-word, mn 29 shape).
  - The fix: the cx / cy / depth rows read `m[0][k] * p->pos.x` instead of `* x`. That ilod keeps copypropagate
    from rewriting cy's branch uses, so cy is one register, computed before the first compare. The load CSEs with
    the draw-block `x = p->pos.x` load, so it costs no code. The w row keeps `x`.
  - `p->pos.y` / `p->pos.z` work too, but score lower. Neither the cut before the cx row nor the cz-first swap is
    needed now: the swap is byte-neutral on this base.
- **Ilod blockers that do not work, or cost code:**
  - `float (*mp)[4] = m;`: blocks in-block forwarding only. It works for the two-step form (cx / cy stay single
    LRs, 97.995), but the row sums then live in the variables. One-step + mp is propagated (mp is forwarded first).
  - `*(volatile float *)&m[k][1]`: +1 addiu (`&m` in a register).
  - `+ zf1(p->size, 0)` in cy: the fold leaves `mtc1 zero; cvt.s.w; add.s` (+3).
  - `m[0][1 + zf1(p->size, 0)]`: leaves `sll t6,zero,2; addu t7,sp,t6` (+2).
  - Dead second definitions (`if (zf1(cy, 0)) cy = ..;`, the ref / `?:` inlines): mn 38-52.
- **Base: agent-e's run 775 frame set** (tex through lp, B4 / BB via gDPWord, the run-753 `t = ..` temp with
  `assign`, op* as `r.set(..); return r;`). Stacked with the above, it scores 98.455.
- **Colours:**
  - `+ zf1(halfW, 0) + zf1(cx, 0)` in the EE word fixes halfW / cx / depth (98.84).
  - The size reads go back to a plain `p->size`, with no zf2(w) index, which gives 1 / w f14 and cy f12 (98.94).
- **Left:**
  - Draw-block x is f16 and -halfH f18; the target has them swapped. About 300 single-fold probes found nothing:
    -halfH / x / p->pos.x folds at the compare, size, offX / offY and EE sites, and the row-to-variable mappings.
  - Int t-register rotations in the draw tail. dl / count are a2 / v1 where the target has v1 / v0.
  - The temp area and the spill are 4 bytes low: r 172 and spill 112, against the target's 176 / 116. This is
    agent-e's SNOW_CAM2 spill-slot lead.

### snoweffects.uso 0x28E0: the draw-block e45 temp (agent-c run 773, research only, no commits)

- **No commit; 97.96 stands (793 words, frame 520, mn 2 / reg 199).** About 600 compiles. Scratch:
  /tmp/claude-1000/c773/:
  - `lrq.sh TAG`: draw-block LRs;
  - `nodes.sh TAG LO HI`: per-node `expoccur` from `-zdbug:2`;
  - `perm.py`: statement-order grid;
  - `evr.sh`: `VR=-Wo,-varref,N` diagnostic;
  - `col.py`: cy / depth registers.
- **Item 1 (cy / depth swap) is solved, but the gain is eaten by a cascade.** Swap the loop-top `cy = ..` and
  `cz = ..` statements, so cz's row comes first. The loop-top code is unchanged (only the x / y / z register
  renames below). M-192 (the depth) then gets LR index 253 and M-52 (cy) gets 270, so the depth wins the
  pri-30 tie. Result: depth f2, cy f12, 1/w f14, as in the target. The LR index is set where the variable is
  first assigned in code, not by declaration order. Declaring cz before cy does nothing.
  Draft: keep/28E0_A_czfirst_cy12_dep2_793w_97.70.cpp.
- **The cascade: e45 (pri 15) beats M-284 (-halfH, also pri 15) on index.**
  - e45 now interferes with cy's f12, so it takes f16. -halfH moves to f18, and x / y / z move to f20 / f22 / f24.
  - Net: reg 199 -> 237.
  - `(-halfH < cy) + zf1(-halfH, 0)` in the third `&&` operand raises -halfH (sv 2.0), and -halfH gets f16 back.
    e45 then takes f18 and x / y / z still shift (reg 235).
  - The target has no free callee-saved FP register over blocks 41-42: f28 is the 0.0 constant and f26 the 1.0.
    So e45 must not exist at all.
- **What e45 is:**
  - It is the PRE temp of the cx row sum (base row 534: `add.s f12`, target `f8`).
  - uopt block 41 = 1/w, sw, sz, `cx = row0` (plus the cy-row m loads). Block 42 = the two scalings and the first
    compare. It is a straight-line node pair (varref boundary, kit XXXV).
  - The m[i][j] elements are separate M variables (M-100 / M-84 / M-96 / M-80 ..), so each one is a counted load.
  - The boundary does not move for `-varref` 19..24. It moves earlier at 18 and later at 28.
  - Any order of the six statements (sw, sz, both rows, both scales; 89 orders) compiles to the same bytes.
  - In the target, the cx row sum and the cx scaling are in one block. The row sum is a ugen temp, and cy is
    computed before the first compare.
- **Moving the boundary before the cx row** (+1 counted load in the sw / sz index, e.g. `zf1(halfW, 0)` in both;
  equivalent to varref 18) removes e45. But cy is then copy-propagated into the compare blocks (the 792-word,
  mn 29 shape, reg 196). Neither a dead `if (zf1(cy, 0)) cy = 0.0f;` second def nor one-step cx / cy forms keep
  cy in place. `if (zf1(cx, 0)) cx = 0.0f;` gives 794 words, mn 9: halfH is reloaded at 561, and e45 stays.
- **Negatives:**
  - The depth in wz / wy / wx: joins their LRs.
  - Folds `if (zfK(cz, 0)) {}` / `if (1 + zfK(cz, 0)) {}` at the EE block.
  - `zf8` / `zf1` instead of `zf4` in the EE word.
  - `if (1) {}` before / after the rows (mn 18-56).
  - Any 4-way gDPWord / snowW x next / nextN / nextR choice for the E7 / B9 / BA / BB tail: 144 forms, all >= 199.
    The forms that move the t4 spill to 112 change the frame.
- **Next:** find how the target keeps cy un-propagated with both cy statements in the compare block. The
  run-729 `*(volatile float *)&halfH` ILOD idea is one candidate. Do it in the boundary-before-cx shape, then
  stack the cz-first swap on top.
  The 8-byte temp gap (item 2) and the int ring (item 3) were not reached.

### snoweffects.uso 0x28E0 NM 96.11 -> 97.96, frame 520 (agent-c run 769)

- **Three commits on agent-c**, each with gate PASS, 3576 / 3579, the exact set unchanged, and no renames; all 793 words, frame 520:
  - a7d9f38bc: 97.42;
  - df487872c: 97.49;
  - 7268c6435: 97.96.

  Mnemonic-aligned diffs 21 -> 2.
- **Loop-top cx / cy / cz (fixed).** `if (cy) if (cz) {}` forced cy into its own earlier uopt block, so cy was
  computed first. Without it, cy sinks into its own compare block. The fix is to replace it with folds in the first
  compare: `if ((cx < -30.0f) + zf8(cx, 0) + zf1(cy, 0) + zf1(cz, 0))`. The folded cy / cz uses keep both in the cx
  block, so they are computed in the order cx, cy, cz. Adding `+ zf12(cz, 0)` to the cz compare raises the cz temp
  (e1307) above cy, which gives cx f0, cz f2, cy f12.
  - The loop-top cx / cz are expression temps (e7 / e1307), not M vars, and the compare folds count on those temps.
  - M-52 / M-56 / M-48 are the draw-block cx / cy / w.
  - zf8 / zf12 must be written as one flat `v + v + ...`. Nested zf4 calls change the code (+11 words).
- **The depth goes into cz before the EE packet** (`cz = m-row2; gDPWord(EE, ((cz * w + 1) * k ...))`). This gives
  the target's interleave of the depth row with the x0 / y0 conversions. Other placements cost words.
- **`SnowDLHolder2 *tex` declared last** (agent-e run 767): m / rot move to sp+404 / 340.
- **1/w -> f14:** fixed by `+ zf4(cz, 0)` in the EE word: `(int)(...) + zf4(cz, 0) & 0x7FFF`.
- **EE order (fixed):** EE now uses gDPWord, so w0 is stored before the depth. With EE alone this makes the frame
  528. Changing **B4** to snowW brings it back to 520.
- **Left:**
  - **Draw-block cy / depth colours:** we have cy f2 and depth f12; the target has cy f12 and depth f2. Both are pri 30, and cy
    has the lower LR index. A cz fold in the EE word does not add to M-192's count. Hill-climbs over single and paired
    folds at 8 sites (sp9) found nothing better.
  - **Temp area:** the temps and the spill are 8 bytes lower than in the target (228 / 188 / 116 there, 220 / 180 / 108 here).
    A `float pd[2]` local adds the 8 bytes above the spill, not below it.
  - Some int t-register rotations.
- Tools in /tmp/claude-1000/c769/:
  - q.py now replaces inside the 28E0 body first, so comment text no longer matches by mistake;
  - sw.py runs a parallel spec sweep;
  - hc3.py, sp6-sp12.

### snoweffects.uso 0x28E0 NM 95.44 -> 96.15, frame 520 (agent-c run 763)

- **Commit a395bfa05 on agent-c** (gate PASS, 3576 / 3579, exact set identical, no renames; 793 words, frame 520).
  Positional diffs 426 (the 794-word n1b lead) -> 278; mnemonic-aligned 21 / reg 202.
- **The draw-block mov.s is gone: all four terms use z.** The target keeps the reloaded p->pos.z in f22 for the
  w / cx / cy / depth terms. With `z` in all four terms, z's loop and draw pieces form one LR (u 8, bv 18), and x / y
  / z take f18 / f20 / f22 as in the target. The depth must read a variable, not `p->pos.z`: the EE w0 store comes
  before the depth, so a load there is not CSE'd (795 words).
- **Why the all-z form cost +4 words before: uopt substitutes cx / cy into the compares.** With only variables in the
  cx expression (no `p->pos.z` ILOD), the compares read an expression temp (e279 / e662) and the variable survives
  only for x0, so there are two interfering LRs plus a mov.s each. Any ILOD in the expression blocks this, which is
  why the old `p->pos.z` form had no copies.
  - **Fix: assign the row sums first, then scale after both:**
    `cx = (row0); cy = (row1); cx = cx * w * halfW; cy = cy * w * -halfH;` (793 words, no copies, the target's
    schedule). A 5 x 5 grid of cx / cy forms (c763/forms.py): every other order keeps 2 copies or loses the schedule.
    `cx = E * w; cy = E' * w; cx *= halfW; ...` also has no copies, but cx's `* halfW` sinks below cy (795).
- **Zero-code zf() folds (agent-e run 756) placed only on pointer bases** (`self->axis[1 + zf2(wy, 0)]`,
  `p[zf2(w, 0)].size`, `(&SNOW_CAM2->offX)[zf2(cy, 0)]`). wy then beats wx and x: wy f16 / wx f24 as in the target.
  **A zf in a stack-array index (`m[zf(x, 0)][3]`) is not free:** it emits `addiu tN,sp,K` for the row address.
- **Left (hill-climbs c763/sp11 converge here):** M is one word short around m (m at 400, target 404; the t4 spill
  at 108, target 116); the loop-top cx / cy / cz colours (f2 / f0 / f12, target f0 / f12 / f2); 1/w in f12 (target
  f14); the EE packet order (gDPWord form costs a word here, so EE stays snowW).
- Tools in /tmp/claude-1000/c763/: hc3.py (hill-climb scored by mnemonic / reg diffs; WP = word / frame penalty),
  q.py (base + replacements -> one score), forms.py, sp4-sp11 knob specs.
  keep/28E0_c763_44i_793w_96.06.cpp is the first 793-word form.

### snoweffects.uso 0x28E0 NM 95.39 -> 95.44, frame 520 (agent-c run 759)

- **Commit 2a486602e on agent-c** (gate PASS, 3576 / 3579, exact set identical, no renames; 793 words, frame 520).
  `last` is now a pointer local `lp` set in the for-init (`for (i = 0, p = self->items, lp = &self->lastCam; ...)`)
  instead of a reference initialised at the top. The hoisted &lastCam LR is created after i's, so it loses the
  2.38 priority tie: i / lp take t3 / t4 as in the target (store order `sw t4,lp-spill` / `sw t3,312`). reg-diffs
  247 -> 239.
- **Why agent-e's `+=` recipe costs 4 words here:** not the block or `assign()`, it is `t = ...` itself. It adds one
  block to c's (M-16) LR (bv 46 -> 47), which raises the s-register cost from 14.75 to 15.0. That ties the t cost (15,
  c crosses randf), and the tie goes to t3: c spills to its home 504 (+3 words) and K-332 takes s2. Removing a loop
  block to compensate (`if (1) {}` after drawn++, one of the cy / cz ifs) breaks other things (794 / 528, or the cy / cz
  sinking). Joint climbs (c759/sp7.py) top out at 95.03.
- **Spill offset = frame - M - 4 * spills.** Ours: M 408, one spill -> 108. The target's 116 means M 400 (the
  gDPWord macro's named `_g` costs one fresh M word per site; snowW sites are pooled).
- **The 794-word lead (95.79 % objdiff, positional diffs 426 vs 592):**
  /tmp/claude-1000/c759/keep/28E0_n1b_794w_95.79.cpp. On top of the commit it has:
  - a `SnowDLHolder2 *tex` local (`tex = self->tex; d = gl_func(tex->dl);`): self->tex becomes an LR in v0 (the
    target's `lw v0,44(s1)` twice) and the t6..t9 rotation lines up through the 0x06 packet;
  - FA: `(((unsigned int)(self->r * 255.0f) & 0xFF) << 24)`: the `& 0xFF` folds away but leaves the target's
    `or t8,t7,zero` (+1 word; the t-rotation then matches through the FA packet);
  - EE back through gDPWord (w0 stored before the depth), B4 and BA through snowW (M back to 404 with tex).
  The only extra word left is the draw-block `mov.s $f22,$f2` (z var vs the p->pos.z CSE).
- **The z mov.s is the blocker.** Using z in all four draw terms removes it, but then the draw-block cx / cy pieces
  drop to priority 6.7 and take f26 / f28 (two more mov.s), K0 takes f30 and halfW spills (798 words, frame 528); the
  same with any other variable for the screen x / y. In that form wx / wy also come out swapped (wx f16, wy f24; the
  target wy f16, wx f24; wx 70/6 beats wy 70/7 in every init order).
  A draft that drops the draw-block `z = p->pos.z` is 793 words / 95.79, but its depth uses the stale loop-top z (the
  wrong semantics, kept only as a reference: keep/28E0_STALEZ_793w_95.79_semantics_wrong.cpp).
- **Next:** remove the mov.s in the n1b lead; or find another word in n1b, which is 1 over. A semantics-preserving
  draw-z spelling whose LR is the loop z's f22 is needed.
- Tools in /tmp/claude-1000/c759/: hc2.py (hill-climb with a soft word / frame penalty, so it can climb from 794+),
  one.py (evaluate listed knob vectors), od.py (aligned operand diffs), slots2.py, tr.sh (uopt colouring trace; its
  fN names are one slot off: trace f2 = f0, f12 = f2, ..., 35 = f30), sp7-sp13.py knob specs.

### snoweffects.uso 0x28E0 NM 95.04 -> 95.39, frame 520 (agent-c run 752)

- **Commit 6ff863693 on agent-c** (gate PASS, 3576 / 3579, exact set identical, no renames; 793 words, frame 520).
  Mnemonic-aligned reg diffs 293 -> 247 (branch targets masked).
- **The r1_2 lead now fits 793 words.** Its extra word was s4: the uopt trace showed that K-292 (the op- return-copy
  address) was CSE'd with the post-loop `lastCam = cam` copy, hoisted above the zero-trip test (den 13), and coloured s3,
  which pushed the gGfxLib base to s4. The target hoists K-332 (sp+188, in ra) instead, and K-292 (t5) covers the loop
  only, so the post-loop copy recomputes `addiu t5,sp,228`. Fix found by a hill-climb (c752/hc.py: single and pair
  knob flips, scored by objdiff with 793 words and frame 520 required):
  r1_2 + snowW on 0x06 + E4 back to gDPWord + a code-free `if (1) {}` after `self->drawn++`. op* r is at -344 (the target's).
- **agent-e's `+=` temp recipe** (`assign()` + block `SnowV3d t`, w753) on top of this: 797 words; the best hill-climbed
  793-word form is 94.98 % objdiff, so it is not in yet. Next is to combine it with a word saving.
- **Left:** i / last in t4 / t3 (target t3 / t4); the last spill at 112 (target 116: M 404 against the target's 400
  plus a second spill word); the EE packet order (the target stores w0 before the depth, the macro order, with the
  packet in a3); the draw-block z `mov.s`; the FA `or t8,t7,zero`.
- Tools in /tmp/claude-1000/c752/: ev.sh (now also prints low sp spill offsets), kn.py (knob product / random
  sampler), hc.py (hill-climb), rd.py (mnemonic-aligned reg-diff count), ad.py (difflib listing), sp*.py knob specs.

### snoweffects.uso 0x28E0 NM 94.88 -> 95.04, frame 520 (agent-c run 749)

- **Commit d17635bb7 on agent-c** (gate PASS, 3574 / 3579, exact set identical, no renames; 793 words, frame 520).
- **Frame map via the edg word dump.** `NCC -g3` + agent-g's `md.py` gives named M slots (c749/vn.sh); agent-a's
  `fl.py` (c749/fl.py, fixed to pick the 2nd function's tree) gives every pool word per line. Target in M space
  (sp - 520): cam -12, m -116, rot -180, halfH -188, i -208, `+=` caller temps C* -268 / C- -280, op- return copy
  -292, op- ctor temp -304 (+ 3 ctor R params and one unused word), op* return copy -332, op* r -344.
- **Fixes:**
  - all loop variables in function scope, halfH and i after rot (order: cam c halfW p d x y z w cx cy m rot last
    halfH cz sz sw x0 i y0 wz wy wx). Code bytes unchanged; the caller temps then land on -268 / -280.
  - M 416 -> 408: the gDPWord macro's `Gfx *_g` is a named block local, so every packet costs a fresh word.
    An inline `snowW(Gfx *, unsigned, unsigned)` has pooled parameters instead. Site choice matters for registers:
    0x06 + EE + E4 is best (search over subsets, c749/sw2.py).
  - coordinator lever (single-return inline): `operator*` as `{ SnowV3d r; return (r.set(..), r); }` makes `a` a
    pooled A word (needs the extra pool words from snowW at 0x06). reg-diffs 308 -> 303.
- **Left / leads:**
  - C* / C- are allocated C- first in every form tried (64 op- / op* / += signature + body combinations, member
    and friend, by value / const ref). The target has C* first.
  - op* r at -348 (target -344, right under the return copy): s also needs a pooled R word. Ctor via
    `set(a, b, c)` makes s pooled but then `a` goes fresh (set's `this` takes the A word).
  - The target spills t4 at sp 116 with M 400 and frame 520 (frame = round8(M + 108 + 4 * spills) fits two spill
    slots); ours spills at 108.
  - **snowW on the EE site only, with the ctor body as `set(a, b, c)`** (c749/v/r1_2.cpp): reg-diffs 277 (from 303), positional diffs 451
    (from 613), but 794 words (over the 793 cap). Find one word elsewhere and it is the next base.
  - Callee return types (void blank jals for the 4 non-value calls): no change.

### snoweffects.uso 0x28E0 NM 92.57 -> 94.88 (agent-c run 741)

- **Commits on agent-c** (gate PASS both times, 3571 / 3579, exact set identical, no renames; 793 words, frame 528):
  - 0c3443c2b: 94.83 % (report);
  - 6ac466621: 94.88 % (report).
- **The op* products must be register LRs.** The target's op* does `mul.s f2 / f12 / f14` and then three `swc1`;
  ours interleaved mul / store through the f4..f10 temps. The fix: the inline computes named floats first,
  `float x = a.x * s, y = a.y * s, z = a.z * s; SnowV3d r; r.x = x; ...`. Taking `a` by const reference gives frame
  528; by value gives 536. (`return SnowV3d(a.x * s, ...)` and `a.x *= s` forms are worse.)
- **wx / wy lose the tie to the op temps when their LRs are created later.** wx, wy and the op- / op* temps all
  have priority 10, and the tie goes to the lower LR index, which is creation order. The fix: declare
  `float wz, wy, wx;` and assign them after the `+=` (and, slightly better, after the x / y / z loads). The op- and
  op* temps then take f0 / f2 / f12 and f2 / f12 / f14 as in the target, wy goes to f16, wz to f26 and K0 to f28.
- With those two changes, the earlier levers move again:
  - the volatile halfH read is no longer needed (it costs 2 words);
  - the 1.0f literal on 1 / w and the sizes, with snowOne on the depth, gives the target's f26 1.0 in the draw
    block only, and halfW keeps f30;
  - a z variable in the depth term only;
  - nested `if (cy) if (cz) {}` brings back the target's cx, cy, cz order (cz finishes after the first compare,
    so no nop). That brought the word count to 793.
- **Left:**
  - In the wrap, x / y / cx / cy / wx are in different registers from the target's (x f18, y f20, z f22,
    wx f24). The target's z (M-48, priority 80/8 with the depth use) colours before wx; the `if (1) {}` cut does not
    add a block to wx's LR.
  - The draw-block z needs one `mov.s` (the z var LR and the p->pos.z expression LR get different colours).
  - The EE packet order.
  - Frame 528 against 520. Every declared local has a home, in declaration order. The target has 10 words
    between cam and m, and spills halfH / i to 332 / 312 below rot (one unknown word at 336 and four between
    332 and 312), so its declaration list differs from ours.
- **Flat or worse:**
  - a separate `inv` (797-798: halfW splits);
  - all 4096 draw-block operand x / y / z / p->pos combinations, both before and after the new base;
  - z in every draw term with volatile halfH in any of 5 sites, or a p->pos ilod in cx (796+);
  - the depth precomputed into `d` or an int local;
  - cx / cy / cz statement order and 15 empty-if forms;
  - a random knob climb (about 8k compiles: inv, vol, 1.0 partition, init order / position, operands, if form).
- Tools in /tmp/claude-1000/c741/: rc.py (knobs + build), grid.py, climb.py, k.py (string probes), ud.py, tr.sh.

### snoweffects.uso 0x28E0 NM 92.56 -> 92.57 (agent-c run 734)

- **Commit a5fea1c29 on agent-c** (gate PASS, 3571 / 3579, exact set identical, no renames): `wz, wy, wx` declared
  in that order (the target's loop-top init order). 792 words, frame 520.
- **The third 1.0 group is reached by the existing two-way lever.** snowOne on 1 / w, sw and sz (literal on alpha
  and depth) gives exactly the target's draw block: 1.0 loaded into f26 right before the div, and alpha and depth
  rematerialised with `lui / mtc1`. It scores lower (91.87) because the callee-saved register the 1.0 LR frees goes
  to another constant: -30.0 takes f30, and halfW stays in f28.
  - Splitting the wrap constants (`(float)snowK(-30)` etc., all 2048 subsets of the 11 sites) only moves the
    freed register to the next constant: 60.0, then the alpha / depth 1.0. Best 92.31.
  - In the target, wx sits in a callee-saved register (f24, shared with -halfW in the draw block), so there is
    no spare one. Our wx is in f2: in the uopt trace (c734/tr.sh) wx (M-260) interferes only with cx, x and y.
    Next lead: find why the target's wx LR is long enough to interfere with cy / cz / wy (or crosses randf).
  - Third-group spellings at alpha or depth (unsigned / short inline, float inline, `static const float`,
    `(float)1u`, a float inline param): each merges with the literal or the snowOne group. A double inline
    emits cvt.s.d.
- **z reload / EE order.** The target's EE packet stores come after x0 / y0 and the depth's m loads because z is
  in f22 (no p->pos.z load stuck behind the header store). A z variable in every draw-block term reproduces that
  order (573 positional diffs against 697), but halfW is then split and spilled (798 words, frame 528).
  Computing depth into an int first (new local or reused `d`), or a gDPWord that reads w1 first, gives frame 528
  and puts the t5 / ra address LRs in s4 / s5.
- halfH declared after rot gets 336 (the target spills to 332), but m / rot move up 4: no gain.
- Flat: empty-if placements, FA packet next kinds, sx / sy draw-block variables (frame 528), the rc2 climb
  (c734/rc2.py: 1.0, 0.0 and wrap-constant sites, packet kinds, the z form).

### snoweffects.uso 0x28E0 NM 90.25 -> 92.56 (agent-c run 729)

- **Commits on agent-c** (gate PASS both times, 3571 / 3579, exact set identical, no renames):
  - 5b321b51b: 92.13 % (report), 793 words;
  - 35b67636e: 92.56 % (report), 792 words, frame 520.
- **The ilod blocker that does not split x is a volatile read of halfH**, e.g. `cy < *(volatile float *)&halfH`
  in the last y compare. halfH's address is taken, so it gets a memory home. That matches the target, which
  spills halfH and reloads it from 332(sp) in the draw block. The ilod also stops copypropagate rewriting the
  sx / sy branch uses. With the run-726 double sw / sz def this gives 791 words, 90.69-90.81.
  - The `cy` def site and the first compare score about the same.
  - Writing halfW the same way is worse (86.4).
- **The 1.0f partition lever:** `(float)snowOne()` with `inline int snowOne() { return 1; }` folds late, so its
  sites form a constant LR separate from the literal 1.0f sites.
  - Every assignment of the five 1.0f sites (1 / w, sw + 1, sz + 1, fadeIn alpha, depth + 1) to the two
    groups scores like a two-way partition.
  - A second inline (`snowOneP`) merges with snowOne, and an inline returning a float merges with the literal.
    So only two groups are possible, and the target's three (1 / w with the sizes in f26, alpha and depth
    rematerialised) have not been reached.
  - Best: 1 / w alone in the snowOne group, which gives 793 words and 92.09.
- **Random climb** (c729/rc.py; knobs: per-site x / y / z variable or `p->pos` read, cx / cy order, the halfH
  volatile site, the 1.0f partition, per-packet next kind, the empty-if forms). It moved the volatile read to
  `cy < halfH` and replaced z with `p->pos.z` in every draw-block term (no z variable there): 92.52 (fz).
  About 800 more neighbours: flat.
- **Left:**
  - The literal 1.0f group is hoisted to f30 for the whole function (`lui / mtc1 $f30` at the loop entry), so
    halfW drops to f28. The target has halfW in f30 and 1.0 in f26 in the draw block only.
  - a z reload for the depth;
  - the FA `or`, and the op* copy-chain slots.
- Flat or worse:
  - grid1: 8192 operand-site variants (x / y / z variable or `p->pos` in w / cx / cy / depth, both orders).
    The best at 793 words or under was 87.76: dropping a variable changes the head colouring.
  - Two volatile m reads.
  - `snowOne` on the sw site alone (799 words).
- Tools in /tmp/claude-1000/c729/:
  - gd.py / gd2.py: the draw-block generator plus string replacements;
  - grid1-3.py, p3.py: partition grids;
  - rc.py: the climb;
  - ud.py: a mnemonic-alignment diff against the target.

### snoweffects.uso 0x28E0 (agent-c run 726, no commit: best drafts are over the 793-word cap)

- **What blocks global copypropagate of a branch use: an indirect load (ilod) in the copy's expression.**
  Found by probing; the uopt_x.c body was not decoded. Each of these removes the sx / sy `mov.s` copies, and the
  compares then read the single variable register:
  - a non-volatile `p->pos.x` in place of `x` in the cx expression (and `p->pos.y` in cy). The load CSEs with the
    draw-block `x = p->pos.x` load, so it adds no load. The cost is a new split: x var vs the ilod expression
    (+1 `mov.s`).
  - `*(volatile float *)&m[k][0]`. The volatile ilod keeps `lda m` as an expression. With one such site, the
    lda is computed in the block (+1 addiu). With two sites, the lda is hoisted into an s register (s3 / s4
    shift, 86-87 %).
  - No effect (bytes identical to base): a `volatile float m[4][4]` declaration (direct lods lose the qualifier),
    `volatile float (*mp)[4]`, self-assignments (`x = x;`, `cx = cx;`, ...), and an identity inline
    `snowF(v)` on the def.
  - mp alone does not block the global rewrite (mp is forwarded to `lda m` first), so "mp + blocker" is not
    needed. mp on the new bases scores lower (87-90).
- **The target has TWO sprite-size variables.** sw (t1) feeds x0, x0 + sw and texW / sw; sz (t2) feeds y0,
  y0 + sz and texH / sz. The two are joined by `or t1,t2,zero` and need two separate sz / 2 sequences. The base
  CSE'd sz / 2, and that saved the words which paid for its extra copies.
  - `sw = sz` copy: 91.56 % (799 words). It coalesces, so there is no `or`.
  - The same expression assigned twice (`sw = (int)(E); sz = (int)(E);`, sw first): 92.07 %, and it emits the
    target's `or`.
- **Best: 92.30 % at 797 words** (/tmp/claude-1000/c726/keep/q_g_xy_v0_px.cpp). It is the double sw / sz def,
  plus cx computed before cy, plus one volatile m read in cx and `p->pos.x` in cy (frame 528).
  - Also /tmp/claude-1000/c726/keep/s_g_h__px_px.cpp: 92.17 % at 796 words.
  - The 793-word cap (TRUNCATE_TEXT) blocks both. Nothing at or under 793 words beat 90.25 in about
    5k compiles (/tmp/claude-1000/c726/g*.py and g*.txt).
- **What is left over 793 (s_g_h__px_px):**
  - the K1.0 constant materialised twice (lui + mtc1 + a nop). The target keeps it in f26 for both `1.0f / w`
    and `+ 1.0f`. A `one` local is propagated as a constant, so that has no effect.
  - the x split `mov.s` from the ilod blocker;
  - the earlier pre-existing diffs (lines 130-360).

  Fix K1.0 and the extra words drop to 793 or under. Next: a code-free ilod blocker that does not split x, and
  the K1.0 colour.

### snoweffects.uso 0x28E0 NM 90.19 -> 90.25, frame 520 (agent-c run 721)

- **Commit dae85e8dc on agent-c** (gate PASS, 3570 / 3579, no renames; objdiff report 90.30, fz 90.25, 793 words,
  frame 528 -> 520 = target). The draw block declares no new named locals: the loop's cx / cy hold the screen
  x / y and `w = 1.0f / w` replaces inv. The callee-save area, m (404..464) and the 508..516 slots now sit
  where the target has them. (cx / cy alone with a separate inv: 90.21, frame 520, fewer positional diffs.)
- **Why each of inv / sx / sy gets two LRs: two separate forwardings (c721 tr.sh + -zcopy probes).**
  - **In-block (readnxtinst):** the bb45 compare `-halfW < sx` and the sz / sx / sy uses of inv read the stored
    expression, not the variable. That gives the expression LR in bb45.
    - Spelling the matrix reads through `float (*mp)[4] = m;` blocks it for sx: the tree still has ilods at read
      time, so `ules{-halfW}{sx}` uses the variable. uopt forwards mp afterwards, and the loads stay `lwc1 K(sp)`.
  - **Global (copypropagate):** the branch uses in bb46..48 (`sx < halfW`, `-halfH < sy`, `sy < halfH`) are
    rewritten to the expression (new entries ~590+ in the zdbug:5 table). The non-branch use in bb49 (x0) keeps
    the variable, even with all of bb49's stores removed. That is the branch-only rule of IDO_CODEGEN's
    `find_replacements` note.
  - **Proof:** mp plus `-Wo,-zcopy:0` gives the target's draw-block shape with no mov.s: sx / sy single
    registers, halfW f30, -halfH f16. -zcopy:0 alone still has the bb45 mov.
    So the C lever must block both: mp handles the in-block forwarding. Nothing found yet for the global one.
- **Flat or worse:**
  - by-value inline params for the draw (83.0);
  - `snowSet(float &, v)` stores (sx / sy go to memory; 86-89, frame 520);
  - `snowIn` / `snowLt` compare helpers (inline params are forwarded too; `&&` of int returns adds 10-20 words);
  - compare spellings: `>` forms, nested ifs, `!(<=)`, parentheses, `+ 0.0f`, `cx * 0.0f +`;
  - the `float *wp = &w` ilod for inv (w goes to memory, 88.8);
  - mp on the new base (89.08: the in-block block alone recolours x / y / z).
- Next: find a code-free spelling that stops copypropagate rewriting a branch use. Candidates:
  - a def that does not dominate the compare;
  - a second reaching def of cx (the wrap-block def already reaches it, which is not enough);
  - an alias that `f_indirectaccessed` / `f_cskilled` reject.
  The uopt_x.c copypropagate body is lines 20391-24966 of /tmp/claude-1000/agent-h/r687/u/uopt_x.c; the decision
  is around its offsets +2480..+2730. Tools are in /tmp/claude-1000/c721/:
  - ev.sh: words / diffs / fz / frame;
  - evx.sh: the same with EXTRA flags;
  - tr.sh: the LR trace;
  - gen*.py: draw-block variants.

### snoweffects.uso 0x28E0 NM 90.15 -> 90.19, frame 528 (agent-c run 716)

- **Commit 8e0e53df3 on agent-c** (gate PASS, 3569 / 3579, no renames; objdiff report 90.24, fz.sh 90.19,
  positional diffs 574 -> 518, 793 words, frame 536 -> 528). The change: inv / sx / sy declared in the draw
  block (`float inv, sx, sy;` after the near / far test) and sy computed before sx.
- **Compiler: stays on 7.1.** Under `tools/ncc721.sh` the in-tree donor scores 83.97 (808 words). The POD
  SnowV3d (no ctors, field-by-field op-) gets frame 520 but scores 82.5 (805 words). Its draw block colours as on
  7.1: inv f24, halfW spilled. The ct3 / ct0 forms do worse (73-72). Mnemonic-only diffs: 7.1 49, 7.2.1 85-88.
  The extra ones are in the op- / op* copy chain (target lines 250-300). That chain is the 2.19 shape, so
  nothing here points to 7.2.1.
- **Why inv / sx / sy lose the caller-saved registers** (`-Wo,-zdbug:5`, c716/tr.sh + iu/x.lr). In lre.py's
  float columns, col 24 = f0, 25 = f2, 26 = f12, 27 = f14, 28 = f16, 29.. = f18.. and 35 = f30.
  - uopt splits each of inv / sx / sy into a variable LR and an expression LR.
    - The variable LR runs from the def in bb45 to the x0 / y0 / EE use in bb49 (2 refs, 5 blocks, pri 10).
    - The expression LRs are the in-block uses and the compares in bb45..48: udiv e854 pri 50, the products
      pri 20, -halfH pri 15.
  - The expression LRs colour first and take all five caller-saved registers (f0 / f2 / f12 / f14 / f16 = the
    target's sx / w / sy / inv / -halfH). The variables then get f24..f28, joined by `mov.s` copies (ours has
    5 mov.s, the target 3).
  - In the target each value has a single register (no copies), so the variable and expression LRs must
    either be one LR or share a colour. Through bb45 they interfere, so sharing a colour is impossible.
  - K0.0 then takes f30 (pri 9.17) and halfW splits.
- **Flat or worse, all on the draw block:**
  - 1080-point grid (c716/gen2.py, grid2.py), 640-point grid with `if (1) {}` / `if (inv) {}` / `if (halfW) {}` /
    `if (halfH) {}` cuts (gen3.py), then a 5.8k-compile perturbation climb with per-site packets and the cy / cz
    ifs (gen4.py, rp4.py; 90.217 is reachable, but only at frame 536).
  - The grids covered: inv / sx / sy scope (loop / block / function), sz before / after, sx / sy order, a
    `-halfW` local before / after inv, compare forms, `halfW + sx`. None gives inv f14 or halfW f30 with
    sx / sy in registers.
  - Two-statement spellings (`sx = A * inv; sx *= halfW;` and others) give identical bytes.
  - `snowIn(const float &v, ...)` helper: sx goes to memory (84-86). With `float h` by value, halfW gets f30,
    but sx is stored at sp+276.
  - No sx variable (the expression written at all three uses): halfW f30, inv f0, 89.36.
  - An `if (1) {}` cut after sx: halfW f30, inv f0, 89.4.
  - `if (halfW) {}` at any loop or draw position emits `c.eq.s` (float empty ifs are not code-free): 88-89.
- Next: get one LR per value. The target's sx is defined in bb45 and used up to x0 with no copy, so look
  for a source form where uopt does not substitute the expression into the compares. Candidates: a store
  between def and compare, sx assigned in both arms, or inv / sx / sy as inline-function parameters.
  Frame: halfW's spill slot and the copy-temp layout (target triples at 176 and 216..260, ours 180 / 196 /
  240 / 252 / 300).

### snoweffects.uso 0x28E0 NM 88.9 -> 90.15 (agent-c run 712)

- **Second commit (90.15 %, 789 words, positional diffs 663 -> 574)**: a random 2-4-knob perturbation climb
  (rp.py) from the first commit found `if (cy) {} if (cz) {}` with no sw copy and packets
  nextR (0x06) / nextN (FA) / nextM (E4, `int n = count++; return &buf[n];`) / next elsewhere.
  nextM is added to the in-tree GCtx. Commit b5c75e217 (gate PASS, 3569 / 3579, no renames); frame 536 vs 520.

- **First commit** af526c5fa on agent-c (90.03 %, gate PASS, no renames): body 791 words (limit 793), c in s2, frame 568.
  Three changes from the run-704 draft:
  - **`if (cy) if (cz) {}`** (nested, two blocks fewer than three separate ifs) instead of `if (cz) {} if (cy) {}`;
  - `sw = sz` used only as the texW divisor (sw in the x0 / x0 + sw sites cost the extra words);
  - per-site next / nextN packets: nextN on the 0x06 / FA / B4 / BA001301 / BB packets, next elsewhere.
  Found by coordinate descent over per-site packet kind, 16 empty-if spellings, the three sw sites, fadeIn
  form and the op- ctor (tools: /tmp/claude-1000/c712/gen.py, cd.py / cd2.py, rp.py; `ev.sh tag genome`).
- **Ctor stripping (agent-h run 702 lever) does not help here:** POD SnowV3d (no ctors, op- builds r field by field
  or by aggregate init) cuts c's block count only 46 -> 45 and loses the target's op- store / copy schedule:
  90.43 -> 87.6. Declaration order of halfW / halfH, x / y / z and inv is a no-op (identical bytes).
- **tr.sh float names are shifted by one pair:** a `col=fN` in the colour trace is the real f(N-2) (`35` is f30).
  With that: x / y / z f18 / f20 / f22 (as in the target), inv f28 and sx f30 (`35`, M-260) because every
  caller-saved register is forbidden in bb44..49 when they are coloured (pri 6.67).
- **What is left is float pressure in the draw block.** The target has inv f14, sx f0, sy f12 (caller-saved),
  halfW f30 for the whole function, and the global K1.0 LR coloured f26 in the draw block (one `mtc1 at,$f26`
  for both `1.0f / w` and `+ 1.0f`). Ours: halfW and K1.0 are split with every piece at sv = 0 (never coloured),
  so halfW spills (588 / 544(sp)) and 1.0 is materialised twice. K1.0 is function-wide because the fadeIn
  `alpha = 1.0f` store also uses it.
- Next: lower the caller-saved pressure in bb44..49 so inv / sx / sy colour first (then halfW and K1.0 keep their
  homes); the frame (536 vs 520 after the second commit) is the other half.

### snoweffects.uso 0x1E60 EXACT; 0x28E0 leads (agent-c run 704)

- **0x1E60 EXACT** (commit ad16ab83c on agent-c; gate PASS, 3569 / 3579, no renames). Moved from agent-b's
  `snoweffects_uso_ncc_b.cpp` (NON_MATCHING-only, `SNOW_NM_B_FUNCS` removed) into `snoweffects_uso_ncc_nm.cpp`
  (`SNOW_NM_FUNCS`, both trees).
  - Same hop-everywhere form as 15D0, but with 18 packets the unit cuts land elsewhere. The target's
    a1 / a2 rotation (a3 at the 0xBA000602 packet and EndDL, E700 t1, F568 a3, t0 never emitted) comes from:
    - `if (1) {}` after the SetTImg and after the second PipeSync;
    - `hopI` on the render SetTile;
    - SNOW_PH x1 on SetTileSize, x2 on 0xBA001402, x3 on the combine word.
  - The straddling hop temps are the target's hidden t0. agent-b's dead `switch` for the jr ra delay slot
    is not needed in this form; with plain `next()` the switch has to sit after EndDL to give the a3 there.
  - Found with a layout score: packet-register sequence, plus the E700 / F568 / 64 registers, plus words != 300.
    A coordinate-descent climb from the all-hop 15D0 recipe hit (0, 0) in one run. Plain-`next()` climbs
    stalled at "F568 a3 needs a hidden t0".
  - Tools in /tmp/claude-1000/c704/:
    - gen.py: 18-packet body (per-packet kind, PH, `if` sites, switch sites);
    - sc.py: layout score;
    - cd3.py / grid.py / mini.py: climb, grid and minimiser;
    - un.sh / tr.sh: cut and colour views for 1E60.
- **0x28E0 (NM 88.9, not committed).** Best draft is 90.43 % but 797 words; the 793-word limit (TRUNCATE_TEXT)
  blocks it. Draft: /tmp/claude-1000/c704/keep/28E0_r3_90.4_797w.cpp.
  - **c's s-register cost = 3.25 + 0.25 x bv** (bv = c's block count in tr.sh). The t-cost is 15, so c needs
    bv <= 46 for s2.
  - **The target computes sz / 2 twice.** It has `mfc1 t2; or t1,t2,zero`: a second int that copies sz, used
    by x0 (`sw / 2`, `x0 + sw`, the texW divide). y0 uses sz. Writing it as `sw = sz;` restores the 4-word
    second division.
  - **Packets through `nextN()`** (named n / g) give the target's v1 / a2 pool words: +0.15.
  - With all three: c is s2 and the gfx base is s3, as in the target, at 90.43 %. The other two changes:
    - `if (cz) {} if (cy) {}` replaces the three empty ifs (bv back to 46);
    - `sw` for x0, x0 + sw and the texW divide.
  - Left:
    - 4 words too many;
    - halfW spilled (the target keeps it in f30, -halfW in f24);
    - the draw-part float colouring;
    - the `+=` copy chain at 287..293.
  - Not faithful: `alpha = 0; if (fadeIn) alpha = 1;` also gives s2. The target has the if / else, two stores
    and `beqz zero`.

### snoweffects.uso 0x15D0 / 0x1A18 / 0x2310 EXACT (agent-c run 691)

- Commit bc0eab37b on agent-c (gate PASS, 3566 / 3579, no renames). The donor
  `snoweffects_uso_ncc_nm.cpp` is now spliced in both trees (`SNOW_NM_FUNCS`); the 1E60 draft stays out.
- **The holder was a hop temp.** Every packet goes through `hop()` = two `(this + 0)` hops over `next()`.
  - Inside a live unit the hop copy is forwarded away. Where a uopt unit cut (20 counted loads; agent-h's
    run-687 counter) falls inside a hop chain, the copy lives across the cut and keeps refs on both sides.
  - With cuts inside packets 4 / 6 / 8 / 10, the hop word spans units P2..P12 with priority 4 (> the
    packets' 3), so it takes a1 before them: the target's a2 / a3 rotation. All-hop keeps ctx / dl / count
    in v0 / v1 / a0; mixing hop and plain packets splits those pool words.
  - A cut after count 3..6 of a packet's own loads straddles the hop chain; after 1, or after the pointer
    def, it does not.
- **Placing the cuts:**
  - SNOW_PH loads go in the packet's w0 argument, one count each. A phantom on the pointer expression
    creates a new pointer temp and wrecks the colouring.
  - One `if (1) {}` after the SetTImg packet makes the P1 | P2 cut.
  - The FA packet's old phantoms are removed, so the last cut falls after the EndDL packet's dl use
    (v1 as in the target).
  - The N1 hooks are dropped: their `_g * 1` expression LR took a3 ahead of packet 3.
  - P4 (LoadTile) uses `hopI` (unnamed result); it fixes the t-ring offset and the scheduling.
- Not in the target structure: 0x1A18's texture is IA8. In 0x2310 the preamble int stores go one per line
  (ascending store order).
- Method: /tmp/claude-1000/c691/
  - un.sh: per-line counts and cuts, wrapping agent-h's units.sh.
  - one.sh: compile, then show the packet sequence and the multi-unit LRs.
  - g2.py build2: per-packet kind, phantoms, `if` sites, hooks.
  - cd2.py / mini.py: coordinate descent and minimisation.
- 0x28E0 was not reached this run.

### snoweffects.uso 0x270 EXACT; 15D0 family / 0x28E0 (agent-c run 683)

- **0x270 EXACT** (commit 907076098 on agent-c; gate PASS, 3561 / 3579, no renames). Donor
  `snoweffects_uso_ncc_c.cpp`, now in `SNOW_C_FUNCS` (both trees); 0xC90 / 0x28E0 stay NM, bytes unchanged.
  - **Score the layout, not the diff count.** Raw diff lines are swamped by the t-ring cascade: when E7 / F568 take
    t0 / t1 instead of t1 / t2, every ugen temp shifts and the count jumps from ~15 to ~170. That is why the run-674
    climb plateaued at 14. The useful objective is the packet-pointer register sequence (the `addu rX` whose
    `sw ..,0(rX)` follows) plus the registers of the E7 / F568 / 32 constants, compared with the target. Climb on
    that first, then on diff count.
  - **The hidden t0 is a cross-BB index.** `nextBI() { int n = dl->count++; if (1) {} return &dl->buf[n]; }` on the
    LoadTile append: n is defined before the block cut and used after it, so it is not copy-propagated. It becomes a
    2-unit LR (num 2, den 2, coloured after the packets), takes t0 and is never emitted (the address uses a0). That
    pushes E7 to t1 and F568 to t2, as in the target. `Gfx *r = g; if (1) {} return r;` does not do it: the copy
    is propagated away.
  - **Final form** (after greedy minimisation): no free-standing `if (1) {}`. Per packet, nextR x4, next, nextR,
    nextR, next, nextB (`if (1) {}` after the slot address), nextBI, nextR, nextB, next x3, plus 9 zero-code
    counted loads (`SNOW_PH`) in the FA / SetTImg / load-SetTile packets.
  - Tools: /tmp/claude-1000/c683/: gen.py (body generator: per-site kind, w0 / w1 phantoms, `if (1)` sites), score.py
    (layout score), hc.py / hc2.py (parallel climbs, layout-first / diff-first), mini.py (minimiser), uv.py / uv2.py
    (LR unit view from the zdbug:5 dump), lay.py.
- **15D0 / 1A18 / 2310: not cracked.** The same climb (f/gen15.py, f/hc15.py, f/mini15.py; kinds plus nextB / nextBI /
  nextBN / nextC / nextD / nextE..J) reaches 15 / 17 / 18 positional words (committed NM: 18 / 20 / 21). Not
  committed: it needs about 40 phantom loads for 3 words.
  - The target's P2..P11 rotate a2 / a3, so a1 is busy in every unit there and in P12's unit (t0), but free at
    P0 / P1 / P13.
  - **A 2-unit hidden range cannot cause that.** It is coloured after 1-unit packets (pri 1.0 vs 3.0) and after
    2-unit packets (1.5).
  - The holder needs a priority of at least 2 in every unit P2..P12: a pooled edg variable (like the ctx / dl /
    count temps v0 / v1 / a0) with about 2 refs per unit, all folded at emission. Or a 1-unit range with 2 refs
    (pri 2), with each packet a 2-unit range (pri 1.5).
  - Flat or worse: `DList *d = dl` locals (nextE / nextF) change the code (one dl reload fewer); `Gfx *r = g` copies
    are propagated away; post-increment splits (nextG / nextH / nextJ) recolour from P0.
- **0x28E0: c (M-16) still ties at 15.0** (t1 wins the tie; s2 is needed).
  - Any spelling with fewer blocks in c's range gives s2. Nested `if (cz) if (cy) if (cx) {}` gives 14.5;
    `if (cz) {} if (cy) if (cx) {}` and `if (cz) if (cy) {} if (cx) {}` give 14.75. But cy / cz then sink into the
    wrap branches, and mnemonics fall 95.3 -> 90-90.7.
  - Removing a block anywhere else does not lower the cost (still 15.0):
    - `while` / `for (;;)` loop forms;
    - `else {}` on the fill test, or the fill test as a comma expression;
    - nested ifs for the && chains;
    - separate `if`s for the wrap chains (they also cost mnemonics);
    - a fadeIn ternary.
  - A trailing `continue` adds one (15.25).
  - The cost counts blocks in c's range, so the cut has to come from inside the loop. Next idea: a wrap-test
    spelling that keeps cy / cz early with one block fewer, such as the z-chain written so its join is shared with
    the empty tests.

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

## heli.uso 0xB08 slerp delay slots: M-220 cost split (agent-e run 780, research only, no commits)

- **Rows 531 / 547 fixed, code-free, 943 words, frame 368: objdiff 99.130 -> 99.979 on main's f9b3b17cd source
  (agent-g run 777, `c25.cpp`).** Raw rows 13 -> 5: only the v0 / v1 rows 312..322 (q) are left, plus the pad
  nop. Verified in-tree (`make build/src/heli_uso/heli_uso_mp72_nm.cpp.o`, then objdiff against
  expected/: 99.97879); the worktree was restored afterwards. Source: /tmp/claude-1000/agent-e/w780/b08_e780.cpp;
  diff: `b08_e780.diff` (3 hunks). Tools: `v.py` (score), `rd.py`, `chk.sh` (slot rows), `lr.sh` + `col.py`
  (M-220's SAVE / PICK / COL lines).
- **The mechanism (uopt cost split, IDO_CODEGEN "split trigger").** uopt ends a block at every call, so the
  slerp's sin-term word M-220 has def-only units 56 / 58 / 60. Each of them crosses that component's cos `jal`,
  and use-only units 57 / 59 / 61 follow.
  - Coloured whole (main: num 13 over units 56..61, vel.z 68 and the pitch lerp 94 / 95 / 97), M-220 is f16
    everywhere. ugen then emits `mov.s f16,f0; l.s f12,44; s.s f16,148; jal`: the caller-save store comes after
    the argument reload, so as1 puts the store in the delay slot.
  - The target splits M-220 instead. The split happens when `save (= pri x cnt) <= best`, and best is f16's
    caller-range cost, which is 10. The def units then go uncoloured: uopt stores `s.s f0,148` at the def, and
    the use piece reloads f16. as1 then puts `lwc1 f12,44(sp)` in the slot, as the target does.
  - Without the pitch lerp, M-220 has 8 appearances (6 slerp, 2 vel.z): save 8 <= 10, so it splits
    (pieces 56 / 58 / 60 = -1, {57, 59, 61, 68} = f16). So **the target's lerp is not in M-220.**
- **The lerp needs its own LR at pri 2.5 that takes f16 before -pi/8 (pri 2.0) and adds no frame word.**
  - A fresh pooled word works (4 x `dumf` + `idm`, or `idm(float x) { return (float &)x; }`; 99.957, register-exact).
    But it creates M-312 at 56(sp), and every ugen temp below it moves down 4 (sp rows only).
  - `dist` on its own: dist's whole LR (pri 1.0, blocks 47..97) is split late, so -pi/8 takes f16 first and the
    lerp gets f18 (99.94).
  - `g` on its own: the LR joins the yaw-region g, so the roll is f16 where the target has f14 (99.958).
  - **Answer: the lerp goes in `g` and the roll goes in `dist`.** g is then {94, 95, 97} only (2.5, f16). dist's
    pieces are 47 / 48 uncoloured, 62 / 63 f14, and the roll piece 85 / 86 / 88 f14 (the target's colour).
  - The three `dumf(pf)` pads and `idm()` are no longer needed: plain `g = (pf - HF(0x148)) * 0.2f + HF(0x148);`.
  ```
  dist = -(side.x * dir.x + side.y * dir.y + side.z * dir.z) * 1.5;
  if (HF(0x154) < 100.0f) { hh = 100; dist *= HF(0x154) / hh; }
  if (1) {}
  *(float *)(self + 0x144 + zf6(-0.3f, 0) + 0 * (unsigned)(yaw + yaw)) = (dist - HF(0x144)) * (0.07f) + HF(0x144);
  ...
  g = (((pf - HF(0x148)) * 0.2f + HF(0x148)));
  *(float *)(self + 0x148 + 0 * (unsigned)(HF(0x148))) = g;
  if (1) {}
  *(float *)(self + 0x148) = clampP(g, -0.3926991f, 0.3926991f, 0);
  ```
- **Measured on the way:**
  - Cuts in slc() (`if (1) {}`) add ugen a2 save / restores (+4 words).
  - Every clampP dead-read variant except `zf1(v, ..)` / `(int)v` forms drops 2 words (942).
  - Moving the lerp into struct members (toTgt / side / dir / fwdAx / vel fields) costs +2 words.
  - Splitting vel.z out of set3q (two-param set3q, `const float &c`) shifts the frame.
  - The lerp in M-164 (1 x dumf + idm) gives 99.94: M-164 joins at 3.75, picks before the HF(0xF4) LR (#448,
    3.0) and swaps f12 / f16 at rows 839..883.
- **Left: rows 312..322 (q in v1, target v0).** Inert on the new form: q = p reused (the frame shifts, still v1),
  `q = p; q = *(q + 0x2C)`, dum4A argument mixes (p / q), `((char **)p)[11]`, a re-read of `*(p + 0x2C)` for
  mpos, and `p = q` after the load. R2 (the call's v0) has a use in q's only block (37: the q load base), so v0 is
  forbidden for M-124. That is consistent with block-granular interference. The target therefore either has the
  q def in a block without an R2 appearance, or uses a different interference rule for precoloured R2.

## heli.uso 0xB08 g / HF144 / -0.3f colour order (agent-e run 756, research only, no commits)

- **Fixed, code-free, 943 words: objdiff 97.789 -> 97.842 on agent-g's run-755 source (0af401b6e).** Raw rows go
  from 118 to 110. Both-masked rows stay at 53, because the change is colours only. On the head-fix source
  (`r751/e6_head_fix.cpp`, 944 words) the score goes from 97.837 to 97.890. Scratch: /tmp/claude-1000/agent-e/w756/.
  - `t.py SPEC` scores each variant and prints the K-0.3 constant's SAVE line (num / den / pri), taken from the
    instrumented uopt.
  - `pk2.py NAME lo hi` lists the FP LRs and their picks for a unit range.
  - `b08_e756.cpp` is the proposed source, and `b08_e756.diff` is its diff against agent-g's run-755 donor.
- **The lever:** raise the -0.3f constant LR from pri 0.5 to 3.5 with folded uses in HF144's block, so it is picked
  before HF(0x144) (pri 3.0):
  ```
  static inline int zf(float lo, int z) { return z * (int)(lo + lo + lo + lo + lo + lo); }
  ...
  *(float *)(self + 0x144 + zf(-0.3f, 0)) = (g - HF(0x144)) * (0.07f) + HF(0x144);
  ```
  - With this, -0.3f takes f0, HF144 f2 and g f14, and the unit is byte-identical to the target.
  - The constant needs 6 extra counted uses: num 7 / den 2 = 3.5, which has to be strictly above 3.0 (HF144 has the
    lower LR index, so it wins a tie). 5 uses (3.0) loses the tie. 7 to 9 uses give the same bytes as 6.
- **What counts as a use, and what doesn't:**
  - **Counted:** z is a constant parameter (substituted, so edg cannot see `z * x` = 0); uopt folds the product to 0
    after it has counted the uses.
  - **Each `lo` term counts.** `z * (int)(lo + lo)` = 2 uses; distinct conversions like `(int)lo` and `(unsigned)lo`
    count once each.
  - **No count:** `(int)lo - (int)lo`, a literal `(int)(-0.3f)` (both folded by edg), and `z & (int)lo`.
  - **Code changes:** `(int)-lo` (a `neg.s` survives) and `yaw + 0 * (int)lo` (float context).
- **Empty `if (yaw < -0.3f) {}` / `if (lo != K) {}` tests are byte-identical but don't help.** Each test is its own
  uopt unit, so num and den grow together: 8 tests give 9 / 6 = 1.5.
- **axZ zero / angle:** agent-g's `dumf(f)` (run 755) already fixes it. Another fix that gives the same bytes: reuse
  the int local `hh = 0;` and store `hh` in all five 0.0f slots (HF(0xF4 / 0xF8 / 0xFC), axZ.y, axZ.x).
  - The int-to-float conversion folds only in uopt, so the five zeros form their own one-unit web (num 4 / den 1),
    which is picked before f (3.0) and takes f0.
  - A new `int zi` local changes registers elsewhere (reg rows 55 -> 77).
  - Combined with zf, this matches dumf + zf byte for byte (97.842).
- **Pitch pointer (agent-g's fwdOf + q1f base, `r755/bA.cpp`):** the same zf fold works there.
  - With 4 or more `lo` terms (`zk(-0.3926991f, 0)` in the HF(0x148) store address), -pi/8 is hoisted into block 91
    and takes f18, as in the target: `add.s f0; c.lt.s f0,f18; swc1 f0` (both-masked rows 39 -> 25).
  - The value is still one LR: there is no `mov.s f2,f16` split yet.
  - Extra folds on pf (`zp(pf, 0)`) move pf / old-h but did not produce the split. Old-h folds (`zh(HF(0x148), 0)`)
    are worse (raw rows about 960).
  - Variants: /tmp/claude-1000/agent-e/w756/s11.py and s12.py.

## heli.uso 0xB08 pitch colours (agent-e run 764, research only, no commits)

- **The pitch window is now byte-identical to the target, including `mov.s f2,f16`.** All 26 rows from
  `cvt.s.d f0` to the angle block's `lui at,0x3f80` match. Colours: pf f0, old-h f2, F4 f12, F8 f14, the lerp
  value f16, -pi/8 f18 (hoisted), +pi/8 f0, the clampf copy f2, and the result f12.
  - Built on agent-g's run-761 `R4_0_4_q5.cpp`. Source: /tmp/claude-1000/agent-e/w764/b08_e764.cpp; diff:
    `b08_e764.diff`.
  - Not landable yet: 945 words (target 943) and 95.14 %. The two extra words are elsewhere (see "Left").
- **The source changes** (each one was checked against the instrumented uopt PICK / COL trace):
  ```
  static inline float clampV(float v, float lo, float hi, int z) { float w = v;
      if ((w < lo) + zf8(w, z)) return lo; if (zf1(w, z)) w = lo; if ((hi < w) + zf4(hi, z)) return hi; return w; }
  ...
  HF(0x14C) = HF(0x14C) + yaw * (0.06);
  if (1) {}                                  // (4)
  fwdOf(fwdAx, &HF(0xF4));
  pf = dot(fwdAx, vel) / 200.0f; pf = pf + fwdAx.y * (0.1);
  dist = (pf - HF(0x148)) * 0.2f + HF(0x148);                                          // (1)
  *(float *)(self + 0x148 + zf4(pf, 0) + zf3(-0.3926991f, 0) + zf1(HF(0x148), 0)) = dist;
  if (1) {}                                  // (2)
  *(float *)(self + 0x148) = clampV(dist, -0.3926991f, 0.3926991f, 0);
  ```
  1. **The lerp value goes in its own variable (`dist`, which is dead by this point), not `f`.** With `f`, the lerp
     LR runs on through the clamp tests into the angle blocks. It is then one LR with the angles' f2, picked at
     pri 4-5.5.
  2. **An `if (1) {}` between the HF(0x148) store and the clamp starts a new uopt block for test 1 and the copy
     `w = v`.** This costs no code. uopt interference works per block, so without this cut the copy and old-h
     (both f2 in the target) share block 91 and conflict. as1 still schedules `c.lt.s` / `swc1` / `mov.s` in the
     target's order.
  3. **The dead `w = lo` sits between test 1 and test 2 (agent-g's z5 position).** Then test 2 reads w (target
     `c.lt.s f0,f2`), not the lerp value. In the z7 / q5 position, test 2 is copy-propagated to the lerp value.
  4. **An `if (1) {}` after `HF(0x14C) = .. yaw * 0.06` moves the yaw-clamp return temp M-160 (LR 206, pri 2.6)
     out of the lerp block.** Without it, M-160 takes f18 before -pi/8 does.
- **Priority levers.** In `(cond) + zfK(x, z)`, the zf goes inside an `if` condition, so it adds no block and no
  code. The fold's uses count on whatever x is at that point:
  - `zf8(w)` in test 1: w is single-def there, so the uses are propagated to `dist`. dist goes 1.0 -> 2.67, so it
    is coloured, and it now comes after F4 / F8 (3.0) and before -pi/8. With zf5..7, dist stays below its split
    threshold and is spilled to 320(sp).
  - `zf4(hi)` in test 2: +pi/8 goes 0.5 -> 2.5 and takes f0 in the arms. That is the f0 holder that leaves f2 for
    the copy (pri 2.0).
  - `zf1(HF(0x148))` in the store address: old-h goes 3.0 -> 4.0, so it is picked before F4 / F8 and takes f2.
  - `zf3(-pi/8)`: -pi/8 is 2.5, which is below dist (2.67). zf4 gives 3.0, and then -pi/8 takes f16 before dist.
    Its den is 2, so it moves in steps of 0.5.
  - A zf on w at a point where w is multi-def (after `if (zf1(w, z)) w = lo;`) counts on the copy itself. As
    `if ((hi < w) + zfK(w, z))` it lifted the copy 1.5 -> 6.0 (zf8). This was not needed in the end.
- **Left (2 words, frame):** dist is now one LR with its earlier sqrt / slerp region (blocks 47-63), coloured f16
  there too. That adds a `swc1 f,320(sp)` and two reloads around rows 480-565. All frame temps below 56 also move
  down one word (kit CCXCIII: one fewer spilltemp).
  - Next: a lerp variable with no earlier LR. `float hn` declared after pf gave the same pitch shape in the Vhn
    sweep, but the frame changed (reg rows 202).
  - Or keep dist and cut its join: dist's earlier piece split off at its lower priority in the W0 forms.
  - Or reuse yaw or g (S_dist_yaw 95.05 / S_dist_g 94.84, both still 944-945).
- Tools: `an.sh NAME` (trace + pitch-region picks + pitch window against the target), `cols.py NAME..` (one line
  of the key LR colours / priorities, plus MOV when `mov.s f2,f16` is present), `pk3.py NAME LO HI` (FP picks with
  true register names; lre.py's names are shifted by one FP register). Sweeps: s4..s16.

## heli.uso 0xB08 ring map + set3 words (agent-e run 771, research only, no commits)

- **Result: 99.019 % (raw 31 rows, reg-masked 15, 943 words + pad, frame exact).** That beats the landed 98.72 %.
  Source: /tmp/claude-1000/agent-e/w771/b08_e771.cpp (= `w/H2.cpp`). It is built on agent-g's r770 `m3c0.cpp`
  (98.52), not on the landed main form. The same four edits on main's form score 98.3, because the word placement
  differs there.
- **Ring-offset map (per-row t / FP ring index of ours minus the target's, with registers masked out of the
  alignment).** Tools: `rot.py` / `runs.py` / `ex.py` (score plus run map per variant).
  - g4: the int ring is +1 on every int temp (rows 7-654). The FP ring is +1 on rows 12-515, 0 on 524-528 and -1
    from 540 to the end.
  - The int +1 is the single hidden t-ring temp of `zf1(HF(0x148))`: removing only that fold gives 0 everywhere.
    zf2 / zfa / (double) forms of the same fold do the same. zf4(pf) has no effect at all (b2 is byte-identical
    to g4).
  - The FP steps at 519 / 535 / 558 are the three uncoloured-M-220 reloads (ring temps instead of the coloured
    f16).
  - **Ring law, refined from probes** (a `zf1(HF(x))` int probe at the start, the middle and the end):
    - a hidden temp at row p shifts every row after p by one;
    - it also shifts the WHOLE function by one, as if ugen's ring start depends on the total temp count.
    So the offset at row r = (total temps) + (temps before r). A run that is offset everywhere means the total
    count is off. A step marks where the extra temp is. agent-h's "backward" reading is the global term.
- **What took m3c0 98.52 -> 99.02:**
  1. **vel's set3 words.** The target's vel products are M-164 / M-168 / M-220 (f12 / f14 / f16): the vel
     statement has -160 locked. The fix is `Vec3 vel = (dumf(HF(0x164)), *FWD * HF(0x154));`.
     - The dumf argument matters: HF(0x164) and HF(0x158) are clean. `0.0f`, `dist`, `dir.x` and `(float)0` lose
       two words. Plain HF(0x154) adds a second `lwc1 f0,340(s0)`.
     - A by-value `operator*(float s)` also shifts the words, but costs a mov.
  2. **The trailing cut on toTgt's subc: `set3(..); if (1) {} return ..`** (the leading cut stays). M-168
     (toTgt.z) and HF(0xF8)'s LR (e1358 #433) then no longer share block 70, so HF(0xF8) can take f14
     (98.83 at this step).
  3. **M-168 above M-220.** vel goes through `mq()`, a copy of operator* that calls
     `set3q(r, a, b, c) { r.x = a; r.y = b; r.z = c; if (0 * (unsigned)b) r.y = b; }`. M-168 goes 3.0 -> 3.33
     and M-220 stays at 3.25, so M-168 = f14, M-220 = f16 (slerp reloads, lerp, vel.z) and HF(0xF8) = f14, as
     in the target (98.96).
     - An address-fold form (`*(float *)((char *)&r + 4 + 0 * (unsigned)b)`, `(&r.y)[0 * ..]`) makes r a
       computed pointer and costs 1.7 %.
  4. **yaw (M-248) above e1358 #524.** Put `+ 0 * (unsigned)(yaw + yaw)` in the HF(0x144) store address
     (2.5 -> 3.0, which wins the tie on LR id). yaw then takes f12 at rows 728-796 (99.02). A single
     `(unsigned)yaw` does nothing.
- **Left (raw 31):**
  - the add.s order at 95-98;
  - v0 / v1 at 312-322 and t4 / v1 at 53;
  - the jal / lwc1 f12,44(sp) swaps at 531 and 547;
  - the 585 vel load shape (`lwc1 f4,0(v0)`: ours re-reads 340(s0)), plus its 584 branch offset;
  - rows 769-784: e1358 #524 is f2 where the target has f14, and old-h is f14 where the target has f2;
  - the 907 swc1 order;
  - the tail 925-933 (f8 / f6 swapped).
- Also measured:
  - stc(&addr-ref, v) with an `if (1) {}` (W7) gives FP offset 0 everywhere. It puts clampP's return in M-220.
  - lerpR2(ref, ..) gives 98.54 but loses the copy mov.

- **0xB08 NM 97.84 -> 98.72 % (agent-g 79d9395c2; gate PASS, 3576 / 3579, exact set identical, no renames, 943 words,
  frame 368).** Raw rows 110 -> 84, register-masked rows 53 -> 15. Scratch: /tmp/claude-1000/agent-g/r770/
  (`v.py` score, `rd.py` / `off.py` per-row register substitutions, `ring.py` int / FP ring mismatch counts,
  `lr.sh` + `pk3.py` LR picks with true FP names). Committed source = `d2r.cpp`.
- **The g4 rotation was two hidden ring effects, found with agent-h's "look where the offset ends" method:**
  - **Int ring (rows 7..654, +1):** no int ring temp exists after 654, so the extra temp had to be in the pitch.
    `zf1(HF(0x148), 0)` in the HF(0x148) store address costs one hidden ugen t-ring temp (its `(int)` conversion
    in an address). Dropping it (or `0 * (unsigned)HF(0x148)`, which changes nothing else) fixes the whole int
    ring. zf folds on constants (-0.3f, -pi/8) and inside `if` conditions cost nothing; a param-fold
    (`zu1(x, 0)`) in a store address burns a temp too.
  - **FP ring (rows 12..932):** the slerp's sin-term word M-220 was uncoloured, so its three reloads went through
    ring temps (target `lwc1 f16,148(sp)`), which shifted the f4..f10 ring everywhere before them. M-220 needs a
    join with a pitch-side temp to be coloured.
- **The lever: `*(float *)(self + 0x148) = (dumf(f), dumf(f), clampP(f, ..));`** The two dumf() calls hold two
  pooled edg float words to the end of the statement, so clampP's return temp lands on M-220 (checked in the LR
  dump: M-220 = slerp 56..61 + clamp 94..100). Both rings then line up.
  - Pads 1 / 3 / 4 are worse (d1 95.3, d3 98.3, d4 95.2). A pad as a separate statement does nothing: words free
    at the statement end. `dumf` takes a word because it assigns its parameter; an inline whose parameter is
    not assigned (`idf(x) { return x; }`) is substituted and takes none.
- **What is left (register-masked 15 + shared structure):**
  - In d2r the three pooled words are permuted: t / ternary / sa are f16 / f2 / f14 (target f2 / f14 / f16),
    and the clamp result is f14 (target f12). The target's colours fit **H1**: clampP's v = t's word M-160 (f2),
    its return = M-164 (f12), and the **lerp value** joins M-220 (f16, as sa).
  - **`r770/m3c0.cpp` builds H1:** `f = (dumf(pf), dumf(pf), dumf(pf), idm(lerp));` with
    `idm(float x) { x = x; return x; }` and no clamp pads. Raw 70 (best raw), but objdiff 98.52, because two
    things are wrong: (a) M-220 (lerp + sa) is f14 and F8 is f16 (target: the reverse), and (b) a second
    `jal` / `lwc1 f12,44(sp)` swap at 531.
    - (a) is pick order. M-220 is 11/3 = 3.67 and goes before F8 (e1358 #433, 6/2 = 3.0). Also M-168 (the ternary
      word, which is also set3's third parameter in block 70) wins the 3.0 tie and takes f14 in block 70.
    - The target needs F8 picked after M-272 / old-h (4.0) and M-164 (f12), but before M-220 and M-168.
    - Tried without success: F8 folds in the pitch address (`0*(unsigned)HF(0xF8)` is folded by edg; k >= 2 makes
      F8 4.0, so it wins the tie and takes f0), in the side.x read address, and in clampP conditions; `if (1) {}`
      cuts around the lerp; slc cuts; set3 pool pads (`dumq` before Vec3) in operator* / sub / subc.
  - Shared with the committed source: head add.s order 95..98, 547 jal / lwc1, 585, 2.0f in f18 not f2
    (602 / 637), 728..801 f12 / f14 / f2, 907 axZ store order, and the tail f6 / f8 swap at 925..933.
- **Next:** in m3c0, lower M-220 below 3.0 (num <= 8 at den 3; the pitch side has 5 uses) or move set3's pooled
  words so that M-168 leaves block 70; then fix the 531 swap.

## snoweffects.uso 0xC90 EXACT recipe (agent-g run 785, research only, no commits)

- **0xC90 NM 99.18 -> 100.0 (0 positional diffs, 592 words, frame 400, sp offsets exact).** The source is in agent-h's
  run-779 file (main 58affb666) plus the five edits below. To verify, I copied it into
  src/snoweffects_uso/snoweffects_uso_ncc_nm_h.cpp and ran
  `make build/non_matching/src/snoweffects_uso/snoweffects_uso.c.o`. The spliced function's 592 words are identical
  to expected/ (objdump word compare), and objdiff gives 100.0. The worktree file was then restored
  (`git checkout`). Files: /tmp/claude-1000/agent-g/r785/C90_exact_repo.cpp (repo includes) and
  C90_exact.diff (its diff against main).
  To land it, the donor also needs to go on the matching build (as for 47D4). The gTR macro now reads the loop-local
  `ge` by name, so a tidy version should pass ge as a macro parameter (code-free).
- **Edits (all code-free):**
  1. agent-h's run-783 C5 base: the y1 `z0(0) * ((int)p + (int)p + y0)` fold moves onto the `if (y0 ..) {}` line.
     That frees block-21 IR, so the E4 pooled-count form adds no uopt size-split block.
  2. The E4 count goes in as a pooled inline parameter: `c->atE1(0, c->dl->count)` with
     `Gfx *atE1(int d0, int n) { d0 = d0; dl->count = n + 1; return &dl->buf[n]; }`. The FB and E4 counts become
     one LR on M-132 (v0).
  3. The yh clamp has no dummy (`dm1` dropped). It lands on M-128 (tex / s-middle, a1), and the yh temp e233 takes v0.
  4. **The EE pointer is kept live into the texrect block as a phantom LR.** primDepth returns its `g`:
     `inline Gfx *primDepth(int z, GCtx *c) { ...; return g; }`. Write `ge = primDepth(..)` with `Gfx *ge;` declared
     **at the top of the inner `if`** (a loop-top declaration gives v / __V / r at 196 / 184 / 216). Then add five
     `(int)ge` terms to the existing xh-arm fold:
     `(s16)(xh) + z0(0) * ((int)(s16)(xh) + (int)(s16)(xh) + (int)ge x5)`.
     - The EE pointer's LR (M-232) now runs from block 14 to the xh arm (block 22). It interferes with the FB
       pointer, the dl temp and the counts, so it takes a1.
     - It is also live across e762's blocks (the xh CSE, 21-22), so e762 can't take a1 and takes a2.
     - With a1 used last at the EE w1 store, the yh preset `or a1,zero,zero` is scheduled right after it, as in the
       target. as1 then stops hoisting xl / yl, which restores the 592nd word.
  5. The term count sets the priority. M-232's num is 30 + 10 per term, at den 3 (blocks 15-21 are default-live):
     - 4 terms: 23.3, below e762's 25 (98.36).
     - **5 terms: 26.7.** M-232 is coloured after the FB pointer M-148 (30, a0) and before e762 (25), giving a1, as
        in the target.
     - 6-8 terms: 30 or more, and it is coloured before M-148: EE a0 / FB a1 (99.59).
     - 16 or more terms: block-size split, 593 words.
- **Why it works (target structure):** the a1 holder through the FB / E4 block in the target is the EE pointer, not
  the yh word. That is why the yh preset sits right after the EE w1 store. Our split blocks (`if (c) {}` lines,
  FB's `if (1)`) cut the EE pointer's LR at block 14, and the zero-code `(int)ge` uses rebuild it.
  Lever (general): **to make a value hold its register through later blocks with no code, return it from its inline
  to a block-scoped named pointer and add zero-code fold uses where it must stay live. The fold term count sets its
  colouring slot between the neighbouring priorities.**
- **Also measured (dead ends):**
  - Dead-def copy-keep (`if (zp(g, 0)) g = 0;`) on the FB pointer adds uopt blocks here (591 words).
  - The 13/14 split is a uopt block-size split. Adding IR to block 13 (`x0 = x0 + z0(0) * x0`) moves it earlier,
    and `&c->dl->buf[c->dl->count++]` in primDepth does not move it.
  - A named `yr = 0` preset for yh is constant-propagated away (same bytes as no preset).
- Tools, in /tmp/claude-1000/agent-g/r785/ (agent-h's sc / od / r / vr / lm / keep, re-pointed at agent-g):
  - pv2.py BASE JSON: variant runner;
  - al.py SRC: aligned diff against the target;
  - pre.py: where the clamp presets go;
  - lrq.sh: the 13/14 block split plus the LRs there;
  - v1-v17.json: the batches.

## heli.uso (agent-g run 781)

- **0xB08 EXACT (agent-g 0d3ec4e89 NM 99.15, a0ccd8bd1 NM 100.0, 619872257 matching build; gate PASS each, report
  3577 / 3579, exact set identical, no renames, 943 words + pad, frame 368).** heli: 26 / 26. Scratch:
  /tmp/claude-1000/agent-g/r781/ (`v.py`, `lrv.sh NAME` = M-220's LR and pick cost, `fm.py` = frame-offset map
  of aligned rows). Committed source = `c28.cpp`.
- **0d3ec4e89, rows 312..322 (q in v0):** a dead def right after case 2's lookup, `if (zp(p, 0)) p = 0;` with
  `zp(v, z) = z * (int)v`. uopt folds it only after copy propagation, so p is multi-def at copy-prop time and
  stays a variable. The call result is then copied into p (the copy coalesces into v0) instead of being propagated as
  R2, so R2's LR ends at the copy and no longer reaches q's block, and q takes v0. Reusing p for q
  (`p = *(p + 0x2C)`) together with this fold is worse (frame words move with dum4A's arguments). The same fold in
  q's block, or inside an inline load helper (`ld2Cz`), also works.
- **a0ccd8bd1, rows 531 / 547 (agent-e run 780 edits, on top of 0d3ec4e89):** the lerp value goes in g (the roll
  value in dist), with no dumf pads and no idm().
  - The mechanism is a uopt COST split (IDO_CODEGEN "needsplit"). The trace line `COL ... save=13 best=10`
    shows that M-220 is coloured while its num (13 appearances) is above f16's call-crossing cost (10).
  - When num <= cost, `split(A, c, 1)` keeps the piece out of the call blocks. The def-only blocks 58 / 60 / 62
    then stay in memory, so the sin result is stored at its def, before the cos argument reload, and as1 fills
    the jal slot with `lwc1 f12,44(sp)`.
  - Any edit that takes the pitch appearances off M-220 does this. Two examples: a fourth `dumf(pf)` (but idm()'s
    parameter is then a new word, M-312, which pushes the uopt temps 4 lower), or one dumf (idm then takes
    M-164, so the lerp value is f12, not f16).
- **619872257, matching build:** HELI_NM_FUNCS is spliced on both builds, and heli_uso.c has a placeholder body
  (as for 0x8A8).
  - The splice renames the donor's .rodata relocs to `heli_uso_func_00000B08_rodata`, pinned at 0x78.
  - The target's jump table is at RoData+0x7C, with the doubles after it unpadded. So the donor has one 4-byte
    const word, `heli_roPad_b08`, ahead of its literals. Every donor offset is then target - 0x78. With no pad,
    the 4 references below the first double are off by 4 at either pin.
  - The donor file keeps its `_nm` name (renaming it is a separate git mv).

## heli.uso (agent-g run 777)

- **0xB08 NM 99.08 -> 99.13 % (agent-g a9b42d1a8 99.10, f64b6905a 99.11, 12f9f5cba 99.13; gate PASS each, 3576 / 3579,
  exact set identical, no renames, 943 words, frame 368).** Raw rows 20 -> 13; register-masked 15 -> 9. Scratch:
  /tmp/claude-1000/agent-g/r777/ (`v.py`, `rd.py`, `ncs.sh` = ncc.sh plus the ugen `-l` listing, with `.loc` lines).
  Committed source = `c25.cpp`.
- **a9b42d1a8, row 585 (the clamp-arm reload):** `mq(float s)` by value, and the vel statement drops the
  `dumf(HF(0x164))` pad (the by-value parameter takes that pooled word, so the set3 words do not move). HF(0x154) is
  now loaded before mq()'s `if (1) {}` cut, at the clamp join, so uopt PRE puts the reload in the clamp arm and the
  fall-through keeps the compare's f0. The bc1fl delay slot is then the join's `lwc1 f4,0(v0)`, as in the target.
  - With `const float &s` the load sits after the cut and is not PRE'd. `float t = s;` before the cut also fixes 585,
    but t is a fresh inline named word (frame map -4).
- **f64b6905a, row 53:** `(char *)(delta + (int)p)`. The int sum keeps the source order (`addu a0,t4,v1`); every
  pointer-sum spelling (`delta + p`, `p + delta`, `&p[delta]`) puts p first.
- **12f9f5cba, rows 95..98:** case 3's test, its `HI(0x16C) = 1;` arm and the `if (1) {}` cut on ONE line. as1 then
  issues the tg addiu, the add.s and the `li 1` in the target's order. (Moving the arm to its own later line, or
  only the cut onto the arm's line, does nothing.)
- **Rows 531 / 547 (the jal / lwc1 f12,44(sp) slot):** the ugen listing shows every inlined slerp instruction carries the
  slerp call's line (`.loc 293`), so line joins inside slerp / slc are inert (13 spellings, incl. slc defined after
  the function). ugen emits `mov.s f16,f0; l.s f12,44; s.s f16,148; jal`: the sa store is the colouring's save of
  f16 at the call, after the argument reload. **Lead:** `slc(const float &sa, ..)` stores the sin result to its
  temp word at the def, and both slots then match the target. But it adds two frame words and loses f16 for M-220
  (96.07 with q0 / q1 dropped to keep frame 368). A word-neutral form of that is the next step.
- **Rows 312..322 (q in v1, target v0):** the LR dump shows p is never a variable: uopt propagates the call's
  return register (`R2`, LR in blocks 34 / 35 / 37), so R2 is live in q's block, and v0 is forbidden for q
  (M-124, fb [1 14]). Inert: reusing p (`p = *(p + 0x2C)`; the new def is then its own LR, still v1); `if (1) {}`
  at four points; `&&` split into nested ifs / goto; the comma-assign in the test; a pointer-returning call cast;
  `setp(p, ..)` / `setp(q, ..)` stores through a reference (ring temp t4, -1.2 %); an expression in place of q
  (ring temp t4). The target needs R2's LR to end before q's block, or q to join it.

## heli.uso (agent-g run 774)

- **0xB08 NM 98.72 -> 99.08 % (agent-g 9312742a5 99.02, ae89b7023 99.06, 95c0f004e 99.08; gate PASS each, 3576 / 3579,
  exact set identical, no renames, 943 words, frame 368).** Raw rows 84 -> 20; the 15 register-masked rows left are
  all structural. Scratch: /tmp/claude-1000/agent-g/r774/ (`v.py`, `rd.py`, and `pp.sh` / `pk4.py NAME LO HI all`
  for the picks, named locals included). Committed source = `c22.cpp`.
- **9312742a5 banks agent-e's run-771 edits on the m3c0 form** (`b08_e771.cpp`: mq / set3q, the trailing cut in subc,
  the yaw+yaw fold). The same edits on d2r score about 98.3, so m3c0 (the lerp in idm()'s parameter = M-220) is the
  base.
- **Found on m3c0 (superseded by e771, but the mechanism holds):** clampP's dead `if (zf1(v, z)) v = lo;` reads v
  before v is redefined, so uopt propagates that read to the lerp word (M-220's 95:1/0 use). `zf1(lo, z)` keeps the
  copy (v is still multi-def) and drops the use, so M-220 splits at pri 2.0: m3c0 98.52 -> 98.80. On e771 the same
  change is worse (98.22), because e771 needs M-220 joined.
- **ae89b7023: the g / HF(0x144) swap (rows 769..784).**
  - The cause: g (M-256) was one LR joining the yaw-region g and the three angle values (pri 3.33, f2). The target
    has g f14, HF(0x144) f2 and the angles f2.
  - Putting the angle values in `f` (dead after the clamp) splits g off.
  - The angle variable then took f0 before the zero constant did. agent-e's run-756 int-hh form fixes that:
    `hh = 0;` is stored to the five 0.0f slots, and the zero web picks first at 4.0.
  - `dumf(g)` is dropped (it no longer has any effect).
- **95c0f004e:** axZ and axY are now written x, y, z. This fixes the 907 swc1 order and the f6 / f8 swap at 925..933.
- **Left (shared structure):**
  - row 53: the addu operand order;
  - rows 95..98: the head add.s / addiu order;
  - rows 312..322: v0 / v1;
  - rows 531 and 547: the jal / lwc1 delay slot;
  - row 585: the target's bc1fl delay slot is the join's `lwc1 f4,0(v0)`. The target keeps HF(0x154) in f0 across
    the clamp join and reloads it in the clamp arm; ours reloads it at the join. `dumf(HF(0x154))` in place of
    `dumf(HF(0x164))` in the vel statement gives the arm reload, but costs +1 word (99.084, raw 35).

## heli.uso (agent-g run 766)

- **0xB08: no commit (97.84 % stands; 3576 / 3579).** The pitch window is solved structurally, but the build is not
  yet above 97.84 %: the int / FP temp rings are rotated (raw rows about 800), so the score is about 94.5 %.
  Scratch: /tmp/claude-1000/agent-g/r766/ (`v.py` = score, `dr.py` = register-masked diff, `cmpw.py` = pitch
  window, `lr.sh` / `pk2.sh` = LR picks).
- **Best source: `r766/g4.cpp`.** It builds on agent-e's run-764 source (`b08_e764.cpp`).
  - Structure: 943 words plus the pad nop, the frame is correct (no 4-byte shift), and -pi/8 is hoisted into f18
    at the target row.
  - Pitch colours: pf f0, old-h f2, the copy f2, the result f12, hi f0, -pi/8 f18, and the angle value f2 all match
    the target. The only wrong colour is the lerp value: f14 (target f16).
  - The changes from e764:
    - the lerp value in `f`, not `dist`. This fixes the frame and the 320(sp) spill.
    - a **param-copy clamp** `clampP(v, lo, hi, z) { if (v < lo) return lo; if (zf1(v, z)) v = lo;
      if ((hi < v) + zf4(v, z)) return hi; return v; }`. It replaces the local-`w` clampV, which drops a frame word.
      The copy is EDG's M-160.
    - -pi/8's fold moved from the pitch store to the **yaw store address**:
      `*(float *)(self + 0x14C + zf4(-0.3926991f, 0)) = HF(0x14C) + yaw * (0.06);`. This hoists -pi/8 into f18
      at the target row.
      - Keep exactly one fold site for a constant. Two zf sites with shared `lo + lo ..` prefixes get CSE'd, and
        the sum survives as real code (len +3 to +5).
    - the angle sequence in `g` (`dumf(g); g = HF(0x144); .. ppf(.., g)` x3). f's live range is then only
      {A, B, one arm} (pri 2.5).
- **What is left (register-masked rows: 18):**
  - **(1) The lerp value is f14, not f16.** HF(0xF8)'s LR (e1358 #433) spans block 70 and the lerp block. It is
    picked after M-168 (a shared EDG temp, f14 in block 70; it wins the 3.0 tie on a lower index), so it takes f16,
    and f is left with f14. Either break 433's link to block 70, or get F8 picked before M-168.
    - zf terms on HF(0xF4) / HF(0xF8) in a store address don't help. fwdOf reads them through `q`, so the folds
      create new EDG param temps (M-164 / M-168 LRs) instead of adding uses to 433 / 444.
    - A fwdOf variant with a folded member-store address (`fwdOfZ`) and the direct HF form of fwdAx (len 934) are
      both much worse.
  - **(2) The slerp rows 518..558 (three `lwc1 f16,148(sp)` sites).** In the committed source the EDG temp M-220 is
    one LR joining the slerp blocks 56..61 with the pitch clamp (via lerpTo / clampTo), so it gets a colour. In
    every copy-form source M-220 is slerp-only and spilled.
    - The target therefore routes the pitch through the same inline temp as the committed lerpTo / clampTo form.
    - Not M-220: clampf with a default `z` argument, a `clampToP(float &d, ..)` wrapper, `setf(HF(0x148), ..)`, or a
      `float &d` local.
    - **Next:** find which inline's temp M-220 is (the slerp's slc / heli_ff result?) and route the pitch result
      through it.
  - (3) The rows the committed source also has: the head add.s order 95..98, 585, 602 / 637, and 907 (the axZ
    store order).
- Also useful: the lerp `if (1) {}` cut must come after the HF(0x148) store (agent-e's (b)). A cut right after
  `f = lerp` instead gives the copy form, but with -pi/8 not hoisted.

## heli.uso (agent-g run 761)

- **0xB08 NM 97.79 -> 97.84 % (agent-g f74783a86; gate PASS, 3576 / 3579, exact set identical, no renames, 943 words).**
  This banks agent-e's run 756 lever: `zf(-0.3f, 0)` in the HF(0x144) store address.
- **The pitch "split" is not a uopt LR split. It is an un-propagated clampf parameter copy.** The target's
  `mov.s f2,f16` is `v = f` (the inline's param copy). The first test reads f (f16), and the second test and the
  `return v` arm read v (f2). The result goes to M-164 (f12) through three `mov.s f12, X` arms. uopt keeps the copy
  only when v is multi-def at copy-propagation time and the extra def is folded away later.
  - The kept form: `clampz7(v, lo, hi, z) { if (v < lo) return lo; if (hi < v) return hi; if (zf1(v, z)) v = lo;
    return v; }`, called with z = 0. zf1 = `z * (int)v`; uopt folds it only after copy propagation.
  - The copy appears with the dead def before the tests (z4), after them (z7 / z12) and in the arms (z5). A plain
    `if (z)`, an `if (0)` or a second named copy (g / pf / yaw / a local w) is propagated, so no mov appears.
    Explicit `v = lo / v = hi` arms (K1 / K2) keep a copy but give the wrong arm shape.
  - The copy is the shared EDG temp M-160 (or M-312 for a local `w`), not a new frame word. The angle blocks no
    longer need f, so f's role in the target is the lerp block only.
- **The pf statement is two statements in the target:** `pf = dot(fwdAx, vel) / 200.0f; pf = pf + fwdAx.y * (0.1);`
  (P1). This gives the target's `cvt.d.s f4,f8; div.s f0; ..; cvt.d.s f8,f0; add.d; cvt.s.d f0` exactly.
  - On the copy body it is worth +0.9 (94.08 -> 95.01). On the committed body it is worse (93.97), because there
    the ring shifts.
- **Where it stands:** `r761/w/R4_0_4_q5.cpp` (fwdOf, no `if (1) {}` before fwdOf, P1, clampq5, zf4 pf, zf4(-pi/8)
  in the HF(0x148) store address, not in the clamp store). The 28 rows above the pitch store are byte-identical to
  the target. -pi/8 is f18 and the result is f12 (both target). Three colours are still wrong:
  - old-h is f16 (target f2);
  - f is f2 (target f16);
  - the copy is spilled to 56(sp) (target f2).
  The length is 944 or 945 words (target 943), so it can't land yet.
  - zf on -pi/8 in the clamp store address extends -pi/8's LR across the arms to block 98. Put it in the block-91
    store address instead.
  - Extra zf uses of the local copy (`zfK(w, z)`) don't raise its priority. The copy LR (pri 1.5) is picked last,
    with all six colours forbidden.
- **Next:** the copy needs f2 before f is coloured, and f needs f0 / f2 / f12 / f14 forbidden.
  - f's only neighbours are the copy, -pi/8, M-164 and +pi/8, so f0 / f14 need a codeless holder over f's block-91
    tail and arms. That is agent-e's zf-constant holder, now aimed at the copy's colouring order rather than a
    split.
  - Also: raise the copy above f (its uses are in the arms; try a zf on v in the clamp store address with the copy
    live there).
  - Scratch: /tmp/claude-1000/agent-g/r761/
    - `v.py` = score;
    - `pm.py` / `cmpw.py` = pitch-window diff against the target;
    - `lr.sh` + `pk2.sh` = LR picks;
    - sweeps s13..s23.

## heli.uso (agent-g run 758)

- **0xB08: no commit (97.79 % stands; 3576 / 3579).** No variant produced the target's `mov.s f2,f16` pitch split, so
  the head fix still cannot land at 943 words. About 450 compiles. Scratch: /tmp/claude-1000/agent-g/r755/ (`bZ.cpp` =
  fwdOf + q1f + head fix + agent-e's zf6 on -0.3f + zf4 on -pi/8; `g1..g6.py` sweeps; `pit.py` prints the pitch-store
  shape) and r751/ (`fc.sh NAME` = f's LR and pick costs, `pk2.sh NAME LO HI` = FP LRs with pick order).
- **Which split the target uses (IDO_CODEGEN kit CCXCIII item 4).** f's pieces are {lerp block} = f16 and {clamp
  arms, three angle blocks} = f2. A cost split (b) cannot cause it: f's value is num 11 (7 uses + 4 defs) and every
  caller register costs 4. So it must be an eager neighbour split (a). The register taken last is the one the carved
  piece gets, and the piece is seeded where that register is still free. So **old HF(0x148) (lerp block only) must
  take f2 as f's LAST free colour**, after pf f0, HF(0xF4) f12, HF(0xF8) f14 and -pi/8 f18 are coloured in the lerp
  block, and after some f16 LR in f's other blocks (clamp arms / angle blocks). f must still be uncoloured at that
  point.
  - The f16 holder is the open question. No f16 appears in the target's code from the clamp to the end. The
    return-value temp M-160 (EDG's shared inline-return variable: slerp abs, yaw clamp, pitch clamp) is f's only
    neighbour there. In the target it is f12 (the clamp result `swc1 f12,328(s0)`), so it is either split itself or
    the f16 holder is a codeless LR.
- **Priority levers measured (agent-e's zf fold, `z * (int)(x + x ..)` in a store address):**
  - `zfK(pf, 0)` in the `HF(0x148) = f` store address gives pf pri 2 + K (k = 6: pf 8.0 = f0, first).
  - `zfK(HF(0x148), 0)` lifts old-h the same way (k = 2: 5.0, f2).
  - With a `if (1) {}` before fwdOf (no reload, -pi/8 hoisted to f18, 942 words), pf f0 / old-h f2 now match the
    target, but f (3.67) is still picked before HF(0xF4) / HF(0xF8) (3.0) and M-160 (2.83), so it takes f12 whole.
  - Too many zf terms in the lerp block pass uopt's 20-load block limit (kit XXXV) and split it: K >= 12 for one
    term, or pf 8 + F4 / F8 6 each.
  - `dumf(f)` right before `f = (pf - ..)` joins f's LR to the sqrt block 72 (pri 4.0, forbids f0). An eager split
    would then seed at 72, so leave it out.
  - `if (1) {}` after the angle assignments adds no units to f (flat).
- **Next:** the order needs old-h's priority below M-160 (2.83) and F4 / F8, and f's below old-h. The two ways in
  are lowering old-h (a cut between its two lerp uses: `f = pf - HF(0x148); if (1) {} f = f * 0.2f + HF(0x148)`
  gives 2 units, pri 1.5) together with lowering f (more live units), or raising M-160 / F4 / F8 with zf terms while
  keeping the block under 20 loads. Then find the f16 holder.

## heli.uso (agent-g run 755)

- **0xB08 NM 97.71 -> 97.79 % (agent-g 5405f8048; gate PASS, 3574 / 3579, exact set identical, no renames, 943 words).**
  The axZ zero / angle order is fixed: a code-free `dumf(f);` right before `f = HF(0x144); axZ.y = ..` (after the
  HF(0xF4..0x100) stores) makes f's LR reach that block's start, so the 0.0f piece takes f0 and f takes f2 (target).
  `if (1) {}` or moving `f = HF(0x144)` there does nothing. Scratch /tmp/claude-1000/agent-g/r755/ (`v.py` + `ncc.sh`
  with `UOPTX` extra uopt flags, `sw.py SPEC N1,N2` variants x `-varref N`, `lrq.sh NAME` CFG + FP LRs, `ad.py` aligned
  diff).
- **Why the no-reload pitch forms failed: uopt's 20-variable-load block limit** (IDO_CODEGEN kit XXXV). Every
  named-value / direct `HF(0x148) = ..` pitch form ends block 91 before the clamp compare (an extra L0 block), so -pi/8
  is not hoisted into f18 and the value gets one colour. Confirmed with `-varref 22` (diagnosis only). The reference
  forms (lerpTo / clampTo, `float &h`) stay under the limit.
  - **Code-neutral load saver:** `fwdOf(fwdAx, &HF(0xF4))` (an inline taking `const float *q`, with the three fwdAx
    statements on q[0..3]) is byte-identical on base (97.8367) and lets the q1f form (`f = lerp; HF(0x148) = f;
    HF(0x148) = clampf(f, ..)`) keep block 91 whole at N 20.
- **The target's pitch value is the variable f, split.** Target f is f2 in 93..98 (v uses, then the three ppf
  angles) and f16 in block 91, joined by `mov.s f2,f16`: a uopt LR split, not a separate expression. With fwdOf + q1f,
  f is one LR (91, 93, 95..98, pri 3.67) picked before pf (2.0) and old HF(0x148) (3.0) with nothing forbidden, so it
  takes f0 whole (944 words, ring rotated). For the split, f must be picked after pf (f0), old-h (f2) and -pi/8 (f18)
  with every register forbidden somewhere in its range. Store-to-load forwarding (ILOD after ISTR) never happens, and an
  expression written twice is merged into the param (h2 / k / w forms).
- Other near forms: `lerpC -> stClamp(d, (t - d) * k + d, lo, hi)` (p3) keeps -pi/8 in f18 and stores / compares one
  register, but the value lands on pool word M-160 (f2 whole), 942 words. Dummy params to move it change the frame.
- The ugen FP temp ring start depends on the whole function (code added after the last call rotates line 13), so
  ring-rotated scores just mean the pitch code is not yet exact.
- **Next:** with fwdOf + q1f, lower f's priority below 2.0 or raise pf / old-h above 3.67 (folded uses), then add
  the head fix (944 -> 943 once the mov form appears).

## heli.uso (agent-g run 751)

- **0xB08: no commit (97.71 % stands; 3574 / 3579).** The best variant, 97.84 %, cannot land yet. Its source is
  /tmp/claude-1000/agent-g/r751/e6_head_fix.cpp.
- **Head `or v1,a0` + `lw a0,44(v0)` fixed (97.71 -> 97.84, both-masked rows 53 -> 31).** The fix reads the
  next-marker load as an expression, twice:
  `if (*(char **)(p + 0x2C) != 0) { p = *(char **)(p + 0x2C); if (*(float *)(p + 0x38) < z) store p; }`.
  The load becomes its own LR (a0) for the test and the z compare, and the variable p takes the copy for the store.
  - A new `char *n` local gives the same registers but costs a frame word (376). Reusing `mode` / `key` is worse.
- **Why it can't land: function length.** The target is 943 words. Base is also 943 words, but only because it is
  missing the `or` and has one extra word in the pitch block. With the `or`, the donor is 944 words: 0x1ACC moves
  to 0x1AD0 in the non_matching object, and the gate loses it (3573). The extra word comes from the pitch block:
  - Ours: lerpTo stores, then clampTo reloads `lwc1 f2,328(s0)` and needs a `c.lt.s` / `nop`.
  - The target keeps the lerp value as a register LR (f16): `c.lt.s f16,f18; swc1 f16; mov.s f2,f16`.
  - Fixing the head needs this pitch fix in the same commit.
- **Pitch variants** (all 944 words or a different frame, and the ugen FP temp ring shifts):
  - a named value through f / pf / g, or a block float, gives the target's no-reload shape (q1f: masked both 28,
    but raw 94.1 because the f4 / f8 / f10 ring moves everywhere);
  - a shared `float &h`, a `float *h`, a local inside clampTo, and a lerpTo with a local result all still reload.
  - Next: find the no-reload form that leaves the ring alone (possibly a pool-word or `me()` lever on the lerp
    inline).
- **g / HF144 / -0.3f colour (instrumented trace, `r751/pk.sh`).** Picks go by priority:
  - HF144 (e1358, num 3 / den 1 = 3.0) takes f0;
  - yaw (2.5) takes f12;
  - g (2.0) takes f2;
  - -0.3f (K, num 1 = 2 uses - 1 load, den 2 = 0.5) takes f14.
  - Every LR is caller-range, cost 0, so the lowest free register wins.
  - The target needs an f0 holder in HF144's block, picked before HF144. Only -0.3f qualifies, so it needs
    pri > 3. g then follows (f0 HF154, f2 HF144, f12 yaw, so f14).
  - An `if (1) {}` between the HF144 store and the clamp separates them (-0.3f then gets f0), but it also splits
    the as1 block (+2 words, 96.78).
  - Flat or worse:
    - `float lo = -0.3f` anywhere;
    - a separate clamp result;
    - ternary or if-form clamps;
    - an h local with a cut;
    - moving g's declaration (only frame words move);
    - void return types for 0x980 / QNode_update and a pointer return for queryType (flat; coordinator's
      return-type lever).
  - Untried: folded counted uses of the -0.3f constant in its block (MATCHING_SUMMARY §4).
- The same constant-before-memory-LR pattern shows at the axZ block: target zero f0, f var f2; ours the reverse.
  The zero piece splits late from the 16-unit 0.0f LR.
- Case 2's `lw v0,44(v0)`: q stays v1 under every q / p form tried (q = p, p = next, declaration order,
  `((char **)p)[11]`). Without a q variable it becomes a ugen temp (t4).

## heli.uso (agent-g run 747)

- **0xB08 NM 96.39 -> 97.71 % (agent-g b98304565 97.43, 99ded151c 97.71; gate PASS each, no renames, 3574 / 3579,
  exact set identical).** Case 4 is now byte-identical to the target.
- **The sp+252 entry unit is an empty two-predecessor block.** `case 3: if (..) {..} if (1) {} L4: break;` and case 4
  ending in `goto L4;` (= break). uopt's K-116 split grows case 4's piece over its successor L4 (ADJ), and L4 has a
  second predecessor outside the piece, so the piece has two entry units for two uses (num 0): case 4 is not coloured
  v1 and rematerializes t8 / t4. Placement matters, because L4 is a predecessor of the switch join and takes the ps
  (a2) PRE def:
  - L4 at case 4's own end (case 3 `goto L4`, first commit, 97.43): case 4 falls into L4, so the `addiu a2` lands in
    the join branch's delay slot instead of mid-case.
  - L4 = case 3's if-join (no `if (1) {}`, 97.46): that block also takes case 3's tg (v0) PRE def, and case 4's
    `V3(0x12C) = *tg` copy folds to 276(s0).
  - L4 after case 6's break / default / end of switch (96.99): it is laid out last, falls into the join, and as1 does
    not copy it.
  - L4 at the end of case 1 (97.27): case 4 is exact, but case 1 now falls into L4 and gets the a2 problem.
  - The kept form: L4 after case 3's join (the `if (1) {}` keeps them apart) ends in `b join`, so as1 copies
    `addiu a2; b join` into case 4 (scheduled mid-case, `swc1` in the slot), and case 3 falls into it with a2 in the
    delay slot, which is the target's case 3.
- `yaw = (6.2831855f) + yaw` gives the target's constant-first `add.s` (+1 row).
- **2.0f / f2 (not solved; the diagnosis is narrower).** The side.x / y / z 2.0f is one live range (K2, uopt bp 691)
  over units 70 and 71. It is coloured late (it splits from the function-wide 2.0f LR at pri 0.71). HF(0xF8) (LR 432,
  `{1358|18}`, units 70 and 91) and HF(0xFC) (436) are coloured first.
  - The target needs F8 = f14, FC = f0 and 2.0f = f2. 432 gets f14 only if f0, f2 and f12 are already taken in units 70
    and 91. That ties this residual to the g / HF144 / -0.3f colours in unit 91 (target f14 / f2 / f0).
  - lre.py's register column is one off for FP: colour 24 = f0, 25 = f2, ... 29 = f18.
  - Zero-code unit shifters work under EDG with `(*(int *)(self + K) - *(int *)(self + K))` (they move the uopt unit
    cut). `& 0` / `* 0` / `0 &` fold first, and so do the minus form in `player`'s address (it is evaluated before
    subc's cut) and in `V3(0xDC) += vel`.
  - In the side.x load address, 8 shifters move the cut to side.x / side.y but the bytes stay the same. In toTgt's
    store address, 4 shifters put all six 2.0f uses in one unit (pri 5.0) but it takes f14 (97.21). Six or more change
    the code (95.19). `if (1) {}` cuts around toTgt / side cost 3+ points.
- Other negatives: `p + delta` for the vcall `this` (`addu a0,t4,v1` order unchanged).
- **Next:** the unit-91 colour order (g / HF144 / -0.3f), which also decides HF(0xF8)'s colour and so the 2.0f f2.
  Smaller ones: case 3's `addiu v0` schedule position, case 2's `lw v0,44(v0)` (ours v1), the p / q `or v1,a0` copy
  at the top, and 148(sp) f16 vs f14.

## heli.uso (agent-g run 742)

- **0xB08 NM 95.76 -> 96.39 % (no renames; gate below).** This uses agent-a's viewrec 3878 lever. One line before the
  donor body, `extern "C" void *heli_updateSlot_b08 = (void *)heli_uso_func_00000B08;` (the Heli vtable's update
  slot), makes as1 treat the function's address as a target of the switch `jr`. The case-6 default is then no
  longer an exclusive block, and xbb fills the bound check's delay slot with the dispatch `sll`, as in the target.
  Both-masked rows go from 68 to 63. A `static` array holding the word does nothing (95.76); an `extern "C"`
  scalar or an extern array both work. None of the run's other probes adds anything on top of this.
- **The case-4 `sp+252` hoist is uopt's live-range split order.**
  - The `-116` lda is one constant live range (bp 680, `r742/lr.sh`: zdbug:5 plus the SAVE / PICK / ADJ trace).
  - Its unit list runs dir (bb45), vel (67-69), and then the case blocks in DESCENDING table label: 7, 6, 5, 4,
    then 2 and 1. (uopt numbers the blocks in source order: case 8 = bb24, case 4 = bb28, case 7 = bb29,
    case 1 = bb30, case 5 = bb31, case 6 = bb42.)
  - The split takes pieces in that order:
    - case 7 absorbs the switch join bb44, so its num is 0 and it is not coloured;
    - case 6 has one use, num 0;
    - case 5 and case 4 have num 1 each and are coloured v1;
    - the remainder (2, 1) has num 0 and stops.
  - A piece's num is its uses minus one per entry unit. To match the target, the remainder after the case-5 piece
    must reach num <= 0 while it still holds case 4. That needs one more entry unit, or one fewer use, among
    case 4 / case 2 / case 1 / bb41 / bb46.
  - `if (1) {}` splits inside case 1 or case 4 add no entry (the two halves are adjacent). A sweep of 102
    single-cut positions from the switch to vel is all flat.
- **Case-6 zero-code alias:** no longer needed. For the record, EDG 2.29 rejects every zero-size type (`char c[]`
  is error 3163; `[0]`, `[1-1]` and a template `[N]` are 3187). `int : 0` copies one byte (92.35). A `0 * (int)&G`
  fold in case 6 moves registers (95.62).
- **vel / HF(0x154):** the target keeps HF(0x154) in f0 across the clamp join: `bc1fl` with `lwc1 f4,0(v0)` in the
  delay slot, and a reload on the store path. A load in the join block, `float k = s;` before operator*'s cut,
  gives that shape. But k becomes its own live range (`mov.s f14,f0`), and the products miss the target's
  f12 / f14 / f16 because the 2.0f constant is f18 here and f2 in the target. That scores 95.20 (96.35 with the
  slot word). `dumf(HF(0x154))` keeps a dead second load (+1 insn).
- **g / HF(0x144) / -0.3f:** the target has f14 / f2 / f0, ours f2 / f0 / f14. Colour order: HF144 (pri 3.0)
  takes f0 first. The target needs the -0.3f constant (pri 0.5) to get f0 ahead of HF144, so the target's
  priorities differ a lot here. The lerpTo form, removing the cut, `dot()` for g, and `g = g * ...` are all
  byte-identical.
- **Next:** an entry unit in the K-116 remainder, then the 2.0f constant colour (f2), which unlocks the vel products.

## heli.uso (agent-g run 739)

- **0xB08 NM 95.39 -> 95.76 % (agent-g 9119c7161; gate PASS, no renames, 3571 / 3579, exact set identical).**
  `dir = tg->sub(*ps)` (the ctor-less, end-cut sub() of run 735) and `toTgt = (*(Vec3 *)player).subc(*ps)` (same
  body, `if (1) {}` first). dir's op- result temp (sp+212) stops being a coloured this-or-new join value (target
  `addiu t3,sp,212`, ugen), so the op= temp sp+252 takes v0 as in the target, and the toTgt loads match. With
  toTgt on the end-cut sub() too it is 95.54 (the 2.0f constant then loads late, f14); toTgt start-cut + dir
  start-cut 92.99; both cuts in toTgt's 95.54. Harness `/tmp/claude-1000/agent-g/r739/` (`pv.py` = r730's with
  base / w here; `xb.sh` = dbg.sh with `as1 -xbbdbg 9` -> `x.o.xbb`).
- **Case 4's sp+252 follows the case LABEL VALUE, not the body.** Bodies made identical (case 4 cut to the two
  copies, case 1 cut to the two copies): case 4 still hoists `lda -116` into v1, case 1 does not. Swapping the
  labels of the case-1 and case-4 bodies moves the hoist with label 4; swapping 4 and 5 keeps both hoisted; moving
  case 1's body before case 4 / case 3 / case 2 in source order changes nothing. So it is uopt's CFG order from the
  xjp table (index 3 and 4), not the statements. Removing the `+=` lines or the stores from case 4 changes nothing.
  The target hoists only label 5. Not found yet: what in the table-order walk separates 4 from 5 in the target.
- **Case-6 default slot = as1 xbb candidate order (TOOLING_DECOMP "as1 xbb internals", kit CDLVI).** `-xbbdbg 9`:
  the bound check is bb24 (weight 4), the exclusive default bb25 and the jump block bb26 (both 7); xbb tries bb25
  first and moves `addiu $2,$16,276` (line 256). The target needs the default numbered after the jump block (a
  second predecessor through the table side) or unreachable for xbb (`.alias` after case 6's `b`). Kit CDLVI's
  zero-byte struct copies do not port: EDG 2.29 rejects `char c[0]` (error 3187), and an empty C++ struct copies
  one byte (`lbu` / `sb`; the slot does flip to the `sll`, 92.35-95.03). `case 6` + `default` moved to the top of
  the switch also flips it (90.09, uopt reshuffles). The blocks after case 4's and case 5's `b` are already
  weight 65534 in ours (their v1 lda LR's `.alias`), so a uopt LDA LR ending in case 6 would do it.
- **Next:** a uopt address LR ending in case 6 with no surviving code (two uses of one global's address whose
  temps as1 deletes) in C++; or the table-order rule for case 4 (uopt `-zdbug` block order around label 37).

## heli.uso (agent-g run 735)

- **0xB08 NM 94.91 -> 95.39 % (agent-g 13b848f03; gate PASS, no renames, 3571 / 3579, exact set identical).**
  Structural rows (sp + reg masked, `r730/sd2.py`) 79 -> 65, frame-map bad rows 3 -> 2. The vel / toTgt / side
  region now matches the target structurally. Harness `/tmp/claude-1000/agent-g/r735/` (`s*.py` specs for
  `r730/pv.py`; `ud2.sh` = front end + uopt + `ugen -d`, which dumps the **post-uopt** tree: `mtype=R offset=4n` is
  the register uopt put a value in, e.g. offset 8 = v0, 12 = v1).
- **toTgt target point:** `player = self + 0x12C;` after the speed clamp (player is dead by then), and
  `toTgt = (*(Vec3 *)player).sub(*ps);`. The pointer assigned in an earlier block stays a register
  (`addiu v0,s0,300`, loads 0 / 4 / 8(v0)), where `(char *)ps + 0x50` folds into 80(a2). Placement before / after
  the clamp, before or after `Vec3 vel`, `ps + 0x50` vs `self + 0x12C`: all the same.
- **sub() must be ctor-less and end in a cut:** `V3b r; set3(r, x - v.x, ...); if (1) {} return *(Vec3 *)&r;`.
  - With the Vec3 ctor (op- or a sub() returning `Vec3(...)`), EDG's ctor emits `this ? this : new` and the
    temp's address (sp+124) reaches the copy as a join value; uopt colours it (v0), where the target recomputes
    it in t3.
  - Without the cut (92.79), or with the cut at the start of sub() (94.96), or after the toTgt statement (92.40):
    the cut at the end ends the uopt block before the side vector, so the 2.0f / HF(0xF8) live ranges no
    longer cover the subtraction; they take f2 / f14 as in the target (f18 / f0 otherwise).
- **Case 4's sp+252 (still open).** The post-uopt tree shows the cause: in cases 4 and 5 uopt hoists
  `lda -116` into v1 at the case entry (a local constant LR with num 1, units 1, coloured), in cases 1 and 7 it
  leaves the lda inline in each mov. The target colours it only in case 5. No source change inside case 4 moved
  it: `= HF + 5000` form, `*tg = ...` (worse), `V3(0x12C) = V3(0x114)` / `*(Vec3 *)(self + 0x114)`, a block
  around the case or the second copy, code-free dummies between the copies, `Vec3(*tg)` (+16 frame). The
  decision is in uopt's constant-LR setup (`SAVE ... bp>=679` lines from the instrumented uopt). Next: find
  which bp is case 4's lda and why case 1's has no LR at all.
- **Case 6 / default `addiu v0,s0,276` (still open):** this one is as1, not uopt. The post-uopt tree has both
  `v0` and `a2` in the default block (label 33). Ours: as1 moves `addiu v0` into the range check's delay slot
  (the default block has one predecessor), where the target fills that slot with the fallthrough `sll`.
  Letting case 6 fall into the default stops the move but drops case 6's own v0 / a2 / branch (95.28). Default
  first: 94.96. A `case 9:` label, `if (1) {}` in the default, or `default: ;` changes nothing. The target's as1
  sees either a second predecessor or v0 live on the jump-table path; neither is found yet.

## heli.uso (agent-g run 730)

- **0xB08 NM 94.39 -> 94.91 % (agent-g 126df1c68 94.44, f80667918 94.91; gate PASS each, no renames, 3571 / 3579,
  lost: none).** sp-offset rows (reg-masked) 113 -> 82, structural rows 87 -> 79. The frame map (`r719/om.py`) now
  equals the target's everywhere except -84 / -88 (one row each) and one -244 row. Harness
  `/tmp/claude-1000/agent-g/r730/`:
  - `pv.py spec.py [pattern..]`: variants of a base file, scored (`sc.sh`), plus each matching source line's EDG
    words from `fl.py` (agent-e's `ud.sh` dump; `R` float, `A` pointer, `l` lda of a struct word);
  - `tw.py uoptlist`: simulates `spilltemps` (kit CCXCIII) from a `-zdbug:4` dump and prints each coloured item's
    temp; make the dump with `ZDBUG=-zdbug:4 /tmp/claude-1000/h414/t/dbg.sh x.cpp x.o` (run in an empty dir);
  - `sd2.py`: structural diff vs the target with the running instruction-count delta.
- **The slerp temps (t -160, X -188, two words, ang -200, sa -220) come from the EDG word rules:**
  - Ours had t one word low because the dir op-'s ctor `this` took a fresh A word at -160. With two old free A
    words, op-'s `v` and the ctor `this` reuse them and the three ctor floats start at -160. A code-free
    `dum4A(q, q, q, q)` (bodies `a0 = a0;`) in case 2's inner block takes -80 / -104 (old, locked) and makes
    -140 / -144 fresh A words. Case 2's `float k` goes (`mpos.y += 3000.0f`), so -140 / -144 are these.
  - The ref-returning op= then puts X right under -176 (-188), as in the target.
  - `float q0 = 0; float q1 = 0;` at the top of slerp (named inline locals are fresh) are the two words between X
    and ang.
  - `dumf(t)` after `Vec3 old = *h` locks the third ctor float word, so the first component's sin term takes a
    fresh word (-220) like the other two. Without it the first takes -168.
  - Placement of the dummies inside case 2, `dum4A(p..)` vs `(q..)`, or q0 / q1 written `= t` is all flat.
  - Rewriting op- without the ctor (V3b + set3 with the floats first) gives the same words but costs 4 %.
- **The 48 / 56 spill slots are spilltemps order, fixed by unfolding the vel loads.** `tw.py` showed the heading
  item (self+0x138, bit 262) and t * ang (bit 297) overlap only each other and ps, so bit order gave the heading
  T0 (56). The target's heading item is also used by vel (`lw v0,48(sp)` after the slerp, `lwc1 f4,0(v0)`), so its
  range overlaps a T0 holder and it lands in T2 (48). Our vel loads were folded into 312(s0) because op*'s `this`
  store and the loads were in one BB. **`operator*(const float &s) { if (1) {} ...}`** puts the cut between them.
  The loads then go through the item and the slots match. A by-value `float s` with the same cut gives
  `mov.s f2,f0` (93.97). `if (s) {}` / `if (this) {}` / the cut after `V3b r` are also worse.
  A `speedf(self, dist)` inline as op*'s argument (94.56) does not unfold the loads and costs a word.
- **Tried, not taken:**
  - toTgt's tg loads, target `addiu v0,s0,300` then `0(v0)`. The same cut in op- or in a toTgt-only `sub()` gives
    exactly that and structural rows 79 -> 73, but scores 94.52. The cut also moves the toTgt temp address
    (target `addiu t3,sp,124` in the vel block) below it, adding an instruction. `cut()` / comma `cut0()` inside the
    ctor arguments are the same (the lda goes where its copy is, not where `this` is stored).
  - Case 4's sp+252: `if (1) {}` before the second op= (or after any `+=`) changes nothing; right after the first
    op= it is worse (93.62).
  - A separate `char *q` for the marker advance (target `lw a0,44(v0)` then `or v1,a0,zero`) costs +8 frame and
    does not change the registers.
- **Next:**
  - toTgt: find a form whose tg `this` is stored in an earlier BB (as vel's is), with no cut between vel and the
    toTgt copies. One option is a pointer word assigned before the speed if / else.
  - Case 4 / X / case-6 default rematerialisations: the target recomputes sp+252, sp+180 and s0+276 for a second
    use, so its K-116 / K-188 ranges split where ours keep one register. Each missing `addiu` shifts every later
    branch offset in objdiff.

## heli.uso (agent-g run 724)

- **0xB08 NM 94.44 -> 94.39 %, committed for structure (agent-g 46da6df4d; gate PASS, no renames, 3570 / 3579).**
  sp-offset rows (reg-masked) 279 -> 113, raw 455 -> 356, both 82 -> 87. Harness `/tmp/claude-1000/agent-g/r724/`:
  - mk.sh: builds hdr.cpp + b_name.cpp;
  - om2.py: frame-top-relative map, with a bad-row count. Use `r719/om.py` (absolute sp) for the final check,
    because the frame size differs until the bottom is right.
- **The layout now matches the run 719 frame map** from ppr down to the axes (absolute sp 60 / 72 / 84 / 100 match):
  - function scope: `ppr, player, ps, toTgt, dir, dist`, then `Vec3 vel = ...` direct-init, `side`, `f`;
  - `{ int mode; head; { key2, tg; switch ... speed } }`;
  - else-block `{ key, p }`: p is the item and also the old q;
  - case 2 `{ p }`, its inner if `{ q, mpos, k }` (`k = 3000; mpos.y += k`);
  - if-block `{ yaw, hh, g, fwdAx, pf, axZ, axX, axY }`. The int 100 is hh, g is the roll value, pf the pitch
    value. **An unused scalar takes no slot under -O2**, though the -g3 build (vn.sh) still lists it.
- **EDG facts, from probes:**
  - Function scope takes one hidden word after its last variable, before the first block (the target's -84).
  - A ref-returning `operator=` costs one hidden word after the switch block's variables. `void operator=` does
    not, so key2 / tg / ps would also fit -96..-104.
  - Declaring axes / mpos mid-block moves code: the hoisted `addiu a1,sp,84` is lost (both +7). Declare them at
    the top of their block.
  - mpos direct-init costs 1 %.
  - `vel = ...` as an assignment (op=, `.set(const &)`, placement new, or a V3b op=) breaks registers
    (sp rows ~1100). vel must stay a direct-init.
  - toTgt from fresh `self + 0xDC` expressions costs 2 %. ps must be one LR from the switch to toTgt (target spill
    at 52(sp)), so it is the function-scope scalar.
  - tg / ps as expressions cost 2-6 %.
  - The named h costs a slot, and the target has none. As an expression it costs 0.17 (i_h).
- **Left in the frame:**
  - the slerp temps: target t at -160 directly under the dir op- temp, X at -188, two words between X and ang.
    Ours has t one word lower and X directly above ang. Param order makes no difference.
    `slerp(Vec3 *, const Vec3 *dp, float)` drops a word (sl2).
  - spill slots 48 / 56 swapped;
  - case 4's sp+252 (not reworked this run).

## heli.uso (agent-g run 719)

- **0xB08 NM 93.25 -> 94.44 % (agent-g 872258c52; gate PASS, no renames, 3570 / 3579).** Masked rows (sp + reg)
  86 -> 82, raw 624 -> 455. The frame is now the target's 0x170. Harness `/tmp/claude-1000/agent-g/r719/`:
  - v.py: variant scorer (`N=name` with s0.py scores a file as is);
  - om.py: target -> ours sp-offset map over the aligned rows (`<<` marks a mismatch);
  - vn.sh: named frame slots via -g3 / md.py, with `{ }` block nesting;
  - t/: small EDG 2.29 probes.
- **Lever: the slerp as `slerp(Vec3 *h, const Vec3 &dir, float t)` (h a pointer parameter, called with FWD).**
  Each component goes through `slc(float sa, float t, float ang, float o, float d, float s)`:
  `return ff((1 - t) * ang) * o / s + d * sa / s;`, called as `slc(ff(t * ang), t, ang, old.x, dir.x, s)`.
  - Because sa is an inline parameter, it is coloured (the target reloads it into f16 per component). ugen then
    evaluates the old-heading term first, as in the target.
  - slc's parameter order makes no difference.
  - `Vec3 &hr` + `Vec3 *h = &hr` scores 94.41. The pointer parameter scores 94.44 (reg-masked rows 548 -> 279).
  - A float local for the cos term inside slc loses (92.9).
- **Did not pay on this base:**
  - the late `tg = self + 0x12C; if (1) {}` (93.96);
  - case 4 through a V3b-typed operator= overload, `.set()` members, or `Vec3(*tg)` (identical or worse);
  - an addf() / setf() reference helper or `tg->y += f` (q1-q8);
  - the run 706 phantom `f = f + (HI(0x16C) & 0)...` after `HF(0x11C) += f`. At k = 7 it gives 94.53, both 79,
    but it cuts the wrong LR: `addiu v1,s0,300` appears, and the temp address stays coloured. Not taken.
- **Frame layout (most of the 455 raw rows are sp offsets).** vfp = sp - 368 in the target:
  - -12 ppr, -16 player (t0 spill home), -20 one scalar;
  - -32 toTgt, -44 dir, -48 dist, **-60 vel**, -72 side, -84..-76 three words;
  - -88 key, -92 one word, -96 key2, -100 / -104 two words;
  - -116 the op= by-value parameter temp (first used in case 4);
  - -124 / -120, then -136 mpos, then -144 / -140;
  - -156 the dir op- temp, -160 t, -176..-164, -188 X (see below);
  - -200 ang, -204 s, -216 old, -220 sa;
  - -232 the vel op* temp, -244 the toTgt op- temp, -256..-248;
  - -268 fwdAx, -272, -284 axZ, -296 axX, -308 axY (so the axes are if-block locals).
- **EDG 2.29 allocation rules, from probes in t/:**
  - All variables of a scope are allocated at scope entry, in declaration order, before any temporary, even when
    declared mid-block (t6, t15).
  - Inner-block variables are allocated at block entry, after the temps already allocated (t7).
  - Used scalars take a word each. Unused scalars take none, but an unused Vec3 does.
  - `v = expr` on a named local (member operator=, a free `assign(Vec3 &, Vec3)`, through a pointer or a
    reference) always goes through an extra temp X: the ctor temp, then the parameter temp, then X, then a
    member-wise copy into v. Only direct-init (`Vec3 v = expr`) copies straight into v (t1-t18).
  - So the target's vel (-60, no X) is a direct-init at function scope, declared between dist and side. dir and
    toTgt (X at -188, shared) are assignments.
  - The target has only one scalar at function scope before toTgt (-20). tg / ps / mode / h / q (ours -96..-120)
    must live in blocks or not exist.
  - An attempt with the axes / yaw in the if-block, key in the else-block, key2 / mpos / f in case blocks and
    vel + side reordered (`mk_l1.py`) lowers reg-masked rows (279 -> 270) but scores 93.45 (both 91).
- Next:
  - Find a body shape with one function-scope scalar before toTgt that keeps the codegen: the head as an inline,
    or tg / ps as expressions. Then move vel / side and the block locals into the target order.
  - Case 4's sp+252 is still CSE'd. The fix is an LR / unit cut between the two op= copies that does not
    materialise self+0x12C.

## heli.uso (agent-g run 714)

- **0xB08 NM 93.27 -> 93.25 %, committed for structure (agent-g 39191f6b4; gate PASS, no renames, 3569 / 3579).**
  On d4, the heading pointer `h = FWD; gl_func_00000000(h);` is a named local used for the three slerp stores and vel
  (`Vec3 old = *FWD` and the dot product stay on FWD). The sp+reg-masked diff rows go from 93 to 86 for -0.02 objdiff.
  Harness `/tmp/claude-1000/agent-g/r714/`: v.py (parallel variant scorer; prints objdiff % and raw / sp / reg / both
  rows), bd.py (both-masked diff blocks), reg.py (diff rows per 100 lines), dz.sh (uopt -zdbug:5 dump), gen_if2.py
  (`if (1) {}` sweep spec).
- **Lever, structural: the slerp is an inline function** `static inline void slerp(Vec3 &hr, const Vec3 &dir, float t)`
  (`Vec3 *h = &hr;` inside, with ang / s / old / sa as its locals), called as `slerp(*FWD, dir, HF(0x164))`. That
  reproduces the target's t handling: t is loaded in the dot-product block and spilled, reloaded into a coloured FP
  register in the old-copy block, then stored again in the if block (`swc1 f2,208(sp)` twice in the target). As a
  plain local, t is never coloured (its uopt LR pieces have adjsave <= 0). The frame becomes the target's 0x170.
  Every call-separated segment except the switch then has the target's t-reg def count. On d4 + h + late tg (below):
  `w/d4_ref.cpp`, both-masked rows 77 (target length 943, ours 942), but objdiff 91.85 because the head ring
  shifts. Remaining differences: t is f14 where the target has f2 (the fabs temp is f2 where the target has f14),
  and sa is not coloured (target f16).
- **Late tg with a cut:** `tg = (Vec3 *)(self + 0x12C); if (1) {}` just before `Vec3 vel = *h * ..` gives the target's
  vel-block address shape: op* r, the return temp in v1, vel, `addiu v0,s0,300`, then the op- r, all in the target's order.
- **The switch's missing 2 t-defs are case 4's sp+252.** The target recomputes it for each op= copy (`addiu t8` / `addiu
  t4`); ours CSEs it into v1. No change from: `V3(0x114).y += f`, moving the f assignment, `Vec3(..)` copies, the
  self+0x114 spelling of the second copy, or `if (1) {}` after the += lines. Moving the three float stores ahead of the
  second copy loses 2.
- Side block (not fixed): the target colours only F8 (f14), FC (f0) and 2.0f (f2). It reloads F4 / 0x100 / F8 / FC for
  side.y / side.z and spills toTgt.x to 32(sp) (a ugen spill). Ours colours all four field loads and puts 2.0f in f18.
- Next: put the inline slerp on the committed base and fix its FP colours (t f2, sa f16). Then fix case 4's sp+252,
  which brings back the head ring.

## heli.uso (agent-g run 710)

- **0xB08 NM 93.21 -> 93.27 % (agent-g commit e0ac9773e; gate PASS, no renames).** Exact count unchanged (3568 / 3579).
  Draft `/tmp/claude-1000/agent-g/r710/d4.cpp` (= the donor). Harness `/tmp/claude-1000/agent-g/r710/`: pg.py (parallel
  greedy over a candidate spec, 16 jobs), c*.py (specs), plus r706/var.py and r695/m.sh.
- **Lever: ctor-less operator* through a by-value setter.** `V3b r; set3(r, x * s, y * s, z * s); return *(Vec3 *)&r;`
  (`set3(V3b &, float, float, float)` inline). The args are evaluated before the stores, so the three mul.s issue
  before the swc1s, as in the target. The temp is a one-use LR in a t-reg (t4 / v1 / t7 for op* temp / return / vel,
  target t5 / v1 / t8). A plain `V3b r; r.x = x * s; ...` interleaves mul and store (90.97). Named float locals
  (`float a = x * s, ...`) batch the muls but each costs a frame slot (91.7). Plus `if (1) {}` before the
  `HI(0x170)` test (+0.016; the only `if (1) {}` position that moves anything on this base).
- **Not combinable:** the late `tg = self + 0x12C` on this base folds to 300(s0) again (92.80). The H() heading
  pointer gives both-masked 82 but 91.8. op- through set3 / V3b (85.9), a separate ctor-less sub() for toTgt
  (87.5), and op* as `Vec3 r; ...; return r;` with the default ctor (92.9) all lose.
- **agent-e's POD lead (no ctors, `ct3(&r, ..)` with `if (p != 0)`, `ct0(&r)` with `if (p == 0) p = new`):** with Vec3
  POD and op- through ct3 (`r710/p2.cpp`) the switch-case region is structurally right (masked diff rows 376 vs 460).
  But the slerp / vel / toTgt region is worse and it scores 92.64. On p2, op* through ct3 or ct0 + ct3, H(), the late
  tg and an `if (1) {}` sweep all lose. An op- returning a ctor-ful `Vec3C : Vec3` temp scores 92.2. A POD
  `Vec3P` with a by-value operator=, used only for the switch's V3() copies on d4, gives identical bytes.
  Empty `Vec3() {}` ctors on the named locals change nothing (V3b locals give identical bytes).
- **Register picture (d4):** the HF(0x154) LR gets f14 (target f0), HF(0x150) f0 (target f2) and dist f2 (target
  f12). The vel op* scale register follows from that.
- Next: p2 (POD) plus the slerp / vel registers. Its remaining structural rows are the heading pointer (48(sp)
  spill), the vel / toTgt temps (`addiu v0,s0,300`, `t3,sp,124`), the side-block 2.0f and the lerp mov.s.

## heli.uso (agent-g run 706)

- **0xB08 NM 93.08 -> 93.21 % (agent-g commit 950053c32; gate PASS, no renames).** Exact count unchanged.
  Draft `/tmp/claude-1000/agent-g/r695/q1.cpp` (= the donor). Harness `/tmp/claude-1000/agent-g/r706/`: var.py
  (base + spec of string replacements, scores and prints the vel-block `addiu` lines), dz.sh (uopt -zdbug:5 dump,
  the address-constant LRs with their uses), sweep.py (`if (1) {}` before each line), ph*.py (phantom sweeps).
- **Lever: `if (1) {}` before case 2's `V3(0x12C) = V3(0x114)`.** Without it uopt colours self+0x12C (v0) for the
  three op= stores; the target folds them to 300 / 304 / 308(s0). With the cut they fold as in the target.
- **Reading the address LRs.** In the -zdbug:5 colouring, a local's address is a constant LR `4 -N` (N = the
  virtual-frame offset; sp offset = frame - N). Register numbers: 1 = v0, 2 = v1, 3 = a0, 5 = a2, 14 = s0.
  The `forbidden` list is printed after colouring, so it shows the final registers of interfering LRs.
  In the vel block, each ctor temp (`return Vec3(..)`) has 2 uses (the copy plus the ctor's `this`), adj 1.0, so
  it is coloured. The vel slot and the op= parameter copy have 1 use and get ring t-regs. The target's op* / op-
  temps behave like 1-use LRs.
  - **Without ctors the temp drops to 1 use.** A `struct V3b { float x, y, z; }` result
    (`V3b r; r.x = ..; return *(Vec3 *)&r;`) or a ctor-less Vec3 makes the op* temp a t-reg (target shape),
    and the return temp then takes v1 (`s1`: t8 / v1 / t2). But the scheduling and the rest of the
    function move, so the score drops (90.4 with h1, 87.6 with both operators on q1).
- **tg = self+0x12C in the vel block (target `addiu v0,s0,300`).** On the h1 base, adding the case-2 cut and then
  `tg = (Vec3 *)(self + 0x12C);` just before vel reproduces the late `addiu v0,s0,300` (`n1`, regmask 247,
  both-masked 84, the best rows yet) but scores 91.2. Without the case-2 cut, uopt's PRE hoists the expression into
  every switch case (case 2's coloured self+0x12C makes it partially available).
- Case 4's doubled sp+252 is not fixed yet. `if (1) {}` before any case statement changes nothing, except before
  `HF(0x118) += f` (91.9). A phantom `f = f + (k summed (HI(0x16C) & 0) terms)` before the second op= has an effect only at k = 7
  (93.31, a unit cut inside the op= copy, not between the copies). It is not taken.
- Next: combine the ctor-less op* (1-use temp) with n1's late tg and the case-2 cut. Then recover the scheduling;
  the V3b form stores each product right after its mul, while the target batches three muls before the stores.

## heli.uso (agent-g run 700)

- **0xB08: no gain, nothing committed.** The best is still 93.08 % (donor = `r695/c_e3m4.cpp`). Exact count unchanged
  (3564 / 3579). Harness `/tmp/claude-1000/agent-g/r700/`: srch.py / srch2.py / s3.py (slot-combination
  searches, which print the objdiff %, the both-masked rows and the per-segment t-def mismatches). In `r695/`:
  pad.py / padat.py (insert dummy `HI(a) = HI(b);` ring allocations before anchors), and rows.py (diff rows with
  the padding lines and branch offsets stripped).
- **Ring padding alone is not the lever.** Seven dummy allocations at the end give the target's head
  (t7 t8 t0 t1 ...) but score 91.27. The other segments then shift with it. The numbering runs backward from the
  end, so each segment's register names follow the allocation count AFTER it. Fix the segments tail-first. 15 (the
  vel / toTgt block) is the first mismatch counting from the end.
- **Named heading pointer `Vec3 *h = H(self); gl_func_00000000(h);`, used for old / the 3 stores / vel.** This is
  the target's h LR. The old copy now reloads h into v0 from its spill slot, and vel loads 0(v0), as in the target. Segments 9,
  11 and 13 then match (only 3 +2, 4 +1, 15 +2 differ), both-masked 87 -> 72 rows, but the score drops to 91.3
  (registers shifted; `r695/h1.cpp`). H() only on the stores (`d00007`) gives 91.09, both 93. H() on loads
  (dot, old, vel) without the named variable is byte-identical to FWD.
- **Segment 15's missing 2 allocations are the op* and op- temp ADDRESSES** (target `addiu t5,sp,136`,
  `addiu t3,sp,124`). Ours colours them (v0 / v1 / a0) and the target does not. In the target, v0 holds a fresh
  `addiu v0,s0,300` (toTgt's tg) and v1 the op= parameter temp. Tried and failed:
  - A fresh `Vec3 *tt = self + 0x12C` declared before the vel statement is NOT folded, but uopt hoists it into
    all 10 switch cases. Declared after vel, it is folded into 300(s0).
  - `T(self)`, `((Vec3 *)self)[25]`, `FWD[-1]`, `tg += 2` and `tg[2]` all fold or spill.
  - `h[-1]` keeps h in v0 and loads -12(v0): regmask 252 (best seen), but 90.99.
  - `vel` as a block decl, an outer assignment or a direct-init, and `*ps += vel`, change neither count.
  - Named-result operator* / operator- (`Vec3 r; ...; return r;`) and friend operators also failed.
    The named-result operator- gives fewer raw rows (536), but scores 90.27.
- **Case 4's op= parameter temp:** the target computes sp+252 twice there (t8, t4: ugen temps, not CSE'd); ours CSEs
  it into v1, as the target does in case 5. Block-scoped f, braces and `if (1) {}` change nothing, and the uopt
  20-load unit counter only reaches 14 in case 4. This accounts for the +1 in segment 3, together with the
  marker-block `or v1,a0` copy and the jump-table delay slot.
- Next: find why uopt does not colour the op* / op- temp addresses in the target (read their LRs in a -zdbug:5
  dump of `h1.cpp` vs the colouring rules). Then apply h1 with the segment 15 fix, so that segments 5-14 line up.

## heli.uso (agent-g run 695)

- **0xB08 NM 92.4 -> 93.1 % (agent-g commit 257cc75a2; gate PASS, no renames).** Exact count unchanged (3564 / 3579).
  Rows (`r695/m.sh`): raw 564 -> 569, both masked 102 -> 98. Draft `/tmp/claude-1000/agent-g/r695/c_e3m4.cpp` (= the
  donor). Harness `/tmp/claude-1000/agent-g/r695/`: v.py (string-replace variant + score; `BASE=` env picks the base),
  dif.py (sp-masked opcode diff), tdef.py (t-reg defs), seg.py (t-reg defs per call-separated segment), units.py /
  mpu.sh (agent-h's instrumented uopt run behind the mp72 front end; code is identical to the normal build).
- **Clamp arms (+0.2):** the target writes the clamp result register in every arm (`mov.s f2,f12` / `mov.s f2,f0`
  for yaw, f12 for pitch). A nested ternary gives an inner temp plus a copy. `clampf()` written as
  `if (v < lo) return lo; if (hi < v) return hi; return v;` writes the return register directly; the yaw clamp goes
  through it too (`yaw = clampf(yaw, -0.3f, 0.3f)`). The pitch clamp stores through a reference (`clampTo`, +0.03).
- **toTgt through ps (+0.4):** `tg = (Vec3 *)((char *)ps + 0x50)` (= self + 0x12C) puts the toTgt loads in the
  target's order (the loads use 80(a2) where the target uses 0(v0) with `addiu v0,s0,300`, so the base register still
  differs). Moving `tg = self + 0x12C` before the vel statement hoists the address into every switch case (10 copies).
- **Head t-ring, solved in principle:** ugen's ring is t1 t2 t3 t9 t4 t5 t6 t7 t8 (t0 apart), and the head's start
  register is set by the TOTAL number of ring allocations in the function (one dummy `HI(a) = HI(b);` at the end
  shifts the head by one ring step). Ours has 93 t-reg defs, the target 100; adding 7 gives the target's head
  `t7 t8 t0 t1 t1 t0 t2`. Per call-separated segment (`seg.py e.txt x.txt`) the target has +2 in the marker /
  switch head, +1 in case 2, +1 + 1 in the slerp's x / y stores, -1 in the old copy, +3 in the vel / toTgt block.
  The missing ones are temp ADDRESSES the target puts in t-regs (`addiu t5,sp,136`, `t8,sp,308`, `t3,sp,124`,
  `t3,sp,212`) where ours uses v0 / v1 or folds the address, plus the heading pointer.
- **Heading pointer (agent-b's idea):** `static inline Vec3 *H(char *s) { return (Vec3 *)(s + 0x138); }` for the three
  slerp stores (normalise / old / vel through it change nothing more) reproduces the target's spilled pointer
  (`addiu a0,s0,312; jal; sw a0,..(sp)`, `lw tN` per store) and +3 ring allocations, but scores 92.50 (from 93.08).
  The old copy still loads the pointer into t3 (target v0), and t (HF(0x164)) is loaded before the dot product
  (target: after it, spilled to its home 208). Moving `t = HF(0x164)` after the ang line shifts the ring (90.5).
- **The f16 -> f2 copy after the lerp:** uopt never forwards a float store to a later load of the same field (through
  self, through the reference, or through a named `float &`); the target's copy is a VARIABLE. `f = lerpTo(...)`
  with `lerpTo` returning `d = expr` gives the exact shape (c.lt.s / swc1 / mov.s) but with f's registers (expr f2,
  copy f0; target expr f16, copy f2), 91.1; another variable for the result adds an FP LR and -pi/8 loses f18.
  `return d = d + (t - d) * k` into clampf (agent-b): 89.95. uopt's 20-load unit counter: every `HF()` is one counted
  load (self is a parameter); `p = self;` + `PF()` on the fwdAx lines cuts the count with identical code.
- Next: the vel / toTgt block temps in t-regs (by-value operator= temps, the op* temp), the old copy pointer in v0,
  then the H() stores and the 7-allocation ring together.

## heli.uso (agent-g run 689)

- **0xB08 NM 88.9 -> 92.4 % (agent-g commits 7a9605497, 19b2c308b; gate PASS each, no renames).** Exact count
  unchanged. Rows vs the target (`r689/m.sh`): raw 729 -> 564, both masked 139 -> 102. Draft
  `/tmp/claude-1000/agent-g/b08_keep/mp72_r689_924.cpp` (= the donor).
- **Reading constant colouring from the uopt dump.** In `-zdbug:5` "global coloring", a constant LR is an entry whose
  next line is `const------>` and then the value; the header's last number is the register (-1 = not coloured;
  FP 24..29 = f0, f2, f12, f14, f16, f18). `adj` is (uses - 1) / blocks. Script: `r689/lr.py` (all constant LRs),
  `r689/lrb.py <uoptlist> <bb>` (every LR live in one block), `r689/bk.sh` (which block holds which constant).
- **Why the target rematerialises 2.0f / 1.0f in the fwdAx block: register pressure, not priority.** The 2.0f
  piece there has adj 5, but it is split off a whole-function LR late, after the variable LRs are coloured. It gets
  no register when six FP LRs are live in that block: f (f0), two square CSEs (f12 / f14), the HF(0x148) CSE, the
  lerp value and -pi/8 (f18). That only happens when the pitch smoothing and the clamp compare are in the SAME uopt
  block as fwdAx. In our draft uopt started a new block (flow-graph line 0, no branch) after the 3-term dot
  product, and again before the clamp whenever any statement sat between the smoothing and the clamp. Inline
  helpers keep it one block: `dot(fwdAx, vel)` (by const reference), `lerpTo(HF(0x148), f, 0.2f)` (store through a
  `float &`), then `HF(0x148) = clampf(HF(0x148), lo, hi)`. Plain statements, comma / chained assignments and
  `clampf(HF() = f, ...)` all keep the split. `dot(vel, fwdAx)` scores 1.1 lower (mul operand order).
- **toTgt.y zero:** `setf(toTgt.y, 0.0f)` (inline `d = v` through a reference). uopt does not copy-propagate the
  store, so the zero has one use (adj 0, not coloured); ugen reuses the stored register for the y square, as in
  the target. With it the length is summed x, y, z (the real order). `int z = 0; toTgt.y = z;` folds 0*0 away.
- Still open: the HF(0x148) reload after lerpTo (the target keeps the lerp value in f16 and copies it to f2 for the
  clamp's v), the head t-ring (t1 vs t7), the heading pointer at 48(sp), the slerp's t spill at 208(sp), and the
  frame. No frame work this run.

## heli.uso (agent-g run 682)

- **0xB08 NM 85.7 -> 88.9 % (agent-g commits f16209f66, 5ebf3ca4c, d7e81cf74; gate PASS each, no renames).**
  The exact count is unchanged (3560 / 3579). Diff rows vs the target (`/tmp/claude-1000/agent-g/r682/m.sh`):
  raw 829 -> 729, both masked 180 -> 139.
- **Axis-angle tail (85.7 -> 88.2).** The target loads each quatRotateAxisAngle angle with `lwc1 f2` +
  `mfc1 a2`, ahead of the axis stores. A direct `HF(0x144)` argument gives `lw a2`. A block-scope `float r`
  gets the lwc1 / mfc1 shape but costs frame slots (84.6). Reusing the outer float `f`, assigned BEFORE each
  axis (`f = HF(0x144); axZ.y = ...; call(q, &axZ, f);`), gives the target's order. Assigning it after the axis
  scores 85.8.
- Smaller gains: the pitch clamp as an inline `clampf(f, lo, hi)` with `f = HF(0x148)` re-read after the
  smoothing store; the toTgt length summed y, x, z (only rotates the FP ring, the target multiplies x first);
  an `if (1) {}` after the clamp (88.7 -> 88.9; a sweep over the 34 tail statement boundaries, a second one
  adds at most +0.03).
- **The FP constant colouring is the main tail residual.** uopt dump (`r682/ncc721d.sh`, -zdbug:5, uoptlist
  "global coloring"): ours colours the fwdAx 2.0f LR (adjsave 5), the 1.0f, and the toTgt.y zero (adjsave 2).
  The target colours only the side block's 2.0f (f2) and -pi/8 (f18, loaded at the block head), and
  rematerialises 2.0 / 1.0 / 0.0 at every use in the fwdAx and sqrt blocks, spilling fwdAx.x to 32(sp). Not
  levers: a `Vec3 fwdAx(x, y, z)` ctor (per-use 2.0 remat comes back, but the loads are CSE'd across the args,
  86.4); float temps (86.0, 87.9 interleaved); `(a + b) * 2.0f`; reordered / parenthesised / line-split
  slerp terms (identical bytes: commutative canonicalisation); pitch through `HF() = f = ...` (88.4).
- **Head t-ring:** still t1 vs t7. Truncation (`r682/ring.sh`, `rv.py`) shows the start follows the toTgt.z
  use in the sqrt: dropping the z term gives t6, and one extra int statement at the function end gives +1. Read
  the last t-only mismatch per kit CCCXXV. The target holds several address temps in t-regs that ours colours
  v0 / v1: `addiu t8,sp,252`, `addiu t3,sp,124` and `addiu v0,s0,300` (tg kept as a pointer for the toTgt op-).
- Heading pointer `Vec3 *h` on the 88.7 base: 88.26 (88.33 with `vel = *h * ...`). Not taken.
- Frame: not restructured this run (objdiff ignores sp offsets). The run 678 map still applies; `smap.py`
  counts 51 mismatched slots.
- Draft: `/tmp/claude-1000/agent-g/b08_keep/mp72_r682_889.cpp` (= the donor). Harness `/tmp/claude-1000/agent-g/r682/`:
  greedy.py (statement-edit hill climb on the objdiff %), rv.py (variant + score + first t-regs), m.sh,
  sd.py, smap.py, dz/uoptlist.

## heli.uso (agent-g run 678)

- **0xB08 NM 84.2 -> 85.7 % (commit 8a0941bc0 on agent-g, gate PASS, no renames).** Exact count unchanged
  (3558 / 3579). Diff rows vs the target (scratch `/tmp/claude-1000/agent-g/r678/m.sh`): raw 830 -> 829,
  sp-masked 791 -> 770, reg-masked 316 -> 298, both masked 198 -> 180.
- **`100.0f` twice = an int divisor.** With `f *= HF(0x154) / 100.0f` after `if (HF(0x154) < 100.0f)`, uopt keeps
  one FP constant LR (f14) for both. The target rematerialises `lui at,0x42c8` at each site. `int h = 100;
  f *= HF(0x154) / h;` does it: the int -> float conversion folds late (in uopt), so the divide's 100.0f is no
  longer the same constant LR. Not levers: `if (1) {}` in the arm, `(float)100`, `(float)100.0`, a `float h`.
  The same trick on the quaternion `* 2.0f` (fwdAx, target does not promote 2.0f / 1.0f there, ours does: f16 /
  f18) strength-reduces to `add.s x,x` (worse); `(float)2.0` / `(float)2` fold at the front end (no change).
- **The ugen t-ring start depends on the whole function.** Our first temp is t1, the target's t7; a fresh
  function starts at t6. Truncating the body shows our head's temps flip t6 -> t1 when the tail's
  `sqrt(toTgt.x^2 + toTgt.y^2 + toTgt.z^2)` is kept (any two-term version keeps t6), and a dummy function before
  B08 does not move it (no cross-function state). So the head's register numbering is a symptom of the tail;
  fix the tail first. Harness: `tr.py N...` (truncate after body line N, print first temps).
- **Marker block copy (`q -> v1 -> v0`) not reproduced.** Agent-a's pool-temp recipe gives the copy only when the
  helper returns `n != 0 && n->z < z` (n1: `ah1(L, q = L2, z)`, copy in the null-test delay slot, store through
  q), but edg then materialises the bool (sltu / addiu 1 / beqz, 83.8). A void helper with the `if` inside, a
  comma `return (m, ...)`, `L != 0 &&` outside, and passing the named q all coalesce to one register.
- **Heading pointer + `vel = ...` assignment:** the target computes vel as op* temp (136) -> by-value op= param
  temp (252, shared with the switch's op=) -> vel (308) through `h` (v0 from 48(sp)), i.e. `vel = *h * HF(0x154)`
  with vel declared between dist and side. That puts vel / side at the target's 308 / 296 but scores 84.2
  (p1 = h only: 85.4, structure-masked rows 173 vs 180). A named `Vec3 *h` costs a frame slot (frame 384, target
  368).
- **Frame (target, from the code):** outer = pp 356, player 352, q 348, toTgt 336, dir 324, dist 320, vel 308,
  side 296, a 12-byte local at 284, key 280, 4 at 276, key2 272, 4 at 268, 4 at 264; then the case op= temp 252
  (nothing in between). So only three 4-byte outer named locals besides key / key2 (tg / ps / h?); p, mode, f,
  yaw, t, ang, s, sa, fwdAx and the axes must be nested-scope locals or not variables at all. Replacing tg / ps
  with expressions loses the per-case recompute (79.1). Next: wrap the slerp / tail in nested blocks with their
  own locals (t 208, ang 168, s 164, sa 148 sit between temps), and find a spelling of p / mode with no slot.
- Drafts: `/tmp/claude-1000/agent-g/b08_keep/mp72_c6_857.cpp` (= the donor), `mp72_r678_hptr.cpp` (p1),
  `mp72_r678_hptr_velassign.cpp` (v2). Harness `/tmp/claude-1000/agent-g/r678/`: m.sh (objdiff % + raw /
  sp-masked / reg-masked rows), sd.py (structure diff), smap.py (target -> ours sp-slot map), g.py (outer
  declaration list generator), var.py.

## heli.uso (agent-g run 672)

- **0xB08 NM donor moved to MIPSpro 7.2.1, 80.2 -> 84.2 % (commit 1921696de on agent-g, gate PASS, no renames).**
  New donor `src/heli_uso/heli_uso_mp72_nm.cpp` (Makefile HELI_NM_DONOR, built by tools/ncc721.sh, non_matching
  build only); the NCC donor heli_uso_ncc_nm.cpp is deleted. Exact count unchanged (3557 / 3579).
- **The tg / ps per-case recompute was the switch's default edge, not the front-end IR.** The uopt dumps (r663
  dumpm / dumpn) differ in one place only: NCC lowers the switch to an `uequ` chain, mp72 to `xjp`. With xjp and
  no `default:`, the default edge goes straight to the join, and uopt's code motion does not insert
  `self+0xDC` / `self+0x114` into the cases (the case-2 call-arg copy of ps is a separate, split LR; the join
  recomputes). **An explicit empty `default: break;` after the last case** gives the default edge its own block
  (the target's +0x66C block, which case 6 falls into), and uopt then computes both at the end of every case,
  ps kept in a2 across the case-2 call with the target's `sw a2,52(sp)` spill (77.3 -> 82.0). `default:` first
  in the switch: 81.6. Worth trying on any mp72 switch whose cases recompute a join value.
- Other levers: `mode = mode * 1;` before the switch (agent-b's code-free ref; mode takes v0); reading the
  marker's +0x3C back through `self+0x168` after the advance; `Vec3 old = *FWD;` copy-initialised (the target
  copies old with lw / sw words, no by-value operator= temp; 82.2 -> 84.2).
- **Not yet in the donor, but the target does it:** the slerp keeps the heading pointer self+0x138 in a register
  spilled to sp+48 (`addiu a0,s0,312; jal normalise; sw a0,48(sp)`, then `lw v0,48(sp)` for the old copy and
  `lw t3,48(sp)` for the three component stores; the dot product still reads 312(s0) directly). A `Vec3 *h`
  for the normalise / old / stores / vel reproduces that shape but scores 83.9 (register shifts elsewhere);
  draft `/tmp/claude-1000/agent-g/b08_keep/mp72_h6_hptr.cpp`.
- **The objdiff % ignores sp offsets** (moving locals between slots leaves the score unchanged to the last digit),
  so frame work only shows up in the score through the register changes it causes. MIPSpro 7.2.1 frame rules
  (probes t1..t4.cpp in /tmp/claude-1000/agent-g/r672): every declared local gets a slot, register-allocated
  ones too. Outer-scope named locals go first (in declaration order, even ones declared after statements). Then
  nested-block locals and temps follow in textual order, and a block's named locals come before its temps. The
  by-value operator= parameter temp is shared by all the op= in a scope. Target map: outer = pp 356, player 352,
  q 348, toTgt 336, dir 324, dist 320, vel 308, side 296, 12 bytes at 284, key 280, 4 at 276, key2 272, 4 + 4 at
  268 / 264. After that: case op= temp 252, mpos 232, join op- temp 212, t 208, op= temp 180 (dir and toTgt),
  ang 168, s 164, old 152, sa 148, op* temp 136, toTgt op- temp 124, fwdAx 100, axZ 84, axX 72, axY 60.
- Remaining diffs (k3 draft, mnemonics): the marker block has one copy fewer (target `q -> v1 -> v0`); the
  100.0f in `speed < 100 ? f *= speed / 100` is materialised twice in the target (CSE'd once in ours); the yaw /
  pitch clamp constant order; the axis-angle tail (`neg.s` of +0x14C and the axis stores). Drafts:
  `/tmp/claude-1000/agent-g/b08_keep/mp72_k3_84.cpp` (= the donor), and the harness `/tmp/claude-1000/agent-g/r672/`
  (h.sh = mp72 score, dd.sh = e.txt / o.txt dumps, var.py = string-replace variant, gen.py / gen2.py = declaration
  layout generators).

## heli.uso (agent-g run 663)

- **+1 EXACT (3553 -> 3554), +1 NM, gate PASS each, no renames.** Commits on agent-g: 1a0c5a1c7 (0x4C0
  exact), bdac204b7 (0xB08 NM 80.2). heli: 25 / 26 exact, 0xB08 the last.
- **0x4C0 (Heli ctor), cfe C, exact.** The residual was the tail block's colouring: zero web f2, scale f0
  (target: zero f0, scale f2). Fix: read the RoData+0x58 scale FIRST into a block-scope float, then
  `if (1) {}`, then the stores. That lowers the scale LR's uopt priority below the zero's (the target also
  loads 0x58 first). The remaining store order came from a 720-order hill climb over the store groups
  (B4, B8, BC, scale x3, zero x2, 1.0; BC must precede the scale stores). Calls are CALL() / XCALL().
- **0xB08 NM: NCC donor `src/heli_uso/heli_uso_ncc_nm.cpp`** (Makefile HELI_NM_DONOR, non_matching build
  only, as snoweffects). 77.2 -> 80.2 with three levers:
  - RoData floats as **literals** (each site has its own pool word: 5000, 3000 x3, 0.2 double, 0.001,
    100000, pi, 2pi, -pi, 2pi, -0.3, 0.07, 0.3, -pi/8, 0.06, 0.1, 0.2f, pi/8 at +0x9C..+0xFC). The 0.2 lerp
    factor is loaded once in the target; the per-site extern aliases reloaded it after each store.
  - **Frame:** one dead 4-byte local between player and toTgt (target word at sp+348); `Vec3 vel` declared at
    its use. Target slots: pp 356, player 352, toTgt 336, dir 324, dist 320, vel 308, side 296, key 280,
    key2 272, operator= temp 252, mpos 232, t 208, ang 168, s 164, old 152, sa 148, fwdAx 100, axZ 84,
    axX 72, axY 60 (the old c1 comments). The NCC donor still has the temp at 140 and key / key2 at 304/300.
  - the marker test `*(int *)(p + 0x2C) != 0`: the target loads the link twice (t1 for the test, v0 after).
- **0xB08 match (MIPSpro 7.2.1) findings:**
  - The target has no helper call around the switch (the jump table is inline), so the "NCC body + 7.2.1
    switch helper" split does not apply: it stays one compiler, mp72.
  - The same source under mp72 is 75.6. **mp72 already reproduces the target's two separate
    `addiu tX,sp,252` per case** (one per by-value operator= temp copy; NCC CSEs it into one register).
    That makes mp72 the right front end on this point too.
  - The mp72 residual that matters is `&pp`: mp72 hoists `addiu a3,sp,356` into the prologue (and
    rematerialises it after each call), the target computes it inside each case. Passing 0 instead of
    `&pp` to the marker virtual call still hoists, so the case copies alone drive it. Micro tests
    (switch + by-value operator=, pp member-wise init, inline `think(Vec3 pp)` wrapper, explicit-ctor
    param) all hoist too.
  - **Lever (mp72 75.6 -> 77.3, `b08_keep/mp72_p2.cpp`): declare pp WITHOUT a constructor call.** With
    `Vec3 pp;` the user default ctor `Vec3() {}` takes `&pp` at the declaration, and uopt keeps that address
    web in a3 for the whole function. As an anonymous POD struct (`struct { float x, y, z; } ppr;`, used as
    `*(Vec3 *)&ppr`), every case rematerialises `addiu tX,sp,356` like the target, and the vcall passes
    `addiu a1,sp,356` directly. A Vec3 with no constructors at all also does it, but its op- / op* return
    temps then move the frame (72.9).
  - Next mp72 residual: tg / ps (self+0x114 / self+0xDC). The target (and NCC on the same source)
    rematerialise both at the end of every case and spill ps across the case-2 call (`sw a2,52(sp)`); mp72
    computes them once at the join. Not moved by: `&member` spellings, a HeliS member struct, assigning
    them at the top of the function, `if (1) {}`, reordering, edgcpfe without `-O`. The uopt dump
    (`-zdbug:5` via ido-static-recomp-dump, scratch `ncc721d.sh`) is in r663/dumpm and dumpn for comparison.
  - Not levers: `-Olimit` (below 200 uopt skips the function), edgcpfe `--long_lifetime_temps` /
    `--short_lifetime_temps` (accepted, no change), operator= by reference with an inner copy
    (`Vec3 v = r;` gives one slot per expansion, target has one shared slot).
  - mdebug `-g3` frames (scratch `mdl.py`) differ from `-g0` under both edg front ends (temps move), so
    read the target slot map from the code instead (`smap.py`: target -> ours sp offsets on aligned rows).
- Scratch: /tmp/claude-1000/agent-g/r663/ (x5.cpp = NCC 80.2 source, x5p.cpp = preprocessed for mp72,
  ncc721x.sh = ncc721.sh with extra `FEX` front-end flags, smap.py / sdiff.py; drafts kept in
  /tmp/claude-1000/agent-g/b08_keep/ncc_x5.cpp and mp72_p2.cpp).

## heli.uso (agent-g run 658)

- **+2 EXACT (3541 -> 3543 on the agent-g base, gate PASS each), no renames.** Commits on agent-g:
  2a7328dcc (0x8A8), c0c734d95 (0x980), b4968b0ec (0x4C0 NM 90.7 -> 91.2). heli: 24 / 26 exact.
- **0x8A8 (flight-state reset), NCC donor** `src/heli_uso/heli_uso_ncc.cpp` (Makefile HELI_NCC_DONOR,
  REPLACE_FUNC_BODY over an empty placeholder). Three levers:
  - **edg folds `(float)0` into 0.0f.** For a separate zero constant web, use an int local:
    `{ int z = 0; h->off.x = z; ... }`. The conversion is folded later, in uopt, so the zero stays
    its own web (mtc1 zero f8).
  - **Frame:** a dead `{ int scratch[2]; scratch[0] = 0; }` **nested block at the end** puts its
    words below the inline temps (frame 0x20 -> 0x28, look temp at sp+12). Declared at function
    scope, it goes above the temps instead, which is agent-a's block rule.
  - **Line grouping:** the off block must sit on one source line. Split over four lines, the 2000
    load schedules after the zero (99.4 instead of 100).
- **0x980 (hem marker placement), cfe C:**
  - The first iterator result goes through its own local `r` (v0, then `item = r` copies it to
    v1), as the loop's later results do.
  - cfe gives every declared local a home in declaration order, nested-block ones last. The
    `-O2 -g3` .mdebug dump (`/tmp/claude-1000/c418/py/mdsym.py`) showed where they landed.
    Declaring type / item above the Vec3 temp t, with padB 4, puts t at sp+0x24 in the 0x58 frame.
- **0x4C0 residual, read in the `-Wo,-zdbug:5` uoptlist** (tools/ido-static-recomp-dump cc):
  - The (float)0 zero is one const LR across the main- and tail-rotor blocks (6 uses / 2 BBs,
    adjsave 2.5).
  - The tail's scale chain value (`c0 = c4 = c8 = RO58`) is a cfe temp LR with adjsave 4. It
    interferes, so it is coloured first and takes f0; the zero gets f2 in *both* blocks.
  - With three separate loads (a float extern pinned at 0x58), the zero gets f0 in both blocks,
    but the loads reload after each store (alias), so that is not the fix.
  - No help from these (cfe and NCC): zero spellings; `if (1) {}` / `if (x) {}` splits;
    code-free compare uses; reusing the scale variable for another value; edg `set(a, b, c)` /
    `set1(s)`. Next: a scale value with priority below 2.5 that is still one load, or a zero LR
    with more counted uses.
- **0xB08** not reworked this run. The NCC draft is still 77.2, the mp72 one 74.7.

## viewrec.uso progress (agent-a run 654)

- +3 EXACT (3530 -> 3533 on the agent-a base, gate PASS each): 0x266C (commit e24e1cb5d), 0x1488
  (77102594f), 0x0 (c2919d89c). All three are in the NCC donor viewrec_uso_ncc.cpp; viewrec has no NM
  wraps left below 0x3000.
- **0x266C (records menu input), first NCC compile 95/209 -> exact in four steps:** `x--; if (x < 0)` instead
  of `if (--x < 0)` (edg's pre-decrement temp reuses v1; the target has fresh t-registers): 14 words. The
  state switch read through an `int st` local (v0, not v1): 9 words. The void alias on the snd_postEvent(5)
  before the tab switch and the `proc->mode = proc->nextMode` copy (the dead int $v0 def pushed both into
  v1): 2 words. `old` declared at function scope instead of in the case block (the block-scope one took a
  home 8 bytes higher, frame 0x30 vs 0x28).
- **0x1488:** `VrSprite &label = sVrLabels[i]; VrSprite *spr = &label;` gives the 0x28 frame with the pointer
  spilled at sp+0x1C. A plain pointer local, two `&sVrLabels[i]`, or a bare reference are 5-7 words off.
- **0x0 (a0 vs a1, read in the -Wo,-zdbug:5 colouring dump):** &sVrScreen took a0 because its range ended
  before the jalr block, where edg's `this` temp is coloured a0. The cfe screen switches get a1 because their
  second `if (sVrScreen) {}` stretches the range over that block. Under NCC a second test right after the
  virtual call does the same (a1), but it splits the next blocks and the tail's &sVrProc range then reaches
  back into an empty block and stays uncoloured (no `lui v0; addiu v0,0x87C` CSE; 8 words). Moving the
  second test after the 0x1A08 call (or to the end of the function) gives both. Brute force on test
  placement in the show block alone (250 variants) never got past 3 words.
- **Other modules (only snoweffects attempted):**
  - snoweffects 97C as NCC C++: 2/64 words, the same residual as the cfe NM (p reload above the mul.s).
    All 120 orders of the first store group were tried; none matched.
  - snoweffects 9E10 as NCC C++ with an inline member addChild: 4/30, the same as cfe. The dump shows why:
    head is one range coloured a1 (call-argument preference). The target splits it: head is loaded into
    a2, copied to a1 for list_append, and reloaded into a1 after the call. `c = head; head = 0;` before an
    inline addChild(c) (kit CXCI kill) gets the copy in the delay slot and the 32-byte frame. But head then
    colours v1 before item (higher priority), so item ends in a2: 10 words. Open: lower head's priority
    below item's.
  - Levers that may help the parked NMs: the void alias fits a v0/v1 swap after an int-returning call;
    `h = 0` fits a pseudo needing v0 earlier; the zdbug:5 colouring read fits arg-register swaps (nameent
    2F4 / trnproc 1778 if they are a0/a1 or v0/v1 residuals). Not attempted: owners are active.

- **Re-scope (coordinator):** snoweffects 97C / 9E10 left to agent-h / agent-e (nothing committed for
  them). New scope: snoweffects 0x7FE0 and 0xA10C (own donor snoweffects_uso_ncc_a.cpp, not created yet).
- **0xA10C (snow light update), first NCC draft, not landed.** Callees and data come from
  `scripts/uso-imports.py sites snoweffects`: 9768, PolyShape_getVertex / getNormal8, 9FE8,
  ItemMgr_findType (keys Data+0xA78 / +0xA7C), 9884 / 9BE8 / 9C48, flag Data+0xA30, Bss+0x40 / +0x50,
  RoData+0xF4. The body decode is complete: 16-word matrix copy src+0x70 -> tgt+0x2C, colour parm copy
  +0x124 -> tgt+0x288, ambient-parm dirty check, per-vertex light colours (255 clamp, u8 store), two
  ItemType walks. Levers found so far:
  - The clamp loop as `for (j = 0; j < 3; j++) { float *f = &col.x + j; ... }` (a pointer loop is unrolled
    x4).
  - The colour zeroed through an inline member `col.set(0, 0, 0)` (direct stores fold `0 + x`).
  - The ambient added component-wise, re-reading `t->ambient->v.get()` each time.
  - The iterator as a class with an inline next() (an array iterator is promoted to s-registers).
  - The ItemMgr keys passed as `*(SKey *)(D_00000000 + 0xA78)` by value (the edg by-value temps give
    the target's homes 148 / 172 and the 176-byte frame).
  - The normal bytes in a nested block (the target has them at sp+0x70).
  Left: 193 of 405 words. Most are s-register numbering: self is s5 in the target (s3 here), and the
  Bss+0x50 pointer goes in s4 before the vertex-count test. There is also a v0/v1 pair in the ambient
  compare and the second walk's mask constants (-2 / -3 / -5 hoisted into s2..s4). Scratch:
  /tmp/claude-1000/agent-a/w654/a/best_A10C.cpp. 0x7FE0 is not started.

## snoweffects.uso 0x7FE0 (agent-a run 748)

- **0x7FE0 EXACT (NM 99.97 % -> 100 %, ROM byte-identical).** Donor renamed `snoweffects_uso_ncc_nm_a.cpp` ->
  `snoweffects_uso_ncc_7fe0.cpp`, spliced on both build paths (Makefile `SNOW_7FE0_FUNCS`); the callees go through
  the existing 0-pinned aliases `gl_func_00000000_snowa_v` (0x4374), `_snow_46bc`, `_snow_4714` (the USO jals are
  blank). Scratch /tmp/claude-1000/agent-a/w748/ (`hh.py` on w745/h.py, `tr.sh NAME` = uopt colour trace of
  `v/NAME.cpp`, `g12`..`g21` the sweeps, `cmpo.py` .o byte + reloc compare).
- **The merge partner for the |s| word (M-292) is the rgba[2] colour value, not e.x.** In the target the three
  rgb[k] float values are f0 / f2 / f12 and share one uopt unit (the rgba block). The rgba[2] statement becomes
  `mixq(0, 0, 0, 0, 0, 0, 0, 0, fade, (float)t->cam->rgb[2])` with
  `inline float mixq(float d0..d7, float f, float c) { d0 = d0; ..; return c + (255.0f - c) * f; }`: the 8 dummies
  and f take the nine older R words, so c is the 10th request and lands on -292. The merged LR then interferes with
  rgb[0] / rgb[1] (f0 / f2) and takes f12.
  - **The dummy arguments must be constants.** With `s` as the dummy argument (a load per dummy), 7 or more dummies
    grow the rgba block past uopt's block size, so c lands in a new block (no interference, still f0).
  - The merged LR has num 80. At den 2 (priority 40) it is coloured before the rgb values (30). Two code-free
    `if (1) {}` after `a = fabs_(a)` in the d ctor give n = 6, den 3, priority 26.7.
  - Those loop blocks change the loop-wide 0.0f / fade colours (f24 / f22 swap, 30 words). A per-site sweep of the
    pre-loop code-free blocks (`st0` / `spd1` on the state != 97 test, `st0` on == 98, `st5` on `int g`) fixes it.
    Six 0-diff combinations exist (block total 6, e.g. 0/1/0/5, 0/1/1/4, 0/2/0/4).
- **e.x on -292 also fixes |s| but cannot match** (`v/b012_1_0.cpp`, e ctor `(int, d0, y, z, 6 dummies, x)` plus one
  ctor block for den 3): M-20 loses e.x's refs (18.9 < M-176's 20), so op*1 z / k / M-20 recolour. Moving TQ::op*'s
  blocks out of the up-op* `s` range plus `idi6()` blocks around the k index (`g11`: TQ 4-5 ifs + idi6 1-2 ifs) fix
  M-20 and the cam pointer (9 diffs). What stays is e's load / multiply order (y, z, x), which the param order fixes.
- The coordinator's factory-function lever (a plain-variable argument substituted in a declarations-plus-return
  inline) was not needed. Callee return types match the context header (void 0x4374, int 0x46BC, void 0x4714).

## snoweffects.uso 0x7FE0 (agent-a run 745)

- **No commits, no renames. 0x7FE0 is still NM 99.97 % (5 words, the d ctor's |s| f0 vs f12).** Scratch
  /tmp/claude-1000/agent-a/w745/: `h.py` (`score(name, src)` = NCC compile + positional diff count vs expected,
  branch targets normalised, sp offsets kept; `runall()` 24-way parallel; base = w720/b725.cpp scores 5),
  `g1.py`..`g6.py` the variant sets below. Colour dumps: `w720/tr.sh X.cpp` (uopt `-zdbug:5`, `x.ord` / `x.lr`).
- **No word-layout simulator was needed:** a full NCC compile of this file takes 0.4 s, so every variant was
  compiled and scored on bytes directly (~2700 variants this run).
- **Why the `?:` LR (M-292) takes f0, from the zdbug:5 interference list:** it lives in units 91 / 92 / 93
  and interferes only with s (f16), the constants (f18..f24) and the uncoloured memory words of v / d.
  In uopt's register names, dump `f2` = $f0, `f12` = $f2 and `f14` = $f12. So nothing coloured $f0 / $f2 shares
  a unit with it.
  - For $f12, M-292 must share units with LRs that are coloured $f0 and $f2 before it, and it must not share
    a unit with M-20 ($f12).
  - In the target nothing FP is really live there. So the interferers must come from a merged web: a later
    statement reusing word -292.
- **Merge test that proves the mechanism:** e's ctor with params in the order (dummy, y, z, 6 dummies, x)
  (`g5.py`, `e_1_6_yzx`). edg's first-fit gives d0 -20, y -148, z -172, the dummies -176..-288, and x -292, so
  e.x merges with the `?:`. The frame stays 384, and the `?:` + e.x LR now interferes with e.y ($f0).
  - It still scores 53, for three reasons:
    1. The merged priority (70 / 2 = 35) beats M-172 (26.7), so it takes $f2.
    2. M-20 loses the e.x refs (pri 18.9) and drops to $f14.
    3. The param order also becomes the evaluation order, so e loads y / z / x instead of x / y / z.
  - x must be the 10th R request in its statement, so it cannot be evaluated first. And e.z / e.y cannot carry
    the merge, because their colours are not $f12.
- **Flat (5) or worse:**
  - Statement dummies `dm_PAT()`: all 120 R / A / J patterns of length 1-4, at 11 loop positions (1320
    variants, best 5).
  - Pre / post dummy params on the d ctor, or on a `fabs2` used inside it: every one adds a fresh word in the
    d region (frame 392 / 400).
  - `if (1) {}` at each ctor body position or around d / e: 5.
  - Ctor body store orders: 9-11.
  - e forms: `(0, -1.0f)` scale is 48; member-wise e is 798; swapping d / e is 801.
  - `pkN(d.., v)` / `stN(d.., v, &o)` wrappers that put a later value on word -292 (w[0], u, tv, `u * 3`,
    vtx s / t; N = 6-11): the single-use values are forward-substituted (no LR), except the w[0] site, which
    merges into a block with no $f0 / $f2 LR.
- **Run 733's "only four older words" re-checked:** with the frame fixed (v at M-284, two holes between v and
  e's r at M-304, M length <= 308), every older R word is already one of the eight the d statement uses. Extra
  older R words would have to be fresh words in the frame above v. So the `?:` stays the 10th request, and a
  fix has to come from a later merge.
- **Next:** a merge web for -292 that is the LAST R request of a later statement, in a unit where the $f0 / $f2
  LRs are coloured before it but not M-20. With the merge, its priority must stay below 26.7, which needs
  den >= 3, i.e. >= 6 units. Candidates are the u / tv region (M-116 $f0 / M-120 $f2, pri 20: the merged
  priority would have to be < 20) or a re-ordered e whose x is evaluated first.

## snoweffects.uso 0x7FE0 (agent-a run 733)

- **No commits, no renames. Run 728's last hypothesis is refuted: 0x7FE0 is still NM 99.97 % (5 words).** Scratch
  /tmp/claude-1000/agent-a/w733/ (`v1..v4.txt` variant sets for w728/pv.py on w720/b725.cpp, `sh.sh <variants>` = the R / J
  words of lines 284-287).
  - **Named float locals at the a statement's start** (`idw2` with `float q0..qk` instead of `int g, h`): k = 2 makes
    -200 / -204 fresh R words with frame 384 (`fa2`), but **named locals stay locked for the whole function**. The d
    statement does not reuse them; a / `?:` stay fresh at -288 / -292 (5 diffs, objdiff 99.95).
  - **Freeable fresh R words (dummy parameters `p0..p5 = p0;` on `idw2`, `pa1..pa7`):** params take the old words first
    (-148 / -172 / -176), then fresh -200..-212. Then the d statement reuses them, but in first-fit order: op*2 gets
    -200..-212 and a / `?:` land on the a statement's -228 / -232. pa6 is frame 384 with 17 diffs: the a statement's
    product colours break, and d's |s| is still f0.
  - The same dummies on a second inline around the a statement's `?:` (`q{k}{m}`, k params on idw2 and m on `idq`):
    the best frame-384 cases are 18-24 diffs.
  - **Why it cannot work:** words are handed out first-fit in creation order, which is offset order. -200 / -204 are
    created before -220..-244, so the d statement's first eight R requests (op*1 / op*2) always take them before a and
    the `?:` (requests 9 and 10). For a / `?:` to land on -200 / -204, op*2 would need four R words older than -200,
    and only -20 / -148 / -172 / -176 exist (op*1 already takes those).

## snoweffects.uso 0x7FE0 (agent-a run 728)

- **No commits, no renames. 0x7FE0 is still NM 99.97 % (5 words, the d ctor's |s| f0 vs f12).** Scratch
  /tmp/claude-1000/agent-a/w728/ (`pv.py` = run 725's runner with the d line printed in full, `live.py <x.lr> 91,92,93 [all]`
  lists the LRs live in the given blocks, `v1..v7.txt` are the variant sets run against w720/b725.cpp).
- **Correction to run 725's rule: a ctor with a BODY always materialises its parameters.** `a` keeps R-288 even when
  the body never assigns it (`float b = fabs_(a); ..`, `mulin(v, fabs_(a))`). Only a **mem-initialiser-only ctor**
  (`TV(TV v, float a) : x(v.x * a), .. {}`) substitutes a plain `a`. But then |a| has to be computed per member, or
  passed in as `fabs_(s)`, which evaluates the `?:` before the v copy (801 words). A base-class ctor
  (`struct TVS : TV { TVS(TV v, float a) : TV(v, fabs_(a), 0) {} }`) or a member subobject (`TVD { TV v; .. }`)
  would put the `?:` after the copy, but edg then emits a `this == 0` check that calls `__nw__FUi` (824 words).
  So angle 1 has no plain-C++ spelling.
- **Why the `?:` cannot reach an f12 word in the d statement:** edg pool words have a class. A/J (int and
  pointer) and R (float) never share a word: the d statement's op*2 ctor `this` goes fresh while three old R words
  are still free. Within a class, words are handed out first-fit in creation order (-20, -148, -172, -176, -220,
  -236, -240, -244), and an old word stays locked once used. The d statement makes 10 R requests: op*1 s / x / y / z,
  op*2 s / x / y / z, a, `?:`. So the `?:` is always the 10th, a fresh word. Both f12 words (-20 = M-20, -240 = op*2 y)
  are taken earlier in the same statement. A fresh op*2 word costs one 4-byte word ahead of v per word, and the
  target allows only one there (-272). A const-ref v (`TV(const TV &w, ..)`, with or without `TV v = w;`) binds a
  block-top temp, which shifts every named local (frame 392-400, 806 words with the copy).
- **What the target needs (from `live.py`):** nothing FP is live through blocks 91-93 except s (f16) and the
  constants (f18-f24). M-292 is coloured 40th (pri 25) with no forbidden registers, so it takes f0. For f12 its LR
  must also reach a block holding f0 / f2 LRs and no f12 LR, or it must merge with an f12 LR.
- **Angle 2 tested (`?:` word = e's x):** `t->vFC.mulE(-1.0f)` with k kept dummies (`dumk(x, ..)`).
  - k = 9 puts e.x on the `?:` word (R-292). That LR still takes f0, because e.y / e.z go to fresh words that are
    coloured after it.
  - Costs: the frame is 392, and 22 pre-loop words move (any extra `if (1) {}` op* copy does that).
  - k = 2-7 keeps frame 384 at 46-57 words.
  - Two declarators (`TV d(..), e = ..;`) are separate full expressions, byte-identical to the base.
- **Left:** the merge has to come from the colour order. Two routes:
  - colour e.y / e.z (M-148 f0 / M-172 f2) before the `?:`+e.x LR, which needs e.x on the `?:` word while e.y /
    e.z stay on old words (first-fit forbids it within one statement);
  - or find a target layout where -200 / -204 (now idw2's dead `int g, h`) are R pool words that the d statement
    reuses for a / `?:`. That needs 2 fresh R words at the a statement's start, which first-fit also forbids
    unless every old R word is locked there.

## snoweffects.uso 0x7FE0 (agent-a run 725)

- **No commits, no renames. 0x7FE0 is still NM 99.97 % (5 words: the d ctor's |s|, f0 vs the target's f12);
  exact count unchanged 3570 / 3579.** Scratch /tmp/claude-1000/agent-a/w725/:
  - `ud.sh` / `fl.py <x.cpp> [from line]` are the **IDO 7.1 (EDG 2.19)** port of agent-e's run 718 word tools. They
    run `NCC -keep`, then the dump ugen `-d` on the kept `.B`, and print each source line's pool words (`R` float,
    `A` pointer, `J` int, `l` = lda of a memory word, `r` prefix = a read).
  - `pv.py` is the run 720 variant runner plus the d line's words. The variants are in `w720/` (q*, w*, x*, y*, z*,
    g*, m*, c*, d*, e*, p*).
- **EDG 2.19 allocates exactly like agent-e's 2.29 rules** (checked on 7FE0):
  - Float params and `?:` result temps take the oldest free word of their dtype. The pre-loop `fabs_(v)` temps are
    -20.
  - Words reused from an earlier statement stay locked for the whole statement.
  - Fresh words are freed at the end of their inline, so the same statement can reuse them.
  - A plain-variable argument is substituted only when the inline does not assign the parameter. `a` in
    `a = fabs_(a)` keeps its word.
  - A `float &` param is an A word, so its target is address-taken.
  - Empty-bodied `void dum(float..) {}` allocates nothing. `{ a0 = a0; }` allocates and costs no code.
- **What M-292 is:** the `?:` temp of `fabs_` (`x` is substituted). The ctor's `a` (-288) is copy-propagated away.
  The d statement holds exactly the 8 old R words, in this order:
  - op*1: s -20, then x / y / z -148 / -172 / -176;
  - op*2: s -220, then x / y / z -236 / -240 / -244.

  So `a` and the `?:` are always fresh. Base word to colour: -20 f12, -148 f0, -172 f2, -176 f14, -220 f0, -236 f2,
  -240 f12, -244 f14.
- **A new lever moves the `?:` onto an op* product word:** a dedicated
  `TV mul2(float s) const { if (1) {} dum3(s, s, s); TV r(..); return r; }` for op*2, with
  `inline void dum3(float a0, float a1, float a2) { a0 = a0; a1 = a1; a2 = a2; }`. Op*2's s stays on -220. The dummies
  take -236 / -240 / -244, op*2's ctor x / y / z go fresh, `a` reuses x's word and the `?:` reuses y's word (the
  target's f12 product).
  - With one `if (1) {}` between `x = v.x * a;` and `y = ..` in the d ctor (`w720/c1.cpp`), every colour except
    op*2 x / y matches: 9 words, x f12 / y+|s| f2 (target f2 / f12).
  - **But the frame is 392 and every sp offset is +8.** The by-value `v` param moves from -284 to -296, because op*2's
    three fresh ctor words come before it.
  - Since `v` must stay at -284 (sp+100), op*2's ctor words must be old words. That leaves the `?:` only fresh words
    allocated after `v`, which are private to blocks 91-93 (so it takes f0).
- Flat or worse:
  - `fabs_(s)` / `?:` as the ctor argument: the `?:` lands before the `v` copy (801 words, 332 diffs).
  - `TV(float a, TV v)` arg order (frame 392).
  - if / else forms writing `a` (806 words).
  - `float &` param writing k (k goes to memory).
  - `set(v, fabs_(a))` (frame 392).
  - `mulr(const float &)` on op*1 or op*2 (461-638 diffs).
  - Dummies before op*1, after op*2, or at 1-4 counts in other places (5-61 words; every 5-word one has frame
    392 / 400).
  - Two or more `if (1) {}` in the d ctor, or any in mul2 besides the leading one: 798 words.
- **Next:**
  - In the base, the only fresh word between op*2's `r` (l-268, sp+116) and `v` (-284, sp+100) is A-272. So at most
    ONE op*2 ctor word can go fresh without moving `v`, and only if A-272 becomes an old A word. The c1 shape needs
    two fresh words (x for `a`, y for the `?:`), so with this ctor it cannot keep the frame.
  - Remaining angles:
    - a d ctor whose `a` takes no word (a body that never assigns `a`, with |a| computed in a nested statement
      inline), so the `?:` takes the single freed word;
    - or a sharer for the `?:` that is allocated after `v` but is not private to blocks 91-93.

## snoweffects.uso 0x7FE0 (agent-a run 720)

- **0x7FE0 NM 99.93 -> 99.97 % in-tree (objdiff report; 10 -> 5 / 800 words differ; frame and sp offsets
  unchanged)** (agent-a de693e495, gate PASS, no renames, exact count unchanged 3570 / 3579). Scratch
  /tmp/claude-1000/agent-a/w720/ (tr.sh = h416 trace + lre / ord for 7FE0, sh.sh / absf.sh = key LRs of a variant,
  pv.py variant runner).
  - **Cam pointer fixed (priority, not pool membership).** Start from run 715's separated vel `this` (idv through a
    pointer local, `if (1) {}` after the pos store, lerp3 keeps one dead float). M-124 (a-cam `this` + the `?:`
    index) has 7 refs in the loop = num 70, den 2. Priority is 10 x refs / den, and den only rises with the range's
    unit count: (n - 2) / 4 + 2 for this LR. **Six code-free `if (1) {}` at the top of TQ::operator*** (before the
    products, so `this` is live across them) give den 4 = 17.5, below the stride load's 20: stride v0, a-cam / `?:`
    v1. 1-5 ifs are not enough (den 2-3); statement-level ifs, `if (this) {}` (adds a use) and dead
    `idf(...)` statements are flat or worse.
  - **The side effect is FP.** Every loop block also lands in the loop-wide FP LRs (K255 30 / den, fade 32 / den,
    K0 51 / den), and the target order K255 > fade > K0 (f20 / f22 / f24) is a near tie (2.143 / 2.133 / 2.04 at
    base). With the six ifs: K0 > fade > K255. Fix: code-free blocks BEFORE the loop, which only fade and K0 see.
    `st(c)` / `spd(c)` = `{ if (1) {} if (1) {} return c->state / speed; }` on `t->cam->...` (a non-simple argument;
    a simple one like `t->fade` is substituted and adds nothing): on the state != 97 and == 98 tests, the
    `int g = (st(t->cam), 0)` dead int, and the speed < 60 test inside the hits clear. The blocks before fade's
    def lower K0 only; the ones after lower both. Statement-level `nb();` calls are no-ops.
  - **Left (5 words): the d ctor's |s| (M-292, f0 vs target f12).** FORCE 326:26 gives 0 diffs, so it is the
    colour pick alone. Nothing coloured overlaps blocks 91-93 in f0 / f2. The likely target shape is that the
    fabs_ result shares a pool word with an f12 LR whose own pieces forbid f0 / f2. Candidates: M-20 (pool word 1:
    the pre-loop fabs_ results, the vel / up op* s, **e's TV(x, y, z) x param**, which is f12 with y / z in f0 / f2
    in the same block) or M-88 (the `(0, k)` word). But the d statement is the deepest in the frame, and its
    fabs_ temp is always a FRESH word (-284..-308 over ~60 variants). Flat: ctor param orders and extra params,
    fabs forms (`?:`, if / return, `+x`, `(0, ...)`, idg wraps, `const float &`), |s| at the call site (the `?:`
    moves ahead of the copy chain), `(0, ...)` / idf / idv / idw2 on every operand of vel / a / k / d / e, and
    dummy statements (`s = s;`, `{}`, `(void)k;`) between a / k / d. Next: get the fabs_ temp into a reused
    word (it must stop being fresh), or find what holds -20 during d.

## snoweffects.uso 0x7FE0 (agent-a run 715)

- **0x7FE0 NM 99.61 -> 99.93 % in-tree (objdiff report; 13 -> 10 / 800 words differ; frame and sp offsets
  unchanged)** (agent-a 118c25027, gate PASS, no renames, exact count unchanged 3569 / 3579). Scratch
  /tmp/claude-1000/agent-a/w715/ (pv.py variant runner now prints the frame; spd.py lists the sp-offset diffs).
  - **Preheader order fixed: drop the `&t->v114` / `&t->vFC` pointer locals.** Read `t->v114` / `t->vFC` in place
    in the d / e statements. LICM then hoists a0+276 / a0+252 after the i*44 IV init, as in the target's
    `or a1; addiu t3; addiu t4`. The locals were two frame words in the if (on) block. `int g = 0, h = 0;` in
    their place keeps 384 with every offset unchanged. Uninitialised `int g, h;` gives 376. Keeping the dead
    pointer locals with in-place reads stays at 13 words, because the hoist still comes first.
  - **Cam pointer, diagnosed with the h414 trace:** M-128 is the **pos store pointer**, not idv's `&cam->fwd`:
    blocks 53 / 85 / 88 / 90, the pos and rgb stores. M-124 is one pool word that serves three uses: the vel
    op*'s `this`, the a statement's `&cam->up`, and the `?:` index. The op*'s `if (1) {}` splits the vel
    statement, which leaves `this` defined in block 53 next to the pos pointer, so it interferes and gets v1.
    The target needs the vel `this` in v0, the a-stmt cam and `?:` in v1, and the stride load in v0.
    - **Separating the vel `this` works:** add `if (1) {}` after the pos store, then add
      `idv(const TV &v) { const TV *q = &v; return *q; }` and drop lerp3's `g`. The second change is
      frame-neutral. The vel `this` becomes its own LR in v0. M-124 = {a-cam, `?:`} then has no v0 conflict
      and takes v0 at priority 35, above the stride load's 20, so a-cam and `?:` flip to v0 (20 words).
    - Forcing M-124 to v1 on that body (`FORCE=126:2`) gives 8 words. Adding the d ctor |s| (M-292,
      `327:26`) gives 3, and those 3 were the preheader words now fixed in-tree.
    - So the remaining work is to get M-124 to v1 without forcing. Either its priority has to drop below the
      stride load's, or a v0 LR has to overlap blocks 58 / 67-69. Flat, all at 20: TQ op* / idw2 / statement
      `if (1) {}`, k-index forms, `idi()` wraps, idq on up, and moving f28 / w stores.
  - d ctor |s| (M-292, blocks 77-79, nothing else coloured there, so it takes f0): flat for idf0 / (0, a) /
    `+a` / `0 > a` / fabs3 / `if (1) {}` in the ctor. idf0, (0, a), fabs3 and `a + 0.0f` also cost a frame word.
  - Other flat or worse: no idv (vel ok, a-cam / `?:` swap: 20); `.mul()` without `if (1) {}` for vel (57-64);
    named `fw` / `cam` locals (frame +1 or 801 words); `idc(t->cam)` (801).

## snoweffects.uso 0x7FE0 (agent-a run 708)

- **0x7FE0 NM 99.42 -> 99.61 % in-tree (objdiff report; 40 -> 13 / 800 words differ; frame and every sp offset still
  the target's)** (agent-a 2e6523b41, gate PASS, no renames, exact count unchanged 3568 / 3579). Scratch
  /tmp/claude-1000/agent-a/w708/ (ddn.py = word diff with sp offsets masked, so colour work can run while the frame
  is off; fsweep.sh / role.sh = forcing sweeps; ins.py = insert one line at every statement; pv.py variant runner).
  - **The trace's FP colour names are off by one register here.** In the h414 / h416 trace and `.lr` files, colour
    24 printed "f2" is really **f0**, 25 = f2, 26 = f12, 27 = f14, 28 = f16, 29 = f18 (check it against the asm: s
    prints "f18" but is f16, the zero constant prints "f26" but is f24). Run 690's "M-20 col f14" was f12. For
    FORCE, use the numbers (24 = f0).
  - **Step 1, `(0, k)`:** `TV d(*v114 * (0, k) * t->f184, s)` gives the first op*'s s its own pool word (k stays a
    named float at -88). The |s|, k, *f184 op* colours then match the target (k division f12; x / y / z f0 / f2 / f14),
    but one extra frame word appears (392) and the rest swaps f2 / f12 globally.
  - **Step 2, frame:** d's ctor `TV(TV v, float a) { a = fabs_(a); ... }` (|s| written back into the parameter, no
    named `a`) removes one word, and the frame is back to 384 with every offset matching (57 words, all f2 <-> f12).
  - **Step 3, the swap:** M-20 (pool word 1: the pre-loop fabs_ word, the lerp fraction, the fwd / up s) outranked
    M-172 (the ctor's y word): 30.4 vs 26.7. **`if (1) {}` at the top of TV::operator*** (before `TV r(...)`) fixes
    every s / y / z colour and the pre-loop |v| words: 57 -> 13. Statement-level `if (1) {}`, `do {} while (0)`,
    `goto L; L:;` and `if (1) {}` in any other inline (TV / TQ ctors, TQ op*, idw2, fabs_, idv, lerp3, lerpf, the
    d ctor, operator= / += / *=) are flat or worse. In NCC the empty `if` only counts inside an inline.
  - Flat or worse on the way: lerpf parameter orders, lerp3 dead-local forms, `idf()` / `v =` / `w =` for the lerp
    fraction, `x * 1.0f` / `+ 0 * (int)b` / `b = b` in the ctor, one / two `(this + 0)` hops in op*, a shared
    `float c` in op*, a 4-arg ctor, products computed inside the ctor, `idv(idv(...))`.
  - **Left (13 words):** (1) the `or a1` / `addiu t3` / `addiu t4` preheader order (3); (2) the vel statement's cam
    pointer, v1 where the target has v0 (5). In the trace, M-124 (an op* pool pointer, def in unit 53, uses in 54)
    takes v1 because M-128 (pri 125, idv's &cam->fwd) holds v0 in unit 53. In the target the cam load is probably a
    ugen temp, not M-124. (3) d's ctor |s|: f0 where the target has f12 (5). `a = a < 0 ? -a : a`, `(0, s)`, and
    `if (1) {}` in the ctor are flat; `idf(s)` as the argument breaks the frame (97 words).

## snoweffects.uso 0x7FE0 (agent-a run 701)

- **0x7FE0 NM 99.40 -> 99.42 % in-tree (objdiff report; 52 -> 40 / 800 words differ; every sp offset now matches the
  target)** (agent-a a593a5b57, gate PASS, no renames, exact count unchanged 3564 / 3579). Scratch
  /tmp/claude-1000/agent-a/w701/ (t/ = edg temp-order micro tests, g.sh prints -g3 frame names).
  - **edg block temps (`__V`) are never reused and sit at the top of their block in REVERSE creation order** (micro
    tests: expression statements, inner blocks, by-value calls never share one). So the target's "swapped" loop-top
    pair can't be two loop-body __Vs. The target's sp+336 (up * f180) is a **named vector in the if (on) block**
    (first word below vFC), and the loop body has only d's __V (sp+324).
  - Block starts carry an inline word when the last outer local's type has a user default ctor (TV / TQ `T() {}`:
    one `this` word after it). A ctor-less POD (`struct TQ0 { float x, y, z; }`) has none.
  - The a statement must stay ONE full expression: as two statements, the second op* copies through a3 instead
    of t1. Form: `TV a = ((TQ &)ua = t->cam->up * idw2(t->f180), (TV &)ua) * (s < 0.0f ? -s : s);`. cam->up is a
    TQ, whose implicit operator= is a word copy (TV's by-value operator= is float copies). `(TV &)(ua = ...)` /
    `*(TV *)&(...)` add a 4-byte reference temp; the comma form does not.
  - The two words ahead of up * f180's r are an inline's dead locals evaluated before it:
    `idw2(float f) { int g = 0, h = 0; return f; }` on t->f180 (float locals copy f into pool words: 45 words, not
    40). |s| as a plain `?:` leaves one word after the r, as in the target.
  - Still left (all colours, unchanged by toggles of idv / idf on fwd, v114, k, f184, vFC, ctor mem-init /
    `s * x` forms): fwd / up op* y / z (f14 / f2 vs f2 / f14); the |s|, v114 * k, *f184, d-ctor |s| and e.z
    rotation; the vel statement's cam pointer (v1 vs v0); and the or a1 / addiu t3 preheader order.
  - **MIPSpro 7.2.1 front end (tools/ncc721.sh, coordinator lead): no.** The run-696 and run-701 bodies compile to
    802 words (94.0 %), and the integer temp rotation differs from instruction 7 on, in code that is exact under 7.1. 7FE0 is
    a 7.1 NCC function, so keep the 7.1 donor.

## snoweffects.uso 0x7FE0 (agent-a run 696)

- **0x7FE0 NM 99.30 -> 99.40 % in-tree (objdiff report; 66 -> 52 / 800 words differ)** (agent-a cd257a936, comment
  139d0158a; gate PASS both, no renames; exact count unchanged). Scratch /tmp/claude-1000/agent-a/w696/ (pv.py
  parallel variant runner, fv.py variant runner + `-g3` frame names, sl3.sh one-line frame names, ops.py FP dest
  registers of the loop's op* expansions, rs.py random toggle search, t/ small edg pool tests).
  - **Lever: identity inlines on a NON-TRIVIAL argument add an edg pool word.**
    `inline float idf(float a) { return a; }` and `inline const TV &idv(const TV &v) { return v; }`.
    `TV a = up * f180 * idf(fabs_(s))` puts *|s|, v114 * k and *f184's r on the target's slots (-232 / -256 / -268)
    and fixes the v0 / v1 of the a statement's cam pointer and of the `?:` index. `vel = idv(t->cam->fwd) * f188`
    on top gives 52. Wrapping a SIMPLE argument changes nothing: edg substitutes it straight into the body with
    no pool word (`idf(t->f180)`, `idv(t->cam->up)`, `idv(*v114)`, `+x`, `(0, x)`, `*&x`, casts are all
    byte-identical). Empty inlines (`void nop(float) {}`) also allocate nothing.
  - Small edg tests (`t/`): of N identical `o[k] = u[k] * q;` statements, the 2nd allocates all-new pool words,
    the 3rd reuses all but one, and the 4th / 5th reuse everything. Reuse lags by a statement. A scalar statement in
    between (`s = 1`, `o[5].x = fabs_(s)`) does not change this.
  - Left (all in the loop): fwd / up op* y / z colours (ours f14 / f2, target f2 / f14). Putting idf on op*'s first
    component moves the fwd z to f14 but y to f12, and the pre-loop fabs_ colours break (82 words). up * f180's
    r is still at -208 (target -216, with two words above it). The loop-top __Vs are still swapped (swapping the
    a and d statements swaps them, so the later statement's temp is the higher one). The vel statement's cam
    pointer is v1 (target v0) and the or a1 / addiu t3 order is unchanged. A 14-toggle random search (idf on the
    ramp fabs_, lerpf, ctor components, the lerp fraction) found nothing below 52.

## snoweffects.uso 0x7FE0 (agent-a run 690)

- **0x7FE0 NM 97.85 -> 99.30 % in-tree (objdiff report; fz 99.28, 66 / 800 words differ)** (agent-a 2623b087c, gate
  PASS, no renames; still 3561 / 3579). Scratch /tmp/claude-1000/agent-a/w690/ (vr.py, rm.py = per-instruction
  register map ours -> target, rw.py = ring writes in a `-S` listing, ft.sh = forcing uopt).
  - **The lever: the ramp's range `hi - lo` is a uopt LR in the target.** Every f4 / f6 / f8 / f10 in the body
    differed (also before the ramp), as a consistent ring relabelling. The target's `sub.s $f16,$f2,$f14` sits
    ahead of the |v| branch in f16, a uopt colour (shared with s), not a ring temp. `w = t->hi - t->lo;` ahead of
    `float f = (fabs_(v) - t->lo) / w;` fixed all ring registers and the ramp's lo / f colours (f14 / f2). A new
    named local (`float r`) costs a frame word (392); reusing `w` (assigned t->f164 later) keeps 384.
  - The instrumented ugen (h384 `u/out/NCC`) trace does NOT reproduce the real NCC's initial FP queue here
    (f4 / f6 swapped vs the `-S` listing); read ring order off `NCC -S` instead.
  - Left (all in the loop): (1) op* result colours y / z = f14 / f2 where the target has f2 / f14 (and the *|s|,
    v114 * k, *f184 families shifted the same way); single-LR forcing (19 LRs x 4 colours) gives at most +0.04, so
    it is LR membership, not priority. (2) Frame: up * f180's r is 2 words lower in the target (two holes above it,
    ours 0), then 1 hole before *|s|'s r (ours 2), and the e / d words 1 lower; the two loop-top __Vs are swapped.
    (3) v0 / v1: the `?:` index (ours v0) vs the stride loads (ours v1) are swapped, with the a-statement cam
    pointer. (4) the or a1 / addiu t3 order.
  - No change (byte-identical): do-while forms, `++i`, `stride > i`, `<= stride - 1`, the pointer locals moved
    before the fade / into the for-init / into the loop / joined onto the for line, `i = 0` before them. The three
    instructions are all on the for line in ugen's preheader (`addu $11; addu $12; move $5`), and as1 pulls them up
    in that order, so the order is uopt's preheader order, not line-driven. Worse: unsigned / short i, a pointer
    increment local, the k index as an if / else, `TV a(up * f180, s)` through the by-value ctor, a named
    `fabs_(s)`, `TCam *c`, dropping g / h, `return TV(...)` / member-wise op*, a friend op* (identical).

## snoweffects.uso 0x7FE0 (agent-a run 688)

- **0x7FE0 NM 97.75 -> 97.85 % in-tree (objdiff report), frame 368 -> 384 = target** (agent-a 69def866b, gate PASS,
  no renames; still 3561 / 3579). Scratch /tmp/claude-1000/agent-a/w688/ (vr.py variant runner, dd.py
  positional/unified diff with branch targets normalised, sl.py vfp-relative slot map ours vs target, md.py).
  - **Frame oracle: `-O2 -g3` keeps the -O2 frame and writes mdebug local symbols** (md.py parses them: name ->
    vfp offset for named locals, edg `__V*` temps and inlined `r` / locals). Unnamed gaps are inline parameter
    words. Diffing sl.py maps against that list shows which statement owns each extra word.
  - Real bug: the w[] stores were one index high (target w -> +0x1C, f16C -> +0x20, f17C -> +0x18).
  - The third loop-top TV word (plan step 2) was the ctor argument temp of `TV d(X, |s|)` with a `const TV &`
    param. **A by-value param `TV(TV v, float s) { float a = fabs_(s); ... }` puts it as an inline param word
    deep in the frame (sp+100, exactly the target's slot)**, and the word copy then precedes the fabs as in
    the target. Passing fabs_(s) as the argument instead leaves the copy after the fabs (801 words).
  - The `int z` block local cost a word above the __Vs; clearing through `i` aligns p / a / d / retTemp.
  - Two unused floats in lerp3 (`float g = f, h = f;`) are the target's two words between the p param temp and
    fwd * f188's r (a `const float &f` param also adds them, but stores f: 801 words).
  - Left: up * f180's __V is the lower of the two (target the higher, sp+336); statement order, `TV a; a = ...`
    and ctor forms do not swap them. The a statement has 2 words fewer before up's r and 1 more after it; the d
    ctor gaps are 2 / 1 where the target has 1 / 2. The `or a1` (the i*44 IV init) vs `addiu t3/t4` order is
    uopt's: source-line joins (all windows around the loop head), pointer locals inside the loop body (the
    hoist is uopt's LICM either way) and declaration order do not move it. Pool word 1's colour (f2 vs f12)
    was not attempted this run.

## snoweffects.uso 0x7FE0 (agent-a run 681)

- **0x7FE0 NM spliced, 93.1 -> 97.8 %, 800 / 800 words** (agent-a 9fd85a406 splice, c233ca62c 97.8; gate PASS
  both, no renames). `SNOW_NM_A_FUNCS = snoweffects_uso_func_00007FE0`, NON_MATCHING placeholder in
  snoweffects_uso.c. Scratch /tmp/claude-1000/agent-a/w681/ (var.py / var2.py variant runners, tr.sh colouring
  trace, ft.sh forcing uopt, trip.sh FP-register families of the op* expansions, fr.sh vfp-relative frame map).
  - **The lerp mov.s is a pool word that is only partly copy-propagated.** Nested inline:
    `lerp3(TV &p, const TV &b, float f)` calls `lerpf(float a, float b, float t) { return (b - a) * t + a; }`
    per component. `a` (p.x read through the reference) becomes an edg pool word coloured f0: x reads it twice
    (the sp+48 reload into f0), y copies p.y into it (`mov.s f0,f10`) and the subtraction reads p.y in place,
    z is fully propagated. Flat statements, a `float c` reused per component, a scalar inline lerp with plain
    `p.x` arguments and a one-level `lerp3` all leave `a` substituted or fully propagated (799 words).
    The fraction passed as an expression is pool word 1 (with fabs_'s and op*'s scalar).
  - **Read pool-word membership off the register families.** With the -O0 slot oracle (pool words in f20..f28)
    and the target's FP colours per op* expansion (s / ctor a / b / c), the target's `up * f180 * |s|` and
    `v114 * k * f184` statements use s = word 2, ctor params = words 3 / 1 / 4, which only happens when they
    are op* chains. Named intermediates (`TV up`, `TV b`, `TV c`) gave s = word 1. Chains: 93.5 -> 97.6 %.
  - Frame: i / s / v / w declared in that order put the s / w spill homes at vfp-8 / vfp-16 (target pattern),
    and a named `float k` between a and d is the target's one-word gap there (97.75 %).
  - Left: pool word 1 colours f2 (target f12). It wins the f2 race against the ctor's second parameter word
    (pri 32 vs 26.7); forcing it to f12 gives 97.9 %. Frame 368 vs 384: the loop body has three TV pool
    words at its top where the target has two, and the function-level block has one word more above it.
    Mnemonics differ by one swapped addiu / or pair (the hoisted sp addresses).

## snoweffects.uso 0xA10C / 0x7FE0 (agent-a run 677)

- **0xA10C EXACT (3558 -> 3559 / 3579, gate PASS, no renames; agent-a c59adb0e0).** New exact donor
  `src/snoweffects_uso/snoweffects_uso_ncc_a.cpp` on both build paths (Makefile `SNOW_A_FUNCS`), void-typed
  blank alias `gl_func_00000000_snowa_v`, `snoweffects_uso_func_0000A10C_rodata = 0xF4` (1/127).
  - **The extra frame word was not the named item.** The `-Wo,-zdbug:6` isvar homes showed walk 1's loop
    body has the named item (-80) and **the inline helper's copy of its `t` parameter** (-84). edg copies an
    inline parameter into a pool temp unless the argument is substituted. `q` is substituted only because
    the argument is an assignment to a variable (`item = ...`): edg evaluates it and uses the variable.
    A cast of the assignment (`(SItem *)(type = ...)`) is not substituted and costs a word too.
  - **Fix:** hold walk 1's item in the function-scope `type` (dead inside the walk). The helper's `q` is
    typed `SType *`, the call passes `type = (SType *)it.cur->data`, and the store is
    `((SItem *)type)->flags = 4`. That leaves one word in the loop body, as in the target.
  - Reusing `c` or `i` for the item changes the colouring (s0 / s2 swap). Passing `t` twice (one use per
    parameter) still copies both. `SLights *const &t` forces t to memory.
- **0x7FE0 draft 85.7 -> 93.1 %, 811 -> 799 / 800 words (not spliced; the donor must be 800).** Levers are
  listed in the draft's comment in `snoweffects_uso_ncc_nm_a.cpp`:
  - int-local clears (separate zero web);
  - `speed < 60 || |v| < lo`;
  - an if / else for +-1;
  - **d through a `TV(const TV &, float)` ctor**, which drops 13 words of return-temp / param-temp copy;
  - &v114 / &vFC pointer locals hoisted;
  - the vtx t value computed before the s store.
  - Left: one `mov.s $f0,$f10` in the lerp (the target copies p.y into the register that held the reloaded
    p.x). No change from: an inline lerp, a reused `float q`, a member lerp, `p.x += ...`.

## snoweffects.uso 0xA10C / 0x7FE0 (agent-a run 669)

- **0xA10C NM 99.04 -> 99.80 % objdiff (in-tree report 99.98)**, all registers now match (agent-a 13de00c6c,
  gate PASS, no renames). Scratch /tmp/claude-1000/agent-a/w669/ (c.sh compile + fuzzy, d.sh diff, md.sh -g3
  homes, dump.sh `-Wo,-zdbug:6` isvar homes).
  - **s1 is edg's pooled pointer temporary, one uopt variable.** It holds the colour Parm `this`, the
    ambient Parm `this` of the copy, and each walk's item. The pool is reused after each full expression,
    so walk 1's item living across its first call makes the whole pool variable callee-saved. Tell: a
    callee-saved register that also holds short-lived values that never cross a call.
  - **Pool temp keeps the load, named item becomes the copy:** pass `it.get()` to an inline helper whose
    item parameter is used more than once (a pool temp). Assign the named item inside the same call from a
    second, differently spelled read (`item = (SItem *)it.cur->data`) through a parameter that is used
    only once, so it is substituted after the pool temp is loaded. With the same spelling (`it.get()` twice)
    uopt adds a CSE temp and gives 3 registers. With a plain copy (`item = p`), item coalesces into p.
  - **Ambient compare as two full expressions** (`x || y` then `z`, joined by goto): two pool words above
    the key temp, the compare on the CSE'd base (v1), the copy through the pool temp (s1). One expression
    makes 3 pool words; a named `const SParm &a` makes the right frame, but a0 / v1 colours.
  - **void alias:** the callees whose result is discarded (9768, 9884, 9BE8, 9C48, 9FE8, getNormal8) are
    declared void. The int returns left a dead v0 def that pushed next()'s result, the loop-body Parm base,
    the col cursor and the walk-2 flags reload into v1. The fix was 94 -> 61 diff rows.
  - **Homes:** NCC homes block-scope locals in declaration order, an array included (n8 is not placed after
    the scalars). j / f were declared first in the vertex-loop body, and one more block-scope word
    (`int unused = 0`) put n8 at sp+112. Declaring `SVec *n` before n8 changes codegen: the assignment form
    loses the hoisted D+0x50 base.
  - Left: walk 2's iterator at sp+84 / 88 (target 88 / 92). Walk 1 has one frame word more than the
    target (named item -80 + pool p -84; the target has one word between the two iterators). Moving item
    to function scope or into the if block does not remove it. The pool p probably has to reuse a
    function-level slot.
- **0x7FE0 draft 85.49 -> 85.74 % (still 811 / 800, not spliced; 621b06d93).** t->speed is now read once
  into a local before the cam-speed test (target f0 at 0x8064). The `bc1tl` + two `mtc1 zero,$f24`:
  - The target's zero for the +0x120..+0x134 clears is a ugen f0 constant.
  - The ramp's 0.0f is rematerialised per arm into f24 (callee-saved, live after 46BC).
  - In the draft, one 0.0f live range spans the 0x4374 call in f20.
  - Next: give the clears their own constant. One way is to clear through an inline `set(0, 0, 0)` or an
    int 0 converted. Then split the ramp zero per arm.

## snoweffects.uso 0xA10C / 0x7FE0 (agent-a run 665)

- **0xA10C NM, objdiff 99.04 %** (commit 08d2e259b on agent-a, gate PASS, no renames). New NON_MATCHING-only
  donor `src/snoweffects_uso/snoweffects_uso_ncc_nm_a.cpp` (the run 661 draft file, moved), Makefile
  `SNOW_NM_A_DONOR` / `SNOW_NM_A_FUNCS`. Run 661's "74 %" was a word count; objdiff already gave the
  draft 96.8 %, and 7FE0 79.0 %. Measure with `objdiff-cli diff -1 expected/...c.o -2 x.o -o - --format
  json FUNC` (`match_percent` of the function); scratch /tmp/claude-1000/agent-a/w665/fz.py.
- **The item copy is a CSE temp, not a second variable.** The target loads cur->data into one register
  (first test, calls) and copies it to another (stores; walk 2 reloads flags at the first join because
  the test load used the other base). Read the item as `it.get()` in the first test and as the named
  `SItem *item = it.get();` everywhere else: uopt CSEs the two loads into a temp and the named item becomes
  its copy. 405 / 405 words, 150 -> 73 words off.
  - Two named pointers always coalesce (`x = item`, chained `x = item = ...`, reference, inline `this`).
  - A named copy survives only if its source is killed before the copy's last use
    (`SItem *x = item; ...; item = 0; x->flags = 4;`), as in IDO_CODEGEN "cse-reread-copy-vs-coalesce".
    That costs a frame word the target does not have: frame 184 vs 176.
  - Left: the temp is v0 here; the target keeps it in s1 across the first call (walk 1 passes it to both
    calls). Also left: the s-register numbering that follows from that, next()'s v1 vs v0, and n8 at sp+120 vs sp+112.
- **A donor body must be exactly the target's length, even NM-only.** REPLACE_FUNC_BODY shifts the later
  functions of the non_matching object. With 0x7FE0 at 811 / 800 words, the exact 0xA8D0 dropped to
  41.7 % and the gate failed.
- **0x7FE0: 79.0 -> 85.5 % with a by-value `TV &operator=(TV o)`.** The target copies `t->mid` into the
  param temp as words (lw / sw through a3), then member-wise as floats. It is now 811 / 800 words (was
  789), so it is not spliced. Frame-only levers (dead scratch arrays to reach 384) leave the fuzzy score
  unchanged (79.05). Next: the remaining instruction-count difference. The diff starts at the |speed|
  compare (`bc1tl` + `mtc1 zero,$f24` x2 in the target) and the per-point Vec3 temp chains.

## snoweffects.uso 0xA10C / 0x7FE0 (agent-a run 661)

- No exacts, no NM wraps (both below 80 %). Commit 123ff873b on agent-a: NCC drafts in
  `src/snoweffects_uso/ncc_drafts/snoweffects_nm_a.cpp` (not built; callees by real name so the
  placeholder-call check skips it). Scratch: /tmp/claude-1000/agent-a/w661/ (var.py variant runner,
  mn.py register-blind shape diff, sd.py shape diff listing, md.sh -g3 slot dump, iu/tr.sh colouring trace).
- **0xA10C: 193 -> 150 words off; the frame now matches** (-O2 -g3 slots equal to the target:
  key2 temp vfp-4, key1 temp -28, col -40, iterators -76 / -88). Levers:
  - The second ItemType walk's `type` at function scope (no block): its by-value key temp becomes the
    first frame word (sp+172). The first walk not in its own block puts its key temp at sp+148.
  - `SKey(int)` ctor for the key argument gives the target's `sw a1, K(sp)` arg-temp store
    (`*(SKey *)p` by value gives none; a named key local adds an addiu / sw pair).
  - `c` / `i` at function scope; the ambient Parm bound once, `const SParm<SVec> &a = t->ambient->v;`
    before the compare (`a.get().x` reads), with the copy reading `t->ambient->v.get()`: gives the
    target's amb-first compare loads and the single parm-pointer CSE.
  - With these, self is s5 as in the target (Bss+0x40 / +0x50 colour s3 / s4).
  - 1/127 at RoData+0xF4 as a literal hoists into the loop preheader as in the target (needs a
    `_rodata` pin in a donor).
  Left: (1) the parm pointer copy colours a0 -> v1 (target v1 -> s1: the copy is callee-saved, so its
  LR must reach a call or share a variable with `c`; a `c`-reuse probe lost a frame word); (2) the normal
  bytes at sp+120 vs sp+112 (one more word in the loop-body block; moving the +0x50 pointer local did
  not move it); (3) both walks lack the target's item copy (data in s1 for tests / calls, item in s0
  for stores; `it.get()`, ref, named copy, `item = next()` probes all fail); (4) walk 2 forwards the
  flags value where the target reloads +0x234 after each `&=` store.
- **0x7FE0 decoded whole** (trail emitter update; the structure is in the draft's comment): speed from
  the camera lean, the s ramp (+0x1A4 / +0x1A8 / +0x1AC), 0x4374, 0x46BC -> +0x74, 0x4714 with a float
  4th arg (mfc1 a3: needs a typed alias), then per point of the write row: position (mode 2 copy or
  lerp), velocity terms through edg Vec3 temp chains (op* result -> return temp sp+244 -> by-value
  operator= param sp+188), w[1..3], vtx s/t and the cam colour bytes (signed `char` stores: trunc.w.s,
  not the unsigned cvt sequence). First draft 789 / 800 instructions, frame 320 vs 384. Next: the
  named Vec3 locals' slots (target 336 / 324 / 312 / 300 / 284 / 272 / 100), the in-loop 64.0f, the
  p.x spill at sp+48.

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

## viewrec.uso / heli.uso (agent-g run 652)

- **viewrec +3 EXACT (3524 -> 3527)**, commit d1fd61c1b on agent-g, no renames:
  - **0x4990 (sound options pad handling) is MIPSpro 7.2.1.** Its two 4-label `switch (cursor)` are
    4-entry jump tables (`sltiu at,v0,4`) at RoData +0x38 / +0x48: cfe tables from 5 labels and IDO 7.1
    NCC never, so it is the 4-label family (MATCHING_WORKFLOW "MIPSpro 7.2.1 donor recipe"). Donor
    `src/viewrec_uso/viewrec_uso_mp72_4990.cpp`, viewrec pattern rule + REPLACE_FUNC_BODY in the
    Makefile. The donor's .rodata holds only the two tables (+0 / +0x10), so the splice-renamed
    `viewrec_uso_func_00004990_rodata` is pinned to 0x38 (no layout function needed). The first C++
    draft was already 99.1; the rest was `self->mode--;` as its own statement (the `--self->mode` call
    argument saves a ugen temp the target burns). viewrec RoData: 4 x 0.1f at +0x0 (no Text reloc),
    then 0x3F24's 10-entry table at +0x10, then the 4990 tables. When 0x3F24 is matched as cfe its table
    will come first in viewrec_uso.c's .rodata; it does not affect the 4990 donor.
  - **0x4DEC (sound options draw), cfe C.** The row-label sprite is `&sVrLabels_7E0[i]` with no pointer
    local: uopt strength-reduces it into a temp spilled to sp+0x64, as in the target. A named `spr`
    local spills into its own home instead (wrong slot). Frame 0x100: one `unused` declared before the
    six colour arrays (white then sits at sp+0xEC) and `unused2[4]` after the scalars. `if (1) {}`
    before `d = 255.0f` lets d reuse white's f0. The mode-label if is spelled `j != mode` (else = the
    white one), giving the target's `beq` polarity.
  - **0x5440 (VrScreen5C draw), cfe C**, `s32 unused[5]` for the 0x48 frame.
  - New pins: sVrLabels_7E0 (Bss 0x7E0), gInputMgr_vr4990, vr_sndTbl_4990 (Data+0x318, in-place 0).
    The screen at proc+0x58 is typedef `VrSoundOptions` in viewrec_uso.c (agent-b's ctor 0x4854 builds it).
- **heli under NCC / 7.2.1, no gain:** 0x980 C++ (ListNode iterator class with inline next(), Vec3
  by-value operator=, dy hoisted into a local) reaches 91.0 under both NCC and mp72 (cfe NM 94.7): the
  first next() result lands in a0 where the target hoists `v0 = 0` and uses v0, and the frame is 0x50 vs
  0x58. 0x4C0 NCC 85.7 (cfe NM 90.7): edg merges the `(float)0` web with 0.0f.
- **heli B08 under mp72 (74.67, hc2.cpp):** `&pp` (sp+356) stays a global a3 candidate with every
  spelling tried: pp as a struct member, as a 1-element array, through a reference, through a pointer
  local, operator=(const Vec3 &) with an inner by-value copy. All score 73.4-74.6. The 7.2.1 donors in
  the repo (game_uso B3C, titproc 116C, game_libs 76F0, kernel 1ADC) use the same `ncc721.sh -O2`
  flags, so there is no flag lever. Still below the 80 % NM threshold; not committed.
- **heli 8A8 under NCC (97.5):** edg drops unused locals (`int pad[2]`, `Vec3 unused`, volatile), so the
  frame cannot be padded to 0x28; `h->off = Vec3(...)` keeps the temp in memory (67 %). The cfe NM
  (99.4) stays.

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
