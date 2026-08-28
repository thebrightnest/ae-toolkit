---
type: debt
status: accepted
recorded: 2026-08-28
source: docs/bugs/20260828-fetch-discards-unpushed-record-writes.md
trigger: >-
  A second writer appears that cannot push (a read-only clone, a CI checkout), or any report of a task record losing a field again.
depends_on: []
blocks: []
---

# A forced `refs/aet/*` fetch discards local state with no diagnostic

`GitRefsBackend.fetch` fetches `+refs/aet/*:refs/aet/*`, so every `aet state`
invocation force-resets each local task ref to origin's copy. That is now safe
for the orchestrator's own writes, which replicate through
`_save_task_record`, but the fetch itself still says nothing when it overwrites a
local ref whose content differs from the remote's.

**Why accepted:** the refs hold JSON blobs, not commits, so there is no ancestry
to compare and no merge rule to apply — "the remote wins" is the only available
semantics. Push-after-write is the guard, and it is in place. A diagnostic would
have to diff blob content on every fetched ref, on a hot path that runs before
every transition.

**Trigger to fix:** a second writer appears that cannot push (a read-only clone,
a CI checkout), or any report of a task record losing a field again.
