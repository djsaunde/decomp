import sys, re, subprocess, struct
# usage: score.py donor.o symbol target.s
o, sym, s = sys.argv[1:4]
tgt = [int(m.group(1), 16) for m in re.finditer(r'/\* [0-9A-F]+ [0-9A-F]+ ([0-9A-F]{8}) \*/', open(s).read())]
syms = subprocess.run(['mips-linux-gnu-nm', '-S', o], capture_output=True, text=True).stdout.split('\n')
addr = size = None
for l in syms:
    p = l.split()
    if len(p) == 4 and p[3] == sym: addr, size = int(p[0], 16), int(p[1], 16)
    if len(p) == 4 and sym.startswith('~') and sym[1:] in p[3]: addr, size, sym = int(p[0], 16), int(p[1], 16), p[3]
if addr is None:
    print('symbol not found; candidates:', [l for l in syms if ' T ' in l][:20]); sys.exit(1)
subprocess.run(['mips-linux-gnu-objcopy', '-O', 'binary', '-j', '.text', o, '/tmp/claude-1000/c349/score_text.bin'], check=True)
b = open('/tmp/claude-1000/c349/score_text.bin', 'rb').read()[addr:addr + size]
ours = list(struct.unpack('>%dI' % (len(b) // 4), b[:len(b) // 4 * 4]))
def mask(w):
    op = w >> 26
    if op in (2, 3): return w & 0xFC000000
    if op in (0x0F, 0x09, 0x23, 0x2B, 0x21, 0x25, 0x24, 0x20, 0x28, 0x29, 0x31, 0x39, 0x35, 0x3D): return w & 0xFFFF0000
    return w
n = min(len(ours), len(tgt))
eq = sum(1 for i in range(n) if mask(ours[i]) == mask(tgt[i]))
print(f'{sym}: ours {len(ours)} words, target {len(tgt)} words, masked-equal {eq}/{max(len(ours), len(tgt))} = {100.0*eq/max(len(ours),len(tgt)):.2f}%')
