# Corpus Quality Scoring

Quality and realism scores are **deterministic and rubric-based**. They are
not a learned model. Scoring runs after dedup and before the training-export
gate. The export bar is `quality_score >= 0.70`.

## Dimensions (each 0..1)

- **Provenance completeness**: required `PatternProvenance` fields present.
- **Fragment richness**: at least 2 nodes and 1 edge. More structure scores higher.
- **Findings coverage**: at least one `ExpectedFinding` that references the fragment.
- **Control mapping**: `control_mappings` and/or `missing_controls`.
- **Realism** (`realism_score`): resource type + relationship + severity look
  like they belong together.
- **Confidence**: adapter default, carried through provenance.

See [Learning Corpus](Learning-Corpus.md) for where this sits in the pipeline.
