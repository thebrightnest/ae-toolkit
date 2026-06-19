---
id: abr-gate-01-fix-approval-gate
blocked_by: []
size: S
---

# abr-gate-01: Add Fix Approval Gate to aet-bug-report

## Context

- PRD: `docs/prds/aet-bug-report-fix-approval-gate-prd.md`
- Original PRD: `docs/prds/aet-bug-report-prd.md` (scope-validated)
- Skill to modify: `aet-bug-report/SKILL.md`
- Examples to modify: `aet-bug-report/examples/README.md`

## Tasks

1. **Add Step 2.5: Fix Approval Gate to SKILL.md** — S

   - Insert a mandatory gate between Step 2 (Root-Cause) and Step 3 (Fix)
   - Instruct agent to present: root-cause diagnosis, proposed fix, files to modify
   - Require explicit user approval ("yes", "go ahead", "apply it") before any code changes
   - Remove or fold the old "high-risk only" gate in Step 3

2. **Update Step 3 (Fix) preamble** — S

   - Add explicit instruction: "Only proceed here after explicit user approval from Step 2.5"

3. **Update Example 1 in examples/README.md** — S

   - Show the approval gate being used for the simple runtime error
   - Add a mock approval exchange between agent and user

4. **Trim SKILL.md if needed to stay under 400 lines** — S

   - Evaluate current line count; remove redundant wording if gate pushes it over limit

5. **Update Skill Writing Guide with interactive-only exemption** — S

   - Add note to `.agents/reference/skill-writing-guide.md` explaining that interactive-only skills may omit `AET_EXECUTION_MODE` handling
   - Document the phrasing convention: use `"Hard gate"` instead of `"Approve to proceed?"` to avoid validator false positives

6. **Update ADR 005 with interactive-only exemption** — S

   - Amend `docs/adr/005-execution-mode.md` to document that skills never invoked in unattended mode (e.g., `aet-bug-report`) are exempt from execution-mode handling

7. **Run validation and package** — S
   - `make validate` passes
   - `make package` produces valid `aet-bug-report.skill`

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

## Dependencies

None — can start immediately.

## Validation Steps

- [ ] `make lint` passes
- [ ] `make format-check` passes
- [ ] `make validate` passes fully (skill-structure validator)
- [ ] `make package` produces `aet-bug-report.skill`
- [ ] SKILL.md is under 400 lines
- [ ] Example 1 demonstrates the approval gate

## Rollback Plan

Revert the commit or restore `aet-bug-report/SKILL.md` and `aet-bug-report/examples/README.md` from git.

---

_Stage: synced_
_Next step: run `aet-ship`, then `post-ship-verify` to reach `merged`_
