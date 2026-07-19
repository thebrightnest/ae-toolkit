---
id: gib-06-command-groups-sprint-add
size: L
blocked_by:
  - gib-04-versioned-membership-closure-push
  - gib-05-board-projection-machinery
pipeline: standard
status: draft
security_review: required
security_review_reason: retires the top-level `aet add` command and reroutes it under `aet sprint add`, which commits+pushes plan status and relabels a real issue. A weak id resolution could promote the wrong plan into the runnable sprint; skills-lint must still pass or CI enforcement of the docs↔code contract breaks. Both the resolution path and the lint parity are correctness boundaries.
docs_sync: required
docs_sync_reason: `aet add` is retired in favor of `aet sprint add`; the canonical docs (CONTEXT.md, PIPELINE.md, aet-work/SKILL.md) and every live skill that invokes `aet add` change, and skills-lint validates the new nesting.
---

# Plan: Noun-Scoped Command Groups + `aet sprint add`

## Context

- PRD: `docs/prds/github-issues-backlog-projection-prd.md` (R-11, R-19).
- **Owner decision (2026-07-17):** with two destinations (board, sprint), the destination becomes the noun and `add` the verb under it. Top-level `aet add` is retired (no alias, per no-backward-compat); `aet sprint add` takes its exact current meaning (approved plan → Work Queue, CONTEXT.md line 52/59).
- **Ground truth (2026-07-17):** `aet-work/bin/aet` dispatches a flat `SUBCOMMANDS` map (`add` at line 30). `state` already nests (`aet state <sub>`) and skills-lint validates the subparser choices — the precedent this plan follows. `bin/add` gates on the footer stage (`stage_from_plan`, refuse non-approved), then `backend.save(queue)`; it does not write frontmatter `status` today. 74 `aet add`/`aet-work add` references exist; the live subset (skills, CONTEXT, PIPELINE, aet-work/SKILL) is rewritten, historical plans/audits/bugs are left as records.
- Blocked by gib-04 (status commit+push helper; derived membership) and gib-05 (issue relabel machinery).

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**

## Locked design

- **Two command groups.** Add `sprint` and `backlog` dispatcher entries (targets `aet-work/bin/sprint`, `aet-work/bin/backlog`), each an argparse binary with an `add` subparser — mirroring `aet state <sub>`.
- **`aet sprint add <plan>` = today's `aet add`, renamed + extended.** Resolve the plan by id (fail-closed on unknown), keep the existing approved-only stage guard, set `status: queued`, commit+push via gib-04's `commit_and_push_status`, add to the derived queue, and relabel the issue `aet:ready`/`aet:blocked` (computed). `backlog add` is scaffolded here but implemented in gib-07.
- **Retire top-level `add`.** Remove `add` from `SUBCOMMANDS`; `bin/add` logic moves into `bin/sprint`. `aet add` now returns "unknown subcommand."
- **skills-lint teaches the nesting.** Extend the lint (cli-03) to parse `aet sprint <sub>` / `aet backlog <sub>` against the new subparsers, exactly as it does for `aet state <sub>`. Then sweep every live skill invoking `aet add` → `aet sprint add`.

## Rejected Alternatives

- **Keep `aet add` as an alias for `aet sprint add`** — rejected: no-backward-compat standing rule; aliases are the deprecation window the project forbids.
- **Repurpose `aet add` to mean backlog** — rejected (validate-scope finding): inverts CONTEXT.md's established `aet add`=sprint meaning and churns muscle memory for every existing caller.
- **A flat `aet sprint-add` / `aet backlog-add`** — rejected: the owner asked for noun-scoped groups ("backlog add" / "sprint add"), and `aet state <sub>` already sets the nested precedent.

## Task List

1. Add `sprint`/`backlog` group binaries + dispatcher entries; nest `add` subparser — M (traces: R-19)
2. Move `bin/add` behavior into `sprint add`; set `status: queued` + commit/push (gib-04 helper); relabel ready/blocked — M (traces: R-11)
3. Retire top-level `add` from `SUBCOMMANDS`; delete/redirect `bin/add` — S (traces: R-19)
4. skills-lint: validate `aet sprint <sub>`/`aet backlog <sub>` nesting — S (traces: R-19)
5. Doc sweep: CONTEXT.md, PIPELINE.md, aet-work/SKILL.md + live skills `aet add` → `aet sprint add` — M (traces: R-19)
6. Tests: `tests/test_command_groups.py` (new); update `tests/test_aet_multicall.py` — M (traces: R-11, R-19)

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

**⚠️ Size note:** L by file count (the doc sweep spans many files), but AI-complexity is M — the sweep is a mechanical `aet add` → `aet sprint add` find-replace across canonical docs + live skills, distinct from the command logic. Split point if needed: task 5 (doc sweep) becomes its own child. Kept together because the sweep must land atomically with the retirement or skills-lint goes red mid-merge.

### Batching Check

- [x] Not near-identical additions
- [x] Diff exceeds 3 files / 50 lines
- [x] Cannot share a branch — the command-surface change others build on

## Files to Modify

- `aet-work/bin/aet` (dispatcher: `sprint`/`backlog` entries, retire `add`)
- `aet-work/bin/sprint` (new), `aet-work/bin/backlog` (new, scaffold)
- `aet-work/bin/add` (removed/redirected)
- `scripts/skills-lint` (nested-subcommand validation)
- `CONTEXT.md`, `docs/PIPELINE.md`, `aet-work/SKILL.md` + live skill files invoking `aet add`
- `tests/test_command_groups.py` (new), `tests/test_aet_multicall.py`

## Validation Steps

- [ ] `make validate` passes; **skills-lint green** (the R-19 enforcement)
- [ ] New source coverage:
  - `tests/test_command_groups.py`: `test_sprint_add_promotes_and_commits`, `test_sprint_add_unknown_id_fails_closed`, `test_backlog_group_registered`, `test_top_level_add_is_unknown_subcommand`
  - `tests/test_aet_multicall.py`: nested-dispatch cases for `sprint`/`backlog`
- [ ] R-trace coverage: R-11 (t2), R-19 (t1, t3, t4, t5); no unknown R-ids
- [ ] Distinguish test types: unit (dispatch, resolution) + integration (sprint add → commit → relabel)
- [ ] Grep guard: no live skill or canonical doc contains `aet add` (historical docs excepted)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. Top-level `aet add` returns; `sprint`/`backlog` groups disappear; skills-lint reverts with the doc sweep. Because it is one commit, the skill↔lint contract stays consistent on either side of the revert.

## Pipeline

`pipeline: standard` — command-surface change with a fail-closed resolution boundary and a lint-enforced contract; standard grouping is warranted.

---

_Stage: qa-complete_
