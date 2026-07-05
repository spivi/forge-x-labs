"""Adversarial graph-field corpus — the single source of hostile values (FXL-N2).

A dedicated regression corpus that locks in the emitter hardening from FXL-35 (HCL
``${}`` / ``%{}`` interpolation neutralization in :func:`hcl_str`) and FXL-39
(resource-LABEL ``node.id`` sanitization in :func:`resource_name`). Every value here
is applied to every untrusted string sink by the corpus test modules; the contract is
that each value is EITHER rendered inert (safe under real ``terraform validate``) OR
rejected with a clear cloudforge validation error.

The corpus lives in ``conftest.py`` so it is importable as a plain module *and*
exposed as pytest fixtures; the test modules import :data:`HOSTILE_VALUES` directly
(a single source) and reference it by name for readable parametrize ids.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import pytest


@dataclass(frozen=True)
class HostileValue:
    """One adversarial corpus entry: a stable id and the raw hostile payload."""

    id: str
    value: str


# The corpus. Each entry is a hostile value an untrusted graph field might carry.
# Grouped by the attack class it exercises; kept flat so every test iterates it whole.
HOSTILE_VALUES: tuple[HostileValue, ...] = (
    # --- HCL interpolation / template directive openers (FXL-35 regression-lock) ---
    HostileValue("interp_local_ref", "${local.fake_account_id}"),
    HostileValue("interp_data_ref", "${data.nonexistent.thing.value}"),
    HostileValue("template_if", "%{ if true }evil%{ endif }"),
    HostileValue("template_for", "%{ for x in [1,2] }${x}%{ endfor }"),
    HostileValue("already_escaped_interp", "$${local.already}"),
    # --- string-literal breakout attempts -----------------------------------------
    HostileValue("quote_brace_breakout", 'x" } evil {'),
    HostileValue(
        "resource_injection",
        'a" { resource "aws_iam_role" "PWNED" {} }',
    ),
    HostileValue(
        "multiline_resource_injection",
        'pwned"\n}\nresource "aws_iam_role" "injected" {\n  name = "x',
    ),
    # --- path / traversal ----------------------------------------------------------
    HostileValue("path_traversal", "../../escape"),
    # --- whitespace / control chars ------------------------------------------------
    HostileValue("name_with_spaces", "name with spaces"),
    HostileValue("newline", "line1\nline2"),
    HostileValue("tab", "col1\tcol2"),
    HostileValue("null_byte", "before\x00after"),
    # --- unicode / confusables -----------------------------------------------------
    HostileValue("accented", "café"),
    HostileValue("cjk", "日本"),
    HostileValue("emoji", "😀"),
    HostileValue("cyrillic_lookalike", "аdmin"),  # leading char is Cyrillic U+0430
    # --- size / emptiness ----------------------------------------------------------
    HostileValue("label_256", "A" * 256),
    HostileValue("empty", ""),
    # --- null-like sentinels -------------------------------------------------------
    HostileValue("null_literal", "null"),
    HostileValue("none_literal", "None"),
    HostileValue("tilde_yaml_null", "~"),
    # --- Terraform reserved keywords -----------------------------------------------
    HostileValue("kw_provider", "provider"),
    HostileValue("kw_resource", "resource"),
    HostileValue("kw_variable", "variable"),
    HostileValue("kw_locals", "locals"),
)


def hostile_ids() -> list[str]:
    """Stable parametrize ids so a failing corpus row names the payload class."""
    return [h.id for h in HOSTILE_VALUES]


@pytest.fixture(params=HOSTILE_VALUES, ids=hostile_ids())
def hostile(request: pytest.FixtureRequest) -> HostileValue:
    """Parametrized fixture yielding each corpus entry in turn."""
    return request.param  # type: ignore[no-any-return]


@pytest.fixture
def corpus() -> Iterator[HostileValue]:
    """The whole corpus as an iterable (for tests that fan one scenario over all)."""
    return iter(HOSTILE_VALUES)
