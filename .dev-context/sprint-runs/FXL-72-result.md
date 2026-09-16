# FXL-72 — Seed rule catalog (>=12 patterns) — Result

**Status**: Complete — authored, tested, CI green, NOT merged (per directive).
**PR**: [#86](https://github.com/spivi/forge-x-labs/pull/86) — `feat/FXL-72-seed-catalog` → `master`
**Commit**: `26751b4` — `feat(FXL-72): add seed rule catalog (14 defensive patterns)` (signed-off)
**Ticket closed by this PR**: #72

## What was built

Authored `data/rule_catalog/seed_patterns.yaml` — the Tier-4 local rule catalog that
`data/source_registry.yaml`'s `local-rule-catalog` entry points at (path confirmed by
reading the registry directly) and that the already-merged `rule_catalog_yaml` adapter
(ticket #63) parses. Shape matches the adapter's `_RuleCatalogEntry` schema and the
existing test fixture (`tests/cloudforge/learn/fixtures/sample_rule_catalog.yaml`)
exactly: a top-level `entries:` list, each entry carrying `id`, `title`, `summary`,
`cloud_provider`, `domains`, `weakness_family`, `severity`, `affected_resource_types`,
`risky_relationships`, `missing_controls`, `negative_controls`,
`compensating_controls`, `remediation`, `references`, `license`, `reuse_status`,
`allowed_for_training`.

Added `tests/cloudforge/learn/test_seed_catalog.py` — no app code touched (adapter,
normalizer, models, registry all left read-only, per scope discipline).

## Seed count & coverage

**14 entries** (12 required + 2 extra for domain breadth):

| Provider | Count | Entries |
|---|---|---|
| AWS | 8 | S3 missing access logging · S3 public read w/o compensating control · IAM broad S3 read over sensitive bucket · IAM PassRole chain to sensitive runtime role · security group SSH open to internet · security group admin web UI open to internet · KMS key policy wildcard principal · CloudTrail logging missing · CI/CD long-lived static cloud credentials |
| Azure | 2 | Storage account public blob access · Key Vault public network access |
| GCP | 4 | GCS bucket public IAM member · service account overprivileged project role · Secret Manager secret overly broad IAM access |

(counts overlap slightly above because AWS also carries the CI/CD entry — full
per-provider tally: AWS 8, Azure 2, GCP 4 = 14 total.)

**Domain coverage** — every required domain from the ticket is represented at least
once via each entry's `domains:` list: `iam`, `storage`, `network`, `logging`,
`encryption`, `ci_cd`, `secrets`, `data` (plus `compute` and `governance` incidentally,
since a couple of entries span more than one domain).

## Adapter parse verification

Ran the **real, merged** `RuleCatalogYamlAdapter` against the **real** catalog file
(loaded via `registry.load_registry("data/source_registry.yaml")` +
`registry.get_entry(..., "local-rule-catalog")` — no hand-rolled `SourceEntry`, no
fixture) inside `test_seed_catalog.py`:

- `len(records) >= 12` → **14 `RawPatternRecord`s produced**, all unique `raw_id`s.
- Every record's `provenance` is complete: `source_id="local-rule-catalog"`,
  `adapter_name="rule_catalog_yaml"`, `source_license="CC0-1.0"`,
  `reuse_status=full_reuse`, `allowed_for_training=True`, non-empty `content_hash`,
  `confidence=0.75`.
- Every record has non-empty `title`/`summary`/`cloud_provider`/`resource_types`/
  `severity`/`category`/`remediation`/`references`.
- Every record's `raw_payload` carries the full required field set (all 17 listed
  fields), with `license`/`reuse_status`/`allowed_for_training` stringified correctly
  by the adapter's scalar coercion.
- Provider mix assertion: `{aws, azure, gcp}` exactly, with AWS ≥3, Azure ≥1, GCP ≥1.
- Domain coverage assertion: all 8 required domains present across the raw YAML.
- Registry wiring assertion: `local-rule-catalog.path ==
  "data/rule_catalog/seed_patterns.yaml"`, `adapter == "rule_catalog_yaml"`,
  `enabled == True`.

## Safety confirmation

Three dedicated safety tests scan the catalog's raw text:
- **No unsafe-operational keywords** — checked against a list including `exploit`,
  `payload`, `reverse shell`, `backdoor`, `persistence technique`, `lateral movement`,
  `metasploit`, `nmap`, `sqlmap`, etc. (Caught and fixed one incidental hit — a
  header *comment* using the word "exploit" while describing the safety constraint
  itself, not entry content — reworded to avoid the keyword entirely.)
- **No real-secret-shaped values** — regexes for AWS access-key-ID shape (`AKIA...`)
  and PEM private-key headers; no matches.
- **No live-looking account IDs** — any bare 12-digit number in the file must equal
  the project's `DUMMY_ACCOUNT_ID` (`"000000000000"`, from `app.cloudforge.constants`);
  none appear at all (no entry needed an account-id example).
- Governance fields verified on every raw entry: `license: CC0-1.0`,
  `reuse_status: full_reuse`, `allowed_for_training: true`.

All entries are strictly descriptive of the misconfiguration + its fix (e.g. "enable
Block Public Access," "scope iam:PassRole to specific ARNs," "restrict SSH ingress to
known CIDRs") — no exploitation steps, no persistence/evasion technique, nothing
operational.

## Validation

- `ruff check --fix` (scoped to the new test file; the YAML data file is not a ruff
  target) — clean.
- `ruff format` — clean (test file formatted).
- `mypy --strict app/` — `Success: no issues found in 57 source files` (no app code
  changed by this ticket, ran per instructions anyway).
- `PYTHONPATH=. .venv/bin/pytest tests/cloudforge/learn/test_seed_catalog.py -q --no-cov`
  — **13 passed**.
- `PYTHONPATH=. .venv/bin/pytest tests/cloudforge/ -q --no-cov -m 'not stress'` — **226
  passed, 1 skipped, 5 deselected** (full suite, no regressions).

One near-miss during validation: an initial `ruff check --fix .` run (over the whole
repo, exploring whether repo-wide ruff was clean) auto-fixed an unrelated
`datetime.timezone.utc` → `dt.UTC` line in
`.claude/skills/dependency-guard/scripts/vet_dependency.py`. That file is out of this
ticket's scope, so the change was reverted with `git checkout --` before committing;
final diff is exactly the two new files.

## Scope discipline honored

Only added `data/rule_catalog/seed_patterns.yaml` and
`tests/cloudforge/learn/test_seed_catalog.py`. Did not modify the adapter
(`rule_catalog_yaml.py`), `pattern_models.py`, `source_models.py`, `registry.py`, or
`data/source_registry.yaml` (all read-only per instructions — registry already pointed
at the correct path). `--no-verify` never used.

## CI status

PR #86 — `state=OPEN`, `mergeable=MERGEABLE`, `mergeStateStatus=CLEAN`. All checks
green: `lint-and-type-check` pass (×2), `test` pass (×2) — 4/4 SUCCESS via
`gh pr checks --watch`.

## Blockers

None. PR is open and clean, awaiting human review/merge. **Not merged**, per directive.
