---
id: cfg-02-configure-writer
size: S
blocked_by:
  - cfg-01-config-resolution-overhaul
pipeline: standard
status: queued
security_review: required
security_review_reason: new write surface for persisted config values; write-time validation is the guard against persisting a mode the resolver will reject
docs_sync: required
docs_sync_reason: the configure command's documented key set and scope flag change; CONVENTIONS.md config section must match
---

# Plan: `aet configure` Writer — All Keys, Scoped Writes

## Context

- PRD: `docs/prds/aet-config-file-overhaul-prd.md` (R-5)
- Extends `src/aet/cli/configure_backend.py`, which today writes only
  `task_backend` (in-tree or `--external-config`). After cfg-01 the in-tree
  file is `.agents/aet-config.json`.
- PRD open question (settled here): keep the command name `configure-backend`
  or rename to `aet configure`. **Decision: rename to `aet configure`** per
  ADR-039's atomic alias-free rename rule — the command stops being
  backend-only the moment it writes `integration_mode`.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- One command writes any subset of the four config keys:
  `aet configure [--task-backend json|git-refs] [--trunk-branch B]
  [--integration-mode pr-per-task|single-pr] [--integration-branch B]
  [--scope project|user]`.
- `--scope project` writes `.agents/aet-config.json` (repo root);
  `--scope user` writes `~/.aet/{config-slug}/config.json`. Default scope:
  `project` when an in-tree config already exists, `user` otherwise (the
  shadow-friendly default).
- Writes are merge-style: unspecified keys keep their current values in the
  target file.
- Write-time validation rejects values the resolver would reject
  (`integration_mode` ∉ `INTEGRATION_MODES`, `task_backend` ∉ known set)
  naming the legal values — no persisted config the reader will fail on.
- `--migrate` (cfg-01) remains available under the renamed command.

## Rejected Alternatives

- **Keeping `configure-backend` and piling flags on it** — rejected: the name
  misdescribes the surface once it writes integration keys; ADR-039 prefers
  the atomic rename over a misleading alias.
- **A separate `aet configure` alongside `configure-backend`** — rejected:
  two writers for one file is a drift source; atomic rename instead.

## Task List

1. ✓ Rename `configure-backend` → `aet configure` (atomic, alias-free, ADR-039);
   update dispatcher wiring and help text — S (traces: R-5)
2. ✓ Add the four key flags + `--scope project|user` with merge-style writes and
   the shadow-friendly scope default — M (traces: R-5)
3. ✓ Write-time validation with legal-values errors — S (traces: R-5)
4. ✓ Tests (see Validation Steps) — S (traces: R-5)
5. Merge branch to main and verify integration — S [Deferred: ship stage]

**Size definitions:** S ≤ 2 hr / ≤ 150 lines; M ≤ 1 day / ≤ 600 lines.

### Floor Check

- [x] Stands alone: the writer is independently shippable once cfg-01 defines
  the file model it writes to.

## Files to Modify

- `src/aet/cli/configure_backend.py` (renamed surface)
- `src/aet/cli/main.py`
- `tests/cli/test_configure.py` (new; supersedes configure-backend tests)

## Validation Steps

- [x] `make validate` passes
- [x] New coverage in `tests/cli/test_configure.py`:
  - `test_writes_each_key_to_project_scope` (unit)
  - `test_user_scope_writes_external_config` (unit, HOME redirected)
  - `test_merge_style_preserves_unspecified_keys` (unit)
  - `test_invalid_integration_mode_rejected_naming_legal_values` (unit)
  - `test_scope_defaults_to_user_when_no_in_tree_config` (unit)
  - `test_old_command_name_is_gone` (unit: `configure-backend` rejected)
- [x] R-trace coverage: R-5 by tasks 1-4; no unknown R-ids
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main` [Deferred: ship stage]

## Rollback Plan

Revert the merge commit; configs already written remain valid JSON in the
locations the (reverted) resolver reads.

---

*Stage: synced*
*Next step: run `aet-ship`*
