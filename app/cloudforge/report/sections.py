"""Pure per-section Markdown builders for the scenario report.

Each function returns one section's Markdown. The renderer joins them. Keeping the
sections pure makes them independently testable.
"""

from __future__ import annotations

from app.cloudforge import constants
from app.cloudforge.generate.base import ScenarioBundle
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.validate.results import Status, ValidationReport
from app.cloudforge.validate.scanner_score import ScannerScore

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

# Check labels whose FAIL means the ground-truth risk paths are NOT trustworthy —
# the printed chain may be a disconnected/dangling fiction, so the report must not
# present it as an authoritative, confirmed path (clause S15).
_PATH_INTEGRITY_LABELS = frozenset(
    {
        "ground-truth nodes exist",
        "ground-truth edges exist",
        "ground-truth path exists",
        "critical-sink connectivity",
    }
)

_VALIDATION_FAILED_BANNER = (
    "> ⚠ **THIS SCENARIO FAILED VALIDATION** — the risk paths and findings below "
    "may be inaccurate. Do not treat them as a confirmed ground truth until the "
    "failing checks are resolved."
)
_VALIDATION_UNAVAILABLE = (
    "Validation could not be run for this scenario (an artifact may be missing or "
    "unreadable). This report makes **no** claim that the scenario passed validation."
)


def build_banner() -> str:
    return f"> **Local-only.** {constants.LOCAL_ONLY_BANNER}"


def build_validation(report: ValidationReport | None) -> str:
    """Render the validation-outcome section (clause S15).

    ``report`` is ``None`` when validation could not be run (fail-soft): the section
    then says so explicitly rather than letting the report imply success. Otherwise
    it lists every check's PASS/WARN/FAIL and — when any check FAILed — leads with a
    prominent banner so a reader cannot mistake a FAILed scenario for a sound one.
    """
    lines = ["## Validation", ""]
    if report is None:
        lines.append(_VALIDATION_UNAVAILABLE)
        return "\n".join(lines)
    if report.has_failure:
        lines.extend([_VALIDATION_FAILED_BANNER, ""])
    else:
        lines.extend(["> ✅ All validation checks passed (no failures).", ""])
    for outcome in report.outcomes:
        detail = f" — {outcome.detail}" if outcome.detail else ""
        lines.append(f"- **[{outcome.status.value}]** {outcome.label}{detail}")
    return "\n".join(lines)


def path_integrity_failed(report: ValidationReport | None) -> bool:
    """``True`` iff a ground-truth-path integrity check FAILed (clause S15).

    Signals to :func:`build_critical_path` that the printed chain must NOT be
    presented as a confirmed path. ``None`` (validation unavailable) is treated as
    "cannot confirm", so the path is likewise not asserted as authoritative.
    """
    if report is None:
        return True
    return any(
        o.status is Status.FAIL and o.label in _PATH_INTEGRITY_LABELS for o in report.outcomes
    )


def build_title(spec: ScenarioSpec) -> str:
    return f"# Scenario Report — `{spec.scenario_type}`"


def build_summary(spec: ScenarioSpec) -> str:
    profile = spec.company_profile
    return (
        "## Summary\n\n"
        f"- **Cloud:** {spec.cloud}\n"
        f"- **Type:** {spec.scenario_type}\n"
        f"- **Environment:** {spec.environment} ({spec.difficulty})\n"
        f"- **Company:** {profile.type}, {profile.size} — app `{profile.app_name}`\n"
        f"- **Resource budget:** max {spec.constraints.max_resources}"
    )


def build_resources(bundle: ScenarioBundle) -> str:
    lines = ["## Generated Resources", ""]
    for node in bundle.graph.nodes:
        lines.append(
            f"- `{node.id}` — **{node.type.value}** {node.name} ({node.security.criticality})"
        )
    return "\n".join(lines)


def build_findings(bundle: ScenarioBundle) -> str:
    lines = ["## Intended Findings", ""]
    for finding in _by_severity(bundle):
        resources = ", ".join(finding.resource_ids)
        lines.append(
            f"- **[{finding.severity}]** `{finding.family.value}` "
            f"({resources}) — visibility: {finding.expected_scanner_visibility}"
        )
    return "\n".join(lines)


def build_critical_path(bundle: ScenarioBundle, *, integrity_failed: bool = False) -> str:
    """Render the ground-truth risk paths.

    When ``integrity_failed`` is set (a path node/edge/connectivity check FAILed, per
    :func:`path_integrity_failed`), the section is flagged as UNVERIFIED so a printed
    chain is never presented as a confirmed, connected path (clause S15).
    """
    header = "## Ground-Truth Risk Path"
    lines = [header, ""]
    if integrity_failed:
        lines.append(
            "> ⚠ **UNVERIFIED** — validation could not confirm these paths are "
            "connected in the graph. The chain(s) below may be inaccurate."
        )
        lines.append("")
    for path in bundle.ground_truth.paths:
        chain = " → ".join(path.nodes)
        status = " — ⚠ NOT VERIFIED" if integrity_failed else ""
        lines.append(f"### `{path.id}` ({path.severity}){status}\n\n{chain}\n\n{path.explanation}")
    return "\n\n".join(lines)


def build_remediation(bundle: ScenarioBundle) -> str:
    lines = ["## Remediation Order (highest risk first)", ""]
    for idx, finding in enumerate(_by_severity(bundle), start=1):
        lines.append(f"{idx}. **[{finding.severity}]** {finding.remediation}")
    return "\n".join(lines)


def build_scanner_summary(available: bool, detail: str) -> str:
    body = detail if available else "checkov not run locally (tool absent)."
    return f"## Scanner Results\n\n{body}"


def build_opa_summary(available: bool, detail: str) -> str:
    body = detail if available else "OPA not run locally (tool absent)."
    return f"## OPA Policy Results\n\n{body}"


def build_scanner_score(score: ScannerScore | None, not_scored_reason: str | None = None) -> str:
    """Summarize how well the observed scanner covered the expected findings.

    ``not_scored_reason`` (clause S12) lets a caller distinguish "the scanner was
    never run" from "checkov.json existed but was unusable" instead of always
    printing the same generic message for both — a corrupted scanner run must not
    look identical to one that never happened. Any ``score.warnings`` (malformed
    entries skipped, empty-file, etc.) are rendered as explicit caveats, never
    silently dropped.
    """
    if score is None:
        reason = not_scored_reason or "no scanner output"
        return f"## Scanner Score\n\nnot scored — {reason}."
    coverage_pct = f"{score.scanner_coverage_score * 100:.0f}%"
    lines = [
        "## Scanner Score",
        "",
        f"- **Scanner:** {score.scanner}",
        f"- **Expected findings:** {score.expected_findings}",
        f"- **Matched (detected):** {score.matched_findings}",
        f"- **Missed:** {score.missed_findings}",
        f"- **Unexpected (observed false positives):** {score.unexpected_findings}",
        f"- **Coverage score:** {score.scanner_coverage_score} ({coverage_pct})",
        f"- **Match strategy:** {score.match_strategy}",
    ]
    if score.warnings:
        lines.append("- **Caveats:**")
        lines.extend(f"  - {warning}" for warning in score.warnings)
    return "\n".join(lines)


def build_limitations() -> str:
    return (
        "## Limitations\n\n"
        "- Deterministic, rule-based generation (one scenario family).\n"
        "- Terraform is validated statically and **never applied**.\n"
        "- checkov/OPA are optional; absent tools are skipped, not failed.\n"
        "- No LLM/diffusion/cloud engines in this MVP."
    )


def _by_severity(bundle: ScenarioBundle) -> list:  # type: ignore[type-arg]
    return sorted(bundle.findings.findings, key=lambda f: _SEVERITY_ORDER[f.severity])
