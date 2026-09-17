"""cloudforge learning-corpus pipeline.

A local-first ETL library that fetches, ingests, normalizes, validates, dedups,
scores, and exports cloud-risk **patterns** from an approved source registry. This
epic is about DATA DISCIPLINE — provenance, governance, safety classification — not
ML. Nothing here trains a model, runs on a GPU, or crawls the internet.

This package is the DATA foundation for a future graph-generation effort; it stops at
a validated, deduped, quality-scored, provenance-complete set of normalized
``RiskPattern`` objects whose ``graph_fragment`` reuses the product's own
``ScenarioGraph`` vocabulary.

See ``docs/plans/2026-07-05-learning-corpus-design.md`` for the full plan.
"""

from __future__ import annotations
