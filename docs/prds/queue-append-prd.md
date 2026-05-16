# PRD: Fix work-queue.json Overwrite in aet-plan

## Overview

Update `aet-plan` and `aet-pipeline-plan` skills so that their `create-stories` / `plan` steps explicitly instruct agents to **read the existing `.agents/work-queue.json`, merge new tickets into it, and write the merged result** — never dropping existing tasks.

## Goals

- Eliminate accidental work-queue.json overwrites during planning
- Make the read-merge-write behavior explicit and unambiguous in skill instructions
- Add a lightweight validation check after queue writes

## Non-Goals

- Do not change the queue file format or schema
- Do not introduce a backup/restore system (out of scope for this fix)
- Do not modify `aet-work` queue logic

## Root Causes

1. **Language:** `aet-plan/SKILL.md` line 95 says **"Generate `.agents/work-queue.json`"** — "generate" semantically means "create from scratch."
2. **Missing step:** The work-queue generation procedure (lines 102–108) never tells the agent to read the existing file before writing.

## Changes

### aet-plan/SKILL.md

In the `create-stories` command:

1. Replace step 6:

   > **Generate `.agents/work-queue.json`** from the tickets.

   With:

   > **Merge into `.agents/work-queue.json`**. Read the existing queue file if it exists. Append new tickets to the existing array, preserving all current entries and their statuses. Do not remove or modify any existing task.

2. In the **Work queue generation** subsection, add as the first bullet:
   > - **Read first** — If `.agents/work-queue.json` exists, load it. Existing tasks must remain intact.
   > - **Merge** — Add new tasks from `docs/plans/*.md` to the existing array. Avoid duplicate IDs.
   > - **Validate** — After writing, confirm no previously existing task IDs were removed. If any are missing, restore them from the read copy.

### aet-pipeline-plan/SKILL.md

In the `plan` command, Step 2 (`aet-plan`), add a guardrail note:

> When `aet-plan` produces `.agents/work-queue.json`, it must merge new tickets into the existing queue rather than replacing it. Existing tasks must survive the planning session unchanged.

## Acceptance Criteria

- [ ] `aet-plan/SKILL.md` uses "merge into" instead of "generate" for queue updates
- [ ] `aet-plan/SKILL.md` explicitly instructs reading the existing queue before writing
- [ ] `aet-pipeline-plan/SKILL.md` reinforces queue preservation in its plan command
- [ ] Both edited skills remain under 400 lines
- [ ] `make validate` passes after edits
- [ ] `make package` produces updated `.skill` files

## Rollback Plan

Revert the two `SKILL.md` files to their pre-edit state and re-run `make package`.

---

_Stage: scope-validated_
_Next step: run `aet-pipeline-implement` (single task) or `aet-work` (multi-task queue)_
