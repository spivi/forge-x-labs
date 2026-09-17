"""Typed, addressable fragment vocabulary the composer assembles scenarios from.

Every ``core_*.py`` module in this package is imported here, at package-import
time, so a new core family is discovered by adding its module file alone: no
other module has to list it by name. Non-core kinds (``decoy``, ``false_positive``,
``compensating_control``, ``benign_noise``, the ``noncore_*`` vendor modules) are
a fixed, hand-maintained set and stay explicitly imported where they are used
(``generate/composer.py``).
"""

from __future__ import annotations

import importlib
import pkgutil


def _discover_core_fragments() -> None:
    for module_info in pkgutil.iter_modules(__path__, prefix=f"{__name__}."):
        name = module_info.name.rsplit(".", 1)[-1]
        if name.startswith("core_"):
            importlib.import_module(module_info.name)


_discover_core_fragments()
