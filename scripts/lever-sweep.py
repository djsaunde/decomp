#!/usr/bin/env python3
"""Lever sweep: apply one mechanical, semantics-preserving source lever at a time to one function and
score every variant with objdiff against the target. Never writes src/ -- every probe compiles a scratch
copy under --work.

Two input kinds (picked from the --src path):
  * in-tree IDO unit (src/**/*.c): the named function's body is edited inside a scratch copy of the whole
    file, which is run through asm-processor + IDO 7.1 cc with -DNON_MATCHING (the cfe/NM body path).
    Use --flags for units not built at plain -O2.
  * standalone donor (*.cpp for NCC, any .c outside src/ for cfe): the whole file is the function;
    compiled directly, the first mangled/defined symbol is renamed to --fn if needed.

Subcommands (one lever each; each variant is one change from the base):
  denaming   replace a once-assigned local by a #define of its expression (kit CXXIV de-naming)
  volatile   add `volatile` to one local declaration at a time (volatile homes)
  order      swap adjacent independent statements, and move one assignment 2-4 lines up/down past
             statements that don't touch it (independent-store order). The dependency check is textual
             (a swap is skipped when one side writes what the other mentions): CHECK hits by hand,
             and never keep a hit that reorders calls or volatile accesses.
  bbsplit    append `if (1) {}` after one statement at a time (basic-block split lever)
  all        all of the above

usage:
  lever-sweep.py order --src projects/1080-agent-c/src/game_libs/game_libs_post.c --fn gl_func_000415A4 \
      --target build/src/game_libs/game_libs_post.c.o [--wt projects/1080-agent-c] [--jobs 8] \
      [--work /tmp/claude-1000/x/ls] [--all-results]
  (--target is relative to --wt; --wt defaults to the worktree containing --src.)
Prints the base score, then every variant that beats it (or all with --all-results), best first.
Scores from standalone donors are a ranking (relocs differ from the spliced unit); confirm winners with
refresh-report. Hits are candidates, not proofs: the gate is the in-tree build.
"""
import argparse, json, os, re, subprocess, sys
from concurrent.futures import ProcessPoolExecutor

CFE_FLAGS = '-G 0 -non_shared -Xcpluscomm -Wab,-r4300_mul -O2 -mips2 -32'
NCC_FLAGS = '-G 0 -non_shared -Wab,-r4300_mul -O2 -mips2 -32'
DECL = re.compile(r'^\s+(?:volatile\s+|const\s+|unsigned\s+|signed\s+|struct\s+)*[A-Za-z_][\w:]*'
                  r'(?:\s*[\*&]+\s*|\s+)[A-Za-z_]\w*(\[[^\]]*\])?\s*(=.*)?;\s*$')
SKIP = ('return', 'break', 'continue', 'goto', 'if', 'for', 'while', 'do', '}', 'case', 'default', '#',
        '//', '/*', '*', 'typedef', 'extern', 'struct', 'inline')
CTX = {}


def find_body(L, fn, whole):
    if whole:
        return -1, len(L)
    st = [i for i, l in enumerate(L) if re.match(r'^[A-Za-z].*\b%s\s*\(.*\)\s*\{\s*$' % fn, l)] or \
         [i for i, l in enumerate(L) if re.match(r'^[A-Za-z].*\b%s\s*\([^;]*$' % fn, l)]
    if not st:
        sys.exit('function %s not found' % fn)
    s0 = st[-1]  # last definition = the NON_MATCHING body when an INCLUDE_ASM precedes it
    e0 = next(i for i in range(s0 + 1, len(L)) if L[i].startswith('}'))
    return s0, e0


def is_stmt(l):
    t = l.strip()
    # '*' in SKIP is for comment continuation lines; a store like *(T *)(p + K) = v is a statement
    is_comment_star = t.startswith('*') and (t == '*' or t[1:2] in (' ', '/'))
    starts_skip = t.startswith(tuple(s for s in SKIP if s != '*')) or is_comment_star
    return t.endswith(';') and t.count(';') == 1 and not DECL.match(l) and not starts_skip \
        and len(l) - len(l.lstrip()) >= 4


def lhs(t):
    m = re.match(r'^(.*?)\s*([-+*/|&^]?=)(?!=)', t.strip())
    return m.group(1).strip() if m else None


ind = lambda x: len(x) - len(x.lstrip())


def writes(t):
    """What a simple statement writes: the full assignment target text and any ++/-- operand names."""
    out = set(re.findall(r'(?:\+\+|--)\s*([A-Za-z_]\w*)|([A-Za-z_]\w*)\s*(?:\+\+|--)', t))
    out = {x or y for x, y in out}
    l = lhs(t)
    if l:
        out.add(l)
    return out


_NOTCALL = {'if', 'while', 'for', 'switch', 'return', 'sizeof'}


def has_call(t):
    """True if the statement contains a function call. Casts and field-access expressions like
    *(T *)((char *)(p) + K) don't count; ALL-CAPS identifiers are treated as access macros (e.g. FW(p, K)),
    not calls. Conservative enough for a textual sweep; hits are still checked by hand."""
    for m in re.finditer(r'\b([A-Za-z_]\w*)\s*\(', t):
        name = m.group(1)
        # only known pure field-access macros are exempt; other ALL-CAPS macros (e.g. PKT) may expand to calls
        if name in _NOTCALL or name in _ACCESS_MACROS:
            continue
        return True
    return False


_ACCESS_MACROS = {'FW', 'FH', 'FB', 'FF', 'FS', 'FD', 'FP', 'FU8', 'FS8', 'FU16', 'FS16', 'FF32'}


def lhs_names(t):
    """Identifiers a statement may write through its left-hand side. For `*(T *)&(x.f) = v` or `p->f = v`
    style targets, every identifier after '&' or before '.'/'->' counts (conservative); the plain
    `*(T *)((char *)(p) + K) = v` field-store form keeps the whole-text comparison only."""
    l = lhs(t) or ''
    names = set()
    for m in re.finditer(r'&\s*\(?\s*([A-Za-z_]\w*)', l):
        names.add(m.group(1))
    if re.match(r'^[A-Za-z_]\w*$', l):
        names.add(l)
    return names


def variants(cmd, L, s0, e0):
    out = []
    if cmd in ('denaming', 'all'):
        names = {}
        for i in range(s0 + 1, e0):
            l = L[i]
            m = re.match(r'^(\s+)([A-Za-z_]\w*) = (.+);\s*$', l)
            if m:
                names.setdefault(m.group(2), []).append(('a', i, m.group(3)))
            m = re.match(r'^(\s+)(?:const\s+)?[A-Za-z_][\w:]*(?:\s*\*+\s*|\s+)([A-Za-z_]\w*) = (.+);\s*$', l)
            if m and not l.strip().startswith('return'):
                names.setdefault(m.group(2), []).append(('i', i, m.group(3)))
        for n, occ in names.items():
            if len(occ) != 1:
                continue
            k, i, expr = occ[0]
            decl = None
            if k == 'a':
                for j in range(max(s0, 0), i):
                    if re.match(r'^\s+(?:volatile\s+)?[A-Za-z_][\w:]*(?:\s*\*+\s*|\s+)%s;\s*$' % re.escape(n), L[j]):
                        decl = j
                if decl is None:
                    continue
            if not any(re.search(r'\b%s\b' % re.escape(n), L[x]) for x in range(i + 1, e0)):
                continue
            M = L[:]
            M[i] = '#define %s (%s)' % (n, expr)
            if decl is not None:
                M[decl] = ''
            if e0 < len(L):
                M[e0] = L[e0] + '\n#undef %s' % n
            out.append(('denaming %s (line %d)' % (n, i + 1), M))
    if cmd in ('volatile', 'all'):
        for i in range(s0 + 1, e0):
            l = L[i]
            if 'volatile' in l or l.lstrip().startswith(SKIP + ('else',)):
                continue
            m = re.match(r'^(\s{4,})((?:unsigned |signed |const )?[A-Za-z_][\w:]*(?:\s*\*+\s*|\s+))([A-Za-z_]\w*)(\s*(=.*)?;\s*)$', l)
            if not m or m.group(2).strip() in ('return', 'goto', 'delete', 'else', 'case'):
                continue
            M = L[:]
            if '*' in m.group(2):
                M[i] = m.group(1) + m.group(2).rstrip() + ' volatile ' + m.group(3) + m.group(4)
            else:
                M[i] = m.group(1) + 'volatile ' + m.group(2) + m.group(3) + m.group(4)
            out.append(('volatile line %d: %s' % (i + 1, l.strip()[:50]), M))
    if cmd in ('order', 'all'):
        for i in range(s0 + 1, e0 - 1):
            a, c = L[i], L[i + 1]
            # never swap two statements that both contain calls (call order is observable)
            # never move a statement across a call: a callee may read or write member, global or pointed-to
            # state that a textual check can't see (bare C++ member stores, globals, reads of globals)
            if is_stmt(a) and is_stmt(c) and ind(a) == ind(c) and not has_call(a) and not has_call(c) \
                    and 'volatile' not in a and 'volatile' not in c:
                # textual dependency check: skip when one statement writes a name the other mentions
                wa, wc = writes(a) | lhs_names(a), writes(c) | lhs_names(c)
                if any(re.search(r'(?<![\w.>])%s(?!\w)' % re.escape(w), c) for w in wa) or \
                   any(re.search(r'(?<![\w.>])%s(?!\w)' % re.escape(w), a) for w in wc):
                    continue
                M = L[:]
                M[i], M[i + 1] = c, a
                out.append(('swap line %d: %s <> %s' % (i + 1, a.strip()[:40], c.strip()[:40]), M))
        for i in range(s0 + 1, e0):
            a = L[i]
            la = lhs(a) if is_stmt(a) else None
            # field stores like *(T *)((char *)(p) + K) = v are allowed; statements with calls are not
            if not la or has_call(a) or '++' in a or '--' in a or 'volatile' in a:
                continue
            for k in (2, 3, 4, -2, -3, -4):
                lo, hi = (i + 1, i + k) if k > 0 else (i + k, i - 1)
                if lo <= s0 or hi >= e0:
                    continue
                seg = L[lo:hi + 1]
                if not all(is_stmt(x) and ind(x) == ind(a) and lhs(x) and not has_call(x) and '++' not in x
                           and '--' not in x and 'volatile' not in x for x in seg):
                    continue
                if any(la in x.strip() or lhs(x) in a.strip() for x in seg):
                    continue
                M = L[:]
                if k > 0:
                    M[i:hi + 1] = seg + [a]
                else:
                    M[lo:i + 1] = [a] + seg
                out.append(('move line %d by %+d: %s' % (i + 1, k, a.strip()[:50]), M))
    if cmd in ('bbsplit', 'all'):
        for i in range(s0 + 1, e0):
            if is_stmt(L[i]):
                M = L[:]
                M[i] = L[i].rstrip() + ' if (1) {}'
                out.append(('bbsplit line %d: %s' % (i + 1, L[i].strip()[:50]), M))
    if cmd == 'declmove':
        lo = s0 + 1 if s0 >= 0 else 0
        # find function body starts: lines ending with '{' at col 0 containing '(' (for standalone) or s0
        starts = [s0] if s0 >= 0 else [i for i, l in enumerate(L) if re.match(r'^[A-Za-z].*\)\s*\{\s*$', l) and not l.startswith(('struct', 'typedef', 'inline', 'extern "C" {'))]
        for st in starts:
            i = st + 1
            blk = []
            while i < len(L) and (DECL.match(L[i]) or L[i].strip().startswith(('/*', '*', '//')) and blk):
                if DECL.match(L[i]):
                    blk.append(i)
                i += 1
            if len(blk) < 2:
                continue
            for a in blk:
                for b in blk:
                    if a == b:
                        continue
                    M = L[:]
                    line = M[a]
                    M[a] = None
                    if b < a:
                        M[b] = line + '\n' + M[b]
                    else:
                        M[b] = M[b] + '\n' + line
                    M = [x for x in M if x is not None]
                    M = '\n'.join(M).split('\n')
                    out.append(('declmove %d -> %d: %s' % (a + 1, b + 1, line.strip()[:40]), M))
    if cmd == 'hoist':
        starts = [s0] if s0 >= 0 else [i for i, l in enumerate(L) if re.match(r'^[A-Za-z].*\)\s*\{\s*$', l) and not l.startswith(('struct', 'typedef', 'inline', 'extern "C" {'))]
        for st in starts:
            e = next((i for i in range(st + 1, len(L)) if L[i].startswith('}')), len(L))
            i = st + 1
            while i < e and (DECL.match(L[i]) or not L[i].strip()):
                i += 1
            for j in range(i, e):
                l = L[j]
                m = re.match(r'^(\s+)((?:const\s+|unsigned\s+|struct\s+)*[A-Za-z_][\w:]*(?:\s*\*+\s*|\s+))([A-Za-z_]\w*)(\[[^\]]*\])?\s*(=\s*(.*))?;\s*(//.*|/\*.*)?$', l)
                if not m or m.group(2).strip() in ('return', 'goto', 'delete', 'else', 'case', 'new'):
                    continue
                ty, nm, arr, init = m.group(2), m.group(3), m.group(4) or '', m.group(6)
                for pos in ('top', 'bottom'):
                    M = L[:]
                    d = '    ' + ty.rstrip() + (' ' if not ty.rstrip().endswith('*') else '') + nm + arr + ';'
                    if init is None:
                        M[j] = ''
                    else:
                        if arr:
                            continue
                        M[j] = m.group(1) + nm + ' = ' + init + ';'
                    if pos == 'top':
                        M[st] = M[st] + '\n' + d
                    else:
                        M[i - 1] = M[i - 1] + '\n' + d
                    M = '\n'.join(M).split('\n')
                    out.append(('hoist %s line %d (%s)' % (pos, j + 1, l.strip()[:40]), M))
    if cmd == 'unlever':
        lo = s0 + 1 if s0 >= 0 else 0
        for i in range(lo, e0):
            l = L[i]
            for m in re.finditer(r'\s*if \(!?[A-Za-z_0-9]+\) \{\s*\}', l):
                M = L[:]
                M[i] = l[:m.start()] + l[m.end():]
                out.append(('rm if1 line %d: %s' % (i + 1, l.strip()[:50]), M))
            if re.match(r'^\s*if \(1\) \{\s*$', l):
                d = 0
                for j in range(i, e0):
                    d += L[j].count('{') - L[j].count('}')
                    if d == 0:
                        break
                if d == 0 and L[j].strip() == '}':
                    M = L[:]
                    M[i] = ''
                    M[j] = ''
                    out.append(('rm if1-block line %d' % (i + 1), M))
            for m in re.finditer(r'\bvolatile\s+', l):
                M = L[:]
                M[i] = l[:m.start()] + l[m.end():]
                out.append(('rm volatile line %d: %s' % (i + 1, l.strip()[:50]), M))
            if re.match(r'^\s+[^=()]*\bpad\w*\b[^()]*;', l) and not l.strip().startswith(('//', '/*', '*')):
                M = L[:]
                M[i] = ''
                out.append(('rm pad line %d: %s' % (i + 1, l.strip()[:50]), M))
            if re.match(r'^\s*\}\s*while \(0\);', l):
                out.append(('(while0 at %d: manual)' % (i + 1), L[:]))
    return out


def probe(job):
    tag, lines = job
    c = CTX
    p = os.path.join(c['work'], 'v%s%s' % (tag, c['ext']))
    o = p.rsplit('.', 1)[0] + '.o'
    open(p, 'w').write('\n'.join(lines))
    try:
        if c['intree']:
            pp = p[:-2] + '_pp.c'
            with open(pp, 'w') as f:
                subprocess.run(['python3', c['wt'] + '/tools/asm-processor/asm_processor.py', '-O2', p],
                               stdout=f, stderr=subprocess.DEVNULL, cwd=c['wt'])
            r = subprocess.run([c['cc']] + ['-c'] + c['flags'].split() +
                               ['-I', 'include', '-I', 'src', '-DNON_MATCHING', '-o', o, pp],
                               capture_output=True, text=True, cwd=c['wt'])
        else:
            r = subprocess.run([c['cc'], '-c'] + c['flags'].split() +
                               ['-I', os.path.join(c['wt'], 'include'), '-I', os.path.join(c['wt'], 'src'), '-o', o, p],
                               capture_output=True, text=True, cwd=os.path.dirname(c['src']))
        if r.returncode or not os.path.exists(o):
            return tag, None
        if not c['intree']:
            nm = subprocess.run(['mips-linux-gnu-nm', o], capture_output=True, text=True).stdout.split('\n')
            T = [l.split()[2] for l in nm if len(l.split()) == 3 and l.split()[1] == 'T']
            if c['fn'] not in T and T:
                cand = [t for t in T if '__' in t and not t.startswith('__sti')] or T
                subprocess.run(['mips-linux-gnu-objcopy', '--redefine-sym', cand[0] + '=' + c['fn'], o])
        d = json.loads(subprocess.run(['objdiff-cli', 'diff', '-c', 'functionRelocDiffs=none', '-1', c['target'], '-2', o, '-o', '-', c['fn']],
                                      capture_output=True, text=True).stdout)
        Lf = [x for x in d['left']['symbols'] if x['name'] == c['fn']][0]
        Rf = [x for x in d['right']['symbols'] if x['name'] == c['fn']][0]
        return tag, (Lf.get('match_percent', 0), int(Rf['size']), int(Lf['size']))
    except Exception:
        return tag, None
    finally:
        for q in (p, o, p[:-2] + '_pp.c'):
            if q != p and os.path.exists(q):
                os.remove(q)


def init(ctx):
    CTX.update(ctx)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['denaming', 'volatile', 'order', 'bbsplit', 'all', 'unlever', 'declmove', 'hoist'])
    ap.add_argument('--src', required=True)
    ap.add_argument('--fn', required=True)
    ap.add_argument('--target', required=True, help='target .o, relative to --wt (or absolute)')
    ap.add_argument('--wt', default=None)
    ap.add_argument('--flags', default=None)
    ap.add_argument('--jobs', type=int, default=8)
    ap.add_argument('--work', default=None, help='scratch dir (default /tmp/claude-1000/lever-sweep/<fn>)')
    ap.add_argument('--all-results', action='store_true')
    a = ap.parse_args()
    src = os.path.abspath(a.src)
    wt = os.path.abspath(a.wt) if a.wt else None
    if wt is None:
        d = os.path.dirname(src)
        while d != '/' and not (os.path.exists(os.path.join(d, 'Makefile')) and os.path.isdir(os.path.join(d, 'src'))):
            d = os.path.dirname(d)
        wt = d
    ext = os.path.splitext(src)[1]
    intree = ext == '.c' and src.startswith(os.path.join(wt, 'src') + os.sep)
    work = os.path.abspath(a.work or '/tmp/claude-1000/lever-sweep/' + a.fn)
    if work.startswith(os.path.join(wt, 'src')):
        sys.exit('--work must not be inside src/')
    os.makedirs(work, exist_ok=True)
    ctx = dict(wt=wt, src=src, ext=ext, intree=intree, work=work, fn=a.fn,
               target=a.target if os.path.isabs(a.target) else os.path.join(wt, a.target),
               cc=os.path.join(wt, 'tools/ido-static-recomp/build/7.1/out', 'NCC' if ext == '.cpp' else 'cc'),
               flags=a.flags or (NCC_FLAGS if ext == '.cpp' else CFE_FLAGS))
    if intree:
        try:
            mk = open(os.path.join(wt, 'Makefile')).read()
            if re.search(r'REPLACE_FUNC_BODY\s*\+=\s*%s=' % re.escape(a.fn), mk):
                print('WARNING: %s has a REPLACE_FUNC_BODY donor in the Makefile; the in-tree body never reaches '
                      'report.json in the non_matching build. Sweep the donor source instead.' % a.fn, flush=True)
        except OSError:
            pass
    L = open(src).read().split('\n')
    s0, e0 = find_body(L, a.fn, not intree)
    V = variants(a.cmd, L, s0, e0)
    jobs = [('base', L)] + [('%04d' % n, M) for n, (_, M) in enumerate(V)]
    labels = {'base': 'base'}
    labels.update({'%04d' % n: lab for n, (lab, _) in enumerate(V)})
    print('%d variants (%s, %s)' % (len(jobs) - 1, a.cmd, 'in-tree cfe' if intree else 'standalone'), flush=True)
    with ProcessPoolExecutor(a.jobs, initializer=init, initargs=(ctx,)) as ex:
        res = dict(ex.map(probe, jobs))
    base = res.get('base')
    print('base', base)
    if base is None:
        sys.exit('base does not compile/score')
    rows = [(res[t], labels[t]) for t in res if t != 'base' and res[t] is not None]
    fails = sum(1 for t in res if res[t] is None)
    rows.sort(key=lambda r: (-r[0][0], abs(r[0][1] - r[0][2])))
    for s, lab in rows:
        if a.all_results or s[0] > base[0] + 1e-3:
            print('%s%.3f  size %d/%d  %s' % ('GAIN ' if s[0] > base[0] + 1e-3 else '     ', s[0], s[1], s[2], lab))
    print('done: %d scored, %d failed to compile' % (len(rows), fails))


if __name__ == '__main__':
    main()
