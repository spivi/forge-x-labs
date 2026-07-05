<!-- cc10x session memory: PATTERNS. DO NOT DELETE.
     Cross-session knowledge base — gotchas, traps, and learnings that must
     survive compaction and outlive any single ticket. This is the gem: append
     a one-line entry whenever a non-obvious failure or fix is discovered, under
     the right taxonomy heading. Keep entries short and concrete (what + why).
     The session-start hook surfaces this file so future sessions don't relearn
     the same lesson. -->

# Patterns & Gotchas

> Append under the matching heading. Format: `- <symptom/context>: <fix/rule> (why)`.
> Add new headings as the project grows.

## Runtime / Language

## Async & Concurrency

## Testing
- importlib-loaded module with a `@dataclass` + `from __future__ import annotations`: register it in `sys.modules[name]` BEFORE `spec.loader.exec_module` or dataclass field resolution crashes (`dataclasses._is_type` does `sys.modules.get(cls.__module__).__dict__` → None). See `tests/scripts/test_ledger_append.py`.
- scripts/ tests load modules by path (`spec_from_file_location`); a script that imports a sibling (e.g. `dataset` → `debrief`) must `sys.path.insert(0, str(_HERE))` at top so the sibling import resolves under any load context.
- mypy is scoped to `app/` only (`exclude: ^(scripts/|tests/|lemmings/)` in pre-commit); coverage gate is `app/` too. scripts/ is ruff-gated, NOT mypy/coverage-gated — don't chase strict-typing debt there.

## Silent Failures
<!-- The error class that fails quietly instead of raising: dict.get() masking
     invalid input, unguarded float()/int() on external data, parsers deriving
     success from a count, substring matches with false positives. -->

## Performance

## Shell / Cross-platform

## Database / ORM

## Tooling & Build
- CSV schema migration that must stay back-compat: `store._columns()` reads the FILE's live header on write, so old-width files round-trip until a `migrate` command rewrites them with the canonical `COLUMNS`. Migrators must be idempotent (`if _columns(p) == COLUMNS: return False`) and back-fill new typed columns from the legacy `labels` string.
- `budgets.yml` pricing must carry FAMILY keys (`opus`/`sonnet`/`haiku`) for the version-proof family-first lookup in `ledger_append`/`billing_costs`, AND the version-pinned keys (`claude-opus-4-6`) the SessionEnd bash hook matches exactly. Keep both.
- New `rules/*.md` must be registered in `sync-tool-configs.py::CURSOR_RULE_CONFIG` then `--sync`'d, else the pre-commit drift hook (`--check`) fails. Generated `.cursor/.antigravity` files are untracked (only `.gitkeep` tracked) — regenerate, don't commit.

## Last Updated
_2026-06-01 — harness parity: typed ML labeling + dataset + sub-agent/review capture._
