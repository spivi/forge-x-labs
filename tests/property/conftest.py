"""Marks every test collected under ``tests/property/`` with ``@pytest.mark.property``.

Keeps the marker centralized (registered once here; this module only
consumes it) instead of decorating every single test function by hand.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.property


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "tests/property/" in str(item.fspath).replace("\\", "/") or "/property/" in str(
            item.fspath
        ).replace("\\", "/"):
            item.add_marker(pytest.mark.property)
