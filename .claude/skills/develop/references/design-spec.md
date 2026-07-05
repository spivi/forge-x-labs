# Full Design Spec Process

Only generated when explicitly requested (via UX opinion step in Phase 2 or
manual `/develop design {{TICKET_PREFIX}}-NNN`).

1. **Read**: `.dev-context/design-guidelines.md`, `app/templates/shop.html`

2. **Invoke `example-skills:frontend-design`** with constraints:
   - RTL Hebrew-first (`dir="rtl"`, Heebo font)
   - Mobile-first, one-handed supermarket use (48px+ touch targets)
   - Single Jinja2 template — no build step, no framework
   - Anti-AI-aesthetic guidelines from design-guidelines.md

3. **Generate design spec** with sections:
   - Layout, Typography, Colors, Interactions, Mobile Constraints
   - Anti-AI Checklist

4. **Human gate** via `AskUserQuestion`: Approve / Revise / Skip

5. **On approval**: Append to PRD file as `## Design Spec` (binding constraint)
