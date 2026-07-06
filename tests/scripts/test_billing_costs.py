"""Tests for scripts/billing_costs.py -- Anthropic billing API pricing lookup.

FXL-102: verifies `model_pricing` / `calculate_token_cost` price `claude-fable-5`
correctly via the family-first (`fable`) budgets.yml key, matching the parallel
fix in scripts/ledger_append.py so the two scripts stay consistent.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _ROOT / "scripts"
_spec = importlib.util.spec_from_file_location("billing_costs", _SCRIPTS / "billing_costs.py")
bc = importlib.util.module_from_spec(_spec)
sys.modules["billing_costs"] = bc
_spec.loader.exec_module(bc)

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


def test_model_pricing_fable_family_lookup():
    assert bc.model_pricing("claude-fable-5", PRICING) == (10.0, 50.0)


def test_model_pricing_bare_fable_key():
    assert bc.model_pricing("fable", PRICING) == (10.0, 50.0)


def test_model_pricing_unknown_falls_back_to_sonnet_4_5():
    assert bc.model_pricing("mystery-model", PRICING) == (3.0, 15.0)


def test_calculate_token_cost_fable_is_nonzero_and_correct():
    # 1M input + 1M output for claude-fable-5 at real rates ($10/$50) = $60.00.
    result = {
        "model": "claude-fable-5",
        "uncached_input_tokens": 1_000_000,
        "output_tokens": 1_000_000,
        "cache_creation": {},
        "cache_read_input_tokens": 0,
    }
    assert bc.calculate_token_cost(result, PRICING) == 60.0
