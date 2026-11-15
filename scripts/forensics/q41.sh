#!/bin/bash
# run an IDO 4.1 (ECOFF) binary under decomp.me's qemu-irix-4.0 using the Ubuntu 24.04 snapshot glibc + glib shim
S=/home/danjs/.local/share/docker/containerd/daemon/io.containerd.snapshotter.v1.overlayfs/snapshots/2/fs
F=/home/danjs/code/decomp/tools/forensics/ido4.1
exec $S/lib64/ld-linux-x86-64.so.2 --library-path $S/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu --preload /home/danjs/code/decomp/tools/forensics/scripts/libshim.so $F/usr/bin/qemu-irix-4.0 -silent -L $F "$@"
