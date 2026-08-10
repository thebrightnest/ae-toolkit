---
id: epi-01-base-branch-resolver
size: M
blocked_by: []
pipeline: standard
status: merged
security_review: skipped
security_review_reason: reads git refs and existing config files; introduces no network, credential, or filesystem-write surface
docs_sync: required
docs_sync_reason: introduces trunk_branch, integration_branch, and AET_WORK_BASE_BRANCH as user-facing configuration
---

# Plan: Resolve the base and trunk branches instead of assuming `main`

## Context

- PRD: `docs/prds/non-trunk-integration-workflow-prd.md` (R-1, R-2, R-3)
- ADR: `docs/adr/044-base-branch-is-configured-not-assumed.md`
- Bug: `docs/bugs/2026-07-22-orchestrator-base-branch-hardcoded.md`

This is the foundation for `epi-02`, which threads the resolved values through
every consumer. This plan adds the resolver and its configuration; it changes no
existing caller, so it is behavior-neutral on its own.

R-5 (surfacing the resolved trunk and its provenance in `aet setup verify`) is
**not** in this plan. That command does not exist yet — it is created by
`fic-02-installer-bootstrap-boundary` under a different PRD. Blocking the
resolver on unrelated installer work would stall everything downstream of it, so
R-5 is carried by `epi-11`, which holds the cross-PRD blocker. The resolver
still returns provenance here; only its display is deferred.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

The defect this unblocks is recorded in the bug report above. This plan is the
enhancement half — new configuration and a new resolver — and introduces no fix
by itself.

## Locked design

- **Two names, not one.** `trunk_branch` (final merge target) and
  `integration_branch` (what worktrees are cut from) are distinct. They are equal
  in Scenario A. Collapsing them into a single `base_branch` is the conflation
  ADR-045 has to undo and is explicitly rejected.
- **Resolution order is fixed** and must be expressed as data, not as nested
  conditionals per consumer:
  - `trunk_branch`: config → `git symbolic-ref refs/remotes/origin/HEAD` → `main`
  - `integration_branch`: `--base` → `AET_WORK_BASE_BRANCH` → config
    `integration_branch` → `trunk_branch`
- **`integration_branch` is a per-run input.** The config key exists only as the
  lowest-precedence fallback. Do not present it as the normal way to set the
  branch (ADR-044 decision 1).
- **No second config reader.** `trunk_branch` and `integration_mode` go through
  `resolve_config()` in `src/aet/backends/factory.py:59`, which already
  implements the external-first chain. Do not read `.agents/aet-work.json`
  directly — `worktree.py:215` and `:254` already do that for
  `symlink_dependencies` and are the pattern to avoid, not to copy.
- **Detection returns its provenance.** The resolver reports whether the trunk
  came from config, detection, or fallback, because R-5 needs to display it and
  a silent fallback to `main` on a `dev` repo is the failure mode ADR-044 flags
  as a risk.
- `symbolic-ref` output is `refs/remotes/origin/<name>`; strip the prefix. A
  non-zero exit means unset, which is the fallback case, not an error.

## Task List

1. Add `src/aet/branch_ref.py` with `resolve_trunk_branch(repo_root, config)`
   and `resolve_integration_branch(repo_root, config, cli_base=None)`, each
   returning the ref and its provenance — M (traces: R-1, R-2)
2. Read `trunk_branch` and `integration_branch` via the existing
   `resolve_config()` chain rather than a new file reader — S (traces: R-3)
3. Honour `AET_WORK_BASE_BRANCH` at its documented precedence, above the config
   key and below an explicit `--base` — S (traces: R-2)
4. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 100 lines; M ≤ 1 day / ≤ 200 lines; L must be
re-evaluated.

### Batching Check

- [x] Not one of several near-identical additions — one resolver, one precedence
      chain
- [x] The diff is expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with `epi-02` — it could, but `epi-02` is a
      wide-blast-radius rename across five call sites and two modules; keeping
      the new resolver reviewable on its own is worth the extra branch

## Rejected Alternatives

- **A module-level `BASE_BRANCH` constant** — rejected: one value for two
  concepts. It fixes the literal `main` and preserves the conflation.
- **Read `.agents/aet-work.json` directly, as `worktree.py` already does** —
  rejected: bypasses the external-first precedence ADR-036 established, so an
  operator's `~/.aet/{slug}/config.json` would be ignored for these keys but
  honoured for `task_backend`.
- **Derive the integration branch from the operator's current branch** —
  rejected in ADR-044: it makes an implicit input decide where code lands.
- **Cache the detected trunk in the queue file** — rejected: the queue is
  ephemeral (ADR-013) and would then carry configuration, which is exactly the
  coupling ADR-036 removes.

## Files to Modify

- `src/aet/branch_ref.py` (new)
- `src/aet/backends/factory.py`
- `tests/test_branch_ref.py` (new)

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] New source coverage: `tests/test_branch_ref.py` covers each precedence
      rung for both refs, including `AET_WORK_BASE_BRANCH` beating the config
      key and losing to an explicit `--base`
- [ ] A repo whose `refs/remotes/origin/HEAD` names `dev` resolves trunk to
      `dev` with provenance `detected`, and with the ref unset resolves to
      `main` with provenance `fallback`
- [ ] `resolve_config` is the only config reader touched; no new direct read of
      `.agents/aet-work.json` is introduced
- [ ] The resolver returns provenance (`config` / `detected` / `fallback`) for
      both refs, so `epi-11` can display it without re-deriving
- [ ] R-trace coverage: R-1 by task 1; R-2 by tasks 1 and 3; R-3 by task 2.
      R-5 is deferred to `epi-11` (see Context)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. Nothing calls the resolver until `epi-02`, so rollback is a
pure deletion with no behavioral change to undo.

## Pipeline

`standard`.

---

*Stage: merged*
*Next step: run `aet-ship`*
