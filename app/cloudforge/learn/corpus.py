"""Corpus load/save + corpus-level validation checks (STUB — implemented in ticket #12).

Corpus-level gate (mirroring the FXL-D003 12-point scenario discipline): every pattern
has complete provenance (**no provenance, no corpus**), every ``graph_fragment`` passes
fragment validation, no two patterns share an ``id``, no ``unsafe_operational`` pattern
is present, ``safety_classification`` / ``training_eligible`` are internally consistent
with provenance, and all enums are in-vocabulary. No corpus logic lives here in the
foundation ticket.

See design §9.5.
"""

from __future__ import annotations

# Implemented in ticket #12 (Implement corpus validation).
