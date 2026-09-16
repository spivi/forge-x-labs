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
