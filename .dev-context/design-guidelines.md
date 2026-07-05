# Design Guidelines

> Anti-AI-aesthetic principles for building distinctive, human-feeling interfaces.
> These are binding constraints for any frontend work.

## Philosophy

Build interfaces that feel crafted, not generated. Avoid the "AI look" --
center-aligned hero sections, emoji-heavy headers, gradient backgrounds,
uniform card grids, and generic color schemes.

## Anti-AI Checklist

Every frontend PR must pass this checklist:

| # | Constraint | Rationale |
|---|-----------|-----------|
| 1 | No center-aligned blocks (except modals/dialogs) | AI defaults to centered layouts |
| 2 | No emoji in headers or navigation | AI overuses emoji for visual appeal |
| 3 | No uniform card styling with box-shadows everywhere | AI defaults to Material-like cards |
| 4 | No gradient backgrounds | AI loves gradients; flat colors feel more intentional |
| 5 | Max 5 type size stops | AI tends to create too many font sizes |
| 6 | No generic "AI app" color scheme (blue/purple gradients) | Be distinctive |
| 7 | No rounded corners > 16px on containers | Overly rounded = generic |
| 8 | No decorative illustrations that don't serve a function | AI adds filler art |

## Typography

- Use a single font family (max 2)
- Establish clear hierarchy: heading, subheading, body, caption, label
- Use weight (not just size) to create hierarchy

## Colors

- Define a palette of 6-8 colors maximum
- Use CSS custom properties for all colors
- Test with both light and dark backgrounds

## Interactions

- Touch targets: minimum 44px (48px recommended for mobile)
- Transitions: 150-300ms, ease-out
- Loading states: skeleton screens over spinners
- Error states: inline, contextual, never modal

## Mobile First

- Design for smallest viewport first
- Use CSS Grid / Flexbox for responsive layouts
- Test thumb-reachability zones for primary actions
