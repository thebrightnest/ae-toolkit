# AE Toolkit Pipeline and Work-Class Routing

This document defines the canonical pipeline stages and the work-class routing table used by the AE Toolkit skills.

## Work Classes

Every incoming request is classified into one of three work classes before any skill runs. `work_class` is also a stored, machine-readable task attribute: an optional plan-frontmatter key (`trivial`, `normal`, or `critical`) that `aet-work sync` validates and copies onto the task record, defaulting to `unclassified` when absent. The stored value is used by downstream readers (risk score, zero-review track record) rather than the routing decision itself.

| Class        | Trigger Examples                                | Pipeline                                                | Plans?           | QA Gate           |
| ------------ | ----------------------------------------------- | ------------------------------------------------------- | ---------------- | ----------------- |
| **Trivial**  | Fix typo, change button color, update copy      | Direct edit → `make validate` → ship                    | No               | Diff review only  |
| **Normal**   | Add email field, new API endpoint, simple modal | Quick plan (≤ 4 tasks) → implement → auto checks → ship | Yes, lightweight | Automated tests   |
| **Critical** | Add OAuth, migrate database, upgrade framework  | Full PRD → TDD → QA → review → `aet-verify` → ship      | Yes, full        | Observed evidence |

## Classification Decision Tree

1. **Is this a reproducible defect in existing code?**
   - Yes → **Bug** → `aet-bug-report`
2. **Does it touch auth, sessions, permissions, passwords, data models, migrations, infrastructure, or bump a dependency?**
   - Yes → **Critical** → Full PRD + TDD + QA + review + `aet-verify`
3. **Is it a copy change, color tweak, typo fix, or similarly small (≤ 3 files, ≤ 100 lines)?**
   - Yes → **Trivial** → Direct edit + `make validate` + ship
4. **Everything else** → **Normal** → Quick plan → implement → ship

## Pipeline Mode Selection

Every plan declares its orchestration mode in frontmatter (`pipeline: standard`). The default choice is size-driven, with a risk override for changes that need more isolation.

| Plan size | Default `pipeline` | Rationale |
| --------- | ------------------ | --------- |
| **S** (≤ 2 hr human time / ≤ 100 expected diff lines) | `minimal` | Lowest overhead; telemetry shows no reliability regression for small plans. |
| **M** (≤ 1 day / ≤ 200 lines) | `standard` | Staged QA and review catch real defects without `full` isolation cost. |
| **L** (> 1 day OR > 200 lines) | `standard` or `full` | Larger change surface benefits from more isolation; pick based on risk. |

**Risk override:** Regardless of size, use `standard` or `full` when the change touches authentication, authorization, sessions, or permissions; data models, migrations, or persisted state; public or internal API contracts or wire formats; dependencies, frameworks, or infrastructure; or other security-sensitive surfaces such as secrets, trust boundaries, or injection paths.

Plan authors must record the `pipeline` value explicitly; the orchestrator does not auto-switch. See [ADR-047](./adr/047-pipeline-mode-by-plan-size.md) for the telemetry evidence and decision record.

## Stage-Based Validation Split

Validation ownership is split by stage so the pipeline stays fast without sacrificing coverage:

- **`aet-implement` runs targeted tests only.** It uses a path-based floor (same-directory and matching-name test files) and records the commands it ran.
- **`aet-qa` runs the full test suite unconditionally.** No impact scoping, no cached reuse from implement, no skipping previously green tests.
- **Targeted-test results travel via the run handoff note.** QA compares them against any failing tests to produce gap analysis: a missed test is flagged with the reason it fell outside the implement floor.

This split removes redundant full-suite runs during implementation while keeping QA as the sole, unconditional gate on the complete validation surface.

## Symmetric Routing Guards

Entry-point skills enforce symmetric guards to prevent misrouted work:

- **`aet-plan` / `aet-pipeline-plan`**: If the user describes a reproducible defect, redirect to `aet-bug-report`.
- **`aet-bug-report`**: If the user describes a new capability or redesign, redirect to `aet-plan`.

## Canonical Stage State Machine

The `aet-work` orchestrator is the sole conductor of the pipeline. It reads each task's recorded `state` and `stage` from `.agents/work-queue.json`, spawns isolated agent sessions per stage group, and advances plans automatically. The plan footer `*Stage:*` is a human breadcrumb, not a scheduler input.

The stage sequence, skill bindings, evidence gates, and session grouping are **data, not engine code**. The canonical stage list is the workflow file: a repo-level `.agents/workflows/<name>.json` when present, otherwise the packaged `aet-work/workflows/software.json`; the plan frontmatter key `workflow:` selects the workflow by name (default `software`). A missing or invalid workflow file fails the run loudly at task start — there is no baked-in fallback sequence. The table below mirrors the packaged `software` workflow.

| Stage           | Skills                     | Evidence gate                                                  | Next stage    |
| --------------- | -------------------------- | -------------------------------------------------------------- | ------------- |
| `plan-approved` | `aet-tdd`, `aet-implement` | —                                                              | `implemented` |
| `implemented`   | `aet-qa`                   | passing `qa` verdict                                           | `qa-complete` |
| `qa-complete`   | `aet-review`               | passing `review` verdict                                       | `reviewed`    |
| `reviewed`      | `aet-cso`                  | passing `cso` verdict; skipped when `security_review: skipped` | `secure`      |
| `secure`        | `aet-sync-docs`            | passing `sync-docs` verdict; skipped when `docs_sync: skipped` | `synced`      |
| `synced`        | — (terminal, skill-less)   | —                                                              | `done`        |

At standard isolation the session groups are `[plan-approved, implemented]` → `[qa-complete]` → `[reviewed, secure]`. `aet-ship` merges after `synced`; `merged` is a queue state (see Legal Transitions), not a stage. The planning footers `plan-draft`, `prd-approved`, and `scope-validated` belong to the PRD pipeline (`aet-plan` / `aet-validate-scope`), upstream of the engine stage machine — they are not workflow stages.

## Session Liveness

The orchestrator distinguishes a slow-but-alive session from a genuinely wedged one using hybrid liveness, not just stdout silence.

- **Hybrid liveness** combines two signals:
  - **Process-tree activity**: the session's main process has active descendants (background tasks, subagents, long validations).
  - **Run-log/file writes**: watched log or telemetry files are still growing.
  Either signal resets the stall timer. A lightweight watchdog thread inside the single-plan session runner polls both signals and terminates the process group when `now - last_sign_of_life > stall_timeout`.
- **Stall timeout** is resolved from the active `CLIAdapter` (`stall_timeout`; default 7200 s for all supported adapters). With hybrid liveness the value is uniform across adapters because it is a backstop for true death, not a proxy for per-CLI output cadence.
- **`--task-timeout`** is the coarse wall-clock backstop. It defaults to the adapter's `wall_backstop` (7200 s) and remains overridable. It is retained for the pathological cases liveness cannot see: a process whose descendants are alive but the session itself is still stuck, or one that streams forever.

A session with active descendants or growing log files is left running. A session with neither signal is killed by the stall watchdog; the wall-clock backstop catches the pathological cases liveness cannot.

## Failure Handling

The night-shift runtime classifies every task failure with the nsr-01 taxonomy and routes it according to the `--on-failure` mode passed to `aet run` (default `triage`).

### Failure taxonomy

| Class           | Meaning                                              | Typical signals                                  |
| --------------- | ---------------------------------------------------- | ------------------------------------------------ |
| `environment`   | Missing tool, dependency, network, auth, or permission | `command not found`, `connection refused`, ...   |
| `flaky`         | Non-deterministic test or transient runtime issue    | Non-zero exit with no design-side signal         |
| `design`        | Code/test/design defect                              | Assertion failure, lint/style failure, type/name/syntax error |
| `timeout`       | Killed by wall-clock backstop or stall watchdog      | Wall-clock or silence timeout                    |
| `canceled`      | Killed by signal or orchestrator shutdown            | `SIGINT`/`SIGTERM`, graceful shutdown            |

### `--on-failure` modes

| Mode        | Behavior                                                                                                 |
| ----------- | -------------------------------------------------------------------------------------------------------- |
| `triage`    | Spawn a cheap triage session with the failure tail + class + signature. `requeue` ⇒ `failed → ready`; `quarantine` ⇒ `quarantined`. Fail-closed: an errored or unparseable verdict falls back to the nsr-01 default action. |
| `continue`  | Mark the task `failed` and keep spawning new tasks. No triage session.                                   |
| `halt`      | Mark the task `failed` and stop spawning new tasks; drain running tasks and exit non-zero.               |

The per-task circuit breaker (nsr-03) has absolute precedence: the third identical signature on a single task always quarantines it, regardless of the triage verdict or mode. The triage session only decides *action*; the breaker key stays deterministic so identical failures always collide.

## Recorded-Forward State

Workflow state is **recorded at transition time and trusted on read**.

- `aet-state transition` is the only writer of `tasks[].state`.
- `aet-work status`, `aet-work next`, and the orchestrator project the stored `state` directly and make **zero git calls** on the read path.
- `aet-state audit` reconciles stored state against git ground truth on demand; it is never invoked during normal operation.

## Sprint Membership

The live queue **is the board**: it holds exactly the set of open work (ADR-013, ADR-055). Nothing re-derives membership by scanning `docs/plans/`.

- Plans are admitted explicitly via `aet sprint add` (or `aet backlog add`); intake is curated.
- `sync` reconciles the existing queue: it drops terminal records and rebuilds the blocker DAG, never scans the plans directory.
- `next` selects from the derived queue, so two clones produce the same sprint after fetching `refs/aet/*`.

The queue `state` axis (`ready`, `blocked`, `in_progress`, …) remains the runtime scheduling signal; `ready`/`blocked` are still computed solely from `blocked_by` (R-12), never from labels or human edits.

## Closure Push

Terminal closure is versioned. `aet-state record-merge` records the terminal ledger event and updates the plan footer (`*Stage: merged*`) through the closure transaction, then pushes the resulting commit. A push failure leaves the local commit intact and returns a recoverable error; re-running `record-merge` retries the push without duplicating queue history.

When the plan file is absent from the checkout, `record-merge` first attempts to resolve it from the merged branch (so a squash-merged plan that only existed on the feature branch still closes correctly). If the plan cannot be found in the checkout or on the merged branch, closure fails closed: the merge record remains intact, but the command returns non-zero and reports where it looked and how to recover.

## Legal Transitions

```text
sync:        ∅ → planned
sync:        planned → blocked            (pending_blockers > 0)
sync:        planned → ready              (pending_blockers == 0)
transition:  blocked → ready              (last blocker reached terminal)
transition:  ready → in_progress          (branch + worktree recorded)
transition:  in_progress.stage advances   (tdd → implement → qa → review → cso → sync-docs)
transition:  in_progress → awaiting_merge (pipeline exited 0; NOT terminal)
transition:  in_progress → quarantined    (deterministic failure; human un-quarantine)
transition:  failed → quarantined         (deterministic failure; human un-quarantine)
transition:  quarantined → ready          (human un-quarantine after fix)
transition:  quarantined → abandoned      (human gives up; TERMINAL)
transition:  awaiting_merge → merged      (TERMINAL; merge_commit verified once)
transition:  any → abandoned (reason)     (TERMINAL)
transition:  in_progress → failed         (needs inspection; may re-enter)
transition:  ready → failed               (needs inspection; may re-enter)
```

Terminal states are `merged` and `abandoned`. Only terminal states satisfy blockers. `awaiting_merge` and `quarantined` deliberately do **not** satisfy blockers; `quarantined` is non-actionable and is never auto-retried.

## Intake Contract

Atomic plan files must carry a validated YAML frontmatter contract:

```yaml
---
id: { ticket-id }
size: S/M/L
blocked_by:
  - { blocker-id }
---
```

- `id` must match the filename stem and be unique within the PRD family.
- `blocked_by` is the authoritative dependency DAG; prose dependency sections are ignored by `aet-work sync`.
- `size` is the S/M/L complexity label.
- `stage` lives only in the task record, never in plan frontmatter.

`aet-work sync` validates every plan and fails closed on missing, duplicate, or mismatched IDs, unknown blockers, or invalid size values.

## Live / Settled Partition

`.agents/work-queue.json` holds only non-terminal tasks. When a task reaches a terminal state, the writer appends its final record plus history to `.agents/work-history.jsonl` and removes it from the live file atomically. The orchestrator, `status`, and `next` never load settled history for scheduling.

## Task Ledger Record Fields

Each live task record in `.agents/work-queue.json` carries the fields needed by the orchestrator and the morning desk. Fields are written only by their sanctioned paths and are read-only for everyone else unless noted.

| Field | Writer | Description |
| ----- | ------ | ----------- |
| `id` | `aet sprint add/sync` | Plan identifier, matching the plan filename stem. |
| `state` | `aet-state transition` | Canonical lifecycle state (see Legal Transitions). |
| `stage` | orchestrator | Sub-state of `in_progress` (e.g., `implement`, `qa`). |
| `plan_file` | `aet sprint add/sync` | Relative path to the plan markdown file. |
| `branch` / `worktree` | orchestrator | Git branch and checkout path for isolated execution. |
| `cost` | orchestrator | **Analytics-only** per-task token/cost rollup written at task close. See below. |
| `delivered_size` | `aet-state` seal | **Analytics-only** first-parent diff-stat for the recorded `merge_commit`, paired with the plan's declared `size`. See below. |

### Per-Task Cost (`cost`)

At task close the orchestrator sums the task's `stage` telemetry records (`token_count` / `cost_estimate`) into a per-task total and writes:

```json
{
  "cost": {
    "tokens": 1234,
    "usd": 0.0567
  }
}
```

- The field is **analytics-only** (ADR-031): the desk and scoreboard may read it, but no runtime gate, kill, throttle, or triage path does.
- Null is preserved honestly: a task whose stage records carry no token/cost values gets no `cost` field (rather than a zeroed or null-valued object).
- The per-run total remains available via the telemetry archive; `cost` is the per-task decomposition needed by downstream reporting.

### Per-Task Delivered Size (`delivered_size`)

At terminal seal the writer computes the diff introduced by the task's recorded `merge_commit` and stores:

```json
{
  "delivered_size": {
    "headline": 320,
    "total": 480,
    "declared_size": "M",
    "status": "ok",
    "reason": null
  }
}
```

- The measurement uses the first-parent range `git diff <merge_commit>^1..<merge_commit>`, so it is exact for both squash and regular merges and needs no trunk ref.
- `headline` excludes planning artifacts (`docs/`, `.agents/`, `content/`, `reports/`) so it is comparable to the declared `size` bands.
- The field is **analytics-only** (ADR-046): a measurement failure is recorded with `status: "failed"` and a reason, but the task still settles.

## Diff Budget for Bug Fixes

`aet-bug-report` enforces a diff budget to keep fixes proportional:

- **Budget**: ≤ 3 files and ≤ 100 lines
- **Exceeding the budget** requires explicit justification:
  - Why a smaller change is insufficient
  - Why the scope expansion is necessary to fix the root cause
- **Weak justification** → redirect to `aet-plan`; the issue likely requires redesign, not a targeted fix.
