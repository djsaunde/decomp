# Matching Summary: what actually worked

> A distillation of the 1080 Snowboarding endgame (Nov 2026). At the end, 3288 of 3288 functions were byte-exact
> (100 % code), and the one data unit was matched as C. The last exact was post0b `gl_func_00048AEC` (kit DXVIII).
> The big notes (`IDO_CODEGEN.md`, `PATTERNS.md`, `MATCHING_WORKFLOW.md`, `TOOLING_DECOMP.md`, `N64_FORENSICS.md`)
> are append-only lab books. This file is the map into them.
>
> **How to cite:** "kit CDXCVII" means the `## kit CDXCVII (` heading in `IDO_CODEGEN.md`
> (`grep -n '^## kit CDXCVII (' docs/IDO_CODEGEN.md`). Other references name the doc and its section anchor.
> Every claim here comes from those notes; where the notes are tentative this file says so. Function names are
> short forms: "post0b 48AEC" = `gl_func_00048AEC` in `game_libs_post0b`, "bootup E68" = `func_00000E68` in
> bootup_uso, and so on.

## Contents

1. Policy: what counts as a match
2. Toolchain identification
3. Decoding: get the source right before tuning it
4. uopt register colouring
5. edg (C++ front end) pool words and frame layout
6. ugen temp rings
7. as1: scheduling, xbb and `.alias`
8. Build infrastructure
9. Workflow lessons
10. Contrived matches worth revisiting for readability

---

## 1. Policy: what counts as a match

- **A match means the C (or C++) compiles to the target bytes with the project toolchain.** Post-compile instruction
  patching was removed on 2026-05-23 as match-faking (`INSN_PATCH`, `PROLOGUE_STEALS`, instruction-appending
  `SUFFIX_BYTES*`). About 233 fake matches and 358 episodes were deleted. See the banner at the top of every big
  doc and the CLAUDE.md "POST_CC_RECIPES" note.
- **Still legal:** mechanisms that are not instructions. These are all-zero padding SUFFIX words, USO-header
  `PREFIX_BYTES`, `TRUNCATE_TEXT` / `TEXT_CLIP_KEEP_ALIGN` boundaries, `undefined_syms_auto.txt` pins and donor
  splices of compiler output (section 8).
- **Toolchain:** the original toolchain is used unmodified. Using the game's own other compilers (IDO 5.3, IDO 7.1
  `NCC`, the period MIPSpro 7.2.1 `edgcpfe`) per function counts as choosing the right compiler, "not a toolchain
  patch" (MATCHING_WORKFLOW `#mipspro721-donor-recipe` and the NCC section near "game_uso was written in C++").
  The instrumented and forcing uopt/ugen/as1 builds of sections 4-7 are **diagnosis only**. They are never used to
  build.
- **Hand-written `.s`:** only routines that really were assembly (libultra `bcopy`, `bzero`, CP0 helpers, the boot
  stub and the Yay0 decoder) are kept as `.s` source and `GLOBAL_ASM`'d in place (MATCHING_WORKFLOW
  `#handwritten-assembly-sources`). The `.s` oracle (hand-edited `cc -S` output fed to as0 + as1) is a diagnosis
  tool for as1 questions (kits CDXXI, CDXCIV), not a way to land a function.
- **Permuter:** not banned in the docs, but it is a last resort by user preference. It burns CPU, and its wins
  teach nothing unless analysed afterwards. The endgame kits rely on explicit, semantics-preserving search
  instead: `scripts/spelling-grid.py`, `lever-sweep.py`, `zero-use-sweep.py` (MATCHING_WORKFLOW
  `#spelling-grid-search`, `#lever-sweep-monorepo`, `#zero-use-sweep`).
- **Uninitialised reads** (MATCHING_WORKFLOW `#uninitialised-local-exception`). An empty test on a local that is
  uninitialised on some path is banned. One exception: the target bytes of the *same* function read an
  uninitialised local elsewhere, and a comment cites the instruction and its offset (first use: titproc 5DC). The
  2026-11-12 extension allows a faithful decode of an uninitialised read the target provably makes (first
  candidate: kernel 1ADC).
- **Zero-length aggregates** (`#zero-length-aggregate-lever`, 2026-11-13). A `struct { char c[0]; }` copy (cfe
  Warning 654) may be used as a code-free lever only if the final bytes show no code from it and no ISO form works.
  Comment the reason above it. First use: 396FC; also used for 1824.
- **NM wraps:** `#ifdef NON_MATCHING { C } #else INCLUDE_ASM #endif`, at 80 % or better, else plain INCLUDE_ASM.
  **Episodes** (`episodes/<func>.json`) are logged for exact matches only, so training never pairs C with bytes it
  does not produce.
- **Fake-match traps:** a mnemonic-only diff, `verify-blocks other=0`, or a permuter score of 0 on spill-slot swaps
  can all hide wrong bytes. Byte-verify against `expected/` (MATCHING_WORKFLOW "FALSE-MATCH TRAP" entries).

## 2. Toolchain identification

- **Several compilers in one ROM.** Most C is IDO 7.1 cfe at -O2. The statically linked libultra in game_libs is
  IDO 5.3 at -O1, where verbatim libreultra source matches (MATCHING_WORKFLOW "game_libs IDO 5.3 carve"). game_uso,
  gui and much of post0b are C++ built by IDO 7.1 `NCC` (edg 2.19 front end). The tell is the pointer-to-member
  compare / call shapes only edg emits (IDO_CODEGEN `#game-uso-is-cplusplus-ncc-pmf-compare-d204`). Some -O0
  code (arcproc B4 / 12C and other -O0 donors, per the 1080 Makefile comments) is NCC -O0. The tell is that edg -O0
  has no dead closing-brace `b epilogue; nop`, which cfe emits (Makefile comments citing kit XIX).
- **The 4-entry jump-table family** (game_uso B3C / 8CD8, game_libs 76F0, titproc 116C, kernel 1ADC). These
  targets use a dense `sltiu at,x,4` table that no cfe and no IDO 7.1 NCC emits: cfe tables need 5 labels.
  Kit CDXX first called it a "verified cap", since the decode was right. The forensics runs (TOOLING_DECOMP
  "Toolchain forensics" I-VII, runs 349-393) found the MIPSpro 7.2 / 7.2.1 o32 `edgcpfe` (EDG 2.29). It has the
  rule "table iff n >= 4 and size <= 2n" and runs ahead of the IDO 7.1 back end. On the 214 existing NCC donors,
  87 change under it, so it is a **per-function donor front end only** (`*_mp72_*.cpp` via `tools/ncc721.sh`;
  MATCHING_WORKFLOW `#mipspro721-donor-recipe`). It gave all five exacts: B3C (run 355), 1ADC (kit CDXLIX),
  116C (kit CDLI), 76F0 (kit CDLIV) and 8CD8 (kit DXIII). The notes conclude that 1080 mixed two EDG front ends.
  The exact original is "likely an EDG between 2.19 and 2.29 that we do not have" (forensics II).
- **EDG 2.29 vs 2.19 lever differences** (kit CDXLV). The inline-temp frame cost model is identical. Pool-word
  order is reversed. Temporaries sit above named locals. So NCC-tuned slot levers must be found again on a 7.2.1
  donor. Under 2.29 an unused dummy parameter takes no pool word but a kept one does (kit CDXCII). Kit DII
  covers 2.29 frame allocation from the ucode `.B` and the mdebug symbols.
- **Forensics method** (TOOLING_DECOMP runs 349-393). Collect every public IDO / MIPSpro build, with sha256s and
  URLs recorded (`scripts/forensics/`). Swap one pipeline piece at a time (front end, uopt, ugen, as1). Judge each
  swap by **whole-object fingerprints** and by its effect on the existing exact donors, not by the one target. That
  is how the "4.1 as1", "Olimit", "-O3", "DCC" and "IDO 6.x cfe" hypotheses were each refuted. Kit CDLXXV shows
  every runnable as1 (5.2 through 7.4.4) gives an identical mgrproc object.

## 3. Decoding: get the source right before tuning it

- **Reloc audit first** (MATCHING_WORKFLOW `#reloc-audit-before-decode`, kit CDLXXVII). Dump the function's USO
  TextRelocs and check each data symbol against the C: one struct or several globals, array or scalars, record size
  against the next symbol. post1b 65EE4 sat at 98 % with "one record + nine views". The relocs showed three
  separate 0x40-byte BSS records, and with that fix it went EXACT at plain -O2. Separate symbols pinned at the same
  value give identical bytes, so only the reloc table shows this. No data HI16/LO16 pair means there is nothing to
  fix at this level (kit CDLXXX: 8CD8, 36694, E2D0).
- **Re-decode from the asm** instead of patching an old body. post0b 3B9C0 went EXACT once values the donor had
  named before the loop were written as in-loop expressions that uopt hoists, as in the exact sibling 3BE1C
  (kit CDLXXIII). Kernel run 112 found that many "colouring caps" were hand transcriptions of IDO's own output
  (manual unrolls, `register` invariants). The plain loop IDO started from matched (MATCHING_WORKFLOW
  `#kernel-plain-loops-run112`). A register-normalised diff hides load-order decode errors, so also normalise sp
  offsets and reloc immediates and report the immediates that still differ (kit CCCXXVII).
- **C++ decoded as C.** Many stubborn near-misses were C++ written out as C. Rewriting them as natural C++ for NCC
  (classes, inline members, stock gbi macros) gave large jumps, e.g. 42938 69.98 -> 97.15 (kit CX). After that,
  tuning happens inside the C++ (sections 4-5). A target `this == 0` alloc prologue marks an edg constructor
  (kit CCCLXVIII).
- **Static initializers (`__sti__`).** bootup 6204 / E9FC turned out to be edg static initializers and are EXACT
  (TOOLING_DECOMP `#toolchain-forensics-run349`). The tells (kit CDLXXVII):
  the prologue is placed late, because `__sti__` takes the TU's EOF line as its start line; and a `.data` link
  record `{0, __sti__, 0, 0}` puts a DataReloc on the function's export symbol. 65EE4 had no DataReloc, so it is
  an ordinary function.
- **Data misidentified as code.** game_libs 0x31DF8..0x32D74 was RSP microcode split into five fake CPU functions
  (N64_FORENSICS `#game-libs-rsp-ucode-31df8-reclass`). Some kernel rmon jump tables do not exist in retail
  (N64_FORENSICS index). The other way round, the kernel_026 `.rodata` span is really `.data`: IDO puts every
  address-initialised object in `.data`, `const` included (MATCHING_WORKFLOW `#data-as-c-kernel-026`).
- **Stolen-prologue / orphan fragments.** Splat's `jr ra` heuristic mis-splits functions. Signs: a tiny (0x4-0x8)
  symbol with no `jr ra`; a successor that reads `t6` / `a0` / `f0` uninitialised; a backward branch to before the
  `.s` start. These were almost always one function, so merge forward or backward (MATCHING_WORKFLOW
  "Splat mis-boundary direction 4", "stolen HEAD", "hoisted-prologue mis-split", and the numbered "mis-split
  case" entries, which run past twenty-five). A 2-word `lui a0; lw a0,0x148(a0)` orphan is the next function's first call argument, passed with no
  named local (`#yay0-timproc-promotions-run-439`). A "caller-set `$t6`" cap was a stolen prologue every time it
  was checked.
- **Call-argument evidence** (kit CCCV). A register the target sets, or leaves set, in an argument slot at a call
  is a call ARGUMENT. Adding it fixed 40304 and BB8C. A value spilled and reloaded around a `jal` is often an
  argument too. So is a target `this`-copy: an inline member called on an rvalue receiver,
  `(c + off * 0)->face(i)` (kit CCCLXXXV, 3B6A0).

## 4. uopt register colouring

- **The priority formula** (kit CDXCVII, read from the recompiled `globalcolor` / `compute_save`).
  `priority = num / den`. `num` = sum over the LR's live units of (uses + defs) x loop weight, minus a move cost
  per unit that needs a reload or store. `n` = units + live-through blocks. `den = n if n < 3 else (n - 2) / 4 + 2`
  (integer division), so the denominator is **quantised**: four more blocks cost a long LR 1 in den, and a short LR
  goes from den 3 to den 4 at n = 10. Kit CDXLIII states the same thing as "save / appearance blocks, not LR size".
- **Tie rules** (kits CDXCVII, CCCXXXVIII, CDXV, CDLXXXVII). Picks use a strict `>`, so on equal priority the lower
  LR index wins. The index is roughly the first appearance in the ucode. Registers are scanned v0 v1 a0 a1 a2 a3
  t0 .. then the callee-saved ones, and a strict `<` on cost means the first register in scan order wins a cost
  tie. Short temps cost the same everywhere, so "who gets a2" is decided by which interfering LR is picked first.
  You can win a tie by moving the rival's first appearance later (E68 kit CDLXXXVII) or by making the rival local
  to a later block (3BE1C kit CDXV). Unconstrained LRs colour in LR-id order. With a call in the function, every
  LR counts as constrained (kits CCCXXXVIII, CDLXX).
- **Interference is per basic block** (kits CCCXXII, CDXLVIII, CDXXXI). Two LRs that share a block interfere even
  if one dies before the other is born.
- **Block adders `if (1) {}`.** A code-free BB split raises `n`, which lowers the priority of every LR whose span
  contains it. List every such LR and check each race against the den quantum. In 8CD8 one set of ctor blocks
  served three races (kit DXIII "Rule"). Consecutive empty splits merge into one block. Too many splits can push a
  long constant LR past the split budget, after which the whole object changes (kit D §3).
- **Folded counted uses** `+ 0 * (int)(x)` add uses and raise priority with no code (kits CC, CCCXI,
  `scripts/zero-use-sweep.py`). A *second distinct* fold raises priority again. An identical one is CSE'd into its
  own expression LR (kit CCCXCIII). A code-free test in a later block lowers adjsave (kit CCCXCIV). In cfe,
  `0 * (int)&G` is real code; use the code-free constant test `if (x != K) {}` instead (kit CDLXX). Folds go stale
  after other changes, so re-test them, and removing one can be the gain (E68 kit CDLXXIX, 3B9C0 kit CDXIX).
- **Phantom LRs** (kits CCCXXVIII, CCCXLVIII, CDLXIX). A zero-code CSE candidate or a constant whose only uses are
  folds is still a real LR, and it holds a register through every block between its uses. Place one to occupy the
  register the target leaves "mysteriously" unused. This gave 4FD00 EXACT (kit CDLXIX).
- **v0 is forbidden through a value-returning call's block** (kits CCCXLVII, CDIV, CDXII). Declaring a virtual
  call's return type as `int` (result never read) gave 493AC its colours, and then EXACT (kit CDIV). Holding an
  earlier call result live (`void *rv` + `if (rv) {}` after the loop) pushed a value off v0 for 34890 EXACT
  (kit CDXII).
- **Callee-saved first-use cost** grows with the function's block count (`clamp(movcost * BBs * 0.25, 4, 60)`), so
  extra blocks can push an s-register parameter into a caller-saved register. A code-free use of it as the last
  statement brought s0 back for 1824 (kit CDXCV §2).
- **The instrumented uopt** (TOOLING_DECOMP `#instrumented-uopt-colouring-trace-run414`; kits CDXXVI, CDXCVII). This
  is the dump compiler's recompiled `uopt.c` with printfs added, diagnosis only. It prints the colouring queue,
  each LR's num/den, the forbidden set at pick time and each register's cost. It turns "why is this a2" into
  arithmetic. It also exposed the lda cost-split rule and the BFS neighbour budget behind gui 2DE0
  (kits CDXXVI, CDXXVIII). Earlier, a replay of globalcolor from the `-Wo,-zdbug:5/6` dumps (zero mispredictions on
  five functions) separated PRIORITY problems from IDENTITY problems (kit CCCXCIII).
- **The forcing oracle** (kit D). This uopt build forces a chosen LR to a chosen colour (`FORCE=bp:colour`). Force
  each LR to each colour, and compare the score. If no single forced colour helps, the residual is LR *membership*
  (which values share a variable or pool word), not priority. Trust single-LR results only, since forcing cascades.
  Kit DV used it to show that 98.48 on 8CD8 was reachable by colours alone.
- **KR identity wrappers** (kits DVII, DX, DXIII; definitions in kit DVII). `KR5(const T &r) { return r; }`:
  returning a temporary through a const-ref identity makes the return `mov` read the ctor's `this` result, which
  drops the chain temp's num from 3 to 2 with the same code. This only holds while that word is a live LR in a
  neighbouring statement (kit DXIII §2). `KR2(r) { return *KP(&r); }` with `KP(p) { if (0) { p = 0; } return p; }`
  gives the same dead-block code but keeps its pointer in pooled VREGs, so it adds no frame word (kit DVII). KR1
  (a named `const T *p`) costs a word at every expansion. `K3(T *p) { p = p; return p; }` adds a pool word with no
  block split (kit CDXLVIII). 8CD8 went EXACT with these (kits DX, DXIII).
- **u32-view CSE / copy-propagation splits.** A `u32` view of a pointer in one arm splits a cross-arm expression LR
  (48AEC arm 1 byte-exact, kit CDXCVIII). Storing a block-local copy into a long-lived variable through an int view,
  `*(u32 *)&head = (u32)_h`, hides it from copy propagation, so the copy stays a separate one-block LR with an early
  colour (bootup E68 EXACT, kit CDLXXXIX). A store, then a read-back through a different-signedness type, keeps a
  value in a ugen temp (kit CCCLV, 30AF4 EXACT).
- **The one-variable lever** (kits CCCXXI, CCCXLII, CCCLXXVIII, CCCXCIV, CDXC, DXVIII). One C variable is one uopt
  LR and one colour. When the target puts two roles in one register, they are probably one variable. That holds
  even across types: an int count and a pointer in one register is one variable cast both ways. When it puts one
  m2c variable's roles in two registers, split it. Reusing a variable for a later value lowers its priority
  (gui 3714 EXACT, kit CCCLXXVIII). 4BAF4's three a2 residuals were one count variable (EXACT, kit CDXC). 48AEC's
  s0 family was one named function-scope variable (EXACT, kit DXVIII).

## 5. edg (C++ front end) pool words and frame layout

- **Pool-slot rules, IDO 7.1 NCC / EDG 2.19** (kits CCCIII, CCCIV, CCCLXXXIV, CDXXVII, DIV). Temporaries come from
  a typeless first-fit pool, freed at the start of every statement and reused across statements. The pool is sized
  by the hungriest full-expression. **One pool word is one uopt LR** across every expression that reuses it, so two
  values the target keeps in one register inside one block can be one pool slot (kits CCCLXVII, CDLXV). Single-
  `return` inlines are substituted and get no VREG. Multi-statement inlines materialise `this` and every
  non-constant parameter, unused ones included (kit DIV).
- **Pool-slot rules, MIPSpro 7.2.1 / EDG 2.29** (kits CDXLV, DII, DXI). Named locals and temporaries never share
  words. A block's statement-level temporaries come first, then named locals in declaration order. Inline
  parameters form a per-dtype VREG pool sized by the hungriest statement. Pool-word order is reversed from 2.19.
- **The `-O0 -K` oracle** (kits CDLV, CDLVIII, DIV). Under NCC `-O0`, ugen keeps pool slots 1-8 in `$16-$23` in slot
  order, so the `-O0` listing names the role of every pool word. `-O0 -g2` mdebug names every temporary
  (`__V<addr>`) with the same vfp offsets as -O2 (kit DII). With the target's colour families read off the asm,
  "which statement owns which word" becomes a calculation instead of a search.
- **Kept and non-constant dummy arguments** (kits CCCXV, CDXC, CDXCII). Constant arguments are substituted and take
  no word. A non-constant argument takes one even when the parameter is unused, and the dead copy is deleted.
  Leading dummy parameters `nQk(int z0, .., int z{k-1}, int n)` therefore put `n` on the k-th free word at that call
  site. This put one count on the same word at three sites (4BAF4 EXACT, kit CDXC) and three s0 roles on one word
  (48AEC, kit CDXCIII). Under 7.2.1 the dummy must be **kept** (`z0 = z0;`).
- **Receiver `me()` depth** (kits CCCLXXI, CDII, DVIII, DXV, DXVIII). `T *me() { return this; }` emits no code, but
  each hop moves the callee's temporaries to different pool words. Depths beyond the usual 0-3 paid off: 4FD00 at
  depth 4 and 7 (kits CCCLXXI, CDLXIV), 48AEC's else count at depth 3 (kit DXVIII). A member inline called on a
  simple named variable (`T *ip = &obj;`) does not materialise `this` at all (kit DXV).
- **Named-local scope and order** (kits CCCLXVI, CDXXXVIII, CDLXXI, DXVI). NCC frame order is edg allocation order.
  Function-scope named locals are hoisted above every temporary even when declared last. Every used named local is
  homed in declaration order, so a frame residual is fixed by *where* named locals are declared and *how many*
  there are (gui 0F04 EXACT). At -O2 the frame keeps only ucode-referenced words, in creation order (kit DXVI).
- **By-value parameters and operator temporaries** (kits CCCLXXXVII, CCCXC, CDXXX). A class parameter is allocated
  after its argument is evaluated, below the argument's temps. Reference and pointer parameters come before. A
  by-value identity on an inline operator's own parameter creates its slot inside the caller's full-expression.
  Named `set()`-filled operator results closed 4F2DC (kit CCCXC). 36694's binding copy was a by-value inline
  parameter (kit CDXXX), and 36694 went EXACT later (kits CDLXXXIII, CDLXXXIV).
- **Order of hoisted inline calls** (kit DXVIII §5). Side-effecting receivers and arguments evaluate before the
  hoisted inline calls, so an assignment that must happen late goes in the *last* parameter of a free inline.

## 6. ugen temp rings

- **The t-register ring is a FIFO free queue** (kit CCCXCI). Allocation takes the head over t6 t7 t8 t9 t1..t5, and a
  register freed at its last use goes to the tail. FP temps follow the same FIFO over f4 f6 f8 f10 f16 f18. Any
  register uopt colours anywhere in the function leaves the ring for the *whole* function (kits CCCXCI, CDLXX). Read
  ugen's order from `cc -S` / `NCC -S` (before as1), replay it with a small simulator, and search for the invisible
  op the target needs before writing C. as1 merges consecutive shifts and redundant masks, so `x << a << b` or a
  value-preserving `& 0xFFFF` costs ring slots but no code (kits CCCXCI, CCCLXXXVIII, CDXLVII). uopt never colours
  t6-t9, so a target value in t9 is a ugen-local value (kit CDVIII).
- **Code-free compound tests rotate the FP ring** (kit CDXCI, bootup E2D0 EXACT). The claim that "no C construct
  gives a zero-code FP ring rotation" (kits CDLXX, CDLXXV) was wrong. Two code-free tests on the **same** compound
  expression of memory-resident values, `if (E != a) {} if (E != b) {}`, make uopt CSE E. ugen still evaluates
  E's sub-terms into ring temps, and as1 deletes them as dead. These are hidden pop/free pairs, and E's tree shape
  picks the reordering. Find them with an instrumented-ugen pop count minus the ring writes in the object, and
  choose the shape with a FIFO simulation. Use defined variables as comparands so no constant LRs appear.
- **ugen parity is not forward-only** (kits CCCVIII, CCCXXV). A narrowing cast late in a function can change the
  head block's t6..t9 choices. A whole-arm shift can also be the uopt colour count, not a missing burn (kit CCCXCII).

## 7. as1: scheduling, xbb and `.alias`

- **Source line breaks scheduling ties** (kits CCCLXXIV, CDXVI, CDXLIX, CDLXXVII). Within a block, as1 issues ready
  instructions by highest `aftercycles`, then the **lowest source line**, then ugen order. So whitespace matters:
  one line per region fixed 65EE4's delay slots (kit CDLXXVII). For a statement that must execute first but be
  scheduled after a later one, put it in the body of a one-pass `for` whose step holds the later statement
  (31A74 EXACT, kit CDXVI). uopt drops the line numbers of a join block it folds into a test's fall-through, so
  where a statement sits inside an `if`/`else` changes its line (1ADC EXACT, kit CDXLIX). The prologue's
  placement compares the body's lines with the `.ent` line (kit CDLXXVII). Trace with `-Wab,-R` (kit CDXVIII) and
  `-Wb,-xbbdbg,N` (kit CDL).
- **xbb pulls instructions across blocks into idle slots** (kits CDXVIII, CDLIV, CDXCIV). Kit CDXCIV has the full
  decline-condition list, read from `as1.c` and checked with an instrumented as1. A register live into a side exit
  blocks a pull. At a jump-table `jr`, liveness is the union of the table targets' live-ins. Kit CDLIV first read
  it as "all registers", and kit CDLVI corrected that. Killing a downstream t7 liveness let 76F0's bound-check
  `sll` into the `beqz` slot (76F0 EXACT, kit CDLIV).
- **The 11-candidate cap and code-free labels** (kits CDXCIV, CDXCV, mgrproc 1824 EXACT). xbb tries at most 11
  dominated candidate blocks, and `count > 10` stops the scan. If enough empty blocks are numbered ahead of the
  block that holds `li at,1`, the pull never happens. Kit CDXCIV concluded that C cannot make empty labelled blocks.
  Kit CDXCV found that it can: `if (sel == K) *(Z0 *)(sel + 0x10) = *(Z0 *)(sel + 0x20);` with a zero-byte `Z0`
  prints `bne $2,K,$L; $L:`. as1 deletes the branch to the next instruction (and its `li at`) but keeps `$L` as a
  block boundary. Ten guards are ten empty blocks. Side effects were fixed separately: each guard burns two ugen
  temps, so use multiples of 5 to keep the ring in phase, and the s0 cost was handled as in section 4.
- **`.alias` makes a block unreachable for xbb** (kits CDL, CDLVI). A `.alias` / `.noalias` pseudo-op between an
  unconditional `b` and the next label makes that labelled block unreachable in as1's CFG (weight 65534), so xbb
  never takes a filler from it. 51AD8 got this from a counted use. For 396FC, kit CDLIII argued that no code-free
  `.alias` exists, because uopt rematerialises addresses after calls. Kit CDLVI then got it from two zero-byte
  struct copies from a global at the end of the arm before `default:` (396FC EXACT). One uopt LDA LR places the
  `.alias`, and as1 deletes the dead `la`.

## 8. Build infrastructure

- **Donor splices (`REPLACE_FUNC_BODY`).** A function that needs a different compiler or flags is compiled alone
  into a donor object (`*_ncc_*.cpp`, `*_mp72_*.cpp`, `*_o2_*.c`, `*_ido53_*.c`), and
  `scripts/replace-function-body.py` splices its `.text` into the host object over a same-size placeholder. Use the
  two-target form `host.c.o non_matching/host.c.o: private REPLACE_FUNC_BODY += fn=$(DONOR)`. Without `private`,
  make passes the variable down to the donor prerequisite, which broke clean builds only (MATCHING_WORKFLOW
  "Clean-build-only CI break").
- **Pins** (`undefined_syms_auto.txt`). A donor's jump-table `.rodata` reloc is renamed `<func>_rodata` and pinned
  to the in-place offset (e.g. `gl_func_000396FC_rodata = 0x1A64`). Unpinned imports in promoted bodies can make
  `ld` segfault while reading `.mdebug` (kit CDXCI §5).
- **Table placement and `_lay`** (`#mipspro721-donor-recipe`, kit DXIII §5). In raw-text Yay0 units the table's %lo
  is an in-place addend, so the table must sit at the target's offset inside the donor's own `.rodata`. Layout-only
  functions named `<func>_lay` (e.g. 64 distinct float multiplies for 8CD8, putting its table at +0x100) emit what
  precedes it. The host placeholder re-emits the function's RoData words. For 1824, a file-scope `const char`
  array of the exact staff-credit bytes put the table at +0x5B8 (kit CDXCV §3).
- **`TRUNCATE_TEXT` / clip budgets.** Splits and clips are legal boundaries, but an NM body that grows silently shifts
  everything after it and can cut the post0b sentinel `62F08` (MATCHING_WORKFLOW "post0b NM clip" entries).
  Re-probe the clip after every size change.
- **SUFFIX pad words.** Only all-zero padding is allowed. A 1-word trailing pad becomes `SUFFIX_BYTES_FORCE += fn=0`
  and is trimmed from the `.s`, because a 1-word GLOBAL_ASM sidecar emits 8 bytes (`#yay0-timproc-promotions-run-439`
  item 1).
- **`ld -r` static callee** (run 439 item 2). A Yay0 block links its unit with `ld -r`, which fills a `jal` field
  only for a `static` callee. A global callee leaves the field 0 and verify-blocks reports `jal=1`.
- **Data placement.** IDO puts address-initialised data in `.data` even when it is `const`. objdiff pairs data by
  section name, then by symbol name and size. Re-label the target `.s` to match the C's boundaries
  (`#data-as-c-kernel-026`).
- **The parallel-make donor race** (1080 repo commit `64aa30600`, agent-g run 438; not yet written up in docs/).
  Thirty-two `.c` donors were still in `C_FILES`. Under `-j` each was built twice, once by the top-level make and once
  by the consumer recipe's `$(MAKE) $$donor` sub-make, so a consumer could splice a half-built donor. CI failed
  with `KeyError: symbol ... not found`. Fix: filter donors out of `C_FILES`, add a `DONOR_IN_C_O_FILES` guard,
  add `|| exit 1` on the sub-make and the splice, and set `.DELETE_ON_ERROR`.

## 9. Workflow lessons

- **"Caps" kept turning out wrong.** Every "proven cap" of the endgame was eventually matched in C:
  - bootup E2D0, "no zero-code FP ring rotation" (kits CDLXX, CDLXXV) -> doubled compound tests (kit CDXCI);
  - mgrproc 1824, "C cannot make the labels" (kit CDXCIV) -> zero-byte guarded copies (kit CDXCV);
  - post0b 396FC, "no code-free `.alias`" (kit CDLIII) -> zero-byte copies (kit CDLVI);
  - the 4-entry jump-table family, "verified cap" (kit CDXX) -> MIPSpro 7.2.1 donors (section 2);
  - post1b 65EE4, read as an `-Olimit` fallback -> refuted (kit CDLXXVI), then EXACT from a reloc decode fix (kit CDLXXVII);
  - bootup E68, "m split by uncolourability" / "no interferer can give m v0" (kits CDXLIII, CDLXX) -> int-view copy (kit CDLXXXIX);
  - bootup 6204 / E9FC -> `__sti__` static initializers;
  - many "caller-set `$t6`" caps -> stolen prologues.

  Earlier notes say the same thing (memory "no such thing as a cap", MATCHING_WORKFLOW "EXISTING 'cap' comments
  are often MISDIAGNOSES"). Treat a cap note as "not found yet" and keep a record of what was tried.
- **Instrument the tool instead of searching.** The endgame turned when agents stopped running thousands of variants
  blind and read the compiler's decision instead. Tools used: the instrumented uopt (priority arithmetic), the
  forcing oracle (colour vs membership), `-O0` listings (pool roles), the as1 xbb trace and `.s` oracle (why a pull
  happens), and the ugen pop counter plus FIFO simulator (hidden ring events). All are diagnosis only. Random
  search (kits CCC, CDIII) and full factorials still helped, but mostly to search near a basin found by reasoning.
- **Re-grid after every gain** (kits CCCLXI, CCCLXXXII, CDXIX). A lever that fixes one register often makes an older
  lever stale. Drop it, re-test old negatives, and look for new split points.
- **Fit layout before colours.** Reading the frame through M-offsets and per-site registers (kit CDXCVI), or with a
  layout-distance score (kit DII `ev2.py`), beats chasing the fuzzy score. A max-score permutation with loads at
  the wrong field offsets is a false optimum (kit CCCXXIX).
- **Parallel agents with split ownership.** Agents c, g and h each worked an assigned list of functions in its own
  worktree (`scripts/spin-up-agent.sh`). Lists were swapped now and then for a fresh reading (kits CCCLIX, CDV),
  and every kit records its base commit so another agent can pick up the body. Hazards: a shared scratchpad
  (put helpers under `scratchpad/<letter><run>/`, `#shared-scratchpad-collision-run105`) and concurrent edits to
  one `.c`. Land through one landing worktree (agent-d).
- **Landing scripts.** `scripts/land-agent.sh <letter>` purges stale objects (`purge-landing-objs.sh`), cherry-picks
  the agent branch into the landing worktree and runs `gate-landing-tree.sh`: ROM cmp, `non_matching_objects`,
  report refresh, exact-set diff against origin/main, sentinels, and a fresh-clone build. `finish-landing.sh`
  commits report.json and pushes. `land-agent-wave.sh` handles multi-commit waves and regenerates conflicting
  `expected/` objects. Each is one command, so a landing raises no permission prompts. `verify-blocks 6/6` is
  required for Yay0 units.

## 10. Contrived matches worth revisiting for readability

These are byte-exact and policy-clean, but the source reads as compiler steering rather than as what the original
programmer wrote. A future pass could look for a more natural form that gives the same bytes. Treat these as
candidates, not known errors: the natural form may simply not exist.

- **mgrproc 1824**: ten `if (sel == K) *(Z0 *)(sel + 0x10) = *(Z0 *)(sel + 0x20);` zero-byte guarded copies to trip
  the xbb candidate cap, a code-free trailing `if (s0) {}`, and a credits array placed by hand (kit CDXCV).
- **post0b 396FC**: two zero-byte struct copies from a global before `default:` (kit CDLVI).
- **game_uso 8CD8**: `Vec3(float, int, float)` vs `Vec3(float, short, float)` base ctors chosen by argument TYPE,
  to carry five or zero `if (1) {}` blocks; KR5 / KR2 / K3 identity wrappers with per-site dummy counts; and a
  `_lay` function of 64 float multiplies that exists only to place the jump table (kits DX, DXIII).
- **post0b 48AEC**: an int count held in a `Ctx *` variable (`(Ctx *)count`, read back as `(int)A`), a count in a
  dead `f32 (*)[4]` variable `B`, `me(me(me(gctx)))` receiver depth, and dead-stored named words for frame
  placement. The notes do not say whether the last of these survived to the final body (kits DXVI-DXVIII).
- **bootup E2D0**: two code-free tests of an odd compound
  `((v[1].z + v[1].y) + (v[0].z * v[0].x)) - (v[0].y * v[1].x)` against `lim` and `dot`, only to rotate the FP
  ring (kit CDXCI).
- **bootup E68**: a block-local copy stored through `*(u32 *)&head = (u32)_h` plus a folded use, and a loop counting
  through the dead `tlut` local (kits CDLXXXV, CDLXXXIX).
- **post0b 4BAF4**: leading unused dummy parameters (`nQk`) to pick pool words (kit CDXC).
- **post0b 4FD00**: `0 * (int)&G` phantom folds and `me()` depth 7 (kits CDLXIV, CDLXIX).
- **post1b 65EE4**: `if (s != 0) {}` dead tests on `&record` to stop address CSE, and one source line per region
  (kit CDLXXVII). The dead test may well be what an inlined cfront-style ctor looked like (the notes draw that
  parallel), so this one may be faithful.
- **post 31A74**: a one-pass `for (mode = 1; mode; call(..), mode = 0) { store; }` to invert source lines (kit CDXVI).
- **post0b 493AC**: a virtual `hit()` declared `int` whose result is never read, plus `me0()` levels inside
  `Arr::iter()` (kit CDIV).
- **post0b 34890**: block-scope `void *rv` + `if (rv) {}` to keep v0 busy (kit CDXII).
- **post0b 3B6A0**: `(c + off * 0)->face(i)` rvalue receivers and code-free `if (pt) {}` tests (kit CCCLXXXV).
- **post0b 415A4**: a leading value-preserving `| 2` so uopt folds only the first identity OR (kit CCCLXXXI).
- **post0b 37540**: a volatile-view union `union { P3 v; VW w; }` to get re-reads of a just-stored struct
  (kit CCCLXX). This could be faithful too, but the notes do not say.
- **titproc 5DC**: the uninitialised-local `if (t) {}`, which is allowed under the exception but is still a lever
  (MATCHING_WORKFLOW `#uninitialised-local-exception`).
