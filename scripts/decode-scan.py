#!/usr/bin/env python3
"""decode-scan.py -- project-wide scan for mechanical DECODE errors in NM bodies.

Run from a project dir (e.g. projects/1080-agent-c):
    python3 ../../scripts/decode-scan.py [--min-fuzzy 0] [--max-fuzzy 100] [--unit SUBSTR]

Read-only.  Needs fresh build/non_matching objects (`make non_matching_objects`)
and report.json.  For every function scoring < 100 in report.json:

  A  address classes (object-based, uses undefined_syms_auto.txt pins):
     A1 every %lo site's effective address (pin + hi<<16 + sext(lo)) in the NM
        object vs the expected object.  An NM address the target never forms,
        built from a NON-ZERO pinned symbol with a non-zero addend, is a
        double-added pin offset candidate (33094: pin 0x128 and `+ 296` in C).
        Other missing / extra addresses are listed too (wrong field / wrong pin).
     A2 same address, different split: the target forms it with `addiu` (holds
        the full address, accesses 0(reg)) where the NM folds it into the
        load/store displacement, or vice versa (31A74).
  B  negated float compares left by m2c: `!(a <= b)`, `!(a < b)`, `!(a == b)`...
     A3 an UNPINNED NM symbol at a site the target forms differently: prints
        the address the positionally-paired target site holds (a pin hint --
        pairing is by site order, so check it with rdiff --raw --pins).
        `--unpinned` lists every unpinned non-section symbol instead.
     A4 C-text: `SYM + K` / `SYM[K]` (K >= 16) where SYM has a non-zero pin.
     Own .rodata/.bss/.data section sites are placement, not decode: skipped.
     NOTE objdiff's fuzzy score IGNORES relocated immediates (reloc vs baked
     word scores the same whatever the value), so A1/A3/A4 fixes are
     correctness-only (score flat); A2 changes instruction shape and can score.
  C  other m2c leftovers in the C body: M2C_ERROR, saved_reg_*, unksp*, sp+0x..
     names, `(f32)(u32)` casts, `M2C_FIELD`, `?` types.

Output: one line per finding, ranked by function bytes (largest first).
"""
import collections
import json
import os
import re
import subprocess
import sys

ROOT = os.getcwd()
ARGS = sys.argv[1:]


def opt(name, default):
    if name in ARGS:
        return ARGS[ARGS.index(name) + 1]
    return default


MINF = float(opt('--min-fuzzy', '0'))
MAXF = float(opt('--max-fuzzy', '100'))
USUB = opt('--unit', '')

PINS = {}
for l in open(os.path.join(ROOT, 'undefined_syms_auto.txt')):
    m = re.match(r'\s*(\S+)\s*=\s*(0x[0-9a-fA-F]+|\d+)\s*;', l)
    if m:
        PINS[m.group(1)] = int(m.group(2), 0)


def sext16(v):
    v &= 0xFFFF
    return v - 0x10000 if v >= 0x8000 else v


LOADST = {'lw', 'sw', 'lh', 'lhu', 'sh', 'lb', 'lbu', 'sb', 'lwc1', 'swc1', 'ldc1', 'sdc1'}


def disasm(obj, fn):
    out = subprocess.run(['mips-linux-gnu-objdump', '-dr', '-M', 'no-aliases',
                          '--disassemble=' + fn, obj], capture_output=True, text=True).stdout
    rows, at, pending = [], {}, []
    for l in out.splitlines():
        m = re.match(r'\s+([0-9a-f]+):\s+([0-9a-f]{8})\s+(\S+)\s*(.*)', l)
        if m:
            at[int(m.group(1), 16)] = len(rows)
            rows.append([m.group(3), m.group(4).strip(), int(m.group(2), 16), None, None])
            continue
        m = re.match(r'\s+([0-9a-f]+):\s+R_MIPS_(\w+)\s+(\S+)', l)
        if m:
            pending.append((int(m.group(1), 16), m.group(2), m.group(3)))
    for off, rt, sym in pending:
        k = at.get(off)
        if k is not None:
            rows[k][3], rows[k][4] = rt, sym
    return rows


REG_W = re.compile(r'^(\w+),')


def sites(rows):
    """[(kind, sym, addend, lo16)] for every lui-based address site.

    USO expected objects carry NO relocations: the ROM words hold `lui r,0`
    plus the real %lo in the addiu / load / store (the loader patches the
    %hi).  So both sides are compared on the low 16 bits of the effective
    address, found by a linear register dataflow from each `lui`; relocated
    sites use pin + addend (sym None = raw target word)."""
    res = []
    held = {}          # reg -> (sym, hi addend)
    for i, (op, args, word, rt, sym) in enumerate(rows):
        regs = [x.strip() for x in re.split(r'[,()]', args) if x.strip()]
        if op == 'lui' and regs:
            held[regs[0]] = ('lui', sym if rt == 'HI16' else None, (word & 0xFFFF) << 16)
            continue
        base = None
        if op in LOADST and len(regs) >= 3:
            base = regs[2]
        elif op == 'addiu' and len(regs) >= 3:
            base = regs[1]
        newaddr = None
        if base is not None and base in held and (rt in (None, 'LO16')):
            h = held[base]
            kind = 'ls' if op in LOADST else 'addiu'
            if h[0] == 'lui':
                hsym, hi = h[1], h[2]
                lsym = sym if rt == 'LO16' else hsym
                add = hi + sext16(word)
                add = ((add + 0x80000000) & 0xFFFFFFFF) - 0x80000000
                pin = PINS.get(lsym, 0) if lsym else 0
                full = (pin + add) & 0xFFFFFFFF
                eff = full & 0xFFFF
                res.append((kind, lsym, add, eff, full))
                if kind == 'addiu':
                    newaddr = ('addr', lsym, add, eff, full)
            elif rt is None:   # displacement off a held full address
                hsym, add0, eff0, full0 = h[1], h[2], h[3], h[4]
                d = sext16(word)
                full = (full0 + d) & 0xFFFFFFFF
                eff = full & 0xFFFF
                res.append(('via' if kind == 'ls' else 'addiu', hsym, add0 + d, eff, full))
                if kind == 'addiu':
                    newaddr = ('addr', hsym, add0 + d, eff, full)
        # any write to a register drops its held lui value
        if regs and op not in LOADST - {'lw', 'lh', 'lhu', 'lb', 'lbu', 'lwc1', 'ldc1'} \
                and not op.startswith('b') and op not in ('jr', 'j', 'jal', 'mtc1', 'ctc1'):
            if op in ('sw', 'sh', 'sb', 'swc1', 'sdc1'):
                pass
            else:
                held.pop(regs[0], None)
        if newaddr is not None:
            held[regs[0]] = newaddr
        if op in ('jal', 'jalr'):
            for r in ('at', 'v0', 'v1', 'a0', 'a1', 'a2', 'a3', 't0', 't1', 't2', 't3',
                      't4', 't5', 't6', 't7', 't8', 't9'):
                held.pop(r, None)
    return res


def is_local(sym):
    """section-relative sites (own .rodata/.bss/.data): placement, not decode."""
    return bool(sym) and (sym.startswith('.') or (
        sym not in PINS and re.search(r'_(rodata|bss|data)$', sym) is not None))


def addr_findings(ours, target, fn):
    try:
        a, b = sites(disasm(ours, fn)), sites(disasm(target, fn))
    except Exception as e:  # noqa
        return ['A? %s' % e]
    out = []
    ea = collections.Counter(s[3] for s in a if s[3] is not None)
    eb = collections.Counter(s[3] for s in b if s[3] is not None)
    tset = set(eb)
    seen = set()
    nloc = sum(1 for s in a if is_local(s[1]))
    for kind, sym, add, eff, _f in a:
        if eff is None or eff in tset or (sym, add) in seen or is_local(sym):
            continue
        seen.add((sym, add))
        base = PINS.get(sym, 0) if sym else 0
        near = min(tset, key=lambda t: abs(t - eff)) if tset else None
        tag = 'A1'
        if base != 0 and add != 0 and ((eff - add) & 0xFFFF) in tset:
            tag = 'A1-DOUBLE'      # pin already = target address, C adds again
        elif base != 0 and add != 0 and (add & 0xFFFF) in tset:
            tag = 'A1-DOUBLE'
        out.append('%s %s%+#x eff=%#x not in target%s' % (
            tag, sym, add, eff, '' if near is None else ' (nearest %#x, d=%+#x)' % (near, eff - near)))
    for t in sorted(set(eb) - set(ea)):
        syms = sorted({str(s[1]) for s in b if s[3] == t})
        out.append('A1-MISSING target forms %#x (%s) never formed by NM%s' % (
            t, ','.join(syms), ' [NM has %d local-section sites]' % nloc if nloc else ''))
    # positional pairing: unpinned NM symbol at a site where the target forms X
    import difflib
    sm = difflib.SequenceMatcher(None, [s[0] for s in a], [s[0] for s in b], autojunk=False)
    sugg = {}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal' or (tag == 'replace' and i2 - i1 == j2 - j1):
            for x, y in zip(a[i1:i2], b[j1:j2]):
                sym = x[1]
                if sym and sym not in PINS and not is_local(sym) and x[3] != y[3]:
                    sugg.setdefault(sym, set()).add((y[4] - x[2]) & 0xFFFFFFFF)
    for sym in sorted(sugg):
        v = sorted(sugg[sym])
        out.append('A3-PIN %s unpinned; target site says %s' % (
            sym, ' / '.join('%#x' % q for q in v) + (' (CONFLICT)' if len(v) > 1 else '')))
    for sym in (sorted({s[1] for s in a if s[1] and s[1] not in PINS and not is_local(s[1])})
                if '--unpinned' in ARGS else []):
        out.append('A3-UNPINNED %s (NM object addend only; a landing needs a pin)' % sym)
    # split form
    ka = collections.defaultdict(set)
    kb = collections.defaultdict(set)
    for kind, sym, add, eff, _f in a:
        if eff is not None:
            ka[eff].add(kind)
    for kind, sym, add, eff, _f in b:
        if eff is not None:
            kb[eff].add(kind)
    for e in sorted(set(ka) & set(kb)):
        if ka[e] != kb[e]:
            out.append('A2-SPLIT %#x NM %s vs target %s' % (e, '/'.join(sorted(ka[e])), '/'.join(sorted(kb[e]))))
    return out


SIGN_PAIRS = [('lh', 'lhu'), ('lb', 'lbu'), ('sra', 'srl'), ('srav', 'srlv'), ('slt', 'sltu'),
              ('slti', 'sltiu'), ('div', 'divu'), ('mult', 'multu'), ('c.lt.s', 'c.le.s'),
              ('c.lt.d', 'c.le.d'), ('bc1t', 'bc1f'), ('bc1tl', 'bc1fl'), ('cvt.s.w', 'cvt.s.d'),
              ('sh', 'sw'), ('sb', 'sh'), ('lwc1', 'lw'), ('swc1', 'sw')]


def sign_findings(ours, target, fn):
    """D: signedness / width / compare-sense opcode swaps (type decode errors):
    NM has N more of one opcode of a pair and the target N more of the other."""
    try:
        ca = collections.Counter(r[0] for r in disasm(ours, fn))
        cb = collections.Counter(r[0] for r in disasm(target, fn))
    except Exception:  # noqa
        return []
    out = []
    # E: literal constants (non-relocated immediates of value-forming ops).
    def consts(rows):
        c = collections.Counter()
        for op, args, word, rt, sym in rows:
            if rt:
                continue
            if op == 'lui' and (word & 0xFFFF) < 0x100:
                continue   # USO address %hi baked without a reloc: not a literal
            if op in ('lui', 'ori', 'andi', 'xori', 'slti', 'sltiu') or \
                    (op == 'addiu' and re.search(r',zero,', args)):
                c[(op, word & 0xFFFF)] += 1
        return c
    try:
        ka, kb = consts(disasm(ours, fn)), consts(disasm(target, fn))
        lo_a = {k for k in ka if ka[k] > kb[k]}
        lo_b = {k for k in kb if kb[k] > ka[k]}
        for k in sorted(lo_b):
            if not any(o == k[0] for o, _ in lo_a) and k[0] != 'lui':
                continue
            out.append('E-CONST target %s %#x x%d, NM %s' % (
                k[0], k[1], kb[k] - ka[k],
                ' '.join('%s %#x' % q for q in sorted(lo_a) if q[0] == k[0]) or '-'))
    except Exception:  # noqa
        pass
    for x, y in SIGN_PAIRS:
        dx, dy = ca[x] - cb[x], ca[y] - cb[y]
        if dx * dy < 0:
            n = min(abs(dx), abs(dy))
            a_, b_ = (x, y) if dx > 0 else (y, x)
            out.append('D-SWAP NM has %d more %s, target %d more %s' % (n, a_, n, b_))
    return out


# --- C-body scans ---------------------------------------------------------
SRC_EXT = ('.c', '.cpp')


def load_sources():
    src = {}
    for d, _, fs in os.walk(os.path.join(ROOT, 'src')):
        for f in fs:
            if f.endswith(SRC_EXT):
                p = os.path.join(d, f)
                try:
                    src[p] = open(p, errors='replace').read()
                except OSError:
                    pass
    return src


DEF_RE = r'^[A-Za-z_][\w \t\*]*?\b%s\s*\([^;{]*\)\s*\{'


def bodies_for(fn, src):
    """yield (path, body) for every C definition of fn (NM bodies and donors)."""
    for p, t in src.items():
        if fn not in t:
            continue
        for m in re.finditer(DEF_RE % re.escape(fn), t, re.M):
            i, depth = m.end() - 1, 0
            for j in range(i, len(t)):
                if t[j] == '{':
                    depth += 1
                elif t[j] == '}':
                    depth -= 1
                    if depth == 0:
                        yield p, t[i:j + 1]
                        break


CMP = r'(?:<=|>=|<|>|==|!=)'
NEG_RE = re.compile(r'!\s*\(\s*([^()!&|]+?)\s*(' + CMP + r')\s*([^()&|]+?)\s*\)')
PINOFF_RE = re.compile(r'&?\s*\b([A-Za-z_]\w*)\s*\)?\s*\+\s*(0x[0-9A-Fa-f]+|\d+)\b'
                       r'|\b([A-Za-z_]\w*)\s*\[\s*(0x[0-9A-Fa-f]+|\d+)\s*\]')
LEFT_RE = [
    ('C-M2C_ERROR', re.compile(r'M2C_ERROR')),
    ('C-saved_reg', re.compile(r'\bsaved_reg_\w+')),
    ('C-unksp', re.compile(r'\bunksp\w*|\bsp[0-9A-F]{2,}\b')),
    ('C-f32u32', re.compile(r'\(f32\)\s*\(u32\)')),
    ('C-M2C_FIELD', re.compile(r'M2C_FIELD|M2C_STRUCT_COPY|M2C_UNK')),
    ('C-qtype', re.compile(r'\?\s*\*|\b\? ')),
]


def strip_comments(t):
    t = re.sub(r'/\*.*?\*/', ' ', t, flags=re.S)
    return re.sub(r'//[^\n]*', ' ', t)


def c_findings(fn, src):
    out = []
    for p, body in bodies_for(fn, src):
        b = strip_comments(body)
        rel = os.path.relpath(p, ROOT)
        for m in NEG_RE.finditer(b):
            lhs, op, rhs = m.groups()
            # integer `!(x == y)` is harmless; flag float-looking ones and all ordered compares
            fl = re.search(r'\d\.\d*f?|\bf\d|f32|float|D_\w+', lhs + rhs)
            if op in ('<', '<=', '>', '>=') or fl:
                out.append('B-NEGCMP %s: !(%s %s %s)' % (rel, lhs.strip(), op, rhs.strip()))
        for m in PINOFF_RE.finditer(b):
            sym = m.group(1) or m.group(3)
            k = m.group(2) or m.group(4)
            if PINS.get(sym, 0) != 0:
                kv = int(k, 0)
                # `SYM[k]` is element-scaled: small indexes are ordinary arrays
                if kv != 0 and not (m.group(3) and kv < 16):
                    out.append('A4-PINOFF %s: %s pinned %#x and `+ %s` in C (eff %#x)' % (
                        rel, sym, PINS[sym], k, PINS[sym] + kv))
        for tag, rx in LEFT_RE:
            hits = sorted(set(rx.findall(b)))
            if hits:
                out.append('%s %s: %s' % (tag, rel, ' '.join(hits[:6])))
    return out


def main():
    rep = json.load(open(os.path.join(ROOT, 'report.json')))
    src = load_sources()
    rows = []
    for u in rep['units']:
        if USUB and USUB not in u['name']:
            continue
        ours = None
        for e in ('.c.o', '.cpp.o'):
            p = os.path.join(ROOT, 'build/non_matching', u['name'] + e)
            if os.path.exists(p):
                ours = p
                tgt = os.path.join(ROOT, 'expected', u['name'] + e)
                break
        for f in u.get('functions', []):
            fz = f.get('fuzzy_match_percent', 0.0)
            if fz >= 100 or not (MINF <= fz <= MAXF):
                continue
            fn, size = f['name'], int(f['size'])
            finds = []
            if ours and os.path.exists(tgt):
                finds += addr_findings(ours, tgt, fn)
                finds += sign_findings(ours, tgt, fn)
            finds += c_findings(fn, src)
            for x in finds:
                rows.append((size, fn, fz, u['name'], x))
    rows.sort(key=lambda r: (-r[0], r[1]))
    cnt = collections.Counter(r[4].split()[0] for r in rows)
    for size, fn, fz, unit, x in rows:
        print('%5d %-34s %6.2f %-40s %s' % (size, fn, fz, unit, x))
    print('# totals: ' + ', '.join('%s=%d' % kv for kv in sorted(cnt.items())))


if __name__ == '__main__':
    main()
