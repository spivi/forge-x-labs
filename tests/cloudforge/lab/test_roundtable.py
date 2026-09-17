"""Roundtable: rotate three identity-federation families, write facilitator pack."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from app.cli import app
from app.cloudforge.lab.paths import FORBIDDEN_STUDENT_NAMES
from app.cloudforge.lab.roundtable import TRACKS

runner = CliRunner()


def test_roundtable_rotates_identity_federation_families(tmp_path: Path) -> None:
    names = tmp_path / "students.txt"
    names.write_text("alice\nbob\ncara\ndave\n")
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
    roster_families = [row["family"] for row in roster["entries"]]
    assert families[0] in roster_families
    assert families[1] in roster_families
    assert families[2] in roster_families
    alice_family = families[0]
    dave_family = families[0]  # 4th student wraps
    assert (out / "alice" / "student" / "estate.html").is_file()
    assert alice_family in (out / "alice" / "student" / "brief.md").read_text()
    assert dave_family in (out / "dave" / "student" / "brief.md").read_text()
    assert (out / "alice" / "student" / "terraform" / "k8s.tf").is_file()
    assert (out / "bob" / "student" / "terraform" / "azure.tf").is_file()
    assert (out / "cara" / "student" / "terraform" / "gcp.tf").is_file()
    assert (out / "bob" / "student" / "estate.json").read_bytes() != (
        out / "cara" / "student" / "estate.json"
    ).read_bytes()


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
