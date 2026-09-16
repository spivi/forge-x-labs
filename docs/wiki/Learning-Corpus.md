# Learning Corpus

`cloudforge learn` is a **data** pipeline. It fetches, ingests, validates, and
exports cloud-risk patterns from an allow-listed set of sources. It does **not**
train a model.

See [Future Diffusion Training](Future-Diffusion-Training.md) for the boundary.

## Pipeline

```
approved sources only (see Source Registry)
        |
        v fetch          data/raw/<source_id>/<content_hash> + metadata.json
        v adapter        RawPatternRecord
        v normalize      RiskPattern (ontology + graph_fragment + provenance)
        v validate       endpoints resolve, types known, no forbidden actions
        v dedup          deterministic key; keep best provenance
        v score          rubric quality + realism (not a learned model)
        v export         training-eligible, safe, reuse-allowed patterns
```

Code lives under `app/cloudforge/learn/`. Commands:

```bash
cloudforge learn fetch-sources
cloudforge learn ingest --adapter <name>
cloudforge learn validate-corpus
cloudforge learn summarize
cloudforge learn export-training
```

## Related pages

- [Source Registry](Source-Registry.md)
- [Source Adapters](Source-Adapters.md)
- [Risk Pattern Ontology](Risk-Pattern-Ontology.md)
- [Provenance and Licensing](Provenance-and-Licensing.md)
- [Corpus Quality Scoring](Corpus-Quality-Scoring.md)
