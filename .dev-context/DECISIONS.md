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

## FXL-D006: Duplicate resource labels are rejected pre-emission, scoped per resource TYPE

**Status**: accepted
**Date**: 2026-07-05

**Context**: `identifiers.resource_name` (FXL-39) sanitizes any `node.id` to a Terraform-legal
label (`[^A-Za-z0-9_]` → `_`, leading-char guard). Distinct ids that differ ONLY by an
illegal-char / `-` / `_` swap collapse to the SAME label (`a-b` and `a_b` both → `a_b`).
Terraform then errors on a duplicate resource label (`Duplicate resource "aws_s3_bucket"`),
turning an externally-authored / generatively-authored graph into a `terraform validate` DoS.
The two shipped families have zero collisions today, but the FXL-39 review flagged this as a
follow-up reachable once a generative engine authors graphs.

**Decision**: Detect the collision BEFORE emission and **reject** it with a `GraphIntegrityError`
naming BOTH colliding node ids + the shared label — do NOT silently uniquify (a generator
producing a collision is a generator bug; fail loud). The check is **scoped per emitted
resource TYPE**, not global: Terraform labels only clash within the same `resource "<type>"`
namespace, so `a_b` as an `aws_s3_bucket` label and `a_b` as an `aws_iam_role` label do NOT
collide. Per-type is the *correct* scope (a global over-approximation would raise false
positives on legitimately distinct-type nodes sharing a label) and costs little extra code:
a static `NodeType → resource_type` map mirroring the block assemblers. Node types that emit
no resource (Account / CICDIdentity / Application / DataSet / LogTrail) carry no label and are
skipped. The guard lives in `pipeline/label_collisions.py`, called first in
`TerraformEmitter.emit` (before any file is written). The CLI `generate` command's
`write_all` call was moved INSIDE the existing `except CloudforgeError` block so the error
surfaces as a clean `error: …` exit-1, not a raw traceback.

**Consequences**: A collision fails fast and loud at `generate` time with a diagnosable
message, never as an opaque downstream `terraform validate` duplicate-resource error. The
`NodeType → resource_type` map in `label_collisions.py` must stay in sync with the block
assemblers in `terraform_blocks.py` if a new resource-emitting node type is added.

## FXL-D007: CSA CCM control-ID mappings are training-eligible; control text is not; CIS stays restricted

**Status**: accepted
**Date**: 2026-07-05

**Context**: The FXL-E2 learning corpus can map cloudforge weakness families to external control
frameworks. CSA publishes the Cloud Controls Matrix machine-readably (JSON/YAML/OSCAL); CIS
Benchmark content is more restricted.

**Decision**: For CSA CCM, our-id -> CCM control-ID **mappings** are training-eligible
(`reuse_status: mappings_only`, `allowed_for_training: true`) — the corpus may record which CCM
control a pattern maps to. Copying CCM control **body text** into the corpus or training export
is NOT permitted. CIS Benchmarks stay `metadata_only` / not-training-eligible (section IDs/titles
only; never the benchmark text). A new `mappings_only` reuse_status is added to the registry
vocabulary for this posture.

**Consequences**: FXL-E2 adapters that touch CSA CCM emit `control_mappings` (id references) only,
never control text; a corpus-validation check must reject any CCM-sourced record carrying control
body text. Revisit CIS if reuse rights are later confirmed.

## FXL-D008: OPA coarse-grained, graph engine precise — defense-in-depth via BFS reachability

**Status**: accepted
**Date**: 2026-07-06

**Context**: FXL-79 raised that the family-agnostic OPA check (from FXL-54) verifies a critical-risk
edge and a `stores_sensitive_data` sink **exist** in the graph, but not that they lie on a
**shared reachable path**. A scenario with both on **disconnected components** passes OPA and is
caught only by ground-truth path validation. The gap is intentional coarseness — OPA is a
universal sanity gate (decoupled from family-specific edge types), while per-path reachability is
the Python graph engine's job. But this split wasn't explicit.

**Decision**: Harden the defense-in-depth **in the graph engine, not the OPA**. Added
`_check_critical_path_connectivity()` to `GraphRiskEngine`, which asserts that at least one
critical-risk edge (excluding `stores_sensitive_data` itself) can reach a `stores_sensitive_data`
sink via BFS graph traversal. This is **family-agnostic** (no edge-type hardcoding) and **coarse**
(any path, no attack vector), mirroring the OPA's intent. The check runs after ground-truth path
validation, catching the rare case where a declared path is coherent but the critical edge was
somehow disconnected from all sinks post-generation.

**Consequences**: The OPA stays a coarse existence gate; the engine now has a reachability backstop.
New scenario families automatically benefit (no rego coupling needed). The BFS is O(V + E) and
runs once per validated scenario, negligible cost. The git push will reference issue #79 (Closes).

## FXL-D009: Third scenario family is unblocked after VAR-1 large-run GO

**Status**: accepted
**Date**: 2026-09-16

**Context**: FXL-D004 gated a third family on the 12-point definition being enforceable.
M7, STRESS, VAR-1 composer, the diversity gate, and the 2,000-scenario large run
(0 FAIL, 77 shapes, `--gate` exit 0) make that bar enforceable.

**Decision**: New families may be added. Each must join the composer integrity net
(seeds `{0,1,2,17,99}`, zero FAIL) and emit only resource types the Terraform
emitter already knows, or land with an emitter ticket in the same change.

**Consequences**: `cross_account_trust` is the first new family (IAM/S3 only).

---

## FXL-D010: Student lab pack must not contain the answer key

**Status**: accepted
**Date**: 2026-09-16

**Context**: `cloudforge lab` splits a scenario into student/ and instructor/. The full
graph labels criticality and edge risk, which is the answer key.

**Decision**: Student pack = stripped estate (no `security` on nodes/edges), brief (no
`can_pass_role`, no critical-path node-id chain), Terraform, spec. Findings, ground-truth
paths, report, and grade_key live only under `instructor/`.

**Consequences**: Leak tests are load-bearing. `grade` reads `instructor/grade_key.json` only.

---

