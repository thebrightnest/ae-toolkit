---
id: rdm-01-decision-adrs
size: S
blocked_by: []
pipeline: minimal
status: approved
---

# Plan: Decision ADRs — Enforcement Boundary (020) and Evolve-in-Place (021)

## Context

- PRD: `docs/prds/roadmap-p0-decision-records-prd.md` (G1/G2; R-1…R-5)
- Sources (locked): `content/fable-review/06-2026-07-10-cli-contract-engine-discussion.md` (Resolutions 2/6, P1/P2 razors, multi-harness addendum), `08` (greenfield + restart question), `09` (roadmap decision section); ADR-011 (determinism precedent).
- Both decisions are already made and recorded in discussion docs; this plan converts them to ADRs. The implementing agent should need nothing beyond this plan and the cited sources.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Task List

1. Write `docs/adr/020-sequencing-is-not-delegable.md` per the locked outline below — S (traces: R-1, R-2)
2. Write `docs/adr/021-evolve-in-place-greenfield-trigger-gated.md` per the locked outline below — S (traces: R-3, R-4)
3. Add both entries to `docs/adr/README.md` in the existing index format — S (traces: R-5)
4. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Locked outline — ADR-020 "Scheduling Is Delegable; Sequencing Is Not; the CLI Is the Enforcement Boundary"

- **Status**: Accepted (2026-07-10). Implements PRD `roadmap-p0-decision-records-prd.md` G1; informed by fable-review 06 (+ multi-harness addendum) and 09.
- **Context**: fable-review 02 recommended demoting the local orchestrator to a portable fallback; doc 06 Resolution 2 amended it — harnesses are session-scoped while AET's pipeline is lifecycle-scoped (cross-session, cross-agent, multi-day, with a ledger); harness vendors ship mechanisms, not policy (incentive argument, doc 06 Resolution 3).
- **Decision** (numbered):
  1. Scheduling and compute (cron, CI, cloud runners) are freely delegable.
  2. Sequencing, state legality, and gate evidence are never delegated; they are enforced by the CLI layer (today `aet-work`/`aet-state`; destination: the single `aet` binary).
  3. Placement razor: if an agent ignoring an instruction would corrupt state or skip a gate, it goes in the CLI; if it would just produce worse work, it stays skill prose.
  4. Route with judgment once at plan time, enforce with code forever — no runtime conditionals in the engine.
  5. Multi-harness: inbound (any agent shells out to the CLI) is identity and universal; outbound (spawning harnesses) is a scoped adapter contract with conformance tiers — "supported" = conformance suite green in CI. Harness/model routing is workflow config, not process structure. Formulation: **substitutability, enforced in the repo, proven on the scoreboard**.
- **Consequences**: workflow-as-data becomes possible (roadmap Phase 1); skills-lint and git hooks are the second wall; no daemon — always-on is cron + run-once; per-harness support claims become CI properties, not README claims.

### Locked outline — ADR-021 "Evolve in Place; the Greenfield Is Trigger-Gated"

- **Status**: Accepted (2026-07-10). Implements PRD `roadmap-p0-decision-records-prd.md` G2; informed by fable-review 08 and 09.
- **Context**: doc 08 recommended a greenfield Go kernel; its escape rationale (unsound concurrency, dead weight) was retired the same day it was written — the frh hardening arc (frh-03…frh-17) completed 2026-07-10. Owner decision: AET is working well and stable; keep compounding the learnings in the chassis that earned them.
- **Decision** (numbered):
  1. AET evolves the existing chassis; the doc 08 greenfield is demoted to a reference design study.
  2. Four re-opening triggers, recorded verbatim: external install demand where Python distribution hurts; a second workflow class straining the chassis; the CLI identity structurally fighting Python; the embedded-skills endgame becoming strategic.
  3. Convergence commitment: plumbing decisions steer toward doc 08's shape (ledger-as-git, projections over one source of truth, frozen states) so a future port is a translation, not a redesign.
  4. A fired trigger re-opens the question only via a new ADR superseding this one — never silently.
- **Consequences**: roadmap phases 1–7 run on the current chassis; the git-refs backend flips to default in Phase 3; doc 08 stays the benchmark for every storage/state decision.

### Batching Check

- [x] These ARE near-identical additions — batched into this single plan deliberately (shared `docs/adr/README.md` index; avoids a two-plan chain over one file)
- [x] Diff expected ~3 files / ~150 lines
- [x] Cannot usefully share a branch with rdm-02 (independent concern, independent review)

## Files to Modify

- `docs/adr/020-sequencing-is-not-delegable.md` (new)
- `docs/adr/021-evolve-in-place-greenfield-trigger-gated.md` (new)
- `docs/adr/README.md`

## Validation Steps

- [ ] `make validate` passes (link check — recent learning: broken README links have bitten before)
- [ ] Both ADRs follow the `000-template.md` section structure (Status/Context/Decision/Consequences)
- [ ] `docs/adr/README.md` lists 020 and 021 in the existing format
- [ ] No source files introduced → no unit tests; the named check for this plan is `make validate` plus index-format consistency
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit; ADRs are additive documents with no code dependencies.

---

_Stage: plan-approved_
_Next step: run `aet-work`_
