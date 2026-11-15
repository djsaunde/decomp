#!/bin/bash
# as1run.sh AS1 OUT.o  -- run an IRIX as1 on the mgrproc m.G/m.T with the build flags, report 1824/3240/whole object
F=/home/danjs/code/decomp/tools/forensics; R=/tmp/claude-1000/h393/r721; D=/tmp/claude-1000/h393/2
cd $D
timeout 100 $F/x_mipspro744/usr/bin/qemu-irix -L $R $1 -t5_ll_sc_bug -elf -G 0 -p0 -r4300_mul -mips2 -EB -g0 -O2 m.G -o $2 -t m.T ${@:3}
echo rc=$?
python3 -I /tmp/claude-1000/h389/t/cmpobj.py $2 /tmp/claude-1000/h389/3/m.o | tail -8
mips-linux-gnu-objdump -d --no-show-raw-insn $2 | grep -A16 "<mgrproc_uso_func_00001824>:" | tail -5 | tr "\n" " "; echo
mips-linux-gnu-objdump -d --no-show-raw-insn $2 | grep -A7 "<mgrproc_uso_func_00003240>:" | tail -4 | tr "\n" " "; echo
