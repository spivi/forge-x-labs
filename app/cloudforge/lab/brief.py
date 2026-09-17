"""Student investigation brief — inventory + prompt, no answer key."""

from __future__ import annotations

from app.cloudforge.lab.strip import strip_graph
from app.cloudforge.models.graph import ScenarioGraph
from app.cloudforge.models.scenario import ScenarioSpec

_LEAK_EDGE = "can_pass_role"

_PROMPTS: dict[str, str] = {
    "ci_cd_iam_chain": (
        "A CI identity deploys into this account. Can it reach sensitive customer "
        "data? Which issues are real, and which look worse than they are?"
    ),
    "public_data_exposure": (
        "Some data in this account may be reachable from the internet. Find the "
        "exposure. Not every public-looking bucket is a true positive."
    ),
    "cross_account_trust": (
        "An external AWS account is trusted into this environment. Which role does "
        "it land in, and what can that role reach from there?"
    ),
    "kms_key_overbroad": (
        "A customer data store is encrypted with a KMS key. Who can decrypt with "
        "that key, and what does the key unlock?"
    ),
    "public_ebs_snapshot": (
        "An EBS snapshot in this account may be shared more widely than intended. "
        "Which snapshot, and who can create a volume from it?"
    ),
    "iam_privesc_policy_version": (
        "An internal developer identity has been provisioned with limited scope. "
        "Can it reach a role that administers the account, and how?"
    ),
    "ec2_imds_credential_exfil": (
        "A public-facing web server is accessible from the internet. Can an attacker "
        "leverage server-side requests to steal credentials and access internal data?"
    ),
    "lambda_public_function_url": (
        "A serverless function URL has been configured. Is it protected by "
        "authentication, and what backend data can it reach?"
    ),
    "secretsmanager_policy_overbroad": (
        "Production database credentials are stored in AWS Secrets Manager. "
        "Can a principal outside this account read the secret itself?"
    ),
    "public_rds_instance": (
        "A production relational database has been deployed. Can the database "
        "itself be reached from the internet, or is it isolated in private subnets?"
    ),
    "ecr_repository_public_read": (
        "A container repository hosts application images. Can external parties "
        "pull the image, and what does it embed?"
    ),
    "sqs_queue_overbroad_policy": (
        "An event queue handles transaction messages. Can unauthorized external "
        "parties read or inject the messages in flight?"
    ),
    "k8s_pod_irsa_exfil": (
        "A pod in this cluster can talk to cloud IAM. Can that workload identity "
        "reach sensitive data, and is the hop obvious from the estate?"
    ),
    "azure_imds_keyvault_harvest": (
        "An App Service has a managed identity. Can it reach secrets or customer "
        "data that a human operator would not expect it to hold?"
    ),
    "gcp_workload_identity_federation": (
        "An external CI identity federates into this project. Can it impersonate "
        "a service account and read restricted storage?"
    ),
}

_DEFAULT_PROMPT = (
    "Investigate this estate. Find any risk path from an entry point to what an "
    "attacker reaches. Not every finding-shaped resource is a true positive."
)
_HOW_TO_ANSWER = (
    "For each path, name where it starts, what opens the way, and what the "
    "attacker reaches. That is not always data: it can be a role, a key, a "
    "secret, an image, a queue, a snapshot or a database."
)


def render_brief(spec: ScenarioSpec, graph: ScenarioGraph) -> str:
    """Markdown brief listing resources and relationships without the key."""
    estate = strip_graph(graph)
    profile = spec.company_profile
    lines = [
        f"# Lab: `{spec.scenario_type}`",
        "",
        f"{profile.type} / {profile.size} / `{profile.app_name}` · {spec.environment}",
        "",
        "## Your job",
        "",
        _PROMPTS.get(spec.scenario_type, _DEFAULT_PROMPT),
        "",
        _HOW_TO_ANSWER,
        "",
        "## Resources",
        "",
    ]
    for node in estate["nodes"]:
        lines.append(f"- `{node['id']}`: **{node['type']}** {node['name']}")
    lines.extend(["", "## Relationships", ""])
    for edge in estate["edges"]:
        lines.append(f"- `{edge['from']}` --{edge['type']}--> `{edge['to']}`")
    text = "\n".join(lines) + "\n"
    if _LEAK_EDGE in text:
        text = text.replace(_LEAK_EDGE, "linked-role")
    return text
