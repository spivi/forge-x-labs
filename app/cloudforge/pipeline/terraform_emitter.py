"""Emits the Terraform artifact tree from the risk graph.

A thin facade over the pure block builders. ``providers.tf`` / ``variables.tf`` /
``main.tf`` are static (family-independent); ``iam.tf`` / ``s3.tf`` / ``network.tf``
are assembled from the scenario graph nodes, so each family's compiled Terraform
matches its own resources. Every ``.tf`` filename in the output contract has exactly
one builder.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from app.cloudforge.io.loaders import write_text
from app.cloudforge.models.graph import GraphNode, ScenarioGraph
from app.cloudforge.pipeline import terraform_blocks as blocks
from app.cloudforge.pipeline.label_collisions import check_label_collisions

_STATIC_BUILDERS: dict[str, Callable[[], str]] = {
    "providers.tf": blocks.build_providers_tf,
    "variables.tf": blocks.build_variables_tf,
}

# ``main.tf`` derives ``common_tags`` from the graph, so it is graph-aware, not static.
_MAIN_FILENAME = "main.tf"

_GRAPH_BUILDERS: dict[str, Callable[[list[GraphNode]], str]] = {
    "iam.tf": blocks.build_iam_tf,
    "s3.tf": blocks.build_s3_tf,
    "network.tf": blocks.build_network_tf,
}


class TerraformEmitter:
    """Writes the six ``.tf`` files that make up the compiled scenario."""

    def __init__(self, graph: ScenarioGraph) -> None:
        self._graph = graph

    def emit(self, terraform_dir: Path) -> list[Path]:
        # Fail loud BEFORE writing any file: distinct node ids that sanitize to the
        # same per-type resource label would make ``terraform validate`` reject a
        # duplicate resource (FXL-N4).
        check_label_collisions(self._graph.nodes)
        written: list[Path] = []
        for filename, static_builder in _STATIC_BUILDERS.items():
            written.append(self._write(terraform_dir, filename, static_builder()))
        tags = blocks.derive_common_tags(self._graph.nodes)
        written.append(self._write(terraform_dir, _MAIN_FILENAME, blocks.build_main_tf(tags)))
        for filename, graph_builder in _GRAPH_BUILDERS.items():
            written.append(self._write(terraform_dir, filename, graph_builder(self._graph.nodes)))
        return written

    @staticmethod
    def _write(terraform_dir: Path, filename: str, text: str) -> Path:
        path = terraform_dir / filename
        write_text(path, text)
        return path
