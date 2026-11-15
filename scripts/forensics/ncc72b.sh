#!/bin/bash
# usage: dcc744.sh in.cpp out.o [OPT=-O2] [BE=744|71|60]  -- MIPSpro 7.4.4 Delta C++ (edg 2.29) o32 front end + IDO-family backend
set -e
IN=$1; OUT=$2; OPT=${3:--O2}; BE=${4:-744}
FX=/home/danjs/code/decomp/tools/forensics; F=$FX/x_mipspro744; FE=${FEBIN:-$FX/x_mipspro72cxx/usr/lib/DCC/edgcpfe}
R=/home/danjs/code/decomp/projects/1080-agent-c/tools/ido-static-recomp/build
T=$(mktemp -d /tmp/claude-1000/r1/tmp/n.XXXXXX); cp "$IN" $T/in.cpp; cd $T
$F/usr/bin/qemu-irix -silent -L $F $FE -D_MIPS_FPSET=16 -D_MIPS_ISA=2 -D_ABIO32=1 -D_MIPS_SIM=_ABIO32 -D_MIPS_SZINT=32 -D_MIPS_SZLONG=32 -D_MIPS_SZPTR=32 -YE -D_LANGUAGE_C_PLUS_PLUS=1 -D__cplusplus=1 -D__ANSI_CPP__=1 -Dsgi -D__sgi -Dmips -D__mips=2 -D_MIPSEB -DMIPSEB -D__STDC__=1 $DCCFLAGS -O -b -Zz -ZO -ZS$T/t.S -Qn -u -YNout.o -YO./x.ii -YG0 -Zg0 in.cpp > t.B 2> fe.err || { cat fe.err >&2; exit 1; }
run() { local t=$1; shift; case $BE in
  744) $F/usr/bin/qemu-irix -silent -L $F $F/usr/lib/$t "$@";;
  721) $F/usr/bin/qemu-irix -silent -L /tmp/claude-1000/r1/root72 /tmp/claude-1000/r1/root72/usr/lib/$t "$@";;
  60) $FX/x_ido6.0/usr/bin/qemu-irix -silent -L $FX/x_ido6.0 $FX/x_ido6.0/usr/lib/$t "$@";;
  *) $R/7.1/out/$t "$@";; esac; }
if [ "$OPT" = "-O0" ] || [ "$OPT" = "-O1" ]; then cp t.B t.O; else run uopt -G 0 $UOPTX -mips2 -EB -g0 $OPT t.B t.O -t t.S t.os >/dev/null; fi
run ugen -G 0 -mips2 -EB -g0 ${OPT%% *} t.O -o t.G -t t.S -temp t.gt >/dev/null
AS1X=""; [ "$BE" = 71 ] && AS1X="-t5_ll_sc_bug -r4300_mul"
run as1 $AS1X -elf -G 0 -p0 -mips2 -EB -g0 ${OPT%% *} t.G -o out.o -t t.S >/dev/null
cd - >/dev/null; cp $T/out.o "$OUT"
