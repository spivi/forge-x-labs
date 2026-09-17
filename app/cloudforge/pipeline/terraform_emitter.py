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
from app.cloudforge.pipeline import (
    terraform_azure as azure,
)
from app.cloudforge.pipeline import (
    terraform_blocks as blocks,
)
from app.cloudforge.pipeline import (
    terraform_compute as compute,
)
from app.cloudforge.pipeline import (
    terraform_database as database,
)
from app.cloudforge.pipeline import (
    terraform_gcp as gcp,
)
from app.cloudforge.pipeline import (
    terraform_k8s as k8s,
)
from app.cloudforge.pipeline import (
    terraform_providers as providers,
)
from app.cloudforge.pipeline import (
    terraform_serverless as serverless,
)
from app.cloudforge.pipeline import (
    terraform_services as services,
)
from app.cloudforge.pipeline.label_collisions import check_label_collisions

_STATIC_BUILDERS: dict[str, Callable[[], str]] = {
    "variables.tf": blocks.build_variables_tf,
}

_MAIN_FILENAME = "main.tf"
_PROVIDERS_FILENAME = "providers.tf"

_GRAPH_BUILDERS: dict[str, Callable[[list[GraphNode]], str]] = {
    "iam.tf": blocks.build_iam_tf,
    "s3.tf": blocks.build_s3_tf,
    "network.tf": blocks.build_network_tf,
    "kms.tf": blocks.build_kms_tf,
    "snapshot.tf": blocks.build_snapshot_tf,
    "compute.tf": compute.build_compute_tf,
    "serverless.tf": serverless.build_serverless_tf,
    "database.tf": database.build_database_tf,
    "services.tf": services.build_services_tf,
    "azure.tf": azure.build_azure_tf,
    "gcp.tf": gcp.build_gcp_tf,
    "k8s.tf": k8s.build_k8s_tf,
}


class TerraformEmitter:
    """Writes the compiled scenario ``.tf`` files (static + graph-driven)."""

    def __init__(self, graph: ScenarioGraph) -> None:
        self._graph = graph

    def emit(self, terraform_dir: Path) -> list[Path]:
        # Fail loud BEFORE writing any file: distinct node ids that sanitize to the
        # same per-type resource label would make ``terraform validate`` reject a
        # duplicate resource (FXL-N4).
        check_label_collisions(self._graph.nodes)
        written: list[Path] = []
        written.append(
            self._write(
                terraform_dir,
                _PROVIDERS_FILENAME,
                providers.build_providers_tf(self._graph.nodes),
            )
        )
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
