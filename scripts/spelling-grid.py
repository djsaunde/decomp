#!/usr/bin/env python3
"""Spelling-grid search: try explicit, semantics-preserving source alternatives and score each
compile against the target with objdiff (~1 s per probe, parallel).

This is NOT the permuter: it never invents code. It only enumerates alternatives YOU write into a
template copy of a standalone donor (.cpp for NCC, .c for cfe). Every alternative must mean the same
thing (operand order, increment spelling, inline routing, decl order, statement order of independent
stores, line layout, ...). Results still have to pass the normal gate; the tool never touches src/.

Template markers (no nesting):
  @{ altA @| altB @| altC }@     choose one alternative (an alternative may be empty)
  @[ stmt1 @; stmt2 @; stmt3 ]@  try every order of the items (<= 7 items)
  @{=NAME altA @| altB }@        named group: every marker with the same NAME takes the same index

Output columns: objdiff match %, rows objdiff marks as differing, size vs target. `--render "alt0=1 perm3=2"`
scores and writes just that combination. Under NCC, K&R `()` externs fail to compile: declare them `(...)`.

Search: exhaustive when the product is <= --max-full, otherwise greedy coordinate descent
(one marker at a time, repeated until a full round brings no gain), then a pairwise pass over the
most sensitive markers. Score = objdiff match_percent for --fn; ties prefer size closer to target.

usage:
  spelling-grid.py --wt projects/1080-agent-c --src /tmp/claude-1000/x/t.cpp --fn gl_func_00037348 \
      --target build/src/game_libs/game_libs_post0b.c.o [--flags "..."] [--jobs 8] [--out best.cpp]
"""
import argparse, itertools, json, os, re, shutil, subprocess, sys, tempfile, hashlib
from concurrent.futures import ProcessPoolExecutor

MARK = re.compile(r'@\{(=\w+)?(.*?)\}@|@\[(.*?)\]@', re.S)
DEF_FLAGS = {'.cpp': '-G 0 -non_shared -Wab,-r4300_mul -O2 -mips2 -32',
             '.c': '-G 0 -non_shared -Xcpluscomm -Wab,-r4300_mul -O2 -mips2 -32'}


def parse(text):
    """Split the template into literal chunks and markers. Returns (chunks, markers)."""
    chunks, markers, pos = [], [], 0
    for m in MARK.finditer(text):
        chunks.append(text[pos:m.start()])
        if m.group(3) is not None:
            items = [s.strip('\n') for s in m.group(3).split('@;')]
            if len(items) > 7: sys.exit(f'permutation block with {len(items)} items (max 7)')
            alts = ['\n'.join(p) for p in itertools.permutations(items)]
            markers.append({'name': None, 'alts': alts, 'kind': 'perm', 'label': f'perm{len(markers)}'})
        else:
            name = m.group(1)[1:] if m.group(1) else None
            alts = m.group(2).split('@|')
            markers.append({'name': name, 'alts': alts, 'kind': 'alt', 'label': name or f'alt{len(markers)}'})
        pos = m.end()
    chunks.append(text[pos:])
    for mk in markers:
        if any('@{' in s or '@[' in s or '}@' in s or ']@' in s for s in mk['alts']):
            sys.exit(f'nested marker inside {mk["label"]}: markers cannot nest; use named groups @{{=NAME ..}}@ instead')
    for mk in markers:
        if any(s.rstrip().endswith('@') for s in mk['alts']):
            sys.exit(f'{mk["label"]}: an alternative ends in "@" (typo "@}}@" for "}}@" or "@]@" for "]@"?)')
    if any('@{' in c or '@[' in c or '@|' in c or '@;' in c for c in chunks):
        sys.exit('unbalanced marker: a stray @{ @[ @| or @; is outside any complete marker')
    return chunks, markers


def groups(markers):
    """Collapse named markers into one choice dimension each. Returns list of (label, n_alts, [marker idx])."""
    dims, byname = [], {}
    for i, mk in enumerate(markers):
        if mk['name']:
            if mk['name'] in byname:
                d = dims[byname[mk['name']]]
                if len(mk['alts']) != d[1]: sys.exit(f'named group {mk["name"]} has differing alt counts')
                d[2].append(i); continue
            byname[mk['name']] = len(dims)
        dims.append([mk['label'], len(mk['alts']), [i]])
    return dims


def render(chunks, markers, dims, choice):
    pick = [0] * len(markers)
    for (label, n, idxs), c in zip(dims, choice):
        for i in idxs: pick[i] = c
    out = [chunks[0]]
    for i, mk in enumerate(markers):
        out.append(mk['alts'][pick[i]]); out.append(chunks[i + 1])
    return ''.join(out)


CTX = {}


def init(ctx):
    CTX.update(ctx)


def probe(job):
    """Compile one rendered source and score it. Returns (choice, score, size, err)."""
    choice, text = job
    # include the choice so identical renderings from different choices never share a probe dir
    h = hashlib.sha1((repr(choice) + text).encode()).hexdigest()[:16]
    d = os.path.join(CTX['tmp'], h); os.makedirs(d, exist_ok=True)
    src = os.path.join(d, 'p' + CTX['ext']); obj = os.path.join(d, 'p.o')
    with open(src, 'w') as f: f.write(text)
    cmd = [CTX['cc'], '-c'] + CTX['flags'] + ['-o', obj, src]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=CTX['wt'], timeout=120)
    except subprocess.TimeoutExpired:
        return choice, -1.0, 0, 'compile timeout'
    if r.returncode or not os.path.exists(obj):
        return choice, -1.0, 0, '\n'.join((r.stdout + r.stderr).strip().splitlines()[-12:]) or 'compile failed'
    fn = CTX['fn']
    nm = subprocess.run(['mips-linux-gnu-nm', obj], capture_output=True, text=True).stdout.split('\n')
    T = [l.split()[2] for l in nm if len(l.split()) == 3 and l.split()[1] in 'Tt']
    if fn not in T:
        cand = [t for t in T if CTX['sym'] and t == CTX['sym']] or \
               [t for t in T if '__' in t and not t.startswith('__sti')] or T
        if not cand: return choice, -1.0, 0, 'no text symbol'
        subprocess.run(['mips-linux-gnu-objcopy', '--redefine-sym', cand[0] + '=' + fn, obj])
    try:
        out = subprocess.run(['objdiff-cli', 'diff', '-c', 'functionRelocDiffs=none', '-1', CTX['target'], '-2', obj, '-o', '-', fn],
                             capture_output=True, text=True, timeout=120).stdout
        dj = json.loads(out)
        L = [s for s in dj['left']['symbols'] if s['name'] == fn][0]
        R = [s for s in dj['right']['symbols'] if s['name'] == fn]
        size = int(R[0]['size']) if R else 0
        rows = sum(1 for ins in L.get('instructions', []) if ins.get('diff_kind'))
        return choice, float(L.get('match_percent', 0) or 0), size, (None, rows)
    except Exception as e:
        return choice, -1.0, 0, f'score failed: {e}'
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--wt', required=True, help='project worktree (compile cwd; tools/ and include/ live here)')
    ap.add_argument('--src', required=True, help='template file with @{..}@ / @[..]@ markers (keep it outside src/)')
    ap.add_argument('--fn', required=True, help='function symbol in the target object')
    ap.add_argument('--target', required=True, help='target object, relative to --wt (e.g. build/src/.../unit.c.o)')
    ap.add_argument('--sym', default='', help='donor symbol to rename to --fn (default: first mangled T symbol)')
    ap.add_argument('--flags', default=None, help='compiler flags (default: Makefile NCC/cfe flags at -O2)')
    ap.add_argument('--jobs', type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument('--max-full', type=int, default=3000, help='exhaustive search up to this many combos')
    ap.add_argument('--rounds', type=int, default=6, help='max coordinate-descent rounds')
    ap.add_argument('--top', type=int, default=10)
    ap.add_argument('--out', default='', help='write the best rendered source here (outside src/)')
    ap.add_argument('--render', default=None, metavar='"alt0=1 perm3=2"',
                    help='score and write ONLY this combination (labels as printed; unnamed = 0) to --out')
    a = ap.parse_args()

    wt = os.path.abspath(a.wt)
    src = os.path.abspath(a.src)
    if os.path.commonpath([src, os.path.join(wt, 'src')]) == os.path.join(wt, 'src'):
        sys.exit('refusing: keep the template outside src/ (sweeps never write into src/)')
    ext = os.path.splitext(src)[1]
    if ext not in DEF_FLAGS: sys.exit('template must be .c or .cpp')
    cc = os.path.join(wt, 'tools/ido-static-recomp/build/7.1/out', 'NCC' if ext == '.cpp' else 'cc')
    flags = (a.flags if a.flags is not None else DEF_FLAGS[ext]).split() + ['-I', 'include', '-I', 'src']
    target = os.path.join(wt, a.target)
    if not os.path.exists(target): sys.exit(f'no target object {target} (run make first)')

    chunks, markers = parse(open(src).read())
    if not markers: sys.exit('no @{..}@ / @[..]@ markers in template')
    dims = groups(markers)
    sizes = [d[1] for d in dims]
    total = 1
    for n in sizes: total *= n
    tmp = tempfile.mkdtemp(prefix='spelling-grid-', dir='/tmp/claude-1000' if os.path.isdir('/tmp/claude-1000') else None)
    ctx = dict(cc=cc, flags=flags, wt=wt, fn=a.fn, sym=a.sym, target=target, ext=ext, tmp=tmp)
    print(f'{len(dims)} choice dimensions {sizes} -> {total} combinations; jobs={a.jobs}', flush=True)
    want = None
    if a.render is not None:
        lab = {d[0]: i for i, d in enumerate(dims)}
        want = [0] * len(dims)
        for tok in a.render.split():
            k, _, v = tok.partition('=')
            if k not in lab or not v.isdigit() or int(v) >= dims[lab[k]][1]: sys.exit(f'bad --render item {tok}')
            want[lab[k]] = int(v)
        want = tuple(want)

    seen = {}

    def run(choices, pool):
        jobs = [(c, render(chunks, markers, dims, c)) for c in choices if c not in seen]
        for c, s, z, res in pool.map(probe, jobs):
            if isinstance(res, tuple): seen[c] = (s, z, None, res[1])
            else: seen[c] = (s, z, res, -1)
        return [(c, seen[c]) for c in choices]

    def key(item):
        c, (s, z, err, rows) = item
        return (s, -abs(z - tsize) if tsize else 0, -rows)

    with ProcessPoolExecutor(max_workers=a.jobs, initializer=init, initargs=(ctx,)) as pool:
        base = want if want is not None else tuple([0] * len(dims))
        run([base], pool)
        s0, z0, e0, r0 = seen[base]
        if e0:
            print('baseline (all first alternatives) failed to compile/score; compiler output:')
            print(e0); shutil.rmtree(tmp, ignore_errors=True); sys.exit(1)
        dj = json.loads(subprocess.run(['objdiff-cli', 'diff', '-c', 'functionRelocDiffs=none', '-1', target, '-2', target, '-o', '-', a.fn],
                                       capture_output=True, text=True).stdout or '{}')
        tsize = next((int(s['size']) for s in dj.get('left', {}).get('symbols', []) if s['name'] == a.fn), 0)
        tag = '--render' if want else 'first alternatives'
        print(f'baseline ({tag}): {s0:.4f}  {r0} diff rows  size {z0} (target {tsize})', flush=True)

        if a.render is not None:
            pass
        elif total <= a.max_full:
            run(list(itertools.product(*[range(n) for n in sizes])), pool)
        else:
            best = base
            for rnd in range(a.rounds):
                improved = False
                for di, n in enumerate(sizes):
                    cands = [best[:di] + (k,) + best[di + 1:] for k in range(n)]
                    res = max(run(cands, pool), key=key)
                    if key(res) > key((best, seen[best])):
                        best = res[0]; improved = True
                print(f'round {rnd + 1}: best {seen[best][0]:.4f} ({len(seen)} probes)', flush=True)
                if not improved: break
            # pairwise pass over the dimensions whose single changes moved the score most
            sens = []
            for di, n in enumerate(sizes):
                vals = [seen.get(best[:di] + (k,) + best[di + 1:], (-1,))[0] for k in range(n)]
                sens.append((max(vals) - min(v for v in vals if v >= 0) if any(v >= 0 for v in vals) else 0, di))
            hot = [di for _, di in sorted(sens, reverse=True)[:6]]
            pairs = []
            for x, y in itertools.combinations(hot, 2):
                for kx in range(sizes[x]):
                    for ky in range(sizes[y]):
                        c = list(best); c[x] = kx; c[y] = ky; pairs.append(tuple(c))
            if pairs and len(pairs) <= a.max_full:
                run(pairs, pool)
                print(f'pairwise: {len(pairs)} combos, {len(seen)} probes total', flush=True)

    ok = [(c, v) for c, v in seen.items() if not v[2]]
    fails = len(seen) - len(ok)
    ok.sort(key=key, reverse=True)
    print(f'\n{len(seen)} probes, {fails} failed to compile/score. Top {a.top}:')
    for c, (s, z, _, rows) in ok[:a.top]:
        desc = ' '.join(f'{d[0]}={k}' for d, k in zip(dims, c) if k)
        print(f'  {s:8.4f}  {rows:4d} rows  size {z}{"" if z == tsize else f" ({z - tsize:+d})"}  {desc or "(all first)"}')
    if fails:
        c, v = next((c, v) for c, v in seen.items() if v[2])
        print('first compile/score failure:', ' '.join(f'{d[0]}={k}' for d, k in zip(dims, c) if k) or '(all first)')
        print('  ' + str(v[2]).replace('\n', '\n  '))
    if ok and a.out:
        out = os.path.abspath(a.out)
        if os.path.commonpath([out, os.path.join(wt, 'src')]) == os.path.join(wt, 'src'):
            print('not writing --out inside src/; copy the winner in by hand after checking it')
        else:
            with open(out, 'w') as f: f.write(render(chunks, markers, dims, ok[0][0]))
            print(f'best source -> {out}')
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
