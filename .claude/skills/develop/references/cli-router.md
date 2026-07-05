# CLI Router — Harness Efficiency Policy

Routes long harness output through the Gemini CLI before injecting it into Claude's
context, and pre-filters PR diffs to avoid spending Sonnet/Opus on clean changes.
Opt-in (`HARNESS_ROUTER=on` in `project.conf`); requires a `gemini` CLI install.
Fully fail-soft — when Gemini is unavailable the harness uses the raw input unchanged.

## When to use

| Trigger | Operation | Expected saving |
|---------|-----------|----------------|
| Reading pytest / mypy / ruff output > 50 lines | `summarize-ci` | ~90% context reduction |
| Reading `gh run view --log` output | `summarize-ci` | ~95% context reduction |
| Reading `gh pr diff` output before summary | `summarize-diff` | ~85% context reduction |
| Before the Claude review gate (non-security diff) | `review-prepass` | 100% review tokens on PASS |

## Invocation pattern

```bash
# Capture long output to a temp file, route through Gemini, fall back to raw
_ci_out=$(mktemp)
PYTHONPATH=. .venv/bin/pytest ... 2>&1 | tee "$_ci_out"
_summary=$(TICKET="$TICKET" scripts/harness_router.sh summarize-ci < "$_ci_out")
_exit=$?
if [[ $_exit -eq 0 ]]; then
    echo "CI summary: $_summary"   # inject summary into Claude context
else
    cat "$_ci_out"                 # fallback: raw output (current behavior)
fi
rm -f "$_ci_out"
```

## Fallback protocol

Exit code 2 from `harness_router.sh` means all providers failed (or Gemini is not
installed). **Always fall back to current behavior — never block the harness.**

```bash
scripts/harness_router.sh review-prepass < diff.txt || true
# if exit code != 0 → proceed to the Claude review gate unchanged
```

## Exhaustion detection

`harness_router.sh` detects a missing `gemini` binary, rate-limit / quota errors,
and non-JSON output internally and exits 2. The harness never needs to parse
Gemini's error messages.

## Security surface guard

`review-prepass` automatically exits 2 (force Claude) when the diff touches a path
matching `SECURITY_SURFACE_GLOB` (`project.conf`; portable default covers `auth`,
`secret`, `crypto`, `token`, `password`, `DECISIONS.md`, `security.md`). No harness
skill needs to check this manually. Keep this glob aligned with the review gate's
security-surface list (`claude-review-gate.md`).

## Benchmark ledger

Every call writes one row to `.dev-context/kpis/cli-routing.csv` (fail-soft).
Run `python scripts/debrief.py --cli-routing-report` after 5+ calls to see
threshold verdicts (avg latency, fallback rate, Claude-skips).

## Environment variables

| Var | Default | Purpose |
|-----|---------|---------|
| `TICKET` | `` | Ledger row tag |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Override Gemini model |
| `HARNESS_ROUTER_TIMEOUT` | `30` | Per-call timeout (seconds) |
| `HARNESS_ROUTER_LEDGER` | `.dev-context/kpis/cli-routing.csv` | Override ledger path |
| `SECURITY_SURFACE_GLOB` | (from `project.conf`) | Diff paths that always go to Claude |
