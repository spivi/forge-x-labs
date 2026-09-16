"""Grading: subsequence path match + finding-family set (FXL-145)."""

from __future__ import annotations

from app.cloudforge.lab.grade import grade_submission
from app.cloudforge.lab.submission import LabSubmission, PathGuess

_KEY = {
    "paths": [{"id": "p1", "nodes": ["a", "b", "c", "d"]}],
    "finding_families": ["iam_passrole_risk", "s3_logging_missing"],
}


def test_subsequence_hits_the_path() -> None:
    guess = LabSubmission(paths=[PathGuess(nodes=["a", "c", "d"])], findings=["iam_passrole_risk"])
    result = grade_submission(_KEY, guess)
    assert result.path_hits == ["p1"]
    assert result.path_misses == []
    assert result.finding_hits == ["iam_passrole_risk"]
    assert result.finding_misses == ["s3_logging_missing"]


def test_wrong_path_is_a_miss_plus_extra() -> None:
    guess = LabSubmission(paths=[PathGuess(nodes=["x", "y"])], findings=[])
    result = grade_submission(_KEY, guess)
    assert result.path_hits == []
    assert result.path_misses == ["p1"]
    assert "x->y" in result.extras


def test_empty_submission_misses_everything() -> None:
    result = grade_submission(_KEY, LabSubmission())
    assert result.path_misses == ["p1"]
    assert set(result.finding_misses) == {"iam_passrole_risk", "s3_logging_missing"}
