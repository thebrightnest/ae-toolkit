---
id: cfg-04-guided-setup
size: M
blocked_by:
  - cfg-02-configure-writer
pipeline: standard
status: merged
security_review: required
security_review_reason: writes config into the user home directory or a shared repo based on interactive choices; scope confusion writes AET config where it should not be
docs_sync: required
docs_sync_reason: the setup flow's documented steps change; aet-setup skill and setup docs must describe the guided config step
---

# Plan: Guided Setup — Scope and Mode in Two Questions

## Context

- PRD: `docs/prds/aet-config-file-overhaul-prd.md` (R-11)
- Today a fresh install reaches a working config only by hand-editing JSON
  after reading CONVENTIONS.md. The 2026-07-24 consumer needed a source-code
  reading to get there. This plan makes setup produce the config.
- Builds on cfg-02's writer (single write path, no duplicated write logic).

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- `aet setup` gains a config step (or `aet configure --guided`): asks exactly
  two questions — **scope** (`team`: commit `.agents/aet-config.json`;
  `shadow`: external `~/.aet/{slug}/config.json`, nothing committed) and
  **mode** (`pr-per-task` / `single-pr`) — then writes via cfg-02's writer
  and prints the result with provenance.
- Existing config is detected first: the flow shows current values and asks
  before overwriting.
- Non-interactive use (`--scope`/`--integration-mode` flags, or
  `AET_EXECUTION_MODE=unattended`) skips prompts and writes directly —
  agent-driven setups must not block on a TTY.
- The aet-setup skill's checklist gains the guided-config step so bootstrapped
  projects land on the same path.
- Repo-level hooks are explicitly out of the shadow path: choosing `shadow`
  installs nothing in the repo.

## Rejected Alternatives

- **A wizard with per-key prompts** — rejected: four keys is two decisions
  (scope, mode) with defaults for the rest; every extra question is a place
  to get it wrong.
- **Guided flow only in the aet-setup skill (no CLI)** — rejected: skills are
  agent-mediated; a scripted/first-run terminal setup needs the CLI path.

## Task List

1. Guided config flow in the setup surface: two questions, writer-backed,
   existing-config detection, non-interactive bypass — M (traces: R-11)
2. aet-setup skill checklist + SKILL.md: add the guided-config step, state the
   team/shadow split — S (traces: R-11)
3. Tests (see Validation Steps) — S (traces: R-11)
4. Merge branch to main and verify integration — S [Deferred: ship stage]

**Size definitions:** S ≤ 2 hr / ≤ 150 lines; M ≤ 1 day / ≤ 600 lines.

### Floor Check

- [x] Stands alone: ships a complete user-visible setup behavior on top of
  cfg-02's writer.

## Files to Modify

- `src/aet/cli/setup.py` (or `configure` surface, per implementation seam)
- `skills/aet-setup/SKILL.md`
- `skills/aet-setup/references/` (checklist)
- `tests/cli/test_guided_setup.py` (new)

## Validation Steps

- [ ] `make validate` passes
- [ ] New coverage in `tests/cli/test_guided_setup.py`:
  - `test_shadow_choice_writes_external_config_only` (integration: temp repo,
    HOME redirected; repo tree stays free of AET config)
  - `test_team_choice_writes_in_tree_config` (unit)
  - `test_existing_config_requires_confirmation` (unit)
  - `test_non_interactive_flags_skip_prompts` (unit)
- [ ] R-trace coverage: R-11 by tasks 1-3; no unknown R-ids
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit; configs already written stay valid. The aet-setup
skill reverts with the commit.

---

_Stage: merged_
_Next step: run `aet-work`_
