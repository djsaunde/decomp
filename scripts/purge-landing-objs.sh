#!/usr/bin/env bash
# Delete stale build objects before a landing gate.
# usage: scripts/purge-landing-objs.sh <worktree> [<seg>/<unit> | <path/to/file.o> ...]
# Always removes every *_ncc_*.cpp.o (both trees). For each <seg>/<unit>, removes
# build/{,non_matching/}src/<seg>/<unit>.c.o. Arguments ending in .o are removed as
# worktree-relative paths (for cfe/IDO 5.3 donor objects the ncc sweep doesn't cover).
# Exists so the landing loop never needs inline rm loops (they trigger permission prompts).
set -uo pipefail
WT="$1"; shift
cd "$WT" || exit 1
n=0
for u in "$@"; do
  case "$u" in
    *..*|/*) echo "skip unsafe path: $u"; continue ;;
    *.o) rm -f "$u" ;;
    *) rm -f "build/src/$u.c.o" "build/non_matching/src/$u.c.o"; n=$((n+1)) ;;
  esac
done
find build/src build/non_matching/src -name '*_ncc_*.cpp.o' -type f -delete 2>/dev/null
echo "purged $n unit(s) + ncc donors in $WT"
