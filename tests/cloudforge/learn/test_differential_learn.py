"""Learn-pipeline differential consistency tests (FXL-STRESS-8, #110).

Covers:
  * a pattern's ``quality_score >= 0.70`` -> re-running ``score_pattern`` reproduces
    the same score deterministically (STRESS-4's determinism guarantee extended to
    the learn side).
  * the corpus summary's ``exportable`` count -> the export file has EXACTLY that
    many records (the summary and the writer must agree on "how many").

Each check pairs with a deliberate-inconsistency fixture proving it is not
vacuously true.
"""

from __future__ import annotations

from pathlib import Path

from app.cloudforge.learn.adapters.rule_catalog_yaml import RuleCatalogYamlAdapter
from app.cloudforge.learn.corpus import load_corpus
from app.cloudforge.learn.export import export_training, write_training_export
from app.cloudforge.learn.normalizer import PatternNormalizer
from app.cloudforge.learn.quality import EXPORT_QUALITY_BAR, score_pattern, summarize_corpus
from app.cloudforge.learn.registry import get_entry, load_registry
from app.cloudforge.learn.validate import validate_fragment
from tests.cloudforge.learn.conftest import build_pattern

_REGISTRY_PATH = Path("data/source_registry.yaml")
_SOURCE_ID = "local-rule-catalog"
_SEED_COUNT = 14
_EXPECTED_EXPORTABLE = 12


def _load_scored_seed_patterns() -> list:  # type: ignore[type-arg]
    registry = load_registry(_REGISTRY_PATH)
    entry = get_entry(registry, _SOURCE_ID)
    assert entry.path is not None
    records = RuleCatalogYamlAdapter().extract(entry, Path(entry.path))
    normalizer = PatternNormalizer()
    patterns = [normalizer.normalize(r) for r in records]
    validated = [validate_fragment(p) for p in patterns]
    return [score_pattern(p)[0] for p in validated]


# --- 1. quality_score >= 0.70 -> re-scoring reproduces it exactly -------------


class TestQualityScoreReproducibleDifferential:
    """A pattern whose ``quality_score >= 0.70`` (exportable) must reproduce the
    SAME score if the scorer is re-run over the same pattern (no hidden state,
    no nondeterminism)."""

    def test_high_quality_pattern_score_is_reproduced_on_rerun(self) -> None:
        pattern = build_pattern()
        scored_once, report_once = score_pattern(pattern)
        assert scored_once.quality_score >= EXPORT_QUALITY_BAR
        assert report_once.exportable is True

        scored_twice, report_twice = score_pattern(pattern)

        assert scored_twice.quality_score == scored_once.quality_score
        assert report_twice.exportable == report_once.exportable

    def test_real_seed_catalog_scores_reproduce_across_many_reruns(self) -> None:
        patterns = _load_scored_seed_patterns()
        exportable_ids = {p.id for p in patterns if score_pattern(p)[1].exportable}
        assert exportable_ids, "fixture sanity: at least one seed pattern is exportable"

        for _ in range(5):
            rerun_ids = {p.id for p in patterns if score_pattern(p)[1].exportable}
            assert rerun_ids == exportable_ids

    def test_planted_inconsistency_fires_when_scoring_a_mutated_copy(self) -> None:
        """Deliberate-inconsistency fixture: scoring a DIFFERENT (lower-quality)
        pattern must NOT reproduce the high-quality pattern's score — proving the
        reproducibility check is sensitive to actual input, not vacuously equal."""
        rich = build_pattern()
        sparse = rich.model_copy(
            update={
                "id": "sparse-differential",
                "expected_findings": [],
                "control_mappings": [],
                "missing_controls": [],
                "confidence": 0.0,
            }
        )

        rich_scored, _ = score_pattern(rich)
        sparse_scored, sparse_report = score_pattern(sparse)

        assert sparse_scored.quality_score != rich_scored.quality_score
        assert sparse_report.exportable is False


# --- 2. corpus summary "N exportable" -> export file has EXACTLY N records ----


class TestSummaryExportCountDifferential:
    """``CorpusSummary.exportable`` must equal the number of records the export
    writer actually persists for the same scored corpus."""

    def test_hand_built_corpus_summary_count_matches_export_file_record_count(
        self, tmp_path: Path
    ) -> None:
        rich, _ = score_pattern(build_pattern())
        sparse, _ = score_pattern(
            build_pattern().model_copy(
                update={
                    "id": "sparse-export-diff",
                    "expected_findings": [],
                    "control_mappings": [],
                    "missing_controls": [],
                    "confidence": 0.0,
                }
            )
        )
        scored = [rich, sparse]
        summary = summarize_corpus(scored)

        result = export_training(scored)
        write_training_export(result, tmp_path)
        on_disk = load_corpus(tmp_path / "corpus.jsonl")

        assert summary.exportable == len(on_disk)
        assert summary.exportable == result.manifest.exported_count

    def test_real_seed_catalog_summary_says_12_and_export_file_has_exactly_12(
        self, tmp_path: Path
    ) -> None:
        patterns = _load_scored_seed_patterns()
        assert len(patterns) == _SEED_COUNT
        summary = summarize_corpus(patterns)

        result = export_training(patterns)
        write_training_export(result, tmp_path)
        on_disk = load_corpus(tmp_path / "corpus.jsonl")

        assert summary.exportable == _EXPECTED_EXPORTABLE
        assert len(on_disk) == _EXPECTED_EXPORTABLE
        assert summary.exportable == len(on_disk)

    def test_planted_inconsistency_fires_when_summary_and_export_see_different_corpora(
        self, tmp_path: Path
    ) -> None:
        """Deliberate-inconsistency fixture: computing the summary over one corpus
        subset but exporting a DIFFERENT subset must NOT coincidentally agree —
        proving the equality check is a real comparison, not a tautology."""
        rich, _ = score_pattern(build_pattern())
        sparse, _ = score_pattern(
            build_pattern().model_copy(
                update={
                    "id": "sparse-mismatch",
                    "expected_findings": [],
                    "control_mappings": [],
                    "missing_controls": [],
                    "confidence": 0.0,
                }
            )
        )
        # Summary computed over BOTH patterns (1 exportable)...
        summary_over_both = summarize_corpus([rich, sparse])
        # ...but export run over only the sparse (non-exportable) one.
        result = export_training([sparse])
        write_training_export(result, tmp_path)
        on_disk = load_corpus(tmp_path / "corpus.jsonl")

        assert summary_over_both.exportable == 1
        assert len(on_disk) == 0
        assert summary_over_both.exportable != len(on_disk)
