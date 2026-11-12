# Tooling Decomp

> Decompilation tooling: m2c, Ghidra, the permuter, decomp.dev integration.

_10 entries. Auto-generated from per-memo notes; content may be rough on first pass — light editing welcome._

## Index

- [Toolchain forensics III: MIPSpro 7.2 / 7.2.1 C++ edgcpfe (1997 / 1998) against the 1080 caps (run 352)](#toolchain-forensics-run352) — _Found on discmaster.textfiles.com: the MIPSpro C++ 7.2 CD, the Varsity Update Aug 1998 CD (7.2.1 c++_fe / c_fe) and IRIX 6.4 IDF 1.1 (7.2.1 driver / uopt / ugen / as1). sha256s and an IRIX inst extractor are included. Both o32 edgcpfe builds say "EDG 2.29" (Aug 29 1997 / Mar 13 1998), have the 4-label table rule, AND inline class-returning-by-value operators (no weak copies; 1DDC stays 384 words). So 7.4.4's non-inlining is a later SGI change. B3C is 706/706 standalone, and 116C / 76F0 / 1ADC are identical to 7.4.4's output. 8CD8 gets the target length plus a native table at the target's position. But on the NCC donor gate it is 127 same / 87 differ (7.2 and 7.2.1 give identical objects): evaluation order, temp frames, `this` spills. 57D8's 8-way compare chain rules it out for that donor. So 1080 mixed two edg front ends. It is safe only as a per-function donor front end._
- [Toolchain forensics II: IDO 5.2 / 6.0 / MIPSpro 7.4.4 against the 1080 caps (run 351)](#toolchain-forensics-run351) — _The three LLONSIT archives are decomp.me's own sources (decompme/compilers values.yaml), with sha256s recorded. No cfe (5.2 / 6.0 / 7.1 / 7.4.4) tables a 4-label switch, so "IDO 6.x cfe" is false. EDG 2.29 (MIPSpro 7.4.4 DCC) has the target's rule (n >= 4, size <= 2n). For C-style code it is cfe plus native tables: game_uso B3C comes out 706/706 standalone, with the unit's leading 1/6 literal in place, and 940 is unchanged, and 116C / 76F0 are left with only the cfe residuals. But 93 of the 214 NCC donors change under it (it will not inline class-returning operators, so the copy chains disappear), and it was built in 2002. 8CD8 (inlined operators plus a 4-entry table) rules out both EDG builds. game_uso also holds 57D8, whose dense switches are compare chains, so it most likely mixes two front ends. The original is likely an EDG between 2.19 and 2.29 that we do not have. 5.2 / 6.0 / 7.4.4 as1 and back ends: 396FC / 1824 / 65EE4 are unchanged, and 5.2 / 6.0 as1 break sentinel exacts. No new compiler-generated functions among the open non-exacts._
- [Toolchain forensics: every IDO-family toolchain we can run, and what each 1080 cap really is (run 349)](#toolchain-forensics-run349) — _Downloaded decomp.me's ido5.3_cfront, which bundles cfront 3.0.1 and Delta C++ (EDG 2.19) plus qemu-irix. bootup 6204 / E9FC were edg static initializers (__sti__: the prologue is on the TU's last line, the ctor call on the definition line, so lui comes before sw ra) and are now EXACT. Mixing 5.3 / 7.1 uopt / ugen / as1 gives byte-identical code on 396FC / 1824 / E2D0. DCC does not explain the C++ near-misses. The 4-entry jump-table family: IDO 4.1's pcc-derived ccom / accom genswitch (table iff n >= 4 && 0 < range <= 3n) matches the target exactly. Confirmed by running accom (through the docker-snapshot glibc + glib shim) with the 7.1 back end: native `sltiu 4` tables, and kernel 1ADC reaches 114/134 words (cfe NM: 103). But 76F0's operand order and float compares match cfe, not accom, so the likely original is a cfe with a 4-label threshold (IDO 6.x?). The 4.1 as1 / as1 options are ruled out for 396FC / 1824 / E2D0 by whole-object fingerprints._
- [decode-sweep.py: automated objdiff-gated m2c-graft decode transforms (2026-06-16)](#decode-sweeppy-automated-objdiff-gated-m2c-graft-decode-transforms-2026-06-16) — _`scripts/decode-sweep.py` automates the three biggest mechanical post-graft %-movers (graft-cleanup items 21/22 + struct-copy collapse): builds a per-(base-register,offset) WIDTH CATALOG from the target's own `.s` (lb/lbu/lh/lhu/lw/lwc1...; handles BOTH raw-.word USO and mnemonic kernel/bootup formats), then (1) retypes mistyped `*(s32*)((char*)BASE+0xOFF)` derefs to the cataloged sub-word type, (2) splits absolute `*(T*)0xADDR` derefs to `&D_00000000+0xADDR` (also strips `(unaligned sN)` artifacts — a COMPILE-ENABLER, not just a %-mover), (3) collapses >=4 contiguous word-copies into Quad4 (16B exact, no whole-struct overshoot). Each transform is OBJDIFF-GATED (rebuild + re-read fuzzy, revert on regression) and idempotent. Validated: retype +2.58pp (gl_func_00021498 28.20->30.79), +3.77pp (gl_func_00064588 48.67->52.44); revert path byte-verified. NO-OP on already-correctly-typed fns (no false gains)._
- [disasm-raw.py dropped pinned jal/lui reloc-alias lines from raw-.word .s (FIXED 2026-08-22)](#disasm-rawpy-dropped-pinned-jallui-reloc-alias-lines-from-raw-word-s-fixed-2026-08-22) — _Pre-fix, its `.word`-regex scan silently dropped pinned `jal sym` / `lui $r,%hi(sym)` lines (word only in the `/* OFF WORD -> sym */` comment): calls vanished, every later offset shifted -4. Now parses line-by-line, shows callee names, and has `--selftest`. Distrust pre-2026-08-22 disasm-raw output for any USO fn with pinned relocs._
- [coloring-solve.py: inverse register-coloring solver from the uopt trace (2026-06-15)](#coloring-solvepy-inverse-register-coloring-solver-from-the-uopt-trace-2026-06-15) — _`scripts/coloring-solve.py` parses a `-Wo,-zdbug:6` coloring trace for one function (decodes LR bitpos -> register, constrained/unconstrained, priority/bitpos color order, spills, splits) and, given target+build `.s`, aligns the two instruction streams to separate REGISTER-RENUMBER residuals (shape-correct, wrong reg) from STRUCTURAL diffs, emitting the target<-build register-pairing histogram + algorithm-derived levers. The generalizable regalloc-cap diagnostic instrument: tells you WHICH LR is mis-colored and WHY before you touch the C._
- [permuter-factory: unattended permuter queue-runner over the 90-99 long tail (2026-06-15)](#permuter-factory-unattended-permuter-queue-runner-over-the-90-99-long-tail-2026-06-15) — _`scripts/permuter-factory.py` auto-discovers the 90<=fuzzy<100 band from a fresh objdiff report (size-sorted, cap-comment-filtered), runs `import.py` per-fn then a wall-clock-bounded `permuter.py --best-only --stop-on-zero -jN`, splices the best output back, and OBJDIFF-VERIFIES (the permuter score lies). Checkpoints to `.permuter-factory/` for crash-resume; commits verified 100.0 cracks as "<fn> permuter-factory crack to 100.0 (NM body, pending land)" (no land/push). Kills children by PGID, never pkill -f._
- [references/ido: the decompiled uopt source + dump-flag instrumentation (2026-06-11)](#referencesido-the-decompiled-uopt-source--dump-flag-instrumentation-2026-06-11) — _n64decomp/ido clone = uopt allocator source with original symbol names; -Wo,-zdbug:1/2/5/6, -dowhyuncolor, pass kill-switches, -zmovc. Grep it before theorizing about regalloc caps; derived rules in IDO_CODEGEN._
- [578B4 pass 8: slot-map closed via decl-order relayout + per-arm web splits (81.52)](#578b4-pass-8-slot-map-closed-via-decl-order-relayout--per-arm-web-splits-8152-2026-06-11) — _Recipe: target slot map from m2c spXXX names -> decl reorder (addr = offset-frame); split shared webs by renaming arm temps to the spXXX vars; volatile locals for selector-CSE temploc + dead stores; drop m2c phantom call args. NEGATIVES: temp_t1_3 per-arm split cascades scratch rotation -300 LCS; goto-dispatch collapses; fuzzy underweights sp-offset fixes ~25:1 (track exact-word LCS + offset histogram)._
- [Hybrid emit (m2c temp coalescing): the spill-home frame-bloat fix for big SSA grafts](#hybrid-emit-m2c-temp-coalescing-the-spill-home-frame-bloat-fix-for-big-ssa-grafts-578b4-pass-7-2026-06-11) — _Big SSA graft frame bloat = spill homes for "not colored (-ve save)" webs (142 on 578B4), NOT temp pressure. `scripts/m2c-hybrid-emit.py` coalesces same-(reg,type) disjoint-textual-range temps: 578B4 75.07->81.22, frame 1280->496 exact. Tune per class (a/v win, t0/ra hurt); useless vs structural drift (44F4 negative: s-reg phi merges crash 51->39)._
- [`discover --sort-by size` marks every INCLUDE_ASM placeholder as `[has source]` — write a sub-filter for genuinely-unstarted candidates](#feedback-discover-has-source-misleading) — Discover treats any mention of a symbol in `src/` as "has source", including bare `INCLUDE_ASM(...)` lines. For source-3 picks (small unstarted), use a Python filter that checks for an actual C function definition (`(void|int|...) name(...)` syntax), not just the symbol name.
- [Decomp prioritization — call-graph DFS from entry point beats by-segment-size mass-match](#feedback-decomp-call-graph-priority) — When a project has a clear entry point (USO loader → main loop → per-frame update), depth-first decomp from there reveals the actually-used code and naturally drives type discovery.
- [m2c on .word-only USO asm — assemble + objdump round-trip to get mnemonics](#feedback-m2c-word-only-asm) — splat emits `.word 0xNNNNNNNN` for USO functions whose lui-relocations spimdisasm can't resolve; m2c then errors with "Function contains no instructions". Round-trip the bytes through `mips-linux-gnu-as` + `objdump -d -M no-aliases` to get readable mnemonics for hand-paste into a temp .s.
- [Scanning NM wraps for near-misses: compare the LINKED elf, not the unlinked .o (jal/symbol immediates are 0 in the .o → false diffs)](#feedback-nm-wrap-scan-use-linked-elf) — _2026-05-23. To auto-find promotable NM wraps, building `build/non_matching/.../<file>.c.o` and diffing each function's words against `asm/.../<func>.s` reports a FALSE 1-diff for every resolved-call/symbol-ref function: in the unlinked .o, `jal target` is `0C000000` and `lui/addiu/lw` symbol immediates are 0, while the asm shows the resolved values. So `gl_func_00024080` (already episode'd, calls `gl_ref_00037F80`) shows as "1/8 regonly JAL" — a false positive. Only RELOC-FREE functions (no jal, no symbol lui/addiu) give a valid .o-vs-asm comparison; for everything else, link first and diff `build/tenshoe.elf` (default path) or the linked non_matching elf. Also: cross-check `ls episodes/<func>.json` — the scan resurfaces already-done functions whose `.NON_MATCHING` alias artifact looks like a near-miss._
- [decomp-permuter `import.py` needs a C body under `#ifdef NON_MATCHING` — bare `INCLUDE_ASM` invisible](#feedback-permuter-import-requires-ifdef-non-matching-body) — _When you intend to grind a function via permuter, the verified decode MUST be wrapped in `#ifdef NON_MATCHING / #else INCLUDE_ASM` (even at sub-80% fuzzy where the `/decompile` skill normally says "keep plain INCLUDE_ASM"). `import.py` parses C source for a function DEFINITION; `INCLUDE_ASM(funcname)` alone registers no function. Discovered 2026-05-16 via parallel-agent commits restoring DBEC/DDC0 C bodies as permuter seeds._
- [WORKING permuter setup (2026-05-23): `permuter_settings.toml` (compiler_type=ido) + import with full `CPPFLAGS=-I include -I src -DNON_MATCHING`](#feedback-permuter-working-setup-2026-05-23) — _The 0/6 F444 failure was a MISCONFIG, not a permuter limitation: no settings file and the import lacked `-DNON_MATCHING` (so it compiled the `#else INCLUDE_ASM` path, no C body) and `-I include -I src` (headers). Fixed; validated gl_func_0005C784 base 75→35 with 0 errors. This is the sanctioned last-mile match tool now that INSN_PATCH is banned._
- [`import.py` "Failed to find compile command" on a big multi-fn TU → build the permuter scratch dir BY HAND; BUT on a frame-SIZE residual the reseed-from-best "fuzzy gain" is a FALSE IMPROVEMENT — objdiff normalizes sp-offsets and hides frame growth, so gate on RAW byte-exact count not fuzzy](#feedback-permuter-manual-scratch-and-reseed-chain) — _`import.py` derives compile flags via `make --always-make --dry-run` + grep for the source filename; on a 30k-line shared TU (e.g. `game_libs_post0b.c`) where you want to permute a minimal extract, or any scratch .c that isn't a make target, it fails "Failed to find compile command from build script output". Bypass: build `nonmatchings/<name>/` by hand — `base.c`=`cpp -nostdinc -DNON_MATCHING -I include -I src scratch.c | grep -v '^#'`, `target.o`=`mips-linux-gnu-as -EB -march=vr4300 -mabi=32 -I include` over the `.s` with the glabel/endlabel macro prelude prepended (copy from any existing scratch's `target.s`), `compile.sh` (cd to root + the IDO 7.1 cc line), `settings.toml` (`func_name`+`compiler_type="ido"`); the scratch .c must live INSIDE the project tree (root-detection walks up for `permuter_settings.toml`). Verify the manual base.o is byte-identical to the in-tree `.o` first. **CAUTION (the real lesson):** reseed-from-best on gl_func_0004C928 (frame 0x80 vs target 0x78 + coloring cascade) drove permuter score 720→455 and objdiff fuzzy 97.56→98.71% over 7 passes — but this was a FALSE IMPROVEMENT (REVERTED): objdiff NORMALIZES sp-relative offsets so it neither penalizes frame growth nor docks wrong-offset sp loads, and the chain raised fuzzy by GROWING the frame 0x80→0x98 (further from 0x78); RAW byte-exact-position matches actually DROPPED 87/227→84/227. When the residual is a frame-SIZE diff, gate the permuter on raw exact-match count + the frame word, NOT on `fuzzy_match_percent`; a rising fuzzy with a diverging frame is a regression. Permuter is right only for SAME-frame coloring/scheduling. 2026-06-22 agent-b._
- [Permuter "score 0" is a FALSE POSITIVE for pure spill-slot (sp-offset) swaps — its scorer normalizes sp-relative offsets; ALWAYS raw-byte-verify before logging an episode](#feedback-permuter-score-0-sp-offset-false-positive) — _gl_func_0005D054 (quaternion product): permuter reported base score 0 but `cmp` of the built .text vs target still differed by one x↔z spill-slot pair (32↔40(sp))._
- [CI / decomp.dev compares fresh build/.o vs committed expected/.o — `make expected` results MUST be git-committed for changes to show on the dashboard](#feedback-expected-must-be-committed-for-decomp-dev) — The land script and `scripts/refresh-report.sh` do NOT run `make expected`.
- [Ghidra struct annotation does NOT auto-propagate across xrefs — each function in a family needs its own prototype set](#feedback-ghidra-struct-annotation-doesnt-auto-propagate) — _Validated 2026-05-04 on 1080's rmon family.
- [Permuter DOES crack small (low-score) load-order / instruction-scheduling residuals — try it on 1-3 diff scheduling near-misses](#feedback-permuter-cracks-small-load-order) — _A 2-diff load-ORDER residual (base score 20) that ~10 hand C variants couldn't flip cracked at iteration 18 (~30s): the winning mutation combined two stores into `a0[0]=(a0[1]=a0)`, shifting IDO's tail scheduling. When diffs are operand/load ORDER (same opcodes/regs, reordered) — NOT $s-reg renumber — run the permuter with `--stop-on-zero`. Import: `C_INCLUDE_PATH=include python3 .../import.py src/<f>.c <clean-glabel.s> CPPFLAGS=-DNON_MATCHING`. Verified game_libs_func_00066440._
- [Permuter scores ≥1000 genuinely mean "structural issue, no match possible" — stop grinding (BUT 2026-05-23 refinement: it CAN crack record-append/pointer-arith $t-class register-renumber via shape-changing mutations — 2 episodes; resists loops/delay-slot/cursor/unfilled-delay/$s-$a-class)](#feedback-permuter-1000-plus-structural) — _Ran decomp-permuter random mode for ~3 minutes on `n64proc_uso_func_00000014` (12k+ iterations).
- [pyghidra-mcp setup notes for N64 decomp work — JDK 21, raw-binary load, MIPS:BE:32:default, ~7-min auto-analysis](#feedback-pyghidra-mcp-setup-for-n64-decomp) — pyghidra-mcp install gotchas verified 2026-05-04.
- [report.json was overstating because land script used `make expected` — RESOLVED 2026-05-04](#feedback-report-json-vs-decomp-dev-diverge) — _HISTORICAL — the land script's `make expected` blanket-cp build/→expected/ used to pollute expected/ with decomp-bodies build, inflating matched_code_percent by ~1pp (8.84% reported vs 7.68% truth).
- [When to consult Ghidra during /decompile (trigger list — m2c remains the default)](#feedback-when-to-consult-ghidra-during-decomp) — _1080 has a Ghidra project + MCP server, but reaching for Ghidra has cost (slower than m2c, GCC-flavored not IDO-flavored).


---

## decode-sweep.py: automated objdiff-gated m2c-graft decode transforms (2026-06-16)

`scripts/decode-sweep.py` front-loads the 40%->70% climb on big struct-heavy
functions by automating the three deterministic post-graft cleanups that were
previously done BY HAND on every big function (graft-cleanup items 21 & 22 +
the 00004118 struct-copy lesson). All three are derivable from the TARGET asm,
so the tool builds an access catalog once and rewrites the m2c body to match.

**Input contract:** a `.c` file that ALREADY contains a *compilable*
`#ifdef NON_MATCHING` body for FN (a graft you've run through
`m2c-graft-clean.py` and fixed any remaining m2c artifacts — `(bitwise f32 *)`,
`*(f32 *)& rvalue`, pointer-vs-int compares; those are NOT in scope here). The
function's `.s` must be reachable under `asm/nonmatchings/`.

**The access catalog** is the load-bearing primitive: parse the function's own
`.s` and bucket every `(base-register, offset)` to a width
(lbu->u8, lb->s8, lhu->u16, lh->s16, lw/sw->w32, lwc1->f32). It handles BOTH
the raw-`.word` USO format (objdump the byte blob) AND the mnemonic
kernel/bootup format (parse decoded ops directly). The m2c var/temp name
encodes the originating register (`var_s2` -> reg `s2`), which is the join key.

**Transforms (run in order, each objdiff-gated):**
1. **field-width retype** — retype `*(s32*)((char*)BASE+0xOFF)` to the
   cataloged sub-word C type. Base-register match (`var_s2`->`s2`) is
   high-confidence; for arg/sp/expression bases it falls back to an
   offset-global agreement (every base that touches that offset agrees on one
   sub-word type). NEVER narrows a `w32` slot, NEVER touches a mixed-family or
   signed-clash (ambiguous union) slot — the no-blanket-retype rule
   (578B4-pass-5: blanket s32->X broke pointer arithmetic).
2. **global-base split** — rewrite absolute `*(T*)0xADDR` (>=0x100) to
   `*(T*)((char*)&D_00000000 + 0xADDR)` so IDO does the target's lui %hi+lo16
   split instead of a bare lui+ori immediate; catches the s8/s16/u32/u64/void
   widths `m2c-graft-clean.py` misses. Also strips `(unaligned sN)` cast
   artifacts. KEY FINDING: this transform is often a COMPILE-ENABLER, not just
   a %-mover — a fresh graft with `*(s16 *)0x2048` and `(unaligned s32)` casts
   won't even parse until split, so run it before measuring a baseline.
3. **struct-copy collapse** — collapse runs of >=4 contiguous word-copies
   (dst & src offsets both advancing by 4, same bases) into 16-byte `Quad4`
   struct copies (auto-injects the typedef). EXACT 4-word chunks only; a
   partial tail (<4) stays single — whole-struct overshoots (00004118).

**Gating + safety:** `--gate` (default) rebuilds `build/non_matching/<unit>.c.o
RUN_CC_CHECK=0`, regenerates the objdiff report, and keeps a transform only if
the function's `fuzzy_match_percent` rises (or `--keep-flat` for ties);
regressions are reverted byte-identically (verified). Idempotent / re-runnable.
`--no-gate` applies blindly for a fast preview. `--only retype,global,structcopy`
selects transforms.

**Validation (agent-w, NM bodies, not landed):**
- `gl_func_00021498` (game_libs_post): retype 16 changes KEPT, **28.20 -> 30.79
  (+2.58pp)**.
- `gl_func_00064588` (game_libs_post1b): retype 11 changes KEPT, **48.67 ->
  52.44 (+3.77pp)**; re-run idempotent (no further changes).
- Revert path: forced-regression test (mock measure 48.67->40.0) reverted and
  restored the file byte-identically.
- `gl_func_00046050`: 0 sub-word offsets in catalog -> 0 changes (correct
  no-op; the tool never invents gains on already-correctly-typed code).

**Limitations:** operates only on the canonical `m2c-graft-clean` deref form
(`*(T*)((char*)BASE+0xOFF)`); heavily hand-refactored bodies (named typed
locals, FW() macros) are untouched. The retype gain is bounded by how many
sub-word fields the function has. Does not fix the m2c artifacts that block
compilation in the first place — graft-clean + manual artifact cleanup is the
prerequisite. structcopy needs the copy to already be in single-word form
(m2c usually emits it that way; an already-typed struct field copy is skipped).

## coloring-solve.py: inverse register-coloring solver from the uopt trace (2026-06-15)

`scripts/coloring-solve.py` (monorepo root) inverts IDO 7.1's register
allocator. The allocator is Chow-Hennessy priority-based coloring
(references/ido, src/uopt/uoptreg2.c `globalcolor`) and is fully
deterministic given its ucode input; `-Wo,-zdbug:6` emits a complete
per-decision trace. This tool reads that trace + the target/build `.s` and
tells you exactly which live range is mis-colored and what source change the
algorithm says would fix it.

Usage:

```
# 1. get a coloring trace (strip // first; needs -DNON_MATCHING for #ifdef bodies):
sed 's://.*$::' src/<seg>/<file>.c > /tmp/nocmt.c
tools/ido-static-recomp/build/7.1/out/cc -c -G 0 -non_shared -Xcpluscomm \
  -Wab,-r4300_mul -O2 -mips2 -32 -DNON_MATCHING -Wo,-zdbug:6 -I include \
  /tmp/nocmt.c -o /tmp/x.o          # writes ./uoptlist (needs the ecvt patch)
# 2. dump the build's .s for the function:
mips-linux-gnu-objdump -d --no-show-raw-insn build/non_matching/src/<seg>/<file>.c.o \
  | awk '/<FUNC>:/{f=1;next} f&&/^[0-9a-f]+ </{exit} f&&/:\t/{print}' > /tmp/build.s
# 3. solve:
python3 scripts/coloring-solve.py --trace uoptlist --func FUNC \
  --target-s asm/nonmatchings/<seg>/FUNC.s --build-s /tmp/build.s
```

What it decodes (register color codes from `enum RegisterColor`,
uoptdata.h: 1..13 = v0 v1 a0..a3 t0..t5 ra; 14..23 = s0..s7 fp ra;
24..35 = f0 f2 f12..f30):

- The full coloring trace: each LR's bitpos -> register, whether it was
  colored in the **constrained** phase (max-priority order; earlier = higher
  priority = grabs the lower register) or the **unconstrained** phase (plain
  bitpos / first-occurrence order), plus spills ("not colored (-ve save)" =
  a frame home) and live-range splits.
- The itab cross-reference (ichain id, op, M/P class, frame offset) for each
  LR, so you can map a trace LR back to a source value.
- **The key output for cracking a cap:** it re-aligns the target and build
  instruction streams TWICE — once keeping register names, once wildcarding
  them — so it can report how many instructions are SHAPE-CORRECT but
  REGISTER-RENUMBERED (the coloring residual) vs genuinely STRUCTURAL, and
  prints the `target_reg <- build_reg` pairing histogram. A dominant pair
  like `$a0 <- $v0 x61` means one value is colored one class too low across
  61 sites — a single coupled coloring permutation, not 61 bugs.

The levers it names map to the algorithm: to push a value to a HIGHER
register (v0->a0), color it LATER by LOWERING its priority (longer span /
fewer uses); to a LOWER register, color it EARLIER (higher priority, or
earlier bitpos if unconstrained); to flip two equal LRs, change their
relative first-occurrence order; to spill, kill priority (inline recompute).

CALIBRATION NOTE (func_0001304C, where this was built): the diff mode showed
the entire 92.61->100 residual is `$a0 <- $v0 x61` + the coupled
`$v0 <- $v1` / `$v1 <- $a0` deref cascade — the function-tail base pointer
`*(*(func_0000023C+0x18)+0x158)` colors into v0 in the build but a0 in the
target. The base also wants the SYMBOL spelling `&func_0000023C + 0x18`
(`lui/lw %hi/%lo`, a reloc) not the raw `*(void**)0x254` (`lw N(zero)`, no
reloc). VERIFIED DEAD ENDS for the a0 targeting: holding the full chain in
one local (build CSEs it into v0, longest-span but still v0); per-block
reload of the chain (each reload is a fresh SHORT LR -> grabs v0, and adds
~51 insns -> 81.3); full web-inline (67). The base wants a MEDIUM span
(held within each block across its 2 head-derefs, reloaded between blocks) —
a cost-model sweet spot no tested C spelling hits. This is a genuine
arg-register-targeting cap; the solver proves it's ONE permutation so the
permuter is the only remaining tool (and it floors — no regalloc randomizer).
ADDITIONAL DEAD END (2026-06-15): hoisting the base-ptr compute to BEFORE the
0x20×0x20 integrator loop (max span extension) REGRESSED 92.61->89.49 — the
extended span crosses the high-pressure loop and perturbs the loop-body
coloring instead of demoting the base ptr. "Span extension" only lowers
priority usefully when the extra span lands in LOW-pressure region; here every
direction is occupied. Confirms the cost-model-sweet-spot verdict.

SOLVER FIXES SHIPPED 2026-06-15 (two real rough edges found while wielding it):
1. The register histogram only matched `$reg` (splat) tokens, so a build `.s`
   from `objdump --no-show-raw-insn` (BARE regs, no `$`) read as all-zero —
   every delta was bogus (target +N, build 0). `SREG_RE` now matches `$?reg`
   and strips the objdump address column. ALWAYS sanity-check the histogram
   has nonzero BUILD counts before trusting the delta.
2. game_libs / relocatable-USO targets are raw `.word 0xXXXXXXXX` (splat can't
   disassemble them), so the target parsed as 1 "instruction". `_read_s_lines`
   now auto-detects a word-only `.s` and objdumps it as a big-endian blob — no
   manual `scripts/disasm-raw.py` step. Step 2/3 above now work with the raw
   `asm/nonmatchings/.../FUNC.s` directly for game_libs.
3. Added a `!! SIZE MISMATCH` banner: when target/build insn counts differ the
   renumber map is PARTLY diff-alignment noise — fix the count delta (extra
   spill/reload, missing block) before trusting the pairing histogram.

COHORT RESULTS (2026-06-15, solver applied to the "allocator-internal" near-100s):
- gl_func_0000C28C (99.83): streams are byte-IDENTICAL except ONE temp —
  `arg1->a` reload colors `$t8` (build) vs `$t9` (target). No emission-neutral
  C knob moves a single UNCOUPLED temp's register when the surrounding code is
  already identical: reordering the store before the struct copy (the only
  first-occurrence lever) reorders the EMITTED store too -> 95.6 regress. The
  build picks t8 because it's the lowest free reg post-copy; the target holds
  something extra in t8. Genuine tie-break cap.
- gl_func_00035834 (99.38): `r` (dispatch return, spilled across the 2nd call)
  colors `$v1` (build) vs `$a2` (target). Solver trace shows TWO constrained
  LRs: a param-home LR grabs a2 FIRST (higher priority), so r's reload LR gets
  v1 second. This is BELOW the global-coloring phase the solver models — it is
  the uopt split/needsplit adjsave-SIGN decision (target's no-call-path piece
  of r is COLORED into a2; ours is rejected -ve-save so ugen binds v1 at
  translate). Removing `(void)a0` (new solver hypothesis: drop the param LR's
  priority) was FLAT — the param home isn't driven by the cast. Solver-
  refinement signal: decode the pre-coloring split-rejection trace, not just
  the color order.
- gl_func_000578B4 (~94): huge (2419 insns), 92% shape-aligned but a massive
  coupled t6/t7/t8/t9 rotation (137+97+58+55+… renumber pairs) — same CLASS as
  1304C (one global coloring permutation across a div-hazard spill region), not
  a single swap. Permuter-class.
The pattern: the solver is excellent at LOCATING the mis-colored LR and proving
single-permutation vs structural, but for the residual near-100 cohort the
prescribed levers (priority/bitpos/span) are not emission-neutral — any C edit
that changes color order also changes emission order. The unsolved gap is a
lever that perturbs the interference/priority graph WITHOUT moving statements;
the trace's pre-coloring split phase (35834) is the most promising place to
extend the solver next.

## permuter-factory: unattended permuter queue-runner over the 90-99 long tail (2026-06-15)

`scripts/permuter-factory.py` (monorepo root) wraps the decomp-permuter into an
unattended queue-runner so the whole 90<=fuzzy<100 near-miss band can be ground
on all cores without babysitting. It encodes the 2026-06-11 permuter calibration
(see IDO_CODEGEN.md): import.py per-fn scratch is what unlocked the allocator
gates; the permuter's own score LIES vs objdiff fuzzy, so EVERYTHING is
objdiff-verified; single-diff gates fall ~250k iters while multi-diff structural
residuals descend fast then plateau and don't fall (the per-fn wall-clock budget
concedes those automatically).

**Run it from a fresh/clean worktree** (the build dirs and src tree it edits are
the worktree's; `scripts/spin-up-agent.sh 1080` makes one, or reuse a clean
`agent-<letter>` rebased onto main):

```bash
# Launch DETACHED (setsid) so it survives the agent harness reaping its
# background tasks (~hourly) — otherwise the launcher wrapper's SIGTERM stops it.
# The script handles SIGTERM cleanly (kills its worker group, reverts the
# in-flight fn, checkpoints) and a fresh launch RESUMES from the checkpoint,
# so even if it is killed you just relaunch and it skips everything done.
setsid nohup python3 /path/to/decomp/scripts/permuter-factory.py \
    --worktree "/path/to/decomp/projects/1080-agent-h" \
    --jobs 6 --budget-secs 1500 --sort fuzzy \
    > "/path/to/decomp/projects/1080-agent-h/.pf-run.log" 2>&1 &
# budget-secs 1500 ~= 225k iters at the observed ~150 iter/s on 150-350B fns;
# 480s (~60-95k iters) is TOO SHORT for a genuine single-diff gate to fall.
# --sort fuzzy puts the fewest-diff fns first (highest crack yield/min).
# optional: --total-budget-secs, --limit N, --only fn1,fn2, --min/--max band,
#           --no-commit, --no-rediscover, --retry-capped.
```

Per function the factory:
1. **discovers** the band from a fresh `objdiff-cli report generate` (after
   `make non_matching_objects`), size-sorted desc, EXCLUDING functions whose
   `#ifdef NON_MATCHING` wrap comment carries a cap concession ("cap stands",
   "permuter-class", "allocator-internal", "genuine cap", … — see `CAP_MARKERS`)
   and EXCLUDING functions with no `#ifdef NON_MATCHING` C body (import.py can't
   see a bare `INCLUDE_ASM`).
2. **imports** a fresh scratch: `import.py <src.c> <fn>.s 'CPPFLAGS=-I include -I src -DNON_MATCHING'`
   (the `.s` may keep its `nonmatching`/`endlabel` lines — import.py tolerates them).
3. **permutes** with a wall-clock cap, parsing `score = N` / `iteration N` from
   stdout, stopping early on a score-0 candidate.
4. **splices** the best `output-<score>-*/source.c` into the function's
   `#ifdef NON_MATCHING` body, rebuilds, and reads the function's fuzzy from a
   FRESH objdiff report. Keeps it only if objdiff improved; reverts otherwise
   (and rebuilds clean). A verified 100.0 is committed
   `<fn> permuter-factory crack to 100.0 (NM body, pending land)` — it does NOT
   land or push (that's the main session's job, with the full-ROM cmp gate from
   the 2026-06-11 notes: D_/extern (&D+const) inlines can objdiff-100 but
   link to the wrong address).

State lives in `<worktree>/.permuter-factory/`: `progress.log` (timeline),
`checkpoint.json` (per-fn status, so a re-run resumes / skips done), and
`scoreboard.json` (running tally attempted/cracked/improved/capped/errored).
Crash-robust: per-fn try/except, atomic checkpoint writes. Children are killed by
process-group PID (`start_new_session=True` + `killpg`), NEVER `pkill -f` — that
would match the factory's own argv (see the pkill memo).

GOTCHAS baked in: the splice targets the `#ifdef NON_MATCHING` … `#else` region
only (regex-locates the def after the ifdef, replaces up to `#else`); if the
permuter's pruned source.c references symbols the full TU lacks, the verify build
fails and the function is reverted+counted errored (not silently left broken).
Functions where objdiff doesn't improve are tallied as "new caps" — but trust
that only as a permuter verdict per the staleness rule, not a permanent cap.

### Band-yield calibration (2026-06-18, ~10-batch run over the sub-90 tail)

Empirical yield by starting-fuzzy band (`--min`/`--max`, sub-90 = the never-run
zone below the original `--min 90` factory pass; budget ~130s/fn, jobs 6):
- **86–90%**: BEST yield. ~2-3 NM improvements per 8-fn batch (e.g. +3-13pp,
  several reaching 96-98%). Most fixable diffs are few and the permuter lands
  big jumps. Focus here.
- **80–86%**: marginal. ~1 improvement per batch, rising verify-fail rate.
- **<84%**: UNPRODUCTIVE — mostly `verify build/objdiff FAILED -> reverting`
  (the permuter's pruned-source mutations don't even pass isolated verify;
  these functions are too multi-diff). One 84-86 batch returned 0 improved /
  3 errored. Don't spend batches below ~84.
WORKFLOW WASTE: with `--no-commit`, verify-FAILED functions are NOT checkpointed
as done, so they RE-RUN every batch (gl_func_000355A0 / 0002A904 / 0003F7A8 each
burned ~2min/batch across 3+ batches). Either pass an explicit `--only` fresh
list, or add a cap-comment to chronic verify-failers so the cap-filter skips them.
LAND YIELD: of the isolated "VERIFIED 100.0" cracks this run, ~1/3 held in the
matching in-tree build (titproc_uso_func_00000418 landed; gl_func_00048354 +
func_00002088 were isolated false-100s, see MATCHING_WORKFLOW "permuter false-100
#2"). ALWAYS matching-build-verify before landing. NM improvements (<100) are
pure decode-progress — they add 0 to decomp.dev matched_code (binary metric).

<a id="feedback-discover-has-source-misleading"></a>
## `discover --sort-by size` marks every INCLUDE_ASM placeholder as `[has source]` — write a sub-filter for genuinely-unstarted candidates

_Discover treats any mention of a symbol in `src/` as "has source", including bare `INCLUDE_ASM(...)` lines. For source-3 picks (small unstarted), use a Python filter that checks for an actual C function definition (`(void|int|...) name(...)` syntax), not just the symbol name._

**Symptom (verified 2026-05-08 on 1080):** Running `uv run decomp discover --sort-by size` and walking the head of the list — `__osSetFpcCsr` (libreultra `.s`, skip), `func_80009EA0` (`.rodata`, skip), `func_800073DC` (cap-confirmed fragment), `func_0000E9FC` (NM-86 cap-confirmed), `mgrproc_uso_func_000032F8` (reloc-encoding cap-confirmed) — produces zero genuinely-fresh candidates among the smallest 9 entries even though all are tagged `[has source]`. The "[has source]" tag is true (each appears in `src/`), but the content is just `INCLUDE_ASM("...", funcname);`, not a decompiled body.

**Sub-filter recipe:**
```python
# In project root. Walks asm/nonmatchings/, filters out functions whose
# only mention in src/ is an INCLUDE_ASM line. Keeps small candidates.
import os, re, subprocess
for root, _, files in os.walk('asm/nonmatchings'):
    for f in files:
        if not f.endswith('.s'): continue
        with open(os.path.join(root, f)) as fp:
            line1 = fp.readline()
        m = re.match(r'nonmatching\s+(\S+),\s+0x([0-9A-Fa-f]+)', line1)
        if not m: continue
        name, size = m.group(1), int(m.group(2), 16)
        if size > 0x60: continue
        r = subprocess.run(['grep', '-rln', name, 'src/'],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(f'TRULY-UNSTARTED size={size} {name}'); continue
        # Has source — but is it a real C body?
        has_body = False
        for src in r.stdout.strip().split('\n'):
            with open(src) as sf: txt = sf.read()
            if re.search(r'\b(void|int|char|float|s32|u32|s8|u8|short)\s*\*?\s*'
                         + re.escape(name) + r'\s*\(', txt):
                has_body = True; break
        if not has_body:
            print(f'INCLUDE_ASM-only size={size} {name}')
```

**Why the gap:** Splat emits `INCLUDE_ASM(...)` lines for every disassembled function in the parent `.c` file at project setup, so EVERY function reads as `[has source]` from day 0. Discover's `[has source]` flag was designed to suppress trivial duplicates, not to mean "decompiled C exists" — but read naively it suggests prior work has already happened and biases away from these candidates.

**How to apply:**
- For source-3 picks (random-roll): run the sub-filter to find genuinely-unstarted small candidates (e.g. 8-byte save-arg sentinels, save-arg-+-return-1 stubs, `func_00000000` 1-call wrappers).
- The sub-filter is also useful for source-4 (untouched USOs): scan an entire USO segment in one pass for INCLUDE_ASM-only entries before deciding it's "exhausted" of small targets.
- Discover's tag remains correct for filtering parallel-agent-collisions (don't pick a function someone else is mid-decomp on) — the tag covers more, not less, than true "has body".

**Two further false-positive classes the sub-filter still misses (verified 2026-05-08 on 1080 kernel):**

1. **Symbol absorbed by larger-predecessor INCLUDE_ASM.** When splat emits multiple `.s` files for what's actually one function (e.g. `func_80008E08.s`, `func_80008E38.s` — both inside the predecessor `func_80008DF0`'s 0xA8-byte symbol that ends at 0x80008E98), only the LARGEST .s gets an INCLUDE_ASM line; the absorbed siblings have NO mention in `src/` at all. The sub-filter's `grep -rln name src/` returns empty, flagging them as "TRULY-UNSTARTED" — but their bytes are emitted via the predecessor's INCLUDE_ASM, and there's no work to do. To detect: check `undefined_syms_auto.txt` for an entry like `func_X = 0xX;` AND grep for the function in NEARBY `.s` files for the size-larger predecessor whose declared `nonmatching SIZE` covers the absorbed offset. If covered, skip — splat cruft, not work.

2. **Cap-doc'd structurally-uncapable functions wrapped under `_unreachable` stub names.** Functions documented as standalone-uncompilable (chained-suffix register inheritance, prologue-stolen-successor with too-deep predecessor tail, etc.) are sometimes wrapped as `extern void <func>_unreachable(...)` inside `#if 0 ... #endif` instead of the standard `#ifdef NON_MATCHING / #else INCLUDE_ASM`. The sub-filter's regex `(void|int|...) name(...)` doesn't match `name_unreachable(...)`, so these flag as INCLUDE_ASM-only. To detect: also grep for `<funcname>_unreachable` (or `<funcname>_alt`, etc.) and any `#if 0` block referencing the function name in its trailing comment. If present, skip — already cap-doc'd.

3. **Asm orphan post-merge** — `merge-fragments` consolidated bytes into the predecessor and re-exported the absorbed symbol via `undefined_syms_auto.txt`, but the absorbed `.s` file was left on disk. The asm file is unreferenced from any INCLUDE_ASM (no `INCLUDE_ASM(... funcname);` anywhere in `src/`), the symbol IS declared `extern` from one or more callers, and `undefined_syms_auto.txt` has a `funcname = 0xADDR;` line for it. Discover and the sub-filter both surface it as INCLUDE_ASM-only because the `extern` declarations satisfy "src mentions" but no real C body matches the regex. Real work was done (the merge); the asm file is just cleanup debris. Distinct from class 1 — class 1 is splat-cruft never-touched; class 3 is post-merge cleanup left undone. **To detect**: a one-liner — `grep -L 'INCLUDE_ASM.*funcname' src/**/*.c | wc -l` and `grep -c '^funcname' undefined_syms_auto.txt`; if no INCLUDE_ASM and undefined_syms_auto has the entry, the `.s` file is the orphan. **Action**: delete the `.s` file; build is unaffected (bytes come from the predecessor's INCLUDE_ASM, symbol resolution comes from undefined_syms_auto). Splat re-runs will re-emit it, so `git checkout --` revert any re-emission per the splat-rerun-gotchas note. Verified 2026-05-08 on `func_80009C30` (was absorbed into `func_80009B60`'s 0xE0-byte body).

All three classes consume tick budget if not pre-filtered. Adding `'has_unreachable_stub'` and `'absorbed_by_predecessor'` checks to the Python sub-filter would surface only fresh candidates. Untracked TODO; for now, when source-3 yields a fishy candidate (4-insn shared-tail epilogue, fragment lacking jr ra, `lui+addiu+...` setup-only body), skim adjacent `.s` files and `src/`'s nearby comments before grinding.

---

<a id="feedback-decomp-call-graph-priority"></a>
## Decomp prioritization — call-graph DFS from entry point beats by-segment-size mass-match

_When a project has a clear entry point (USO loader → main loop → per-frame update), depth-first decomp from there reveals the actually-used code and naturally drives type discovery. Mass-matching the largest segment first produces matched-but-disconnected wrappers that don't tell you anything._

**Rule:** When working a decomp project where the strategic goal is understanding (port, modding, deep analysis) — not just match-percentage — pick the next function by **traversing the call graph from a known entry point**, not by "biggest segment with most unmatched functions."

**Why call-graph DFS wins:**

1. **Reveals what code actually matters.** Many functions in middleware segments (e.g. 1080's game_libs, papermario's libgcc helpers) are linked-but-never-called dead utilities. Following the call graph from `main` skips those.
2. **Drives type discovery in the right order.** Each function call tells you the callee's parameter types. Each struct access tells you the struct's shape. By the time you've decompiled 50 reachable functions, you've SEEN the engine-state struct fields enough to type it.
3. **Builds a coherent narrative.** "Per-frame update calls physics calls collision detection" is something you can explain. "I matched 200 chain wrappers in game_libs" isn't.
4. **Type-just-in-time becomes natural.** When the 5th function accesses `gl_ref_00021CBC[3]`, you know it's the engine state's frame counter, and you can type it.

**Anti-pattern (and what we caught ourselves doing on 1080 in agent-d's session 2026-04-19):**

Mass-matching game_libs because it's the biggest segment with the most easy wins. We matched ~200 wrapper functions. They're matched, episode-logged, training data. But they don't tell us how snowboarding physics works, what the Player struct looks like, or how the renderer is structured. They're matched-but-meaningless coverage.

**How to apply:**

1. **Find the entry point.** For relocatable USO games like 1080, this is the first function in the main game USO's text section.
2. **Read its callees.** Each `jal` is a child node.
3. **For each child:** if same USO, decompile next. If cross-USO (e.g. `jal gl_func_00000000`), pull the right game_libs function.
4. **Decompile depth-first.** A leaf function is one that only calls libultra primitives or has no calls.
5. **Type structs as they reveal themselves.** Wait until 5+ accesses to triangulate the field, then refactor retroactively.
6. **Mass-match the rest as background.** Once the spine is done, the remaining wrappers are throughput work that doesn't block understanding.

**When mass-match IS the right move:**

- Pure training-data goal (`decomp/` repo's primary mission).
- Idle agent capacity that would otherwise waste cycles.
- Boundary cleanup before a complex segment.
- When a wrapper family is so large (50+ functions, all the same shape) that pattern-matching it once unlocks all of them in 30 minutes.

**Trigger to re-evaluate priority:** if you've matched 50 functions in a row that don't change your mental model of the game, you're mass-matching when you should be call-graph-DFS-ing.

**Origin:** 2026-04-19 1080 Snowboarding strategic conversation. After splatting all USOs (14 segments, ~1750 functions accessible), the question of "what to decompile next" surfaced the realization that defaulting to game_libs's biggest-segment status was wrong. The user explicitly wants 100% decomp ending in a clean PC-portable codebase — call-graph DFS from game.uso's entry better serves that goal than "match the most functions per day."

---

---

<a id="feedback-expected-must-be-committed-for-decomp-dev"></a>
## CI / decomp.dev compares fresh build/.o vs committed expected/.o — `make expected` results MUST be git-committed for changes to show on the dashboard

_The land script and `scripts/refresh-report.sh` do NOT run `make expected`. CI checks out the repo, builds fresh `build/.o`, then runs `objdiff-cli report` which compares against the COMMITTED `expected/.o` files. If the committed `expected/` is stale (older than the source changes), CI scores the new build against the old baseline and the % shown on decomp.dev is wrong/stale._

**Rule:** Whenever a function's `.o` BYTES change (decompile, NM-wrap, pragma addition, etc.), `expected/<file>.c.o` must be regenerated AND COMMITTED. Otherwise CI / decomp.dev shows the wrong %.

**Why this matters:**

- The local workflow runs `make expected` after a successful match → local `report.json` shows correct %. ✓
- The land script (`scripts/land-successful-decomp.sh`) regenerates `report.json` locally but does NOT touch `expected/`. ✗
- CI does NOT run `make expected` either — it reuses whatever's committed. ✗
- decomp.dev fetches the CI artifact `us_report` (= `report.json`), so it shows whatever CI computed. ✗

**Symptom:** local says 5.08 % matched, decomp.dev says 5.01 %. The 0.07 % gap = N functions whose source changed but whose `expected/.o` wasn't refreshed in the same commit.

**How to apply:**

After ANY change that affects compiled output (decomp, NM wrap, GLOBAL_ASM pragma add, asm-processor directive, OPT_FLAGS override):

1. `make RUN_CC_CHECK=0` — produces `build/<file>.c.o`
2. `make expected RUN_CC_CHECK=0` — copies `build/.o` → `expected/.o`
3. `git add expected/src/<file>.c.o` — STAGE the refreshed baseline
4. Commit BOTH the source change AND the expected refresh in the same commit (or as paired commits).
5. Push.

**The land script handles this automatically as of commit 24e6443 (2026-04-20).** After validating the named functions match exact, it runs `make expected RUN_CC_CHECK=0` and creates a follow-up commit ("Refresh expected/ baseline for <func> land") if any `expected/.o` files changed. Agents using `scripts/land-successful-decomp.sh` no longer need to remember step 2-4 above.

**For sweeping changes (e.g., trim-trailing-nops rollout):** ALWAYS commit the fresh `expected/` after the source-change commit. 22 expected/.o files were stale after the pad-sidecar rollout because I forgot this — committing them bumped the CI / decomp.dev % from 5.01 % → expected ~5.08 %.

**Edge case:** `expected/` files are binary blobs. `git diff --stat` shows them as 0 lines but Bin XXX -> YYY bytes. They're NOT compressible by .gitignore (`*.o` would gitignore them — they're force-tracked despite the pattern).

---

---

<a id="feedback-ghidra-struct-annotation-doesnt-auto-propagate"></a>
## Ghidra struct annotation does NOT auto-propagate across xrefs — each function in a family needs its own prototype set

_Validated 2026-05-04 on 1080's rmon family. Setting `RmonMsg *msg` on func_80006D0C makes its decomp use `msg->type / msg->id / msg->domain`. Sibling func_80006C64 (also takes RmonMsg per source) keeps showing `*(int*)(param_1+0xc)` until it's individually annotated. Batch-script the family to apply prototypes wholesale._

**The good news**: setting a function prototype + parameter type in Ghidra DOES change decomp output exactly as expected — `*(byte*)(param_1+4)` becomes `msg->type` etc. Validated end-to-end via direct pyghidra (bypassing pyghidra-mcp's MCP layer, which had separate hangs).

**The mediocre news**: this requires Ghidra's `Function.updateFunction()` with a fully-built signature (return type + parameter list) and `SourceType.USER_DEFINED`. The MCP server's `set_function_prototype` tool wraps this, but pyghidra-mcp had a hung-call bug in our session. Direct pyghidra worked first try.

**The annoying news**: type info **does not propagate across xrefs automatically**. If you annotate `func_80006D0C(RmonMsg *msg)`, callers and same-prototype siblings stay untyped. Each function in a family needs its own prototype set.

**Workflow recipe (1080 / rmon as the example):**

1. Find the family via `list_xrefs` to a known shared callee (e.g. `__rmonSendHeader` = FUN_000073f8 in our project — 27 rmon callers in one query).
2. Define the struct ONCE in the data type manager (Ghidra's data type categories are project-global).
3. Loop over the family, calling `func.updateFunction(...)` with the prototype.

Sketch:
```python
from java.util import ArrayList
from ghidra.program.model.listing import ParameterImpl, ReturnParameterImpl
from ghidra.program.model.listing.Function import FunctionUpdateType
from ghidra.program.model.symbol import SourceType
from ghidra.program.model.data import IntegerDataType

# Inside a transaction:
RMON_FAMILY = ["func_80006C64", "func_80006D0C", "func_80006BD8", ...]
for name in RMON_FAMILY:
    f = ... # lookup function
    params = ArrayList()
    params.add(ParameterImpl("msg", rmon_msg_ptr, program))
    f.updateFunction(
        None,                                            # keep calling convention
        ReturnParameterImpl(IntegerDataType.dataType, program),
        params,
        FunctionUpdateType.DYNAMIC_STORAGE_FORMAL_PARAMS,
        True,                                            # force override
        SourceType.USER_DEFINED,
    )
```

Cost is one transaction per N functions — fast even for 30+ at once.

**Where the value still wins big**:
- Define struct once → applies to all N functions you annotate (vs m2c which has no project-level type memory).
- Field-name decomp is far easier to read than `*(byte*)(param_1+0x9)`.
- Cross-function consistency: if two functions both access `msg->domain`, you SEE that they do, by name. Easier to spot family patterns.

**Where it doesn't help**:
- "Annotate one function, see types everywhere" — no, doesn't work that way. Plan to batch-annotate.
- m2c-style codegen-fidelity for IDO matching — Ghidra's GCC-flavored output won't byte-match. Use Ghidra for *understanding*, m2c for *codegen*.

**Concrete in 1080**: see `scripts/ghidra-annotate-rmon.py` (committed) for a working example. Scales by adding to the family list.

---

---

<a id="feedback-permuter-cracks-small-load-order"></a>
## Permuter DOES crack small (low-score) load-order / instruction-scheduling residuals — try it on 1-3 diff scheduling near-misses before giving up

_Counter to the "permuter only floors" instinct: for a SMALL near-miss (base score ~20, 2 raw diffs) that's a pure instruction-SCHEDULING residual — not an $s-reg renumber — the permuter finds the fix fast. Verified 2026-05-28 `game_libs_func_00066440` (circular-dlist remove-self): the unlink's `next->prev = prev` loaded `a0->0` before `a0->4` in the target, and ~10 hand-written C variants couldn't flip that load order. Permuter cracked it at iteration 18 (~30s) — the winning mutation combined the two self-link stores into `a0[0] = (a0[1] = (int)a0)`, a shape change that shifted IDO's tail scheduling enough to flip the earlier load order (a non-obvious global effect no human would guess). Lesson: when a merge/decode lands at 1-3 diffs and the diffs are operand/load ORDER (same opcodes, same regs, reordered) rather than $s-reg renumber, run the permuter with `--stop-on-zero` — it's the right tool and it's fast here. Import recipe: clean target `.s` (just `glabel <fn>` + `.word` lines, no `nonmatching`/`endlabel`), then `C_INCLUDE_PATH=include python3 tools/decomp-permuter/import.py src/<seg>/<file>.c <clean.s> CPPFLAGS=-DNON_MATCHING` (C_INCLUDE_PATH lets cpp find common.h; equivalently pass `CPPFLAGS=-I include -I src -DNON_MATCHING`), then `permuter.py nonmatchings/<fn> --stop-on-zero -j2`. Distinct from [the ≥1000 structural-cap note below](#feedback-permuter-1000-plus-structural): that's about HIGH scores / $s-reg renumber where it floors; THIS is low-score scheduling where it wins._

**Calibration (2026-05-28, five cases tested) — what the permuter CRACKS vs FLOORS even at a LOW base score:**
- CRACKS: pure instruction/load SCHEDULING reorder (same opcodes+regs, only the emit *order* differs). `game_libs_func_00066440` 20→0.
- FLOORS (don't burn time): (1) **commutative operand-order** — FPU `mul.s`/`add.s` operand swap where a value is pinned by ABI (`$f0` call-return), `gl_func_00052104` 15→5; AND integer `beq`/`bnel` operand-order ($s-first vs $t-first emit normalization), `uso_skip_to_end` 20→10. (2) **register PLACEMENT** — value in `$v1`+`move v0,v1` vs direct `$v0`, `game_libs_func_0002831C` floored ~60. (3) **branch-likely LAYOUT** — `beqzl`-to-end arm placement, `game_libs_func_0005330C` floored ≥885. (4) **preheader loop-invariant-address-setup ordering** — the N `lui+addiu` that materialize loop-invariant pointers in the preheader, emitted in ascending- vs descending-reg order. LOOKS like a crackable scheduling reorder (same opcodes/regs, only order differs) but ISN'T: it's a deterministic IDO loop-hoist/preheader-schedule choice, not perturbed by C mutations. `gl_func_00033B6C` (4 pointer-setup addiu, s0..s3 vs s3..s0) floored at base 85 over ~28k iters (2026-05-29). Rule of thumb: if the 2 diffs are a *reorder of when instructions are emitted* WITHIN the function body, permute; if they're *which register/operand-slot holds a value*, *which arm is laid out where*, OR *the order of preheader loop-invariant address setup*, it's a structural cap — leave NM/INCLUDE_ASM.

<a id="feedback-permuter-1000-plus-structural"></a>
## Permuter scores ≥1000 genuinely mean "structural issue, no match possible" — stop grinding

_Ran decomp-permuter random mode for ~3 minutes on `n64proc_uso_func_00000014` (12k+ iterations). Best score 1030. Per the skill's score-band rubric, 1000+ is "structural issues remain" — and indeed the winning variant only hoisted a `base+0x40` expression into a named local, didn't change any $s-reg assignments. For reg-renumber issues specifically (where target has $s0=X but mine has $s0=Y despite identical logic), random-mode permuter won't crack it; only compiler-version differences or manual `register T x asm("$N")` can — and IDO rejects the latter._

**Origin (2026-04-21, n64proc_uso_func_00000014):**

Setup:
- Function had known 4-way $s-reg renumber mismatch (target s0=cur/s1=flag/s2=one/s3=base/s4=base10/s5=arg0, mine s0/s1/s2=base/s3=one/s4=arg0/s5=base10).
- Already documented as weight-driven in `feedback_ido_sreg_order_not_decl_driven.md` — decl order doesn't flip, literal 1s regress.

Permuter run:
```bash
python3 /home/dan/Documents/code/decomp/tools/decomp-permuter/import.py \
    src/n64proc_uso/n64proc_uso.c \
    asm/nonmatchings/n64proc_uso/n64proc_uso/n64proc_uso_func_00000014.s PERMUTER=1
python3 /home/dan/Documents/code/decomp/tools/decomp-permuter/permuter.py \
    nonmatchings/n64proc_uso_func_00000014 -j4
```
3 minutes, ~12k iterations. Best score: 1030. Dozens of `output-1030-N`, `output-1040-N`, `output-1080-N`, etc. saved.

Best output (score 1030) just added:
```c
int *new_var;                                    /* new local */
new_var = (int *) (((char *) base) + 0x40);      /* hoisted expr */
...
arg1 = *new_var;                                 /* use it */
```
Zero register-renumber changes. The permuter's randomization space didn't include anything that flipped the $s-allocator's weight calculation to match the target.

**Lesson:** for register-renumber-only diffs at the $s-reg level, random-mode permuter is ineffective. The allocator's weight formula is deterministic on the IR, and random C perturbations (hoisting, splitting, renaming) don't change the formula's output ORDER — they just shuffle which expressions exist. You need to change REF COUNTS materially, which is hard to do via random mutations.

**When to skip permuter on an NM wrap:**
- Existing comment notes "register renumber" or "$s-reg swap" as the remaining diff
- Existing comment notes "$a-class register pick" (e.g. target uses $a3, mine uses $a1) — 2026-04-21 update: these also don't crack. Ran permuter on `gl_func_0000D9B8` (base score 20, just 2 $a1/$a3 diff insns). Permuter ran 1000+ iterations, best stayed at 20. Even "close" scores (20 vs 1030) don't mean permuter can close them — reg-class picks are deterministic on IDO's side.
- **$t-class renumber also resists in practice (2026-05-28).** Despite the "$t-class CAN sometimes crack" note above, a concrete test on `gl_func_0000C28C` (59-insn struct-copy + dispatch; 2-insn diff = `lw/sw $t8` mine vs `$t9` target on the `arg0[4]=arg1->a` store) ran ~230s across 8 threads (`--stop-on-zero -j 8`) and never beat **base score 50** — the shape-changing mutation it found (splitting the store into `new_var = arg1->a; arg0[4] = new_var;`) scored an identical 50. The "2 episodes" of $t-renumber cracks were record-append/pointer-arith shapes with a genuinely different ALLOCNO COUNT achievable from C; a plain mid-function $t8↔$t9 swap on an otherwise-fixed shape is NOT reachable. Triage adjacent-$t renumbers as caps unless the diff is in heavy pointer-arith where ref-count can be materially changed.
- Prior passes already tried decl reordering + literal folding
- The skill's band rubric "1000+ structural" applies

When to TRY permuter:
- Remaining diff is 1-3 instructions in leaf-function **scheduling** (operand position in the stream, not register choice)
- Operand swaps on commutative ops (addu, or, and)
- Branch-likely conversion patterns
- Score likely 100-500 band AND the diff isn't a register-pick

**Key distinction:** permuter can flip instruction ORDER but not register ASSIGNMENT. If the target and mine differ only in "what register holds this value" (regardless of $s/$a/$t class), random-mode permuter cannot reach the target — the allocator's decision is deterministic given the RTL shape, and permuter's random C mutations usually preserve the shape enough that the allocator makes the same choice.

**Cost:** ~3 min + a few MB of output variants in `nonmatchings/<func>/`. Always clean up with `rm -rf nonmatchings/` after.

<a id="feedback-permuter-score-0-sp-offset-false-positive"></a>
### Permuter "score 0" is a FALSE POSITIVE for pure spill-slot (sp-offset) swaps — raw-byte-verify before logging an episode

**The permuter's asm scorer normalizes sp-relative offsets**, so two builds that differ ONLY in which stack slot a spilled value lands in score as identical (0) even though the **emitted bytes differ** (the `swc1`/`lwc1` immediate encodes the offset). A permuter "score 0" therefore does NOT prove a byte match — it proves a match modulo stack-slot assignment. **Always confirm with a raw byte-compare before logging an episode:**

```bash
mips-linux-gnu-objcopy -O binary --only-section=.text built.o built.bin
mips-linux-gnu-objcopy -O binary --only-section=.text target.o target.bin
cmp built.bin target.bin   # silent = real match; "differ" = NOT a match
```

**Worked example (2026-05-24, gl_func_0005D054 — quaternion/Hamilton product, reloc-free -O2, 56 insns).** Deterministic decode reached a *single* logical diff: all 16 `mul.s` (with the `a1[c]*a0[c]` operand order on each last-subtracted term), every `add.s`/`sub.s`, store order `a2[0,1,2,3]`, and the full schedule matched — but GCC assigned `x`'s spill slot to `40(sp)` and `z`'s to `32(sp)` where the target has them reversed (`x→32, z→40`). The permuter reported `base score = 0` and exited on `--stop-on-zero`; `cmp` of the .text still differed at the two `swc1` + one `lwc1`. **This is an honest cap, not an episode.**

**Why the slot pair won't flip from C:** spill slots are assigned in pseudo-regno order (`assign_stack_local` walks pseudos by number; first → lowest offset). The x↔z pair did NOT flip under any tried C structure — store-order permutations (only `a2[0,1,2,3]` keeps the w-store scheduling correct; others regress), declaration-order permutations (disturb the whole schedule → far worse), fully-inlined stores (62 diffs), `*a2++` pointer-postinc (8), temp copies (`float xx=x;`), and extra refs (`a2[2]=z` twice). It's a frame-layout artifact the IDO frontend's RTL doesn't expose to source-level control. Class: **spill-slot-assignment cap** — leave `#ifdef NON_MATCHING`. (Distinct from the $t-renumber class below, which the permuter CAN sometimes crack via shape mutation.)

**REFINEMENT 2026-05-23 — the permuter CAN crack SOME register-renumber near-misses (the "can't" above is for $s-reg/$a-class picks).** The blanket "permuter flips ORDER not ASSIGNMENT" holds for $s-reg priority and $a-class arg-reg picks (deterministic). But for **record-append / pointer-arithmetic functions with $t-class temp renumber** (same opcodes/order, only $t-numbering differs, e.g. 20/25–20/29 diffs, too pervasive for INSN_PATCH), the permuter DOES find SHAPE-CHANGING C variants that flip the $t allocation to match — because it mutates the RTL shape (not just hoisting). Winning mutations it found: route an address through an `int new_var = base + idx*8; arr = (int*)new_var;` intermediate, and reuse one local (`idx`) as both pointer-int and count. Cracked `game_libs_func_0005769C` (25 insns) and `_00057628` (29, masking) → byte-exact episodes, 2026-05-23. Use `-j6`, ~**280s** (180s only reached score 15 on the masking one; it needed the longer run). **Still resistant** (don't waste runs): loops (best score got WORSE — 20E78 125), delay-slot scheduling (2A9F0 55), cursor-vs-offset fold (1D17C 280), unfilled-jr-delay (571E4 35), arg-home spill. So: TRY the permuter on straight-line record-append/pointer-arith $t-renumber near-misses; SKIP loops / delay-slot / cursor / unfilled-delay / $s-$a-class. **Sub-refinement 2026-05-23 — record-append + RIGID HEAD also resists.** `game_libs_func_0005703C` (50 insns) is a flag-decode bit-test chain (`sll tN, v1, K; bgez tN, skip; ori v0,...` — high single-bit masks that don't fit `andi`'s 16-bit immediate, forced via `((unsigned)v1 << K) >> 31` per IDO_CODEGEN#feedback-ido-bit-N-test-via-sll-bgezl) FOLLOWED BY two record-appends. Structurally 100% exact (all opcodes/immediates/branch-offsets match; only 30/50 $t fields differ), reloc-free. Permuter -j6 285s got down to score-50 but NOT 0: it shape-mutates the record-append TAIL's $t-alloc, but the head's bit-test-chain $t numbering is rigid (each `>>31` test's pseudo creation order is fixed; tail mutations don't reach it). So the crackable class is PURE record-append; a record-append preceded by a non-trivial computed head (bit-test chain, arithmetic) keeps the head's $t-renumber and stays NM. Don't re-run the permuter on record-appends with a substantial head. **Sub-refinement 2026-05-23 — FP↔int register interplay also resists, even straight-line.** `game_libs_func_00029934` (17 insns, reloc-free, NO loop: `lwc1; trunc.w.s; mfc1; addu; srl+andi; table lh; sra/sll/sra`) — structurally exact, ~10 $t-renumber driven by the float-to-int (`trunc.w.s`/`mfc1`) result competing with the two int loads for registers. Permuter -j6 240s → best 45, not 0. The crackable class is pure-INTEGER record-append/pointer-arith; when the renumber is driven by FP→int reg interplay (mfc1 result + int loads), the permuter's int-shape mutations don't reach the FP-side allocation. SKIP the permuter on FP-flavored straight-line $t-renumber too. Also tiny (≤~8-insn) leaves resist for lack of mutation surface (27504 6-insn → best 2/6 only via an ugly mask-chain not worth episoding).

---

---

<a id="feedback-pyghidra-mcp-setup-for-n64-decomp"></a>
## pyghidra-mcp setup notes for N64 decomp work — JDK 21, raw-binary load, MIPS:BE:32:default, ~7-min auto-analysis

_pyghidra-mcp install gotchas verified 2026-05-04. Needs Ghidra 12.x + JDK 21 (NOT JDK 17). N64 ROMs need raw-binary load with explicit language="MIPS:BE:32:default" + loader="ghidra.app.util.opinion.BinaryLoader". Auto-analysis on 16 MB 1080 baserom takes ~7 min (one-time). Re-opening cached project: ~5 sec. pyghidra-mcp is a `uv tool` install — scripts must use ~/.local/share/uv/tools/pyghidra-mcp/bin/python, not the system python._

**Install (sudoless):**

```bash
# 1. pyghidra-mcp via uv (separate tool venv)
uv tool install pyghidra-mcp

# 2. Adoptium portable JDK 21 — Ghidra 12.x rejects JDK 17
mkdir -p /tmp/ghidra-spike && cd /tmp/ghidra-spike
curl -sL https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.5%2B11/OpenJDK21U-jdk_x64_linux_hotspot_21.0.5_11.tar.gz -o jdk21.tar.gz
tar xzf jdk21.tar.gz

# 3. Ghidra 12 (latest from GitHub releases)
GHIDRA_URL=$(curl -s https://api.github.com/repos/NationalSecurityAgency/ghidra/releases/latest | python3 -c "import json,sys; d=json.load(sys.stdin); print([a['browser_download_url'] for a in d['assets'] if 'PUBLIC' in a['name'] and a['name'].endswith('.zip')][0])")
curl -sL "$GHIDRA_URL" -o ghidra.zip && unzip -q ghidra.zip

# 4. Env vars (need on every shell)
export JAVA_HOME=/tmp/ghidra-spike/jdk-21.0.5+11
export PATH=$JAVA_HOME/bin:$PATH
export GHIDRA_INSTALL_DIR=/tmp/ghidra-spike/ghidra_12.0.4_PUBLIC
```

**N64 baserom load (the right magic):**

```python
import pyghidra
pyghidra.start()
from pyghidra import open_program

# IMPORTANT: don't use loader="BinaryLoader" — Ghidra needs the FQN
# IMPORTANT: language is "MIPS:BE:32:default", NOT "MIPS:BE:32:R3000"
# IMPORTANT: VR4300 is N64's CPU but Ghidra has no specific VR4300 lang ID;
#            "default" is the closest. The relevant Ghidra MIPS variants:
#            MIPS:BE:32:default, MIPS:BE:32:R6, MIPS:BE:32:micro,
#            MIPS:BE:64:default, MIPS:BE:64:micro, MIPS:BE:64:R6,
#            MIPS:BE:64:64-32addr (for embedded 32-bit-pointers-on-64-bit-CPU)

with open_program(
    rom_path,
    project_location=cache_dir,
    project_name="my_project",
    analyze=True,                          # ~7 min on 16 MB ROM, one-time
    language="MIPS:BE:32:default",
    loader="ghidra.app.util.opinion.BinaryLoader",
) as flat_api:
    program = flat_api.getCurrentProgram()
    ...
```

**Re-opening cached project (no re-analysis):**

```python
with open_program(rom_path, project_location=cache_dir, project_name="my_project",
                  analyze=False, language="MIPS:BE:32:default",
                  loader="ghidra.app.util.opinion.BinaryLoader") as flat_api:
    ...  # ~5 seconds
```

**Running scripts via pyghidra:**

`pyghidra-mcp` was installed via `uv tool install`, so its venv lives at `~/.local/share/uv/tools/pyghidra-mcp/`. Scripts that import `pyghidra` MUST use that interpreter:

```bash
~/.local/share/uv/tools/pyghidra-mcp/bin/python script.py
```

`python3 script.py` will fail with `ModuleNotFoundError: No module named 'pyghidra'`.

**Two-stage analysis (pyghidra-mcp's quirk):**

There are TWO analysis passes that happen, NOT one:

1. **Ghidra auto-analysis** (~7 min) — runs once on a fresh `.gpr` project, populates the function manager with detected functions. Triggered by `setup-ghidra.py` in our setup. Persistent in the project file.

2. **pyghidra-mcp's own indexing** (~3-5 min on top of #1) — builds a chromadb vector index for symbol search + verifies analysis is complete. Runs every time pyghidra-mcp starts. The first run takes longer (creating chromadb collection); subsequent runs are faster (chromadb cached at `<project>/<name>-pyghidra-mcp/chromadb/`).

The MCP server's flag `--wait-for-analysis` tells it to block on its own indexing pass before responding to tool calls. Without it, tool calls return `"Analysis incomplete for binary 'baserom.z64'. Wait and try tool call again."` — clients then need to retry.

**Use `--wait-for-analysis` in `.mcp.json`** so client code doesn't have to retry. The cost is the server takes 3-5 min to start the first time after a fresh `setup-ghidra.py` run.

**Pass `--project-path` as the .gpr file path, NOT the directory.**

```json
"args": [
  "--transport", "stdio",
  "--project-path", "/path/to/build/ghidra-project/tenshoe.gpr",
  "--wait-for-analysis"
]
```

If you pass `--project-path /path/to/build/ghidra-project --project-name tenshoe`, pyghidra-mcp will CREATE A SECOND empty project at `<path>/<name>/<name>.gpr` instead of opening yours. (Their docs say project-path accepts either a dir or a .gpr; for our use-case .gpr is correct.)

**`open_program` is deprecated and doesn't persist** — use `open_project` + `program_loader().loaders(BinaryLoader)` (singular `.loaders()` takes a Java Class, NOT a list) + explicit `loaded.save(monitor)` + `loaded.release(None)`. Then run analysis via `program_context(project, "/baserom.z64")` block + explicit `program.save(...)` after. Without explicit saves, work is in-memory only and discarded on context exit.

**Verified output quality (1080 baserom, 2026-05-04):**
- Auto-analysis time: 391.6s (~6.5 min)
- Functions discovered: 2,505 (vs 2,668 known — 94%)
- Decompile of small libultra helper (interrupt-bracket pattern at VRAM 0x80000118): clean readable C
- Decompile of rmon function (348 bytes at VRAM 0x80008430): structurally clean, struct field offsets clearly visible — the exact use case for which Ghidra is recommended over m2c

**What's MISSING from a vanilla load (worth setting up before productive use):**
- Image base = 0x0; addresses are file offsets, not VRAM. Set up memory blocks: kernel @ 0x80000000 (ROM 0x1000+), USOs at VRAM=0.
- Functions named `FUN_<addr>`. Import `symbol_addrs.txt` to get `func_80008430`-style names.
- USO segments overlap each other in VRAM=0 — would benefit from overlay memory blocks if Ghidra-side analysis cares about cross-USO disambiguation.

**Disk cost:** ~2.4 GB total (JDK + Ghidra + cached project + uv tool venv). Removable any time with `rm -rf /tmp/ghidra-spike` (cached project goes too — re-analysis required after).

**MCP integration sketch (.mcp.json snippet):**
```json
{
  "mcpServers": {
    "pyghidra-mcp": {
      "command": "/home/dan/.local/share/uv/tools/pyghidra-mcp/bin/pyghidra-mcp",
      "args": ["--transport", "stdio", "/path/to/baserom.z64"],
      "env": {
        "JAVA_HOME": "/tmp/ghidra-spike/jdk-21.0.5+11",
        "GHIDRA_INSTALL_DIR": "/tmp/ghidra-spike/ghidra_12.0.4_PUBLIC"
      }
    }
  }
}
```

This exposes `decompile_function`, `get_xrefs_to/from`, `set_function_prototype`, `rename_function`, `set_local_variable_type`, `set_decompiler_comment` etc. as MCP tools.

---

---

<a id="feedback-report-json-vs-decomp-dev-diverge"></a>
## report.json was overstating because land script used `make expected` — RESOLVED 2026-05-04

_HISTORICAL — the land script's `make expected` blanket-cp build/→expected/ used to pollute expected/ with decomp-bodies build, inflating matched_code_percent by ~1pp (8.84% reported vs 7.68% truth). Fixed 2026-05-04 by switching to refresh-expected-baseline.py and patching SUFFIX/TRUNCATE recipes to handle the INCLUDE_ASM case. Truth baseline numbers now apply._

> **STATUS — RESOLVED 2026-05-04 in `agent-e` (1080 project).** Land script now calls `python3 scripts/refresh-expected-baseline.py` instead of `make expected`. The refresh script was unblocked by patching `inject-suffix-bytes.py` and `truncate-elf-text.py` to recognize INCLUDE_ASM-mode (see `feedback_refresh_expected_baseline_blocks_on_yay0_rom_mismatch.md`). The committed `expected/` now reflects a truthful pure-asm baseline.
>
> **Truth values 2026-05-04 (post-fix):** 7.68% / 902-of-2668 funcs / 58860-of-766568 bytes. Both decomp.dev's 8.07% and the previously-stamped 8.84% were wrong — different shades of pollution. Commit `<TBD>` lands the truthful expected/ tree; expect decomp.dev to drop to ~7.68% on its next ingest.

**Root cause (for context):** The Makefile's `expected` target was a blanket cp — `cp build/*.o expected/*.o` after deleting expected/. The land script ran `make expected` after each landing to refresh CI's baseline, but at that moment `build/*.o` reflected decomp-bodies sources, not pure-INCLUDE_ASM. So expected/.<file>.o became byte-identical to build/.<file>.o for every touched file → objdiff reported 100% match for every function in those files, including NM-wrapped ones.

The ALSO-wrong number 8.07% (decomp.dev's view) came from a related but distinct effect: the previously-committed expected/.o files had wrong (smaller) function sizes. SUFFIX_BYTES is supposed to grow function st_size to include trailing stolen-prologue / continuation bytes; the polluted expected/.o had that growth ALREADY APPLIED at decomp-bodies size, but then incremental edits drifted the baseline. With proper refresh, total_code grew from 737844 → 766568 (+28724 bytes = correct accounting of SUFFIX_BYTES growth), which lowered the percentage even though matched_code stayed similar.

**Mechanism of the fix:**
1. `inject-suffix-bytes.py` — added a second skip path: check function's TRAILING n_bytes (within st_size) for already-equal-to-payload. INCLUDE_ASM build has the suffix baked into the .s symbol declaration so this skip fires.
2. `truncate-elf-text.py` — `.text size <= target` is now a no-op (informational print) instead of an error. INCLUDE_ASM emits exactly-asm-length .text which is naturally smaller than C-emit-and-clip target.
3. `refresh-expected-baseline.py` — switched `make → make objects` (C objects only, no link, no Yay0, no md5sum), so Yay0 ROM-checksum nondeterminism doesn't abort the parallel build before all USO .c.o files are produced.
4. `land-successful-decomp.sh` — `make expected` → `python3 scripts/refresh-expected-baseline.py`. Adds ~30-60s per landing for the clean-INCLUDE_ASM rebuild, but the baseline is now truthful.

**How to apply:**
- Trust the post-fix `report.json` (and decomp.dev once it ingests). They will match.
- For ad-hoc local truth: `git checkout HEAD -- expected/ && make clean && make RUN_CC_CHECK=0 objects && objdiff-cli report generate -o /tmp/r.json`.
- If you add a new post-cc recipe type, follow the "INCLUDE_ASM-aware skip path" pattern in `feedback_refresh_expected_baseline_blocks_on_yay0_rom_mismatch.md`. Otherwise it'll silently break refresh-expected-baseline.py the next time it runs.

---

---

<a id="feedback-when-to-consult-ghidra-during-decomp"></a>
## When to consult Ghidra during /decompile (trigger list — m2c remains the default)

_1080 has a Ghidra project + MCP server, but reaching for Ghidra has cost (slower than m2c, GCC-flavored not IDO-flavored). Use only when one of 4 triggers fires: struct shape unknown, function family ≥3, stuck wrap <50% fuzzy with structural unknowns, suspected fragment with `in_t9`/`in_stack_*` reads. Otherwise stick with m2c._

**Default**: use `m2c --target mips-ido-c` for initial C decomp. It's faster, IDO-flavored (matches our codegen target), works on a single .s file with no setup. Good enough for most functions.

**Switch to Ghidra ONLY when one of these triggers fires** (otherwise the cost of Ghidra setup + caching + GCC-flavored output isn't worth it):

1. **Struct shape unknown.** Function reads `*(T*)(arg + 0xN)` patterns and you don't know the struct. Ghidra's typed decomp (after annotating `arg` as `MyStruct *`) renders fields as `arg->fieldname`, exposes field types, and surfaces neighboring offsets you didn't notice in the asm. m2c can't do this — it has no project-level type memory.

2. **Family of related functions** (≥3 callers of a shared callee, or ≥3 functions taking the same struct). Ghidra's `list_xrefs` returns the entire family in one query (e.g. `list_xrefs to FUN_000073f8` returned 27 rmon callers); `grep -rn 'jal func_X' asm/` is slower and misses DATA xrefs. Then `scripts/ghidra-annotate-family.py` batches the struct annotation across the family.

3. **Stuck wrap <50% fuzzy with structural mismatch** (control flow unclear, your draft doesn't match any obvious shape). Ghidra's canonical form often reveals the function is much simpler than your draft. Verified 2026-05-04 on `func_80008030`: our 5-line build-up-and-return wrap was at 36% fuzzy; Ghidra showed the actual logic is `return (D_A4040010 & 3) == 0;` — a one-liner.

4. **Suspected fragment** (function has no prologue / starts mid-flow). Ghidra's decomp output uses `in_t9` / `in_a1` / `in_stack_0000002c` (uninitialized register / stack reads) → caller passes registers, not a standalone function. Diagnostic info you'd otherwise derive by reading asm. Verified on `func_80003FF0`.

**Don't reach for Ghidra**:
- **Yay0-COMPRESSED USO functions (game_uso / *-USO segments).** Ghidra analyzes the static ROM, where these segments are Yay0-COMPRESSED data, not code — so the USO functions are simply NOT in the project. Verified 2026-05-29: after a full `setup-ghidra.sh` (2505 fns), `ghidra-decompile-func.sh game_uso_func_0000D204` → `NOT FOUND`, and symbol-import logged `not-a-known-fn=1086` (the USO funcs). Ghidra only sees the UNCOMPRESSED kernel/game_libs code. For USO orchestrators, m2c also fails (`.word` form, see [m2c on .word-only USO asm](#feedback-m2c-word-only-asm)) and the data relocs aren't in the `.c.o`; hand-decode from `objdump -dr build/src/<seg>/<seg>.c.o` using the `&D_00000000 + offset` convention (single USO base symbol, links via undefined_syms) + `gl_func_00000000` calls + literal floats for inline `lui` consts.
- **Byte-correct matching.** Ghidra's GCC-flavored decomp won't byte-match IDO emit. Use it for *understanding*, not *codegen*.
- **Register-allocation grinding** (>90% fuzzy, just need to flip a register). Use the permuter.
- **Final-mile tightening** (>90% fuzzy in general). m2c output is closer-to-IDO; Ghidra's structural rephrasing actively hurts.
- **First time on a new project.** Ghidra setup (~7 min auto-analysis + ~5 min indexing on first MCP start) isn't worth it for a one-off. Wait until you have ≥10 candidate functions before setting it up.

**How to invoke** (1080 only):
- One-shot decomp: `bash scripts/ghidra-decompile-func.sh <func_name>`
- Family annotate: `python3 scripts/ghidra-annotate-family.py --struct-name RmonMsg --funcs A,B,C,...` (when written; current ref impl is `scripts/ghidra-annotate-rmon.py`)
- MCP queries from Claude Code (read-side only — write-side has had hangs).
- Setup: `bash scripts/setup-ghidra.sh` (~7 min one-time per worktree).

**Companion memos**:
- `feedback_pyghidra_mcp_setup_for_n64_decomp.md` — install + setup quirks (JDK 21, MIPS:BE:32:default, .gpr-not-dir, etc.)
- `feedback_ghidra_struct_annotation_doesnt_auto_propagate.md` — annotations don't propagate across xrefs; batch-script the family.

---

<a id="feedback-m2c-word-only-asm"></a>
## m2c on .word-only USO asm — assemble + objdump round-trip to get mnemonics

_splat emits `.word 0xNNNNNNNN` for USO functions whose lui-relocations spimdisasm can't resolve; m2c then errors with "Function contains no instructions". Round-trip the .word values through `mips-linux-gnu-as` + `objdump -d -M no-aliases` to get readable mnemonics for hand-paste into a temp .s._

**AUTOMATED 2026-05-24 — `scripts/disasm-func.py`.** No more hand round-trip:
`python3 scripts/disasm-func.py <func> --m2c` looks up the function's `st_value`
in `build/non_matching/**/*.c.o` (or `expected/**`), objdumps that byte range to
mnemonics, reformats to m2c-ready `.s` (`glabel` + `.L<addr>:` labels for branch
targets, operands joined), and pipes through `uv run m2c --target mips-ido-c`.
Without `--m2c` it prints the `.s`. Validated on `game_libs_func_00060F90`
(linked-list unlink) → clean pseudo-C. The function must already be built into a
`.o` (it is, via INCLUDE_ASM). This unblocks medium-function decode grinds on every
USO segment. (Manual round-trip below kept for reference.)

**GOTCHA — `disasm-func.py` mis-RESOLVES reloc'd `jal` targets in an unlinked `.o`; every call prints the SAME wrong name (verified 2026-06-04, func_8000745C).** When you disasm `build/non_matching/**/*.c.o` or `expected/**/*.c.o`, the R_MIPS_26 call targets are unresolved (address 0 + reloc), so objdump/disasm-func names them by the nearest symbol — usually whatever symbol owns offset 0 (e.g. `func_800066EC`). So a manual disasm diff shows BOTH your build AND expected calling `func_800066EC` for calls that are really to two DIFFERENT functions (the `.s` under `asm/nonmatchings/` has the correct names via its `/* … */` reloc comments). Do NOT conclude "I'm calling the wrong function" from a disasm-func call-target diff — it's a symbol-resolution artifact, identical in both objects. Trust objdiff's reloc-aware `fuzzy_match_percent` (it compares the reloc SYMBOL, not the resolved address) and read the real call names from the `asm/nonmatchings/<seg>/<func>.s` `jal` lines. Cost me a detour on func_8000745C before objdiff confirmed the calls were fine and the real residual was a `-1`-constant CSE/regalloc divergence.

**GOTCHA (bigger) — `disasm-func.py` shows the BUILT `.c.o`, which for an ALREADY-WRAPPED function is the CURRENT C body's compilation, NOT the target (verified 2026-06-06, gl_func_000717CC / gl_func_0006BC4C).** It objdumps `build/non_matching/**/*.c.o`. For an INCLUDE_ASM-only function that's the real target bytes (INCLUDE_ASM embeds the `.s`), so disasm-func + `--m2c` are correct. But once the function has a `#ifdef NON_MATCHING` body, the `.c.o` contains YOUR compiled body — so disasm-func "reconstructs" what's already there (I rebuilt gl_func_000717CC's existing 46% body believing it was the target, and it was actually a caller-set-$t6 cap). ALWAYS sanity-check: disasm-func's first instruction must equal the raw `.s` first `.word`; if not, you're looking at a wrapped body or a mis-resolved symbol. To see the TARGET regardless of wrap state, decode the raw `.s` `.word` blob directly: `python3 -c "import re,struct;ws=[int(m,16) for m in re.findall(r'\.word 0x([0-9A-Fa-f]{8})',open(S).read())];open('/tmp/t.bin','wb').write(b''.join(struct.pack('>I',w) for w in ws))"` then `mips-linux-gnu-objdump -D -b binary -m mips:4000 -EB /tmp/t.bin`. (To diff target-vs-built, decode BOTH this way — built via the .c.o symbol range.) **2026-06-06: this whole workaround is now packaged as `scripts/disasm-raw.py <func> [--m2c]`** — it does the blob decode automatically (always TARGET, branches in range) and `--m2c` reformats correctly (only branch mnemonics get `.L` labels, so `lui/ori` immediates aren't mangled; warns on past-end/inter-function tail-branch targets). Prefer it over `disasm-func.py` for anything that might be wrapped.

**GOTCHA — `report.json` is STALE for local candidate-picking; regenerate before filtering.** It's git-tracked and updated only by the land script, so a function it lists at 0%/"<5%" may already be 46%+ in your tree (gl_func_000717CC 2026-06-06). Picking "0% unwrapped" candidates off `report.json` surfaces already-wrapped caps. Always `make non_matching_objects RUN_CC_CHECK=0 && objdiff-cli report generate -o /tmp/rp.json` and filter `/tmp/rp.json`.

**LEVER — `switch` beats an `if (x==a) … else if (x==b) …` chain for small command dispatchers.** IDO compiles a `switch` over a few `case` constants into a `beql/beq` compare chain with the taken-case's first load hoisted into the delay slot — matching the typical hand-written dispatcher. The equivalent if-else-if chain emits `bne …; branch-away` instead and scores lower. gl_func_00051F5C jumped 67.7→81.9% just by switching the dispatch form to `switch`.

**GOTCHA — m2c renders a reloc'd `&D_00000000`-pointer store as `= 0` (verified 2026-05-29, mgrproc_uso_func_00002940).** When the asm is `lui rX,0x0; addiu rX,rX,0; sw rX, OFF(base)` (i.e. store the *address* `&D_00000000` into a field), m2c shows it as `field = 0` because the relocation target resolves to 0x0 and m2c can't see the reloc. So a field m2c claims is zeroed may actually hold a POINTER. Tell them apart by the insn count: a real zero-store is one `sw zero, OFF` (1 insn); a `&D` store is `lui;addiu;sw` (3 insns, with R_MIPS_HI16/LO16 relocs). If your NM body is ~2 insns short per such field, change `*(int*)(p+OFF) = 0;` to `*(char**)(p+OFF) = (char*)&D_00000000;`. Recovered 8 insns / +6.5pp on mgrproc_uso_func_00002940. Same root cause as the `*(s32 *)0x68`-style m2c renderings (those are `&D_00000000 + 0x68`).

**GOTCHA — m2c renders an FP comparison as a bogus INTEGER bit-test (verified 2026-06-05, gui_func_00000F04).** When the target gates a block on the sign of a truncated float (asm: `trunc.w.s; mfc1 rN,..; sll rN,..; bgez rN, skip` or a `c.lt.s`+`bc1t/bc1f`), m2c often can't model the FP/branch and emits a nonsense int mask like `if ((s32)f2 & 0x20000000)` (bit-29 is never a real test). Read the target's ACTUAL branch to recover the true condition: `bgez rN`→`if (x >= 0)` (so the *gated* body runs when `x < 0`), `bltz`→`if (x < 0)`, `c.lt.s f0,f1`+`bc1t`→`if (a < b)`. Two payoffs: (1) correctness; (2) the bogus int var (here `f10 = (int)f2`) is often held live ACROSS a call only to feed that fake test — once you rewrite the gate in terms of a value you already keep (`s4 = (int)f2*4`, test `s4 < 0`), that var dies early and you DROP a cross-call spill, shrinking the frame (0x130→0x128 on F04). So an m2c int-mask test on a float-derived value is both a decode bug AND a frame-reduction lever.

**Symptom:** an asm file under `asm/nonmatchings/<uso>/<uso>/<func>.s` is all `.word 0x…` lines with no mnemonics. Running `uv run m2c --target mips-ido-c <file>.s` errors with:

```
Decompilation failure in function <func>:
Function <func> contains no instructions. Maybe it is rodata?
```

**Why:** spimdisasm gives up on `lui $at, 0` followed by an unresolvable relocation (e.g. `lwc1 $f16, 0($at)` where `$at` should be patched by the USO loader). USO segments at synthetic VRAM=0 don't have global addresses to anchor the disasm, so the whole function falls back to `.word`. m2c only parses mnemonic instructions and treats `.word` as data.

**Fix — round-trip through binutils:**

```bash
# 1. Extract the .word values:
grep -oP '0x[0-9A-F]{8}' asm/nonmatchings/<uso>/<uso>/<func>.s > /tmp/words.txt

# 2. Wrap them in an assemblable .s file:
{ echo ".set noreorder"; echo ".text"; echo ".global _start"; echo "_start:"
  while read w; do echo ".word $w"; done < /tmp/words.txt; } > /tmp/decode.s

# 3. Assemble + disassemble to get mnemonics:
mips-linux-gnu-as -EB -march=vr4300 -o /tmp/decode.o /tmp/decode.s
mips-linux-gnu-objdump -d -M no-aliases /tmp/decode.o

# 4. Hand-paste mnemonics into a fresh .s with proper `glabel` and `.LXXXX:` labels,
#    then run m2c on THAT temp .s.
```

**Caveats:**
- `lui $at, 0` will look weird in objdump output (no symbol resolution) — you'll need to leave it as a literal `lui $at, 0` in the m2c input. m2c handles this fine; it just emits `*(T*)0` accesses, which you replace with `&D_00000000 + offset` in the C body.
- Branch targets (`bne … 0x20 <_start+0x20>`) need to be rewritten as `.LXXXX` labels matching the original ROM offsets — m2c errors with "Cannot find branch target" if the labels don't exist. Add label lines (`.LXXXX:`) at the appropriate offsets in your temp .s.
- If you forget a label, m2c's error names exactly which one, so iterate until it parses.
- **If you SCRIPT the relabel step** (regex-rewrite branch targets to `.LXXXX`), only rewrite operands of actual branch ops (`b/beq/bne/beqz/bnez/bgez/...`). A naive `,(0x[0-9a-f]+)$` substitution also matches the immediate in `lui rX, 0x2`, corrupting it to `lui rX, .L2` → m2c aborts with `lui/lis argument must be a literal or %hi/@ha/@h macro`. Guard the rewrite on the mnemonic. (Hit 2026-05-29 auto-synthesizing the temp .s for gl_func_0003829C.)

**When to use this:** any USO function whose .s is .word-only AND whose body is non-trivial (≥30 insns) — small functions you can decode by hand instruction-by-instruction faster than the round-trip. Used 2026-05-05 on `game_uso_func_00002744` (52 insns) — m2c produced a clean structural decode in one pass that would've taken 30+ minutes by hand.

**Long-term fix:** migrate USO disasm to spimdisasm proper (per `project_1080_uso_spimdisasm_migration_todo.md`) so the .s files have mnemonics from the start. Until then, the round-trip is the cheapest workaround.

---

---

<a id="feedback-permuter-import-requires-ifdef-non-matching-body"></a>
## decomp-permuter `import.py` needs a C body under `#ifdef NON_MATCHING` — bare `INCLUDE_ASM` invisible

_For the `<80% → keep INCLUDE_ASM` rule (`/decompile` skill threshold): if you intend to grind the function via permuter later, leave the verified C decode wrapped in `#ifdef NON_MATCHING` even when fuzzy is sub-80%. `import.py` parses the source file looking for a function DEFINITION that matches the target asm — bare `INCLUDE_ASM("...", funcname);` registers no function, and permuter setup fails with "no such function found"._

**Symptom:** `python3 decomp-permuter/import.py <src.c> <asm.s>` errors with no function matching the target name — even though `INCLUDE_ASM(funcname)` is right there in the .c file. The import is C-source-driven, not asm-symbol-driven.

**Recipe:** when documenting a sub-80% verified decode, wrap it:
```c
#ifdef NON_MATCHING
/* <doc comment with cap notes> */
void funcname(int a0, ...) {
    /* verified decode, even at 60-79% fuzzy */
}
#else
INCLUDE_ASM("asm/nonmatchings/<seg>", funcname);
#endif
```

The `#else INCLUDE_ASM` keeps the default build byte-exact via ROM bytes; the `#ifdef NON_MATCHING` block makes the function importable by permuter for later grinding. This is the EXCEPTION to the "<80% keep plain INCLUDE_ASM" rule: any function you plan to permuter-grind needs the NM wrap.

**Discovered 2026-05-16** when a parallel agent (per main commit `4c5f7158`) restored `game_libs_func_0003DBEC`'s C body under NON_MATCHING explicitly as a "permuter seed" — same gotcha as `game_libs_func_0003DDC0`. The verified-decode-as-INCLUDE_ASM-only pattern blocked permuter setup until the body was restored.

**Caveat (false-positive-episode risk):** the project-wide classifier flagged ~140 episodes as tautology-trap candidates because they were logged against NM-wrapped functions where the C body was 19–78% but the wrap inflated reported match. Permuter seeds DO NOT and SHOULD NOT log episodes — they're scaffold, not ground truth. Episode-logging guard remains "exact match only, via build/non_matching/.o byte-verify against expected/.o."

---

<a id="feedback-permuter-working-setup-2026-05-23"></a>
## WORKING permuter setup (2026-05-23) — the 0/6 was misconfiguration

The permuter is the **sanctioned last-mile match tool** (INSN_PATCH and all
instruction-byte patching were removed 2026-05-23 — see
`memory/feedback_no_instruction_forcing_matches_policy`). It only helps functions
already CLOSE (count-match, register-allocation/scheduling/branch-order diffs);
structural diffs (count-mismatch, wrong fields) need a C fix first.

Earlier runs scored 0/6 not because the permuter can't do it, but because it was
run **unconfigured**. Two fixes:

1. **`projects/1080-*/permuter_settings.toml`** (committed):
   ```toml
   compiler_type = "ido"
   [weight_overrides]
   perm_temp_for_expr = 100
   ```
   Without `compiler_type = "ido"` the permuter uses generic weights ill-suited
   to IDO codegen.

2. **Import with the FULL CPPFLAGS** (from the project worktree dir):
   ```bash
   python3 ../../tools/decomp-permuter/import.py \
       src/<seg>/<file>.c asm/nonmatchings/<seg>/<sub>/<func>.s \
       'CPPFLAGS=-I include -I src -DNON_MATCHING'
   python3 ../../tools/decomp-permuter/permuter.py nonmatchings/<func> --stop-on-zero
   ```
   - `-DNON_MATCHING` is MANDATORY: functions are `#ifdef NON_MATCHING { C } #else
     INCLUDE_ASM #endif`. Without it the build takes the `#else` (INCLUDE_ASM) path
     and there is **no C body to permute** (this silently broke old runs).
   - `-I include -I src` is MANDATORY (the PERMUTER make rule uses `$(CPPFLAGS)`;
     passing a bare `CPPFLAGS=-DNON_MATCHING` *clobbers* the include paths →
     `common.h: No such file`). Pass all three as one quoted arg.

When the permuter reaches **score 0**, the matching C is in
`nonmatchings/<func>/output-0-*/source.c`. Put that C into the function's
`#ifdef NON_MATCHING` block in src, rebuild, verify byte-exact against the `.s`
(`raw-diff=0`), and it's a **real match** — no patch, episode-worthy. `nonmatchings/`
is gitignored. Score bands still apply (≥1000 ≈ structural, stop and fix the C).- (5) **frame-SIZE differences** (not just spill-slot swaps) — when the target frame is e.g. 0x90 but your C emits 0x98 (an extra 8-byte spill/temp slot), the permuter is USELESS: its scorer normalizes ALL sp-relative offsets, so it neither sees the size diff nor the cascade of shifted sp-offsets it causes, and it will happily report a *lower* score for a variant that actually GREW the frame (verified `func_80000D2C` 2026-05-31: 28k iters, "score 15" while frame grew 0x98→0xA0, 18 raw diffs vs base 13). Frame-size caps need MANUAL spill-elimination (reduce live-range pressure), not the permuter. 

<a id="feedback-permuter-manual-scratch-and-reseed-chain"></a>
### `import.py` fails on a big multi-fn TU → build the scratch dir by hand; BUT on a frame-SIZE cascade the reseed-from-best "fuzzy gain" is a FALSE IMPROVEMENT (objdiff hides frame growth) (2026-06-22)

`import.py` derives the compile command by running `make --always-make --dry-run --debug=j PERMUTER=1 <CPPFLAGS>` and grepping the output for the source filename. This fails ("Failed to find compile command from build script output") whenever the .c you point it at is not itself a make target — e.g. a minimal extract of one function out of a 30k-line shared TU like `game_libs_post0b.c`. Also note `find_root_dir` walks UP from the source file looking for `permuter_settings.toml`, so the scratch .c must live inside the project tree (a `/tmp/...` path errors "Can't find root dir of project!").

**Bypass — construct `nonmatchings/<name>/` manually** (the permuter only reads these 4 files):
- `base.c` — preprocessed source: `cpp -nostdinc -DNON_MATCHING -I include -I src scratch.c | grep -v '^#'`. (Pre-expanding sidesteps any IDO cc header-path quirk; the result feeds straight to `compile.sh`.)
- `target.o` — assemble the `.s` with the glabel/endlabel macro prelude prepended: copy the prelude (everything before the first `glabel`) from any existing scratch's `target.s`, concatenate your function's body (drop the leading `nonmatching <fn>, 0xNNN` line), then `mips-linux-gnu-as -EB -march=vr4300 -mtune=vr4300 -mabi=32 -I include target.s -o target.o`. (objdump may show ONE extra trailing word vs `expected` — harmless padding past the symbol size; the permuter scores by symbol size.)
- `compile.sh` — `cd` to the project root then `tools/ido-static-recomp/build/7.1/out/cc -c -G 0 -non_shared -Xcpluscomm -Wab,-r4300_mul -O2 -mips2 -32 -I include -I src "$INPUT" -o "$OUTPUT"`.
- `settings.toml` — `func_name = "<fn>"` + `compiler_type = "ido"` (+ optional `[weight_overrides]`).

**Sanity gate:** before trusting the base score, confirm the manual `base.o`'s function bytes are IDENTICAL to the in-tree `build/non_matching/.../X.c.o` (objdump both, compare the word list). If they match, `base score` will equal the documented near-miss floor.

**Reseed-from-best chain (and why it BACKFIRED here — read before trusting a permuter fuzzy gain on a frame near-miss):** run `-jN --best-only --stop-on-zero`, take the best `output-NNN-K/source.c`, make it the NEXT scratch's `base.c`, re-run; repeat. On gl_func_0004C928 (frame 0x80, target 0x78, plus a v0/v1-coloring cascade) seven reseeds drove permuter score 720→610→…→455 and objdiff fuzzy **97.56→98.71%**, each pass adding a DEAD artifact (`long long pad;`/`int new_var3..5;` spill-slot decls, dead `if(arg0->dD0){}`/`do{}while(0)` blocks, `((0,arg0))` comma-expr, offset indirections). **It was a FALSE IMPROVEMENT and was reverted.** `objdiff` (and thus `fuzzy_match_percent` / decomp.dev) NORMALIZES sp-relative offsets, so it gives ZERO penalty for frame growth and full credit for "matching" sp-relative loads/stores that sit at the wrong offset. The reseed chain raised the normalized score by GROWING the frame 0x80→0x98 — i.e. moving it FURTHER from the target's 0x78 — while the true byte-exact count REGRESSED: **raw exact-position-matched instructions dropped 87/227 (orig, frame 0x80) → 84/227 (best, frame 0x98).** The +8-byte frame is a genuine optimizer spill, verified INVARIANT to declaration order by a 120-permutation full-decl-order brute force; permuter randomization cannot shrink it.

**LESSON: when the residual is a frame-SIZE diff, do NOT trust the permuter's fuzzy gain — it is the documented "frame-SIZE cap, scorer hides it" trap (see point 5 in the WORKING-setup section). Gate the chain on RAW byte-exact-position count (objdump -d both, difflib on the word list) AND on the frame-size word, not on `fuzzy_match_percent`.** A rising fuzzy with a growing/diverging frame is a regression dressed as progress; revert it. The permuter remains the right tool ONLY for same-frame coloring/scheduling residuals.

`report generate` STOMPS the git-tracked `report.json` — `git checkout HEAD -- report.json` afterward. Clean up `nonmatchings/scratch*` dirs (gitignored, but they pile up).

### Disassembling a raw-.word USO .s: extract symbolic jal/lui lines too, or the .bin is corrupt (2026-06-01)

A common quick-decode move is to scrape a USO `.s` for instruction words and `objdump -b binary` the result. PITFALL: splat renders RELOCATED instructions symbolically, e.g.
`    jal game_uso_func_000023D4   /* 002930 0C000000 -> game_uso_func_000023D4 */`
and `lui $a1, %hi(game_uso_D_...)  /* ... 3C050000 -> ... */`. Their hex word sits before `-> sym`, NOT before `*/`. A regex like `([0-9A-F]{8}) \*/` (matches only raw `/* a v HEX */ .word 0xHEX` lines) SILENTLY DROPS every jal/lui-with-reloc, so the rebuilt `.bin` is missing those instructions and every offset after the first dropped one is shifted — a fully corrupted disassembly. Symptom: your scrape reports "0 jals" on a function whose comment/decomp says it has N cross-USO calls (caught 2026-06-01 on game_uso_func_00000B3C: scrape said 0 jals, real count 22; led to a false "spurious gl_func" conclusion — the gate-revert saved it).

Fix: extract the hex from BOTH forms — match the THIRD hex field of the `/* rom vram HEX ... */` comment regardless of what follows (`r'/\*\s+[0-9A-Fa-f]+\s+[0-9A-Fa-f]+\s+([0-9A-Fa-f]{8})'`), not the `... HEX */` tail. Better: disassemble the actual built `.o` (`objdump -d build/non_matching/.../<file>.c.o`, reloc-aware) instead of scraping the `.s`. Corollary: gate-verified edits (build + objdiff per change) are still trustworthy even if your guiding disasm was flawed — that's why the C48C sub-init climb (27→48%) held up despite this tooling bug; the objdiff gate, not the scrape, confirmed each value.

### objdump `reg-names=n32` mislabels $8-$11 as a4-a7 (they're o32 t0-t3) (2026-06-02)

When disassembling 1080 (o32 ABI) code with `mips-linux-gnu-objdump -M no-aliases,reg-names=n32`, registers $8-$11 print as `a4,a5,a6,a7` — but 1080 is O32, where $8-$11 are `t0,t1,t2,t3` (temporaries), NOT argument registers (o32 args are only a0-a3 = $4-$7). Misreading `a4-a7` as call arguments will produce wrong C (e.g. inventing a 5th-8th register arg). Use plain `reg-names=o32` (or no reg-names override — gas default for the target is o32) when decoding 1080 USO functions. Caught while decoding titproc_uso_func_000005DC's s5-bitmask cases: `or a5,s5,at; ... sw a7,68(sp)` is `or t1,s5,at; ... sw t3,68(sp)` — temps building a bitmask spilled to a stack local, not arg-register setup.

## Ghidra reconstruction gotchas: FP constants are mis-displayed, and ~some gl_func USO names aren't in the project (2026-06-04)

Using `scripts/ghidra-decompile-func.sh <fn>` to drive an m2c-collapsed/stub reconstruction (the technique that took `gl_func_0005E288` 28.8→65% and `gl_func_0003CBB4` 13.8→17.2%) — two traps:

1. **Ghidra's FP constants are not trustworthy — cross-check every one against the asm.** On `gl_func_00036F0C` Ghidra rendered `fVar4 = 100.0` for the 0x40/0x80 flag scale, but the `.s` shows `lui $at, 0x4059` (= 3.390625f) TWICE plus a single `lui 0x42C8` (= 100.0f) — i.e. the 3.39 constant is the real pitch scale and Ghidra mislabeled it 100.0. Before trusting a reconstructed constant, grep the asm for the float-hi luis: `grep -oE '\.word 0x[0-9A-F]{8}' fn.s | <decode op==0x0F lui imm>` and map `imm0000` → IEEE754 (0x4059→3.39, 0x42C8→100, 0x4120→10, 0x4080→4, 0x42B2→89). A wrong constant silently caps the match.

2. **Not all `gl_func_*` USO symbols are in the Ghidra project.** `gl_func_0004FD18` and `gl_func_00020A28` return `NOT FOUND` (2505 fns imported, but some relocatable-USO names aren't named in the .gpr). When a target isn't found, fall back to m2c + manual asm decode; don't assume the reconstruction vein is available for every low-% function.

3. **Reconstructing an FP function faithfully from Ghidra often SPILLS where IDO keeps registers.** A direct translation of Ghidra's `if (d<0) d=-d;` abs blocks plus a multi-term dot product creates enough simultaneously-live FP values that IDO spills them all to stack — `gl_func_0003CBB4`'s reconstruction landed at frame -0xD0 (18 spill slots) vs the target's -0x50. The two-var Ghidra abs form (`if(delta<0){sd=delta;abs=-sd}else{abs=delta;sd=abs}`) did NOT help (regressed 17.2→15.5%) — the spill is driven by total live-FP pressure, not the abs shape. Getting these to high % is a register-pressure-reduction grind (fewer simultaneously-live temps), same class as the regalloc-dump caps — the structural reconstruction is the easy +pp; the last 50% is the grind.

4. **regalloc-dump triage (verified 2026-06-04, gl_func_0004880C): before grinding a `$s`-register near-miss with the `-Wo,-zdbug:6` dump, FIRST check whether the dump's final coloring already MATCHES the target.** The `./uoptlist` tail prints `<candidate>: <n> assigned (constrained) <hardreg>` (hardreg 16=$s0, 17=$s1, 18=$s2, …). On gl_func_0004880C the dump assigned a0→$s2, a1→$s1, i→$s0 — IDENTICAL to the target — yet the build still diffs at 99.2%, because the 3 `move $sN, <arg>` prologue-init instructions EMIT in a different ORDER (target s2,s0,s1; IDO s1,s2,s0). That is allocno/move-emission SCHEDULING, NOT coloring, and the dump cannot fix it (no candidate-priority knob changes instruction order; decl reorder doesn't flip it either — it's permuter-class). **Rule: the regalloc-dump only helps a near-miss whose COLORING differs (a true `$sX`↔`$sY` value swap). If `uoptlist` shows the colors already correct, stop — the residual is scheduling, and you're better off on the permuter or moving on.**

**Band survey (2026-06-04): the regalloc-dump vein is nearly empty — the `$s` near-miss band is emission-ORDER-dominated, not coloring.** Surveyed all game_libs ≤6-diff 95-99% `$s`-register near-misses: gl_func_0004880C (3d), gl_func_00033B6C (4d), gl_func_00041148 (4d) — every one is the SAME instructions (same `$s` coloring) emitted in a different ORDER (prologue arg-saves, or the pointer-init `addiu $sN,&base,off` block, emitted ascending `$s0..$s3` where the target is descending). True coloring swaps (same position, different `$s` register) were NOT found in the band. The decl/assign-separation trick (declare in coloring order, ASSIGN in target emission order) REGRESSES (gl_func_00033B6C 4→8 diffs): IDO re-couples the assignment order back into the coloring, so you can't get target-emission-order AND target-coloring at once — the first-emitted init takes the highest `$s`, exactly the FP `$f14`-first coupling in IDO_CODEGEN.md's "if(1){}" scope-caveat #2. Net: these are permuter-class scheduling caps; don't open the regalloc-dump for them.

## disasm-func --m2c can emit PHANTOM out-of-function labels (mis-based branches) (2026-06-10)

On timproc 1DB0, `scripts/disasm-func.py --m2c` failed with "label
.L1CC0 does not exist" -- implying a backward branch into the PREVIOUS
function. A direct word-scan (decode branch opcodes 1/4/5/6/7/20-23,
compute addr+4+off*4 against the symbol range) showed the only
out-of-range branch was FORWARD (bnezl -> +4 past the declared end, the
usual tail-fragment family). The tool mis-based at least one branch.
Rule: before acting on an m2c/disasm-func cross-function branch claim,
confirm with the direct word-scan -- it is ~10 lines of python and
decides merges definitively. (Same scan also catches the size-vs-word-
count mismatches from lowercase-hex comment lines that simple regexes
miss.)

## Candidate census: use report.json, never grep src for definitions (2026-06-10)

Three false "unstarted" candidates in one tick: grep-based "has no C
def" checks miss pointer-return defs (`void *fn(`), K&R implicit-int
defs (`fn(a0) int *a0; {`), and macro-wrapped forms. 1080 now has
`scripts/list-unstarted.py` (parses report.json fuzzy_match_percent,
sorts by size, flags BARE vs WRAPPED). Refresh report.json first. The
proc-USO family (boarder1/2, n64proc, eddproc, h2hproc, titproc) was
verified FULLY matched in the same pass -- don't re-census it.

## log-exact-episode routes to the CWD's episodes/, not the worktree's (87F4, 2026-06-10)

`uv run python -m decomp.main log-exact-episode` (run from the monorepo
root, as required for uv) writes to `<cwd>/episodes/` by default --
NOT the agent worktree's episodes/ that land-successful-decomp checks.
Symptoms in order: "missing episodes/<fn>.json" from the land script,
then a confusing ls (the monorepo's untracked episodes/ shadows it).
Fix: pass `--log-dir projects/<wt>/episodes` (or mv the json over).
Also: the positional function_name comes FIRST and --source-file is
required; and refresh-report dirties report.json, so `git checkout
HEAD -- report.json` before landing (the script refuses tracked
changes).

## Standalone-cc harnesses: never keep USO FW absolute-address reads as bare constants (940)

When pulling an NM body into a standalone test file, FW(p, o) forms
that read *(s32*)0xNN (USO D_-symbol references flattened to small
absolute addresses) MUST be rewritten as `extern char D_base;` +
offsets -- IDO compiles bare small-address loads differently (folds
the lui/addiu, can even drop a comparison arm from an OR-chain),
making the byte-diff meaningless. Symptom: standalone diff wildly
worse than the in-tree fuzzy, with structural "missing arms" the C
clearly contains. Seen on game_uso_func_00000940 (in-tree 88.66 vs
bogus standalone 73-diff).

## Ad-hoc .s word extraction: match the 3-field comment, not the rendering (3 failures in one session)

Raw-word USO .s files render lines THREE ways -- plain `.word 0x...`,
symbolic reloc lines (`lui $at, %hi(sym)` with `/* ... 3C010000 -> sym */`
or trailing `*/` only), and full-mnemonic lines (titproc style). Any
extraction regex keyed to `.word` or `-> ` silently DROPS words,
producing phantom out-branches, shifted byte-diffs, and bogus
"truncated symbol" conclusions (87F4 lost its lui; 116C appeared to
have 14 out-branches and a missing 0xD0 tail). The ONLY safe pattern:
`/\* [0-9A-Fa-f]+ ([0-9A-Fa-f]{8}) ([0-9A-Fa-f]{8}) \*/` -- every line
carries the addr+word pair in its comment regardless of rendering.
Better: use scripts/disasm-raw.py instead of ad-hoc regexes.

Addendum (2026-06-10, 940 in-tree): the raw-absolute gotcha is not
just a harness issue -- m2c lifts of USO code leave D-references as
bare `*(s32 *)0xNN` / `*(char *)0xNN` absolutes IN WRAP BODIES, which
compile to folded small-address loads (wrong shape AND wrong relocs).
Converting all 8 such sites in game_uso 940 to the
`*(int *)((char *)&D_00000000 + 0xNN)` extern form was worth +7.5pp
in-tree (89.74 -> 97.24). SWEEP LEAD: grep src/ for
`\*\((s32|u32|char|int) \*\)0x[0-9A-Fa-f]+\b` inside NM wraps -- every
m2c-lifted USO wrap is a candidate for the same mechanical fix.

CAVEAT to the raw-absolute sweep (2026-06-10): the conversion is
UNIT-CONVENTION-DEPENDENT. game_libs_post's 241 sites REGRESSED the
unit 47.0 -> 19.1 (reverted; the measure gate caught it): in game_libs
wraps, m2c's bare absolutes are placeholders for OTHER loaded bases
(not &D) -- converting adds wrong lui/addiu pairs and size-shifts
dozens of mid-% wraps. The conversion is only correct where the TARGET
materializes the D base at those sites (game_uso 940: +7.5pp; timproc
b5: +0.34pp). Rule: convert per-file ONLY with the unit measure gate,
and check a sample site's target asm for the lui/addiu+reloc pair
first. game_libs pools (post 204, game_libs.c 58, post0b 48) are OFF
the sweep list.

## uoptlist verbosity ceiling (2026-06-10): order questions yes, color questions no

-zdbug:6 gives the candidate/pseudo table (CREATION ORDER -- answers
temp-numbering and pseudo-order questions directly). :7 adds per-node
dataflow sets (av/ant live-range data, numlr counts). Higher values
(8/10/16/22/38/70) plateau at the :6 content; hex args don't parse.
The FINAL COLOR ASSIGNMENT (which lr -> which register) is not printed
at any probed level -- numcoloredlr prints 0 even for fns with v0/v1
pair residuals. Consequence for the "uoptlist queue": creation-order
class residuals (273B8 temp pattern, 5B5D8 skip) are inspectable;
pure coloring-choice residuals (E04 spill slot, ECEC/56814 pairs,
46C4C marshal-reuse) are NOT -- escalation would be reading uopt's
source in ido-static-recomp or patching more print paths (ecvt-style).

## Mnemonic-LCS diff for distributed-gap NM wraps (116C pass 5, +9.4pp in one block)

When an NM emit is N insns short and position-based word-diff shows
"everything differs", run difflib.SequenceMatcher over the two
MNEMONIC lists (opcodes only, build .o disasm vs target words disasm)
and print the delete/insert opcodes: missing CODE BLOCKS pop out as
contiguous `delete` runs (116C: one 27-insn run = an entire undecoded
sub-block; the rest were 2-3-insn shape gaps). Far faster than eyeball
side-by-side for 200+ insn fns; pairs with the multi-run convention --
each big delete run is one pass's decode target.

## m2c full-body graft: the cleanup-class checklist (90CC, 2.74->53.24)

For big-swing grafts of raw m2c output over a stub wrap (the pipeline:
.s comment words -> objdump 0-based blob -> label-resolved .s -> m2c),
the output needs a FIXED set of mechanical conversions before IDO
compiles it; apply in this order and re-grep after each:
1. collapsed callees: m2c emits bare `0(...)` calls for jal-0 -- regex
   `(?<![\w.])0\(` -> `func_00000000(`.
2. `->unkNN` -> `*(s32 *)((char *)(X) + 0xNN)` -- THREE forms: plain
   identifier, NEGATIVE offsets (`->unk-4`), and parenthesized bases
   (nested parens defeat one-shot regexes; fix leftovers by hand).
   TRAP: the identifier regex SPLITS hex literals -- `0x868C->unk1`
   matches `x868C` as the base, producing `0` + `(x868C)` garbage;
   sweep for `\bx[0-9A-Fa-f]{3,}\b` afterwards.
3. absolute derefs (`*0`, `*(s32 *)4`, `*(f32 *)0x8B0`, `*(void *)4`)
   -> `*(T *)((char *)&D_00000000 + N)`; mind that a naive `0` regex
   also hits the 0 in `0x..` (the `+ 0)x34` mangle) -- repair with
   `\+ 0\)x([0-9A-Fa-f]+)` -> `+ 0x\1)`.
4. `void *` locals -> `char *` (IDO rejects void* arithmetic); keep
   the signature.
5. float stores m2c typed as s32: `*(s32 *)(...) = (f32)` -> `*(f32 *)`.
6. m2c struct-ish stack vars (`spA.unkN`) -> `*((s32 *)&spA + N/4)` +
   declare the extra spilled words it references (sp60/sp64 class).
7. vtable calls `*(s32 *)((char *)(X) + 0xNN)(args)` -> cast through
   `((void (*)())...)`.
Each class is one regex; the whole graft (2106 insns) took ~7 cycles
of compile-and-fix. Expect 2-5% -> 40-55% structural in one tick.

Addendum to the graft checklist (7C1C, +38.5pp): (8) m2c emits
collapsed jal-0 calls as `NULL(...)` too (not just `0(...)`) -- handle
both; (9) double-chained `->unk` on parenthesized bases needs a
paren-BALANCED fixer (regex char classes fail on nested parens);
(10) anchor body edits at the DEF line including the `{` -- anchoring
on the function NAME alone finds the extern declaration first and
silently patches the wrong span (burned: a whole fixer pass no-op'd);
(11) if m2c says "label .LXXXX does not exist", the .s window is
UNDERSIZED (branch past declared end) -- re-extract through the gap
from the verified block asset / byte-exact ROM, not the .s.

Addendum (2E354): (12) inline jumptables in direct-linked game_libs --
extract-uso-jumptable.py needs a standalone USO module and does not
apply; SYNTHESIZE for m2c instead: case heads = the blocks after the
jr, delimited by unconditional-b convergence (block-walk); entries in
address order. The case ORDER is approximate -- expect m2c switch
structuring to wobble (flatten broken switches to goto-blocks with
case markers); refine later from the USO reloc records. (13) m2c
resolves REAL stored jal targets as absolute fn-ptr casts
`(T (*)(...))0xADDR(...)` -- convert to named externs (these are
recovered callee identities!). (14) ORDER MATTERS: run the *0/*(T*)N
absolute-deref conversions AFTER NULL->0 (or convert *NULL first) --
NULL->0 mints new `*0`s. (15) m2c `M2C_ERROR(unset register)` reads +
assignments from void-typed calls: placeholder with a loud marker
comment, fix in refinement.

Addendum (2BB7C): (16) YIELD PREDICTOR for graft target selection --
check the jumptable sltiu bounds vs fn size BEFORE grafting. Sparse
tables (bound ~= distinct case bodies; 2E354's 5/11) synthesize fine
(+39pp); DENSE tables (2BB7C: bounds 66/41/97 over 778 insns =
heavily shared bodies) defeat block-walk head inference and m2c's
structuring collapses (+14pp only). Dense-table fns should wait for
true table extraction from the USO reloc records, or be grafted with
tempered expectations. REFINED (2FB74): head COVERAGE is not
sufficient -- shared case TAILS + sparse case VALUES over wide ranges
(e.g. {24,34,0x104}) still interleave-collapse m2c's structuring under
an approximate order; such double-dispatchers are loader-RE-gated. ALSO low-yield: f64-HEAVY
fns (ldc1/sdc1/cvt.d density; m2c emits 'second half of f64'
placeholders) -- m2c f64 reconstruction + IDO f64 register pairing
diverge structurally (C234: +1pp). Check FP-width before grafting:
f32-heavy = sweet spot (+44..+75pp), f64-heavy = skip or temper.
THIRD low-yield class (454C4): BITWISE-FP -- float bits moved through
int regs (high 0x44xxxxxx COP1-move density; m2c types FP-reg temps as
s32, e.g. 's32 temp_f4'). m2c reconstructs bit-moves as int math; IDO
emits different sequences (+7pp only). REVISED 2026-06-10: 454C4
jumped 7.24->29.77 once its (u32)float FCSR-dance decompositions were
recomposed (now automatic in m2c-graft-clean.py) -- HIGH COP1 DENSITY
IS AMBIGUOUS between u32-cast dances (fixable) and true reinterpret
moves (the real cap). Diagnose by grepping the m2c output for the
2.1474836e9f signature BEFORE classifying as bitwise-FP. THRESHOLD CALIBRATION (5A2CC):
~11% COP1-move density still grafted fine (+47.9pp); ~15% (454C4)
killed it -- the line sits between, so measure density and temper
expectations in the 12-15% band. SHARPENED (5BE20, 19 COP1 + 12 f64 in
281 insns): bitwise-FP grafts can come out OVERSIZE (lw+mtc1 pairs vs
lwc1) past objdiff's alignment window -> fuzzy=None = ZERO metric
value (worse than the honest INCLUDE); and retyping the s32-typed
temp_fN vars INVERTS into cvt bloat when the values genuinely cross
int contexts. Mixed bitwise+f64 fns: skip the graft, leave bare,
typed hand decode only. Also: m2c recovering a RECURSIVE self-call
(jal to the fn's own address) needs the self-extern dropped -- the
def is the decl.

## game_libs jumptable TRUE-table extraction: negative result + leads (2026-06-10)

Searched for the 2E354/2BB7C jumptable words (data+0x5860/0x5880 per
the lw lo16s): NOT in assets/game_libs_post.bin (len 0x2d5c < the
offset!), NOT in game_libs_dl_data.bin (RSP ucode at that offset),
no pointer runs under raw/+0x24/-0x24 conventions anywhere in
post.bin. Conclusion: the lui %hi reloc does NOT resolve to the
post.bin data base; the true table lives wherever the BOOT-TIME
game_libs reloc processing maps it (possibly a heap-built table or
another section). UNLOCK PATH: RE the kernel's game_libs loader
(the reloc records at the segment tail -- 3-word (0x62-type, offset,
count) records decoded during the relayout ledger work) to learn the
hi16 resolution, THEN extract. Until then the dense-table fns keep
their approximate synthesized tables (graft items 12/16).

Addendum (4118): (17) GRAFT-VS-HAND-BODY crossover -- a full m2c graft
reliably beats stub/skeletal bodies (<40%: +14..+50pp observed) but
LOST to a 49.2% hand body (scored 48.1; m2c mixed ./->unk chains and
approximate tables cost more than the tail coverage gained). Rule:
below ~40% graft; above ~45% refine the hand body (LCS the gaps,
decode just the missing blocks). Always score-and-compare BEFORE
committing a graft over a hand body (monotonic rule). REFINED (4948):
the crossover is NOT purely %-based -- a 14.79% body beat a fresh
graft (14.60) because it already captured the m2c-equivalent skeleton.
The tell: graft score ~= existing score means the existing body IS
m2c-equivalent and the divergence is structural (register/shape/tail)
-- regeneration cannot help; only hand work moves it. The tell holds
at BOTH ends of the scale: at ~5% (4FD18: hand 4.56, fresh graft 5.30)
it means something STRUCTURAL is broken (caller-set regs, unalignable
shape) -- diagnose the mechanism, don't regenerate.

Addendum (B3C): (18) m2c "Label .LX refers to a delay slot" -- IDO
branch-likely targets another branch's delay insn. Fix iteratively:
move the label off the delay insn, add a continuation label right
after it, retarget the offending branch to an appended tail block
[duplicated delay insn; b continuation]. Loop until m2c passes (B3C
needed 3). FIXER GOTCHA (6E224): blanket deref-cast sweeps can match
their OWN OUTPUT across iterations, producing runaway chains
(*(s32 *)(s32 *)(s32 *)... ). Guard sweeps with (?<!\*\)) style
negative lookbehinds or collapse afterwards with
re.sub(r'(\*\(s32 \*\))(\(s32 \*\))+', r'', s). (19) m2c pointer-typed locals compared/arith'd with ints
need (s32) cast sweeps -- expect "Unacceptable operand of ==" tails.

Addendum (31F4C): (20) GRAFT PRE-FILTER -- if the disasm shows branch
targets far outside the fn (0x400xxxx-class) or backwards past the
start, dump the raw words first: 0x40xxxxxx = mfc0/mtc0 (CP0) words
that objdump renders as bogus branches. CP0 + zero-pad lead-ins +
busy-wait bne loops + cross-symbol backwards branches = a HANDWRITTEN
system block (permanent INCLUDE, reference_1080_mips3_runtime_helpers
class), not a splat fragment -- do not graft, merge, or decode. Caught
at game_libs [0x31DF8..0x32884) after one wasted m2c attempt; the
pre-filter costs one objdump grep. EXTENDED (6A5F0): k0-register
trampolines (3C1A/275A/03400008 = lui k0/addiu k0/jr k0) + sd/ld
64-bit saves (FFxx/DFxx opcodes) + CP0 density = the __osException
handler family -- same permanent-INCLUDE verdict, one more fingerprint
the pre-filter catches before m2c runs.

Addendum (2E354 refinement, +20pp 45->65 over a stale m2c graft): (21)
FIELD-WIDTH RETYPE FROM THE ASM ACCESS CATALOG is the single biggest
post-graft cleanup class for struct-heavy fns -- m2c types EVERY
`->field` deref as `s32`, but the target reads many fields as byte
(lbu/lb/sb), half (lhu/sh), or float (lwc1/swc1). A naive `lw` where
the target has `lbu` mis-shapes the whole block (a byte field read as a
32-bit at an unaligned offset emits `lwl/lwr`/`swl/swr` PAIRS -- the
unaligned-access tell). RECIPE: derive a per-offset width map straight
from the target asm in one pass --
`disasm-raw.py FN | grep -E '\b(lb|lbu|sb|lh|lhu|sh|lw|sw|lwc1|swc1)\b.*\(BASEREG\)'`
then bucket op->{b,h,w,f} per offset -- then regex-rewrite each
`*(s32 *)((char *)(arg0) + 0xNN)` to the catalog's type (u8/s8 for
lbu/lb, u16 for lhu, f32 for lwc1). Mixed-width offsets (e.g. a slot
both lw and lwc1 = int/float union, or both lb and lbu) stay s32 / pick
the dominant -- only retype the UNAMBIGUOUS ones. This one mechanical
pass was +17.9pp alone. (22) GLOBAL-BASE TABLE READS: m2c emits
`*(s32 *)((char *)(reg) + 0xBIGOFF)` (reg = scaled index) and bare
`*(T *)0xADDR` absolute derefs; both materialize the address with
`lui+ori` (immediate). The target uses `lui hi + addu index + lwc1/lw
lo16(at)` (a GLOBAL base, hi/lo split, lo possibly negative). Rewrite
to `*(T *)((char *)&D_00000000 + 0xBIGOFF + index)` (and bare derefs to
`((char *)&D_00000000 + 0xADDR)`) so IDO does the hi/lo split; +0.8pp
each here, and retype the table element to f32 if the target loads it
with lwc1 (kills an m2c-inserted lw+mtc1+cvt.s.w int->float dance).
Pointer ADDRESS args passed to callees (`lui a1,0x2; addiu a1,a1,-N` in
the target = `&D + (0x20000-N)`) likewise need `(s32)((char *)&D + off)`
not a bare `0xADDR` immediate. CEILING NOTE: after these, measure
OPCODE-ONLY LCS (registers/operands stripped) vs target -- if the shape
ratio is still <~60% (2E354: 56.9%), the residual is STRUCTURAL (here:
the two synthesized approximate jumptables + FP-expression grouping in
the loader-RE-gated dense-table body), NOT regalloc -- permuter and temp
coalescing CANNOT move it (coalescing a/v merges even REGRESSED -1pp,
44F4-class), and the spill-home frame bloat (272 vs 128) is a SYMPTOM of
the wrong deep-body shape, not a fixable cause. Stop at the
semantic-cleanup ceiling; the rest waits on true table extraction from
the USO reloc records.

Addendum (3BE1C): (21) m2c can leak the literal `sp` stack symbol as a
pointer base (`*(s32 *)((char *)((sp + idx*4)) + 0xBC)`) when the fn
indexes its own stack frame as an array -- there is no C-expressible
equivalent under the graft conventions, so placeholder it with a
MARKED &D read (`/* sp-leak placeholder */`) and treat the marker as a
refinement site (the true form is a local array; declare one when
hand-refining). Also new mopped classes: hex-base `(void *)0xNNN->unkM`
(now in the cleaner), halfword *6-stride record reads (s16), and
comma-expression embedded stores.

Addendum (CI incident, 6B0FC/5A2CC): (22) GRAFT-PLACEMENT SAFETY --
when grafting onto a BARE INCLUDE (no existing wrap), rfind-based
'#ifdef'/'#else' anchors can match a PRECEDING function's wrap and
REPLACE THAT NEIGHBOR'S BODY silently (two wraps clobbered before CI
caught it). Rules: (a) after inserting, verify the new body's next
'#else' pairs with the SAME function's INCLUDE (one regex check);
(b) the local NM gate MUST be from-scratch (rm -rf
build/non_matching) after any wrap-structure change -- incremental
builds mask asm-processor's "symbol defined twice" that CI's clean
build hits; (c) the wrap-pairing audit (body -> next #else -> next
INCLUDE must name the same fn) across all touched fns costs seconds
and would have caught both. (d) EXTENSION (36224): an INCLUDE inside
an EXISTING wrap's #else accepts a nested insert that compiles but is
DEAD CODE (inner #ifdef NM inside outer #else never fires) -- the tell
is a perfectly FLAT score. Check for an enclosing wrap (is the nearest
preceding unmatched #ifdef/#else pair open?) before any insert.

Addendum (kernel 5C50): (23) KERNEL BOUNDARY CAVEAT -- the kernel
relayout verified SECTION bytes, not internal symbol boundaries;
unmatched kernel INCLUDEs still carry splat's boundary guesses. Tell:
a named jumptable whose ROM-true entries (readable directly from the
byte-exact ROM at VRAM-0x400+0x1000) land inside ANOTHER symbol's
span, and/or neighbors starting without prologues (bnez first insn =
fragment). Such regions need a boundary-merge analysis before any
graft/decode -- the kernel's symbolic .s feeds m2c directly once
boundaries are right (no raw-word pipeline needed there). METHOD
(5C50 region, 2026-06-10, CORRECTED): derive the TRUE function map
from the byte-exact ROM, but take the ROM offset from the .s
comment's FIRST FIELD (/* ROMOFF VRAM WORD */) -- NEVER from a VRAM
formula (two wrong bases produced a phantom 7-fn map + a paradox
before the field-1 check; kernel text is ROM = VRAM - 0x7FFFF000 in
this ROM, and DATA has a different offset). Outcome: splat's
boundaries are mostly right; 5C50 = [0x5C50..0x6110) with the
prologue-less 60F0 folded in; the region is a debugger command
dispatcher whose jtbl_8000A770 symbol actually points at ASCII
command names via the TEXT formula -- the true handler table needs
the DATA-segment mapping from tenshoe.map.

Addendum (1304C pass 7): (24) M2C GOTO-LOOP SNAPSHOT = PHANTOM S-REG.
When m2c renders a nested loop as goto-loop_N spaghetti, it can
materialize a SNAPSHOT local of a loop variable (taken before the
inner loop, compared at the back-edge) that the original C never had
-- the build then saves an extra callee-saved pair (move sN,tX +
bne sN,tY back-edge is the asm tell; prologue saves N+1 s-regs vs
target N with a SMALLER target frame... or larger if the original
kept values on the stack). Diagnose: disasm the build, find each
extra s-reg's first def; if it's a `move sN,<other loop reg>` right
before an inner loop, it's the snapshot artifact. Fix = re-derive the
nest as clean for-loops (score-volatile; do it in a focused pass, not
a cadence tick). VALIDATED on the source case (1304C pass 8): nested
fors + row<<5 recompute killed BOTH the snapshot s-reg and the offset
accumulator; register set matched the target exactly; +1.4pp
(86.32->87.76) and -0x20 frame in one edit.

Addendum (20A28): (25) `M2C unset $fN` / `M2C unset $vN` markers in
m2c output = CALLER-SET REGISTER detector -- the fn reads a register
the caller leaves set (here $f0 multiplied at 4 sites). IDO C cannot
express it: permanent structural cap (the caller-set-reg class, float
variant). Do NOT graft such output: m2c renders the read as `* 0`
placeholders, IDO constant-folds the expressions away, and the result
goes fuzzy=None (undersized/unalignable). Keep the existing measurable
body, classify at the wrap. Add `grep "M2C unset"` to the post-m2c
pre-filter alongside the 2.1474836e9f check. CORRECTED (47B40): run
the grep on the CLEANED output (or both) -- the raw m2c file can carry
the marker in a form the simple grep misses while the cleaned body
shows `/* M2C unset $t6 */` inline; 47B40's $t6+$f4 caller-set
markers slipped past the raw-file grep and were caught by eye in the
cleaned head.

Addendum (26D64): (26) M2C DUFF'S-DEVICE CASE FALL-INS -- on dense
dispatchers where a case head is also a branch target from another
arm, m2c emits `case 0xNN:` labels INSIDE else-branches or OUTSIDE
the switch's closing brace ("case or default label appears outside a
switch statement"). Flatten to a comment + duplicate the arm's logic
in place (the fixer's flatten rule). Costs structure: the target's
true shape is a goto-into-switch / shared-arm form, so expect a
modest score (26D64: 3.74->19.58 only). Also new cleaner classes:
(bitwise s8/s16) -> plain int casts, (bitwise uN) -> (uN).

## Reading the uoptlist global-coloring section (15F0 trace, 2026-06-10)

The -Wo,-zdbug:6 dump's tail (after "reg alloc preparation") is the
global coloring log, one line per candidate decision:
  `  90:   90 assigned (constrained)   3`
= candidate(live-range) 90, live-unit 90, got REGISTER 3 by a
CONSTRAINT (copy to/from a precolored node), where the number is the
MIPS register index (2=v0, 3=v1, 4-7=a0-a3, 8-15=t0-t7, 24=t8).
`live range 90: 90 split out 113` lines show live-range splitting;
`not colored (-ve save)` = spilled (negative save = not worth a reg).
For 15F0: the contested src temp IS candidate 90 -> reg 3 ($v1)
"(constrained)" -- v1 is forced by a constraint edge, not a free pick;
the C-side levers fail because they don't break that edge. Next: find
which copy creates the constraint (the candidate table's isop lines
referencing {90|x}) and restructure THAT expression. This makes the
temp-pool renumber class mechanically diagnosable: dump, find the
contested candidate's "(constrained)" line, trace its constraint
source. DEPTH 2 (15F0): live-range IDs in the coloring section are
SPARSE (14 ids vs finalnumlr=16 -- they are lr ids, not dense
indices); "(constrained) R" is a CONSTRAINED-POOL pick where v1
precedes t0 in the preference order for non-call-spanning temps. A
target coloring t0 where the build picks v1 therefore implies the
ORIGINAL's lr spanned a constrained point the rebuilt one doesn't --
the diagnosis question becomes "what made the original lr longer/
constrained", answerable only with uopt allocator internals
(preference-order + constrained-point semantics). Open research item;
candidates: ido-static-recomp uopt RE notes, community uopt source.

## Permuter scratch: hand-rolled target.o scores TU-WIDE (27BC attempt)

A hand-built permuter scratch (base.c + the expected TU .o copied as
target.o + function.txt) RUNS but the diff metric covers the entire
TU (~247k base score for a 2-insn gate = meaningless signal; the
"improvements" it logs are noise elsewhere in the TU). The target.o
must contain ONLY the target function -- use
tools/decomp-permuter/import.py with the PERMUTER=1 Makefile mode to
build the scratch properly (import.py extracts the per-fn context and
target). function.txt alone does NOT scope the diff.

## m2c spXXX local names ARE the target's frame offsets (578B4 pass 1-2)

In m2c graft bodies, the generated stack-local names encode the
TARGET function's frame offsets directly: `sp1EC` lives at frame
offset 0x1EC, matching the target's `sw v0,492(sp)`. So the target's
true stack layout (which locals are real frame slots, and the frame
size = highest spXXX + width, rounded) is readable straight off the
m2c output -- compare against the BUILD's `addiu sp,sp,-N` to measure
spill-pressure delta precisely (578B4: target 496 vs build 1256 =
the ~400 m2c SSA temps' overflow).

CAUTION -- mass single-hop temp inlining BACKFIRES: inlining 59
call-free single-use temps (of 398) grew the frame 1256 -> 1576;
recompute duplication creates MORE pseudos than the temps it removes.
The inline-recompute lever works per-hot-variable, not en masse. For
chained-SSA temp populations: block-scoping is ALSO DEAD (pass 3:
scoping all 395 temps into innermost blocks left the score flat and
GREW the frame 1256->1504 -- C scope does not inform uopt frame
allocation). The only remaining instruments are per-arm hand rewrite
against the .s, or re-emitting m2c with different folding flags.

## m2c --reg-vars all: the temp-collapse instrument for big grafts (578B4 pass 4)

For m2c graft bodies drowning in SSA temps (578B4: 398 temps, frame
+760B over target), re-emit with `--reg-vars all` -- one variable per
register instead of per-SSA-value (398 -> 36 temps + ~55 var_ decls,
directly mirroring the target's register allocation). Pipeline:
`python3 scripts/disasm-func.py <fn> --obj expected/<unit>.c.o` (the
TARGET .o -- default obj is the BUILD, wrong frame!) -> `uv run m2c
--target mips-ido-c --reg-vars all` -> `m2c-graft-clean.py <out> <fn>`.
CAVEAT: the emit has ~30 type-conflict sites (a register var used as
both int and pointer; s16 var assigned 0x20000). Do NOT blanket-retype
to s32 -- that breaks m2c's pointer-arithmetic scaling (578B4 scored
56.8 vs the 75.0 graft). Fix conflicts site-by-site preserving m2c's
types: switch-expr casts, deref casts at the conflicted uses only,
s16->s32 widenings where the assigned value overflows. (An iterative
error-driven fixer works: parse cfe error lines, apply the matching
cast at that line only, rebuild; 578B4 converged in 3 iterations.)
OUTCOME CALIBRATION (578B4 pass 5): the two emits err in OPPOSITE
directions -- SSA graft 75.0 with frame +760B (structure-faithful,
spill-heavy); reg-vars 53.1 with frame UNDER target (allocation-
faithful, structure-drifted: register-transfer statements add moves
and shift control-flow placement). NEITHER is a drop-in for a big fn;
use the SSA emit for structure and the reg-vars emit as the
allocation reference during per-arm hand rewrites. PREMISE CHECK
(pass 6): a hand rewrite of one switch arm with 5 reused locals (vs
~21 SSA temps) was CODEGEN-EQUIVALENT -- IDO coalesces short-lived
within-arm temps on its own, so SSA temp COUNT is not the frame-
pressure source. For a big-fn frame delta, do NOT assume temps:
run the uoptlist occupant trace (-Wo,-zdbug:6) and map the EXTRA
frame slots to their C variables before choosing a transform.

## Hybrid emit (m2c temp coalescing): the spill-home frame-bloat fix for big SSA grafts (578B4 pass 7, 2026-06-11)

THE DIAGNOSIS (closes the pass-6 open question): a big m2c SSA graft's
frame bloat (578B4: build 1280 vs target 496) is spill HOMES, not
register pressure. The -zdbug:6 dump showed 142 of 483 uopt candidates
"not colored (-ve save)" -- each such web reserves a per-VARIABLE home
slot in the frame even when the emitted code barely touches it (the
1280B frame had only 48 distinct slots accessed). The target frame, by
contrast, is 100% named m2c spXXX locals: every target sp-slot maps to
an spXXX name, ZERO anonymous spill slots -- the original's webs all
colored.

THE FIX: `scripts/m2c-hybrid-emit.py` (monorepo root) renames m2c
temps of the same register whose textual live ranges ([first-assign,
last-use] lines) don't overlap into one shared variable, preserving
each temp's exact type (same-(reg,type) groups only; never retype).
Safety: m2c temps are SSA and per-path execution order == textual
order in loop-free structured bodies, so disjoint textual ranges can
never clobber; ranges partially intersecting a loop span get expanded
to the whole span; goto/label bodies are refused without --force.

RESULTS (gl_func_000578B4, 9.7KB, src/game_libs/game_libs_post0b.c):
  --regs a0,a1,a2,a3,v0,v1,t1,t2,t3,t4,t5,t8 --include-vars --pad 2
  => fuzzy 75.07 -> 81.22, frame 1280 -> 496 EXACT, not-colored webs
  142 -> 90, insn profile converged (build 2423 vs target 2419 insns;
  sw 347/348, lw 581/586).
CALIBRATION -- coalescing is NOT codegen-neutral (uopt candidate count
drops ~4x; webs join), so tune per register class against the score:
a/v merges were the big win (+4.7pp), t1-t5/t8 score-neutral but
frame-shrinking, --include-vars (var_ phis, same textual rule) +1.0pp,
volatile --pad to the exact target frame +0.01pp; t0 (the dense
bitfield-pack scratch) and ra merges HURT (-5.2/-2.5pp) -- exclude any
register whose merge drops the score.

WHERE IT DOES NOT PAY (game_uso_func_000044F4, 4.7KB): the in-tree
hand body (79.57) already has the target frame (232/232) -- no
spill-home bloat to reclaim. [RESOLVED 2026-06-11: 44F4 closed at
100.0 via the struct-by-value marshalling rewrite -- see
docs/IDO_CODEGEN.md "STRUCT-BY-VALUE MARSHALLING"; the residual was
semantic (struct args/sentinels/fail-edges), not spill homes.] A fresh SSA graft scores 51.2 (frame
544); on it, v0-temp coalescing is score-NEUTRAL (frame 544->368) and
s-reg phi coalescing (var_s0 stanza pointers, callee-saved,
call-crossing) CRASHES the score to 39.1. Hand body kept. Rule: the
lever applies when the residual is frame/spill-home bloat (SSA-temp
mass + "not colored (-ve save)" dump lines); it does NOT fix
structural drift, and it makes callee-saved phi-webs WORSE.

REMAINING GAP on 578B4 (81 -> 100 path): mnemonic stream is 90.6%
aligned; residual = ~250 register-coloring diffs + ~125 sp-slot-OFFSET
diffs + structural drift. uopt home assignment is NOT pure decl order
(probe: sp50 lands at 244 vs target 80 even at matching frame size),
so per-slot home alignment needs uopt layout RE (open) or per-arm
register-shape rewrites.

## 578B4 pass 8: slot-map closed via decl-order relayout + per-arm web splits (81.52, 2026-06-11)

The pass-7 "open" home-order question is SOLVED — full rule + frame
budget in docs/IDO_CODEGEN.md "FRAME-SLOT HOME ASSIGNMENT RULE".
Applied to 578B4: every memory-resident web now homes at its target
offset (sp-offset histogram exact at 32-492, frame 496); exact-word
LCS 467 -> 875/2419, fuzzy 81.22 -> 81.52 committed (agent-w).
RECIPE for a big graft:
1. Decode target slot map from m2c spXXX names; required frontend addr
   = offset - framesize. Reorder ALL decls so each spXXX sits at its
   addr (4 bytes/slot from -4 down; colored vars are free gap fillers;
   volatile pads top up; keep total span <= the frame budget).
2. SPLIT shared webs: one C var = one home. m2c's per-arm copies
   (`spFC = temp_a2;`) are copyprop'd away — RENAME the arm's temp to
   the spXXX var (def + arm-scoped uses, delete the self-copy). The
   web then homes (colored caller-save OR uncolored) at its own decl
   slot.
3. Selector-CSE trap: `switch(x)` + `FW(...)` re-read of the selector
   in the default arm CSEs into one dispatch->default web = anonymous
   temploc below the locals (frame +8/+16). Break it: assign the
   re-read to a VOLATILE named local in the default block.
4. Target dead stores (sw with no load) = volatile named local.
5. m2c phantom call args (extra `move a1,a3` before a call whose extra
   arg m2c hallucinated): drop the arg; K&R externs don't care.
NEGATIVES (don't repeat):
- Per-arm renames of the switch-1 t1-pointer (temp_t1_3 -> 4 arm vars)
  cascade-regressed the ugen scratch rotation across all arm bodies
  (-300 LCS words) even though the homes were right. Interaction-only
  effect: single-group ablation showed 0, removing all four showed
  +309. KEEP shared temps when per-arm split regresses; pin the shared
  decl at the FIRST arm's slot.
- goto-label dispatch (to reproduce the target's unsorted beq chain;
  build's switch sorts comparisons ascending) collapsed LCS 875->307.
  if-else chains inline arm 1 behind bnel. Keep the plain switch.
- Statement-order and +-operand-order swaps in arm bodies: codegen
  no-ops (uopt GCM reorders).
MEASUREMENT GOTCHA: objdiff fuzzy weights an sp-offset-only sw/lw diff
near zero — ~70 offset fixes moved fuzzy +0.02 but LCS +116. Track
big-graft progress with an exact-word LCS + sp-offset histogram
(decode sw/lw base=sp), not fuzzy alone. jal words always differ in a
.o (unfilled relocs) — exclude ~30 from any byte count.
REMAINING to 100 (in the wrap comment too): ~250 scratch-rotation
coloring diffs in switch-1 arms 2-5; 4 webs the target SPLIT-spills
mid-arm (spF0/spB8/sp9C/sp80) but we keep colored; var_a2 tail web;
dispatch comparison order; prologue scheduling pair-swaps.

## references/ido: the decompiled uopt source + dump-flag instrumentation (2026-06-11)

`references/ido` = local clone of github.com/n64decomp/ido — the IDO
7.1 uopt (ucode global optimizer, the register allocator) decompiled
to C WITH ORIGINAL Pascal procedure names (`globalcolor`,
`compute_save`, `spilltemps`, `makelivranges`, `linearize`,
`gettemp`, ...). This is the primary instrument for "allocator cap"
questions — grep it before theorizing. The full derived-rules writeup
(algorithm, priority function, slot assignment, addu operand order,
cfe call-result temps, dead-local frame persistence) lives in
docs/IDO_CODEGEN.md under "uopt internals (allocator opened)".
Companion instrumentation, all standalone-cc compatible:
`-Wo,-zdbug:1` (itab: binary-op operand order + `isvar M 3 -N` local
homes), `:2` (post-reemit), `:5` (regalloc dataflow), `:6` (coloring
trace), `-Wo,-dowhyuncolor`, pass kill-switches `-zcopy:0 -zcomo:0
-zstor:0 -zscm:0`, and `-Wo,-zmovc:N` (move-cost knob). Dumps land in
`./uoptlist` (cwd-relative; needs the ecvt patch in
tools/ido-static-recomp/libc_impl.c — re-apply after clean checkout,
see the regalloc-dump memo). The repo also ships `udb.py`, an
interactive ncurses debugger over the decompiled uopt (32-bit build
required) — not needed so far; the dump flags cover slot/coloring
forensics.

## Jumptable-resolved decode: m2c lost-base array derefs need &D_00000000 patch (func_00010FEC)

The jumptable vein workflow: `extract-uso-jumptable.py <fn> --module 0xD9FE28
--vaddr 0xV --size 0xS` (shim 0x1466C for game_libs-in-bootup, 0x0 for
bootup_uso direct) -> `uso-jumptable-to-m2c.py <expected.c.o> <fn> 0x<ooff>
--vaddr --size` (ooff = fn offset in objdump -d of the matching .o) -> emits a
jtbl-labeled .s -> `m2c` resolves the computed `jr` into a switch.
GOTCHA: m2c often emits lost-base array accesses as `*(arg1 * 4)` (the table
base resolved to 0). These won't compile ("Dereferenced a non-pointer"). Patch
each to the &D_00000000 placeholder form: `*(s32 *)((char *)&D_00000000 + arg1
* 4)`; for NESTED forms `*(*(arg1*4)*4)` replace the inner first, then the
outer (ordered). This made func_00010FEC compile + score 30.8->36.2 (the switch
resolution itself is the gain; the &D base derefs are approximate, not exact).
DELAY-SLOT CAVEAT (from the tool docstring): m2c rejects a label in a branch
delay slot — skip or hand-patch those functions.

## objdiff fuzzy_match_percent OVERSTATES exact-byte progress on big functions — use it to rank, not to estimate remaining work (2026-06-20)

objdiff's `fuzzy_match_percent` (the report.json/decomp.dev per-function number) is a
BLOCK-ALIGNED fuzzy score: it credits structurally-similar chunks even when they're
positionally displaced. For large functions this badly overstates how close you are
to a byte-exact match. Measured this batch: `gl_func_0001E134` showed **57.2% fuzzy
but only 1.65% exact-byte** (7.6% of mnemonics aligned in order) — the 57% was
entirely block-level credit for displaced chunks. A m2c graft with the wrong frame
size + wrong caller-arg→saved-reg coloring routinely scores 50-65% fuzzy while being
nowhere near landable.

CONSEQUENCES for the mid-band decomp marathon:
- The 40-90% fuzzy band is the bulk of unmatched code, but a function's fuzzy% is NOT
  a reliable "how much work is left" gauge. A 57% function may need a near-total
  rewrite; an 88% function may be 2 frame words away.
- To gauge REAL closeness, measure exact-byte: build the matching path + word-compare
  vs target .s (or count in-order mnemonic alignment), not the fuzzy field.
- matched_code / the headline 18% IS honest — it counts only whole-function exact
  matches (episodes). Only the per-function fuzzy% is inflated.
- Picking: use fuzzy% to RANK candidates within a segment (higher = generally closer),
  but expect big mid-band functions to need MULTIPLE passes + permuter, and expect a
  meaningful fraction (caller-arg coloring class, per caller_set_int_reg_cap memo) to
  floor below 100% no matter the structure. Budget accordingly — this is a marathon of
  hundreds of multi-pass functions, not a near-miss mop-up.

## disasm-raw.py dropped pinned jal/lui reloc-alias lines from raw-.word .s (FIXED 2026-08-22)

Raw USO `.s` files under `asm/nonmatchings/` contain two line kinds: plain
`/* OFF ADDR WORD */  .word 0xWORD`, and PINNED reloc aliases whose word lives
only in the trailing comment:

    jal mgrproc_uso_func_055904   /* 0009C0 0C000000 -> mgrproc_uso_func_055904 */
    lui $v0, %hi(import_800201CC)   /* 001B68 3C020000 -> import_800201CC */

`scripts/disasm-raw.py`'s original loader was a whole-file regex for
`.word 0x[hex]{8}` — pinned lines produced NO word, so every pinned call/lui
was silently dropped and all subsequent offsets shifted -4. Any agent decoding
a pinned-reloc function from its output saw a fiction (missing calls, wrong
branch targets). ~2106 pinned `jal` + ~1399 pinned `lui` lines exist across
the 1080 tree, so this affected a large share of USO functions.

Fix (2026-08-22, agent-h): parse line-by-line; pinned lines take the word from
the `/* OFF WORD -> sym */` comment and record the symbol, so the output shows
`jal <real_callee>` (and `--m2c` emits real callee names, not `func_000000`).
`scripts/disasm-raw.py --selftest` is the regression check: a synthetic .s with
pinned jal+lui lines must round-trip at 7/7 insns with correct offsets.

Rule: if you decoded a USO function with pre-fix disasm-raw output and the
reconstruction "mysteriously" missed calls or had -4-shifted branch targets,
re-derive from the fixed tool before concluding anything about the function.

## Toolchain forensics: every IDO-family toolchain we can run, and what each 1080 "proven cap" really is (agent-c run 349, 2026-11-12) <a name="toolchain-forensics-run349"></a>

**Question.** Finished IDO decomps (OoT, Paper Mario) have no "impossible" functions. Their apparent caps turned out to be
(a) a different compiler / flags, (b) original hand-written asm, (c) a post-compile patch (OoT iQue `driverominit.o`,
`oot/tools/patch_ique_driverominit.py`), or (d) a wrong decode. This run checked 1080's caps against every toolchain we
could get.

**Inventory (local + downloaded).**
- On disk: IDO 5.3 and 7.1 static recomps (`projects/<1080>/tools/ido-static-recomp/build/{5.3,7.1}/out`; 7.1 has
  `NCC` + `edgcpfe`), and the original IRIX binaries under `tools/ido-static-recomp-dump/ido/{5.3,7.1}`. KMC GCC is Glover-only.
- Downloaded into `tools/forensics/` (untracked) from decomp.me's compiler bucket:
  `https://github.com/decompme/compilers/releases/download/compilers/ido5.3_cfront.tar.gz` and `.../ido4.1.tar.gz`.
  - `ido5.3_cfront` ships its own `qemu-irix`. It holds the IRIX 5.3 IDO (cfe/uopt/ugen/as1 are md5-identical to our 5.3; only
    as0 differs) plus two C++ front ends:
    - AT&T **cfront 3.0.1**: `usr/lib/c++/cfront`, which emits C.
    - SGI **Delta C++ = EDG C/C++ front end 2.19**: `usr/lib/DCC/edgcpfe`, which emits ucode. It is a different edg from
      7.1 NCC's.
  - The `CC` driver dies under qemu (sgisys 24). Drive the phases by hand. Run cfront directly as
    `qemu-irix -silent -L <dir> <dir>/usr/lib/c++/cfront +a1 +f<name> < in.ii > out.c`, then use any IDO cc.
  - Run DCC's edgcpfe with the argument list that `DCC -v` prints (make a symlink named `DCC` to `usr/bin/cc` and run it
    under qemu-irix), then run our uopt / ugen / as1 from either version. Scratch wrappers: `/tmp/claude-1000/c349/scripts/{dcc,cfront}.sh`.
  - `ido4.1` is ECOFF. Its bundled `qemu-irix-4.0` needs glibc 2.38, which this machine (2.35) does not have, so it was not run.
- NOT downloaded: decomp.me's `ido5.2`, `ido6.0` and `mips_pro_744`. decomp.me's own `cromper/cromper/compilers.py` pulls
  them from `github.com/LLONSIT/qemu-irix-helpers`, which is outside the approved source list. **Getting IDO 6.0 (and any
  7.2) is the one open lead for the jump-table family**, and it needs the user's OK on that source.

**Fingerprint results.**
1. **bootup 6204 / E9FC (`lui a0` above `sw ra`) = (d) decode, now EXACT.** Both are **edg static initializers**
   (`__sti__<stamp>`) for namespace-scope objects. The mechanism:
   - edg emits the __sti__ at the END of the TU, so its prologue carries the last source line.
   - The constructor call carries the object definition's earlier line.
   - So the argument `lui` outranks `sw ra` in as1. A C function can never do this, because its call cannot sit on a line
     before its own `{`.

   Details:
   - 6204 = `struct T { T(); }; T obj;`.
   - E9FC = `struct B { B(); int w[10]; }; struct Dv : B { Dv() {} virtual void v(); }; Dv obj;`. That is the base ctor
     call, then `obj.vptr = &vtbl` at +0x28. The ROM word is `AC2E0028`; splat's `func_00000008 + 0x20` was an artefact.
   - It needs at least one source line after the definition. With the definition on the last line you get `sw ra` first.
   - NCC also writes a 16-byte `.data` link record `{0, __sti__, 0, 0}`.
   - The __sti__ name embeds a compile timestamp. The Makefile renames it with
     `--redefine-sym $$($(CROSS)nm $@ | awk '$$3 ~ /^__sti__/ {print $$3}')=func_X`.
   - **Generalisation: look for prologue-order "caps" on tiny call-then-store functions. They may be compiler-generated
     (`__sti__` / `__std__` / vtable thunks), not user functions.**
2. **Backend version is NOT the cause of the as1 / ugen / uopt caps.** On standalone extracts that reproduce each residual
   (post0b 396FC bound-check steal, mgrproc 1824 `li at,1` fill, bootup E2D0 FP FIFO), we ran 7.1 cfe followed by every
   mix of 5.3 / 7.1 uopt, ugen and as1. All of them gave byte-identical objects.
3. **DCC (edg 2.19) does not explain the C++ near-misses.**
   - Our donors for 4B620 and 3B9C0 give identical words under DCC + 7.1 backend and under NCC.
   - 42938 is worse under DCC.
   - The float-heavy units (4FD00, 48AEC, 36694, 4BAF4) come out 4-8 words SHORTER and wrong under DCC.
   - The 65EE4 argument-order micro (`f(&G, G.base)`, -Olimit 1) gives the same `addiu a0` jal slot under DCC 5.3 / 7.1 and NCC.
4. **Jump tables (B3C / 8CD8 / 116C / 76F0 / 1ADC): still (a), with the toolchain unknown.**
   - None of the IDO 5.3 / 7.1-era front ends emits a 4-label table:
     - cfe 5.3 and 7.1 build tables only at 5 or more labels;
     - edg 2.19 (DCC) and 7.1 (NCC) never emit `xjp`;
     - cfront passes the switch through to cfe unchanged (8CD8's donor through cfront + cfe 7.1 gives a compare chain).
   - Why not hand-written (b): the targets use pure IDO idioms (`lui at; addu at; lw tN,%lo(at); jr tN; nop`, ugen's
     synthesised bound check).
   - Why not a post-compile patch (c): the table has exactly 4 words (kit CDXX), so a patch would have had to rebuild
     the table too.
   - **Lead: IDO's OLD pcc-derived C front ends `ccom` / `accom` use exactly the target's rule.** Both ship in IDO 4.1
     (`tools/forensics/ido4.1/usr/lib/{ccom,accom}`, ECOFF). Statically disassembled with
     `mips-linux-gnu-objdump -d -M no-aliases` (it reads ECOFF):
     - The genswitch is at ccom 0x401c80 and accom 0x402500. It is pcc's classic test:
       `range = hi - lo; if (range > 0 && range <= 3 * n && n >= 4)` build a table, otherwise a compare chain.
     - The table path then emits `lod` (0x52), `xjp` (0x8c) and `clab` (0x11) with length range + 1.
     - So a 4-label dense switch (0..3, or 1..4 in 1ADC) becomes a 4-entry table, and ugen synthesises `sltiu 4`.
       That is exactly the target.
     - cfe's rule never tables fewer than 5 labels. pcc's rule never tables a sparse switch like 2FB74's 21-entry
       [19..39], so 2FB74 is cfe and these five are not.
     - The IDO 5.3 and 7.1 drivers still carry `ccom` / `accom` / `oldccomflag` strings, but neither recomp ships those
       binaries, and no driver option we found (`-oldc`, `-Xoldc`, `-cckr`, ...) selects them.
     - **Confirmed by running it.** `qemu-irix-4.0` needs glibc 2.38. It runs on this machine through the loader and
       libc of the local Ubuntu 24.04 docker snapshot
       (`~/.local/share/docker/containerd/.../snapshots/2/fs/lib64/ld-linux-x86-64.so.2 --library-path <snap>/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu`)
       plus a 2-function glib shim (`g_assertion_message_cmpint`, `g_string_free_and_steal`) passed with `--preload`.
       Wrappers are in `tools/forensics/scripts/` (`q41.sh`, `accom.sh`; untracked).
     - The 4.1 cc driver's default C front end is `accom -Xprototypes -Xxansi`.
     - On a 4-case switch, accom ucode run through our 7.1 uopt / ugen / as1 gives
       `sltiu at,a0,4; beqz; sll; lui; addu; lw; jr; nop` plus a 4-word table, which is the target's head.
       accom's ucode is accepted by 7.1 uopt.
     - **kernel func_80001ADC under accom + 7.1 back end:** 134 / 134 words (cfe gives 139 without the phantom label).
       114 / 134 positionally-equal words (reloc fields masked), against 103 / 134 for the committed cfe NM under the
       same metric. The changes were:
       - drop `case 5:`;
       - drop the `+ 0 *` fold;
       - write `D_80012C44` as a function-pointer variable (the target calls it with `jalr`);
       - write the R_26 OR as `(sum) | (*p & 0xFC000000)`.
       What is left: the head's `andi a2` / `lw a3` order (uopt hoists `info & 7` into an s-register in every
       type-before-flags order), the HI16 arm's delay slot (`lh t4` vs `addu a2`), and a t6 / t7 / t8 rotation in the
       LO16 / R_32 arms. Best source: `tools/forensics/scripts/accom_1ADC_best.c`.
     - With the IDO 4.1 back end the code is longer: 137 words, with `lwl` / `lwr` for the `char *` struct loads.
       If it were accom at all, it would be with the 5.3 / 7.1 back end, not the 4.1 back end. The 76F0 result below
       argues against accom.
     - **titproc 116C under accom + 7.1:** native `sltiu 4` head after removing the phantom `case 4:`, at the same length
       (290 words). But all 10 vtable-call `this + off` adds come out `addu a0,v1,tN` against the target's (and cfe's)
       `tN,v1`. That is the same accom canonical order seen in 76F0, so it is evidence against accom here too.
     - **But game_libs 76F0 argues against accom as the original front end.**
       - Under accom + 7.1 its three tables come out native: `sltiu 6`, `sltiu 4`, `sltiu 4`.
       - Everything else gets worse than cfe: 447 / 578 aligned against cfe's 473 / 577.
         - Every `vt->e[k].off + self` add comes out `addu a0,s0,tN` where the target and cfe give `tN,s0`. Swapping
           the source operands does not help, because uopt canonicalises the accom ucode.
         - Three float tests come out `c.lt.s f2,f0` where the target and cfe give `c.le.s f0,f2`.
       - With the 4.1 back end it is 641 words.
       - So the original front end looks like a **cfe build with a 4-label table threshold**, which our 5.3 / 7.1 cfe
         lack. IDO 6.x cfe is the obvious candidate (decomp.me's `ido6.0` and `mips_pro_744` live at
         `github.com/LLONSIT/qemu-irix-helpers`, not yet approved).
       - accom 4.1 reproduces the switch rule but is not that compiler. Do not wire accom donors on this evidence alone.
       - Also: accom sorts compare-chain cases (2, 4, 3 becomes 2, 3, 4), the same as cfe.
     - Policy / infra question before landing anything: the build would need IDO 4.1 accom runnable. Options are the
       glibc trick above, a container, or a static recomp of the ECOFF binary, which ido-static-recomp does not support
       as-is.
5. **IDO 4.1 as1 (an older as1) removes both as1-order residuals, but it is NOT the original assembler.**
   - Reassemble 7.1 ugen output with the 4.1 as1:
     `q41.sh <4.1>/usr/lib/as1 -G 0 -p0 -mips2 -EB -g0 -O2 x.G -o x.o -t x.T`. It warns "version stamps wrong" but works.
   - For 396FC: no bound-check steal (`sll t7` stays in the slot, `or a0,a3` stays at the default head), and every
     other word is unchanged.
   - For mgrproc 1824: the `li at,1` pull disappears. But other blocks also schedule differently: 144 words against
     the target's 142.
   - Whole post0b object (asm-processor pre-pass, `cc -K`, then the .G through each as1): **167 of 902 functions
     differ** from the 7.1 as1.
     - Both sides were run without `-r4300_mul`, which the 4.1 as1 lacks. The 7.1 as1 with `-t5_ll_sc_bug
       -r4300_mul` reproduces the build's object exactly, 902 / 902.
     - Most of the 167 are exact today, so the 4.1 as1 is ruled out as the original.
     - The 7.1 as1 at `-O1` / `-O0` changes 350 functions, so it is ruled out too.
   - The 5.3 as1 is byte-identical to 7.1 on 396FC / 1824 / E2D0.
   - **as1 option fingerprint (7.1 as1, whole post0b, compared with the build object):**

     | as1 option | functions changed | 396FC fixed? |
     |---|---|---|
     | `-r4600` | 290 | no |
     | `-multi_issue` | 544 | no |
     | `-t5_mtc1` | 113 | no |
     | `-tfp` | 536 | no |
     | `-t5_r31` | all 902 | no |
     | `-t5_muldiv`, `-force_branch_fixup` | 0 | no |
     | `-r4200` | rejected | n/a |

     None helps 1824 or E2D0 either. A per-file as1 flag is ruled out for these residuals.
   - An as1 between 4.1 and 5.3 (decomp.me `ido5.2`, also on the LLONSIT host) is the only untested candidate.
     Gate any as1 candidate on a whole-object reassembly with zero exact-function changes.
6. **cfront as a 396FC explanation: negative.** The 396FC body through cfront + cfe 7.1 still steals `or a0,s0` into
   the bound-check slot, and the code shape changes (146 vs 153 words).

## Toolchain forensics II: IDO 5.2 / 6.0 and MIPSpro 7.4.4 (o32) tested against the 1080 caps (agent-c run 351, 2026-11-12) <a name="toolchain-forensics-run351"></a>

Follow-up to [run 349](#toolchain-forensics-run349). All three remaining decomp.me IRIX toolchains were downloaded and
run. **None of them is the original toolchain for any open function. Nothing was wired into the build.**

**Provenance.**
- decomp.me's compiler list is `github.com/decompme/compilers` `values.yaml`. Read at commit `2d480975`
  (2026-11-08), it pulls its n64 IRIX compilers from these LLONSIT URLs:
  - `ido5.2`, lines 88-91: `https://github.com/LLONSIT/qemu-irix-helpers/raw/refs/heads/n/qemu/ido5.2.tar.xz`
  - `ido6.0`, lines 109-112: `.../raw/n/qemu/ido6.0.tar.xz`
  - `mips_pro_744`, lines 127-130: `.../raw/n/qemu/mipspro7.4.4.tar.xz`
- `decomp.me/cromper/cromper/compilers.py` only names the ids. It does not contain any URL.
- Downloaded into `tools/forensics/dl_*` (untracked) and extracted to `tools/forensics/x_{ido5.2,ido6.0,mipspro744}`.
  No archive member has an absolute path or `..`. sha256:
  - `ido5.2.tar.xz` `870cd946d31d6abee24d47926328d15909771520240a0a4f5cb7d27aea90e1ad`
  - `ido6.0.tar.xz` `c56d4be020bdaf76310ceec455ebc0d443fb7a46c740491f74898b04f6a60356`
  - `mipspro7.4.4.tar.xz` `df33be0d9605b00b44070e567121fc00283a9b1f97763403f0898d2216028d24`

**How to run them.**
- Each archive's own `usr/bin/qemu-irix` works with the glibc 2.35 on this machine:
  `qemu-irix -silent -L <root> <root>/usr/lib/<phase> ...`. ido5.2's `qemu-irix-4.0` needs glibc 2.38 and is not needed.
- The 6.0 `usr/bin/cc` driver runs end to end.
- The 5.2 and 7.4.4 drivers (`usr/lib/driver`, run with `-0 cc`) run, but 5.2's cfe asserts under the driver
  (`main.c:155`). Drive the phases by hand instead, which works for every version: cfe, then uopt, then ugen, then as1.
- MIPSpro 7.4.4 o32 still ships the ucode chain (`cfe` / `uopt` / `ugen` / `as1`). It also ships
  `DCC/edgcpfe` = **EDG 2.29** (built Nov 2002); IDO 7.1 NCC is EDG 2.19.
- `ecfe` (in 5.2, 6.0 and 7.4.4) is EDG's 1.26 C-to-C translator, not a ucode front end. It needs `TMPDIR`, and
  under qemu it emits wrong case labels. Ignore it.
- 5.2 and 6.0 as1 do not know `-r4300_mul` or `-t5_ll_sc_bug`.
- Scratch wrappers live in `/tmp/claude-1000/c351/scripts/`:
  - `irix.sh in.c out.o FE BE [OPT] [AS]` mixes cfe / uopt-ugen / as1 from 52 / 60 / 744 / 53 / 71.
  - `ncc744.sh` and `dcc744.sh` run EDG 2.29 followed by the 7.1 back end.
  - `e71.sh` runs the 7.1 edgcpfe with extra flags.

**1. 4-entry jump-table family (B3C / 8CD8 / 116C / 76F0 / 1ADC): no available cfe makes a 4-label table.**
- cfe 5.2, 6.0 and 7.4.4-o32 all build a compare chain for a dense 4-case switch, and a table at 5. This holds at
  -O0 / -O1 / -O2 and in mixed back ends.
- 7.1 cfe gives the same at every -O / -g / -mips / -cckr / -ansi / -xansi level. None of the 31 cfe-private options in
  its strings changes it (`-cplus`, `-XF`, `-XL`, `-XQ`, `-XT`, `-XU`, `-Xh`, `-Xp`, `-dwopcode`, ...).
- **So the "IDO 6.x cfe with a 4-label threshold" hypothesis from run 349 is FALSE.**
- 7.1 NCC (EDG 2.19) never emits `xjp`. That holds for 4 / 5 / 8 dense cases, default / return / unsigned / enum /
  char / member-function switches, and -O0 / -O1 / -O2 / -g. None of the 62 single `-Z<c>` edgcpfe options changes it.
  **The code confirms it.** In the 7.1 edgcpfe recomp (`tools/ido-static-recomp-dump/build/7.1/edgcpfe.c`),
  `mbe_statement` sends EDG statement kind 9 to `func_51d740`, the switch lowering. That function writes ucode only
  through `ucw_write`, with opcodes 0x88 / 0x23 / 0x7f / 0x42 / 0x52, i.e. compare-and-jump plus one `lod`. It
  never writes 0x8c (`xjp`). It also contains no threshold test. 7.1 NCC simply has no table path, so no option
  can enable one.
  The same goes for 7.1 cfe (`build/7.1/cfe.c`). The cluster decision in `func_465d90` is `if (count < 5)`, with
  5 as an immediate, sending small clusters to the compare chain. Larger clusters reach `func_465654` and then
  `func_46508c`, which writes `xjp` (0x8c) and `ujp` (0x88). The threshold is hard-wired, not an option variable.
- **EDG 2.29 (MIPSpro 7.4.4 DCC) is the only compiler found with the target's rule.** It builds a table iff
  n >= 4 and the table size is at most 2n:
  - [0..3], [1..4], {0,1,2,5}, {0,1,2,7} and {0,2,4,6} get a table;
  - {0,1,2,9} and {0,10,20,30} do not.

  Its head is exactly the target's: `sltiu at,x,4; beqz; sw ra; sll; lui; addu; lw; jr; nop`, and for 1..4 it
  subtracts 1 first, as 1ADC does.
- **On the family's C-style bodies, EDG 2.29 + the 7.1 back end gives cfe's code plus native tables.** Each body was
  extracted standalone from the cpp output with `/tmp/claude-1000/c351/scripts/extract.py`, wrapped in
  `extern "C"`, with `()` prototypes turned into `(...)`.
  - **game_uso B3C: byte-exact standalone, with a native `sltiu 4`.** The phantom `case 4:` was removed, and two source changes
    were needed:
    - store `ob[0]` through `*(char **)((char *)ob + 0)`, because edg forwards a plain `ob[0] = tv`;
    - write `x == 1` instead of `1 == x` in one `&&` test.

    That leaves only the jump-table `%lo`, 0x4C against 0x50. It is a standalone layout artefact: the unit's first
    RoData word is game_uso_func_00000000's 1/6 literal. **With that literal function placed first
    (`/tmp/claude-1000/c351/b3c/y5.cpp`), B3C is 706/706 and 940 is 107/107.** Only the relocated `lui` / `jal`
    fields are masked, so `%lo` offsets and jump-table offsets are compared too. The result is the same with the
    7.4.4 and 6.0 back ends, so it does not depend on the back end.
  - **game_uso 940 (cfe-exact, tables 7 / 6 / 6):** unchanged under EDG 2.29, as above.
  - **titproc 116C:** a native `sltiu 4` once the phantom `case 4:` is removed. edg canonicalises `ptr + short` to
    ptr-first, which `(*(short *)(vt + 0x58) + (int)v1)` fixes. What is left is exactly the cfe NM's own residual set
    (v0 / v1 and a1 / v0 swaps) plus the `%lo` artefact.
  - **76F0:** the same picture. Drop both phantom `case 4:` labels and write the 16 vcall this-adjusts as
    `(char *)(vt->e[k].off + (int)self)`. Then all three tables come out native (`sltiu 6 / 4 / 4`), and what is
    left (122 diff lines, against cfe's 124) is the cfe NM's own residual set: the head `beqz` / `beqzl` and t / v
    register numbering.
  - **kernel 1ADC:** 116/134, the best of any front end (accom 114, cfe NM 103).
    - The flags test comes before the `value` / `type` reads.
    - edg drops unused locals, so a first-declared `s32 info; Sym *sym;` with a dead `if (0)` store restores the
      0x50 frame. The uninitialised hival / hiptr homes then land at 40 / 52, as in the target.
    - The residuals are where val's `lw` is scheduled relative to `sltiu`, the R_26 arm's store / delay order and
      a t6 / t7 / t8 rotation in the LO16 / R_32 arms. 18 load-order variants plateau at 116
      (`/tmp/claude-1000/c351/k3/fa_first.cpp`).
- **C-side consistency.** edgcpfe 2.29 also compiles C: `--c` is ANSI C, and `-K` / `--old_c` is K&R C, which promotes
  float to double. Whole cpp'd units in `-K` mode, compared with cfe:
  - titproc: 41 of 43 cfe-exact functions are identical. The 2 differences are K&R float promotion. In ANSI `--c`
    mode it is 42 / 43; that run needed `(void *)` casts on the 18 int-to-pointer assignments that ANSI edg
    rejects. The one left, 1E9C, is a decode lever: `int * volatile slot` used as `f(slot = expr, ...)`. edg
    re-reads the volatile after the store, and cfe passes the value through.
  - kernel: 46 of 51 identical, the same in `-K` and in ANSI `--c` (one call needed argument casts). 18F0 and 12BC
    differ only in `addu` operand order for ptr + int, which source order can fix. 0168 and 2250 differ in
    register colouring (a1 / v1, branch-likely shape). The edg ucode web order differs from cfe's for those cfe-tuned
    bodies. 2530 is not a cfe exact.
  - h2hproc: 34 of 37 identical. 15F0 and 17A0 are K&R double promotion; 9F8 is `addu` order.
  - gui: 34 of 37 identical. 25B4 is double promotion, 13E8 is `beql` operand order, and 3B14 is order plus a
    register shift.

  In total that is about 155 of 167 cfe-exact C functions byte-identical. The rest are:
  - K&R float-promotion artefacts of `-K` mode;
  - source-order operand placement (ptr + int `addu`, `==` operands);
  - edg's volatile re-read after assignment;
  - and a few register-colouring changes in cfe-tuned bodies (kernel 0168 / 2250, gui 3B14).

  So for C-style code EDG 2.29 is very close to cfe, plus the table-at-4 rule. Bodies that were fitted to cfe would
  need small re-spellings under an edg-family original.
- **But EDG 2.29 is ruled out as 1080's C++ compiler, by the unit gate and by date:**
  - Whole-file gate: all 214 non-NM NCC donors (`src/*/*_ncc_*.cpp` without `_nm`) were compiled with EDG 2.29 +
    the 7.1 back end at each one's own -O, and each .text was compared with the build's NCC object.
    - **121 are identical and 93 differ.** The 121 include all 7 `_o0_` donors and the 4 gui donors that need
      `-I src/gui_uso` (sentinel 4568 among them).
    - The differences include 13 game_uso donors (1DDC, 24BC, 28C0, 2CC8, 3558, 3AC0, 43D8, 57D8, 6A30, 6FA8, 71E0,
      97EC, BB8C), which surround B3C and 8CD8.
    - **EDG 2.29 does not inline inline functions that return a class by value**, such as `V3 operator*(float)
      const` and `XZ operator-`. It emits them as weak out-of-line copies (`__ml__2V3CFf`, `__mi__2XZCFRC2XZ`) and
      calls them. That holds with an explicit `inline`, with a named-return spelling, and under every single
      `-Z` / `-Y` / `-Q<c>` flag. EDG 2.19 inlines them, which produces 1080's three-hop copy chains. So 1DDC drops
      from 384 to 300 words (13 jals against 5), and the 8CD8 NM donor drops from 709 to 473 words (target 692).
      EDG 2.29 still inlines simple members (`dot`, `set`).
    - In member functions it also spills `this` to the stack and reloads it at every use. A free function with an
      explicit self pointer, as in the 116C decode, keeps it in a register.
    - 485C (2 words, argument scheduling) shows that even small exact functions change.
  - Date: EDG 2.29 was built in 2002, and 1080 shipped in 1998.
  - Both EDG 2.19 and EDG 2.29 emit `addu a0,tN,this` for virtual-call this-adjusts, the same as cfe and the target.
    So run 349's operand-order argument rules out accom but cannot tell cfe from edg.
- **Status: still (a), but the front-end family is now located.** The 4-entry functions were compiled by an
  **edg-based front end with SGI's `xjp` lowering (n >= 4, size <= 2n)**. For C-style code it is otherwise
  indistinguishable from cfe: B3C and 940 are byte-exact under EDG 2.29 standalone. It is not cfe (no cfe
  version tables 4 labels) and not 7.1 NCC (EDG 2.19 never tables). It is also not EDG 2.29 itself: that breaks
  about 93 exact C++ donors, and it dates from 2002.
  - The likely original is an SGI EDG release between 2.19 and 2.29, i.e. a MIPSpro 7.2.x / 7.3 DCC or NCC that
    keeps 2.19's copy chains but has the table lowering. It is not on decomp.me.
  - Is 1080 then one compiler throughout? cfe-exact C would also come out identical under it, given the C-side
    results above. Testing that needs that compiler.
  - No per-file toolchain is legal on the current evidence. **Do not wire EDG 2.29.** A B3C "exact" through it
    would be a fit from an anachronistic compiler.
  - **Per-unit gate, even if EDG 2.29 were allowed:**

    | unit | exact NCC donors | new exact from EDG 2.29 |
    |---|---|---|
    | kernel | 2 / 2 identical (1184, 598) | none (1ADC 116/134) |
    | mgrproc | 3 / 3 (23FC, 2B7C, o0_700) | none (1824 gets worse) |
    | titproc | no C++ donors | none (116C keeps the cfe residuals) |
    | game_uso | 13 differ | B3C |
    | gui | 0F04 (sentinel) and 3B80 differ | none |

    Where EDG 2.29 passes the gate it gains nothing. The only unit where it gives an exact is game_uso, and that is
    where it breaks 13 exacts. Both ways, nothing to wire.
  - The same table argument applies to whole units. 1824 (`sltiu 5`) and 396FC (`sltiu 6`) need tables, which cfe
    or a table-capable edg can give. Under NCC 2.19 their C bodies become compare chains (139 / 143 diff lines
    against cfe's 2), so they are not 2.19.
    - mgrproc's C++ donors come out the same under 2.19 and 2.29, so mgrproc cannot tell them apart.
    - post0b (game_libs) holds many 2.19-only donors next to 396FC. So if a unit is one TU, its compiler had both
      the table lowering and 2.19's C++ codegen: the same intermediate-EDG conclusion.

**2. as1 / back-end candidates for 396FC and mgrproc 1824: negative.**
- **post0b, whole object** (run 349's `post0b2.G`; the 7.1 as1 `-t5_ll_sc_bug -r4300_mul` oracle reproduces the
  build object):
  - 5.2 as1 changes 46 / 902 functions and 6.0 as1 changes 44 / 902. Most of that is the missing `-r4300_mul`,
    because 7.1 without it changes 40.
  - Compared with 7.1 without `-r4300_mul`:
    - 5.2 still changes 6 functions: 3CB00, **415A4**, 52674, 533EC, 5721C, **62F08**;
    - 6.0 still changes 4: 3CB00, **415A4**, 52674, **62F08**.

    The bold ones are sentinel exacts.
  - Neither touches 396FC.
  - MIPSpro 7.4.4 as1 is byte-identical to 7.1 (902 / 902).
- **post0b back end:** 6.0 uopt + ugen + 7.1 as1 changes 1 / 902 functions (5E288); 7.4.4 changes 0. 396FC is
  unchanged in both.
- **mgrproc, whole object** (asm-processor pre-pass, `-DNON_MATCHING`, `cc -K`):
  - 5.2 as1 and 6.0 as1 are byte-identical to 7.1 for all 42 functions, 1824 included.
  - 6.0 uopt + ugen are also identical.
  - 5.2 uopt (which reads 7.10 ucode as 3.18) changes 9 functions, 1824 among them (143 words).
- **65EE4:** `-O2 -Olimit 1` gives the same 146 words (95 / 146) under every combination tried: front ends
  5.2 / 6.0 / 7.4.4 / 7.1 with back ends 60 / 744 / 71, NCC 2.19 and EDG 2.29. Every version agrees, so the
  residual is not the compiler version.
  - The macro body expands onto one line. Splitting it into one statement per line drops it to 83 / 146, so as1
    line numbers do matter here. A greedy search over the 29 statement-boundary newlines (two starts, 89 evaluations,
    `/tmp/claude-1000/c351/e2/greedy.py`) peaks at the same 95. Line layout does not fix it.
- **Every IDO-family back end we can run (4.1, 5.2, 5.3, 6.0, 7.1, 7.4.4) is now ruled out for these residuals.**
- **Building through text assembly (ugen's `-K` `.s` listing reassembled by the 7.1 `cc`, i.e. as0 + as1) is ruled
  out too.** Kit LXXIX saw no `li at,1` hoist in 1824 under `cc -S`, but across the whole mgrproc object this route
  changes 25 of 42 functions (macro / `la` expansions and lengths), and 1824 becomes 156 words. It fails the
  whole-object gate.

**3. Sweep for compiler-generated functions among the open non-exacts (fresh target reads).**
- Every target is a single, correctly sized function: one prologue, `jr ra` at the end, and no mid-body prologue.
  This covers 396FC, 4B620, 4BAF4, 3B9C0, 4FD00, 42938, 48AEC, 36694, E68, E2D0, 1824 and 65EE4.
- None has the shape of an `__sti__` / `__std__` / thunk / vtable stub. E2D0 is an ordinary by-value Vec3 member body.
- 65EE4 is three straight-line copies of an init block on one global. A C++ inline-member version (`this` = &G)
  puts &G in s0 (106 words), while the target rematerialises &G at every use. So it is not a member expansion.
- 42938 opens with three edg function-local-static guards (`lw flag; bnez; sw 1,flag; ...`). Its `_nm.cpp` already
  models them.

**4. Jump-table census and the other residuals under EDG (run 351 follow-up).**
- **Census of every IDO-emitted table in `build/src/*/*.c.o`** (62 tables; `/tmp/claude-1000/c351/scripts/jtrule.py`):
  - The ROM has exactly five 4-entry tables, all dense (n = 4): 1ADC, B3C, 8CD8, 116C and 76F0.
  - Exact cfe functions that have 4 real labels in a wider range (40304 / 68990 / 343F4 / timproc_b5 87A0 / 4118,
    K = 6..8) already reach cfe's 5-label rule with in-range "phantom" labels on the default arm (e.g. 40304's
    `case 0x70: case 0x71: default:`). The edg rule would table those with 4 labels, so they do not discriminate.
  - Several exact game_libs `_o2_` split files have very sparse tables that the EDG 2.29 rule (size <= 2n) refuses
    unless they had many more default-arm labels: 2FB74 (K = 21, 5 non-default slots), 2BB7C (K = 41 / 97), 2C7A4
    (K = 113), 2E290 (K = 32) and 26790 (K = 16). That fits those split files being cfe-compiled C.
- **8CD8 is the deciding function.** It has a native 4-entry table (no EDG 2.19 build can emit one) AND edg by-value
  copy chains from inlined class-returning operators (EDG 2.29 calls those operators out of line: the NM donor drops
  from 709 to 473 words, against 692 in the target). Neither available EDG produces both. The target's only callees
  are 055750 (the `this == 0` operator-new guard of inlined ctors) and 071028, so its operators really are inline.
  EDG 2.29 puts every class-returning inline function (member or not, const or not, 2- or 3-float ctor) out of line
  as a local / weak copy. No single `-Z` / `-Y<c>[0|1]` flag changes that, and `--remarks` gives no inline
  diagnostic. Test any future EDG candidate on 8CD8 first.
- **game_uso mixes two switch-lowering regimes, so it is at least two TUs or front ends.**
  - **game_uso_func_000057D8 is EXACT under NCC 2.19 with dense `[1..7]` and `[0..3]` switches lowered as compare
    chains.** cfe would table the 7-case one, and EDG 2.29 tables both.
  - B3C has the identical `[0..3]` shape as a 4-entry table, and 940 has 7 / 6 / 6 tables.
  - So the same unit holds a no-table regime (57D8, EDG 2.19) and a table regime (B3C, 940, ECEC, 8CD8).
  - The evidence for the split is strong but not conclusive. 57D8 written as an if / else-if chain or a goto chain
    gives 88 words (target 84) under both EDG builds, so the natural source is a switch, but some other spelling
    could exist. Other "chains" flagged by a scan (E5C8 / E91C) are already if / goto source and do not count.
  - That would make it a front-end split inside game_uso, but its boundary is not located. A per-file toolchain
    would still need the table-regime compiler itself. cfe cannot do B3C, accom gives 940 82/107 and B3C 719 words
    on the same source, and EDG 2.29 cannot do 8CD8's inlining.
- **Other differences between EDG 2.29 and 2.19 on exact donors.** There are 25 same-length diffs, which do not come
  from the inlining difference:
  - more frame for temporaries: 38598 / 3D54C get frames +24, with the slots shifted;
  - different CSE base registers: 24BC, 1 word;
  - argument evaluation order: 485C.
- **396FC / 1824 / E2D0 through EDG 2.29 (extracted standalone, extern "C"):**
  - 396FC keeps exactly the cfe residual (`or a0,a3` stolen into the bound-check slot), plus 3 `mul.s` operand
    swaps that source order can fix.
  - 1824 still has the `li at,1` pull, plus new v0 / t9 colouring diffs (114 diff lines against cfe's 2).
  - E2D0 gets worse (200 against 26).
  - So these residuals depend neither on the front end nor on the back-end version.

**5. Integration plan, if the table-regime compiler is ever obtained (NOT wired).**
- **Gate first.**
  - It must reproduce B3C and 940 natively (EDG 2.29 already does).
  - It must reproduce 8CD8's inlined copy chains with a native 4-entry table.
  - It must leave every exact function in the target unit's split file byte-identical.
  - The split boundary must be located: which game_uso TU holds B3C / 8CD8 / 940 / ECEC, and which holds 57D8.
- **Running it.** Two candidates:
  - **ido-static-recomp.** It already recompiles IDO 7.1's dynamically linked `DCC/edgcpfe` (MIPS-I). A MIPSpro
    edgcpfe is MIPS-II, so the recompiler may need more opcodes. It gives a native, reproducible binary under
    `tools/ido-static-recomp/build/<ver>/out/`, with no qemu.
  - **Fallback: a pinned qemu-irix wrapper** in `tools/`, using that archive's own sha256-pinned `qemu-irix` (glibc
    2.35 works today). This works, but it adds a non-native step to the build.
- **Wiring.** Use the existing donor recipe: a `src/<unit>/<unit>_edgX_<addr>.cpp` (or `.c`) per function, built by a
  dedicated rule (`EDGX := ...`, the edgcpfe front end plus the 7.1 uopt / ugen / as1 with `-t5_ll_sc_bug
  -r4300_mul`), spliced with `REPLACE_FUNC_BODY` and the `<fn>_rodata` pin for the jump table (29CCC recipe). No
  container or system package is needed for either route, but it is still the user's call.

## Toolchain forensics III: MIPSpro 7.2 / 7.2.1 C++ (o32 edgcpfe, Aug 1997 / Mar 1998) against the 1080 caps (run 352, 2026-11-12) <a name="toolchain-forensics-run352"></a>

Follow-up to [run 351](#toolchain-forensics-run351), which guessed the original was "an EDG between 2.19 and 2.29 in a
MIPSpro 7.2 / 7.3". Period-correct MIPSpro 7.2 and 7.2.1 C++ front ends were found and tested. **Neither is the
original for the NCC donors. Nothing was wired into the build.**

**Where they came from.** All files are on discmaster.textfiles.com (public CD-ROM image browser, no login), each
file is fetchable raw at `https://discmaster.textfiles.com/file/<id>/<iso name>/<path>`. Downloads are in
`tools/forensics/dl_*` (untracked), extractions in `tools/forensics/x_*`.
- **MIPSpro C++ 7.2** CD (collection 9046, `SGI MIPSpro C++ 7.2.iso`, Sept 1997), `dist/c++_fe{,.idb,.sw}`
  → `dl_mipspro72cxx/`, `x_mipspro72cxx/`.
  - `c++_fe.sw` `0ca465c71d7dc6c51aaff422a6a542a88e433a57d0febde52c188846e604586d`
  - `c++_fe.idb` `1a281f8d681e33cf2e45326400532a6153c4e2c866be9a111eb98801d3a85074`
  - `usr/lib/DCC/edgcpfe` (o32, ucode-emitting; build path `v7.2/targ32_m2/edgcpfe`): banner "Edison Design
    Group C/C++ Front End, version **2.29**", built **Aug 29 1997**. sha256
    `48c06d7a4382b95e2defffb2f818a9a720d41900ae0f477c895c8ea705a8363f`.
- **SGI Varsity Update 1998 August** CD (collection 9077), `dist/c++_fe{.idb,.sw}` and `dist/c_fe{.idb,.sw}` =
  **MIPSpro 7.2.1** C++ / C front ends → `dl_varsity9808/`, `x_mipspro721cxx/`.
  - `c++_fe.sw` `6c6dfae3c42a270266b67d4e69c478c754ba10985e017ba09fa53200a6ff7423`
  - `c++_fe.idb` `e5aa2611352f8db296281a59e9d8b219904e44f27cb129f1a1adcfd34313e4e1`
  - `c_fe.sw` `11fe2dcabf74fb8c65afbff64232e1030b999afd72347d402094a856412651c5`
  - `c_fe.idb` `a55b7f3b88dc4068f33a76a6c448a78740a370ecb89a6b32fedf636be795e4b4`
  - `usr/lib/DCC/edgcpfe`: also says **2.29**, built **Mar 13 1998** (`v721/.../targ32_m2/edgcpfe`). sha256
    `459cc16e72de63fb17137cd7dc02f4bc211044e40e0956a92e81eeda47e1d9a3`.
  - `usr/lib/cfe` (7.2.1 o32 C) sha256 `36ed994e531cca27002f3e6c7e33bc10e885ba34f603285665e545539977cd13`.
- **IRIX 6.4 Development Foundation 1.1** CD (collection 9002), `dist/dist6.4/compiler_dev{.idb,.sw}` = the
  MIPSpro 7.2.1 o32 `driver` / `uopt` / `ugen` / `as1` → `dl_idf64_721/`, `x_idf64_721/`.
  - `compiler_dev.sw` `ec14087bc8cba83e7446f80254f5efb4affd72b57c3345a6a5ee3b7ba54f4959`
  - `compiler_dev.idb` `699aecdd5308ddd2422c2b34316a2f3309e3f2374405d2d227a14e10f15bd367`
- Also fetched, not useful: the **MIPSpro 7.2.1 Compiler Patches June 1998** CD (collection 9044). Its C++ rollup
  `patchSG0003048` only replaces `usr/lib32/cmplrs/fecc`, the n32 front end, which emits WHIRL, not ucode
  (`dl_mipspro721p/`; `patchSG0003048.c++_fe_sw` `eb6e9206b867766236c7e43bfa2d1b522f7ab1962060966fb9ed1a2e82132993`).
- Other MIPSpro 7.2 CDs on discmaster: 9045 (C 7.2), 9047 / 9048 (Fortran). No MIPSpro 7.3 CD was found there.

**How to run them.**
- IRIX inst format: `.idb` is text (`f mode owner group dst src subsys ... size(N) cmpsize(M)`). In the
  `<product>.<sw>` file each file is stored as `u16 len, path, data`; data is Unix `compress` (`.Z`) when cmpsize > 0.
  Extractor: `tools/forensics/scripts/idbx.py <idb> <dir> <outdir> [path-substr...]` (gzip -dc decompresses).
  The extracted binaries need `chmod +x`.
- They run under `x_mipspro744/usr/bin/qemu-irix` with a root that has 7.4.4's `lib/rld`, `lib/libc.so.1`,
  `usr/lib/libc.so.1`, `usr/lib/libexc.so` (as1) and `lib/libmalloc.so` (cfe). Run 352 used a symlink root at
  `/tmp/claude-1000/r1/root72`.
- The 7.2.1 driver (`qemu-irix -0 /usr/bin/NCC .../driver -show ...`) prints the exact edgcpfe command line, then
  stops at the FlexLM licence check. The flags are the same as the 7.1 driver's, except that 7.1's `-Qn` is
  missing. So `ncc744.sh` with the front end swapped is the faithful invocation. Wrappers:
  - `tools/forensics/scripts/ncc72.sh`: the 7.2 edgcpfe, or `FEBIN=<edgcpfe>`, followed by the 7.1 back end.
  - `ncc72b.sh` also accepts BE=721 (the 7.2.1 uopt / ugen / as1).
  - `one.sh` and `optmap.py` run the donor gate against `1080-agent-d/build`.

**Results.**
- **(a) 4-label table: YES.** Both 7.2 and 7.2.1 table a dense 4-case switch natively. The head is
  `sltiu at,a0,4; beqz; sw ra; sll; lui; addu; lw; jr`, and for 1..4 they subtract 1 first. This is EDG 2.29's
  rule.
  - The 7.2.1 **cfe**, like every cfe, still builds a compare chain at 4 cases. So this rule is specific to the edg
    front end.
- **(b) Class-returning-by-value inlines: YES, unlike 7.4.4.**
  - Across all 214 donor objects, 7.2 / 7.2.1 emit **no** weak out-of-line copies (`__ml__2V3CFf` and so on).
    Under 7.4.4, 17 of the donor objects do.
  - game_uso 1DDC stays 384 words (7.4.4: 300). The copy chains are present.
  - So the "EDG 2.29 never inlines class returns" finding of run 351 is a **later SGI change, made between
    Mar 1998 and the Nov 2002 7.4.4 build**. It is not EDG 2.29 behaviour.
  - The version string "2.29" therefore covers 1997–2002 SGI builds. Run 351's date argument against "2.29" does
    not hold. The argument against the 7.4.4 *binary* still holds.
- **(c) Family.** All results below are identical between 7.2 and 7.2.1.
  - B3C standalone (`c351/b3c/y5.cpp`): **706/706, and 940 is 107/107**. The .text is byte-identical to the
    EDG-2.29 (7.4.4) object, all 820 words.
  - 116C (`c351/t116/t*.cpp`), 76F0 (`c351/t76/g*.cpp`) and 1ADC (`c351/k3/fa_first.cpp`, 116/134) are each
    byte-identical to run 351's 7.4.4 objects, so run 351's residual analysis applies unchanged.
  - **8CD8** (the agent-d NM donor `game_uso_ncc_8CD8_nm.cpp`, unmodified) is the first build with **both**
    properties at once:
    - 709 words, the target's length;
    - inlined operator copy chains;
    - a native `sltiu 4` table at insn 627 with `jr` at 634, exactly the target's positions. 7.1 NCC has no
      table there.

    Run 351 said this function "rules out both EDG builds". The 7.2 front end is **not** ruled out by it.
    What remains is guard-pointer / temp register colouring and stack-offset residuals. Strict reloc-masked
    aligned score is 18.3 %, against 28.9 % for the tuned 7.1-NCC donor. That is expected, because the body was
    tuned under NCC.
  - game_uso **57D8**, an 8-way dense switch that the target lowers as a compare chain, comes out as a table under
    7.2. It is an exact NCC donor, so game_uso still mixes the two front ends.
- **(d) Gate.** All 214 non-`_nm` `src/*/*_ncc_*.cpp` were compiled at their Makefile -O, with
  `-I<srcdir> -I include -I src`. Each .text was compared with agent-d's `build/src/...cpp.o`.
  - **7.2: 127 identical, 87 differ.**
  - **7.2.1: the same 127 / 87, and all 214 objects are byte-identical to 7.2's.**
  - With the 7.2.1 back end instead of the 7.1 one, only 107 are identical. Keep the 7.1 back end.
  - Same harness with the 7.4.4 front end, for calibration: 125 / 89. Run 351's 121 / 93 used a different include
    set. 7.2 only gains game_libs 4E244 and game_uso 3558.
  - 15 of 7.4.4's 17 weak-copy objects still differ under 7.2, for other reasons.
  - Breakdown of the 87: game_libs 57, game_uso 12 (1DDC, 24BC, 28C0, 2CC8, 3AC0, 43D8, 57D8, 6A30, 6FA8, 71E0,
    97EC, BB8C), bootup 7, timproc_b5 5, gui 2, arcproc / h2h / timproc_b1 / timproc_b3 1 each.
  - 41 change length and 46 keep it. Even small exacts move.
  - The differences are edg-front-end ucode, not the back end. The same classes appear under 7.4.4:
    - argument / operand evaluation order: 485C (2 words), 3D71C (a 4-word swap);
    - bigger frames for stack-resident class temporaries: 3D54C is 32 vs 8 and 38598 is 64 vs 40;
    - `this` spilled to the stack and reloaded in constructors: 15FC;
    - a base address materialised with `addiu` instead of folded into `%lo`: 5165C;
    - `this` taken from the copy rather than the argument register: 24BC (`lw v1,60(a2)` vs `60(a0)`).
  - edgcpfe.eh, the EH variant, is worse.
  - A sweep of every single `-Z<c>`, `-Y<c>` and `-Q<c>` flag over 485C, 3D54C and 24BC fixes only 24BC (`-Yc`).
    `-Yc` on the whole gate gives 128 / 86.

**Verdict.**
- MIPSpro 7.2 / 7.2.1 edgcpfe has the family's rule: a 4-label table, together with 2.19-style
  class-return inlining. It is period-correct: Aug 1997 / Mar 1998, and 1080 shipped in 1998.
- It is the best candidate yet for the compiler of B3C / 8CD8 / 116C / 76F0 / 1ADC. B3C is byte-exact standalone.
  For 8CD8 it is the only front end that gives the target's length and table shape.
- **But it is not the compiler of the 214 NCC donors.**
  - 87 of the donors change under it, many of them the same functions that run 351 broke. 57D8 needs a compare chain
    at 8 cases, which this front end cannot produce.
  - So the game was built with **both** an EDG-2.19 NCC (IDO 7.1-era) and an SGI EDG-2.29 (MIPSpro 7.2.x-era)
    front end. That could be per file or per developer.
  - The other reading: the original is a single front end we still lack, with 2.19 lowering for ordinary code and
    2.29 switch lowering. That seems unlikely, because switch lowering lives in SGI's mbe code, not EDG's.
- **Adopting it per file is safe only for files that contain no NCC donor.**
  - The family functions sit in `game_uso.c` / `titproc` / `game_libs` / `kernel`. Their bodies are C and C-style
    C++ compiled into the unit object, and they would be spliced as separate donors (`REPLACE_FUNC_BODY`). So a
    per-function 7.2 donor does **not** recompile any existing NCC exact.
  - Run 351 found about 155 of 167 cfe-exact C functions byte-identical under 2.29. Per-function donors avoid that
    question entirely.
  - Do not switch whole NCC donor files to it: 87 exacts would regress.
- **Wiring is the user's call.** The rule is the same as run 351's: a B3C "exact" through 7.2.1 uses a period
  front end, not an anachronistic one, so it is defensible on provenance. Still, it means running an
  IRIX binary under qemu-irix in the build, unless an `ido-static-recomp` of this edgcpfe is made. That recomp
  is the obvious next step.
