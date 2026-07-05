---
name: social-animation
description: "Generate browser-based HTML/CSS/JS animations for social media from git diffs and PRs. Auto-selects animation style (Product Demo, Motion Graphics, Data Storytelling), renders bilingual MP4/GIF, saves to Notion. Use when: /social-animation, animation, visual content, social video, create animation, feature video. Modes: auto (from /social-media, skip if not animation-worthy) or standalone (default, always generates)."
---

# Social Animation Skill

Auto-generate browser-based HTML/CSS/JS animations for social media content from
git diffs and PRs. Every shipped feature becomes a viral-ready visual with zero
manual effort.

**CRITICAL**: All animations must reflect actual feature changes. Never fabricate
capabilities. Ground visuals in the real PR diff and PRD.

## Prerequisites

Before first use, ensure these tools are available:

```bash
# Playwright (one-time install)
npx playwright install chromium

# ffmpeg (check)
ffmpeg -version

# Verify
npx playwright --version && ffmpeg -version
```

If either is missing, output the HTML animation file only with a message:
```
Animation generated at social-assets/<{{TICKET_PREFIX}}-NNN>/animation-en.html
To render: install Playwright (`npx playwright install chromium`) and ffmpeg, then re-run.
```

---

## Step 1: Gather Context

1. **Read the ticket**:
   - `gh issue view <{{TICKET_PREFIX}}-NNN>` for issue details
   - Read PRD at `.dev-context/prds/{{TICKET_PREFIX}}-<NNN>.md` (if exists)

2. **Read the PR diff**:
   - `gh pr list --search "{{TICKET_PREFIX}}-<NNN>" --state merged` to find the merged PR
   - `gh pr diff <PR>` to see the actual code changes
   - `gh pr view <PR> --json title,body,additions,deletions,changedFiles`

3. **Read brand config**:
   - `.dev-context/social-brand.yml` for colors, fonts, logo, frame style

4. **Synthesize**:
   - What the feature does (plain language, one sentence)
   - Key visual concept (what would grab attention in a 5s scroll)
   - Target audience (developers, users, general public)

---

## Step 2: Analyze & Select Animation Mode

Based on the diff, select ONE animation mode:

### Mode Selection Rules

| Signal in Diff | Mode | Reasoning |
|---------------|------|-----------|
| New/changed files in `app/agent/tools/`, `app/api/`, `app/schemas/`, UI components | **Product Demo** | User-facing feature — show it in action |
| New/changed files in `app/core/`, `app/services/`, infrastructure, config, CI/CD | **Motion Graphics** | Abstract concept — explain visually with typography + icons |
| Performance changes, caching, batching, metrics, benchmarks | **Data Storytelling** | Numbers tell the story — animate the improvement |
| Mixed signals | Choose the mode matching the **primary user value** | |

### Duration Selection

| Diff Size | Changed Files | Duration | Loop |
|-----------|--------------|----------|------|
| < 50 lines | 1-2 files | 3-5s | Yes (seamless loop) |
| 50-200 lines | 3-5 files | 5-10s | No |
| > 200 lines | 6+ files | 10-15s | No |

Present the selection:
```
### Animation Plan
- **Mode**: Product Demo / Motion Graphics / Data Storytelling
- **Duration**: Xs
- **Loop**: Yes / No
- **Key Visual**: <one-line description of the animation concept>
- **Headline EN**: <short punchy text for the animation>
- **Headline HE**: <Hebrew translation>
```

**When `mode=auto`**: If the feature is purely internal (docs, CI config, agent
specs with no code changes), print skip message and exit:
```
Social Animation: Skipped for {{TICKET_PREFIX}}-NNN — no visual content opportunity.
```

---

## Step 3: Generate Animation (English)

Generate a single self-contained HTML file with embedded CSS and JS. The animation
must work by simply opening the file in a browser — no external dependencies
except Google Fonts (loaded via `<link>`).

Start from the template in `assets/template.html`. Read `references/animation-modes.md`
for mode-specific patterns (Product Demo, Motion Graphics, Data Storytelling) and
design principles.

Save the English animation to:
```
social-assets/<{{TICKET_PREFIX}}-NNN>/animation-en.html
```

---

## Step 4: Generate Hebrew Variant

Create a copy of the English animation with these changes:

1. **HTML lang/dir**: `<html lang="he" dir="rtl">`
2. **Font**: Replace `Inter` with `Heebo` (add Google Fonts link for Heebo)
3. **Text content**: Translate all visible text to Hebrew
4. **Layout mirroring**: RTL-aware positioning (swap left/right margins, alignments)
5. **Chat bubbles**: Mirror bubble radius (user: `12px 12px 12px 0`, bot: `12px 12px 0 12px`)

Save to:
```
social-assets/<{{TICKET_PREFIX}}-NNN>/animation-he.html
```

---

## Step 5: Render & Convert

Render and convert using `scripts/capture.mjs` and ffmpeg. See
`references/rendering-guide.md` for the full rendering pipeline, ffmpeg commands,
file size checks, and cleanup steps.

Output files per language: landscape MP4, square MP4, landscape GIF (6 files total
for EN + HE).

---

## Step 6: Save to Notion

1. **Search** for "Social Media Content" page using Notion MCP
2. **Create subpage** titled `{{TICKET_PREFIX}}-<NNN>: <feature title> — Animation`
3. **Body content**:

```markdown
# Animation: {{TICKET_PREFIX}}-<NNN> — <feature title>

## Animation Details
- **Mode**: <Product Demo / Motion Graphics / Data Storytelling>
- **Duration**: <X>s
- **Concept**: <one-line description>

## English Variants
- Landscape MP4 (Twitter/X): `social-assets/<{{TICKET_PREFIX}}-NNN>/en-landscape.mp4`
- Square MP4 (Instagram): `social-assets/<{{TICKET_PREFIX}}-NNN>/en-square.mp4`
- GIF (LinkedIn): `social-assets/<{{TICKET_PREFIX}}-NNN>/en-landscape.gif`

## Hebrew Variants
- Landscape MP4 (Twitter/X): `social-assets/<{{TICKET_PREFIX}}-NNN>/he-landscape.mp4`
- Square MP4 (Instagram): `social-assets/<{{TICKET_PREFIX}}-NNN>/he-square.mp4`
- GIF (LinkedIn): `social-assets/<{{TICKET_PREFIX}}-NNN>/he-landscape.gif`

## Source Files
- English HTML: `social-assets/<{{TICKET_PREFIX}}-NNN>/animation-en.html`
- Hebrew HTML: `social-assets/<{{TICKET_PREFIX}}-NNN>/animation-he.html`

## Suggested Post Copy
<Include brief post suggestions for each platform, or reference
the /social-media content plan if it exists>
```

### Notion Fallback

If Notion MCP is unavailable:
- Print the content summary to terminal
- Print: `Notion unavailable. Files saved locally at social-assets/<{{TICKET_PREFIX}}-NNN>/`
- Do NOT fail — the files are the primary deliverable

---

## Step 7: Report

Print final summary:

```
## Animation Generated: {{TICKET_PREFIX}}-<NNN>

- **Mode**: <mode>
- **Duration**: <X>s (<loop/no loop>)
- **Languages**: English + Hebrew
- **Files**: 8 total
  - animation-en.html, animation-he.html (source)
  - en-landscape.mp4, en-square.mp4, en-landscape.gif
  - he-landscape.mp4, he-square.mp4, he-landscape.gif
- **Location**: social-assets/<{{TICKET_PREFIX}}-NNN>/
- **Notion**: <link or "saved locally only">

Preview the animation by opening:
  open social-assets/<{{TICKET_PREFIX}}-NNN>/animation-en.html
```

---

## Validation Rules

- **Never fabricate** features — all visuals must match actual code changes
- **Always read the diff** before selecting animation mode
- **Always apply brand config** from `social-brand.yml`
- **Always generate both languages** (EN + HE) — never skip Hebrew
- **GIF max 5MB** — reduce quality/resolution/duration if exceeded
- **Auto mode**: skip silently for internal-only changes (no user-facing visual)
- **Standalone mode**: always generate, always show full report
- **If Playwright unavailable**: output HTML files only, print install instructions
- **If ffmpeg unavailable**: output HTML files only, print install instructions
- **Clean up temp files**: remove `raw/`, `palette.png` after conversion
