"""The variation harness measures structural diversity of generated scenarios.

This package only reads ``ScenarioBundle`` artifacts produced by
``app.cloudforge.generate``; it never composes graphs itself and has no
write-to-cloud or credentials code path. ``VariationConstraints.no_apply`` and
``no_credentials`` are structural, not toggles (see ``models.py``).
"""

from __future__ import annotations
