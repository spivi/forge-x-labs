# Ralph Loop Prompt Template

Substitute `{{TICKET_PREFIX}}-<NNN>`, `<ticket title>`, `<acceptance criteria>`,
`<worktree path>`, and `{{PROJECT_NAME}}` before invoking `/ralph-loop`.

```
/ralph-loop "You are implementing ticket {{TICKET_PREFIX}}-<NNN> in worktree ../{{PROJECT_NAME}}--{{TICKET_PREFIX}}-<NNN>.

## Ticket
<ticket title>

## Acceptance Criteria
<acceptance criteria from PRD or ticket, as checklist>

## Mandatory Process
1. Read the PRD at .dev-context/prds/{{TICKET_PREFIX}}-<NNN>.md (if exists)
   - If PRD contains a '## Design Spec' section, follow it as binding UX constraints
   - For any HTML/CSS work, also read .dev-context/design-guidelines.md
2. Read STATUS.md — note files touched by other active branches and avoid them
3. **Fetch library docs via Context7** (per .dev-context/rules/context7.md):
   - Identify which external libraries this ticket touches
   - For each library in the Context7 mandatory list: resolve-library-id → query-docs
   - If Context7 MCP unavailable: use WebSearch/WebFetch as fallback
   - Do this BEFORE writing any code or tests
4. Use /test-driven-development skill for structured TDD:
   - Write failing test FIRST
   - Implement minimal code to make test pass
   - Verify test passes
   - Refactor if needed
   - Commit: feat({{TICKET_PREFIX}}-<NNN>): <subject>  (or fix() for Fix tier)
5. Follow all rules in .dev-context/rules/:
   - Max 30-line functions, max 200-line modules
   - Type annotations on all functions
   - from __future__ import annotations in every module
6. Test requirements:
   - Feature: unit tests (happy + error paths) + integration test for API endpoints
   - Bug fix: regression test reproducing the bug + unit test for the fix

## Validation (ALL must pass before outputting promise)
1. ruff check . --fix && ruff format .
2. mypy app/ --ignore-missing-imports
3. PYTHONPATH=. pytest tests/ --cov=app --cov-fail-under=85
4. pre-commit run --all-files

## Completion
When ALL four validation steps pass with zero errors:
<promise>DEVELOPMENT COMPLETE</promise>

## If Stuck
If the same error persists after 3 fix attempts: STOP.
Describe the blocker clearly. Do NOT output the promise.
Do NOT use --no-verify or skip any validation step.
" --completion-promise "DEVELOPMENT COMPLETE" --max-iterations 20
```
