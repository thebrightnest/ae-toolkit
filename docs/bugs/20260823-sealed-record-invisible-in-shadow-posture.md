# A settled task reports "Task not found" in shadow posture

**Date:** 2026-08-23
**Status:** fixed
**Source:** `content/bugs/open-items.md` item 9 (found while fixing item 7)

## Symptom

Re-running a closure against an already-settled task fails instead of being
idempotent:

- `aet state record-merge <id>` → `Task not found: <id>`, exit 1
- `aet ship close <id>` (`src/aet/cli/ship.py:196`) → same

R-4 makes these commands idempotent on settled tasks, precisely so an
interrupted closure can be resumed. Instead the operator gets a message
saying the task does not exist, which misdescribes the cause: the task
settled successfully.

This affects **shadow posture**, which `create_backend` infers whenever no
in-tree project-scope config is the effective source — the default for any
project nobody configured. The common case, not an edge case.

## Reproduction

Seal a merged task in a bare repo (shadow posture), then resolve it:

```
posture: shadow
seal returned state: merged
history file exists: False
settled_ids: {'t1'}
resolve_task_record -> task=None sealed=None
```

The tombstone is present and `settled_ids` sees it. `resolve_task_record`
does not.

## Root cause

`resolve_task_record` (`src/aet/cli/aet_state.py`) looked for sealed records
in one place only:

```python
history_file = getattr(backend, "history_file", None)
if history_file:
    sealed = find_task(queue_lib.read_history(history_file), task_id)
```

Shadow posture never writes that file. `GitRefsBackend.seal` skips the
`append_history_record` call by design — "in shadow posture the history file is
not written: AET leaves no artifact in the working tree".

What `seal` *does* write, in every posture, is the tombstone blob at
`refs/aet/sealed/<id>`, in the same atomic transaction as the task-ref
deletion (ADR-055). It carries the full record. Nothing consulted it.

So the durable record existed the whole time, in the one place the resolver
never looked. The failure is silent in the worst way: it presents as a missing
task rather than as an unreadable store.

## Fix

1. `GitRefsBackend.read_sealed(task_id)` returns the tombstone record, or
   `None` when the ref is absent. A corrupt or partial blob reads as absent
   rather than raising, matching how `load` treats an unreadable task ref.
2. `resolve_task_record` consults, in order: the live queue, the tombstone,
   then the history JSONL. The tombstone comes first because it is the record
   that always exists; the JSONL remains as a fallback for records sealed
   before tombstones existed (ADR-055).

`read_sealed` lives on `GitRefsBackend` rather than `TaskBackend`, following
the precedent set by `settled_ids`: ref-namespace methods belong to the backend
that owns the namespace, and `create_backend` returns that type
unconditionally.

Files: `src/aet/backends/git_refs_backend.py`, `src/aet/cli/aet_state.py`,
`tests/backends/test_shadow_posture.py`.

## Validation

- New regression test verified to fail without the fix and pass with it.
- `tests/backends`, `tests/state`, `tests/ship` — 297 passed, 2 skipped.
- Full suite green.

## Lesson

Two stores held the same fact, one of them conditionally. The resolver read the
conditional one. Whenever a record is written to more than one place under
different conditions, the reader has to consult the one with the weaker
condition first — or, better, the write should not be conditional at all.
