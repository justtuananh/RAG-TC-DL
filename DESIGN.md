---
name: Trợ lý Kiểm định
description: Offline Vietnamese RAG lookup tool for metrology calibration procedures — "Kỹ Nghệ Xanh"
colors:
  # Primary brand — single accent (emerald green)
  brand: "#16A34A"
  brand-dark: "#15803D"
  brand-light: "#F0FDF4"
  brand-border: "#BBF7D0"
  brand-focus: "#DCFCE7"
  # Surfaces — 3-layer hierarchy
  canvas: "#F1F5F2"
  surface: "#FFFFFF"
  bot-zone: "#EDF8F2"
  bot-zone-border: "#C3DDD0"
  source-panel: "#EEF3F0"
  # Text — warm sage scale (grays lean toward brand, not cool blue-slate)
  ink-primary: "#111B16"
  ink-body: "#1D2D23"
  ink-secondary: "#3D5045"
  ink-muted: "#6B7C72"
  ink-faint: "#9AAFA3"
  # Structural
  border: "#DDE5E0"
  border-strong: "#C3D0C8"
  # Semantic states
  state-success-text: "#15803D"
  state-success-bg: "#F0FDF4"
  state-success-border: "#BBF7D0"
  state-success-dot: "#22C55E"
  state-warning-text: "#B45309"
  state-warning-bg: "#FFFBEB"
  state-warning-border: "#FDE68A"
  state-warning-dot: "#F59E0B"
  state-error-text: "#DC2626"
  state-error-bg: "#FEF2F2"
  state-error-border: "#FECACA"
  # Citation chips
  cite-bg: "#DCFCE7"
  cite-border: "#86EFAC"
  cite-text: "#15803D"
  # Tables (inside rendered markdown)
  table-header-bg: "#EEF2EE"
  table-even-row: "#F5FAF7"
typography:
  display:
    fontFamily: "'Be Vietnam Pro', system-ui, -apple-system, sans-serif"
    fontSize: "15.5px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.01em"
  body:
    fontFamily: "'Be Vietnam Pro', system-ui, -apple-system, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "normal"
  label:
    fontFamily: "'Be Vietnam Pro', system-ui, -apple-system, sans-serif"
    fontSize: "13.5px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0.01em"
  meta:
    fontFamily: "'Be Vietnam Pro', system-ui, -apple-system, sans-serif"
    fontSize: "11.5px"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "normal"
  doc:
    fontFamily: "'Lora', Georgia, serif"
    fontSize: "13.5px"
    fontWeight: 400
    lineHeight: 1.65
    letterSpacing: "normal"
rounded:
  xs: "6px"
  sm: "8px"
  md: "9px"
  lg: "11px"
  bubble: "16px"
  pill: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "15px"
  lg: "22px"
  xl: "30px"
components:
  button-primary:
    backgroundColor: "{colors.brand}"
    textColor: "#FFFFFF"
    rounded: "{rounded.lg}"
    height: "46px"
    padding: "0 18px"
  button-primary-hover:
    backgroundColor: "{colors.brand-dark}"
    textColor: "#FFFFFF"
    rounded: "{rounded.lg}"
    height: "46px"
    padding: "0 18px"
  button-ghost:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.brand-dark}"
    rounded: "{rounded.md}"
    height: "34px"
    padding: "0 14px"
  message-user:
    backgroundColor: "{colors.brand}"
    textColor: "#FFFFFF"
    rounded: "16px 16px 5px 16px"
    padding: "11px 15px"
  message-assistant:
    backgroundColor: "{colors.bot-zone}"
    textColor: "{colors.ink-body}"
    rounded: "16px 16px 16px 5px"
    padding: "13px 16px"
  citation-chip:
    backgroundColor: "{colors.cite-bg}"
    textColor: "{colors.cite-text}"
    rounded: "6px"
    height: "21px"
    padding: "0 5px"
  source-card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.xs}"
    padding: "26px 30px"
  input-text:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink-body}"
    rounded: "{rounded.lg}"
    height: "46px"
    padding: "0 15px"
---

# Design System: Trợ lý Kiểm định

## 1. Overview

**Creative North Star: "The Calibration Document"**

This interface is a precision tool, not a chat product. The metrologist arrives with an instrument and a procedure number; the interface must vanish into the lookup task within the first keystroke. The visual system is named *Kỹ Nghệ Xanh* (Engineering Green) — a discipline of structured density, a single emerald accent, and a text scale where every gray leans sage-warm toward the brand rather than cold blue-slate. That last move — warm grays instead of Tailwind's default slate — is the difference between a palette that feels coherent and one that reads as two unrelated systems bolted together.

The layout follows a 3-column professional workstation model: history sidebar | chat column | source document panel. Each panel has a distinct background level (canvas → white → tinted), so a user scanning at a glance always knows which zone they're in. Bot responses earn their own background color (`#EDF8F2`) — a light sage tint that says "AI response zone" without shouting. User messages sit in solid emerald. Chrome and panels are white. The outer canvas is barely-there sage.

This system explicitly rejects three anti-references (from PRODUCT.md):
- **Vietnamese government portal aesthetic** — no red/gold/green palette, no colored section headers, no heavy border decoration, no dense tables without breathing room
- **Generic ChatGPT clone** — no centered bubble UI, no floating input, no sparse consumer-grade layout
- **Heavy enterprise dashboards** — no navy-grey walls, no IBM-style data tables, no authoritative-but-wrong direction for a query-first tool

**Key Characteristics:**
- Single emerald accent used only on interactive elements and active states — ≤10% of visible surface
- Three-level surface hierarchy with distinct backgrounds for each panel zone
- Warm sage text scale (all grays biased toward brand hue, eliminating warm-surface / cool-text conflict)
- Bot response bubbles as a distinct visual zone (light sage-green, not neutral gray)
- Lora serif restricted exclusively to the source-document reading pane — all UI chrome stays in Be Vietnam Pro
- Formula fidelity is a trust signal; KaTeX blocks have full four-side borders, not left-side stripes

## 2. Colors: The Sage Accord

A restrained palette anchored by a single emerald green, with neutrals that lean warm-sage rather than cool-slate — they exist on the same hue axis as the brand so the palette reads as one coherent system.

### Primary

- **Emerald Active** (`#16A34A`): The sole non-neutral accent. Send button, active nav indicator stripe, brand logo background gradient, any interactive affordance that needs clear visibility. Its presence on ≤10% of the screen surface at any time is the point.
- **Emerald Deep** (`#15803D`): Hover state of Emerald Active, text-mode links, active row text in sidebar. Never used as a primary fill — reserved for state transitions downward.
- **Emerald Whisper** (`#F0FDF4`): Hover backgrounds on sample question buttons, status badge backgrounds, light fill on ghost-button hover. A tint, not a fill.
- **Sage Focus** (`#DCFCE7`): Input focus ring (3px spread), active conversation row background in sidebar. The "you are here" signal.
- **Bot Zone** (`#EDF8F2`): Background of AI response bubbles — the defining spatial signal that "this is an AI response", distinct from white chrome and the emerald user bubble.
- **Bot Zone Boundary** (`#C3DDD0`): Border of AI response bubbles. Slightly stronger than the general border to frame the AI zone clearly.

### Neutral

- **Near-Black Sage** (`#111B16`): Display headings, important labels. Near-black with a deliberate warm green bias — never pure `#000000`.
- **Body Sage** (`#1D2D23`): Message content, paragraph text in chat. Passes ≥7:1 on surface white.
- **Secondary Sage** (`#3D5045`): Metadata labels, sidebar section headers, panel titles, table headers. Passes ≥4.5:1 on white.
- **Muted Sage** (`#6B7C72`): Timestamps, helper text, captions. Passes ≥4.5:1 on white; do not use for body text.
- **Faint Sage** (`#9AAFA3`): Placeholder text in inputs, icon tints for muted icon states. **Do not use for any readable text — fails AA on white at small sizes.** Restricted to decorative icon tinting and scrollbar thumb.
- **Canvas** (`#F1F5F2`): Outer app background — the lowest surface layer, barely sage.
- **Source Panel** (`#EEF3F0`): Source document panel background — one step deeper than canvas, distinct from sidebar white.
- **Boundary** (`#DDE5E0`): All structural borders — sage-warm so they harmonize with both green and neutral surfaces. Replaces cold slate.
- **Boundary Strong** (`#C3D0C8`): Scrollbar thumb, stronger internal separators.

### Semantic (confined to state use only)

State colors carry meaning exclusively. Using them for decoration is a trust violation in a precision tool.

- **Success** (text `#15803D` / bg `#F0FDF4` / border `#BBF7D0` / dot `#22C55E`): Online status indicator, process-step completion checks.
- **Warning** (text `#B45309` / bg `#FFFBEB` / border `#FDE68A` / dot `#F59E0B`): LLM connection checking state. The amber dot also appears on pinned conversations (the same warning hue signals "held for attention").
- **Error** (text `#DC2626` / bg `#FEF2F2` / border `#FECACA`): Failed API calls, error message bubbles.

**The One Accent Rule.** Emerald is the only non-neutral color. Its rarity is the signal. A second decorative accent — teal, indigo, orange, amber used as fill — anywhere in the interface is prohibited, not a design option. Amber appears only as a semantic warning indicator.

**The Warm Gray Rule.** Every gray in this system must sit on the warm-sage hue axis (toward brand green). The Tailwind `slate-` scale (which is blue-gray) is prohibited for new surface or text colors — it creates a warm-surface / cool-text split that makes the palette read as two disconnected systems.

## 3. Typography

**Display / UI Font:** Be Vietnam Pro (400, 500, 600, 700 weights; subsets: Vietnamese, Latin)
**Document Reading Font:** Lora (400 weight; subsets: Vietnamese, Latin)

**Character:** Be Vietnam Pro is a Vietnamese-origin geometric humanist sans — it earns its place by being native to the script domain, not just a "safe" choice. At 14px with 1.6 leading, it reads cleanly at the densities a workstation requires. Lora appears only in the source-document reading panel, where its serif rhythm slows the eye down for careful verification of regulatory text.

### Hierarchy

- **Display** (700, 15–16px, 1.2 leading): App title, panel section headers. One instance each. `text-wrap: balance`.
- **Label** (600, 13.5px, 1.4 leading, 0.01em tracking): Button text, navigation tabs, sidebar group headings, sub-panel titles. The workstation's action register.
- **Body** (400–500, 14px, 1.55–1.65 leading): Chat message content, source document prose in Be Vietnam Pro chrome, example question buttons. Max ~65ch line length in prose contexts.
- **Meta** (500, 11–12px, 1.4 leading): Timestamps, section paths, status labels, citation chip numbers. The high-density information layer.
- **Document** (Lora 400, 13.5px, 1.65 leading): Source document viewer panel (`.md-doc`) only. Headings inside Lora blocks revert to Be Vietnam Pro 700 at 14px so structural hierarchy is visually distinct from prose.

**The Lora Containment Rule.** Lora is permitted in exactly one place: the `.md-doc` source reading panel. In every other UI surface — sidebar, header, chat bubbles, buttons, status chips — only Be Vietnam Pro. Mixing serif into chrome degrades the "technical instrument" character and makes the app feel decorative.

**The Scale Floor Rule.** Nothing below 11px. Source document annotations at 10px currently violate this; 11px is the absolute floor. The information benefit never exceeds the legibility cost below 11px.

## 4. Elevation

Flat by default. The calibration workstation recedes; the content advances. No element rests at a raised elevation; shadows appear only as structural spatial signals or hover responses, never as decoration.

### Shadow Vocabulary

- **Structural Separation** (`0 1px 2px rgba(15,23,42,.04)`): Applied on the app header and subtle structural cards at rest. Barely perceptible — a whisper that the header is above the content layer, not a decorative flourish.
- **Source Card** (`0 6px 22px -10px rgba(15,23,42,.16)`): Source document page card in the reading panel. The document "page" sits above the tinted panel background; this controlled lift is the one place depth is used structurally. No more than this.
- **Process Step Card** (`0 6px 18px -10px rgba(15,23,42,.18)`): The thinking card shown while the pipeline runs. Same spatial logic as source card — it sits above the chat surface.

**The Flat-at-Rest Rule.** Every surface ships flat or at Structural Separation shadow. The source-card lift appears only on the document page card inside the source panel and the process step card — nowhere else. An element resting at elevated shadow implies permanence; restrict lift to genuine elevation of page-like content.

**The No-Stripe Rule.** `border-left` or `border-right` greater than 1px as a colored accent on cards, callouts, formula blocks, or list items is absolutely prohibited. Formula blocks use a full four-side border (`1px solid #DDE5E0`) plus background tint. A side stripe reads as a design shortcut; a full enclosure reads as a deliberate container.

## 5. Components

### Buttons

Tactile and precise — the send button is the single primary action; it must be instantly identifiable. No outer glows.

- **Shape:** 9–11px radius. Primary is 11px; ghost is 9px; icon-only is 11px.
- **Primary (Send, Confirm):** Emerald Active fill (`#16A34A`), white text, `height: 46px`, `padding: 0 18px`. Hover: Emerald Deep (`#15803D`). Active: `-1px translateY` (tactile downpress). No `box-shadow` glow on hover.
- **Ghost / Outline:** White bg, `1px solid #16A34A`, Emerald Deep text. Hover: Emerald Whisper fill. Used for secondary actions: "Hội thoại mới", "Mở tài liệu gốc".
- **Icon Action (28px):** Transparent bg, Muted Sage icon. Context-aware hover: `#F0FDF4` for safe actions, `#FEF2F2` for destructive. Radius 7px.
- **Disabled:** `#CBD5E1` fill (cold neutral for clearly inactive), white icon.

### Chat Bubbles

The central interaction surface. Visual language: green = user, sage = AI, white = chrome.

- **User Bubble:** Emerald Active fill (`#16A34A`), white text, `border-radius: 16px 16px 5px 16px` (sharp bottom-right signals direction). Shadow `0 2px 5px rgba(22,163,74,.22)`. Max 80% of column width. Right-aligned.
- **Assistant Bubble:** Bot Zone bg (`#EDF8F2`), `1px solid #C3DDD0` border, `border-radius: 16px 16px 16px 5px` (sharp bottom-left). Light sage-green deliberately distinct from both white chrome and emerald user bubble.
- **Bot Avatar:** 32px circle, Sage Focus bg (`#DCFCE7`) + `1px solid #BBF7D0`, brand icon at `#16A34A`. Sits at left of each AI turn.
- **Error State:** Error bg (`#FEF2F2`), error border (`#FECACA`), error text (`#DC2626`). Same bubble shape.

### Citation Chips `[n]`

Inline citation buttons embedded in assistant markdown. Designed to be scannable at reading speed.

- **Style:** 21px height, `#DCFCE7` background, `1px solid #86EFAC` border, `#15803D` text, 6px radius. Inline-flex at -3px vertical offset to sit cleanly in text lines. Bold number.
- **Hover:** Emerald Active fill, white text, matching border.
- **Usage:** Appear both inline in answer text (replacing `[n]` markers) and as a source-chip row below the answer bubble.

### Source Document Card

The "page" object inside the source panel — meant to evoke a real document page.

- **Shape:** 6px radius (gently curved, not bubbly — this is a document)
- **Surface:** White bg, `1px solid #DDE5E0` border, Source Card elevation shadow
- **Internal padding:** 26px top/bottom, 30px left/right — generous enough to breathe, tight enough for density
- **Excerpt highlight:** `#F0FDF4` background, `2px solid #16A34A` border, 8px radius. The label "Đoạn trả lời" tag sits at `-9px` on the top-right in Emerald Active.
- **Section divider (dashed):** `1px dashed #DDE5E0` between metadata header and body text

### Inputs / Fields

- **Style:** White bg, `1px solid #CBD5E1` border (slightly stronger than general border for visibility), 11px radius.
- **Focus:** Border shifts to `#16A34A`; `box-shadow: 0 0 0 3px #DCFCE7`. No outline.
- **Placeholder:** `#6B7C72` (Muted Sage) — passes 4.5:1 on white; never Ink Faint.
- **Autosize textarea:** Min 46px, max 130px, `resize: none`.

### Navigation Tabs (Header)

- **At rest:** Transparent bg, `#4E6457` text, 700 weight
- **Active:** Emerald Deep text (`#15803D`), `3px solid #16A34A` bottom indicator stripe (3px only at bottom of nav, not a side accent)
- **Hover background:** `#F1F5F2` (canvas color — subtle, not a state change)

### Signature Component: Process Steps

The thinking card shown while the retrieval pipeline runs.

- White card, `1px solid #DDE5E0`, `border-radius: 16px 16px 16px 5px` (matches bot bubble), shadow elevated above chat bg
- Spinning border-top loader: `2px solid #BBF7D0` with `borderTopColor: #16A34A`
- Completed step: filled Emerald Active circle with white check; active step: spinner; future steps: hidden until reached

## 6. Do's and Don'ts

### Do:

- **Do** use Emerald Active (`#16A34A`) on ≤10% of any screen. Its rarity is what makes it a signal. Send buttons, active indicators, focus rings, and the bot avatar are the canonical uses.
- **Do** give formula blocks full four-side borders (`1px solid #DDE5E0`) plus a background tint (`#F8FAFC` in source docs, white in chat). Formula distinction comes from enclosure, not a side stripe.
- **Do** set all gray text in this system to the warm-sage scale (`#3D5045`, `#6B7C72`). Do not use Tailwind `slate-500` (`#64748B`) — it's blue-gray and conflicts with the sage surfaces.
- **Do** keep Lora serif to the `.md-doc` source reading pane only. All UI chrome — labels, titles, buttons, error messages — uses Be Vietnam Pro.
- **Do** give bot response bubbles the `#EDF8F2` background and `#C3DDD0` border. This is the spatial marker that tells users "this came from the AI"; it must be consistent.
- **Do** respect `prefers-reduced-motion: reduce` — all CSS keyframe animations (`fadeUp`, `hlGlow`, `pulseDot`, `spin`) must have a static fallback (`animation: none`).
- **Do** apply `WCAG AA` contrast to all text. Body text at `#1D2D23` on `#FFFFFF` gives ≥11:1. Secondary text `#3D5045` on white gives ≥7:1. `#6B7C72` on white gives ≈4.7:1 — it passes AA but must not be used for body text in dense paragraphs.

### Don't:

- **Don't** use cool Tailwind slate grays (`slate-500` `#64748B`, `slate-700` `#334155`) for any new surface, border, or text color. They introduce a blue-gray temperature that fights the warm sage palette.
- **Don't** introduce a second decorative accent color. No teal, indigo, purple, or blue anywhere in the UI chrome. Amber is permitted only for the semantic warning state and pin indicator.
- **Don't** use `border-left` or `border-right` greater than 1px as a colored accent stripe on any card, callout, or formula block. This is absolutely prohibited — rewrite with a tinted background and full border.
- **Don't** use `background-clip: text` with gradient for headings. Emphasis is weight or size, never gradient text.
- **Don't** make this look like a Vietnamese government portal: no colored section headers, no red/gold/green decorative palette, no full-width horizontal rule dividers used as page chrome.
- **Don't** make this look like a generic consumer chat clone: no centered empty-state hero with a large illustration, no floating input that's the only content, no sparse consumer padding.
- **Don't** make this look like heavy enterprise dashboards (IBM/SAP): no navy-grey panel walls, no data tables as the primary UI pattern, no hierarchical breadcrumb navigation for procedure selection.
- **Don't** use `#9AAFA3` (Ink Faint) for any text that must be read. It fails WCAG AA on white at 14px. Restrict to icon tinting and scrollbar thumb.
- **Don't** use `#000000` pure black. Near-Black Sage (`#111B16`) is the darkest text value — it's still dark but positioned on the same hue axis as the brand.
- **Don't** add extra fonts. Be Vietnam Pro and Lora are self-hosted (offline). Any CDN-linked webfont defeats the offline-first constraint.
