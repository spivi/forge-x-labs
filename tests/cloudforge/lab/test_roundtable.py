"""Roundtable: rotate four identity-federation families, write facilitator pack."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from app.cli import app
from app.cloudforge.lab.paths import FORBIDDEN_STUDENT_NAMES
from app.cloudforge.lab.roundtable import TRACKS

runner = CliRunner()


def test_track_has_four_distinct_families_with_aws_as_the_fourth() -> None:
    families = TRACKS["identity_federation"]
    assert len(families) == 4
    assert len(set(families)) == 4
    assert families[:3] == (
        "k8s_pod_irsa_exfil",
        "azure_imds_keyvault_harvest",
        "gcp_workload_identity_federation",
    )
    assert families[3] == "ci_cd_iam_chain"


def test_roundtable_rotates_identity_federation_families(tmp_path: Path) -> None:
    names = tmp_path / "students.txt"
    names.write_text("alice\nbob\ncara\ndave\neve\n")
    out = tmp_path / "rt"
    result = runner.invoke(
        app,
        ["roundtable", "--students", str(names), "--out", str(out)],
    )
    assert result.exit_code == 0, result.output
    families = TRACKS["identity_federation"]
    assert (out / "facilitator.md").is_file()
    roster = json.loads((out / "roster.json").read_text())
    assert roster["track"] == "identity_federation"
    by_name = {row["name"]: row["family"] for row in roster["entries"]}
    # a roster of four names maps to four distinct families, one per vendor
    assert [by_name[n] for n in ("alice", "bob", "cara", "dave")] == list(families)
    assert by_name["eve"] == families[0]  # 5th student wraps
    for name in ("alice", "bob", "cara", "dave"):
        assert (out / name / "student" / "estate.html").is_file()
        assert by_name[name] in (out / name / "student" / "brief.md").read_text()
    tf = {name: out / name / "student" / "terraform" for name in by_name}
    assert "kubernetes_pod" in (tf["alice"] / "k8s.tf").read_text()
    assert "azurerm_key_vault" in (tf["bob"] / "azure.tf").read_text()
    assert "google_storage_bucket" in (tf["cara"] / "gcp.tf").read_text()
    assert "aws_iam_role" in (tf["dave"] / "iam.tf").read_text()
    for vendor_file in ("k8s.tf", "azure.tf", "gcp.tf"):
        assert (tf["dave"] / vendor_file).read_text().startswith("# No resources")
    assert (out / "bob" / "student" / "estate.json").read_bytes() != (
        out / "cara" / "student" / "estate.json"
    ).read_bytes()


def test_facilitator_agenda_names_four_vendors(tmp_path: Path) -> None:
    names = tmp_path / "students.txt"
    names.write_text("alice\nbob\ncara\ndave\n")
    out = tmp_path / "rt"
    result = runner.invoke(app, ["roundtable", "--students", str(names), "--out", str(out)])
    assert result.exit_code == 0, result.output
    facilitator = (out / "facilitator.md").read_text()
    assert "four vendors" in facilitator
    assert "four clouds" in facilitator
    assert "three" not in facilitator
    for bullet in ("- Kubernetes:", "- Azure:", "- GCP:", "- AWS:"):
        assert bullet in facilitator
    for family in TRACKS["identity_federation"]:
        assert f"`{family}`" in facilitator


def test_roundtable_student_pack_has_no_answer_key(tmp_path: Path) -> None:
    names = tmp_path / "students.txt"
    names.write_text("alice\n")
    out = tmp_path / "rt"
    result = runner.invoke(app, ["roundtable", "--students", str(names), "--out", str(out)])
    assert result.exit_code == 0, result.output
    student = out / "alice" / "student"
    found = {path.name for path in student.rglob("*") if path.is_file()}
    assert found.isdisjoint(FORBIDDEN_STUDENT_NAMES)
    brief = (student / "brief.md").read_text()
    assert "can_pass_role" not in brief
    facilitator = (out / "facilitator.md").read_text()
    assert "terraform apply" in facilitator
    assert "instructor/" in facilitator


def test_roundtable_unknown_track_exits_one(tmp_path: Path) -> None:
    names = tmp_path / "students.txt"
    names.write_text("alice\n")
    result = runner.invoke(
        app,
        [
            "roundtable",
            "--students",
            str(names),
            "--out",
            str(tmp_path / "rt"),
            "--track",
            "nope",
        ],
    )
    assert result.exit_code == 1
    assert "error:" in result.output


def test_roundtable_empty_roster_exits_one(tmp_path: Path) -> None:
    names = tmp_path / "students.txt"
    names.write_text("\n\n")
    result = runner.invoke(
        app,
        ["roundtable", "--students", str(names), "--out", str(tmp_path / "rt")],
    )
    assert result.exit_code == 1
    assert "error:" in result.output
