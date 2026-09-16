# FXL-63 — Rule catalog YAML adapter — Result

**Status**: Complete — implemented, tested, CI green, NOT merged (per directive).
**PR**: [#82](https://github.com/spivi/forge-x-labs/pull/82) — `feat/FXL-63-rule-catalog-adapter` → `master`
**Commit**: `9af139b` — `feat(FXL-63): rule catalog YAML adapter` (signed-off)
**Ticket closed by this PR**: #63

## What was built

Implemented `RuleCatalogYamlAdapter` in the previously-stubbed
`app/cloudforge/learn/adapters/rule_catalog_yaml.py` (design §8, adapter 2): parses a
LOCAL curated YAML rule catalog (the seed patterns, Tier-4 local registry) into
`RawPatternRecord`s. Does NOT normalize into `RiskPattern` (ticket #66) and does not
build graph fragments — out of scope, correctly left alone.

### Field-mapping approach

Catalog file shape: a top-level `entries:` list; each entry is validated against an
internal `_RuleCatalogEntry` Pydantic model (`extra="allow"`, so unmapped fields pass
through) requiring `id`/`title`/`cloud_provider`/`severity`, with optional
`summary`/`domains`/`affected_resource_types`/`remediation`/`references`.

Mapping to `RawPatternRecord`:
- `source_id` ← `SourceEntry.id` (the registry entry passed to `extract()`, not the
  catalog file).
- `raw_id` ← entry `id`; `title`/`summary` ← as-is.
- `cloud_provider` ← entry `cloud_provider` (validated against the `CloudProvider` enum).
- `resource_types` ← `affected_resource_types`.
- `severity` ← entry `severity` (validated against `Severity`).
- `category` ← `domains[0]` (first domain; the design's `RawPatternRecord.category` is a
  single field but a catalog entry carries a domain list — normalizer/#66 is the seam
  that would map full multi-domain to `RiskPattern.domains` later).
- `remediation`, `references` ← as-is.
- `raw_payload` ← the full parsed entry dict, **coerced** to `dict[str, str | list[str]]`
  (the field's declared type in `pattern_models.py`, not modified here) — bools/`None`/
  other scalars are stringified (`"true"`/`"false"`/`""`) rather than dropped, so no
  catalog data is silently lost even though the raw record's typed shape is narrower than
  YAML's.

### Provenance (complete on every record, no-provenance-impossible)

`adapter_name="rule_catalog_yaml"` / `adapter_version="0.1.0"` (module constants) are
always stamped; `reuse_status` / `allowed_for_training` / `source_license` come from the
`SourceEntry` passed in (so a caller using the real `local-rule-catalog` registry entry
gets `full_reuse` / `true` / `CC0-1.0` automatically — verified by a test that overrides
the `SourceEntry` and confirms provenance follows it, not a hardcoded default).
`extraction_method="yaml_parse"`; `content_hash` is a `sha256` of the catalog file bytes
(stable across repeated calls — tested); `confidence=0.75` (module constant, per design
§8 default). `extracted_at` is an optional keyword parameter defaulting to
`datetime.now(UTC)` **at call time** inside `extract()` — never defaulted at import,
per the ticket's directive — and a test passes an explicit stamp to confirm it flows
through unmodified. `normalizer_version` is stamped `"unset"` (a module constant) since
the normalizer (ticket #66) hasn't run yet; that ticket will overwrite it.

### Error handling

A new `RuleCatalogEntryError(CloudforgeError)` is raised (never a bare crash) for:
missing/unreadable catalog file, malformed YAML (via `load_yaml`, reused per the
ticket's read instructions), a top-level `entries` that isn't a list, a non-mapping list
item, and a schema-invalid entry (`pydantic.ValidationError` caught and re-wrapped with
the offending entry's `id` in the message).

## Test fixtures

`tests/cloudforge/learn/fixtures/`:
- `sample_rule_catalog.yaml` — 4 entries (2 AWS: S3 public-read, IAM PassRole wildcard;
  2 GCP: public GCS bucket, KMS key without rotation), spanning storage/iam/encryption
  domains, one entry exercising a `compensating_controls` value.
- `malformed_rule_catalog_bad_yaml.yaml` — unbalanced brackets (YAML parse failure).
- `malformed_rule_catalog_missing_field.yaml` — valid YAML, entry missing required
  `title`.

Not authored: the real ≥12-entry seed catalog (ticket #14's data), per scope discipline.

## Test count & coverage

**13 unit tests**, all passing, in `tests/cloudforge/learn/test_rule_catalog_yaml_adapter.py`:
- `TestExtract` (7): N-entries → N-records; AWS field mapping (every field checked);
  GCP provider/domain mapping; provenance completeness across all records; content-hash
  stability across repeated calls; provenance following `SourceEntry` overrides
  (license/reuse_status/allowed_for_training); explicit `extracted_at` passthrough.
- `TestErrorHandling` (6): missing file, malformed YAML, missing required field,
  non-mapping entry, non-list `entries`, null-scalar coercion in `raw_payload`.

Coverage: the adapter module itself is **100%** covered
(`--cov=app.cloudforge.learn.adapters.rule_catalog_yaml`, 81/81 lines). Full project
suite: **180 passed, 5 deselected** (`-m 'not stress'`), project coverage **96.85%**
(gate ≥80%).

## Validation

- `ruff check` (0.9.4, pinned per FXL-52) — clean.
- `ruff format --check` — clean.
- `mypy --strict app/` — clean, 57 source files.
- `pytest tests/cloudforge/ -q --no-cov -m 'not stress'` — 180 passed, 5 deselected.
- `pytest tests/cloudforge/ -q -m 'not stress'` (with coverage gate) — 180 passed,
  project coverage 96.85%, `--cov-fail-under=80` satisfied.

## Scope discipline honored

Only touched `adapters/rule_catalog_yaml.py` + its test + 3 fixtures. Did NOT modify
`pattern_models.py`, `base.py`, `registry.py`, or `adapters/__init__.py` (all read-only,
per instructions). Did NOT implement the fetcher, other adapters (`cloudforge_scenario`,
`checkov_policy_index` remain stubs), the normalizer, or the full seed catalog.
`--no-verify` never used.

## CI status

PR #82 — `state=OPEN`, `mergeable=MERGEABLE`, `mergeStateStatus=CLEAN`. All checks green:
`lint-and-type-check` pass (×2), `test` pass (×2) — 4/4 SUCCESS via `gh pr checks --watch`
(2 polling rounds, both clean).

## Blockers

None. PR is open and clean, awaiting human review/merge. **Not merged**, per directive.

## Note on issue #63's title

The GitHub issue #63 title/body text read "cloudforge_scenario adapter", but the task
brief, the design doc §8 row 2, and the existing stub docstring
(`adapters/rule_catalog_yaml.py`, pre-change: "STUB — implemented in ticket #5") all
consistently point to `rule_catalog_yaml` as adapter #63/#5 in the epic's numbering.
Implemented per the brief/design/stub (rule_catalog_yaml), which also matches the file
this ticket's acceptance criteria and scope-discipline section explicitly name. Flagging
for a human to reconcile the issue title if it's simply stale — no code impact either way
since `cloudforge_scenario.py` was left untouched.
