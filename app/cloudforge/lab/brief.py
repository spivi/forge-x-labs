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
        "An external AWS account is trusted into this environment. Can it access "
        "sensitive customer data?"
    ),
    "kms_key_overbroad": (
        "A customer data store is encrypted with KMS. Can unauthorized or external "
        "principals decrypt the contents?"
    ),
    "public_ebs_snapshot": (
        "An EBS snapshot exists in this account. Can unauthorized external parties "
        "create volumes and extract data?"
    ),
    "iam_privesc_policy_version": (
        "An internal developer identity has been provisioned with limited scope. "
        "Can it escalate privileges to access sensitive financial data?"
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
        "Does the resource policy allow external access?"
    ),
    "public_rds_instance": (
        "A production relational database has been deployed. Is it exposed to "
        "internet traffic or properly isolated in private subnets?"
    ),
    "ecr_repository_public_read": (
        "A container repository hosts application images. Can external parties "
        "pull proprietary container layers?"
    ),
    "sqs_queue_overbroad_policy": (
        "An event queue handles transaction messages. Can unauthorized external "
        "parties read or inject messages?"
    ),
}

_DEFAULT_PROMPT = (
    "Investigate this estate. Find any identity-to-data risk path. "
    "Not every finding-shaped resource is a true positive."
)


def render_brief(spec: ScenarioSpec, graph: ScenarioGraph) -> str:
    """Markdown brief listing resources and relationships without the key."""
    estate = strip_graph(graph)
    profile = spec.company_profile
    lines = [
        f"# Lab — `{spec.scenario_type}`",
        "",
        f"{profile.type} / {profile.size} / `{profile.app_name}` · {spec.environment}",
        "",
        "## Your job",
        "",
        _PROMPTS.get(spec.scenario_type, _DEFAULT_PROMPT),
        "",
        "## Resources",
        "",
    ]
    for node in estate["nodes"]:
        lines.append(f"- `{node['id']}` — **{node['type']}** {node['name']}")
    lines.extend(["", "## Relationships", ""])
    for edge in estate["edges"]:
        lines.append(f"- `{edge['from']}` --{edge['type']}--> `{edge['to']}`")
    text = "\n".join(lines) + "\n"
    if _LEAK_EDGE in text:
        text = text.replace(_LEAK_EDGE, "linked-role")
    return text
