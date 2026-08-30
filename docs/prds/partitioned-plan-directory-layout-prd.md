# PRD: Partitioned Plan Directory Layout & Resilient Closure Archival

## Overview

Plan files currently live in a flat `docs/plans/<id>.md` directory. This creates a recurring operational tension:

1. **Active/Draft Friction:** While drafting and iterating, operators and subagents create, rewrite, and experiment with plan markdown files. If `docs/plans/` is git-tracked, these scratch files trigger dirty working tree warnings and base hygiene blocks. If `docs/plans/` is git-ignored, completed plans cannot be committed to git history at closure.
2. **Brittle Negate Rules in `.gitignore`:** Using negative globs (`!docs/plans/archive/`) is notoriously brittle across tooling, subdirectories, and git versions.
3. **Multi-Agent / Distributed Execution Absence:** Per ADR-061 (*The Record Is the Plan After Intake*), the source of truth for execution after intake is the immutable task record (`refs/aet/tasks/<id>`). When one machine authors a task and pushes the task ref, and another worker executes it, the local `.md` file does not exist on the worker's disk. At closure, attempting a mandatory file move creates false errors or awkward fallback dependencies.

This PRD introduces a partitioned directory layout:

- `docs/plans/active/` — authoring scratch and in-flight plans (ignored in `.gitignore` by default).
- `docs/plans/archive/` — settled plans moved at closure (versioned by default, or optionally ignored if the operator prefers 100% ephemeral plans).
- **Resilient Closure Archival:** If `docs/plans/active/<id>.md` is present on disk at closure, it is moved to `docs/plans/archive/<id>.md` and staged. If absent, an informational notice is emitted, and closure proceeds without blocking or failing.

---

## Goals

1. **Clean Workspace & Default Git Hygiene:** Operators can author plans in `docs/plans/active/` without polluting `git status` or tripping base hygiene checks.
2. **User Sovereignty Over Archival Retention:** Repositories can track `docs/plans/archive/` by default without negative `.gitignore` rules, or ignore it entirely if they prefer pure git ref storage.
3. **Resilient Distributed Archival:** Closure handles absent local plan files cleanly with an informational notice, preserving ADR-061's contract that execution depends on the task record spec rather than local files.
4. **Backward Compatibility:** All tooling (`sprint add`, `backlog add`, `plans lint`, `plan validate`) seamlessly recognizes plans in `docs/plans/active/` as well as legacy `docs/plans/`.

---

## Non-Goals

- **Mandatory Markdown Storage:** We do not force projects to commit archived plan files. Projects that prefer zero committed markdown retain full capability via task refs and `.agents/provenance.jsonl`.
- **Modifying the Task Record Schema:** The spec format inside `refs/aet/tasks/*` and `.agents/work-queue.json` remains unchanged.
- **Re-introducing Plan-Path Arguments to Execution Commands:** Per ADR-061, execution and shipping commands continue to operate on task IDs, not file paths.

---

## Requirements

### R-1: Partitioned Directory Structure

The toolkit establishes two canonical directories:

- `docs/plans/active/` for draft and in-progress plan files.
- `docs/plans/archive/` for completed, merged, or abandoned plan files.

### R-2: Transparent Discovery and Intake

`aet sprint add`, `aet backlog add`, `aet plan validate`, and `aet plans lint` resolve plan paths by checking:

1. Exact path provided (e.g. `docs/plans/active/<id>.md`).
2. Relative lookup in `docs/plans/active/<id>.md`.
3. Legacy relative lookup in `docs/plans/<id>.md`.

Corpus linters glob both `docs/plans/active/*.md` and legacy `docs/plans/*.md` (excluding `docs/plans/archive/`).

### R-3: Non-Blocking Closure Archival

At terminal closure (`aet ship merge` and `aet ship close`):

1. The closure logic checks if `docs/plans/active/<id>.md` (or legacy `docs/plans/<id>.md`) exists on disk.
2. **If present:** It moves the file to `docs/plans/archive/<id>.md`, creates parent directories if needed, and stages the destination file into git if the path is not git-ignored.
3. **If absent:** It logs an informational message:
   `ℹ Plan archival: No local plan file found at docs/plans/active/<id>.md; archive move skipped (spec preserved in task record).`
4. The closure process continues without error or failure.

### R-4: Default `.gitignore` & Template Updates

Project scaffolding, setup skills, and repo `.gitignore` templates are updated:

```gitignore
# Active/draft plan scratch
docs/plans/active/
```

### R-5: Decision Record (ADR-073)

Record the partitioned layout, optional archive tracking, and missing-file closure semantics in `docs/adr/073-partitioned-plan-directory-layout.md`.

### R-6: Skills and Conventions Synchronization

Update `skills/aet-plan/`, `skills/aet-ship/`, `docs/CONVENTIONS.md`, and `README.md` to reflect `docs/plans/active/` authoring and `docs/plans/archive/` settlement.

---

## Story Breakdown

| ID | Title | Size | Dependencies | Target Subsystems |
| --- | --- | --- | --- | --- |
| **`ppa-01-plan-discovery-and-admission`** | Support `docs/plans/active/` across admission, validation, and linting | S | — | `src/aet/admission.py`, `src/aet/plans_lint.py`, `src/aet/cli/sprint.py`, tests |
| **`ppa-02-resilient-closure-plan-archival`** | Implement non-blocking plan archival and informational notice at closure | S | `ppa-01` | `src/aet/closure.py`, `src/aet/cli/ship.py`, tests |
| **`ppa-03-adr-conventions-and-skills-sync`** | Record ADR-073, update templates, `.gitignore`, and skill documentation | S | `ppa-02` | `docs/adr/`, `docs/CONVENTIONS.md`, `skills/`, `.gitignore` |

---

## Verification Criteria

1. `aet sprint add docs/plans/active/<id>.md` successfully admits the plan into the queue.
2. `aet plans lint` scans `docs/plans/active/` without errors.
3. When `aet ship merge` runs on a machine with `docs/plans/active/<id>.md`, the file is moved to `docs/plans/archive/<id>.md`.
4. When `aet ship merge` runs on a machine *without* a local plan file, the closure logs the informational message and finishes cleanly with exit code 0.
5. All test suites pass with 100% coverage across new paths (`make validate`).
