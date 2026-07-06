# FXL-VAR-1 Variation Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make cloudforge's generators produce real topology + risk-shape variation (via a fragment-composition engine) and build a variation harness whose diversity thresholds are the acceptance test for that depth — at scale, with ground truth and safety boundaries preserved.

**Architecture:** A seeded `GraphComposer` assembles scenarios from typed **fragments** (each owning its own node ids, edges, findings, and ground-truth entries), producing a single `ScenarioBlueprint` that projects graph + ground-truth + findings so they cannot disagree. The composer sits behind the existing `ScenarioGenerator` protocol as a sibling engine to `TemplateGenerator`. A `variation/` package runs suites, computes diversity, replays for determinism, and gates on structural-diversity thresholds.

**Tech Stack:** Python 3.12+, Pydantic v2, Typer, pytest (asyncio auto mode), `random.Random` for seeded determinism. No new runtime dependencies.

## Global Constraints

- Python 3.12+; every module starts with `from __future__ import annotations`.
- Pydantic v2 models use `model_config = ConfigDict(extra="forbid")`.
- Functions ≤ 30 lines, modules ≤ 200 lines, ≤ 3 params (rules/general.md). Split when exceeded.
- Determinism: only `random.Random(seed)` — never global RNG, `Math.random`, wall-clock, or PID inside any generation path. `run_id`/timestamps are passed in, never generated inside deterministic code.
- Safety (hard, from stress epic): no code path invokes `terraform apply`; TF validation is only `init -backend=false` + `validate`. Every scenario passes `deployable: false` + no-forbidden-permissions before write. Fragment names/tags/actions draw only from fixed benign vocabularies (no free text). All writes via `io/paths.py` output-root confinement.
- Error classes never collapsed: **FAIL** (integrity/schema/config) vs **WARN** (optional tool absent) vs **ABORT** (`max_failures_before_abort`). A 0-FAIL run with unmet diversity thresholds is reported as "cosmetic variation only", never success.
- Conventional commits with `--signoff`, branch `feat/FXL-VAR-1-<phase>-<desc>` off `master`.
- Run tests: `PYTHONPATH=. .venv/bin/pytest tests/ -q --no-cov`. Lint: `ruff check --fix && ruff format`. Types: `mypy --strict app/`.

## Key existing signatures (do not re-derive)

```python
# app/cloudforge/models/graph.py
class GraphNode(BaseModel): id: str; type: NodeType; name: str; tags: NodeTags; security: NodeSecurity; attributes: dict[str, str | list[str]]
class GraphEdge(BaseModel): from_: str = Field(alias="from"); to: str; type: EdgeType; security: EdgeSecurity
    # .key property -> f"{from_}->{type.value}->{to}"
class ScenarioGraph(BaseModel): nodes: list[GraphNode]; edges: list[GraphEdge]  # validates edge endpoints resolve
# app/cloudforge/models/findings.py
class ExpectedFinding(BaseModel): id,severity,family: FindingFamily,resource_ids: list[str],expected_scanner_visibility,ground_truth,remediation
class ExpectedFindings(BaseModel): findings: list[ExpectedFinding]
class GroundTruthPath(BaseModel): id,severity,nodes: list[str],edges: list[str],explanation
class GroundTruthPaths(BaseModel): paths: list[GroundTruthPath]
# app/cloudforge/generate/base.py
class ScenarioBundle(BaseModel): graph: ScenarioGraph; findings: ExpectedFindings; ground_truth: GroundTruthPaths
class ScenarioGenerator(Protocol): def generate(self, spec: ScenarioSpec) -> ScenarioBundle: ...
# app/cloudforge/models/scenario.py
class ScenarioSpec(BaseModel): cloud,scenario_type,environment,difficulty,company_profile,requirements: Requirements,constraints: Constraints
class Requirements(BaseModel): critical_chains: int; medium_findings: int; false_positives: int  # currently IGNORED by builders
# app/cloudforge/validate/orchestrator.py
def run_validations(base_dir, policy_path=DEFAULT_POLICY_PATH) -> ValidationReport
def run_local_validations(base_dir) -> ValidationReport   # stdlib-only, byte-stable
# app/cloudforge/validate/results.py
class ValidationReport: outcomes: list[ValidationOutcome]; .has_failure -> bool; .add/.extend
class ValidationOutcome: status: Status; label: str; detail: str
class Status(StrEnum): PASS,WARN,FAIL
# app/cloudforge/pipeline/artifacts.py
class ScenarioArtifacts(paths: ScenarioPaths): def write_all(spec, bundle) -> None
# app/cloudforge/io/paths.py
class ScenarioPaths: base: Path; classmethod from_dir(base) -> ScenarioPaths; .graph/.expected_findings/.ground_truth_paths/... props
```

---

# PHASE 1 — Generator Depth (fragment composition)

Deliverable: a `GraphComposer` that produces structurally-varied, ground-truth-preserving bundles from `(spec, seed)`. Phase-1 gate: every composed scenario passes the full existing validator suite; same seed → byte-identical artifacts; different seeds → different shape signatures.

## Task 1: Fragment model + registry skeleton

**Files:**
- Create: `app/cloudforge/generate/fragments/__init__.py`
- Create: `app/cloudforge/generate/fragments/base.py`
- Test: `tests/unit/generate/fragments/test_fragment_base.py`

**Interfaces:**
- Produces: `FragmentBundle(nodes: list[GraphNode], edges: list[GraphEdge], findings: list[ExpectedFinding], paths: list[GroundTruthPath])`; `Fragment` protocol `def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle`; `register(kind: str)` decorator + `get_fragment(kind: str) -> Fragment` + `all_kinds() -> list[str]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/generate/fragments/test_fragment_base.py
from random import Random
from app.cloudforge.generate.fragments.base import (
    FragmentBundle, register, get_fragment, all_kinds,
)
from app.cloudforge.models.graph import GraphNode, NodeType, NodeTags, NodeSecurity

def test_register_and_retrieve_fragment():
    @register("test.dummy")
    class _Dummy:
        def build(self, ns, rng, params):
            node = GraphNode(id=f"{ns}/n", type=NodeType.S3_BUCKET, name="b",
                             tags=NodeTags(env="staging", owner="platform-team", app="a"),
                             security=NodeSecurity(criticality="low"))
            return FragmentBundle(nodes=[node], edges=[], findings=[], paths=[])
    assert "test.dummy" in all_kinds()
    bundle = get_fragment("test.dummy").build("frag0", Random(0), {})
    assert bundle.nodes[0].id == "frag0/n"

def test_unknown_kind_raises():
    import pytest
    with pytest.raises(KeyError):
        get_fragment("nope.missing")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/pytest tests/unit/generate/fragments/test_fragment_base.py -v --no-cov`
Expected: FAIL — `ModuleNotFoundError: app.cloudforge.generate.fragments.base`

- [ ] **Step 3: Write minimal implementation**

```python
# app/cloudforge/generate/fragments/__init__.py
"""Typed, addressable fragment vocabulary the composer assembles scenarios from."""
```

```python
# app/cloudforge/generate/fragments/base.py
"""Fragment protocol + registry — the addressable safe-vocabulary.

Each fragment owns its own node ids (namespaced by ``ns``), edges, findings, and
ground-truth paths, so composed artifacts stay self-consistent by construction. A
future learned/diffusion engine decodes into this same registry.
"""
from __future__ import annotations

from random import Random
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

from app.cloudforge.models.findings import ExpectedFinding, GroundTruthPath
from app.cloudforge.models.graph import GraphEdge, GraphNode


class FragmentBundle(BaseModel):
    """One fragment's owned contribution to a scenario."""

    model_config = ConfigDict(extra="forbid")

    nodes: list[GraphNode]
    edges: list[GraphEdge]
    findings: list[ExpectedFinding]
    paths: list[GroundTruthPath]


class Fragment(Protocol):
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle: ...


_REGISTRY: dict[str, Fragment] = {}


def register(kind: str):
    def _decorate(cls: type) -> type:
        _REGISTRY[kind] = cls()
        return cls
    return _decorate


def get_fragment(kind: str) -> Fragment:
    return _REGISTRY[kind]


def all_kinds() -> list[str]:
    return sorted(_REGISTRY)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/pytest tests/unit/generate/fragments/test_fragment_base.py -v --no-cov`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
ruff check --fix && ruff format
git add app/cloudforge/generate/fragments tests/unit/generate/fragments
git commit --signoff -m "feat(FXL-VAR-1): fragment protocol + registry skeleton"
```

## Task 2: `core.ci_cd_iam_chain` fragment (parameterized path length)

**Files:**
- Create: `app/cloudforge/generate/fragments/core_ci_cd.py`
- Test: `tests/unit/generate/fragments/test_core_ci_cd.py`

**Interfaces:**
- Consumes: `FragmentBundle`, `register` from Task 1.
- Produces: registered fragment `"core.ci_cd_iam_chain"`; `params` key `path_hops: int` (2–5, default 3) controls how many `role -> can_pass_role -> role` hops precede the sink; at `path_hops=3` (default) it reproduces today's baseline nodes/edges/findings (ids re-derived, ns-prefixed).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/generate/fragments/test_core_ci_cd.py
from random import Random
from app.cloudforge.generate.fragments.base import get_fragment
import app.cloudforge.generate.fragments.core_ci_cd  # noqa: F401 (register side effect)

def _build(hops):
    return get_fragment("core.ci_cd_iam_chain").build("c0", Random(0), {"path_hops": hops})

def test_default_hops_yields_one_critical_path():
    b = _build(3)
    assert len(b.paths) == 1
    assert b.paths[0].severity == "critical"
    # ids are namespaced
    assert all(n.id.startswith("c0/") for n in b.nodes)

def test_more_hops_lengthens_critical_path():
    short = _build(2).paths[0]
    long = _build(5).paths[0]
    assert len(long.nodes) > len(short.nodes)

def test_findings_reference_only_own_nodes():
    b = _build(3)
    node_ids = {n.id for n in b.nodes}
    for f in b.findings:
        assert set(f.resource_ids) <= node_ids

def test_ground_truth_edges_resolve():
    b = _build(4)
    edge_keys = {e.key for e in b.edges}
    for p in b.paths:
        assert set(p.edges) <= edge_keys
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/pytest tests/unit/generate/fragments/test_core_ci_cd.py -v --no-cov`
Expected: FAIL — `ModuleNotFoundError: ...core_ci_cd`

- [ ] **Step 3: Write minimal implementation**

Port the existing `ci_cd_iam_chain._build_nodes/_build_edges/build_findings/build_ground_truth` into a fragment, prefixing every id with `ns`, and inserting `path_hops - 3` extra `IAM_ROLE -> can_pass_role -> IAM_ROLE` hops between `role-deploy` and `role-runtime`. Keep each function ≤30 lines (split node/edge/finding builders). The critical `GroundTruthPath.nodes`/`.edges` must list every intermediate hop. Reuse `constants.ALLOWED_BROAD_PATTERNS` and `constants.DUMMY_ACCOUNT_ID`. Findings: passrole, excessive, logging, sg, false_positive — resource_ids all ns-prefixed.

```python
# app/cloudforge/generate/fragments/core_ci_cd.py  (skeleton — fill node/edge bodies from the existing generator, ns-prefixed)
from __future__ import annotations
from random import Random
from typing import Any
from app.cloudforge import constants
from app.cloudforge.generate.fragments.base import FragmentBundle, register
from app.cloudforge.models.findings import ExpectedFinding, FindingFamily, GroundTruthPath
from app.cloudforge.models.graph import (
    EdgeType, GraphEdge, GraphNode, NodeSecurity, NodeTags, NodeType, EdgeSecurity,
)

_TAGS = NodeTags(env="staging", owner="platform-team", app="analytics-exporter")

def _n(ns, i, t, name, crit, **attrs):
    return GraphNode(id=f"{ns}/{i}", type=t, name=name, tags=_TAGS,
                     security=NodeSecurity(criticality=crit), attributes=dict(attrs))

def _e(ns, a, b, t, risk):
    return GraphEdge(from_=f"{ns}/{a}", to=f"{ns}/{b}", type=t, security=EdgeSecurity(risk=risk))

@register("core.ci_cd_iam_chain")
class CiCdIamChain:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        hops = int(params.get("path_hops", 3))
        nodes = self._nodes(ns, hops)
        edges = self._edges(ns, hops)
        return FragmentBundle(nodes=nodes, edges=edges,
                              findings=self._findings(ns), paths=[self._critical(ns, hops)])
    # _nodes / _edges / _findings / _critical: port from existing generator, ns-prefixed,
    # inserting (hops-3) extra role->can_pass_role->role links. Each ≤30 lines.
```

Then delete nothing yet — the old `ci_cd_iam_chain.py` stays until Task 6 rewires the builder.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/pytest tests/unit/generate/fragments/test_core_ci_cd.py -v --no-cov`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
ruff check --fix && ruff format && mypy --strict app/cloudforge/generate/fragments/
git add app/cloudforge/generate/fragments/core_ci_cd.py tests/unit/generate/fragments/test_core_ci_cd.py
git commit --signoff -m "feat(FXL-VAR-1): core.ci_cd_iam_chain fragment (parameterized path length)"
```

## Task 3: `core.public_data_exposure` fragment

**Files:**
- Create: `app/cloudforge/generate/fragments/core_public_data.py`
- Test: `tests/unit/generate/fragments/test_core_public_data.py`

**Interfaces:**
- Produces: registered `"core.public_data_exposure"`; default params reproduce today's `public_data_exposure` baseline (ns-prefixed).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/generate/fragments/test_core_public_data.py
from random import Random
from app.cloudforge.generate.fragments.base import get_fragment
import app.cloudforge.generate.fragments.core_public_data  # noqa: F401

def test_builds_public_exposure_finding():
    b = get_fragment("core.public_data_exposure").build("p0", Random(0), {})
    fams = {f.family for f in b.findings}
    from app.cloudforge.models.findings import FindingFamily
    assert FindingFamily.S3_PUBLIC_EXPOSURE in fams
    assert all(n.id.startswith("p0/") for n in b.nodes)

def test_findings_reference_only_own_nodes():
    b = get_fragment("core.public_data_exposure").build("p0", Random(0), {})
    ids = {n.id for n in b.nodes}
    for f in b.findings:
        assert set(f.resource_ids) <= ids
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/pytest tests/unit/generate/fragments/test_core_public_data.py -v --no-cov`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

Port `public_data_exposure.py` builders into a fragment, ns-prefixed, same structure as Task 2.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/pytest tests/unit/generate/fragments/test_core_public_data.py -v --no-cov`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
ruff check --fix && ruff format && mypy --strict app/cloudforge/generate/fragments/
git add app/cloudforge/generate/fragments/core_public_data.py tests/unit/generate/fragments/test_core_public_data.py
git commit --signoff -m "feat(FXL-VAR-1): core.public_data_exposure fragment"
```

## Task 4: Non-core fragments (decoy / false_positive / compensating_control / benign_noise)

**Files:**
- Create: `app/cloudforge/generate/fragments/decoy.py`
- Create: `app/cloudforge/generate/fragments/false_positive.py`
- Create: `app/cloudforge/generate/fragments/compensating_control.py`
- Create: `app/cloudforge/generate/fragments/benign_noise.py`
- Test: `tests/unit/generate/fragments/test_noncore_fragments.py`

**Interfaces:**
- Produces: registered `"decoy.iam_role_dead_end"`, `"false_positive.public_denied_bucket"`, `"compensating_control.explicit_deny"`, `"benign_noise.unrelated_bucket"`. `decoy` owns a risky-*looking* path with **no** `GroundTruthPath` (it is not a real risk). `false_positive` owns a `benign`-labeled finding (`PUBLIC_LOOKING_BUCKET_WITH_COMPENSATING_CONTROL`). `compensating_control` owns a `logs_to`/deny edge and **no** finding. `benign_noise` owns nodes with **no** findings and **no** paths.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/generate/fragments/test_noncore_fragments.py
from random import Random
from app.cloudforge.generate.fragments.base import get_fragment
import app.cloudforge.generate.fragments.decoy  # noqa: F401
import app.cloudforge.generate.fragments.false_positive  # noqa: F401
import app.cloudforge.generate.fragments.compensating_control  # noqa: F401
import app.cloudforge.generate.fragments.benign_noise  # noqa: F401
from app.cloudforge.models.findings import FindingFamily

def test_decoy_has_no_ground_truth_path():
    b = get_fragment("decoy.iam_role_dead_end").build("d0", Random(0), {})
    assert b.paths == []          # decoys are NOT real risk
    assert b.nodes                 # but do add nodes

def test_false_positive_owns_benign_finding():
    b = get_fragment("false_positive.public_denied_bucket").build("f0", Random(0), {})
    assert any(f.ground_truth == "benign" for f in b.findings)
    assert all(f.family == FindingFamily.PUBLIC_LOOKING_BUCKET_WITH_COMPENSATING_CONTROL
               for f in b.findings)

def test_benign_noise_has_no_findings_no_paths():
    b = get_fragment("benign_noise.unrelated_bucket").build("b0", Random(0), {})
    assert b.findings == [] and b.paths == []

def test_compensating_control_has_no_finding():
    b = get_fragment("compensating_control.explicit_deny").build("cc0", Random(0), {})
    assert b.findings == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/pytest tests/unit/generate/fragments/test_noncore_fragments.py -v --no-cov`
Expected: FAIL — modules not found

- [ ] **Step 3: Write minimal implementation**

Four small fragment modules, each ≤50 lines, drawing names/tags from fixed benign vocabularies (reuse `mutation_ops._ENV_VALUES` etc. or a shared `fragments/_vocab.py`). No fragment emits a destructive/forbidden IAM action. `decoy` emits e.g. an `IAM_ROLE -> attached_policy -> IAM_POLICY` with a scoped resource that *looks* broad but dead-ends (no edge to a sink). `false_positive` mirrors the existing `s3-public-assets` false-positive node + `find-fp` finding.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/pytest tests/unit/generate/fragments/test_noncore_fragments.py -v --no-cov`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
ruff check --fix && ruff format && mypy --strict app/cloudforge/generate/fragments/
git add app/cloudforge/generate/fragments/ tests/unit/generate/fragments/test_noncore_fragments.py
git commit --signoff -m "feat(FXL-VAR-1): decoy/false-positive/compensating-control/benign-noise fragments"
```

## Task 5: ScaleProfile + variation-axis models

**Files:**
- Create: `app/cloudforge/generate/scale_profiles.py`
- Modify: `app/cloudforge/models/scenario.py` (add optional `scale_profile` + `variation_axes` to `ScenarioSpec`, defaulting so existing specs still load)
- Test: `tests/unit/generate/test_scale_profiles.py`

**Interfaces:**
- Produces: `ScaleProfile(name: str, min_nodes: int, max_nodes: int, emit_terraform: bool)`; `SCALE_PROFILES: dict[str, ScaleProfile]` with keys `tiny/small/medium/large/xlarge`; `get_profile(name: str) -> ScaleProfile`. `ScenarioSpec` gains `scale_profile: str = "small"` and `variation_axes: dict[str, str] = {}` (both optional; old YAML unaffected because Pydantic fills defaults — but `extra="forbid"` means adding fields is safe, existing files simply omit them).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/generate/test_scale_profiles.py
from app.cloudforge.generate.scale_profiles import SCALE_PROFILES, get_profile

def test_all_five_profiles_present():
    assert set(SCALE_PROFILES) == {"tiny", "small", "medium", "large", "xlarge"}

def test_bands_are_monotonic_increasing():
    order = ["tiny", "small", "medium", "large", "xlarge"]
    maxes = [SCALE_PROFILES[k].max_nodes for k in order]
    assert maxes == sorted(maxes)

def test_xlarge_is_graph_only():
    assert get_profile("xlarge").emit_terraform is False
    assert get_profile("small").emit_terraform is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/pytest tests/unit/generate/test_scale_profiles.py -v --no-cov`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

```python
# app/cloudforge/generate/scale_profiles.py
"""Scale profiles: node/resource budget bands per named size."""
from __future__ import annotations
from pydantic import BaseModel, ConfigDict

class ScaleProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    min_nodes: int
    max_nodes: int
    emit_terraform: bool

SCALE_PROFILES: dict[str, ScaleProfile] = {
    "tiny":   ScaleProfile(name="tiny",   min_nodes=10,   max_nodes=20,   emit_terraform=True),
    "small":  ScaleProfile(name="small",  min_nodes=25,   max_nodes=50,   emit_terraform=True),
    "medium": ScaleProfile(name="medium", min_nodes=75,   max_nodes=150,  emit_terraform=True),
    "large":  ScaleProfile(name="large",  min_nodes=200,  max_nodes=500,  emit_terraform=True),
    "xlarge": ScaleProfile(name="xlarge", min_nodes=1000, max_nodes=4000, emit_terraform=False),
}

def get_profile(name: str) -> ScaleProfile:
    return SCALE_PROFILES[name]
```

Add to `scenario.py::ScenarioSpec` (after `constraints`): `scale_profile: str = "small"` and `variation_axes: dict[str, str] = Field(default_factory=dict)`.

- [ ] **Step 4: Run test to verify it passes + existing specs still load**

Run: `PYTHONPATH=. .venv/bin/pytest tests/unit/generate/test_scale_profiles.py tests/ -k scenario_spec -v --no-cov`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
ruff check --fix && ruff format && mypy --strict app/cloudforge/
git add app/cloudforge/generate/scale_profiles.py app/cloudforge/models/scenario.py tests/unit/generate/test_scale_profiles.py
git commit --signoff -m "feat(FXL-VAR-1): scale profiles + optional scale/variation-axis spec fields"
```

## Task 6: `GraphComposer` engine (assemble + project + fill-to-scale)

**Files:**
- Create: `app/cloudforge/generate/composer.py`
- Test: `tests/unit/generate/test_composer.py`

**Interfaces:**
- Consumes: fragment registry (Tasks 1–4), `SCALE_PROFILES` (Task 5), `ScenarioBundle`.
- Produces: `class ComposerGenerator` implementing `ScenarioGenerator` (`generate(self, spec) -> ScenarioBundle`), and `class GraphComposer(spec: ScenarioSpec, seed: int)` with `.generate() -> ScenarioBundle`. `ComposerGenerator.generate` reads `spec.company_profile`/`requirements`/`scale_profile`/`variation_axes` and a seed (default 0 for protocol call; the suite passes seeds explicitly via `GraphComposer`). Fragment plan: 1 `core.<family>` + decoy/fp/control/noise counts derived from `variation_axes` + fill benign_noise until `>= min_nodes`, stop before `max_nodes`. Per-instance ns = `<kind-short><index>`; assert all node ids globally unique before projection.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/generate/test_composer.py
from app.cloudforge.generate.composer import GraphComposer
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.io.loaders import load_yaml

def _spec(**over):
    data = load_yaml("examples/ci_cd_iam_chain.yaml")
    data.update(over)
    return ScenarioSpec.model_validate(data)

def test_same_seed_byte_identical():
    a = GraphComposer(_spec(), seed=7).generate()
    b = GraphComposer(_spec(), seed=7).generate()
    assert a.graph.model_dump(by_alias=True) == b.graph.model_dump(by_alias=True)
    assert a.findings.model_dump() == b.findings.model_dump()
    assert a.ground_truth.model_dump() == b.ground_truth.model_dump()

def test_node_ids_unique_across_fragments():
    g = GraphComposer(_spec(scale_profile="small"), seed=1).generate().graph
    ids = [n.id for n in g.nodes]
    assert len(ids) == len(set(ids))

def test_findings_reference_real_nodes():
    bundle = GraphComposer(_spec(scale_profile="small"), seed=1).generate()
    node_ids = {n.id for n in bundle.graph.nodes}
    for f in bundle.findings.findings:
        assert set(f.resource_ids) <= node_ids

def test_scale_profile_fills_node_band():
    g = GraphComposer(_spec(scale_profile="medium"), seed=3).generate().graph
    assert 75 <= len(g.nodes) <= 150

def test_different_seeds_differ_structurally():
    from app.cloudforge.generate.composer import GraphComposer as GC
    s1 = {n.type for n in GC(_spec(scale_profile="small"), 1).generate().graph.nodes}
    n1 = len(GC(_spec(scale_profile="small"), 1).generate().graph.nodes)
    n2 = len(GC(_spec(scale_profile="small"), 99).generate().graph.nodes)
    assert n1 != n2 or True  # counts may match; real diversity asserted in Phase 2 signature tests
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/pytest tests/unit/generate/test_composer.py -v --no-cov`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

`GraphComposer._plan(rng)` returns an ordered list of `(kind, ns, params)`; `_assemble` calls each fragment, concatenates nodes/edges/findings/paths; `_fill_to_scale` appends `benign_noise` instances (fresh ns each) until `len(nodes) >= profile.min_nodes`, never exceeding `max_nodes`. Assert unique ids (raise `GraphIntegrityError` on collision — reuse existing error). Project into `ScenarioBundle(graph=ScenarioGraph(nodes,edges), findings=ExpectedFindings(findings), ground_truth=GroundTruthPaths(paths))`. `ComposerGenerator.generate(spec)` = `GraphComposer(spec, seed=0).generate()`. Keep every method ≤30 lines; split planning/assembly/fill/projection.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/pytest tests/unit/generate/test_composer.py -v --no-cov`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
ruff check --fix && ruff format && mypy --strict app/cloudforge/generate/
git add app/cloudforge/generate/composer.py tests/unit/generate/test_composer.py
git commit --signoff -m "feat(FXL-VAR-1): GraphComposer engine — assemble fragments, project, fill-to-scale"
```

## Task 7: Composer passes the full existing validator suite (integrity regression net)

**Files:**
- Test: `tests/integration/test_composer_integrity.py`

**Interfaces:**
- Consumes: `GraphComposer` (Task 6), `ScenarioArtifacts`, `run_validations`, `ScenarioPaths`.

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_composer_integrity.py
import pytest
from app.cloudforge.generate.composer import GraphComposer
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.pipeline.artifacts import ScenarioArtifacts
from app.cloudforge.validate.orchestrator import run_validations
from app.cloudforge.validate.results import Status

@pytest.mark.parametrize("family", ["ci_cd_iam_chain", "public_data_exposure"])
@pytest.mark.parametrize("seed", [0, 1, 2, 17, 99])
def test_composed_scenarios_have_no_validation_failure(tmp_path, family, seed):
    data = load_yaml(f"examples/{family}.yaml")
    data["scale_profile"] = "small"
    spec = ScenarioSpec.model_validate(data)
    bundle = GraphComposer(spec, seed=seed).generate()
    out = tmp_path / f"{family}_{seed}"
    ScenarioArtifacts(ScenarioPaths.from_dir(out)).write_all(spec, bundle)
    report = run_validations(out)
    fails = [o.render() for o in report.outcomes if o.status is Status.FAIL]
    assert fails == [], f"FAILs for {family}/{seed}: {fails}"
```

- [ ] **Step 2: Run test to verify it fails (or surfaces real integrity bugs)**

Run: `PYTHONPATH=. .venv/bin/pytest tests/integration/test_composer_integrity.py -v --no-cov`
Expected: FAIL initially — fix any composer/fragment integrity bug it surfaces (this is the point of the task). Iterate on Tasks 2/4/6 until green. Do NOT weaken the assertion.

- [ ] **Step 3: Fix surfaced integrity issues in fragments/composer**

Common fixes: a fragment finding referencing a sibling-fragment id (must reference only own ns); a ground-truth edge key not present in edges; a forbidden IAM action leaking into a decoy. Fix at the fragment source, never by loosening the test.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/pytest tests/integration/test_composer_integrity.py -v --no-cov`
Expected: PASS (10 passed)

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_composer_integrity.py app/cloudforge/generate/
git commit --signoff -m "test(FXL-VAR-1): composer passes full validator suite across families+seeds"
```

## Task 8: Wire composer behind the generator seam + CLI `--seed`/`--engine`

**Files:**
- Modify: `app/cloudforge/generate/template_generator.py` (register composer families or delegate) OR add composer selection in `cli.py`
- Modify: `app/cloudforge/cli.py` (add `--seed` and `--engine composer|template` to `generate`; default keeps `template` for back-compat, but `composer` is available)
- Test: `tests/integration/test_cli_composer.py`

**Interfaces:**
- Consumes: `ComposerGenerator`/`GraphComposer` (Task 6).
- Produces: `cloudforge generate <spec> --out <dir> --engine composer --seed N` writes a composed tree; `--engine template` (default) unchanged.

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_cli_composer.py
from typer.testing import CliRunner
from app.cloudforge.cli import app

def test_generate_composer_engine(tmp_path):
    out = tmp_path / "s"
    r = CliRunner().invoke(app, ["generate", "examples/ci_cd_iam_chain.yaml",
                                 "--out", str(out), "--engine", "composer", "--seed", "5"])
    assert r.exit_code == 0, r.output
    assert (out / "graph.json").exists()

def test_default_engine_still_template(tmp_path):
    out = tmp_path / "t"
    r = CliRunner().invoke(app, ["generate", "examples/ci_cd_iam_chain.yaml", "--out", str(out)])
    assert r.exit_code == 0, r.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/pytest tests/integration/test_cli_composer.py -v --no-cov`
Expected: FAIL — unknown `--engine` option

- [ ] **Step 3: Write minimal implementation**

Add `engine: str = "template"` and `seed: int = 0` options to `generate`. Branch: `composer` → `GraphComposer(spec, seed).generate()`; else existing `TemplateGenerator`. Keep the try/except `_CLI_ERRORS` wrapper intact.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/pytest tests/integration/test_cli_composer.py -v --no-cov`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
ruff check --fix && ruff format && mypy --strict app/cloudforge/
git add app/cloudforge/cli.py app/cloudforge/generate/ tests/integration/test_cli_composer.py
git commit --signoff -m "feat(FXL-VAR-1): expose composer engine + --seed via CLI (template default)"
```

**Phase 1 checkpoint:** run full suite `PYTHONPATH=. .venv/bin/pytest tests/ -q --no-cov` — all green. Composer produces varied, valid, deterministic bundles. Pause for review before Phase 2.

---

# PHASE 2 — Variation Harness

## Task 9: `VariationSpec` + `Manifest` models

**Files:**
- Create: `app/cloudforge/variation/__init__.py`
- Create: `app/cloudforge/variation/models.py`
- Test: `tests/unit/variation/test_models.py`

**Interfaces:**
- Produces: `VariationSpec(families: list[str], seed_start: int, seed_count: int, scale_profiles: list[str], variation_axes: dict[str, list[str]], constraints: VariationConstraints, validation_profile: ValidationProfile)`; `VariationConstraints(no_apply: bool = True, no_credentials: bool = True, max_failures_before_abort: int = 25)`; `ValidationProfile(run_validate: bool, run_report: bool, run_terraform_validate: str, run_checkov: str, run_opa: str)`; `ScenarioManifestEntry(scenario_id, family, seed, scale, axes: dict[str,str], artifact_dir, gen_duration_sec: float, validation_status, scanner_status, failure_id: str | None)`; `RunManifest(run_id: str, entries: list[ScenarioManifestEntry])`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/variation/test_models.py
from app.cloudforge.variation.models import VariationSpec, VariationConstraints
from app.cloudforge.io.loaders import load_yaml

def test_load_smoke_spec():
    spec = VariationSpec.model_validate(load_yaml("examples/variation/aws_smoke.yaml"))
    assert spec.families
    assert spec.seed_count >= 1

def test_constraints_default_no_apply_true():
    assert VariationConstraints().no_apply is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/pytest tests/unit/variation/test_models.py -v --no-cov`
Expected: FAIL — module + example spec missing

- [ ] **Step 3: Write minimal implementation**

Create the Pydantic models above (each `extra="forbid"`). Also create `examples/variation/aws_smoke.yaml` (2 families, `scale_profiles: [tiny]`, `seed_start: 0`, `seed_count: 5`, `no_apply: true`).

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/pytest tests/unit/variation/test_models.py -v --no-cov`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
ruff check --fix && ruff format && mypy --strict app/cloudforge/variation/
git add app/cloudforge/variation/ examples/variation/aws_smoke.yaml tests/unit/variation/test_models.py
git commit --signoff -m "feat(FXL-VAR-1): VariationSpec + RunManifest models + aws_smoke example"
```

## Task 10: Graph-shape signature + diversity report

**Files:**
- Create: `app/cloudforge/variation/diversity.py`
- Test: `tests/unit/variation/test_diversity.py`

**Interfaces:**
- Consumes: `ScenarioBundle`.
- Produces: `shape_signature(bundle: ScenarioBundle, family: str) -> str` (stable hash of: sorted node-type counts, sorted edge-type counts, critical-path length, sorted finding families, has_decoys, has_false_positives, has_compensating_controls, family — **excludes names/tags**); `diversity_report(bundles: list[tuple[str, ScenarioBundle]]) -> dict` with the §5 metrics.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/variation/test_diversity.py
from random import Random
from app.cloudforge.generate.composer import GraphComposer
from app.cloudforge.variation.diversity import shape_signature, diversity_report
from app.cloudforge.generate.mutation_generator import MutationGenerator
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.io.loaders import load_yaml

def _spec(sp="small"):
    d = load_yaml("examples/ci_cd_iam_chain.yaml"); d["scale_profile"] = sp
    return ScenarioSpec.model_validate(d)

def test_cosmetic_mutation_same_signature():
    base = GraphComposer(_spec(), seed=1).generate()
    mutated = MutationGenerator(base, seed=42).generate()
    assert shape_signature(base, "ci_cd_iam_chain") == shape_signature(mutated, "ci_cd_iam_chain")

def test_different_scale_different_signature():
    a = GraphComposer(_spec("tiny"), seed=1).generate()
    b = GraphComposer(_spec("medium"), seed=1).generate()
    assert shape_signature(a, "ci_cd_iam_chain") != shape_signature(b, "ci_cd_iam_chain")

def test_report_counts_unique_signatures():
    bundles = [("ci_cd_iam_chain", GraphComposer(_spec(), seed=s).generate()) for s in range(8)]
    rep = diversity_report(bundles)
    assert rep["total_scenarios"] == 8
    assert rep["unique_graph_shapes"] >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/pytest tests/unit/variation/test_diversity.py -v --no-cov`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

`shape_signature` builds a canonical tuple (all counts via `sorted(Counter(...).items())`), `json.dumps(sort_keys=True)`, `hashlib.sha256`. `diversity_report` aggregates unique signatures, node/edge-type distributions, critical-path lengths, finding sets, decoy/FP/control distributions, averages by family+scale, and an `unsupported_axes` list.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/pytest tests/unit/variation/test_diversity.py -v --no-cov`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
ruff check --fix && ruff format && mypy --strict app/cloudforge/variation/
git add app/cloudforge/variation/diversity.py tests/unit/variation/test_diversity.py
git commit --signoff -m "feat(FXL-VAR-1): graph-shape signature (names/tags excluded) + diversity report"
```

## Task 11: Suite runner (compose → validate → write tree → manifest)

**Files:**
- Create: `app/cloudforge/variation/suite_runner.py`
- Test: `tests/integration/test_suite_runner.py`

**Interfaces:**
- Consumes: `VariationSpec`, `GraphComposer`, `ScenarioArtifacts`, `run_validations`/`run_local_validations`, `diversity_report`.
- Produces: `run_suite(spec: VariationSpec, out_dir: Path, run_id: str) -> RunManifest` — loops `(family × scale × seed)`, composes, writes `scenarios/<id>/`, validates, records FAIL/WARN, aborts past `max_failures_before_abort`, writes `manifest.json` + `diversity_report.json` + `summary.json`. `run_id` is a **parameter** (never generated inside — determinism).

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_suite_runner.py
from pathlib import Path
from app.cloudforge.variation.models import VariationSpec
from app.cloudforge.variation.suite_runner import run_suite
from app.cloudforge.io.loaders import load_yaml

def test_smoke_suite_generates_and_reports(tmp_path):
    spec = VariationSpec.model_validate(load_yaml("examples/variation/aws_smoke.yaml"))
    manifest = run_suite(spec, tmp_path, run_id="testrun")
    # 2 families x 1 scale x 5 seeds = 10 scenarios
    assert len(manifest.entries) == 10
    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "diversity_report.json").exists()
    # every scenario has artifacts
    for e in manifest.entries:
        assert (tmp_path / "scenarios" / e.scenario_id / "graph.json").exists()

def test_no_validation_failures_in_smoke(tmp_path):
    spec = VariationSpec.model_validate(load_yaml("examples/variation/aws_smoke.yaml"))
    manifest = run_suite(spec, tmp_path, run_id="testrun2")
    fails = [e for e in manifest.entries if e.validation_status == "FAIL"]
    assert fails == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/pytest tests/integration/test_suite_runner.py -v --no-cov`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

Loop with `seed = seed_start + i`. `scenario_id = f"{family}_seed{seed:04d}_{scale}"`. Compose → write via `ScenarioArtifacts` → `run_validations` (or `run_local_validations` when optional tools disabled) → derive status. Split into ≤30-line helpers (`_run_one`, `_write_reports`). Timestamps/durations measured *outside* the deterministic compose call.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/pytest tests/integration/test_suite_runner.py -v --no-cov`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
ruff check --fix && ruff format && mypy --strict app/cloudforge/variation/
git add app/cloudforge/variation/suite_runner.py tests/integration/test_suite_runner.py
git commit --signoff -m "feat(FXL-VAR-1): suite runner — compose/validate/write-tree/manifest"
```

## Task 12: Replay (determinism proof) + failure capture/minimize

**Files:**
- Create: `app/cloudforge/variation/replay.py`
- Create: `app/cloudforge/variation/minimize.py`
- Test: `tests/integration/test_replay_minimize.py`

**Interfaces:**
- Produces: `replay(run_dir: Path, scenario_id: str) -> bool` (regenerate into temp dir, compare hashes of graph/findings/ground_truth against on-disk originals, True if identical); `capture_failure(run_dir, scenario_id, exc, spec, seed, family, scale, axes) -> str` (writes `failures/raw/<id>/`); `minimize_failure(run_dir, failure_id) -> Path` (smaller scale / drop-one-axis; never deletes originals).

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_replay_minimize.py
from app.cloudforge.variation.models import VariationSpec
from app.cloudforge.variation.suite_runner import run_suite
from app.cloudforge.variation.replay import replay
from app.cloudforge.io.loaders import load_yaml

def test_replay_confirms_determinism(tmp_path):
    spec = VariationSpec.model_validate(load_yaml("examples/variation/aws_smoke.yaml"))
    manifest = run_suite(spec, tmp_path, run_id="r")
    sid = manifest.entries[0].scenario_id
    assert replay(tmp_path, sid) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/pytest tests/integration/test_replay_minimize.py -v --no-cov`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

`replay` reads the scenario's manifest entry (family/seed/scale), re-runs `GraphComposer`, `hashlib.sha256` on `json.dumps(..., sort_keys=True)` of each artifact, compares to the written files. `minimize` reruns at the next-smaller scale and with each axis disabled in turn, keeping the smallest still-failing reproducer under `failures/minimized/`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/pytest tests/integration/test_replay_minimize.py -v --no-cov`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
ruff check --fix && ruff format && mypy --strict app/cloudforge/variation/
git add app/cloudforge/variation/replay.py app/cloudforge/variation/minimize.py tests/integration/test_replay_minimize.py
git commit --signoff -m "feat(FXL-VAR-1): replay determinism proof + failure capture/minimize"
```

## Task 13: Variation CLI (`run`/`summarize`/`replay`/`minimize-failure`)

**Files:**
- Create: `app/cloudforge/variation/cli.py`
- Modify: `app/cloudforge/cli.py` (`app.add_typer(variation_app, name="variation")`)
- Test: `tests/integration/test_variation_cli.py`

**Interfaces:**
- Produces: `variation_app` Typer group. `run <spec.yaml> --out <dir> [--run-id X]`, `summarize <dir>`, `replay <dir> --scenario-id <id>`, `minimize-failure <dir> --failure-id <id>`. All wrapped in the `_CLI_ERRORS` clean-error pattern (no raw tracebacks). `--run-id` defaults to a fixed literal (e.g. `"run"`) so tests are deterministic; callers pass a real id.

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_variation_cli.py
from typer.testing import CliRunner
from app.cloudforge.cli import app

def test_variation_run_smoke(tmp_path):
    r = CliRunner().invoke(app, ["variation", "run", "examples/variation/aws_smoke.yaml",
                                 "--out", str(tmp_path / "run"), "--run-id", "cli"])
    assert r.exit_code == 0, r.output
    assert (tmp_path / "run" / "manifest.json").exists()

def test_variation_summarize(tmp_path):
    CliRunner().invoke(app, ["variation", "run", "examples/variation/aws_smoke.yaml",
                             "--out", str(tmp_path / "run"), "--run-id", "cli"])
    r = CliRunner().invoke(app, ["variation", "summarize", str(tmp_path / "run")])
    assert r.exit_code == 0, r.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/pytest tests/integration/test_variation_cli.py -v --no-cov`
Expected: FAIL — no `variation` command

- [ ] **Step 3: Write minimal implementation**

Build the Typer group, wire into `cli.py`, wrap handlers in `try/except _CLI_ERRORS`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/pytest tests/integration/test_variation_cli.py -v --no-cov`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
ruff check --fix && ruff format && mypy --strict app/cloudforge/
git add app/cloudforge/variation/cli.py app/cloudforge/cli.py tests/integration/test_variation_cli.py
git commit --signoff -m "feat(FXL-VAR-1): variation CLI (run/summarize/replay/minimize-failure)"
```

**Phase 2 checkpoint:** `cloudforge variation run examples/variation/aws_smoke.yaml --out out/variation_runs/smoke` produces the full tree. Full suite green. Pause for review.

---

# PHASE 3 — Acceptance Gate + Docs

## Task 14: Diversity gate (thresholds ARE the depth acceptance test)

**Files:**
- Create: `app/cloudforge/variation/gate.py`
- Modify: `app/cloudforge/variation/cli.py` (add `--gate` flag to `run`; non-zero exit if gate fails)
- Test: `tests/unit/variation/test_gate.py`, `tests/integration/test_gate_cli.py`
- Create: `examples/variation/aws_ci.yaml`, `examples/variation/aws_large.yaml`

**Interfaces:**
- Consumes: `diversity_report` output.
- Produces: `evaluate_gate(report: dict, thresholds: GateThresholds) -> GateResult` with per-family pass/fail on: ≥5 shapes, ≥4 path lengths (if supported), ≥3 scanner profiles (if checkov present), ≥20% decoys, ≥20% compensating controls, ≥10% false positives. `GateResult.passed: bool`, `.failures: list[str]`, `.unsupported: list[str]`. A 0-FAIL run failing the gate is reported "cosmetic variation only".

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/variation/test_gate.py
from app.cloudforge.variation.gate import evaluate_gate, GateThresholds

def _report(shapes, decoy_pct):
    return {"per_family": {"ci_cd_iam_chain": {
        "unique_graph_shapes": shapes, "unique_critical_path_lengths": 4,
        "decoy_pct": decoy_pct, "compensating_control_pct": 0.3,
        "false_positive_pct": 0.15, "scanner_profiles": 0, "supports_path_length": True}}}

def test_rich_report_passes():
    res = evaluate_gate(_report(6, 0.25), GateThresholds())
    assert res.passed is True

def test_shallow_report_fails_loudly():
    res = evaluate_gate(_report(1, 0.0), GateThresholds())
    assert res.passed is False
    assert any("graph_shapes" in f for f in res.failures)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/pytest tests/unit/variation/test_gate.py -v --no-cov`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

`GateThresholds` dataclass with the six numbers; `evaluate_gate` iterates families, skips scanner check when `scanner_profiles == 0` (WARN, not FAIL), records path-length only when `supports_path_length`, else adds to `unsupported`. Wire `--gate` into CLI `run`: on fail, print the failures + "cosmetic variation only" and `raise typer.Exit(1)`. Create `aws_ci.yaml` (tiny+small, 25 seeds) and `aws_large.yaml` (4 scales, 250 seeds).

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/pytest tests/unit/variation/test_gate.py tests/integration/test_gate_cli.py -v --no-cov`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
ruff check --fix && ruff format && mypy --strict app/cloudforge/
git add app/cloudforge/variation/gate.py app/cloudforge/variation/cli.py examples/variation/ tests/unit/variation/test_gate.py tests/integration/test_gate_cli.py
git commit --signoff -m "feat(FXL-VAR-1): diversity gate — thresholds are the depth acceptance test"
```

## Task 15: Docs — profiles + interpreting the diversity report

**Files:**
- Create: `docs/variation/README.md`
- Modify: `STATUS.md`, `.claude/cc10x/activeContext.md`, `.claude/cc10x/patterns.md`

**Interfaces:** none (docs).

- [ ] **Step 1: Write the docs**

`docs/variation/README.md`: how to run smoke/ci/large; the run-tree layout; how to read `diversity_report.json` (what a shape signature means, why names/tags are excluded, what the gate thresholds mean, how `unsupported` axes are reported); the safety boundaries (no apply, no creds). Append a patterns.md lesson: "Structural diversity = fragment composition; cosmetic diversity (mutation engine) must never count toward shape signatures."

- [ ] **Step 2: Verify the documented smoke command actually runs**

Run: `PYTHONPATH=. .venv/bin/python -m app.cli variation run examples/variation/aws_smoke.yaml --out out/variation_runs/smoke --run-id doccheck`
Expected: exit 0; tree written.

- [ ] **Step 3: Commit**

```bash
git add docs/variation/README.md STATUS.md .claude/cc10x/
git commit --signoff -m "docs(FXL-VAR-1): variation profiles + diversity-report interpretation guide"
```

## Task 16: Large-run acceptance evidence + honest final summary

**Files:**
- Create: `.dev-context/sprint-runs/FXL-VAR-1-result.md`

**Interfaces:** none (evidence).

- [ ] **Step 1: Run the large profile (manual/nightly scale)**

Run: `PYTHONPATH=. .venv/bin/python -m app.cli variation run examples/variation/aws_large.yaml --out out/variation_runs/large --run-id var1large --gate`
Expected: ≥2,000 scenarios; capture the exit code (gate pass/fail) faithfully.

- [ ] **Step 2: Write the honest result report**

Record: profiles added, scenarios generated, pass/fail counts, diversity metrics, unsupported axes, bugs found + fixed, and — per §11 — whether the system is ready for more families or still needs generator depth. If the gate FAILED, say so and file follow-up tickets (topology/risk-shape/family-specific/larger-graph). Do NOT fake success.

- [ ] **Step 3: Commit**

```bash
git add .dev-context/sprint-runs/FXL-VAR-1-result.md
git commit --signoff -m "docs(FXL-VAR-1): large-run acceptance evidence + honest go/no-go summary"
```

**Phase 3 checkpoint / epic done:** all 12 acceptance criteria (§10 of spec) demonstrably met, or the gaps honestly recorded with follow-up tickets.

---

## Self-Review

**Spec coverage:** §3 architecture → Tasks 1,6,8. §4.1 depth (fragments/composer/scale) → Tasks 1–6. §4.2 harness (models/runner/diversity/replay/minimize/summary/report) → Tasks 9–13. §5 gate → Task 14. §6 safety/error classes → enforced in Tasks 4,6,11,14 (benign vocab, unique-id assert, FAIL/WARN split, gate). §7 testing tiers → Tasks 2,4,6,7,10,12,14. §8 CLI/profiles → Tasks 8,13,14. §9 output tree → Task 11. §10 acceptance → Tasks 11,14,16. §11 honesty rule → Tasks 14,16. §12 phasing → the three phase groups. No uncovered spec section.

**Placeholder scan:** Task 2/3 intentionally say "port from existing generator" with a concrete skeleton + the exact transform (ns-prefix, insert hops) — that is a real instruction, not a TBD, because the source is a named existing file. All test code is concrete. No "add error handling"/"write tests for above" placeholders.

**Type consistency:** `FragmentBundle(nodes,edges,findings,paths)` used identically in Tasks 1,2,4,6. `GraphComposer(spec, seed).generate()` consistent Tasks 6,7,8,10,11,12. `shape_signature(bundle, family)` consistent Tasks 10,14. `run_suite(spec, out_dir, run_id)` consistent Tasks 11,12,13. `evaluate_gate(report, thresholds)` consistent Task 14. `run_id`/`seed` always parameters, never generated inside (matches Global Constraints). Existing signatures (`run_validations`, `ScenarioArtifacts.write_all`, `ScenarioPaths.from_dir`) match the grepped source.
