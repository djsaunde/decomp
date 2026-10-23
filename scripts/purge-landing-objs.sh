#!/usr/bin/env bash
# Delete stale build objects before a landing gate. usage: scripts/purge-landing-objs.sh <worktree> [<seg>/<unit> ...]
# Always removes every *_ncc_*.cpp.o (both trees) plus build/{,non_matching/}src/<seg>/<unit>.c.o for each unit given.
set -uo pipefail
WT="$1"; shift
cd "$WT" || exit 1
for u in "$@"; do rm -f "build/src/$u.c.o" "build/non_matching/src/$u.c.o"; done
find build/src build/non_matching/src -name '*_ncc_*.cpp.o' -type f -delete 2>/dev/null
echo "purged ${#} unit(s) + ncc donors in $WT"
