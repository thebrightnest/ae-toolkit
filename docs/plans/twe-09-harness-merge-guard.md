---
id: twe-09-harness-merge-guard
size: M
blocked_by:
  - ewl-06-adversarial-rehearsal
pipeline: standard
security_review: required
security_review_reason: this is the enforcement mechanism for the exit-end merge boundary. A guard that fails open, misidentifies the active harness, or is trivially bypassable defeats the whole wall. The fail-closed (refuse under auto/bypass mode) and fail-safe (unsupported harness → named gap, never silent pass) behaviors are the security-critical guarantees the review must verify.
docs_sync: required
docs_sync_reason: introduces new `aet-setup` behavior (active-harness detection + a generated merge-guard artifact) and a harness-adapter interface; the setup skill and checklist change and must stay in sync with the code.
status: approved
---

# Plan: Per-Provider Merge-Guard — `aet setup` Harness Detection + Adapter Interface + Claude Code Guard

## Context

- PRD: `docs/prds/roadmap-p4-two-human-ends-prd.md` (G5; R-13, R-14). The **enforcement half** of the 2026-07-15 audit remediation.
- **Why the guard must be per-provider and live in setup:** the toolkit has **no `gh pr merge`** anywhere (`aet run` halts at `awaiting_merge`; `ship` is post-merge only) — the incident was an agent running `gh pr merge` *around* the pipeline under session auto mode. `gh pr merge` merges **server-side**, so it is **invisible to the git pre-push hook** (`aet-setup/bin/hooks` / ewl-03, which only sees local pushes). The only place to refuse it is the **harness's own tool-call layer**, which differs per provider — so `aet setup` must detect the harness and generate the matching guard.
- **Ground truth (2026-07-15):** `aet-setup/bin/hooks` is the precedent — a **self-contained, idempotent, non-clobbering generator** that writes `.git/hooks/pre-push` (marker `aet:generated pre-push shim`; refuses to clobber a non-AET hook). `aet-setup` detects the *stack* via research today but has **no harness detection**. Claude Code supports `PreToolUse` hooks (in `.claude/settings*.json`) that run **even under session auto/bypass mode** and can block a tool call — unlike a bare `permissions.deny`, which auto/bypass mode overrides (the incident's exact hole).
- **Guard scope (owner decision):** blocks **`gh pr merge` only** — it does **not** touch `git push`, so the legitimate closure push (the gap-1 `aet-bug-report` fix) and normal branch pushes are unaffected, and no sanctioned-vs-ad-hoc push disambiguation is needed.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement** (net-new enforcement capability), not a reproducible defect.

## Locked design

- **Active-harness detection** (`aet-setup/lib/harness_guard.py`): detect the operating harness from workspace/home markers (`.claude/` → `claude-code`; `.kimi-code/` → `kimi`; extensible), with an explicit override (arg/env), mirroring how setup already resolves the stack. Detection is a pure function over filesystem markers.
- **Harness-adapter interface** (same module): a minimal registry mapping `harness_id → adapter`, where an adapter exposes `generate_merge_guard(repo_root) -> None` (idempotent) and a human-readable `name`. Deliberately lightweight (registry dict + one protocol), not an elaborate class hierarchy — Phase 6 adds more entries.
- **Claude Code adapter**: generates a `PreToolUse`-class guard that refuses a Bash tool call matching `gh pr merge` (a generated guard script + the `.claude/settings*.json` hook entry that invokes it), returning a **blocking** decision so it holds under auto/bypass mode. Idempotent and **non-clobbering** (marker-based, mirrors `bin/hooks`); refuses to overwrite a non-AET guard and says so.
- **Unsupported harness → named gap (fail-safe):** an undetected/unsupported harness prints a named `"no merge-guard adapter for <harness> — deferred to Phase 6"` notice and exits non-zero from the guard-install path, **never** a silent success.
- **CLI entry** (`aet-setup/bin/harness-guard`, mirroring `bin/hooks`): `install` (detect + generate) and `check` (report what is installed) subcommands; invoked from the setup procedure.
- **Mode-1 clean:** the generated guard is the operator's *harness* config (e.g., under `.claude/`, gitignorable), not AET litter in the shared tree.

> If the diff exceeds the M limit at implementation, the clean split is **09a** (detection + registry + `bin/harness-guard` + unsupported-gap) and **09b** (Claude adapter + guard generation + its tests); the task list below is ordered to make that cut along task 2.

## Rejected Alternatives

- **A `permissions.deny` rule instead of a `PreToolUse` hook** — rejected: a bare deny does not hold under session auto/bypass mode (exactly how the incident's `gh pr merge` slipped through); the hook does.
- **Also block `git push` to `main`** — rejected for this plan (owner decision): scope is `gh pr merge` only, which avoids colliding with the legitimate closure push and needs no sanctioned-push carve-out. Expandable later.
- **A single hardcoded Claude-only guard written directly into `.claude/`** — rejected: violates the agent-agnostic mandate (AGENTS.md). The adapter interface keeps the toolkit agnostic (a generator) while emitting a provider-specific artifact.
- **Intercept the agent's shell at the toolkit layer** — rejected: the toolkit cannot intercept an arbitrary harness's tool calls; enforcement must be installed into the harness's own hook surface, which is why it is per-provider and setup-generated.

## Task List

1. `aet-setup/lib/harness_guard.py`: active-harness detection (markers + override) + adapter registry/interface + unsupported-harness named-gap path — M (traces: R-13)
2. Claude Code adapter in `aet-setup/lib/harness_guard.py`: generate the `PreToolUse` guard (script + settings hook entry) refusing `gh pr merge`; idempotent, non-clobbering, marker-based — M (traces: R-13)
3. `aet-setup/bin/harness-guard` (`install`/`check`), wired into the setup procedure — S (traces: R-13)
4. `tests/test_harness_merge_guard.py` — M (traces: R-13, R-14)
5. Docs: `aet-setup/SKILL.md` (harness-adapter interface + guard) + `aet-setup/checklist.md` (guard install step) — S (traces: R-13)
6. Merge branch to main and verify integration — S [Deferred: runs at `aet-ship`]

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions at the plan level (detection, adapter, and CLI are one vertical slice: "setup installs a merge-guard for the detected harness")
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Independent of `twe-08` (setup code vs. governance docs) — parallel worktrees; both implement the audit remediation

## Files to Modify

- `aet-setup/lib/harness_guard.py` (new)
- `aet-setup/bin/harness-guard` (new)
- `tests/test_harness_merge_guard.py` (new)
- `aet-setup/SKILL.md`
- `aet-setup/checklist.md`

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] New source coverage — `tests/test_harness_merge_guard.py`:
  - `test_detects_claude_code_from_marker`
  - `test_explicit_override_beats_detection`
  - `test_claude_guard_refuses_gh_pr_merge` (simulated `PreToolUse` invocation returns a blocking decision)
  - `test_guard_ignores_git_push_and_desk_merge` (a `git push` / `aet desk merge` command is not blocked)
  - `test_guard_install_is_idempotent_and_non_clobbering`
  - `test_unsupported_harness_named_gap_nonzero` (fail-safe: no silent pass)
- [ ] R-trace coverage: R-13 by tasks 1–3,5; R-14 (guard slice) by task 4; no unknown R-ids cited
- [ ] Generated guard is confirmed gitignorable (Mode-1 non-invasive) — install writes under the harness config dir, not the tracked tree
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. The generator and adapter are removed; any already-generated `.claude/` guard is inert operator config the owner can delete. No state migration; no effect on the pipeline (which never merged anyway).

## Pipeline

`pipeline: standard` with `security_review: required` — the review focuses on fail-closed (refuses under auto/bypass mode) and fail-safe (unsupported harness → named gap) behavior, since a guard that fails open is worse than none.

---

*Stage: reviewed*
