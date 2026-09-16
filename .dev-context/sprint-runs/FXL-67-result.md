# FXL-67 — Graph-fragment validation — Result

**Status**: Complete — implemented, tested, CI green, NOT merged (per directive).
**PR**: [#92](https://github.com/spivi/forge-x-labs/pull/92) — `feat/FXL-67-fragment-validation` → `master`
**Commit**: `3871dea` — `feat(FXL-67): graph-fragment validation` (signed-off)
**Ticket closed by this PR**: #67 (title + body both match the fragment-validation spec —
no title/body scramble on this one).

## What was built

Implemented `validate_fragment(pattern: RiskPattern) -> RiskPattern` (plus a helper,
`validation_reasons(pattern) -> list[str]`, for surfacing why a pattern failed) in the
previously-stubbed `app/cloudforge/learn/validate.py` (design §9.2). Deterministic,
does not mutate its input (`model_copy(update=...)` throughout) — returns a new
`RiskPattern` with `validation_status` (and, on a rule-4 failure,
`safety_classification`) set.

### The 4 rules and how each is enforced

1. **Endpoints resolve** — `_dangling_edge_reasons` recomputes the node-id set and
   checks every edge's `from_`/`to` against it, exactly mirroring
   `ScenarioGraph._edges_reference_existing_nodes`. In practice this can never fire
   for a constructed `RiskPattern`, because `ScenarioGraph`'s own `model_validator`
   already rejects dangling edges at construction time — but the ticket explicitly
   asks to "surface it explicitly here," so the check exists as a documented,
   always-passing invariant rather than being silently assumed.
2. **Node/edge types known-or-generic** — `_unknown_type_reasons` checks
   `node.type not in NodeType` / `edge.type not in EdgeType`. Verified by direct
   experiment that Pydantic itself refuses to construct a `GraphNode`/`GraphEdge`
   with a type string outside the enum (`ValidationError: Input should be 'Account',
   'VPC', ... [type=enum]`) — so, like rule 1, this is structurally guaranteed for any
   already-built fragment today. `NodeType.APPLICATION` is the de facto "documented
   generic placeholder" (it's exactly what the normalizer's `_minimal_fragment`
   builder uses for a bare resource-type list with no other signal) — a dedicated
   test confirms a fragment built entirely from `NodeType.APPLICATION` placeholder
   nodes passes.
3. **Findings reference existing resources** — `_missing_finding_resource_reasons`
   diffs each `ExpectedFinding.resource_ids` against the fragment's node-id set
   (mirrors FXL-D003 point 4 exactly, and the `GraphRiskEngine._check_broad_grants_
   documented`-style set-diff pattern from `validate/graph_risk.py`). This is the one
   rule that *can* actually fail in practice (findings are a separate list on
   `RiskPattern`, not structurally tied to the fragment), and the test suite exercises
   both the pass and fail path plus the "no findings at all" trivially-passing case.
4. **No forbidden destructive actions** — `_forbidden_permission_reasons` /
   `_matched_forbidden` / `_actions_of` are a direct, intentional near-duplication of
   `validate/graph_risk.py`'s `_check_forbidden_permissions` / `_matched_forbidden` /
   `_actions_of`: same `fnmatch` scan, same `constants.FORBIDDEN_PERMISSION_PATTERNS`
   import, scanning every node's `attributes["actions"]` (not restricted to
   `IAMPolicy`-typed nodes only, since a fragment's policy content can live on any
   node's attributes). A match both fails validation and forces
   `safety_classification = SafetyClassification.UNSAFE_OPERATIONAL` via the update
   dict passed to `model_copy`. Broad *read* grants (`s3:Get*`, `s3:List*`) are
   confirmed allowed by a dedicated test, matching the generator's risk engine
   (`constants.ALLOWED_BROAD_PATTERNS`) — no `ALLOWED_BROAD_PATTERNS` check is needed
   here since §9.2 doesn't require findings-document-broad-grants for the corpus
   validator (that's the generator's own rule, not restated in the ticket).

`validation_status` is set to `VALID` only when `_failure_reasons` returns empty
(all 4 rule-checkers return no reasons); otherwise `INVALID` with every failing
reason collected (not just the first).

### Reuse (no reinvention)

- `constants.FORBIDDEN_PERMISSION_PATTERNS` imported directly — not redefined.
- The fnmatch-based scan (`_matched_forbidden`, `_actions_of`) is structurally
  identical to `validate/graph_risk.py`'s private helpers of the same name/shape —
  same signature, same fnmatch call, same `node.attributes.get("actions", [])`
  extraction. `graph_risk.py` itself was left untouched (read-only, per scope).
- `NodeType`/`EdgeType` imported from `app.cloudforge.models.graph` — not
  redeclared.
- `pattern_models.py`, `normalizer.py`, `models/graph.py`, `constants.py` were all
  read-only for this ticket, as instructed.

### Module layout (200-line cap)

`app/cloudforge/learn/validate.py` — **138 lines** (was a 14-line stub). All 10
functions are ≤15 lines and take exactly 1 parameter (well under the 30-line/
3-param limits in `rules/general.md`).

## Files changed

- `app/cloudforge/learn/validate.py` (implemented; was a stub) — 138 lines
- `tests/cloudforge/learn/test_validate.py` (new, 21 tests)

No other files were modified — `pattern_models.py`, `normalizer.py`,
`models/graph.py`, `constants.py`, `dedup.py`/`quality.py`/`corpus.py`/`export.py`/
`cli.py` were all left untouched per the ticket's scope discipline.

## Test count

**21 tests** in `test_validate.py`, grouped into 7 classes:

1. `TestEdgeEndpointsResolve` (2) — clean fragment passes; confirms the explicit
   check doesn't false-positive on a normal fragment (dangling edges can't even be
   constructed, per `ScenarioGraph`'s own validator).
2. `TestTypesKnownOrGeneric` (2) — all-known node/edge types pass; a fragment built
   entirely from the `NodeType.APPLICATION` generic placeholder passes.
3. `TestFindingsReferenceExistingResources` (3) — finding referencing a real node
   passes; finding referencing a missing node is invalid (reason names both the
   finding id and the missing resource id); no findings at all trivially passes.
4. `TestNoForbiddenDestructiveActions` (9) — clean read-only actions pass; one
   parametrized-style test per forbidden pattern (`iam:Delete*` via `iam:DeleteRole`,
   `s3:DeleteBucket`, `ec2:TerminateInstances`, `kms:ScheduleKeyDeletion`,
   `organizations:*` via `organizations:LeaveOrganization`); the `iam:Delete*` case
   additionally asserts `safety_classification` flips to `unsafe_operational`; broad
   `s3:Get*`/`s3:List*` grants are confirmed allowed; a forbidden-action-absent case
   confirms `safety_classification` is left untouched on a pass.
5. `TestOverallStatusAndDeterminism` (4) — unvalidated→valid promotion, non-mutation
   of the input pattern, byte-identical determinism across two calls, and a
   multi-rule-failure case (forbidden action + missing finding resource) confirming
   *all* reasons are reported, not just the first.
6. `TestRealNormalizedPatterns` (2) — **integration, no hand-waving**: every seed
   pattern from `data/rule_catalog/seed_patterns.yaml` (via
   `RuleCatalogYamlAdapter` → `PatternNormalizer`) validates as `VALID`; the
   `cloudforge_scenario` adapter's `scenario_ci_cd_iam_chain` fixture (via
   `CloudforgeScenarioAdapter` → `PatternNormalizer`) also validates as `VALID` —
   this is the acceptance criterion "a clean normalized pattern (from a seed or
   scenario) → valid," proven against real data rather than only hand-built fixtures.

## Validation

- `ruff check --fix` (`.venv/bin/ruff`, confirmed pinned **0.9.4**): clean, no
  issues on either touched file.
- `ruff format`: clean (reformatted `test_validate.py`'s spacing/line-wrapping
  cosmetically; no logic change).
- `.venv/bin/mypy --strict app/cloudforge/learn/validate.py`: clean.
- `.venv/bin/mypy --strict app/`: clean, **59 source files**, 0 issues (unchanged
  file count from before this ticket — `validate.py` was already counted as a stub).
- `.venv/bin/pytest tests/cloudforge/ -q --no-cov` (bare, per instructions): **288
  passed**, 9 deselected (stress/internet-marked) — was 267 passing before this
  ticket's 21 new tests (net +21, no regressions).
- Coverage (`--cov=app --cov-report=term-missing -m 'not stress and not internet'`):
  **97.36%** total, well over the 80% floor. `validate.py` itself: **96%** (67
  statements, 3 missed) — the 3 uncovered lines are exactly the rule-1/rule-2
  defensive branches (`_dangling_edge_reasons`'s failure line,
  `_unknown_type_reasons`'s two failure lines) that are structurally unreachable
  because `ScenarioGraph`/`GraphNode`/`GraphEdge` refuse to construct the invalid
  states in the first place — consistent with `graph_risk.py`'s own coverage profile
  (94%, similarly unreachable defensive lines).
- CI (`gh pr checks 92 --watch`, then polled repeatedly `gh pr checks 92`): **all
  green throughout, 0 failures at any point**. Final `gh pr view 92
  --json statusCheckRollup` confirms `lint-and-type-check` (x2) and `test` (x2) all
  `COMPLETED SUCCESS`.
- PR state: `OPEN`, `MERGEABLE`.

## Blockers

None. PR #92 is open, green, mergeable — awaiting human merge decision (per
directive, did not merge). No issue title/body scramble found on #67 (title and body
both correctly describe the fragment-validation spec).
