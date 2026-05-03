---
name: aet-review
description: Staff-level code review with multi-lens checks and cross-model adversarial challenge. Use before merging code — by author or reviewer. Catches structural issues, edge cases, and completeness gaps. Triggers on requests like "review this code," "code review," or "check my PR."
---

# aet-review

Code review for agentic engineering. Multi-lens diff review before anything lands.

## When to Use

- Before merging any PR
- After implementation but before shipping
- When you want a second opinion on a complex change
- As part of the `aet-ship` gate

## Shared Preamble

Before executing any command in this skill, collect the following context:
- `BRANCH` — current git branch
- `REPO_STATE` — clean / dirty / merge-conflict
- `AGENTS_MD` — presence and last-modified date of AGENTS.md
- `LEARNINGS` — top-3 relevant entries from `.agents/learnings.jsonl` (if exists)
- `ACTIVE_PLAN` — any `docs/plans/*.md` modified in last 7 days
- `LAST_PIV` — date of last completed plan-implement-validate cycle (from git log if available)

Use this context to ground all recommendations. Do not ask the user to provide it manually.

## Commands

### `review`

Staff-level diff review with multiple lenses.

**Procedure:**
1. Read the git diff for the current branch (or files specified by user)
2. Read the corresponding `docs/plans/{ticket}-plan.md` to compare implementation against plan
3. Run through review lenses:
   - **Architecture** — does the change fit the existing structure? Are modules deep or shallow?
   - **SQL Safety** — are queries parameterized? Any injection risks?
   - **Conditional Side Effects** — are there hidden side effects in conditional branches?
   - **Error Handling** — are all error paths handled? Are failures observable?
   - **Completeness** — does the diff fulfill the plan? Any acceptance criteria missed?
   - **Tests** — are there tests for new behavior? Are edge cases covered?
4. For each issue found: classify as fix-now or flag-for-human
5. Auto-fix obvious issues (typos, style, missing imports)
6. Produce a review report with: pass/fail status, issues found, auto-fixes applied, human flags

### `codex-review`

Cross-model adversarial review. If another AI model is available, run an independent review and compare findings.

**Procedure:**
1. Summarize the diff and plan in a format suitable for another model
2. Ask the other model to review with an adversarial stance: "Actively try to find bugs, security issues, and design flaws."
3. Compare findings with the primary review
4. Highlight discrepancies — areas where one model found something the other missed

**Model personality heuristic:**
- Claude-style models: great at architecture, patterns, and broad reasoning
- Codex-style models: great at precision, edge cases, and challenging assumptions
- Cross-model analysis catches failure modes that either model alone would miss

## Key Principles

- **Multi-lens catches more** — no single review catches everything
- **Adversarial mode** — actively try to break the code, not just validate it
- **Auto-fix the obvious** — don't waste human time on style/naming issues
- **Flag the subtle** — human review is for architecture and edge-case judgment
- **Compare to plan** — implementation must match what was agreed upon
