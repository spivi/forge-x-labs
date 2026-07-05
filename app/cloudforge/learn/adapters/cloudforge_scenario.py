"""``cloudforge_scenario`` adapter (STUB — implemented in ticket #6).

Ingests existing ``out/<scenario>`` dirs (``scenario.yaml`` / ``graph.json`` /
``expected_findings.json`` / ``ground_truth_paths.json``) — already validated and
self-consistent — into ``RawPatternRecord``s. Confidence default 0.85; training-eligible
by default (``full_reuse``). No extraction logic lives here in the foundation ticket.

See design §8.
"""

from __future__ import annotations

# Implemented in ticket #6 (Implement cloudforge scenario adapter).
