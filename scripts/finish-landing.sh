#!/usr/bin/env bash
# After a passing scripts/land-agent.sh gate: commit report.json in agent-d, push HEAD:main,
# reset the agent worktree, and commit any docs/ changes in the monorepo.
# usage: scripts/finish-landing.sh <letter> "<report.json commit subject>" ["<docs commit subject>"]
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
L="$1"; MSG="$2"; DOCMSG="${3:-}"
TRAILER=$'\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01DbfSRBWaw6Jqe5SgVrtjU5'
D="$ROOT/projects/1080-agent-d"
git -C "$D" fetch -q
if [ "$(git -C "$D" rev-parse origin/main)" != "$(git -C "$D" merge-base HEAD origin/main)" ]; then
  echo "!! origin/main moved since the gate; re-run land-agent.sh"; exit 1
fi
if [ -e "$(git -C "$D" rev-parse --git-path CHERRY_PICK_HEAD)" ]; then
  echo "!! cherry-pick in progress in agent-d (land-agent.sh did not finish); not resetting agent-$L"; exit 1
fi
A="$ROOT/projects/1080-agent-$L"
AH="$(git -C "$A" rev-parse HEAD)"
# every agent commit must have an equivalent patch on agent-d HEAD (git cherry marks those '-')
MISSING="$(git -C "$D" cherry HEAD "$AH" | grep '^+' || true)"
if [ -n "$MISSING" ] && [ "${LANDED_BY_HAND:-0}" != 1 ]; then   # LANDED_BY_HAND=1: coordinator resolved a conflicted pick (patch-ids differ)
  echo "!! agent-$L commits not on agent-d HEAD (landing incomplete?); not resetting:"; echo "$MISSING"; exit 1
fi
git -C "$D" add report.json
if git -C "$D" diff --cached --quiet; then
  echo "report.json unchanged: pushing the landed commits without a report commit"
else
  git -C "$D" commit -q -m "$MSG$TRAILER" || { echo "!! commit failed"; exit 1; }
fi
git -C "$D" push -q origin HEAD:main || { echo "!! push failed"; exit 1; }
echo "pushed: $(git -C "$D" log --oneline -1 | cut -c1-120)"
cd "$ROOT" && bash scripts/reset-agent-worktree.sh "$L" 2>&1 | tail -1
if [ -n "$DOCMSG" ] && [ -n "$(git -C "$ROOT" status --porcelain docs)" ]; then
  echo "docs: $(git -C "$ROOT" diff --shortstat docs)"
  git -C "$ROOT" add docs && git -C "$ROOT" commit -q -m "$DOCMSG$TRAILER" && echo "docs committed: $(git -C "$ROOT" log --oneline -1)"
fi
