#!/usr/bin/env python3
# efs.py IMG ls [PATTERN]        : list every regular file (path size) in an SGI EFS image (volume header + EFS)
# efs.py IMG get PATH OUTDIR     : extract one file (safe relative output path)
import sys, struct, os, re

img = open(sys.argv[1], 'rb')
def rd(off, n):
    img.seek(off); return img.read(n)

# volume header -> partition with an EFS superblock
vh = rd(0, 512)
assert struct.unpack('>I', vh[:4])[0] == 0x0BE5A941, 'no SGI volume header'
part = None
for i in range(16):
    nblks, first, typ = struct.unpack('>IIi', vh[312 + 12 * i: 324 + 12 * i])
    if nblks == 0: continue
    sb = rd(first * 512 + 512, 512)
    if struct.unpack('>I', sb[28:32])[0] in (0x072959, 0x07295A):
        part = first * 512; break
assert part is not None, 'no EFS partition'
sb = rd(part + 512, 512)
fs_size, firstcg, cgfsize = struct.unpack('>iii', sb[0:12])
cgisize, = struct.unpack('>h', sb[12:14])
BS = 512
def blk(bn, n=1): return rd(part + bn * BS, n * BS)

def inode(ino):
    per = cgisize * 4
    cg, r = divmod(ino, per)
    bn = firstcg + cg * cgfsize + r // 4
    return blk(bn)[(r % 4) * 128:(r % 4) * 128 + 128]

def extents(ino):
    d = inode(ino)
    mode, = struct.unpack('>H', d[0:2]); size, = struct.unpack('>i', d[8:12])
    nex, = struct.unpack('>h', d[28:30])
    raw = [struct.unpack('>II', d[32 + 8 * i: 40 + 8 * i]) for i in range(12)]
    ex = [(w0 & 0xFFFFFF, w1 >> 24, w1 & 0xFFFFFF) for w0, w1 in raw]
    if nex > 12:
        nind = ex[0][2]
        out = []
        for bn, ln, _ in ex[:nind]:
            b = blk(bn, ln)
            for j in range(len(b) // 8):
                w0, w1 = struct.unpack('>II', b[8 * j: 8 * j + 8])
                out.append((w0 & 0xFFFFFF, w1 >> 24, w1 & 0xFFFFFF))
        ex = out[:nex]
    else:
        ex = ex[:nex]
    return mode, size, ex

def data(ino):
    mode, size, ex = extents(ino)
    buf = bytearray()
    for bn, ln, off in sorted(ex, key=lambda e: e[2]):
        if len(buf) < off * BS: buf.extend(b'\0' * (off * BS - len(buf)))
        buf[off * BS: off * BS + ln * BS] = blk(bn, ln)
    return bytes(buf[:size])

def readdir(ino):
    d = data(ino); out = []
    for b in range(0, len(d), BS):
        blkd = d[b:b + BS]
        if struct.unpack('>H', blkd[0:2])[0] != 0xBEEF: continue
        slots = blkd[3]
        for s in range(slots):
            o = blkd[4 + s]
            if o == 0: continue
            o <<= 1
            inum, = struct.unpack('>I', blkd[o:o + 4]); nl = blkd[o + 4]
            name = blkd[o + 5:o + 5 + nl].decode('latin1')
            if name not in ('.', '..'): out.append((name, inum))
    return out

def walk(ino, path, depth=0):
    for name, inum in readdir(ino):
        mode, size, _ = extents(inum)
        p = path + '/' + name
        t = mode & 0xF000
        if t == 0x4000 and depth < 12: yield from walk(inum, p, depth + 1)
        elif t == 0x8000: yield p, size, inum

cmd = sys.argv[2]
if cmd == 'ls':
    pat = re.compile(sys.argv[3]) if len(sys.argv) > 3 else None
    for p, size, inum in walk(2, ''):
        if pat is None or pat.search(p): print(p, size)
elif cmd == 'get':
    want, outd = sys.argv[3], sys.argv[4]
    for p, size, inum in walk(2, ''):
        if p == want:
            rel = p.lstrip('/'); assert '..' not in rel
            o = os.path.join(outd, rel); os.makedirs(os.path.dirname(o), exist_ok=True)
            open(o, 'wb').write(data(inum)); print('wrote', o, size)
