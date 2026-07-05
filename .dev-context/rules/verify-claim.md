# verify-claim.md — Pre-PR verify-claim guard

> **Status**: ADVISORY. No enforcement machinery, CI gate, or merge block.
> Self-certification by the PR author at review time. If the same failure class
> recurs in a future `/debrief`, escalate to a hard gate via a new ticket.

**Applies to**: Any PR that relabels a reported value **or** adds a new warning
or log line. Two triggers; either one activates the checklist.

---

## Trigger 1 — Relabel / rename of a reported value

When a change renames or relabels a value that appears in a report, CLI output,
log, or user-visible surface (e.g. a column header, a section title, a metric
name):

1. **Trace the actual data source.** Find the expression that produces the value.
   Follow it back to the raw input — a CSV column, a ledger row, a SQL field, an
   API response key.
2. **Confirm the new label matches what the code computes.** If the code sums
   `billed_usd`, the label must say *billed*, not *notional* or *API-equivalent*.
   If it sums `compute_cost_usd`, the label must reflect that.
3. **Self-certify in the PR body**: one sentence naming the source expression and
   confirming the label is accurate.

### Worked example — a mislabeled cost report

A formatter relabeled its output *"notional / API-equivalent"* but it actually
summed a `billed_usd` ledger column. The label was wrong. Tracing the source
(`billed_usd → ledger → formatter`) caught the mismatch before the PR closed.

---

## Trigger 2 — New warning or log line

When a change adds a `warnings.warn(...)`, `logger.warning(...)`, `print(...)`
to stderr, or any other diagnostic emission:

1. **Confirm the output path reaches a visible sink.** A visible sink is: the
   terminal when run interactively, a log file that is actually read, or CI
   stdout/stderr captured by a runner.
2. **Disqualifying sinks** (output is swallowed, trigger fires):
   - `2>/dev/null` wrapping the subprocess or command that emits the message.
   - `$(...)` subshell **combined with** `2>&1` or another stderr redirect (e.g.
     `out=$(cmd 2>&1)`) — plain `$(cmd)` leaves stderr attached to the caller
     and is *not* disqualifying on its own.
   - A stream redirected to a variable or file that is never printed or logged.
3. **Self-certify in the PR body**: one sentence confirming the warning is visible
   (or explaining why silent degradation is intentional and acceptable).

### Worked example — a swallowed warning

A pricing-miss warning was added to a shell hook via an inline `python3 -c "..."`
block. The block was wrapped in `command 2>/dev/null` which swallowed stderr —
the warning never appeared. Checking the output path
(`stderr → 2>/dev/null → /dev/null`) caught the swallow before merge.

---

## How to self-certify

Add one or both lines to the PR body (next to the relevant test-plan item):

```
Claim verified: relabel — formatter sums `billed_usd`; label updated to "billed".
Claim verified: warning — pricing-miss stderr not wrapped in 2>/dev/null; visible in terminal.
```

No special format is enforced; plain prose in the PR body is enough.

---

## Why this rule exists

Claim-vs-reality mismatches — a label that no longer matches what the code
computes, or a warning that never reaches a visible sink — are cheap for an
author to introduce and expensive for a reviewer to catch post-hoc. These two
triggers are the smallest change that closes that gap before the next PR, moving
the verification cost back to the author.

## Reference

- `.claude/skills/develop/SKILL.md` Phase 5 — checklist integration point
