---
name: prd
description: "Product manager: generate PRDs with threat modeling, manage roadmap, create backlog tickets. Use when: /prd, product requirements, roadmap, feature idea, write requirements, new feature spec, what should we build. Actions: <idea> (generate PRD), roadmap (codebase analysis), list (show PRDs), approve/reject <id>."
---

# PRD Skill (Product Manager)

Generate structured Product Requirements Documents from ideas, manage the
product roadmap, and create backlog tickets. Read the full agent definition
at `.dev-context/agents/product_manager.md` before proceeding.

## Instructions

### Action: `<idea>` (default — generate PRD)

Generate a PRD from a feature idea or improvement request.

1. **Read context** (mandatory, in order):
   - `.dev-context/project.conf` → project ID
   - `STATUS.md` → current phase, active work, blockers
   - `DECISIONS.md` → architectural constraints (check for conflicts)
   - Ticket backlog: Linear MCP `list_issues` (team filter: {{TICKET_PREFIX}}) → verify idea isn't already tracked. Fallback: `gh issue list` if Linear MCP unavailable

2. **Analyze feasibility** (mandatory):
   - Scan the codebase to identify affected modules and files
   - Check existing abstractions — can we extend or need something new?
   - Review related test files — what coverage exists?
   - Look for similar patterns already in the codebase
   - Estimate complexity: S (1-2 files), M (3-5 files), L (6+ files)

3. **Generate PRD** using the template at `references/prd-template.md`

4. **Security threat model** (mandatory):

   After generating the PRD, produce a threat model advisory by reading the
   Security Architect agent definition at `.dev-context/agents/security_architect.md`
   (section "Threat Model Advisory"). Analyze the proposed feature for:

   - **Attack surface**: New endpoints, data flows, or integrations introduced
   - **Threats**: Evaluate against three OWASP frameworks:
     1. **OWASP Top 10 (Web Apps)**: Injection, broken auth, XSS, SSRF, etc.
     2. **OWASP API Security Top 10**: BOLA, broken auth, excessive data exposure,
        lack of rate limiting, mass assignment, SSRF, etc.
     3. **OWASP Top 10 for LLM Applications**: Prompt injection, insecure output
        handling, training data poisoning, model DoS, supply chain vulnerabilities,
        sensitive information disclosure, insecure plugin design, excessive agency, etc.
   - **Mitigations**: Concrete security controls for each threat

   Append threat model using the template at `references/threat-model-template.md`

5. **Present to human** for approval:
   ```
   ## PRD Review: <title>

   <Full PRD content, including Threat Model section>

   ---
   Recommended action:
   - Approve → I'll create a GitHub Issue with labels
   - Revise → tell me what to change
   - Reject → I'll archive it
   - Defer → I'll add it to the roadmap for later
   ```

6. **On approval** — create ticket (Linear-first):
   - **Primary** — Linear MCP `save_issue` (or `create_issue` if new):
     - team: {{TICKET_PREFIX}}
     - title: `<title>`
     - description: `<PRD body as markdown>`
     - priority: mapped (P0→1 Urgent, P1→2 High, P2→3 Normal, P3→4 Low)
     - state: "Backlog"
     - Linear↔GitHub sync auto-creates the corresponding GitHub Issue
   - **CRITICAL — Linear markdown formatting**:
     - Pass the `description` parameter as a **real multi-line string** with actual
       newlines, NOT escaped `\n` sequences. The MCP tool accepts multi-line strings
       natively. Escaped `\n` gets double-escaped and renders as literal `\\n` in Linear.
     - Use standard markdown: `## Headings`, `- [ ] checkboxes`, `**bold**`, `| tables |`
     - Linear auto-converts `- item` to `* item` — both are fine
     - Keep descriptions concise for Linear (summary + acceptance criteria + scope +
       dependencies). Link to the full PRD file for details: `Full PRD: \`.dev-context/prds/{{TICKET_PREFIX}}-NNN.md\``
   - **Fallback** (if Linear MCP unavailable):
     `gh issue create --title "{{TICKET_PREFIX}}-<NNN>: <title>" --body "<PRD>" --label "priority:<P>,status:ready"`
     Log warning: "Linear MCP unavailable — created via gh CLI."
   - Save PRD to `.dev-context/prds/<{{TICKET_PREFIX}}-NNN>.md`
   - **Stamp the planning pair (REQUIRED — satisfies the planning gate)**: seed the
     AI wall-clock estimate + cheapest-sufficient model into the canonical
     `estimates.csv` (and mirror to the tracker). Use the complexity bucket from
     step 4 as the `effort:` label:
     ```bash
     python scripts/tracker.py plan {{TICKET_PREFIX}}-<NNN> --type <feature|fix|tweak> \
        --labels "effort:<S|M|L>" --priority "<P0|P1|P2|P3>"
     ```
     This reads `planning/base-estimates.yml` × learned `calibration.json` /
     `model-policy.json` (`scripts/estimator.py`). Report the seeded pair.
   - Report: "Ticket created: {{TICKET_PREFIX}}-<NNN> — est <N>m on <model>, ready for next sprint"

### Action: `roadmap`

Analyze the codebase and generate a prioritized roadmap of improvements.

1. **Read context** (same as above)

2. **Scan codebase** for improvement opportunities:
   - `grep -r "TODO\|FIXME\|HACK\|XXX"` across `app/` and `tests/`
   - Identify modules without corresponding test files
   - Check for stale code (files with TODOs older than 30 days)
   - Review DECISIONS.md for deferred items
   - Analyze error handling patterns (missing error paths, bare excepts)
   - Check for features referenced in docs but not implemented
   - Review recent git log for areas of frequent churn (instability signals)

3. **Prioritize findings**:
   - P0: Security gaps, data loss risks
   - P1: Missing core functionality, broken user flows
   - P2: Code quality, test coverage, performance
   - P3: Nice-to-have improvements, cosmetic issues

4. **Present roadmap**:
   ```
   ## Roadmap — <date>

   ### High Priority (P0-P1)
   | # | Finding | Type | Affected Files | Suggested Action |
   |---|---------|------|---------------|-----------------|
   | 1 | <finding> | <type> | <files> | <action> |

   ### Medium Priority (P2)
   ...

   ### Low Priority (P3)
   ...

   ### Summary
   - Total items found: N
   - Aligned with current project goals: N (NN%)
   - New opportunities identified: N

   ### Recommended Next Sprint Items
   1. <item> — because <reason>
   2. <item> — because <reason>
   3. <item> — because <reason>

   ---
   To create a PRD for any item: `/prd <describe the item>`
   ```

5. **On human selection**: Generate individual PRDs for chosen items

### Action: `list`

Show all PRDs and their status.

1. **Scan** `.dev-context/prds/` for existing PRD files
2. **Cross-reference** with Linear MCP `list_issues` (fallback: `gh issue list`) to get current status
3. **Present**:
   ```
   ## PRDs

   | # | Title | Status | Priority | Ticket |
   |---|-------|--------|----------|--------|
   | 1 | <title> | Draft / Approved / Rejected / Deferred | P0-P3 | {{TICKET_PREFIX}}-NNN or — |
   ```

### Action: `approve <id>`

Mark a draft PRD as approved and create the GitHub Issue.

1. Read the PRD from `.dev-context/prds/<id>.md`
2. Create ticket (Linear-first): Linear MCP `create_issue` (team: {{TICKET_PREFIX}}). Fallback: `gh issue create`
3. Update PRD status to "Approved"

### Action: `reject <id>`

Mark a PRD as rejected.

1. Read the PRD from `.dev-context/prds/<id>.md`
2. Update status to "Rejected" with reason
3. Move to archive (keep the file, just update status)

## Validation

- Never create GitHub Issues without explicit human approval
- Always check DECISIONS.md for conflicts before writing a PRD
- Always include acceptance criteria — no PRD without testable criteria
- Always estimate scope — "unknown" is acceptable but must trigger a spike recommendation
- Never assign priority P0 without human confirmation
- Always save PRDs to `.dev-context/prds/` for traceability
- If the idea already exists as a ticket, link to it instead of creating a duplicate
- Roadmap scans are limited to top 15 items to avoid overwhelming the human
- When `gh` CLI is unavailable, save PRD locally and inform human to create the issue manually
