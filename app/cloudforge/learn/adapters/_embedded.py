"""Serialization of hand-authored embedded seed artifacts (ticket #98).

A rule-catalog seed entry may embed a hand-authored ``graph_fragment`` (a
``ScenarioGraph``-shaped mapping) and ``expected_findings`` (a list of
``ExpectedFinding``-shaped mappings). Both are validated against the REAL product
models at parse time — a malformed seed fails loudly with a ``CloudforgeError`` —
and serialized into deterministic (sorted-key) JSON strings under the SAME
``raw_payload`` keys the ``cloudforge_scenario`` adapter uses (``"graph"`` /
``"expected_findings"``), so the normalizer REUSES them verbatim
(``learn/_fragment.py``) instead of fabricating anything.

Split out of ``rule_catalog_yaml.py`` to keep that module within the 200-line cap
(rules/general.md).
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.cloudforge.errors import CloudforgeError
from app.cloudforge.models.findings import ExpectedFindings
from app.cloudforge.models.graph import ScenarioGraph

# Seed-entry field names (authored in the YAML).
GRAPH_FRAGMENT_FIELD = "graph_fragment"
EXPECTED_FINDINGS_FIELD = "expected_findings"
EMBEDDED_ENTRY_FIELDS = frozenset({GRAPH_FRAGMENT_FIELD, EXPECTED_FINDINGS_FIELD})

# raw_payload keys — MUST match what the normalizer reuse path reads
# (learn/_fragment.py) and what the cloudforge_scenario adapter emits.
RAW_GRAPH_KEY = "graph"
RAW_FINDINGS_KEY = "expected_findings"


class EmbeddedArtifactError(CloudforgeError):
    """A seed's embedded ``graph_fragment``/``expected_findings`` fails model validation."""


def embedded_payload(raw_entry: dict[str, Any], entry_id: str) -> dict[str, str]:
    """Validate + JSON-encode a seed's embedded artifacts for ``raw_payload``.

    Returns only the keys the entry actually declares — an entry without a
    ``graph_fragment`` still flows through the normalizer's honest
    minimal-fragment fallback. Never mutates ``raw_entry``.
    """
    payload: dict[str, str] = {}
    fragment = raw_entry.get(GRAPH_FRAGMENT_FIELD)
    if fragment is not None:
        payload[RAW_GRAPH_KEY] = _serialize_fragment(fragment, entry_id)
    findings = raw_entry.get(EXPECTED_FINDINGS_FIELD)
    if findings is not None:
        payload[RAW_FINDINGS_KEY] = _serialize_findings(findings, entry_id)
    return payload


def _serialize_fragment(value: object, entry_id: str) -> str:
    """Validate a ``ScenarioGraph``-shaped mapping and dump it as sorted-key JSON."""
    try:
        fragment = ScenarioGraph.model_validate(value)
    except ValidationError as exc:
        raise EmbeddedArtifactError(
            f"seed entry {entry_id!r} has an invalid graph_fragment: {exc}"
        ) from exc
    return json.dumps(fragment.model_dump(mode="json"), sort_keys=True)


def _serialize_findings(value: object, entry_id: str) -> str:
    """Validate an ``ExpectedFinding`` list and dump it as sorted-key JSON.

    Wrapped in the ``ExpectedFindings`` envelope (``{"findings": [...]}``) to match
    the ``cloudforge_scenario`` adapter's ``raw_payload["expected_findings"]`` shape.
    """
    try:
        findings = ExpectedFindings.model_validate({"findings": value})
    except ValidationError as exc:
        raise EmbeddedArtifactError(
            f"seed entry {entry_id!r} has invalid expected_findings: {exc}"
        ) from exc
    return json.dumps(findings.model_dump(mode="json"), sort_keys=True)
