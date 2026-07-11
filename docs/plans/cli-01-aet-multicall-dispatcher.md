---
id: cli-01-aet-multicall-dispatcher
size: M
blocked_by:
  - wfd-04-workflow-lint-variant-proof
pipeline: standard
status: approved
security_review: required
security_review_reason: new executable entry point with cross-skill path resolution and exec dispatch — path-resolution correctness is security-relevant
docs_sync: skipped
docs_sync_reason: user-facing docs migrate wholesale in cli-05, the phase's dedicated rewrite task; piecemeal interim docs would create divergence
---

# Plan: The `aet` Multicall Dispatcher

## Context

- PRD: `docs/prds/roadmap-p2-aet-binary-prd.md` (G1; R-1, R-2, R-3, plus R-10 tests)
- The identity shift of doc 06 step 3: the orchestrator becomes `aet run`, a subcommand of the contract engine. The frh-05 dispatcher (`aet-work/bin/aet-work`) is the seed — same exec-based pattern, extended across skills and given an importable spec table so tooling (cli-03's skills-lint) validates against the same source of truth the dispatcher executes.
- Additive only: the old dispatcher and the standalone installer are untouched (deleted in cli-05); nothing references `aet` yet. `install`/self-repair land in cli-04 (split from this plan for session size).

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- `aet-work/bin/aet` (new, stdlib-only Python): module-level `SUBCOMMANDS` spec — ordered mapping `name → {"target": ("<skill-dir>", "<bin-name>"), "mode": "exec" | "run" | "run-one"}`. Wrapped set: `add`, `review`, `status`, `next`, `sync`, `report`, `init-queue` → `aet-work/bin/*`; `state` → `aet-work/bin/aet-state`; `run`/`run-one` → `aet-work/bin/orchestrator`; `ship` → `aet-ship/bin/ship`; `retro` → `aet-evolve/bin/aet-retro`; `mine-learnings` → `aet-evolve/bin/mine-learnings`; `configure-backend` → `aet-setup/bin/configure-task-backend`. The `install` row is added by cli-04.
- Dispatch is `os.execvp` 1:1 — args forward verbatim except the `run`/`run-one` mappings carried unchanged from the frh-05 dispatcher (`--queue-file .agents/work-queue.json` default; `run-one` plan-file positional → `--plan-file`; `--max-jobs`/`--isolation`/`--task-timeout`/`--cli-bin` passthrough).
- Skills-root resolution: `Path(__file__).resolve().parent.parent.parent` — the `aet-ship/bin/ship:31` pattern; works for repo checkout, symlinked dev install, and real skills-dir installs (ADR-016 distributes as a system). Missing sibling → exit 1 with an error naming the missing skill directory; unknown subcommand → exit 2 + usage generated from `SUBCOMMANDS`.
- Zero behavior change to any wrapped binary; the spec table is data so Phase 3+ subcommands are one-row additions (R-3).

## Rejected Alternatives

- **argparse subparser tree inside `aet` itself** — rejected: duplicates the wrapped binaries' parsers and drifts; exec dispatch keeps byte-for-byte behavior parity, and flag validation stays with the target's own parser (linted via cli-02's `build_parser()`).
- **Forwarding `run`/`run-one` args verbatim without the mapping** — rejected: changes the documented CLI contract for no gain; R-1 freezes the existing frh-05 mapping.
- **Including `install`/self-repair here** — rejected: pushes the task past the ≤300-line session limit; split to cli-04 (`Split from: cli-01` recorded there).

## Task List

1. Write `aet-work/bin/aet`: `SUBCOMMANDS` spec table + exec dispatch + skills-root sibling resolution — M (traces: R-1, R-3)
2. Carry the frh-05 `run`/`run-one` flag mapping unchanged; unknown-subcommand exit 2 with usage from the spec; missing-sibling error naming the skill — S (traces: R-1, R-2)
3. Write `tests/test_aet_dispatcher.py`: spec-table import (SourceFileLoader), per-subcommand routing with `os.execvp` monkeypatched, run/run-one mapping equality with the old dispatcher's output, unknown-subcommand exit 2, missing-sibling error; one subprocess integration case (`aet status --queue-file <tmp>`) exercising the real exec path — M (traces: R-10)
4. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not a near-identical addition — new entry-point semantics, distinct from cli-02 (parser exposure) and cli-04 (install)
- [x] Diff expected > 50 lines
- [x] Cannot share a branch with cli-04 — recombining recreates the >300-line session this split exists to avoid

## Files to Modify

- `aet-work/bin/aet` (new)
- `tests/test_aet_dispatcher.py` (new)

## Validation Steps

- [ ] `make validate` passes
- [ ] Named tests per new source file: `aet-work/bin/aet` → `tests/test_aet_dispatcher.py` (unit: routing, run/run-one mapping, usage/exit codes, missing sibling; integration: subprocess `aet status` against a temp queue)
- [ ] R-trace coverage: R-1, R-2, R-3 covered by tasks 1–2; R-10 by task 3; no unknown R-ids cited
- [ ] Manual spot-check: `aet state audit`, `aet ship --help`, `aet retro --help` reach their targets from a worktree
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. The binary is additive and unreferenced by any skill until cli-05; deleting it restores the exact prior surface.

---

_Stage: reviewed_
_Next step: run `aet-cso`_
