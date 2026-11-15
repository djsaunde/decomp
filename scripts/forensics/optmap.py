import re,glob,os
R='/home/danjs/code/decomp/projects/1080-agent-d'
lines=open(R+'/Makefile').read().split('\n')
var={}; optl={}
for l in lines:
    m=re.match(r'^(\w+)\s*:=\s*(build/src/\S+\.cpp\.o)\s*$',l)
    if m: var[m.group(2)]=m.group(1)
    if 'OPT_FLAGS' in l and ':' in l:
        m=re.search(r':\s*(?:private\s+)?OPT_FLAGS\s*:=\s*(-O\d)',l)
        if m:
            tg=l.split(':')[0].split()
            for t in tg: optl[t]=m.group(1)
for f in sorted(glob.glob(R+'/src/*/*_ncc_*.cpp')):
    if '_nm' in os.path.basename(f): continue
    rel=f[len(R)+1:]; obj='build/'+rel+'.o'
    opt=optl.get(obj) or (obj in var and optl.get('$('+var[obj]+')')) or '-O2'
    print(rel,opt)
