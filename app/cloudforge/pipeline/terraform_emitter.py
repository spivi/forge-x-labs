"""Emits the Terraform artifact tree from the risk graph.

A thin facade over the pure block builders. Every ``.tf`` filename in the output
contract has exactly one builder.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from app.cloudforge.io.loaders import write_text
from app.cloudforge.pipeline import terraform_blocks as blocks

_FILE_BUILDERS: dict[str, Callable[[], str]] = {
    "providers.tf": blocks.build_providers_tf,
    "variables.tf": blocks.build_variables_tf,
    "main.tf": blocks.build_main_tf,
    "iam.tf": blocks.build_iam_tf,
    "s3.tf": blocks.build_s3_tf,
    "network.tf": blocks.build_network_tf,
}


class TerraformEmitter:
    """Writes the six ``.tf`` files that make up the compiled scenario."""

    def emit(self, terraform_dir: Path) -> list[Path]:
        written: list[Path] = []
        for filename, builder in _FILE_BUILDERS.items():
            path = terraform_dir / filename
            write_text(path, builder())
            written.append(path)
        return written
