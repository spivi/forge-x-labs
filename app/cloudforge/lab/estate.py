"""Offline HTML view of a stripped estate (no CDN, no answer-key labels)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.cloudforge import __version__
from app.cloudforge.generate.fragments.base import core_meta, core_scenario_types

_TEMPLATE_PATH = Path(__file__).parent / "estate_template.html"

# Findings shared across families, or not owned by any single one (a chain's
# supporting finding, not its critical one). These are not part of any core
# fragment's declared surface, so they stay a hand-maintained list.
_SHARED_FINDINGS: tuple[dict[str, str], ...] = (
    {
        "id": "iam_excessive_privilege",
        "label": "IAM: Overly Broad Permissions (s3:Get*/List*)",
        "cloud": "aws",
    },
    {
        "id": "s3_logging_missing",
        "label": "Governance: S3 Server Access Logging Missing",
        "cloud": "aws",
    },
    {
        "id": "security_group_overexposed",
        "label": "Network: Security Group Ingress 0.0.0.0/0",
        "cloud": "aws",
    },
    {
        "id": "public_looking_bucket_with_compensating_control",
        "label": "Benign/Decoy: Public-Looking Bucket with Control",
        "cloud": "aws",
    },
)


def _core_findings() -> tuple[dict[str, str], ...]:
    """One row per registered core family, derived from its ``checklist`` and
    ``cloud`` class attributes (``fragments/base.py``) instead of hand-copied here."""
    rows = []
    for scenario_type in core_scenario_types():
        meta = core_meta(scenario_type)
        finding_id, label = meta.checklist
        rows.append({"id": finding_id, "label": label, "cloud": meta.cloud})
    return tuple(rows)


# The full finding catalog the workbench checklist offers, one entry per row the
# template's own fallback list carries. ``cloud`` says which vendor's estate the
# entry belongs to; render_estate_html filters this down to the vendors the
# estate actually contains before embedding it, so an Azure lab does not list
# EC2 or RDS findings it has no basis for.
CANONICAL_FINDINGS: tuple[dict[str, str], ...] = _core_findings() + _SHARED_FINDINGS

# Node types the ``aws`` fragment pool mints (app/cloudforge/generate/fragments/
# {decoy,false_positive,compensating_control,benign_noise}.py). The Kubernetes
# family draws that pool too, since its path federates into AWS IAM, so these
# types say nothing about which vendor the estate's own story belongs to and must
# not trip the ``aws`` bucket below.
_SHARED_FILLER_TYPES = frozenset(
    {
        "IAMRole",
        "IAMPolicy",
        "S3Bucket",
        "KmsKey",
        "EcrRepository",
        "SqsQueue",
        "LogTrail",
        "DataSet",
    }
)


def _vendors_present(nodes: list[dict[str, Any]]) -> set[str]:
    """The cloud vendors the estate's own node types point to.

    Any type starting with ``Azure`` -> azure, ``Gcp`` -> gcp, ``K8s`` -> k8s;
    everything else -> aws, except the shared filler types every family draws
    regardless of cloud (see ``_SHARED_FILLER_TYPES``).
    """
    vendors: set[str] = set()
    for node in nodes:
        node_type = str(node.get("type", ""))
        if node_type in _SHARED_FILLER_TYPES:
            continue
        if node_type.startswith("Azure"):
            vendors.add("azure")
        elif node_type.startswith("Gcp"):
            vendors.add("gcp")
        elif node_type.startswith("K8s"):
            vendors.add("k8s")
        else:
            vendors.add("aws")
    return vendors


def _filtered_findings(nodes: list[dict[str, Any]]) -> list[dict[str, str]]:
    """``CANONICAL_FINDINGS`` cut down to the vendors this estate actually has."""
    vendors = _vendors_present(nodes)
    return [
        {"id": entry["id"], "label": entry["label"]}
        for entry in CANONICAL_FINDINGS
        if entry["cloud"] in vendors
    ]


def render_estate_html(
    estate: dict[str, Any],
    prompt: str = "",
    title: str = "Interactive Lab Workbench",
) -> str:
    """Self-contained interactive layered architecture workbench for stripped estate."""
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    rows = "\n    ".join(
        f"<tr><td><code>{_esc(n['id'])}</code></td>"
        f"<td>{_esc(n['type'])}</td><td>{_esc(n['name'])}</td></tr>"
        for n in estate["nodes"]
    )
    edge_lines = "\n".join(f"{e['from']} --{e['type']}--> {e['to']}" for e in estate["edges"])
    safe_prompt = (
        _esc(prompt)
        if prompt
        else (
            "Investigate this estate. Find any identity-to-data risk path. "
            "Not every finding-shaped resource is a true positive."
        )
    )
    safe_title = _esc(title)
    findings = json.dumps(_filtered_findings(estate["nodes"]))

    return (
        template.replace("<!-- ESTATE_JSON_PLACEHOLDER -->", json.dumps(estate))
        .replace("<!-- CANONICAL_FINDINGS_PLACEHOLDER -->", findings)
        .replace("<!-- RAW_ROWS_PLACEHOLDER -->", rows)
        .replace("<!-- RAW_EDGES_PLACEHOLDER -->", _esc(edge_lines))
        .replace("<!-- BRIEF_PROMPT_PLACEHOLDER -->", safe_prompt)
        .replace("<!-- SCENARIO_TITLE_PLACEHOLDER -->", safe_title)
        .replace("<!-- VERSION_PLACEHOLDER -->", _esc(__version__))
    )


def _esc(value: object) -> str:
    text = str(value)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
