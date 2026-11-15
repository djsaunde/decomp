#!/bin/bash
# one.sh rel opt outdir  -> compile donor with $FEBIN (+7.1 BE) and compare .text with agent-d build object
R=/home/danjs/code/decomp/projects/1080-agent-d
rel=$1; opt=$2; O=$3; b=$(basename $rel .cpp)
export DCCFLAGS="-I$R/$(dirname $rel) -I$R/include -I$R/src"
if timeout 100 /tmp/claude-1000/r1/scripts/ncc72.sh $R/$rel $O/$b.o $opt 71 2>$O/$b.err >/dev/null; then
  echo "$rel $opt $(python3 -I /tmp/claude-1000/r1/scripts/textcmp.py $O/$b.o $R/build/$rel.o)"
else echo "$rel $opt FEFAIL $(head -c 150 $O/$b.err | tr '\n' ' ')"; fi
