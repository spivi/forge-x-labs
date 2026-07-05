---
name: handoff-review
description: "Non-blocking human-review handoff for a delivered wave. Emits ONE human-only GitHub tracking issue per wave (the wave's accept-ticket) that showcases each merged feature with a review checkbox and feedback slot; routes per-feature feedback to the original ticket; on clear the human signs off the WHOLE wave (underlying feature tickets stay Done). Use when: /handoff-review, emit handoff, review wave, human review, sign off wave, clear handoff. Actions: emit <ticket-ids>, clear <handoff-issue>."
---

# Handoff-Review Skill

A **non-blocking, human-only** review handoff. After a wave merges, `emit` creates **one**
GitHub tracking issue per wave — **the wave's single accept-ticket** — that showcases each
delivered feature for the human to review at leisure. The human reviews, leaves any
per-feature feedback inline, and on `clear` **signs off the whole wave** (the underlying
feature tickets stay `Done`); per-feature feedback still routes to the original ticket.

This is distinct from the `handoff` skill (which saves AI-session→session state for a
platform switch, NOT human review). Governed by `HANDOFF_REVIEW` in `project.conf`
(off by default; needs a GitHub repo via `GITHUB_OWNER`/`GITHUB_REPO`).

> **Human-only invariant.** The emitted issue carries the `handoff:human-review` label —
> **that label is the gate**: `/sprint plan`/`execute` excludes it (`-label:handoff:human-review`,
> per `.dev-context/rules/iteration-gate.md`) so no AI agent ever claims or works it.

## Action: `emit <ticket-ids…>`

Create the wave's handoff issue. NON-BLOCKING and **fail-soft** — a failure is surfaced but
never blocks/reverts the merge (the wave already shipped).

1. **Gather per-feature material.** For each ticket, read its delivery record
   `.dev-context/sprint-runs/{{TICKET_PREFIX}}-<NNN>-result.md` (Status, PR, what-shipped,
   Rail evidence).

2. **Build the showcase** (one artifact per wave, anchored per feature):
   - If `HANDOFF_RENDER_CMD` is set in `project.conf`, run it to render the app's primary
     artifact (e.g. an HTML report) and link it; otherwise link each feature's **PR diff**
     and its **Rail evidence** line. Never block on rendering — a render failure degrades to
     the PR-link form.
   - (Optional) If the project has a vis-UI surface and `VIS_UI_GATE` is configured, attach
     `scripts/app_screenshot.py` captures (Playwright cloud-skip: in cloud, link instead of
     blocking).

3. **Compose the issue body** — one block per feature, each with:
   ```
   <!-- feature:{{TICKET_PREFIX}}-<NNN> -->
   ## #<NNN> — <title>   [ ] reviewed
   **Showcase:** <artifact link or PR diff> · PR #<n> · Rail: <R|U — claim>
   <one-line what-shipped>
   <!-- feedback:start -->
   _(leave blank to accept; write feedback here to route it to #<NNN>)_
   <!-- feedback:end -->
   ```
   Plus a header explaining: this single issue IS the wave's accept-ticket — review the
   features, write in a feedback slot to send that text back to a feature's original ticket,
   then close THIS issue (or run `/handoff-review clear <this-issue>`) to sign off the wave.

4. **Create the issue** with the human-only label (works on any GitHub repo):
   ```bash
   gh issue create --repo "$GITHUB_OWNER/$GITHUB_REPO" \
     --title "Handoff: <wave name> (#<NNN> …)" --body-file <body.md> \
     --label "handoff:human-review"
   ```
   (When `TRACKER_BACKEND=github_projects`/`linear`, also add the issue to the board and set
   `Status="In review"` + the wave's iteration so it shows as a card in the human's filtered
   view. Under `none` the issue + label alone is the handoff — no board.)
   Print the issue number/URL.

## Action: `clear <handoff-issue>`

Process the human's review and take the handoff off the table. **Fail-soft per feature** — one
feature's routing error never aborts the rest.

1. **Read the current issue body** (`gh issue view <handoff-issue> --json body,comments`). The
   human has checked some `[x] reviewed` boxes and/or filled some `<!-- feedback:start -->`
   slots; also read comments for any `re: {{TICKET_PREFIX}}-NNN` feedback.

2. **Route per-feature feedback (only).** For each feature block whose slot has
   non-placeholder text (or a `re:` comment targets it), route that text to the original
   ticket — reopen it if closed, add `needs-rework`, and post the feedback as a comment
   (pass the body via `--body-file`, never string-interpolated — injection-safe):
   ```bash
   gh issue reopen <NNN> --repo "$GITHUB_OWNER/$GITHUB_REPO" 2>/dev/null || true
   gh issue edit  <NNN> --repo "$GITHUB_OWNER/$GITHUB_REPO" --add-label "needs-rework"
   gh issue comment <NNN> --repo "$GITHUB_OWNER/$GITHUB_REPO" --body-file <feedback.md>
   ```
   A feature WITH feedback is sent back; do NOT sign off the wave if ANY feature got
   feedback — surface that the wave is not fully signed off and stop (the human re-runs
   `clear` after the rework lands). Features with NO feedback are already `Done`.

3. **Sign off the wave** — only when NO feature had feedback. Close the handoff issue:
   ```bash
   gh issue close <handoff-issue> --repo "$GITHUB_OWNER/$GITHUB_REPO" --reason completed
   ```
   (Under `github_projects`/`linear`, also move the handoff card to `Accepted`; the
   underlying feature tickets stay `Done` and are NOT individually moved.)
   Print a summary: wave → signed off, or which features → routed-for-rework.

## Validation

- The handoff issue MUST carry `handoff:human-review` (the label is the human-only gate that
  excludes it from `/sprint`).
- **Sign-off = the single handoff issue closed/Accepted** (one per wave). Underlying feature
  tickets stay `Done`; never bulk-accept them.
- Feedback bodies are passed via `--body-file` (never string-interpolated) — injection-safe.
- `clear` is idempotent: re-running skips already-routed feedback and an already-closed issue.
- Never block a merge on `emit`; never abort `clear` on one feature's failure.
