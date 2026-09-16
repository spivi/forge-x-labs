# FXL-65 — Checkov policy index adapter (metadata-only) — Result

**Status**: Complete — implemented, tested, CI green, NOT merged (per directive).
**PR**: [#85](https://github.com/spivi/forge-x-labs/pull/85) — `feat/FXL-65-checkov-adapter` → `master`
**Commit**: `ce231e0` — `feat(FXL-65): checkov policy index adapter (metadata-only)` (signed-off)
**Ticket closed by this PR**: #65 (title)

## Issue-numbering discrepancy (flag for human reconciliation)

Confirmed the same title/body swap already flagged independently by the FXL-64 agent
(see `FXL-64-result.md`), extending it to #65: issue **#65**'s title says "Checkov
policy index adapter (metadata-only)" but its **body** is actually the
`PatternNormalizer` spec (§9.1, `normalizer.py`) — unrelated to this ticket. Issue
**#64**'s title says "cloudforge scenario adapter" but its **body** is the Checkov
adapter spec (§3 Tier 1 / §8) matching this PR almost verbatim (confidence 0.55,
training_eligible=false, `benchmark_pattern`, `metadata_only`). So titles/bodies are
scrambled across #63/#64/#65.

I resolved this against **design doc §8 directly** (ground truth, independent of the
tracker): adapter #3 is unambiguously `checkov_policy_index`, confidence 0.55,
training_eligible=false. That is exactly what my orchestrator task spec asked for, so I
built to spec and PR #85 closes #65 (the ticket ID / branch I was assigned), matching
the FXL-64 agent's same resolution approach for its ticket. Recommend a human fix the
#63/#64/#65 title-vs-body scramble in the tracker (likely a batch issue-creation script
bug) so future issue reads aren't misleading; also worth checking whether #65's body
content (currently the normalizer spec) needs its own dedicated ticket if it isn't
already tracked elsewhere as #76's normalizer work.

## What was built

Implemented `CheckovPolicyIndexAdapter` in the previously-stubbed
`app/cloudforge/learn/adapters/checkov_policy_index.py` (design §8, adapter 3):
parses a **recorded fixture HTML** of the Checkov Terraform policy index into
metadata-only `RawPatternRecord`s.

### HTML-parse approach

- **No BeautifulSoup available** (`import bs4` fails in this repo's venv) — used
  stdlib **`html.parser.HTMLParser`** as directed.
- `_PolicyTableParser(HTMLParser)`: a small, deliberately tolerant `<table>` → `<tr>` →
  `<td>`/`<th>` cell-text collector. Nested tags inside a cell (e.g. `<a href=...>` for
  the source-link column) are flattened to their text content only — the href itself is
  never captured as page content, only re-derived as `f"{source.location}#{check_id}"`
  for the `references` field.
- Row → field mapping (fixture column order: check_id, kind, resource_type, title,
  iac_type, severity): `raw_id`/`rule_id` = check id (e.g. `CKV_AWS_20`),
  `resource_types` = `[resource_type]`, `title` = policy title, `cloud_provider`
  derived from the check-id prefix (`CKV_AWS_`→AWS, `CKV_AZURE_`→AZURE, `CKV_GCP_`→GCP,
  `CKV_K8S_`→KUBERNETES, else GENERIC), `severity` normalized to the shared `Severity`
  literal if recognized (else `None` — never fabricated).
- Rows without a `CKV*`-prefixed first cell (e.g. the header row) are dropped.

### Metadata-only / not-training-eligible confirmation

- Every `RawPatternRecord`: `title`, `resource_types`, `rule_id`, `severity`,
  `references` (link back to the public index page anchor) — **no rule body, no Rego,
  no Python check-source, no full policy logic** anywhere in the record or
  `raw_payload` (which is always `{}` for this adapter — nothing beyond the typed
  fields is stashed).
- `PatternProvenance` on every record: `adapter_name="checkov_policy_index"`,
  `adapter_version="1.0.0"`, `reuse_status=ReuseStatus.METADATA_ONLY` (hardcoded by the
  adapter, not merely inherited from the registry entry — so this posture holds even if
  the registry YAML is ever edited), `allowed_for_training=False` (hardcoded,
  same reasoning), `confidence=0.55`, `content_hash` = sha256 of the fixture file's raw
  bytes (stable across repeated calls on the same fixture), `extraction_method
  ="fixture_html_metadata"`, `source_id`/`source_name`/`source_type`/`source_license`
  passed through from the `checkov-terraform-index` `SourceEntry`.
- A dedicated test (`test_no_rule_source_code_leaks_into_any_record`) asserts none of a
  set of rule-source-shaped strings (`def scan_resource_conf`, `CheckResult.FAILED`,
  `class Check(`, `import checkov`) ever appear in any record's text fields, and another
  (`test_raw_payload_never_contains_rule_logic_keys`) asserts `raw_payload` never
  carries a `rule_source`/`source_code`/`logic`/`check_body` key.

### Error handling

- Missing/unreadable fixture file → `CheckovParseError` (a `CloudforgeError` subclass;
  chosen since that's an operator mistake, not a page-shape variation).
- Empty page (no `<table>`) → `[]`, not an error (documented in the adapter docstring
  and `extract()`'s own docstring).
- Malformed/unclosed HTML → `html.parser` degrades gracefully (drops the incomplete
  trailing row); adapter never crashes, returns whatever complete rows it found.

## Fixture HTML

Hand-authored (not fetched from the live site) under
`tests/cloudforge/learn/fixtures/`:
- `checkov_terraform_index_sample.html` — 12 representative rows: AWS S3
  logging/encryption/public-access (`CKV_AWS_18/19/20`), security-group unrestricted
  ingress (`CKV_AWS_24/260`), KMS wildcard principal (`CKV_AWS_33`), RDS public exposure
  (`CKV_AWS_17`), CloudTrail logging/encryption/validation (`CKV_AWS_36/35/67`), plus
  one Azure storage public-access row (`CKV_AZURE_35`) and one GCP storage row
  (`CKV_GCP_62`) — covering every family design §8 calls out.
- `checkov_terraform_index_empty.html` — well-formed page, no policy table (edge case).
- `checkov_terraform_index_malformed.html` — truncated/unclosed markup (robustness case).

## Files changed

- `app/cloudforge/learn/adapters/checkov_policy_index.py` (implemented; was a stub) —
  199 lines
- `tests/cloudforge/learn/adapters/__init__.py` (new package — did not exist yet)
- `tests/cloudforge/learn/adapters/test_checkov_policy_index.py` (new, 13 tests)
- `tests/cloudforge/learn/fixtures/checkov_terraform_index_sample.html` (new)
- `tests/cloudforge/learn/fixtures/checkov_terraform_index_empty.html` (new)
- `tests/cloudforge/learn/fixtures/checkov_terraform_index_malformed.html` (new)

`app/cloudforge/learn/adapters/__init__.py` was **not** touched — no adapter export
exists there yet for any of the three adapters (sibling stubs also unexported), and
tests import `CheckovPolicyIndexAdapter` directly from the submodule, matching the
`test_registry.py` convention of importing directly from its module.

## Test count

**13 tests** in `test_checkov_policy_index.py`:
1. `test_adapter_identity` — `adapter_name`/`adapter_version` stamped
2. `test_extract_returns_one_record_per_table_row` — 12 fixture rows → 12 records
3. `test_records_carry_metadata_fields` — check id, resource type, title, severity,
   cloud provider, reference link
4. `test_azure_and_gcp_rows_map_to_correct_cloud_provider`
5. `test_provenance_is_metadata_only_and_not_training_eligible` — every provenance
   field, every record
6. `test_content_hash_is_stable_for_same_fixture_bytes` — determinism
7. `test_no_rule_source_code_leaks_into_any_record` — governance guardrail
8. `test_raw_payload_never_contains_rule_logic_keys` — governance guardrail
9. `test_empty_html_returns_empty_list` — documented empty-list behavior
10. `test_malformed_html_does_not_crash` — documented tolerant-degrade behavior
11. `test_missing_fixture_file_raises_parse_error` — documented hard-error behavior
12. `test_cloud_provider_for_unrecognized_prefix_falls_back_to_generic` — fallback path
13. `test_every_record_is_a_valid_raw_pattern_record` — round-trips through the real
    pydantic model with no coercion surprises

## Validation

- `ruff check --fix` (`.venv/bin/ruff`, confirmed pinned **0.9.4**): clean
- `ruff format`: clean (2 files unchanged after formatting)
- `mypy --strict app/`: clean (57 source files, 0 issues)
- `pytest tests/cloudforge/ -q --no-cov -m 'not stress'`: **180 passed**, 5 deselected
  (was 179 before this ticket — net +1 test file worth landed cleanly, no regressions)
- Module-scoped coverage: `checkov_policy_index.py` **100%** (90/90 lines)
- Full-suite coverage (repo default `--cov=app --cov-fail-under=80`): **96.65%**
- `isinstance(CheckovPolicyIndexAdapter(), PatternAdapter)` → `True` (protocol
  conformance, structurally checked)
- CI (`gh pr checks 85`): **all green**, 0 failures (checked via `--watch`, then a
  follow-up poll — no pending/failed checks remained)
- PR state: `OPEN`, `MERGEABLE`

## Blockers

None. PR #85 is open, green, mergeable — awaiting human merge decision (per directive,
did not merge). Only outstanding item is the #63/#64/#65 title/body scramble in the
issue tracker, noted above and in the PR description, for a human to reconcile
(consistent with what the parallel FXL-64 agent already flagged for #63/#64).
