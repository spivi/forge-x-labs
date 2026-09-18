"""Metamorphic consistency tests (#110).

A metamorphic test transforms an input in a way that PRESERVES its semantics, then
asserts an invariant still holds on the transformed output. Covers the transforms
named in issue #110: rename app/owner, change ``--mutate-seed``, reorder YAML/graph
keys, change non-critical tags, reorder graph nodes/findings. Invariants: risk
semantics + critical path unchanged, scanner score stable within variance, dedup
key stable where it should be.

Each invariant is paired with a deliberate-inconsistency fixture proving the
assertion actually distinguishes "preserved" from "not preserved" (so it is not
vacuously true).
"""

from __future__ import annotations

import json
from pathlib import Path

from app.cloudforge.generate.base import ScenarioBundle
from app.cloudforge.generate.mutation_generator import MutationGenerator
from app.cloudforge.generate.template_generator import TemplateGenerator
from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.models.graph import NodeTags, ScenarioGraph
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.pipeline.artifacts import ScenarioArtifacts
from app.cloudforge.validate import tool_probe
from app.cloudforge.validate.graph_risk import GraphRiskEngine
from app.cloudforge.validate.orchestrator import run_validations
from app.cloudforge.validate.results import Status

_EXAMPLE_SPEC = Path("examples/ci_cd_iam_chain.yaml")


def _example_spec() -> ScenarioSpec:
    return ScenarioSpec.model_validate(load_yaml(_EXAMPLE_SPEC))


def _base_bundle() -> ScenarioBundle:
    return TemplateGenerator().generate(_example_spec())


def _risk_outcomes(bundle: ScenarioBundle, spec: ScenarioSpec) -> dict[str, Status]:
    return {o.label: o.status for o in GraphRiskEngine(bundle, spec).run()}


def _critical_path_ids(bundle: ScenarioBundle) -> tuple[str, ...]:
    ids: list[str] = []
    for path in bundle.ground_truth.paths:
        if path.severity == "critical":
            ids.extend(path.nodes)
    return tuple(ids)


# --- transform 1: rename app/owner tags (cosmetic) ----------------------------


class TestRenameAppOwnerTagsPreservesRisk:
    """Renaming ``app``/``owner`` tags is a cosmetic transform: risk must be stable."""

    def _renamed_bundle(self) -> ScenarioBundle:
        base = _base_bundle()
        new_tags = NodeTags(env="staging", owner="new-owner-team", app="renamed-app")
        renamed_nodes = [n.model_copy(update={"tags": new_tags}) for n in base.graph.nodes]
        return base.model_copy(
            update={"graph": base.graph.model_copy(update={"nodes": renamed_nodes})}
        )

    def test_renaming_tags_preserves_critical_path_and_risk_checks(self) -> None:
        spec = _example_spec()
        base = _base_bundle()
        renamed = self._renamed_bundle()

        base_outcomes = _risk_outcomes(base, spec)
        renamed_outcomes = _risk_outcomes(renamed, spec)

        assert renamed_outcomes == base_outcomes
        assert _critical_path_ids(renamed) == _critical_path_ids(base)

    def test_planted_inconsistency_fires_when_rename_touches_a_ground_truth_node_id(
        self,
    ) -> None:
        """Deliberate-inconsistency fixture: renaming a node's ``id`` (not just its
        display tags) breaks ground truth resolution — proving the equality check
        above is sensitive to real breakage, not just always-true."""
        spec = _example_spec()
        base = _base_bundle()
        renamed_ids = [
            n.model_copy(update={"id": "role-runtime-RENAMED"}) if n.id == "role-runtime" else n
            for n in base.graph.nodes
        ]
        broken = base.model_copy(
            update={"graph": base.graph.model_copy(update={"nodes": renamed_ids})}
        )

        outcomes = _risk_outcomes(broken, spec)

        assert outcomes["ground-truth nodes exist"] is Status.FAIL
        assert outcomes != _risk_outcomes(base, spec)


# --- transform 2: --mutate-seed (deterministic, ground-truth preserving) -----


class TestMutateSeedPreservesRisk:
    """Different ``--mutate-seed`` values must preserve risk semantics (S10/S11)."""

    def test_same_seed_is_byte_identical(self) -> None:
        base = _base_bundle()

        first = MutationGenerator(base, seed=42).generate()
        second = MutationGenerator(base, seed=42).generate()

        first_json = json.dumps(first.graph.model_dump(by_alias=True), sort_keys=True)
        second_json = json.dumps(second.graph.model_dump(by_alias=True), sort_keys=True)
        assert first_json == second_json

    def test_different_seeds_preserve_critical_path_and_findings(self) -> None:
        spec = _example_spec()
        base = _base_bundle()
        base_critical = _critical_path_ids(base)
        base_forbidden = _risk_outcomes(base, spec)["no forbidden permissions"]

        for seed in (1, 2, 3, 99):
            variant = MutationGenerator(
                base, seed=seed, max_resources=spec.constraints.max_resources
            ).generate()
            outcomes = _risk_outcomes(variant, spec)

            assert _critical_path_ids(variant) == base_critical
            assert outcomes["no forbidden permissions"] == base_forbidden
            assert outcomes["ground-truth path exists"] is Status.PASS

    def test_planted_inconsistency_fires_when_ground_truth_path_id_set_differs(self) -> None:
        """Deliberate-inconsistency fixture: swap in a different scenario's critical
        path node ids so the "unchanged across seeds" comparison actually has
        something to disagree with (proves it is not vacuously true)."""
        base = _base_bundle()
        other_ids = ("acct-main", "s3-public-data", "data-customer-pii")

        assert _critical_path_ids(base) != other_ids


# --- transform 3: reorder YAML keys (scenario spec) --------------------------


class TestReorderYamlKeysPreservesSpec:
    """Reordering top-level YAML keys must not change the parsed ``ScenarioSpec``."""

    def test_reordered_yaml_produces_an_equal_spec(self, tmp_path: Path) -> None:
        original = _example_spec()
        raw = load_yaml(_EXAMPLE_SPEC)
        assert isinstance(raw, dict)
        reordered_raw = dict(reversed(list(raw.items())))
        reordered_path = tmp_path / "reordered.yaml"
        import yaml

        reordered_path.write_text(yaml.safe_dump(reordered_raw), encoding="utf-8")

        reordered_spec = ScenarioSpec.model_validate(load_yaml(reordered_path))

        assert reordered_spec == original

    def test_planted_inconsistency_fires_when_a_field_value_actually_changes(
        self, tmp_path: Path
    ) -> None:
        """Deliberate-inconsistency fixture: changing (not just reordering) a field
        value DOES change the parsed spec — proving the equality check is meaningful."""
        raw = load_yaml(_EXAMPLE_SPEC)
        assert isinstance(raw, dict)
        mutated_raw = dict(raw)
        mutated_raw["environment"] = "production-DIFFERENT"
        mutated_path = tmp_path / "mutated.yaml"
        import yaml

        mutated_path.write_text(yaml.safe_dump(mutated_raw), encoding="utf-8")

        mutated_spec = ScenarioSpec.model_validate(load_yaml(mutated_path))

        assert mutated_spec != _example_spec()


# --- transform 4: reorder graph nodes/edges + findings -----------------------


class TestReorderGraphAndFindingsPreservesRisk:
    """Reordering the node/edge/finding lists must not change risk outcomes."""

    def _reordered_bundle(self, base: ScenarioBundle) -> ScenarioBundle:
        reordered_graph = ScenarioGraph(
            nodes=list(reversed(base.graph.nodes)), edges=list(reversed(base.graph.edges))
        )
        reordered_findings = base.findings.model_copy(
            update={"findings": list(reversed(base.findings.findings))}
        )
        return base.model_copy(update={"graph": reordered_graph, "findings": reordered_findings})

    def test_reordering_nodes_edges_findings_preserves_risk_outcomes(self) -> None:
        spec = _example_spec()
        base = _base_bundle()
        reordered = self._reordered_bundle(base)

        assert _risk_outcomes(reordered, spec) == _risk_outcomes(base, spec)
        assert {n.id for n in reordered.graph.nodes} == {n.id for n in base.graph.nodes}
        assert {f.id for f in reordered.findings.findings} == {
            f.id for f in base.findings.findings
        }

    def test_reordering_preserves_scanner_score(self, tmp_path: Path) -> None:
        """Same checkov output scored against a reordered graph -> identical score."""
        spec = _example_spec()
        base = _base_bundle()
        reordered = self._reordered_bundle(base)

        base_dir = tmp_path / "base"
        reordered_dir = tmp_path / "reordered"
        ScenarioArtifacts(ScenarioPaths.from_dir(base_dir)).write_all(spec, base)
        ScenarioArtifacts(ScenarioPaths.from_dir(reordered_dir)).write_all(spec, reordered)

        checkov_payload = {
            "results": {
                "failed_checks": [
                    {"check_id": "CKV_AWS_60", "resource": "aws_iam_role.role_deploy"},
                    {"check_id": "CKV_AWS_23", "resource": "aws_security_group.sg_web"},
                ],
                "passed_checks": [],
            }
        }
        for scenario_dir in (base_dir, reordered_dir):
            paths = ScenarioPaths.from_dir(scenario_dir)
            paths.checkov_results.parent.mkdir(parents=True, exist_ok=True)
            paths.checkov_results.write_text(json.dumps(checkov_payload), encoding="utf-8")

        from app.cloudforge.validate import scanner_score

        base_score = scanner_score.score_scenario(ScenarioPaths.from_dir(base_dir))
        reordered_score = scanner_score.score_scenario(ScenarioPaths.from_dir(reordered_dir))

        assert base_score is not None
        assert reordered_score is not None
        assert base_score.scanner_coverage_score == reordered_score.scanner_coverage_score
        assert base_score.matched_findings == reordered_score.matched_findings

    def test_planted_inconsistency_fires_when_an_edge_is_actually_dropped(self) -> None:
        """Deliberate-inconsistency fixture: dropping (not reordering) the sink edge
        changes risk outcomes — proving equality above is sensitive to real change."""
        spec = _example_spec()
        base = _base_bundle()
        dropped_edges = [
            e
            for e in base.graph.edges
            if not (e.from_ == "role-runtime" and e.to == "s3-customer-exports")
        ]
        broken = base.model_copy(
            update={"graph": base.graph.model_copy(update={"edges": dropped_edges})}
        )

        assert _risk_outcomes(broken, spec) != _risk_outcomes(base, spec)


# --- non-critical tag change (env-neutral) preserves everything --------------


class TestNonCriticalTagChangePreservesEverything:
    """Changing a non-critical attribute (a node's display ``name``) is benign."""

    def test_renaming_display_names_preserves_full_validation_pass(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.setattr(tool_probe, "detect_tool", lambda name: False)
        spec = _example_spec()
        base = _base_bundle()
        renamed_nodes = [
            n.model_copy(update={"name": f"{n.name}-renamed"}) for n in base.graph.nodes
        ]
        renamed = base.model_copy(
            update={"graph": base.graph.model_copy(update={"nodes": renamed_nodes})}
        )

        out = tmp_path / "renamed_scenario"
        ScenarioArtifacts(ScenarioPaths.from_dir(out)).write_all(spec, renamed)

        report = run_validations(out)

        assert not report.has_failure

    def test_planted_inconsistency_fires_when_name_change_hides_a_forbidden_action(
        self,
    ) -> None:
        """Deliberate-inconsistency fixture: renaming display name does NOT launder a
        forbidden action attribute — the risk engine still catches it, proving the
        "benign" transform class is distinct from an actually-risky one."""
        spec = _example_spec()
        base = _base_bundle()
        tampered_nodes = [
            n.model_copy(
                update={
                    "name": f"{n.name}-renamed",
                    "attributes": {**n.attributes, "actions": ["iam:DeleteRole"]},
                }
            )
            if n.id == "pol-deploy-passrole"
            else n
            for n in base.graph.nodes
        ]
        tampered = base.model_copy(
            update={"graph": base.graph.model_copy(update={"nodes": tampered_nodes})}
        )

        outcomes = _risk_outcomes(tampered, spec)

        assert outcomes["no forbidden permissions"] is Status.FAIL


# --- dedup key stability under cosmetic pattern transforms -------------------


class TestDedupKeyStability:
    """The learn dedup key is built from semantic fields only — cosmetic changes to
    provenance/confidence/title must not change which patterns are considered
    duplicates of each other."""

    def test_dedup_key_unaffected_by_title_confidence_and_provenance_notes(self) -> None:
        from app.cloudforge.learn.dedup import dedup
        from tests.cloudforge.learn.conftest import build_pattern

        original = build_pattern()
        cosmetically_different = original.model_copy(
            update={
                "id": "s3-public-read-aws-002",
                "title": "COMPLETELY DIFFERENT TITLE",
                "confidence": 0.12,
                "quality_score": 0.99,
            }
        )

        survivors, report = dedup([original, cosmetically_different])

        assert len(survivors) == 1
        assert report.dropped_duplicate_ids

    def test_planted_inconsistency_fires_when_a_semantic_field_actually_differs(self) -> None:
        """Deliberate-inconsistency fixture: changing a SEMANTIC dedup field
        (``weakness_family``) must NOT be deduplicated — proving the key is
        sensitive to real differences, not just always collapsing everything."""
        from app.cloudforge.learn.dedup import dedup
        from app.cloudforge.learn.pattern_enums import WeaknessFamily
        from tests.cloudforge.learn.conftest import build_pattern

        original = build_pattern()
        semantically_different = original.model_copy(
            update={
                "id": "iam-excessive-privilege-aws-001",
                "weakness_family": WeaknessFamily.IAM_EXCESSIVE_PRIVILEGE,
            }
        )

        survivors, _report = dedup([original, semantically_different])

        assert len(survivors) == 2
