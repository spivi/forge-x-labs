"""Package-skeleton test: every §5 module (real + stub) imports cleanly.

The foundation ticket ships stub homes for later tickets; this proves the whole
``app/cloudforge/learn/`` tree is importable so later tickets have valid landing spots.
"""

from __future__ import annotations

import importlib

import pytest

_MODULES = [
    "app.cloudforge.learn",
    "app.cloudforge.learn.pattern_models",
    "app.cloudforge.learn.source_models",
    "app.cloudforge.learn.registry",
    "app.cloudforge.learn.fetch",
    "app.cloudforge.learn.normalizer",
    "app.cloudforge.learn.validate",
    "app.cloudforge.learn.dedup",
    "app.cloudforge.learn.quality",
    "app.cloudforge.learn.corpus",
    "app.cloudforge.learn.export",
    "app.cloudforge.learn.summarize",
    "app.cloudforge.learn.cli",
    "app.cloudforge.learn.adapters",
    "app.cloudforge.learn.adapters.base",
    "app.cloudforge.learn.adapters.cloudforge_scenario",
    "app.cloudforge.learn.adapters.rule_catalog_yaml",
    "app.cloudforge.learn.adapters.checkov_policy_index",
]


@pytest.mark.parametrize("module_name", _MODULES)
def test_learn_module_imports(module_name: str) -> None:
    assert importlib.import_module(module_name) is not None
