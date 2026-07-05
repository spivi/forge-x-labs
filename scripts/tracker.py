#!/usr/bin/env python3
"""Tracker abstraction seam -- CSV-canonical, optional external mirror.

`.dev-context/kpis/estimates.csv` is the source of truth. Every `set`/`plan`
writes the CSV first, then best-effort mirrors to the configured backend
(`TRACKER_BACKEND` in project.conf: none | linear | github_projects). Reads
always come from the CSV, so the full learning loop runs with no tracker.

Key commands:
    tracker.py plan <ticket> --type feature --effort M [--labels ..] [--priority ..]
    tracker.py ready <ticket>          # exit 0 if launchable, else 1 + reason
    tracker.py estimate get|set <ticket> [minutes]
    tracker.py model    get|set <ticket> [model]
    tracker.py status   get|set <ticket> [status]
    tracker.py refresh                 # re-seed planned tickets from learned factors
    tracker.py lead-time <ticket>      # JSON {in_progress, done, lead_minutes}
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import estimator  # noqa: E402  (sibling module)
from trackers import store  # noqa: E402

_ESTIMATES = _REPO / ".dev-context" / "kpis" / "estimates.csv"
_PROJECT_CONF = _REPO / ".dev-context" / "project.conf"

# Statuses from which a ticket may be launched / re-seeded.
LAUNCHABLE = {"planned", "ready", "in_progress"}
RESEEDABLE = ("planned", "ready")


# --- config / backend -----------------------------------------------------


def read_conf(key: str, default: str = "") -> str:
    if not _PROJECT_CONF.exists():
        return default
    for line in _PROJECT_CONF.read_text().splitlines():
        line = line.strip()
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return default


def _load_backend():
    name = read_conf("TRACKER_BACKEND", "none")
    try:
        if name == "linear":
            from trackers import linear as backend
        elif name == "github_projects":
            from trackers import github_projects as backend
        else:
            from trackers import none_backend as backend
        return backend
    except Exception:
        from trackers import none_backend as backend

        return backend


def _mirror(ticket: str, fields: dict[str, Any]) -> None:
    """Best-effort push to the external tracker. Never raises."""
    with contextlib.suppress(Exception):
        _load_backend().mirror(ticket, fields)


# --- canonical logic (pure, path-injectable) ------------------------------


def is_ready(path: str | Path, ticket: str) -> tuple[bool, str]:
    """The hard planning gate: a ticket is launchable iff it has a row with an
    estimate, a recommended model, and a launchable status."""
    row = store.get_row(path, ticket)
    if row is None:
        return False, f"{ticket} not found in estimates.csv -- run /prd first"
    if not (row.get("estimate_minutes") or "").strip():
        return False, f"{ticket} has no estimate_minutes -- run /prd first"
    if not (row.get("recommended_model") or "").strip():
        return False, f"{ticket} has no recommended_model -- run /prd first"
    status = (row.get("status") or "").strip()
    if status and status not in LAUNCHABLE:
        return False, f"{ticket} status '{status}' is not launchable"
    return True, "ready"


def refresh(
    path: str | Path,
    *,
    seed: dict[str, Any],
    calibration: dict[str, Any],
    policy: dict[str, Any],
    statuses: tuple[str, ...] = RESEEDABLE,
) -> list[str]:
    """Re-seed estimate_minutes + recommended_model for not-yet-started tickets
    from the immutable seed scaled by current learned factors. Idempotent by
    construction (same inputs -> same outputs). Returns the changed tickets."""
    changed: list[str] = []
    for row in store.read_rows(path):
        if (row.get("status") or "").strip() not in statuses:
            continue
        type_ = row.get("type") or ""
        effort = (row.get("effort") or "").strip() or estimator.effort_from_labels(
            row.get("labels")
        )
        new_est = estimator.estimate_minutes(type_, effort, seed, calibration)
        new_model = estimator.recommend_model(type_, effort, row.get("labels"), seed, policy)
        if str(new_est) != (row.get("estimate_minutes") or "") or new_model != (
            row.get("recommended_model") or ""
        ):
            store.upsert(
                path,
                row["ticket"],
                estimate_minutes=new_est,
                recommended_model=new_model,
            )
            changed.append(row["ticket"])
    return changed


# Typed dimensions to back-fill from the legacy `labels` string on migration.
# (col, label_prefix, is_effort) -- effort is constrained (S/M/L/XL), the rest open.
_TYPED_BACKFILL = (
    ("effort", "effort:", True),
    ("milestone", "milestone:", False),
    ("risk", "risk:", False),
    ("area", "area:", False),
)


def migrate_estimates_header(path: str | Path) -> bool:
    """Idempotently widen estimates.csv to the canonical 17-col COLUMNS, back-filling
    the typed dimension columns from the legacy `labels` string. Returns True if the
    file was rewritten, False if it was already canonical or absent."""
    p = Path(path)
    if not p.exists() or store._columns(p) == list(store.COLUMNS):
        return False
    rows = store.read_rows(p)
    for row in rows:
        labels = row.get("labels", "")
        for col, prefix, is_effort in _TYPED_BACKFILL:
            if (row.get(col) or "").strip():
                continue
            val = (
                estimator.effort_from_labels(labels)
                if is_effort
                else estimator.dim_from_labels(labels, prefix)
            )
            if val:
                row[col] = val
    store._write(p, list(store.COLUMNS), rows)
    return True


# --- CLI ------------------------------------------------------------------


def _cmd_plan(args) -> int:
    effort = args.effort or estimator.effort_from_labels(args.labels)
    plan = estimator.plan_ticket(
        args.type,
        effort,
        args.labels,
        estimator.load_seed(),
        estimator.load_calibration(),
        estimator.load_model_policy(),
    )
    fields = {
        "estimate_minutes": plan["estimate_minutes"],
        "recommended_model": plan["recommended_model"],
        "type": args.type,
        "labels": args.labels,
        "effort": effort or args.effort or "",
        "milestone": args.milestone,
        "risk": args.risk,
        "area": args.area,
        "priority": args.priority,
        "status": "planned",
    }
    store.upsert(_ESTIMATES, args.ticket, **fields)
    _mirror(args.ticket, fields)
    print(json.dumps({"ticket": args.ticket, **plan, "status": "planned"}))
    return 0


def _cmd_migrate(args) -> int:
    changed = migrate_estimates_header(_ESTIMATES)
    print(json.dumps({"migrated": changed}))
    return 0


def _cmd_ready(args) -> int:
    ok, reason = is_ready(_ESTIMATES, args.ticket)
    print(reason)
    return 0 if ok else 1


def _cmd_field(args, field: str) -> int:
    if args.action == "get":
        row = store.get_row(_ESTIMATES, args.ticket)
        print((row or {}).get(field, ""))
        return 0
    store.upsert(_ESTIMATES, args.ticket, **{field: args.value})
    _mirror(args.ticket, {field: args.value})
    return 0


def _cmd_refresh(args) -> int:
    changed = refresh(
        _ESTIMATES,
        seed=estimator.load_seed(),
        calibration=estimator.load_calibration(),
        policy=estimator.load_model_policy(),
    )
    for ticket in changed:
        row = store.get_row(_ESTIMATES, ticket) or {}
        _mirror(
            ticket,
            {
                "estimate_minutes": row.get("estimate_minutes"),
                "recommended_model": row.get("recommended_model"),
            },
        )
    print(json.dumps({"refreshed": changed}))
    return 0


def _cmd_lead_time(args) -> int:
    try:
        result = _load_backend().lead_time(args.ticket)
    except Exception:
        result = None
    print(json.dumps(result or {"in_progress": None, "done": None, "lead_minutes": None}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tracker-agnostic estimate/model store")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_plan = sub.add_parser("plan", help="seed a ticket (estimate + model)")
    p_plan.add_argument("ticket")
    p_plan.add_argument("--type", required=True)
    p_plan.add_argument("--effort", default=None)
    p_plan.add_argument("--milestone", default="")
    p_plan.add_argument("--risk", default="")
    p_plan.add_argument("--area", default="")
    p_plan.add_argument("--labels", default="")
    p_plan.add_argument("--priority", default="")

    p_ready = sub.add_parser("ready", help="planning-gate check (exit 0/1)")
    p_ready.add_argument("ticket")

    sub.add_parser("migrate", help="widen estimates.csv to the typed 17-col schema")

    for name in ("estimate", "model", "status"):
        sp = sub.add_parser(name, help=f"get/set {name}")
        sp.add_argument("action", choices=["get", "set"])
        sp.add_argument("ticket")
        sp.add_argument("value", nargs="?", default="")

    sub.add_parser("refresh", help="re-seed planned tickets from learned factors")

    p_lt = sub.add_parser("lead-time", help="lead time from the external tracker")
    p_lt.add_argument("ticket")

    args = parser.parse_args(argv)
    field_for = {"estimate": "estimate_minutes", "model": "recommended_model", "status": "status"}
    if args.cmd == "plan":
        return _cmd_plan(args)
    if args.cmd == "ready":
        return _cmd_ready(args)
    if args.cmd == "migrate":
        return _cmd_migrate(args)
    if args.cmd in field_for:
        return _cmd_field(args, field_for[args.cmd])
    if args.cmd == "refresh":
        return _cmd_refresh(args)
    if args.cmd == "lead-time":
        return _cmd_lead_time(args)
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
