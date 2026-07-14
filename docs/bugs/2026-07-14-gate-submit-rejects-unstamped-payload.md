# Bug Report: `aet gate submit` rejects verdict payloads without `tree_hash` — the documented skill contract

## Metadata

- **Reported:** 2026-07-14T15:20Z
- **Severity:** high (blocks every checking stage that follows the documented writer contract)
- **Status:** open — routed to a new plan

## Symptoms

`aet gate submit --stage qa --verdict pass --evidence <payload.json>` fails with:

```
error: invalid 'qa' verdict payload: Missing required key 'tree_hash' for 'qa' verdict
```

when the payload follows the writer contract documented in the checking skills
(e.g. `aet-qa`'s verdict record example, which has no `tree_hash`). Hit live
during the QA stage of `pfe-02-orchestrator-freshness-injection`; the pfe-01
session hit the same wall (its learnings entry records falling back to direct
`evidence.write_verdict` calls).

## Reproduction Steps

1. Build a `qa` verdict payload exactly per the `aet-qa` SKILL.md writer
   contract (no `tree_hash` key).
2. Run `aet gate submit --stage qa --verdict pass --evidence payload.json`.
3. Exit 1 with the missing-key error above.

## Root Cause

pfe-01 made `tree_hash` a **required** key in all four verdict schemas
(`aet-work/lib/evidence.py` SCHEMAS) and added auto-stamping to
`write_verdict` (stamp → validate → write), per ADR-025: "the code records
provenance, the skill's writer contract is unchanged." But `aet-work/bin/gate`
was not updated: `_submit` calls `evidence.validate_verdict(record, stage)`
on the **raw payload file** before `write_verdict` gets a chance to stamp it.
The gate therefore enforces a contract the skills were never told about — the
sanctioned writer (G1) rejects the documented payload, and every skill's
fallback path becomes the de-facto writer.

## Fix Direction

Mirror `write_verdict`'s ordering inside `gate._submit`: stamp `tree_hash`
(via `verifier.working_tree_hash(telemetry.resolve_repo_root())`) when absent,
then validate, then write. Regression tests in `tests/test_gate_evidence.py`:
payload without `tree_hash` is accepted and stamped; an explicit `tree_hash`
is preserved; a schema-invalid payload still fails closed. Also re-check the
ADR-025 note that hand-written fallback verdicts omitting `tree_hash` "are
treated as RUN" against `read_verdict`'s schema validation (a required key
may make such verdicts unreadable rather than degraded).

## Workaround (used here)

Write the verdict through the sanctioned fallback: resolve the destination
with `evidence.resolve_verdict_path(task_id, kind)` (env-aware, ADR-023) and
call `evidence.write_verdict(..., worktree_dir=<stage worktree>)`, which
auto-stamps before validating. Equivalent to what the gate would write.
