---
name: ux-review
description: "Review frontend UX for engagement anti-patterns and conversion risks. Analyzes 8 engagement scenarios (multi-step flows, CTAs, feedback, trust signals, mobile, RTL, onboarding, error handling). Use when: /ux-review, UX audit, engagement review, conversion check, usability review, user experience check. Target: file path, directory, or 'staged'."
---

# UX Engagement Review Skill

Analyze frontend changes for user engagement anti-patterns that cause drop-offs,
confusion, or lost conversions. Goes beyond visual design compliance — focuses on
the psychological flow of user interactions.

## Instructions

1. **Read context** (mandatory):
   - `.dev-context/design-guidelines.md` — binding visual constraints
   - The target file(s) — read full contents of every HTML/CSS/JS file in scope

1b. **Visual validation via Stitch** (if available):
    - Check if Stitch MCP tools are available (`get_screen_image`,
      `get_screen_code`, `build_site`)
    - If available: Use `build_site` to render the target HTML/CSS and
      `get_screen_image` to capture a visual screenshot for analysis
    - This provides pixel-level validation rather than code-only review
    - If Stitch unavailable: proceed with code-only analysis (existing behavior)

1c. **Gemini-powered analysis** (if available):
    - Check if Gemini CLI is available: `command -v gemini` via Bash
    - If available: Send the target code (and screenshot from 1b if captured)
      to Gemini for detailed UX analysis:
      ```bash
      gemini -p "Analyze this UI code for UX engagement anti-patterns.
      Focus on: [applicable scenarios from S1-S8 below].
      Code: [target code content]
      Report findings as BLOCK/WARN/INFO with specific line references." 2>&1
      ```
    - If Gemini returns quota error (exit code != 0, stderr contains
      "quota", "rate limit", "RESOURCE_EXHAUSTED", or "429"):
      proceed with Claude-only analysis
    - Merge Gemini findings with Claude's own analysis — deduplicate,
      prefer the more specific finding when both flag the same issue
    - If Gemini unavailable: proceed with Claude-only analysis (existing behavior)

2. **Detect applicable scenarios** — scan the target for which engagement
   categories are relevant. Only report on categories that apply to the change.
   A simple color tweak should not trigger a 10-category review.

3. **For each applicable scenario**, analyze the code against the anti-patterns
   listed below and report findings.

---

## Engagement Scenario Catalog

### S1: Multi-Step Flow Psychology

**Applies when**: code contains multiple form steps, staged reveals, wizard flows,
or any UI that transitions through distinct states before a final action.

**Anti-patterns**:
- **Premature completion signal**: Success messages, checkmarks, celebration
  animations, or "You're in!" language appearing BEFORE the user has completed
  all required steps. This is the #1 registrant killer.
- **Missing progress indicator**: No step dots, progress bar, or breadcrumbs
  to signal how many steps remain. Users abandon when they can't gauge effort.
- **Unclear step transitions**: Abrupt show/hide without animation. Users lose
  spatial context of where they are in the flow.
- **Optional-feeling required steps**: Passive button language ("Done", "Skip")
  on steps that are actually needed for completion. Use imperative active
  language ("Complete registration", "Confirm order").
- **No data safety net**: If the flow has multiple POSTs, earlier steps should
  fire a backup submission so partial data isn't lost if users bail mid-flow.

**What good looks like**:
- Progress indicator visible from step 1
- Each transition uses directional animation (RTL-aware)
- Final celebration only after the LAST step
- Active, urgent button copy on the completion step
- Backup data capture at each step boundary

---

### S2: Call-to-Action Clarity

**Applies when**: code contains buttons, links, or interactive elements that
drive user actions (form submits, navigation, purchases, signups).

**Anti-patterns**:
- **Competing primary CTAs**: Multiple buttons with equal visual weight on the
  same screen. Users freeze when they can't identify THE action.
- **Passive completion language**: "Done", "OK", "Close" on buttons that
  perform important actions. These signal "dismiss" not "act".
- **Ghost button for primary action**: Outline-only or text-only styling on
  the most important button. Primary CTAs need filled, high-contrast styling.
- **CTA below the fold without anchor**: If the main action requires scrolling,
  there's no sticky CTA or scroll indicator pointing to it.
- **Ambiguous next step**: After completing an action, the user has no clear
  indication of what happens next or what to do.

**What good looks like**:
- One primary CTA per screen (filled, high-contrast)
- Secondary actions visually subordinate (outline, muted color)
- Active imperative verbs ("Reserve my spot", "Start shopping", "Send list")
- Sticky mobile CTA for long pages
- Post-action: clear next step or confirmation with path forward

---

### S3: Feedback & State Transparency

**Applies when**: code performs async operations (fetch, form submit, API calls)
or has states that change based on user/system actions.

**Anti-patterns**:
- **Silent submission**: Form fires `fetch()` with no loading indicator. Users
  don't know if their click registered — they click again (double submit).
- **Ambiguous loading**: Spinner without text. Users can't tell if it's loading,
  processing, or stuck. Add contextual text ("Saving...", "Sending...").
- **No error recovery**: If `fetch()` fails silently (`catch(() => {})`), the
  user is stuck in a broken state with no feedback or retry option.
- **Optimistic UI without rollback**: UI updates immediately but has no plan
  for reverting if the server rejects the change.
- **State desync**: Hidden elements that should be shown, or visible elements
  that should be hidden based on the current state. Check all state transitions
  for completeness.

**What good looks like**:
- Every async action shows loading feedback within 100ms
- Loading text is contextual (not just a spinner)
- Error states are recoverable (retry button, helpful message)
- Optimistic updates have a rollback path
- All possible states are accounted for (empty, loading, success, error)

---

### S4: Trust & Conversion Signals

**Applies when**: code collects user data (forms, inputs, personal information)
or asks users to commit to an action (signup, purchase, share).

**Anti-patterns**:
- **Premature celebration**: Confetti, party animations, or emphatic success
  language before the action is actually confirmed server-side.
- **Missing privacy assurance**: Input fields collecting personal data (phone,
  email, name) with no nearby privacy text or "no spam" assurance.
- **Unclear data usage**: Form asks for data without explaining why it's needed
  or what happens next ("We'll WhatsApp you when ready").
- **No social proof near CTA**: If the page has social proof (user count,
  testimonials) but it's far from the action point, it's not reinforcing
  the decision at the critical moment.
- **Friction without justification**: Extra fields that aren't obviously
  necessary. Each field must justify its existence or be moved to a later step.

**What good looks like**:
- Privacy assurance text adjacent to data collection fields
- Social proof near or above the CTA
- "Why we ask" micro-copy for non-obvious fields
- Celebration only after server confirmation (or fire-and-forget with backup)
- Minimal fields per step — progressive profiling for the rest

---

### S5: Mobile & One-Handed Use

**Applies when**: code produces UI intended for mobile use (responsive layouts,
touch interactions, viewport-dependent behavior).

**Anti-patterns**:
- **Tiny touch targets**: Interactive elements (buttons, links, radio options)
  smaller than 48px in any dimension. Check `padding`, `min-height`, `height`.
- **Critical actions outside thumb zone**: Primary CTAs positioned at the top
  of the screen on mobile, requiring reach. Bottom-anchored is better.
- **Sticky elements blocking content**: Fixed headers/footers that eat >15%
  of viewport height on small screens.
- **No safe area handling**: Bottom-fixed elements without
  `env(safe-area-inset-bottom)` will be clipped by phone home indicators.
- **Scroll-dependent visibility**: Important CTAs that only appear after
  scrolling, with no hint that they exist.

**What good looks like**:
- 48px+ touch targets on all interactive elements
- Primary CTA in thumb zone (bottom half) or sticky bottom bar
- Safe area padding on fixed elements
- Scroll indicators for below-fold CTAs

---

### S6: RTL & Localization

**Applies when**: code serves Hebrew/Arabic UI or any RTL language.

**Anti-patterns**:
- **LTR-biased animations**: `translateX(30px)` for slide-in on an RTL page.
  Forward direction in RTL is LEFT, not RIGHT. Slide-in should come from
  `translateX(-30px)`, slide-out should go to `translateX(30px)`.
- **Hardcoded left/right**: `margin-left`, `padding-right`, `text-align: left`
  instead of logical properties (`margin-inline-start`, `text-align: start`).
- **Icon mirroring**: Directional icons (arrows, chevrons, progress indicators)
  that aren't mirrored for RTL. `←` means "forward" in RTL.
- **Mixed direction text**: LTR content (numbers, URLs, code) embedded in RTL
  without proper `dir="ltr"` isolation, causing jumbled rendering.
- **Reading flow breaks**: Layout that forces the eye to jump left-to-right
  in an RTL context (e.g., numbered steps arranged left-to-right).

**What good looks like**:
- `dir="rtl"` on html or container elements
- CSS logical properties throughout (`inline-start/end`, not `left/right`)
- Animations direction-aware (or using logical transforms)
- `dir="ltr"` on phone numbers, URLs, and code snippets
- Visual flow follows RTL reading direction (right to left)

---

### S7: Onboarding & First Impressions

**Applies when**: code is part of a signup flow, landing page, waitlist,
onboarding wizard, or first-time user experience.

**Anti-patterns**:
- **Too many fields upfront**: Asking for >3 pieces of information before
  the user gets any value. Progressive profiling (ask basics now, details later)
  converts better.
- **Value prop invisible at decision point**: The CTA asks users to act, but
  the value proposition (why should I?) isn't visible at the same scroll position.
- **No exit grace**: User starts a flow but can't easily exit without losing
  everything. "Come back later" should be possible.
- **Post-signup dead end**: After registering, the user sees a static "thanks"
  with no next action. Offer a tour, a preview, a share link — something.
- **Registration = commitment anxiety**: The word "register" or "sign up"
  creates friction. Softer language ("Reserve your spot", "Join the waitlist")
  reduces perceived commitment.

**What good looks like**:
- 2-3 fields max for initial action
- Value prop visible alongside or above CTA
- Post-action engagement path (tour, preview, share)
- Soft commitment language on CTAs
- Progressive profiling for additional data

---

### S8: Error & Edge Cases

**Applies when**: code handles user input, form validation, network requests,
or any flow that can fail.

**Anti-patterns**:
- **No double-submit prevention**: Button stays clickable during async
  operations. Users double-tap, causing duplicate submissions.
- **Validation only on submit**: Errors appear only after clicking submit,
  not inline as the user types. Late feedback causes frustration.
- **Generic error messages**: "Something went wrong" with no actionable
  guidance. Tell the user what happened and what to try next.
- **Empty states without guidance**: When a list/page is empty, showing
  nothing (or just whitespace) instead of a helpful message with a CTA.
- **No offline/slow-network handling**: On mobile in a supermarket, network
  can be spotty. No consideration for degraded connectivity.

**What good looks like**:
- Buttons disabled during async operations
- Inline validation with specific, helpful error messages
- Empty states with helpful text and suggested action
- Graceful degradation on slow/no network

---

## Analysis Process

For each applicable scenario:

1. **Trace the user journey**: Walk through the code as if you were the user.
   What do they see? What do they click? What feedback do they get?
2. **Identify decision points**: Where does the user decide to continue or
   leave? What information do they have at that moment?
3. **Check against anti-patterns**: For each relevant scenario, check the
   specific anti-patterns listed above.
4. **Assess severity**:
   - **BLOCK**: Will directly cause user drop-off or data loss (e.g., premature
     success signal, no double-submit prevention on payment)
   - **WARN**: Creates friction or confusion but user can still complete the
     flow (e.g., passive button language, missing progress indicator)
   - **INFO**: Minor UX improvement opportunity (e.g., could add autocomplete
     attribute, animation could be smoother)

---

## Output Format

```
## UX Engagement Review: [target]

**Applicable Scenarios**: S1 (Multi-Step), S4 (Trust), S7 (Onboarding) ...

### Findings

#### [BLOCK] S1: Premature completion signal
`file:line` — Success checkmark appears after step 1 of 3. Users will
think they're done and leave.
**Fix**: Move celebration to after the final step. Show "Almost done!"
with progress indicator during intermediate steps.

#### [WARN] S2: Passive CTA language
`file:line` — Button says "Done" (סיימתי) for the registration completion
action. This signals dismissal, not commitment.
**Fix**: Change to "Complete registration" (השלימו הרשמה) with primary
CTA styling.

#### [INFO] S5: Missing autocomplete attributes
`file:line` — Phone input lacks `autocomplete="tel"`. Adding it would
speed up mobile form filling.
**Fix**: Add `autocomplete="tel"` to the input element.

### Passing
- S3: Loading states present on all async operations
- S6: RTL direction correctly applied

**Verdict**: BLOCK ([N]) | WARN ([N]) | CLEAN
```

---

## Integration Notes

This skill is invoked by the `/develop` pipeline:
- **Phase 5 (Review)**: Mandatory for any change touching frontend files
  (`app/templates/**`, `app/static/**`, `*.html`, `*.css`, `*.js`)
- Runs alongside `/code-review` and `/security-review`
- BLOCK findings must be fixed before PR creation (same as code review violations)
- WARN findings should be addressed but can proceed with human approval

## Tool Integration (Optional Enhancements)

When available, this skill leverages external tools for deeper analysis:

- **Google Stitch MCP**: Renders target code as visual screenshots for
  pixel-level UX validation (layout, spacing, visual hierarchy).
  Requires: `stitch` in `.claude/mcp.json` with valid `STITCH_API_KEY`.

- **Gemini CLI**: Provides additional UX analysis using Gemini's visual
  understanding. Useful for catching visual anti-patterns that code-only
  review misses. Requires: `gemini` CLI installed with active Ultra plan.

- **Graceful degradation**: Both tools are optional. The skill works
  identically to its original behavior if neither is available. Tool
  failures or quota exhaustion are logged and silently skipped.
