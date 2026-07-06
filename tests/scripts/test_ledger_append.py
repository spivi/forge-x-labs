"""Tests for scripts/ledger_append.py -- sub-agent actuals capture.

The orchestrator appends exactly one 16-column ledger row per finished sub-agent.
Pure functions (parse/cost) are tested directly; append is tested against a tmp
ledger. A guard test asserts the column set never drifts from the committed header.
"""

from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _ROOT / "scripts"
_spec = importlib.util.spec_from_file_location("ledger_append", _SCRIPTS / "ledger_append.py")
la = importlib.util.module_from_spec(_spec)
# Register before exec so the @dataclass string annotations resolve (dataclasses
# looks up sys.modules[cls.__module__] when fields use future annotations).
sys.modules["ledger_append"] = la
_spec.loader.exec_module(la)

PRICING = {
    "anthropic": {
        "opus": {"input_per_1m": 15.0, "output_per_1m": 75.0},
        "sonnet": {"input_per_1m": 3.0, "output_per_1m": 15.0},
        "haiku": {"input_per_1m": 0.80, "output_per_1m": 4.0},
        # Real Claude Fable 5 pricing (FXL-102) -- see .dev-context/budgets.yml
        # for the sourced citation.
        "fable": {"input_per_1m": 10.0, "output_per_1m": 50.0},
    }
}


# --- pure helpers ---------------------------------------------------------


def test_normalize_model_strips_date_suffix():
    assert la.normalize_model("claude-opus-4-6-20250929") == "claude-opus-4-6"
    assert la.normalize_model("claude-opus-4-8") == "claude-opus-4-8"


def test_model_family_is_version_proof():
    assert la.model_family("claude-opus-4-8") == "opus"
    assert la.model_family("claude-opus-4-8[1m]") == "opus"
    assert la.model_family("haiku") == "haiku"


def test_model_family_fable_is_version_proof():
    # FXL-102: claude-fable-5 (and any future Fable version) and bare "fable"
    # must both map to the "fable" pricing family.
    assert la.model_family("claude-fable-5") == "fable"
    assert la.model_family("fable") == "fable"
    assert la.model_family("claude-fable-5[1m]") == "fable"


def test_provider_for_model():
    assert la.provider_for_model("claude-sonnet-4-6") == "anthropic"
    assert la.provider_for_model("opus") == "anthropic"
    assert la.provider_for_model("gpt-5-codex") == "openai"


def test_provider_for_fable_is_anthropic():
    # FXL-102: claude-fable-5 already matches via startswith("claude"); a bare
    # "fable" id must also resolve to anthropic via the family path.
    assert la.provider_for_model("claude-fable-5") == "anthropic"
    assert la.provider_for_model("fable") == "anthropic"


# --- parse_task_result ----------------------------------------------------


def test_parse_modelusage_sums_and_picks_headline():
    result = {
        "modelUsage": {
            "claude-haiku-4-5": {
                "inputTokens": 100,
                "outputTokens": 50,
                "cacheCreationInputTokens": 0,
                "cacheReadInputTokens": 0,
            },
            "claude-opus-4-8": {
                "inputTokens": 10,
                "outputTokens": 5,
                "cacheCreationInputTokens": 0,
                "cacheReadInputTokens": 0,
            },
        },
        "total_duration_ms": 120000,
    }
    p = la.parse_task_result(result)
    assert p["model"] == "claude-opus-4-8"  # highest tier is the headline
    assert p["input_tokens"] == 110
    assert p["output_tokens"] == 55
    assert p["duration_sec"] == 120
    assert len(p["per_model"]) == 2


def test_parse_flat_usage_fallback():
    result = {
        "model": "claude-sonnet-4-6",
        "usage": {"input_tokens": 200, "output_tokens": 100},
        "duration_sec": 42,
    }
    p = la.parse_task_result(result)
    assert p["model"] == "claude-sonnet-4-6"
    assert p["input_tokens"] == 200
    assert p["duration_sec"] == 42


def test_malformed_result_is_safe():
    p = la.parse_task_result({})
    assert p["model"] == "unknown"
    assert p["input_tokens"] == 0
    assert p["duration_sec"] == 0


# --- cost -----------------------------------------------------------------


def test_compute_cost_family_lookup():
    # 1M input @ $15 + 0 output -> $15.00 via the family key (no version-pinned needed).
    assert la.compute_cost("claude-opus-4-8", 1_000_000, 0, 0, 0, PRICING) == 15.0


def test_compute_cost_unknown_model_is_zero():
    assert la.compute_cost("mystery-model", 1_000_000, 0, 0, 0, PRICING) == 0.0


def test_compute_cost_fable_family_lookup_nonzero():
    # FXL-102 acceptance criterion: a claude-fable-5 run prices at a non-zero,
    # correct $ via the family-first lookup. 1M input @ $10 + 1M output @ $50
    # = $60.00 (real Fable 5 rates -- see budgets.yml citation).
    assert la.compute_cost("claude-fable-5", 1_000_000, 1_000_000, 0, 0, PRICING) == 60.0


def test_compute_cost_fable_bare_family_key():
    assert la.compute_cost("fable", 1_000_000, 0, 0, 0, PRICING) == 10.0


def test_compute_run_cost_prices_each_model_at_own_rate():
    # Haiku-heavy run with a small Opus call: 1M haiku ($0.80) + 1M opus ($15) = $15.80,
    # NOT 2M @ opus ($30). This is the multi-model correctness guarantee.
    per_model = [
        {
            "model": "claude-haiku-4-5",
            "input": 1_000_000,
            "output": 0,
            "cache_create": 0,
            "cache_read": 0,
        },
        {
            "model": "claude-opus-4-8",
            "input": 1_000_000,
            "output": 0,
            "cache_create": 0,
            "cache_read": 0,
        },
    ]
    assert la.compute_run_cost(per_model, PRICING) == 15.80


# --- build_row / append ---------------------------------------------------


def _run():
    return la.SubAgentRun(
        result={
            "modelUsage": {
                "claude-opus-4-8": {
                    "inputTokens": 1000,
                    "outputTokens": 500,
                    "cacheCreationInputTokens": 0,
                    "cacheReadInputTokens": 0,
                }
            },
            "total_duration_ms": 120000,
        },
        ticket="ABC-1",
        session_id="sess-1",
    )


def test_build_row_has_16_columns():
    row = la.build_row(_run(), PRICING)
    assert list(row.keys()) == list(la.LEDGER_COLUMNS)
    assert len(la.LEDGER_COLUMNS) == 16


def test_ledger_columns_match_committed_header():
    header = (_ROOT / ".dev-context" / "cost-ledger.csv").read_text().splitlines()[0]
    assert header.split(",") == list(la.LEDGER_COLUMNS)


def test_subscription_billed_zero_api_nonzero():
    sub = la.build_row(_run(), PRICING)
    assert sub["billing_type"] == "subscription"
    assert sub["billed_usd"] == "0.0000"
    assert float(sub["compute_cost_usd"]) > 0  # notional still recorded

    api_run = la.SubAgentRun(result=_run().result, ticket="ABC-1", billing_type="api")
    api = la.build_row(api_run, PRICING)
    assert float(api["billed_usd"]) == float(api["compute_cost_usd"]) > 0


def test_append_row_writes_one_row(tmp_path):
    ledger = tmp_path / "cost-ledger.csv"
    ledger.write_text(",".join(la.LEDGER_COLUMNS) + "\n")
    la.append_row(_run(), ledger_path=ledger, pricing=PRICING)
    with ledger.open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["ticket"] == "ABC-1"
    assert rows[0]["duration_sec"] == "120"
    assert rows[0]["model"] == "claude-opus-4-8"
