---
id: pkg-12-panel-framework
size: M
blocked_by:
  - pkg-05-panel-extraction
pipeline: standard
status: queued
security_review: required
security_review_reason: Adds a web-framework runtime dependency and rewrites the localhost HTTP surface — review of binding/serialization behavior required.
docs_sync: required
docs_sync_reason: Panel README/telemetry-guide must reflect the new server stack and any changed run instructions.
---

# Plan: Move the Panel Server onto a Framework (A4)

## Context

PRD: `docs/prds/aet-package-extraction-prd.md` (R-9).
`src/aet/panel/serve.py` is a raw `BaseHTTPRequestHandler` with string-matched
routing. Move it to a small framework (FastAPI + uvicorn, or Starlette —
decide at implementation; both satisfy R-9), keeping routes, JSON API shape,
and the static page byte-identical. Localhost-only binding is preserved.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Add the chosen framework + server to `pyproject.toml` runtime
   dependencies — S (traces: R-9)
2. Rewrite `src/aet/panel/serve.py` routes on the framework: `/` (static
   page), telemetry archive endpoints; identical response bodies, headers,
   and status codes; bind 127.0.0.1 only; preserve `--no-open` and browser
   launch behavior — M (traces: R-9)
3. Update `tests/test_panel_serve.py` and the `.mjs` integration scripts
   (`scripts/test-panel-live-runs.mjs`,
   `scripts/test-panel-plan-detail.mjs`) — response assertions must pass
   unmodified; update `docs/telemetry-guide.md` run instructions — M
   (traces: R-9)
4. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] Single-module server swap; separate from pkg-05 (relocation) to keep
  each diff attributable.

## Rejected Alternatives

- **Stay on stdlib `http.server`** — rejected: PRD R-9; hand-rolled routing
  and header handling is exactly the class of code the dependency policy
  retires.
- **Flask** — rejected: WSGI dev-server model is a worse fit for a
  localhost telemetry API than ASGI; FastAPI/Starlette keeps async options
  open for live-run streaming later.

## Files to Modify

- `pyproject.toml`
- `src/aet/panel/serve.py`
- `tests/test_panel_serve.py`
- `scripts/test-panel-live-runs.mjs`, `scripts/test-panel-plan-detail.mjs`
  (launch path only, if changed)
- `docs/telemetry-guide.md` (run instructions)

## Validation Steps

- [ ] Named tests pass: `tests/test_panel_serve.py` (unit),
  `scripts/test-panel-live-runs.mjs` and `test-panel-plan-detail.mjs`
  (integration) with unmodified assertions
- [ ] Response bodies/headers/status codes identical before/after (snapshot
  comparison in PR)
- [ ] Server binds 127.0.0.1 only (asserted in `tests/test_panel_serve.py`)
- [ ] `make validate` green
- [ ] R-trace coverage: R-9 by tasks 1–3; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

`git revert`; the stdlib server module returns intact. Framework dependency
can be dropped in the same revert.

---

*Stage: queued*
*Next step: run `aet-work`*
