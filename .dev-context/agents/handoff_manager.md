# Handoff Manager Agent

> Triggers on merge to main or manual `/release` command. Generates release
> notes grouped by conventional commit type, creates draft GitHub Releases,
> and notifies the human for approval.

## Identity

- **Role**: Release communicator and release notes generator
- **Boundaries**: Does NOT deploy code (deployment is handled by CI/CD).
  Does NOT merge PRs. Does NOT publish releases without human approval.
  Generates release artifacts only.
- **Personality**: Precise, factual, thorough. Lists every change without
  editorializing. Presents clear options for version bumping.

## Why This Exists

Release notes are tedious to write manually but critical for project history.
Without this agent:

1. **Release notes are skipped** or written hastily after merging
2. **Version tags are inconsistent** (manual semver is error-prone)
3. **Stakeholders are not notified** about what shipped
4. **Change history is lost** when not captured at release time

The Handoff Manager automates release note generation from conventional
commits, suggests the correct semver bump, and creates a draft GitHub Release
for human review before publishing.

## Trigger

| Method | When |
|--------|------|
| GitHub Action | Push to `main`/`master` (post-merge) |
| Manual | Human runs `/release` skill in Claude Code session |

## Input

1. **Git history**: `git log <last-tag>..HEAD --format=...`
2. **Last release tag**: `git describe --tags --abbrev=0` (e.g., `v0.2.0`)
3. **Commit messages**: Parsed for conventional commit prefix and scope
4. **Ticket references**: Extracted from commit scopes (pattern: `{{TICKET_PREFIX}}-NNN`)

## Tools

- **git**: `git log`, `git tag`, `git describe` for history traversal
- **GitHub CLI**: `gh release create --draft` for draft releases
- **Shell scripting**: Commit parsing, semver calculation, report generation
- **No AI/LLM**: This agent is purely deterministic -- saves cost

## Process

### 1. Determine Version Range

```bash
LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
if [ -z "$LAST_TAG" ]; then
  RANGE="HEAD"; LAST_TAG="v0.0.0"
else
  RANGE="${LAST_TAG}..HEAD"
fi
```

### 2. Collect and Parse Commits

```bash
git log "$RANGE" --format="%h %s" --no-merges
```

Parse each message with regex:
`^(feat|fix|refactor|test|docs|chore|perf)(\(.+?\))?(!)?: (.+)$`

Extract: type, scope (optional), breaking flag, subject.

### 3. Compute Next Version

Project-scoped versioning -- always bump MINOR by 1, reset PATCH to 0:
- `v0.2.0` -> `v0.3.0` -> `v0.4.0`
- Major bumps (`v1.0.0`) are manual human decisions only
- If tag exists, error and ask human for override

### 4. Generate Release Notes

Group commits by type with human-readable headers. Empty sections omitted.
Each entry includes short hash and ticket references from scope.

```markdown
## What's Changed
### New Features
- <subject> (<hash>) [{{TICKET_PREFIX}}-NNN]
### Bug Fixes
- <subject> (<hash>)
### Breaking Changes
- <subject> (<hash>) -- BREAKING
**Full Changelog**: <compare-url>
```

### 5. Present Draft for Human Approval

Show version bump reasoning, commit counts, and generated notes. Offer:
Approve, Edit, Change version, or Skip.

### 6. Create Draft GitHub Release

On approval: `gh release create <version> --title "<version>" --notes-file release-notes.md --draft`

The release is created as a DRAFT. Human publishes from GitHub Releases page.

### 7. Log KPIs and Notify

Append row to `.dev-context/kpis/release-log.csv`. Inform human of draft URL.

## Output

| Artifact | Location | Format |
|----------|----------|--------|
| Release notes | GitHub Release (draft) | Grouped markdown |
| Release tag | Git tag (created by `gh release`) | Semver `vX.Y.Z` |
| KPI log entry | `.dev-context/kpis/release-log.csv` | CSV row |
| Human notification | CLI output or PR comment | Structured text |

## Human Gates

The Handoff Manager **requires human approval** for:

- [ ] Release notes content before creating the draft release
- [ ] Version number confirmation (especially for major/minor bumps)
- [ ] Publishing the draft release (manual action on GitHub)

The agent NEVER publishes a release automatically. All releases are drafts.

## Failure Modes

| Failure | Action |
|---------|--------|
| No tags exist in repository | Use `v0.0.0` as base, compute from all history |
| No conventional commits found | List raw subjects ungrouped, warn human |
| `gh` CLI not authenticated | Print release notes to stdout, ask human to create manually |
| Git history too large (>500 commits) | Truncate to last 100, note in release notes |
| Tag already exists for computed version | Increment patch and retry |
| GitHub API rate limit | Retry once after 60s, then print notes locally |
| Commit has no conventional prefix | Group under "Other Changes" section |

## Integration with Other Agents

| Agent | Handoff Manager Interaction |
|-------|----------------------------|
| **E2E Tester** | Runs before merge. Handoff Manager acts after merge. |
| **Code Reviewer** | Runs before merge. Handoff Manager acts after merge. |
| **Scrum Master** | Tracks release cadence KPI. Escalates if no release in a sprint. |
| **Budget Review** | Zero additional AI cost (no LLM calls). Only CI compute. |
| **Product Manager** | Release notes feed PM's go-to-market suggestions. |

## KPI Tracking

Appends a row to `.dev-context/kpis/release-log.csv` after each run:

```csv
version,date,features_count,bugfixes_count,notes_approved_first_draft,notification_sent,human_edits
```

KPI targets (from `.dev-context/kpis/agent-kpis.md`):

| KPI | Target |
|-----|--------|
| Release cadence | >= 1 release/sprint |
| Notes accuracy | 100% (notes match actual changes) |
| Notification delivery | 100% |
| First-draft approval rate | >= 80% |

## GitHub Action Configuration

See `.github/workflows/release.yml`. Triggers via `workflow_dispatch` (manual).

Required secrets: `GITHUB_TOKEN` (automatically available).
No additional secrets needed (no AI/LLM provider keys required).

## Resource Validation

- [ ] Git history accessible (`git log` works in CI)
- [ ] `gh release create` permissions granted (`contents: write`)
- [ ] `.dev-context/kpis/release-log.csv` is writable
