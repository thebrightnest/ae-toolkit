# Queue Reference

Operator references for the `aet` work queue. The `aet-drive` skill runs the queue;
these files describe the mechanics behind it.

- [`queue-commands.md`](queue-commands.md) — procedures for `aet sprint add`, `aet run`, `aet run-one`, cleanup, audit, and terminal transitions.
- [`parallel-execution.md`](parallel-execution.md) — concurrency caps, worktrees, and resume behavior.
- [`context-isolation.md`](context-isolation.md) — why each stage runs in a fresh process, and plan snapshot semantics.
- [`github-backend.md`](github-backend.md) — the GitHub Issues projection: labels, `gh` requirements, sync.
- [`reconcile.md`](reconcile.md) — reporting and healing drift between plans and their GitHub Issues mirror.
- [`telemetry-log-schema.md`](telemetry-log-schema.md) — the run telemetry archive and its record shapes.
- [`frontmatter-parsing.md`](frontmatter-parsing.md) — how plan frontmatter is parsed, and how it fails.
- [`upgrading-existing-project.md`](upgrading-existing-project.md) — one-time upgrade for projects on the old queue model.
