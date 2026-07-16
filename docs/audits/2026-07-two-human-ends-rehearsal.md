# Phase 4 Exit-Gate — End-to-End Rehearsal

**Date:** 2026-07-16
**Scope:** `twe-07-exit-gate-rehearsal` — Phase 4 exit-gate demonstration (roadmap P4 PRD G4, G5; R-10, R-11, R-14), executed after twe-03 (desk merge/abandon), twe-05 (intake-gate wiring), twe-06 (zero-review mechanism, shipped OFF), and twe-09 (per-provider merge guard) landed on `origin/main`.
**Question:** Do the four exit-gate claims hold when exercised together on already-shipped code — desk merge reaches `merged`, intake rejects a bad plan, zero-review stays off by default, and the merge guard refuses an agent-issued `gh pr merge` while leaving sanctioned paths open?

**Verdict, up front:** all four claims hold. (a) **PASS** — `aet desk merge <id>` drove the closure path and the task reached `merged` with the plan footer updated. (b) **PASS** — `aet add` rejected a plan missing its PRD reference with a named error and left the queue unmutated. (c) **PASS** — the shipped default policy shows every class disabled; the twe-06 test suite proves the mechanism would fire only when a class is explicitly enabled *and* its threshold is met. (d) **PASS** — the generated Claude Code `PreToolUse` guard refused a simulated `gh pr merge` under Bash and allowed `git push` and `aet desk merge`; one honest finding: `aet harness-guard check` looks for the AET marker in `settings.json` instead of the guard script, so it incorrectly reports "not installed" even after a successful install.

## Method

- Code under test: the globally installed `aet` CLI symlinks to `/Users/pedrorocha/Sites/aiskills/aet-work/bin/aet`, which exercises the merged twe-03 / twe-05 / twe-06 / twe-09 code at `origin/main` (`3e7f72d`).
- All rehearsals ran in a scratch repository under `/tmp/twe-07-rehearsal/` with a temporary GitHub remote (`pedrorocha-net/twe-07-rehearsal-temp`). No mocks: real `aet add`, real `aet state transition`, real `aet desk merge`, real `gh pr create` / `gh pr merge --squash`, real `aet harness-guard install`, and direct invocation of the generated guard script.
- The scratch repo was initialized with `docs/plans/` and `docs/prds/` directories and a minimal PRD carrying R-10 and R-11.

## (a) Desk merge — PASS (traces: R-10, R-11)

Setup: add a clean plan, create a feature branch, open a PR, advance the task to `awaiting_merge`, then merge from the desk.

```text
$ aet add docs/plans/reh-a-desk-merge.md
✓ Added reh-a-desk-merge.md to the queue as ready.
[exit 0]

$ git checkout -b reh-a-desk-merge && echo "feature work" > feature.txt && git add feature.txt && git commit -m "Add feature work for rehearsal (a)" && git push origin reh-a-desk-merge
Switched to a new branch 'reh-a-desk-merge'
[reh-a-desk-merge d47e932] Add feature work for rehearsal (a)
[exit 0]

$ gh pr create --base main --head reh-a-desk-merge --title "Rehearsal (a): desk merge" --body "Scratch PR for twe-07 exit-gate rehearsal."
https://github.com/pedrorocha-net/twe-07-rehearsal-temp/pull/1
[exit 0]
```

The task branch was recorded in the queue (a small helper script used the JSON backend to set `task["branch"]`), then the task was advanced through the public state machine:

```text
$ aet state transition reh-a-desk-merge ready in_progress
Transitioned reh-a-desk-merge: ready -> in_progress
[exit 0]

$ aet state transition reh-a-desk-merge in_progress awaiting_merge
Transitioned reh-a-desk-merge: in_progress -> awaiting_merge
[exit 0]

$ aet status
awaiting_merge: 1
[exit 0]
```

The actual desk merge:

```text
$ aet desk merge reh-a-desk-merge
Recorded merge for reh-a-desk-merge: 21fa2ca8ff7fb2c757add0213e6fd2152d2d7e77 (squash)
[exit 0]

$ aet status
awaiting_merge: 0
[exit 0]
```

After the merge the plan footer reads `_Stage: merged_`, confirming the closure path updated the tracked plan file as well as the queue. The merge commit was resolved by the `gh pr view` / diff-equivalence fallback because the PR was squash-merged; the important property is that `merged` was written by `aet-state record-merge`, preserving the single closure writer.

## (b) Intake rejection — PASS (traces: R-10)

A plan that fails the twe-04 validation suite is refused at `aet add` before the queue is mutated.

```text
$ cat docs/plans/reh-b-intake-reject.md
---
id: reh-b-intake-reject
size: S
status: approved
---

# Plan: Rehearsal (b) — Intake rejection

This plan is intentionally missing required sections so the intake gate has something to reject.

---

*Stage: plan-approved*

$ aet add docs/plans/reh-b-intake-reject.md
⛔ Refusing to add reh-b-intake-reject.md: intake validation failed.
  - rtrace: no PRD reference found in plan context
[exit 1]

$ aet status
planned: 0
[exit 0]
```

The refusal is named (`rtrace: no PRD reference found in plan context`) and the queue remains empty — no task was admitted.

## (c) Zero-review present-but-off — PASS (traces: R-10)

The shipped default policy leaves every class disabled:

```text
$ aet desk --eligibility
Zero-review eligibility (clean-merge count / enabled / threshold):
  trivial  count=  0 enabled=no  threshold=- (not met)
  normal   count=  0 enabled=no  threshold=- (not met)
  critical count=  0 enabled=no  threshold=- (not met)
[exit 0]
```

To show the contrast — the mechanism is present and would fire only with an explicit enable + met threshold — the twe-06 regression tests were re-run:

```text
$ python3 -m pytest tests/test_zero_review.py::TestEligibilityReporting::test_default_policy_empty_nothing_auto_merges tests/test_zero_review.py::TestAutoMergeAction::test_enabled_class_at_threshold_auto_merges_via_closure_path -v
tests/test_zero_review.py::TestEligibilityReporting::test_default_policy_empty_nothing_auto_merges PASSED
tests/test_zero_review.py::TestAutoMergeAction::test_enabled_class_at_threshold_auto_merges_via_closure_path PASSED
============================== 2 passed in 0.06s ===============================
```

The default-off guarantee holds today; the enabled-and-qualified path is proven by the same suite.

## (d) Merge-guard holds — PASS (traces: R-14)

Setup: run `aet harness-guard install` in the scratch repo. The harness was detected from the `.claude/` marker and a `PreToolUse` hook was written.

```text
$ mkdir -p .claude && aet harness-guard install
installed claude-code merge guard -> /private/tmp/twe-07-rehearsal/.claude/settings.json
[exit 0]
```

The generated guard script was invoked directly with three Bash payloads:

```text
$ echo '{"tool_name": "Bash", "input": {"command": "gh pr merge --squash 123"}}' | python3 .claude/harness-merge-guard.py
AET merge guard: refusing `gh pr merge`. Use the sanctioned merge path (`aet desk merge` or the GitHub UI).
[exit 1]

$ echo '{"tool_name": "Bash", "input": {"command": "git push origin feature-branch"}}' | python3 .claude/harness-merge-guard.py
[exit 0]

$ echo '{"tool_name": "Bash", "input": {"command": "aet desk merge reh-a-desk-merge"}}' | python3 .claude/harness-merge-guard.py
[exit 0]
```

The guard refuses the unsanctioned `gh pr merge` and allows both the legitimate closure push (`git push`) and the sanctioned desk merge path.

Mode-1 cleanness was verified: both `.agents/` and `.claude/` are untracked in the scratch repo, so no AET-specific config is in the shared tree.

### Honest finding: `aet harness-guard check` reports incorrectly

After a successful install, `aet harness-guard check` says the guard is not installed:

```text
$ aet harness-guard check
claude-code: merge guard not installed
[exit 0]
```

The reason is in `aet-setup/lib/harness_guard.py`: `check_merge_guard` searches for the `GUARD_MARKER` (`aet:generated merge guard`) inside `.claude/settings.json`, but the marker is written only into the guard script. The install itself is correct and blocks as designed; the check command is the only surface that is out of sync. This should be fixed in a follow-up so operators can verify installation without inspecting files manually.

## Known gaps / findings

1. **`aet harness-guard check` false-negative.** As noted in (d), the check command looks for the AET marker in the wrong artifact. The guard installs and blocks correctly; the check is cosmetic but misleading.
2. **The guard is harness-local and client-side.** Like the pre-push shim in ewl-06, the `PreToolUse` hook stops only an operator whose harness has it installed and who does not bypass it. Server-side / Mode 2 enforcement is roadmap Phase 6 and is not claimed here.
3. **Desk merge requires a real PR.** The rehearsal used a temporary GitHub repo/PR because `aet desk merge` calls `gh pr merge --squash`. This is the intended skill-driven closure path; a local-only demo would need to call `aet-state record-merge` directly and would not exercise the desk command.

## R-trace

- **R-10** (exit-gate claims demonstrated): rehearsals (a), (b), (c).
- **R-11** (integrated end-to-end demonstration): rehearsal (a) drives the full desk-merge closure path; the audit doc ties (a)–(d) together.
- **R-14** (merge guard demo): rehearsal (d).
