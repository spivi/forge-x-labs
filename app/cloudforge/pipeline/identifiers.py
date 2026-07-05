"""Terraform identifier sanitization for graph-derived resource labels.

The resource-LABEL position (``resource "type" "<label>"``) is a bare Terraform
identifier, not a quotable string, so :func:`hcl_str` cannot guard it. This module
maps any ``node.id`` to a Terraform-legal identifier, closing the label-breakout
surface for future generative (untrusted) node data.
"""

from __future__ import annotations

import re

from app.cloudforge.models.graph import GraphNode

# Any char outside the Terraform-legal identifier charset collapses to ``_``.
_ILLEGAL_ID_CHAR = re.compile(r"[^A-Za-z0-9_]")
# A Terraform label must start with a letter or underscore, never a digit.
_LEADING_DIGIT = re.compile(r"^[0-9]")


def resource_name(node: GraphNode) -> str:
    """A Terraform-legal local resource-label identifier for ANY ``node.id``.

    We map every char outside ``[A-Za-z0-9_]`` to ``_`` (closing the label-breakout
    surface) and guarantee a valid leading char: a Terraform label must start with a
    letter or underscore, so an empty or digit-leading result is prefixed with ``_``.
    The output always matches ``^[A-Za-z_][A-Za-z0-9_]*$``.
    """
    sanitized = _ILLEGAL_ID_CHAR.sub("_", node.id)
    if not sanitized or _LEADING_DIGIT.match(sanitized):
        return f"_{sanitized}"
    return sanitized
