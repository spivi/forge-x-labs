"""Source adapters — turn a cached raw source into ``RawPatternRecord``s.

Adapters live in a sub-package because they will grow (Trivy, Prowler, provider
guidance) without bloating ``learn/``. Only the ``PatternAdapter`` protocol
(``base.py``) is implemented in the foundation ticket; the concrete adapters
(``cloudforge_scenario``, ``rule_catalog_yaml``, ``checkov_policy_index``) land in
later tickets #5/#6/#7.
"""

from __future__ import annotations
