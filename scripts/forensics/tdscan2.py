#!/usr/bin/env python3
# tdscan2.py NAMESFILE BASEURL : stream each tardist until its .idb member, report idbs shipping as1/ugen/uopt/cfe/as0
import sys, re, tarfile, urllib.request
from concurrent.futures import ThreadPoolExecutor
names = [l.split()[0] for l in open(sys.argv[1]) if l.strip()]
base = sys.argv[2]
def go(n):
    hits = []
    try:
        r = urllib.request.urlopen(base + n, timeout=120)
        tf = tarfile.open(fileobj=r, mode='r|')
        for m in tf:
            if m.name.endswith('.idb'):
                t = tf.extractfile(m).read().decode('latin1')
                for l in t.split('\n'):
                    f = l.split()
                    if len(f) > 6 and f[0] == 'f' and re.search(r'(^|/)usr/lib/(as1|ugen|uopt|cfe|as0)$', f[4]):
                        hits.append((f[4], f[5], [x for x in f if x.startswith(('sum(', 'size('))]))
                r.close(); return n, 'ok', hits
        return n, 'noidb', hits
    except Exception as e:
        return n, 'ERR %s' % e, hits
with ThreadPoolExecutor(6) as ex:
    for n, st, hits in ex.map(go, names):
        if st != 'ok' or hits: print(n, st, hits, flush=True)
print('done', len(names))
