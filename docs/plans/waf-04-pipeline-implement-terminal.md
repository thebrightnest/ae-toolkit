# Plan: aet-pipeline-implement Terminal Resilience

## Context

PRD: `docs/prds/workflow-audit-fixes-prd.md`
Audit finding #4 (step limit aborts at commit), #6 (artifact files risk commit).

COV-R5 failed because the `kimi` agent hit the 100-step limit during `aet-pipeline-implement`. The final step was a `git commit` that failed the pre-commit hook (Prettier formatting). Uncommitted changes were left in the worktree. Additionally, pipeline-generated reports (`.review-report.md`, `.qa-report.md`, `.security-*.md`) were staged and risked being committed.

## Tasks

1. Update `aet-pipeline-implement/SKILL.md`: reserve final ~5 steps for lint-fix + `git commit` + optional `git push` when step budget is below 10 — M
2. Add "terminal mode" guidance: when step limit is approaching, only allow git/commit actions and skip non-essential stages — S
3. Update all report-generating skills in the pipeline (`aet-qa`, `aet-review`, `aet-cso`) to write reports to `/tmp/aet-reports/<task-id>/` instead of repo root — M
4. Update `aet-pipeline-implement/SKILL.md` completion protocol: remove `.review-report.md`, `.qa-report.md`, `.security-audit.md` from "Reports committed" list — S
5. Add repo root `.gitignore` rules for `/.review-report.md`, `/.qa-report.md`, `/.security-*.md` as a safety net — S
6. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

## Dependencies

- None — can start immediately.

## Validation Steps

- [ ] `make lint` passes
- [ ] `make validate` passes
- [ ] Manual: run a short pipeline and verify reports land in `/tmp/aet-reports/` not repo root
- [ ] Manual: simulate low step budget → skill instructions indicate terminal-mode actions
- [ ] Manual: verify `aet-pipeline-implement` completion protocol no longer lists reports as committed
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert modified skill files and `.gitignore` to previous commit.

---

_Stage: synced_
_Next step: run `aet-ship`, then `post-ship-verify` to reach `merged`_
