---
id: cli-03-skills-lint
size: M
blocked_by:
  - cli-01-aet-multicall-dispatcher
  - cli-02-build-parser-status-json
pipeline: standard
status: merged
security_review: skipped
security_review_reason: repo-CI lint reading tracked markdown; failure direction is merge-blocking only — no runtime, auth, data-model, or dependency surface
docs_sync: required
docs_sync_reason: adds a make validate step and the escape-marker convention worth documenting
---

# Plan: skills-lint v1 — Documented Invocations Parse Against the Real Tree

## Context

- PRD: `docs/prds/roadmap-p2-aet-binary-prd.md` (G2; R-7, R-8 warn-only, plus R-10 tests)
- Doc 06 P5 delivered: the #1 systemic wound (docs↔code reality gap; the cli_adapter fake-flag incident) becomes a merge failure. The lint consumes cli-01's `SUBCOMMANDS` spec and cli-02's `build_parser()` exposures — the same sources of truth the dispatcher executes, so lint and binary cannot drift (PRD R-3).
- The legacy-reference rule ships **warn-only**: the tree still legitimately contains legacy references until cli-05 rewrites them and flips severity to error.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- `scripts/skills-lint` (new, stdlib-only Python): loads `aet-work/bin/aet` via `SourceFileLoader` → `SUBCOMMANDS`; loads each target's `build_parser()`; introspects valid flags from `parser._actions` option strings and subparser choices (for `aet state <sub>`).
- **Extraction**: linted files = `aet-*/**/*.md`, `.agents/templates/*.md`, `.agents/commands/*.md`, `AGENTS.md`. Code spans only: fenced blocks (`bash`, `sh`, `console`, unlabeled) and inline backtick spans; shlex-split; a token stream starting with `aet` is validated. Opaque tokens pass as values: `<…>`, `{…}`, `…`, `$VAR`, `$(…)`.
- **Rule 1 (error)**: unknown `aet` subcommand or unknown flag for its target parser fails the build.
- **Rule 2 (legacy, warn at this task)**: command-position `aet-work`, `aet-state`, `orchestrator`, `aet-retro`, `mine-learnings`, `configure-task-backend`, `install-aet-binaries`, or `aet-*/bin/…` path invocations — except paths ending in `aet-work/bin/aet` (by-path bootstrap of the binary itself, validated as an `aet` invocation). Severity via `--legacy=warn|error`; Makefile passes `warn` here; cli-05 flips to `error`.
- **Escape markers**: `<!-- aet-lint: off -->` / `<!-- aet-lint: on -->` exempt deliberately historical spans (target state: zero uses outside content that quotes old names as history).
- `Makefile` `validate` gains `./scripts/skills-lint --legacy=warn` after the workflow lint step (adapting to wherever wfd-04 left the target).
- Prose mentions of names (file paths in narrative, concept references) are not command-position invocations and do not match either rule.

## Rejected Alternatives

- **`--help` output parsing** — rejected: fragile text scraping; `build_parser()` introspection is the real tree (brief rejected-alternatives, carried).
- **A hand-maintained command spec for the lint** — rejected: second source of truth that drifts; the lint imports what the dispatcher executes.
- **Linting all repo markdown including `docs/` and `content/`** — rejected: the fable-review corpus legitimately quotes old and future command shapes; the exit gate scopes to skills + scaffolding.
- **Shipping the legacy rule at error severity now** — rejected: the tree still contains legitimate legacy references until cli-05; error-now would force the sweep into this task and break additive-then-flip.

## Task List

1. ✓ Write `scripts/skills-lint`: span extraction + `aet` invocation validation against the imported spec/parsers — M (traces: R-7)
2. ✓ Legacy-reference rule with `--legacy=warn|error` severity + escape-marker handling — S (traces: R-8)
3. ✓ Wire into `Makefile` `validate` (`--legacy=warn`) — S (traces: R-7)
4. ✓ Write `tests/test_skills_lint.py` + fixtures under `tests/fixtures/skills-lint/`: valid invocation passes; unknown subcommand fails; unknown flag fails; placeholder tokens pass; legacy name warns at `warn` and fails at `error`; escape-marked span skipped — M (traces: R-10)
5. [Deferred: merge runs at `aet-ship`, per additive-then-flip batching] Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not a near-identical addition — one coherent lint contract (extraction + two rules + wiring), batched deliberately like wfd-04's lint-plus-proof
- [x] Diff expected > 3 files / > 50 lines
- [x] Cannot share a branch with cli-05 — the flip must be a separate merge from the mechanism (additive-then-flip)

## Files to Modify

- `scripts/skills-lint` (new)
- `Makefile`
- `tests/test_skills_lint.py` (new)
- `tests/fixtures/skills-lint/` (new fixtures)

## Validation Steps

- [x] `make validate` passes — and now includes skills-lint itself (legacy at warn)
- [x] Named tests per new source file: `scripts/skills-lint` → `tests/test_skills_lint.py` (unit: every rule and escape path via fixtures; integration: lint run over the real tree exits 0 at `--legacy=warn`)
- [x] Deliberately inserting `aet status --bogus` into a SKILL.md makes `make validate` exit non-zero; removing it goes green
- [x] R-trace coverage: R-7 by tasks 1, 3; R-8 by task 2; R-10 by task 4; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main` (deferred to `aet-ship`)

## Rollback Plan

Revert the merge commit; remove the Makefile line if reverting manually. The lint is additive CI tooling — no engine or skill behavior to unwind.

---

_Stage: merged_
_Next step: run `aet-ship`_
