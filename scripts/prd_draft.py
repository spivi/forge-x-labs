#!/usr/bin/env python3
"""Auto-draft missing PRD sections via a generator->reviewer provider chain.

When `/sprint plan` finds a ticket whose PRD is missing required sections, it can
auto-draft them (if enabled) instead of hard-stopping. Two modes (auto-draft.yml):

  pair   — generator drafts, reviewer critiques/refines; on generator failure the
           roles swap; if both fail, the fallback provider does a single call.
  single — walk the `providers` list, first success wins; else the fallback.

This is the GENERIC, template-safe core: the chain ORCHESTRATION is pure and unit-
tested via an injected `call_provider(name, role, draft=...) -> str | None`. The real
provider adapters (codex / gemini / claude) are fail-soft placeholders a project wires
to its own CLIs/SDKs — this module stays free of vendor coupling and network in tests.
Ships DISABLED (`enabled: false`) so a fresh copy never calls external APIs unprompted.
Failures are surfaced as Blocked/Skipped, NEVER a hard-stop.

CLI:
    python scripts/prd_draft.py draft ABC-42 [--apply]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

PROJECT_DIR = Path(__file__).resolve().parent.parent
AUTODRAFT_PATH = PROJECT_DIR / ".dev-context" / "auto-draft.yml"


# --- config ---------------------------------------------------------------


def load_autodraft_config(path: Path = AUTODRAFT_PATH) -> dict[str, Any]:
    """Read auto-draft.yml. Missing/invalid → {'enabled': False} (safe default)."""
    p = Path(path)
    if not p.exists():
        return {"enabled": False}
    try:
        import yaml

        return yaml.safe_load(p.read_text()) or {"enabled": False}
    except Exception:  # noqa: BLE001  (fail-soft)
        return {"enabled": False}


# --- chain orchestration (pure; providers injected) -----------------------


def draft_sections(
    config: dict[str, Any],
    call_provider: Callable[..., str | None],
) -> str | None:
    """Run the generator->reviewer chain per `config`. `call_provider(name, role,
    draft=...)` returns drafted text or None (failure). Returns the final text or None.

    Disabled config → None. pair mode: generator then reviewer; on generator failure
    swap roles; if both fail, fallback single-call. single mode: first provider success
    wins, else fallback."""
    if not config.get("enabled"):
        return None
    fallback = config.get("fallback_provider") or "claude"

    if config.get("mode") == "single":
        for name in config.get("providers") or []:
            out = call_provider(name, "single")
            if out:
                return out
        return call_provider(fallback, "single")

    # pair mode (default)
    pair = config.get("pair_order") or []
    if len(pair) >= 2:
        gen, rev = pair[0], pair[1]
        result = _run_pair(call_provider, gen, rev)
        if result is None:  # symmetric swap: reviewer becomes generator
            result = _run_pair(call_provider, rev, gen)
        if result is not None:
            return result
    return call_provider(fallback, "single")


def _run_pair(
    call_provider: Callable[..., str | None], generator: str, reviewer: str
) -> str | None:
    """One generator->reviewer attempt. None if the generator fails; the raw draft if
    the reviewer fails (a draft beats nothing); else the reviewed text."""
    draft = call_provider(generator, "generator")
    if not draft:
        return None
    reviewed = call_provider(reviewer, "reviewer", draft=draft)
    return reviewed or draft


# --- real provider adapters (fail-soft placeholders; project-wired) -------


def make_call_provider(ticket: str) -> Callable[..., str | None]:  # pragma: no cover (network)
    """Build the real `call_provider` for a ticket. Each provider name maps to a
    project-configured CLI/SDK call (codex/gemini/claude). The shipped template returns
    None for every provider (no vendor calls) — wire these to your drafting backends."""

    def call_provider(name: str, role: str, *, draft: str | None = None) -> str | None:
        # Placeholder: a real implementation shells out to the provider CLI or SDK,
        # passing the ticket context (and `draft` for the reviewer role). Returning
        # None marks a provider failure so the chain can swap/fall back.
        print(
            f"prd_draft: provider '{name}' (role={role}) not configured for {ticket} — skipping",
            file=sys.stderr,
        )
        return None

    return call_provider


# --- CLI ------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Auto-draft missing PRD sections")
    parser.add_argument("command", choices=["draft"])
    parser.add_argument("ticket")
    parser.add_argument("--apply", action="store_true", help="write the draft to the PRD file")
    args = parser.parse_args(argv)

    config = load_autodraft_config()
    if not config.get("enabled"):
        print("prd_draft: auto-draft disabled (auto-draft.yml enabled: false) — skipped")
        return 0
    text = draft_sections(config, make_call_provider(args.ticket))
    if not text:
        print(
            f"prd_draft: no draft produced for {args.ticket} (all providers failed) — skipped",
            file=sys.stderr,
        )
        return 0  # fail-soft: Blocked/Skipped, never a hard-stop
    if args.apply:
        prd = PROJECT_DIR / ".dev-context" / "prds" / f"{args.ticket}.md"
        prd.parent.mkdir(parents=True, exist_ok=True)
        prd.write_text(text)
        print(f"prd_draft: wrote draft to {prd}")
    else:
        print(text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
