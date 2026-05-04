# Architectural Decision Records (ADRs)

This directory contains ADRs for the AE Toolkit repository itself (not for projects using the toolkit).

## What is an ADR?

An Architectural Decision Record (ADR) captures a significant architectural decision, the context in which it was made, and its consequences. ADRs are immutable once accepted; if a decision changes, a new ADR supersedes the old one.

## When to Write an ADR

Write an ADR when:

- Adding a new skill to the toolkit
- Changing the packaging format (`.skill` files)
- Modifying the directory structure or conventions
- Introducing a new quality tool or automation step
- Changing the skill specification format (frontmatter, markdown schema)

Do **not** write an ADR for:

- Routine skill content updates
- Bug fixes in individual skills
- README wording changes

## Format

Use `000-template.md` as the starting point. Name files sequentially: `001-why-markdown-only.md`, `002-no-ci-services.md`, etc.

## Status Definitions

- **Proposed** — Under discussion, not yet decided.
- **Accepted** — Decision made, record is truth.
- **Deprecated** — Decision reversed; a newer ADR supersedes this one.
- **Superseded by NNN** — Link to the replacement ADR.
