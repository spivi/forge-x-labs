#!/usr/bin/env python3
"""Capture an external code-review wave into kpis/reviews.csv.

dev-template has no reviews.csv writer by default; this is it. Two responsibilities:

1. **Quiescence poll** (`poll_review`) -- a bounded, adaptive-backoff poll for a
   reviewer bot's artifacts on a PR. Stops on QUIESCED (>=1 artifact seen AND no
   new artifact for a quiet window) or TIMEOUT (overall budget exhausted; soft-fail,
   records review_stale_s). Provider-agnostic: the reviewer bot login is a parameter,
   not a hardcoded `codex`. The network/`gh` feed is injected as a `fetch` callable so
   the loop is unit-tested without network or real sleeps.

2. **reviews.csv writer** (`build_review_row` / `append_review`) -- writes a 13-col
   row, migrating a legacy 11-col file to 13 on first write (adds the latency columns
   review_first_event_at + review_stale_s).

CLI:
    python scripts/review_capture.py --ticket ABC-2 --pr 42 --provider codex \
        --owner you --repo your-repo --reviewer-login "some-bot[bot]"
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

_REPO = Path(__file__).resolve().parent.parent
_REVIEWS = _REPO / ".dev-context" / "kpis" / "reviews.csv"

# 13-col schema = legacy 11 + the two latency columns.
REVIEW_COLUMNS = [
    "ticket",
    "pr",
    "provider",
    "reviewed_at",
    "cycles",
    "findings_total",
    "p1",
    "p2",
    "p3",
    "categories",
    "fix_commit_count",
    "review_first_event_at",
    "review_stale_s",
]
_LEGACY_REVIEW_COLUMNS = REVIEW_COLUMNS[:11]

QUIESCED = "QUIESCED"
TIMEOUT = "TIMEOUT"

_POLL_INITIAL_BACKOFF = 3.0
_POLL_BACKOFF_CAP = 20.0
_POLL_MAX_WAIT = 300.0
_POLL_QUIESCENCE = 40.0


# --- quiescence poll (pure loop; network injected) ------------------------


def poll_review(
    fetch: Callable[[str | None], list[dict[str, Any]]],
    *,
    since: str | None = None,
    max_wait: float = _POLL_MAX_WAIT,
    quiescence: float = _POLL_QUIESCENCE,
    initial_backoff: float = _POLL_INITIAL_BACKOFF,
    backoff_cap: float = _POLL_BACKOFF_CAP,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Adaptive-backoff poll for reviewer artifacts.

    `fetch(watermark)` returns artifacts strictly newer than `watermark` (each a
    dict with an `updated_at`/`created_at` ISO-8601 string). Returns a dict with
    status (QUIESCED|TIMEOUT), artifacts, watermark, first_event_at, review_stale_s."""
    start = clock()
    backoff = initial_backoff
    watermark = since
    seen: list[dict[str, Any]] = []
    first_event_at: str | None = None
    last_new_at: float | None = None

    while True:
        if clock() - start >= max_wait:
            return _poll_result(TIMEOUT, seen, watermark, first_event_at, clock() - start)

        new = fetch(watermark)
        if new:
            seen.extend(new)
            stamps = [str(a.get("updated_at") or a.get("created_at") or "") for a in new]
            stamps = [s for s in stamps if s]
            if stamps:
                newest = max(stamps)
                if watermark is None or newest > watermark:
                    watermark = newest
                if first_event_at is None:
                    first_event_at = min(stamps)
            last_new_at = clock()

        if seen and last_new_at is not None and (clock() - last_new_at) >= quiescence:
            return _poll_result(QUIESCED, seen, watermark, first_event_at, clock() - start)

        sleep(backoff)
        backoff = min(backoff * 2, backoff_cap)


def _poll_result(
    status: str, seen: list, watermark: str | None, first_event_at: str | None, stale: float
) -> dict[str, Any]:
    return {
        "status": status,
        "artifacts": seen,
        "watermark": watermark,
        "first_event_at": first_event_at,
        "review_stale_s": round(stale, 2),
    }


def gh_fetch(
    owner: str, repo: str, pr: int, reviewer_login: str
) -> Callable[[str | None], list[dict[str, Any]]]:
    """Build a `fetch(watermark)` over the three GitHub PR feeds, filtered to the
    reviewer bot login and to artifacts newer than the watermark. Network-bound;
    the returned closure is what poll_review consumes."""

    def fetch(watermark: str | None) -> list[dict[str, Any]]:  # pragma: no cover (network)
        out: list[dict[str, Any]] = []
        for path, feed in (
            (f"pulls/{pr}/reviews", "reviews"),
            (f"pulls/{pr}/comments", "inline"),
            (f"issues/{pr}/comments", "conversation"),
        ):
            try:
                res = subprocess.run(
                    ["gh", "api", f"repos/{owner}/{repo}/{path}", "--paginate"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                data = json.loads(res.stdout)
            except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
                continue
            for item in data:
                login = (item.get("user") or {}).get("login")
                if reviewer_login and login != reviewer_login:
                    continue
                updated = str(item.get("updated_at") or item.get("created_at") or "")
                if watermark and updated and updated <= watermark:
                    continue
                out.append({**item, "_feed": feed})
        return out

    return fetch


# --- reviews.csv writer (13-col, migrates legacy 11-col) ------------------


def build_review_row(
    ticket: str,
    pr: int,
    provider: str,
    *,
    summary: dict[str, Any] | None = None,
    poll_result: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Build a 13-col reviews.csv row. `summary` carries the finding counts; the
    latency columns come from `poll_result` (blank when not polled)."""
    s = summary or {}
    pr_ = poll_result or {}
    row = {c: "" for c in REVIEW_COLUMNS}
    row.update(
        {
            "ticket": ticket,
            "pr": str(pr),
            "provider": provider,
            "reviewed_at": str(s.get("reviewed_at", "")),
            "cycles": str(s.get("cycles", 0)),
            "findings_total": str(s.get("findings_total", 0)),
            "p1": str(s.get("p1", 0)),
            "p2": str(s.get("p2", 0)),
            "p3": str(s.get("p3", 0)),
            "categories": str(s.get("categories", "")),
            "fix_commit_count": str(s.get("fix_commit_count", 0)),
            "review_first_event_at": str(pr_.get("first_event_at") or ""),
            "review_stale_s": ""
            if pr_.get("review_stale_s") is None
            else str(pr_["review_stale_s"]),
        }
    )
    return row


def _header(path: Path) -> list[str]:
    if not path.exists():
        return []
    first = path.read_text().splitlines()
    return first[0].split(",") if first else []


def migrate_reviews_header(path: str | Path) -> bool:
    """Widen a legacy 11-col reviews.csv to the 13-col schema (back-fills the two
    latency columns as blank). Idempotent; returns True only if it rewrote."""
    p = Path(path)
    header = _header(p)
    if not header or header == REVIEW_COLUMNS:
        return False
    with p.open(newline="") as f:
        rows = list(csv.DictReader(f))
    _write(p, rows)
    return True


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REVIEW_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in REVIEW_COLUMNS})


def append_review(row: dict[str, str], path: str | Path = _REVIEWS) -> None:
    """Append one review row, migrating a legacy 11-col file to 13-col first."""
    p = Path(path)
    if not p.exists():
        p.write_text(",".join(REVIEW_COLUMNS) + "\n")
    else:
        migrate_reviews_header(p)
    with p.open("a", newline="") as f:
        csv.writer(f, quoting=csv.QUOTE_MINIMAL).writerow([row.get(c, "") for c in REVIEW_COLUMNS])


def render_row_csv(row: dict[str, str]) -> str:
    """Serialize a single row (for --dry-run / logging)."""
    buf = io.StringIO()
    csv.writer(buf).writerow([row.get(c, "") for c in REVIEW_COLUMNS])
    return buf.getvalue().strip()


# --- CLI ------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Capture a review wave into reviews.csv")
    p.add_argument("--ticket", required=True)
    p.add_argument("--pr", type=int, required=True)
    p.add_argument("--provider", default="codex")
    p.add_argument("--owner", default="")
    p.add_argument("--repo", default="")
    p.add_argument("--reviewer-login", default="", help="bot login to filter on ('' = any)")
    p.add_argument("--since", default=None)
    p.add_argument("--reviews", type=Path, default=_REVIEWS)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    poll_result = None
    if args.owner and args.repo:  # pragma: no cover (network)
        fetch = gh_fetch(args.owner, args.repo, args.pr, args.reviewer_login)
        poll_result = poll_review(fetch, since=args.since)

    row = build_review_row(args.ticket, args.pr, args.provider, poll_result=poll_result)
    if args.dry_run:
        print(render_row_csv(row))
        return 0
    append_review(row, path=args.reviews)
    status = (poll_result or {}).get("status", "no-poll")
    print(f"captured review: ticket={args.ticket} pr={args.pr} status={status}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
