#!/usr/bin/env python3
"""Zero-use sweep: brute-force the `+ 0 * (int)(X)` counted-use lever over one function.

For every `= E;`, `return E;` and `if (E)` / `while (E)` site in the function and every identifier X
mentioned in it, build one variant with ` + 0 * (int)(X)` appended to E (or `((E) + 0 * (int)(X))` for
conditions) and score it with objdiff against the target object (`-c functionRelocDiffs=none`, the same
metric report.json uses). The folded term emits no code, but in cfe/NCC it counts as a use of X, which
changes live ranges and therefore the register coloring (kit CXCIV / CXCVI in docs/IDO_CODEGEN.md).

Well-definedness filter (match policy): a variant is generated only if X is certainly set at the site on
every path -- X is a parameter, a non-local (global / member), or a local whose declaration-initializer
or plain assignment textually precedes the site in the same block or an enclosing block, and is not the
body of a brace-less if/else/while/for. Locals that are only set conditionally (or set later in a loop)
are skipped and listed. The check is textual and conservative; still eyeball every hit. Use
--no-defcheck to disable it (diagnosis only; never keep such a hit).

Inputs (as in lever-sweep.py, whose compile/score machinery this reuses):
  * in-tree IDO unit (src/**/*.c): the named function's NON_MATCHING body inside a scratch copy of the
    file, run through asm-processor + IDO 7.1 cc -DNON_MATCHING;
  * standalone donor (*.cpp -> NCC, other .c -> cfe): the whole file is compiled, the symbol renamed to --fn.
Never writes src/: every probe is compiled from a scratch copy under --work.

usage:
  zero-use-sweep.py --src projects/1080-agent-c/src/game_libs/game_libs_ncc_4A308_nm.cpp \
      --fn gl_func_0004A308 --target build/src/game_libs/game_libs_post0b.c.o \
      [--wt projects/1080-agent-c] [--vars a,b] [--exprs] [--lines 120-180] [--noint] [--jobs 8] [--top 15]
  (--target is relative to --wt; --wt defaults to the worktree containing --src.)
Prints the base score, then the best --top variants ('GAIN' = beats base). Standalone donor scores are a
ranking; confirm a winner in-tree after a full rebuild (make + make non_matching_objects + report).
"""
import argparse, importlib.util, os, re, sys
from concurrent.futures import ProcessPoolExecutor

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location('lever_sweep', os.path.join(_here, 'lever-sweep.py'))
ls = importlib.util.module_from_spec(_spec)
sys.modules['lever_sweep'] = ls  # lets the worker pool pickle ls.probe / ls.init
_spec.loader.exec_module(ls)

KW = set('if else while for do return break continue switch case default int char short long unsigned '
         'signed float double void struct const volatile inline extern static sizeof goto typedef union new '
         'this operator virtual enum register delete'.split())
COMMENT = re.compile(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|^[ \t]*#(?:[^\n]*\\\n)*[^\n]*', re.S | re.M)  # incl. `\` continuations
TYPE = r'(?:(?:const|volatile|unsigned|signed|struct|register|static)\s+)*[A-Za-z_][\w:]*(?:\s*[\*&]+\s*|\s+)'


def blank_comments(S):
    """Same-length copy of S with comments, strings and preprocessor lines replaced by spaces."""
    return COMMENT.sub(lambda m: re.sub(r'[^\n]', ' ', m.group(0)), S)


def other_bodies(C, lo, hi):
    """(open, close) of every top-level `) {...}` function body outside [lo, hi) (the swept function)."""
    out, d, start = [], 0, None
    for m in re.finditer(r'[{}]', C):
        k = m.start()
        if C[k] == '{':
            if d == 0 and C[:k].rstrip().endswith(')') and not (k >= lo and k < hi):
                start = k
            d += 1
        else:
            d -= 1
            if d < 0:
                return None  # unbalanced (e.g. braces split across #if arms): no reduction
            if d == 0 and start is not None:
                out.append((start, k))
                start = None
    return out if d == 0 else None


def reduce_text(T, ranges, lo, shift):
    """Empty every other function body (`{}`, newlines kept so line numbers are unchanged).
    Ranges before lo apply as-is; ranges after the swept function are shifted by `shift` (variant growth)."""
    parts, last = [], 0
    for a, b in ranges:
        if a >= lo:
            a, b = a + shift, b + shift
        parts.append(T[last:a])
        parts.append('{' + re.sub(r'[^\n]', ' ', T[a + 1:b]) + '}')
        last = b + 1
    parts.append(T[last:])
    return ''.join(parts)


SCALAR = set('int char short long float double unsigned signed u8 s8 u16 s16 u32 s32 u64 s64 f32 f64 '
             'size_t bool'.split())


def struct_assign(C, lhs, rhs, lo, hi):
    """True if `lhs = rhs` is (textually) an aggregate copy: a `*(T *)` cast or a local / `*local` whose
    type is not scalar (e.g. `*(Tri3i *)&a = *(Tri3i *)&b;`, `stage = *p;` with `Vec3 stage, *p`)."""
    def deref_type(e):
        e = e.strip()
        m = re.match(r'^\*\s*\(\s*(?:(?:const|volatile|struct|union)\s+)*([A-Za-z_]\w*)\s*\*\s*\)', e)
        if m:
            return m.group(1), 0
        m = re.match(r'^(\**)\s*([A-Za-z_]\w*)$', e)
        if not m:
            return None
        name, nd = m.group(2), len(m.group(1))
        for d in re.finditer(r'(?:^|[;{}(,])\s*(?:(?:const|volatile|struct|union|register|static)\s+)*'
                             r'([A-Za-z_]\w*)\s+((?:\*\s*)*)' + re.escape(name) + r'\s*[;=,\[)]', C[lo:hi] or C):
            if d.group(1) in KW - SCALAR:
                continue
            ptr = d.group(2).count('*')
            return (d.group(1), 0) if ptr == nd else None
        return None
    for e in (lhs, rhs):
        t = deref_type(e)
        if t and t[0] not in SCALAR:
            return True
    return False


def block_path(C, p, lo):
    """Stack of '{' positions enclosing p, starting from position lo."""
    st = []
    for k in range(lo, p):
        if C[k] == '{':
            st.append(k)
        elif C[k] == '}' and st:
            st.pop()
    return st


def stmt_start(C, a, lo):
    """Start of the statement containing position a (just after the previous ; { or } )."""
    k = a - 1
    d = 0
    while k > lo:
        ch = C[k]
        if ch == ')':
            d += 1
        elif ch == '(':
            if d == 0:
                return None  # inside a parenthesis (condition / call argument): not a plain statement
            d -= 1
        elif d == 0 and ch in ';{}':
            return k + 1
        k -= 1
    return lo


def conditional_prefix(C, s):
    """True if the statement starting at s is the brace-less body of if/else/while/for/do."""
    t = C[:s].rstrip()
    if re.search(r'\b(else|do)$', t):
        return True
    if t.endswith(')'):
        d = 0
        k = len(t) - 1
        while k >= 0:
            if t[k] == ')':
                d += 1
            elif t[k] == '(':
                d -= 1
                if d == 0:
                    break
            k -= 1
        return bool(re.search(r'\b(if|while|for|switch)\s*$', t[:k]))
    return False


def declared_in_list(body, x):
    """True if x is a later declarator of a multi-name declaration (`int a, b, x;`, `T *p, *x = 0;`)."""
    for st in re.split(r'[;{}]', body):
        m = re.match(r'^\s*(?:(?:const|volatile|unsigned|signed|struct|register|static)\s+)*([A-Za-z_][\w:]*)\s', st)
        if not m or m.group(1) in KW - {'int', 'char', 'short', 'long', 'float', 'double', 'unsigned', 'signed'}:
            continue
        parts, d, cur = [], 0, ''
        for ch in st[m.end():]:
            d += ch in '([{'
            d -= ch in ')]}'
            if ch == ',' and d == 0:
                parts.append(cur)
                cur = ''
            else:
                cur += ch
        parts.append(cur)
        if len(parts) > 1 and any(re.match(r'^[\s\*&]*' + re.escape(x) + r'\s*(\[|=|$)', q.split('=')[0] + ('=' if '=' in q else ''))
                                  for q in parts):
            return True
    return False


class DefCheck:
    def __init__(self, C, lo, hi):
        self.C, self.lo, self.hi = C, lo, hi
        self.funcs = []  # (open-brace pos, close pos, params)
        d = 0
        for m in re.finditer(r'[{}]', C):
            if m.group(0) == '{':
                if d == 0:
                    head = C[max(0, m.start() - 600):m.start()]
                    pm = re.search(r'\(([^()]*(?:\([^()]*\)[^()]*)*)\)\s*(?:const\s*)?$', head)
                    params = set()
                    if pm:
                        for part in pm.group(1).split(','):
                            ids = re.findall(r'[A-Za-z_]\w*', part)
                            if ids:
                                params.add(ids[-1])
                    self.funcs.append([m.start(), None, params])
                d += 1
            else:
                d -= 1
                if d == 0 and self.funcs and self.funcs[-1][1] is None:
                    self.funcs[-1][1] = m.start()

    def func_at(self, p):
        for f in self.funcs:
            if f[0] < p and (f[1] is None or p < f[1]):
                return f
        return None

    def ok(self, x, p):
        """Is identifier x certainly set at position p?"""
        f = self.func_at(p)
        if f is None:
            return True
        fo, fc, params = f
        if x in params:
            return True
        body = self.C[fo:fc if fc else self.hi]
        decl = re.compile(r'(?:^|[;{}(,])\s*' + TYPE + r'(?:[\*&]\s*)*' + re.escape(x) + r'\s*(\[|=|;|,|\))')
        if not decl.search(body) and not declared_in_list(body, x):
            return True  # not a local: global, member, or enum constant
        # goto labels: a `goto` can skip an assignment only by landing on a label between it and the site
        # (case labels are handled below; a label before the assignment re-runs it)
        labs = [fo + m.start(1) for m in re.finditer(r'(?:^|[;{}])\s*([A-Za-z_]\w*)\s*:(?!:)', body, re.M)
                if m.group(1) not in ('case', 'default')] if re.search(r'\bgoto\b', body) else []
        sp = block_path(self.C, p, fo)
        pat = re.compile(r'(?<![\w.>])' + re.escape(x) + r'\s*(=)(?!=)|' + TYPE + re.escape(x) + r'\s*(=)(?!=)')
        for m in pat.finditer(self.C, fo, p):
            a = m.start()
            ap =block_path(self.C, a, fo)
            if ap != sp[:len(ap)]:
                continue  # assignment sits in a block that does not enclose the site
            s = stmt_start(self.C, a, fo)
            if s is None:
                if re.search(r'\bfor\s*\(\s*$', self.C[fo:a]):
                    return True  # for-init always runs
                continue
            head = re.sub(r'^(\s*(?:case\b[^:]*|default\s*):(?!:))+', '', self.C[s:a])
            if head != self.C[s:a]:
                s = a - len(head)
            if any(block_path(self.C, a + k.start(), fo) == ap
                   for k in re.finditer(r'\b(case|default)\b', self.C[a:p])):
                continue  # a switch label between the set and the site: another entry skips the set
            if any(a < k < p for k in labs):
                continue  # a goto label between the set and the site
            if head.strip() and not re.match(r'^' + TYPE + r'$', head):
                continue  # x = ... is not the statement head (e.g. inside a larger expression)
            if conditional_prefix(self.C, s):
                continue
            return True
        return False


ZT = {}


def zinit(ctx, S, R):
    ls.init(ctx)
    ZT['S'], ZT['R'] = S, R


def zprobe(job):
    """Build one variant from its (kind, p, q, z) edit on the full or reduced text and score it."""
    tag, reduced, (kind, p, q, z) = job
    S = ZT['R'] if reduced else ZT['S']
    if kind == 'ins':
        T = S[:p] + z + S[p:]
    else:
        T = S[:p] + '((' + S[p + 1:q] + ')' + z + ')' + S[q + 1:]
    return ls.probe((tag, T.split('\n')))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--src', required=True)
    ap.add_argument('--fn', required=True)
    ap.add_argument('--target', required=True, help='target .o, relative to --wt (or absolute)')
    ap.add_argument('--wt', default=None)
    ap.add_argument('--flags', default=None)
    ap.add_argument('--vars', default=None, help='comma list of identifiers (default: all in the function)')
    ap.add_argument('--lines', default=None, help='restrict sites to a line range a-b of --src')
    ap.add_argument('--exprs', action='store_true',
                    help='also sweep dereference / member / index expressions (*p, p->f, a.b, v[i]); the def '
                         'check applies to the base identifier (kit CXCIV used `+ 0 * *q`)')
    ap.add_argument('--noint', action='store_true', help='use `+ 0 * (X)` without the (int) cast')
    ap.add_argument('--noreduce', action='store_true',
                    help='in-tree units: compile the whole file (default: every other function body is emptied '
                         '(`{}`, line numbers kept; checked against a full-file base compile)')
    ap.add_argument('--no-defcheck', action='store_true', help='also try maybe-unset locals (diagnosis only)')
    ap.add_argument('--keep-float', action='store_true',
                    help='also try float-typed identifiers (default: skipped -- `(int)(float)` is a cvt, not zero code)')
    ap.add_argument('--jobs', type=int, default=8)
    ap.add_argument('--top', type=int, default=15)
    ap.add_argument('--maxv', type=int, default=4000)
    ap.add_argument('--work', default=None, help='scratch dir (default /tmp/claude-1000/zero-use-sweep/<fn>)')
    a = ap.parse_args()

    src = os.path.abspath(a.src)
    if a.wt:
        wt = os.path.abspath(a.wt)
    else:
        wt = os.path.dirname(src)
        while wt != '/' and not (os.path.exists(os.path.join(wt, 'Makefile')) and os.path.isdir(os.path.join(wt, 'src'))):
            wt = os.path.dirname(wt)
    ext = os.path.splitext(src)[1]
    intree = ext == '.c' and src.startswith(os.path.join(wt, 'src') + os.sep)
    work = os.path.abspath(a.work or '/tmp/claude-1000/zero-use-sweep/' + a.fn)
    if work.startswith(os.path.join(wt, 'src')):
        sys.exit('--work must not be inside src/')
    os.makedirs(work, exist_ok=True)

    S = open(src).read()
    L = S.split('\n')
    if intree:
        s0, e0 = ls.find_body(L, a.fn, False)
        lo = sum(len(l) + 1 for l in L[:s0])
        hi = sum(len(l) + 1 for l in L[:e0 + 1])
        flo, fhi = lo, hi
    else:
        # standalone donor: sweep only the --fn body when it is defined by name (helpers / inline methods
        # elsewhere in the file would add sites and out-of-scope identifiers that cannot compile);
        # fall back to the whole file (e.g. a member function renamed to --fn after compiling)
        st = [i for i, l in enumerate(L) if re.match(r'^[A-Za-z].*\b%s\s*\([^;]*$' % re.escape(a.fn), l)]
        e0 = next((i for i in range(st[-1] + 1, len(L)) if L[i].startswith('}')), None) if st else None
        if e0 is not None:
            lo = sum(len(l) + 1 for l in L[:st[-1]])
            hi = sum(len(l) + 1 for l in L[:e0 + 1])
        else:
            lo, hi = 0, len(S)
    if a.lines:
        l0, l1 = map(int, a.lines.split('-'))
        lo = sum(len(l) + 1 for l in L[:l0 - 1])
        hi = sum(len(l) + 1 for l in L[:l1])
    C = blank_comments(S)
    seg = C[lo:hi]
    if a.vars:
        vocab = a.vars.split(',')
    else:
        # member names (`.y`, `->x`) and goto labels are not values: every variant using them fails to compile
        ids = set(m.group(0) for m in re.finditer(r'\b[A-Za-z_]\w*\b', seg)
                  if not re.search(r'(\.|->)\s*$', seg[max(0, m.start() - 4):m.start()]))
        labels = set(re.findall(r'\bgoto\s+([A-Za-z_]\w*)', seg)) | set(
            re.findall(r'(?:^|[;{}])\s*([A-Za-z_]\w*)\s*:(?!:)', seg, re.M))
        ids -= labels - {'default'}
        fnames = set(re.findall(r'\b([A-Za-z_]\w*)\s*\(', seg))
        vocab = sorted(i for i in ids if i not in KW and i not in fnames
                       and not re.match(r'^(D_|gl_|func_|import_|[us]\d+$|f32|f64)', i) and not i[0].isupper())
    if a.exprs:
        # unary `*x` only: the previous non-blank character must not end an operand (`a * x` is a product)
        ex = set(m.group(0) for m in re.finditer(r'(?<![\w)\]])\*\s*[A-Za-z_]\w*\b(?!\s*\()', seg)
                 if not re.search(r'[\w)\]]\s*$', seg[max(0, m.start() - 40):m.start()])
                 or re.search(r'\b(return|case|else|do)\s*$', seg[max(0, m.start() - 40):m.start()]))
        ex |= set(re.findall(r'\b[A-Za-z_]\w*(?:\s*(?:->|\.)\s*[A-Za-z_]\w*)+\b(?!\s*\()', seg))
        ex |= set(re.findall(r'\b[A-Za-z_]\w*\s*\[\s*\w+\s*\]', seg))
        ex = sorted(re.sub(r'\s+', '', e) for e in ex if not re.match(r'^\*\s*(' + '|'.join(KW) + r')\b', e))
        vocab = sorted(set(vocab) | set(ex)) if not a.vars else vocab + ex
    if not a.keep_float:
        # `+ 0 * (int)(f)` on a float/double is a real conversion (+4..8 bytes, kit CC), never a zero-code use
        fl = set()
        for m in re.finditer(r'\b(?:f32|f64|float|double)\s+([^;(){}]*)', C[flo:fhi] if intree else seg):
            for part in m.group(1).split(','):
                # a leading `*` (pointer to float) is not matched; `f32 a, f32 b` parameter lists are
                n = re.match(r'^\s*(?:(?:f32|f64|float|double)\s+)?([A-Za-z_]\w*)', part)
                if n:
                    fl.add(n.group(1))
        # globals declared float anywhere in the file (`extern f32 g;`, `f32 tbl[4];`)
        for x in vocab:
            if re.match(r'^[A-Za-z_]\w*$', x) and re.search(
                    r'\b(?:f32|f64|float|double)\s+(?:[A-Za-z_]\w*\s*,\s*)*' + re.escape(x) + r'\s*[;,=\[]', C):
                fl.add(x)
        fl &= set(vocab)
        if fl:
            print('float-typed (skipped; --keep-float to try):', ' '.join(sorted(fl)))
            vocab = [x for x in vocab if re.match(r'^\**([A-Za-z_]\w*)', x).group(1) not in fl]
    print('vocab', len(vocab), flush=True)

    sites = []
    for m in re.finditer(r'(?<![=!<>+\-*/&|^%])=(?!=)([^;{}]*);|\breturn\s+([^;{}]+);', C):
        if lo <= m.start() and m.end() <= hi:
            rhs = C[m.start() + 1:m.end() - 1] if m.group(2) is None else m.group(2)
            if rhs.count('(') != rhs.count(')'):
                continue  # `=` inside a parenthesised condition (`if (!((v0 = x) & 1)) goto L;`)
            # q = statement start: the def check must not count this statement's own assignment
            q = max(C.rfind(ch, lo, m.start()) for ch in ';{}') + 1
            if m.group(2) is None and struct_assign(C, C[q:m.start()], rhs, *((flo, fhi) if intree else (0, len(C)))):
                continue  # aggregate copy: `struct + 0 * x` does not compile

            sites.append(('ins', m.end() - 1, q))
    for m in re.finditer(r'\b(if|while)\s*\(', C):
        if m.start() < lo or m.end() > hi:
            continue
        p = m.end() - 1
        d = 0
        for k in range(p, hi):
            if C[k] == '(':
                d += 1
            elif C[k] == ')':
                d -= 1
                if d == 0:
                    break
        sites.append(('cond', p, k))

    ranges = other_bodies(C, flo, fhi) if intree and not a.noreduce else None

    dc = DefCheck(C, lo, hi)
    V, skipped = [], set()
    agg = set(x for x in vocab if struct_assign(C, x, '', *((flo, fhi) if intree else (0, len(C)))))
    if agg:  # `(int)(struct value)` does not compile
        print('aggregate-typed (skipped):', ' '.join(sorted(agg)))
        vocab = [x for x in vocab if x not in agg]
    for kind, p, q in sites:
        ln = S.count('\n', 0, p) + 1
        for x in vocab:
            base_id = re.match(r'^\**([A-Za-z_]\w*)', x).group(1)
            if not a.no_defcheck and not dc.ok(base_id, q if kind == 'ins' else p):
                skipped.add('%s@L%d' % (x, ln))
                continue
            z = (' + 0 * (%s)' % x) if a.noint else (' + 0 * (int)(%s)' % x)
            V.append(('L%d %s %s' % (ln, kind, x), (kind, p, q, z)))  # edit only: texts are built in the worker
    if skipped:
        print('maybe-unset (skipped):', ' '.join(sorted(skipped)[:80]), '...' if len(skipped) > 80 else '')
    V = V[:a.maxv]
    ctx = dict(wt=wt, src=src, ext=ext, intree=intree, work=work, fn=a.fn,
               target=a.target if os.path.isabs(a.target) else os.path.join(wt, a.target),
               cc=os.path.join(wt, 'tools/ido-static-recomp/build/7.1/out', 'NCC' if ext == '.cpp' else 'cc'),
               flags=a.flags or (ls.NCC_FLAGS if ext == '.cpp' else ls.CFE_FLAGS))
    if intree:  # the scratch copy lives outside src/: keep `#include "x.c"` siblings resolvable
        ctx['flags'] += ' -I ' + os.path.dirname(src)
    lab = {'%05d' % n: x for n, (x, _) in enumerate(V)}
    print(len(sites), 'sites', len(V), 'variants', flush=True)
    R = reduce_text(S, ranges, flo, 0) if ranges else S  # same length as S: every edit offset still applies
    with ProcessPoolExecutor(a.jobs, initializer=zinit, initargs=(ctx, S, R)) as ex:
        if ranges:  # check the reduction first; fall back to whole-file compiles if it changes the base
            res = dict(ex.map(ls.probe, [('base', R.split('\n')), ('full', L)]))
            if res['base'] is None or res['base'] != res['full']:
                print('reduced base %s != full-file base %s: falling back to whole-file compiles'
                      % (res['base'], res['full']), flush=True)
                ranges = None
                res = {'base': res['full']}
            else:
                print('reduced: %d other function bodies emptied (base = full-file base)' % len(ranges))
                del res['full']
        else:
            res = {}
        if 'base' not in res:
            res.update(dict(ex.map(ls.probe, [('base', L)])))
        jobs = [('%05d' % n, bool(ranges), e) for n, (_, e) in enumerate(V)]
        res.update(dict(ex.map(zprobe, jobs, chunksize=4)))
    base = res['base']
    print('base', base)
    if base is None:
        sys.exit('base does not compile/score')
    rows = sorted([(res[t], lab[t]) for t in res if t != 'base' and res[t]],
                  key=lambda r: (-r[0][0], abs(r[0][1] - r[0][2])))
    for s, x in rows[:a.top]:
        print('%s%.3f size %d/%d %s' % ('GAIN ' if s[0] > base[0] + 1e-3 else '     ', s[0], s[1], s[2], x))
    same = [r for r in rows if r[0][1] == base[1]]
    if same and len(same) != len(rows):
        print('best same-length (NM size %d) rows:' % base[1])
        for s, x in same[:min(a.top, 8)]:
            print('%s%.3f size %d/%d %s' % ('GAIN ' if s[0] > base[0] + 1e-3 else '     ', s[0], s[1], s[2], x))
    print('done', len(rows), 'scored', sum(1 for t in res if t != 'base' and res[t] is None), 'failed', flush=True)


if __name__ == '__main__':
    main()
