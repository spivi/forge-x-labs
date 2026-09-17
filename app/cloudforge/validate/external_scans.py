"""Fail-soft runners for the optional external scanners.

Each returns a ``ValidationOutcome``. A missing tool -> WARN + skip. terraform
network/provider issues -> WARN. Real config/syntax errors or policy denials -> FAIL.
"""

from __future__ import annotations

from app.cloudforge.io.loaders import write_text
from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.validate import tool_probe
from app.cloudforge.validate.results import Status, ValidationOutcome

_MISSING_DETAIL = "not found, skipping"


def run_terraform(paths: ScenarioPaths) -> ValidationOutcome:
    if not tool_probe.detect_tool("terraform"):
        return ValidationOutcome(Status.WARN, "terraform validate", _MISSING_DETAIL)
    tf_dir = paths.terraform_dir
    init = tool_probe.run_tool(["terraform", "init", "-backend=false", "-input=false"], cwd=tf_dir)
    if not init.ok:
        status = Status.WARN if init.looks_like_network_issue else Status.FAIL
        return ValidationOutcome(status, "terraform init", init.stderr.strip()[:200])
    result = tool_probe.run_tool(["terraform", "validate", "-no-color"], cwd=tf_dir)
    if result.ok:
        return ValidationOutcome(Status.PASS, "terraform validate")
    status = Status.WARN if result.looks_like_network_issue else Status.FAIL
    return ValidationOutcome(status, "terraform validate", result.stderr.strip()[:200])


def run_checkov(paths: ScenarioPaths) -> ValidationOutcome:
    if not tool_probe.detect_tool("checkov"):
        return ValidationOutcome(Status.WARN, "checkov scan", _MISSING_DETAIL)
    result = tool_probe.run_tool(
        ["checkov", "-d", str(paths.terraform_dir), "--output", "json", "--compact"]
    )
    write_text(paths.checkov_results, result.stdout or "{}")
    # Checkov exits nonzero when it finds issues — expected here. Record, don't fail.
    return ValidationOutcome(Status.PASS, "checkov scan", "results written to scanner_results/")


def run_opa(paths: ScenarioPaths, policy_path: str) -> ValidationOutcome:
    if not tool_probe.detect_tool("opa"):
        return ValidationOutcome(Status.WARN, "opa eval", _MISSING_DETAIL)
    result = tool_probe.run_tool(
        [
            "opa",
            "eval",
            "-i",
            str(paths.graph),
            "-d",
            policy_path,
            "data.cloudforge.deny",
            "--format",
            "json",
        ]
    )
    write_text(paths.opa_results, result.stdout or "{}")
    if not result.ok:
        return ValidationOutcome(Status.WARN, "opa eval", result.stderr.strip()[:200])
    return _interpret_opa(result.stdout)


def _interpret_opa(stdout: str) -> ValidationOutcome:
    import json

    try:
        payload = json.loads(stdout or "{}")
    except json.JSONDecodeError:
        return ValidationOutcome(Status.WARN, "opa eval", "unparseable output")
    expressions = payload.get("result", [])
    denials = [
        v for r in expressions for e in r.get("expressions", []) for v in (e.get("value") or [])
    ]
    if denials:
        return ValidationOutcome(
            Status.FAIL, "opa policy", f"{len(denials)} deny rule(s) triggered"
        )
    return ValidationOutcome(Status.PASS, "opa policy")
