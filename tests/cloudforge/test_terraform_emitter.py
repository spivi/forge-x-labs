"""Terraform emitter tests (check 4: terraform files emitted)."""

from __future__ import annotations

from pathlib import Path

from app.cloudforge import constants
from app.cloudforge.pipeline.terraform_emitter import TerraformEmitter


def test_emit_writes_all_six_tf_files(tmp_path: Path) -> None:
    written = TerraformEmitter().emit(tmp_path)

    names = {p.name for p in written}
    assert names == set(constants.TERRAFORM_FILES)


def test_iam_tf_contains_passrole(tmp_path: Path) -> None:
    TerraformEmitter().emit(tmp_path)

    iam = (tmp_path / "iam.tf").read_text(encoding="utf-8")
    assert "iam:PassRole" in iam


def test_emitted_hcl_has_no_forbidden_actions(tmp_path: Path) -> None:
    TerraformEmitter().emit(tmp_path)

    blob = "\n".join(p.read_text(encoding="utf-8") for p in tmp_path.glob("*.tf"))
    assert "iam:Delete" not in blob
    assert "s3:DeleteBucket" not in blob


def test_network_tf_has_open_ingress(tmp_path: Path) -> None:
    TerraformEmitter().emit(tmp_path)

    network = (tmp_path / "network.tf").read_text(encoding="utf-8")
    assert "0.0.0.0/0" in network
