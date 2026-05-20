# Retro: P3-REM Branches Implemented but Never Merged

**Date:** 2026-05-20
**Severity:** High — functional code existed on branches but was invisible to `main`
**Branches involved:** `P3-REM-1`, `P3-REM-2`, `P3-REM-3`, `P3-REM-4`, `P3-REM-5`
**Resolution:** Merged all 5 branches into `main` via commit `5a1f7e9`, followed by hot-fix `6b79a12` and restore `5b9a689`

---

## What Happened

On 2026-05-19, five feature branches were created as part of the `p3-remaining-claudeapi` cleanup initiative. Each branch contained a complete, working migration of renderer IPC calls to HTTP APIs:

| Branch   | Domain                    | Commit    | Backend Added                                               | Renderer Migrated                          |
| -------- | ------------------------- | --------- | ----------------------------------------------------------- | ------------------------------------------ |
| P3-REM-1 | Project config, path, env | `c8f47f1` | `PATCH /projects/:id/path`, `GET /projects/:id/env`, etc.   | `settings.tsx`, `ProjectSetupWizard.tsx`   |
| P3-REM-2 | Media, images, PDF        | `739a460` | `GET /projects/:id/images`, `GET /images/metadata`          | `media.tsx`, `mediaStore.ts`               |
| P3-REM-3 | Flow operations           | `6cb5026` | `POST /flows/parse`, `/import`, `/export`                   | `FlowsImportTab.tsx`, `FlowsExportTab.tsx` |
| P3-REM-4 | Stripe integration        | `f8e943d` | `POST /stripe/connect`, `/disconnect`, `GET /stripe/status` | `StripeCard.tsx`                           |
| P3-REM-5 | OAuth audit + cleanup     | `923b778` | — (audit & removal)                                         | Handler/preload cleanup                    |

**None of these branches were merged into `main`.** They were pushed to `origin`, the plans were marked complete in the work queue, but the merge step was skipped. As a result:

- The renderer on `main` continued calling `window.claudeApi.*` for these domains.
- The backend HTTP handlers existed only on the feature branches.
- The preload methods had been removed on the branches but were still expected by `main`.
- When the branches were finally detected as "unmerged," it appeared as if functionality had been "erased" — when in fact it had been **built on parallel timelines that never converged**.

---

## Symptoms Observed

1. **"Missing" preload methods**: `selectSavePath`, `selectImages`, `readEnvFile`, `writeEnvFile`, etc. were reported as missing from `nativeBridge.ts` even though they had been "migrated."
2. **Deprecated warnings in production**: `window.claudeApi` deprecation logs were still firing for domains that were supposed to be cleaned up.
3. **Broken no-backend calls**: Renderer files were calling methods like `registryGet`, `getTrackedSessionBySessionId`, `listKnowledgeFiles`, `getProjectProviders`, and `upsertProjectConfig` on `window.claudeApi` — but these had never had IPC handlers. They were dead code that only worked when the HTTP API layer was present.
4. **Merge conflicts on integration**: When attempting to merge all 5 branches at once, conflicts arose in `nativeBridge.ts` and `index.ts` because each branch had removed overlapping sets of preload methods and IPC handlers.

---

## Root Causes

1. **Missing merge gate in workflow**: The plan files (e.g., `docs/plans/P3-REM-1-project-config-path-env.md`) ended with implementation and QA steps, but had no explicit **merge-to-main** checklist item. The work queue marked tasks as "merge-verified" based on branch existence, not actual integration.

2. **Feature-branch isolation without integration cadence**: Five branches were created from `main` in rapid succession (same morning). Each branch was self-consistent, but they touched overlapping files (`nativeBridge.ts`, `src/main/index.ts`). Without merging each one before starting the next, integration debt compounded.

3. **No automated branch-drift detection**: There was no CI check or bot that flagged "branch older than X days with no PR." The branches sat for ~1 day before being noticed.

4. **Plan fragmentation obscured ownership**: Splitting one plan into 5 sub-plans made it harder to see the whole picture. The work queue showed 5 "done" items, giving a false sense of completion.

---

## Resolution Steps

1. **Detected** (2026-05-19 afternoon): Running `git branch -a` showed `P3-REM-1..5` as unmerged. Renderer on `main` still had `window.claudeApi` calls in the affected domains.

2. **Merged individually** (commit `5a1f7e9`):

   - Merged P3-REM-1 → temp integration branch
   - Merged P3-REM-2 → resolved `nativeBridge.ts` conflicts (both removed `getProjectImages`)
   - Merged P3-REM-3 → resolved `index.ts` conflicts (handler registration)
   - Merged P3-REM-4 → clean merge
   - Merged P3-REM-5 → clean merge
   - Fast-forwarded `main` to the integration result

3. **Fixed broken no-backend calls** (commit `6b79a12`):

   - `registryGet` → `projectsApi.registryGet`
   - `getTrackedSessionBySessionId` → `sessionsApi.getTrackedBySessionId`
   - `listKnowledgeFiles` → `knowledgeApi.list`
   - `getProjectProviders` → `projectsApi.getProviders`
   - `upsertProjectConfig` → `projectsApi.updateProjectConfig`

4. **Restored dropped preload method** (commit `5b9a689`):

   - P3-REM-5 had removed `selectSavePath` during cleanup, but `FlowsExportTab.tsx` still needed it for the native save dialog. Restored to `nativeBridge.dialog`.

5. **Deleted legacy artifacts**:
   - Root `index.html` (295 KB, 62 `window.claudeApi` calls, obsolete)
   - `dist-src/` directory (legacy build output)
   - `scripts/protect.js` (legacy obfuscation script)
   - `electron-builder.protected.json` (legacy builder config)
   - Removed `protect`, `build:legacy`, `start:legacy` scripts from `package.json`

---

## Lessons Learned

1. **A branch is not done until it's on `main`.** Update the work queue to distinguish between "implementation complete" and "merged to main."

2. **Merge early, merge often.** When multiple branches touch the same files, integrate them sequentially rather than batching at the end. Overlapping changes to `nativeBridge.ts` and `src/main/index.ts` are high-conflict zones.

3. **Keep a single source of truth for branch status.** The work queue said "merge-verified" but `git branch --merged main` said otherwise. Use git as the ground truth.

4. **Audit for "no-backend" calls before declaring migration complete.** Methods that only existed on the flat `claudeApi` shim and had no real IPC handler were ticking time bombs. A grep for `window.claudeApi` without a matching IPC handler should fail CI.

5. **Cleanup branches need a "restore" checklist.** P3-REM-5 was an audit/cleanup branch. It correctly removed dead code, but also removed `selectSavePath` which was still live. Any removal PR should include a grep for the removed symbol across the entire tree.

---

## Action Items

| #   | Action                                                                             | Owner   | Status            |
| --- | ---------------------------------------------------------------------------------- | ------- | ----------------- |
| 1   | Add "Merge to main" as explicit final step in plan templates                       | Process | Pending           |
| 2   | Add CI check: fail if branch >24h old with no open PR                              | Infra   | Pending           |
| 3   | Add pre-merge script: grep for removed preload methods in renderer                 | Infra   | Pending           |
| 4   | Update work-queue schema to track `mergedAt` separately from `completedAt`         | Process | Pending           |
| 5   | Document high-conflict files (`nativeBridge.ts`, `src/main/index.ts`) in AGENTS.md | Docs    | Done (this retro) |

---

## Appendix: Branch Commit Details

```
P3-REM-1  c8f47f1  2026-05-19 11:43  refactor(api): migrate project config, path, and env operations to HTTP API
P3-REM-2  739a460  2026-05-19 11:43  refactor(api): migrate media/images and PDF operations to HTTP API
P3-REM-3  6cb5026  2026-05-19 11:43  refactor(api): migrate flow operations to HTTP API
P3-REM-4  f8e943d  2026-05-19 11:43  refactor(api): migrate Stripe integration to HTTP API
P3-REM-5  923b778  2026-05-19 14:02  refactor(api): audit and clean up orphaned IPC handlers and preload methods
```

All commits were authored and tested correctly. The failure was purely in the **integration step** of the pipeline.
