# Examples for aet-verify

## Feature Mode — API Endpoint

Verify a new `/api/users` endpoint after implementation:

```bash
# Start the dev server
make dev &

# Capture the evidence
curl -s -w "\n---STATUS:%{http_code}\n" http://localhost:3000/api/users \
  -H "Accept: application/json" \
  -o /tmp/aet-reports/clv-01/evidence/feature-20260610-users.json

# Verify status code and response structure
```

Evidence file (`feature-20260610-users.json`):

```
---
mode: feature
task: clv-01
tool: curl
timestamp: 2026-06-10T14:30:22Z
---
[
  {"id": 1, "name": "Alice"},
  {"id": 2, "name": "Bob"}
]
---STATUS:200
```

## Foundation Mode — Smoke Output

Run substrate checks before a critical auth refactor:

```bash
make smoke
```

Expected output:

```
[SMOKE] Boot .................. PASS (startup 1.2s)
[SMOKE] Auth .................. PASS (login + session)
[SMOKE] CRUD (projects) ....... PASS (create, read, update, delete)
[SMOKE] Database .............. PASS (response 12ms)
[SMOKE] Cache ................. PASS (hit ratio 94%)
---
All checks passed. Substrate healthy.
```

If any check fails, stop and fix the substrate before proceeding.

## Reproduction Mode — Bug Report

A bug report says: "Clicking 'Delete' on a project with 100+ tasks hangs indefinitely."

Reproduction steps:

1. Seed a project with 100 tasks: `make seed-large-project`
2. Navigate to the project detail page
3. Click the Delete button
4. Capture: browser screenshot after 30s, server logs, network tab HAR

Evidence saved to `/tmp/aet-reports/bug-42/evidence/` with timestamped filenames.
