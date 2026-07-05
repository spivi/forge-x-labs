---
name: security-review
description: "Deep security analysis against OWASP Top 10 (Web, API, LLM) and project-specific security rules. Runs pip-audit, bandit, and manual review. Use when: /security-review, security audit, vulnerability check, OWASP review, security scan, is it secure, pentest check. Target: file path, directory, or 'staged'."
---

# Security Review Skill

Deep security analysis against OWASP Top 10 and project-specific security rules.

## Instructions

1. **Read the Security Architect agent definition** at `.dev-context/agents/security_architect.md`
2. **Read security rules** at `.dev-context/rules/security.md`
3. **Identify the target**: specific file, directory, or staged git changes
4. **Run automated scans** (if tools are available locally):
   - `pip-audit` (dependency CVEs)
   - `bandit -r <target> -ll -ii` (static security analysis)
5. **Perform manual security analysis** on each file:

### OWASP Top 10 Checks
- [ ] **A01 Broken Access Control**: auth bypass, missing permission checks, IDOR
- [ ] **A02 Cryptographic Failures**: weak algorithms, hardcoded keys
- [ ] **A03 Injection**: SQL, command, XSS — including indirect data flows
- [ ] **A04 Insecure Design**: missing rate limits, trust boundary violations
- [ ] **A05 Security Misconfiguration**: debug mode, default creds, **exposed docs/debug endpoints**
- [ ] **A06 Vulnerable Components**: known CVEs in dependencies
- [ ] **A07 Auth Failures**: weak password policies, missing brute-force protection
- [ ] **A08 Data Integrity Failures**: insecure deserialization
- [ ] **A09 Logging Failures**: sensitive data in logs, missing audit trail
- [ ] **A10 SSRF**: user-controlled URLs without validation

### Production Hardening Checks
- [ ] FastAPI docs disabled in production (`docs_url=None, redoc_url=None, openapi_url=None`)
- [ ] Security headers set at application level (not relying solely on CDN)
- [ ] No 500 errors on public endpoints from invalid/missing inputs
- [ ] Health endpoint does not expose internal state or versions

### SSRF-Specific Checks
- [ ] Any outbound HTTP client that fetches user-supplied URLs has validation
- [ ] Private IP ranges blocked before outbound requests
- [ ] Non-HTTP schemes blocked (file://, gopher://, ftp://)
- [ ] Redirect following either disabled or validated
- [ ] Timeout and response size limits set on outbound requests

### Rate Limiting Checks
- [ ] All user-facing endpoints have rate limits (not just auth)
- [ ] Webhook/callback endpoints rate limited per IP and per sender
- [ ] LLM-invoking endpoints rate limited to prevent cost amplification
- [ ] Rate limit responses return 429 with Retry-After header

### Input Validation Checks
- [ ] Path parameters validated before database access
- [ ] Empty/missing query parameters handled with 400, not crash
- [ ] Unicode/non-ASCII input handled without errors
- [ ] Oversized inputs rejected before processing (413 or 400)

### Project-Specific Checks
- [ ] No user-supplied data in `text()` SQL queries
- [ ] API keys loaded from env vars only (Pydantic Settings)
- [ ] CORS allowlist explicit (no wildcards)
- [ ] Response schemas exclude sensitive fields

### Data Flow Tracing
- Trace user input from API entry point through to storage/output
- Identify any point where untrusted data is used without sanitization
- Flag any user input used to construct URLs, file paths, or shell commands

## Output Format

```
## Security Review: [target]

**Risk Level**: LOW / MEDIUM / HIGH / CRITICAL

### Automated Scan Results
- pip-audit: [summary]
- bandit: [summary]

### Passing
- [check]: [evidence]

### Findings
- [severity]: `file:line` — [CWE-XXX] [description] — **Fix**: [recommendation]

### Production Hardening
- [status]: FastAPI docs in production
- [status]: Security headers
- [status]: Error handling on public endpoints

### Dependency Alerts
- [package@version]: [CVE-XXXX-YYYY] — [severity] — [recommendation]

**Verdict**: SECURE (0 findings) | REVIEW (informational) | BLOCK ([N] findings)
```
