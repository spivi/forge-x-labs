#!/usr/bin/env python3
"""Append a cost-ledger row from a background/sub-agent Task completion result.

Closes a data-completeness gap in the learning loop: `/sprint execute` spawns
developer agents as background Task agents, but `log-session-cost.sh` only fires
on the MAIN session's `SessionEnd` -- never on spawned sub-agents. Their duration
and token usage therefore never reach `cost-ledger.csv`, so `/debrief` and
`scripts/dataset.py` see incomplete actuals for parallel work.

Design (orchestrator-side append -- chosen for reliability): the scrum master
receives each background Task agent's completion result when the agent finishes.
That result is the single authoritative record of the sub-agent's duration +
token usage. The orchestrator is the one writer, so exactly one row is appended
per agent and there is no double-counting.

The row reuses the existing 16-column ledger schema (same header as
`log-session-cost.sh` emits). `compute_cost_usd` is derived from `budgets.yml`
pricing (family-first, version-proof) for the model the agent actually used.

Pure functions carry the logic and are unit-tested directly; the CLI / file path
wires them to `budgets.yml` and the ledger.

CLI:
    python scripts/ledger_append.py --ticket ABC-2 --agent developer \
        --session-id <id> --result-json <path|-> [--billing-type api]
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent.parent
LEDGER_PATH = PROJECT_DIR / ".dev-context" / "cost-ledger.csv"
BUDGETS_PATH = PROJECT_DIR / ".dev-context" / "budgets.yml"

# Column order MUST match log-session-cost.sh and the ledger header exactly (16).
LEDGER_COLUMNS = (
    "timestamp",
    "agent",
    "session_id",
    "provider",
    "model",
    "input_tokens",
    "output_tokens",
    "cache_creation_tokens",
    "cache_read_tokens",
    "compute_cost_usd",
    "billing_type",
    "billed_usd",
    "ticket",
    "session_start",
    "session_end",
    "duration_sec",
)

# Anthropic cache pricing relative to the input rate (matches log-session-cost.sh
# and scripts/billing_costs.py).
CACHE_CREATION_MULTIPLIER = 1.25
CACHE_READ_MULTIPLIER = 0.10

# Larger number = costlier / higher tier; used to pick the headline model when a
# run touched more than one model.
_MODEL_TIER = {"haiku": 1, "sonnet": 2, "opus": 3}


@dataclass(frozen=True)
class SubAgentRun:
    """The orchestrator-supplied context for one finished sub-agent.

    `result` is the Task tool's completion result (token usage + duration);
    `ticket`/`agent`/`session_id` are known to the orchestrator that spawned it.
    """

    result: dict[str, Any]
    ticket: str
    agent: str = "developer"
    session_id: str = "unknown"
    billing_type: str = "subscription"


# --- pure helpers ---------------------------------------------------------


def normalize_model(model: str) -> str:
    """Strip a trailing 8-digit date suffix: claude-opus-4-6-20250929 -> ...-4-6."""
    model = (model or "").strip()
    if not model:
        return "unknown"
    parts = model.rsplit("-", 1)
    if len(parts) == 2 and len(parts[1]) == 8 and parts[1].isdigit():
        return parts[0]
    return model


def model_family(model: str) -> str:
    """Normalise a model id to a pricing family (opus/sonnet/haiku).

    Version-proof: ``claude-opus-4-8``, ``claude-opus-4-8[1m]`` and bare ``opus``
    all map to ``opus``."""
    m = (model or "").lower()
    for fam in ("opus", "sonnet", "haiku"):
        if fam in m:
            return fam
    return m or "unknown"


def provider_for_model(model: str) -> str:
    # `gpt*` is OpenAI's model id; `codex` is a routing family used when an
    # external executor authored the work and returned no concrete model id.
    if model.startswith("gpt") or model.startswith("codex"):
        return "openai"
    # `claude-*` ids and bare family names (opus/sonnet/haiku) are all Anthropic.
    if model.startswith("claude") or model_family(model) in ("opus", "sonnet", "haiku"):
        return "anthropic"
    return "unknown"


def _model_rank(model: str) -> int:
    for fam, tier in _MODEL_TIER.items():
        if fam in model:
            return tier
    return 0


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _tokens(model: str, raw: dict[str, Any], keys: tuple[str, str, str, str]) -> dict[str, Any]:
    """One per-model token slice from a usage block (keys order: in/out/cc/cr)."""
    return {
        "model": normalize_model(model),
        "input": _int(raw.get(keys[0])),
        "output": _int(raw.get(keys[1])),
        "cache_create": _int(raw.get(keys[2])),
        "cache_read": _int(raw.get(keys[3])),
    }


def _from_model_usage(model_usage: dict[str, Any]) -> list[dict[str, Any]]:
    """One token slice per model in the camelCase `modelUsage` map."""
    keys = ("inputTokens", "outputTokens", "cacheCreationInputTokens", "cacheReadInputTokens")
    return [_tokens(model, usage, keys) for model, usage in model_usage.items()]


def _from_flat_usage(result: dict[str, Any]) -> list[dict[str, Any]]:
    """A single token slice from the flat `usage` + top-level `model` fallback."""
    keys = (
        "input_tokens",
        "output_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
    )
    return [_tokens(result.get("model", ""), result.get("usage") or {}, keys)]


def _duration_sec(result: dict[str, Any]) -> int:
    if "total_duration_ms" in result:
        return _int(result.get("total_duration_ms")) // 1000
    if "duration_ms" in result:
        return _int(result.get("duration_ms")) // 1000
    return _int(result.get("duration_sec"))


def parse_task_result(result: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Task completion result into ledger-ready fields.

    Handles two shapes: the camelCase `modelUsage` map (real Task tool result)
    and a flat `usage` + top-level `model` fallback. Missing fields default to
    safe zeros / "unknown" so a malformed result never aborts the append.

    `per_model` keeps the per-model token slices so cost is priced at each model's
    own rate. The single ledger token columns carry the run TOTALS, and `model` is
    the highest-tier model used (display metadata)."""
    model_usage = result.get("modelUsage")
    slices = _from_model_usage(model_usage) if model_usage else _from_flat_usage(result)
    models = [s["model"] for s in slices if s["model"] != "unknown"]
    headline = max(models, key=_model_rank) if models else "unknown"
    return {
        "model": headline,
        "input_tokens": sum(s["input"] for s in slices),
        "output_tokens": sum(s["output"] for s in slices),
        "cache_creation_tokens": sum(s["cache_create"] for s in slices),
        "cache_read_tokens": sum(s["cache_read"] for s in slices),
        "duration_sec": _duration_sec(result),
        "per_model": slices,
    }


def compute_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_tokens: int,
    cache_read_tokens: int,
    pricing: dict[str, Any],
) -> float:
    """Dollar cost from tokens x budgets.yml pricing for the model.

    Family-first (version-proof), then legacy version-pinned key. A genuine miss
    warns to stderr instead of silently pricing at $0 (model-drift surfaces)."""
    provider = provider_for_model(model)
    prov_rates = pricing.get(provider, {})
    rates = prov_rates.get(model_family(model)) or prov_rates.get(normalize_model(model))
    if not rates:
        print(
            f"WARNING: no pricing for model {model!r} (family {model_family(model)!r}); "
            "recording notional $0",
            file=sys.stderr,
        )
        return 0.0
    input_rate = float(rates.get("input_per_1m", 0))
    output_rate = float(rates.get("output_per_1m", 0))
    cost = (
        input_tokens * input_rate
        + output_tokens * output_rate
        + cache_creation_tokens * input_rate * CACHE_CREATION_MULTIPLIER
        + cache_read_tokens * input_rate * CACHE_READ_MULTIPLIER
    ) / 1_000_000
    return round(cost, 4)


def compute_run_cost(per_model: list[dict[str, Any]], pricing: dict[str, Any]) -> float:
    """Sum cost across a run's per-model token slices, each priced at its own rate.

    Pricing all summed tokens at the headline (highest-tier) model's rate
    over-bills (e.g. a Haiku run with a small Opus call billed entirely at Opus)."""
    total = sum(
        compute_cost(
            s["model"], s["input"], s["output"], s["cache_create"], s["cache_read"], pricing
        )
        for s in per_model
    )
    return round(total, 4)


def build_row(run: SubAgentRun, pricing: dict[str, Any]) -> dict[str, str]:
    """Build the 16-column ledger row dict for one finished sub-agent run."""
    p = parse_task_result(run.result)
    cost = compute_run_cost(p["per_model"], pricing)
    now = dt.datetime.now(dt.UTC)
    end = now.isoformat().replace("+00:00", "Z")
    start = (now - dt.timedelta(seconds=p["duration_sec"])).isoformat().replace("+00:00", "Z")
    billed = f"{cost:.4f}" if run.billing_type == "api" else "0.0000"
    return {
        "timestamp": end,
        "agent": run.agent,
        "session_id": run.session_id,
        "provider": provider_for_model(p["model"]),
        "model": p["model"],
        "input_tokens": str(p["input_tokens"]),
        "output_tokens": str(p["output_tokens"]),
        "cache_creation_tokens": str(p["cache_creation_tokens"]),
        "cache_read_tokens": str(p["cache_read_tokens"]),
        "compute_cost_usd": f"{cost:.4f}",
        "billing_type": run.billing_type,
        "billed_usd": billed,
        "ticket": run.ticket,
        "session_start": start,
        "session_end": end,
        "duration_sec": str(p["duration_sec"]),
    }


# --- I/O ------------------------------------------------------------------


def load_pricing(budgets_path: Path = BUDGETS_PATH) -> dict[str, Any]:
    if not budgets_path.exists():
        return {}
    try:
        import yaml
    except ImportError:
        print("WARNING: PyYAML not installed; cost will be 0.0000", file=sys.stderr)
        return {}
    config = yaml.safe_load(budgets_path.read_text()) or {}
    return config.get("pricing", {})


def append_row(
    run: SubAgentRun,
    ledger_path: Path = LEDGER_PATH,
    pricing: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Append exactly one RFC-4180 row for `run` to the ledger; return the row.

    The header must already exist (it does in the committed ledger). Existing rows
    are never read or rewritten, so legacy rows are untouched."""
    if pricing is None:
        pricing = load_pricing(BUDGETS_PATH)
    row = build_row(run, pricing)
    with ledger_path.open("a", newline="") as f:
        csv.writer(f, quoting=csv.QUOTE_MINIMAL).writerow([row[c] for c in LEDGER_COLUMNS])
    return row


# --- CLI ------------------------------------------------------------------


def _read_result_json(source: str) -> dict[str, Any]:
    raw = sys.stdin.read() if source == "-" else Path(source).read_text()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("result JSON must be an object")
    return data


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Append a sub-agent run to cost-ledger.csv")
    p.add_argument("--ticket", required=True)
    p.add_argument("--agent", default="developer")
    p.add_argument("--session-id", default="unknown")
    p.add_argument("--billing-type", default="subscription", choices=["subscription", "api"])
    p.add_argument("--result-json", required=True, help="path to JSON file, or - for stdin")
    p.add_argument("--ledger", type=Path, default=LEDGER_PATH)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run = SubAgentRun(
        result=_read_result_json(args.result_json),
        ticket=args.ticket,
        agent=args.agent,
        session_id=args.session_id,
        billing_type=args.billing_type,
    )
    row = append_row(run, ledger_path=args.ledger)
    print(
        f"appended ledger row: ticket={row['ticket']} model={row['model']} "
        f"duration_sec={row['duration_sec']} notional_cost=${row['compute_cost_usd']}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
