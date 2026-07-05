"""Rail R/U manifestation framework — parser, ledger, and coverage.

The Rail evidence contract: every merged ticket declares a single line in its PR
body of the form

    Rail evidence: R — <one-line measurable claim>      # Rail R (measurable delta)
    Rail evidence: U — <one-line claim>                  # Rail U (UI-surface evidence)

This module is the standing-harness home of that contract:

  * ``parse_rail_evidence`` — strict regex parse of a PR body (R/U, uppercase,
    em-dash or hyphen, non-empty claim);
  * ``append_rails_row`` — fail-soft append to the ``kpis/rails.csv`` ledger;
  * ``parse_and_append`` — the combined helper ``/sprint merge`` calls (flags a
    PR that carries no valid Rail evidence line instead of writing a row);
  * ``rails_coverage`` — per-wave/iteration aggregation consumed by ``/debrief``.

Pure functions; the only I/O is the CSV ledger. All side effects fail soft —
the Rails ledger must never block a merge.
"""

from __future__ import annotations

import csv
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from pathlib import Path

# Ledger schema — fixed column order (AC: kpis/rails.csv).
RAILS_FIELDS: list[str] = ["timestamp_utc", "ticket", "pr", "rail", "claim", "measurable"]

# Strict contract: literal "Rail evidence:", uppercase R|U, em-dash or hyphen,
# then a non-empty claim. Anchored per-line (MULTILINE) so it is found anywhere
# in a multi-line PR body. Lowercase r/u and other letters do NOT match.
_EVIDENCE_RE = re.compile(r"^Rail evidence: ([RU]) [—-] (.+)$", re.MULTILINE)

# Heading-form tolerance: agents naturally write the evidence as a Markdown
# section — a `## Rail evidence` (or `**Rail evidence**`) heading followed by the
# `R/U — claim` on the NEXT non-blank line — instead of the strict one-liner.
# That is the same evidence, just laid out as a section, so we accept it too
# rather than flag a PR that clearly carries a claim. The heading may carry any
# leading markdown (`#`, `*`, `>`); the claim line is the next non-empty line of
# the form `R|U <dash> <claim>`.
_EVIDENCE_HEADING_RE = re.compile(
    r"^[#>*\s]*Rail evidence\*?\*?:?\s*\n\s*\n?\s*([RU]) [—-] (.+)$",
    re.MULTILINE,
)

# A claim is "measurable" if it carries a numeric signal (a delta, a count, a
# duration). The cheap, deterministic heuristic is the presence of a digit.
_MEASURABLE_RE = re.compile(r"\d")


class RailEvidence(TypedDict):
    """Parsed Rail evidence line."""

    rail: str
    claim: str
    measurable: bool


def parse_rail_evidence(body: str) -> RailEvidence | None:
    """Parse the single valid ``Rail evidence:`` line from a PR body.

    The contract requires **exactly one** valid claim. ``None`` is returned when
    none is present OR when more than one DISTINCT claim is present (a stale line
    left beside a replacement is ambiguous and must not silently record an
    arbitrary claim) — the caller treats ``None`` as a flag, not a merge. The
    claim is stripped; an empty/whitespace claim does not count.

    Two layouts are accepted: the strict one-liner ``Rail evidence: R — claim``
    and the Markdown heading form (a ``## Rail evidence`` heading followed by
    ``R/U — claim`` on the next line). A claim matched by BOTH patterns is counted
    once (dedup), so a single section-styled evidence block is not mis-flagged as
    "more than one".
    """
    matches = _EVIDENCE_RE.findall(body) + _EVIDENCE_HEADING_RE.findall(body)
    # Dedup on (rail, claim) so the same evidence found by both patterns counts once.
    seen: set[tuple[str, str]] = set()
    valid: list[tuple[str, str]] = []
    for rail, claim in matches:
        key = (rail, claim.strip())
        if key[1] and key not in seen:
            seen.add(key)
            valid.append(key)
    if len(valid) != 1:
        return None
    rail, claim_raw = valid[0]
    return RailEvidence(
        rail=rail,
        claim=claim_raw,
        measurable=bool(_MEASURABLE_RE.search(claim_raw)),
    )


def append_rails_row(csv_path: Path, row: dict[str, str]) -> bool:
    """Append one row to the rails ledger, writing the header on first write.

    Fail-soft: returns ``True`` on success, ``False`` on any I/O error (e.g. a
    missing parent directory). Never raises — the ledger must not block a merge.
    """
    try:
        write_header = not csv_path.exists() or csv_path.stat().st_size == 0
        with csv_path.open("a", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=RAILS_FIELDS)
            if write_header:
                writer.writeheader()
            writer.writerow({field: row.get(field, "") for field in RAILS_FIELDS})
        return True
    except OSError:
        return False


class ParseAndAppendResult(TypedDict, total=False):
    """Outcome of ``parse_and_append``."""

    flagged: bool
    rail: str
    claim: str
    measurable: bool
    appended: bool


def parse_and_append(
    *,
    pr_body: str,
    ticket: str,
    pr: str,
    rails_csv: Path,
) -> ParseAndAppendResult:
    """Parse a PR body and append its Rail evidence to the ledger.

    The combined helper ``/sprint merge`` calls per PR. When the body carries no
    valid Rail evidence line the result is ``{"flagged": True}`` and NO row is
    written — the merge step surfaces the flag (evidence-less PRs escalate).
    """
    parsed = parse_rail_evidence(pr_body)
    if parsed is None:
        return ParseAndAppendResult(flagged=True)
    row = {
        "timestamp_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ticket": ticket,
        "pr": pr,
        "rail": parsed["rail"],
        "claim": parsed["claim"],
        "measurable": "true" if parsed["measurable"] else "false",
    }
    appended = append_rails_row(rails_csv, row)
    return ParseAndAppendResult(
        flagged=False,
        rail=parsed["rail"],
        claim=parsed["claim"],
        measurable=parsed["measurable"],
        appended=appended,
    )


class RailsCoverage(TypedDict):
    """Rails-coverage KPI for a wave or iteration."""

    merged: int
    with_claim: int
    coverage_pct: float
    r_count: int
    u_count: int
    measurable_r_count: int


def _read_rows(csv_path: Path) -> list[dict[str, str]]:
    """Read ledger rows; a missing file yields an empty list (fail-soft)."""
    try:
        with csv_path.open(newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError:
        return []


def rails_coverage(csv_path: Path, merged_tickets: list[str]) -> RailsCoverage:
    """Aggregate Rails coverage over a set of merged tickets.

    ``coverage_pct`` is the share of merged tickets that carry a claim; the
    R/U split and ``measurable_r_count`` are computed only over claims whose
    ticket is in ``merged_tickets``. The ledger append is not idempotent (a
    re-run of ``/sprint merge`` can write a ticket's row twice), so rows are
    **deduplicated to one per ticket** (last row wins) before counting — a
    single merged R ticket never inflates the split to ``R=2``. A missing/empty
    ledger yields zero coverage without raising.
    """
    merged_set = set(merged_tickets)
    relevant = [r for r in _read_rows(csv_path) if r.get("ticket") in merged_set]
    by_ticket = {r["ticket"]: r for r in relevant}  # last row per ticket wins
    deduped = list(by_ticket.values())
    with_claim = len(by_ticket)
    merged = len(merged_tickets)
    r_count = sum(1 for r in deduped if r.get("rail") == "R")
    u_count = sum(1 for r in deduped if r.get("rail") == "U")
    measurable_r_count = sum(
        1 for r in deduped if r.get("rail") == "R" and r.get("measurable") == "true"
    )
    coverage_pct = (with_claim / merged * 100.0) if merged else 0.0
    return RailsCoverage(
        merged=merged,
        with_claim=with_claim,
        coverage_pct=coverage_pct,
        r_count=r_count,
        u_count=u_count,
        measurable_r_count=measurable_r_count,
    )
