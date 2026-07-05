---
name: social-media
description: "Generate platform-specific social media drafts for shipped features. Evaluates significance, asks human for platform/audience/language preferences, produces ready-to-copy bilingual content. Use when: /social-media, marketing content, social post, feature announcement, tweet, linkedin post, announce feature."
---

# Social Media Skill

Generate social media content for shipped features. Always human-driven —
asks what to post, where, for whom, and in what language before generating.

**CRITICAL**: Never fabricate feature capabilities. Ground all content in
actual PR, PRD, and code changes. No hyperbole ("revolutionary", "game-changing").

## Step 1: Gather Context

1. **Read the ticket**:
   - `gh issue view <{{TICKET_PREFIX}}-NNN>` for GitHub issue details
   - Linear MCP `get_issue` for additional context
   - Read PRD at `.dev-context/prds/{{TICKET_PREFIX}}-<NNN>.md` (if exists)

2. **Read the PR**:
   - `gh pr list --search "{{TICKET_PREFIX}}-<NNN>" --state merged` to find merged PR
   - `gh pr view <PR> --json title,body,additions,deletions,changedFiles`

3. **Synthesize**: What the feature does, who benefits, what's noteworthy.

---

## Step 2: Significance Check

Quick assessment — is this worth posting about?

| Criterion | 0 (Skip) | 1 (Low) | 2 (Medium) | 3 (High) |
|-----------|----------|---------|------------|----------|
| **User Visibility** | Internal/infra only | Minor UI tweak | Noticeable UX improvement | Major new capability |
| **Novelty** | Bug fix / maintenance | Incremental improvement | New feature | First-of-kind |
| **Audience Appeal** | Developers only | Niche users | Broad user base | Viral potential |
| **Brand Value** | No brand signal | Minor trust signal | Shows innovation | Thought leadership |

Present the score (0-12) with brief reasoning.

**If score <= 3**: Say so honestly and ask: "Score is low (X/12). Still want to generate content?"
**If score > 3**: Proceed to Step 3.

---

## Step 3: Ask the Human

Before generating anything, use `AskUserQuestion` to understand what the
human actually wants. Ask up to 3 questions in a single call:

### Question 1: Platforms
"Which platforms should we target?"
- Options (multiSelect: true):
  - "X (Twitter)" — short, punchy, developer community
  - "LinkedIn" — professional, thought leadership
  - "Medium/Blog" — deep dive, tutorial, technical
  - (Other — let them specify)

### Question 2: Audience & Tone
"Who is the audience and what tone?"
- Options:
  - "Developers — technical, show the how"
  - "End users — practical, show the value"
  - "Investors/professional — business impact, growth signal"
  - (Other — custom audience)

### Question 3: Language
"What language(s)?"
- Options:
  - "English only"
  - "Hebrew only"
  - "Bilingual (English + Hebrew)"
  - (Other — specify)

---

## Step 4: Generate Content

Based on human choices, generate ready-to-use drafts:

```markdown
## Content Plan: {{TICKET_PREFIX}}-NNN — <feature title>

### Score: X/12
### Platforms: <selected>
### Audience: <selected>
### Language: <selected>

---

### Platform: <name>

**Format**: Single post / Thread / Article
**Suggested Timing**: <day, time range>

**Draft**:
> <Full draft, ready to copy-paste, in chosen language>

**Hashtags**: #tag1 #tag2
**Visual Suggestion**: <what screenshot/image would work>
**Engagement Hook**: <question or CTA to drive replies>

---
```

For bilingual: generate separate drafts per language (not a translation —
adapt for each audience's cultural context).

---

## Step 5: Save (Optional)

After presenting drafts, ask:

"Save to Notion?"
- If yes and Notion MCP available: create page under "Social Media Content"
- If yes and Notion unavailable: output markdown, suggest manual copy
- If no: done

---

## Step 6: Animation (Optional)

After content is generated, offer:

"Want a social animation for this? (`/social-animation {{TICKET_PREFIX}}-NNN`)"

Only offer if:
- Score >= 5
- At least one visual platform selected (X, LinkedIn)

Do NOT auto-invoke. The human decides.

---

## Validation Rules

- **Never publish** content directly — only generate plans
- **Never fabricate** capabilities — ground in actual changes
- **Never skip** the human questions (Step 3) — always ask
- **No hyperbole** — authentic, practical tone
- **Max 2 platforms** per plan — quality over quantity
- Content reflects the product's voice — practical, helpful, human
