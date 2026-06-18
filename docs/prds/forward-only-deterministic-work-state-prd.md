# PRD: Forward-Only Deterministic Work State

## Overview

Redesign how the AE Toolkit manages tasks, plans, and execution so that workflow state is **recorded forward by deterministic code and trusted on read**, instead of re-derived from git and markdown on every read. The change spans three layers: **intake** (a validated, fail-closed plan→task compiler), the **state spine** (a single monotonic lifecycle with one code writer and no derive-on-read), and **completion** (code records the merge once; the live working set is partitioned from settled history). This implements ADR-011 and supersedes the derive-on-read premise of ADR-010 and the "Store Facts, Derive Action" PRD.

The motivating failure is that completed, shipped tasks reappear as actionable `unblocked` work, and the orchestrator "gets lost" on current state while re-reading every plan and re-running git on every loop. The root cause is architectural, not data hygiene: the system distrusts its own recorded state and reconstructs it from lossy signals with parsers that fail open.

## Goals

1. **State is recorded at transition time and trusted on read.** `aet-work status`, `next`, and the orchestrator make **zero git calls** on the read path.
2. **Resurrection is structurally impossible.** A task that reached `merged` can never re-derive to `unblocked`.
3. **Intake fails closed.** A plan that cannot be compiled into a well-formed task is rejected loudly, never emitted with silently empty fields.
4. **The dependency DAG is real.** `blocked_by` reflects authored dependencies for 100% of synced plans (today only 8 of 86 plans use a dependency heading the parser reads).
5. **Exactly one code writer of state.** No command and no human edits `status`/`state` directly.
6. **Merge recording is deterministic code.** `merge_commit` and `merged` are written by an executable at merge time, never by an AI hand-edit.
7. **One lifecycle** replaces the parallel queue-`status` and footer-`stage` machines.
8. **Operational cost is independent of project age.** Reads load only the live working set; settled history is retained but never loaded for scheduling.

## Non-Goals

- No move to GitHub issues or an external tracker (consistent with ADR-006/010/011).
- No SQLite; flat files remain. Revisit only past low-thousands of tasks.
- No full event-sourcing; state is a stored field plus append-only history, not a fold over events.
- No change to the PRD-authoring conversation (`aet-discover`, `clarify-goal`, `create-prd`) beyond what intake validation requires.
- No change to what the orchestrator's pipeline **stages** do (tdd / implement / qa / review / cso / sync-docs); only how their progress is recorded.

## Root Causes

1. **Intake fails open.** `.agents/templates/plan-template.md` ships `## Dependencies` and `## Tasks`; `aet-work/lib/plan_parser.py` reads `## Blocked by` and `## Task List`. ~62/86 plans declare dependencies under the ignored heading → `blocked_by` silently empty. The size gate reads `## Files to Modify`/`## Task List`, present in ~4% of plans → it never fires. Task id = filename stem, unvalidated; cross-plan refs rely on scraping "Ticket N" from titles, which collides across PRD families.
2. **State re-derived from lossy git ancestry.** Squash merge + branch deletion erases ancestry; with `merge_commit` unset, `aet-state derive` returns `unblocked` for finished work.
3. **Completion left to AI discretion.** `merge_commit` has zero deterministic writers; `post-ship-verify` has no implementation; the only automatic terminal write is `done` ("pipeline exited 0 in a worktree" ≠ merged), which is archive-eligible — so unverified work can be archived as complete.
4. **Multiple disagreeing truths, re-derived on every read.** Queue `status` vs footer `*Stage:*` vs git, with nothing reconciling them; `derive` runs git per task on every `status`/`next` call and three times per orchestrator loop.

## User Stories

- **As a developer,** `aet-work status` / `next` return instantly and never bring a finished task back as actionable.
- **As the agent that just merged a PR,** a deterministic command records the squash SHA and flips the task to `merged` — I cannot forget it or get it wrong.
- **As a planner,** if I author a plan the queue cannot parse, `sync` tells me loudly instead of dropping my dependencies silently.
- **As a project lead,** the live queue stays small as the project grows to hundreds of tasks; history is retained but never loaded into context.
- **As a maintainer,** I can reconcile state against git on demand with `aet-state audit`, but normal operation never pays that cost.

## Acceptance Criteria

### Workstream A — Completion & merge recording (contain the active bug first)

- [ ] A deterministic `aet-state record-merge <task_id>` executable resolves the real merge commit (`gh pr view --json mergeCommit`, with a documented fallback), verifies it is an ancestor of `origin/main`, and atomically writes `merge_commit`, `status: merged`, and `merged_at` — or exits non-zero without mutating state.
- [ ] `aet-ship` invokes `record-merge`; no skill instructs an AI to hand-edit `.agents/work-queue.json` to record a merge.
- [ ] The orchestrator writes a non-terminal status (`awaiting_merge`) on pipeline success and no longer writes `done`.
- [ ] `done` is removed as an automatically written status; lingering references normalize to `merged` / `awaiting_merge`.
- [ ] A task in `awaiting_merge` is never archived and never counts as a satisfied blocker.

### Workstream B — Forward-only state spine

- [ ] Each task stores one `state` from {`planned`, `ready`, `blocked`, `in_progress`, `awaiting_merge`, `merged`, `abandoned`, `failed`} plus an append-only `history` array of `{from, to, at, by, evidence}`.
- [ ] `aet-state transition` is the **only** writer of `state`: it validates legality, applies the change atomically, appends a history entry, and updates dependents.
- [ ] On a transition to `merged`/`abandoned`, the writer decrements each dependent's pending-blocker count and promotes any that reach zero to `ready`.
- [ ] `status`, `next`, and the orchestrator read stored `state` and make zero git calls — enforced by a test that fails if a git subprocess is invoked on the read path.
- [ ] `aet-state derive` is repurposed to `aet-state audit`: an explicit, human-run reconcile-against-git that reports discrepancies and is never called by `status`/`next`/orchestrator.
- [ ] The pipeline stage is recorded as a sub-state of `in_progress` in the task record; the orchestrator no longer reads the plan footer to determine the current stage.
- [ ] The plan footer `*Stage:*` is written from the task record as a human breadcrumb and is never read to make scheduling decisions.

### Workstream C — Intake (fail-closed, real DAG)

- [ ] Atomic plan files carry a validated YAML frontmatter contract: `id`, `blocked_by` (list of ids), `size`; body remains human prose.
- [ ] `.agents/templates/plan-template.md` is updated to the frontmatter contract; the `## Dependencies`/`## Blocked by` and `## Tasks`/`## Task List` divergence is eliminated.
- [ ] `aet-work sync` validates each plan and **fails closed**, rejecting with a clear message any plan whose `id` is missing/duplicate/mismatched to its filename, whose `blocked_by` references an unknown id, or which exceeds the size limit without an explicit oversize marker.
- [ ] `sync` never emits a task with an empty `blocked_by` caused by an unparsed section.
- [ ] One plan file maps to exactly one task; a plan describing multiple independent units is rejected or flagged.
- [ ] A migration converts the existing `docs/plans/*.md` corpus to the frontmatter contract and re-ingests the queue; a report lists every dependency recovered and every one left unresolved for human review.

### Workstream D — Archive / scaling

- [ ] Terminal tasks leave the live `.agents/work-queue.json` automatically as a consequence of the transition (no manual `cleanup` required for correctness).
- [ ] Settled history is recorded append-only (e.g. `.agents/work-history.jsonl`) and is never read by `status`/`next`/orchestrator.
- [ ] A task exists in exactly one place (live xor settled); a test verifies no id appears in both.
- [ ] `status`/`next` output is a projection of the live set only.

### Cross-cutting

- [ ] ADR-011 is accepted and ADR-010 is marked `Superseded by 011`.
- [ ] `aet-work/SKILL.md`, `aet-plan/SKILL.md`, `aet-plan/references/work-queue-format.md`, `docs/PIPELINE.md`, `docs/CONVENTIONS.md`, and `CONTEXT.md` are updated to the new model.
- [ ] `make validate` passes and `make package` produces updated `.skill` files.

## Technical Notes

### Task record schema

```json
{
  "id": "wsa-01-record-merge",
  "title": "...",
  "plan_file": "docs/plans/wsa-01-record-merge.md",
  "blocked_by": ["wsb-03-transition-writer"],
  "blocks": [],
  "pending_blockers": 1,
  "size": "M",
  "state": "blocked",
  "stage": null,
  "branch": null,
  "worktree": null,
  "merge_commit": null,
  "merged_at": null,
  "history": [
    {
      "from": null,
      "to": "planned",
      "at": "2026-06-18T12:00:00Z",
      "by": "sync"
    }
  ]
}
```

`blocks` and `pending_blockers` are maintained forward by the writer; they are not re-derived on read. `stage` is the `in_progress` sub-state (one of the pipeline stage names) or `null`.

### Lifecycle and legal transitions

```
sync:        ∅ → planned
ingest/release: planned → blocked            (pending_blockers > 0)
                planned → ready              (pending_blockers == 0)
release:     blocked → ready                 (last blocker reached terminal)
next/orch:   ready → in_progress             (branch + worktree recorded)
orch stages: in_progress.stage advances      (implement → qa → review → …)
orch done:   in_progress → awaiting_merge    (pipeline exited 0; NOT terminal)
record-merge: awaiting_merge → merged        (TERMINAL; merge_commit verified once)
human:       any → abandoned (reason)        (TERMINAL)
orch fail:   in_progress → failed            (needs inspection; may re-enter)
```

Terminal = {`merged`, `abandoned`}. Only terminal tasks satisfy a blocker. `awaiting_merge` deliberately does **not** satisfy blockers, closing the "pipeline done ≠ merged" gap.

### `record-merge` algorithm (deterministic)

1. `git fetch origin`.
2. If `branch` is an ancestor of `origin/main`, use its tip as `merge_commit`.
3. Else resolve `gh pr view <branch> --json mergeCommit`; verify the SHA is an ancestor of `origin/main`.
4. Else apply the documented diff-equivalence fallback; if still unresolved, **exit non-zero and mutate nothing**.
5. On success: `aet-state transition <id> awaiting_merge merged` with the resolved SHA, written atomically with `merged_at`.

### Forward frontier (no DAG re-walk)

`sync` sets `pending_blockers = len(blocked_by)` and `state = ready|blocked`. When a task reaches a terminal state, the writer iterates its `blocks` list, decrements each dependent's `pending_blockers`, and transitions any that hit `0` from `blocked` to `ready`. "What's ready" is then `state == ready`, filtered in topological order — no git, no recursion.

### Live/settled partition

The live file holds only non-terminal tasks. On a terminal transition, the writer appends the task's final record + history to `.agents/work-history.jsonl` and removes it from the live file, atomically. Safe unconditionally because the task's forward effect on dependents was already applied. A browsable `archive.json` view, if wanted, is derived from the log and is never a source of truth.

### Migration

1. Add frontmatter to each `docs/plans/*.md`, inferring `id` from the current stem and `blocked_by` from the existing `## Dependencies`/`## Blocked by` text where unambiguous; flag the rest for human review (free-text "Task N blocks Task M" is intra-plan and must not become an inter-plan edge).
2. Rebuild the queue from frontmatter via the fail-closed `sync`.
3. Backfill terminal state for already-merged work using `record-merge` (resolving real squash SHAs), then let archival move them to history.
4. Produce a reconciliation report: dependencies recovered, dependencies unresolved, tasks marked terminal.

## Decisions

1. **Append-only history over a second mutable snapshot.** A `.jsonl` log only grows by appends, cannot disagree with the live file (a task is live xor sealed), and is the cheapest "remember forever, read never." No browsable `archive.json` is built; a view is derived from the log on demand only if ever needed.
2. **Flat files, not SQLite.** Diffable, git-native, zero-dependency; adequate to low-thousands of tasks.
3. **`awaiting_merge` replaces auto-`done`.** A finished-but-unmerged task is never terminal, never archived, never a satisfied blocker.
4. **Frontmatter contract over filename-derived id and prose dependencies.** Eliminates the heading-mismatch, ticket-collision, and rename-orphan failure modes at once.
5. **One plan = one task,** structurally enforced, not "atomic = one file."
6. **`derive` becomes `audit`,** off the hot path. Git reconciliation is deliberate and occasional, not implicit and per-read.
7. **Ship Workstream A first** as its own atomic plan: it contains the active resurrection bug with no schema change and is independently valuable.
8. **Frontmatter fields are `id`, `blocked_by`, `size`** (S/M/L enum). `stage` lives only in the task record, never in frontmatter.
9. **Migration auto-infers, then a human signs off.** Code infers dependency edges where unambiguous and flags the rest in a reconciliation report; the recovered DAG is not trusted until that report is approved. Free-text "Task N blocks Task M" is intra-plan and never becomes an inter-plan edge.

## Open Questions

None remaining. Resolved 2026-06-18:

- Frontmatter = `id` + `blocked_by` + `size` (S/M/L); `stage` in the task record only → Decision 8.
- History store = append-only log only; no browsable `archive.json` → Decision 1.
- Migration = auto-infer + human-reviewed reconciliation report → Decision 9.
- "Pipeline finished, not yet merged" state = `awaiting_merge` → Decision 3.
- Sequencing = Workstream A standalone first → Decision 7.

---

_Stage: scope-validated_
_Next step: run `aet-work` (single-plan or multi-task queue)_
