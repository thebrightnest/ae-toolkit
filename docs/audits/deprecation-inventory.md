# Deprecation and Backward-Compatibility Inventory

**Generated:** 2026-06-19
**Scope:** AE Toolkit repository (`aiskills`)
**Purpose:** Catalog every deprecated, superseded, or backward-compatible artifact so the project can decide what to remove, what to retain, and what to document.

## Summary

| Category                 | Count | Risk   | Notes                                                        |
| ------------------------ | ----- | ------ | ------------------------------------------------------------ |
| State/status legacy      | 3     | High   | Central to queue correctness; must be removed carefully      |
| Deprecated commands      | 1     | Low    | `aet-state archive` is a migration helper                    |
| Superseded storage       | 2     | Low    | `work-archive.json` and `.aet-work-orchestrator.log`         |
| Legacy plan formats      | 1     | Low    | Many plans still contain `## Dependencies` / `## Blocked by` |
| Orchestrator/run legacy  | 2     | Low    | `run-scripted` and generated orchestrators already removed   |
| Skill/validator warnings | 1     | Low    | Line-count warning for legacy skills                         |
| Superseded ADRs          | 1     | None   | ADR-010 kept for history                                     |
| Bugs / inconsistencies   | 1     | Medium | `init-queue` accepts `--history-file` but does not use it    |
| Intentional fallbacks    | 4     | None   | Resilience features, not legacy debt                         |

---

## 1. State / status legacy

### 1.1 `state` ↔ `status` coexistence shim

- **Location:** `aet-work/lib/queue.py` (lines 48–87)
- **What it is:** `_STATE_TO_STATUS`, `_STATUS_TO_STATE`, `state_to_status()`, `status_to_state()`, and `current_state()` fallback from `state` to legacy `status`.
- **Why it exists:** FODS-02 introduced `state` alongside `status` so the queue remained readable by existing tooling during the migration. FODS-06 was supposed to retire `status`.
- **Current usage:**
  - `aet-work/bin/aet-state` keeps `status` in sync after every transition (line 301).
  - `aet-work/bin/init-queue` writes both `status` and `state` (line 64–65).
  - `aet-work/bin/sync` normalizes `status` (line 131–134).
  - `aet-work/SKILL.md` documents both fields.
- **Test coverage:** `tests/test_init_queue_sync.py`, `tests/test_aet_state.py`, `tests/test_queue.py`.
- **Risk of removal:** High — every read path currently uses `current_state()`, and some consumers may still inspect `status`.
- **Removal cost:** Large (multi-file refactor of `aet-state`, `sync`, `init-queue`, `orchestrator`, tests, and skill docs).
- **Recommended action:** Schedule removal as a dedicated plan after every state write is proven to set `state` directly and no skill reads `status`.

### 1.2 Legacy terminal statuses: `done` and `merge_verified`

- **Locations:**
  - `aet-work/lib/queue.py` (`_STATUS_TO_STATE` maps both to `awaiting_merge`; line 320 normalizes `merge_verified`)
  - `aet-work/bin/sync` (lines 131–134)
  - `aet-work/bin/init-queue` (lines 58–65)
  - `aet-work/SKILL.md` (documents both as legacy)
  - `scripts/test-merge-verified-removed.sh` (TDD guard)
- **What it is:** Old terminal status strings that predate the canonical `merged` state.
- **Why it exists:** Old queue entries and some orchestrator paths historically emitted these strings.
- **Test coverage:** `tests/test_init_queue_sync.py::test_normalizes_merge_verified_to_merged`, `scripts/test-merge-verified-removed.sh`.
- **Risk of removal:** Medium — the normalization paths are centralized, but external projects may still produce `done`.
- **Removal cost:** Medium.
- **Recommended action:** Remove after confirming the live queue and all supported orchestrator outputs use only `merged`/`abandoned`. The `test-merge-verified-removed.sh` guard can be retired at the same time.

### 1.3 `aet-state derive` → `aet-state audit`

- **Location:** `aet-work/bin/aet-state` (`derive_status()` lines 160–245; `audit` command)
- **What it is:** The old derive-on-read path is now an explicit, human-run reconcile command.
- **Why it exists:** ADR-011 moved derivation off the hot path but kept the logic for occasional audits.
- **Test coverage:** `tests/test_aet_state.py::test_diff_fallback`.
- **Risk of removal:** Medium — `audit` is intentionally retained for debugging.
- **Removal cost:** Medium (would require removing `derive_status()` and all derived-status tests).
- **Recommended action:** Retain. The `audit` command is a resilience/debug tool, not legacy debt. Rename the internal helper from `derive_status` to `audit_status` if desired for clarity.

---

## 2. Deprecated commands

### 2.1 `aet-state archive`

- **Location:** `aet-work/bin/aet-state` (lines 557–590, 673–676)
- **What it is:** A command that seals terminal tasks from the live queue to history.
- **Why it exists:** Terminal tasks that became `merged` _before_ FODS-07 never triggered the new automatic live→settled seal. The command provides a one-time migration helper.
- **Current state:** Prints a deprecation warning at runtime. Documented as deprecated in `aet-work/SKILL.md` and `docs/adr/009-archive-aware-work-queue-sync.md`.
- **Test coverage:** Indirect — sealing logic is tested via terminal transitions.
- **Risk of removal:** Low.
- **Removal cost:** Small.
- **Recommended action:** Remove now, after confirming no terminal tasks remain in the live queue. At the time of this audit, the live queue contains zero terminal FODS tasks and zero legacy terminal tasks.

---

## 3. Superseded storage

### 3.1 `.agents/work-archive.json`

- **Location:** `.agents/work-archive.json` (1,522 lines)
- **What it is:** The old dedup-on-sync archive, superseded by `.agents/work-history.jsonl`.
- **Why it exists:** Historical record of terminal tasks before the live/settled partition.
- **Current state:** `sync` and `init-queue` no longer read this file; they consult `.agents/work-history.jsonl` instead.
- **Risk of removal:** Low.
- **Removal cost:** Small.
- **Recommended action:** Move to `.agents/references/work-archive-legacy.json` or delete after verifying no tool reads it. Update ADR-009 if the file is removed.

### 3.2 `scripts/.aet-work-orchestrator.log`

- **Location:** `scripts/.aet-work-orchestrator.log`
- **What it is:** An execution log from the legacy generated-orchestrator era.
- **Why it exists:** Generated by past `run-scripted` / orchestrator sessions.
- **Current state:** Not referenced by any code or skill.
- **Risk of removal:** Low.
- **Removal cost:** Trivial.
- **Recommended action:** Delete; add `scripts/.aet-work-orchestrator.log` to `.gitignore` if it is not already ignored.

---

## 4. Legacy plan formats

### 4.1 `## Dependencies` / `## Blocked by` sections

- **Location:** `aet-work/lib/plan_parser.py` (lines 121–125, 261–263); 70+ files under `docs/plans/*.md`
- **What it is:** Old prose dependency sections that `plan_parser.py` now rejects in favor of the YAML frontmatter `blocked_by` field.
- **Why it exists:** Plans were authored with human-readable dependency sections before the frontmatter contract existed.
- **Current state:** `has_legacy_dependency_section()` detects these sections and `sync`/`init-queue` fail closed when they are present.
- **Risk of removal:** Low for code; medium for human readability.
- **Removal cost:** Medium (many files to edit).
- **Recommended action:** Decide whether these sections are kept for human readers or removed. If kept, ensure they are never parsed as machine truth. A bulk cleanup plan can strip them after confirming frontmatter is complete.

---

## 5. Orchestrator / run legacy

### 5.1 `run-scripted` command

- **Location:** Historical references in `CHANGELOG.md`, `docs/adr/004-unify-aet-work-run.md`, old PRDs and plans.
- **What it is:** A removed command that generated a per-project orchestrator script.
- **Why it exists:** Already removed per ADR-004; references remain in historical docs.
- **Current state:** Not implemented; `aet-work run` now uses the unified orchestrator.
- **Risk of removal:** None.
- **Removal cost:** None.
- **Recommended action:** Retain historical mentions in PRDs/plans/ADRs. Do not reintroduce.

### 5.2 `scripts/.aet-work-orchestrator.sh`

- **Location:** Not present in repo (only the `.log` file remains).
- **What it was:** A generated per-project orchestrator script.
- **Current state:** Removed.
- **Recommended action:** None; already gone.

---

## 6. Skill / validator warnings

### 6.1 Legacy skill line-count warning

- **Location:** `scripts/validate-skills.sh` (line 58)
- **What it is:** A warning (not a failure) for existing skills whose `SKILL.md` exceeds 400 lines.
- **Why it exists:** The 400-line rule was applied retroactively; legacy skills need gradual cleanup.
- **Risk of removal:** Low.
- **Removal cost:** Medium (requires splitting long skills into references).
- **Recommended action:** Keep the warning. Address per skill as they are revised; do not bulk-change skills just for line count.

---

## 7. Superseded ADRs

### 7.1 ADR-010 — Queue State Is Derived from Persistent Facts

- **Location:** `docs/adr/010-queue-derived-state.md`
- **What it is:** ADR marked "Superseded by ADR-011."
- **Why it exists:** Historical record of the derive-on-read architecture.
- **Risk of removal:** None.
- **Removal cost:** None.
- **Recommended action:** Retain. ADRs are intentionally kept for history even when superseded.

---

## 8. Bugs / inconsistencies discovered during audit

### 8.1 `init-queue` ignores `--history-file`

- **Location:** `aet-work/bin/init-queue` (lines 33–37 accept `--history-file`; line 98 reads the queue but never reads history)
- **What it is:** `init-queue` has a `--history-file` argument and imports no `read_history`. It therefore does not skip already-settled plans, unlike `sync`.
- **Why it exists:** Likely an oversight during the FODS-07 migration.
- **Risk:** Medium — running `init-queue` can resurrect settled plans.
- **Removal cost:** Small.
- **Recommended action:** Fix `init-queue` to consult `.agents/work-history.jsonl` and skip settled plans, matching `sync` behavior. This is a bug fix, not a deprecation removal.

---

## 9. Intentional fallbacks (retain by design)

These are resilience features, not legacy debt. They should be retained and documented.

| Fallback                                 | Location                                               | Purpose                                                                                        |
| ---------------------------------------- | ------------------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| `gh` → diff-equivalence merge resolution | `aet-work/bin/aet-state` (lines 88–157)                | Resolve squash-merge SHAs when `gh` is unavailable or branch tip is not on `origin/main`       |
| `aet-verify` smoke-script fallback       | `aet-verify/SKILL.md`                                  | Run `.agents/smoke/*.sh` or `npm/pnpm/yarn smoke` when no explicit smoke command is configured |
| `aet-release-prep` keyword fallback      | `aet-release-prep/references/COMMIT-CLASSIFICATION.md` | Classify commits by keyword when conventional-commit parsing fails                             |
| `queue_updated_at` mtime fallback        | `aet-work/SKILL.md`                                    | Use queue file modification time when `queue_updated_at` is missing                            |

---

## Recommended cleanup order

1. **Immediate / low-risk**

   - Remove `aet-state archive` command and its parser entry.
   - Delete or archive `.agents/work-archive.json`.
   - Delete `scripts/.aet-work-orchestrator.log` and ensure it is gitignored.
   - Fix `init-queue` to respect `--history-file`.

2. **Short-term**

   - Decide the fate of `## Dependencies` / `## Blocked by` sections in plan files; bulk-convert or explicitly ignore.

3. **Medium-term**

   - Remove `done` / `merge_verified` normalization paths after verifying all producers emit canonical terminal states.

4. **Long-term**

   - Remove the `state` ↔ `status` coexistence shim and make `state` the only stored field. This is the largest cleanup and should be its own plan.

5. **Permanent retention**
   - ADR-010 and historical PRD/plan mentions of `run-scripted`.
   - Intentional fallbacks listed in section 9.
   - Legacy skill line-count warning until all skills are under 400 lines.
