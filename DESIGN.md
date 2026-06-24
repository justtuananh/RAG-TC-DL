---
name: QTKĐ Chatbot
description: Offline Vietnamese RAG lookup tool for metrology calibration procedure standards
colors:
  instrument-blue: "#2563EB"
  instrument-blue-deep: "#1D4ED8"
  instrument-blue-light: "#DBEAFE"
  instrument-blue-subtle: "#EFF6FF"
  instrument-blue-text: "#1E40AF"
  surface-base: "#F8FAFC"
  surface-elevated: "#FFFFFF"
  surface-divider: "#F1F5F9"
  ink-primary: "#0F172A"
  ink-secondary: "#1E293B"
  ink-tertiary: "#64748B"
  ink-muted: "#94A3B8"
  border-default: "#E2E8F0"
  border-subtle: "#CBD5E1"
  state-success-bg: "#F0FDF4"
  state-success-text: "#166534"
  state-success-indicator: "#22C55E"
  state-error-bg: "#FEF2F2"
  state-error-border: "#FECACA"
  state-error-text: "#B91C1C"
typography:
  title:
    fontFamily: "system-ui, -apple-system, sans-serif"
    fontSize: "20px"
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: "normal"
  body:
    fontFamily: "system-ui, -apple-system, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "normal"
  label:
    fontFamily: "system-ui, -apple-system, sans-serif"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "normal"
  meta:
    fontFamily: "system-ui, -apple-system, sans-serif"
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: "normal"
  mono:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: "11px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "normal"
rounded:
  xs: "4px"
  sm: "8px"
  md: "12px"
  bubble: "16px"
  pill: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.instrument-blue}"
    textColor: "{colors.surface-elevated}"
    rounded: "{rounded.md}"
    size: "44px"
  button-primary-hover:
    backgroundColor: "{colors.instrument-blue-deep}"
    textColor: "{colors.surface-elevated}"
    rounded: "{rounded.md}"
    size: "44px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink-tertiary}"
    rounded: "{rounded.sm}"
    padding: "6px 12px"
  button-ghost-hover:
    backgroundColor: "{colors.state-error-bg}"
    textColor: "{colors.state-error-text}"
    rounded: "{rounded.sm}"
    padding: "6px 12px"
  input-text:
    backgroundColor: "{colors.surface-elevated}"
    textColor: "{colors.ink-secondary}"
    rounded: "{rounded.md}"
    padding: "12px 16px"
  source-chip:
    backgroundColor: "{colors.instrument-blue-subtle}"
    textColor: "{colors.instrument-blue-text}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
  source-card:
    backgroundColor: "{colors.surface-elevated}"
    textColor: "{colors.ink-primary}"
    rounded: "{rounded.md}"
    padding: "14px"
  message-user:
    backgroundColor: "{colors.instrument-blue}"
    textColor: "{colors.surface-elevated}"
    rounded: "{rounded.bubble}"
    padding: "12px 16px"
  message-assistant:
    backgroundColor: "{colors.surface-elevated}"
    textColor: "{colors.ink-secondary}"
    rounded: "{rounded.bubble}"
    padding: "12px 16px"
---

# Design System: QTKĐ Chatbot

## 1. Overview

**Creative North Star: "The Calibration Bench"**

This is a metrologist's workstation, not a chat product. The Calibration Bench means a technician's workspace where every element occupies a known position, serves a measurement function, and nothing decorates for its own sake. A user arrives with an instrument, a procedure number, and a question — the interface must disappear into that task the moment they start typing.

The visual system is restrained by discipline, not laziness. Slate neutrals hold the field. Instrument Blue appears exactly where it belongs — on primary actions, focus states, and navigational anchors — and nowhere else. Formulas are first-class content: rendered with precision, visually distinguished by a full container border (never a side stripe), and never recomputed or approximated downstream. The right-panel source citations exist to be cross-checked against the source document; their layout must make that act fast.

This system rejects three wrong registers by name. The Vietnamese government-portal aesthetic (colored section headers, small crowded type, borders as decoration, red/gold/green palette) is the primary anti-reference — the tool must read nothing like the portals that index the same QTKĐ documents it cites. Generic chat-clone minimalism (centered bubble UI, padded whitespace, consumer curves) is the second — this is a professional lookup tool, not a consumer assistant. Enterprise-dashboard weight (navy-grey walls, data tables without hierarchy, heavy side navs) is the third.

**Key Characteristics:**
- System font throughout — no custom typefaces competing with technical content
- Two surface levels exactly (page bg, elevated panel/card) — no deeper layering
- Instrument Blue on ≤10% of visible surface at any time — action and state only, never fill
- Formulas distinguished by full four-side border + background tint — never by a left-side stripe
- Monospace for calibration IDs and file stems — code-legibility is functional, not decorative
- Flat at rest; minimal lift on hover — the interface recedes

## 2. Colors: The Precision Field

A restrained palette anchored by one committed color. Instrument Blue is the sole non-neutral accent; every other color either belongs to the neutral field or carries an explicit semantic role (success, error, warning). There is no secondary accent.

### Primary
- **Instrument Blue** (`#2563EB`): The one committed color. Send button, focus rings, active link text in source panels, selected-state indicators. Its presence signals "interactive or important." Never used as a background fill for containers, panels, or cards.
- **Instrument Blue Deep** (`#1D4ED8`): Hover state of Instrument Blue only. Not used independently.
- **Instrument Blue Light** (`#DBEAFE`): Focus halos and file-badge backgrounds. A tint layer, never a fill. Signals "this element has focus" when used as a ring.
- **Instrument Blue Subtle** (`#EFF6FF`): Status bar background, hover surfaces for example buttons, inline code background. Near-invisible; carries state without volume.
- **Instrument Blue Text** (`#1E40AF`): Badge label text on Instrument Blue Light backgrounds. Passes 5.2:1 contrast on `#DBEAFE`.

### Neutral
- **Lab White** (`#FFFFFF`): Chat panel, header, source cards, message bubbles. The content layer — everything a user reads lives on Lab White.
- **Surface Base** (`#F8FAFC`): Page background and source-panel tray background. A fractional blue tint (barely perceptible) that recedes behind white panels.
- **Surface Divider** (`#F1F5F9`): Internal separators inside cards and between source sections. A whisper of distinction, not a border.
- **Ink Primary** (`#0F172A`): App title, primary headings. Near-black.
- **Ink Secondary** (`#1E293B`): Body text, message content. The default reading color.
- **Ink Tertiary** (`#64748B`): Secondary labels, panel header titles, section path breadcrumbs. Passes 4.5:1 on Lab White.
- **Ink Muted** (`#94A3B8`): ⚠️ A11y gap — approximately 2.7:1 on Lab White, below WCAG AA for 14px text. Restricted to purely decorative or non-readable elements: scrollbar thumb, visual timing markers. Never for text that must be read.
- **Border Default** (`#E2E8F0`): Container borders, card borders, input borders, dividers.
- **Border Subtle** (`#CBD5E1`): Scrollbar thumb, subtler internal dividers.

### Tertiary (Semantic — confined to state use only)
- **Status Green** (`#22C55E` / bg `#F0FDF4` / text `#166534`): Online indicator only.
- **Error Red** (bg `#FEF2F2` / border `#FECACA` / text `#B91C1C`): Error message states on assistant bubbles and API failure banners.

### Named Rules

**The One Instrument Rule.** Instrument Blue is the only non-neutral, non-semantic color permitted. It appears on ≤10% of visible surface at any time. A second accent — teal, orange, purple, an extra shade of green — anywhere in the interface is a violation of this rule, not a design decision.

**The Semantic Confinement Rule.** Error Red, Success Green, and Warning Amber appear only when conveying their explicit semantic state. Using red for navigational labels, green for decorative badges, or amber for neutral annotations is prohibited. The SourceCard section path currently using `text-red-500 italic` is a known violation to fix — it reads as an error before the user processes any text.

## 3. Typography

**Font:** system-ui, -apple-system, sans-serif (system native throughout)
**Mono Font:** ui-monospace, SFMono-Regular, Menlo, monospace (calibration IDs and file stems only)

**Character:** The system font is a deliberate choice, not a budget constraint. On a calibration workstation, the interface should be invisible; native text lets Vietnamese technical content dominate. Monospace for document identifiers (QTKD_1.061, QTKD_1.063) makes codes scannable in dense source panels — functional distinction, not decoration.

### Hierarchy

- **Title** (700, 20px, 1.25 line-height): App header only. One instance per page. `text-wrap: balance`.
- **Body** (400, 14px, 1.6 line-height): Message content, source panel prose, example button text. The reading voice.
- **Label** (500, 12px, 1.4 line-height): Panel header titles ("Tài liệu nguồn"), button text on ghost buttons, section headings in source prose.
- **Meta** (400, 11px, 1.4 line-height): Rerank scores, section path breadcrumbs, kind annotations (¶ paragraph, ∑ formula). The high-density information layer.
- **Mono** (600, 11px, 1.4 line-height): Calibration document IDs and file stems in badges and chips. Bold weight makes codes scannable in tight badge contexts.

### Named Rules

**The Scale Floor Rule.** Nothing below 10px. Source cards currently use 10px for kind annotations — this is the absolute minimum. Every new metadata annotation starts at 11px (Meta role).

**The Monospace Discipline Rule.** Monospace is reserved for calibration document identifiers, file stems, and inline code only. Never for prose, labels, or error messages — its specificity is the point.

## 4. Elevation

Flat by default. The Calibration Bench has no lifted surfaces at rest; depth appears only as a response to interaction. Two shadow steps exist — nothing beyond them.

### Shadow Vocabulary

- **Ambient Low** (`0 1px 2px 0 rgba(0,0,0,0.05)`): Applied at rest on the header, message bubbles, and source cards. Barely perceptible — structural layer separation, not decorative depth.
- **Interactive Lift** (`0 4px 6px -1px rgba(0,0,0,0.10), 0 2px 4px -2px rgba(0,0,0,0.10)`): Source cards on hover only. One-step elevation that communicates "this is expandable." Resets to Ambient Low on mouse-leave.

No colored shadows. No glow effects. No shadow-lg or deeper.

### Named Rules

**The Flat-at-Rest Rule.** Every surface ships at Ambient Low or flat. Interactive Lift appears only in direct response to user hover or focus — not at rest, not by default, not as a ranking signal. An element resting at Interactive Lift elevation implies it is perpetually active, which is false.

## 5. Components

### Buttons

- **Shape:** 12px radius (primary icon-only button); 8px radius (ghost text utility).
- **Primary (Send):** 44×44px square, Instrument Blue fill, white SVG icon, no border. Hover: Instrument Blue Deep. Focus: 3px ring in Instrument Blue Subtle. Disabled: `#E2E8F0` bg, cursor not-allowed. `transition: background-color 150ms ease`.
- **Ghost / Utility (Clear):** Transparent bg, Ink Tertiary text, 1px Border Default border at rest. Hover: Error Red bg (`#FEF2F2`), error text — this button is destructive, the hover color confirms it. Focus: 2px Instrument Blue Light outline. `transition: color 150ms ease, background-color 150ms ease`.

### Inputs / Fields

- **Style:** Lab White bg, 1px Border Default border, 12px radius. Body text (14px, Ink Secondary). Placeholder: Ink Tertiary (`#64748B` — not Ink Muted; placeholder text must pass AA).
- **Focus:** Border shifts to Instrument Blue Light (`#DBEAFE`); 3px ring in Instrument Blue Subtle. `outline: none`.
- **Disabled:** 0.6 opacity, cursor not-allowed.
- **Sizing:** Min-height 44px; max-height 128px auto-expanding textarea. `resize: none`.

### Cards / Containers

- **Source Card:** Lab White bg, 1px Border Default border at rest, 12px radius, Ambient Low shadow. Hover: border shifts to `#93C5FD` (blue-300), Interactive Lift shadow. `transition: border-color 150ms ease, box-shadow 150ms ease`. Internal: 14px padding, 8–10px between rows. No nested cards.
- **Status Bar (streaming):** Instrument Blue Subtle bg, 1px Instrument Blue Light border, 12px radius, 8–12px padding. Ephemeral — disappears on stream completion.

### Message Bubbles

- **User:** 16px radius with top-right corner snipped to 6px (directional tail), Instrument Blue fill, white text. Right-aligned, max 75% width. Ambient Low shadow.
- **Assistant:** 16px radius with top-left corner snipped to 6px, Lab White bg, 1px Border Default border, Ink Secondary text. Left-aligned with 28×28px avatar at left. Max 85% width. Ambient Low shadow. Source citation chips below answer text on completion, separated by a 1px Surface Divider.
- **Avatar:** 28×28px circle, Instrument Blue Subtle bg, 1px Instrument Blue Light border, 📐 emoji center-aligned.
- **Typing indicator:** Three Ink Muted dots (6×6px), staggered 0.2s, 1.2s cycle. `prefers-reduced-motion` override: instant opacity pulse, no translation.
- **Error state:** Error Red bg, Error Red border, error text color.

### Formula Blocks (.katex-display)

The most critical display element in the entire system. Formulas earn their container through completeness, not an accent stripe.

- **Container:** Surface Base bg (`#F8FAFC`), 1px Border Default on **all four sides** (`border: 1px solid #E2E8F0`), 8px radius, 14px vertical / 18px horizontal padding. Centered. Horizontal scroll on overflow.
- **Font:** 1.1em display math; 1.05em inline math.
- **On colored backgrounds** (source cards if teal or colored bg variant is used): bg `rgba(255,255,255,0.12)`, border `rgba(255,255,255,0.25)` all sides, text white.

### Navigation (Header)

- **Height:** 64px, Lab White bg, 1px Border Default bottom, Ambient Low shadow. z-index: 10.
- **Left:** Title (Title role, 20px bold, Ink Primary) + subtitle (Meta role, 12px, Ink Tertiary). No logo — the title carries the identity in a single-product tool.
- **Right:** Online badge (pill, Status Green palette), Clear button (ghost destructive, appears only when `hasMessages`).

### Signature Component — Source Citation Chip

Inline citation reference inside assistant message bubbles. Citation number `[n]` + file stem in monospace.

- **Style:** Instrument Blue Subtle bg, 1px Instrument Blue Light border, pill radius, 12px label (Ink for `[n]`), 10px monospace for the file stem.
- **No hover state** in current implementation — cosmetic/navigational reference only.

## 6. Do's and Don'ts

### Do:
- **Do** use Instrument Blue (`#2563EB`) exclusively on primary interactive elements: the send button, focus rings, active link text, selected-state indicators.
- **Do** give formula blocks a full four-side border (`border: 1px solid #E2E8F0`). The formula container earns its distinction from a complete enclosure, not a left-side stripe.
- **Do** set placeholder and hint text to Ink Tertiary (`#64748B`) or darker. This is the minimum value that clears WCAG 2.1 AA (4.5:1) on Lab White at 14px.
- **Do** keep section path text in source cards at Ink Tertiary (`#64748B`) — it is navigational breadcrumb content, not a warning or error state.
- **Do** apply `@media (prefers-reduced-motion: reduce)` overrides for all animations: fade-up on messages (instant opacity), typing dots (instant opacity pulse, no translateY), online pulse (static dot).
- **Do** use Monospace role (11px 600-weight, `ui-monospace`) for all calibration document identifiers and file stems.
- **Do** keep shadows at Ambient Low at rest; Interactive Lift applies on hover/focus and resets on mouse-leave.

### Don't:
- **Don't** use `border-left` or `border-right` greater than 1px as a colored accent on any element — formula blocks, callout boxes, cards, list items. Prohibited absolutely. The current `border-left: 3px solid #3b82f6` on `.katex-display` is a violation to fix.
- **Don't** use `text-red-500` or any error-state color for non-error content. The SourceCard section path is currently `text-red-500 italic` — this communicates error before the user reads the text. Fix to Ink Tertiary.
- **Don't** use Ink Muted (`#94A3B8`) for any text that must be read. It fails WCAG AA at 14px on Lab White (~2.7:1). Scrollbar thumbs and visual decoration only.
- **Don't** use gradient text (`background-clip: text` with a gradient). One solid color; emphasis through weight or size.
- **Don't** use Instrument Blue as a background fill for panels, containers, or cards. It appears on ≤10% of visible surface; a blue panel violates the One Instrument Rule.
- **Don't** introduce a second accent color anywhere in the interface — no teal headers, no orange badges, no green action buttons. Semantic state colors are confined to their roles.
- **Don't** make this look like a Vietnamese government portal: no colored section headers, no red/gold/green palette, no full-width decorative borders, no font sizes below 11px.
- **Don't** make this look like a generic consumer chat clone: no hero-centered empty states, no bubbly consumer curves as the dominant radius, no heavy marketing copy in UI chrome.
- **Don't** use numbered section markers (`01 /`) or tiny uppercase tracked eyebrows as scaffold for new screens.
- **Don't** nest cards. Source cards contain text and chips; they do not contain child cards.
