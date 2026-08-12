# PRD: Single-Source Enforcement — Wire the Authoritative Ledger, Register What We Write

## Overview

A review of two prose-only fixes turned into an audit of every place the toolkit
states a fact it does not enforce (`reports/2026-08-12-prose-vs-enforcement-open-items.md`).
The audit found one architectural gap and a family of defects that share a shape:
a fact that code owns in one place, and a second place that restates or
recomputes it.

The architectural gap is ADR-055. It decides that settled-ness lives in the
append-only content-addressed ledger and that the ledger travels with the repo as
pushed git refs. Neither half was built: `Ledger.read_events()` has no production
caller, no backend touches `.agents/ledger.jsonl`, and the real settled-ness
authority (`_is_settled_from_authority`) reads a settled-history log, git
ancestry, and the plan footer. Four files assert the unbuilt behaviour as fact.
This PRD wires the decision as written, rather than amending it.

Wiring it promotes several defects from cosmetic to blocking. A ledger nothing
reads can be fragmented, unregistered, or corrupt without symptom; a ledger that
answers "is it done?" cannot. So this PRD also single-sources the ledger's
resolution, makes stage events fire under every backend, registers every file the
toolkit writes, and closes the value-check and naming collisions the audit found
alongside them.

## Goals

- Settled-ness is answered by exactly one authoritative store pair — the ledger
  plus git ancestry — as ADR-055 decided, with the plan footer removed from the
  authority set.
- The ledger travels between machines, satisfying ADR-055 decision 4's premise
  (one operator, several machines).
- No downstream project halts because the toolkit wrote a file it never
  registered; a test makes the next such file impossible to forget.
- Every fact code owns has exactly one owner: one ledger resolver, one meaning per
  environment variable, one stamper for `tree_hash`.
- `aet-evolve` escalates by whether a requirement is mechanically decidable, so
  the next instance of this class is not answered with prose.

## Non-Goals

- **The 2026-08-11 "settled tasks disappeared" incident.** Its recorded mechanism
  is impossible (nothing reads the ledger), so it has no confirmed cause. It
  needs a reproduction through `aet-bug-report` before any fix. Wiring the ledger
  raises its priority but does not diagnose it.
- **`set-stage` write-ordering atomicity.** The queue is saved and pushed before
  the ledger event is written, so a raise between them leaves them disagreeing.
  That belongs to `docs/prds/single-ledger-closure-prd.md`.
- **Plan-overlay semantics.** `_copy_deferred_files` clobbering an advanced
  worktree plan is a real and expensive defect, but fixing it changes ADR-054's
  deferral model and needs its own PRD.
- **Offline and state-machine defects.** `aet ship`'s unconditional fetch,
  `record-merge`'s fetch, the batch loop's unadopted `in_progress` tasks, and
  `aet status`'s fail-open empty read are a separate defect backlog.
- **Removing the in-tree ledger for existing installs by force.** Migration is
  offered and documented; no user's provenance is deleted on upgrade.

## Requirements

- **R-1**: Settled-ness is derived from ledger events plus git ancestry.
  `_is_settled_from_authority` reads the ledger; the plan-footer input is removed
  from the authority set, and its docstring matches what it does.
- **R-2**: The content-addressed ledger is stored in pushed git refs, outside the
  working tree, and is fetched and pushed on the same boundaries as the queue.
- **R-3**: Every ledger writer resolves the store through one exported
  derivation. No call site computes its own path, and none resolves differently
  by launch mode, backend, or current working directory.
- **R-4**: Stage events are recorded under every configured backend.
  `_record_stage` routes through the backend instead of probing for a hardcoded
  JSON file, so a task record's stage is never silently left null.
- **R-5**: A ledger that cannot be read or written fails the command that needed
  it, rather than warning and exiting zero.
- **R-6**: Every file the toolkit writes under `.agents/` is registered in
  exactly one hygiene declaration, and a test fails when a writer is added
  without registering its file.
- **R-7**: "Do not track this" and "tolerate this dirty" are separate
  declarations with separate consumers. A tracked-but-tool-written file can be
  tolerated without being gitignored.
- **R-8**: A hygiene halt names the paths that caused it.
- **R-9**: The toolkit root and the project root are carried by two distinctly
  named environment variables, each with exactly one reader contract.
- **R-10**: `tree_hash` is stamped by code on every verdict write; a
  caller-supplied value cannot suppress the stamp.
- **R-11**: Documentation, docstrings, and comments describing ledger storage and
  transport match the implementation, and both senses of "ledger" are defined in
  the CONTEXT.md glossary.
- **R-12**: `aet-evolve` selects an escalation rung by whether the requirement is
  mechanically decidable, not by incident count, and recurrence is keyed to
  defect class rather than artifact name.
- **R-13**: A lint flags documentation prose that names a schema field, CLI flag,
  or file path owned by code, so a restatement cannot drift unnoticed.

## User Stories

- As an operator running AET across a laptop and a cloud box, I want settled-ness
  to travel with the repo so a fresh clone never resurrects merged work
  (satisfies: R-1, R-2).
- As an operator adopting AET in a new project, I want `aet setup` to leave a
  repo that does not halt on its own writes (satisfies: R-6, R-7).
- As an operator whose unattended run halted, I want the halt to tell me which
  paths caused it (satisfies: R-8).
- As a maintainer, I want one place that answers where the ledger lives, so a new
  writer cannot invent a fifth answer (satisfies: R-3, R-4).
- As a maintainer, I want a verdict's freshness fingerprint to be unforgeable by
  a payload field (satisfies: R-10).
- As a maintainer diagnosing `aet setup verify`, I want an environment variable to
  mean one thing (satisfies: R-9).
- As a maintainer running a retro, I want the escalation rung chosen by whether
  the rule is checkable, so a mechanical requirement is never answered with a
  warning in prose (satisfies: R-12, R-13).

## Acceptance Criteria

- [ ] `_is_settled_from_authority` reads ledger events; removing the plan footer
      from its inputs does not change the answer for any task in the corpus
      (satisfies: R-1)
- [ ] A ledger event written on one clone is visible on a second clone after a
      fetch, with no working-tree file required (satisfies: R-2)
- [ ] A test asserts every ledger call site resolves the same store from inside a
      worktree, under `aet run` and `aet run-one`, under both backends
      (satisfies: R-3)
- [ ] Running a task under the `git-refs` backend leaves a non-null stage on the
      task record and a `stage` event in the ledger (satisfies: R-4)
- [ ] `aet gate submit` exits non-zero when the ledger is corrupt (satisfies: R-5)
- [ ] A test enumerates the toolkit's `.agents/` writers and fails when one is
      unregistered; adding an unregistered writer fails CI (satisfies: R-6)
- [ ] Appending a learning does not make `check_base_hygiene` report a dirty tree,
      and `.agents/learnings.jsonl` remains tracked (satisfies: R-7)
- [ ] A dirty-tree halt prints the offending paths (satisfies: R-8)
- [ ] `aet setup verify` reports project config provenance under a venv install
      (satisfies: R-9)
- [ ] A verdict payload carrying `"tree_hash": "pending"` is written with the
      real stamp or refused (satisfies: R-10)
- [ ] No file asserts refs transport for a store that lacks it; CONTEXT.md defines
      both senses of "ledger" (satisfies: R-11)
- [ ] A first-occurrence learning whose requirement is mechanically decidable is
      escalated past documentation on the first pass (satisfies: R-12)
- [ ] The drift lint flags a doc line naming a schema field that code owns, and
      does not flag judgment-shaped prose (satisfies: R-13)

## Technical Notes

- **Refs layout is the open design decision.** ADR-055 already records that a
  chained `content_hash` over a changing ref set is non-commutative and produced
  irreconcilable conflicts, which is why the queue backend abandoned it. The
  ledger is append-only and commutative by construction (content-addressed ids,
  duplicate writes are no-ops), so a per-event or per-task ref layout preserves
  that property while a single-blob layout does not. `sst-04` settles this in an
  ADR before any storage code is written.
- **Sequencing is load-bearing.** `sst-01` ships first and alone: downstream
  projects halt today, and that fix must not wait on transport design. R-1 cannot
  land before R-4, because a reader over a store that never received `stage`
  events answers wrongly under `git-refs`.
- **R-5 is only defensible after R-1.** ADR-057 deliberately made the gate's
  ledger write advisory ("a ledger write failure must not roll back the verdict").
  That holds while the ledger is unread; it stops holding when the ledger answers
  settled-ness. The change is a consequence of R-1, not an independent opinion.
- **Existing in-tree ledgers must migrate, not vanish.** `~/.aet` and every
  adopting project may hold a working-tree ledger with real events. `sst-06`
  imports them into refs by content address, which is idempotent by construction.
- **R-3 shrinks after R-2** but is not obviated: refs need a single resolver as
  much as paths do, and the resolver is what lets `sst-05` swap storage without
  touching five call sites.

## Open Questions

- Should the refs-backed ledger push on every write, or only at the closure
  boundary as the queue does? ADR-055 makes push mandatory at closure and
  best-effort elsewhere; `sst-04` should confirm the ledger inherits that rule
  rather than inventing its own.
- Does removing the plan footer from the settled-ness authority set (R-1) leave
  any recovery path that depended on it — specifically `aet state heal` and
  `init-queue` on a repo whose refs were never fetched?
- Should `AET_REPO_ROOT` be retained as a deprecated alias for one of the two new
  variables (R-9), or removed outright? Retaining it keeps existing installer
  invocations working; removing it makes the collision unrepeatable.
