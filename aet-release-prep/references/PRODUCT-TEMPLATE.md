# PRODUCT.md Template

Use this scaffold when `PRODUCT.md` does not yet exist.

```markdown
# Product Name

One-line description of what the product does.

---

## Current Version: X.Y.Z

Last updated: YYYY-MM-DD

---

## Core Features

### Feature One

What it does — one-sentence summary.

**Why it matters:** Benefit to the user in plain language.

**Use cases:**

- Concrete scenario 1
- Concrete scenario 2

### Feature Two

What it does — one-sentence summary.

**Why it matters:** Benefit to the user in plain language.

**Use cases:**

- Concrete scenario 1

---

## Integrations

| Name          | Description                 |
| ------------- | --------------------------- |
| Integration A | What it connects to and why |

---

## What's New

### What's New in vX.Y.Z

- Benefit statement 1
- Benefit statement 2

### What's New in vX.Y.Z-1

- Benefit statement 1

---

_This file is maintained by `aet-release-prep`. Do not delete historical "What's New" sections._
```

## Writing Rules

- Every section must read as **current product documentation**, not a changelog
- Use present tense: "Start conversations with..." not "We added chat..."
- "What's New" sections are **append-only historical records**
- Internal changes (tests, refactors, CI) never appear in "What's New"
