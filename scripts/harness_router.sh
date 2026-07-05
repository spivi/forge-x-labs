#!/usr/bin/env bash
# harness_router.sh — route long harness output through the Gemini CLI, then Claude.
#
# A token-saving filter: condense long CI/diff output (or run a cheap review
# pre-pass) on Gemini BEFORE it enters Claude's context. Fully fail-soft — if
# Gemini is absent or returns non-JSON, exit 2 and the caller uses the raw input
# unchanged. Ships disabled (HARNESS_ROUTER=off); opt-in, needs a `gemini` CLI.
#
# Usage:
#   harness_router.sh summarize-ci    < ci_output.txt
#   harness_router.sh summarize-diff  < diff.txt
#   harness_router.sh review-prepass  < diff.txt
#
# Exit codes:
#   0  result on stdout (JSON)
#   2  all providers failed (or a security-surface diff); caller uses raw input
#
# Environment:
#   TICKET                  current ticket id for the ledger row
#   HARNESS_ROUTER_LEDGER   override ledger path (default: .dev-context/kpis/cli-routing.csv)
#   HARNESS_ROUTER_TIMEOUT  gemini call timeout in seconds (default: 30)
#   GEMINI_MODEL            gemini model to use (default: gemini-2.5-flash)
#   SECURITY_SURFACE_GLOB   ERE of diff paths that always go to Claude (never Gemini).
#                           Falls back to SECURITY_SURFACE_GLOB in project.conf, then a
#                           portable default (auth|secret|crypto|token|password|DECISIONS|security).
#
# Scope boundary: harness meta-ops only — summarizing CI/diff output and a review
# pre-pass. This is NOT an application LLM-routing seam; do not route app logic here.

set -euo pipefail

OPERATION="${1:-}"
SCRIPT_DIR="${BASH_SOURCE[0]%/*}"
[[ "$SCRIPT_DIR" == "${BASH_SOURCE[0]}" ]] && SCRIPT_DIR="."
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LEDGER="${HARNESS_ROUTER_LEDGER:-$REPO_ROOT/.dev-context/kpis/cli-routing.csv}"
TIMEOUT="${HARNESS_ROUTER_TIMEOUT:-30}"
MODEL="${GEMINI_MODEL:-gemini-2.5-flash}"
TICKET="${TICKET:-}"
CONF="$REPO_ROOT/.dev-context/project.conf"

# Resolve the security-surface glob: env override → project.conf → portable default.
_conf_value() {
    # Read KEY=value from project.conf, stripping quotes/comments. Empty if absent.
    [[ -f "$CONF" ]] || return 0
    sed -n "s/^$1=//p" "$CONF" 2>/dev/null | head -n1 | sed 's/[[:space:]]*#.*$//; s/^"//; s/"$//'
}
SECURITY_SURFACE_GLOB="${SECURITY_SURFACE_GLOB:-$(_conf_value SECURITY_SURFACE_GLOB)}"
SECURITY_SURFACE_GLOB="${SECURITY_SURFACE_GLOB:-auth|secret|crypto|token|password|\.dev-context/DECISIONS\.md|security\.md}"

_usage() {
    echo "usage: harness_router.sh <summarize-ci|summarize-diff|review-prepass>" >&2
    exit 1
}

# --- security surface guard (review-prepass only) ---
# Diffs that touch these paths always go to Claude, regardless of Gemini verdict.
_security_surface() {
    local input="$1"
    # Match path substrings anywhere in the line (unified diff headers use a/ b/ prefixes).
    echo "$input" | grep -qE "$SECURITY_SURFACE_GLOB" && return 0 || return 1
}

# --- prompt definitions ---
_prompt_summarize_ci() {
    cat <<'EOF'
Summarize these CI results. Return ONLY valid JSON, no other text, matching exactly:
{"status":"pass|fail","failed_tests":[],"lint_errors":[],"type_errors":[],"summary_line":"<one line>"}
EOF
}

_prompt_summarize_diff() {
    cat <<'EOF'
Summarize this git diff. Return ONLY valid JSON, no other text, matching exactly:
{"files_changed":0,"summary_bullets":["<change>"],"risk_level":"low|medium|high","summary_line":"<one line>"}
EOF
}

_prompt_review_prepass() {
    cat <<'EOF'
Review this code diff for bugs and correctness issues. Return ONLY valid JSON, no other text, matching exactly:
{"verdict":"PASS|FAIL","findings":[{"severity":"P1|P2|P3","file":"<path>","line":0,"message":"<issue>"}]}
verdict is PASS when findings is empty. P1=critical/high, P2=medium, P3=low.
Focus on correctness, not style.
EOF
}

# --- millisecond timestamp (portable: BSD date on macOS lacks %N) ---
_ms_now() { python3 -c "import time; print(int(time.time() * 1000))"; }

# --- run a command with a timeout if `timeout` is available, else plain (portable) ---
# GNU coreutils `timeout` is absent on a stock macOS; degrade to a plain call so the
# Gemini path still works (the gemini CLI has its own network timeouts).
if command -v timeout >/dev/null 2>&1; then
    _with_timeout() { timeout "$TIMEOUT" "$@"; }
elif command -v gtimeout >/dev/null 2>&1; then
    _with_timeout() { gtimeout "$TIMEOUT" "$@"; }
else
    _with_timeout() { "$@"; }
fi

# --- strip markdown fences from gemini output ---
_strip_fences() {
    sed -E 's/^```(json)?[[:space:]]*//; s/^```[[:space:]]*$//'
}

# --- validate JSON (reads from stdin) ---
_is_json() {
    python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null
}

# --- ledger append (fail-soft: never blocks harness) ---
_ledger_append() {
    local op="$1" provider="$2" in_chars="$3" out_chars="$4" ms="$5" fallback="$6" skipped="$7"
    local ts
    ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    local in_tok=$(( in_chars / 4 ))
    local out_tok=$(( out_chars / 4 ))
    mkdir -p "$(dirname "$LEDGER")" 2>/dev/null || true
    if [[ ! -f "$LEDGER" ]]; then
        printf 'ts_iso,ticket,operation,provider,input_chars,est_input_tokens,output_chars,est_output_tokens,wall_clock_ms,fallback,claude_skipped\n' \
            >> "$LEDGER" 2>/dev/null || true
    fi
    printf '%s,%s,%s,%s,%d,%d,%d,%d,%d,%d,%d\n' \
        "$ts" "$TICKET" "$op" "$provider" \
        "$in_chars" "$in_tok" "$out_chars" "$out_tok" \
        "$ms" "$fallback" "$skipped" \
        >> "$LEDGER" 2>/dev/null || true
}

# --- main ---
[[ -z "$OPERATION" ]] && _usage

INPUT="$(cat)"
IN_CHARS="${#INPUT}"

case "$OPERATION" in
    summarize-ci)    PROMPT="$(_prompt_summarize_ci)" ;;
    summarize-diff)  PROMPT="$(_prompt_summarize_diff)" ;;
    review-prepass)
        if _security_surface "$INPUT"; then
            # Security surface: force Claude; log as security-guard (Gemini never called)
            _ledger_append "$OPERATION" "security-guard" "$IN_CHARS" 0 0 1 0
            exit 2
        fi
        PROMPT="$(_prompt_review_prepass)"
        ;;
    *) _usage ;;
esac

# --- try Gemini ---
if command -v gemini &>/dev/null; then
    TS_START="$(_ms_now)"
    # No --yolo: avoid auto-approving Gemini tool calls when piping arbitrary diff content.
    # Without --yolo, Gemini runs in prompt-only mode; timeout kills any interactive prompt.
    RESULT="$(echo "$INPUT" | _with_timeout gemini -p "$PROMPT" -m "$MODEL" 2>/dev/null | _strip_fences)" || true
    TS_END="$(_ms_now)"
    ELAPSED=$(( TS_END - TS_START ))
    OUT_CHARS="${#RESULT}"

    if [[ -n "$RESULT" ]] && echo "$RESULT" | _is_json; then
        _ledger_append "$OPERATION" "gemini" "$IN_CHARS" "$OUT_CHARS" "$ELAPSED" 0 1
        echo "$RESULT"
        exit 0
    fi
    # Gemini returned non-JSON or failed; log fallback
    _ledger_append "$OPERATION" "gemini" "$IN_CHARS" 0 "$ELAPSED" 1 0
fi

# All providers exhausted — signal caller to use raw input
exit 2
