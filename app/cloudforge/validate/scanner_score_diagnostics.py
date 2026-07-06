"""Why ``scanner_score.score_scenario`` returned ``None`` (clause S12 caveats).

``score_scenario`` collapses two very different situations into the same ``None``:
(a) the scanner genuinely never ran (no ``checkov.json`` on disk), and (b)
``checkov.json`` exists but could not be used — invalid JSON, wrong top-level
shape, or the scenario's own ``graph.json``/``expected_findings.json`` failed to
load. A caller that reports both as the same generic "not scored — no scanner
output" message is masking a real problem: a corrupted scanner run looks
identical to one that was never invoked. :func:`not_scored_reason` recovers the
distinguishing detail (never raises) so the orchestrator and the report can
surface it as an explicit caveat instead of silently dropping it.
"""

from __future__ import annotations

import json

from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.validate.scanner_score import score_scenario
from app.cloudforge.validate.scanner_score_loaders import load_expected, load_graph


def not_scored_reason(paths: ScenarioPaths) -> str | None:
    """Why ``score_scenario`` returned ``None``, or ``None`` if it did not.

    Distinguishes the two "not scored" situations a caller must not report
    identically: the scanner was genuinely never run (no ``checkov.json``) versus
    ``checkov.json`` (or the scenario's own artifacts) exists but could not be used.
    Never raises.
    """
    if score_scenario(paths) is not None:
        return None
    if not paths.checkov_results.exists():
        return "no scanner output"
    shape_error = _checkov_shape_error(paths)
    if shape_error is not None:
        return shape_error
    if load_graph(paths) is None:
        return "checkov.json present but graph.json could not be loaded"
    if load_expected(paths) is None:
        return "checkov.json present but expected_findings.json could not be loaded"
    return "checkov.json present but could not be scored"


def _checkov_shape_error(paths: ScenarioPaths) -> str | None:
    """Describe why ``checkov.json`` (known to exist) could not be parsed/shaped.

    Mirrors the same checks ``scanner_score._load_failed_resources`` applies, but
    returns a human-readable reason instead of silently collapsing to ``None``.
    """
    try:
        raw = paths.checkov_results.read_text(encoding="utf-8")
    except OSError as exc:
        return f"checkov.json could not be read ({exc})"
    if not raw.strip():
        return "checkov.json is empty"
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return f"checkov.json is not valid JSON ({exc})"
    if not isinstance(payload, dict):
        return f"checkov.json top level is a {type(payload).__name__}, expected an object"
    results = payload.get("results", {})
    if not isinstance(results, dict):
        return f"checkov.json 'results' is a {type(results).__name__}, expected an object"
    failed = results.get("failed_checks", [])
    if not isinstance(failed, list):
        kind = type(failed).__name__
        return f"checkov.json 'results.failed_checks' is a {kind}, expected a list"
    return None
