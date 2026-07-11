# PRD: Roadmap Phase 3 — Enforcement Walls

## Overview

Phase 3 of the AET roadmap (`content/fable-review/09-2026-07-10-roadmap.md`): completes what frh-11/13/14/17 started and makes the doc 06 P1 invariant demonstrable — _the CLI is the only legitimate writer; hooks make illegitimate writes fail; tamper-evidence makes the ones that slip through visible._ Four pieces: `aet gate submit` centralizes and fail-closes verdict writing (fixing a live concurrency bug in the same pass); `aet hooks install` extends the existing pre-push hook so a task branch cannot be pushed without recorded gate evidence; git-refs becomes the default task-storage backend; and GitRefsBackend gains its own tamper-evidence mechanism so the "hand-edited ledger" exit-gate claim is true for the backend that is actually the default once this phase lands.

## Goals

- **G1**: Gate submission is centralized and fail-closed — `aet gate submit` is the only writer of stage verdicts, schema-validates per gate type, and fails closed on missing or malformed input rather than silently succeeding; the concurrent group-session path bug that caused false stage failures (thp-04) is fixed at the root (R-1, R-2, R-3).
- **G2**: The CLI is the only legitimate writer, enforced at the git boundary — `aet hooks install` extends the existing pre-push hook so a task branch cannot be pushed without recorded gate evidence, regardless of which harness or agent attempted the skip (R-4).
- **G3**: The ledger is git, and tampering with it doesn't go unnoticed — git-refs becomes the default task-storage backend, and a hand-edited ledger write is mechanically detected, not just theoretically detectable (R-5, R-6).
- **G4**: The exit gate is demonstrated, not asserted — an adversarial rehearsal proves both enforcement walls under real attempted violations, and the result is recorded (R-7, R-8).

## Non-Goals

- No `aet desk`, `aet plan validate`, or zero-review-class mechanism (Phase 4).
- No failure taxonomy, circuit breaker, stall watchdog, or budget ceilings (Phase 5).
- No multi-harness adapters, `aet doctor`, or cross-vendor review routing (Phase 6).
- No scoreboard, `aet eval`, or learning loop (Phase 7).
- No shared fail-closed helper for hypothetical future interactive CLI prompts. Verified against the codebase: there is currently no `input()`/stdin call site anywhere in the toolkit — HARD GATEs (`aet-plan`, `aet-pipeline-plan`) are prose-only, live-chat conventions, not code the orchestrator executes unattended. R-2 covers only `aet gate submit`'s own argument/evidence validation; a general-purpose primitive is deferred to whenever a real interactive consumer exists (see Open Questions).
- No change to git-refs's local-only-by-default push policy (frh-13) — pushing `refs/aet/*` remains a manual, documented choice.
- No retirement of the JSON backend code path — it remains available as an explicit config opt-out (`task_backend: "json"`), not deleted. "Demoted to disposable projection/cache" describes its role as default, not its removal.
- No cryptographic signing (GPG-signed commits/refs) for tamper-evidence — content-hash-based detection only, consistent with frh-17's existing approach; identity/signature verification is out of scope.
- No changes to the four evidence schemas themselves (frh-10's `qa`/`review`/`cso`/`sync-docs` `SCHEMAS`) — `aet gate submit` wraps existing validation, it doesn't redefine it.
- Standing fences hold (roadmap doc 09): no DAG/parallel stage graphs, no daemon, no plugin verifier APIs.

## Requirements

- **R-1**: A new `aet gate submit --stage <s> --verdict pass|fail --evidence <path>` subcommand — one additional row in the `aet` dispatcher's spec table (cli-01), exactly as that plan's own design anticipated ("Phase 3+ subcommands are one-row additions"). It wraps `aet-work/lib/evidence.py`'s existing `write_verdict`/`validate_verdict` (frh-10), schema-validating per gate type (`qa`, `review`, `cso`, `sync-docs`). The orchestrator's evidence gate (frh-11) becomes the only consumer of verdicts written through this path — no other writer is sanctioned.
- **R-2**: `aet gate submit` fails closed on malformed input: missing or empty `--verdict`/`--evidence`, an evidence file that doesn't exist or isn't readable, or a payload that fails `validate_verdict`'s schema check — each is a non-zero exit with a clear, named error, never a silent or implicit success.
- **R-3**: Fix `AET_EVIDENCE_PATH` derivation in `run_stage_group` (`aet-work/bin/orchestrator`). Confirmed by inspection: `run_stage` sets `AET_EVIDENCE_PATH` (`orchestrator:414`); `run_stage_group` (`orchestrator:454`) does not. Under batch/group-session concurrency this forces a fallback to a CWD-derived project-slug path that can diverge from the path the gate actually reads — the confirmed root cause of thp-04 being marked failed three times despite complete, verified work. `run_stage_group` must set `AET_EVIDENCE_PATH` per evidence-bound stage the same way `run_stage` does.
- **R-4**: A new `aet hooks install` subcommand extends the existing `scripts/hooks/pre-push` (waf-05) rather than replacing it — adds a gate-evidence check alongside the current coverage gate. For a push on a task branch, the hook refuses unless the branch's task has recorded gate evidence for its required stages (core qa/review, plus security/docs stages per the plan frontmatter's `security_review`/`docs_sync` routing keys). waf-05's pure-deletion short-circuit and the existing coverage-gate behavior for non-task-branch pushes are preserved unchanged. `aet hooks install` formalizes the manual symlink step `docs/CONVENTIONS.md` currently documents by hand.
- **R-5**: `GitRefsBackend` (frh-13/14) becomes the default `task_backend` in `aet-work/lib/backends/factory.py`; the JSON queue file becomes a disposable, regenerable projection rather than the source of truth. Existing installs can opt back to `task_backend: "json"` explicitly. frh-14's parity suite (`tests/test_git_refs_parity.py`) is the safety net proving the flip is behavior-preserving and must stay green against the new default.
- **R-6**: `GitRefsBackend` gains a tamper-evidence mechanism with a guarantee equivalent to frh-17's JSON-wrapper `revision`/`content_hash` stamping (`aet-work/lib/queue.py`), which has no git-refs counterpart today (`GitRefsBackend.seal` drops a ref and appends to history with no integrity stamp). A hand-edited or out-of-band-modified task ref or envelope blob (`refs/aet/tasks/<id>`, `refs/aet/meta/queue`) must be detected on next read and surfaced as a fail-closed integrity error, mirroring `QueueIntegrityError`'s contract — mutating paths fail closed; read-only paths warn and continue.
- **R-7**: The phase's exit gate is demonstrated end-to-end, not just asserted, and the demonstration is recorded (audit doc, matching frh-14's A/B-findings precedent):
  - (a) an agent instructed to skip gates and force-push a task branch is stopped by the installed pre-push hook (R-4);
  - (b) a hand-edited git-refs ledger write is surfaced by tamper-evidence on next read (R-6).
- **R-8**: Tests: `aet gate submit` schema validation and fail-closed CLI behavior (R-1, R-2); `AET_EVIDENCE_PATH` correctness under concurrent group-session batch execution, regression-testing the thp-04 scenario (R-3); hook install plus the adversarial-push rehearsal (R-4, R-7a); git-refs default-flip parity still green (R-5); git-refs tamper-evidence detection of a hand-edited ref/blob (R-6, R-7b).

## User Stories

- As an agent completing a checking stage, I submit my verdict through one command, and if I get the invocation wrong the failure is immediate and legible instead of a silent pass that surfaces as a mystery failure three stages later (satisfies: R-1, R-2).
- As the owner running a night-shift batch, a group-session task's evidence lands where the gate actually looks for it, so a fully-completed task is never marked failed by a path mismatch again (satisfies: R-3).
- As the owner, I install one hook once (`aet hooks install`) and from then on, no task branch — mine or an agent's — reaches the remote without its gates having actually passed (satisfies: R-4, R-7a).
- As the owner, if someone or something hand-edits the task ledger outside the CLI, I find out the next time anything reads it, whether the backend is JSON or git-refs (satisfies: R-6, R-7b).
- As the Phase 4 implementer, I build `aet desk` and `aet plan validate` on a queue whose default storage is git-refs and whose gate evidence is verdict-driven, not footer-driven (enabled by R-1, R-5).

## Acceptance Criteria

- [ ] `aet gate submit --stage qa --verdict pass --evidence <path>` writes a schema-valid verdict that the orchestrator's evidence gate accepts; omitting `--verdict`, omitting `--evidence`, pointing `--evidence` at a missing file, or pointing it at a schema-invalid JSON payload each exit non-zero with a named error (satisfies: R-1, R-2).
- [ ] A 4-way batch run covering a `[reviewed, secure]` stage group writes both verdicts to the path `aet gate submit`/the gate reader agree on, under concurrent sibling tasks, with no path-derivation divergence (satisfies: R-3).
- [ ] After `aet hooks install`, pushing a task branch with an unrecorded required gate is refused by the pre-push hook; pushing a branch-deletion ref still short-circuits per waf-05; pushing a non-task branch runs the existing coverage gate unchanged (satisfies: R-4).
- [ ] With no `task_backend` configured, a fresh `aet-setup` run yields `git-refs` as the active backend; `tests/test_git_refs_parity.py` passes against it (satisfies: R-5).
- [ ] Hand-editing a task's git-refs blob content (bypassing the CLI) and then reading it through any `aet state`/`aet status` path raises a fail-closed integrity error instead of returning the tampered value (satisfies: R-6).
- [ ] The adversarial rehearsal from R-7 is executed and its outcome (both (a) and (b)) is written up in `docs/audits/` (satisfies: R-7, R-8).

## Technical Notes

- **Ground truth**: `aet-work/lib/evidence.py` — `write_verdict`, `read_verdict`, `validate_verdict`, `SCHEMAS` (frh-10). `aet-work/bin/orchestrator:390` `run_stage` sets `AET_EVIDENCE_PATH` at `:414`; `:454` `run_stage_group` does not (confirmed by direct inspection, not assumed from the roadmap prose). `aet-work/lib/backends/base.py` `TaskBackend.seal()` — the file-backed default reads/writes via `queue.py`'s `read_queue`/`write_queue`/`append_history_record`; `GitRefsBackend` (frh-13, `aet-work/lib/backends/git_refs_backend.py`) overrides `seal` to drop the task's ref and append to history, with no integrity-stamp equivalent to `write_queue`'s `revision`/`content_hash` (frh-17, `aet-work/lib/queue.py`). `aet-work/lib/backends/factory.py` (frh-14) maps `task_backend` config → backend class, currently defaulting to JSON. `scripts/hooks/pre-push` (waf-05) — deletion short-circuit, else full test+coverage gate; install today is a manual symlink per `docs/CONVENTIONS.md`. `aet-work/bin/aet` (cli-01, `awaiting_merge`) — `SUBCOMMANDS` spec table + exec dispatch; explicitly designed so Phase 3 subcommands are one-row additions.
- **Phase ordering via queue edges**: cli-01/cli-02 (Phase 2) are `awaiting_merge`; cli-03 (skills-lint, Phase 2's actual exit gate) is `blocked`. Per the roadmap's strict phase ordering, all `ewl-*` plans from this PRD are `blocked_by: cli-03-skills-lint` in their frontmatter — mechanically enforced by the queue, not remembered, exactly as P1→P2 ordering was enforced via wfd-04.
- **`aet gate submit` verified fail-closed, not assumed**: grepped the full toolkit (`aet-work`, `aet-plan`, `aet-pipeline-plan`, `aet-validate-scope`, and repo-wide for `input(`/`sys.stdin`/`click.confirm`/`Prompt.`) — zero interactive-prompt call sites exist anywhere. The roadmap's "missing answer, closed stdin" language has no current code target; R-2's CLI-argument/evidence-file validation is the concrete, buildable interpretation for this phase. A general-purpose fail-closed prompt helper is explicitly deferred (Non-Goals, Open Questions).
- **Tamper-evidence mechanism (R-6) is an implementation-time choice**, not fixed here: the cheapest option consistent with frh-17's approach is a content-hash chain across `refs/aet/meta/queue`'s envelope blob (each save's hash covers the prior hash + current task-ref set), detecting any ref rewritten outside the chain. Left to the implementing plan to lock in, the same way frh-13/17 made their storage-design calls inline rather than in the PRD.
- **Hook scope**: "task branch" detection reuses whatever convention `aet-ship`/`aet-work` already use to identify a task's branch from its plan ID (worktree naming), not a new heuristic.
- **Sizing**: 6 plans (`ewl-01…06`) vs the roadmap's ~4 — the `AET_EVIDENCE_PATH` fix (R-3) and git-refs tamper-evidence (R-6) split out as their own plans because they surfaced only during clarify-goal grounding (a confirmed live concurrency bug, and a confirmed gap between frh-17's JSON-only tamper-evidence and git-refs becoming default), not from the roadmap's original terse bullet list; the adversarial rehearsal + audit doc closes the phase as its own small plan, mirroring frh-14's A/B-findings precedent.
- Intake triage: enhancement — no reproducible defect; classification recorded here.

## Open Questions

1. **Deferred fail-closed helper**: no current interactive CLI prompt exists to attach a shared "gated confirm, fails on EOF" primitive to. Revisit if Phase 4 (`aet desk`) or Phase 5 (`--on-failure=triage`) introduces a real one — building it against zero consumers now would be speculative.
2. **`aet hooks install` bundling**: stays a separate, deliberate command in this phase (matches roadmap prose). Whether it should later fold into `aet install`'s self-repairing bootstrap (Phase 2, R-11) is an open call — git hooks are repo-local, `aet install`'s PATH link is global, so bundling isn't obviously correct; not blocking for Phase 3.
3. **Exact git-refs tamper-evidence mechanism** (content-hash chain vs. something richer) — left to the implementing plan, per the Technical Notes precedent from frh-13/17.

---

_Stage: prd-approved_
_Next step: run `aet-validate-scope`_
