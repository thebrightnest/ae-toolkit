# Structured Gate Evidence Replaces Footer Regex for Stage Gating

## Status

Accepted (2026-07-09). Implements PRD `docs/prds/fable-review-hardening-prd.md` G7; informed by the Fable 5 review (`content/fable-review/02-2026-07-09-strategic-alternatives.md`, alternative 3). Extended by ADR-025 (2026-07-13): the common core gains a required `tree_hash` — a git tree-object fingerprint of the working tree the verdict attests to — auto-stamped by `write_verdict`.

## Context

The pipeline knows a checking stage passed because an agent edited a `*Stage:*` footer that code regex-parses. Despite PIPELINE.md calling the footer a breadcrumb, the orchestrator's group-session path reads it to decide how far a session advanced — prose edited by an AI is load-bearing for scheduling. Divergence detection reads hardcoded `/tmp/aet-reports/{task-id}`: not portable, collides across projects, and nothing in the repo writes there. Meanwhile the QA stage's actual results (test counts, commands) are invisible to code, so telemetry like `test_run_record` cannot be emitted deterministically.

Three homes for evidence were considered: in-repo `.agents/reports/` (re-creates the relative-path triangle — in-worktree agents must escape to the main checkout), `/tmp` with a project namespace (not portable, lost on reboot), and a user-level archive mirroring telemetry.

## Decision

1. Checking skills (qa, review, cso, sync-docs) write a JSON **verdict** per stage to `~/.aet/reports/{project-slug}/{task-id}/`, overridable via `AET_REPORTS_DIR`, path exported to sessions as `AET_EVIDENCE_PATH`. Verdicts are written before the footer is updated.
2. Verdicts are validated against checked-in schemas (required keys + types, stdlib validation): a common core (`task_id`, `stage`, `skill`, `verdict`, `summary`, `generated_at`) plus per-kind fields (qa test counts, review/cso findings, sync-docs divergences).
3. Orchestrator gates **fail closed**: a missing, schema-invalid, or failing verdict fails the stage exactly like a nonzero exit. Group-session advancement is determined by which stages have valid verdicts.
4. The plan footer `*Stage:*` is demoted to a human breadcrumb everywhere; no gating decision reads it.
5. Derived telemetry: a valid qa verdict deterministically yields a `test_run_record`.

## Consequences

- Gates become machine-checkable; "the footer says so" stops being evidence. Semantically-wrong-but-green work still lands — this ADR proves delivery of checks, not correctness — but what was checked is now inspectable.
- Skills gain a hard output contract; a skill that produces no verdict fails its stage even if the session exits 0. This is intentional and is the enforcement mechanism.
- Evidence lives outside the repo (like telemetry), keeping runtime artifacts out of the working tree (consistent with ADR-013) at the cost of not versioning them; the morning-review-desk direction consumes them in place.
- The `/tmp/aet-reports` contract and footer-driven group advancement are deleted, not deprecated.
