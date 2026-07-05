# Threat Model Template

Append this to the PRD after generating the main sections. Read the Security
Architect agent definition at `.dev-context/agents/security_architect.md`
(section "Threat Model Advisory") for analysis guidelines.

Only populate threat tables that are relevant to the feature. If a category
doesn't apply (e.g., no LLM interaction), write "N/A -- feature does not
involve LLM interactions" instead of the table.

If the feature has no security-relevant surface (pure refactor, docs-only),
write: `## Threat Model\n\nNo security-relevant changes. PROCEED.`

```markdown
## Threat Model

### Attack Surface
- <New endpoints, data flows, or integrations introduced>

### Threats (OWASP Web App Top 10)
| Threat | Likelihood | Impact | Mitigation |
|--------|-----------|--------|------------|
| <description> | High/Med/Low | High/Med/Low | <recommended control> |

### Threats (OWASP API Security Top 10)
| Threat | Likelihood | Impact | Mitigation |
|--------|-----------|--------|------------|
| <description> | High/Med/Low | High/Med/Low | <recommended control> |

### Threats (OWASP LLM Top 10)
| Threat | Likelihood | Impact | Mitigation |
|--------|-----------|--------|------------|
| <description> | High/Med/Low | High/Med/Low | <recommended control> |

### Security Requirements
- [ ] <Requirement that must be in acceptance criteria>

### Security Recommendation
PROCEED / PROCEED WITH CONDITIONS / BLOCK (explain)
```
