"""``cloudforge learn`` CLI tests (FXL-73, design §10).

Uses Typer's ``CliRunner`` throughout. ``fetch-sources`` is exercised with a MOCKED
fetch function (patched onto ``fetch.fetch_all_sources``'s injection point) — no
network access anywhere in this suite. ``ingest``/``validate-corpus``/``summarize``/
``export-training`` are exercised against the real seed rule catalog
(``data/source_registry.yaml`` + ``data/rule_catalog/seed_patterns.yaml``), proving the
whole pipeline end-to-end without touching the network, terraform, checkov, or opa.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.cli import app
from app.cloudforge.learn import fetch
from app.cloudforge.learn.source_models import SourceEntry

runner = CliRunner()

_REAL_REGISTRY = "data/source_registry.yaml"
_SEED_COUNT = 14
_EXPECTED_EXPORTABLE = 12


def _corpus_path(tmp_path: Path) -> Path:
    return tmp_path / "corpus.jsonl"


def _ingest_real_seed_catalog(tmp_path: Path) -> Path:
    corpus_path = _corpus_path(tmp_path)
    result = runner.invoke(
        app,
        [
            "learn",
            "ingest",
            "--adapter",
            "rule_catalog_yaml",
            "--registry",
            _REAL_REGISTRY,
            "--corpus",
            str(corpus_path),
        ],
    )
    assert result.exit_code == 0, result.stdout
    return corpus_path


class TestLearnHelpSurface:
    def test_learn_help_lists_all_five_subcommands(self) -> None:
        result = runner.invoke(app, ["learn", "--help"])

        assert result.exit_code == 0
        for name in (
            "fetch-sources",
            "ingest",
            "validate-corpus",
            "summarize",
            "export-training",
        ):
            assert name in result.stdout

    def test_top_level_help_is_unchanged(self) -> None:
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        for name in ("generate", "validate", "report", "version", "learn"):
            assert name in result.stdout


class TestFetchSourcesMocked:
    """``fetch-sources`` hits the network in production; here it never does."""

    def test_fetch_sources_uses_mocked_fetch_and_reports_counts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        raw_dir = tmp_path / "raw"
        registry_path = tmp_path / "registry.yaml"
        registry_path.write_text(
            "sources:\n"
            "  - id: fake-src\n"
            "    name: fake\n"
            "    type: scanner_rule_index\n"
            '    url: "https://example.com/fake"\n'
            "    adapter: checkov_policy_index\n"
            "    enabled: true\n"
            '    license: "Apache-2.0"\n'
            "    reuse_status: metadata_only\n"
            "    allowed_for_training: false\n",
            encoding="utf-8",
        )

        def _fake_fetch_all_sources(
            *, sources: list[SourceEntry], raw_dir: Path, fetch_fn: object
        ) -> fetch.FetchSummary:
            assert fetch_fn is None  # CLI never injects its own — real net path unused here
            return fetch.FetchSummary(fetched=1, skipped=0, failed=0, results=[])

        import app.cloudforge.learn.cli as learn_cli

        monkeypatch.setattr(learn_cli.fetch, "fetch_all_sources", _fake_fetch_all_sources)

        result = runner.invoke(
            app,
            [
                "learn",
                "fetch-sources",
                "--registry",
                str(registry_path),
                "--raw-dir",
                str(raw_dir),
            ],
        )

        assert result.exit_code == 0, result.stdout
        assert "fetched" in result.stdout

    def test_fetch_sources_reports_clean_error_on_bad_registry(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            [
                "learn",
                "fetch-sources",
                "--registry",
                str(tmp_path / "does-not-exist.yaml"),
                "--raw-dir",
                str(tmp_path / "raw"),
            ],
        )

        assert result.exit_code == 1
        assert "error:" in result.stdout
        assert "Traceback" not in result.stdout


class TestIngest:
    def test_ingest_real_seed_catalog_appends_fourteen_patterns(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            [
                "learn",
                "ingest",
                "--adapter",
                "rule_catalog_yaml",
                "--registry",
                _REAL_REGISTRY,
                "--corpus",
                str(_corpus_path(tmp_path)),
            ],
        )

        assert result.exit_code == 0, result.stdout
        assert str(_SEED_COUNT) in result.stdout

    def test_ingest_unknown_adapter_is_a_clean_cli_error(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            [
                "learn",
                "ingest",
                "--adapter",
                "nonexistent_adapter",
                "--registry",
                _REAL_REGISTRY,
                "--corpus",
                str(_corpus_path(tmp_path)),
            ],
        )

        assert result.exit_code == 1
        assert "error:" in result.stdout
        assert "Traceback" not in result.stdout


class TestValidateCorpus:
    def test_validate_corpus_passes_on_real_seed_catalog(self, tmp_path: Path) -> None:
        corpus_path = _ingest_real_seed_catalog(tmp_path)

        result = runner.invoke(app, ["learn", "validate-corpus", "--corpus", str(corpus_path)])

        assert result.exit_code == 0, result.stdout
        assert "PASS" in result.stdout

    def test_validate_corpus_fails_on_duplicate_ids(self, tmp_path: Path) -> None:
        corpus_path = _ingest_real_seed_catalog(tmp_path)
        # duplicate the corpus file's content to trigger a duplicate-id FAIL.
        text = corpus_path.read_text(encoding="utf-8")
        corpus_path.write_text(text + text, encoding="utf-8")

        result = runner.invoke(app, ["learn", "validate-corpus", "--corpus", str(corpus_path)])

        assert result.exit_code == 1
        assert "FAIL" in result.stdout

    def test_validate_corpus_missing_corpus_is_a_clean_error(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app, ["learn", "validate-corpus", "--corpus", str(tmp_path / "missing.jsonl")]
        )

        assert result.exit_code == 1
        assert "error:" in result.stdout
        assert "Traceback" not in result.stdout


class TestSummarize:
    def test_summarize_prints_provider_domain_family_and_quality(self, tmp_path: Path) -> None:
        corpus_path = _ingest_real_seed_catalog(tmp_path)
        runner.invoke(app, ["learn", "validate-corpus", "--corpus", str(corpus_path)])

        result = runner.invoke(app, ["learn", "summarize", "--corpus", str(corpus_path)])

        assert result.exit_code == 0, result.stdout
        assert "total patterns" in result.stdout
        assert "provider coverage" in result.stdout
        assert "domain coverage" in result.stdout
        assert "weakness family coverage" in result.stdout
        assert "average quality_score" in result.stdout

    def test_summarize_missing_corpus_is_a_clean_error(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app, ["learn", "summarize", "--corpus", str(tmp_path / "missing.jsonl")]
        )

        assert result.exit_code == 1
        assert "error:" in result.stdout
        assert "Traceback" not in result.stdout


class TestExportTraining:
    def test_export_training_missing_corpus_is_a_clean_error(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            [
                "learn",
                "export-training",
                "--corpus",
                str(tmp_path / "missing.jsonl"),
                "--out",
                str(tmp_path / "export"),
            ],
        )

        assert result.exit_code == 1
        assert "error:" in result.stdout
        assert "Traceback" not in result.stdout

    def test_export_training_reports_the_honest_twelve_of_fourteen(self, tmp_path: Path) -> None:
        corpus_path = _ingest_real_seed_catalog(tmp_path)
        runner.invoke(app, ["learn", "validate-corpus", "--corpus", str(corpus_path)])
        out_dir = tmp_path / "export"

        result = runner.invoke(
            app,
            [
                "learn",
                "export-training",
                "--corpus",
                str(corpus_path),
                "--out",
                str(out_dir),
            ],
        )

        assert result.exit_code == 0, result.stdout
        assert str(_EXPECTED_EXPORTABLE) in result.stdout
        assert (out_dir / "corpus.jsonl").exists()
        assert (out_dir / "manifest.json").exists()

    def test_export_training_include_restricted_flows_the_flag(self, tmp_path: Path) -> None:
        corpus_path = _ingest_real_seed_catalog(tmp_path)
        runner.invoke(app, ["learn", "validate-corpus", "--corpus", str(corpus_path)])
        out_dir = tmp_path / "export"

        result = runner.invoke(
            app,
            [
                "learn",
                "export-training",
                "--corpus",
                str(corpus_path),
                "--out",
                str(out_dir),
                "--include-restricted",
            ],
        )

        assert result.exit_code == 0, result.stdout
        import json

        manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["include_restricted"] is True


class TestEndToEndChain:
    """ingest -> validate-corpus (PASS) -> summarize -> export-training (12/14)."""

    def test_full_pipeline_over_the_real_seed_catalog(self, tmp_path: Path) -> None:
        corpus_path = _corpus_path(tmp_path)
        out_dir = tmp_path / "export"

        ingest_result = runner.invoke(
            app,
            [
                "learn",
                "ingest",
                "--adapter",
                "rule_catalog_yaml",
                "--registry",
                _REAL_REGISTRY,
                "--corpus",
                str(corpus_path),
            ],
        )
        validate_result = runner.invoke(
            app, ["learn", "validate-corpus", "--corpus", str(corpus_path)]
        )
        summarize_result = runner.invoke(app, ["learn", "summarize", "--corpus", str(corpus_path)])
        export_result = runner.invoke(
            app,
            [
                "learn",
                "export-training",
                "--corpus",
                str(corpus_path),
                "--out",
                str(out_dir),
            ],
        )

        assert ingest_result.exit_code == 0, ingest_result.stdout
        assert validate_result.exit_code == 0, validate_result.stdout
        assert "PASS" in validate_result.stdout
        assert summarize_result.exit_code == 0, summarize_result.stdout
        assert export_result.exit_code == 0, export_result.stdout
        assert str(_EXPECTED_EXPORTABLE) in export_result.stdout
