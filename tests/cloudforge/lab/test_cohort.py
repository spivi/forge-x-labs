"""Cohort seed stability + roster/results (plan L3)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from app.cli import app
from app.cloudforge.lab.cohort import seed_for

runner = CliRunner()


def test_seed_for_is_stable_and_not_python_hash() -> None:
    assert seed_for("alice") == seed_for("alice")
    assert seed_for("alice") != seed_for("bob")


def test_lab_cohort_writes_roster_and_per_student_packs(tmp_path: Path) -> None:
    names = tmp_path / "students.txt"
    names.write_text("alice\nbob\n")
    out = tmp_path / "cohort"
    result = runner.invoke(
        app,
        [
            "lab-cohort",
            "examples/ci_cd_iam_chain.yaml",
            "--students",
            str(names),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert (out / "roster.json").is_file()
    assert (out / "alice" / "student" / "brief.md").is_file()
    assert (out / "bob" / "instructor" / "grade_key.json").is_file()
    assert (out / "alice" / "student" / "estate.json").read_bytes() != (
        out / "bob" / "student" / "estate.json"
    ).read_bytes()


def test_grade_cohort_writes_results_md(tmp_path: Path) -> None:
    names = tmp_path / "students.txt"
    names.write_text("alice\n")
    cohort = tmp_path / "cohort"
    runner.invoke(
        app,
        [
            "lab-cohort",
            "examples/ci_cd_iam_chain.yaml",
            "--students",
            str(names),
            "--out",
            str(cohort),
        ],
    )
    subs = tmp_path / "subs"
    subs.mkdir()
    (subs / "alice.yaml").write_text("paths: []\nfindings: []\n")
    result = runner.invoke(app, ["grade-cohort", str(cohort), "--submissions", str(subs)])
    assert result.exit_code == 0, result.output
    text = (cohort / "results.md").read_text()
    assert "alice" in text
    assert "paths miss" in text or "miss" in text
