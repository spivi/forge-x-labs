# FXL-66 — PatternNormalizer (RawPatternRecord -> RiskPattern) — Result

**Status**: Complete — implemented, tested, CI green, NOT merged (per directive).
**PR**: [#88](https://github.com/spivi/forge-x-labs/pull/88) — `feat/FXL-66-normalizer` → `master`
**Commit**: `68456f4` — `feat(FXL-66): PatternNormalizer (RawPatternRecord -> RiskPattern)` (signed-off)
**Ticket closed by this PR**: #66 (title + body both match the normalizer spec — no
scramble on this one, unlike the #63/#64/#65 title/body swap flagged by prior agents).

## What was built

Implemented `PatternNormalizer` in the previously-stubbed
`app/cloudforge/learn/normalizer.py` (design §9.1): a single public method,
`normalize(raw: RawPatternRecord) -> RiskPattern`, that deterministically maps any of
the three adapters' output onto the `RiskPattern` ontology.

### Mapping approach

- **`id`**: stable slug `f"{slugify(source_id)}-{slugify(raw_id)}"` (lowercase,
  non-alphanumeric runs collapsed to a single `-`). Deterministic and unique per
  source+raw_id — e.g. `checkov-terraform-index-ckv-aws-20`.
- **Direct fields**: `title`, `summary`, `severity` (default `"medium"` if the adapter
  left it `None`), `remediation`, `cloud_provider` (default `GENERIC` if `None`),
  `affected_resource_types` (deduped + sorted), `source_mappings` (`[rule_id]` if
  present, else `[]`) map straight across.
- **`domains` / `weakness_family`** (not present as structured fields on
  `RawPatternRecord` — adapters only carry a loose `category` string): inferred via a
  small deterministic keyword-lookup table in a new `_taxonomy.py` helper —
  `category` is tried first as a literal `Domain` value, then resource-type keywords
  (`s3`/`bucket`→storage, `iam`/`role`→iam, `kms`→encryption, etc.) are OR'd in;
  falls back to `Domain.GOVERNANCE` if nothing matches. `weakness_family` matches
  title/summary/category keywords (`passrole`, `public`/`expos`, `logging`,
  `encrypt`, `security_group`/`ingress`, etc.), falling back to `WeaknessFamily.OTHER`.
  Explicitly rule-based lookup tables, not a classifier — no ML per the guiding
  directive.
- **`graph_fragment`**: two paths. (1) The `cloudforge_scenario` adapter stores the
  full, already-validated scenario graph as JSON under
  `raw_payload["graph"]` — when present, it's parsed back into a real `ScenarioGraph`
  via `model_validate_json` and reused **verbatim** (richer fragment, real edges,
  already passed the model's edge-endpoint validator once at adapter time). (2)
  Otherwise (rule_catalog_yaml, checkov_policy_index — neither carries structured
  relationships), a minimal fragment is built: one generic `Application`-typed node
  per distinct (sorted) resource type, zero edges. An edge-less fragment is
  trivially valid against `ScenarioGraph`'s `_edges_reference_existing_nodes`
  validator (nothing to resolve).
- **`safety_classification`**: derived from `provenance.reuse_status` —
  `metadata_only`/`mappings_only` → `benchmark_pattern`; `restricted`/`unknown` →
  `restricted_source`; everything else (`full_reuse`/`attribution`) →
  `defensive_pattern`. This is **overridden unconditionally** by the unsafe-content
  scan: any hit forces `unsafe_operational` regardless of how permissive the reuse
  posture otherwise is.
- **Unsafe-operational content scan** (new `_safety.py` helper,
  `is_unsafe_content(*fields)`): scans `title`/`summary`/`remediation` for the
  keyword list specified in the ticket — `exploit`, `persistence`, `evasion`,
  `credential-theft`/`credential theft`, `malware`, `payload`,
  `destructive-action`/`destructive action`, plus `backdoor` — case-insensitive
  substring match, and two regexes: a PEM private-key header
  (`-----BEGIN ... PRIVATE KEY-----`) and a `key=value`/`key: value`-shaped
  secret-looking assignment (`aws_secret_access_key`/`api_key`/`password` followed
  by a ≥12-char token). Deliberately conservative/keyword-based per the directive —
  not a trained classifier.
- **Provenance**: copied from `raw.provenance` via `model_copy(update=...)` with only
  `normalizer_version` overwritten to the pinned `NORMALIZER_VERSION = "0.1.0"`
  module constant; every other field (including `confidence`, which flows straight
  into `RiskPattern.confidence`) passes through untouched. **Completeness is
  enforced first**, before any other work: `_assert_provenance_complete` checks 8
  required string fields (`source_id`, `source_name`, `source_url_or_path`,
  `source_license`, `extraction_method`, `content_hash`, `adapter_name`,
  `adapter_version`) are non-blank, raising `NormalizerError` (a `CloudforgeError`
  subclass) naming every blank field if not.
- **`validation_status`**: always set to `ValidationStatus.UNVALIDATED` — ticket #67's
  fragment validator is the only thing that promotes it to `valid`/`invalid`.
- **`training_eligible`**: never touched directly — it stays the existing
  `RiskPattern.computed_field` (verified by a dedicated test that an
  otherwise-training-favorable record still comes back `training_eligible=False`
  purely because `validation_status` is `unvalidated`).
- Fields with no adapter signal at all (`risky_relationships`, `missing_controls`,
  `negative_controls`, `compensating_controls`, `expected_findings`,
  `detection_hints`, `control_mappings`) are left at their empty-list defaults —
  `RawPatternRecord` carries none of these; populating them would mean inventing
  data the adapters never extracted, which the ticket doesn't ask for and later
  tickets (validate/quality/dedup) don't depend on being pre-filled.

### Determinism confirmation

Two dedicated tests confirm `model_dump(mode="json")` is byte-identical across two
independent `normalize()` calls on the same input: one against a hand-built record,
one against a real record produced by the `cloudforge_scenario` adapter (which itself
embeds a `sha256` content hash and a real graph, so this exercises the full path
including JSON round-tripping the embedded fragment). All list fields
(`affected_resource_types`, `domains`, `source_mappings`) are explicitly sorted before
being handed to `RiskPattern`, and dict/set intermediate structures are never left
unsorted at serialization time.

### Module layout (200-line cap)

`normalizer.py` came in at 308 lines on the first working draft (all 41 tests green)
— over the module cap (rules/general.md). Split into three files rather than trim
logic:
- `app/cloudforge/learn/normalizer.py` — **193 lines** — orchestration only
  (`PatternNormalizer.normalize`, id slugification, provenance-completeness check,
  graph-fragment construction, the reuse_status→classification switch).
- `app/cloudforge/learn/_taxonomy.py` — **96 lines** (new) — the domain/
  weakness-family keyword tables + `infer_domains`/`infer_weakness_family`.
- `app/cloudforge/learn/_safety.py` — **46 lines** (new) — the unsafe-content scan,
  `is_unsafe_content`.

All three modules end up at 100% branch coverage in the full suite run.

## Files changed

- `app/cloudforge/learn/normalizer.py` (implemented; was a stub) — 193 lines
- `app/cloudforge/learn/_taxonomy.py` (new helper module) — 96 lines
- `app/cloudforge/learn/_safety.py` (new helper module) — 46 lines
- `tests/cloudforge/learn/test_normalizer.py` (new, 41 tests)

No adapter, `pattern_models.py`, `adapters/__init__.py`, or `validate.py` files were
touched — read-only per the ticket's scope discipline. `data/source_registry.yaml`
and the test fixtures under `tests/cloudforge/learn/fixtures/` were also read-only
(reused as-is: `sample_rule_catalog.yaml`, `checkov_terraform_index_sample.html`,
`scenario_ci_cd_iam_chain/`).

## Test count

**41 tests** in `test_normalizer.py`, grouped into 9 classes:

1. `TestFieldMapping` (9) — core field pass-through, id slugification (plain +
   non-alnum raw_id), list-field sorting, `source_mappings`/rule_id, `None`
   cloud_provider/severity defaults, confidence carry-through.
2. `TestDomainAndWeaknessInference` (5) — category-as-domain, resource-type keyword
   inference, governance fallback, weakness-family `other` fallback, title-keyword
   inference.
3. `TestGraphFragment` (3) — minimal fragment from resource types, empty-but-valid
   fragment, real-graph reuse from `cloudforge_scenario`'s `raw_payload`.
4. `TestValidationStatusAndVersioning` (3) — always-unvalidated, pinned
   `normalizer_version`, `training_eligible` stays derived (not settable).
5. `TestSafetyClassification` (9) — the full reuse_status→classification mapping
   (metadata_only, restricted, unknown, full_reuse, mappings_only), 3 parametrized
   unsafe-keyword trigger cases (title/summary/remediation), a private-key trigger
   case, and a benign-content non-trigger case.
6. `TestProvenanceCompleteness` (4) — incomplete provenance raises, blank
   content_hash raises, complete provenance doesn't raise, full field-stamping check.
7. `TestDeterminism` (2) — same-record-twice byte-identical dump, real-adapter-record
   byte-identical dump.
8. `TestAllThreeAdapters` (6) — one exercise-and-normalize test per adapter
   (`cloudforge_scenario`, `rule_catalog_yaml`, `checkov_policy_index`) plus two
   "normalize every record from this adapter without error + unique ids" tests
   covering the full fixture set (12 checkov rows, 4 rule-catalog entries).

## Adapters tested against

All three, using existing fixtures (no new fixtures needed, no hand-waving):

- **`cloudforge_scenario`** — `CloudforgeScenarioAdapter().extract(...)` against
  `tests/cloudforge/learn/fixtures/scenario_ci_cd_iam_chain/` → normalized; confirms
  the embedded-graph-reuse path (fragment has >2 nodes, >1 edge, and the real node id
  `cicd-github` survives the JSON round-trip).
- **`rule_catalog_yaml`** — `RuleCatalogYamlAdapter().extract(...)` against
  `tests/cloudforge/learn/fixtures/sample_rule_catalog.yaml` (4 entries: 2 AWS + 2
  GCP) → all 4 normalize without error, unique ids, sorted resource types.
- **`checkov_policy_index`** — `CheckovPolicyIndexAdapter().extract(...)` against
  `tests/cloudforge/learn/fixtures/checkov_terraform_index_sample.html` (12 rows,
  loaded via the real `checkov-terraform-index` `SourceEntry` from
  `data/source_registry.yaml`) → all 12 normalize without error, unique ids,
  `benchmark_pattern` classification, `training_eligible=False` (metadata_only
  reuse_status correctly keeps it ineligible even post-normalization).

## Validation

- `ruff check --fix` (`.venv/bin/ruff`, confirmed pinned **0.9.4**): clean (1
  auto-fixable import-order issue in the first pass, fixed; 1 `SIM105` in
  `_taxonomy.py` fixed by hand with `contextlib.suppress`)
- `ruff format`: clean
- `mypy --strict app/`: clean (**59 source files**, 0 issues — was 57 before this
  ticket's 2 new modules)
- `PYTHONPATH=. pytest tests/cloudforge/ -q --no-cov -m 'not stress'`: **254 passed**,
  1 skipped, 5 deselected (was 213 before this ticket's 41 new tests — net +41, no
  regressions)
- Module-scoped coverage: `normalizer.py` **100%** (56/56), `_safety.py` **100%**
  (13/13), `_taxonomy.py` **100%** (30/30)
- Full-suite coverage (repo default `--cov=app --cov-fail-under=80`): **97.43%**
- `pre-commit run --files <touched files>`: ruff, ruff-format, mypy, and the
  branch-protection hook all pass
- CI (`gh pr checks 88 --watch`): **all green**, 0 failures (`lint-and-type-check` x2,
  `test` x2, plus additional checks — polled until pending cleared, no failures at
  any point)
- PR state: `OPEN`, `MERGEABLE`

## Blockers

None. PR #88 is open, green, mergeable — awaiting human merge decision (per
directive, did not merge). No issue title/body scramble found on #66 (title and body
both correctly describe the `PatternNormalizer` spec, unlike the #63/#64/#65 swap
flagged by prior agents) — no tracker discrepancy to report this time.
