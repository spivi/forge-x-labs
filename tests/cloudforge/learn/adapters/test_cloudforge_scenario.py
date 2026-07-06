"""``cloudforge_scenario`` adapter tests: ingest a real generated scenario dir.

Fixtures under ``tests/cloudforge/learn/fixtures/scenario_*`` are trimmed copies of
real ``cloudforge generate`` output (``scenario.yaml`` / ``graph.json`` /
``expected_findings.json`` / ``ground_truth_paths.json``) — no hand-authored JSON.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.cloudforge.errors import CloudforgeError
from app.cloudforge.learn.adapters.cloudforge_scenario import (
    ADAPTER_NAME,
    ADAPTER_VERSION,
    CloudforgeScenarioAdapter,
)
from app.cloudforge.learn.source_models import ReuseStatus, SourceEntry, SourceType

_FIXTURES = Path(__file__).parent.parent / "fixtures"
_CI_CD_DIR = _FIXTURES / "scenario_ci_cd_iam_chain"
_PDE_DIR = _FIXTURES / "scenario_public_data_exposure"


def _source_entry(path: str = "out/") -> SourceEntry:
    # The entry's ``path`` is a provenance LABEL only — the directory the adapter actually
    # reads is passed as ``extract``'s second argument. Since FXL-109 added path-traversal
    # containment to ``SourceEntry.path`` (absolute/escaping paths are rejected at the
    # model boundary), this label defaults to the real registry's in-tree relative value
    # (``out/``) rather than an absolute ``tmp_path``. The read location stays wherever the
    # test points ``extract`` — decoupling the (contained) provenance label from the
    # (test-local, absolute) read path.
    return SourceEntry(
        id="local-scenarios-out",
        name="cloudforge generated scenario dirs",
        type=SourceType.LOCAL_SCENARIO_DIR,
        path=path,
        adapter="cloudforge_scenario",
        enabled=True,
        license="CC0-1.0",
        reuse_status=ReuseStatus.FULL_REUSE,
        allowed_for_training=True,
        notes="test",
    )


def test_extract_ci_cd_iam_chain_maps_critical_path_to_record() -> None:
    adapter = CloudforgeScenarioAdapter()
    records = adapter.extract(_source_entry(), _CI_CD_DIR)

    assert len(records) == 1
    record = records[0]
    assert record.source_id == "local-scenarios-out"
    assert record.raw_id == "path-critical-01"
    assert "ci_cd_iam_chain" in record.title
    assert record.cloud_provider is not None
    assert record.cloud_provider.value == "aws"
    assert record.severity == "critical"
    assert set(record.resource_types) == {
        "CICDIdentity",
        "IAMRole",
        "S3Bucket",
        "DataSet",
    }
    assert "GitHub Actions OIDC" in record.summary
    assert record.remediation != ""


def test_extract_public_data_exposure_maps_critical_path_to_record() -> None:
    adapter = CloudforgeScenarioAdapter()
    records = adapter.extract(_source_entry(), _PDE_DIR)

    assert len(records) == 1
    record = records[0]
    assert record.raw_id == "path-critical-pde-01"
    assert record.severity == "critical"
    assert set(record.resource_types) == {"Account", "S3Bucket", "DataSet"}
    assert "public-read" in record.summary or "public" in record.summary.lower()


def test_extract_stamps_complete_provenance() -> None:
    adapter = CloudforgeScenarioAdapter()
    records = adapter.extract(_source_entry(), _CI_CD_DIR)
    provenance = records[0].provenance

    assert provenance.adapter_name == ADAPTER_NAME == "cloudforge_scenario"
    assert provenance.adapter_version == ADAPTER_VERSION
    assert provenance.source_id == "local-scenarios-out"
    assert provenance.extraction_method == "scenario_dir"
    assert provenance.reuse_status is ReuseStatus.FULL_REUSE
    assert provenance.allowed_for_training is True
    assert provenance.confidence == pytest.approx(0.85)
    assert provenance.content_hash != ""
    assert provenance.source_license == "CC0-1.0"


def test_extract_parent_dir_ingests_all_child_scenarios() -> None:
    adapter = CloudforgeScenarioAdapter()
    records = adapter.extract(_source_entry(), _FIXTURES)

    raw_ids = {r.raw_id for r in records}
    assert raw_ids == {"path-critical-01", "path-critical-pde-01"}


def test_extract_missing_scenario_dir_raises_cloudforge_error(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    adapter = CloudforgeScenarioAdapter()

    with pytest.raises(CloudforgeError):
        adapter.extract(_source_entry(), missing)


def test_extract_incomplete_scenario_dir_raises_cloudforge_error(tmp_path: Path) -> None:
    incomplete = tmp_path / "incomplete-scenario"
    incomplete.mkdir()
    (incomplete / "scenario.yaml").write_text(
        (_CI_CD_DIR / "scenario.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    # graph.json / expected_findings.json / ground_truth_paths.json are missing.
    adapter = CloudforgeScenarioAdapter()

    with pytest.raises(CloudforgeError):
        adapter.extract(_source_entry(), incomplete)


def test_extract_empty_parent_dir_returns_no_records(tmp_path: Path) -> None:
    empty_parent = tmp_path / "empty-out"
    empty_parent.mkdir()
    adapter = CloudforgeScenarioAdapter()

    records = adapter.extract(_source_entry(), empty_parent)

    assert records == []


def test_adapter_satisfies_pattern_adapter_protocol() -> None:
    from app.cloudforge.learn.adapters.base import PatternAdapter

    assert isinstance(CloudforgeScenarioAdapter(), PatternAdapter)
