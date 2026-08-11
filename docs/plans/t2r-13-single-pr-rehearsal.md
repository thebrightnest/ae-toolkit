---
id: t2r-13-single-pr-rehearsal
size: M
work_class: normal
blocked_by: []
pipeline: standard
security_review: required
security_review_reason: adds a real third-party npm dependency install to the test surface
docs_sync: required
docs_sync_reason: R-12's acceptance criterion must sync against the as-built rehearsal and the change_scope trigger
---

# Plan: `single-pr` Rehearsal — Non-Trunk Integration Branch, Shadow Config, Real Dependency Install

## Context

PRD: `docs/prds/structural-review-tier-2-prd.md` (R-12). The `single-pr`
integration mode is fully implemented (ADR-045; `src/aet/cli/orchestrator.py`
single-pr block at `process_task`, `_integrate_single_pr_task`,
`src/aet/integration_lock.py`) but verified only through
`tests/orchestrator/test_single_pr_loop.py`, which runs the `_FAKE_ADAPTER`
echo adapter with the stage runner mocked out and no dependency install. The
configuration the hardest client repos actually run — `single-pr` + non-trunk
integration branch + shadow config + heavy dependencies — shares almost no
code path with the dogfooded config (`pr-per-task` + trunk + team config + no
deps). ADR-045 names this dual meaning of "done" as the most likely source of
future bugs; R-12 rehearses the production-shaped configuration before the
next production incident does.

Precedent: the nightshift rehearsal (`tests/orchestrator/test_nightshift_rehearsal.py`,
`tests/fixtures/nightshift/{healthy,deterministic-failure,stall}.md`, and an
inline `rehearsal.json` workflow) runs a real `run_batch` loop against a temp
repo with a fake `claude` CLI. This plan follows that shape exactly, swapping
the fixture behavior for a real `npm ci` install and the queue semantics for
`single-pr` integration.

Decisions this plan is scoped against:

+ **ADR-045** — `single-pr` semantics: integrate into the epic integration
  branch locally, push only that branch, "done means integrated".
+ **ADR-048** — two-layer config: the shadow layer is
  `~/.aet/{slug}/config.json`, resolved by
  `src/aet/backends/factory.py:resolve_config` (env `AET_WORK_CONFIG` →
  shadow → in-tree). The rehearsal must resolve config from the shadow layer,
  not an in-tree `.agents/aet-config.json`.
+ **ADR-049** — validation scope is derived from the change set in
  `src/aet/change_scope.py`, never in Makefile shell. The rehearsal trigger
  wires into `change_scope.targets()`, not a shell grep.
+ **ADR-055 (post-slc state)** — plan frontmatter carries no `status`;
  `aet gate submit` is the sole verdict writer; closure is one transaction.
  This plan adds no verdict, stage, or closure machinery and reintroduces no
  prose writer around any of them.

Recorded assumptions and collisions:

+ **Fixture ecosystem (PRD Open Question 4):** resolved in favor of **npm**
  (`npm ci`). The node toolchain is near-universal (this machine: node
  v22.20.0, npm 11.14.1) and `npm ci` exercises the full real-install path
  (lockfile fetch, extract, postinstall) with one ecosystem. **composer is the
  named follow-up** — consumer evidence centers on Laravel/composer, but the
  composer fixture belongs with item 0's `worktree_setup` (Tier 1, tracked
  separately); per the PRD, this rehearsal exercises item 0 but does not
  implement it.
+ **Ledger:** `src/aet/ledger.py` taxonomy is `{cut, stage, verdict, land}`.
  This plan adds no new state-producing mechanism — the rehearsal *observes*
  states the production single-pr path already writes through the existing
  queue/state machinery — so no new ledger events are emitted. Nothing here
  wraps `aet gate submit` or `aet state set-stage`.
+ **No sibling collision:** the parked `cov-02`/`cov-04` plans and the
  R-6/R-7 lens plans also touch `change_scope`, but they add gate lenses, not
  test-target wiring; the trigger hook here is a small additive union that a
  later lens change can extend without conflict.

## Intake Triage

+ [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
+ [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Fixture npm package under `tests/fixtures/single-pr/npm/`: `package.json`
   pinning one tiny runtime dependency, a committed reproducible
   `package-lock.json` (generated with `npm install --package-lock-only` and
   verified by a clean `npm ci`), and `index.js` that requires the installed
   dependency and writes its result to a marker file — S (traces: R-12)
2. Fixture plans `tests/fixtures/single-pr/first-task.md` and
   `tests/fixtures/single-pr/second-task.md` (frontmatter `workflow:
   rehearsal`; second task `blocked_by` the first), modeled on
   `tests/fixtures/nightshift/*.md` — S (traces: R-12)
3. `tests/orchestrator/test_single_pr_rehearsal.py` (new, marked
   `xdist_group("process-group")` to serialize with the nightshift rehearsal):
   temp repo + bare origin on the nightshift pattern; non-trunk integration
   branch `epic-rehearsal`; **no in-tree config** — `integration_mode:
   single-pr`, `integration_branch: epic-rehearsal`, `trunk_branch: main`
   written to `~/.aet/{slug}/config.json` under a patched `HOME` so the real
   shadow-layer resolution in `resolve_config` is exercised; fake `claude` CLI
   (nightshift pattern) whose healthy path runs a real `npm ci` and
   `node index.js` in the worktree and commits the marker; two-task queue run
   unattended through `orchestrator.run_batch`;
   `AET_INTEGRATION_VALIDATE_CMD="npm ci && node index.js"` so the post-rebase
   validation re-runs the real install; `pytest.skip` with a named reason when
   `npm` is absent from `PATH` — M (traces: R-12)
4. Rehearsal assertions, all observable end states: both tasks reach `merged`;
   `git ls-remote --heads origin` shows only `main` and `epic-rehearsal` (no
   per-task branches); `git log origin/epic-rehearsal` contains both
   `Integrate <task>` squash commits in dependency order; the second task's
   committed marker contains the first task's installed output (proving
   live-tip sequencing through the real install);
   `resolve_integration_mode_with_provenance` reports the shadow layer
   (`config (user)`) for the fixture repo — S (traces: R-12)
5. Trigger wiring in `src/aet/change_scope.py` per ADR-049: add a
   `REHEARSAL_TRIGGER_PREFIXES` set (the single-pr/worktree surface:
   `src/aet/cli/orchestrator.py`, `src/aet/integration_lock.py`,
   `src/aet/worktree.py`, `src/aet/backends/factory.py`) — when the changed
   set intersects it, `targets()` unions
   `tests/orchestrator/test_single_pr_rehearsal.py` into the emitted list
   (additive only; never narrows the fail-safe fallbacks); add the missing
   `("src/aet/integration_lock.py", "tests/orchestrator")` mapping entry;
   extend `tests/test_change_scope.py` with unit tests for the union and the
   new mapping — S (traces: R-12)
6. Merge branch to main and verify integration — S

### Floor Check

+ [x] Stands alone: R-12 is the only Tier 2 move touching rehearsal
  infrastructure; merging it into a lens or context-command sibling would mix
  unrelated subsystems into one PR.
+ [x] Expected diff (~500 lines across one new test module, fixtures, and a
  small `change_scope` hook) materially exceeds branch/PR/review overhead.
+ [x] Cannot share a branch with the R-6/R-7 lens plans: their
  `change_scope` work adds gate lenses on a separate acceptance contract, and
  sequencing them together would couple an unverified-config rehearsal to an
  unrelated gate design.

## Rejected Alternatives

+ **composer for the fixture install** — rejected: the node toolchain is
  near-universal on maintainer machines and `npm ci` covers the real-install
  code path (lockfile fetch, extract, postinstall) with one ecosystem;
  composer is the named follow-up once item 0's `worktree_setup` lands (PRD
  Open Question 4; R-12 ↔ item 0 coupling).
+ **Extend `test_single_pr_loop.py` instead of a new rehearsal module** —
  rejected: that file mocks the stage runner and uses an echo adapter; the
  rehearsal's value is the real `run_batch` loop on the nightshift precedent.
  Mixing real-loop and mocked-loop tests in one module blurs both contracts.
+ **Makefile-shell trigger (`git diff --name-only | grep` in the Makefile)** —
  rejected: ADR-049 decision 2 puts scope decisions in `change_scope` Python,
  not Makefile shell; a shell grep reintroduces a second scoping authority.
+ **A `pytest -m rehearsal` marker as the trigger** — rejected: a marker
  selects only when a human remembers to pass it; `change_scope` already
  computes targets from the change set, so the union hook runs the rehearsal
  with zero operator recall. Direct selection
  (`pytest tests/orchestrator/test_single_pr_rehearsal.py`) covers manual
  runs.
+ **In-tree committed `.agents/aet-config.json` in the fixture repo** —
  rejected: that exercises the team layer; the configuration used in anger is
  the shadow (project-local, uncommitted) layer per ADR-048, which is the
  layer this rehearsal exists to verify.

## Files to Modify

+ `tests/fixtures/single-pr/npm/package.json` (new)
+ `tests/fixtures/single-pr/npm/package-lock.json` (new)
+ `tests/fixtures/single-pr/npm/index.js` (new)
+ `tests/fixtures/single-pr/first-task.md` (new)
+ `tests/fixtures/single-pr/second-task.md` (new)
+ `tests/orchestrator/test_single_pr_rehearsal.py` (new)
+ `src/aet/change_scope.py`
+ `tests/test_change_scope.py`

## Validation Steps

+ [ ] Lint passes (`make lint-py`)
+ [ ] Tests pass (`make test`)
+ [ ] `tests/test_change_scope.py` (unit): a change set touching
  `src/aet/integration_lock.py` (or `src/aet/worktree.py`,
  `src/aet/backends/factory.py`) emits
  `tests/orchestrator/test_single_pr_rehearsal.py` in the target list; a
  change set disjoint from the trigger prefixes does not; fail-safe fallbacks
  (`conftest.py`, shared fixtures, unmapped paths) still force the full suite
+ [ ] `tests/orchestrator/test_single_pr_rehearsal.py` (integration —
  cross-layer: orchestrator + git plumbing + shadow config resolution + real
  npm install): passes end-to-end on a machine with npm; asserts every
  observable end state in task 4
+ [ ] Fixture lockfile is reproducible: `npm ci` in
  `tests/fixtures/single-pr/npm/` succeeds from a clean cache and produces the
  pinned dependency
+ [ ] Skip behavior: with npm removed from `PATH` the rehearsal skips with its
  named reason and does not fail the suite
+ [ ] `python -m aet.change_scope --explain` on this plan's own branch emits
  the rehearsal target (the change touches the trigger surface)
+ [ ] No new source file lacks a named test: fixtures are exercised by the
  rehearsal integration test; `change_scope.py` changes by the
  `tests/test_change_scope.py` unit tests; the rehearsal module is self-testing
+ [ ] R-trace coverage: R-12 covered by tasks 1–5; no task cites another R-id
+ [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge. The rehearsal test, fixtures, and `change_scope` hook are
all additive: the revert deletes them and restores the prior target mapping
with no state to unwind. The fixture `package-lock.json` pins a public npm
package; nothing is published or cached outside npm's normal cache.

## Pipeline

`standard` — the M-size default; the change touches the validation-scope
mechanism (`change_scope`) and adds an external-install test, which argues
against collapsing stages into one `minimal` session.

---

*Stage: implemented*
*Next step: run `aet-qa`*
