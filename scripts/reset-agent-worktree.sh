#!/usr/bin/env bash
# Reset a 1080 agent worktree to origin/main after its work has landed. usage: scripts/reset-agent-worktree.sh <letter>
set -uo pipefail
L="$1"; WT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/projects/1080-agent-$L"
cd "$WT" || exit 1
git fetch -q origin
git checkout -q -- report.json 2>/dev/null
git checkout -q -B "agent-$L" origin/main
git reset -q --hard origin/main
rm -f build/tenshoe.elf
echo "agent-$L reset to $(git log --oneline -1)"
