# Future Diffusion Training

> **No model is trained in this epic.** FXL-E2 stops at the DATA. This page documents how
> the learning corpus *prepares* a possible future graph-diffusion effort — it does not
> build one, and nothing described as "future" below exists in this repo today.

## The one-line boundary

FXL-E2 (the learning corpus) produces a validated, deduped, quality-scored,
provenance-complete set of normalized `RiskPattern`s. It does **not** produce a model. That
line is deliberate and absolute for this epic:

- **No embeddings.**
- **No tokenizer.**
- **No GNN (graph neural network).**
- **No diffusion model.**
- **No training loop.**
- **No GPU.**
- **No Modal.**

The planned `cloudforge learn export-training` command (ticket #71, currently a stub)
writes a **dataset** — a versioned JSON/JSONL bundle plus a coverage manifest — not a
model, not a checkpoint, not a set of weights.

## What the corpus provides

Once the full pipeline is built (see [Learning Corpus](Learning-Corpus) for what's built
vs. still a stub), the training-ready export would be:

- A set of normalized `RiskPattern`s (see [Risk Pattern Ontology](Risk-Pattern-Ontology))
  whose `graph_fragment`s are already `ScenarioGraph`s — the product's own graph
  vocabulary (see [Graph Model](Graph-Model)), not a bespoke or ad-hoc format.
- Each fragment paired with its own ground truth: `expected_findings`, severity,
  `missing_controls` / `negative_controls` / `compensating_controls`.
- Full provenance and a `quality_score` on every pattern, so a downstream consumer can
  filter or weight by data quality rather than treating the corpus as uniformly
  trustworthy (see [Corpus Quality Scoring](Corpus-Quality-Scoring)).
- Only training-eligible material — the export gate excludes anything
  `restricted`/`metadata_only`/`unknown`/`unsafe_operational` per
  [Provenance and Licensing](Provenance-and-Licensing).

In short: training-ready **graphs**, with ground truth and labels, in a format a future
consumer would not need to reverse-engineer.

## The seam: where a future engine would plug in

The product's [Roadmap](Roadmap) and
[Modal & Diffusion Future Integration](Modal-and-Diffusion-Future-Integration) pages
already document a possible future `DiffusionGraphGenerator` as one of several engines
behind the existing `ScenarioGenerator` protocol:

```python
class ScenarioGenerator(Protocol):
    def generate(self, spec: ScenarioSpec) -> ScenarioBundle: ...
```

The intended seam is:

1. A future `DiffusionGraphGenerator` would **consume** the learning corpus's training
   export (once it exists) as its training data.
2. It would **emit** candidate `ScenarioGraph`s — proposals, not final artifacts.
3. Those candidate graphs would go straight back through the **existing local
   validators** — the same risk engine (and, where available, checkov/OPA) that validates
   every `TemplateGenerator`/`MutationGenerator` output today (see
   [Validation Pipeline](Validation-Pipeline)).

Nothing about this seam is implemented as part of FXL-E2. It is documented here so the
boundary between "data discipline" (this epic) and "generation" (a hypothetical future
epic) stays explicit, and so the corpus work cannot quietly drift into ML work without a
deliberate, separately-scoped decision.

## Invariant preserved: validators outrank generation, always

This mirrors the product's existing, already-accepted stance
(**FXL-D002**: validators over generation cleverness) exactly as it applies to
`TemplateGenerator` and `MutationGenerator` today: a generated graph is only trustworthy
once the risk engine confirms it. A future diffusion engine does not get a pass on this —
the corpus can make better *proposals* possible, but it never outranks validation. If a
future diffusion effort is ever undertaken, this invariant is expected to hold unchanged.

## Why this page exists

Per the design doc for this epic, this page exists specifically so the "prepares future
diffusion without implementing it" boundary is written down, not just implied. If a future
ticket or epic proposes building `DiffusionGraphGenerator`, embeddings, a GNN, or any
training loop, that is new, separately-scoped work — not a continuation of FXL-E2.

## Related pages

- [Learning Corpus](Learning-Corpus) — the pipeline whose export this page describes the
  eventual consumer of.
- [Risk Pattern Ontology](Risk-Pattern-Ontology) — what a `RiskPattern`'s `graph_fragment`
  actually is.
- [Corpus Quality Scoring](Corpus-Quality-Scoring) — the (planned) quality signal a future
  consumer could use to filter training data.
- [Modal & Diffusion Future Integration](Modal-and-Diffusion-Future-Integration) — the
  generation-side documentation this page complements from the data side.
- [Safety & Scope](Safety-and-Scope) — the product-wide defensive-only, local-first
  posture this epic inherits.
