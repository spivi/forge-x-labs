---
description: "Generate handoff state when switching AI platforms. Trigger: /handoff, switch platform, session end, save state"
arguments:
  - name: target_platform
    description: "Platform switching to (cursor, claude, antigravity, codex)"
    required: false
---

# Handoff Skill

Generate a session state snapshot for seamless platform switching.

## Instructions

When triggered, perform these steps:

1. **Summarize current state**: What was being worked on, what's done, what's pending
2. **List modified files**: Every file changed in this session with one-line summary
3. **Capture open questions**: Any unresolved decisions or ambiguities
4. **Note blockers**: Anything preventing progress
5. **Write next steps**: Concrete, actionable items for the next session

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
