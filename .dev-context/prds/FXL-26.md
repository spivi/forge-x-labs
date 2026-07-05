# FXL-26 — Second scenario family: `public_data_exposure`

**Status**: Draft
**Priority**: P2
**Type**: feature
**Effort**: M (3–5 files)
**Milestone**: M1 — Scenario graph and first generator (family extension)

## Problem / Motivation

Benchmarking needs more than one risk *shape*. `ci_cd_iam_chain` models a privilege-chain
risk; a second family that models **direct data exposure** exercises different scanner
capabilities (public-access blocks, bucket policies, unencrypted data, missing logging)
and different ground-truth path structure. This proves the pipeline is genuinely
family-agnostic (the extension seam works) and doubles the benchmark corpus.

## Goals

- A new `public_data_exposure` family: a public-read S3 bucket holding sensitive data,
  reachable from the internet, with **no** compensating control — plus a properly-locked
  sibling bucket as the false-positive/near-miss.
- Registered in `template_generator._BUILDERS`; the pipeline, validators, and report need
  **zero** changes (proves the seam).
- Its own `examples/public_data_exposure.yaml`, self-consistent graph + ground-truth path
  + expected findings.

## Non-Goals

- No new node/edge types unless strictly required (reuse the existing model).
- No mutation logic (that's FXL-14).

## Approach

- New module `app/cloudforge/generate/public_data_exposure.py` mirroring the structure of
  `ci_cd_iam_chain.py` (small `build_graph` / `build_ground_truth` / `build_findings`).
- Critical path: `internet → exposed public bucket → sensitive dataset` (using
  `exposed_to_internet`, `stores_sensitive_data`). Findings across families:
  `s3_public_exposure` (new, if needed) or reuse existing families
  (`security_group_overexposed` analog for buckets), `s3_logging_missing`, and the
  `public_looking_bucket_with_compensating_control` false-positive.
- Register the builder; add the example YAML.

## Acceptance Criteria

- [ ] `cloudforge generate examples/public_data_exposure.yaml --out out/pde` produces the
      full artifact tree.
- [ ] `cloudforge validate out/pde` is all-PASS (schema, ground-truth path reachable, no
      forbidden perms, broad grants documented) with checkov/opa fail-soft.
- [ ] The report renders with the critical path + findings + banner.
- [ ] `TemplateGenerator` dispatches `public_data_exposure`; `ci_cd_iam_chain` is unchanged.
- [ ] `ruff` + `mypy --strict` clean; coverage on `app` ≥80%.

## Affected Files

- `app/cloudforge/generate/public_data_exposure.py` (new)
- `app/cloudforge/generate/template_generator.py` (register builder)
- `app/cloudforge/models/findings.py` (add a family only if a new one is genuinely needed)
- `examples/public_data_exposure.yaml` (new)
- `tests/cloudforge/test_public_data_exposure.py` (new)

## Threat Model (advisory)

Local offline generator — no external attack surface. Output-integrity risks only: the new
family must still refuse destructive permissions (risk engine covers it) and must not emit
real bucket names/account ids (dummy `000000000000`, fake bucket names). The scenario
*models* public exposure but never *creates* it (never applied). **Residual risk: low.**

## Dependencies

- Depends on the shipped generator seam. Independent of FXL-14 (can run in parallel).
