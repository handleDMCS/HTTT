---
name: anthropic-style
description: A warm, editorial design system inspired by Anthropic.com.
---

## When to use

**IMPORTANT:** Always apply this skill when it comes to UI code in this project, this is my favourite design system

# Anthropic Style

Implement UIs following Anthropic's visual identity: warm, intellectual, high-end editorial.

## Palette
| Token | Value | Use |
|---|---|---|
| Background | `#F7F2F0` | Page base |
| Surface | `#FFFFFF` | Cards, inputs |
| Text primary | `#1D1D19` | Headings, body |
| Accent | `#D97757` | CTAs, highlights |
| Border | `#E5DDD9` | Cards, inputs |

## Typography
- **Headings**: `Young Serif` (Google Fonts) — literary, editorial weight
- **Body / UI**: `Source Sans Pro` — clean, readable
- Scale: generous. Let type breathe.

## Tailwind v4
Use CSS-first config — no `tailwind.config.js`:

```css
@import "tailwindcss";

@theme {
  --color-background: #F7F2F0;
  --color-surface: #FFFFFF;
  --color-text: #1D1D19;
  --color-accent: #D97757;
  --color-border: #E5DDD9;

  --font-heading: 'Young Serif', Georgia, serif;
  --font-body: 'Source Sans Pro', sans-serif;

  --radius-btn: 4px;
}
```

Apply via utilities: `bg-background`, `text-accent`, `font-heading`, `rounded-[4px]`.  
For components not covered by utilities, drop into `@layer components` or use arbitrary values.

## Components

**Nav**: Single top bar, text links only, no icons, no heavy borders.

**Buttons**:
- Primary — `bg-accent text-white rounded-[4px] px-5 py-2`
- Outline — `border border-text text-text rounded-[4px] px-5 py-2`
- No shadows. No gradients.

**Cards**: `bg-surface border border-border rounded-sm p-6` — border, not elevation.

**Inputs**: `bg-surface border border-border rounded-[4px] px-4 py-2 focus:border-accent` — no heavy shadows.

## Rules
- Spacious layouts. Generous whitespace. Readability first.
- No gradients, no drop shadows, no decorative flourishes.
- Clear information hierarchy over visual complexity.
- One accent color used sparingly — don't dilute it.