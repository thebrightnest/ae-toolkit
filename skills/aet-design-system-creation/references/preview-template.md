# DESIGN Preview Template

Use this template when generating `docs/designs/DESIGN-preview.html` in Phase 5.

## HTML Structure

```html
<!doctype html>
<html>
  <head>
    <title>[Project Name] — Design System Preview</title>
    <style>
      /* Inline all CSS. Use the exact token values from DESIGN.md frontmatter. */
      /* Map tokens to CSS custom properties for clarity. */
      :root {
        --color-primary: #...;
        --color-secondary: #...;
        /* ... all tokens ... */
      }
    </style>
  </head>
  <body>
    <h1>Design System: [Project Name]</h1>
    <p class="memorable-thing">"[The memorable thing]"</p>

    <section>
      <h2>Typography</h2>
      <!-- Show each typography token with sample text -->
    </section>

    <section>
      <h2>Color Palette</h2>
      <!-- Show each color as a swatch with hex value -->
    </section>

    <section>
      <h2>Spacing Scale</h2>
      <!-- Show each spacing step as a visual bar -->
    </section>

    <section>
      <h2>Components</h2>
      <!-- Button, Card, Input styled with the design system -->
    </section>
  </body>
</html>
```

## Required Content

- **Typography section**: Show every typography token with real text. Label each with token name, font family, size, weight, line-height.
- **Color section**: Show each color as a rectangle swatch (80px × 80px minimum). Label with token name and hex value. Show text on both light and dark backgrounds to demonstrate contrast.
- **Spacing section**: Show each spacing step as a horizontal bar with width = spacing value. Label with token name and pixel value.
- **Components section**: At minimum show:
  - Primary button (default, hover, active states)
  - Card with sample content
  - Text input (default, focus, error states)
  - Heading + paragraph combination

## CSS Rules

- Use the exact font names, hex values, spacing values, and easing curves from the design system
- Apply the actual easing curve to button hover transitions so the user feels the motion
- Make the page responsive (max-width container, padding on mobile)
- Keep it clean and minimal — the design system itself is the star, not the preview chrome
