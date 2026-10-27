#!/usr/bin/env bash
# Gate an agent branch in the landing worktree (projects/1080-agent-d). Does not push.
# usage: scripts/land-agent.sh <letter> [<seg>/<unit> | <path/to/donor.o> ...]
# Purges the given units/objects (plus all ncc donors), cherry-picks origin/main..agent-<letter>,
# and runs the full gate. Single entry point so the coordinator never chains shell commands.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
L="$1"; shift
export PATH="$ROOT/.venv/bin:$PATH"
export LAND_SCRATCH="${LAND_SCRATCH:-/tmp/claude-1000/land-scratch}"
mkdir -p "$LAND_SCRATCH"
cd "$ROOT" || exit 1
bash scripts/purge-landing-objs.sh projects/1080-agent-d "$@" | tail -1
git -C projects/1080-agent-d fetch -q
echo "origin/main: $(git -C projects/1080-agent-d log --oneline -1 origin/main | cut -c1-100)"
H=$(git -C "projects/1080-agent-$L" log --reverse --format=%h origin/main.."agent-$L" | tr '\n' ' ')
# SKIP="<hash> <hash>" env var: leave those commits out of the pick (e.g. a step the policy rejects)
for s in ${SKIP:-}; do H=$(echo " $H " | sed "s/ ${s:0:9}[0-9a-f]* / /"); echo "skipping $s"; done
[ -z "$H" ] && { echo "agent-$L has no commits ahead of origin/main"; exit 0; }
echo "picking: $H"
bash scripts/land-agent-wave.sh $H 2>&1 | grep -v '^      [-+]' | grep -v '^== picked' | tail -13
