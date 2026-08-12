# Mechanical Enforcement over Prose: What Shipped, What Is Still Open

**Date:** 2026-08-12
**Branch:** `fix/mechanical-enforcement-over-prose` (6 commits, unpushed)
**Scope:** items 1–3 of the prose-vs-enforcement review, plus everything found
while implementing them. Later items were surfaced by two parallel sessions — one
investigating a downstream AET project's halt loop, one running the
poc-03a/03b/05 batch (`aet-toolkit-defects.md`) — and re-verified against the
source tree here; where their framing was off, the correction is noted.

## What shipped

| Commit     | Change                                                                              |
| ---------- | ----------------------------------------------------------------------------------- |
| `01ed6e81` | Ledger verifies content addresses on load; appends instead of rewriting; `verify()`  |
| `45e788ef` | `evidence.submit_command` single-sources builder mode; four skills document it       |
| `328f7b2c` | Missing-verdict recovery session; stage prompts derive their submit command          |
| `c0d35b1c` | Corrected a false repair hint and two warnings describing a non-existent mechanism   |
| `29601183` | Group prompt no longer contradicts itself; recovery stops asserting completion       |

Full suite green (1675 tests), plus `ruff`, `skills-lint`, `validate-skills`,
`plans lint`, `docs lint`, `validate-workflows`, markdownlint.

## Open items, most consequential first

### 1. ADR-055's authoritative ledger is declared, not wired

**ADR-055** (accepted 2026-08-09) decides that settled-ness lives in the
append-only provenance ledger, and that "is it done?" is answered by "the
ledger plus git ancestry — exactly one authoritative store pair, replacing
eight." Decision 4 adds: "Queue and ledger travel with the repo as pushed git
refs … `refs/aet/*` lives inside the repository, **outside the working tree,
invisible to every PR diff**."

`.agents/ledger.jsonl` currently has **five writers and zero readers**:

- Writers: `cli/sprint.py:149`, `cli/aet_state.py:584`, `cli/aet_state.py:735`,
  `cli/gate.py:369`, `cli/ship.py:860`.
- `Ledger.read_events()` has no caller anywhere in `src/aet` — only tests.
- No file under `src/aet/backends/` or `src/aet/projections/` references the
  ledger at all. `git_refs_backend.py` manages `refs/aet/tasks/*` and
  `refs/aet/meta/queue`; it has no ledger handling, so **no backend
  configuration moves the ledger out of the working tree.**

The actual settled-ness authority is `_is_settled_from_authority()`
(`cli/init_queue.py:71`), used by `aet queue sync` and `init-queue`. It reads
three things: the settled history log, a merge commit on `origin/main`, and the
**plan footer**. Its docstring says settled-ness is derived "from the ledger or
git ancestry"; the function never touches the ledger. `cli/sync.py:82` carries
the same claim as a comment.

Prose asserting the unbuilt behaviour as fact, beyond those two:

- `docs/CONVENTIONS.md:388` — "Queue and ledger state travel with the repo via
  `refs/aet/*` on origin."
- `docs/WORKFLOW-github.md:23` — "fetch refs/aet/\* → queue derived from
  ledger." Doubly false: the ledger is not refs-borne, and nothing derives the
  queue from it.
- `git_refs_backend.py:13` — "Nothing here pushes `refs/aet/*`: the backend is
  local-only by default", so even the *queue* half of decision 4 is conditional
  on configuration.

Neither authoritative store travels. `.agents/work-history.jsonl` — the store
that actually answers "is it done?" — is itself in `AET_IGNORED_PATHS`, i.e.
gitignored and machine-local. ADR-055's premise (one operator across several
machines, laptop invisible to the cloud box) is unmet on both halves.

**Why it went unnoticed: "ledger" names two different stores.** There is the
git-refs store — what `breaker.py:6` means by "rides the existing git-refs
ledger" (`BREAKER_REF = "refs/aet/breaker"`, `breaker.py:21`, written directly
via git, bypassing the backend class), and what ADR-030 means. And there is the
content-addressed event ledger — `aet.ledger.Ledger`, the JSONL defined by
ADR-055 §1–3. Decision 4, read in the context of §1–3, plainly means the
second; the implementation only ever delivered the first. Anyone reading the
ADR or the docs would reasonably conclude the ledger is refs-borne.

**Suggested shape:** either wire the reader and the transport, or amend ADR-055
to record what was built. Add both senses of "ledger" to the CONTEXT.md
glossary — `aet-validate-scope` exists to catch exactly this class of
terminology collision, and it did not, because both senses are legitimate
domain terms. Leaving four files asserting an unbuilt model is the worst of the
three options.

### 2. The ledger path is not single-sourced, and which file a run writes depends on how it was launched

Four call sites, four derivations:

| Call site                  | Derivation                                                   |
| -------------------------- | ------------------------------------------------------------ |
| `cli/gate.py:368`          | `telemetry.resolve_repo_root() / ".agents" / "ledger.jsonl"` |
| `cli/aet_state.py:583,734` | `Path(backend.queue_file).resolve().parent / "ledger.jsonl"` |
| `cli/sprint.py:148`        | `Path(args.queue_file).resolve().parent / "ledger.jsonl"`    |
| `cli/ship.py:860`          | bare `Ledger()` → CWD-relative default                       |

`resolve_repo_root()` (`project_id.py:16`) checks `AET_REPO_ROOT` **first**, then
falls back to `git rev-parse --show-toplevel` — which inside a git worktree
returns the worktree's own root (verified with a probe: from `/tmp/wt-probe/wt`
it returned `/tmp/wt-probe/wt`). Only one launch path sets that variable:

- **`aet run` (batch).** The batch loop spawns a per-task child orchestrator with
  `env["AET_REPO_ROOT"] = repo_root` (`cli/orchestrator.py:2895`, passed to
  `Popen(cmd, env=env)`), so the child and every stage session it spawns inherit
  it. A worktree session's `aet gate submit` therefore writes the **main
  checkout's** ledger.
- **`aet run-one`, or a directly invoked orchestrator.** `_spawn_detached`
  (`cli/main.py:343`) copies the environment and sets only `AET_RUN_ID`. With
  `AET_REPO_ROOT` unset, the same command writes the **worktree's** ledger —
  which `.worktrees/` gitignores and `aet ship close` deletes with
  `git worktree remove --force` (`cli/ship.py:1003`).

So one call site writes to different files depending on launch mode, and in one
of those modes the events are discarded at closure. An earlier draft of this
report asserted the worktree case unconditionally and concluded that verdict
events are always deleted; that is wrong for the batch path, which is the
dominant one. Under `aet run` the symptom is the inverse, and it is what a
downstream session hit: a worktree session greps its own `.agents/ledger.jsonl`,
sees nothing, and concludes the gate never ran.

**Under the `git-refs` backend there are no `stage` events at all.**
`_record_stage` (`cli/orchestrator.py:305`) probes a hardcoded
`os.path.join(repo_root, ".agents", "work-queue.json")` and shells out to `aet
state set-stage` only if that file exists. `git_refs_backend` keeps a
`queue_file` attribute (`:76-79`) for path derivation but never writes the file,
so under `git-refs` the branch is never taken: the advanced stage is persisted
only to an in-memory dict, no `stage` ledger event is written, and every task ref
carries `"stage": null` permanently. `get_current_stage` (`:293`) then falls back
to the plan footer — which its docstring calls a "backward-compatible fallback"
while it is in fact the only path, and which is exactly the input the plan
overlay corrupts (item 10). Backend-blind path probing inside backend-agnostic
code: the same defect class as `gate.py:368`.

Two smaller divergences:

- `ship.py:860`'s bare `Ledger()` is CWD-relative, so `aet ship` from a
  subdirectory reads and writes a different file than every other call site.
- `--queue-file` and the `queue` argument are user-settable
  (`cli/sprint.py:175`, `cli/aet_state.py:1409`). A non-default value moves the
  ledger with it while `gate.py` stays at the repo root.

**Suggested shape — two separate fixes, not one.**

1. *The ledger path.* One exported derivation, the way ADR-023 already solved
   this exact problem for verdict paths (`evidence.resolve_verdict_path` —
   "writers and the gate must share this single derivation; hand-computing slugs
   from the worktree CWD is out of contract"). The precedent makes this a
   known-solved problem applied to a second store, not a design question. Tests
   should assert all call sites agree from inside a worktree, under both launch
   modes and both backends.
2. *The stage writer.* `_record_stage` needs to route through the configured
   backend instead of probing for a JSON file — a backend-aware writer, not a
   path fix. This is design work: the sole-writer rule (ADR-020) currently rides
   a subprocess call to `aet state set-stage`, and making it backend-aware means
   deciding whether the orchestrator calls the backend directly or the CLI grows
   a backend-agnostic entry point.

### 3. Downstream projects hit an unrecoverable halt loop: the ledger is missing from `AET_IGNORED_PATHS`

`AET_IGNORED_PATHS` (`worktree.py:535`) holds seven entries and **does not
include `.agents/ledger.jsonl`**. It is consumed by two things whose docstring
promises they "always agree":

1. `write_aet_gitignore_entries()` (`cli/setup.py:44`) — what `aet setup` writes
   into a project's `.gitignore`.
2. `check_base_hygiene()` (`worktree.py:588`) — which excludes AET-generated
   paths from the dirty check "because the orchestrator mutates them as part of
   normal operation and they must be gitignored in projects using the toolkit".

So in any project bootstrapped by `aet setup`: the ledger is not gitignored; the
first AET command that records an event creates it; `check_base_hygiene` runs
`git status --short --untracked-files=all` and does not forgive it
(`worktree.py:603-620`, `_is_ignored_path` misses); the tree is permanently
dirty; ADR-027 halts the next unattended run. The file does not even need to be
*tracked* — untracked is enough.

`ae-toolkit`'s own `.gitignore:15` carries `.agents/ledger.jsonl*`, hand-added.
The dogfooding repo is masked from the break it ships.

**Correcting the source session's framing:** it concluded "the toolkit ships
nothing that makes that automatic". The mechanism does exist and is correct —
one shared constant feeding both the gitignore writer and the hygiene gate. The
defect is a **missed registration** in that constant when ADR-055 added a new
file the toolkit writes on every run. That distinction changes the fix: not
"build an automatic mechanism" but "add the entry, and add a test asserting
every file AET writes under `.agents/` appears in `AET_IGNORED_PATHS`". The
second half is what stops the next store from repeating this.

**`.agents/learnings.jsonl` is the same halt, and needs the opposite fix.** It is
tracked in this repo, written by `aet learnings append`, and absent from both
allow-lists — so appending a learning (which `aet-evolve` asks for on every
retro) dirties the tree and halts the next run until it is committed. But
gitignoring it would be wrong: it is *meant* to be tracked. `AET_IGNORED_PATHS`
conflates two different properties — "do not track this" (it feeds the
`.gitignore` writer) and "tolerate this dirty" (it feeds the hygiene gate) — and
a tracked-but-tolerated file cannot be expressed in it. `DEFERRED_PATH_PREFIXES`
is exactly that second concept, already used for `docs/plans/`. So: ledger →
`AET_IGNORED_PATHS`, learnings → `DEFERRED_PATH_PREFIXES`. Splitting the two
consumers apart is the durable fix; adding the ledger to one shared set is the
one-liner.

**Caveat that makes it a decision, not a cleanup:** adding the entry embeds the
"ledger is machine-local" answer to item 1's architectural question. The halt is
real on either branch, so the entry should ship regardless and the ADR question
be taken separately — but shipping it quietly settles the ADR by default, which
is the pattern this whole review is about. Take the decision explicitly.

For a project already halted, the remedies are `git rm --cached
.agents/ledger.jsonl` plus a local gitignore entry (loses nothing that exists —
see item 2: half the events were being deleted anyway), or keep it tracked and
accept the halt. A tracked JSONL that every writer appends to would also
conflict-thrash on merge, which is precisely why decision 4 chose refs.

### 4. The 2026-08-11 "settled tasks disappeared" incident is still undiagnosed

The learning attributed it to hand-editing the ledger. That cannot be the
mechanism: nothing reads the ledger to decide settled-ness (item 1). The
hardening in `01ed6e81` fixed a real data-loss bug in that file — silent line
drops amplified into permanent erasure by rewrite-all — but it did **not** fix
the reported symptom.

Prior learnings point at the likely neighbourhood: `derive_status` rule 1
(`is_ancestor_of_main` on a bare branch) and `cmd_heal`'s trust of that
derivation. **Suggested shape:** a real reproduction before any further fix.
Without one, the third fix will aim at the wrong store too.

### 5. The escalation ladder escalates on the wrong signal

`skills/aet-evolve/references/escalation-ladder.md` maps recurrence 1 →
document, 2 → checklist, 3 → review lens, 4 → executable gate. Both recent
learnings sit at recurrence 1, so the prose-only fixes were the ladder working
as designed. The defect is the trigger, not evolve's leniency:

- **Rung should be chosen by check-shape, not incident count.** Whether a
  requirement is mechanically decidable is knowable at the first incident.
  Incident count charges three incidents of tuition for it.
- **The counter undercounts by construction.** Ladder step 1 matches on
  `trigger` keywords, which are artifact names (`.agents/ledger.jsonl`, `manual
  edit`). The ledger learning is the same *class* as the earlier
  work-queue.json hand-edit warning it explicitly cites, but no trigger
  overlaps, so it logged as recurrence 1. Class-keyed matching puts it at rung
  2+ immediately.

This is the ADR-worthy piece: it changes how `aet-evolve` accepts a fix.

### 6. The narrow drift lint

Not "MUST without a referenced gate" — most `MUST`s in the skill corpus are
judgment-shaped, and flagging them all trains suppressions. The enforceable
version is drift detection: **flag prose naming a schema field, CLI flag, or
path that code owns.** Host: `docs_lint.py` with `.agents/doc-rules.yaml`
(ADR-040, documentation invariants as data).

Evidence it works: `scripts/skills-lint` already validates CLI flags mentioned
in skills against the real CLI, and it caught a draft in this session citing
`aet gate submit --help` — a flag that does not exist. Items 1 and 3 show the
target set is wider than `skills/`: the false claims live in module docstrings,
inline comments, `CONVENTIONS.md`, and `WORKFLOW-github.md`.

The class has at least four recorded instances: skill verdict examples omitting
the then-required `tree_hash` while `evidence.SCHEMAS` demanded it (learning
2026-07-14); hand-authored payload instructions in four skills while builder mode
sat undocumented; `aet state audit` named as a ledger rebuild that does not exist
(`c0d35b1c`); and the ADR-055 claims in item 1. Each was prose restating a fact
code owned, and each drifted.

### 7. `aet state set-stage` writes the ledger after the queue is already pushed

`cli/aet_state.py:729-735`: `backend.save()` → `backend.push()` → print → then
the ledger event. A raise between them leaves the queue advanced with no
`stage` event; in the `sprint add` path (`cli/sprint.py:144-158`) it also skips
`projections.on_add()` and `backend.close()`. Pre-existing, but corruption is
now a reachable raise, so it is easier to hit. Verified by smoke test: the
command printed `Set stage for smk-01: qa-complete` and *then* refused on the
ledger. Belongs with `docs/prds/single-ledger-closure-prd.md`.

### 8. Two deliberate decisions worth re-taking

- **`aet gate submit` swallows ledger corruption as a warning**
  (`cli/gate.py:388`, `except Exception` → print, exit stays 0). Deliberate per
  ADR-057 ("advisory provenance"), but a *corruption* warning is the silent
  shape being removed. If item 1 is wired, advisory is no longer defensible.
- **Whether an unread store should fail closed.** `01ed6e81` makes a store with
  no readers refuse to open when damaged, justified by ADR-033 §3 and ADR-055's
  intent. If item 1 is abandoned, revisit: a write-only advisory store blocking
  commands is over-strict. Note the interaction with item 3 — a stricter ledger
  raises the cost of the halt loop for downstream projects.

### 9. Follow-through on what shipped

- **Watch the recovery rate.** Query stage telemetry for records with
  `attempt >= 2`. If verdict recovery fires on most runs, the prompt is not the
  problem and the ask should shrink further — e.g. have the qa stage emit its
  own report file so `--from-pytest` has an input by construction.
- **The 7f6cace learning still records the prompt clause as the fix.** Now
  superseded by builder mode plus recovery. Worth a correcting append, as was
  done for the ledger learning.
- **`.agents/learnings.jsonl.lock` is left on disk by `aet learnings append`**
  and is not in `AET_IGNORED_PATHS` (unlike the ledger's sibling lock, which
  ae-toolkit's own `.gitignore` covers by glob). Same class as item 3; the
  proposed "every file AET writes is registered" test would catch both.
- **Reinstall before trusting `aet` behaviour.** The installed CLI is a
  snapshot; the five files changed on this branch differ from what `aet` on
  PATH executes until reinstall.

## Defects from the poc-03a/03b/05 batch

A downstream session running that batch against 1.8.0 produced
`aet-toolkit-defects.md` (13 items, D1–D13). Its D4 and D6 are items 3 and 1
above, found independently. Its D13 corrected item 2 of this report. Everything
load-bearing below was re-verified against the source tree; four fixes exist
only as edits to that session's `site-packages` tree and are **not upstream**.

### 10. Fixed here: the stage-group prompt contradicted itself (D1)

`build_stage_group_prompt` opened with "Execute the following consecutive
pipeline stages in order … Do not proceed past the final stage listed", then
appended one block per stage carrying the **single-stage** wording verbatim:
"Execute only this stage. Do not proceed to subsequent stages." The agent obeys
the nearer, more specific instruction, so a group session completes its first
stage and the next gate fails closed on a later stage's verdict. Field-observed
on `poc-03a`, with the child stating it stopped deliberately — and
**nondeterministic**: another group in the same run completed both stages, so a
green batch is no evidence of absence.

Fixed in this branch: the per-stage block now says to finish the stage and
continue to the next block in the prompt. The single-stage builder's copy is
correct and was deliberately left alone; a test now pins both.

This is the one item in this report whose fix is legitimately more prose — a
prompt is irreducibly prose, and "do every stage in this session" is not
checkable from inside it. The mechanical backstop already exists (the group gate
checks each stage's verdict); what was missing is covered next.

### 11. Fixed here: verdict recovery asserted a premise the orchestrator cannot check

The recovery session added in `328f7b2c` told the agent "its work is complete and
committed". D1 makes that reachable and false: when a group session skips a later
stage, "verdict missing" and "stage never ran" are indistinguishable at the gate,
so recovery would have asked for a verdict on work that never happened — a false
premise in a prompt, inviting a fabricated pass. The prompt now states only that
the session ended without writing the verdict, tells the agent to establish what
happened from the branch's commits, and requires `--verdict fail` naming the
omission if the stage was not performed. Ambiguity becomes a reported signal
instead of a coerced pass.

### 12. The plan overlay clobbers an advanced worktree plan (D2) — open

`_copy_deferred_files` (`worktree.py:353`) overlays `docs/plans/` from the main
checkout into the worktree "regardless of git state", and `copy_untracked_files`
runs unconditionally on every task start including a resume
(`cli/orchestrator.py:1282`). ADR-054 deliberately leaves the main copy
un-advanced mid-sprint, so a resume regresses the worktree's plan footer to the
entry stage and presents a diff deleting the stage notes — 166 lines on
`poc-03a`, after which the pipeline re-ran `aet-tdd`, `aet-implement`, `aet-qa`
and `aet-review` over already-reviewed code at a measured **~$24**.

Compounded by item 2's `_record_stage` no-op: with the task record's stage always
null under `git-refs`, the clobbered footer is the *only* stage input.

Their mtime-guard fix is sound but changes overlay semantics (an operator edit no
longer wins if the worktree copy is newer), so it wants a test and an ADR note
against ADR-054 rather than a quiet patch.

### 13. The halt message discards its own diagnosis (D5) — open, one-liner

`check_base_hygiene` returns a bare `"Working tree is dirty"`
(`worktree.py:620`) while holding `dirty_lines`. For an unattended run that
cannot ask, the entire cost of the halt is that the operator must reproduce
`git status` by hand and cross-check two allow-lists. Naming up to N offending
paths makes the halt self-diagnosing. Squarely on this report's theme: a
mechanical check that computed the answer and threw it away.

### 14. Only `verdict` is value-checked in evidence payloads (D12) — open

`aet gate submit` stamps `tree_hash` only when the key is **absent**
(`cli/gate.py:378`), and `validate_verdict` type-checks every field but
value-checks only `verdict` (`evidence.py:167-186`). So a payload carrying
`"tree_hash": "pending"` type-checks as `str`, suppresses the real stamp, and is
accepted — silently defeating ADR-025's freshness comparison, whose entire input
is that hash. Builder mode dodges it (the key is always absent, so the stamp
always happens), which is another reason to prefer it, but the `--evidence` path
remains open. Fix: stamp unconditionally, or value-check the field. Cheap.

### 15. Offline paths, and a state-machine gap (D7, D8, D10, D11) — open

Outside this report's theme but verified and worth a defect backlog:

- **D7** — `_run_git` defaults to `check=True` (`cli/ship.py:348`), so
  `_fetch_origin()` (`:353`, called at `:455`) raises on a repo with no remote.
  Every `aet ship` subcommand runs the pre-merge gate, so `gate`, `open`, `merge`
  and `split` all die identically. The `git-refs` backend's own `fetch()` is
  deliberately remote-safe; ship bypasses that guard.
- **D8** — `cmd_record_merge` runs an unconditional `git fetch origin` and
  returns 1 on failure (`cli/aet_state.py:1308`), so no invocation succeeds
  offline, while `aet state transition` handles the same case correctly.
- **D10** — `_BATCH_ACTIONABLE_STATES` includes `in_progress` on the documented
  assumption that such a task "has a live child" (`cli/orchestrator.py:1931`),
  but `get_next_ready_task` spawns only `ready`. A task whose child died is
  therefore neither run nor given up on. `aet state reset` derives from git, and
  a worktree with commits derives `in_progress`, so it converts a visibly-failed
  task into a silently-stuck one; `aet state transition failed ready` is the
  correct recovery.
- **D11** — an `aet status` that reported an empty queue while
  `refs/aet/tasks/*` held five tasks, alongside a stale
  `.agents/work-queue.json.lock`. Unreproduced and self-resolving, so not
  actionable as stated, but a fail-open read on the authoritative store invites
  destructive "recovery" such as `aet init-queue`. Worth reproducing before
  filing.

### 16. `AET_REPO_ROOT` carries two incompatible meanings (D9, and worse) — open

Their D9: `aet setup verify` resolves the wrong repo root. Verified.
`_repo_root()` (`cli/setup.py:29`) returns *the AE Toolkit's* root — its docstring
says so, and `setup link` needs it to find `skills/`. Line 310 reuses it to locate
**the user's project** config (`repo_root / ".agents" / "aet-config.json"`), so
under a venv install it points inside `site-packages`, the project config is never
found, and `verify` prints built-in defaults as though they were the project's
configuration. The tell is provenance reading `default` / `trunk` instead of
`config (project)`. `install.sh` sets `AET_BIN_DIR` but not `AET_REPO_ROOT` for
the `verify` step (`:192`), so the fallback is what runs.

The underlying defect is larger than the one call site. **`AET_REPO_ROOT` means
two different things to two readers:**

- `cli/setup.py:38` reads it as *the toolkit's* root, and `scripts/install.sh:197`
  feeds it exactly that (`REPO_DIR="$AET_DATA_DIR/repo"`) for `setup skills`.
- `project_id.py:21` reads it as *the project's* root, and
  `cli/orchestrator.py:2895` feeds it exactly that — which is what item 2's whole
  launch-mode split turns on.

So the same variable is deliberately set to two different values by two callers
and consumed by two functions that each assume their own. `aet setup skills` run
inside an orchestrated session would link skills from the project directory
instead of the toolkit. This is the same shape as the two senses of "ledger" in
item 1: one name, two referents, no enforcement — except here the collision is in
a live environment variable rather than in prose, so it fails silently instead of
merely misleading. Fix: two distinct variable names, and a test that pins which
reader owns which.

### Corrections to that document

- **D6 claims `cli/sprint.py:148` "reads it for settled-ness".** It writes a
  `cut` event; `read_events()` has no production caller (item 1). The
  "load-bearing" premise is what justifies their "keep tracking the ledger"
  recommendation, and it does not hold — tracking it buys no durability today and
  costs the hygiene halt.
- **D13's mechanism was inferred, not tested.** It is right for `aet run` and
  wrong for `run-one`; the difference is `AET_REPO_ROOT` (item 2). My own earlier
  claim had the same shape of error in the other direction.
- **D4's "once the ledger is tracked"** understates it: hygiene runs
  `--untracked-files=all`, so an untracked ledger halts the run too.
- **D8's "returns 1 before it ever reads `--merge-commit`"** is imprecise — the
  value is read at `:1305`, just unused before the early return.

## Their four venv patches: which are now upstream

`aet-toolkit-defects.md` records four fixes applied only to that session's
`~/.local/share/ae-toolkit/venv/.../aet/` tree — unversioned, unreviewed, and
reverted by the next upgrade. Status against this branch:

| Their patch                        | Upstream here          | Action for them                          |
| ---------------------------------- | ---------------------- | ---------------------------------------- |
| D1 group-prompt wording            | **Yes** (`29601183`)   | Drop the local patch after release       |
| D5 halt message names paths        | No (item 13)           | Keep until taken upstream                |
| D4 ledger in `AET_IGNORED_PATHS`   | No — held (item 3)     | Keep; it also needs the deferred split   |
| D2 plan-overlay mtime guard        | No (item 12)           | Keep, but it is a semantics change       |

Their proposed remedy — wiring `deny-toolkit-venv-writes.sh` via
`permissions.deny` plus a `PreToolUse` hook so the venv is read-only while still
readable for diagnosis — is the right shape and is theirs to enable; it is
recorded here only so the dependency is visible. The durable half is upstream
releases, which is what items 12–16 are for.

## Closed — do not reopen

**Deriving the qa verdict from observed test execution.** Foreclosed by
ADR-051: the observed wire stream carries command, timestamps, and exit code
and "never knows how many tests were in the run"; counts exist only on the
claimed record, and counting a claimed record as a passing run "double-counts
the verdict as evidence for itself". ADR-050 makes the wire reader kimi-only,
so under the claude adapter there is no observed stream at all. Synthesizing
the verdict would require the estimation ADR-031 forbids.

The realized alternative was to **shrink the ask, not remove it**: builder mode
reduces the qa payload from 11 schema fields to a verdict, a summary, and four
measured counts. Shipped in `45e788ef`.

**Moving the ledger out of the tree via backend configuration.** No such
configuration exists (item 1). Any recommendation of the form "switch to the
git-refs backend to make this go away" is wrong.

## The rule, as it now reads

Prose must never be the sole carrier of a machine-decidable fact, **and must
never restate a fact code owns** — it should name where the fact lives. Two
questions at authoring time:

1. Is this decidable from repo state or command output? → put it on a code path.
2. Does code already own it? → point at it; do not copy it.

Items 1–3 sharpen it with a third failure mode the original review did not
name: **a fact that code owns in one place, and a second place that recomputes
it.** Item 2 is that defect (four derivations of one path), item 3 is its
inverse (one shared constant, one file forgotten). Neither is a prose problem
and neither would be caught by auditing `skills/`. ADR-023 already solved the
general form for verdict paths; the lesson is that a single-derivation rule
holds only for the store it was written about, unless something enforces it for
the next one.
