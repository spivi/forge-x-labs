"""Typed filesystem read/write helpers.

Thin wrappers over ``json``/``yaml`` so callers never sprinkle encoding or
serialization details across the codebase.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from app.cloudforge.errors import ScenarioLoadError

_JSON_INDENT = 2


def load_yaml(path: Path) -> dict[str, Any]:
    """Parse a YAML mapping file, raising ScenarioLoadError on any read/parse error."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ScenarioLoadError(f"cannot read {path}: {exc}") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ScenarioLoadError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ScenarioLoadError(f"expected a mapping at the top of {path}")
    return data


def load_json(path: Path) -> dict[str, Any]:
    """Parse a JSON object file, raising ScenarioLoadError on any read/parse error."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ScenarioLoadError(f"cannot read {path}: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ScenarioLoadError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ScenarioLoadError(f"expected a JSON object at the top of {path}")
    return data


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    """Write a JSON object with stable key order and a trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=_JSON_INDENT, sort_keys=False)
    path.write_text(text + "\n", encoding="utf-8")


def dump_yaml(path: Path, payload: dict[str, Any]) -> None:
    """Write a YAML mapping preserving insertion order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(payload, sort_keys=False, default_flow_style=False)
    path.write_text(text, encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    """Write UTF-8 text, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
