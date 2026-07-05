#!/usr/bin/env python3
"""Poll Anthropic billing API and reconcile with cost-ledger estimates.

Tracks ONLY actual API-billed spend (money that leaves your wallet).
Claude Code subscription usage is excluded.

Usage: python scripts/poll-anthropic-billing.py [--period daily|weekly|monthly]
Reads: .dev-context/budgets.yml, .dev-context/cost-ledger.csv, ANTHROPIC_ADMIN_KEY env
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml
from billing_costs import ANTHROPIC_API_BASE, fetch_usage, sum_api_key_usage
from billing_format import format_report

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DAILY_BUDGET = 20.00


def load_budgets(budgets_path: Path) -> dict:  # type: ignore[type-arg]
    """Load budget configuration from budgets.yml."""
    if not budgets_path.exists():
        print("WARNING: budgets.yml not found, using $20/day default.", file=sys.stderr)
        return {"budgets": {"daily": {"total": DEFAULT_DAILY_BUDGET}}, "alerts": {}}
    with open(budgets_path) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        print(
            "WARNING: budgets.yml is empty or malformed, using defaults.",
            file=sys.stderr,
        )
        return {"budgets": {"daily": {"total": DEFAULT_DAILY_BUDGET}}, "alerts": {}}
    return data


def _period_cutoff(period: str) -> datetime:
    """Return the UTC cutoff datetime for the given period."""
    now = datetime.now(UTC)
    deltas = {"daily": timedelta(days=1), "weekly": timedelta(weeks=1)}
    return now - deltas.get(period, timedelta(days=30))


def load_ledger_costs(ledger_path: Path, period: str) -> dict:  # type: ignore[type-arg]
    """Sum estimated costs from cost-ledger.csv for the given period."""
    if not ledger_path.exists():
        return {"total": 0.0, "by_provider": {}, "rows": 0}
    cutoff = _period_cutoff(period)
    total = 0.0
    by_provider: dict[str, float] = {}
    rows = 0
    with open(ledger_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts_str = row.get("timestamp", "").strip().strip('"')
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except (ValueError, KeyError):
                continue
            if ts < cutoff:
                continue
            try:
                cost = float(row.get("billed_usd", "0").strip().strip('"'))
            except ValueError:
                continue
            provider = row.get("provider", "unknown").strip().strip('"')
            total += cost
            by_provider[provider] = by_provider.get(provider, 0.0) + cost
            rows += 1
    return {"total": total, "by_provider": by_provider, "rows": rows}


def poll_anthropic_api(
    period: str,
    pricing: dict | None = None,  # type: ignore[type-arg]
) -> dict | None:  # type: ignore[type-arg]
    """Fetch actual API-billed spend from Anthropic Admin API.

    Uses usage_report/messages grouped by api_key_id+model, then calculates
    costs from token counts. Excludes api_key_id=null (subscription usage).
    Requires ANTHROPIC_ADMIN_KEY env var.
    """
    admin_key = os.environ.get("ANTHROPIC_ADMIN_KEY")
    if not admin_key:
        return None
    cutoff = _period_cutoff(period)
    start = cutoff.replace(hour=0, minute=0, second=0, microsecond=0)
    params = [
        ("starting_at", start.strftime("%Y-%m-%dT%H:%M:%SZ")),
        ("group_by[]", "api_key_id"),
        ("group_by[]", "model"),
    ]
    headers = {"x-api-key": admin_key, "anthropic-version": "2023-06-01"}
    url = f"{ANTHROPIC_API_BASE}/usage_report/messages"
    data = fetch_usage(url, params, headers)
    if data is None:
        return None
    return sum_api_key_usage(data, pricing or {})


def get_budget_status(
    spend: float,
    budgets: dict,
    period: str,  # type: ignore[type-arg]
) -> dict:  # type: ignore[type-arg]
    """Calculate budget status from spend and budget config."""
    period_budgets = budgets.get("budgets", {}).get(period, {})
    budget_total = float(period_budgets.get("total", DEFAULT_DAILY_BUDGET))
    alerts = budgets.get("alerts", {})
    warn_pct = float(alerts.get("warn_at_percent", 70))
    critical_pct = float(alerts.get("critical_at_percent", 90))
    pct = (spend / budget_total * 100) if budget_total > 0 else 0.0
    if pct >= 100:
        status = "EXCEEDED"
    elif pct >= critical_pct:
        status = "CRITICAL"
    elif pct >= warn_pct:
        status = "WARNING"
    else:
        status = "OK"
    return {"spend": spend, "budget": budget_total, "percent": pct, "status": status}


def main() -> None:
    """Entry point: parse args, load data, reconcile, print report."""
    parser = argparse.ArgumentParser(description="Poll Anthropic billing and reconcile costs")
    parser.add_argument("--period", choices=["daily", "weekly", "monthly"], default="daily")
    args = parser.parse_args()
    budgets_path = PROJECT_ROOT / ".dev-context" / "budgets.yml"
    ledger_path = PROJECT_ROOT / ".dev-context" / "cost-ledger.csv"
    budgets = load_budgets(budgets_path)
    estimated = load_ledger_costs(ledger_path, args.period)
    pricing = budgets.get("pricing", {})
    actual = poll_anthropic_api(args.period, pricing)
    spend = actual["total"] if actual else estimated["total"]
    budget_status = get_budget_status(spend, budgets, args.period)
    print(format_report(estimated, actual, budget_status))


if __name__ == "__main__":
    main()
