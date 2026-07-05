---
name: diagnose
description: "Structured debugging: reproduce, trace root cause, identify fix path using source code, production logs, and database state. Does NOT write code — pure investigation. Use when: /diagnose, debug, investigate, why is this broken, error, trace, root cause, what went wrong, stack trace, exception. Target: error message, log snippet, ticket ID, or problem description."
---

# Diagnose Skill (Structured Debugging)

Systematic investigation of bugs and errors. Traces from symptom to root cause
without jumping to conclusions. Does NOT fix the bug — outputs a diagnosis
with a recommended fix path. Use `/hotfix` or `/develop fix` to apply the fix.

Investigates across three layers:
- **Source code** — trace code paths, check tests, read git history
- **Production logs** — search for error patterns, timing, frequency
- **Database / infra state** — pool health, schema version, targeted data queries

## Process

```
Infra Check → Gather → Reproduce → Trace → Root Cause → Recommend
```

---

## Pre-Step: Infrastructure Availability Check

Before investigating, determine what production access is available.
This gates all infra-dependent instructions — the skill never blocks on
unavailable infrastructure.

### Check sequence

1. **Try platform CLI** (e.g., `railway status`, `vercel ls`, `fly status`):
   - Success → **FULL** access (logs + DB + health)

2. **Try health endpoint** (e.g., `curl -sf https://<production-domain>/health/ready | jq .`):
   - Success → **PARTIAL** access (health metrics only)

3. Both fail → **NONE** (source-code-only investigation)

Record the result — it appears in all output templates.

### Adapting to your platform

| Platform | FULL check | Log command | DB access |
|----------|-----------|-------------|-----------|
| Railway | `railway status` | `railway logs --service <svc>` | `railway run psql -c "..."` |
| Vercel | `vercel ls` | `vercel logs <url>` | Direct DB connection via env vars |
| Fly.io | `fly status` | `fly logs` | `fly ssh console -C "psql ..."` |
| AWS/ECS | `aws ecs describe-services ...` | `aws logs filter-log-events ...` | `aws rds ...` or direct psql |
| Docker Compose | `docker compose ps` | `docker compose logs <svc>` | `docker compose exec db psql ...` |

---

## Step 1: Gather Evidence

Collect everything available about the problem:

### 1a. Ticket & Error Context

1. **If {{TICKET_PREFIX}}-NNN provided**: read ticket details (`gh issue view` or Linear MCP)
2. **If error message/log provided**: parse for:
   - Exception type and message
   - File path and line number
   - Stack trace (if present)
   - Timestamp and frequency
3. **Check recent changes**:
   ```bash
   git log --oneline -10
   ```
   - Did a recent deploy introduce this? Compare timing.

### 1b. Production Log Investigation

> Requires **FULL** access. If PARTIAL or NONE, skip and note "Logs not available".

Fetch recent logs and search for the reported error — this is a targeted
investigation, not a general log scan. Every query must answer a specific
diagnostic question.

1. **Fetch logs** using your platform's CLI (see table in Pre-Step)

2. **Targeted scan** (in the fetched output):
   - Search for the reported exception type or error message substring
   - Extract ERROR/CRITICAL lines with 5 lines of surrounding context
   - Count occurrences — is this a one-off or a pattern?
   - Note timestamps — when did it first appear? Does it correlate with a deploy?
   - Extract entity identifiers from error lines (user IDs, resource IDs, request context)
     for DB correlation in step 1c

3. **Deploy correlation**:
   - Compare first-error timestamp against recent deploy timestamps
   - If error started immediately after a deploy, that commit is the prime suspect

### 1c. Infrastructure State

> Requires **FULL** or **PARTIAL** access. If NONE, skip and note "Infra state not checked".

1. **Health endpoint** (PARTIAL or FULL):
   - Hit the readiness endpoint (`/health/ready` or equivalent)
   - Check DB pool metrics (size vs active connections) → connection exhaustion
   - Check cache/Redis latency or status → session/cache issues

2. **Database diagnostic queries** (FULL access only, and only when error suggests DB involvement):

   Run read-only queries via your platform's DB access method:

   | Query | When to use |
   |-------|-------------|
   | Schema version check (e.g., `SELECT version_num FROM alembic_version;`) | Schema drift suspected — compare with local migration head |
   | `SELECT count(*) FROM pg_stat_activity WHERE datname = current_database();` | Connection exhaustion suspected |
   | `SELECT pid, now() - query_start AS duration, query FROM pg_stat_activity WHERE state = 'active' AND query_start < now() - interval '30 seconds';` | Deadlock or timeout suspected |
   | Targeted data query (e.g., `SELECT ... FROM <table> WHERE id = 'X' LIMIT 5;`) | Error references specific entity — check actual data shape |

   **Constraint**: Only SELECT queries. Never write to the production database.

### Evidence Output

```
## Evidence
- Symptom: <what the user/system observes>
- First seen: <timestamp or "unknown">
- Frequency: <once / intermittent / constant>
- Error: <exact error message if available>
- Stack trace: <yes/no — key frames>
- Recent deploys: <last 3 commits>
- Infra access: FULL / PARTIAL / NONE
- Log evidence: <summary of log findings or "not available">
- DB state: <pool metrics, schema version, or "not checked">
```

---

## Step 2: Reproduce

Attempt to reproduce the issue locally or trace its trigger:

1. **Trace the code path**:
   - From the error location (file:line), read the function
   - Walk up the call chain — who calls this? What data flows in?
   - Identify the trigger condition (what input/state causes this?)

2. **Check tests**:
   - Is there a test covering this path?
   - If yes: does it pass? (if so, the test may not cover the edge case)
   - If no: this is an untested path — note for fix phase

3. **Identify variables**:
   - What data could vary? (user input, DB state, external API response, timing)
   - Which variable likely causes the failure?

4. **Check production data shapes** (FULL access only):
   - If the error involves a specific entity, query production to see the actual
     data that triggered the failure (use identifiers extracted in Step 1b)
   - Compare production data against what the code expects

**Output**:
```
## Reproduction
- Code path: <module.function → module.function → ...>
- Trigger: <specific input/state/condition>
- Reproducible: yes (steps) / likely (hypothesis) / unknown
- Test coverage: covered / partial / none
- Production data checked: yes (findings) / no (reason)
```

---

## Step 3: Root Cause Analysis

Narrow from symptom to cause:

1. **Eliminate candidates**: For each hypothesis, check if the evidence supports it:
   - Check data types, None handling, boundary conditions
   - Check async race conditions (if applicable)
   - Check external dependencies (API changes, DB schema drift, config changes)
   - **Cross-reference with production logs** (FULL access): if hypothesis is
     "this path is never reached", check logs for the relevant log line.
     If hypothesis is "only happens with specific input", search logs for the
     error pattern and extract the varying parts

2. **Schema drift check** (FULL access, when suspected):
   - Compare local migration head against production schema version
   - Mismatch = strong signal for schema drift root cause

3. **Apply the 5 Whys** (stop when you reach the architectural/design level):
   - Why did the error occur? → <direct cause>
   - Why was that possible? → <missing guard / bad assumption>
   - Why wasn't it caught? → <test gap / monitoring gap>

4. **Classify**:
   | Category | Examples |
   |----------|---------|
   | Logic error | Wrong condition, off-by-one, missing case |
   | Data error | None where expected, wrong type, stale cache |
   | Race condition | Async timing, concurrent writes, state desync |
   | External | API change, dependency bug, infra issue |
   | Config | Wrong env var, missing setting, environment mismatch |
   | Schema drift | DB migration missed, model/schema mismatch |

**Output**:
```
## Root Cause
- Category: <from table above>
- Cause: <1-2 sentence explanation>
- Why it wasn't caught: <test gap, missing validation, etc.>
- Confidence: high / medium / low
- Evidence source: code / logs / DB state / combination
```

---

## Step 4: Recommend Fix

Don't implement — just provide a clear fix plan:

1. **Files to change**: List specific files and what changes
2. **Test to add**: Describe the regression test (what it asserts)
3. **Risk assessment**: What could the fix break? If root cause was confirmed
   via production logs or DB state, note the evidence that supports the fix
4. **Recommended path**:
   - Trivial fix (1-2 lines, high confidence) → `/hotfix {{TICKET_PREFIX}}-NNN`
   - Non-trivial fix (multiple files, medium confidence) → `/develop fix {{TICKET_PREFIX}}-NNN`
   - Architecture issue (design change needed) → `/develop {{TICKET_PREFIX}}-NNN` (full pipeline)

**Output**:
```
## Recommended Fix

### Changes
- `app/services/classifier.py:45` — add None check before `.lower()` call
- `tests/unit/test_classifier.py` ��� add test for empty input edge case

### Regression Test
```python
async def test_classify_empty_input_returns_unknown():
    result = await classifier.classify("")
    assert result.intent == "unknown"
```

### Risk
- Low — isolated to classifier input handling
- No downstream effects (unknown intent is already handled)

### Next Step
Run: `/hotfix {{TICKET_PREFIX}}-<NNN>` (trivial fix, high confidence)
```

---

## What this skill does NOT do

- Does NOT write or edit code
- Does NOT create branches or PRs
- Does NOT run tests (except reading existing test results)
- Does NOT modify any files
- Does NOT write to the database (read-only queries only)
- Does NOT restart services or trigger deployments

It is a **pure investigation tool**. Its output feeds into `/hotfix` or `/develop fix`.

## Boundary with `/monitor`

| Aspect | `/monitor` | `/diagnose` |
|--------|-----------|-------------|
| Trigger | "Is production OK?" | "Why did X break?" |
| Log usage | Scan for any errors (broad sweep) | Search for a specific error pattern |
| DB usage | Pool metrics via health endpoint | Targeted queries about specific data |
| Output | Status dashboard | Root cause + fix recommendation |
| Scope | Broad health check | Narrow, hypothesis-driven |

Key principle: every production query in `/diagnose` must answer a specific
diagnostic question. No general health sweeps — that's what `/monitor` is for.

## Integration

- Works standalone: `/diagnose "TypeError: NoneType has no attribute lower"`
- Works with tickets: `/diagnose {{TICKET_PREFIX}}-NNN`
- Pairs with `/monitor`: use monitor output as input for diagnose
- Feeds into `/hotfix` or `/develop fix`: diagnosis becomes the implementation plan

## Adapting This Skill

When customizing for a specific project, replace the generic platform references:

1. **Pre-Step**: Replace the platform CLI check with your actual command (e.g., `railway status`)
2. **Step 1b**: Replace the log fetch command with your platform's log CLI
3. **Step 1c**: Replace the health URL with your production domain's readiness endpoint
4. **Step 1c**: Replace the DB access method with your platform's CLI wrapper
5. **Step 3**: Replace the migration tool reference with your schema migration tool

Mark project-specific commands with `<!-- project: <name> -->` HTML comments
so future updates from the template can be merged cleanly.
