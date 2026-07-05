---
name: code-review
description: "Review code compliance with project rules in .dev-context/rules/ (general, python, security, testing, git). Use when: /review, review code, check rules, code review, check my code, lint check, rule violations, compliance check. Target: file path, directory, or 'staged' for git staged changes."
---

# Code Review Skill

Review code for compliance with all project rules.

## Instructions

1. **Read all rule files** in `.dev-context/rules/`
2. **Identify the target**: specific file, directory, or staged git changes
3. **Check each rule category** against the code — use the checklists in each rule file as your guide

Enforce all rules from: `general.md`, `python.md`, `security.md`, `testing.md`, `git.md`

## Output Format

```
## Code Review: [target]

### Passing
- [rule]: [evidence]

### Violations
- [rule]: [file:line] — [description] — [fix suggestion]

### Suggestions
- [optional improvement, not a rule violation]

**Verdict**: PASS / FAIL ([N] violations)
```
