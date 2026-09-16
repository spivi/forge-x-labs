# Validated under stress

This is the machine-checkable definition of hardened. A build passes stress
only if all 15 clauses hold.

A single scenario is "validated" when schema, graph, ground truth, Terraform,
and the risk engine agree. This contract asks a harder question: can the tool
be made to lie, deploy, leak, lose ground truth, emit invalid artifacts, or
export unsafe data under adversarial or high-volume input?

## The 15 clauses

| # | Clause | Enforced by |
|---|--------|-------------|
| S1 | No generated scenario is deployable. | `deployable` field validator |
| S2 | No generated artifact requires cloud credentials. | dummy account `000000000000`; no apply path |
| S3 | No unsafe HCL interpolation (`${` / `%{`) or duplicate resource labels. | `neutralize_hcl_openers`; `check_label_collisions` |
| S4 | No graph can claim a critical path unless that path is connected. | graph-risk + BFS |
| S5 | No expected finding references a missing resource. | graph-risk |
| S6 | No broad grant exists without a documented expected finding. | graph-risk |
| S7 | No destructive permission survives validation. | forbidden-permission patterns |
| S8 | No unsafe-operational text enters the training export, including under `--include-restricted`. | `learn/_safety` |
| S9 | Restricted / metadata_only / unknown sources do not enter the training export by default. | reuse-status gate |
| S10 | Same input and seed produce byte-identical output. | `random.Random(seed)` |
| S11 | Different seeds preserve risk invariants. | mutation is cosmetic only |
| S12 | Scanner scoring stays stable on malformed, partial, empty, and unexpected output. | fail-soft parse |
| S13 | Optional tools fail-soft only when absent or environmentally blocked. | `tool_probe` |
| S14 | Tool syntax/config failures fail hard. | terraform syntax error or OPA deny is FAIL |
| S15 | Reports cannot render false success when validation failed. | report includes validation outcomes |

## Fail and fix

A stress test that reproduces a genuine contract violation is a real bug:
write a minimal reproducer, fix the guard, add regression coverage, re-run.
A test that fails because the test is wrong is a test bug. A hostile input
rejected with a clear error is the guarantee working.
