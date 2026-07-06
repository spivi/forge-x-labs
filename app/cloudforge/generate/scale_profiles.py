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
    "tiny": ScaleProfile(name="tiny", min_nodes=10, max_nodes=20, emit_terraform=True),
    "small": ScaleProfile(name="small", min_nodes=25, max_nodes=50, emit_terraform=True),
    "medium": ScaleProfile(name="medium", min_nodes=75, max_nodes=150, emit_terraform=True),
    "large": ScaleProfile(name="large", min_nodes=200, max_nodes=500, emit_terraform=True),
    "xlarge": ScaleProfile(name="xlarge", min_nodes=1000, max_nodes=4000, emit_terraform=False),
}


def get_profile(name: str) -> ScaleProfile:
    return SCALE_PROFILES[name]
