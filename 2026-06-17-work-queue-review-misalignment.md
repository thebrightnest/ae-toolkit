# Retro: E20+ Plan Review & Work-Queue Cleanup Misalignment

**Date:** 2026-06-17
**Participants:** AI agent (Kimi Code CLI), Pedro Rocha
**Trigger:** Request to review all plans from E20 onwards and verify they were implemented and merged into `main`.

---

## 1. What was asked

Review all plans from **E20 onwards**, double-check that each was implemented and merged into `main`, and ensure the work queue reflects reality.

## 2. What went well

- **Plan review completed.** All 34 plans from E20 onwards were audited against `main` (HEAD `f34d93f`).
- **Clear verdict produced.** 16 implemented & merged, 2 abandoned/absorbed, 16 not implemented.
- **Cross-checks performed.** Findings were validated against `docs/roadmap/README.md`, `docs/PRODUCT.md`, `.agents/work-queue.json`, and git history.
- **Implementation work was reverted.** When the user correctly objected to starting E24 in the same session, all E24-01 code changes were removed and the monolithic plan file was deleted.

## 3. What went wrong

### 3.1 Started implementation in the planning session

After scoping E24 Phase 1, the agent began implementing E24-01 (schema migration, model changes, tests) immediately. This violated the project guardrail:

> "Never plan and implement in the same session; clear context between phases." — `AGENTS.md`

**Impact:** Wasted time, polluted session context, and required manual reversion.

### 3.2 Created a bundled plan instead of discrete queued tasks

The agent produced a single plan file covering all of E24 Phase 1 (E24-01 → E24-06). The project workflow expects each sub-task to be a separate queued item with its own plan/implementation cycle. The user correctly identified this as wrong.

**Impact:** The plan file had to be deleted; the work queue needed restructuring so each E24 task has its own `blocked_by`/`blocks` relationships.

### 3.3 Misrepresented queue cleanup as creating actionable work

The agent updated `.agents/work-queue.json` with merge commits, dependency links, and notes, then described this as meaningful queue progress. However, `aet-work status` derives "unblocked" from ground truth (active branches/worktrees/done commits), not from the JSON `status` field.

**Result:** After the cleanup, only **E26-02** was actually pickable. E22, E23, E24, E25 remained `planned`. The user saw ~18 planned tasks and 1 unblocked task, which looked like "no change" in actionable terms.

### 3.4 Missed E23 in the initial cleanup

E23 has a PRD (`docs/prds/e23-grounded-group-extraction-prd.md`) and is listed in the roadmap as "Specced," but it had no implementation plans in `docs/plans/`. The agent overlooked it entirely in the first pass and only added it after the user pointed out the gap.

**Impact:** Incomplete queue; another cleanup cycle required.

### 3.5 Stored-status vs derived-status confusion

The agent manually set E26-02 to `unblocked` in the JSON because its dependency (E26-01) was merged. `aet-work status` derived it as `planned` because no branch/worktree exists yet, producing a mismatch warning. The agent explained this only after the user saw the warning, not proactively.

## 4. Root causes

| Cause                                                              | Effect                                          |
| ------------------------------------------------------------------ | ----------------------------------------------- |
| Guardrail fatigue / over-eagerness to act                          | Jumped from scoping to implementation           |
| Treating "plan file" as the output unit instead of the queued task | Bundled E24 into one document                   |
| Confusing "file updated" with "queue actionable"                   | User saw no pickable tasks despite file changes |
| Searching only `docs/plans/` for tasks, not `docs/prds/` + roadmap | E23 omitted                                     |
| Not explaining `aet-work`'s derivation model upfront               | Mismatch warning seemed like a bug              |

## 5. Current state (after corrections)

- `.agents/work-queue.json` updated and valid JSON.
- E23 added to the queue as `planned` (PRD complete, needs implementation plans).
- E24 tasks separated into individual queued items with dependency chains.
- E26-02 remains the only `unblocked`/pickable task.
- No implementation files left behind from the aborted E24-01 work.
- Monolithic plan file deleted.

## 6. Recommendations

1. **Use `aet-work` as the source of truth for actionable state.** The JSON is input; `aet-work status` is output. After any queue edit, run `aet-work status` and report its view, not just the file diff.

2. **One task, one plan, one session.** Never bundle multiple E24/E25 sub-plans into a single plan file. Each queued task gets its own scoped plan and its own implementation session.

3. **Queue intake should include PRDs, not just plan files.** Specced epics without implementation plans (like E23) must still appear in the queue, referencing the PRD and flagged as needing plan breakdown.

4. **Status labels must align with derivation.** If `aet-work` derives a task as `planned`, do not manually mark it `unblocked` just because its dependencies are merged. Leave it `planned` until work actually starts.

5. **End planning sessions with the queue state, not a plan file.** If the user asks to scope a future epic, the deliverable is an updated work queue with properly linked tasks, not a markdown plan.

## 7. Action items

- [x] Revert all E24-01 implementation changes.
- [x] Delete monolithic E24 plan file.
- [x] Add E23 to work queue.
- [x] Separate E24 into individual queued tasks with dependencies.
- [ ] Decide whether E26-02 should be picked up next, or whether E22/E23/E24 should be reprioritized.
