---
subject: work-state
supersedes: [10]
---

# Work State Is Recorded Forward, Not Derived on Read

## Status

Accepted. Supersedes ADR-010 (Queue State Is Derived from Persistent Facts).

## Context

ADR-010 made work-queue state **derived on read**: `.agents/work-queue.json` stores facts, and `aet-state derive` recomputes actionable status from git and the filesystem every time a command needs it. The 2026-06-18 audit (`docs/audits/2026-06-18-aet-work-queue-inconsistency-root-causes.md`) showed completed tasks reappearing as `unblocked`. A full review of intake, state, and completion found this is not a queue bug — it is one architectural pattern repeated at three layers:

- **Intake fails open.** The plan template ships `## Dependencies` and `## Tasks`, but `plan_parser.py` reads `## Blocked by` and `## Task List`. Only 8 of 86 plans use the recognized `## Blocked by`; ~62 declare dependencies under `## Dependencies`, which the parser ignores, so their `blocked_by` is silently empty. The size gate reads sections ~95% of plans omit, so it never fires. Task ids are filename stems with no validation.
- **State is re-derived from a lossy signal.** After a squash merge with the branch deleted, the original commits are not ancestors of `origin/main` and the branch is gone. If `merge_commit` was not recorded, `derive` falls back to `unblocked` and the finished task looks like new work.
- **Completion depends on AI discretion.** `merge_commit` — the only field that survives a squash merge — has zero deterministic writers; it is set only by an AI hand-editing JSON per prose. `post-ship-verify`, the step documented to reach `merged`, has no implementation. The only automatic terminal write is `done`, which means "pipeline exited 0 in a worktree," not "merged to main" — and it is archive-eligible.

The shared sin: **the system never authoritatively records workflow state and trusts it. It re-guesses truth from secondary signals — markdown prose and git ancestry — with parsers and derivation that fail open.** Each task carries up to five disagreeing fragments (filename, footer `*Stage:*`, queue `status`, git reality, archive presence) with none canonical.

ADR-010 correctly identified "two sources of truth that disagree" but chose the wrong resolution — derive everything — and its own Consequences predicted the cost: _"status, next, and the orchestrator must always derive before acting."_ That cost is now the daily failure mode: reads are slow (the orchestrator calls `derive` three times per loop, each running git per task), state is unstable, and completed work resurrects.

Two requirements follow: state mutation must be **deterministic code, not AI judgment** ("it is not allowed for the AI to mess up"), and state must be **recorded going forward and trusted** — once work advances, no command re-litigates the past.

## Decision

Workflow state is **recorded forward by code and trusted on read**, never re-derived from git/filesystem during normal operation.

1. **Record forward, trust the record.** Each task has one `state` recorded at the moment of transition. Reads return the recorded state. Terminal states (`merged`, `abandoned`) are absorbing — no command re-evaluates them.
2. **One writer.** All transitions go through a single code path (`aet-state transition`) that validates legality, applies the change atomically, and appends a per-task `history` entry. No other command and no human edits `state` directly.
3. **Git is consulted once, at write time.** The merge transition resolves and records the real merge commit (`aet-state record-merge`); no read path ever re-checks ancestry. The old `derive` leaves the hot path and becomes an explicit, human-run `aet-state audit` that reconciles against git on demand.
4. **Validate at the boundary; fail closed.** Plan files carry their machine contract (`id`, `blocked_by`, `size`) in validated frontmatter. `sync` rejects a malformed plan loudly instead of emitting a clean-looking task with silently empty fields. The dependency DAG reflects what was authored.
5. **Artifacts are consumed forward.** PRD → plan file → task record → execution → merged. Each stage compiles the prior artifact into a more-structured one and never reads back. The task record is the sole source of truth for state; plan-file content is read only by the implementer of that one task, never to determine state.
6. **One lifecycle.** A single monotonic state machine replaces the parallel queue-`status` and footer-`stage` machines. The "ready" frontier is maintained forward — when a blocker merges, the writer decrements its dependents and promotes any that reach zero — not recomputed by walking the DAG on every read.
7. **Partition live from settled.** The live working set (non-terminal tasks) is the only thing loaded operationally; settled history (`merged`/`abandoned`) is recorded append-only and never read for scheduling. The live file stays bounded by work-in-flight regardless of project age.

## Consequences

- **Easier:** `status`, `next`, and the orchestrator are O(1) reads with zero git calls — fast and stable.
- **Easier:** the squash-merge resurrection bug becomes structurally impossible; a merged task cannot re-derive to `unblocked`.
- **Easier:** context/token cost and git-diff size stop scaling with project age; the live queue stays small.
- **Easier:** the dependency graph means something — dependencies are validated at intake instead of silently dropped.
- **Harder:** every transition must be recorded by code; a missed write is not self-healed. Mitigated by the single-writer chokepoint (which verifies against git at write time) and the occasional `audit`.
- **Harder:** a one-time migration is required. The current `blocked_by` data is ~89% fictional and cannot be trusted; plans must be migrated to the frontmatter contract and re-ingested.
- **Harder:** `aet-ship` must invoke the deterministic merge-record step, which becomes load-bearing rather than optional prose.
- Supersedes ADR-010. Revises ADR-009: archival becomes an automatic consequence of the merge transition and an append-only history store, not a dedup-on-sync concern.

## Alternatives Considered

1. **Keep derive-on-read; teach `derive` to also read plan footers, backfill `merge_commit`s, and add an audit command** (the 2026-06-18 audit's own recommendation). Rejected: it layers more reconciliation onto the mechanism that needs reconciling, leaves intake failing open, and keeps every read expensive. It treats the symptom (resurrection) without removing the cause (re-deriving from a lossy signal).
2. **Keep derive-on-read but cache the derived result.** Rejected: caching a derivation from a lossy signal caches the wrong answer; it neither fixes resurrection nor the empty DAG.
3. **Full event-sourcing — rebuild all state by folding an event log on every read.** Rejected as heavier than needed: a stored `state` field plus an append-only `history[]` delivers "never look back" with O(1) reads and a complete audit trail, without a fold step.
4. **Move the queue to GitHub issues / an external tracker.** Rejected, consistent with ADR-006 and ADR-010: violates the toolkit's agent- and infra-agnosticism and has poor native DAG support.
5. **Adopt SQLite for the queue.** Rejected for now: flat files are diffable, git-native, and zero-dependency, and are adequate to low-thousands of tasks. Revisit only past that threshold; it is not the current bottleneck.
