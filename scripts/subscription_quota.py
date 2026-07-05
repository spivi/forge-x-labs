#!/usr/bin/env python3
"""Subscription quota gate for the /sprint budget check.

Complements the dollar-budget gate: when a project pays a flat subscription rather
than per-API-call, the constraint is a rolling token quota (5h + weekly windows),
weighted per model family (Opus draws far more than Haiku). `/sprint` runs BOTH
gates and the most-restrictive band wins.

This is the GENERIC, template-safe core: band classification + the gate contract.
It ships DISABLED (`subscription.provider: null` in budgets.yml) and no-ops until a
project sets a provider. The actual usage source (e.g. ~/.claude/stats-cache.json)
is project-specific and injected via `usage` — keeping this module testable and free
of any vendor-stats coupling. Fail-open: any missing data → disabled, never blocks.

CLI:
    python scripts/subscription_quota.py status        # JSON gate report
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent.parent
BUDGETS_PATH = PROJECT_DIR / ".dev-context" / "budgets.yml"

# Per-family quota weight: Opus draws ~5x a Haiku token against the ceiling.
DEFAULT_QUOTA_WEIGHT = {"opus": 5.0, "sonnet": 1.0, "haiku": 0.2}
_BAND_SEVERITY = {"OK": 0, "WARN": 1, "CRITICAL": 2, "EXCEEDED": 3}


# --- pure helpers ---------------------------------------------------------


def model_family(model: str) -> str:
    m = (model or "").lower()
    for fam in ("opus", "sonnet", "haiku"):
        if fam in m:
            return fam
    return m or "unknown"


def compute_quota_draw(
    per_family_tokens: dict[str, int], *, quota_weight: dict[str, float] | None = None
) -> float:
    """Weighted quota draw = sum(tokens[family] * weight[family])."""
    weights = quota_weight or DEFAULT_QUOTA_WEIGHT
    total = 0.0
    for fam, tokens in (per_family_tokens or {}).items():
        total += float(tokens or 0) * float(weights.get(model_family(fam), 1.0))
    return total


def classify_band(pct: float, *, warn_at: float = 70.0, critical_at: float = 90.0) -> str:
    """OK < warn_at <= WARN < critical_at <= CRITICAL < 100 <= EXCEEDED."""
    if pct >= 100.0:
        return "EXCEEDED"
    if pct >= critical_at:
        return "CRITICAL"
    if pct >= warn_at:
        return "WARN"
    return "OK"


def most_restrictive_band(bands: list[str]) -> str:
    """Most severe band (OK<WARN<CRITICAL<EXCEEDED). Empty/unknown → OK (safe)."""
    best = "OK"
    for band in bands:
        if _BAND_SEVERITY.get(band, 0) > _BAND_SEVERITY.get(best, 0):
            best = band
    return best


# --- config ---------------------------------------------------------------


def load_subscription_config(budgets_path: Path = BUDGETS_PATH) -> dict[str, Any]:
    """Return the `subscription:` block from budgets.yml, or {} (fail-soft)."""
    p = Path(budgets_path)
    if not p.exists():
        return {}
    try:
        import yaml

        budgets = yaml.safe_load(p.read_text()) or {}
    except Exception:  # noqa: BLE001  (fail-soft)
        return {}
    return budgets.get("subscription") or {}


# --- gate -----------------------------------------------------------------


def _disabled(error: str | None = None) -> dict[str, Any]:
    return {
        "enabled": False,
        "weekly_band": "OK",
        "5h_band": "OK",
        "weekly_pct": 0.0,
        "5h_pct": 0.0,
        "overall_band": "OK",
        "error": error,
    }


def run_quota_gate(
    *, budgets_path: Path = BUDGETS_PATH, usage: dict[str, dict[str, int]] | None = None
) -> dict[str, Any]:
    """Compute the subscription-quota status for the /sprint gate.

    Disabled (and a safe `OK` overall) when `subscription.provider` is null, or when
    no `usage` source is supplied (fail-open). `usage` is `{"weekly": {fam: tokens},
    "5h": {fam: tokens}}` — injected by the caller from its own stats source."""
    sub = load_subscription_config(budgets_path)
    if not sub.get("provider"):
        return _disabled()
    if not usage:
        return _disabled(error="no usage source supplied — fail-open")

    weights = {k: float(v) for k, v in (sub.get("quota_weight") or DEFAULT_QUOTA_WEIGHT).items()}
    weekly_limit = int(sub.get("window_limit_weekly", 0)) or 0
    fiveh_limit = int(sub.get("window_limit_5h", 0)) or 0
    warn_w = float(sub.get("warn_at_weekly_pct", 70.0))
    crit_w = float(sub.get("critical_at_weekly_pct", 90.0))
    warn_5 = float(sub.get("warn_at_5h_pct", 70.0))
    crit_5 = float(sub.get("critical_at_5h_pct", 90.0))

    weekly_pct = _pct(
        compute_quota_draw(usage.get("weekly", {}), quota_weight=weights), weekly_limit
    )
    fiveh_pct = _pct(compute_quota_draw(usage.get("5h", {}), quota_weight=weights), fiveh_limit)
    weekly_band = classify_band(weekly_pct, warn_at=warn_w, critical_at=crit_w)
    fiveh_band = classify_band(fiveh_pct, warn_at=warn_5, critical_at=crit_5)
    return {
        "enabled": True,
        "weekly_band": weekly_band,
        "5h_band": fiveh_band,
        "weekly_pct": round(weekly_pct, 1),
        "5h_pct": round(fiveh_pct, 1),
        "overall_band": most_restrictive_band([weekly_band, fiveh_band]),
        "error": None,
    }


def _pct(draw: float, limit: int) -> float:
    return (draw / limit) * 100 if limit > 0 else 0.0


# --- CLI ------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Subscription quota gate")
    parser.add_argument("command", choices=["status"], nargs="?", default="status")
    parser.parse_args(argv)
    print(json.dumps(run_quota_gate(), indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
