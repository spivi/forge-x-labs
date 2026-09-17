"""The workbench finding checklist must be filtered to the estate's own vendors.

``CANONICAL_FINDINGS`` covers every family cloudforge can generate (AWS, Azure,
GCP, K8s); an estate for one family must not offer findings from another (an
Azure lab listing EC2 or RDS options, for example).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.cloudforge.generate.composer import GraphComposer
from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.lab.estate import CANONICAL_FINDINGS, render_estate_html
from app.cloudforge.lab.strip import strip_graph
from app.cloudforge.models.scenario import ScenarioSpec

_FINDINGS_BLOCK = re.compile(
    r'<script id="canonical-findings-data" type="application/json">\s*(.*?)\s*</script>',
    re.DOTALL,
)


def _finding_ids_in(html: str) -> set[str]:
    match = _FINDINGS_BLOCK.search(html)
    assert match, "canonical-findings-data script block not found"
    payload = json.loads(match.group(1))
    return {entry["id"] for entry in payload}


def _render(example: str, seed: int = 0) -> str:
    spec = ScenarioSpec.model_validate(load_yaml(Path(example)))
    bundle = GraphComposer(spec, seed=seed).generate()
    estate = strip_graph(bundle.graph)
    return render_estate_html(estate, prompt="", title="test")


def test_catalog_has_a_cloud_tag_for_every_entry() -> None:
    assert len(CANONICAL_FINDINGS) == 19
    for entry in CANONICAL_FINDINGS:
        assert entry["cloud"] in {"aws", "azure", "gcp", "k8s"}, entry


def test_catalog_tags_the_three_non_aws_families_and_nothing_else() -> None:
    non_aws = {
        entry["id"]: entry["cloud"] for entry in CANONICAL_FINDINGS if entry["cloud"] != "aws"
    }
    assert non_aws == {
        "k8s_pod_irsa_exfil": "k8s",
        "azure_imds_keyvault_harvest": "azure",
        "gcp_workload_identity_federation": "gcp",
    }


def test_azure_lab_hides_rds_and_ec2_but_shows_azure() -> None:
    ids = _finding_ids_in(_render("examples/azure_imds_keyvault_harvest.yaml"))
    assert "rds_instance_public" not in ids
    assert "ec2_imdsv1_enabled" not in ids
    assert "azure_imds_keyvault_harvest" in ids


def test_public_rds_lab_shows_rds_and_ec2_but_hides_azure() -> None:
    ids = _finding_ids_in(_render("examples/public_rds_instance.yaml"))
    assert "rds_instance_public" in ids
    assert "ec2_imdsv1_enabled" in ids
    assert "azure_imds_keyvault_harvest" not in ids


def test_gcp_lab_only_shows_the_gcp_entry_and_no_other_vendor() -> None:
    ids = _finding_ids_in(_render("examples/gcp_workload_identity_federation.yaml"))
    assert "gcp_workload_identity_federation" in ids
    assert "azure_imds_keyvault_harvest" not in ids
    assert "k8s_pod_irsa_exfil" not in ids
    assert "rds_instance_public" not in ids
    assert "ec2_imdsv1_enabled" not in ids


def test_k8s_lab_only_shows_the_k8s_entry_and_no_other_vendor() -> None:
    ids = _finding_ids_in(_render("examples/k8s_pod_irsa_exfil.yaml"))
    assert "k8s_pod_irsa_exfil" in ids
    assert "azure_imds_keyvault_harvest" not in ids
    assert "gcp_workload_identity_federation" not in ids
    assert "rds_instance_public" not in ids
    assert "ec2_imdsv1_enabled" not in ids


def test_yaml_export_and_evaluator_still_read_selected_ids() -> None:
    """The checklist filter must not touch the submission/evaluator wiring."""
    html = _render("examples/ci_cd_iam_chain.yaml")
    assert "selectedFindings" in html
    assert "Score Submission" in html
    assert "Deterministic In-Browser Evaluator" in html
