# AET Toolkit Bug Report: Work Queue Plan Atomicity Gap

**Reported:** 2026-05-27
**Project:** Atelier (sagescan/atelier)
**Affected Skills:** `aet-work`, `aet-plan`, `aet-pipeline-implement`
**Severity:** High — causes pipeline mis-routing, context bloat, and worktree confusion

---

## Executive Summary

The `aet-work` skill's `init-queue` and `sync` commands treat **every `.md` file in `docs/plans/` as an executable task**, with no guardrail to distinguish atomic implementation plans from roadmaps, meta-plans, audits, or strategy documents. This violates the 1:1 mapping between queue entries and plan files that `aet-pipeline-implement` expects, leading to:

- Multiple queue entries pointing to the same plan file
- Non-implementable documents (roadmaps, audits) entering the AFK execution loop
- Confusion about whether to run `aet-pipeline-implement` on a plan or its sub-tasks
- Wasted worktrees and branches for documents that should never have been queued

---

## 1. What the Skills Specify

### `aet-plan` — Task Size Guardrails

The `aet-plan` skill enforces a **dual-limit model**:

| Layer                       | Human Time          | AI Complexity                  |
| --------------------------- | ------------------- | ------------------------------ |
| Story (PRD → ticket)        | ≤ 2 days            | ≤ 10 files / 500 diff lines    |
| **Task (ticket → plan.md)** | **≤ 4 agent-hours** | **≤ 8 files / 300 diff lines** |

The `plan` command produces:

> "`docs/plans/{ticket-id}-plan.md` containing: Summary, locked-in architecture, files to create, ordered granular task list..."

The `create-stories` command says:

> "Apply task size guardrails. Evaluate each story against the dual-limit model. Auto-split oversized stories recursively."

### `aet-work` — Queue Management

`init-queue` and `sync` scan `docs/plans/*.md` and build a DAG of tasks. Each queue entry maps to one `plan_file`.

`aet-pipeline-implement` expects:

> "**Input:** Path to `docs/plans/{ticket}-plan.md`"

---

## 2. What Actually Happens

The `aet-work sync` command has **zero filtering**. It recursively adds every `.md` file in `docs/plans/` to the queue, regardless of content type, atomicity, or implementability.

### 2.1 Roadmaps Treated as Tasks

**File:** `docs/plans/p3-completion-roadmap.md`

This is a **5-phase roadmap** with 15+ sub-tasks across multiple phases. It explicitly references other plan files (e.g., "Plan: `docs/plans/fix-broken-native-bridge-handlers.md`"). It is not an atomic, implementable task.

Yet the queue contains **two entries pointing to this same file**:

```json
{
  "id": "P3-CLEAN-1",
  "title": "Preload Hygiene & claudeApi Removal",
  "plan_file": "docs/plans/p3-completion-roadmap.md",
  "status": "merge_verified"
},
{
  "id": "P3-CLEAN-2",
  "title": "IPC Handler Audit & Deletion",
  "plan_file": "docs/plans/p3-completion-roadmap.md",
  "status": "merge_verified"
}
```

Both entries share the same `plan_file`. If `aet-pipeline-implement` were invoked on this file, it would run the same pipeline twice under different task IDs.

### 2.2 Meta-Plans Treated as Tasks

**File:** `docs/plans/E2E-critical-journeys-plan.md`

This is a **parent plan** describing 5 separate E2E test journeys (E2E-1 through E2E-5), each with its own spec file, selectors, and estimated runtime. It has an "Implementation Order" section and "Acceptance Criteria" for all 5 combined.

It exists in the queue as:

```json
{
  "id": "E2E-critical-journeys-plan",
  "title": "E2E Critical Journeys — Plan",
  "plan_file": "docs/plans/E2E-critical-journeys-plan.md",
  "status": "unblocked"
}
```

Meanwhile, **individual atomic plans also exist** for some of these journeys:

```json
{
  "id": "E2E-2-comment-threads",
  "title": "E2E-2: Comment Threads Journey",
  "plan_file": "docs/plans/E2E-2-comment-threads-plan.md",
  "status": "merged"
}
```

This creates ambiguity: should the pipeline run on the meta-plan (which covers 5 specs) or the atomic plan (which covers 1 spec)? The meta-plan is not implementable in a single session — it exceeds the 8-file / 300-line limit by design.

### 2.3 Audit / Strategy Docs Treated as Tasks

These files are analytical or strategic documents, not implementation tasks:

| Queue ID                  | File                                     | Actual Nature                             |
| ------------------------- | ---------------------------------------- | ----------------------------------------- |
| `TEST-audit-and-strategy` | `TEST-audit-and-strategy.md`             | Testing suite audit report                |
| `COV-scope-validation`    | `COV-scope-validation.md`                | Scope validation for coverage gap closure |
| `P3-REM-CLEANUP`          | `p3-remaining-claudeapi-cleanup-plan.md` | Delta audit post hot-fix                  |
| `P3-REM-DELTA`            | `p3-remaining-claudeapi-delta-plan.md`   | Delta audit (second one)                  |

All of these have `branch: null, worktree: null` because they were never meant to be implemented. They were either reviewed and closed, or they are living documents. Yet they occupy queue slots and appear in `aet-work status` output.

### 2.4 Shared Branches for Multiple Plans

`E2E-1` and `E2E-2` are separate queue entries with separate plan files, but share a single branch:

```json
{
  "id": "E2E-1",
  "plan_file": "docs/plans/e2e-auth-token-fix-plan.md",
  "branch": "fix/e2e-infra-repair"
},
{
  "id": "E2E-2",
  "plan_file": "docs/plans/e2e-renderer-cleanup-fixes-plan.md",
  "branch": "fix/e2e-infra-repair"
}
```

This is not inherently wrong if the user intentionally grouped them, but it highlights that the queue's mental model (1 task = 1 branch = 1 worktree) is fragile when plans are not truly atomic or independent.

---

## 3. Impact

### User Confusion

The primary symptom is the user's own confusion: _"it seems that sometimes it shows plans, instead of the atomic tasks that we should actually execute `aet-pipeline-implement` on."_

When `aet-work status` lists 40+ tasks, many of which are roadmaps or audits, the user cannot tell which items are actually ready for `aet-pipeline-implement` without opening each file manually.

### Pipeline Mis-Routing

If `aet-work run` (the AFK loop) picks up a roadmap or meta-plan, it will spawn a worktree and invoke `aet-pipeline-implement` on a non-atomic document. This causes:

- Context bloat (roadmaps reference many files across many phases)
- Failure at the `aet-tdd` or `aet-implement` step because there is no single testable interface
- Wasted compute and git noise

### Violation of the Dual-Limit Model

Roadmaps and meta-plans inherently exceed the task size guardrails. By allowing them into the queue, the system silently violates its own constraint:

> "A task **fails** if **either** limit is exceeded."

### Orphaned / Misleading State

Documents like `launch-fatal-error-handling-plan` have:

```json
"status": "merged",
"merge_verified": false
```

This contradictory state is possible because the document was never a real task, so it was never properly verified post-merge.

---

## 4. Root Cause Analysis

The gap exists at the boundary between **planning** and **queue management**:

1. **`aet-plan` produces documents** but does not constrain WHERE non-atomic documents are saved.
2. **`aet-work` assumes everything in `docs/plans/` is a task** with no validation of atomicity, stage, or file type.
3. **`aet-pipeline-implement` assumes its input is a single atomic plan** but has no way to verify this.

There is no shared contract between these three skills about what qualifies as a queue-able task.

---

## 5. Recommended Fixes

### Option A: Directory Separation (Recommended)

Enforce a directory convention so `aet-work sync` only scans the correct location:

```
docs/plans/           → Atomic, implementable task plans ONLY
docs/roadmaps/        → Multi-phase roadmaps, completion trackers
docs/audits/          → Testing audits, strategy reviews, gap analyses
docs/prds/            → Product Requirements Documents (already exists)
```

Update `aet-work` skill:

> "Scan `docs/plans/*.md` for atomic task plans. If a file does not represent an atomic implementation task, it MUST be stored in `docs/roadmaps/` or `docs/audits/` and will NOT be added to the work queue."

### Option B: Filename Convention Filter

If directory separation is too disruptive, add a filename filter to `aet-work sync`:

| Pattern         | Action                                     |
| --------------- | ------------------------------------------ |
| `*-roadmap.md`  | Skip — not a task                          |
| `*-audit.md`    | Skip — not a task                          |
| `*-meta.md`     | Skip — not a task                          |
| `*-strategy.md` | Skip — not a task                          |
| `*-plan.md`     | Add to queue (convention for atomic plans) |

Update `aet-plan` skill:

> "Atomic task plans MUST be named `{ticket-id}-plan.md`. Roadmaps, audits, and meta-plans MUST use a distinct suffix (`-roadmap.md`, `-audit.md`, etc.)."

### Option C: Frontmatter / Footer Gate

Only add a plan to the queue if its footer reads `*Stage: plan-approved*` or `*Stage: scope-validated*`.

Documents at `plan-draft`, `idea`, or without a stage are excluded.

This requires `aet-plan` to set the correct stage on atomic plans and something else (e.g., `roadmap-draft`) on non-atomic documents.

### Option D: Content Heuristic (Last Resort)

Add a validation step in `aet-work sync` that scans the plan's task list. If it finds:

- Multiple "Phase" or "Ticket" sections
- References to OTHER plan files
- No `## Implementation` section with a single focused change

...then refuse to add it and emit:

> "⚠️ `{filename}` appears to be a roadmap or meta-plan. Move it to `docs/roadmaps/` or split it into atomic plans before adding to the queue."

---

## 6. Migration Path for Existing Repos

For the Atelier repo specifically, the following cleanup is needed:

1. **Move non-atomic documents out of `docs/plans/`:**

   - `p3-completion-roadmap.md` → `docs/roadmaps/`
   - `E2E-critical-journeys-plan.md` → `docs/roadmaps/` or split into atomic plans
   - `TEST-audit-and-strategy.md` → `docs/audits/`
   - `COV-scope-validation.md` → `docs/audits/`
   - `p3-remaining-claudeapi-cleanup-plan.md` → `docs/audits/` (it is a delta audit)
   - `p3-remaining-claudeapi-delta-plan.md` → `docs/audits/`

2. **Deduplicate queue entries:**

   - `P3-CLEAN-1` and `P3-CLEAN-2` should not share a plan file. If they represent real tasks, they need real atomic plan files.

3. **Re-run `aet-work init-queue`** after cleanup to rebuild the queue from a clean `docs/plans/` directory.

---

## 7. Skill File References

Evidence drawn from the following skill files:

- `aet-plan/SKILL.md` — Task Size Guardrails (lines 49–83), `plan` command (lines 194–209)
- `aet-work/SKILL.md` — `init-queue` (lines 36–52), `sync` (lines 54–74)
- `aet-pipeline-implement/SKILL.md` — Input spec (line 54), resumption table (lines 37–46)
- `aet-pipeline-plan/SKILL.md` — Output spec (lines 144–149)

---

## 8. Conclusion

The AET toolkit assumes a clean 1:1 mapping between `docs/plans/{ticket}-plan.md` files and executable tasks, but provides no enforcement mechanism at the filesystem or queue level. Users naturally place roadmaps, audits, and meta-plans in `docs/plans/` because that is where "planning documents" belong. The `aet-work` skill then dutifully adds all of them to the queue, breaking the atomicity contract.

**The fix is a structural boundary:** separate atomic task plans from non-atomic planning artifacts, and teach `aet-work sync` to respect that boundary.

---

_End of report_
