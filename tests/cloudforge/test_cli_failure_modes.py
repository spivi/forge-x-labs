"""FXL-STRESS-9 (#111): CLI failure-mode + UX stress (S1/S15).

Proves the CLI fails clearly on every hostile/adversarial input named in the issue:
missing scenario file, empty/invalid YAML, unknown scenario family, an
already-populated (but not corrupted-by-us) out dir, a read-only output dir, a path
containing spaces, a corrupted ``graph.json``/``expected_findings.json``/
``ground_truth_paths.json``, ``report``/``validate`` run before ``generate``, ``learn
export-training`` before ``ingest``, ``learn ingest --adapter <unknown>``, and a
``deployable: true`` scenario (S1).

For every case: exit code != 0, a clean ``error:`` message, NO raw Python traceback
(``Traceback (most recent call last)`` must never appear in CLI output), and no false
"success"/"generated"/"PASS" claim on a failed run (S15).

Two genuine bugs were found and fixed in this PR (see ``app/cloudforge/cli.py`` and
``app/cloudforge/learn/cli.py``): ``generate``/``validate``/``report`` (and every
``learn`` subcommand) caught only ``CloudforgeError``, so a schema-invalid-but-
well-formed artifact (``pydantic.ValidationError`` — e.g. ``deployable: true``, which
is rejected by a field validator that raises ``ValueError``/``ValidationError``, not a
``CloudforgeError``) or an unwritable output path (raw ``OSError``/``PermissionError``)
leaked a raw traceback instead of a clean ``error:`` + exit 1. Both are fixed by
widening the caught exception tuple to ``(CloudforgeError, ValidationError, OSError)`` —
mirroring the fail-soft pattern ``report/renderer.py::_run_validation`` already used
internally. Regression coverage lives in ``TestDeployableTrueLeaksCleanly`` and
``TestReadOnlyOutputDirLeaksCleanly`` below (both now assert clean-failure, not xfail).
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.cli import app
from app.cloudforge.validate import tool_probe

runner = CliRunner()

_EXAMPLE_SCENARIO = "examples/ci_cd_iam_chain.yaml"
_TRACEBACK_MARKER = "Traceback (most recent call last)"


@pytest.fixture(autouse=True)
def _no_external_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every case here must be reachable without terraform/checkov/opa installed."""
    monkeypatch.setattr(tool_probe, "detect_tool", lambda name: False)


def _assert_clean_failure(result, *, forbid_words: tuple[str, ...] = ()) -> None:  # type: ignore[no-untyped-def]
    """Shared assertion: non-zero exit, clean ``error:``, no traceback, no false success."""
    assert result.exit_code != 0, result.stdout
    assert _TRACEBACK_MARKER not in result.stdout
    assert "error:" in result.stdout or "error" in result.stdout.lower()
    for word in forbid_words:
        assert word not in result.stdout


def _valid_scenario_yaml(
    *, deployable: bool = False, scenario_type: str = "ci_cd_iam_chain"
) -> str:
    return f"""
cloud: aws
scenario_type: {scenario_type}
environment: staging
difficulty: medium
company_profile:
  type: b2b_saas
  size: small
  app_name: analytics-exporter
requirements:
  critical_chains: 1
  medium_findings: 2
  false_positives: 1
constraints:
  no_real_secrets: true
  no_destructive_permissions: true
  max_resources: 40
  deployable: {str(deployable).lower()}
"""


class TestMissingScenarioFile:
    def test_generate_on_missing_scenario_file_fails_cleanly(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            ["generate", str(tmp_path / "does-not-exist.yaml"), "--out", str(tmp_path / "out")],
        )

        _assert_clean_failure(result, forbid_words=("generated", "PASS"))
        assert not (tmp_path / "out").exists()


class TestEmptyYaml:
    def test_generate_on_empty_yaml_fails_cleanly(self, tmp_path: Path) -> None:
        scenario = tmp_path / "empty.yaml"
        scenario.write_text("", encoding="utf-8")

        result = runner.invoke(app, ["generate", str(scenario), "--out", str(tmp_path / "out")])

        _assert_clean_failure(result, forbid_words=("generated", "PASS"))
        assert not (tmp_path / "out").exists()


class TestInvalidYaml:
    def test_generate_on_malformed_yaml_fails_cleanly(self, tmp_path: Path) -> None:
        scenario = tmp_path / "bad.yaml"
        scenario.write_text("cloud: aws\n  bad_indent: [1,2\n", encoding="utf-8")

        result = runner.invoke(app, ["generate", str(scenario), "--out", str(tmp_path / "out")])

        _assert_clean_failure(result, forbid_words=("generated", "PASS"))
        assert not (tmp_path / "out").exists()


class TestUnknownScenarioFamily:
    def test_generate_on_unknown_scenario_type_fails_cleanly(self, tmp_path: Path) -> None:
        scenario = tmp_path / "unknown_family.yaml"
        scenario.write_text(
            _valid_scenario_yaml(scenario_type="totally_bogus_family"), encoding="utf-8"
        )

        result = runner.invoke(app, ["generate", str(scenario), "--out", str(tmp_path / "out")])

        _assert_clean_failure(result, forbid_words=("generated", "PASS"))
        assert "totally_bogus_family" in result.stdout
        assert not (tmp_path / "out").exists()


class TestOutDirExistsAndNonEmpty:
    """Not a bug: overwriting into a pre-populated dir is a supported, correct success.

    ``ScenarioArtifacts.write_all`` writes the full fixed artifact set every time
    (fixed terraform filenames from ``constants.TERRAFORM_FILES``), so re-generating
    into an already-populated directory produces a complete, internally-consistent
    tree — it does not corrupt or partially overwrite. Pre-existing unrelated files are
    left alone (cloudforge only ever writes its own known filenames). This is asserted
    as correct behavior, not treated as a stress finding.
    """

    def test_generate_into_nonempty_dir_succeeds_and_does_not_corrupt(
        self, tmp_path: Path
    ) -> None:
        out = tmp_path / "out"
        out.mkdir()
        (out / "unrelated_junk.txt").write_text("pre-existing", encoding="utf-8")

        result = runner.invoke(app, ["generate", _EXAMPLE_SCENARIO, "--out", str(out)])

        assert result.exit_code == 0, result.stdout
        assert _TRACEBACK_MARKER not in result.stdout
        assert (out / "unrelated_junk.txt").exists()
        assert (out / "graph.json").exists()
        assert (out / "terraform" / "iam.tf").exists()

    def test_regenerating_a_different_scenario_type_over_existing_out_leaves_no_stale_files(
        self, tmp_path: Path
    ) -> None:
        out = tmp_path / "out"
        first = runner.invoke(
            app, ["generate", "examples/public_data_exposure.yaml", "--out", str(out)]
        )
        files_after_first = sorted(p.name for p in out.rglob("*") if p.is_file())

        second = runner.invoke(app, ["generate", _EXAMPLE_SCENARIO, "--out", str(out)])
        files_after_second = sorted(p.name for p in out.rglob("*") if p.is_file())

        assert first.exit_code == 0, first.stdout
        assert second.exit_code == 0, second.stdout
        assert files_after_first == files_after_second


class TestReadOnlyOutputDirLeaksCleanly:
    """BUG(CRITICAL): a read-only output dir leaked a raw ``PermissionError`` traceback.

    Reproducer: ``--out`` resolves under a directory with no write permission.
    ``ScenarioArtifacts.write_all`` calls ``Path.mkdir()`` unguarded, and ``generate``'s
    ``except CloudforgeError`` did not catch the resulting ``PermissionError`` (a raw
    ``OSError``, not a ``CloudforgeError``) — a real terminal would print a full Python
    traceback instead of a clean CLI error. Fixed in this PR: ``cli.py`` now catches
    ``(CloudforgeError, ValidationError, OSError)``. This test now asserts the fixed,
    clean-failure behavior (was: ``xfail(strict=True)`` during the bug-hunt).
    """

    def test_generate_into_read_only_parent_dir_fails_cleanly(self, tmp_path: Path) -> None:
        parent = tmp_path / "ro_parent"
        parent.mkdir()
        out = parent / "scenario"
        os.chmod(parent, stat.S_IREAD | stat.S_IEXEC)
        try:
            result = runner.invoke(app, ["generate", _EXAMPLE_SCENARIO, "--out", str(out)])
        finally:
            os.chmod(parent, stat.S_IRWXU)

        _assert_clean_failure(result, forbid_words=("generated", "PASS"))
        assert not out.exists()


class TestPathWithSpaces:
    def test_generate_validate_report_succeed_with_spaces_in_out_path(
        self, tmp_path: Path
    ) -> None:
        out = tmp_path / "path with spaces" / "scenario dir"

        gen = runner.invoke(app, ["generate", _EXAMPLE_SCENARIO, "--out", str(out)])
        val = runner.invoke(app, ["validate", str(out)])
        rep = runner.invoke(app, ["report", str(out)])

        assert gen.exit_code == 0, gen.stdout
        assert val.exit_code == 0, val.stdout
        assert rep.exit_code == 0, rep.stdout
        for result in (gen, val, rep):
            assert _TRACEBACK_MARKER not in result.stdout
        assert (out / "graph.json").exists()
        assert (out / "report.md").exists()


def _generate(tmp_path: Path, name: str = "out") -> Path:
    out = tmp_path / name
    result = runner.invoke(app, ["generate", _EXAMPLE_SCENARIO, "--out", str(out)])
    assert result.exit_code == 0, result.stdout
    return out


class TestCorruptGraphJson:
    def test_validate_on_corrupt_graph_json_fails_cleanly(self, tmp_path: Path) -> None:
        out = _generate(tmp_path)
        (out / "graph.json").write_text("{not valid json", encoding="utf-8")

        result = runner.invoke(app, ["validate", str(out)])

        _assert_clean_failure(result, forbid_words=("PASS",))

    def test_report_on_corrupt_graph_json_fails_cleanly(self, tmp_path: Path) -> None:
        out = _generate(tmp_path)
        (out / "graph.json").write_text("{not valid json", encoding="utf-8")

        result = runner.invoke(app, ["report", str(out)])

        _assert_clean_failure(result, forbid_words=("report written",))
        assert not (out / "report.md").exists()


class TestCorruptExpectedFindingsJson:
    def test_validate_on_corrupt_expected_findings_fails_cleanly(self, tmp_path: Path) -> None:
        out = _generate(tmp_path)
        (out / "expected_findings.json").write_text("{not valid json", encoding="utf-8")

        result = runner.invoke(app, ["validate", str(out)])

        _assert_clean_failure(result, forbid_words=("PASS",))

    def test_report_on_corrupt_expected_findings_fails_cleanly(self, tmp_path: Path) -> None:
        out = _generate(tmp_path)
        (out / "expected_findings.json").write_text("{not valid json", encoding="utf-8")

        result = runner.invoke(app, ["report", str(out)])

        _assert_clean_failure(result, forbid_words=("report written",))
        assert not (out / "report.md").exists()


class TestCorruptGroundTruthPathsJson:
    def test_validate_on_corrupt_ground_truth_paths_fails_cleanly(self, tmp_path: Path) -> None:
        out = _generate(tmp_path)
        (out / "ground_truth_paths.json").write_text("{not valid json", encoding="utf-8")

        result = runner.invoke(app, ["validate", str(out)])

        _assert_clean_failure(result, forbid_words=("PASS",))

    def test_report_on_corrupt_ground_truth_paths_fails_cleanly(self, tmp_path: Path) -> None:
        out = _generate(tmp_path)
        (out / "ground_truth_paths.json").write_text("{not valid json", encoding="utf-8")

        result = runner.invoke(app, ["report", str(out)])

        _assert_clean_failure(result, forbid_words=("report written",))
        assert not (out / "report.md").exists()


class TestSchemaInvalidScenarioYamlLeaksCleanly:
    """BUG(CRITICAL): a schema-invalid-but-well-formed ``scenario.yaml`` leaked a raw
    ``pydantic.ValidationError`` traceback from ``validate`` and ``report``.

    Reproducer: hand-edit a generated ``scenario.yaml`` to set ``cloud: ibm`` (a
    well-formed YAML mapping that fails the allowed-cloud schema check).
    ``validate``'s risk-engine path and ``report``'s renderer both call
    ``ScenarioSpec.model_validate`` directly, and the CLI commands caught only
    ``CloudforgeError`` — ``ValidationError`` is not a ``CloudforgeError`` subclass, so
    it escaped uncaught. Fixed alongside the read-only-dir bug (same root cause, same
    fix): ``cli.py`` now catches ``(CloudforgeError, ValidationError, OSError)``.
    """

    def test_validate_on_schema_invalid_scenario_yaml_fails_cleanly(self, tmp_path: Path) -> None:
        out = _generate(tmp_path)
        (out / "scenario.yaml").write_text(
            _valid_scenario_yaml().replace("cloud: aws", "cloud: ibm")
        )

        result = runner.invoke(app, ["validate", str(out)])

        _assert_clean_failure(result, forbid_words=("PASS",))

    def test_report_on_schema_invalid_scenario_yaml_fails_cleanly(self, tmp_path: Path) -> None:
        out = _generate(tmp_path)
        (out / "scenario.yaml").write_text(
            _valid_scenario_yaml().replace("cloud: aws", "cloud: ibm")
        )

        result = runner.invoke(app, ["report", str(out)])

        _assert_clean_failure(result, forbid_words=("report written",))
        assert not (out / "report.md").exists()


class TestReportBeforeGenerate:
    def test_report_before_generate_fails_cleanly(self, tmp_path: Path) -> None:
        out = tmp_path / "never_generated"

        result = runner.invoke(app, ["report", str(out)])

        _assert_clean_failure(result, forbid_words=("report written",))
        assert not out.exists()


class TestValidateBeforeGenerate:
    def test_validate_before_generate_fails_cleanly(self, tmp_path: Path) -> None:
        out = tmp_path / "never_generated"

        result = runner.invoke(app, ["validate", str(out)])

        _assert_clean_failure(result, forbid_words=("PASS",))
        assert not out.exists()


class TestLearnExportBeforeIngest:
    def test_export_training_before_ingest_fails_cleanly(self, tmp_path: Path) -> None:
        corpus_path = tmp_path / "corpus.jsonl"
        out_dir = tmp_path / "export"

        result = runner.invoke(
            app,
            ["learn", "export-training", "--corpus", str(corpus_path), "--out", str(out_dir)],
        )

        _assert_clean_failure(result, forbid_words=("exported",))
        assert not out_dir.exists()


class TestLearnIngestUnknownAdapter:
    def test_ingest_unknown_adapter_fails_cleanly(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            [
                "learn",
                "ingest",
                "--adapter",
                "bogus_adapter_xyz",
                "--registry",
                "data/source_registry.yaml",
                "--corpus",
                str(tmp_path / "corpus.jsonl"),
            ],
        )

        _assert_clean_failure(result, forbid_words=("ingested",))
        assert "bogus_adapter_xyz" in result.stdout
        assert not (tmp_path / "corpus.jsonl").exists()


class TestDeployableTrueLeaksCleanly:
    """BUG(CRITICAL) S1: ``deployable: true`` leaked a raw ``pydantic.ValidationError``
    traceback instead of the clean load error the stress contract (S1) requires.

    Reproducer: a scenario YAML with ``constraints.deployable: true`` — well-formed
    YAML, rejected by ``Constraints._must_not_be_deployable`` (a ``@field_validator``
    that raises ``ValueError``), which Pydantic wraps into a ``ValidationError`` at
    ``ScenarioSpec.model_validate`` in ``generate``. ``generate``'s
    ``except CloudforgeError`` did not catch it (``ValidationError`` is not a
    ``CloudforgeError``), so it printed a full Python traceback and exited via an
    unhandled exception rather than ``typer.Exit(1)``. Fixed in this PR (see module
    docstring); this test now asserts the fixed clean-load-error behavior.
    """

    def test_deployable_true_yaml_produces_a_clean_load_error(self, tmp_path: Path) -> None:
        scenario = tmp_path / "deployable_true.yaml"
        scenario.write_text(_valid_scenario_yaml(deployable=True), encoding="utf-8")

        result = runner.invoke(app, ["generate", str(scenario), "--out", str(tmp_path / "out")])

        _assert_clean_failure(result, forbid_words=("generated", "PASS"))
        assert "deployable" in result.stdout.lower()
        assert not (tmp_path / "out").exists()
