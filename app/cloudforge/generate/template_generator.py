"""The deterministic template generator.

Dispatches on ``scenario_type`` to a registered builder. New scenario families
register here; new *engines* (LLM, diffusion) implement ``ScenarioGenerator``
separately. This is the MVP's only engine.
"""

from __future__ import annotations

from collections.abc import Callable

from app.cloudforge.errors import TemplateProjectionMissingError, UnknownScenarioTypeError
from app.cloudforge.generate import (
    ci_cd_iam_chain,
    cross_account_trust,
    ec2_imds_credential_exfil,
    ecr_repository_public_read,
    iam_privesc_policy_version,
    kms_key_overbroad,
    lambda_public_function_url,
    public_data_exposure,
    public_ebs_snapshot,
    public_rds_instance,
    secretsmanager_policy_overbroad,
    sqs_queue_overbroad_policy,
)
from app.cloudforge.generate.base import ScenarioBundle
from app.cloudforge.generate.composer_kinds import CORE_KINDS
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


def _build_kms_key_overbroad() -> ScenarioBundle:
    return ScenarioBundle(
        graph=kms_key_overbroad.build_graph(),
        findings=kms_key_overbroad.build_findings(),
        ground_truth=kms_key_overbroad.build_ground_truth(),
    )


def _build_public_ebs_snapshot() -> ScenarioBundle:
    return ScenarioBundle(
        graph=public_ebs_snapshot.build_graph(),
        findings=public_ebs_snapshot.build_findings(),
        ground_truth=public_ebs_snapshot.build_ground_truth(),
    )


def _build_iam_privesc_policy_version() -> ScenarioBundle:
    return ScenarioBundle(
        graph=iam_privesc_policy_version.build_graph(),
        findings=iam_privesc_policy_version.build_findings(),
        ground_truth=iam_privesc_policy_version.build_ground_truth(),
    )


def _build_ec2_imds_credential_exfil() -> ScenarioBundle:
    return ScenarioBundle(
        graph=ec2_imds_credential_exfil.build_graph(),
        findings=ec2_imds_credential_exfil.build_findings(),
        ground_truth=ec2_imds_credential_exfil.build_ground_truth(),
    )


def _build_lambda_public_function_url() -> ScenarioBundle:
    return ScenarioBundle(
        graph=lambda_public_function_url.build_graph(),
        findings=lambda_public_function_url.build_findings(),
        ground_truth=lambda_public_function_url.build_ground_truth(),
    )


def _build_secretsmanager_policy_overbroad() -> ScenarioBundle:
    return ScenarioBundle(
        graph=secretsmanager_policy_overbroad.build_graph(),
        findings=secretsmanager_policy_overbroad.build_findings(),
        ground_truth=secretsmanager_policy_overbroad.build_ground_truth(),
    )


def _build_public_rds_instance() -> ScenarioBundle:
    return ScenarioBundle(
        graph=public_rds_instance.build_graph(),
        findings=public_rds_instance.build_findings(),
        ground_truth=public_rds_instance.build_ground_truth(),
    )


def _build_ecr_repository_public_read() -> ScenarioBundle:
    return ScenarioBundle(
        graph=ecr_repository_public_read.build_graph(),
        findings=ecr_repository_public_read.build_findings(),
        ground_truth=ecr_repository_public_read.build_ground_truth(),
    )


def _build_sqs_queue_overbroad_policy() -> ScenarioBundle:
    return ScenarioBundle(
        graph=sqs_queue_overbroad_policy.build_graph(),
        findings=sqs_queue_overbroad_policy.build_findings(),
        ground_truth=sqs_queue_overbroad_policy.build_ground_truth(),
    )


_BUILDERS: dict[str, Callable[[], ScenarioBundle]] = {
    "ci_cd_iam_chain": _build_ci_cd_iam_chain,
    "public_data_exposure": _build_public_data_exposure,
    "cross_account_trust": _build_cross_account_trust,
    "kms_key_overbroad": _build_kms_key_overbroad,
    "public_ebs_snapshot": _build_public_ebs_snapshot,
    "iam_privesc_policy_version": _build_iam_privesc_policy_version,
    "ec2_imds_credential_exfil": _build_ec2_imds_credential_exfil,
    "lambda_public_function_url": _build_lambda_public_function_url,
    "secretsmanager_policy_overbroad": _build_secretsmanager_policy_overbroad,
    "public_rds_instance": _build_public_rds_instance,
    "ecr_repository_public_read": _build_ecr_repository_public_read,
    "sqs_queue_overbroad_policy": _build_sqs_queue_overbroad_policy,
}


class TemplateGenerator:
    """Rule-based generator: looks up a builder by ``scenario_type``.

    The template engine only covers the families with a hand-written projection
    (``_BUILDERS``); a family registered only as a core fragment (a new family
    added after v1.4.0 needs none) has no projection here and must be generated
    with ``--engine composer`` instead.
    """

    def generate(self, spec: ScenarioSpec) -> ScenarioBundle:
        builder = _BUILDERS.get(spec.scenario_type)
        if builder is not None:
            return builder()
        if spec.scenario_type in CORE_KINDS:
            raise TemplateProjectionMissingError(
                f"{spec.scenario_type!r} has no template projection; use "
                f"--engine composer (template supports: {', '.join(sorted(_BUILDERS))})"
            )
        known = ", ".join(sorted({*_BUILDERS, *CORE_KINDS})) or "(none)"
        raise UnknownScenarioTypeError(
            f"no generator for scenario_type={spec.scenario_type!r}; known: {known}"
        )
