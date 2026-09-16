"""The deterministic template generator.

Dispatches on ``scenario_type`` to a registered builder. New scenario families
register here; new *engines* (LLM, diffusion) implement ``ScenarioGenerator``
separately. This is the MVP's only engine.
"""

from __future__ import annotations

from collections.abc import Callable

from app.cloudforge.errors import UnknownScenarioTypeError
from app.cloudforge.generate import ci_cd_iam_chain, cross_account_trust, public_data_exposure
from app.cloudforge.generate.base import ScenarioBundle
from app.cloudforge.models.scenario import ScenarioSpec


def _build_ci_cd_iam_chain() -> ScenarioBundle:
    return ScenarioBundle(
        graph=ci_cd_iam_chain.build_graph(),
        findings=ci_cd_iam_chain.build_findings(),
        ground_truth=ci_cd_iam_chain.build_ground_truth(),
    )


def _build_public_data_exposure() -> ScenarioBundle:
    return ScenarioBundle(
        graph=public_data_exposure.build_graph(),
        findings=public_data_exposure.build_findings(),
        ground_truth=public_data_exposure.build_ground_truth(),
    )


def _build_cross_account_trust() -> ScenarioBundle:
    return ScenarioBundle(
        graph=cross_account_trust.build_graph(),
        findings=cross_account_trust.build_findings(),
        ground_truth=cross_account_trust.build_ground_truth(),
    )


_BUILDERS: dict[str, Callable[[], ScenarioBundle]] = {
    "ci_cd_iam_chain": _build_ci_cd_iam_chain,
    "public_data_exposure": _build_public_data_exposure,
    "cross_account_trust": _build_cross_account_trust,
}


class TemplateGenerator:
    """Rule-based generator: looks up a builder by ``scenario_type``."""

    def generate(self, spec: ScenarioSpec) -> ScenarioBundle:
        builder = _BUILDERS.get(spec.scenario_type)
        if builder is None:
            known = ", ".join(sorted(_BUILDERS)) or "(none)"
            raise UnknownScenarioTypeError(
                f"no generator for scenario_type={spec.scenario_type!r}; known: {known}"
            )
        return builder()
