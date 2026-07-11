---
id: cli-02-build-parser-status-json
size: M
blocked_by:
  - wfd-04-workflow-lint-variant-proof
pipeline: standard
status: approved
security_review: skipped
security_review_reason: mechanical extraction of parser construction plus a read-only JSON projection of local queue state — no auth, data-model, API, or dependency surface
docs_sync: skipped
docs_sync_reason: internal refactor; the new --json flag is documented in cli-05's wholesale surface migration
---

# Plan: `build_parser()` Exposure and `aet status --json`

## Context

- PRD: `docs/prds/roadmap-p2-aet-binary-prd.md` (G2, G4; R-4, R-6, plus R-10 tests)
- R-6 is what makes doc 06 P5's "parse against the real argparse tree" literal: every wrapped binary exposes its `ArgumentParser` for cli-03's skills-lint to introspect. R-4 is doc 09's named seam (`aet status --json`) that the Phase 4 desk builds on.
- Parallel-safe with cli-01 (different files); both blocked on wfd-04 for phase ordering. wfd-03 rewires the orchestrator internals — this plan rebases on whatever `parse_args` shape wfd leaves at `aet-work/bin/orchestrator:206`.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- Twelve bins gain `build_parser() -> argparse.ArgumentParser` at module level, with `parse_args()` reduced to `build_parser().parse_args(argv)`: `aet-work/bin/{add,review,status,next,sync,report,init-queue,aet-state,orchestrator}`, `aet-ship/bin/ship`, `aet-evolve/bin/{aet-retro,mine-learnings}`. Zero flag or behavior changes — existing test suites are the parity net.
- `status --json`: machine-readable projection to stdout (suppresses human output; exit codes unchanged): `{"queue_updated_at": …, "summary": {"<state>": <count>, …}, "tasks": [{"id", "state", "stage", "blocked_by", "pending_blockers", "plan_file"}, …]}`. Minimal v1 per PRD open question 2; the desk (Phase 4) extends it.
- File count (14) exceeds the 8-file session heuristic but the change is ~6 identical mechanical lines per bin (~250 total diff lines, inside the 300-line cap); splitting per-skill would recreate the tiny-PR anti-pattern the Batching Rule (docs/CONVENTIONS.md, learning 2026-07-06) exists to prevent. Flagged deliberately for scope review here rather than hidden.

## Rejected Alternatives

- **Only exposing parsers for bins the lint currently checks** — rejected: partial coverage reintroduces the drift blind spot per binary; the refactor is uniform and mechanical.
- **A central parser registry module** — rejected: parsers belong to their binaries; a registry is a second source of truth (the disease being treated). The spec table (cli-01) maps names → targets; targets own their parsers.
- **Rich `--json` schema (history, worktrees, costs)** — rejected: no consumer yet; the desk is the first real one (PRD open question 2). Minimal stable keys now.

## Task List

1. `build_parser()` extraction across the nine `aet-work` bins — M (traces: R-6)
2. `build_parser()` extraction for `ship`, `aet-retro`, `mine-learnings` — S (traces: R-6)
3. `status --json` projection + human-output suppression — S (traces: R-4)
4. Write `tests/test_build_parsers.py` (SourceFileLoader-import each of the twelve bins; assert `build_parser()` returns an `ArgumentParser` carrying one known flag per bin) and add `--json` schema assertions beside the existing status coverage — M (traces: R-10)
5. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Near-identical mechanical additions batched deliberately (Batching Rule) — splitting per skill would produce 3+ trivial PRs
- [x] Diff expected > 3 files / > 50 lines
- [x] Cannot share a branch with cli-01 — independent files, parallel-safe, separate review surfaces

## Files to Modify

- `aet-work/bin/add`, `aet-work/bin/review`, `aet-work/bin/status`, `aet-work/bin/next`, `aet-work/bin/sync`, `aet-work/bin/report`, `aet-work/bin/init-queue`, `aet-work/bin/aet-state`, `aet-work/bin/orchestrator`
- `aet-ship/bin/ship`, `aet-evolve/bin/aet-retro`, `aet-evolve/bin/mine-learnings`
- `tests/test_build_parsers.py` (new)
- status `--json` test additions (existing status test module)

## Validation Steps

- [ ] `make validate` passes (existing suites prove behavior parity)
- [ ] Named tests per new source file: `tests/test_build_parsers.py` → covers all twelve `build_parser()` exposures (unit); `status --json` → schema assertions incl. `python3 -m json.tool` round-trip (unit) beside existing status tests (integration)
- [ ] R-trace coverage: R-6 by tasks 1–2; R-4 by task 3; R-10 by task 4; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. The refactor is behavior-preserving and `--json` is additive; no consumer depends on either until cli-03 (lint) and Phase 4 (desk).

---

_Stage: qa-complete_
_Next step: run `aet-review`_
