#!/bin/bash
# usage: dcc.sh in.cpp out.o [OPT=-O2] [BACKEND=53|71]  -- IDO 5.3 Delta C++ (edg 2.19) front end + IDO backend
set -e
IN=$1; OUT=$2; OPT=${3:--O2}; BE=${4:-53}
F=/home/danjs/code/decomp/tools/forensics/ido5.3_cfront
R=/home/danjs/code/decomp/projects/1080-agent-c/tools/ido-static-recomp/build
T=$(mktemp -d /tmp/claude-1000/c349/dcctmp.XXXXXX)
cp "$IN" $T/in.cpp
cd $T
PATH="$F/usr/bin:/usr/bin:/bin" $F/usr/bin/qemu-irix -silent -L $F $F/usr/lib/DCC/edgcpfe -D_MIPS_FPSET=16 -D_MIPS_ISA=2 -D_ABIO32=1 -D_MIPS_SIM=_ABIO32 -D_MIPS_SZINT=32 -D_MIPS_SZLONG=32 -D_MIPS_SZPTR=32 -YE -D_LANGUAGE_C_PLUS_PLUS=1 -D__cplusplus=1 -D__ANSI_CPP__=1 -D_DELTA_EXTENSIONS=1 -Dsgi -D__sgi -Dmips -D__mips=2 -D_MIPSEB -DMIPSEB -D__STDC__=1 $DCCFLAGS -O -b -Zz -ZO -ZS$T/t.S -Qn -u -YD -YNout.o -YO./x.ii -YG0 -Zg0 in.cpp > t.B
B=$R/5.3/out; [ "$BE" = 71 ] && B=$R/7.1/out
if [ "$OPT" = "-O0" ] || [ "$OPT" = "-O1" ]; then cp t.B t.O; else $B/uopt -G 0 -mips2 -EB -g0 $OPT t.B t.O -t t.S t.os; fi
$B/ugen -G 0 -mips2 -EB -g0 ${OPT%% *} t.O -o t.G -t t.S -temp t.gt
$B/as1 -elf -G 0 -p0 -mips2 -EB -g0 ${OPT%% *} t.G -o out.o -t t.S
cd - >/dev/null
cp $T/out.o "$OUT"
