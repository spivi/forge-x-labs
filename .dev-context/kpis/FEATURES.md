# Dataset feature dictionary

Auto-generated from `scripts/dataset.py::FIELD_SPECS` by `/debrief` (or `python scripts/dataset.py`). One row per ticket in `kpis/dataset.csv`. Do not edit by hand.

| column | type | source | role | notes |
|---|---|---|---|---|
| `ticket` | str | estimates.csv | id | ticket key (join key) |
| `type` | str | estimates.csv | feature | feature|fix|tweak|refactor|... |
| `effort` | str | estimates.csv | feature | S|M|L|XL (typed, labels fallback) |
| `milestone` | str | estimates.csv | feature | open vocabulary |
| `risk` | str | estimates.csv | feature | low|medium|high |
| `area` | str | estimates.csv | feature | open vocabulary (api|ui|infra|...) |
| `priority` | str | estimates.csv | feature | open vocabulary |
| `recommended_model` | str | estimates.csv | feature | planned cheapest-sufficient model |
| `estimate_minutes` | int | estimates.csv | feature | planned wall-clock minutes |
| `scope_changed` | int | estimates.csv | feature | 1 if folded/partial, else 0 |
| `architectural_deviation` | int | estimates.csv | feature | 1 if deviated, else 0 |
| `clarifying_questions_asked` | int | estimates.csv | feature | spec-quality signal |
| `caused_by` | str | estimates.csv | feature | originating ticket (bugs only) |
| `actual_duration_sec` | int | cost-ledger.csv | outcome | summed session seconds |
| `session_count` | int | cost-ledger.csv | outcome | ledger rows for the ticket |
| `session_min` | float | cost-ledger.csv | outcome | actual wall-clock minutes |
| `tokens_in` | int | cost-ledger.csv | outcome | input+cache_creation+cache_read |
| `tokens_out` | int | cost-ledger.csv | outcome | output tokens |
| `cost_usd` | float | cost-ledger.csv | outcome | summed cost (billed||compute) |
| `effective_model` | str | cost-ledger.csv | outcome | highest-tier model actually used |
| `estimate_ratio` | float | derived | outcome | actual_min / estimate_minutes |
| `review_cycles` | int | reviews.csv | outcome | max push->review rounds |
| `findings_total` | int | reviews.csv | outcome | all review findings |
| `p1` | int | reviews.csv | outcome | critical findings |
| `p2` | int | reviews.csv | outcome | major findings |
| `p3` | int | reviews.csv | outcome | minor findings |
| `review_stale_s` | float | reviews.csv | outcome | review latency seconds (may be blank) |
| `suitability_verdict` | str | derived | outcome | underpowered|overkill|well-matched |
