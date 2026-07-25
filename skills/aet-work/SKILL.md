---
name: aet-work
description: Work queue management and sequential task execution. Use when you have plan.md files to run in order, want hands-free task execution, or need to check what's ready. Triggers on "run the queue", "pick next task", "what's next", "what's unblocked", "run all tasks", "keep working", "run tasks", "execute plans", "night shift", "AFK mode", "queue status", "init queue", "what can I work on", "run unblocked tasks".
---

# aet-work

Queue management for agentic engineering. The single job of this skill is to manage the ephemeral sprint board and orchestrate task execution — not to plan, implement, or review.

## When to Use

- You have multiple `docs/plans/*.md` files from a PRD breakdown
- You want to run tasks sequentially without manual intervention
- You want to check what's blocked, what's unblocked, what's done
- You want the "night shift" AFK loop

## Shared Preamble

Before executing any command in this skill, collect the following context:

- `BRANCH` — current git branch
- `REPO_STATE` — clean / dirty / merge-conflict
- `AGENTS_MD` — presence and last-modified date of AGENTS.md
- `LEARNINGS` — top-3 relevant entries from `.agents/learnings.jsonl` (if exists)
- `ACTIVE_PLAN` — any `docs/plans/*.md` modified in last 7 days
- `LAST_PIV` — date of last completed plan-implement-validate cycle (from git log if available)
- `ACTIVE_PRD_STAGE` — current `*Stage:` value from the most-recently-modified `docs/prds/*.md` footer (if exists)
- `ACTIVE_PLAN_STAGE` — current `*Stage:` value from the most-recently-modified `docs/plans/*.md` footer (if exists)

Use this context to ground all recommendations. Do not ask the user to provide it manually.

If a stage is found, print at the start of execution: `"📍 Current stage: {stage}."`

## Prerequisites

This skill invokes AET helpers through the `aet` dispatcher (`aet state`, `aet status`, `aet init-queue`, `aet queue sync`, `aet next`, `aet report`, `aet run`). `aet` must be on `PATH`. Run `aet setup link` once after installing skills. If you are developing in this repo, `make install-skills` runs it automatically.

## Mental Model: Plan Files Are the Source of Truth

`docs/plans/{id}.md` files are the durable source of truth for intent, current stage, and terminal closure. `.agents/work-queue.json` is an ephemeral, gitignored sprint board that holds only the active tasks you have explicitly chosen to work on. `.agents/work-history.jsonl` is an optional, gitignored execution log.

This means:

- Approved plans do **not** automatically enter the sprint. Use `aet sprint add` to curate the queue.
- `aet gate review` reads plan files and reports their status without mutating the queue.
- `aet status` reports only the active sprint, not every approved plan.
- Plan drift is informational, not a hard gate.

### File roles

| File                         | Role                                                    | Tracked         |
| ---------------------------- | ------------------------------------------------------- | --------------- |
| `docs/plans/{id}.md`         | Source of truth for intent, stage, and terminal closure | Yes             |
| `.agents/work-queue.json`    | Ephemeral sprint board: active tasks only               | No (gitignored) |
| `.agents/work-history.jsonl` | Optional execution log for transitions and timing       | No (gitignored) |

### Mutation guard

While a batch or `run-one` is live, the orchestrator writes a run lease to `.agents/work-queue.lease` (gitignored). Mutating commands — `add`, `aet queue sync`, `init-queue`, and the `aet state` writers — refuse to run while another run holds a live lease, naming the owning run id. A lease whose process has exited is reclaimed as stale automatically.

Use `--force` only to deliberately override a lease you know is stale, or to make an urgent manual edit during a batch. It prints a loud warning and can corrupt a live run, so prefer re-running after the batch finishes.

Queue writes are also tamper-evident: a hand-edited `work-queue.json` fails closed on read for mutating commands. Run `aet state audit` to inspect the unverified queue against git ground truth, and `aet state heal --apply` to reconcile and restamp the envelope. Read-only commands like `status` warn and continue.

The `git-refs` backend carries the equivalent protection. Its envelope ref (`refs/aet/meta/queue`) is stamped with a chained `content_hash` over the prior hash plus the current task-ref set (task ids + blob OIDs), so a hand-edited, inserted, or removed task ref — or a rewritten envelope blob — is detected on the next read. Mutating commands fail closed; read-only commands warn and continue; and git-refs data written before this protection (no stamp) is accepted and stamped on the next write. The same `audit` / `heal --apply` recovery applies.

### Queue lifecycle

1. Plan is authored with `status: approved`.
2. User runs `aet sprint add docs/plans/FEAT-001.md` → task appears in queue as `ready` (or `blocked` if it has pending blockers).
3. `aet next` or `aet run` transitions it through `in_progress` and its stage sub-states.
4. Task reaches `awaiting_merge`.
5. PR is opened and merged into the resolved trunk branch.
6. `aet-ship` verifies the merge commit is on the resolved trunk branch.
7. `aet-ship` sets plan `status: merged`, appends closure to `.agents/work-history.jsonl`, and removes the task from `.agents/work-queue.json`.

## Task Backends

`aet` routes queue I/O through a pluggable storage backend. The default
`git-refs` backend stores queue state in git refs; the `json` backend stores it
in `.agents/work-queue.json` for non-git contexts.

### Configuration

Backends are configured in `.agents/aet-config.json` (team mode) or
`~/.aet/{config-slug}/config.json` (shadow mode). Use `aet configure --guided`
to create the file in the right place:

```bash
aet configure --guided --scope team --integration-mode pr-per-task
```

Valid values for `task_backend` are `git-refs` (default) and `json`. Run
`aet-setup` (or `aet configure`) to write this file.

### git-refs backend

The default backend stores the active queue in git refs under `refs/aet/meta/`
and the optional execution log in `.agents/work-history.jsonl`. No GitHub
access is required.

### json backend

The local JSON backend stores the active queue in `.agents/work-queue.json` and
the optional execution log in `.agents/work-history.jsonl`. Use this for
non-git projects or while debugging the git-refs backend.

### GitHub Issues projection

GitHub Issues mirroring is configured on the orthogonal `projections` axis, not
as a `task_backend` value. Add a projection entry to the same config file:

```json
{
  "task_backend": "git-refs",
  "integration_mode": "pr-per-task",
  "projections": [
    { "type": "github", "repo": "owner/repo", "label_prefix": "aet" }
  ]
}
```

AET states map to `aet:*` labels on the mirrored issues. `aet next` picks the
next open issue labeled `aet:ready` when a GitHub projection is enabled.

See [`references/github-backend.md`](references/github-backend.md) for the full
label contract, `gh` CLI requirements, issue body format, and sync behavior.

## Integration Modes

`integration_mode` selects how tasks close:

| Mode          | Behavior                                                              |
| ------------- | --------------------------------------------------------------------- |
| `pr-per-task` | Each task ships in its own PR to the resolved trunk branch (default). |
| `single-pr`   | Tasks integrate into a shared epic/Integration Branch and ship together. |

Configure the mode with `aet configure`:

```bash
aet configure --integration-mode single-pr --scope user
```

The per-epic integration branch is a per-run input, not a config value. Use
`--base` with `aet run` or `aet run-one`:

```bash
aet run --base feat/epic-name
aet run-one --base feat/epic-name docs/plans/FEAT-001.md
```

`aet setup verify` prints the resolved `trunk_branch`, `integration_branch`, and
`integration_mode` with provenance.

## Commands

### `sprint add`

Promote a single approved plan into the runnable sprint.

```bash
aet sprint add docs/plans/FEAT-001.md
aet sprint add FEAT-001
```

Accepts a plan file path or a task ID. Refuses plans that are not `plan-approved`, terminal plans (`merged`, `abandoned`), and settled tasks. Sets the plan frontmatter to `status: queued`, commits and pushes the change, then adds the task to the ephemeral queue. Blockers already settled in `work-history.jsonl` do not count toward `pending_blockers` — a plan whose blockers have all merged enters as `ready`, never deadlocked.

### `backlog add`

Scaffolded for gib-07; full backlog intake is not yet implemented.

### `review`

Scan all `docs/plans/*.md` files and print a human-readable status summary. Board columns derive positionally from the loaded workflow — entry stage → approved, terminal skill-less stage → queued, every other stage → in-progress — so variant workflow vocabularies render a sensible board without a per-workflow mapping table; queue states keep fixed columns. For the packaged `software` workflow:

- **Approved:** `plan-approved` (workflow entry stage)
- **Queued:** `synced` (terminal skill-less stage)
- **In Progress:** `implemented`, `qa-complete`, `reviewed`, `secure`, and any other non-terminal stage
- **Awaiting Merge:** `awaiting_merge`
- **Closed:** `merged`, `abandoned`

```bash
aet gate review
```

This reads plan footer stages; it does not modify the queue.

### `status`

Show the current sprint board.

```bash
aet status
```

Reports active task counts, a dependency table (pending `blocked_by` only), next ready tasks, failed tasks, and worktree health. Plan drift is reported as a warning only.

### `next`

Pick the next ready task and transition it to `in_progress`.

```bash
aet next
```

### `run`

AFK loop that runs queued tasks in isolated worktrees. Invokes the orchestrator.

```bash
aet run
```

Configuration and detailed behavior: [`references/queue-commands.md`](references/queue-commands.md).

### `run-one`

Run the full pipeline on a single plan without adding it to the queue.

```bash
aet run-one docs/plans/FEAT-001.md
```

### `sync`

Append-only reconciliation for plans already in or entering the queue. It does **not** auto-add every approved plan.

```bash
aet queue sync
```

Use `add` for explicit curation; use `aet queue sync` after queue edits or when resolving blocker DAGs.

### `init-queue`

Rebuild the queue file from existing plans, preserving terminal metadata. Useful when the queue file is lost.

```bash
aet init-queue
```

### `state heal`

Seal terminal tasks and repair stale queue entries. Worktree removal is manual (`git worktree remove`) — see [`references/queue-commands.md`](references/queue-commands.md).

```bash
aet state heal
```

### `audit`

Reconcile stored state against git ground truth without mutating the queue. Human-run diagnostic only.

```bash
aet state audit
```

### `report`

Print execution telemetry summary.

```bash
aet report
```

### Plan-drift detection

List plan files that are not in the active queue or settled history. Informational only — reported automatically by `aet status` and `aet next`.

```bash
aet status
```

### Drift check

Detect tasks marked terminal whose commits are not on the resolved trunk branch — part of `aet state audit`.

```bash
aet state audit
```

### Marking tasks terminal

Manually mark a task as `merged` or `abandoned`. This is the only supported way to set a terminal status manually.

```bash
aet state transition FEAT-001 <current_status> merged
aet state transition FEAT-001 <current_status> abandoned --reason="duplicate"
```

**Rules:**

- Never mark a task `merged` without verifying its merge commit is on the resolved trunk branch.
- Never mark a task `done` manually; use `merged` or `abandoned`.
- `merge_verified` is a legacy status; use `merged` instead.

## Queue Terminal Statuses

| Status      | Meaning                                        | Set by                 |
| ----------- | ---------------------------------------------- | ---------------------- |
| `merged`    | Code is verified on the resolved trunk branch  | `aet-ship`             |
| `abandoned` | Task explicitly cancelled                      | `aet state transition` |
| `failed`    | Pipeline failed; needs human review            | Orchestrator           |

## Key Principles

- **Plans are the source of truth** — queue is a runtime view
- **Explicit curation** — only `add` puts work in the sprint
- **Gitignored sprint board** — `.agents/work-queue.json` and `.agents/work-history.jsonl` are never committed
- **Forward-only state** — transitions are recorded by code and trusted on read
- **Queue-unaware pipeline** — individual skills know nothing about the queue
- **Session isolation** — `run` spawns fresh OS processes per stage
- **Agent-agnostic** — uses only git commands and generic session language
