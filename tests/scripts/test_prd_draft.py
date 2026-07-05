"""Tests for scripts/prd_draft.py -- the generator->reviewer chain orchestration.

The chain logic (pair / swap / fallback / single) is pure and exercised with a stub
`call_provider`; no network. The real provider adapters are project-wired (excluded).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_spec = importlib.util.spec_from_file_location("prd_draft", _SCRIPTS / "prd_draft.py")
pd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pd)

PAIR_CFG = {
    "enabled": True,
    "mode": "pair",
    "pair_order": ["codex", "gemini"],
    "fallback_provider": "claude",
}


def _stub(responses):
    """call_provider stub: responses is {(name, role): text|None}. Records calls."""
    calls: list[tuple] = []

    def cp(name, role, *, draft=None):
        calls.append((name, role, draft))
        return responses.get((name, role))

    cp.calls = calls
    return cp


# --- disabled / single ----------------------------------------------------


def test_disabled_returns_none():
    assert pd.draft_sections({"enabled": False}, _stub({})) is None


def test_single_mode_first_success():
    cfg = {
        "enabled": True,
        "mode": "single",
        "providers": ["codex", "gemini"],
        "fallback_provider": "claude",
    }
    assert pd.draft_sections(cfg, _stub({("codex", "single"): "DRAFT"})) == "DRAFT"


def test_single_mode_falls_back_to_fallback():
    cfg = {
        "enabled": True,
        "mode": "single",
        "providers": ["codex"],
        "fallback_provider": "claude",
    }
    assert pd.draft_sections(cfg, _stub({("claude", "single"): "FB"})) == "FB"


# --- pair -----------------------------------------------------------------


def test_pair_generator_then_reviewer():
    cp = _stub({("codex", "generator"): "D", ("gemini", "reviewer"): "REVIEWED"})
    assert pd.draft_sections(PAIR_CFG, cp) == "REVIEWED"


def test_pair_reviewer_failure_yields_raw_draft():
    # Reviewer returns None -> the raw generator draft beats nothing.
    cp = _stub({("codex", "generator"): "D"})
    assert pd.draft_sections(PAIR_CFG, cp) == "D"


def test_pair_swaps_roles_on_generator_failure():
    # codex (generator) fails -> swap: gemini generates, codex reviews.
    cp = _stub({("gemini", "generator"): "D2", ("codex", "reviewer"): "R2"})
    assert pd.draft_sections(PAIR_CFG, cp) == "R2"


def test_pair_falls_back_when_both_generators_fail():
    cp = _stub({("claude", "single"): "FB"})  # codex + gemini generators both fail
    assert pd.draft_sections(PAIR_CFG, cp) == "FB"


# --- config ---------------------------------------------------------------


def test_load_config_missing_is_disabled(tmp_path):
    assert pd.load_autodraft_config(tmp_path / "nope.yml") == {"enabled": False}


def test_shipped_autodraft_is_disabled():
    cfg = pd.load_autodraft_config()  # the committed .dev-context/auto-draft.yml
    assert cfg.get("enabled") is False
