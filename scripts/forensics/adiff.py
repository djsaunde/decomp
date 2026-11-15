import sys, re, subprocess, difflib
# usage: adiff.py ours.o sym target.s  -> aligned mnemonic diff (objdump no-aliases), reloc imms ignored
o, sym, s = sys.argv[1:4]
txt = subprocess.run(['mips-linux-gnu-objdump', '-d', '-M', 'no-aliases', '--disassemble=' + sym, o], capture_output=True, text=True).stdout
ours = [l.split('\t', 2)[2].strip() for l in txt.split('\n') if re.match(r'\s+[0-9a-f]+:\t', l) and len(l.split('\t')) > 2]
words = [m.group(1) for m in re.finditer(r'/\* [0-9A-F]+ [0-9A-F]+ ([0-9A-F]{8}) \*/', open(s).read())]
open('/tmp/claude-1000/c349/adiff_t.bin', 'wb').write(bytes.fromhex(''.join(words)))
t2 = subprocess.run(['mips-linux-gnu-objdump', '-D', '-b', 'binary', '-m', 'mips:4300', '-EB', '-M', 'no-aliases', '/tmp/claude-1000/c349/adiff_t.bin'], capture_output=True, text=True).stdout
tgt = [l.split('\t', 2)[2].strip() for l in t2.split('\n') if re.match(r'\s+[0-9a-f]+:\t', l) and len(l.split('\t')) > 2]
norm = lambda x: re.sub(r'0x[0-9a-f]+|\b\d+\b', 'N', x.split('<')[0]).strip()
a = [norm(x) for x in ours]; b = [norm(x) for x in tgt]
sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
eq = sum(bl.size for bl in sm.get_matching_blocks())
print(f'ours {len(a)} target {len(b)} aligned-equal {eq}  ratio {sm.ratio():.4f}')
if len(sys.argv) > 4:
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op != 'equal':
            print(op, 'ours', i1, ours[i1:i2], '| tgt', j1, tgt[j1:j2])
