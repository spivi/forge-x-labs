#!/usr/bin/env bash
# council-on-doc-write.sh — PostToolUse (Write|Edit|MultiEdit) hook.
#
# Auto-convenes the document-review council when a PLAN, EVR, or milestone SUMMARY
# is written. Reads the hook JSON on stdin, checks the written path against a document
# glob, and (if COUNCIL_REVIEW=on) fires scripts/council-review.sh in the background.
#
# It is deliberately FAIL-SOFT and NON-BLOCKING: it always exits 0 and never emits a
# block decision — a review must never prevent the author from writing a document. The
# council itself runs detached so the hook returns immediately (external members can
# take many seconds). Cost policy lives in council-review.sh (Sonnet chair; Opus gated).
set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
CONF="${ROOT}/.dev-context/project.conf"

# Gate: off unless COUNCIL_REVIEW=on in project.conf.
if [[ -f "$CONF" ]] && grep -qE '^COUNCIL_REVIEW=on([[:space:]]|$)' "$CONF"; then :; else
  exit 0
fi

# Read the payload and extract the written file path.
input="$(cat 2>/dev/null || true)"
have_jq() { command -v jq >/dev/null 2>&1; }
fp=""
if have_jq; then
  fp="$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null || true)"
fi
[[ -z "$fp" ]] && exit 0            # no path (e.g. non-file tool) -> nothing to do
[[ -f "$fp" ]] || exit 0

# Match the document globs: plans, EVRs, summaries, reports. Everything else is ignored.
base="$(basename "$fp")"
doc_type=""
case "$fp" in
  */docs/plans/*-design.md)  doc_type="plan" ;;
esac
case "$base" in
  *_evr.md)      doc_type="evr" ;;
  *_summary.md)  doc_type="summary" ;;
  *_report.md)   doc_type="summary" ;;
esac
[[ -z "$doc_type" ]] && exit 0      # not a reviewed document type

# Fire the council detached so the hook returns instantly. Output path / project context
# are left to the wrapper's defaults here (the AI-Video wiring passes --output + context).
COUNCIL="${ROOT}/scripts/council-review.sh"
[[ -x "$COUNCIL" || -f "$COUNCIL" ]] || exit 0
log_dir="${ROOT}/.dev-context/kpis"; mkdir -p "$log_dir" 2>/dev/null
nohup bash "$COUNCIL" "$fp" --doc-type "$doc_type" --ticket "auto:${base%.md}" \
  </dev/null >>"${log_dir}/council-hook.log" 2>&1 &

exit 0
