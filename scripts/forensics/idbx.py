# extract regular files from IRIX inst .idb + .sw* into outdir (safe paths only)
import sys,os,re,subprocess
idb,swdir,out,want=sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4:]
for line in open(idb,encoding='latin1'):
    p=line.split()
    if not p or p[0]!='f': continue
    dst=p[4]; sub=p[6]
    if want and not any(w in dst for w in want): continue
    m=re.search(r'cmpsize\((\d+)\)',line); cs=int(m.group(1))
    sz=int(re.search(r' size\((\d+)\)',line).group(1))
    swf=os.path.join(swdir, os.path.basename(idb)[:-4]+'.'+sub.split('.')[1])
    data=open(swf,'rb').read()
    key=b'\x00'+bytes([len(dst)])+dst.encode()
    i=data.find(key)
    assert i>=0,(dst,swf)
    s=i+len(key); n=cs if cs else sz
    blob=data[s:s+n]
    if cs:
        blob=subprocess.run(['gzip','-dc'],input=blob,capture_output=True).stdout
    assert '..' not in dst and not dst.startswith('/')
    o=os.path.join(out,dst); os.makedirs(os.path.dirname(o),exist_ok=True)
    open(o,'wb').write(blob)
    print(dst,len(blob),'expect',sz,'OK' if len(blob)==sz else 'MISMATCH')
