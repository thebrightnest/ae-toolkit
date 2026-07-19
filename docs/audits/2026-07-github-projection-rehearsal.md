---
id: gib-09-live-rehearsal-audit
date: 2026-07-19
repo: pedrorocha-net/aet-throwaway-rehearsal-20260719-035144
---

# Live Rehearsal + Audit: GitHub Issues Projection Exit Gate

## Setup

- **Projection target:** `pedrorocha-net/aet-throwaway-rehearsal-20260719-035144` (private GitHub repo created for this rehearsal).
- **Local AET origin:** `/tmp/aet-rehearsal-origin.git` (bare), cloned into `/tmp/aet-rehearsal-clone-a` and `/tmp/aet-rehearsal-clone-b`.
- **AET config in each clone:**

  ```json
  {
    "task_backend": "json",
    "projections": [
      {
        "type": "github",
        "repo": "pedrorocha-net/aet-throwaway-rehearsal-20260719-035144",
        "label_prefix": "aet"
      }
    ]
  }
  ```

- **`gh` status:** authenticated as `pedrorocha-net`.

## Executive Verdict

The board-entry projection (`aet backlog add`, `aet sprint add`) and reconcile command work against a live GitHub repo. Fail-open behavior holds. However, **state transitions and closures do not propagate to GitHub labels** because the storage backend (`JsonBackend`/`GitRefsBackend`) never forwards `on_transition`/`close_task` to the projection dispatcher. This is the single blocking defect uncovered by the rehearsal. A secondary defect in `init-queue` misclassifies status commits as merge commits, breaking the second-clone membership story.

| Arm | Claim | Verdict | Blocking Defect |
| --- | --- | --- | --- |
| (a) | `aet backlog add` creates issue, labels `aet:draft`/`aet:backlog` | **PASS** | — |
| (b) | `aet sprint add` labels `aet:ready` / `aet:blocked` | **PASS** | — |
| (c) | Transition → `aet:in-progress`; close → issue closed | **FAIL** | Backend does not forward transitions/closure to projections |
| (d) | `quarantined` task labels `aet:quarantined` | **FAIL** (direct), **PASS** (via reconcile) | Same transition-forwarding defect |
| (e) | Reconcile dry-run reports drift; `--apply` heals it | **PASS** | — |
| (f) | Broken `gh` mid-flow: state change succeeds with warning | **PASS** (on board entry) | — |
| (g) | Second clone pulls, `aet run` selects same task | **FAIL** | `init-queue` treats status-commit messages as merge commits |

## Per-Arm Evidence

### (a) Backlog add creates an issue keyed by plan id

Subject: `gib-09-rehearsal-alpha` (`status: draft`).

```text
$ aet backlog add docs/plans/gib-09-rehearsal-alpha.md
✓ Added gib-09-rehearsal-alpha.md to the backlog as aet:draft.
```

Result: issue `#1` created with label `aet:draft` and body containing `<!-- aet-id: gib-09-rehearsal-alpha -->`.

**Verdict: PASS.**

### (b) Sprint add computes `ready`/`blocked` from the DAG

Subject: `gib-09-rehearsal-alpha` (no blockers) and `gib-09-rehearsal-beta` (blocked by `gib-09-rehearsal-blocker`).

```text
$ aet sprint add docs/plans/gib-09-rehearsal-alpha.md
✓ Promoted gib-09-rehearsal-alpha.md to the sprint as ready.

$ aet sprint add docs/plans/gib-09-rehearsal-beta.md
✓ Promoted gib-09-rehearsal-beta.md to the sprint as blocked.
```

Result: `#2` labeled `aet:ready`, `#3` labeled `aet:blocked`.

**Verdict: PASS.**

### (c) State transition updates label; closure closes issue

Local transitions succeeded:

```text
$ aet state transition gib-09-rehearsal-alpha ready in_progress
Transitioned gib-09-rehearsal-alpha: ready -> in_progress

$ aet state transition gib-09-rehearsal-alpha in_progress awaiting_merge
Transitioned gib-09-rehearsal-alpha: in_progress -> awaiting_merge

$ aet state record-merge gib-09-rehearsal-alpha --branch gib-09-rehearsal-alpha
Recorded merge for gib-09-rehearsal-alpha: 567ac5e... (regular)
```

However, the GitHub label remained `aet:ready` and the issue stayed open. The local queue correctly removed the sealed task.

**Verdict: FAIL.** `JsonBackend`/`GitRefsBackend` inherit the default no-op `on_transition` and `close_task` from `TaskBackend`; the projection dispatcher is only invoked from `aet backlog add` and `aet sprint add`, not from `aet-state`.

### (d) Quarantined state projects `aet:quarantined`

Local transition succeeded:

```text
$ aet state transition gib-09-rehearsal-gamma in_progress quarantined
Transitioned gib-09-rehearsal-gamma: in_progress -> quarantined
```

Direct projection did not update the label (issue `#4` stayed `aet:ready`). After running `aet reconcile --apply`, the label became `aet:quarantined`, proving the label map is complete and the projection can compute the state.

**Verdict: FAIL on direct transition, PASS on reconcile.** Root cause is the same transition-forwarding defect as (c).

### (e) Reconcile reports and heals drift

Hand-broke issue `#3` by swapping `aet:blocked` for `aet:ready`:

```text
$ aet reconcile
DRY RUN — no changes applied (pass --apply to write)
Live plans: 5 | Issues scanned: 4
Drift:
  mislabeled: gib-09-rehearsal-beta (#3: expected aet:blocked, actual aet:ready)
  mislabeled: gib-09-rehearsal-gamma (#4: expected aet:quarantined, actual aet:ready)
  orphan: gib-09-rehearsal-alpha (#1 no live plan; not deleted)

$ aet reconcile --apply
... same drift listed; writes applied ...
```

After `--apply`, `#3` carried `aet:blocked` and `#4` carried `aet:quarantined`. Orphan issues are reported, not deleted, matching R-17.

**Verdict: PASS.**

### (f) Fail-open when `gh` is broken

Replaced `gh` in `PATH` with a wrapper that exits 1, then ran backlog add on a fresh plan:

```text
$ PATH=/tmp/fake-gh-bin:$PATH aet backlog add docs/plans/gib-09-rehearsal-delta.md
warning: projection GitHubBackend failed during on_add: gh command failed (1): gh: simulated failure
✓ Added gib-09-rehearsal-delta.md to the backlog as aet:draft.
```

The status commit/push succeeded and the command exited 0.

**Verdict: PASS.**

### (g) Second clone pulls and runs the same task

In clone A, `gib-09-rehearsal-delta` was promoted to `status: queued` and pushed. In clone B:

```text
$ git pull origin main
$ aet init-queue
❌ 01-scaffold-skill-structure.md: rtrace: no PRD reference found ...
... (many legacy plans fail validation) ...
```

With the full corpus, `init-queue` fails before writing a queue. A minimal second-clone experiment (only the travel subject plan) showed the status frontmatter traveled, but `init-queue` then reconciled the task as terminal because `git_merge_commit_for` greps commit messages for the task id, matching the `chore(gib-09-travel-subject): mark plan as queued` status commit.

```text
✅ init-queue complete: 1 new tasks added, 0 active tasks.
```

The resulting queue was empty.

**Verdict: FAIL.** Two issues: (1) `init-queue` cannot rebuild the queue in a fresh clone containing the legacy corpus; (2) `git_merge_commit_for` treats status commits as merge commits.

## Additional Findings

### `aet backlog add` overwrites the plan footer with the status value

After `aet backlog add` on an approved plan, the footer became `_Stage: approved_`. This breaks the `aet sprint add` gate, which requires `plan-approved`. The rehearsal had to manually restore the footer before promotion. The footer should preserve the pipeline stage, not mirror plan status.

### Label provisioning works automatically

All `aet:*` labels were created on first projection use with no manual step, including `aet:quarantined`, confirming R-14.

## R-Trace

| Requirement | Demonstrated By | Status |
| --- | --- | --- |
| R-10 | `aet backlog add` created `#1` keyed by plan id | PASS |
| R-11 | `aet sprint add` computed `aet:ready` and `aet:blocked` | PASS |
| R-12 | `aet:blocked` was derived from a live blocker, not human-assigned | PASS |
| R-14 | `aet:quarantined` label exists and is applied by reconcile | PASS |
| R-15 | Reconcile corrected labels to exactly the current state | PASS |
| R-16 | Terminal closure did **not** close the issue (FAIL) | FAIL |
| R-17 | Reconcile dry-run and `--apply` healed drift | PASS |
| R-4 | Broken `gh` produced a warning and exit 0 on board entry | PASS |
| R-9 | Status frontmatter traveled, but queue derivation failed | PARTIAL |

## Recommendations

1. **Wire projections into the storage backend.** `JsonBackend` and `GitRefsBackend` should accept a `ProjectionDispatcher` (or resolve one from config) and forward `on_transition`/`close_task`/`sync_task` to it. This is the only change required to turn arms (c) and (d) green.
2. **Fix `init-queue` merge detection.** `git_merge_commit_for` should match merge commits by something stronger than `--grep <task-id>`, or `commit_and_push_status` should use a commit-message prefix that is excluded from the search.
3. **Preserve pipeline stage in `commit_and_push_status`.** The footer update should use the pipeline stage, not the plan status.

## Cleanup

- Throwaway GitHub repo and local AET clones can be deleted after this audit is reviewed.
- No code changes were made to the AE Toolkit repository; the audit doc is the only tracked artifact.
