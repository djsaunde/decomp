#!/usr/bin/env python3
# tdscan.py LISTHTML BASEURL : read the first 64 KB of each tardist member, report idbs shipping as1/ugen/uopt/cfe
import sys, re, io, tarfile, urllib.request
from concurrent.futures import ThreadPoolExecutor
html = open(sys.argv[1]).read(); base = sys.argv[2]
names = sorted(set(re.findall(r'patches_6\.2\.tar/(patchSG\d+\.tardist)"', html)))
def go(n):
    try:
        r = urllib.request.urlopen(base + n, timeout=60); b = r.read(1 << 17); r.close()
    except Exception as e: return n, 'ERR %s' % e, []
    hits = []; desc = ''
    try:
        tf = tarfile.open(fileobj=io.BytesIO(b), mode='r|')
        for m in tf:
            if m.name.endswith('.idb'):
                t = tf.extractfile(m).read().decode('latin1')
                for l in t.split('\n'):
                    f = l.split()
                    if len(f) > 6 and f[0] == 'f' and re.search(r'(^|/)usr/lib/(as1|ugen|uopt|cfe|as0)$', f[4]):
                        hits.append((f[4], [x for x in f if x.startswith(('sum(', 'size('))]))
                break
    except Exception as e:
        desc = 'tarerr %s' % e
    return n, desc, hits
with ThreadPoolExecutor(6) as ex:
    n_ok = 0
    for n, desc, hits in ex.map(go, names):
        if desc: print(n, desc)
        if hits: print('##', n, hits)
print('tardists', len(names))
