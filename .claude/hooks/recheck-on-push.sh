#!/usr/bin/env bash
# recheck-on-push.sh — review-staleness guard (PostToolUse Bash hook).
#
# When a `git push` or `git commit` changes a PR's head SHA, invalidate any stale
# in-session review by flipping the `ai-code-review` commit status to `pending` for
# the NEW SHA and dropping a marker the merge step reads. This makes "review is
# stale" a property of the SHA — a push can never slip an unreviewed diff past the
# merge gate, which refuses to merge a pending/absent-review SHA.
#
# Gated by REVIEW_RECHECK in .dev-context/project.conf (default on). Inert without
# the AI review gate (DT-10): harmless no-op without an open PR / gh auth.
#
# Invariants:
#   * Fail-soft: ALWAYS exit 0. A review-gate hiccup must never block a tool call.
#   * Cheap: bail immediately unless the command is a git push/commit.
#   * Idempotent: a SHA that already carries `ai-code-review=success` is a no-op.
set -uo pipefail

CONTEXT="ai-code-review"

# Resolve repo root + project.conf (template IS the repo root — no monorepo workaround).
ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
CONF="$ROOT/.dev-context/project.conf"

_conf_value() {
    [ -f "$CONF" ] || return 0
    sed -n "s/^$1=//p" "$CONF" 2>/dev/null | head -n1 | sed 's/[[:space:]]*#.*$//; s/^"//; s/"$//'
}

# Respect the gate (treat unset as on).
[ "$(_conf_value REVIEW_RECHECK)" = "off" ] && exit 0

OWNER="${GITHUB_OWNER:-$(_conf_value GITHUB_OWNER)}"
REPO="${GITHUB_REPO:-$(_conf_value GITHUB_REPO)}"
[ -z "$OWNER" ] || [ -z "$REPO" ] && exit 0  # owner/repo unset → nothing to gate

# 1. Read the PostToolUse payload and extract the bash command (fail-soft).
payload="$(cat 2>/dev/null || true)"
cmd="$(printf '%s' "$payload" \
  | python3 -c 'import json,sys
try:
    d=json.load(sys.stdin)
    print(((d.get("tool_input") or {}).get("command")) or "")
except Exception:
    print("")' 2>/dev/null || true)"

# 2. Only react to a real git push/commit. Anything else: silent no-op.
case "$cmd" in
  *"git push"*|*"git commit"*) : ;;
  *) exit 0 ;;
esac

command -v gh >/dev/null 2>&1 || exit 0

# 3. Resolve the current branch's open PR + head SHA (no PR → nothing to gate).
branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
[ -z "$branch" ] || [ "$branch" = "HEAD" ] && exit 0

pr="$(gh pr list --repo "$OWNER/$REPO" --head "$branch" --state open \
        --json number --jq '.[0].number' 2>/dev/null || true)"
[ -z "$pr" ] && exit 0

head_sha="$(gh pr view "$pr" --repo "$OWNER/$REPO" --json headRefOid \
              --jq '.headRefOid' 2>/dev/null || true)"
[ -z "$head_sha" ] && exit 0

# 4. Idempotent: if this exact SHA already passed review, do nothing.
state="$(gh api "repos/$OWNER/$REPO/commits/$head_sha/status" \
          --jq '.statuses[] | select(.context=="'"$CONTEXT"'") | .state' 2>/dev/null \
          | head -n1 || true)"
[ "$state" = "success" ] && exit 0

# 5. Invalidate: mark the new SHA pending + drop a marker for /sprint merge.
gh api -X POST "repos/$OWNER/$REPO/statuses/$head_sha" \
  -f state=pending \
  -f context="$CONTEXT" \
  -f description="diff changed — re-run the in-session review gate" >/dev/null 2>&1 || true

marker_dir="$ROOT/.dev-context"
if [ -d "$marker_dir" ]; then
  printf 'pr=%s\nbranch=%s\nhead_sha=%s\n' "$pr" "$branch" "$head_sha" \
    > "$marker_dir/.review-pending" 2>/dev/null || true
fi

exit 0
