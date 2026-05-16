# Product Brief: Fix work-queue.json Overwrite in aet-plan

## Problem

`aet-pipeline-plan` → `aet-plan` → `create-stories` instructs agents to **"generate `.agents/work-queue.json`"** from new tickets. Agents interpret "generate" as "create from scratch," which overwrites the existing queue and erases active tasks. There is no explicit instruction to read the existing file, merge new entries, and preserve old ones.

## Status Quo

Users only discover the overwrite after planning completes — by noticing missing tasks in the queue. Recovery is manual and error-prone.

## Wedge

Update two skill files (`aet-plan/SKILL.md` and `aet-pipeline-plan/SKILL.md`) to replace "generate" with explicit **read-merge-write** instructions. Add a validation sentence: after writing the queue, confirm no previously existing task IDs were dropped.

## Verdict

**BUILD** — Single-file skill edit with high leverage. Prevents data loss across all future planning sessions.

---

_Stage: brief-validated_
_Next step: run `aet-plan`_
