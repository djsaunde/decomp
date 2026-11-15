#!/bin/bash
# usage: accom.sh in.c out.o [OPT=-O2] [BE=41|71|53] -- IDO 4.1 accom (pcc-derived ANSI C front end) + chosen backend
set -e
IN=$1; OUT=$2; OPT=${3:--O2}; BE=${4:-41}
Q=/home/danjs/code/decomp/tools/forensics/scripts/q41.sh; F=/home/danjs/code/decomp/tools/forensics/ido4.1
R=/home/danjs/code/decomp/projects/1080-agent-c/tools/ido-static-recomp/build
T=$(mktemp -d /tmp/claude-1000/c349/actmp.XXXXXX); cp "$IN" $T/in.c; cd $T
cpp -P -undef -D__STDC__=1 -DLANGUAGE_C -D_LANGUAGE_C -Dmips -D__mips=2 -D_MIPSEB $CPPFLAGS in.c > in.i
$Q $F/usr/lib/accom -mips2 -EB -Xg0 $OPT -Xprototypes -Xxansi -XS$T/t.S < in.i > t.B
if [ "$BE" = 41 ]; then
  $Q $F/usr/lib/uopt -G 0 -mips2 -EB -g0 $OPT t.B t.O -t t.S t.os
  $Q $F/usr/lib/ugen -G 0 -mips2 -EB -g0 $OPT t.O -o t.G -t t.S -temp t.gt
  $Q $F/usr/lib/as1 -G 0 -p0 -mips2 -EB -g0 $OPT t.G -o out.o -t t.S
  python3 $F/usr/bin/ecoff_tool.py --convert-elf out.o -o out.elf.o 2>/dev/null && mv out.elf.o out.o || true
else
  B=$R/7.1/out; [ "$BE" = 53 ] && B=$R/5.3/out
  $B/uopt -G 0 -mips2 -EB -g0 $OPT t.B t.O -t t.S t.os
  $B/ugen -G 0 -mips2 -EB -g0 $OPT t.O -o t.G -t t.S -temp t.gt
  $B/as1 -elf -G 0 -p0 -mips2 -EB -g0 $OPT t.G -o out.o -t t.S
fi
cd - >/dev/null; cp $T/out.o "$OUT"
