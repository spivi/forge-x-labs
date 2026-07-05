---
name: frontend-design
description: "Create distinctive, production-grade frontend interfaces using a multi-tier design cascade: Gemini CLI for design specs, Figma MCP for automated visual generation, Stitch for optional human-initiated design, Claude as orchestrator and fallback. Use when: /frontend-design, build UI, create component, design page, frontend work, styling, beautifying web UI."
---

# Frontend Design Skill (Design Cascade)

Create distinctive, production-grade frontend interfaces with high design
quality. Uses a tiered approach to optimize token usage and design output.

## Tier System

| Tier | Tool | Role | Automation | When |
|------|------|------|------------|------|
| **T1** | Gemini CLI | Design specs: tokens, CSS, components, animations | Fully automated | Default for design thinking |
| **T2** | Figma MCP | Visual generation + code extraction | Fully automated | Default visual tier |
| **T2b** | Stitch MCP | Visual generation (human uses web UI) | Human-in-the-loop | Optional, human-initiated |
| **T3** | Claude (native) | Orchestration + generation fallback | Fully automated | Always active |

**Key principle**: T1 and T2 are fully automated (no human step needed).
T2b (Stitch) is only used when the human explicitly wants to browse the
Stitch web UI for visual inspiration or iteration.

---

## Phase 0: Availability Check

Before starting design work, check tool availability:

1. **Gemini CLI**: Run `GEMINI_API_KEY="..." command -v gemini` via Bash.
   - Available: T1 active
   - Not found: skip T1

2. **Figma MCP**: Check if Figma tools are available
   (`generate_figma_design`, `get_design_context`, `get_screenshot`).
   - Available: T2 active
   - Not available: check for Stitch (T2b), then fall back to T3

3. **Stitch MCP** (optional): Check if `stitch` MCP tools are listed.
   Note: Stitch MCP is **read-only** — generation requires the web UI.
   Only useful if the human wants to iterate in stitch.withgoogle.com.

4. **Report tier status** to the user:
   ```
   Design Cascade: T1 [Gemini ✓/✗] → T2 [Figma ✓/✗] → T2b [Stitch ✓/✗] → T3 [Claude ✓]
   ```

---

## Phase 1: Design Thinking (Claude — always)

Before any code generation, understand context and commit to a BOLD
aesthetic direction. This phase is always done by Claude as orchestrator.

- **Purpose**: What problem does this interface solve? Who uses it?
- **Tone**: Pick an extreme aesthetic direction — brutally minimal,
  maximalist chaos, retro-futuristic, organic/natural, luxury/refined,
  playful/toy-like, editorial/magazine, brutalist/raw, art deco/geometric,
  soft/pastel, industrial/utilitarian. Use for inspiration but design one
  true to the project's character.
- **Constraints**: Technical requirements, RTL support, mobile-first,
  framework, performance, accessibility.
- **Differentiation**: What makes this UNFORGETTABLE? What's the one
  thing someone will remember?

**CRITICAL**: Choose a clear conceptual direction and execute it with
precision. Bold maximalism and refined minimalism both work — the key is
intentionality, not intensity.

Read `.dev-context/design-guidelines.md` if it exists for project-specific
constraints.

---

## Phase 2: Design Specs (T1: Gemini CLI)

**Skip this phase if T1 is not available.**

Delegate token-heavy design work to Gemini CLI. Run up to 3 parallel
prompts for efficiency:

### 2a. Design Tokens & Color Palette

```bash
GEMINI_API_KEY="..." gemini -p "Generate a design token system for:
[design brief from Phase 1]. Include: color palette (hex values),
typography (font pairing from [supported fonts]), type scale (rem),
spacing (4px base), border radius, colored shadows.
Output CSS custom properties and Tailwind config extend." 2>&1
```

### 2b. Component Specs

```bash
GEMINI_API_KEY="..." gemini -p "Design component specs for:
[design brief]. Include HTML structure with Tailwind classes for:
[list components]. Include RTL rules (logical properties)." 2>&1
```

### 2c. Animation Specs

```bash
GEMINI_API_KEY="..." gemini -p "Specify CSS-only animations for:
[design brief]. Include @keyframes for: page load sequence,
card stagger reveal, hover states, scroll-triggered reveals,
shimmer skeleton. RTL-aware transforms." 2>&1
```

### Validation

Claude reviews Gemini's output for:
- Compliance with project design guidelines
- RTL correctness (logical properties, not left/right)
- No generic AI aesthetics (Inter, Roboto, purple gradients)
- Proper CSS custom properties usage

### Quota handling

If exit code != 0 AND stderr contains "quota", "rate limit",
"RESOURCE_EXHAUSTED", or "429": skip to T2/T3. Retry once for
other errors.

---

## Phase 3: Visual Generation (T2: Figma MCP — Automated)

**Skip this phase if T2 is not available.**

Use Figma MCP for fully automated visual design generation. Unlike
Stitch, Figma MCP can **generate AND extract** designs programmatically.

**IMPORTANT**: Before calling any `use_figma` tool, invoke the
`figma:figma-use` skill first. This is mandatory.

### 3a. Generate Design in Figma

Use `generate_figma_design` with:
- Design direction from Phase 1
- Token system from Phase 2 (if available)
- Target components and layout

The tool creates a Figma design and returns a file URL.

### 3b. Extract & Review

1. Use `get_screenshot` to visually preview the generated design
2. Use `get_design_context` to extract code + design tokens
3. Review against Phase 1 vision — iterate if needed

### 3c. Fallback

- If Figma MCP fails or produces poor results: skip to T2b or T3
- If the user prefers Stitch: proceed to Phase 3b (Stitch)

---

## Phase 3b: Visual Generation (T2b: Stitch — Human-in-the-Loop)

**Only use when the human explicitly requests Stitch, or T2 is unavailable.**

Stitch MCP is **read-only** — it extracts code from designs but cannot
generate them. See `/stitch` skill for full workflow.

### Workflow

1. Claude crafts an optimized Stitch prompt from Phase 1 + Phase 2
2. Present prompt to the human for stitch.withgoogle.com
3. Human generates screens in the web UI
4. Claude extracts code via `get_screen_code` / `get_screen_image`

### Fallback

- If the human is unavailable: skip to Phase 4 (Claude native)
- If Stitch quota exhausted (350/month): skip to Phase 4

---

## Phase 4: Claude Native Generation (T3: Fallback)

If T1, T2, and T2b are all unavailable or exhausted, Claude generates
everything natively using the full aesthetic guidelines below.

### Frontend Aesthetics Guidelines

- **Typography**: Choose fonts that are beautiful, unique, and interesting.
  Avoid generic fonts like Arial and Inter; opt for distinctive choices
  that elevate the frontend. Pair a distinctive display font with a
  refined body font.

- **Color & Theme**: Commit to a cohesive aesthetic. Use CSS variables for
  consistency. Dominant colors with sharp accents outperform timid,
  evenly-distributed palettes.

- **Motion**: Animations for effects and micro-interactions. Prioritize
  CSS-only solutions for HTML. Use Motion library for React when available.
  Focus on high-impact moments: one well-orchestrated page load with
  staggered reveals creates more delight than scattered micro-interactions.
  Use scroll-triggering and hover states that surprise.

- **Spatial Composition**: Unexpected layouts. Asymmetry. Overlap. Diagonal
  flow. Grid-breaking elements. Generous negative space OR controlled density.

- **Backgrounds & Visual Details**: Create atmosphere and depth rather than
  defaulting to solid colors. Add contextual effects and textures that match
  the aesthetic — gradient meshes, noise textures, geometric patterns, layered
  transparencies, dramatic shadows, decorative borders, custom cursors,
  grain overlays.

**NEVER** use generic AI-generated aesthetics: overused fonts (Inter, Roboto,
Arial, system fonts), cliched color schemes (purple gradients on white),
predictable layouts, cookie-cutter design. No design should be the same.

Match implementation complexity to the aesthetic vision. Maximalist designs
need elaborate code with extensive animations and effects. Minimalist
designs need restraint, precision, and careful attention to spacing,
typography, and subtle details.

---

## Phase 5: Integration & Refinement (Claude — always)

Regardless of which tier produced the code:

1. **Fetch framework docs via Context7** — Before adapting generated code,
   query Context7 for the target framework/library docs (e.g., Tailwind,
   React, Jinja2) to ensure current API usage. See `.dev-context/rules/context7.md`.
   If Context7 unavailable, use WebSearch as fallback.
2. **Adapt to project stack** — Ensure output matches project conventions
   (templates, existing CSS structure, component patterns)
3. **Apply project design tokens** — Map to existing CSS variables
4. **Mobile verification** — Ensure responsive behavior
5. **RTL verification** — Check logical properties, direction-aware animations
6. **Accessibility** — ARIA labels, keyboard navigation, contrast ratios
7. **Production readiness** — Clean code, no dead CSS, proper imports
