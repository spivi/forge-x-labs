# Animation Modes Reference

Mode-specific templates, CSS, and JS patterns for each animation style.

---

## Design Principles (Indie Hacker Viral Aesthetic)

1. **Clean and bold**: Large text, high contrast, generous whitespace
2. **One concept per frame**: Don't cram — each "scene" shows one thing
3. **Motion with purpose**: Every animation communicates, never decorates
4. **Brand colors as accents**: Primary green for highlights, not backgrounds
5. **No stock imagery**: Use CSS shapes, icons (Unicode/SVG), and typography
6. **Punchy transitions**: Use `cubic-bezier(0.16, 1, 0.3, 1)` for snappy easing

---

## Product Demo

Structure: Phone frame with animated interaction inside.

### Scene Flow

```
Scene 1 (0-1s): Phone frame slides in from bottom
Scene 2 (1-3s): Chat messages animate in (typing -> bubble appears)
Scene 3 (3-5s): Result/response appears with subtle highlight
Scene 4 (optional, 5-8s): Second interaction or list view
```

### Phone Frame CSS

```css
.phone-frame {
  width: 375px;
  height: 700px;
  border-radius: var(--frame-radius);
  border: 3px solid #E5E5E5;
  background: #F7F7F7;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0,0,0,0.15);
  position: relative;
}
```

### Chat Bubble CSS

```css
.bubble-user {
  background: #DCF8C6;
  border-radius: 12px 12px 0 12px;
  padding: 8px 14px;
  max-width: 260px;
  margin-left: auto;
  font-size: 15px;
}
.bubble-bot {
  background: white;
  border-radius: 12px 12px 12px 0;
  padding: 8px 14px;
  max-width: 260px;
  font-size: 15px;
}
```

---

## Motion Graphics

Structure: Kinetic typography + icon animations.

### Scene Flow

```
Scene 1 (0-2s): Feature name types in, large and bold
Scene 2 (2-4s): Key benefit animates in below (slide + fade)
Scene 3 (4-6s): Abstract visual (connecting lines, flowing dots, icon grid)
Scene 4 (6-8s): Logo watermark fades in
```

### Typography Animation CSS

```css
@keyframes typeIn {
  from { width: 0; }
  to { width: 100%; }
}
.type-text {
  overflow: hidden;
  white-space: nowrap;
  border-right: 3px solid var(--primary);
  animation: typeIn 1.5s steps(30) forwards,
             blink 0.7s step-end infinite;
}
```

---

## Data Storytelling

Structure: Numbers that move.

### Scene Flow

```
Scene 1 (0-1s): "Before" metric appears (e.g., "2.3s response time")
Scene 2 (1-3s): Counter animates down to "After" value (e.g., "0.4s")
Scene 3 (3-5s): Percentage improvement pulses (e.g., "-83%")
Scene 4 (5-7s): Comparison bar chart animates
```

### Counter Animation JS

```javascript
function animateCounter(el, start, end, duration, suffix = '') {
  const startTime = performance.now();
  function update(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
    const current = start + (end - start) * eased;
    el.textContent = current.toFixed(1) + suffix;
    if (progress < 1) requestAnimationFrame(update);
  }
  requestAnimationFrame(update);
}
```

---

## Watermark

Always include a subtle logo watermark in the bottom-right corner:

```css
.watermark {
  position: absolute;
  bottom: 24px;
  right: 24px;
  opacity: 0.3;
  width: 40px;
  height: 40px;
}
```

Use the SVG logo at `docs/app-icon.svg` — read the file and embed inline.
