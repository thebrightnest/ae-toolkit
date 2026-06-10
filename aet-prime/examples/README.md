# Examples for aet-prime

## Trivial Path: "Fix a typo in the header"

**User:** "Fix the typo 'Recieve' → 'Receive' in the page header"

**Agent (aet-prime):**

1. Loads AGENTS.md, checks branch
2. Asks intake questions:
   - Touches auth/data/infra/upgrade? **No**
   - Reproducible defect? **No** (it's a copy error, not misbehavior)
   - Estimated scope? **1 file, 1 line**
3. Class = **trivial**
4. Routes: direct edit → `make validate` → `aet-ship`
5. Does not create a plan.md, does not run `aet-plan`

## Normal Path: "Add an email field to the signup form"

**User:** "Add email validation to the signup form"

**Agent (aet-prime):**

1. Loads AGENTS.md, reads most recent PRD/plan, checks recent commits
2. Asks intake questions:
   - Touches auth/data/infra/upgrade? **No** (form field only)
   - Reproducible defect? **No**
   - Estimated scope? **2–3 files, ~30 lines**
3. Class = **normal**
4. Routes: quick plan (≤ 4 tasks) → `aet-implement` → auto checks → `aet-ship`
5. Creates lightweight plan.md, skips full PRD and `aet-verify`

## Critical Path: "Add OAuth login"

**User:** "Let users sign in with Google OAuth"

**Agent (aet-prime):**

1. Loads AGENTS.md, reads most recent PRD/plan, checks recent commits
2. Asks intake questions:
   - Touches auth? **Yes**
3. Class = **critical** (short-circuits remaining questions)
4. Routes: full PRD → `aet-tdd` → `aet-implement` → `aet-qa` → `aet-review` → `aet-verify` → `aet-ship`
5. No shortcuts permitted

## Bug Path: "The checkout button throws a 500 error"

**User:** "Clicking checkout crashes the app"

**Agent (aet-prime):**

1. Loads AGENTS.md, checks branch and recent commits
2. Asks intake questions:
   - Reproducible defect? **Yes**
3. Routes directly to `aet-bug-report`
4. Does NOT create a plan.md or enter `aet-plan`
