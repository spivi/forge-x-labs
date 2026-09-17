"""Student investigation brief — inventory + prompt, no answer key."""

from __future__ import annotations

from app.cloudforge.generate.fragments.base import core_meta, core_scenario_types
from app.cloudforge.lab.strip import strip_graph
from app.cloudforge.models.graph import ScenarioGraph
from app.cloudforge.models.scenario import ScenarioSpec

_LEAK_EDGE = "can_pass_role"

# The student brief prompt per family, derived from each core fragment's own
# ``prompt`` class attribute (``fragments/base.py``) instead of hand-copied here.
_PROMPTS: dict[str, str] = {st: core_meta(st).prompt for st in core_scenario_types()}

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
