---
id: pkg-11-typer-consolidation
size: L
blocked_by:
  - pkg-06-cross-skill-extraction
pipeline: standard
status: queued
security_review: required
security_review_reason: Adds the typer runtime dependency and rewrites the entire CLI parsing surface — both supply-chain and behavior-review relevant.
docs_sync: required
docs_sync_reason: CONVENTIONS.md Skill Binaries section and SKILL.md invocation examples must be re-validated against the new parser tree.
---

# Plan: Consolidate the CLI on Typer (A4)

## Context

PRD: `docs/prds/aet-package-extraction-prd.md` (R-8).
Nineteen `argparse` binaries each re-implement parser setup, and the multicall
dispatcher exists only to exec between them. Consolidate into one Typer
application: subcommands register directly, the exec-dispatch and
`SUBCOMMANDS` spec are deleted, and skills-lint re-validates documented `aet`
invocations against the Typer command tree (roadmap-p2 reality-gap gate
preserved).

> **⚠️ ATOMIC OVERSIZED — requires explicit user approval.**
> Rewriting 19 parsers in one plan exceeds the line guardrail, but a
> half-migrated argparse/Typer mix doubles the parsing surface that
> skills-lint and `_ensure_path_link` must stay correct against. The
> per-subcommand rewrites are mechanical and independently testable;
> complexity concentrates in the dispatcher deletion, which is atomic.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Add `typer` to `pyproject.toml` runtime dependencies; create the app
   skeleton in `src/aet/cli/main.py` (`app = typer.Typer()`) with the same
   top-level help surface — M (traces: R-8)
2. Migrate each `src/aet/cli/*.py` subcommand from argparse to a Typer
   command, preserving flags, defaults, and help text; one commit group per
   domain (queue/orchestrator, state/gate, ship/retro/setup) — L (traces: R-8)
3. Delete the exec-dispatch machinery: `SUBCOMMANDS` spec, os.exec plumbing,
   and legacy symlink pruning that only existed for multi-binary dispatch —
   keep `aet install` and `_ensure_path_link` (single-name PATH ownership is
   still required) — M (traces: R-8)
4. Retarget skills-lint's parser-tree validation to introspect the Typer app;
   the gate must still fail on any documented invocation the real CLI rejects — M
   (traces: R-8)
5. Update CLI tests: `tests/test_aet_multicall.py` → app-tree tests;
   `tests/test_command_groups.py`, `tests/test_cli_adapter.py`,
   `tests/test_aet_dispatcher.py` rewritten against the Typer runner; update
   `docs/CONVENTIONS.md` if any documented invocation changes — M
   (traces: R-8)
6. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] Consolidation is the atomic unit; per-subcommand plans were rejected
  (see below).

## Rejected Alternatives

- **Per-subcommand Typer migration plans** — rejected: the mixed
  argparse/Typer interim state doubles the surface skills-lint and the PATH
  self-repair must track; more risk, not less.
- **Click instead of Typer** — rejected per PRD open question resolution:
  Typer preferred for type-hint-driven interfaces; either satisfies R-8, so
  the lighter-authoring option wins. (Record in PRD divergence if reversed at
  implementation time.)
- **argparse subparsers in one file, no new dependency** — rejected: keeps the
  19-parser authoring style that produced the sprawl; PRD's dependency policy
  exists precisely for this case.

## Files to Modify

- `pyproject.toml`
- `src/aet/cli/main.py` and all `src/aet/cli/*.py`
- `scripts/skills-lint`
- `tests/test_aet_multicall.py`, `tests/test_aet_dispatcher.py`,
  `tests/test_command_groups.py`, `tests/test_cli_adapter.py`,
  `tests/test_aet_install.py`
- `docs/CONVENTIONS.md` (if invocation examples change)

## Validation Steps

- [ ] `aet --help` lists the same subcommands as before (diff captured in PR)
- [ ] Named tests pass: rewritten `tests/test_aet_multicall.py`,
  `tests/test_command_groups.py`, `tests/test_cli_adapter.py`,
  `tests/test_aet_install.py`
- [ ] skills-lint still fails on a deliberately broken documented invocation
  (negative test named in `tests/test_skills_lint.py`)
- [ ] Every subcommand's `--help` and flag behavior matches pre-migration
  (snapshot comparison scripted in the PR)
- [ ] `make validate` green
- [ ] R-trace coverage: R-8 by tasks 1–5; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

`git revert` the merge; Typer remains declared but unused for one commit is
harmless (or drop the pin in the same revert).

---

*Stage: queued*
*Next step: run `aet-work`*
