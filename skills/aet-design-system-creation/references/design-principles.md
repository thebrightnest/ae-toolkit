# AET Design Principles

This skill follows these core principles when creating design systems.

## 1. Memorable Thing First

Design that tries to be memorable for everything is memorable for nothing. Every decision — font, color, spacing, motion — must serve the one thing the user wants remembered.

## 2. Opinionated Proposals

The skill proposes specific choices, not menus. "Use Space Grotesk at 32px for H1, #0A0A0A for primary text, 1.5rem spacing scale" — not "What font do you like?" Users can push back. The conversation is what matters.

## 3. Research-Driven, Not Template-Driven

Before proposing, the skill researches what exists in the product's category. Layer 1 (table stakes), Layer 2 (trends), Layer 3 (deliberate departures). No generic "startup landing page" templates.

## 4. Specific Over Generic

- Specific font names, not "a sans-serif"
- Specific hex colors, not "a blue"
- Specific spacing values, not "generous"
- Specific animation curves, not "smooth"

## 5. SAFE vs RISK

Every proposal labels choices as SAFE (conventional, expected, low risk) or RISK (bold, differentiated, high reward if right). The user decides their risk appetite.

## 6. Project-Local Source of Truth

DESIGN.md lives in the repo root. Preview HTML lives in docs/designs/. Taste profiles live in docs/designs/. Everything is versioned with git. No hidden state in dotfiles.

## 7. Progressive Enhancement

The skill works with native agent capabilities only. WebSearch for research. File I/O for DESIGN.md. HTML generation for previews. No external binaries required. If advanced tools (AI mockups, browse screenshots) are available, they are used. If not, the skill falls back gracefully.
