# Corpus Quality Scoring

> **Status: design intent.** The scorer described here lands in ticket **#69** (Implement
> quality scoring). `app/cloudforge/learn/quality.py` is currently a stub that documents
> this design; no scoring logic is implemented yet. This page describes the intended
> behavior so the design is discoverable ahead of implementation — nothing on this page
> should be read as already-running code.

## Where scoring sits in the pipeline

Quality and realism scoring runs after deduplication and before the training-export gate
(see [Learning Corpus](Learning-Corpus) for the full pipeline). `export.py`'s intended
export bar is `quality_score >= 0.70` (see the "export gate" section below) — scoring is
what makes that bar meaningful.

## Deterministic, rubric-based — not learned

Both `quality_score` and `realism_score` are meant to be **deterministic and rubric-based**,
explicitly **not** a learned/ML score. This matters for the epic's own discipline: nothing
in the corpus pipeline should require a model to run in order to build the corpus that
might one day train one.

## Intended quality dimensions

Each dimension scores 0..1 and is weighted into the overall `quality_score`; realism is
scored and reported separately as `realism_score`:

- **Provenance completeness** — are all required `PatternProvenance` fields present? (See
  [Provenance and Licensing](Provenance-and-Licensing).)
- **Fragment richness** — does the `graph_fragment` have at least 2 nodes and at least 1
  edge? More structure scores higher.
- **Findings coverage** — does the pattern have at least one `ExpectedFinding` that
  references the fragment?
- **Control mapping** — does the pattern carry `control_mappings` and/or
  `missing_controls`?
- **Realism** (`realism_score`) — is the resource-type + relationship + severity
  combination plausible? Incoherent combinations (e.g. a severity that doesn't match the
  weakness family, or resource types that don't co-occur in practice) are penalized.
- **Confidence** — the adapter's confidence default, carried through provenance (see
  [Source Adapters](Source-Adapters) for the three shipped adapters' defaults: 0.85 /
  0.75 / 0.55).

## Deduplication (ticket #68) feeds scoring

Deduplication happens before scoring in the pipeline. Two patterns are considered
duplicates when their **deterministic dedup key** matches:

```
key = (
    cloud_provider,
    weakness_family,
    tuple(sorted(affected_resource_types)),
    tuple(sorted(risky_relationships)),
    tuple(sorted(missing_controls)),
    tuple(sorted(compensating_controls)),
)
```

On a collision, the design intent is: keep the pattern with the highest `quality_score`,
merge the dropped duplicates' provenance into the survivor (e.g. a `duplicate_provenances`
list or merged `source_mappings`), and record the dropped IDs on the survivor as
`duplicate_ids`. No fuzzy matching and no embeddings — the same input corpus must always
produce the same survivors. `dedup.py` is currently a stub (ticket #68); this section
describes intended, not implemented, behavior.

## Corpus summary (design §9.4 / planned `summarize` command)

Once scoring exists, the intended `cloudforge learn summarize` command (ticket #73) would
print a coverage summary over the corpus:

- Counts by `cloud_provider`.
- Counts by `domains`.
- Counts by `weakness_family`.
- The `quality_score` distribution across the corpus.

This mirrors the coverage manifest the (planned) training export is also meant to emit —
see below.

## The export gate reads the score (ticket #71, also a stub)

The training-export gate's intended rule (`export.py`, currently a stub) is that a pattern
is written to the training export only if **all** of the following hold:

```
validation_status == valid
AND training_eligible == true
AND safety_classification in {defensive_pattern, benchmark_pattern, training_pattern}
AND provenance.reuse_status allows reuse (full_reuse, attribution, or mappings_only)
AND provenance.allowed_for_training == true
AND quality_score >= 0.70
```

`restricted_source`, `unsafe_operational`, and `unknown` are excluded outright. A planned
`--include-restricted` CLI flag would be able to override the `restricted_source`
exclusion for local analysis only — it can **never** include `unsafe_operational`, and the
export record would note that the flag was used. The export format is intended to be a
versioned JSON/JSONL bundle plus a manifest (counts, provider/domain/family coverage, and
the exact export ruleset applied) — none of this is implemented yet.

## Corpus-level validation (ticket #70, also a stub)

Separately from per-pattern quality scoring, a corpus-level gate is intended to check the
corpus as a whole (mirroring the scenario-side 12-point discipline, `FXL-D003`):

- Every pattern has complete provenance (no provenance, no corpus).
- Every pattern's `graph_fragment` passes fragment validation (ticket #67).
- No two patterns share an `id`.
- No `unsafe_operational` pattern is present (they must have been rejected upstream).
- `safety_classification` and `training_eligible` are internally consistent with
  provenance.
- Enums are in-vocabulary.

## Related pages

- [Learning Corpus](Learning-Corpus) — the full pipeline and the built-vs-stub status
  table.
- [Risk Pattern Ontology](Risk-Pattern-Ontology) — the `quality_score` / `realism_score`
  fields on `RiskPattern`.
- [Provenance and Licensing](Provenance-and-Licensing) — provenance completeness as an
  input to scoring, and the reuse-status vocabulary the export gate reads.
