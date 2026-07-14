---
id: ewl-07-non-invasive-config-root
size: M
blocked_by:
  - cli-03-skills-lint
  - uct-01-usage-cost-telemetry
  - ewl-04-git-refs-default-flip
pipeline: standard
security_review: required
security_review_reason: introduces a config-resolution precedence (env → external root → in-tree → defaults) and a new config-write location; a precedence bug could silently read the wrong config or write AET config into a shared repo it was meant to stay out of — the correctness of that precedence is the property this plan delivers
docs_sync: required
docs_sync_reason: introduces a non-invasive config setup path (AET backend/mode config resolvable from outside the repo); configure-backend and setup docs must describe where config lives and the resolution order
---

# Plan: Non-Invasive External Config Root

## Context

- PRD: `docs/prds/roadmap-p3-enforcement-walls-prd.md` (G5; R-9, R-10, plus R-8 tests)
- **Why this exists:** in some projects the owner cannot enforce AET on the team, so AET must run without requiring any AET _config_ committed to the shared repo (owner reconsidering mandatory GitHub across clients on Azure DevOps, GitHub, and file-only projects, 2026-07-12). **Plans and PRDs are versioned project artifacts and stay in `docs/` — only the AET backend/mode config leaves version control** (owner decision, 2026-07-12).
- **This is a narrow, finishing move — config is the last leak.** The codebase already keeps its state external: gate-evidence at `~/.aet/reports/{slug}/` (ADR-019), telemetry at `~/.aet/telemetry/{slug}/` (ADR-012), a locally-derived slug that works for remoteless repos (ADR-022, which also **rejected** a "stable project-id file committed per repo … repo litter"). The task queue/history (`.agents/work-queue.json`, `.agents/work-history.jsonl`) are already gitignored (`.gitignore:10,13`) and ewl-04 moves them into `.git` (`refs/aet/*`, unpushed). That leaves exactly one un-gitignored `.agents/` file — the backend/mode config `.agents/aet-work.json` — as the only AET artifact that would still surface in a client repo's `git status`. This plan makes that config resolvable from outside the repo.
- **Concrete seam:** `aet-work/lib/backends/factory.py` `_read_config` today reads only the single in-tree `.agents/aet-work.json`. This plan extends it to an external-first precedence; `derive_project_slug()` (ADR-022) already gives the `{slug}`.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- **Config resolution is external-first**, so keeping AET config out of a repo never itself requires an in-tree file: **env** (`AET_PROJECT_ID` already scopes the slug; add a direct config/path override only if warranted) → **external** `~/.aet/{slug}/config.json` → **in-tree** `.agents/aet-work.json` → built-in defaults. `{slug}` comes from the existing `derive_project_slug()` (ADR-022) — the same identity already naming `~/.aet/reports/{slug}/` and `~/.aet/telemetry/{slug}/`. `factory.py` `_read_config` walks this precedence rather than reading the single in-tree path. This closes the chicken-and-egg where the file that says "keep AET out of the repo" would otherwise have to live in the repo (R-10).
- **Plans and PRDs are untouched.** They stay versioned in `docs/plans/` and `docs/prds/` exactly as today — they are project artifacts, not tooling, and nothing about them is relocated. (This is the correction to the earlier "external state root" framing: only config moves.)
- **`aet-setup` chooses where to _write_ config; there is no persisted mode.** For a non-invasive project it writes `~/.aet/{slug}/config.json` and touches nothing in the repo; for self-hosting it writes the in-tree `.agents/aet-work.json` as today. Because reads are always external-first, a `sidecar|in-repo` mode enum is unnecessary — the write location is the only choice, made once at setup.
- No change to git-refs/JSON backend internals, to evidence/telemetry paths (already external), or to how plans/PRDs are written. This plan is additive: an external-first config precedence plus a setup option to write config externally.
- **Validation note (2026-07-12):** `derive_project_slug()` currently lives in `aet-work/lib/telemetry.py:66`. The resolver should obtain the slug from a neutral identity/paths helper (relocate the function if needed) rather than importing `telemetry` into the backend factory — avoids a backends→telemetry layering inversion.

## Rejected Alternatives

- **Relocating plans/PRDs to the external root too (the earlier "sidecar state root")** — rejected: plans and PRDs are versioned project artifacts (owner decision, 2026-07-12), not AET tooling; only the backend/mode config leaves version control. This also removes ewl-07's earlier dependency on moving closure into the ledger (the reverted ADR-025): the plan file stays versioned, so plan-file `status` remains a durable closure record (ADR-011/013) with nothing to change in Phase 3.
- **A `sidecar | in-repo` project-mode enum** — rejected as unnecessary once only config moves: external-first read precedence plus `aet-setup`'s write-location choice deliver the same outcome without a persisted mode flag to keep in sync.
- **Gitignoring `.agents/aet-work.json` in-repo instead of externalizing it** — rejected: adding the `.gitignore` entry is itself a committed edit to a shared file, so it fails the "nothing required in the client repo" bar (R-9). The external config needs nothing in the repo at all.
- **A committed per-repo config-select file** — rejected: exactly ADR-022's rejected "committed per-repo project-id file … repo litter," and it reintroduces the chicken-and-egg R-10 exists to remove.

## Task List

1. ✓ Extend `factory.py` `_read_config` to the external-first precedence (env → external `~/.aet/{slug}/config.json` → in-tree `.agents/aet-work.json` → defaults), resolving the external path via `derive_project_slug()` — S (traces: R-9, R-10)
2. ✓ `aet-setup`/`configure-task-backend`: add the option to write config to `~/.aet/{slug}/config.json` for a non-invasive project (nothing written in-repo); messaging states where config resolves from and the precedence — S (traces: R-9, R-10)
3. ✓ Tests: `tests/test_config_resolution.py` (new) — precedence (env > external > in-tree > default); a non-invasive setup keeps the tracked tree free of AET _config_ and pushes no `refs/aet/*`; in-tree config resolves unchanged — S (traces: R-9, R-10, R-8)
4. ✓ Docs: non-invasive config setup + resolution order, in `docs/CONVENTIONS.md` or a dedicated setup doc — S (traces: R-9, R-10)
5. [Deferred: runs at `aet-ship`] Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not a near-identical addition to anything queued
- [x] Diff expected ~4 files / ~130 lines (config precedence + setup messaging + tests + docs)
- [x] Cannot share a branch with ewl-04 — ewl-04 flips the backend default in the same `factory.py`; this layers external-first resolution on top and must land after it (blocked_by edge), not beside it

## Files to Modify

- `aet-work/lib/backends/factory.py`
- `aet-setup/bin/configure-task-backend` (and/or the setup entry point that writes config)
- `docs/CONVENTIONS.md` (or a new non-invasive-setup doc)
- `tests/test_config_resolution.py` (new)

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] New source coverage — `tests/test_config_resolution.py`:
  - `test_default_when_no_config_present`
  - `test_in_tree_config_resolves_unchanged`
  - `test_external_config_resolves_under_home_aet_slug`
  - `test_precedence_env_over_external_over_in_tree`
  - `test_noninvasive_setup_leaves_tracked_tree_free_of_aet_config`
- [ ] Manual: with config written to `~/.aet/{slug}/config.json`, a plan→ship lifecycle on a scratch repo leaves `git status` free of AET _config_ and the remote free of `refs/aet/*` (plans/PRDs in `docs/` are expected versioned artifacts); the same with in-tree `.agents/aet-work.json` resolves unchanged (satisfies R-9, R-10)
- [ ] R-trace coverage: R-9 by tasks 1–4; R-10 by tasks 1, 2, 3; R-8 by task 3; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit — `_read_config` returns to reading the single in-tree `.agents/aet-work.json`. Any external config a project wrote under `~/.aet/{slug}/` stays on disk (external, not in the repo); it is simply no longer resolved until re-applied. No in-tree behavior changes, and plans/PRDs were never touched.

## Pipeline

`pipeline: standard`.

---

_Stage: synced_
_Next step: run `aet-ship`_
