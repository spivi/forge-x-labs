"""Deterministic corpus dedup (STUB — implemented in ticket #10).

Two patterns are duplicates iff their deterministic dedup key matches (cloud_provider,
weakness_family, sorted resource types / relationships / missing_controls /
compensating_controls). On a collision: keep the highest ``quality_score``, merge the
dropped patterns' provenance into the survivor, and record the dropped ``duplicate_ids``.
Same input corpus -> same survivors. No fuzzy matching, no embeddings (that would be
ML). No dedup logic lives here in the foundation ticket.

See design §9.3.
"""

from __future__ import annotations

# Implemented in ticket #10 (Implement deterministic dedup).
