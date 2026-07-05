#!/usr/bin/env bash
# council-review.sh — convene a document-review council over one produced document
# (a plan, an EVR, or a milestone summary) and write a synthesized report.
#
# Engine: the vendored hex/claude-council plugin (.dev-context/vendor/claude-council).
# Members: codex + gemini (each seeded with a doc-review role). Chair: Claude, which
# synthesizes through the Architectural Methodologist persona (prompts/synthesis.md).
#
# This wrapper is the SINGLE place the model/cost policy lives:
#   - codex/gemini members fire freely (subscription / GEMINI_API_KEY).
#   - the chair runs on Sonnet (COUNCIL_CHAIR_MODEL); an opus chair model is REFUSED
#     unless --allow-opus is passed (a human opt-in). Never silently escalate.
# It is fail-soft: a missing member is skipped, never fatal; the Write that triggered
# it (via the hook) is never blocked.
#
# Usage:
#   council-review.sh <document-path> [--doc-type plan|evr|summary]
#                     [--output <report-path>] [--context-file <extra-prompt-file>]
#                     [--allow-opus] [--ticket <id>]
set -uo pipefail   # NOTE: no -e — we handle failures explicitly and stay fail-soft.

# --- locate dev-context + load config -------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEVCTX_DIR="$(cd "${SCRIPT_DIR}/../.dev-context" 2>/dev/null && pwd)"
if [[ -z "${DEVCTX_DIR}" || ! -f "${DEVCTX_DIR}/council.env" ]]; then
  # Allow callers in other projects to point us at a council.env explicitly.
  if [[ -n "${COUNCIL_ENV:-}" && -f "${COUNCIL_ENV}" ]]; then
    # shellcheck disable=SC1090
    source "${COUNCIL_ENV}"
    DEVCTX_DIR="$(cd "$(dirname "${COUNCIL_ENV}")" && pwd)"
  else
    echo "council-review: cannot find council.env (set COUNCIL_ENV)" >&2
    exit 0   # fail-soft: no config => no-op, do not block anything
  fi
else
  # shellcheck disable=SC1090
  source "${DEVCTX_DIR}/council.env"
fi

# --- KPI ledger (one row per run; fail-soft) ------------------------------------------
# Defined early so the Opus-block / no-member early-exits can record a row.
AUTOFIX_STATUS="off"   # overwritten if the autofix step runs; default for early exits
_ledger_append() {   # args: status members_count
  local status="${1:-unknown}" members="${2:-0}"
  local ledger="${COUNCIL_LEDGER:-.dev-context/kpis/council.csv}"
  # Resolve a relative ledger path against DEVCTX_DIR's parent (the project root).
  case "$ledger" in
    /*) : ;;
    *)  ledger="$(cd "${DEVCTX_DIR}/.." 2>/dev/null && pwd)/${ledger}" ;;
  esac
  local ts; ts="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)"
  mkdir -p "$(dirname "$ledger")" 2>/dev/null
  if [[ ! -f "$ledger" ]]; then
    echo "ts_iso,ticket,document,doc_type,providers,members_run,chair_model,status,autofix" > "$ledger" 2>/dev/null
  fi
  printf '%s,%s,%s,%s,"%s",%s,%s,%s,%s\n' \
    "$ts" "${TICKET:-}" "${DOC:-}" "${DOC_TYPE:-}" "${COUNCIL_PROVIDERS:-}" \
    "$members" "${COUNCIL_CHAIR_MODEL:-}" "$status" "${AUTOFIX_STATUS:-off}" >> "$ledger" 2>/dev/null || true
}

# --- parse args -----------------------------------------------------------------------
DOC=""; DOC_TYPE=""; OUTPUT=""; CONTEXT_FILE=""; ALLOW_OPUS=0; TICKET=""
AUTOFIX="${COUNCIL_AUTOFIX:-off}"   # env is the default; --autofix/--no-autofix override
while [[ $# -gt 0 ]]; do
  case "$1" in
    --doc-type)     DOC_TYPE="$2"; shift 2 ;;
    --doc-type=*)   DOC_TYPE="${1#*=}"; shift ;;
    --output)       OUTPUT="$2"; shift 2 ;;
    --output=*)     OUTPUT="${1#*=}"; shift ;;
    --context-file) CONTEXT_FILE="$2"; shift 2 ;;
    --context-file=*) CONTEXT_FILE="${1#*=}"; shift ;;
    --ticket)       TICKET="$2"; shift 2 ;;
    --ticket=*)     TICKET="${1#*=}"; shift ;;
    --allow-opus)   ALLOW_OPUS=1; shift ;;
    --autofix)      AUTOFIX="on"; shift ;;
    --no-autofix)   AUTOFIX="off"; shift ;;
    -h|--help)      grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)              [[ -z "$DOC" ]] && DOC="$1" || true; shift ;;
  esac
done

if [[ -z "$DOC" || ! -f "$DOC" ]]; then
  echo "council-review: document not found: '${DOC}'" >&2
  exit 0   # fail-soft
fi
[[ -z "$DOC_TYPE" ]] && DOC_TYPE="document"

# --- cost brake: Opus chair requires explicit opt-in ----------------------------------
CHAIR_MODEL="${COUNCIL_CHAIR_MODEL:-claude-sonnet-4-6}"
case "$CHAIR_MODEL" in
  *opus*)
    if [[ "$ALLOW_OPUS" != "1" && "${COUNCIL_ALLOW_OPUS:-0}" != "1" ]]; then
      echo "council-review: STOP — chair model '${CHAIR_MODEL}' is an Opus tier." >&2
      echo "  Opus requires approval. Re-run with --allow-opus to proceed, or set" >&2
      echo "  COUNCIL_CHAIR_MODEL=claude-sonnet-4-6 for the automatic Sonnet chair." >&2
      _ledger_append "opus_blocked" 0
      exit 0   # fail-soft: refuse to spend, do not error the pipeline
    fi
    ;;
esac

# --- member availability guards (fail-soft: skip a missing member) --------------------
PROVIDERS_REQ="${COUNCIL_PROVIDERS:-codex,antigravity}"
AVAIL=()
IFS=',' read -ra _req <<< "$PROVIDERS_REQ"
for p in "${_req[@]}"; do
  case "$p" in
    codex)  command -v codex >/dev/null 2>&1 && AVAIL+=("codex") \
              || echo "council-review: codex CLI not on PATH — skipping that member" >&2 ;;
    antigravity)
            # The Antigravity provider shells out to the `agy` binary (keyless sub auth).
            command -v agy >/dev/null 2>&1 && AVAIL+=("antigravity") \
              || echo "council-review: antigravity unavailable (agy CLI not on PATH) — skipping" >&2 ;;
    gemini) { command -v gemini >/dev/null 2>&1 || [[ -n "${GEMINI_API_KEY:-}" ]]; } && AVAIL+=("gemini") \
              || echo "council-review: gemini unavailable (no CLI / no GEMINI_API_KEY) — skipping" >&2 ;;
    openai|grok|perplexity)
            # Other plugin-supported providers: gate on their CLI/key the plugin uses.
            command -v "$p" >/dev/null 2>&1 && AVAIL+=("$p") \
              || echo "council-review: ${p} not available — skipping that member" >&2 ;;
    *)      echo "council-review: unknown provider '${p}' — skipping (not in the plugin roster)" >&2 ;;
  esac
done
if [[ ${#AVAIL[@]} -eq 0 ]]; then
  echo "council-review: no council members available — nothing to do" >&2
  _ledger_append "no_members" 0
  exit 0
fi
PROVIDERS_CSV="$(IFS=,; echo "${AVAIL[*]}")"

# --- build the review prompt ----------------------------------------------------------
REVIEW_PROMPT="Independently review this ${DOC_TYPE}. You did not write it and have no prior context; judge it on its own merits through your assigned lens. Cite the section for each finding. Do not propose new scope."
if [[ -n "$CONTEXT_FILE" && -f "$CONTEXT_FILE" ]]; then
  REVIEW_PROMPT="$(cat "$CONTEXT_FILE")

${REVIEW_PROMPT}"
fi

# --- run the members (query -> format), producing a markdown body + empty ## Synthesis -
PLUGIN_ROOT="${COUNCIL_PLUGIN_ROOT}"
if [[ ! -x "${PLUGIN_ROOT}/scripts/run-council.sh" && ! -f "${PLUGIN_ROOT}/scripts/run-council.sh" ]]; then
  echo "council-review: plugin not found at ${PLUGIN_ROOT} — run the bootstrap (clone the pin)" >&2
  _ledger_append "no_plugin" 0
  exit 0
fi

WORKDIR="$(mktemp -d 2>/dev/null || echo /tmp/council.$$)"
mkdir -p "$WORKDIR"
DOC_ABS="$(cd "$(dirname "$DOC")" && pwd)/$(basename "$DOC")"
BODY_REL=""
# run-council.sh writes into ./.claude/council-cache and echoes a RELATIVE path; run it
# from WORKDIR and resolve the echoed path against WORKDIR so it's absolute.
BODY_REL="$(cd "$WORKDIR" && bash "${PLUGIN_ROOT}/scripts/run-council.sh" \
    --providers="${PROVIDERS_CSV}" --roles="${COUNCIL_ROLES:-doc-review}" \
    --file="$DOC_ABS" \
    --no-pane -- "$REVIEW_PROMPT" 2>>"${WORKDIR}/members.err")"
case "$BODY_REL" in
  /*) BODY_FILE="$BODY_REL" ;;
  "") BODY_FILE="" ;;
  *)  BODY_FILE="${WORKDIR}/${BODY_REL}" ;;
esac
if [[ -z "$BODY_FILE" || ! -f "$BODY_FILE" ]]; then
  echo "council-review: member query produced no output (see ${WORKDIR}/members.err)" >&2
  _ledger_append "members_failed" "${#AVAIL[@]}"
  exit 0   # fail-soft
fi

# --- chair step: Claude (Sonnet) writes the Methodologist synthesis under ## Synthesis --
SYNTH_PROMPT_FILE="${PLUGIN_ROOT}/prompts/synthesis.md"
CHAIR_INPUT="$(mktemp 2>/dev/null || echo "${WORKDIR}/chair.in")"
{
  echo "You are the chair of a review council. Below is (A) your synthesis instructions and"
  echo "(B) a report file containing each member's review, ending in an empty '## Synthesis'"
  echo "header. Write ONLY the synthesis text that belongs under that header — do not repeat"
  echo "the members' sections, do not add a new title. Output just the synthesis body."
  echo
  echo "===== (A) SYNTHESIS INSTRUCTIONS ====="
  cat "$SYNTH_PROMPT_FILE" 2>/dev/null
  echo
  echo "===== (B) MEMBER REPORT ====="
  cat "$BODY_FILE"
} > "$CHAIR_INPUT"

SYNTHESIS=""
if command -v claude >/dev/null 2>&1; then
  SYNTHESIS="$(claude -p --model "$CHAIR_MODEL" \
                 --disallowed-tools "Bash Edit Write Read WebFetch" \
                 < "$CHAIR_INPUT" 2>>"${WORKDIR}/chair.err")"
fi
if [[ -z "$SYNTHESIS" ]]; then
  # Fail-soft: keep the member report; leave a marker so a human can synthesize.
  SYNTHESIS="_Chair synthesis unavailable (claude CLI absent or errored). Members' reviews above stand; a human should synthesize._

> **Human architecture-review sign-off required — this council report does NOT approve the work and does NOT move any project-tracker item.**"
  echo "council-review: chair step failed; emitting member report without synthesis" >&2
fi

# --- assemble the final report and place it at --output (or print the path) ------------
FINAL="$(mktemp 2>/dev/null || echo "${WORKDIR}/final.md")"
SYNTH_FILE="$(mktemp 2>/dev/null || echo "${WORKDIR}/synth.md")"
printf '%s\n' "$SYNTHESIS" > "$SYNTH_FILE"
# Splice the chair synthesis in under the trailing empty "## Synthesis" header. File-based
# (awk reads the synthesis from a FILE, never a -v string) so multi-line content is safe.
if grep -q '^## Synthesis' "$BODY_FILE"; then
  awk -v sf="$SYNTH_FILE" '
    /^## Synthesis[[:space:]]*$/ {
      print; print "";
      while ((getline line < sf) > 0) print line;
      close(sf); next
    }
    { print }
  ' "$BODY_FILE" > "$FINAL"
else
  # No synthesis header in the body — append one.
  { cat "$BODY_FILE"; echo; echo "## Synthesis"; echo; cat "$SYNTH_FILE"; } > "$FINAL"
fi

# --- OPTIONAL: auto-DRAFT the chair's blocker fixes (never commits) -------------------
# Gated by COUNCIL_AUTOFIX / --autofix. Reads the machine-readable ```council-autofix```
# block the chair emitted (blockers ONLY — nice-to-haves and acceptance-criteria are
# excluded by the chair per prompts/synthesis.md), and for each blocker DRAFTS a minimal
# edit on a COPY of the target file, producing a unified diff. It STOPS before commit:
# a human reviews the diffs and applies them. Fail-soft — any failure leaves the report
# intact and never blocks. The drafting model is the Sonnet chair (Opus stays gated).
AUTOFIX_STATUS="skipped"
if [[ "$AUTOFIX" == "on" ]]; then
  # Extract the fenced council-autofix block from the synthesis (first one wins).
  AF_BLOCK="$(awk '
    /^```council-autofix[[:space:]]*$/ {grab=1; next}
    grab && /^```[[:space:]]*$/ {exit}
    grab {print}
  ' "$SYNTH_FILE")"

  # Collect valid JSONL action lines (each must parse as a JSON object with the keys we use).
  ACTIONS=()
  while IFS= read -r line; do
    [[ -z "${line// }" ]] && continue
    if command -v jq >/dev/null 2>&1; then
      printf '%s' "$line" | jq -e 'select(type=="object" and .instruction and .target)' >/dev/null 2>&1 \
        && ACTIONS+=("$line")
    else
      case "$line" in *'"instruction"'*'"target"'*|*'"target"'*'"instruction"'*) ACTIONS+=("$line") ;; esac
    fi
  done <<< "$AF_BLOCK"

  DRAFT_DIR="${WORKDIR}/autofix"; mkdir -p "$DRAFT_DIR"
  DRAFT_SUMMARY="${DRAFT_DIR}/_summary.md"
  DOC_DIR="$(cd "$(dirname "$DOC_ABS")" && pwd)"
  n_ok=0; n_fail=0
  {
    echo "## Auto-drafted fixes (PENDING HUMAN APPROVAL — not applied, not committed)"
    echo
    echo "The council flagged the following **blockers**. Each was drafted as a minimal edit on a"
    echo "COPY of the target file; review the diffs below and apply them yourself. Nice-to-have"
    echo "recommendations and acceptance-criteria were intentionally NOT drafted."
    echo
  } > "$DRAFT_SUMMARY"

  if [[ ${#ACTIONS[@]} -eq 0 ]]; then
    echo "_No blocker actions were emitted by the chair — nothing to draft._" >> "$DRAFT_SUMMARY"
    AUTOFIX_STATUS="no_blockers"
  elif ! command -v claude >/dev/null 2>&1; then
    echo "_claude CLI unavailable — could not draft fixes. Blockers listed below for manual action:_" >> "$DRAFT_SUMMARY"
    for a in "${ACTIONS[@]}"; do echo "- $a" >> "$DRAFT_SUMMARY"; done
    AUTOFIX_STATUS="no_drafter"
  else
    idx=0
    for a in "${ACTIONS[@]}"; do
      idx=$((idx+1))
      _jqget() { if command -v jq >/dev/null 2>&1; then printf '%s' "$a" | jq -r "$1 // empty" 2>/dev/null; fi; }
      af_id="$(_jqget '.id')"; af_target="$(_jqget '.target')"
      af_instr="$(_jqget '.instruction')"; af_ctype="$(_jqget '.change_type')"
      [[ -z "$af_id" ]] && af_id="blocker-${idx}"
      [[ -z "$af_instr" ]] && { n_fail=$((n_fail+1)); continue; }

      # Resolve target: prefer path relative to the reviewed doc's dir; fall back to the doc itself.
      tgt=""
      if [[ -n "$af_target" && -f "${DOC_DIR}/${af_target}" ]]; then tgt="${DOC_DIR}/${af_target}"
      elif [[ -n "$af_target" && -f "$af_target" ]]; then tgt="$af_target"
      elif [[ -f "$DOC_ABS" ]]; then tgt="$DOC_ABS"; fi
      if [[ -z "$tgt" || ! -f "$tgt" ]]; then
        { echo "### ${idx}. ${af_id} — SKIPPED (target not found: ${af_target:-none})"; echo; } >> "$DRAFT_SUMMARY"
        n_fail=$((n_fail+1)); continue
      fi

      # DRAFT on a copy — never touch the original.
      work_copy="${DRAFT_DIR}/${idx}_$(basename "$tgt")"
      cp "$tgt" "$work_copy" 2>/dev/null || { n_fail=$((n_fail+1)); continue; }
      # Ask the drafter to wrap the edited file in sentinels; we extract ONLY what's between
      # them, so any model preamble/commentary is deterministically stripped (structural, not
      # prompt-only — per the measured-not-reasoned doctrine).
      draft_prompt="$(printf 'Apply exactly ONE minimal edit to the file, per the instruction. Change ONLY what the instruction says; leave everything else byte-for-byte identical. Output the COMPLETE edited file wrapped EXACTLY between a line reading <<<FILE_BEGIN>>> and a line reading <<<FILE_END>>>, with NOTHING before or after those markers and NO markdown fences.\n\nEDIT INSTRUCTION:\n%s\n\n<<<FILE_BEGIN>>>\n%s\n<<<FILE_END>>>\n' \
        "$af_instr" "$(cat "$work_copy")")"
      raw_draft="$(printf '%s' "$draft_prompt" | claude -p --model "$CHAIR_MODEL" \
                   --disallowed-tools "Bash Edit Write Read WebFetch" 2>>"${DRAFT_DIR}/draft.err")"
      # Extract strictly between the sentinels; fall back to raw only if markers are absent.
      if printf '%s' "$raw_draft" | grep -q '<<<FILE_BEGIN>>>'; then
        drafted="$(printf '%s' "$raw_draft" | awk '
          /<<<FILE_BEGIN>>>/ {grab=1; next}
          /<<<FILE_END>>>/   {grab=0}
          grab {print}')"
      else
        drafted="$raw_draft"
      fi
      if [[ -n "$drafted" ]]; then
        printf '%s\n' "$drafted" > "$work_copy"
        diff_out="$(diff -u "$tgt" "$work_copy" 2>/dev/null)"
        if [[ -n "$diff_out" ]]; then
          {
            echo "### ${idx}. ${af_id} (${af_ctype:-doc}) — target: \`${af_target:-$(basename "$tgt")}\`"
            echo "**Instruction:** ${af_instr}"
            echo
            echo '```diff'
            printf '%s\n' "$diff_out"
            echo '```'
            echo
          } >> "$DRAFT_SUMMARY"
          n_ok=$((n_ok+1))
        else
          { echo "### ${idx}. ${af_id} — no change produced (draft matched original)"; echo; } >> "$DRAFT_SUMMARY"
          n_fail=$((n_fail+1))
        fi
      else
        { echo "### ${idx}. ${af_id} — draft step failed (see draft.err)"; echo; } >> "$DRAFT_SUMMARY"
        n_fail=$((n_fail+1))
      fi
    done
    AUTOFIX_STATUS="drafted:${n_ok}ok/${n_fail}fail"
  fi

  # Append the draft bundle to the report so the diffs travel WITH the review.
  { echo; echo "---"; cat "$DRAFT_SUMMARY"; } >> "$FINAL"
fi

if [[ -n "$OUTPUT" ]]; then
  mkdir -p "$(dirname "$OUTPUT")" 2>/dev/null
  if cp "$FINAL" "$OUTPUT" 2>/dev/null; then
    echo "$OUTPUT"
  else
    echo "council-review: could not write to ${OUTPUT}; report is at ${FINAL}" >&2
    echo "$FINAL"
  fi
else
  echo "$FINAL"
fi

_ledger_append "ok" "${#AVAIL[@]}"
exit 0
