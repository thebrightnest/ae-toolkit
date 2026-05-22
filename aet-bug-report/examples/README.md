# aet-bug-report Examples

## Example 1: Simple Runtime Error

**User request:** "Fix this bug — the API returns 500 on user registration."

**Agent workflow:**

1. **Reproduce:** Send a registration request with a test payload. Confirms 500
   with `TypeError: Cannot read property 'toLowerCase' of undefined`.
2. **Root-Cause:** Trace the error to `normalizeEmail(user.email)` where
   `user.email` is undefined because the frontend sends `emailAddress` but the
   backend expects `email`.
3. **Fix:** Update the backend controller to read `req.body.emailAddress ||
req.body.email`. Low-risk change — apply directly.
4. **Validate:** Re-run registration — 201 Created. Run existing auth tests —
   all pass.

**Output:** `docs/bugs/2026-05-21-registration-500-bug-report.md`

---

## Example 2: Subtle Logic Bug

**User request:** "There's a race condition in the job queue. Jobs sometimes
run twice."

**Agent workflow:**

1. **Reproduce:** Cannot reproduce reliably. The user says it happens ~5% of
   the time under load. Write a load test script that enqueues 100 jobs.
   After 10 runs, observe 7 duplicate executions.
2. **Root-Cause:** Use logging to trace the job lifecycle. Discover that the
   worker heartbeat timeout (30s) is shorter than the average job duration
   (45s). When a worker is processing a long job, the orchestrator marks it as
   dead and reassigns the job to another worker.
3. **Fix:** Increase heartbeat timeout to 60s, or switch to an
   in-progress acknowledgment pattern. This touches orchestrator config — pause
   for human confirmation before applying.
4. **Validate:** Re-run load test — 0 duplicates across 10 runs. Run existing
   queue tests — all pass. Invoke `aet-cso` because the fix touches job
   scheduling logic.

**Output:** `docs/bugs/2026-05-21-job-queue-race-bug-report.md`

---

## Example 3: Non-Reproducible Report (Hard Gate)

**User request:** "The dashboard feels slow."

**Agent workflow:**

1. **Reproduce:** Attempt to measure dashboard load time. Response is 120ms —
   within normal range. Cannot demonstrate unexpected behavior.
2. **Hard Gate triggers.** Stop and redirect:
   > "This appears to be a performance concern or enhancement, not a
   > reproducible bug. Use `aet-plan` to define performance targets and plan
   > optimization work."
