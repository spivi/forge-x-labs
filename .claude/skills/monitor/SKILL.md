---
name: monitor
description: "Read-only production diagnostics: health checks, deployment logs, service status. Never modifies code or infrastructure. Use when: /monitor, health check, production status, railway logs, is it up, is it down, service status, check production, deployment status. Actions: health (default), logs, deployments, full."
---

# Monitor Skill (Production Health Check)

Quick production diagnostics. Check if the service is up, read recent logs,
inspect deployment status. No code changes — read-only.

## Action Routing

| Action | What it does |
|--------|-------------|
| `/monitor` or `/monitor health` | Health endpoint + deployment status |
| `/monitor logs` | Recent Railway logs (last 100 lines) |
| `/monitor deployments` | List recent deployments with status |
| `/monitor full` | All of the above in one pass |

---

## Health Check (default)

1. **Hit the health endpoint**:
   - Read `PRODUCTION_URL` from `.dev-context/project.conf`. If empty, try `mcp__railway-mcp-server__generate-domain` (or the project's hosting MCP) to discover the current URL; if that's unavailable too, ask the user for the URL.
   ```bash
   curl -sf "${PRODUCTION_URL}/health" | jq .
   ```
   - Expected: `{"status": "ok"}`
   - If fails: retry once after 5 seconds
   - If still fails: report DOWN

2. **Check latest deployment**:
   - Use Railway MCP: `mcp__railway-mcp-server__list-deployments` (service: "web", environment: "production", limit: 1)
   - Fallback: `railway status --json` via Bash
   - Report: deployment status, timestamp, commit SHA

3. **Output**:
   ```
   ## Production Health

   | Check | Status |
   |-------|--------|
   | Health endpoint | OK / DOWN |
   | Latest deploy | SUCCESS / BUILDING / FAILED |
   | Deploy time | <timestamp> |
   | Commit | <short SHA> — <subject> |
   ```

---

## Logs

1. **Fetch recent logs**:
   - Railway MCP: `mcp__railway-mcp-server__get-logs` (service: "web", environment: "production")
   - Fallback: `railway logs --service web` via Bash

2. **Scan for patterns**:
   - `ERROR` or `CRITICAL` — highlight these
   - `Traceback` — extract full stack trace
   - Repeated patterns — note if same error appears multiple times

3. **Output**: Raw logs with highlighted errors, plus a summary:
   ```
   ## Log Summary
   - Total lines: <N>
   - Errors found: <N>
   - Most recent error: <1-line summary>
   - Pattern: <repeating / one-off / none>
   ```

---

## Deployments

1. **List recent deployments**:
   - Railway MCP: `mcp__railway-mcp-server__list-deployments` (limit: 5)
   - Show: status, timestamp, trigger (commit SHA or manual)

2. **Output**:
   ```
   ## Recent Deployments

   | # | Status | Time | Commit | Trigger |
   |---|--------|------|--------|---------|
   | 1 | SUCCESS | 2026-02-27 10:30 | abc1234 | push to master |
   | 2 | FAILED | 2026-02-27 09:15 | def5678 | push to master |
   ```

---

## Full

Run all three checks sequentially: health → deployments → logs.
Present as a single report.

---

## Failure Modes

| Failure | Action |
|---------|--------|
| Railway MCP unavailable | Fallback to `railway` CLI via Bash |
| `railway` CLI not installed | Use `curl` for health check, report MCP/CLI unavailable |
| Health endpoint URL changed | Try `mcp__railway-mcp-server__generate-domain` to discover current URL |
| No deployments found | Report "no deployments" — may be a new service |

## Notes

- This skill is **read-only** — it never modifies code, deploys, or restarts services
- If the service is down, suggest: "Run `/hotfix` or check Railway dashboard manually"
- If a deployment failed, show the logs and suggest next steps
