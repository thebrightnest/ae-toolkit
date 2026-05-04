# Typography Reference

Quick reference for font pairing and scale systems used by the skill.

## Font Pairing Patterns

### SaaS / Dashboard
- **Display/Headings**: Space Grotesk, Satoshi, or Geist — geometric, confident
- **Body**: Inter, Geist Sans, or SF Pro — highly legible at small sizes
- **Mono**: JetBrains Mono or Geist Mono — data, code, timestamps

### Editorial / Content
- **Display/Headings**: Newsreader, Source Serif 4, or Lyon — authoritative, readable
- **Body**: Source Sans 3, Inter, or Charter — neutral, high x-height
- **Accent**: Space Grotesk or Cabinet Grotesk — for pull quotes, labels

### E-commerce / Consumer
- **Display/Headings**: Manrope, Cabinet Grotesk, or Melodrama — friendly, approachable
- **Body**: Inter, DM Sans, or Plus Jakarta Sans — warm, legible
- **Accent**: JetBrains Mono — prices, SKUs, metadata

### Developer Tools
- **Display/Headings**: JetBrains Mono or Geist Mono — monospace, technical
- **Body**: Inter or Geist Sans — clean, neutral
- **Code**: JetBrains Mono or Fira Code — ligatures, clear distinction

## Scale Systems

### Major Third (1.25)
Good for dense dashboards and data-heavy UIs.
```
12px → 15px → 19px → 24px → 30px → 37px → 47px → 59px
```

### Perfect Fourth (1.333)
Good for marketing sites and editorial content.
```
12px → 16px → 21px → 28px → 37px → 50px → 67px → 89px
```

### Golden Ratio (1.618)
Good for hero-heavy landing pages where typography is the design.
```
12px → 19px → 31px → 50px → 81px → 131px
```

## Line Heights

- **Headings**: 1.1–1.2 (tight, impactful)
- **Body**: 1.5–1.6 (readable, comfortable)
- **Captions/Labels**: 1.3–1.4 (compact but not cramped)

## Font Weights

- **400**: Body text, long-form reading
- **500**: UI labels, buttons, navigation
- **600–700**: Headings, emphasis (use sparingly)

## Rules

- Never use more than 2 font families in a single design system
- Never use system fonts as the primary choice (Inter is acceptable as a web font)
- Always specify fallbacks: `font-family: 'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif`
