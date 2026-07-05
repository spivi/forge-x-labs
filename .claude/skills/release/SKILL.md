---
name: release
description: "Generate release notes from conventional commits and create draft GitHub Releases. Parses commit history, suggests semantic version, groups changes by type. Use when: /release, release notes, create release, version bump, changelog, what changed, prepare release. Actions: generate (default), preview, history."
---

# Release Skill (Handoff Manager)

Generate structured release notes from conventional commits since the last
tag, suggest the next semver version, and create a draft GitHub Release.
Read the full agent definition at `.dev-context/agents/handoff_manager.md`
before proceeding.

## Instructions

### Action: `generate` (default — generate release notes)

Generate release notes and optionally create a draft GitHub Release.

1. **Read context** (mandatory, in order):
   - `.dev-context/agents/handoff_manager.md` — full agent process
   - `.dev-context/project.conf` — project ID
   - `STATUS.md` — current phase

2. **Determine version range**:
   - Run: `git describe --tags --abbrev=0` to find the last tag
   - If no tags exist, use the full history and base version `v0.0.0`
   - Run: `git log <last-tag>..HEAD --format="%h %s" --no-merges`
   - If no commits found since last tag, inform human and stop

3. **Parse commits** into conventional commit groups:
   - Pattern: `^(feat|fix|refactor|test|docs|chore|perf)(\(.+?\))?(!)?: (.+)$`
   - Extract: type, scope (optional), breaking flag, subject
   - Extract PR numbers from merge commits: `#NNN`
   - Extract ticket references from scope: `{{TICKET_PREFIX}}-NNN` or `{{PROJECT_ID}}-NNN`
   - Commits not matching the pattern go under "Other Changes"

4. **Compute next version** ({{PROJECT_ID}}-D019 — project-scoped versioning):
   - Parse current tag: `vMAJOR.MINOR.PATCH`
   - Always bump MINOR by 1, reset PATCH to 0 (e.g., `v0.2.0` → `v0.3.0`)
   - Major bumps are manual only — ask human if they want a major bump
   - If tag already exists, error and ask human for a version override
   - Display reasoning: "project completion → minor bump per {{PROJECT_ID}}-D019"

5. **Generate release notes** grouped by type:
   ```
   ## What's Changed

   ### New Features
   - <subject> (<short-hash>) [{{TICKET_PREFIX}}-NNN]

   ### Bug Fixes
   - <subject> (<short-hash>)

   ### Refactoring
   - <subject> (<short-hash>)

   ### Tests
   - <subject> (<short-hash>)

   ### Documentation
   - <subject> (<short-hash>)

   ### Chores
   - <subject> (<short-hash>)

   ### Performance
   - <subject> (<short-hash>)

   ### Breaking Changes
   - <subject> (<short-hash>) -- BREAKING

   **Full Changelog**: <compare-url>
   ```
   Omit empty sections. Include short hash (first 7 chars) and any
   ticket references found in scope.

6. **Present draft to human**:
   ```
   ## Release Draft: <suggested-version>

   **Version bump**: <current> → <suggested> (<reason>)
   **Commits**: <N> total (<N> feat, <N> fix, <N> other)

   <generated release notes>

   ---
   ### Recommended Action
   - Approve → Create draft GitHub Release tagged <suggested-version>
   - Edit → Tell me what to change in the notes
   - Change version → Specify a different version number
   - Skip → Do not create a release
   ```

7. **On approval**: Create the draft release:
   ```bash
   gh release create <version> \
     --title "<version>" \
     --notes-file release-notes.md \
     --draft
   ```
   Report the URL to the human.

8. **Log KPIs**: Append a row to `.dev-context/kpis/release-log.csv`:
   ```
   <version>,<date>,<feat_count>,<fix_count>,<true|false>,<true>,<0>
   ```

### Action: `preview`

Show release notes without creating a release.

1. Follow steps 1-5 from `generate` above
2. Present the notes with version suggestion
3. Do NOT offer to create a release
4. Useful for reviewing what would be in the next release

### Action: `history`

Show past releases.

1. Run: `gh release list --limit 10`
2. For each release, show: tag, date, title, draft/published status
3. Present as a table:
   ```
   ## Release History

   | Version | Date | Status | Title |
   |---------|------|--------|-------|
   | v0.3.0 | 2026-02-15 | Published | v0.3.0 |
   ```

## Validation

- Never create a non-draft release (always use `--draft`)
- Never publish a release without explicit human approval
- Never skip the version suggestion step — always show reasoning
- Always parse ALL commits since last tag (do not truncate without warning)
- Always include ticket references when found in commit scope
- If `gh` CLI is unavailable, print release notes and instruct human to
  create the release manually
- If no conventional commits found, list raw subjects under "Other Changes"
- Log every release attempt (including skipped) to release-log.csv
- When version conflict occurs (tag exists), suggest next patch increment
