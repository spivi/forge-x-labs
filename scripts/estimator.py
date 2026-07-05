#!/usr/bin/env python3
"""Cold-start estimate + cheapest-sufficient model seeder for the learning loop.

Given a ticket's type and effort, produce:
  - estimate_minutes: base minutes (from base-estimates.yml) scaled by the
    learned calibration factor (kpis/calibration.json), clamped to sane bounds.
  - recommended_model: the cheapest model that still delivers -- the effort
    floor, up-tiered only when the learned model-policy (kpis/model-policy.json)
    shows that ticket class is underpowered. Routing never drops below the floor.

Pure functions take injected dicts (seed/calibration/policy) so they are trivial
to unit-test. Loaders fail soft: a missing calibration/policy file yields {} and
the seed table alone is used (correct behaviour on a brand-new project).

CLI:
    python scripts/estimator.py plan --type feature --effort M [--labels "a;b"]
        -> {"estimate_minutes": 120, "recommended_model": "sonnet"}
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_DEFAULT_SEED = _REPO / ".dev-context" / "planning" / "base-estimates.yml"
_DEFAULT_CALIBRATION = _REPO / ".dev-context" / "kpis" / "calibration.json"
_DEFAULT_MODEL_POLICY = _REPO / ".dev-context" / "kpis" / "model-policy.json"
_DEFAULT_TAXONOMY = _REPO / ".dev-context" / "planning" / "taxonomy.yml"

_EFFORT_RE = re.compile(r"(?:^|[;,\s])effort:(XL|[SML])\b", re.IGNORECASE)


# --- loaders (fail soft) --------------------------------------------------


def load_seed(path: str | Path | None = None) -> dict[str, Any]:
    """Load the base-estimates seed table. Missing file -> {}."""
    import yaml  # local import so pure-logic tests don't require PyYAML

    p = Path(path) if path else _DEFAULT_SEED
    if not p.exists():
        return {}
    with p.open() as f:
        return yaml.safe_load(f) or {}


def load_calibration(path: str | Path | None = None) -> dict[str, Any]:
    """Load learned calibration factors. Missing/invalid -> {}."""
    p = Path(path) if path else _DEFAULT_CALIBRATION
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text()) or {}
    except (json.JSONDecodeError, OSError):
        return {}


def load_model_policy(path: str | Path | None = None) -> dict[str, Any]:
    """Load learned model-routing policy. Missing/invalid -> {}."""
    p = Path(path) if path else _DEFAULT_MODEL_POLICY
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text()) or {}
    except (json.JSONDecodeError, OSError):
        return {}


def load_taxonomy(path: str | Path | None = None) -> dict[str, Any]:
    """Load the typed-dimension taxonomy (planning/taxonomy.yml). Missing -> {}."""
    import yaml  # local import so pure-logic tests don't require PyYAML

    p = Path(path) if path else _DEFAULT_TAXONOMY
    if not p.exists():
        return {}
    with p.open() as f:
        return yaml.safe_load(f) or {}


# --- pure logic -----------------------------------------------------------


def effort_from_labels(labels: str | list[str] | None) -> str | None:
    """Extract the effort bucket (S/M/L/XL) from a label string or list."""
    if not labels:
        return None
    text = labels if isinstance(labels, str) else ";".join(labels)
    m = _EFFORT_RE.search(text)
    return m.group(1).upper() if m else None


def dim_from_labels(labels: str | list[str] | None, prefix: str) -> str | None:
    """Generic open-vocab dimension parse: the token after `prefix` (e.g. "area:",
    "risk:", "milestone:") up to the next delimiter. Used to back-fill typed
    columns and to consult learned per-dimension policy. None if absent."""
    if not labels:
        return None
    text = labels if isinstance(labels, str) else ";".join(labels)
    m = re.search(rf"(?:^|[;,\s]){re.escape(prefix)}([^;,\s]+)", text, re.IGNORECASE)
    return m.group(1) if m else None


def calibration_factor(calibration: dict[str, Any], type_: str, effort: str | None) -> float:
    """Return the minutes factor for this slice. type: wins over effort:; else 1.0."""
    factors = (calibration or {}).get("factors", {})
    for key in (f"type:{type_}", f"label:effort:{effort}" if effort else None):
        if key and key in factors:
            try:
                return float(factors[key]["factor"])
            except (KeyError, TypeError, ValueError):
                continue
    return 1.0


def estimate_minutes(
    type_: str, effort: str | None, seed: dict[str, Any], calibration: dict[str, Any]
) -> int:
    """base_minutes[type] * calibration_factor, clamped to seed.clamp_minutes."""
    base_table = seed.get("base_minutes", {})
    base = base_table.get(type_, base_table.get("default", 60))
    factor = calibration_factor(calibration, type_, effort)
    raw = base * factor
    lo, hi = seed.get("clamp_minutes", [5, 480])
    return int(max(lo, min(hi, round(raw))))


def _tier(model: str, tiers: list[str]) -> int:
    try:
        return tiers.index(model)
    except ValueError:
        return -1


def recommend_model(
    type_: str,
    effort: str | None,
    labels: str | list[str] | None,
    seed: dict[str, Any],
    model_policy: dict[str, Any],
) -> str:
    """Cheapest-sufficient model: the effort floor, up-tiered only if the learned
    policy recommends a stronger model for this ticket class. Never below floor."""
    tiers = seed.get("model_tiers", ["haiku", "sonnet", "opus"])
    floors = seed.get("effort_floor", {})
    default_floor = seed.get("default_floor", "sonnet")
    floor = floors.get(effort, default_floor) if effort else default_floor

    # Learned policy override, keyed by type, then effort/risk/area labels.
    learned = (model_policy or {}).get("learned", {})
    risk = dim_from_labels(labels, "risk:")
    area = dim_from_labels(labels, "area:")
    override = None
    for key in (
        f"type:{type_}",
        f"label:effort:{effort}" if effort else None,
        f"label:risk:{risk}" if risk else None,
        f"label:area:{area}" if area else None,
    ):
        if key and key in learned:
            override = learned[key].get("recommended_model")
            if override:
                break

    candidate = override or seed.get("type_model", {}).get(
        type_, seed.get("type_model", {}).get("default", floor)
    )
    # External-executor rung: `external:<name>` is off the haiku/sonnet/opus ladder
    # (a config-chosen provider, not a tier). Pass it through unclamped -- the
    # orchestrator dispatches it to the configured command instead of a Claude Task.
    if isinstance(candidate, str) and candidate.startswith("external:"):
        return candidate
    # Clamp UP to the floor -- never route below the intended minimum.
    return candidate if _tier(candidate, tiers) >= _tier(floor, tiers) else floor


def plan_ticket(
    type_: str,
    effort: str | None,
    labels: str | list[str] | None,
    seed: dict[str, Any],
    calibration: dict[str, Any],
    model_policy: dict[str, Any],
) -> dict[str, Any]:
    """Produce the (estimate_minutes, recommended_model) pair for a ticket."""
    return {
        "estimate_minutes": estimate_minutes(type_, effort, seed, calibration),
        "recommended_model": recommend_model(type_, effort, labels, seed, model_policy),
    }


# --- CLI ------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed estimate + model for a ticket")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="emit {estimate_minutes, recommended_model}")
    p.add_argument("--type", required=True)
    p.add_argument("--effort", default=None, help="S|M|L (or read from --labels)")
    p.add_argument("--labels", default="", help="semicolon/comma label string")
    args = parser.parse_args(argv)

    if args.cmd == "plan":
        effort = args.effort or effort_from_labels(args.labels)
        out = plan_ticket(
            args.type,
            effort,
            args.labels,
            load_seed(),
            load_calibration(),
            load_model_policy(),
        )
        print(json.dumps(out))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
