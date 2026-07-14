# Enforcement-Walls Adversarial Rehearsal

**Date:** 2026-07-14
**Scope:** `ewl-06-adversarial-rehearsal` — Phase 3 exit-gate demonstration (roadmap G4; R-7, R-8, R-7c) that the enforcement walls hold under real attempted violations, executed after ewl-03 (pre-push gate), ewl-05 (git-refs tamper-evidence), and frh-18 (group evidence-path contract) landed.
**Question:** Do the walls hold when violated for real — the pre-push gate against a gate-skipping push, the git-refs ledger against a hand-edited ref, the stage write-back under batch concurrency (thp-04's disputed second cause) — and do they hold non-invasively (Mode 1 / R-7c: AET config external, nothing AET-specific in the tracked tree, no `refs/aet/*` pushed)?

**Verdict, up front:** the walls that exist hold. (a) pre-push gate **PASS** — a task-branch push missing required gates is refused with named errors; a fully-gated branch pushes cleanly; a task-branch deletion short-circuits. (b) ledger tamper-evidence **PASS** — a hand-edited task ref fails the mutating path closed and warns on the read-only path, per ewl-05's contract. (c) thp-04 write-back race **NOT reproduced** — all 20 concurrent write-backs persisted, consistent with frh-18's dismissal of the second cause. (d) Mode 1 hook arm **PASS** with zero in-tree AET config and no `refs/aet/*` pushed; the config-external git-refs arm is a recorded **GAP** — ewl-07 is not merged, so `~/.aet/{slug}/config.json` is not resolved and the backend falls back to JSON. One scope boundary reconfirmed honestly: the hook stops only an operator who has it installed and does not bypass it; `--no-verify` and hook-less clones are Mode 2 / server-side concerns (roadmap doc 09 Phase 6), not claimed here.

## Method

- Code under test: worktree `ewl-06-adversarial-rehearsal` at `ec64c9e` (== `origin/main`); the `aet` on `PATH` symlinks to the main checkout at the same commit, so the installed CLI exercises exactly the merged ewl-03 / ewl-05 / frh-18 code.
- All rehearsals ran in scratch repositories under `/tmp/ewl-06-rehearsal/` with a sanitized environment (every inherited `AET_*` variable unset) so nothing leaked from the live orchestrator session. No mocks anywhere: real `aet hooks install` shim, real `aet add` / `aet state` / `aet status` CLI paths, real git plumbing, real concurrent processes.
- Verdict fixtures for the "gates recorded" beats were written with `evidence.write_verdict` (schema-validated, `tree_hash`-stamped) to the canonical `~/.aet/reports/{slug}/{task}/{kind}.json` paths the gate reads. Scratch verdicts and the scratch external config were removed from `~/.aet` after capture.
- Transcripts below are verbatim; only the scratch `python3` heredoc bodies are elided where noted.

## (a) Hook rehearsal — PASS (traces: R-7)

Setup: bare remote + clone; `aet hooks install` wrote the self-contained shim to `.git/hooks/pre-push`; `docs/plans/reh-a-task.md` makes branch `reh-a-task` a task branch. The plan omits the gate-skip keys, so all four evidence gates (qa, review, cso, sync-docs) are required.

### (a.1) Refusal — task branch pushed with no gates recorded

```text
$ aet hooks install
installed pre-push gate shim -> /private/tmp/ewl-06-rehearsal/a/repo/.git/hooks/pre-push
[exit 0]

$ git push origin reh-a-task
pre-push gate: refusing push — missing required gate evidence:
  task 'reh-a-task': required gate 'qa' (stage 'implemented') — no verdict recorded at /Users/pedrorocha/.aet/reports/repo/main/reh-a-task/qa.json
  task 'reh-a-task': required gate 'review' (stage 'qa-complete') — no verdict recorded at /Users/pedrorocha/.aet/reports/repo/main/reh-a-task/review.json
  task 'reh-a-task': required gate 'cso' (stage 'reviewed') — no verdict recorded at /Users/pedrorocha/.aet/reports/repo/main/reh-a-task/cso.json
  task 'reh-a-task': required gate 'sync-docs' (stage 'secure') — no verdict recorded at /Users/pedrorocha/.aet/reports/repo/main/reh-a-task/sync-docs.json
Run the missing stages so each records a passing verdict (e.g. `aet run-one <plan>`), then push again.
error: failed to push some refs to '/tmp/ewl-06-rehearsal/a/remote.git'
[exit 1]
```

The refusal names each missing gate, its stage, and the exact verdict path — the operator-facing contract.

### (a.2) All required gates recorded → clean push

Four schema-valid passing verdicts written to the paths above (heredoc elided), then:

```text
$ git push origin reh-a-task
To /tmp/ewl-06-rehearsal/a/remote.git
 * [new branch]      reh-a-task -> reh-a-task
[exit 0]
```

### (a.3) Task-branch deletion short-circuits (waf-05 preserved)

To make the short-circuit airtight, the remote branch was seeded with `--no-verify` so it existed with **zero** recorded verdicts; deleting it via a normal push then had to pass the shim. Had the gate run, it would have refused for all four missing gates:

```text
$ git push origin reh-a-del --no-verify
To /tmp/ewl-06-rehearsal/a/remote.git
 * [new branch]      reh-a-del -> reh-a-del
[exit 0]

$ test -f /Users/pedrorocha/.aet/reports/repo/main/reh-a-del/qa.json && echo "verdict exists" || echo "no verdict recorded for reh-a-del"
no verdict recorded for reh-a-del
[exit 0]

$ git push origin --delete reh-a-del
To /tmp/ewl-06-rehearsal/a/remote.git
 - [deleted]         reh-a-del
[exit 0]
```

### (a.4) Scope, recorded honestly

`git push --no-verify` bypasses the shim entirely (git does not invoke the hook) — confirmed live: the `reh-a-del` seed push above landed with no verdicts. The wall demonstrated here covers a single operator who has the hook installed and does not bypass it. A fresh clone without the hook, or a `--no-verify` push, is explicitly **not** claimed to be stopped; that is Mode 2 / server-side enforcement (roadmap doc 09 Phase 6).

## (b) Ledger rehearsal — PASS (traces: R-7)

Setup: scratch repo with in-tree `.agents/aet-work.json` = `{"task_backend": "git-refs"}` (in-tree config is legitimate here — non-invasiveness is (d)'s concern); the task was seeded through the real `aet add` CLI path, which wrote `refs/aet/tasks/reh-b-task` and the stamped envelope `refs/aet/meta/queue`.

```text
$ aet add docs/plans/reh-b-task.md
✓ Added reh-b-task.md to the queue as ready.
[exit 0]

$ git for-each-ref --format='%(refname) %(objectname)' refs/aet/
refs/aet/meta/queue 0ff9556b8b23da8a92652be2702f5a052061d07b
refs/aet/tasks/reh-b-task 85b4632ed7165b5029a0914750c698ba5cd754f5
[exit 0]
```

The tamper: the task blob was rewritten outside the CLI — `state: "ready"` flipped to `"merged"` via `git hash-object` + `git update-ref`, simulating a hand-edit of the ledger:

```text
$ old=$(git rev-parse refs/aet/tasks/reh-b-task); doctored=$(git cat-file -p "$old" | python3 -c '... state="merged" ...' | git hash-object -w --stdin); git update-ref refs/aet/tasks/reh-b-task "$doctored"
doctored blob: fec3bf42089872f3ae0c6443fdde83d46b14c28a
ref hand-updated outside the CLI
[exit 0]

$ git cat-file -p refs/aet/tasks/reh-b-task
{"blocked_by":[],...,"state":"merged",...}
[exit 0]
```

Detection on the three paths, per ewl-05's contract:

```text
$ aet state transition reh-b-task ready in_progress
⛔ git-refs queue modified outside aet state — run `aet state audit` to inspect, `aet state heal --apply` to repair
[exit 1]

$ aet status
⚠️  git-refs queue modified outside aet state — run `aet state audit` to inspect, `aet state heal --apply` to repair; read-only status continues with unverified data.
✅ No plan drift detected. All plans are tracked in the queue.
... (summary renders; the tampered "merged" task does not surface as ready) ...
[exit 0]

$ aet state audit
⚠️  Queue integrity check failed (content_hash mismatch); audit continues with unverified data. Run `aet state heal --apply` to reconcile and restamp.
{
  "reh-b-task": {
    "stored": "merged",
    "derived": "ready (warning: merged state but not ancestor of origin/main)",
    "discrepancy": true
  }
}
[exit 0]
```

The mutating path fails closed (exit 1, no write-through of the doctored state), the read-only path warns and continues with unverified data, and the explicit audit path surfaces the doctored `"merged"` value against the derived `"ready"`.

## (c) Write-back observation — hypothesis NOT reproduced (supplementary, untraced)

thp-04's learning recorded two stacked causes for a task stuck at `qa-complete` while its footer read `synced`: the `AET_EVIDENCE_PATH` group-session mismatch (fixed by frh-18) and a `_record_stage` write-back loss under batch concurrency, which frh-18 dismissed as unsupported by evidence (`queue_lock` is held across the load-modify-save at `aet-state:360-388`). This observation runs the thp-04 shape for real — a 4-way sibling batch in the `[reviewed, secure]` group position, each task at `in_progress` / `qa-complete` — and fires the exact `_record_stage` write-back path (`aet state set-stage <id> <stage>`, what `orchestrator._record_stage` invokes) as 4 concurrent processes per round, 5 rounds, alternating target so every round performs real writes. Setup used the default JSON backend (thp-04's shape), seeded via `aet add` + `aet state transition` + `aet state set-stage`.

```text
Concurrent write-back observation: 5 rounds x 4 sibling tasks
Each round fires 4 simultaneous `aet state set-stage` processes (the _record_stage write-back path), alternating target stage.

$ [round 1] for i in 1..4: aet state set-stage reh-c-task-$i synced  (4 concurrent processes)
Set stage for reh-c-task-1: synced
Set stage for reh-c-task-2: synced
Set stage for reh-c-task-3: synced
Set stage for reh-c-task-4: synced
[burst exit codes aggregated: 0]
round 1: stages after burst -> {'reh-c-task-1': 'synced', 'reh-c-task-2': 'synced', 'reh-c-task-3': 'synced', 'reh-c-task-4': 'synced'}
round 1: PERSISTED (all 4 at synced)

$ [round 2] for i in 1..4: aet state set-stage reh-c-task-$i qa-complete  (4 concurrent processes)
Set stage for reh-c-task-1: qa-complete
Set stage for reh-c-task-3: qa-complete
Set stage for reh-c-task-2: qa-complete
Set stage for reh-c-task-4: qa-complete
[burst exit codes aggregated: 0]
round 2: stages after burst -> {'reh-c-task-1': 'qa-complete', 'reh-c-task-2': 'qa-complete', 'reh-c-task-3': 'qa-complete', 'reh-c-task-4': 'qa-complete'}
round 2: PERSISTED (all 4 at qa-complete)

$ [round 3] for i in 1..4: aet state set-stage reh-c-task-$i synced  (4 concurrent processes)
Set stage for reh-c-task-1: synced
Set stage for reh-c-task-2: synced
Set stage for reh-c-task-4: synced
Set stage for reh-c-task-3: synced
[burst exit codes aggregated: 0]
round 3: stages after burst -> {'reh-c-task-1': 'synced', 'reh-c-task-2': 'synced', 'reh-c-task-3': 'synced', 'reh-c-task-4': 'synced'}
round 3: PERSISTED (all 4 at synced)

$ [round 4] for i in 1..4: aet state set-stage reh-c-task-$i qa-complete  (4 concurrent processes)
Set stage for reh-c-task-4: qa-complete
Set stage for reh-c-task-2: qa-complete
Set stage for reh-c-task-3: qa-complete
Set stage for reh-c-task-1: qa-complete
[burst exit codes aggregated: 0]
round 4: stages after burst -> {'reh-c-task-1': 'qa-complete', 'reh-c-task-2': 'qa-complete', 'reh-c-task-3': 'qa-complete', 'reh-c-task-4': 'qa-complete'}
round 4: PERSISTED (all 4 at qa-complete)

$ [round 5] for i in 1..4: aet state set-stage reh-c-task-$i synced  (4 concurrent processes)
Set stage for reh-c-task-2: synced
Set stage for reh-c-task-1: synced
Set stage for reh-c-task-4: synced
Set stage for reh-c-task-3: synced
[burst exit codes aggregated: 0]
round 5: stages after burst -> {'reh-c-task-1': 'synced', 'reh-c-task-2': 'synced', 'reh-c-task-3': 'synced', 'reh-c-task-4': 'synced'}
round 5: PERSISTED (all 4 at synced)

OVERALL: all 20 concurrent write-backs persisted
```

**Result:** no task stuck at `qa-complete`; every write-back persisted (20/20). The disputed second cause does not reproduce on the post-frh-18 codebase. Two structural reasons, for the record: `cmd_set_stage` holds `queue_lock` across the whole load-modify-save (`aet-state:360-388`), so concurrent writers serialize rather than interleave; and `_finalize_task` no longer performs a blind `backend.save` — its comment documents that removing it "closes the lost-update window where a concurrent `set-stage` between a load and a save would silently revert the child's stage record" (`orchestrator:1142-1151`). This observation records evidence either way and is intentionally not traced to a PRD requirement.

## (d) Non-invasive (Mode 1) rehearsal — hook arm PASS; config-external git-refs arm GAP (traces: R-7)

Setup: bare remote + clone with **no in-tree AET config of any kind**; the AET config lives only at the external root `~/.aet/d-repo/main/config.json` = `{"task_backend": "git-refs"}` (ewl-07's location); `aet hooks install` wrote the shim. The scratch repo has a remote, so the (a) arm applies in full.

### (d.1) Hook wall holds with zero in-tree AET config

```text
$ mkdir -p ~/.aet/d-repo/main && echo "{\"task_backend\": \"git-refs\"}" > ~/.aet/d-repo/main/config.json && cat ~/.aet/d-repo/main/config.json
{"task_backend": "git-refs"}
[exit 0]

$ aet hooks install
installed pre-push gate shim -> /private/tmp/ewl-06-rehearsal/d/d-repo/.git/hooks/pre-push
[exit 0]

$ git push origin reh-d-task
pre-push gate: refusing push — missing required gate evidence:
  task 'reh-d-task': required gate 'qa' (stage 'implemented') — no verdict recorded at /Users/pedrorocha/.aet/reports/d-repo/main/reh-d-task/qa.json
  task 'reh-d-task': required gate 'review' (stage 'qa-complete') — no verdict recorded at /Users/pedrorocha/.aet/reports/d-repo/main/reh-d-task/review.json
  task 'reh-d-task': required gate 'cso' (stage 'reviewed') — no verdict recorded at /Users/pedrorocha/.aet/reports/d-repo/main/reh-d-task/cso.json
  task 'reh-d-task': required gate 'sync-docs' (stage 'secure') — no verdict recorded at /Users/pedrorocha/.aet/reports/d-repo/main/reh-d-task/sync-docs.json
Run the missing stages so each records a passing verdict (e.g. `aet run-one <plan>`), then push again.
error: failed to push some refs to '/tmp/ewl-06-rehearsal/d/remote.git'
[exit 1]
```

The gate (`aet hooks check`) needs no AET config at all — workflow, plan frontmatter, and verdict paths suffice — so the pre-push wall holds in a Mode 1 repo. After recording the four verdicts (heredoc elided), the branch pushed cleanly:

```text
$ git push origin reh-d-task
To /tmp/ewl-06-rehearsal/d/remote.git
 * [new branch]      reh-d-task -> reh-d-task
[exit 0]
```

### (d.2) Non-invasive properties confirmed

```text
$ git status --short
[exit 0]

$ git ls-files
docs/plans/reh-d-task.md
[exit 0]

$ git ls-remote origin
19184b015d95c96007e64e969f0bb8a9d3dad704  HEAD
19184b015d95c96007e64e969f0bb8a9d3dad704  refs/heads/main
d87b249c6e63d68a8d7495fa52f160c74abb4306  refs/heads/reh-d-task
[exit 0]

(Tab separators in the `ls-remote` output above are rendered as spaces to keep the doc lint-clean.)

$ git ls-remote origin | grep -c "refs/aet/" || echo "no refs/aet/* on remote (count 0)"
0
no refs/aet/* on remote (count 0)
[exit 0]
```

Clean `git status`; the tracked tree carries only the plan file (a versioned project artifact, expected — not a violation); no `refs/aet/*` on the remote.

### (d.3) GAP: the external config is not resolved (ewl-07 not merged)

With the external config selecting `git-refs` and no in-tree config, the backend actually selected was:

```text
$ test ! -e .agents/aet-work.json && echo "no in-tree AET config present"; echo "external config:"; cat ~/.aet/d-repo/main/config.json
no in-tree AET config present
external config:
{"task_backend": "git-refs"}
[exit 0]

$ python3 -c "from backends.factory import create_backend; print('backend selected in this repo:', type(create_backend()).__name__)"
backend selected in this repo: JsonBackend
[exit 0]

$ aet add docs/plans/reh-d-task2.md
✓ Added reh-d-task2.md to the queue as ready.
[exit 0]

$ git for-each-ref --format='%(refname)' refs/aet/
[exit 0]

$ git status --short
?? .agents/
[exit 0]
```

`factory.py` on `origin/main` reads only the in-tree `.agents/aet-work.json`; the external `~/.aet/{slug}/config.json` is not in its resolution path, so the selection fell back to the JSON default, no `refs/aet/*` were created, and the queue materialized as an untracked `.agents/` entry in `git status` — exactly the surface ewl-07 exists to remove. The git-refs tamper wall itself is unaffected (demonstrated in (b)); what cannot be demonstrated today is selecting it **non-invasively**. Disposition: ewl-07 (`blocked`, behind ewl-04) carries the config-external precedence and its own manual scratch-lifecycle validation step; this arm of (d) should be re-run once ewl-07 lands. The plan frontmatter's `blocked_by: ewl-07` anticipated this, but the queue-level dependency set for ewl-06 deliberately omits ewl-07 (`pending_blockers: 0`), so this rehearsal ran and records the gap rather than papering over it.

## Known gaps

1. **Config-external backend selection does not exist (ewl-07 not merged).** `~/.aet/{slug}/config.json` is unread by `factory.py`; a Mode 1 repo cannot select the git-refs backend without an in-tree `.agents/aet-work.json`, and JSON fallback leaves an untracked `.agents/` in `git status`. Re-run (d)'s git-refs arm after ewl-07 lands (see (d.3)).
2. **The hook is single-operator, client-side only (by design, recorded honestly).** `--no-verify` and hook-less clones bypass it; server-side / Mode 2 enforcement is roadmap doc 09 Phase 6 and out of scope here (see (a.4)).

## R-trace

- R-7 (walls demonstrated under real attempted violations): rehearsals (a), (b), (d), and this record.
- R-7c (Mode 1 arm): rehearsal (d) — hook arm demonstrated; config-external git-refs arm recorded as gap 1.
- R-8 (automated regression coverage): unchanged — lives in ewl-03's `tests/test_hooks_install.py` and ewl-05's `tests/test_git_refs_tamper_evidence.py`; this plan adds the phase-level demonstration, not a third automated copy.
- Observation (c) is the supplementary thp-04 write-back observation — intentionally untraced, recorded either way per the plan.
