"""Report formatting for Anthropic billing reconciliation."""

from __future__ import annotations

ANOMALY_THRESHOLD = 0.20


def format_estimated(estimated: dict) -> list[str]:  # type: ignore[type-arg]
    """Format the estimated costs section of the report."""
    lines = [f"Estimated costs ({estimated['rows']} sessions):"]
    lines.append(f"  Total: ${estimated['total']:.2f}")
    for provider, cost in estimated.get("by_provider", {}).items():
        lines.append(f"  {provider}: ${cost:.2f}")
    return lines


def format_actual(
    estimated: dict,
    actual: dict | None,  # type: ignore[type-arg]
) -> list[str]:
    """Format the actual API spend section of the report."""
    if actual is None:
        return [
            "API spend: NOT AVAILABLE (ANTHROPIC_ADMIN_KEY not set)",
            "  Using estimated costs from token counts only.",
        ]
    lines = ["API spend (billed, excl. subscription):"]
    actual_total = actual.get("total", 0.0)
    lines.append(f"  Total: ${actual_total:.2f}")
    for key_id, cost in actual.get("by_key", {}).items():
        lines.append(f"  {key_id}: ${cost:.4f}")
    if estimated["total"] > 0 and actual_total > 0:
        disc = abs(actual_total - estimated["total"]) / estimated["total"]
        if disc > ANOMALY_THRESHOLD:
            lines.append("")
            lines.append("  *** ANOMALY DETECTED ***")
            lines.append(f"  Discrepancy: {disc:.0%}")
            lines.append(f"  Estimated: ${estimated['total']:.2f}")
            lines.append(f"  Actual: ${actual_total:.2f}")
    return lines


def format_budget(s: dict) -> list[str]:  # type: ignore[type-arg]
    """Format the budget status section of the report."""
    lines = ["Budget status:"]
    lines.append(f"  Daily spend: ${s['spend']:.2f} / ${s['budget']:.2f} ({s['percent']:.0f}%)")
    label = s["status"]
    if label == "EXCEEDED":
        lines.append("  *** BUDGET EXCEEDED *** -- circuit breaker should be active")
    elif label == "CRITICAL":
        lines.append(
            f"  *** CRITICAL *** -- spend at {s['percent']:.0f}%, "
            f"suggest claude-haiku-4-5 for P2/P3"
        )
    elif label == "WARNING":
        lines.append(f"  ** WARNING ** -- spend at {s['percent']:.0f}%, proceed with caution")
    else:
        lines.append("  Status: OK")
    return lines


def format_report(
    estimated: dict,  # type: ignore[type-arg]
    actual: dict | None,  # type: ignore[type-arg]
    budget_status: dict,  # type: ignore[type-arg]
) -> str:
    """Format cost reconciliation report as a string."""
    sep = "=" * 60
    sections: list[str] = [sep, "  Cost Reconciliation Report", sep, ""]
    sections.extend(format_estimated(estimated))
    sections.append("")
    sections.extend(format_actual(estimated, actual))
    sections.append("")
    sections.extend(format_budget(budget_status))
    sections.extend(["", sep])
    return "\n".join(sections)
