#!/usr/bin/env python3
"""CI wall-clock instrumentation for the KPI ledger.

Queries the GitHub check-runs API for a commit SHA and computes end-to-end CI
wall-clock (max(completed_at) - min(started_at)) across non-cancelled check-runs,
appending a row to `.dev-context/kpis/ci-latency.csv` so `/debrief` can track CI
latency deltas over time.

Design (same posture as ledger_append.py):
* Fail-soft everywhere: any `gh api` failure or parse error returns None and skips
  the append; it NEVER blocks a merge.
* No new runtime dependencies — stdlib + `gh` CLI.
* Pure functions carry the logic and are unit-tested directly.

owner/repo come from --owner/--repo or `GITHUB_OWNER`/`GITHUB_REPO` in project.conf.

CLI:
    python scripts/ci_latency.py --ticket ABC-79 --pr 123 --sha <sha> \
        [--owner you --repo your-repo]
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
CI_LATENCY_CSV_PATH = PROJECT_DIR / ".dev-context" / "kpis" / "ci-latency.csv"
_PROJECT_CONF = PROJECT_DIR / ".dev-context" / "project.conf"

CI_LATENCY_FIELDNAMES = [
    "timestamp_utc",
    "ticket",
    "pr",
    "head_sha",
    "ci_wall_clock_s",
    "jobs_observed",
    "slowest_job",
]


def _conf(key: str, default: str = "") -> str:
    if not _PROJECT_CONF.exists():
        return default
    for line in _PROJECT_CONF.read_text().splitlines():
        if line.strip().startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return default


# --- pure helpers (no I/O) ------------------------------------------------


def _parse_iso(ts: str) -> dt.datetime | None:
    """Parse an ISO-8601 timestamp (with or without trailing Z) into UTC. None on error."""
    if not ts:
        return None
    try:
        return dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def compute_ci_wall_clock(check_runs_data: list[dict]) -> dict | None:
    """CI wall-clock from check-run API objects.

    Skips cancelled runs; needs >=1 run with both started_at + completed_at.
    wall_clock_s = max(completed_at) - min(started_at). slowest_job = latest-completing
    run's name. Returns {ci_wall_clock_s, jobs_observed, slowest_job} or None. Pure."""
    if not check_runs_data:
        return None
    eligible: list[tuple[dt.datetime, dt.datetime, str]] = []
    for run in check_runs_data:
        if (run.get("conclusion") or "").lower() == "cancelled":
            continue
        started = _parse_iso(run.get("started_at") or "")
        completed = _parse_iso(run.get("completed_at") or "")
        if started is None or completed is None:
            continue
        eligible.append((started, completed, str(run.get("name") or run.get("id") or "unknown")))
    if not eligible:
        return None
    min_started = min(e[0] for e in eligible)
    max_completed = max(e[1] for e in eligible)
    slowest = max(eligible, key=lambda e: e[1])
    return {
        "ci_wall_clock_s": round(max(0.0, (max_completed - min_started).total_seconds()), 1),
        "jobs_observed": len(eligible),
        "slowest_job": slowest[2],
    }


# --- I/O ------------------------------------------------------------------


def fetch_check_runs(owner: str, repo: str, sha: str) -> list[dict] | None:  # pragma: no cover
    """Fetch check-runs for a commit SHA via `gh api`. None on any failure (fail-soft)."""
    if not (owner and repo and sha):
        return None
    try:
        res = subprocess.run(
            ["gh", "api", f"repos/{owner}/{repo}/commits/{sha}/check-runs", "--paginate"],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(res.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
        return None
    if isinstance(data, list):
        runs: list[dict] = []
        for page in data:
            if isinstance(page, dict):
                runs.extend(page.get("check_runs") or [])
            elif isinstance(page, list):
                runs.extend(page)
        return runs
    if isinstance(data, dict):
        return data.get("check_runs") or []
    return None


def append_ci_latency_row(
    ticket: str, pr: int | str, sha: str, metrics: dict, *, csv_path: Path = CI_LATENCY_CSV_PATH
) -> dict:
    """Append one row to ci-latency.csv (creates header if absent; append-only)."""
    row = {
        "timestamp_utc": dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z"),
        "ticket": str(ticket),
        "pr": str(pr),
        "head_sha": str(sha),
        "ci_wall_clock_s": str(metrics.get("ci_wall_clock_s", "")),
        "jobs_observed": str(metrics.get("jobs_observed", "")),
        "slowest_job": str(metrics.get("slowest_job", "")),
    }
    new_file = not Path(csv_path).exists()
    with Path(csv_path).open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CI_LATENCY_FIELDNAMES)
        if new_file:
            writer.writeheader()
        writer.writerow(row)
    return row


def capture_ci_latency(
    owner: str,
    repo: str,
    ticket: str,
    pr: int | str,
    sha: str,
    *,
    csv_path: Path = CI_LATENCY_CSV_PATH,
) -> dict | None:
    """Fetch + compute + append CI wall-clock for a merged PR. None on any failure
    (fail-soft — a CI API failure MUST NOT block a merge)."""
    check_runs = fetch_check_runs(owner, repo, sha)
    if check_runs is None:
        return None
    metrics = compute_ci_wall_clock(check_runs)
    if metrics is None:
        return None
    return append_ci_latency_row(ticket, pr, sha, metrics, csv_path=csv_path)


# --- CLI ------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Compute CI wall-clock and append to ci-latency.csv")
    p.add_argument("--owner", default=_conf("GITHUB_OWNER"))
    p.add_argument("--repo", default=_conf("GITHUB_REPO"))
    p.add_argument("--ticket", required=True)
    p.add_argument("--pr", required=True)
    p.add_argument("--sha", required=True)
    p.add_argument("--csv", type=Path, default=CI_LATENCY_CSV_PATH, dest="csv_path")
    args = p.parse_args(argv)
    row = capture_ci_latency(
        args.owner, args.repo, args.ticket, args.pr, args.sha, csv_path=args.csv_path
    )
    if row is None:
        print(
            "ci_latency: no metrics (API failure / all cancelled / no owner-repo) — skipped",
            file=sys.stderr,
        )
        return 0  # fail-soft, not an error
    print(
        f"ci_latency: appended ticket={row['ticket']} pr={row['pr']} "
        f"ci_wall_clock_s={row['ci_wall_clock_s']} slowest={row['slowest_job']}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
