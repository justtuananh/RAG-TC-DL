# Product

## Register

product

## Users

Vietnamese calibration and metrology technicians working at measurement labs or standards bodies. Users arrive during active calibration work — they have an instrument in front of them and need to look up the correct procedure, tolerance limit, or formula from a QTKĐ document quickly. They are technically fluent, expect precise language, and are not here to browse. The interface is a professional tool, not a consumer product.

## Product Purpose

QTKĐ Chatbot is an offline RAG lookup tool for Vietnamese metrology calibration procedures. Users ask in Vietnamese, the system finds the exact passage from the relevant QTKĐ document, and returns it verbatim — with formulas rendered in LaTeX and source citations. The tool is lookup-only and never recalculates: the answer must match the source document precisely, not a model's interpretation of it. Everything runs fully offline on a single machine.

## Brand Personality

Calibrated. Precise. Immediate.

The tool should feel like a well-maintained reference instrument — exact, dependable, zero ornamentation. Every element earns its place by serving the query.

## Anti-references

- Vietnamese government portal aesthetic (red/gold/green, heavy borders, dense tables with no breathing room, outdated form controls) — this is the strongest anti-reference
- Generic ChatGPT clone (centered bubble UI, floating input, sparse context) — too consumer, not dense enough for technical lookup
- Heavy enterprise dashboards (IBM/SAP-style navy-grey walls of data) — authoritative but wrong direction for query-first UX

## Design Principles

1. **The answer is the product.** Every layout decision exists to surface the retrieved passage and formula faster. White space and decoration add cognitive load; trim both.
2. **Density is a feature.** Technical users on a workstation can scan dense information faster than padded cards. Information hierarchy, not whitespace, creates clarity.
3. **Formula fidelity is a trust signal.** LaTeX rendering is not cosmetic — it is the reason the tool exists. Formulas must be visually distinct, correctly sized, and unambiguous.
4. **No ornament without function.** Color, borders, and icons carry state (success, warning, error, selected, loading) or distinguish content types (formula vs. paragraph vs. table). Used decoratively, they undermine trust in a precision tool.
5. **Earned familiarity.** The UI vocabulary should be consistent and predictable — users in a task do not want to discover how the interface works. Standard affordances, consistent component shapes, stable layout.

## Accessibility & Inclusion

WCAG 2.1 AA minimum. Key considerations:
- Body text ≥ 4.5:1 contrast against background (metrology docs contain dense small text in source panels — legibility is critical)
- Keyboard navigation for query submission and source expansion
- Formulas rendered as KaTeX (visual) must not be the sole carrier of semantic meaning where possible
- Reduced motion: transitions for state change only, `prefers-reduced-motion` respected throughout
