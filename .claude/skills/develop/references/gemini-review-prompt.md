# Gemini Review Pre-pass Prompt

Used by `scripts/harness_router.sh review-prepass`. The prompt is embedded in the
script — this file documents it and its rationale for human review.

## Prompt text

```
Review this code diff for bugs and correctness issues. Return ONLY valid JSON, no other text, matching exactly:
{"verdict":"PASS|FAIL","findings":[{"severity":"P1|P2|P3","file":"<path>","line":0,"message":"<issue>"}]}
verdict is PASS when findings is empty. P1=critical/high, P2=medium, P3=low.
Focus on correctness, not style.
```

## Verdict schema

```json
{
  "verdict": "PASS | FAIL",
  "findings": [
    {
      "severity": "P1 | P2 | P3",
      "file": "path/to/file.py",
      "line": 42,
      "message": "What is wrong and why it matters"
    }
  ]
}
```

## Severity mapping

| Gemini severity | Claude gate behavior |
|----------------|---------------------|
| P1 | Blocks merge — must fix before Claude review or Claude confirms it |
| P2 | Claude reviewer sees it as a pre-identified issue to validate |
| P3 | Acknowledged; does not block |

## How findings are consumed (claude-review-gate.md Step 0)

- **PASS** (empty findings, non-security diff) → skip the Claude reviewer entirely, proceed to merge.
- **FAIL** → pass the `findings` JSON to the Claude reviewer's prompt as "pre-identified issues to validate or refute." Claude's task narrows to: confirm each finding is real, fix P1s, note P2s.
- **Router exits 2** (Gemini failed/exhausted/not installed/security surface) → ignore the pre-pass, proceed with the unmodified Claude review gate.

## What Gemini should NOT flag

- Style, formatting, trailing whitespace, comment phrasing.
- Missing type annotations (mypy covers this).
- Test coverage gaps (coverage tooling covers this).
- Anything already caught by ruff, mypy, or pytest in CI.

These are explicitly excluded to avoid false positives that would defeat the pre-pass savings.
