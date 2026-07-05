# E2E Tester Agent

> Automated test executor and regression detector that validates every pull
> request by running the full test suite, comparing coverage against the base
> branch, and posting a structured report as a PR comment.

## Identity

- **Role**: Test executor, regression detector, and coverage guardian
- **Boundaries**: Does NOT write application code. Does NOT merge PRs. Does NOT approve or request changes via the GitHub review API. Only reports results as PR comments. May update test configuration (pytest markers, conftest fixtures) but never `app/` code.
- **Personality**: Objective, data-driven, reports facts not opinions. Distinguishes between new failures (regressions) and pre-existing failures.

## Why This Exists

The CI pipeline (`ci.yml`) runs tests and enforces a coverage floor, but it
does not:

1. **Compare coverage** against the base branch (only checks absolute threshold)
2. **Detect regressions** (tests that pass on base but fail on the PR)
3. **Post structured reports** to the PR for quick human review
4. **Track test KPIs** over time for continuous improvement

The E2E Tester fills these gaps with zero additional AI cost (no LLM calls).

## Trigger

| Method | When |
|--------|------|
| GitHub Action | PR opened, synchronized (new commits pushed), or reopened |
| Manual | `PYTHONPATH=. .venv/bin/pytest tests/ -v` from local dev |

## Input

1. **PR branch code**: Full checkout with history (`fetch-depth: 0`)
2. **Base branch code**: Checked out via `github.event.pull_request.base.sha`
3. **Test suite**: `tests/` (unit, integration, e2e, api, models, scripts)
4. **Coverage configuration**: `pyproject.toml` (`[tool.coverage]` section)

## Tools

- **pytest**: Test execution with coverage (`--cov=app --cov-report=xml`)
- **coverage**: Coverage comparison and reporting (`coverage report --format=total`)
- **GitHub CLI**: `gh pr comment --body-file` for posting reports
- **Shell scripting**: Result parsing, report generation, CSV logging
- **No AI/LLM**: This agent is purely deterministic -- saves cost

## Process

### 1. Install Dependencies

```bash
pip install -e .
pip install pytest pytest-asyncio pytest-cov httpx pytest-mock
```

### 2. Run Tests on PR Branch

```bash
python -m pytest tests/ \
  --cov=app \
  --cov-report=xml:coverage-pr.xml \
  --cov-report=term-missing \
  --tb=short -q
```

Capture: exit code, coverage percentage, test count summary, failed test details.

### 3. Run Tests on Base Branch

```bash
git checkout <base-sha>
python -m pytest tests/ \
  --cov=app \
  --cov-report=xml:coverage-base.xml \
  -q --tb=no
git checkout <pr-sha>
```

Capture: base coverage percentage. If base checkout fails, skip this step
and note "baseline unavailable" in report.

### 4. Compute Coverage Delta

```
delta = pr_coverage - base_coverage
```

- Positive delta: coverage improved
- Zero delta: no change
- Negative delta: coverage regressed (potential quality concern)

### 5. Detect Regressions

A **regression** is a test that passes on the base branch but fails on the PR
branch. The agent determines this by comparing test outcomes:

- **New failure** (regression): Passes on base, fails on PR
- **Pre-existing failure**: Fails on both base and PR
- **New test failure**: Test only exists on PR branch and fails

### 6. Post Structured Report

Write report to `e2e-report.md`, then post via `gh pr comment --body-file`.

## Output

### PR Comment Format

```markdown
## E2E Test Report: PR #<number>

**Branch**: `<branch-name>`
**Status**: PASS | FAIL

### Test Results
- Total: <N> tests
- Passed: <N>
- Failed: <N>
- Skipped: <N>
- Duration: <N>s

### Coverage
- PR branch: <N>%
- Base branch: <N>%
- Delta: +<N>% | -<N>%

### Regressions
> Tests passing on base but failing on this PR.

- `tests/path/test_file.py::test_name` -- <error summary>

### Failed Test Details
<details>
<summary>Click to expand (<N> failures)</summary>

<pytest output for failed tests>

</details>

---

**Verdict**: PASS | FAIL (<reason>)
```

### Artifacts

| Artifact | Location | Format |
|----------|----------|--------|
| Test report | PR comment (GitHub) | Structured markdown |
| Coverage XML | CI artifact upload | Cobertura XML |
| Test audit log | `.dev-context/kpis/e2e-test-log.csv` | CSV |

## Human Gates

The E2E Tester **never requires human intervention** -- it is fully automated.

Escalation path:
- Test failures on a reviewed PR: Flagged in PR comment for Developer Worker to fix
- Repeated failures across PRs: Scrum Master tracks test reliability KPI
- Coverage drop below threshold: CI enforces as required status check

## Failure Modes

| Failure | Action |
|---------|--------|
| pytest crashes (import error, fixture error) | Post error output as PR comment, verdict: FAIL |
| Coverage tool fails | Report test pass/fail without coverage delta, note in comment |
| Cannot checkout base branch | Skip regression detection, note "baseline unavailable" |
| Tests take > 10 minutes | Kill process, report timeout, verdict: FAIL |
| GitHub API failure (can't post comment) | Retry once, then write to job summary as fallback |
| Flaky tests (pass on retry, fail initially) | Note as potential flake, do not count as regression |

## Integration with Other Agents

| Agent | E2E Tester Interaction |
|-------|----------------------|
| **Code Reviewer** | Runs in parallel. Both are independent merge gates. |
| **Security Architect** | Runs in parallel. May request specific security test cases. |
| **Developer Worker** | Reads test failure details from PR comment. Fixes regressions. |
| **Scrum Master** | Escalation target for repeated failures. Tracks test reliability KPI. |
| **Budget Review** | E2E Tester is zero additional AI cost (no LLM calls). Only CI compute. |

## KPI Tracking

The agent appends a row to `.dev-context/kpis/e2e-test-log.csv` after each run:

```csv
timestamp,pr_number,branch,total,passed,failed,skipped,duration_s,coverage_pr,coverage_base,coverage_delta,regressions,verdict
```

KPI targets (from `.dev-context/kpis/agent-kpis.md`):

| KPI | Target |
|-----|--------|
| Regression catch rate | 100% |
| Test reliability (no flaky failures) | >= 95% |
| Coverage delta per PR | Non-negative |
| Test execution time | < 5 min |
| Critical path coverage | 100% |

## GitHub Action Configuration

The E2E Tester runs as a GitHub Action. See `.github/workflows/e2e-tests.yml`.

Required secrets:
- Automatically available: `GITHUB_TOKEN` (for PR comments)

No additional secrets needed (no AI/LLM provider keys required).
