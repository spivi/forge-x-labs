"""Registry of fragment kinds and namespace mappings for GraphComposer."""

from __future__ import annotations

CORE_KINDS: dict[str, str] = {
    "ci_cd_iam_chain": "core.ci_cd_iam_chain",
    "public_data_exposure": "core.public_data_exposure",
    "cross_account_trust": "core.cross_account_trust",
    "kms_key_overbroad": "core.kms_key_overbroad",
    "public_ebs_snapshot": "core.public_ebs_snapshot",
    "iam_privesc_policy_version": "core.iam_privesc_policy_version",
    "ec2_imds_credential_exfil": "core.ec2_imds_credential_exfil",
    "lambda_public_function_url": "core.lambda_public_function_url",
    "secretsmanager_policy_overbroad": "core.secretsmanager_policy_overbroad",
    "public_rds_instance": "core.public_rds_instance",
    "ecr_repository_public_read": "core.ecr_repository_public_read",
    "sqs_queue_overbroad_policy": "core.sqs_queue_overbroad_policy",
    "k8s_pod_irsa_exfil": "core.k8s_pod_irsa_exfil",
    "azure_imds_keyvault_harvest": "core.azure_imds_keyvault_harvest",
    "gcp_workload_identity_federation": "core.gcp_workload_identity_federation",
}

NOISE_KINDS: tuple[str, ...] = (
    "benign_noise.unrelated_bucket",
    "benign_noise.sqs_queue",
    "benign_noise.kms_key",
    "benign_noise.iam_role",
    "benign_noise.ecr_repo",
    "benign_noise.data_set",
    "benign_noise.log_trail",
)

EXTRA_KINDS: tuple[str, ...] = (
    "decoy.iam_role_dead_end",
    "false_positive.public_denied_bucket",
    "compensating_control.explicit_deny",
)

SHORT: dict[str, str] = {
    "core.ci_cd_iam_chain": "core",
    "core.public_data_exposure": "core",
    "core.cross_account_trust": "core",
    "core.kms_key_overbroad": "core",
    "core.public_ebs_snapshot": "core",
    "core.iam_privesc_policy_version": "core",
    "core.ec2_imds_credential_exfil": "core",
    "core.lambda_public_function_url": "core",
    "core.secretsmanager_policy_overbroad": "core",
    "core.public_rds_instance": "core",
    "core.ecr_repository_public_read": "core",
    "core.sqs_queue_overbroad_policy": "core",
    "core.k8s_pod_irsa_exfil": "core",
    "core.azure_imds_keyvault_harvest": "core",
    "core.gcp_workload_identity_federation": "core",
    "decoy.iam_role_dead_end": "decoy",
    "false_positive.public_denied_bucket": "fp",
    "compensating_control.explicit_deny": "ctrl",
    "benign_noise.unrelated_bucket": "noise",
    "benign_noise.sqs_queue": "noise",
    "benign_noise.kms_key": "noise",
    "benign_noise.iam_role": "noise",
    "benign_noise.ecr_repo": "noise",
    "benign_noise.data_set": "noise",
    "benign_noise.log_trail": "noise",
}
