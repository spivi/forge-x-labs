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

