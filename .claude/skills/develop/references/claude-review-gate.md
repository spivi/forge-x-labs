# Claude AI Review Gate (fresh-context loop)

Canonical procedure for **running** an in-session Claude PR review and turning it into a
merge gate. Used by `/develop` (Phases 5–6) and `/sprint merge`. Governed by
`AI_REVIEW_GATE` in `.dev-context/project.conf`.

The reviewer is **fresh-context** (independent of the author), **incremental** (cycle 2+
reviews only the new delta), **push-time enforced** (SHA-keyed `ai-code-review` status),
and **self-improving** (label/spec/scope process-insights feed `/debrief`).

> **Independence + one-tier-stronger evaluator.** The reviewer is a *separate* Task agent
> that never sees the author's reasoning — only the diff, the rule files, and the ticket
> spec/labels (see `fresh-reviewer-prompt.md`). It runs **exactly one tier above the
> author's dev model**: haiku-dev → sonnet review, sonnet-dev → opus review, opus-dev →
> opus review (top tier — a *fresh, independent* Opus at higher effort). Floor override:
> any diff touching a path matching `SECURITY_SURFACE_GLOB` always reviews at Opus.
> Fail **closed**: if the gate cannot run, do NOT merge.

## 0. Gemini pre-pass (skip Step 1 on PASS) — only when `HARNESS_ROUTER=on`

Before dispatching the Claude reviewer, run the Gemini pre-filter on the PR diff. This
saves all Sonnet/Opus tokens when the diff is clean and does not touch security surfaces.
When `HARNESS_ROUTER=off` (default), skip this step entirely and go to Step 1.

```bash
PR=<n>
gh pr diff "$PR" > /tmp/pr-diff-$PR.txt
TICKET="<ticket>" scripts/harness_router.sh review-prepass < /tmp/pr-diff-$PR.txt > /tmp/gemini-verdict-$PR.json
PREPASS_EXIT=$?
```

| Condition | Action |
|-----------|--------|
| `PREPASS_EXIT=0` AND `verdict=PASS` | **Skip Steps 1–3.** Record with `provider=gemini-prepass`, then Steps 4–6. No Claude reviewer dispatched. |
| `PREPASS_EXIT=0` AND `verdict=FAIL` | Proceed to Step 1. Pass Gemini's `findings` JSON to the Claude reviewer as "pre-identified issues to validate or refute." |
| `PREPASS_EXIT=2` (security surface / Gemini absent / failure) | **Skip this step.** Proceed to Step 1 as if Step 0 did not exist. |

The security-surface guard is enforced inside `harness_router.sh` via `SECURITY_SURFACE_GLOB`.

## 1. Dispatch the fresh-context reviewer

Pick the reviewer model from the diff surface, then dispatch the reviewer **as an
independent Task subagent** using `references/fresh-reviewer-prompt.md`. The reviewer runs
**both** `/code-review` (rule/correctness) **and** `/security-review` (OWASP), plus the
process-insight pass, and returns a single structured JSON verdict.

```bash
PR=<n>; TICKET={{TICKET_PREFIX}}-<NNN>; BASE=origin/master
# Read SECURITY_SURFACE_GLOB from project.conf; force opus on a security/arch surface.
GLOB="$(sed -n 's/^SECURITY_SURFACE_GLOB=//p' .dev-context/project.conf | head -1)"
gh pr diff "$PR" --name-only | grep -Eq "$GLOB" && REVIEWER_MODEL=opus || REVIEWER_MODEL=sonnet
echo "reviewer: $REVIEWER_MODEL"
```

The developer who wrote the diff **does not** review it. Phase 5 of `/develop` no longer
self-reviews in the author's context — it hands off to this independent reviewer.

## 2. Triage by severity

| Severity | Gate behavior |
|----------|---------------|
| P1 (HIGH / CRITICAL) | **Blocks merge.** Must fix or, with explicit human sign-off, dismiss with a logged rationale. |
| P2 (MEDIUM) | Fix within the review cycle budget; if deferred, log why and file a follow-up ticket. |
| P3 / P4 (LOW / INFO) | Address if cheap; otherwise acknowledge. Does not block. |

`verdict == "FAIL"` iff any P1 exists. Ambiguous severity is treated as P2 (fail toward caution).

## 3. Incremental fix → re-review (≤ 3 cycles)

```
reviewed_sha = BASE ; cycle = 1 ; MAX = 3
loop:
  head = git rev-parse HEAD
  scope = (cycle == 1) ? BASE...head : reviewed_sha...head   # cycle 2+ = ONLY the fix delta
  verdict = dispatch fresh reviewer (fresh-reviewer-prompt.md) on `scope`,
            carrying the prior cycle's open P1/P2 to re-confirm fixed
  reviewed_sha = head
  if verdict.verdict == "PASS":  break -> PASS
  if cycle == MAX:               break -> ESCALATE   # P1 remains after 3 — do NOT merge
  fix P1 (+ in-budget P2) minimally ; ruff --fix && ruff format && mypy && pytest (diff-cover ≥80%)
  git commit --signoff ; git push ; cycle += 1
```

- **Speed:** cycle 1 = full diff + the one-time process-insight pass; cycles 2–3 review
  ONLY the new delta. No polling — each reviewer Task returns as soon as it finishes.
- **Escalation:** still-P1 after 3 cycles → STOP and ask the human. Do not merge.

## 4. Record the outcome for /debrief

```bash
# `verdict.json` is the reviewer's final JSON message ('-' reads stdin).
python scripts/debrief.py --record-review verdict.json
```

This writes one row to `kpis/reviews.csv` (`provider=claude` for Sonnet, `claude-opus`
for an escalated review). Fails soft — a CSV write error never blocks the merge.

> **Preserve cycle-1 process insights.** The process-insight pass runs ONCE, on the full
> PR diff in cycle 1. When a fix cycle runs, splice cycle-1's `process_insights` into the
> final verdict JSON before `--record-review` (the incremental cycles' insights describe
> only the fix delta and would skew `/debrief`).

## 5. Post the GitHub-visible audit

```bash
python scripts/debrief.py --post-review-audit verdict.json --pr "$PR"
```

Posts a PR summary comment (verdict, per-severity counts, findings, Process & Labels) and
sets the `ai-code-review` **commit status** on the PR head SHA (`success` only on a clean
PASS; `failure` otherwise). This is what the `recheck-on-push` hook flips to `pending` on a
new push and what `/sprint merge` reads. Owner/repo default to `GITHUB_OWNER`/`GITHUB_REPO`
from `project.conf`. Fails soft. If the reviewer flagged `label_accuracy != "ok"`, apply
its `suggested_labels` via `gh issue edit`.

## 6. Merge only when clean

Merge only when **CI is green AND the head SHA carries an `ai-code-review = success`
status** (no unresolved P1). The merge method is `MERGE_METHOD` in `project.conf`
(`merge` | `squash` | `rebase`; default `merge`):

```bash
gh pr merge $PR --"$MERGE_METHOD" --delete-branch
```

> **Push-time enforcement.** The `ai-code-review` status is keyed to the head SHA. Any new
> push produces a new SHA with no PASS, so a stale review can never slip through — the
> `recheck-on-push` hook flips the status to `pending` and `/sprint merge` re-runs the
> incremental review (Step 3) before merging. A SHA that already carries PASS makes the
> hook a no-op (no redundant review). `required_conversation_resolution` (if enabled in
> branch protection) means you must resolve the review thread you posted before merging.
