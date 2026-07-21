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

## Index

- [001 — Cross-Cutting Completeness Framework](001-cross-cutting-completeness.md)
- [002 — Planning Implementation Lockout](002-planning-implementation-lockout.md)
- [003 — Toolkit-Level Branch Safety](003-toolkit-level-branch-safety.md)
- [004 — Unify aet-work `run` with OS-Process Isolation](004-unify-aet-work-run.md)
- [005 — Execution Mode Interaction Model](005-execution-mode.md)
- [006 — Work Queue Plan Atomicity Boundary](006-work-queue-atomicity-boundary.md)
- [007 — Separate Release Preparation from Merge Gating](007-ship-release-prep-separation.md)
- [008 — Test Coverage Completeness + API Boundary Contract](008-test-coverage-completeness.md)
- [009 — Archive-Aware Work Queue Sync](009-archive-aware-work-queue-sync.md)
- [010 — Queue State Is Derived from Persistent Facts](010-queue-derived-state.md)
- [011 — Work State Is Recorded Forward, Not Derived on Read](011-forward-only-deterministic-work-state.md)
- [012 — Direct Telemetry Archive and Per-Task Logs](012-direct-telemetry-archive.md)
- [013 — Work Queue Is an Ephemeral Sprint Board, Plans Are the Source of Truth](013-queue-as-ephemeral-sprint-board.md)
- [014 — Optional GitHub Issues Adapter for the Work Queue](014-optional-github-issues-adapter.md) *(superseded by ADR-032)*
- [015 — Telemetry-Driven Skill Improvements](015-telemetry-driven-skill-improvements.md)
- [016 — Distribute AE Toolkit as a System, Not Individual Skills](016-distribute-as-system-not-individual-skills.md)
- [017 — Remove aet-discover from AE Toolkit](017-remove-aet-discover.md)
- [018 — Remove `.skill` Artifacts and Packaging Build Step](018-remove-skill-artifacts.md)
- [019 — Structured Gate Evidence Replaces Footer Regex for Stage Gating](019-structured-gate-evidence.md)
- [020 — Scheduling Is Delegable; Sequencing Is Not; the CLI Is the Enforcement Boundary](020-sequencing-is-not-delegable.md)
- [021 — Evolve in Place; the Greenfield Is Trigger-Gated](021-evolve-in-place-greenfield-trigger-gated.md)
- [022 — Local Worktree Project Identity](022-local-worktree-project-identity.md)
- [023 — One Canonical Verdict Path per (Task, Kind), Published in Every Session Shape](023-one-canonical-verdict-path.md)
- [024 — Queue Integrity Recovery: Audit Inspects, Heal Restamps](024-queue-integrity-recovery.md)
- [025 — Validation Freshness: Gate Stages Trust a Fresh QA Verdict Instead of Re-Running](025-validation-freshness-trust-fresh-qa-verdict.md)
- [026 — Slim Markdown Quality Gates](026-slim-markdown-quality-gates.md)
- [027 — Main Hygiene Halts Unattended Runs](027-main-hygiene-halts-unattended.md)
- [028 — Work Class Is a Recorded Attribute; Zero-Review Auto-Merge Is Policy-Gated and Off by Default](028-work-class-attribute-and-zero-review-policy.md)
- [032 — GitHub Issues Is a Projection, Not a Backend](032-github-issues-projection-not-backend.md)
- [033 — Projections Fail Open; Storage Fails Closed](033-projections-fail-open-storage-fail-closed.md)
- [034 — Settled-ness Is Derived from Versioned Plan Data](034-settled-from-versioned-plan-data.md)
- [036 — Repository Is Content Plus Python Package](036-repo-is-content-plus-python-package.md)
- [037 — Runtime Dependency Policy](037-runtime-dependency-policy.md)
- [038 — Directory Layout Change](038-directory-layout-change.md)
- [040 — Documentation Invariants Are Data](040-documentation-invariants-as-data.md)

## Format

Use `000-template.md` as the starting point. Name files sequentially: `001-why-markdown-only.md`, `002-no-ci-services.md`, etc.

## Status Definitions

- **Proposed** — Under discussion, not yet decided.
- **Accepted** — Decision made, record is truth.
- **Deprecated** — Decision reversed; a newer ADR supersedes this one.
- **Superseded by NNN** — Link to the replacement ADR.
