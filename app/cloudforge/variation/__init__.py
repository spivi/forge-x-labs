"""The variation harness — measures structural diversity of generated scenarios.

See ``docs/superpowers/specs/2026-07-06-FXL-VAR-1-variation-validation-design.md``
§4.2/§5 for the contract. This package only reads ``ScenarioBundle`` artifacts
produced by ``app.cloudforge.generate``; it never composes graphs itself and has
no write-to-cloud/credentials code path (``VariationConstraints.no_apply`` /
``no_credentials`` are structural, not toggles — see ``models.py``).
"""

from __future__ import annotations
