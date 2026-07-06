"""Fail-soft loaders for the scenario's own artifacts (graph, expected findings).

Shared by :mod:`app.cloudforge.validate.scanner_score` (the scorer) and
:mod:`app.cloudforge.validate.scanner_score_diagnostics` (the "why wasn't this
scored" helper) so both agree on exactly what counts as loadable.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.models.findings import ExpectedFindings
from app.cloudforge.models.graph import ScenarioGraph


def load_graph(paths: ScenarioPaths) -> ScenarioGraph | None:
    data = safe_read_json(paths.graph)
    if data is None:
        return None
    try:
        return ScenarioGraph.model_validate(data)
    except ValueError:
        return None


def load_expected(paths: ScenarioPaths) -> ExpectedFindings | None:
    data = safe_read_json(paths.expected_findings)
    if data is None:
        return None
    try:
        return ExpectedFindings.model_validate(data)
    except ValueError:
        return None


def safe_read_json(path: Path) -> object | None:
    """Read + parse a JSON file, or ``None`` on any read/parse error (fail-soft)."""
    try:
        parsed: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return parsed
