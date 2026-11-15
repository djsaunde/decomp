#!/bin/bash
# be.sh XDIR TAG -- XDIR uopt+ugen+as1 on mgrproc m.B (7.1 cfe ucode), compare
F=/home/danjs/code/decomp/tools/forensics; R=/tmp/claude-1000/h393/r721; Q=$F/x_mipspro744/usr/bin/qemu-irix
mkdir -p /tmp/claude-1000/h393/be_$2; cd /tmp/claude-1000/h393/be_$2
cp /tmp/claude-1000/h389/3/m.B m.B; cp /tmp/claude-1000/h389/3/m.T m.T
timeout 100 $Q -L $R $1/usr/lib/uopt -G 0 -mips2 -EB -g0 -O2 m.B m.O -t m.T m.S 2>&1 | head -3
timeout 100 $Q -L $R $1/usr/lib/ugen -G 0 -mips2 -EB -g0 -O2 m.O -o m.G -t m.T -temp m.tmp 2>&1 | head -3
timeout 100 $Q -L $R $1/usr/lib/as1 -t5_ll_sc_bug -elf -G 0 -p0 -r4300_mul -mips2 -EB -g0 -O2 m.G -o m.o -t m.T 2>&1 | grep -v unknown | head -3
python3 -I /tmp/claude-1000/h389/t/cmpobj.py m.o /tmp/claude-1000/h389/3/m.o | tail -10
mips-linux-gnu-objdump -d --no-show-raw-insn m.o | grep -A16 "<mgrproc_uso_func_00001824>:" | tail -5 | tr "\n" " "; echo
mips-linux-gnu-objdump -d --no-show-raw-insn m.o | grep -A7 "<mgrproc_uso_func_00003240>:" | tail -4 | tr "\n" " "; echo
