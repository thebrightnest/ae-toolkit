# Retro: 2026-06-08 — AI Model 404 Cascade

## What Went Well

- The code fix was correct on first attempt: replace hardcoded `gemini-1.5-pro` with `os.getenv("GOOGLE_MODEL", "gemini-3.5-flash")`.
- Rebase + push to `origin/main` succeeded cleanly after resolving one `exceptions.py` conflict.

## What Went Poorly

- The fix had been applied **twice before** and kept regressing. The user explicitly called out "bad worktree/branch management."
- The running `make dev` session was started at 17:24, **hours before** the fix commit at ~23:04. Uvicorn had the old model string in memory.
- The fix existed **only on local `main`** — `origin/main` still had the old hardcoded `gemini-1.5-pro`. Local was 3 commits ahead, 9 commits behind origin.
- No existing agent command or guardrail directed us to check "running process vs disk code" or "local branch divergence from origin" before debugging a service error.
- Time was wasted reproducing an error that was already fixed on disk but not in memory or upstream.

## Root Cause

**Missing layer:** `.agents/commands/`. The directory has only a README. There is no reusable workflow for debugging the common pattern: _"error persists even though the code on disk looks fixed."_

**Contributing factor:** `api-conventions.md` covers dev topology (queue workers, filesystem paths) but omits service-freshness checks when diagnosing runtime errors.

## Action Items

- [x] Create `.agents/commands/debug-service-mismatch.md` — reusable workflow for stale-process / branch-divergence diagnosis (agent)
- [x] Add service-freshness note to `api-conventions.md` → Dev Topology section (agent)
- [x] Log learning in `.agents/learnings.jsonl` (agent)
- [ ] User: review `.agents/commands/debug-service-mismatch.md` and confirm it matches local mental model
