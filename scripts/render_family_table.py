#!/usr/bin/env python
"""Render the README's scenario-family table from the fragment registry.

Since the v1.4.0 registration collapse, a family's ``scenario_type``, teaching
point and example path all come from its core fragment's own class attributes
(``fragments/base.py``); this script is the only place that turns the registry
into the README's Markdown table, so the two can never drift out of sync
(``tests/cloudforge/test_readme_family_table.py`` asserts the README matches
this output).

Usage:
    PYTHONPATH=. .venv/bin/python scripts/render_family_table.py
    PYTHONPATH=. .venv/bin/python scripts/render_family_table.py --check
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.cloudforge.generate.fragments.base import core_meta, core_scenario_types

_README = Path(__file__).resolve().parents[1] / "README.md"
_HEADER = "| `scenario_type` | Teaching point | Example |\n|---|---|---|\n"
_START = "## Scenario families\n"


def render_table() -> str:
    """The family table body (header + one row per registered family)."""
    rows = [_HEADER]
    for scenario_type in core_scenario_types():
        teaching_point = core_meta(scenario_type).teaching_point
        rows.append(
            f"| `{scenario_type}` | {teaching_point} | `examples/{scenario_type}.yaml` |\n"
        )
    return "".join(rows)


def _split_readme(text: str) -> tuple[str, str, str]:
    """``(before, old_table, after)`` split on the ``## Scenario families``
    section: everything from the header line through the last table row."""
    start = text.index(_START) + len(_START)
    # Skip the blank line right after the section header.
    while text[start] == "\n":
        start += 1
    end = text.index("\n\n", start) + 1
    return text[: text.index(_START) + len(_START)], text[start:end], text[end:]


def updated_readme(text: str) -> str:
    before, _old_table, after = _split_readme(text)
    return f"{before}\n{render_table()}{after}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Exit 1 if the README table is out of date."
    )
    args = parser.parse_args()

    original = _README.read_text(encoding="utf-8")
    updated = updated_readme(original)
    if args.check:
        if original != updated:
            print("README scenario-family table is out of date; run without --check to fix.")
            return 1
        print("README scenario-family table is up to date.")
        return 0
    _README.write_text(updated, encoding="utf-8")
    print(f"wrote {_README}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
