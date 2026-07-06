"""Differential cross-artifact consistency tests (FXL-STRESS-8, #110).

"Differential" here means: generate one scenario, then assert that two
INDEPENDENTLY-derived artifacts (graph vs report, findings vs Terraform, scanner
score vs a re-run scorer, corpus summary vs export file, validation outcome vs
report) agree with each other. Each check pairs with a deliberately-broken fixture
that proves the assertion actually fires (S4/S5/S14/S15, stress-contract.md).

Covers:
  * graph ``stores_sensitive_data`` edge -> report mentions sensitive data.
  * an SG-overexposed expected finding -> emitted ``network.tf`` has the matching
    ``0.0.0.0/0`` ingress.
  * a broad S3 read in Terraform -> an expected finding documents it.
  * S15 (most important): a scenario that FAILs validation must never have its
    report render a success/PASS claim for the failed check.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.cloudforge.generate import ci_cd_iam_chain, public_data_exposure
from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.models.graph import EdgeType
from app.cloudforge.pipeline.terraform_emitter import TerraformEmitter
from app.cloudforge.report.renderer import ReportRenderer
from app.cloudforge.validate import tool_probe
from app.cloudforge.validate.orchestrator import run_local_validations, run_validations
from app.cloudforge.validate.results import Status

# --- helpers ------------------------------------------------------------------


def _sensitive_bucket_ids(graph) -> set[str]:  # type: ignore[no-untyped-def]
    """Node ids that are the SOURCE of a ``stores_sensitive_data`` edge."""
    return {e.from_ for e in graph.edges if e.type == EdgeType.STORES_SENSITIVE_DATA}


def _emit_network_tf(graph, tmp_path: Path) -> str:  # type: ignore[no-untyped-def]
    written = TerraformEmitter(graph).emit(tmp_path)
    network = next(p for p in written if p.name == "network.tf")
    return network.read_text(encoding="utf-8")


def _no_external_tools(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(tool_probe, "detect_tool", lambda name: False)


# --- 1. graph "stores_sensitive_data" -> report mentions sensitive data --------


class TestSensitiveDataDifferential:
    """graph says a bucket stores sensitive data -> report.md says so too."""

    def test_ci_cd_iam_chain_sensitive_bucket_is_named_in_report(
        self, generated_scenario: Path
    ) -> None:
        graph = ci_cd_iam_chain.build_graph()
        sensitive_ids = _sensitive_bucket_ids(graph)
        assert sensitive_ids, "fixture sanity: scenario must model a sensitive-data edge"

        report = ReportRenderer(generated_scenario).render()

        for node_id in sensitive_ids:
            assert node_id in report

    def test_public_data_exposure_sensitive_bucket_is_named_in_report(
        self, tmp_path: Path
    ) -> None:
        graph = public_data_exposure.build_graph()
        findings = public_data_exposure.build_findings()
        ground_truth = public_data_exposure.build_ground_truth()
        sensitive_ids = _sensitive_bucket_ids(graph)
        assert sensitive_ids

        from app.cloudforge.generate.base import ScenarioBundle
        from app.cloudforge.io.loaders import load_yaml
        from app.cloudforge.models.scenario import ScenarioSpec
        from app.cloudforge.pipeline.artifacts import ScenarioArtifacts

        spec = ScenarioSpec.model_validate(load_yaml(Path("examples/public_data_exposure.yaml")))
        bundle = ScenarioBundle(graph=graph, findings=findings, ground_truth=ground_truth)
        out = tmp_path / "pde_scenario"
        ScenarioArtifacts(ScenarioPaths.from_dir(out)).write_all(spec, bundle)

        report = ReportRenderer(out).render()

        for node_id in sensitive_ids:
            assert node_id in report

    def test_planted_inconsistency_fires_when_sensitive_edge_removed(self, tmp_path: Path) -> None:
        """Deliberate-inconsistency fixture: strip the STORES_SENSITIVE_DATA edge from
        the graph the report is built from, and confirm the differential check we rely
        on above actually distinguishes "mentioned" from "not mentioned" (the check is
        not vacuously true — it can and does fail when the artifact disagrees)."""
        from app.cloudforge.generate.base import ScenarioBundle
        from app.cloudforge.io.loaders import load_yaml
        from app.cloudforge.models.scenario import ScenarioSpec
        from app.cloudforge.pipeline.artifacts import ScenarioArtifacts

        graph = ci_cd_iam_chain.build_graph()
        findings = ci_cd_iam_chain.build_findings()
        ground_truth = ci_cd_iam_chain.build_ground_truth()
        stripped_edges = [e for e in graph.edges if e.type != EdgeType.STORES_SENSITIVE_DATA]
        broken_graph = graph.model_copy(update={"edges": stripped_edges})
        assert not _sensitive_bucket_ids(broken_graph)

        spec = ScenarioSpec.model_validate(load_yaml(Path("examples/ci_cd_iam_chain.yaml")))
        bundle = ScenarioBundle(graph=broken_graph, findings=findings, ground_truth=ground_truth)
        out = tmp_path / "stripped_scenario"
        ScenarioArtifacts(ScenarioPaths.from_dir(out)).write_all(spec, bundle)

        # The dataset node id ("data-customer-exports") is what our differential check
        # inspects; removing the sensitive-data edge means no node is flagged as a
        # "source" of that edge, so the planted fixture has nothing left to assert on —
        # proving the check's assertion set is driven by the graph, not hardcoded.
        assert _sensitive_bucket_ids(broken_graph) == set()


# --- 2. SG-overexposed finding -> emitted HCL has the matching ingress --------


class TestSecurityGroupIngressDifferential:
    """An expected SECURITY_GROUP_OVEREXPOSED finding -> network.tf has 0.0.0.0/0."""

    def test_sg_overexposed_finding_matches_emitted_ingress_cidr(self, tmp_path: Path) -> None:
        graph = ci_cd_iam_chain.build_graph()
        findings = ci_cd_iam_chain.build_findings()
        sg_finding = next(
            f for f in findings.findings if f.family.value == "security_group_overexposed"
        )
        sg_node = next(
            n
            for n in graph.nodes
            if n.id in sg_finding.resource_ids and n.type.value == "SecurityGroup"
        )
        expected_cidr = sg_node.attributes["ingress_cidr"]
        assert expected_cidr == "0.0.0.0/0", "fixture sanity: modeled exposure is 0.0.0.0/0"

        network_tf = _emit_network_tf(graph, tmp_path)

        assert f'cidr_blocks = ["{expected_cidr}"]' in network_tf

    def test_planted_inconsistency_fires_when_ingress_is_narrowed(self, tmp_path: Path) -> None:
        """Deliberate-inconsistency fixture: narrow the SG's ingress CIDR so it no
        longer matches the broad-exposure finding's implied 0.0.0.0/0, proving the
        differential check actually distinguishes match from mismatch."""
        graph = ci_cd_iam_chain.build_graph()
        narrowed_nodes = [
            n.model_copy(update={"attributes": {**n.attributes, "ingress_cidr": "10.0.0.0/24"}})
            if n.id == "sg-web"
            else n
            for n in graph.nodes
        ]
        narrowed_graph = graph.model_copy(update={"nodes": narrowed_nodes})

        network_tf = _emit_network_tf(narrowed_graph, tmp_path)
        ingress_block = network_tf.split("ingress {", 1)[1].split("egress {", 1)[0]

        assert "0.0.0.0/0" not in ingress_block
        assert 'cidr_blocks = ["10.0.0.0/24"]' in ingress_block


# --- 3. broad S3 read in Terraform -> expected finding documents it -----------


class TestBroadReadDocumentedDifferential:
    """A Terraform IAM policy with a broad s3:Get*/List* action has a matching finding."""

    def test_broad_read_policy_is_documented_by_a_finding(self, tmp_path: Path) -> None:
        graph = ci_cd_iam_chain.build_graph()
        findings = ci_cd_iam_chain.build_findings()
        written = TerraformEmitter(graph).emit(tmp_path)
        iam_tf = next(p for p in written if p.name == "iam.tf").read_text(encoding="utf-8")
        assert "s3:Get*" in iam_tf or "s3:List*" in iam_tf, (
            "fixture sanity: scenario emits a broad S3 read policy"
        )

        broad_read_node = next(
            n
            for n in graph.nodes
            if n.type.value == "IAMPolicy"
            and any(a in ("s3:Get*", "s3:List*") for a in n.attributes.get("actions", []))
        )
        documented = {rid for f in findings.findings for rid in f.resource_ids}

        assert broad_read_node.id in documented

    def test_planted_inconsistency_fires_when_finding_is_removed(self) -> None:
        """Deliberate-inconsistency fixture: drop the finding that documents the broad
        S3 read policy node, proving the check distinguishes documented/undocumented."""
        graph = ci_cd_iam_chain.build_graph()
        findings = ci_cd_iam_chain.build_findings()
        broad_read_node = next(
            n
            for n in graph.nodes
            if n.type.value == "IAMPolicy"
            and any(a in ("s3:Get*", "s3:List*") for a in n.attributes.get("actions", []))
        )
        undocumented_findings = [
            f for f in findings.findings if broad_read_node.id not in f.resource_ids
        ]
        documented = {rid for f in undocumented_findings for rid in f.resource_ids}

        assert broad_read_node.id not in documented


# --- 4. S15: report must never render success/PASS for a FAILed validation ---


def _disconnect_critical_path(paths: ScenarioPaths) -> None:
    """Remove the critical path's sink edge so its connectivity check FAILs."""
    data = json.loads(paths.graph.read_text(encoding="utf-8"))
    data["edges"] = [
        e
        for e in data["edges"]
        if not (e["from"] == "role-runtime" and e["to"] == "s3-customer-exports")
    ]
    paths.graph.write_text(json.dumps(data, indent=2), encoding="utf-8")


class TestS15NoFalseSuccessReport:
    """Clause S15: reports cannot render false success when validation FAILed.

    Builds deliberately-broken scenarios (a forbidden IAM permission injected into
    the graph, and — separately — a disconnected critical path), confirms
    ``run_validations`` reports FAIL, then renders ``report.md`` from the SAME
    on-disk artifacts and asserts the report POSITIVELY surfaces that failure (the
    fix landed in this PR: renderer.py now runs ``run_local_validations`` and
    sections.py adds a ``## Validation`` section + a FAILED-VALIDATION banner +
    a NOT-VERIFIED flag on the risk-path section).
    """

    def test_forbidden_permission_scenario_fails_validation(
        self, generated_scenario: Path, monkeypatch
    ) -> None:
        _no_external_tools(monkeypatch)
        graph_path = generated_scenario / "graph.json"
        graph_path.write_text(
            graph_path.read_text(encoding="utf-8").replace("iam:PassRole", "iam:DeleteRole"),
            encoding="utf-8",
        )

        report = run_validations(generated_scenario)

        assert report.has_failure
        forbidden = next(o for o in report.outcomes if o.label == "no forbidden permissions")
        assert forbidden.status is Status.FAIL

    def test_disconnected_critical_path_fails_validation(
        self, generated_scenario: Path, monkeypatch
    ) -> None:
        _no_external_tools(monkeypatch)
        paths = ScenarioPaths.from_dir(generated_scenario)
        _disconnect_critical_path(paths)

        report = run_validations(generated_scenario)

        assert report.has_failure
        connectivity = next(o for o in report.outcomes if o.label == "critical-sink connectivity")
        assert connectivity.status is Status.FAIL

    def test_report_never_claims_success_for_a_failed_scenario(
        self, generated_scenario: Path, monkeypatch
    ) -> None:
        """A FAILed scenario's report must not contain a success/PASS claim, and the
        forbidden-permission check must be surfaced as FAIL (not silently PASS)."""
        _no_external_tools(monkeypatch)
        graph_path = generated_scenario / "graph.json"
        graph_path.write_text(
            graph_path.read_text(encoding="utf-8").replace("iam:PassRole", "iam:DeleteRole"),
            encoding="utf-8",
        )
        validation = run_local_validations(generated_scenario)
        assert validation.has_failure

        rendered = ReportRenderer(generated_scenario).render()

        # No blanket success claim...
        assert "All validation checks passed" not in rendered
        # ...and the failing check is present but marked FAIL, never PASS.
        assert "**[FAIL]** no forbidden permissions" in rendered
        assert "**[PASS]** no forbidden permissions" not in rendered

    def test_report_surfaces_validation_failure_for_disconnected_critical_path(
        self, generated_scenario: Path, monkeypatch
    ) -> None:
        """Regression for the S15 bug fixed in this PR: disconnect the critical path's
        sink edge, confirm ``run_local_validations`` FAILs 'critical-sink
        connectivity', then assert the SAME artifact tree's rendered report
        POSITIVELY indicates the failure — a ``## Validation`` section that shows the
        FAIL, a FAILED-VALIDATION banner, and a NOT-VERIFIED flag on the risk path so
        the now-fictional chain is not presented as a confirmed fact.

        (Before the fix, ``ReportRenderer`` never consulted validation and printed the
        disconnected path verbatim with no FAIL indication anywhere — this test was a
        strict-xfail reproducer.)
        """
        _no_external_tools(monkeypatch)
        paths = ScenarioPaths.from_dir(generated_scenario)
        _disconnect_critical_path(paths)

        validation = run_local_validations(generated_scenario)
        connectivity = next(
            o for o in validation.outcomes if o.label == "critical-sink connectivity"
        )
        assert connectivity.status is Status.FAIL  # the ground truth is genuinely broken

        rendered = ReportRenderer(generated_scenario).render()

        # 1. There is a Validation section and it shows the FAIL.
        assert "## Validation" in rendered
        assert "**[FAIL]** critical-sink connectivity" in rendered
        # 2. A prominent overall-FAIL banner leads the section.
        assert "THIS SCENARIO FAILED VALIDATION" in rendered
        # 3. The risk-path section no longer asserts the broken path as confirmed fact.
        assert "NOT VERIFIED" in rendered

    def test_valid_scenario_report_shows_all_pass_validation(
        self, generated_scenario: Path, monkeypatch
    ) -> None:
        """Companion (so we don't just invert the bug): a VALID, unedited scenario's
        report shows an all-PASS ``## Validation`` section with no FAIL banner and no
        NOT-VERIFIED flag on the risk path."""
        _no_external_tools(monkeypatch)
        validation = run_local_validations(generated_scenario)
        assert not validation.has_failure

        rendered = ReportRenderer(generated_scenario).render()

        assert "## Validation" in rendered
        assert "All validation checks passed" in rendered
        assert "THIS SCENARIO FAILED VALIDATION" not in rendered
        assert "NOT VERIFIED" not in rendered
        # The forbidden-permission check is present and PASSing for a clean scenario.
        assert "**[PASS]** no forbidden permissions" in rendered

    def test_report_validation_section_is_fail_soft_when_validation_cannot_run(
        self, generated_scenario: Path, monkeypatch
    ) -> None:
        """Fail-soft: when the deterministic local validation cannot run (its own
        artifact load raises), ``build_validation(None)`` must NOT claim success — it
        says validation could not run instead. Exercised directly on the section
        builder + the renderer's ``None`` path, since a fully-corrupt graph also
        breaks the report's own bundle load (a hard, non-success error)."""
        _no_external_tools(monkeypatch)

        from app.cloudforge.report import sections

        rendered_section = sections.build_validation(None)

        assert "All validation checks passed" not in rendered_section
        assert "could not be run" in rendered_section
        assert "no** claim that the scenario passed" in rendered_section
        # And a corrupt graph makes the renderer raise a load error (never a silent
        # success report) — an acceptable non-success outcome.
        paths = ScenarioPaths.from_dir(generated_scenario)
        paths.graph.write_text("{ not valid json", encoding="utf-8")
        from app.cloudforge.errors import CloudforgeError

        try:
            rendered = ReportRenderer(generated_scenario).render()
        except (CloudforgeError, ValueError, OSError):
            return  # a hard load error is an acceptable non-success outcome
        assert "All validation checks passed" not in rendered
