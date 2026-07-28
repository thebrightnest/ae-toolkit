---
id: rid-06-run-docs-reconciliation
size: S
work_class: trivial
blocked_by:
  - rid-01-detached-only-execution
  - rid-03-non-streaming-follower
  - rid-04-bounded-completion-report
pipeline: minimal
status: queued
security_review: skipped
security_review_reason: Documentation-only; touches no executable code path.
docs_sync: required
docs_sync_reason: This plan is the documentation reconciliation.
---

# Plan: Run Documentation and Glossary Reconciliation

## Context

PRD: `docs/prds/run-invocation-determinism-prd.md` (R-13, R-14, R-15).

Scope validation found three live documentation consumers that the code changes falsify:

- `.agents/commands/aet-work.md:38, 44, 49` documents `--foreground` and describes `--follow`
  as tailing output.
- `docs/adr/004-unify-aet-work-run.md` states that `run` "spawns it as a background OS
  process, and waits for completion" — already false since `nc-06` daemonized it, independent
  of this PRD.
- CONTEXT.md gained a **Run Supervision** section during scope validation (R-15); it must be
  verified against shipped behavior.

This plan runs last because it describes the finished behavior.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. [x] Rewrite the `aet run` / `aet run-one` sections of `.agents/commands/aet-work.md`: remove
   `--foreground`, `--max-jobs`, `--isolation`, and `--stall-timeout` from the flag list,
   remove `--foreground` from the anti-patterns list, document blocking `run-one` vs
   returning `run`, and describe `--follow` as waiting for a bounded report — S
   (traces: R-13)
2. [x] Correct ADR-004's consequence text so it no longer claims `run` waits for completion,
   noting that daemonization (`nc-06`) and this PRD changed it — S (traces: R-14)
3. [x] Verify the CONTEXT.md **Run Supervision** entries (`Run`, `Run Id`, `Detached Run`,
   `Follower`, `Bounded Report`, `Stall Timeout`, `Wall Backstop`) match shipped behavior and
   correct any drift — S (traces: R-15)
4. [x] Update the in-repo skill `skills/aet-work/`: `references/queue-commands.md` currently
   documents `aet run --isolation standard --max-jobs 4` and `run-one --isolation standard`
   and shell-backgrounds both commands — rewrite for the R-2/R-2b/R-2c behavior, and sweep
   `SKILL.md` and the other references for any remaining mentions of removed flags — S
   (traces: R-13)
5. [Deferred: handled by `aet-ship`] Merge branch to main and verify integration — S

## Validation

- `grep -rnE -- "--(foreground|max-jobs|isolation|stall-timeout)" .agents/ docs/adr/ skills/`
  returns no hits presenting them as `run` / `run-one` flags outside historical plans and PRDs.
- No live doc describes `--follow` as tailing or streaming, or instructs shell-backgrounding
  `aet run` / `aet run-one`.
- ADR-004 no longer states that `run` waits for completion.
- CONTEXT.md's seven Run Supervision terms match the shipped commands.
- Named tests: none — documentation-only. Verified by the greps above and by `aet docs lint`.

---

*Stage: synced*
*Next step: run `aet-ship`*
