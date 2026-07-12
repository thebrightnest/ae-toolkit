---
id: cli-05-legacy-retirement-sweep
size: M
blocked_by:
  - cli-03-skills-lint
  - cli-04-aet-install-self-repair
pipeline: standard
status: approved
security_review: required
security_review_reason: deletes entry-point files and activates PATH pruning — verify no executable path is orphaned and prune targets resolve only into skills directories
docs_sync: required
docs_sync_reason: this task is the docs migration itself; sync verifies README/CONVENTIONS/AGENTS coherence after the sweep
---

# Plan: Legacy Retirement — the Rewrite Sweep and the Flip

## Plan Notes

⚠️ **File count exceeds the 8-file session heuristic deliberately** (~20 files, almost all mechanical text renames of command references; ~250 diff lines, inside the 300-line cap). Splitting the rename per skill would recreate the tiny-PR anti-pattern the Batching Rule exists to prevent (docs/CONVENTIONS.md; learning 2026-07-06) and would leave the tree half-migrated across merges. Marked here for explicit scope-validation review; the change is one atomic semantic operation: _rename every command reference to `aet`, then make regression impossible_.

## Context

- PRD: `docs/prds/roadmap-p2-aet-binary-prd.md` (G3; R-5 deletion/prune flip, R-8 flip to error, R-9, plus R-10 via the lint's own gate)
- The phase-closing flip of additive-then-flip. Owner decisions at the gate (2026-07-11): no backward compatibility — no alias, no deprecation window; the old dispatcher and the standalone installer die in this merge, the same one that removes their last references. End state: PATH carries exactly one AET name, self-maintained.
- The rewrite contract is **a grep at implementation time, not a frozen file list** — the wfd arc merged while this phase waited and may have added references. Known surface today: ~16 markdown files across `aet-work`, `aet-plan`, `aet-ship`, `aet-evolve`, `aet-setup`, `aet-validate-scope`, `aet-pipeline-plan`, plus `.agents/templates/plan-template.md`, `AGENTS.md`, `README.md`, `docs/CONVENTIONS.md`, `Makefile`, and runtime hint strings (e.g. `aet-work/lib/queue.py:397`).

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- **Sweep**: enumerate with `grep -rnE '(aet-work|aet-state|orchestrator|aet-retro|mine-learnings|configure-task-backend|install-aet-binaries|aet-[a-z-]+/bin/)' aet-*/ .agents/templates .agents/commands AGENTS.md README.md docs/CONVENTIONS.md Makefile` and rewrite every **command-position reference** to the `aet` surface (`aet-work sync` → `aet sync`, `aet-state audit` → `aet state audit`, `aet-ship/bin/ship …` → `aet ship …`, `aet-work run-one` → `aet run-one`). Prose mentions of directories/files/concepts stay.
- **Runtime hints**: every user-facing hint string printed by bins/libs suggests `aet …` (start at `queue.py:397`; grep lib/bin for printed command names).
- **`aet-work/references/migration-aet-state.md`**: rewrite current-command text to `aet state …`; wrap spans that quote old names _as history_ in `aet-lint: off/on` markers — the only sanctioned escape-marker use.
- **Deletions**: `aet-work/bin/aet-work` (dispatcher superseded by `aet`), `aet-setup/bin/install-aet-binaries` (absorbed by `aet install`), `tests/test_aet_work_dispatcher.py` (superseded by `tests/test_aet_dispatcher.py`).
- **Makefile**: `install-skills`/`install-binaries` targets bootstrap via `<repo>/aet-work/bin/aet install`; skills-lint severity flips `--legacy=warn` → `--legacy=error`.
- **Prune flip**: `aet install` pruning becomes unconditional (cli-04's `--prune` gate removed); the seven legacy names leave PATH on the next install/self-repair cycle.
- Sequence inside the task: sweep first, flip lint to error, then run `make validate` and fix stragglers until green — the lint is the completeness proof, not the author's memory.

## Rejected Alternatives

- **Splitting the sweep per skill into separate plans** — rejected: near-identical text changes across a single semantic operation; the Batching Rule exists for exactly this, and a half-migrated tree between merges would teach agents two vocabularies.
- **Keeping `install-aet-binaries` as a wrapper calling `aet install`** — rejected: owner decision, no compat shims; the Makefile and `aet-setup` are the only callers and both are rewired in this merge.
- **Escape-marking legacy references instead of rewriting them** — rejected: markers are for content that quotes history, not a bypass for migration work; target is zero marker uses outside `migration-aet-state.md`.

## Task List

1. Reference sweep: skill SKILL.md + references, `.agents/templates`, `.agents/commands`, `AGENTS.md`, `README.md`, `docs/CONVENTIONS.md` → `aet` surface — M (traces: R-9) ✓
2. Runtime hint strings in bins/libs suggest `aet …` — S (traces: R-9) ✓
3. Deletions (`aet-work/bin/aet-work`, `aet-setup/bin/install-aet-binaries`, `tests/test_aet_work_dispatcher.py`) + Makefile bootstrap rewiring + unconditional prune in `aet install` — S (traces: R-5) ✓
4. Flip skills-lint to `--legacy=error`; run `make validate`; fix stragglers until green — S (traces: R-8) ✓
5. Merge branch to main and verify integration — S [Deferred: runs at `aet-ship` stage]

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Near-identical text renames batched deliberately (Batching Rule) — the plan-notes flag above records the file-count exception
- [x] Diff expected > 3 files / > 50 lines
- [x] Cannot share a branch with cli-03/cli-04 — the flip must land after the mechanism and the sweep together, as one reviewable cut

## Files to Modify

- Enumerated by grep at implementation time. Known today: `aet-work/SKILL.md` + 6 references, `aet-plan/SKILL.md` + `references/work-queue-format.md`, `aet-ship/SKILL.md`, `aet-evolve/SKILL.md` + `references/aet-retro.md`, `aet-setup/SKILL.md` (+ checklist/references), `aet-validate-scope/SKILL.md`, `aet-pipeline-plan/SKILL.md`, `.agents/templates/plan-template.md`, `AGENTS.md`, `README.md`, `docs/CONVENTIONS.md`, `Makefile`, `aet-work/lib/queue.py`, `scripts/skills-lint` (severity flip), `aet-work/bin/aet` (prune flip)
- Deletions: `aet-work/bin/aet-work`, `aet-setup/bin/install-aet-binaries`, `tests/test_aet_work_dispatcher.py`

## Validation Steps

- [ ] `make validate` passes **with `--legacy=error`** — the exit gate, machine-checked
- [ ] Repo grep for the seven legacy names in linted scope returns nothing in command position outside `aet-lint: off` spans in `migration-aet-state.md`
- [ ] `aet install --bin-dir <tmp>` yields exactly one AET link and prunes planted legacy links; `command -v aet-work` finds nothing after a real install cycle
- [ ] Existing tests referencing deleted files are gone with them; suite green
- [ ] R-trace coverage: R-9 by tasks 1–2; R-5 by task 3; R-8 by task 4; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit — restores the old dispatcher, installer, references, and warn-severity in one step (the flip being one merge is what makes rollback one revert).

---

_Stage: synced_
_Next step: run `aet-ship`_
