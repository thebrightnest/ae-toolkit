---
id: rid-02-shared-plan-arg-resolver
size: M
work_class: normal
blocked_by: []
pipeline: standard
status: merged
security_review: required
security_review_reason: Changes path resolution shared by five commands, including filesystem lookups from user input.
docs_sync: required
docs_sync_reason: Changes the accepted argument form for aet run and aet run-one.
---

# Plan: Shared Plan-Argument Resolver

## Context

PRD: `docs/prds/run-invocation-determinism-prd.md` (R-10, R-11, R-11b).

Three near-duplicate resolvers exist and they are **not** equivalent:

| Behavior | `ship.py:186` `_resolve_plan_arg` | `sprint.py:32` / `backlog.py:28` `resolve_plan` |
| --- | --- | --- |
| Missing plan | raises `ValueError` naming both interpretations | returns `None` |
| Non-existent `.md` path | passes through unchecked | falls through to id → `<dir>/<name>.md.md` |
| Plans dir | hardcoded `docs/plans` | `plans_dir` parameter |

Per scope validation, the shared implementation adopts **ship's semantics**; `sprint` and
`backlog` adapt at their call sites to preserve their `None`-returning contract. `aet run` and
`aet run-one` then accept a bare task id, matching `aet ship`.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. ✓ Add a shared `resolve_plan_arg(plan, plans_dir=Path("docs/plans"))` to a common module,
   with ship's semantics: `.md` passes through unchecked; otherwise resolve to
   `<plans_dir>/<id>.md`; raise `ValueError` naming both interpretations when unresolvable — S
   (traces: R-11)
2. ✓ Replace `ship.py:186 _resolve_plan_arg` with the shared helper at all four call sites
   (`ship.py:208, 376, 635, 857`), preserving current behavior exactly — S (traces: R-11)
3. ✓ Replace `sprint.py:32` and `backlog.py:28` with call-site wrappers that catch `ValueError`
   and return `None`, keeping both commands' current contract and their `plans_dir`
   parameterization — M (traces: R-11, R-11b) [Changed: `.md` passthrough now follows ship semantics; `.md.md` fallback removed]
4. ✓ Accept a bare task id for the `plan_file` argument of `run-one` in `src/aet/cli/main.py`
   via the shared helper, and update its help text to match `aet ship`'s wording — S
   (traces: R-10)
5. ✓ Add tests: shared-resolver unit cases (id hit, id miss raises, `.md` passthrough of a
   non-existent path); `sprint add` / `backlog add` parity for a valid id, a missing id, and a
   non-existent `.md` path; `aet run-one <id>` and `aet run-one docs/plans/<id>.md` resolving
   identically — M (traces: R-10, R-11b)
6. Merge branch to main and verify integration — S

## Validation

- `aet run-one rid-01-detached-only-execution` and
  `aet run-one docs/plans/rid-01-detached-only-execution.md` resolve to the same plan.
- `aet run-one no-such-id` errors naming both the path and id interpretations.
- `aet sprint add no-such-id` and `aet backlog add no-such-id` fail exactly as they do today
  (no traceback, same message and exit code).
- `grep -rn "def resolve_plan\b\|def _resolve_plan_arg" src/` returns exactly one definition.
- Named tests: `tests/cli/test_run_dispatcher.py` (id and path forms for `run-one`),
  `tests/ship/` (unchanged ship resolution), `tests/queue/` (sprint/backlog parity cases).

---

*Stage: merged*
*Next step: run `aet-ship`*

---

*Stage: merged*
