# AE Toolkit: Evaluation of Proposed Agentic-Engineering Improvement Areas

**Date:** 2026-06-15
**Scope:** 23 proposed improvement areas across 5 themes, evaluated against current AET skills, `docs/PIPELINE.md`, in-flight PRDs, and the 2026-06-10 systemic improvement analysis.
**Question:** Which of these areas deserve AET investment, and where should they live?

---

## 1. Executive Summary

The proposed map is a good description of the broader agentic-engineering field, but not all of it is a good fit for the AE Toolkit. AET's comparative advantage is the _engineering delivery loop_: planning → implementation → validation → shipping, with explicit work classes and a learning ratchet. The highest-leverage additions are therefore in **measurement** (Evals, LLM-as-Judge, self-consistency), **workflow reliability** (failure recovery, coordination), and **throughput scaling** (orchestration, parallel execution) — all of which directly address the recurring incidents catalogued in `reports/`.

Areas that are essentially prompt-craft techniques should be folded into existing skills or reference docs, not promoted to standalone runtime skills.

Recommended clusters:

- **In-flight / continue:** Multi-Agent Orchestration, Parallel Execution, Agentic Loops, Self-Validating Agents, Coordination & Integration.
- **New or substantially enhanced:** Evals, Failure Recovery & Retry Logic.
- **Lens / enhancement to existing skills:** Prompt Engineering, Context Engineering, Chain-of-Thought, Spec Writing, Task Decomposition, LLM-as-Judge, Best of N, Self-Consistency Checks, Red Teaming, Reflection Patterns.
- **Covered already:** Prompt Chaining, Multi-step Workflow Definition, Human-in-the-Loop Design, Guardrails.
- **Defer / out-of-scope for now:** Tool Use, Remote Sandboxing.

---

## 2. Evaluation Dimensions

For each area we score:

| Dimension          | Meaning                                                          |
| ------------------ | ---------------------------------------------------------------- |
| **Coverage**       | How much AET already handles this                                |
| **Fit**            | How well it matches AET's mission (engineering workflow toolkit) |
| **Leverage**       | Would it prevent real incidents or unlock throughput?            |
| **Cost**           | New skill vs. small enhancement vs. reference-only               |
| **Recommendation** | What to do                                                       |

Scale: 🔴 Gap / 🟡 Partial / 🟢 Covered.

---

## 3. Category-by-Category Evaluation

### 3.1 Getting Agents to Understand You

| Area                       | Coverage | Fit    | Leverage   | Cost                                 | Recommendation                                                                                                                   |
| -------------------------- | -------- | ------ | ---------- | ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------- |
| Prompt Engineering         | 🟡       | Medium | Medium     | Reference doc + skill-authoring lens | Add a prompt-quality checklist to `docs/CONVENTIONS.md` and a lens when reviewing new skills; do **not** create a runtime skill. |
| Context Engineering        | 🟢       | High   | High       | Enhance existing skills              | Strengthen context-budget and retrieval rules; add a reference doc on context engineering for skill authors.                     |
| Chain-of-Thought Prompting | 🟡       | Medium | Low-Medium | Reference pattern                    | Add as an optional pattern for complex specs inside `aet-plan` references; not a standalone skill.                               |
| Spec Writing for Agents    | 🟢       | High   | High       | Enhance existing skills              | Add a spec-quality lint / self-consistency check in `aet-validate-scope`.                                                        |
| Task Decomposition         | 🟢       | High   | High       | Enhance existing skills              | Document decomposition patterns in `aet-plan` references.                                                                        |

### 3.2 Knowing If the Output Is Good

| Area                    | Coverage | Fit         | Leverage  | Cost                                         | Recommendation                                                                                                                     |
| ----------------------- | -------- | ----------- | --------- | -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| Evals                   | 🔴       | High        | Very high | New skill or major `aet-qa` extension        | **High priority:** create `aet-eval` (or `aet-qa --design-eval`) for behavior-driven eval suites with golden examples and metrics. |
| LLM-as-Judge            | 🟡       | Medium-High | Medium    | Lens first                                   | Add an LLM-as-Judge lens to `aet-review` for natural-language artifacts; fold into `aet-eval` for output scoring.                  |
| Best of N               | 🔴       | Medium      | Medium    | Part of `aet-eval`                           | Defer until `aet-eval` exists; add as a technique in its references.                                                               |
| Self-Consistency Checks | 🟡       | High        | High      | Extend `aet-validate-scope` and `aet-review` | Formalize: plan prose ↔ code-block reconciliation, cross-model review, acceptance-criterion coverage check.                       |
| Red Teaming             | 🟡       | Medium      | Medium    | Extend `aet-cso`                             | Add a red-team lens to `aet-cso` for adversarial inputs and trust-boundary abuse; defer general AI-safety red teaming.             |

### 3.3 Building Systems that Compound

| Area                   | Coverage | Fit  | Leverage  | Cost                | Recommendation                                                                                                                              |
| ---------------------- | -------- | ---- | --------- | ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Prompt Chaining        | 🟢       | High | Medium    | Documentation       | The pipeline itself is a chain of skill invocations; keep current architecture and make the stage graph more visible in `docs/PIPELINE.md`. |
| Tool Use               | 🟢       | Low  | Low       | Out of scope        | Agent runtimes provide tools; AET consumes them. Do **not** add unless the toolkit later needs a "wrap a new tool" skill.                   |
| Agentic Loops          | 🟢       | High | Very high | Continue in-flight  | Finish `unified-orchestrator-session-isolated-pipeline.md` and `aet-work-parallel-execution-prd.md`.                                        |
| Self-Validating Agents | 🟡       | High | High      | In-flight + enhance | Embed validation gates in the unified orchestrator so a stage cannot advance without evidence.                                              |
| Reflection Patterns    | 🟡       | High | High      | Enhance existing    | Add a "post-implementation reflection" step that feeds `.agents/learnings.jsonl` with triggers.                                             |

### 3.4 Designing Reliable Workflows

| Area                           | Coverage | Fit  | Leverage | Cost               | Recommendation                                                                                                                          |
| ------------------------------ | -------- | ---- | -------- | ------------------ | --------------------------------------------------------------------------------------------------------------------------------------- |
| Multi-step Workflow Definition | 🟢       | High | Medium   | Documentation      | Covered by `aet-plan`, `aet-pipeline-plan`, `aet-work`, and `docs/PIPELINE.md`; improve examples and keep `docs/PIPELINE.md` canonical. |
| Human-in-the-Loop Design       | 🟢       | High | Medium   | Enhance            | Add HITL decision checklist to `aet-plan` and `aet-work` references.                                                                    |
| Failure Recovery & Retry Logic | 🟡       | High | High     | Enhance `aet-work` | **High priority:** add transient-failure retry, graceful drain, and resume-after-failure semantics.                                     |
| Guardrails                     | 🟢       | High | High     | Maintain           | Covered by AGENTS.md, guardrails partial, pre-commit hooks, `aet-cso`, and work-class routing. Stay proportionate per work class.       |
| Coordination & Integration     | 🟡       | High | High     | In-flight + docs   | Formalize handoff contracts in `docs/PIPELINE.md`; unified orchestrator enforces them.                                                  |

### 3.5 Scaling Throughput

| Area                      | Coverage | Fit    | Leverage  | Cost               | Recommendation                                                                                            |
| ------------------------- | -------- | ------ | --------- | ------------------ | --------------------------------------------------------------------------------------------------------- |
| Multi-Agent Orchestration | 🟡       | High   | Very high | Continue in-flight | **Top priority:** finish the unified orchestrator; it underlies parallel execution and session isolation. |
| Parallel Execution        | 🟡       | High   | Very high | Continue in-flight | **Top priority:** implement after the orchestrator foundation is stable.                                  |
| Remote Sandboxing         | 🔴       | Medium | Medium    | Large infra effort | Defer; mention as a future direction in `aet-verify` references if needed.                                |

---

## 4. Strategic Fit Assessment

### What AET already does well

- **Work-class proportionality** (`docs/PIPELINE.md`) trivial/normal/critical routing.
- **Stage state machine** and skill chaining via `aet-work` and `aet-pipeline-plan`.
- **Security guardrails** via `aet-cso`.
- **Learning ratchet** via `aet-evolve` and `.agents/learnings.jsonl`.
- **Validation hierarchy** via `aet-qa`, `aet-verify`, and `aet-review`.

### Where the proposed areas reinforce AET's direction

The 2026-06-10 systemic analysis identified three failure clusters:

1. **Reality gap** — validation used proxies instead of observed behavior.
   → Addressed by **Evals**, **LLM-as-Judge**, **Self-Consistency Checks**, and **Self-Validating Agents**.
2. **Seams between skills** — handoffs, routing, and state drift.
   → Addressed by **Multi-Agent Orchestration**, **Parallel Execution**, **Coordination & Integration**, and **Failure Recovery & Retry Logic**.
3. **Learning loop leaks** — lessons did not escalate to gates.
   → Addressed by **Reflection Patterns** and richer `aet-evolve` triggers.

The proposed map therefore validates AET's current trajectory rather than pointing to a brand-new direction.

### What to avoid

- **Standalone "prompt engineering" skills** — they compete with the runtime skills and duplicate what good SKILL.md authoring already encodes.
- **Tool-use tutorials** — out of scope; the agent runtime owns tool use.
- **Remote sandboxing as a first-class skill** — too infra-heavy for a portable, markdown-first toolkit.

---

## 5. Prioritized Roadmap

### P0 — Continue / finish in-flight work

These already have PRDs and directly map to the proposed areas:

1. **Unified orchestrator** (`unified-orchestrator-session-isolated-pipeline.md`) — covers Multi-Agent Orchestration, Coordination & Integration, Agentic Loops, Self-Validating Agents.
2. **Parallel execution** (`aet-work-parallel-execution-prd.md`) — covers Parallel Execution.
3. **Failure recovery / resume semantics** — add retry/backoff and drain-on-failure to the orchestrator; covers Failure Recovery & Retry Logic.

### P1 — Add measurement skills

1. **`aet-eval` (or `aet-qa --design-eval`)** — design behavior-driven eval suites with golden examples, metrics, and observed-evidence criteria. Covers Evals, Best of N, and supports LLM-as-Judge.
2. **Self-consistency checks** — extend `aet-validate-scope` to reconcile plan prose vs. code blocks; extend `aet-review` to verify acceptance-criterion coverage. Covers Self-Consistency Checks.

### P2 — Enhance existing skills with new lenses

1. **Context engineering & prompt-quality guidelines** — update `docs/CONVENTIONS.md` and add reference docs for skill authors. Covers Context Engineering, Prompt Engineering, and Chain-of-Thought Prompting.
2. **Red-team lens in `aet-cso`** — adversarial input generation for auth/data boundaries. Covers Red Teaming.
3. **Reflection step** — add post-implementation reflection to `aet-implement` / `aet-evolve` that writes triggered learnings. Covers Reflection Patterns.

### P3 — Reference / documentation only

1. **Spec writing & task decomposition patterns** — examples in `aet-plan/references/`.
2. **Human-in-the-loop checklist** — add to `aet-plan` and `aet-work` references.
3. **Remote sandboxing** — note as future direction in `aet-verify/references/`.

---

## 6. Recommended Next Step

The highest-leverage move is to **land the unified orchestrator first**. It is the foundation for Parallel Execution, Failure Recovery, Self-Validating Agents, and Coordination & Integration. Once it is in place, add `aet-eval` as the next skill, because measurement is the prerequisite for every other quality improvement. Only after those two foundations exist should the toolkit invest in prompt-craft reference material or red-teaming lenses.

---

_Sources: all `aet-*/SKILL.md` files, `docs/PIPELINE.md`, `docs/CONVENTIONS.md`, `docs/use-cases.md`, `docs/audits/2026-06-10-systemic-improvement-analysis.md`, `docs/prds/aet-work-parallel-execution-prd.md`, `docs/prds/aet-work-hybrid-orchestrator-prd.md`, and `docs/prds/unified-orchestrator-session-isolated-pipeline.md`._
