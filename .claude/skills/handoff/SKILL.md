---
name: handoff
description: "Generate session state snapshot for seamless AI platform switching. Updates STATUS.md with current state, modified files, open questions, and next steps. Use when: /handoff, switch platform, session end, save state, save session, end session, switching to cursor, switching to codex, platform handoff."
---

# Handoff Skill

Generate a session state snapshot for seamless platform switching.

> **Not to be confused with `/handoff-review`** — that skill emits a human-only GitHub
> issue to review a *merged wave* of features. This `/handoff` skill saves *AI-session
> state* (STATUS.md snapshot) for switching platforms mid-task.

## Instructions

When triggered, perform these steps:

1. **Summarize current state**: What was being worked on, what's done, what's pending
2. **List modified files**: Every file changed in this session with one-line summary
3. **Capture open questions**: Any unresolved decisions or ambiguities
4. **Note blockers**: Anything preventing progress
5. **Write next steps**: Concrete, actionable items for the next session
6. **Update cc10x session memory** (so the next session resumes with context):
   - `.claude/cc10x/activeContext.md` — refresh Current Focus, Recent Changes, Next Steps, Blockers, Last Updated
   - `.claude/cc10x/patterns.md` — append any durable gotcha/learning discovered this session (under the right heading)
   - `.claude/cc10x/progress.md` — update workflow status + verification evidence

## Output

Update `STATUS.md` with this template:

Read the project identifier from `.dev-context/project.conf` (`PROJECT_ID` field).
Reference it in active tasks using the Linear issue format: `PROJECT_ID-NNN`.

```markdown
## Current State

- **Project**: [PROJECT_ID from project.conf]
- **Phase**: [current project phase]
- **Active task**: [PROJECT_ID-NNN — what's in progress, or "None"]
- **Blocked on**: [blockers or "nothing"]
- **Last agent**: [your model name]
- **Last platform**: [cursor/claude/antigravity/codex]
- **Timestamp**: [ISO 8601]

## Recent Changes

- `path/to/file.py` — [what changed]
- `path/to/other.py` — [what changed]

## Open Questions

1. [question needing resolution]

## Next Steps

1. [specific action item]
2. [specific action item]
```

Append a row to the Session Log table at the bottom of `STATUS.md`.

## Validation

- Verify all modified files actually exist
- Ensure next steps are actionable (start with a verb)
- Confirm no sensitive data in the status file
