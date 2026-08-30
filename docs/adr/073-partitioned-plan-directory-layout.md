---
subject: partitioned-plan-directory-layout
relates: [55, 61]
---

# Partitioned Plan Directory Layout & Resilient Closure Archival

## Status

Accepted (2026-08-30). Relates to ADR-055 (Closure Durability), which supersedes
ADR-054 (Plan Documents Are Outside the Durability Gate) and carries its rule forward and ADR-061 (The Record Is the Plan After Intake). Implements the
`partitioned-plan-directory-layout` PRD
(`docs/prds/partitioned-plan-directory-layout-prd.md`).

## Context

Plan files historically lived in a flat `docs/plans/<id>.md` directory. This
created three operational tensions:

1. **Active/Draft Friction:** While drafting and iterating, operators and
   subagents create, rewrite, and experiment with plan markdown files. If
   `docs/plans/` is git-tracked, these scratch files trigger dirty working tree
   warnings and base hygiene blocks. If `docs/plans/` is git-ignored, completed
   plans cannot be committed to git history at closure.
2. **Brittle Negate Rules in `.gitignore`:** Using negative globs
   (`!docs/plans/archive/`) is notoriously brittle across tooling,
   subdirectories, and git versions.
3. **Multi-Agent / Distributed Execution Absence:** Per ADR-061 (*The Record Is
   the Plan After Intake*), the source of truth for execution after intake is the
   immutable task record (`refs/aet/tasks/<id>`). When one machine authors a task
   and pushes the task ref, and another worker executes it, the local `.md` file
   does not exist on the worker's disk. At closure, attempting a mandatory file
   move creates false errors or awkward fallback dependencies.

## Decision

1. **Partitioned Directory Structure:**
   The toolkit establishes two canonical directories:
   - `docs/plans/active/` for draft and in-flight plan files (git-ignored by default).
   - `docs/plans/archive/` for completed, merged, or abandoned plan files (versioned
     by default, or optionally ignored if the repository prefers pure git-ref storage).

2. **Transparent Discovery and Intake:**
   `aet sprint add`, `aet backlog add`, `aet plan validate`, and `aet plans lint`
   resolve plan paths transparently across `docs/plans/active/<id>.md` and legacy
   `docs/plans/<id>.md`. Linters scan both directories while excluding `docs/plans/archive/`.

3. **Non-Blocking Closure Archival:**
   At terminal closure (`aet ship merge` and `aet ship close`):
   - If `docs/plans/active/<id>.md` (or legacy `docs/plans/<id>.md`) is present on
     disk, it is moved to `docs/plans/archive/<id>.md`, creating parent directories
     if needed, and staged into git if the destination path is not git-ignored.
   - If absent, an informational notice is emitted:
     `ℹ Plan archival: No local plan file found at docs/plans/active/<id>.md; archive move skipped (spec preserved in task record).`
     Closure proceeds cleanly without error or failure.

4. **Default `.gitignore`:**
   Scaffolding and `.gitignore` templates ignore `docs/plans/active/` by default.

## Consequences

- Operators and agents author plans in `docs/plans/active/` without polluting
  `git status` or tripping base hygiene checks.
- Repositories can track `docs/plans/archive/` without negative `.gitignore` rules,
  or ignore it entirely if they prefer 100% ephemeral plans.
- Distributed and multi-agent workflows execute without friction when local plan
  files are absent on secondary workers.

## Alternatives Considered

- **Negative `.gitignore` rules (`!docs/plans/archive/`)**: Rejected because negative
  ignore patterns behave inconsistently across directory levels and nested tools.
- **Mandatory plan presence at closure**: Rejected because it violates ADR-061 by
  making closure dependent on local authoring scratch rather than the task record spec.
