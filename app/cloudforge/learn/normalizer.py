"""PatternNormalizer: ``RawPatternRecord`` -> ``RiskPattern`` (STUB — ticket #8).

Maps adapter-specific fields onto the ontology (design §6), builds/verifies the
``graph_fragment`` as a real ``ScenarioGraph``, assigns ``safety_classification`` from
the source's ``reuse_status`` plus a content scan, stamps provenance completely, and
pins ``normalizer_version``. Sets ``validation_status = unvalidated`` (the validator
promotes it). No normalization logic lives here in the foundation ticket.

See design §9.1.
"""

from __future__ import annotations

# Implemented in ticket #8 (Implement PatternNormalizer).
