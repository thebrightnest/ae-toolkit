---
name: aet-sync-docs
description: Sync PRD and plan.md to reflect what was actually built. Compares the original plan intent against the git diff, appends a Divergence Summary to the PRD, and updates the plan task list. Run after aet-review or aet-cso when deviations were noted, or whenever the PRD feels stale. Triggers on requests like "sync the docs," "update the PRD," "the plan changed," or "document what we actually built."
---

# aet-sync-docs

Documentation sync for agentic engineering. When implementation diverges from the plan — scope narrowed, approach changed, edge cases added — the PRD becomes stale. Stale PRDs corrupt future aet-review and aet-evolve runs by comparing against wrong expectations. This skill closes the gap.

## When to Use

- After `aet-review` or `aet-cso` noted deviations from the plan
- After `aet-implement` reported divergences
- Whenever the PRD or plan.md no longer matches the branch reality
- As the final step in the implementation pipeline (automatic)
- Manually, when a PRD feels stale after any implementation cycle

## Context

Run `aet context` and parse its JSON for session context (branch, repo
state, AGENTS.md, learnings, active plan/PRD stage); print the stage
banner it emits. Do not ask the user for this context manually.

## Commands

### `sync`

Compare the original plan against what was actually built, and update both the PRD and plan.md accordingly.

**Procedure:**

1. Identify the active plan and PRD:
   - Read the active plan content from the orchestrator context (e.g., `AET_PLAN_FILE`)
   - Read its corresponding `docs/prds/*.md` (via the plan's `PRD Reference` field or infer from filename)
2. Read the git diff for the current branch (what was actually built)
3. Compare plan intent vs. actual diff:
   - Which planned tasks were completed as described?
   - Which were changed (different approach, narrowed scope, added edge cases)?
   - Which were added (unplanned work that appeared)?
   - Which were dropped (out of scope or deferred)?
4. If **no meaningful divergences** (diff matches plan within naming/organization tolerance):
   - Skip Divergence Summary
   - Only update stages (step 6)
   - Print: `"✓ No divergences found — plan matches implementation."`
5. If **divergences found**, append a `## Divergence Summary` section to the PRD:

   ```markdown
   ## Divergence Summary

   _Recorded: {date} — Branch: {branch}_

   ### Changed from plan

   - {Task}: {what changed and why}

   ### Added (unplanned)

   - {Task}: {what was added and why}

   ### Deferred

   - {Task}: {what was deferred and when it might be addressed}
   ```

6. Update the plan.md task list:
   - Mark completed-as-planned tasks with `✓`
   - Add inline notes to changed tasks: `[Changed: {brief reason}]`
   - Mark deferred tasks: `[Deferred: {brief reason}]`
7. Update footers on both files:
   - PRD: `*Stage: synced*` / `*Next step: run \`aet-ship\`\*`
   - Plan: `*Stage: synced*` / `*Next step: run \`aet-ship\`\*`
8. Commit the updated docs with message: `docs: sync PRD and plan to implementation reality [{branch}]`

**Gate:** If no changes to PRD or plan were needed (no divergences, stage already synced), skip the commit.

**Evidence verdict (writer contract):**

Submit the stage verdict through the sanctioned writer — `aet gate submit` is the only writer of stage verdicts (G1). Do not hand-edit plan footers or queue state.

Use builder mode, which constructs the payload in code:

```bash
aet gate submit --stage sync-docs --verdict <pass|fail> \
  --summary "<one line>" --divergence "<item or file>"
```

Builder mode constructs the payload in code, stamping every schema field itself. `--divergence` is repeatable and accepts either an inline string or a file path whose contents are read. It needs `AET_TASK_ID`, which orchestrated sessions already have.

Hand-authoring the full payload and passing `--evidence <payload-file>` still works, but you would be reproducing schema fields you cannot see — the cause of past rejected verdicts. Prefer builder mode; `docs/CLI.md` carries the generated option reference.

## Completion Protocol

After `sync` completes:

1. Both files have `*Stage: synced*` in their footers.
2. Print: `"✓ Stage: synced → Next step: run \`aet-ship\`"`

## Key Principles

- **Sync is not blame** — divergences are normal; hiding them is the problem
- **PRD is the north star** — keep it accurate so future sessions start from truth
- **Minimal diffs** — only record meaningful divergences, not naming or refactor changes
- **Commit docs alongside code** — the docs update is part of the delivery, not an afterthought
- **No divergences = fast path** — skip the summary if plan matched; just advance the stage
