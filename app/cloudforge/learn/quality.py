"""Deterministic quality + realism scoring (STUB — implemented in ticket #11).

Rubric-based (NOT learned). Dimensions weighted into ``quality_score``: provenance
completeness, fragment richness, findings coverage, control mapping, and carried-through
adapter confidence; ``realism_score`` is scored separately (plausible resource-type +
relationship + severity combination). ``export.py`` uses ``quality_score >= 0.70`` as
the export bar. No scoring logic lives here in the foundation ticket.

See design §9.4.
"""

from __future__ import annotations

# Implemented in ticket #11 (Implement quality scoring).
