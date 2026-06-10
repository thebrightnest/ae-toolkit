# PRD: Triage Front Door and Work-Class Routing

## Overview

The AE Toolkit currently has no intake classification. Every request — whether a typo fix or an auth system redesign — enters the same pipeline or bypasses the system entirely. This produced the boot-flow disaster (a 2-line bug routed into a 1,165-line feature rewrite) and forces trivial tasks to either endure full ceremony or skip all governance.

This PRD defines the **triage front door**: a repurposed `aet-prime` that classifies incoming work into three classes — **trivial**, **normal**, and **critical** — and routes each to a proportionate pipeline. It also adds the missing symmetric routing guard (bugs rejected by feature pipelines) and a diff budget for fixes.

## Goals

1. **Classify every request** — `aet-prime` (or `aet-start`) loads context, asks intake questions, and assigns a work class before any skill runs.
2. **Trivial path: zero ceremony** — copy changes, color tweaks, typo fixes route to direct edit + ship with diff review only.
3. **Normal path: lightweight** — standard fields, endpoints, simple UI components route through quick plan → implement → fast automated checks.
4. **Critical path: full ceremony** — auth, data models, infrastructure, and dependency upgrades route through full PRD → TDD → QA → review → `aet-verify` observed evidence.
5. **Prevent routing failures** — `aet-plan` and `aet-pipeline-plan` reject reproducible defects (symmetric to `aet-bug-report` redirecting features). Every entry-point skill includes an intake triage question.
6. **Proportionality budget for fixes** — `aet-bug-report` enforces a diff budget (~3 files / ~100 lines). Exceeding it requires explicit justification before writing code.

## Non-Goals

- Rewriting `aet-bug-report` beyond the diff budget and routing redirect. The core bug investigation procedure stays unchanged.
- Creating new skills for trivial or normal work. The existing skills (`aet-plan`, `aet-implement`, `aet-ship`) are re-routed, not duplicated.
- Changing the `aet-work` queue format or introducing GitHub as a backend. Queue improvements are covered by PRD 6 (State Mechanization).
- Implementing `aet-verify` itself. That is PRD 2.

## Work Classes

| Class | Trigger Examples | Pipeline | Plans? | QA Gate |
|-------|-----------------|----------|--------|---------|
| **Trivial** | "fix typo", "change button color", "update copy" | Direct edit → `make validate` → ship | No | Diff review only |
| **Normal** | "add email field to form", "new API endpoint for list", "simple modal component" | Quick plan (≤ 4 tasks) → implement → auto checks → ship | Yes, lightweight | Automated tests |
| **Critical** | "add OAuth", "migrate database", "upgrade Laravel", "refactor auth layer" | Full PRD → TDD → QA → review → `aet-verify` → ship | Yes, full | Observed evidence |

**Classification rules (deterministic):**
- Touches auth, sessions, permissions, passwords → **Critical**
- Touches data models, migrations, foreign keys → **Critical**
- Bumps a dependency by major or minor version → **Critical** (routes to `aet-upgrade`, PRD 7)
- Adds or modifies infrastructure (queues, storage, env vars, domains) → **Critical**
- Reproducible misbehavior of existing code → **Bug** (`aet-bug-report`), not any plan path
- Everything else → **Normal** or **Trivial** based on estimated files/lines

## User Stories

- As a developer fixing a typo, I want to edit and ship in under 2 minutes without writing a PRD or plan.
- As a developer adding a standard CRUD endpoint, I want a lightweight plan that fits in one session, not a full PRD ceremony.
- As a developer working on auth, I want the toolkit to enforce observed verification before shipping, because auth failures are catastrophic.
- As an agent operator, I want `aet-plan` to reject bug reports so they don't enter the feature pipeline and blow up scope.
- As a code reviewer, I want bug fixes under ~100 lines to justify their size before I see a 1,000-line rewrite in the diff.

## Acceptance Criteria

- [ ] `aet-prime` (or `aet-start`) loads context and asks intake classification questions before routing.
- [ ] Trivial tasks skip `aet-plan`, `aet-tdd`, `aet-qa`, and `aet-review`. They run `make validate` and ship.
- [ ] Normal tasks use a lightweight plan template (≤ 4 tasks, no full PRD) and skip `aet-verify`.
- [ ] Critical tasks require full PRD, TDD, QA, review, and `aet-verify` evidence before `aet-ship` gates.
- [ ] `aet-plan` and `aet-pipeline-plan` include a routing guard: "Is this a reproducible defect in existing code?" → redirect to `aet-bug-report`.
- [ ] `aet-bug-report` includes a diff budget check: > 3 files or > 100 lines requires explicit justification before implementation.
- [ ] `aet-bug-report` includes a routing guard: "Is this a new capability or redesign?" → redirect to `aet-plan`.
- [ ] The Shared Preamble in every entry-point skill includes the intake triage question.
- [ ] `docs/PIPELINE.md` documents the canonical stage state machine and work-class routing table.

## Open Questions

1. Should trivial tasks still create a branch, or edit directly on main? (Default: branch for traceability, but no plan file.)
2. Should the normal-class plan template live in `aet-plan` or as a separate `quick-plan` command?
3. How does `aet-work` handle trivial tasks in the queue — skip ingestion, or ingest with a `trivial` flag?

---

*Stage: scope-validated*
*Validated: 2026-06-10*
*Notes: No cross-PRD conflicts. Depends on aet-verify (PRD 2) and aet-upgrade (PRD 7) being classified as critical-class. PRD 6's aet-state will handle queue transitions for routed tasks.*
