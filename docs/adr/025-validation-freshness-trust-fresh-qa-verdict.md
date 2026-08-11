---
subject: verdict-provenance
---

# Validation Freshness: Gate Stages Trust a Fresh QA Verdict Instead of Re-Running

## Status

Accepted (2026-07-13). Extends ADR-019 (structured gate evidence) and builds on ADR-023 (canonical verdict path). Implements recommendation R2 of the pipeline-flow-efficiency audit (`docs/audits/2026-07-13-pipeline-flow-efficiency.md`); delivered by plans `pfe-01-verdict-freshness-primitive` and `pfe-02-orchestrator-freshness-injection`.

## Context

The 2026-07-13 session audit (finding F2) measured the full validation suite running 4–5 times inside a single task. QA runs `make validate`; then review and CSO each re-ran the whole suite as belt-and-suspenders — often against a tree that, since QA passed it green, had changed only a markdown footer. That is ~5–10 minutes of pure re-validation per task, plus agent attention, buying no signal.

The re-runs were driven by a single instruction the orchestrator injects into every stage prompt — "Run validations (tests, lint, format checks) in the foreground" — which carried no concept of freshness. And the evidence contract could not have supported one: a verdict (ADR-019) recorded _that_ a stage passed and _what_ it checked, but never _which_ tree it attested to, so "is QA's green still valid for the current tree?" was unanswerable from the record.

Audit R2 proposed a freshness rule and imagined it as skill-text edits (aet-qa/review/cso). Expressing it as prose, however, asks the agent to _remember_ to check and to _reason_ about staleness — re-creating the AI-discretion failure the rule exists to remove. The decision belongs in code.

## Decision

1. **Verdicts carry provenance.** Every verdict gains a required `tree_hash` — a git tree-object fingerprint of the working tree it attests to (`git add -A` into a throwaway index, then `write-tree`; captures uncommitted mid-stage state, stays diffable). `write_verdict` auto-stamps it: the code records provenance, the skill's writer contract is unchanged. This extends ADR-019's common core.
2. **A freshness query reads it.** `evidence.validation_freshness(task_id, kind, worktree)` compares the current worktree hash to the last verdict's `tree_hash` and returns `RUN` / `LINT_ONLY` / `SKIP` — identical tree → `SKIP`, only non-code (`docs/`, `*.md`, learnings log) changed → `LINT_ONLY`, otherwise `RUN`. It resolves the verdict via the ADR-023 canonical `resolve_verdict_path`; it never hand-computes a slug. Every uncertainty (no prior verdict, a prior fail, an unknown hash, an undiffable tree) resolves to `RUN`.
3. **The orchestrator decides, the stage obeys.** Before each stage spawn, the orchestrator computes freshness against the **QA** verdict (QA is the stage that ran `make validate`) using the same `derive_project_slug(repo_root)` the gate uses, and modulates the prompt it already owns: `SKIP` → "trust the QA verdict, do NOT re-run the suite"; `LINT_ONLY` → "lint/format only"; `RUN` → unchanged. The decision is a code-computed fact handed to the stage, not a judgment left to it. Freshness is exported as `AET_QA_FRESHNESS` for observability.
4. **The gate is untouched.** Freshness modulates only the prompt clause and an env signal. It never touches `write_verdict` or `_require_passing_verdict`: review and CSO still must emit their own passing verdicts. Only the redundant _re-run_ of the suite is suppressed, never the fail-closed gate (ADR-019).

## Consequences

- F2's redundant full-suite re-runs disappear when the tree is unchanged since QA validated it green — the common case for review/CSO, which rarely edit before validating.
- `tree_hash` is reusable beyond freshness: "which git object this evidence attests to" is exactly the atom the roadmap's Phase 3 ancestry-closure gate needs. The field is added once here; closure consumes it later.
- Bias-to-`RUN` makes the failure mode safe by construction: a hash bug, a slug edge, or any doubt costs one unnecessary run — never a skipped-but-needed validation.
- The required `tree_hash` extends ADR-019's documented six-field common core; verdicts written by the skills' hand-written fallback (bypassing the helper) omit it and are treated as `RUN` — degradation, not breakage.
- Freshness re-derives the verdict path from the slug rather than reading an injected exact path. If `AET_EVIDENCE_PATH` were set in the orchestrator's own environment, the ADR-023 step-1 precedence could mis-resolve; the orchestrator normally has no such variable. Closing this edge (inject the QA verdict path as `run_stage_group` injects `AET_EVIDENCE_PATH_<KIND>`) is tracked as a pfe-02 upgrade candidate.

## Alternatives Considered

- **Implement R2 as skill-text (the audit's suggested location)** — rejected: prose asks the agent to remember to check and to reason about staleness, the exact AI-discretion the rule removes. Decide in code; the stage obeys.
- **`tree_hash` optional, not required** — rejected: optional provenance is weaker evidence and gives the future closure gate nothing to rely on. Auto-stamping by the one write path makes "required" nearly free.
- **Key freshness on the commit hash (`HEAD`)** — rejected: misses uncommitted mid-stage edits, which are exactly the state a stage validates.
- **A skill-side freshness check (review/CSO call `validation_freshness` themselves)** — rejected: the worktree would be resolved inside the session, where `AET_REPO_ROOT` can point at the main repo rather than the worktree; and it splits ownership of the "run validations" instruction between the orchestrator prompt and skill prose.
