# Architecture Decisions

> Format: `FXL-D<NNN>` | Status: accepted/superseded/deprecated
> Record decisions here so future sessions don't re-litigate them.

---

<!-- Add decisions below. Template:

## FXL-D001: <Decision Title>

**Status**: accepted
**Date**: YYYY-MM-DD

**Context**: <What problem prompted this decision?>

**Decision**: <What was decided and why?>

**Consequences**: <Trade-offs, risks, follow-up work?>

---
-->

## FXL-D001: Product code lives under `app/cloudforge/` (not `src/`)

**Status**: accepted
**Date**: 2026-07-05

**Context**: The dev-template hardcodes a top-level `app/` package across CI
(`--cov=app`, `mypy app/`), the coverage gate, and the CLI entry-point contract
(`[tool.poetry.scripts] cloudforge = "app.cli:app"`). The product spec suggested a
`src/cloudforge/` layout, which would fight those in ~4 places and require editing CI
and the (intentionally inert) agentic tooling.

**Decision**: Keep the `app/` root the template expects. Product code lives in the
`app/cloudforge/` sub-package; `app/cli.py` is a thin re-export of the real Typer app in
`app/cloudforge/cli.py`. This satisfies `--cov=app`, `mypy app/`, and `app.cli:app` with
zero CI edits.

**Consequences**: The import namespace is `app.cloudforge.*` rather than `cloudforge.*`.
Acceptable — the installed console script is still `cloudforge`. If the project ever
outgrows the template, revisit a `src/` migration together with the CI targets.

## FXL-D002: Deterministic, rule-based generation first; validators + ground truth over generation cleverness

**Status**: accepted
**Date**: 2026-07-05

**Context**: Cloud-misconfiguration scenario generation is only useful for benchmarking if
the scenarios are *labeled and validated*. Jumping straight to LLM/diffusion generation
would produce plausible-but-unverified Terraform with no ground truth.

**Decision**: MVP ships a hardcoded `TemplateGenerator` behind a `ScenarioGenerator`
interface. The graph JSON is the source of truth; Terraform is a compiled artifact;
ground-truth paths + expected findings are authored alongside the graph and checked by a
local risk engine. LLM/Modal/diffusion generators are documented as future engines behind
the same interface — not built.

**Consequences**: First slice is narrow (one `ci_cd_iam_chain` family) but every artifact
is self-consistent and machine-checkable. The generator seam keeps future engines additive.


## FXL-D003: A scenario is "validated" only against a 12-point definition (benchmark-grade)

**Status**: accepted
**Date**: 2026-07-05

**Context**: External engineering review distinguished *engineering-valid* ("does the code
work?") from *product-valid* ("are the scenarios useful, realistic, benchmarkable, and hard
to fake?"). "terraform validates" proves syntax, not cloud semantics or scanner-measurement
value. Without a stricter bar, the project risks false confidence.

**Decision**: A generated scenario is "validated" only if it passes ALL of:
1. Schema-valid (scenario.yaml + graph.json).
2. Graph-consistent (every edge references real nodes).
3. Ground-truth paths resolve (nodes + edges exist; path reachable).
4. Expected findings point to real graph resources.
5. No forbidden destructive permissions.
6. Broad grants documented by an expected finding.
7. Terraform emitted successfully.
8. Terraform validates, or fails only for a known environmental/tooling reason (network/provider).
9. Optional scanners either run or warn clearly (fail-soft).
10. Scanner output is scored against expected findings when a scanner ran.
11. Report renders and includes a limitations section.
12. Mutation, if used, preserves ground truth.

Today the pipeline covers ~1–9 and 11; gaps are **#10 (scanner scoring)** and stronger
**#12 (mutation stress)**, plus adversarial generator hardening feeding #7/#8.

**Consequences**: Drives the M7 backlog (FXL-N1 scanner scorer, FXL-N2 adversarial corpus,
FXL-N3 mutation stress, FXL-N4 emitter dedup, FXL-N5 quality rubric). The tracked coverage
metric is "X/12 gates", not "tests pass".

## FXL-D004: Harden validation before adding a third scenario family

**Status**: accepted
**Date**: 2026-07-05

**Context**: The differentiator is *trusted labeled scenarios*, not scenario count. Adding
families before hardening validation multiplies surface area and false confidence.

**Decision**: Complete the M7 validation-hardening wave (scanner scorer, adversarial corpus,
mutation stress, emitter dedup) BEFORE adding any new scenario family. A new family is gated
on the 12-point definition (FXL-D003) being enforceable, not just authorable.

**Consequences**: Near-term roadmap is validation depth, not scenario breadth. The
`ScenarioGenerator` seam stays ready; new families wait.

## FXL-D005: `jsonencode` policy documents are LIVE HCL, and astral chars need raw UTF-8

**Status**: accepted
**Date**: 2026-07-05

**Context**: The FXL-N2 adversarial corpus, run against every string sink under real
`terraform validate`, uncovered two emitter bypasses the FXL-35/FXL-39 hardening missed.
The prior `hcl_str` docstring asserted "JSON policy documents built via `json.dumps` are
already inert (they are not HCL strings)" — this was FALSE.

**Decision**: Two invariants for every untrusted value reaching emitted HCL:
1. **`jsonencode(...)` arguments are LIVE HCL strings.** HCL evaluates `${}`/`%{}` inside
   the JSON string handed to `jsonencode`. A hostile IAM `resource`/`actions` value or a
   bucket-policy `Resource` (which embeds `node.name`) was therefore live: e.g.
   `${data.nonexistent.thing.value}` broke `terraform validate` (undeclared reference), and
   `%{ for x in [1,2] }${x}%{ endfor }` silently evaluated to `12`. Fix: neutralize `${`→`$${`,
   `%{`→`%%{` (extracted as `neutralize_hcl_openers`) at those JSON sinks too — not only in
   `hcl_str`.
2. **Astral-plane characters must be emitted as raw UTF-8, not surrogate escapes.**
   `json.dumps` defaults to `ensure_ascii=True`, escaping e.g. an emoji as a UTF-16 surrogate
   pair `😀`; HCL cannot decode `\uD800`–`\uDFFF` ("Cannot encode character U+d83d"),
   breaking `terraform validate`. Fix: `json.dumps(..., ensure_ascii=False)` (the `.tf` files
   are UTF-8); `"` / `\` / control chars stay escaped. BMP unicode (`café`, `日本`, Cyrillic)
   was already fine via `\uXXXX`.

**Consequences**: `neutralize_hcl_openers` is now the shared HCL-opener guard, applied at
`hcl_str` AND the `jsonencode` policy-document sinks. AWS provider *content-schema* rejections
(S3 bucket name > 63 chars, IAM role name charset, non-CIDR `cidr_block`) are the
acceptance-criteria "OR rejected with a clear validation error" branch — NOT a breakout — so
the corpus terraform-validate test isolates the pure HCL-injection surface (generic `locals`
strings) from provider naming/CIDR rules.
