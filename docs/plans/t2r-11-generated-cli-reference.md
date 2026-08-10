---
id: t2r-11-generated-cli-reference
size: S
work_class: normal
blocked_by: []
pipeline: minimal
security_review: skipped
security_review_reason: renders local Typer help text into a committed doc; no auth, data-model, API, or dependency surface
docs_sync: required
docs_sync_reason: deletes a skill reference file and repoints its README link
---

# Plan: Generated CLI Reference and Mirror Cleanup

## Context

PRD: `docs/prds/structural-review-tier-2-prd.md` (R-10). The review's
generated-or-absent principle: CLI references are generated from the command
tree or absent, never hand-copied. The Typer tree lives at
`src/aet/cli/main.py:64-92` (13 noun groups — state, backlog, desk, docs,
gate, hooks, plan, plans, queue, setup, ship, size, sprint — plus 13
top-level commands); the
`aet docs` group (`src/aet/cli/docs.py`) already owns doc governance (`lint`)
and is the natural home for `generate` per the ADR-039 noun-verb taxonomy.
Beads precedent: `bd help --doc` generates from the command tree.

**Mirror audit (verified against code, 2026-08-10):**

- `skills/aet-release-prep/references/COMMIT-CLASSIFICATION.md` — **delete.**
  It is a line-level copy of `CONVENTIONAL_PATTERNS` / `KEYWORD_PATTERNS` /
  `classify_commit()` at `src/aet/cli/release_prep.py:16-37,88-105`, already
  pinned by parametrized tests at `tests/test_release_prep.py:97-98` and
  listed as a mirror in `docs/audits/deprecation-inventory.md:188`. The
  generated CLI doc does not cover algorithm internals, so the pointer goes
  to the code + tests, not to the generated doc. Only inbound link:
  `skills/aet-release-prep/references/README.md:5` (the skill's SKILL.md does
  not reference it).
- `skills/aet-ship/references/ship-checklist.md` — **keep.** Judgment/prose
  checklist (gate criteria, commit quality, artifacts); no CLI mirroring.
- `skills/aet-plan/references/work-queue-format.md` — **keep.** Data-format
  prose spec for `.agents/work-queue.json`, linked from
  `skills/aet-plan/SKILL.md:198`; a schema contract the generated CLI doc
  cannot express.

**Collisions / notes:**

- Sibling R-9 plan (docs contradiction lint) will touch `aet docs lint` and
  `.agents/doc-rules.yaml` — a different mechanism in the same command group;
  no shared files, no blocker.
- Post-slc state (ADR-055): no footer, verdict, or stage writes are touched
  here; no prose writer is introduced around `aet gate submit` or
  `aet state set-stage`.
- Ledger: no events. The taxonomy (`src/aet/ledger.py:28`,
  `ALLOWED_KINDS = {cut, stage, verdict, land}`) has no kind for doc
  generation, and generation produces no task-scoped state.
- `tests/cli/test_command_groups.py:304-331` enumerates noun groups, not
  subcommands, so adding `docs generate` breaks no existing test. The list
  is stale, though — it covers 11 of the 13 registered groups (`setup` and
  `size` are missing); task 5 backfills it so the drift guard this plan adds
  starts from a complete list.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Add a deterministic tree-walk generator plus an `aet docs generate`
   subcommand in `src/aet/cli/docs.py`: walk the Typer/click tree from
   `aet.cli.main:app`, render one section per command (path, help, options,
   subcommands), write `docs/CLI.md` with an
   `AUTO-GENERATED: do not edit manually` header — S (traces: R-10)
2. Run `aet docs generate` once and commit the generated `docs/CLI.md`
   — S (traces: R-10)
3. Add `tests/cli/test_docs_generate.py`: unit tests for the walk's output
   shape (sections, marker header) and an integration drift guard asserting
   regenerated content equals the committed `docs/CLI.md`, failing with
   "run `aet docs generate`" — S (traces: R-10)
4. Delete `skills/aet-release-prep/references/COMMIT-CLASSIFICATION.md`;
   repoint `skills/aet-release-prep/references/README.md` to
   `classify_commit()` and its tests; add an `aet docs generate` row to the
   AGENTS.md tooling table — S (traces: R-10)
5. Backfill the drift guard's baseline: add `setup` and `size` to
   `_NOUN_GROUPS` in `tests/cli/test_command_groups.py:307-319` (currently
   lists 11 of the 13 registered groups) so the doc-vs-command-tree drift
   guard this plan adds starts from a complete list — S (traces: R-10)
6. Merge branch to main and verify integration — S

### Floor Check

- [x] Stands alone: doc generation + mirror deletion is one independently
  shippable behavior; R-9's contradiction lint is a separate mechanism.
- [x] Expected diff (~500 lines, dominated by the generated `docs/CLI.md`
  artifact; ~250 lines of hand-written code/test) materially exceeds PR
  overhead.
- [x] Cannot share a branch with the R-9 sibling: generator vs lint-rule
  changes land on different files and validate independently.

## Rejected Alternatives

- **Make target instead of `aet docs generate`** — rejected: the `aet docs`
  group already owns doc governance; a subcommand is directly testable in
  pytest and matches the ADR-039 noun-verb taxonomy, while a make target
  would split the docs surface across two entry points.
- **Hand-written CLI reference updated by convention** — rejected: that is
  the declared-and-not-effective drift pattern the review flagged; generated
  or absent, never hand-copied.
- **A docs-lint rule for drift instead of a pytest guard** — rejected:
  `.agents/doc-rules.yaml` rules are `must_contain`-style string assertions;
  whole-file regeneration equality does not fit that grammar, and the drift
  test already runs under `make test` / `make validate`.
- **Keep COMMIT-CLASSIFICATION.md as an algorithm spec** — rejected: it is a
  third copy of patterns whose source of truth is `release_prep.py` plus
  parametrized tests; nothing in the skill consumes it (only the references
  README links it).

## Files to Modify

- `src/aet/cli/docs.py`
- `docs/CLI.md` (new, generated)
- `tests/cli/test_docs_generate.py` (new)
- `tests/cli/test_command_groups.py` (`_NOUN_GROUPS` backfill)
- `skills/aet-release-prep/references/COMMIT-CLASSIFICATION.md` (delete)
- `skills/aet-release-prep/references/README.md`
- `AGENTS.md` (tooling table row)

## Validation Steps

- [ ] `make validate` passes (code + skill changes; full tier per AGENTS.md)
- [ ] `tests/cli/test_docs_generate.py` (new) covers the generator in
  `src/aet/cli/docs.py`: unit — walk output contains every noun group and
  top-level command with its help text and the `AUTO-GENERATED` marker;
  integration — drift guard regenerates from `aet.cli.main:app` and asserts
  byte equality with the committed `docs/CLI.md`
- [ ] Drift guard fails when a command's help text is edited without
  regenerating (deliberate-drift check during implementation)
- [ ] `tests/cli/test_command_groups.py::TestNounGroups` passes with all 13
  registered noun groups (including `setup` and `size`) in `_NOUN_GROUPS`
- [ ] `aet docs generate` is idempotent: two consecutive runs produce
  byte-identical output
- [ ] `grep -rn "COMMIT-CLASSIFICATION" skills/ src/ tests/ Makefile` shows
  no remaining references after deletion
- [ ] No API boundary tests needed — no frontend ↔ backend contract touched
- [ ] R-trace coverage: R-10 covered by tasks 1–5
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge. `docs/CLI.md` and the deleted reference file restore with
the revert; no state, ledger events, or queue records are written by this
plan, so nothing else needs unwinding.

## Pipeline

`minimal` — S-size doc tooling with no auth/data/API surface; all stages in
one session.

---

*Stage: reviewed*
*Next step: run `aet-sync-docs`*
