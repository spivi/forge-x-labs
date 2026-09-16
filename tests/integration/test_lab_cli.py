"""End-to-end ``cloudforge lab`` / ``grade`` (FXL-144 / FXL-145)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from app.cli import app
from app.cloudforge.lab.paths import FORBIDDEN_STUDENT_NAMES

runner = CliRunner()
_SPEC = "examples/ci_cd_iam_chain.yaml"


def _lab(tmp_path: Path, seed: int = 17) -> Path:
    out = tmp_path / "alice"
    result = runner.invoke(app, ["lab", _SPEC, "--out", str(out), "--seed", str(seed)])
    assert result.exit_code == 0, result.output
    return out


def test_lab_writes_student_and_instructor(tmp_path: Path) -> None:
    out = _lab(tmp_path)
    assert (out / "student" / "brief.md").is_file()
    assert (out / "student" / "estate.json").is_file()
    assert (out / "student" / "estate.html").is_file()
    assert (out / "student" / "terraform").is_dir()
    assert (out / "instructor" / "grade_key.json").is_file()
    assert (out / "instructor" / "report.md").is_file()


def test_student_tree_has_no_answer_key_files(tmp_path: Path) -> None:
    student = _lab(tmp_path) / "student"
    names = {path.name for path in student.rglob("*") if path.is_file()}
    assert names.isdisjoint(FORBIDDEN_STUDENT_NAMES)


def test_estate_json_has_no_security_fields(tmp_path: Path) -> None:
    estate = json.loads((_lab(tmp_path) / "student" / "estate.json").read_text())
    blob = json.dumps(estate)
    assert "criticality" not in blob
    assert '"risk"' not in blob
    for node in estate["nodes"]:
        assert "security" not in node
    for edge in estate["edges"]:
        assert "security" not in edge


def test_student_files_do_not_contain_remediation_or_explanations(tmp_path: Path) -> None:
    out = _lab(tmp_path)
    instructor_findings = json.loads((out / "instructor" / "expected_findings.json").read_text())
    instructor_paths = json.loads((out / "instructor" / "ground_truth_paths.json").read_text())
    student_text = "\n".join(p.read_text() for p in (out / "student").rglob("*") if p.is_file())
    for finding in instructor_findings["findings"]:
        assert finding["remediation"] not in student_text
    for path in instructor_paths["paths"]:
        assert path["explanation"] not in student_text
    assert "can_pass_role" not in (out / "student" / "brief.md").read_text()


def test_same_seed_is_byte_identical(tmp_path: Path) -> None:
    a = _lab(tmp_path / "a", seed=3) / "student" / "estate.json"
    b = _lab(tmp_path / "b", seed=3) / "student" / "estate.json"
    assert a.read_bytes() == b.read_bytes()


def test_grade_exits_zero_on_a_partial_guess(tmp_path: Path) -> None:
    out = _lab(tmp_path)
    key = json.loads((out / "instructor" / "grade_key.json").read_text())
    nodes = key["paths"][0]["nodes"][:3]
    guess = tmp_path / "guess.yaml"
    guess.write_text(f"paths:\n  - nodes: {nodes}\nfindings: []\n")
    result = runner.invoke(app, ["grade", str(out), "--submission", str(guess)])
    assert result.exit_code == 0, result.output
    assert "paths hit" in result.output


def test_grade_missing_key_exits_one(tmp_path: Path) -> None:
    guess = tmp_path / "guess.yaml"
    guess.write_text("paths: []\nfindings: []\n")
    result = runner.invoke(app, ["grade", str(tmp_path), "--submission", str(guess)])
    assert result.exit_code == 1
    assert "error:" in result.output
