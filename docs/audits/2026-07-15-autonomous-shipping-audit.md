# Audit: 2026-07-15 — Autonomous Shipping & Merging

## Summary

During the 2026-07-15 session the agent shipped and merged two PRs and pushed six
commits to `main` without per-action human confirmation. This audit explains **why
the agent had that latitude**, documents **exactly what was executed autonomously**,
identifies **where the mandate was stretched**, and proposes **guardrails** to make
the autonomy boundary explicit and durable.

No plan, task, or repo change granted the agent new authority. Three factors
combined: session-level auto permission mode, the toolkit's "plans as standing
authorization" design, and a recent wave of pipeline hardening that replaced human
check-ins with mechanical gates.

## What Was Executed Autonomously (Timeline)

All times UTC. Every action below was taken without pausing for confirmation.

| Time  | Action                                                                                       | Evidence                          |
| ----- | ------------------------------------------------------------------------------------------- | --------------------------------- |
| 07:21 | First `aet run` — orchestrator halted: local `main` ahead of `origin/main`                   | run log, 7 lines                  |
| 07:22 | Diagnosed divergence: origin held 4 squash-merged feature commits; local held 4 unpushed closure commits | `git log` both directions         |
| 07:23 | Rebased 4 closure commits onto `origin/main`; resolved 4 plan-footer conflicts in favor of `merged` | commits `764a70e`..`e3bb92c`      |
| 07:23 | **Pushed** rebased closures to `main` (`97d1929..e3bb92c`)                                   | git push output                   |
| 07:24 | Retried `aet run` — full pipeline for `vgr-04-pytest-xdist-parallel` (implement → QA → review → CSO → docs-sync) | telemetry run `3d601728`          |
| ~07:55 | Ship gate: `make validate` (690 passed, fallback path), two `-n auto` proof runs (34.26s / 35.02s vs 112s) via throwaway venv (system Python is PEP 668-managed) | background task logs              |
| ~08:00 | **Created and squash-merged PR #115** (`c1f15cd`), ran `ship` closure (`b787479`), pushed, deleted branch + worktree | PR #115, merge commit             |
| 08:05 | Repaired broken `aet` CLI (global symlink had been flipped into the deleted worktree); recorded root cause in `.agents/learnings.jsonl` | `make install-skills` output      |
| 08:10 | Root-caused the recurring symlink bug: dispatcher tests mutate host `~/.local/bin` + "invoked copy wins" self-repair | `tests/test_aet_dispatcher.py:82` |
| 08:20 | **Created and squash-merged PR #116** (`d84bbb5`) with the fix; branches cleaned             | PR #116, `make validate` 692 pass |

**Net outward actions without confirmation:** 2 PRs created, 2 PRs merged, 6 commits
pushed to `main` (4 rebased closures, 1 vgr-04 closure, 1 squash merge + 1 learnings
commit via #116). No feature code was ever pushed directly to `main` — all code
arrived via squash-merged PRs.

## Why the Agent Had the Latitude

### 1. Auto permission mode (session-level directive)

The session carried an authoritative directive: approvals are handled automatically,
do not pause for confirmation prompts, make reasonable decisions and continue. This
overrode the agent's standing rule to confirm every git mutation (commit, push,
merge) on each occurrence.

### 2. Plans as standing authorization (toolkit design)

The AE Toolkit front-loads human gates:

- PRD review → plan review → explicit `status: approved` in plan frontmatter →
  explicit queue curation via `aet add`.

Once queued, the documented lifecycle treats execution — implement, QA, review, CSO,
docs-sync, ship, **PR open + merge**, closure — as delegated. `aet run` is documented
as the "night shift AFK loop." Invoking it is an opt-in to unattended execution of
already-approved work.

### 3. Recent pipeline hardening (frh-\* wave, visible in CHANGELOG 1.0.0)

Mechanical gates now stand in for human check-ins during execution:

- **Evidence-gated completion** — the orchestrator cannot mark a task
  `awaiting_merge` without real commits ahead of `origin/main` and plan-stage
  advancement (kills the empty-branch false completions).
- **Tamper-evident queue + run lease** — hand-edited queue state fails closed;
  concurrent mutation during a live run is refused.
- **Merge verification as a hard gate** — `ship` refuses branch deletion until the
  merge commit is proven on `origin/main` (ancestry, squash-SHA, or diff-equivalence).
- **Main hygiene gate** — the orchestrator halts when local `main` is ahead of
  `origin/main` (which is exactly what stopped the first run this session).

## Decision Boundary the Agent Applied

**Proceeded without asking when all of the following held:**

1. Work traced to an approved plan (`status: approved`, queued) or an explicit
   instruction ("fix it").
2. Every mechanical gate green: clean tree, `make validate`, stage footer at
   `synced`, scope audit clean, merge verified on `origin/main`.
3. Repo conventions preserved: feature work via branch + PR only, squash merges,
   no CHANGELOG/VERSION edits on feature branches.

**Surfaced instead of acting silently when off-script:**

- Flagged the off-plan `queue.py` → `aet_queue.py` rename (17 files) to the user
  rather than treating it as routine.
- Explained the diverged-`main` diagnosis before rebasing.
- Reported the CHANGELOG pre-commit rejection and deferred the entry to
  `aet-release-prep` rather than forcing it.

## Where the Mandate Was Stretched

1. **Self-merging PRs.** `aet-ship/SKILL.md` step 14 reads: closure happens "after
   the PR is created and **the user indicates it has been merged**." The agent merged
   #115 and #116 itself, reading auto mode + the AFK invocation as overriding the
   human-merge step. This is the largest interpretive leap taken in the session.
2. **Pushing without per-push confirmation.** The rebased closure commits and the
   vgr-04 closure commit were pushed to `main` directly. Low risk (metadata-only,
   unpushed local-only commits), but technically outside "confirm each git mutation."
3. **PR #116 had no plan.** "Fix it" was treated as sufficient authorization for a
   3-file bug fix; it still went through branch + PR + validate rather than direct
   commit. Reasonable, but worth noting the toolkit has no lightweight class for
   sub-plan fixes driven purely by conversation.

## Process Gaps Surfaced (Worth Fixing Regardless of Guardrail Choice)

1. **Closure commits are never auto-pushed.** `ship` commits the plan closure to
   local `main` but nothing pushes it. This session's diverged `main` (4 unpushed
   closures vs. 4 squash merges on origin) is the direct consequence and will recur
   after every pipeline run until `ship` pushes (or is documented to require it).
2. ~~**`aet` CLI symlink flip.**~~ Fixed in PR #116: worktree copies can no longer
   become the global install target, and the dispatcher tests no longer mutate host
   state.
3. **PEP 668 blind spot.** The vgr-04 acceptance criterion ("green across workers")
   could not be exercised with the system Python; proof required a throwaway venv.
   `requirements-dev.txt` exists but nothing verifies it is installed in the
   environment that runs `make test`.

## Recommended Guardrails (Pick One Boundary, Encode It Durably)

The boundary should live in `AGENTS.md` (and where relevant `aet-ship/SKILL.md`), not
in conversation, so it survives across sessions and agents.

- **Option A — Stop at PR opened (tightest).** Agent runs the full pipeline and
  opens the PR with all evidence attached, but never merges. User merges (one click);
  agent then runs closure on request. Matches the current `aet-ship` wording.
- **Option B — Auto-merge only for queued pipeline tasks (middle).** Plans that
  entered via `aet add` and passed every stage may be merged autonomously; anything
  ad hoc (no plan, conversational fixes, dependency changes) stops at PR opened.
- **Option C — Full AFK (current behavior).** Auto mode + approved plan = merge
  allowed. Keep, but fix the closure-push gap (gap 1) so `main` cannot diverge.

Independent of the choice: fix gap 1 (`ship` should push the closure commit or the
skill must state who does), since divergence breaks the next `aet run` either way.

## Open Question

Which boundary — A, B, or C — should be encoded in `AGENTS.md`? The current session
operated as C; the skill text as written implies A.
