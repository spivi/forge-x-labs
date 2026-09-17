"""The README's scenario-family table must match the fragment registry.

``scripts/render_family_table.py`` is the only place that turns the registry
into the table; this test holds the README to its output so the two can
never silently drift apart.
"""

from __future__ import annotations

from pathlib import Path

from scripts.render_family_table import updated_readme

_README = Path(__file__).resolve().parents[2] / "README.md"


def test_readme_family_table_matches_the_registry() -> None:
    current = _README.read_text(encoding="utf-8")
    assert updated_readme(current) == current, (
        "README scenario-family table is out of date; run "
        "PYTHONPATH=. .venv/bin/python scripts/render_family_table.py"
    )
