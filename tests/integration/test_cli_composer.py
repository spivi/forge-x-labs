"""CLI tests for the ``--engine composer --seed N`` option on ``generate``.

The default (``--engine template``) behavior must stay unchanged; ``composer``
writes a valid artifact tree; a bad engine name surfaces as a clean CLI error
(no raw traceback), consistent with the stress-fixed ``_CLI_ERRORS`` invariant.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.cli import app
from app.cloudforge.validate import tool_probe

runner = CliRunner()


@pytest.fixture(autouse=True)
def _no_external_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool_probe, "detect_tool", lambda name: False)


def test_generate_composer_engine(tmp_path: Path) -> None:
    out = tmp_path / "s"
    r = runner.invoke(
        app,
        [
            "generate",
            "examples/ci_cd_iam_chain.yaml",
            "--out",
            str(out),
            "--engine",
            "composer",
            "--seed",
            "5",
        ],
    )
    assert r.exit_code == 0, r.output
    assert (out / "graph.json").exists()
    assert (out / "expected_findings.json").exists()
    assert (out / "ground_truth_paths.json").exists()


def test_composer_engine_is_deterministic(tmp_path: Path) -> None:
    def _run(dest: Path) -> None:
        result = runner.invoke(
            app,
            [
                "generate",
                "examples/ci_cd_iam_chain.yaml",
                "--out",
                str(dest),
                "--engine",
                "composer",
                "--seed",
                "9",
            ],
        )
        assert result.exit_code == 0, result.output

    a = tmp_path / "a"
    b = tmp_path / "b"
    _run(a)
    _run(b)
    assert (a / "graph.json").read_text() == (b / "graph.json").read_text()


def test_default_engine_still_template(tmp_path: Path) -> None:
    out = tmp_path / "t"
    r = runner.invoke(app, ["generate", "examples/ci_cd_iam_chain.yaml", "--out", str(out)])
    assert r.exit_code == 0, r.output
    assert (out / "graph.json").exists()


def test_explicit_template_engine_matches_default(tmp_path: Path) -> None:
    default_out = tmp_path / "d"
    explicit_out = tmp_path / "e"
    runner.invoke(app, ["generate", "examples/ci_cd_iam_chain.yaml", "--out", str(default_out)])
    runner.invoke(
        app,
        [
            "generate",
            "examples/ci_cd_iam_chain.yaml",
            "--out",
            str(explicit_out),
            "--engine",
            "template",
        ],
    )
    assert (default_out / "graph.json").read_text() == (explicit_out / "graph.json").read_text()


def test_unknown_engine_is_clean_error(tmp_path: Path) -> None:
    r = runner.invoke(
        app,
        [
            "generate",
            "examples/ci_cd_iam_chain.yaml",
            "--out",
            str(tmp_path / "s"),
            "--engine",
            "bogus",
        ],
    )
    assert r.exit_code == 1
    assert "error:" in r.stdout
    assert "Traceback" not in r.stdout
