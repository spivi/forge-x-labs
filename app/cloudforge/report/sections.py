"""Pure per-section Markdown builders for the scenario report.

Each function returns one section's Markdown. The renderer joins them. Keeping the
sections pure makes them independently testable.
"""

from __future__ import annotations

from app.cloudforge import constants
from app.cloudforge.generate.base import ScenarioBundle
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.validate.scanner_score import ScannerScore

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def build_banner() -> str:
    return f"> **Local-only.** {constants.LOCAL_ONLY_BANNER}"


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


def build_critical_path(bundle: ScenarioBundle) -> str:
    lines = ["## Ground-Truth Risk Path", ""]
    for path in bundle.ground_truth.paths:
        chain = " → ".join(path.nodes)
        lines.append(f"### `{path.id}` ({path.severity})\n\n{chain}\n\n{path.explanation}")
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


def build_scanner_score(score: ScannerScore | None) -> str:
    """Summarize how well the observed scanner covered the expected findings."""
    if score is None:
        return "## Scanner Score\n\nnot scored — no scanner output."
    coverage_pct = f"{score.scanner_coverage_score * 100:.0f}%"
    return (
        "## Scanner Score\n\n"
        f"- **Scanner:** {score.scanner}\n"
        f"- **Expected findings:** {score.expected_findings}\n"
        f"- **Matched (detected):** {score.matched_findings}\n"
        f"- **Missed:** {score.missed_findings}\n"
        f"- **Unexpected (observed false positives):** {score.unexpected_findings}\n"
        f"- **Coverage score:** {score.scanner_coverage_score} ({coverage_pct})"
    )


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
