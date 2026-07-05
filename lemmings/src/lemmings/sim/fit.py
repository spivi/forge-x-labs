"""Fit SEM priors from a project's real KPI ledgers (loop B).

Reads cost-ledger.csv (cost + active duration per agent), bug-ledger.csv (bugs
per ticket) and review-log.csv (review turnaround) and proposes a priors
override. Each knob is fitted INDEPENDENTLY and only when it has at least
`min_samples` observations; otherwise it is skipped and reported -- never
silently dropped. On a brand-new project this yields an empty/partial override
and the synthetic defaults in priors_default.yml stand.

Only knobs with a genuine signal in the available ledgers are fitted:
  - agents.<agent>.cost_rate_per_min  (cost / active minutes)
  - bugs.base_lambda                  (bugs per ticket)
  - review.duration_mu                (log of mean review turnaround)
Knobs that need data we don't collect (e.g. per-line violation rates) are
reported as skipped so the gap is visible, not hidden.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any


def _num(value: Any, cast=float, default=0.0):
    try:
        return cast(value)
    except (TypeError, ValueError):
        return default


# --- per-knob fits --------------------------------------------------------


def fit_cost_rates(
    ledger_rows: list[dict[str, str]], min_samples: int = 5
) -> tuple[dict[str, float], list[tuple[str, str]]]:
    """cost_rate_per_min per agent = total compute cost / total active minutes."""
    agg: dict[str, dict[str, float]] = {}
    for row in ledger_rows:
        agent = (row.get("agent") or "").strip()
        if not agent:
            continue
        a = agg.setdefault(agent, {"sessions": 0, "cost": 0.0, "minutes": 0.0})
        a["sessions"] += 1
        cost = _num(row.get("compute_cost_usd"))
        if cost == 0.0:
            cost = _num(row.get("billed_usd"))
        a["cost"] += cost
        a["minutes"] += _num(row.get("duration_sec")) / 60.0

    rates: dict[str, float] = {}
    skipped: list[tuple[str, str]] = []
    for agent, a in agg.items():
        if a["sessions"] < min_samples:
            skipped.append((agent, f"{int(a['sessions'])} sessions < {min_samples}"))
        elif a["minutes"] <= 0:
            skipped.append((agent, "no duration data"))
        else:
            rates[agent] = round(a["cost"] / a["minutes"], 4)
    return rates, skipped


def fit_bug_lambda(
    ledger_rows: list[dict[str, str]],
    bug_rows: list[dict[str, str]],
    min_samples: int = 5,
) -> tuple[float | None, str]:
    """base_lambda = bug rows / distinct tickets that ran."""
    tickets = {
        (r.get("ticket") or "").strip()
        for r in ledger_rows
        if (r.get("ticket") or "").strip() not in ("", "untracked")
    }
    if len(tickets) < min_samples:
        return None, f"{len(tickets)} tickets < {min_samples}"
    return round(len(bug_rows) / len(tickets), 3), ""


def fit_review_duration(
    review_rows: list[dict[str, str]], min_samples: int = 5
) -> tuple[float | None, str]:
    """duration_mu = ln(mean review turnaround minutes) (lognormal location)."""
    turns = [
        _num(r.get("turnaround_minutes"))
        for r in review_rows
        if _num(r.get("turnaround_minutes")) > 0
    ]
    if len(turns) < min_samples:
        return None, f"{len(turns)} reviews < {min_samples}"
    mean = sum(turns) / len(turns)
    if mean <= 0:
        return None, "non-positive mean turnaround"
    return round(math.log(mean), 4), ""


# --- assembly -------------------------------------------------------------


def fit_priors(
    ledger_rows: list[dict[str, str]],
    bug_rows: list[dict[str, str]],
    review_rows: list[dict[str, str]],
    min_samples: int = 5,
) -> dict[str, Any]:
    """Assemble a priors override from whatever the ledgers support. Returns
    {override, fitted, skipped} -- fitted/skipped name every knob considered."""
    override: dict[str, Any] = {}
    fitted: list[str] = []
    skipped: list[tuple[str, str]] = []

    rates, rate_skips = fit_cost_rates(ledger_rows, min_samples)
    if rates:
        override.setdefault("agents", {})
        for agent, rate in rates.items():
            override["agents"][agent] = {"cost_rate_per_min": rate}
            fitted.append(f"agents.{agent}.cost_rate_per_min={rate}")
    skipped.extend((f"agents.{a}.cost_rate_per_min", why) for a, why in rate_skips)

    lam, lam_reason = fit_bug_lambda(ledger_rows, bug_rows, min_samples)
    if lam is not None:
        override.setdefault("bugs", {})["base_lambda"] = lam
        fitted.append(f"bugs.base_lambda={lam}")
    else:
        skipped.append(("bugs.base_lambda", lam_reason))

    mu, mu_reason = fit_review_duration(review_rows, min_samples)
    if mu is not None:
        override.setdefault("review", {})["duration_mu"] = mu
        fitted.append(f"review.duration_mu={mu}")
    else:
        skipped.append(("review.duration_mu", mu_reason))

    # Knobs with no signal in the current ledgers -- reported, not hidden.
    skipped.append(("violations.alpha_per_line", "no per-line data collected"))

    return {"override": override, "fitted": fitted, "skipped": skipped}


# --- IO -------------------------------------------------------------------


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def load_kpis(
    dev_context: Path,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    """Read (cost-ledger, bug-ledger, review-log) from a .dev-context dir."""
    return (
        _read_csv(dev_context / "cost-ledger.csv"),
        _read_csv(dev_context / "kpis" / "bug-ledger.csv"),
        _read_csv(dev_context / "kpis" / "review-log.csv"),
    )


def write_override(override: dict[str, Any], path: Path) -> None:
    import yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# Fitted priors override -- generated by `lemmings fit` from real KPIs.\n"
        "# Deep-merged on top of priors_default.yml. Safe to regenerate.\n"
    )
    path.write_text(header + yaml.safe_dump(override, sort_keys=True))
