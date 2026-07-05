---
description: "Review code against project rules. Trigger: /review, review code, check rules, code review"
arguments:
  - name: target
    description: "File path, directory, or 'staged' for git staged changes"
    required: true
---

# Code Review Skill

Review code for compliance with all project rules.

## Instructions

1. **Read all rule files** in `.dev-context/rules/`
2. **Identify the target**: specific file, directory, or staged git changes
3. **Check each rule category** against the code:

### General Rules Check
- [ ] Functions ≤ 30 lines, single responsibility
- [ ] ≤ 3 parameters per function
- [ ] No magic numbers/strings
- [ ] No dead code or commented-out code
- [ ] Proper error handling (no bare except)

### Python Rules Check
- [ ] Type annotations on all functions
- [ ] Thin route handlers (validate → service → response)
- [ ] SQLAlchemy 2.0 `select()` style (no legacy Query)
- [ ] Pydantic v2 syntax (`ConfigDict`, `model_dump`)
- [ ] Repository pattern respected (no DB in routes/services)

### Security Rules Check
- [ ] Auth via `Depends()`, not manual token checks
- [ ] No SQL string formatting (parameterized only)
- [ ] No `allow_origins=["*"]`
- [ ] Secrets from env vars, not hardcoded
- [ ] Response schemas exclude sensitive fields

### Testing Rules Check
- [ ] Async test functions
- [ ] `dependency_overrides` for mocking (not monkeypatch)
- [ ] Factory-boy for test data
- [ ] AAA structure, descriptive test names

### Git Rules Check
- [ ] Conventional commit format
- [ ] No secrets in staged changes
- [ ] One logical change per commit

## Output Format

```
## Code Review: [target]

### 🟢 Passing
- [rule]: [evidence]

### 🔴 Violations
- [rule]: [file:line] — [description] — [fix suggestion]

### 💡 Suggestions
- [optional improvement, not a rule violation]

**Verdict**: PASS / FAIL ([N] violations)
```
