---
id: nc-03c-ship-unify-retire-legacy
size: M
blocked_by:
  - nc-03a-ship-gate-as-code
  - nc-03b-ship-pr-creation-as-code
pipeline: standard
status: queued
security_review: required
security_review_reason: Removes a live PATH symlink and edits the installer's legacy-prune list; a botched prune guard could remove or miss the wrong file.
docs_sync: required
docs_sync_reason: .agents/commands/aet-work.md's false "aet ship opens the PR" claim must be corrected; aet-ship/SKILL.md gets its final trim or retirement.
---

# Plan: Unify aet ship and Retire the Legacy Binary

## Context

Source: `docs/prds/namespace-consolidation-prd.md`, R-3 + the ship-slice of R-7. `Split from: nc-03 (aet ship consolidation)`, final sibling after `nc-03a` (gate) and `nc-03b` (PR creation). This ticket wires the two into one entry point, converts closure from an implicit positional-arg mode into an explicit subcommand, and retires the legacy bare `ship` binary/symlink.

Verified directly (before this pipeline's approval) that `~/.local/bin/ship` and the `aet` dispatcher's `"ship"` entry both resolve to the exact same file (`aet-ship/bin/ship`, relocated to `src/aet/cli/ship.py` by `pkg-06`) — there is no second implementation to reconcile, only a redundant PATH entry and a doc that describes them as if they were different tools. `.agents/commands/aet-work.md:42` currently states "`aet ship` opens the PR" while lines 56-70 send closure to a *separate*-sounding bare `ship <task-id> <plan-path>` — the collision this ticket resolves is in the docs and the PATH, not in the underlying logic.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] N/A — no defect redirect needed

## Task List

1. Wire `aet ship` (no subcommand) to run `gate` then `open` in sequence, matching the SKILL.md's current default front-to-back execution through PR creation — M (traces: R-3)
2. Convert the closure invocation from an implicit positional-arg mode (`ship <task_id> <plan_file>`) into an explicit `aet ship close <task_id> <plan_file>` subcommand, reusing the existing `aet-state` `record-merge` logic unchanged — S (traces: R-3)
3. Confirm (verification check, not a fix) that `aet ship close` and the legacy bare `ship <task_id> <plan_file>` invocation resolve to the same underlying script — no behavioral gap exists to reconcile before the bare entry point is removed — S (traces: R-3)
4. Remove the legacy `~/.local/bin/ship` symlink and add `"ship"` to the `LEGACY_NAMES` tuple in the `aet` dispatcher (its post-`pkg-06`/`pkg-04` location) so `aet install` prunes it going forward — S (traces: R-3, R-7)
5. Decide and apply aet-ship's SKILL.md final disposition: reduce to judgment residue (only if a genuine judgment call survives steps 1-15's promotion — e.g. deciding whether to proceed on an ambiguous merge-verification failure) or retire the file entirely — S (traces: R-3)
6. Rewrite `.agents/commands/aet-work.md`'s ship section: replace the false "`aet ship` opens the PR" framing and the separate-sounding bare-`ship`-closure description with the actual unified workflow (`aet ship` = gate + open; `aet ship close` = post-merge closure) — S (traces: R-3, R-7)
7. Add a grep-guard regression test (`tests/test_ship_legacy_removed.py`) confirming no live reference to a standalone `ship` binary or `~/.local/bin/ship` symlink remains in canonical docs or skills, per the gib-06 transition-vehicle mechanism — S (traces: R-3)
8. Verify the acceptance criterion directly: `which ship` returns nothing after a fresh `aet install` — S (traces: R-3)
9. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] This is not one of several near-identical additions.
- [x] The diff is expected to exceed 3 files or 50 lines.
- [x] The work cannot share a branch/PR with `nc-03a`/`nc-03b` — it depends on both landing first and is the ticket that actually satisfies R-3's/R-7's user-visible acceptance criteria.

## Rejected Alternatives

- **Keeping closure as a bare positional-arg mode instead of an explicit `close` subcommand** — rejected: leaving it positional keeps the exact ambiguity (`aet ship <task-id> <plan-path>` reads like an error, not an action) that made the docs describe it as a separate tool in the first place.
- **Deciding aet-ship's SKILL.md residue-vs-retirement question in `nc-01` (the taxonomy ADR)** — rejected: this is a scope/architecture decision about *this specific skill's* remaining content, not a naming decision; R-3's own acceptance criterion assigns it here, not to the ADR.

## Files to Modify

- `src/aet/cli/ship.py`
- `aet-work/bin/aet` (or its post-pkg-04 relocated home) — `LEGACY_NAMES`
- `aet-ship/SKILL.md`
- `.agents/commands/aet-work.md`
- `tests/test_ship_legacy_removed.py` (new, grep-guard)

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: R-3 and the ship-slice of R-7 covered by tasks 1–8; no unknown R-ids cited
- [ ] Named tests per new file: `tests/test_ship_legacy_removed.py` — asserts `"ship"` is in `LEGACY_NAMES`, asserts no canonical doc or live `SKILL.md` references a bare `ship` invocation, asserts `aet ship close` produces identical output to the pre-change positional-arg call on a fixture repo
- [ ] Test types: unit test (`LEGACY_NAMES` membership, grep-guard over `docs/` and skill directories); integration test (`aet install` on a scratch `$HOME` fixture, then `which ship` returns nothing)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

`git revert` the merge. This restores the bare `ship` symlink's prune-exemption (it stops being pruned by `aet install`, but the symlink itself was already removed by this ticket — a fresh `ln -s` would be needed to fully restore the pre-change PATH state, noted here so a revert isn't assumed to be silent). `.agents/commands/aet-work.md` and `aet-ship/SKILL.md` revert to their prior text.

## Pipeline

`pipeline` controls how the orchestrator runs this plan. It is set in the
frontmatter and is read by `aet run`/`run-one`.

| Value      | Behavior                                            |
| ---------- | ---------------------------------------------------- |
| `standard` | Default grouping (TDD→implement→QA, review, CSO)    |
| `minimal`  | All stages in one session; fastest, least isolation |
| `full`     | One session per stage; slowest, maximum isolation   |

`standard`: removes a live PATH symlink and edits the installer's prune list — enough real-world blast radius to warrant the default grouping rather than `minimal`.

---

*Stage: plan-approved*
*Next step: run `aet-work`*
