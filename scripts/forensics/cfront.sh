#!/bin/bash
# usage: cfront.sh in.cpp out.o [OPT] [53|71] -- IDO 5.3 cfront 3.0.1 + IDO cc on its C output
set -e
IN=$1; OUT=$2; OPT=${3:--O2}; BE=${4:-53}
F=/home/danjs/code/decomp/tools/forensics/ido5.3_cfront
R=/home/danjs/code/decomp/projects/1080-agent-c/tools/ido-static-recomp/build
T=$(mktemp -d /tmp/claude-1000/c349/cftmp.XXXXXX)
cp "$IN" $T/in.cpp; cd $T
$R/7.1/out/acpp -D__cplusplus=1 -Dc_plusplus=1 -D_LANGUAGE_C_PLUS_PLUS -D__EDG__=0 in.cpp > in.ii 2>/dev/null || cpp -P -D__cplusplus=1 in.cpp > in.ii
$F/usr/bin/qemu-irix -silent -L $F $F/usr/lib/c++/cfront +a1 +fin.cpp $CFFLAGS < in.ii > in_cf.c
B=$R/5.3/out; [ "$BE" = 71 ] && B=$R/7.1/out
$B/cc -c -G 0 -non_shared -mips2 -32 -Xfullwarn -w $OPT -o out.o in_cf.c
cd - >/dev/null; cp $T/out.o "$OUT"; cp $T/in_cf.c "$OUT.c"
