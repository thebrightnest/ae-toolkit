# PRD: Learning Ratchet

## Overview

`aet-evolve` is described as "the highest-leverage long-term skill," but its current design leaks lessons. Error-swallowing was retroed and "fixed" in the Electron project on May 11 — then bit the Laravel project twice on June 7. Action items from retros go unchecked. The model-404 fix had been "applied twice before and kept regressing" with no escalation. And retrieval from `learnings.jsonl` is pure vibes: "top-3 relevant entries" with no operational matching mechanism.

This PRD turns the learning loop into a **ratchet**: lessons that propagate across projects, action items that close, recurrences that escalate up the enforcement ladder, and retrieval triggered by operational match rules.

## Goals

1. **Cross-project feedback channel** — `reports/` becomes a defined interface. Project retros write toolkit-relevant findings in a standard format; a periodic `aet-evolve --toolkit` pass mines them for patterns.
2. **Action item closure** — `aet-evolve retro` starts with a "retro debt" check: previous action items are verified done, converted to queue tasks, or explicitly dropped.
3. **Escalation ladder on recurrence** — when a new incident matches an existing learning, enforcement moves up: documentation → checklist item → review lens → executable gate.
4. **Operational retrieval** — add a `trigger` field to the learning schema so matching is based on what the agent is doing ("when touching test factories", "when writing catch blocks") rather than semantic similarity.

## Non-Goals

- Rewriting the entire `aet-evolve` skill from scratch. We extend the existing skill.
- Automatic PR creation or issue filing across projects. The feedback channel is read-only mining.
- Replacing `learnings.jsonl` with a database. The format stays JSONL; the schema evolves.

## User Stories

- As a developer on a new project, I want the toolkit to already know about the error-swallowing trap that burned the last team, not rediscover it.
- As a retro facilitator, I want unchecked action items from previous retros surfaced automatically so they don't rot.
- As a toolkit maintainer, I want a third recurrence of the same bug class to automatically become a hard gate, not another doc update.
- As an agent, I want relevant learnings surfaced based on what I'm currently editing, not a random top-3 sample.

## Acceptance Criteria

- [ ] `aet-evolve/SKILL.md` updated with `--toolkit` flag and cross-project mining procedure.
- [ ] Learning schema updated to include `trigger` field (string or list of keywords).
- [ ] `aet-evolve retro` procedure updated to include "retro debt" check at step 1.
- [ ] Escalation ladder documented: doc → checklist → lens → gate, with explicit criteria for each transition.
- [ ] `reports/` convention documented: standard header format for toolkit-relevant retros.
- [ ] Preamble in affected skills (`aet-tdd`, `aet-implement`, `aet-qa`) updated to use `trigger`-based retrieval instead of "top-3 relevant".
- [ ] `aet-evolve` stays under 400 lines; new detail lives in `references/`.

## Open Questions

1. Should `aet-evolve --toolkit` be a manual periodic run, or triggered automatically when a new retro is added?
2. How do we distinguish "toolkit-relevant" retros from project-local retros in the `reports/` directory?
3. Should the escalation ladder be stored in `learnings.jsonl` per-learning, or in a separate `toolkit-gates.jsonl`?

---

_Stage: scope-validated_
_Validated: 2026-06-10_
_Notes: No conflicts. Schema addition (trigger field) is backward-compatible with existing learnings.jsonl. Escalation ladder documentation lives in aet-evolve/references/ to keep SKILL.md under 400 lines._
