# AE Toolkit Defects — Found Running the poc-03a/03b/05 Batch

> Load this before `aet run`, before resuming a failed task, or when a batch halts for a
> reason that does not name a file. Companion to `worktree-ship-hygiene.md`, which covers
> closure; this file covers the defects that stop a run from getting that far.

**Scope.** Everything here was found on **12.08.2026** while running the `poc-03a` /
`poc-03b` / `poc-05` batch, against **ae-toolkit 1.8.0** — both the venv install at
`~/.local/share/ae-toolkit/venv/…/aet/` and the source repo at `~/Work/ae-toolkit`
(`5fde2ae9`, "chore(release): prepare v1.8.0"). Line numbers are the installed 1.8.0
tree. Items D1–D6 and D10–D11 were verified directly this session; D7–D9 were carried
in from `.agents/learnings.jsonl`, and D12–D13 are reported by a pipeline stage rather
than verified here — provenance is stated per item.

**No fix here is upstream.** Four were applied as edits to the installed
`site-packages` tree, which is invisible, unversioned, and **silently reverted by the
next `ae-toolkit` upgrade**. Treat that as a stopgap, not a fix — §"Making the fixes
durable" is the actual remedy.

---

## Severity summary

| # | Defect | Where | Effect | Fixed? |
|---|---|---|---|---|
| D1 | Stage-group prompt contradicts itself | `cli/orchestrator.py:1119` | Group stops after stage 1; next gate fails closed | Patched (venv) |
| D2 | Plan overlay clobbers an advanced worktree plan | `worktree.py:353` | Every resume re-runs completed stages (~$24 measured) | Patched (venv) |
| D3 | `_record_stage` no-ops under `git-refs` | `cli/orchestrator.py:305-306` | Stage never persists; makes D2 fatal | **Open** |
| D4 | Ledger deadlocks the hygiene gate | `worktree.py:535` | Finishing one batch halts the next | Patched (venv) |
| D5 | Halt message names nothing | `worktree.py:620` | Unattended runs stop with an undiagnosable reason | Patched (venv) |
| D6 | ADR-055 decision 4 half-implemented | `backends/git_refs_backend.py` | Ledger has no refs transport; cannot leave the working tree | **Open** |
| D7 | `aet ship` unusable without a remote | `cli/ship.py:353,455` | Whole subcommand family dies | **Open** (worked around) |
| D8 | `aet state record-merge` unconditional fetch | `cli/aet_state.py:1308` | No invocation succeeds offline | **Open** (worked around) |
| D9 | `aet setup verify` reads the wrong repo root | `cli/setup.py:310` | Prints built-in defaults, not your config | Patched previously |
| D10 | `aet state reset` strands a failed task | `cli/orchestrator.py:1915,1931` | Derives `in_progress`, which the batch never spawns | **Open** (avoidable) |
| D11 | `aet status` can report an empty queue | — | Fail-open read; contradicts `refs/aet/tasks/*` | **Open** |
| D12 | Evidence fields are not value-checked | `aet gate submit` | A `"pending"` placeholder suppresses the real stamp | **Open** |
| D13 | Verdict events land in the main checkout's ledger | `cli/gate.py:368` | A worktree session concludes the gate never ran | **Open** |

---

## D1 — The stage-group prompt contradicts itself

**Verified this session.** `_build_group_prompt` (`cli/orchestrator.py:1094-1122`) opens
with *"Execute the following consecutive pipeline stages in order"*, then appends one
block per stage that reuses the **single-stage** wording verbatim, including
*"Execute only this stage. Do not proceed to subsequent stages."* (`:1119`).

The two instructions contradict. The agent obeys the nearer, more specific one, so the
group completes only its first stage and the next gate fails closed. Observed on
`poc-03a`: `qa`, `review` and `cso` all wrote `pass`, then the run died on
`Gate fail-closed: missing sync-docs verdict`. The child said so outright — *"Per your
instructions I stopped here rather than continuing to `aet-sync-docs`."*

**It is nondeterministic, not deterministic.** The `implemented → qa-complete` group in
the same run completed both stages. So it recurs at roughly coin-flip odds on every
grouped run, which is worse than a hard failure — a green batch is no evidence of absence.

The single-stage builder's copy at `:492` is **correct** and must be left alone.

*Fix applied (venv):* the group block now reads *"Finish this stage completely, then
continue to the next stage block in this prompt (if any). Do not go past the last
block."* Verified by the subsequent run, which completed `cso` **and** `sync-docs` in one
session.

*Recognition tell:* a fail-closed missing-verdict gate on a task whose earlier verdicts
all passed, with the child reporting it stopped deliberately.

---

## D2 — The plan overlay clobbers an advanced worktree plan

**Verified this session. The most expensive defect found.**

`_copy_deferred_files` (`worktree.py:353`) overlays `docs/plans/` from the main checkout
into the worktree *"regardless of git state — untracked, modified, or absent from the
base all resolve the same way"*, and `copy_untracked_files` is called unconditionally at
`cli/orchestrator.py:1282` on **every** task start, including a resume.

ADR-054 defers plan durability to the PR, so the main checkout's copy is *deliberately*
left un-advanced mid-sprint. Overlaying it onto a worktree that has advanced therefore:

1. regresses the plan footer to the workflow entry stage, and
2. presents a diff that **deletes** the Implementation, QA, Review and Security notes.

On `poc-03a` the worktree received a stale 10.08 copy — older than every 12.08 commit —
that git reported as a modification deleting **166 lines** of stage history. The pipeline
then re-ran `aet-tdd`, `aet-implement`, `aet-qa` and `aet-review` over already-reviewed
code, at a measured cost of roughly **$24**.

*Fix applied (venv):* skip a destination whose mtime is `>=` the source's. Verified
across three cases — resume keeps the advanced footer, a genuine operator edit still
propagates (editing the source makes it newer), and a fresh worktree is still seeded.

*Trade-off to be aware of:* if an operator edits the main copy while an agent has touched
the worktree copy more recently, the operator's edit no longer propagates. That is
strictly better than silently deleting stage history and re-running reviewed stages, but
it is a behaviour change, not a pure bug fix.

*Without the patch:* before resuming, run `git diff -U0 <plan>` in the worktree. If it
deletes stage history the footer has been clobbered; `git checkout -- <plan>` restores it
losslessly (the working copy adds only the footer lines).

---

## D3 — `_record_stage` silently no-ops under the `git-refs` backend

**Verified this session. This is what makes D2 fatal rather than cosmetic.**

```python
# cli/orchestrator.py:305-306
queue_file = os.path.join(repo_root, ".agents", "work-queue.json")
if task_id and os.path.exists(queue_file):
```

A hardcoded JSON path in backend-agnostic code. Under `git-refs` that file never exists,
so the branch is never taken and the advanced stage is **never persisted** to the task
record — every task ref carries `"stage": null` permanently.

`get_current_stage` (`:293`) is `task.get("stage") or read_plan_stage(plan_file) or
entry_stage`. With the record always empty, the footer fallback is not a
"backward-compatible fallback" as its docstring claims — it is *the only* path. Which is
precisely the input D2 corrupts.

Same defect class as D6's `cli/gate.py:368`.

*Suggested fix:* route through the configured backend instead of probing for a file, or
at minimum resolve the queue path from the backend rather than hardcoding it. **Not
patched** — it needs a backend-aware writer, not a one-line edit.

---

## D4 — The ledger deadlocks base hygiene

**Verified this session.** `check_base_hygiene` (`worktree.py:588`) shells
`git status --short --untracked-files=all` and drops lines matching two allow-lists:
`AET_IGNORED_PATHS` (`:535`) and `DEFERRED_PATH_PREFIXES` (`docs/plans/`).
`.agents/ledger.jsonl` is in neither.

AET appends to the ledger on **every verdict and state transition**. So once the ledger
is tracked, finishing one batch guarantees the next one halts with
`⛔ Working tree is dirty` — and per ADR-027 that is a mechanical durability hard-stop
that fails closed even unattended. Routine operation deadlocks the tool.

This is not hypothetical for other projects either: `factory.py` defaults
`task_backend` to `"json"`, `Ledger()` defaults to `Path(".agents/ledger.jsonl")`
(`ledger.py:52`), and `cli/gate.py:368` hardcodes that path — so **a working-tree ledger
is the shipped default**, unprotected by the hygiene gate.

*Fix applied (venv):* added `.agents/ledger.jsonl` and its `.lock` to
`AET_IGNORED_PATHS`. Justified by ADR-055 decisions 1–3 — the store is append-only,
content-addressed and commutative, so a pending append is never a reason to refuse to
start. Verified against this repo's exact case (`M .agents/ledger.jsonl` now passes).

*Still open in this repo:* `.agents/learnings.jsonl` is the same class — tracked,
tooling-written, not allow-listed — so it will halt future runs until committed.

---

## D5 — The halt message names nothing

**Verified this session.** `worktree.py:620` returned a bare `"Working tree is dirty"`
while holding `dirty_lines`. That is the entire cost of the halt for an unattended run
that cannot ask: diagnosis means reproducing `git status` by hand and cross-checking two
allow-lists.

*Fix applied (venv):* the message now names up to ten offending paths with a `(+N more)`
suffix — e.g. `Working tree is dirty: ?? other.txt; ?? stray.py`. A few lines, and the
halt becomes self-diagnosing.

---

## D6 — ADR-055 decision 4 is half-implemented

**Verified this session.** ADR-055 decision 4 reads:

> **Queue and ledger travel with the repo as pushed git refs**; config, telemetry, and
> reports stay machine-local. … `refs/aet/*` lives inside the repository, outside the
> working tree, invisible to every PR diff.

`backends/git_refs_backend.py` implements **the queue half only** — `refs/aet/tasks/*`
and `refs/aet/meta/queue`. It contains **no ledger handling at all**, in the installed
1.8.0 tree *and* in `~/Work/ae-toolkit` at v1.8.0. Meanwhile `Ledger()` defaults to
`.agents/ledger.jsonl` and `cli/gate.py:368` hardcodes
`repo_root / ".agents" / "ledger.jsonl"` regardless of backend.

**Consequence:** switching to `git-refs` does *not* move the ledger out of the working
tree, because there is nowhere for it to go. So the common advice — untrack the file with
`git rm --cached` and let the backend carry it — does not work: it removes durability
immediately with no supported replacement. The file is load-bearing (`cli/sprint.py:148`
reads it for settled-ness, which is exactly ADR-055's *"a fresh clone never resurrects
settled work"*).

**For this repo specifically:** `.agents/aet-config.json` already sets
`task_backend: "git-refs"`, and `refs/aet/tasks/*` is populated. The tracked
`.agents/ledger.jsonl` is therefore a *workaround for a half-shipped decision*, not a
misconfiguration — and `.gitignore:63-67` says so deliberately. With D4 patched the
deadlock is gone, so **keep tracking the ledger** until a refs transport exists.

*Suggested upstream fix:* implement the ledger half of decision 4 —
`refs/aet/ledger` (or per-task event refs), with `Ledger` resolved through the backend
rather than a hardcoded path. Until then, decision 4 should be documented as aspirational
for the ledger.

---

## D7 — Every `aet ship` subcommand dies without a remote

*Carried from `.agents/learnings.jsonl`; re-confirmed as the reason closure is manual.*

`_run_gate` (`cli/ship.py:442`) calls `_fetch_origin()` (`:353`, invoked at `:455`),
which runs `git fetch origin` with `check=True` and raises. Every subcommand runs the
pre-merge gate, so `gate`, `open`, `merge` and `split` all fail identically on a repo
with no remote — the whole family, not just the pushing paths.

*Workaround in force here:* manual `git merge --no-ff` into the integration branch, then
`aet state transition <task> awaiting_merge merged`. Full sequence in
`worktree-ship-hygiene.md`.

*Suggested fix:* reuse the backend's own remote-safe guard (see D8).

---

## D8 — `aet state record-merge` fetches unconditionally

*Carried from `.agents/learnings.jsonl`.*

`cmd_record_merge` runs its own unconditional `run_git("fetch", "origin")` at
`cli/aet_state.py:1308` and returns 1 **before it ever reads `--merge-commit`**, so no
invocation succeeds offline. This is a toolkit inconsistency rather than a property of
this repo: the `git-refs` backend's own `fetch()` is deliberately remote-safe
(`backends/git_refs_backend.py:269,276` — `if not _has_remote(): return`, *"read-only
commands should not fail when offline"*). `record-merge` bypasses that guard;
`aet state transition` handles it correctly and prints *"No remote configured; local
commit is intact."*

*Consequence of the workaround:* the ledger's `merge_ref` holds a branch name rather than
the merge SHA, and plan frontmatter keeps `status: queued`, because only
`aet ship close` writes it.

---

## D9 — `aet setup verify` resolves the wrong repo root

*Carried from `.agents/learnings.jsonl`; patched previously in the venv.*

`cli/setup.py` `_repo_root()` walks `Path(__file__).parent` four times to reach the
toolkit root — correct for `link`, which needs `skills/`. Line 310 reused it to locate
the **project's** `.agents/aet-config.json`; under a venv install that resolves inside
`site-packages`, so the config is never found and `verify` prints built-in defaults.

*The tell:* provenance reads `default` / `trunk` rather than `config (project)`.
The orchestrator is **not** affected — it calls `resolve_config(..., repo_root=repo_root)`
at `:2449,2868`, so `integration_branch` from config is honoured and `--base` is
unnecessary.

---

## D10 — `aet state reset` strands a failed task

**Verified this session.** The batch spawns **only** tasks whose stored state is `ready`
(`get_next_ready_task`, `cli/orchestrator.py:1915`). `in_progress` is treated as "has a
live child" and never spawned — yet both are in `_BATCH_ACTIONABLE_STATES` (`:1931`), so
the loop neither runs the task nor gives up on it.

`aet state reset` derives its target from git, and a worktree with commits derives
`in_progress`. So `reset` is the wrong recovery for a failed task whose work is already
committed: it converts a visibly-failed task into a silently-stuck one.

*Correct move:* `aet state transition <task> failed ready --reason=…` — legal directly,
confirmed with `aet state validate`. Verify with `aet state audit`, whose
stored-vs-derived table is the honest view.

*Suggested fix:* have `reset` target `ready`/`blocked` as its own `--help` claims, or
make the batch adopt an `in_progress` task with no live run.

---

## D11 — `aet status` can report an empty queue that is not empty

**Verified this session.** `aet status` printed `Queue is empty` / `No active tasks`
while `refs/aet/tasks/*` held all five tasks and `aet state audit` reported them
correctly. It coincided with a stale `.agents/work-queue.json.lock` left behind by the
halted run, and resolved on its own.

A fail-open read on the authoritative store is dangerous in a way a hard error is not:
the honest-looking output invites destructive "recovery" such as `aet init-queue`, which
rebuilds from plans and can resurrect or reset tasks.

*Rule:* never trust an empty `aet status`. Confirm with `aet state audit` and
`git for-each-ref refs/aet/tasks/` before repairing anything, and clear any stale
`.agents/work-queue.json.lock`.

---

## D12 — No evidence field except `verdict` is value-checked

*Reported by `poc-03a`'s `sync-docs` stage from reading the gate source; not
independently verified here.*

A `"pending"` placeholder in `tree_hash` silently suppressed the writer's real stamp,
because `aet gate submit` stamps that field only when the key is **absent**, and the
schema types it as `str` — so any string passes. The stage recorded this as the third
instance of one family: only `verdict` is value-checked.

*Suggested fix:* validate evidence field *values*, or stamp unconditionally rather than
on absence.

---

## D13 — Verdict events land in the main checkout's ledger

*Reported by `poc-03a`'s `cso` stage; consistent with `cli/gate.py:368`, which resolves
`repo_root / ".agents" / "ledger.jsonl"`.*

A worktree session grepping its own `.agents/ledger.jsonl` sees nothing and can wrongly
conclude the gate never ran. Worth knowing before re-submitting a verdict on that basis.

Two gate properties confirmed by the same stage, both reassuring: `aet gate submit` does
**not** write the plan footer, so submitting a verdict cannot regress a plan already
further along; and its ledger event is content-addressed, so re-submitting an identical
verdict appends no row and keeps the original `created_at` while the verdict JSON takes
the new `tree_hash`.

---

## Making the fixes durable

Four fixes (D1, D2, D4, D5) currently exist **only** as edits to
`~/.local/share/ae-toolkit/venv/lib/python3.14/site-packages/aet/`. That location is
unversioned, invisible to review, and overwritten by the next upgrade — the same trap
D9's patch already sits in. Each is recorded in `.agents/learnings.jsonl` with a
re-apply note, which is a reminder, not a fix.

**The real remedy is a change in `~/Work/ae-toolkit`**, released and reinstalled. Two of
the four are small and behaviour-preserving (D1's wording, D5's message); D4 is a
one-line allow-list addition with a rationale; D2 alters overlay semantics and deserves a
test and an ADR note against ADR-054. D3 and D6 need real design work and should not be
patched locally at all.

To stop site-packages edits happening again, a tested guard exists at
`~/.claude/scripts/deny-toolkit-venv-writes.sh` — it denies shell writes into the venv
while still allowing reads, which is necessary for diagnosing exactly these defects. It
is **not wired up**. Enabling it needs this in `~/.claude/settings.json`:

```json
{
  "permissions": {
    "deny": [
      "Edit(//Users/p.rocha/.local/share/ae-toolkit/venv/**)",
      "Write(//Users/p.rocha/.local/share/ae-toolkit/venv/**)",
      "NotebookEdit(//Users/p.rocha/.local/share/ae-toolkit/venv/**)"
    ]
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/scripts/deny-toolkit-venv-writes.sh",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

Merge it with the existing keys rather than replacing the file. Note that the venv
directory is granted per-session via `--add-dir`, not by any settings file, so the deny
rules are what actually revoke it — they take precedence over an added directory.

---

## Operating checklist while these are open

1. `git status --porcelain` must be clean, and `.agents/ledger.jsonl` /
   `.agents/learnings.jsonl` committed, **before** `aet run` (D4).
2. Run `make aet-base` **after** those commits — the integration branch has moved, and
   the integration path does `git reset --hard origin/<branch>`, so a stale shim
   discards commits.
3. Export `UC_OTM_CORPUS_DIR` so the corpus-marked tests actually run inside the
   worktree. A worktree carries no git-ignored files, so they otherwise skip politely and
   a green gate proves nothing about the parser.
4. Before resuming a task, check `git diff -U0 <plan>` in its worktree (D2), unless the
   overlay patch is in place.
5. Requeue a failed task with `aet state transition failed ready`, never
   `aet state reset` (D10).
6. Trust `aet state audit` over `aet status` (D11).
7. Close tasks with a manual `git merge --no-ff` plus `aet state transition` — not
   `aet ship`, not `aet state record-merge` (D7, D8).
