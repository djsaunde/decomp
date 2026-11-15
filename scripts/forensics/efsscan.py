#!/usr/bin/env python3
# efsscan.py IMG : list every idb in an SGI EFS image (volume header + EFS) that ships usr/lib/as1|ugen|uopt|cfe|as0
# (agent-h run 393; uses efs.py from the same directory)
import sys, re, os
img = sys.argv[1]
here = os.path.dirname(os.path.abspath(__file__))
sys.argv = ['efs.py', img, 'none']
exec(open(os.path.join(here, 'efs.py')).read().split("cmd = sys.argv[2]")[0])
n = 0
for p, size, inum in walk(2, ''):
    if p.endswith('.idb'):
        n += 1
        for l in data(inum).decode('latin1').split('\n'):
            f = l.split()
            if len(f) > 6 and f[0] == 'f' and re.search(r'(^|/)usr/lib/(as1|ugen|uopt|cfe|as0)$', f[4]):
                print(p, f[4], [x for x in f if x.startswith(('sum(', 'size('))])
print('idbs', n)
