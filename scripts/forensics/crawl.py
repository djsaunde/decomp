import sys, re, urllib.request, urllib.parse, concurrent.futures as cf, os
B='https://discmaster.textfiles.com'
def get(p):
    u=B+urllib.parse.quote(p)
    try: return urllib.request.urlopen(u,timeout=30).read().decode('latin1')
    except Exception as e: return ''
def ls(p):
    h=get('/browse'+p)
    out=set()
    for m in re.finditer(r'href="(/browse[^"?]*)"',h):
        q=urllib.parse.unquote(m.group(1))[len('/browse'):]
        q=q.replace('&amp;','&')
        if q.startswith(p+'/') and q.count('/')==p.count('/')+1: out.add(q)
    return sorted(out)
roots=sys.argv[1:]
idbs=[]
def walk(p,d):
    for q in ls(p):
        n=q.rsplit('/',1)[1]
        if n.endswith('.idb'): idbs.append(q)
        elif d>0 and '.' not in n[-4:]: walk(q,d-1)
for r in roots: walk(r,2)
def chk(q):
    t=get('/file'+q)
    hits=[l for l in t.split('\n') if re.search(r' usr/lib/(as1|ugen|uopt|cfe) |/usr/lib/as1 ',l)]
    return q,hits
with cf.ThreadPoolExecutor(6) as ex:
    for q,h in ex.map(chk,idbs):
        if h:
            print('##',q)
            for l in h: 
                p=l.split(); print('   ',p[4],p[5],[x for x in p if x.startswith(('sum(','size('))])
print('idbs scanned',len(idbs),file=sys.stderr)
