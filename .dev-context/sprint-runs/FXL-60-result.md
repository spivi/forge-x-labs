# FXL-60 — Registry-gated raw source fetcher + cache — Result

**Status**: Complete — implemented, tested, CI green, NOT merged (per directive).
**PR**: [#83](https://github.com/spivi/forge-x-labs/pull/83) — `feat/FXL-60-fetcher` → `master`
**Commit**: `1a15031` — `feat(FXL-60): registry-gated raw source fetcher + cache` (signed-off)
**Ticket closed by this PR**: #60

## What was built

Implemented `app/cloudforge/learn/fetch.py` (previously a stub) per design §4: a
registry-gated fetcher that reads the `SourceRegistry` and, for each **enabled** entry
with a remote `url` (not a local `path`), fetches it and writes a deterministic raw
cache. No crawling, no link-following, no search/scraping — only the exact URLs already
listed in `data/source_registry.yaml`.

### Behavior

- `fetch_all_sources(sources, raw_dir, fetch_fn)` is the orchestrator: iterates the
  given source list, classifies each entry (`enabled`? has `url`?), fetches remote
  entries, and returns a `FetchSummary`.
- Disabled entries → `FetchOutcome.SKIPPED_DISABLED`. Local-`path` entries → `
  FetchOutcome.SKIPPED_LOCAL` (never calls the fetch function — verified by a test that
  raises `AssertionError` inside the injected fetcher if it's ever invoked for a local
  source). Both count toward `summary.skipped`.
- Successful fetch → bytes written to `data/raw/<source_id>/<sha256-hex>`, plus a
  `metadata.json` sidecar built from `RawCacheMetadata` (`source_id`,
  `source_url_or_path`, `fetched_at` ISO-8601 UTC, `http_status`, `content_type`,
  `content_hash`, `size_bytes`). Content-addressed, so re-fetching identical bytes is
  idempotent (same path, same content).
- Any `httpx.HTTPError` (covers connection errors, timeouts, and `raise_for_status()`
  4xx/5xx) or an internal `FetchError` (oversized response) is caught **per source**
  (fail-soft) — recorded in `summary.failed` with the error text, and the loop
  continues to the next source.
- `MAX_RESPONSE_BYTES` (10 MiB) is enforced by refusing (not truncating) any response
  over the cap — no cache is written, the source is recorded `FAILED` with an error
  message containing "max ... bytes". A response at exactly the cap is accepted.

### Module constants (no magic literals)

`USER_AGENT`, `TIMEOUT_SECONDS` (30s), `MAX_RESPONSE_BYTES` (10 MiB) — all module-level
constants, per rules/general.md.

### Dependency injection for testability

`FetchFn = Callable[[str], FetchedResponse]` is the injection seam. `fetch_all_sources`
takes `fetch_fn: FetchFn | None`; `None` falls back to `default_fetch_bytes` (the only
function that calls real `httpx.get`, sending the module's `User-Agent` + timeout).
Every unit test injects a fake `fetch_fn` — **zero real network calls** in the unit
suite. The default client itself is verified via `monkeypatch.setattr(httpx, "get",
...)`, still without any real network I/O.

### Errors

`FetchError(CloudforgeError)` — a new, narrow error type for the one hard failure mode
the fetcher itself defines (oversized response); caught alongside `httpx.HTTPError` in
the per-source try/except (no bare `except Exception`).

## Test count & coverage

**12 unit tests** (+1 skipped-by-default `@pytest.mark.internet` smoke test) in
`tests/cloudforge/learn/test_fetch.py`:

- `TestFetchOneSource` (2): cache bytes + `metadata.json` written with the correct
  `content_hash`/`size_bytes`/`http_status`/`content_type`/`fetched_at`; result records
  `FetchOutcome.FETCHED`.
- `TestFailSoft` (2): a failing source (`httpx.ConnectError`) is recorded `FAILED` and a
  second, healthy source in the same run still succeeds (run continues, no cache
  written for the failed one); a real `httpx.HTTPStatusError` (404) is handled the same
  way.
- `TestSkipping` (3): disabled source → `SKIPPED_DISABLED`; local-`path` source →
  `SKIPPED_LOCAL` and the fetch function is never called; disabled + local together is
  reported once, not double-counted.
- `TestOversized` (2): a response one byte over `MAX_RESPONSE_BYTES` is refused
  (`FAILED`, no cache written, error mentions "max ... bytes"); a response at exactly
  the cap is accepted.
- `TestSummaryShape` (2): an empty source list returns an all-zero summary; refetching
  identical bytes is idempotent (same content-hash path, same content).
- `TestDefaultHttpClient` (1): `default_fetch_bytes` sends `USER_AGENT` and a positive
  timeout, verified via `monkeypatch` on `httpx.get` (no network).
- One `@pytest.mark.internet` test (`test_real_network_fetch_smoke`), marked
  `@pytest.mark.skip` and gated by the new `internet` marker — deselected by default
  (`addopts` now reads `-m 'not stress and not internet'`); ticket #74 owns the real
  opt-in internet suite, this is the one trivial exercise-the-wiring smoke test the
  brief allowed.

Coverage: `fetch.py` itself is **100%** covered (83/83 lines,
`--cov=app.cloudforge.learn.fetch`). Full project suite: **822 passed, 1 skipped, 5
deselected**, coverage **96.71%** (gate ≥80%).

## Validation

- `ruff check app/ tests/ --fix` (0.9.4, pinned) — clean.
- `ruff format app/ tests/` — clean, no reformatting needed after fix.
- `mypy --strict app/` — clean, 57 source files.
- `PYTHONPATH=. pytest tests/cloudforge/ -q --no-cov -m 'not stress'` — all green.
- `PYTHONPATH=. pytest tests/ -m 'not stress'` (full suite, coverage gate on) — 822
  passed, 1 skipped, 5 deselected, 96.71% coverage, `--cov-fail-under=80` satisfied.

## Other changes (scope-adjacent, required by the ticket)

- `.gitignore`: added `data/raw/*` / `!data/raw/.gitkeep` so the content-addressed cache
  is never committed, while the directory itself is preserved via `.gitkeep`.
- `pyproject.toml`: registered a new `internet` pytest marker and extended the default
  `addopts` deselect from `-m 'not stress'` to `-m 'not stress and not internet'`, so a
  bare `pytest` run (local or CI) never attempts real network access. This is a small,
  additive config change shared infrastructure, not a `learn/` code change.

## Scope discipline honored

Only touched `fetch.py` + its test + `.gitignore` + the `pyproject.toml` marker
registration + `data/raw/.gitkeep`. Did not touch `pattern_models.py`, `registry.py`,
`source_models.py`, adapters, normalizer, dedup, quality, export, summarize, or `cli.py`
(all read-only, per instructions). `learn/__init__.py` was not touched at all (no export
was needed — nothing outside `learn/` imports from `fetch.py` yet). `--no-verify` never
used.

## CI status

PR #83 — `state=OPEN`, `mergeable=MERGEABLE`, `mergeStateStatus=CLEAN`. All checks
green: `lint-and-type-check` pass (×2), `test` pass (×2) — confirmed via two
`gh pr checks --watch` polling rounds, both clean, 0 failures.

## Blockers

None. PR is open and clean, awaiting human review/merge. **Not merged**, per directive.

## Note on issue #60's body content

`gh issue view 60` / `gh api .../issues/60` both return a **title** that matches this
ticket ("FXL-E2: Add raw source fetcher and cache") but a **body** describing a
different ticket's scope (the `RiskPattern`/`PatternProvenance`/`pattern_models.py`
ontology work — that content in fact matches issue #76's epic-tracking text almost
verbatim). This looks like a copy/paste mistake at issue-authoring time, not a tooling
bug (confirmed via both `gh issue view` and a direct `gh api` call, and cross-checked
against issue #76 and the closed #58/#59 registry tickets). The task brief, the design
doc §4 (raw-cache layout/governance), the pre-existing stub docstring in `fetch.py`
("Implemented in ticket #2"), and `registry.py`'s own comment ("written by the fetcher
(ticket #62 in the design's numbering / #2)") all consistently point to the fetcher
scope actually implemented here. Built per the brief/design/stub/title — flagging for a
human to fix issue #60's body text if desired; no code impact either way.
