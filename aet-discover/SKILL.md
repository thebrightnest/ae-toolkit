---
name: aet-discover
version: 1.0.0
description: |
  Product-definition diagnostic before any planning or implementation. Interviews
  the user with YC-style forcing questions to validate demand, narrow the wedge,
  and surface real user pain. Produces a product brief, not a PRD. Use when you
  have an idea but no evidence, when scope feels fuzzy, or when "everyone needs
  this." Hard gate: no code, no implementation planning, no technical decisions.
  Triggers on requests like "is this worth building?", "I have an idea", "who
  would use this?", "help me think through this", or "validate this concept."
triggers:
  - is this worth building
  - I have an idea
  - who would use this
  - help me think through this
  - validate this concept
---

# aet-discover

Product-definition diagnostic for agentic engineering. The #1 failure mode is building something no one desperately needs. This skill catches that before a single line of planning is written.

## When to Use

- You have an idea but no evidence anyone wants it
- Scope feels fuzzy or keeps expanding
- Someone said "everyone needs this"
- You want to stress-test a concept before committing engineering time
- Before running `aet-plan` on any new feature, product, or initiative

## Hard Gate

**No code. No scaffolding. No implementation planning. No technical decisions.**

Your only outputs are:
- A conversation that exposes truth
- A `docs/product-briefs/{name}-brief.md` document

If the user asks for code, tickets, architecture, or stack choices, decline and redirect: "Let's validate the problem first. Code comes after we know someone needs this."

## Shared Preamble

Before executing any command in this skill, collect the following context:
- `BRANCH` — current git branch
- `REPO_STATE` — clean / dirty / merge-conflict
- `AGENTS_MD` — presence and last-modified date of AGENTS.md
- `LEARNINGS` — top-3 relevant entries from `.agents/learnings.jsonl` (if exists)
- `EXISTING_BRIEFS` — any `docs/product-briefs/*.md` files (list titles + dates)
- `EXISTING_PRDS` — any `docs/prds/*.md` files (list titles + dates)

Use this context to ground all recommendations. Do not ask the user to provide it manually.

## Commands

### `discover`

Run the product-definition diagnostic. One question at a time. Push until the answer is specific, evidence-based, and uncomfortable. Comfort means we haven't gone deep enough.

**Procedure:**

1. Ask the user to describe the idea in one paragraph. No structure required — brain dump.
2. Run the Six Forcing Questions (below) one at a time via AskUserQuestion.
3. Push on each answer. The first answer is usually the polished version. The real answer comes after the second or third push.
4. After each question, briefly summarize what you heard and state your position (agree, disagree, need more evidence).
5. After all six questions, synthesize findings into a product brief.
6. Create `docs/product-briefs/` if it doesn't exist. Save the brief to `docs/product-briefs/{slug}-brief.md`.
7. Render a verdict: **BUILD**, **NARROW**, **PIVOT**, or **KILL**.

**The Six Forcing Questions:**

See `references/diagnostic-questions.md` for full pushback patterns and red flags.

| # | Question | What to push for | Red flags |
|---|----------|------------------|-----------|
| 1 | **Demand Reality** — What's the strongest evidence that someone actually wants this? | Specific behavior: paying, expanding usage, building workflow around it, calling when it breaks | "People say it's interesting." "500 waitlist signups." "VCs are excited." |
| 2 | **Status Quo** — What are users doing right now to solve this, even badly? | Specific workflow, hours spent, dollars wasted, tools duct-taped together | "Nothing — there's no solution." |
| 3 | **Desperate Specificity** — Name the actual human who needs this most. | A name, a role, a specific consequence if unsolved | "Healthcare enterprises." "SMBs." "Marketing teams." |
| 4 | **Narrowest Wedge** — What's the smallest version someone would pay for this week? | One feature. One workflow. Ship in days, not months. | "We need the full platform first." "Stripped down wouldn't be differentiated." |
| 5 | **Observation & Surprise** — Have you watched someone use a prototype without helping them? What surprised you? | A specific surprise that contradicted assumptions | "We sent a survey." "Nothing surprising, it's going as expected." |
| 6 | **Future-Fit** — If the world looks different in 3 years, does this become more essential or less? | Specific claim about why change makes *your* product more valuable | "The market is growing 20%." "AI keeps getting better." |

**Smart routing based on product stage:**
- Pre-product (idea stage, no users) → Q1, Q2, Q3
- Has users (not yet paying) → Q2, Q4, Q5
- Has paying customers → Q4, Q5, Q6
- Pure engineering/infra improvement → Q2, Q4 only

**Verdict definitions:**
- **BUILD** — Strong demand evidence, sharp wedge, clear user. Proceed to `aet-plan`.
- **NARROW** — Demand exists but wedge is too broad. Assignment: shrink scope to one feature one user would pay for this week. Re-run `discover` on the narrowed version.
- **PIVOT** — Problem is real but solution mismatch. Assignment: talk to 3 users about their actual workflow, then re-run.
- **KILL** — No demand evidence, vague user, no status-quo workaround. Assignment: find a different problem.

**Rules:**
- One question at a time. Never batch questions.
- Anti-sycophancy: never say "that's an interesting approach." Always take a position.
- If the user cannot answer a question with specifics, that IS the finding. Don't let them off the hook.
- The brief is a document of evidence, not a sales pitch. Include the uncomfortable truths.

## Key Principles

- **Specificity is the only currency** — vague answers get pushed, not accepted
- **Interest is not demand** — waitlists and compliments don't count; behavior counts
- **The status quo is your real competitor** — not the other startup, the spreadsheet-and-Slack workaround
- **Narrow beats wide, early** — the smallest version someone will pay for this week wins
- **Observation beats imagination** — watching real users beats guessing what they want
- **Comfort is the enemy** — if the conversation feels easy, we haven't gone deep enough
