#!/usr/bin/env python3
"""Closed-loop calibration engine.

Joins planning estimates (kpis/estimates.csv) against measured actuals
(cost-ledger.csv duration_sec + cost + tokens) and review outcomes
(kpis/reviews.csv), then learns:

  - calibration.json : per type/effort factor = shrunk median(actual/estimate),
    so the next estimate self-corrects (empirical-Bayes shrinkage toward 1.0).
  - model-policy.json : the cheapest model that delivered without overrun or a
    P1 finding -- "good enough, most economic" routing.
  - recommendations.md : prioritized P1/P2/P3 call-to-action.

Pure analytical functions take plain dict rows and are unit-tested in isolation.
The CLI wires them to the project's CSV/JSON files. No third-party deps -- only
the stdlib `statistics` module.

CLI:
    python scripts/debrief.py [--dry-run]
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import json
import math
import statistics
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
if str(_HERE) not in sys.path:  # let `import dataset` resolve from any load context
    sys.path.insert(0, str(_HERE))
_DEV = _REPO / ".dev-context"
_ESTIMATES = _DEV / "kpis" / "estimates.csv"
_REVIEWS = _DEV / "kpis" / "reviews.csv"
_LEDGER = _DEV / "cost-ledger.csv"
_CALIBRATION = _DEV / "kpis" / "calibration.json"
_MODEL_POLICY = _DEV / "kpis" / "model-policy.json"
_RECOMMENDATIONS = _DEV / "kpis" / "recommendations.md"
_SEED = _DEV / "planning" / "base-estimates.yml"
_DATASET = _DEV / "kpis" / "dataset.csv"
_FEATURES = _DEV / "kpis" / "FEATURES.md"

DEFAULT_TIERS = ["haiku", "sonnet", "opus"]
PRIOR = 1.0
PRIOR_WEIGHT = 3
CLAMP = (0.25, 4.0)


# --- helpers --------------------------------------------------------------


def _num(value: Any, cast=float, default=0):
    try:
        return cast(value)
    except (TypeError, ValueError):
        return default


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def effective_model(models: list[str], tiers: list[str]) -> str | None:
    """Highest-tier model family present among the session model strings."""
    best = None
    best_tier = -1
    for raw in models:
        for i, fam in enumerate(tiers):
            if fam in (raw or "") and i > best_tier:
                best, best_tier = fam, i
    return best


# --- aggregation ----------------------------------------------------------


def sum_actuals(ledger_rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    """Aggregate cost-ledger rows per ticket: duration, sessions, cost, tokens."""
    out: dict[str, dict[str, Any]] = {}
    for row in ledger_rows:
        ticket = row.get("ticket") or ""
        if not ticket or ticket == "untracked":
            continue
        agg = out.setdefault(
            ticket,
            {
                "duration_sec": 0,
                "sessions": 0,
                "cost_usd": 0.0,
                "models": [],
                "tokens_in": 0,
                "tokens_out": 0,
            },
        )
        agg["duration_sec"] += _num(row.get("duration_sec"), int, 0)
        agg["sessions"] += 1
        # Prefer billed_usd (wallet impact); fall back to compute estimate.
        cost = _num(row.get("billed_usd"), float, 0.0)
        if cost == 0.0:
            cost = _num(row.get("compute_cost_usd"), float, 0.0)
        agg["cost_usd"] += cost
        if row.get("model"):
            agg["models"].append(row["model"])
        agg["tokens_in"] += (
            _num(row.get("input_tokens"), int, 0)
            + _num(row.get("cache_creation_tokens"), int, 0)
            + _num(row.get("cache_read_tokens"), int, 0)
        )
        agg["tokens_out"] += _num(row.get("output_tokens"), int, 0)
    return out


def _effort(labels: str | None) -> str | None:
    import re

    m = re.search(r"effort:(XL|[SML])", labels or "", re.IGNORECASE)
    return m.group(1).upper() if m else None


def _label_dim(labels: str | None, prefix: str) -> str:
    """Generic open-vocab dimension parse from the legacy `labels` string: the
    token after `prefix` (e.g. "risk:", "area:", "milestone:"). "" if absent."""
    import re

    m = re.search(rf"{re.escape(prefix)}([^;,\s]+)", labels or "", re.IGNORECASE)
    return m.group(1) if m else ""


def build_runs(
    estimate_rows: list[dict[str, str]],
    actuals: dict[str, dict[str, Any]],
    tiers: list[str],
) -> list[dict[str, Any]]:
    """Join estimates to actuals into runs with an actual/estimate ratio."""
    runs = []
    for row in estimate_rows:
        ticket = row.get("ticket") or ""
        est = _num(row.get("estimate_minutes"), float, 0.0)
        act = actuals.get(ticket)
        if not ticket or est <= 0 or act is None:
            continue
        actual_min = act["duration_sec"] / 60.0
        if actual_min <= 0:
            continue
        labels = row.get("labels") or ""
        runs.append(
            {
                "ticket": ticket,
                "type": row.get("type") or "",
                "labels": labels,
                # Typed columns win; fall back to the legacy `labels` string.
                "effort": (row.get("effort") or "").strip() or _effort(labels),
                "risk": (row.get("risk") or "").strip() or _label_dim(labels, "risk:"),
                "area": (row.get("area") or "").strip() or _label_dim(labels, "area:"),
                "milestone": (row.get("milestone") or "").strip()
                or _label_dim(labels, "milestone:"),
                "estimate_min": est,
                "actual_min": actual_min,
                "ratio": actual_min / est,
                "sessions": act["sessions"],
                "cost_usd": act["cost_usd"],
                "recommended_model": row.get("recommended_model") or "",
                "effective_model": effective_model(act["models"], tiers)
                or (row.get("recommended_model") or ""),
                "tokens_in": act["tokens_in"],
                "tokens_out": act["tokens_out"],
                "scope_changed": _truthy(row.get("scope_changed")),
            }
        )
    return runs


# --- suitability ----------------------------------------------------------


def classify_suitability(
    run: dict[str, Any],
    p1: int,
    p2: int,
    tiers: list[str],
    effort_floor: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Decide whether the model used was underpowered / overkill / well-matched."""
    model = run.get("effective_model") or run.get("recommended_model") or ""
    try:
        cur = tiers.index(model)
    except ValueError:
        return {"verdict": "unknown", "reason": "no model data", "suggested_model": model}

    floor_model = (effort_floor or {}).get(run.get("effort"))
    floor = tiers.index(floor_model) if floor_model in tiers else 0
    ratio = run.get("ratio", 1.0)
    sessions = run.get("sessions", 1)

    if (ratio >= 1.75 or sessions >= 3) and cur < len(tiers) - 1:
        return {
            "verdict": "underpowered",
            "reason": f"ratio {ratio:.2f}, {sessions} session(s) on {model}",
            "suggested_model": tiers[cur + 1],
        }
    if ratio < 0.5 and sessions <= 1 and p1 == 0 and p2 == 0 and cur > floor:
        return {
            "verdict": "overkill",
            "reason": f"ratio {ratio:.2f}, clean & fast on {model}",
            "suggested_model": tiers[cur - 1],
        }
    return {"verdict": "well-matched", "reason": f"ratio {ratio:.2f}", "suggested_model": model}


# --- calibration ----------------------------------------------------------


def _dims(run: dict[str, Any]) -> list[str]:
    """Calibration/policy slicing keys for a run. Typed dimensions are emitted only
    when non-blank, so empty dims never create junk buckets (min_samples drops the
    rest). milestone is intentionally excluded -- it is temporal, not predictive."""
    dims = [f"type:{run['type']}"] if run.get("type") else []
    if run.get("effort"):
        dims.append(f"label:effort:{run['effort']}")
    if run.get("risk"):
        dims.append(f"label:risk:{run['risk']}")
    if run.get("area"):
        dims.append(f"label:area:{run['area']}")
    return dims


def compute_calibration(
    runs: list[dict[str, Any]],
    min_samples: int = 3,
    clamp: tuple[float, float] = CLAMP,
    prior: float = PRIOR,
    weight: int = PRIOR_WEIGHT,
) -> dict[str, Any]:
    """Per-dimension factor = shrunk median(actual/estimate), 95% CI, clamped.
    scope_changed runs are excluded (partial work distorts the signal)."""
    buckets: dict[str, list[float]] = {}
    for run in runs:
        if run.get("scope_changed"):
            continue
        for dim in _dims(run):
            buckets.setdefault(dim, []).append(run["ratio"])

    factors: dict[str, Any] = {}
    for dim, ratios in buckets.items():
        n = len(ratios)
        if n < min_samples:
            continue
        median = statistics.median(ratios)
        shrunk = (n * median + weight * prior) / (n + weight)
        sd = statistics.pstdev(ratios) if n > 1 else 0.0
        stderr = 1.2533 * sd / math.sqrt(n) if n else 0.0
        lo, hi = clamp
        factors[dim] = {
            "factor": round(max(lo, min(hi, shrunk)), 3),
            "samples": n,
            "ci_low": round(max(lo, shrunk - 1.96 * stderr), 3),
            "ci_high": round(min(hi, shrunk + 1.96 * stderr), 3),
        }
    return {
        "_meta": {
            "description": "Per-dimension estimate factors learned by /debrief.",
            "min_samples": min_samples,
            "clamp": list(clamp),
            "prior": prior,
            "prior_weight": weight,
        },
        "factors": factors,
    }


# --- model policy ---------------------------------------------------------


def recommend_models(
    runs: list[dict[str, Any]],
    min_samples: int = 3,
    tiers: list[str] | None = None,
    effort_floor: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Learn the cheapest-sufficient model per dimension from suitability votes."""
    tiers = tiers or DEFAULT_TIERS
    effort_floor = effort_floor or {}
    buckets: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        if run.get("scope_changed"):
            continue
        for dim in _dims(run):
            buckets.setdefault(dim, []).append(run)

    learned: dict[str, Any] = {}
    for dim, group in buckets.items():
        if len(group) < min_samples:
            continue
        effort = group[0].get("effort")
        floor_model = effort_floor.get(effort)
        floor = tiers.index(floor_model) if floor_model in tiers else 0

        verdicts = Counter()
        suggested_tiers = []
        for run in group:
            v = classify_suitability(run, run.get("p1", 0), run.get("p2", 0), tiers, effort_floor)
            verdicts[v["verdict"]] += 1
            if v["suggested_model"] in tiers:
                suggested_tiers.append(tiers.index(v["suggested_model"]))

        if verdicts["underpowered"] > verdicts["overkill"]:
            rec_tier = max(suggested_tiers) if suggested_tiers else floor
        elif verdicts["overkill"] > verdicts["underpowered"]:
            rec_tier = floor  # cheapest-sufficient: drop to the floor
        else:
            modes = Counter(
                tiers.index(r["effective_model"])
                for r in group
                if r.get("effective_model") in tiers
            )
            rec_tier = modes.most_common(1)[0][0] if modes else floor
        rec_tier = max(rec_tier, floor)  # never below the effort floor

        costs = [r["cost_usd"] for r in group]
        learned[dim] = {
            "recommended_model": tiers[rec_tier],
            "samples": len(group),
            "verdicts": dict(verdicts),
            "avg_cost_usd": round(sum(costs) / len(costs), 4) if costs else 0.0,
            "rationale": (
                f"{verdicts['underpowered']} underpowered / {verdicts['overkill']} "
                f"overkill / {verdicts['well-matched']} well-matched "
                f"over {len(group)} runs" + (f" [floor: {floor_model}]" if floor_model else "")
            ),
        }
    return {
        "_meta": {"description": "Model routing learned from suitability verdicts."},
        "base_policy": {},
        "learned": learned,
    }


# --- recommendations ------------------------------------------------------


def generate_recommendations(
    calibration: dict[str, Any], model_policy: dict[str, Any]
) -> list[dict[str, Any]]:
    """Turn learned factors/policy into prioritized call-to-action items."""
    recs = []
    for dim, f in calibration.get("factors", {}).items():
        drift = abs(f["factor"] - 1.0)
        if drift >= 0.5:
            direction = "over-predicts" if f["factor"] < 1.0 else "under-predicts"
            recs.append(
                {
                    "priority": 2 if drift < 1.0 else 1,
                    "category": "tune",
                    "title": f"Estimator {direction} {dim}",
                    "signal": f"factor {f['factor']} over {f['samples']} runs "
                    f"(CI {f['ci_low']}-{f['ci_high']})",
                    "target": "scripts/estimator.py + kpis/calibration.json (auto-applied)",
                    "change": "Calibration factor applied; recheck next debrief.",
                }
            )
    for dim, p in model_policy.get("learned", {}).items():
        v = p.get("verdicts", {})
        if v.get("underpowered", 0) > v.get("well-matched", 0):
            recs.append(
                {
                    "priority": 2,
                    "category": "tune",
                    "title": f"{dim} is underpowered -> {p['recommended_model']}",
                    "signal": p["rationale"],
                    "target": ".dev-context/agents/scrum_master.md + kpis/model-policy.json",
                    "change": f"Up-tier {dim} to {p['recommended_model']}.",
                }
            )
        elif v.get("overkill", 0) > v.get("well-matched", 0):
            recs.append(
                {
                    "priority": 3,
                    "category": "tune",
                    "title": f"{dim} is overkill -> {p['recommended_model']}",
                    "signal": p["rationale"],
                    "target": "kpis/model-policy.json",
                    "change": f"Down-tier {dim} to {p['recommended_model']} (saves cost).",
                }
            )
    return sorted(recs, key=lambda r: r["priority"])


def render_markdown(
    runs: list[dict[str, Any]],
    calibration: dict[str, Any],
    model_policy: dict[str, Any],
    recommendations: list[dict[str, Any]],
) -> str:
    lines = ["# Debrief Report", "", f"Runs analyzed: {len(runs)}", ""]
    lines.append("## Calibration factors")
    if calibration.get("factors"):
        lines.append("| dimension | factor | samples | 95% CI |")
        lines.append("|---|---|---|---|")
        for dim, f in calibration["factors"].items():
            lines.append(
                f"| {dim} | {f['factor']} | {f['samples']} | {f['ci_low']}-{f['ci_high']} |"
            )
    else:
        lines.append("_Not enough samples yet._")
    lines.append("")
    lines.append("## Model policy (cheapest-sufficient)")
    if model_policy.get("learned"):
        lines.append("| dimension | model | avg cost | rationale |")
        lines.append("|---|---|---|---|")
        for dim, p in model_policy["learned"].items():
            lines.append(
                f"| {dim} | {p['recommended_model']} | ${p['avg_cost_usd']} | {p['rationale']} |"
            )
    else:
        lines.append("_Not enough samples yet._")
    lines.append("")
    lines.append("## Call-to-action")
    if recommendations:
        for r in recommendations:
            lines.append(
                f"- **[{r['category'].upper()}] {r['title']}** (P{r['priority']}) "
                f"-- {r['signal']}. Target: `{r['target']}`. {r['change']}"
            )
    else:
        lines.append("_Nothing actionable this round._")
    return "\n".join(lines) + "\n"


# --- IO + CLI -------------------------------------------------------------


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def _reviews_by_ticket(rows: list[dict[str, str]]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for row in rows:
        t = row.get("ticket") or ""
        agg = out.setdefault(t, {"p1": 0, "p2": 0})
        agg["p1"] += _num(row.get("p1"), int, 0)
        agg["p2"] += _num(row.get("p2"), int, 0)
    return out


def _load_floor() -> dict[str, str]:
    try:
        import yaml

        if _SEED.exists():
            return (yaml.safe_load(_SEED.read_text()) or {}).get("effort_floor", {})
    except Exception:
        pass
    return {}


def export_dataset() -> bool:
    """Best-effort ML dataset export (dataset.csv + FEATURES.md), reusing this
    module's path constants so it honours the same monkeypatching/CLI overrides.
    Never raises -- a dataset error must not abort calibration. Returns success."""
    try:
        import dataset  # noqa: PLC0415  (sibling; lazy import avoids a cycle)

        rows = dataset.build_dataset(
            _read_csv(_ESTIMATES), _read_csv(_LEDGER), _read_csv(_REVIEWS), DEFAULT_TIERS
        )
        dataset.write_csv(rows, _DATASET)
        _FEATURES.write_text(dataset.render_features_md())
        return True
    except Exception:  # noqa: BLE001  (fail-soft by design)
        return False


def run_debrief(dry_run: bool = False) -> dict[str, Any]:
    actuals = sum_actuals(_read_csv(_LEDGER))
    runs = build_runs(_read_csv(_ESTIMATES), actuals, DEFAULT_TIERS)
    reviews = _reviews_by_ticket(_read_csv(_REVIEWS))
    for run in runs:
        rv = reviews.get(run["ticket"], {})
        run["p1"], run["p2"] = rv.get("p1", 0), rv.get("p2", 0)

    floor = _load_floor()
    calibration = compute_calibration(runs)
    model_policy = recommend_models(runs, tiers=DEFAULT_TIERS, effort_floor=floor)
    recs = generate_recommendations(calibration, model_policy)
    report = render_markdown(runs, calibration, model_policy, recs)

    if not dry_run:
        _CALIBRATION.write_text(json.dumps(calibration, indent=2) + "\n")
        _MODEL_POLICY.write_text(json.dumps(model_policy, indent=2) + "\n")
        with _RECOMMENDATIONS.open("a") as f:
            f.write("\n## debrief run\n\n")
            for r in recs:
                f.write(
                    f"- **[{r['category'].upper()}] {r['title']}** (P{r['priority']}) "
                    f"-- {r['signal']}. Target: `{r['target']}`. {r['change']}\n"
                )
        export_dataset()  # refresh the ML-ready dataset.csv + FEATURES.md (fail-soft)
    return {
        "runs": runs,
        "calibration": calibration,
        "model_policy": model_policy,
        "recommendations": recs,
        "report": report,
    }


def _cli_routing_thresholds(op: str, avg_ms: float, fallback_rate: float) -> list[str]:
    """Threshold-based calls-to-action for the harness-router (Gemini) ledger."""
    actions: list[str] = []
    if avg_ms > 5000:
        actions.append(
            f"ACTION: {op} avg {avg_ms:.0f}ms > 5000ms threshold"
            " — reconsider external routing for this operation"
        )
    if fallback_rate > 0.20:
        actions.append(
            f"ACTION: {op} fallback rate {fallback_rate:.0%} > 20%"
            " — check Gemini quota / upgrade tier (GEMINI_MODEL)"
        )
    return actions


def cli_routing_report(kpis_dir: Path) -> str:
    """Summarize the harness-router (Gemini) ledger: per-op latency, fallback, skips.

    Reads ``<kpis_dir>/cli-routing.csv`` (written by scripts/harness_router.sh).
    Fail-soft: a missing/empty ledger yields an explanatory line, never raises.
    """
    from collections import defaultdict

    ledger = kpis_dir / "cli-routing.csv"
    if not ledger.exists():
        return "cli-routing.csv not found — no external CLI calls recorded yet"
    with ledger.open() as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return "cli-routing.csv is empty"
    by_op: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        by_op[r.get("operation", "?")].append(r)
    lines = [f"CLI Routing Report — {len(rows)} total calls\n"]
    actions: list[str] = []
    for op, op_rows in sorted(by_op.items()):
        n = len(op_rows)
        avg_ms = sum(int(r.get("wall_clock_ms") or 0) for r in op_rows) / n
        fb = sum(1 for r in op_rows if r.get("fallback") == "1") / n
        skipped = sum(1 for r in op_rows if r.get("claude_skipped") == "1")
        lines.append(
            f"[{op}] n={n}  avg={avg_ms:.0f}ms  fallback={fb:.0%}  claude_skipped={skipped}"
        )
        actions.extend(_cli_routing_thresholds(op, avg_ms, fb))
    if actions:
        lines += ["", "--- CALLS TO ACTION ---"] + actions
    else:
        lines.append("All thresholds OK.")
    return "\n".join(lines)


def format_rails_coverage(kpis_dir: Path, merged_tickets: list[str]) -> str:
    """Render the Rails-coverage KPI for a wave or iteration.

    Reads ``<kpis_dir>/rails.csv`` via ``rails.rails_coverage`` (fail-soft: a
    missing ledger yields zero coverage). Consumed by ``/debrief`` to surface
    how many merged tickets carried Rail evidence (see rules/rails.md).
    """
    import rails  # local import keeps the rails ledger optional

    cov = rails.rails_coverage(kpis_dir / "rails.csv", merged_tickets)
    return (
        "## Rails coverage\n"
        f"- Coverage: {cov['with_claim']}/{cov['merged']} merged tickets "
        f"carry Rail evidence ({cov['coverage_pct']:.1f}%)\n"
        f"- R/U split: R={cov['r_count']} U={cov['u_count']}\n"
        f"- Measurable R deltas: {cov['measurable_r_count']}"
    )


# --- in-session AI review gate (record + audit) ---------------------------
# The fresh-context reviewer (see .claude/skills/develop/references/) returns a
# structured JSON verdict; these helpers record it to reviews.csv and post the
# GitHub-visible audit (PR comment + the SHA-keyed `ai-code-review` commit status
# the recheck hook + merge gate read). All fail soft — never block a merge.


def review_status_state(verdict: dict[str, Any]) -> str:
    """Map a reviewer verdict to the ``ai-code-review`` commit-status state.

    ``success`` only when the reviewer PASSED with zero unresolved P1; ``failure``
    otherwise. The verdict JSON is LLM-generated and can be internally inconsistent
    (``verdict="PASS"`` while a ``findings[]`` entry is ``severity="P1"``), so we
    **fail closed**: a P1 signal from EITHER ``counts.p1`` OR any ``findings[]``
    severity blocks success — an inconsistent verdict can never bypass the gate.
    """
    counts = verdict.get("counts") or {}
    p1 = int(counts.get("p1", 0) or 0)
    findings_p1 = sum(
        1
        for f in (verdict.get("findings") or [])
        if str(f.get("severity", "")).strip().upper() == "P1"
    )
    passed = str(verdict.get("verdict", "")).strip().upper() == "PASS"
    return "success" if (passed and p1 == 0 and findings_p1 == 0) else "failure"


def record_review_from_verdict(
    kpis_dir: Path, verdict: dict[str, Any], *, dry_run: bool = False
) -> dict[str, str]:
    """Record a fresh-context reviewer's JSON verdict to reviews.csv (fail-soft).

    Reuses the template's existing 13-col writer (review_capture.build_review_row +
    append_review). ``provider`` is derived from ``reviewer_model`` so /debrief
    correlates by model (sonnet -> ``claude``; opus -> ``claude-opus``). The
    process-insight fields are surfaced in the PR comment, not the CSV.
    """
    import review_capture

    counts = verdict.get("counts") or {}
    findings = verdict.get("findings") or []
    cats: Counter[str] = Counter()
    for f in findings:
        cats[str(f.get("category") or "other").strip() or "other"] += 1
    reviewer_model = str(verdict.get("reviewer_model") or "").strip().lower()
    provider = "claude-opus" if reviewer_model == "opus" else "claude"
    summary = {
        "reviewed_at": str(verdict.get("reviewed_at", "") or ""),
        "cycles": int(verdict.get("cycle", 1) or 1),
        "findings_total": int(counts.get("total", len(findings)) or 0),
        "p1": int(counts.get("p1", 0) or 0),
        "p2": int(counts.get("p2", 0) or 0),
        "p3": int(counts.get("p3", 0) or 0),
        "categories": ";".join(f"{k}:{v}" for k, v in sorted(cats.items())),
        "fix_commit_count": int(verdict.get("fix_commit_count", 0) or 0),
    }
    row = review_capture.build_review_row(
        str(verdict.get("ticket", "") or ""),
        int(verdict.get("pr", 0) or 0),
        provider,
        summary=summary,
    )
    if not dry_run:
        with contextlib.suppress(OSError):
            review_capture.append_review(row, _REVIEWS)
    return row


def render_review_comment(verdict: dict[str, Any]) -> str:
    """Render a reviewer verdict as a Markdown PR comment (pure; no I/O).

    Includes a Process & Labels section so the PR conversation carries a durable,
    human-readable audit of the in-session review.
    """
    counts = verdict.get("counts") or {}
    p1 = int(counts.get("p1", 0) or 0)
    p2 = int(counts.get("p2", 0) or 0)
    p3 = int(counts.get("p3", 0) or 0)
    verdict_str = str(verdict.get("verdict", "")).strip().upper() or "UNKNOWN"
    icon = "✅" if review_status_state(verdict) == "success" else "❌"
    lines = [
        f"## {icon} AI Review Gate — {verdict_str}",
        "",
        f"In-session fresh-context reviewer ({verdict.get('reviewer_model', 'sonnet')}), "
        f"cycle {verdict.get('cycle', 1)}. **P1: {p1} · P2: {p2} · P3: {p3}**",
        "",
    ]
    findings = verdict.get("findings") or []
    if findings:
        lines.append("### Findings")
        for f in findings:
            loc = f.get("file", "?")
            line_no = f.get("line")
            loc = f"{loc}:{line_no}" if line_no else loc
            lines.append(f"- **{f.get('severity', 'P?')}** `{loc}` — {f.get('title', '')}")
            if f.get("fix"):
                lines.append(f"  - _fix_: {f['fix']}")
        lines.append("")
    insights = verdict.get("process_insights") or {}
    if insights:
        lines.append("### Process & Labels")
        for field in ("spec_clarity", "label_accuracy", "scope_correctness"):
            if insights.get(field):
                lines.append(f"- **{field}**: {insights[field]}")
        if insights.get("label_comment"):
            lines.append(f"- **labels**: {insights['label_comment']}")
        lines.append("")
    lines.append("<sub>in-session fresh-context reviewer · no external bot</sub>")
    return "\n".join(lines)


def _pr_head_sha(owner: str, repo: str, pr: int) -> str:
    """Return a PR's head commit SHA via ``gh``; "" on any error (fail-soft)."""
    try:
        res = subprocess.run(
            ["gh", "pr", "view", str(pr), "--repo", f"{owner}/{repo}", "--json", "headRefOid"],
            capture_output=True,
            text=True,
            check=True,
        )
        return str(json.loads(res.stdout).get("headRefOid", "") or "")
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError, KeyError):
        return ""


def post_review_audit(
    verdict: dict[str, Any], owner: str, repo: str, pr: int, *, dry_run: bool = False
) -> dict[str, Any]:
    """Post the PR summary comment + set the ``ai-code-review`` commit status (fail-soft).

    The commit status is keyed to the PR head SHA — this is what the recheck hook
    flips to ``pending`` on a new push and what ``/sprint merge`` reads. A GitHub
    error never blocks the merge. Returns a dict describing what was (or would be) posted.
    """
    comment = render_review_comment(verdict)
    state = review_status_state(verdict)
    description = (
        f"In-session review: {str(verdict.get('verdict', '')).upper()} "
        f"(cycle {verdict.get('cycle', 1)})"
    )
    head_sha = str(verdict.get("head_sha") or "")
    result: dict[str, Any] = {
        "pr": pr,
        "state": state,
        "head_sha": head_sha,
        "comment_len": len(comment),
        "posted": False,
    }
    if dry_run:
        return result
    if not head_sha:
        head_sha = _pr_head_sha(owner, repo, pr)
        result["head_sha"] = head_sha
    with contextlib.suppress(subprocess.CalledProcessError, FileNotFoundError, OSError):
        subprocess.run(
            ["gh", "pr", "comment", str(pr), "--repo", f"{owner}/{repo}", "--body", comment],
            capture_output=True,
            text=True,
            check=True,
        )
        if head_sha:
            subprocess.run(
                [
                    "gh",
                    "api",
                    "-X",
                    "POST",
                    f"repos/{owner}/{repo}/statuses/{head_sha}",
                    "-f",
                    f"state={state}",
                    "-f",
                    "context=ai-code-review",
                    "-f",
                    f"description={description}",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
        result["posted"] = True
    return result


def _load_verdict(path: str) -> dict[str, Any]:
    """Load a verdict JSON from a file path or '-' (stdin)."""
    text = sys.stdin.read() if path == "-" else Path(path).read_text()
    return json.loads(text)


def _conf(key: str, default: str = "") -> str:
    """Read a KEY=value from .dev-context/project.conf (same seam as ci_latency.py)."""
    conf = _DEV / "project.conf"
    if not conf.exists():
        return default
    for line in conf.read_text().splitlines():
        if line.strip().startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return default


def _resolve_owner_repo(owner: str, repo: str) -> tuple[str, str]:
    """Resolve owner/repo from explicit args, falling back to project.conf."""
    return (owner or _conf("GITHUB_OWNER"), repo or _conf("GITHUB_REPO"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Closed-loop calibration engine")
    parser.add_argument("--dry-run", action="store_true", help="print, do not write")
    parser.add_argument(
        "--cli-routing-report",
        action="store_true",
        help="print the harness-router (Gemini) ledger summary and exit",
    )
    parser.add_argument(
        "--rails-coverage",
        nargs="+",
        metavar="TICKET",
        default=None,
        help="print the Rails-coverage KPI for the given merged tickets and exit",
    )
    parser.add_argument(
        "--record-review",
        metavar="VERDICT_JSON",
        default=None,
        help="record a fresh-context reviewer verdict (file or '-' for stdin) to reviews.csv",
    )
    parser.add_argument(
        "--post-review-audit",
        metavar="VERDICT_JSON",
        default=None,
        help="post the PR comment + set ai-code-review SHA status from a verdict (file or '-')",
    )
    parser.add_argument("--pr", type=int, default=0, help="PR number (for --post-review-audit)")
    parser.add_argument("--owner", default="", help="repo owner (defaults to GITHUB_OWNER)")
    parser.add_argument("--repo", default="", help="repo name (defaults to GITHUB_REPO)")
    args = parser.parse_args(argv)
    if args.cli_routing_report:
        print(cli_routing_report(_DEV / "kpis"))
        return 0
    if args.rails_coverage is not None:
        print(format_rails_coverage(_DEV / "kpis", args.rails_coverage))
        return 0
    if args.record_review is not None:
        row = record_review_from_verdict(
            _DEV / "kpis", _load_verdict(args.record_review), dry_run=args.dry_run
        )
        print(json.dumps(row))
        return 0
    if args.post_review_audit is not None:
        owner, repo = _resolve_owner_repo(args.owner, args.repo)
        out = post_review_audit(
            _load_verdict(args.post_review_audit), owner, repo, args.pr, dry_run=args.dry_run
        )
        print(json.dumps(out))
        return 0
    result = run_debrief(dry_run=args.dry_run)
    print(result["report"])
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
