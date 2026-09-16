# Stress-test results

Hostile validation of generate / validate / report / corpus / CLI.

**Headline:** 7 real bugs found and fixed, all in validation, report, policy,
or CLI. None of them would have shown up from adding another scenario family.

| # | Bug | Severity | Fix |
|---|-----|----------|-----|
| 1 | `report.md` presented a critical path as fact even when `validate` FAILed | Critical | Report runs validation and banners FAIL |
| 2 | `SourceEntry.path` resolved `../../etc/passwd` | High | Load-time validator + `is_relative_to` |
| 3 | Findings could point at nodes that do not exist | High | graph-risk resource check |
| 4 | "scanner never ran" and "checkov.json corrupt" printed the same | Medium | `not_scored_reason` diagnostic |
| 5 | OPA had no secret enforcement | Medium | family-agnostic secret-scan deny |
| 6 | `deployable: true` leaked a raw traceback | Medium | CLI catches `ValidationError` |
| 7 | Read-only `--out` leaked a raw `OSError` | Medium | CLI catches `OSError` |

Mutation determinism: 2,000 variants (2 families x 1,000 seeds), 0 FAIL.
HCL injection: 108 hostile values x every string sink; emitter held.

See [stress-contract.md](stress-contract.md) for the 15 clauses.
