# Night-Shift Failure Handling: Quarantine State, Circuit Breaker, Triage-by-Default

## Status

Accepted (2026-07-16). Roadmap Phase 5 (`content/fable-review/09-2026-07-10-roadmap.md`). Extends the deterministic state model of ADR-011 and applies the razor of ADR-020. Consistent with ADR-005's unattended-execution model but does **not** modify its "gates that must still stop" list.

## Context

The overnight shift cannot survive its own failures. Today a failed task is marked `failed` and left until morning (`_mark_failed`, `aet-work/bin/orchestrator:1125`); there is no classification, retry, quarantine, or hang handling. Two bad outcomes follow: a single deterministic failure (a real `design` bug) is either ignored or blindly re-attempted, and one broken environment can fail task after task, draining the whole queue's budget before dawn.

The fix must respect two standing decisions. ADR-011 froze workflow state as *recorded forward, deterministic, never re-guessed from lossy signals*. ADR-020 drew the razor: *route with judgment once at plan time, enforce with code forever — no runtime conditionals in the engine.* Failure handling appears to strain the razor, because how a task fails is knowable only at runtime, not at plan time. That tension is the crux this ADR resolves.

## Decision

1. **A new `quarantined` state.** `{in_progress, failed} → quarantined`, and `quarantined → {ready, abandoned}` only. It is **non-actionable** (the scheduler never re-picks it) and **non-terminal** (it does not satisfy blockers — a quarantined task did not succeed). It is distinct from `failed` (retry-eligible) and from `abandoned` (human-terminal). The state machine enforces "do not retry," rather than the orchestrator remembering it — squarely ADR-011.

2. **A code-owned failure taxonomy and signature.** Every terminating session is classified into a fixed menu — `environment | flaky | design | timeout | canceled` — and given a **normalized signature** `sha1(stage + normalized-error)` with volatile spans stripped. Both are pure, deterministic functions (`aet-work/lib/failure.py`). The signature is the key the breaker counts; identical failures collide, distinct ones do not.

3. **A circuit breaker, deterministic and persisted.** *Per-task:* the same signature 3× ⇒ the task is quarantined instead of requeued. *Systemic:* one signature across N=3 distinct tasks ⇒ the shift stops spawning, drains, and exits with a named report. Counts persist to the git-refs ledger (`refs/aet/breaker`), so a deterministic failure stays quarantined across shifts. `canceled` failures are excluded from the tallies (a clean stop is not breaker evidence).

4. **`--on-failure={triage|continue|halt}`, default `triage`.** On a failure the engine classifies, consults the breaker, and — if not breaker-quarantined — spawns a **cheap triage session** that confirms the class and routes: `flaky`/`environment` ⇒ requeue (`failed → ready`), `design` ⇒ quarantine. Triage fails closed to the deterministic classifier's default and is always bounded by the per-task breaker, so it cannot loop. `continue` reproduces today's mark-failed-and-continue; `halt` stops on first failure.

**The ADR-020 reconciliation (the load-bearing point).** Failure is an inherently *runtime* event — it cannot be routed at plan time because a plan cannot know it will fail or how. The razor is honored by *where the judgment lives*: the breaker's counting and quarantine decision are **deterministic code** keyed on a deterministic signature (no hidden conditional, no DSL, no AI discretion in the engine's control flow); the only judgment — retry vs quarantine for the ambiguous middle — lives in an **explicit, sanctioned triage session** whose verdict the engine merely *enforces*, exactly as it enforces a review or QA stage's verdict. The engine gains no embedded runtime conditional; it gains one more evidence-producing session. Triage-by-default is the night-shift default because an unattended shift that stops at the first failure is not a night shift.

## Consequences

- The shift survives failures: an injected failure costs one task, not the run. Deterministic failures stop burning budget; a broken environment stops the shift cleanly instead of failing twenty tasks.
- A quarantine sticks across shifts, so a `design` failure is not re-attempted every night until a human fixes and clears it.
- New surface to maintain: one more state across `aet-state`, the panel, and the docs; and a triage session costs one cheap session per failure (capped by the breaker).
- The retry-vs-quarantine judgment is auditable (a triage verdict), and the counting is reproducible (a deterministic signature) — the two halves the razor asks for.

## Alternatives Considered

- **Reuse `failed` + a `quarantine: true` flag** — rejected: `failed → in_progress/ready` is legal, so a flagged task stays selectable; correctness would depend on every picker honoring a flag. A distinct non-actionable state makes "do not retry" a property of the machine (ADR-011), not a convention.
- **In-memory breaker counts** — rejected: a deterministic failure would be re-attempted every shift; cross-shift persistence is the whole point of quarantine.
- **LLM-classify for the breaker's counting key** — rejected: the counting key must be deterministic so identical failures always collide; an LLM key makes the breaker non-reproducible. (The triage *session* may use judgment for the action; the *key* may not.)
- **`continue` as the default** — rejected: leaves failures to rot until morning, defeating the phase.
- **`halt` as the default** — rejected: contradicts the night-shift goal; a single failure would end the run.
