# Brief: Workflow-as-Data — the Extraction Pilot (Roadmap Phase 1)

## Problem

The software pipeline — stage sequence, skill bindings, evidence bindings — is compiled into the engine (`aet-work/lib/pipeline.py`, the `STAGES` table). Editing a gate means editing engine code. Worse, two runtime lambdas embed judgment in the engine: `_security_sensitive` (a filename-keyword heuristic deciding whether security review runs) and `_divergences_found` (an evidence read deciding whether docs sync runs). They violate ADR-020's razor (_the binary verifies that evidence exists and rules pass; it never evaluates whether work is good_) and they are the only thing standing between the pipeline and pure data — a `Callable` cannot be serialized.

## Context

- Roadmap: `content/fable-review/09-2026-07-10-roadmap.md`, Phase 1 (~4 tasks). Doc 06 step 2 named this the **extraction pilot**: "every place the orchestrator can't run from pure data is a coupling that had to be found anyway."
- Principles: doc 06 P2 (_route with judgment once at plan time, enforce with code forever; runtime conditionals disappear from the workflow entirely_) and P3 (_freeze states, generalize stages_ — lifecycle states stay hardcoded; stage sequences become data; linear sequences only).
- ADR-020/021 are queued as `rdm-01`; this phase starts after they merge.
- Repo state at planning (`a6efe17`): frh hardening arc complete; the sole engine consumer of the stage table is `aet-work/bin/orchestrator`; stage vocabulary also leaks into `aet-work/bin/review` (board columns) and the orchestrator's `"plan-approved"` entry-stage literal.
- Pedro is the first customer of the flexibility: the payoff is that editing his own gates stops touching engine code — not hosting other people's workflows.

## Requirements

- **R-1**: A versioned JSON workflow schema and a packaged default `aet-work/workflows/software.json` describe the current software pipeline completely: an ordered, linear stage sequence with per-stage skill bindings and evidence bindings (from the fixed verdict menu), entry stage and terminal succession explicit in the data.
- **R-2**: Session grouping lives in a separate `execution_policy` axis of the workflow file, not on stages; `minimal` / `standard` / `full` isolation semantics are preserved exactly. Unknown extension keys are tolerated (room reserved for context-fidelity settings).
- **R-3**: The engine loads the pipeline exclusively from workflow data. Resolution order: repo-level `.agents/workflows/<name>.json`, else the packaged default; the plan frontmatter key `workflow:` selects the workflow by name (default `software`). The hardcoded `STAGES` table and the `Stage.conditional` field are deleted.
- **R-4**: Plan frontmatter gains `security_review: required|skipped` and `docs_sync: required|skipped`; a `skipped` value requires a recorded reason (`security_review_reason` / `docs_sync_reason`); intake validation enforces this contract for newly added plans only (already-queued plans are grandfathered).
- **R-5**: The orchestrator resolves stage skips from plan frontmatter only; `_security_sensitive` and `_divergences_found` are deleted; a missing key is treated as `required` — fail-safe is running the stage.
- **R-6**: `aet-plan` prose instructs triage to set both routing keys deliberately on every new plan, with the reason recorded in the plan.
- **R-7**: Every engine consumer of stage vocabulary reads the loaded workflow: orchestrator entry stage and stage-membership checks, session grouping, and per-stage verdict kinds (retiring the skill→verdict map); `bin/review`'s board projection tolerates arbitrary stage vocabularies.
- **R-8**: A `routing` section (`default` / `by_stage` → harness + model; the per-workflow `default` is the by-class axis, since routing lives inside each workflow file) is schema-validated, parsed, and exposed on the loaded workflow object; no dispatch behavior changes while only Claude is conformant.
- **R-9**: A workflow lint runs inside `make validate` and fails on: invalid JSON or schema, duplicate or unknown stage references, skill bindings that resolve to no skill directory, evidence kinds absent from the fixed verdict menu, malformed execution-policy or routing sections.
- **R-10**: Parity is proven by tests: the loaded packaged default reproduces today's stage sequence, session groups, and verdict kinds exactly, and a full task lifecycle runs from pure data (stub adapter) with the same traversal as today.
- **R-11**: The team-variant test passes: a second workflow file — different stages, different gates, different evidence bindings, different routing — drives grouping and traversal through the engine with **zero engine changes**.

## Non-Requirements

- No `aet` multicall binary (Phase 2). No `aet gate submit`, no git hooks, no git-refs default flip, no fail-closed kernel rule beyond R-5's default (Phase 3).
- No second workflow class shipped — content-production waits for its trigger (Phase 8); the variant exists only as a test fixture.
- No new evidence kinds: the verdict menu stays `qa` / `review` / `cso` / `sync-docs`; variant workflows bind subsets of it. New kinds mean new kernel schemas — deliberately out of data's reach.
- No harness adapters or routing dispatch (Phase 6); the axis is parsed and stored only.
- Standing fences (roadmap): no runtime condition DSLs, no DAG/parallel stage graphs, no per-workflow state vocabularies, no plugin verifier APIs. Lifecycle states and `LEGAL_TRANSITIONS` stay frozen in code.
- No retrofit of already-queued plans (`rdm-01`, `rdm-02` run unmodified under the fail-safe default).

## Rejected Alternatives

- **Require a per-repo workflow file, no packaged default** — rejected: forces migration of every AET-managed repo (plus an `aet-setup` change) before the next run. A packaged default is zero-migration; the repo-level override path is still exercised by tests (R-3, R-11).
- **Keep `_divergences_found` as a runtime check** (it reads structured evidence deterministically — arguably not "judgment") — rejected: doc 06 P2 dissolves both lambdas explicitly; one mechanism (plan-time routing) beats two; `aet-sync-docs` no-ops cheaply when there is nothing to reconcile.
- **Default missing routing keys to `skipped`** — rejected: silently skipping a security gate is the wrong failure direction. Fail-safe = run the stage; Phase 3 formalizes fail-closed as the kernel rule.
- **YAML or TOML for the workflow file** — rejected: JSON round-trips with the stdlib and matches the `.agents/*.json` + evidence tooling; the hand-rolled YAML subset in `plan_parser` is deliberately minimal and should not grow nested-structure support.
- **Workflow-file conditions for stage gating** (`when: diff matches …`) — permanently fenced by P3's runtime-DSL refusal; gating is plan frontmatter recorded at triage.
- **Greenfield stage machine alongside the old one** — rejected: convergent evolution in place (ADR-021); the loader replaces the table in the same module boundary, guarded by the existing orchestrator test suite.

## Success Signal

The roadmap's Phase 1 exit gate: a full task lifecycle runs from pure data with behavioral parity to today (existing queue unaffected; traversal equality test-proven), **and** a plausible second team's flow is expressible by editing only a workflow file — proven by a fixture variant driving the engine with zero engine changes. `make validate` goes red on a malformed workflow file.

---

_Stage: brief_
_Created: 2026-07-11_
_Traces forward to: `docs/prds/roadmap-p1-workflow-as-data-prd.md`_
