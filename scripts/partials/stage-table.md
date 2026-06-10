## Resuming from a Stage

If `ACTIVE_PLAN_STAGE` is found, skip already-completed steps:

| Stage found | Resume from ||-------------|-------------|| `plan-approved` or `scope-validated` | Step 1 (aet-tdd) |
| `tdd-complete` | Step 2 (aet-implement) |
| `implemented` | Step 3 (aet-qa) |
| `qa-complete` | Step 4 (aet-review) |
| `reviewed` | Step 5 (aet-cso, if applicable) or Step 6 (aet-sync-docs) |
| `secure` | Step 6 (aet-sync-docs) |
| `synced` | Pipeline complete → `aet-ship` then `post-ship-verify` |
| `merged` | Pipeline complete → branch verified on `origin/main` |
