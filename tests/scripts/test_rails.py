"""Tests for scripts/rails.py — the Rail R/U evidence parser and ledger helper.

Covers:
- parse_rail_evidence: strict regex parsing (one-liner + heading form)
- append_rails_row: CSV ledger append (fail-soft)
- parse_and_append: the combined helper /sprint merge calls
- rails_coverage: per-wave/iteration aggregation for /debrief
- debrief.format_rails_coverage: the rendered KPI block
"""

from __future__ import annotations

import csv
import importlib.util
import io
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_spec = importlib.util.spec_from_file_location("rails", _SCRIPTS / "rails.py")
assert _spec and _spec.loader
rails = importlib.util.module_from_spec(_spec)
sys.modules["rails"] = rails
_spec.loader.exec_module(rails)


# ---------------------------------------------------------------------------
# parse_rail_evidence
# ---------------------------------------------------------------------------


def test_parse_valid_r_em_dash() -> None:
    body = "Some text\nRail evidence: R — new kpis/rails.csv ledger\nMore text"
    result = rails.parse_rail_evidence(body)
    assert result is not None
    assert result["rail"] == "R"
    assert result["claim"] == "new kpis/rails.csv ledger"


def test_parse_valid_u_em_dash() -> None:
    body = "Rail evidence: U — settings page renders correctly"
    result = rails.parse_rail_evidence(body)
    assert result is not None
    assert result["rail"] == "U"
    assert result["claim"] == "settings page renders correctly"


def test_parse_valid_r_hyphen() -> None:
    """Accept plain hyphen as well as em-dash."""
    body = "Rail evidence: R - mypy split reduced by 28s"
    result = rails.parse_rail_evidence(body)
    assert result is not None
    assert result["rail"] == "R"
    assert result["claim"] == "mypy split reduced by 28s"


def test_parse_heading_form() -> None:
    """Accept the Markdown heading layout: '## Rail evidence' then 'U — claim'."""
    body = "## Rail evidence\n\nU — bug trend renders as a separate table (no overlap)"
    result = rails.parse_rail_evidence(body)
    assert result is not None
    assert result["rail"] == "U"
    assert result["claim"] == "bug trend renders as a separate table (no overlap)"


def test_parse_heading_and_oneline_same_claim_counts_once() -> None:
    """Heading-form + one-line form of the SAME claim is one match, not a flag."""
    claim = "estimator converges in 7 sprints"
    body = f"## Rail evidence\n\nR — {claim}\n\nRail evidence: R — {claim}"
    result = rails.parse_rail_evidence(body)
    assert result is not None
    assert result["rail"] == "R"
    assert result["measurable"] is True


def test_parse_two_distinct_claims_still_flags() -> None:
    """Two genuinely-different claims remain ambiguous → None (the guard holds)."""
    body = "Rail evidence: R — alpha\nRail evidence: U — beta"
    assert rails.parse_rail_evidence(body) is None


def test_parse_missing_rail_evidence_line() -> None:
    """PR body without any Rail evidence line → None (flag, not merge)."""
    body = "## Summary\nThis PR adds a new feature.\n## Test plan\n- [ ] Tests pass"
    assert rails.parse_rail_evidence(body) is None


def test_parse_wrong_rail_letter() -> None:
    """Only R and U are valid rail letters."""
    assert rails.parse_rail_evidence("Rail evidence: X — some claim") is None


def test_parse_missing_claim() -> None:
    """Line with rail letter but no claim after dash → None."""
    assert rails.parse_rail_evidence("Rail evidence: R — ") is None


def test_parse_missing_claim_hyphen() -> None:
    """Line with hyphen but no claim → None."""
    assert rails.parse_rail_evidence("Rail evidence: U - ") is None


def test_parse_case_sensitive_rail() -> None:
    """Lowercase r/u must NOT match — contract is uppercase only."""
    assert rails.parse_rail_evidence("Rail evidence: r — lowercase should not match") is None


def test_parse_measurable_false_by_default() -> None:
    """Non-measurable claim: measurable=False (no numeric delta indicator)."""
    result = rails.parse_rail_evidence("Rail evidence: U — rendered settings page")
    assert result is not None
    assert result["measurable"] is False


def test_parse_measurable_true_with_delta() -> None:
    """Claim containing a numeric delta → measurable=True."""
    result = rails.parse_rail_evidence(
        "Rail evidence: R — mypy split reduced from 45s to 17s (-28s)"
    )
    assert result is not None
    assert result["measurable"] is True


def test_parse_multiline_pr_body() -> None:
    """Rail evidence line anywhere in PR body should be found."""
    body = (
        "## Summary\n"
        "Added the rails CSV ledger.\n\n"
        "## Test plan\n"
        "- [ ] unit tests pass\n\n"
        "Rail evidence: R — new kpis/rails.csv ledger with strict parser\n\n"
        "Closes #159"
    )
    result = rails.parse_rail_evidence(body)
    assert result is not None
    assert result["rail"] == "R"


def test_parse_rejects_multiple_evidence_lines() -> None:
    """Exactly-one contract: two valid lines → None (ambiguous, do not record)."""
    body = (
        "Rail evidence: R — first claim with 28s delta\n"
        "Rail evidence: U — stale second line left behind\n"
    )
    assert rails.parse_rail_evidence(body) is None


def test_parse_single_line_among_invalid_still_parses() -> None:
    """One valid line plus a malformed (empty-claim) line still parses the valid one."""
    body = "Rail evidence: R — real claim\nRail evidence: U -   \n"
    result = rails.parse_rail_evidence(body)
    assert result is not None
    assert result["rail"] == "R"


# ---------------------------------------------------------------------------
# append_rails_row
# ---------------------------------------------------------------------------


def test_append_creates_header_on_first_write(tmp_path: Path) -> None:
    csv_path = tmp_path / "rails.csv"
    row = {
        "timestamp_utc": "2026-06-01T12:00:00Z",
        "ticket": "ABC-89",
        "pr": "161",
        "rail": "R",
        "claim": "new kpis/rails.csv ledger",
        "measurable": "true",
    }
    rails.append_rails_row(csv_path, row)
    assert csv_path.exists()
    with csv_path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["ticket"] == "ABC-89"
    assert rows[0]["rail"] == "R"
    assert list(rows[0].keys()) == ["timestamp_utc", "ticket", "pr", "rail", "claim", "measurable"]


def test_append_header_not_duplicated(tmp_path: Path) -> None:
    csv_path = tmp_path / "rails.csv"
    rails.append_rails_row(
        csv_path,
        {
            "timestamp_utc": "2026-06-01T12:00:00Z",
            "ticket": "ABC-89",
            "pr": "161",
            "rail": "R",
            "claim": "first claim",
            "measurable": "true",
        },
    )
    rails.append_rails_row(
        csv_path,
        {
            "timestamp_utc": "2026-06-01T13:00:00Z",
            "ticket": "ABC-90",
            "pr": "162",
            "rail": "U",
            "claim": "second claim",
            "measurable": "false",
        },
    )
    with csv_path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert rows[0]["ticket"] == "ABC-89"
    assert rows[1]["ticket"] == "ABC-90"


def test_append_fails_soft_on_io_error(tmp_path: Path) -> None:
    """append_rails_row returns False (not raise) on I/O error."""
    csv_path = tmp_path / "nonexistent_dir" / "rails.csv"
    result = rails.append_rails_row(
        csv_path,
        {
            "timestamp_utc": "2026-06-01T12:00:00Z",
            "ticket": "ABC-89",
            "pr": "161",
            "rail": "R",
            "claim": "claim",
            "measurable": "false",
        },
    )
    assert result is False


# ---------------------------------------------------------------------------
# parse_and_append (combined helper used by /sprint merge)
# ---------------------------------------------------------------------------


def test_parse_and_append_valid(tmp_path: Path) -> None:
    csv_path = tmp_path / "rails.csv"
    result = rails.parse_and_append(
        pr_body="Rail evidence: R — rails ledger and strict parser",
        ticket="ABC-89",
        pr="161",
        rails_csv=csv_path,
    )
    assert result["flagged"] is False
    assert result["rail"] == "R"
    assert csv_path.exists()


def test_parse_and_append_missing_evidence(tmp_path: Path) -> None:
    """Missing Rail evidence line → flagged=True, CSV row NOT written."""
    csv_path = tmp_path / "rails.csv"
    result = rails.parse_and_append(
        pr_body="## Summary\nNo rail evidence here.",
        ticket="ABC-99",
        pr="200",
        rails_csv=csv_path,
    )
    assert result["flagged"] is True
    assert not csv_path.exists()


# ---------------------------------------------------------------------------
# rails_coverage (debrief aggregation)
# ---------------------------------------------------------------------------


def _make_csv_content(rows: list[dict[str, str]]) -> str:
    """Build in-memory CSV string from a list of dicts."""
    fieldnames = ["timestamp_utc", "ticket", "pr", "rail", "claim", "measurable"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def test_rails_coverage_all_r(tmp_path: Path) -> None:
    csv_path = tmp_path / "rails.csv"
    csv_path.write_text(
        _make_csv_content(
            [
                {
                    "timestamp_utc": "t1",
                    "ticket": "ABC-1",
                    "pr": "1",
                    "rail": "R",
                    "claim": "c1",
                    "measurable": "true",
                },
                {
                    "timestamp_utc": "t2",
                    "ticket": "ABC-2",
                    "pr": "2",
                    "rail": "R",
                    "claim": "c2",
                    "measurable": "false",
                },
            ]
        )
    )
    result = rails.rails_coverage(csv_path, merged_tickets=["ABC-1", "ABC-2"])
    assert result["merged"] == 2
    assert result["with_claim"] == 2
    assert result["coverage_pct"] == 100.0
    assert result["r_count"] == 2
    assert result["u_count"] == 0
    assert result["measurable_r_count"] == 1


def test_rails_coverage_partial(tmp_path: Path) -> None:
    csv_path = tmp_path / "rails.csv"
    csv_path.write_text(
        _make_csv_content(
            [
                {
                    "timestamp_utc": "t1",
                    "ticket": "ABC-1",
                    "pr": "1",
                    "rail": "R",
                    "claim": "c1",
                    "measurable": "true",
                },
                {
                    "timestamp_utc": "t2",
                    "ticket": "ABC-2",
                    "pr": "2",
                    "rail": "U",
                    "claim": "c2",
                    "measurable": "false",
                },
            ]
        )
    )
    result = rails.rails_coverage(csv_path, merged_tickets=["ABC-1", "ABC-2", "ABC-3"])
    assert result["merged"] == 3
    assert result["with_claim"] == 2
    assert round(result["coverage_pct"], 1) == round(2 / 3 * 100, 1)
    assert result["r_count"] == 1
    assert result["u_count"] == 1
    assert result["measurable_r_count"] == 1


def test_rails_coverage_empty_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "rails.csv"
    csv_path.write_text("timestamp_utc,ticket,pr,rail,claim,measurable\n")
    result = rails.rails_coverage(csv_path, merged_tickets=["ABC-1"])
    assert result["merged"] == 1
    assert result["with_claim"] == 0
    assert result["coverage_pct"] == 0.0


def test_rails_coverage_missing_csv(tmp_path: Path) -> None:
    """Missing CSV → returns zero coverage without raising."""
    csv_path = tmp_path / "nonexistent.csv"
    result = rails.rails_coverage(csv_path, merged_tickets=["ABC-1"])
    assert result["coverage_pct"] == 0.0
    assert result["merged"] == 1


def test_rails_coverage_dedups_duplicate_ticket_rows(tmp_path: Path) -> None:
    """Non-idempotent append: same ticket twice must not inflate the R count."""
    csv_path = tmp_path / "rails.csv"
    csv_path.write_text(
        _make_csv_content(
            [
                {
                    "timestamp_utc": "t1",
                    "ticket": "ABC-89",
                    "pr": "170",
                    "rail": "R",
                    "claim": "c1",
                    "measurable": "true",
                },
                {
                    "timestamp_utc": "t2",
                    "ticket": "ABC-89",
                    "pr": "170",
                    "rail": "R",
                    "claim": "c1 (re-run)",
                    "measurable": "true",
                },
            ]
        )
    )
    result = rails.rails_coverage(csv_path, merged_tickets=["ABC-89"])
    assert result["with_claim"] == 1
    assert result["r_count"] == 1
    assert result["measurable_r_count"] == 1
    assert result["coverage_pct"] == 100.0


# ---------------------------------------------------------------------------
# debrief integration: format_rails_coverage
# ---------------------------------------------------------------------------


def test_format_rails_coverage_renders_kpi(tmp_path: Path) -> None:
    """debrief.format_rails_coverage renders the Rails-coverage KPI block."""
    _dspec = importlib.util.spec_from_file_location("debrief", _SCRIPTS / "debrief.py")
    assert _dspec and _dspec.loader
    debrief = importlib.util.module_from_spec(_dspec)
    sys.modules["debrief"] = debrief
    _dspec.loader.exec_module(debrief)

    (tmp_path / "rails.csv").write_text(
        "timestamp_utc,ticket,pr,rail,claim,measurable\n"
        "2026-06-01T10:00:00Z,ABC-85,163,R,categorizer histogram,true\n"
    )
    out = debrief.format_rails_coverage(tmp_path, ["ABC-85", "ABC-89"])
    assert "Rails coverage" in out
    assert "1/2" in out
    assert "50.0%" in out
    assert "R=1 U=0" in out
    assert "Measurable R deltas: 1" in out
