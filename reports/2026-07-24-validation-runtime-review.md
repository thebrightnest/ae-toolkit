# Validation Runtime Review: 2026-07-24

## Context

The `aet run` batch for `cfg-01-config-resolution-overhaul` and `cfg-03-cli-surface-fixes`
took **40 min 45 s** of wall-clock time despite both tasks being size M and S. The two
tasks ran in parallel (`concurrency_cap: 4`, `parallel_conflicts_detected: 0`), so the
wall clock was set by the **critical path** — the longer of the two tasks — not by the
sum of their work.

This report breaks down where that time actually went. An earlier draft concluded that
validation was "the dominant cost, roughly half the wall clock." Re-checking that claim
against the raw telemetry showed it was an artifact of summing two *parallel* tasks:
**on the critical path, validation was ~13% of the wall clock as pytest (~18% including
lint and the installer smoke test), and the single dominant cost was one 29-minute
implement/QA session.** The corrected analysis and its consequences for the
recommendations are below.

## Summary of Findings

- **The run was dominated by one session, not by validation.** `cfg-01` session 1
  (plan-approved → implemented → qa-complete) ran **29 min 26 s — 72% of the entire wall
  clock** — and pytest was only **9%** of that session. The other ~27 min was planning,
  implementation, and QA agent work.
- **`cfg-01` was essentially the whole critical path** (2439.5 s of the 2444.8 s wall
  clock, 99.8%). **`cfg-03` ran entirely inside `cfg-01`'s shadow** and contributed
  **zero** wall-clock seconds. Optimizing anything about `cfg-03` — its validation, its
  session count — saves **0 s** of runtime for a batch shaped like this one.
- **Validation on the critical path was ~5.3 min of pytest (12.9%)**, ~7–8 min including
  lint and the installer smoke test (~18%). Not half.
- **Full pytest ran in 4 of the 7 sessions, not 7.** The `reviewed` stage ran no pytest
  in either task; `cfg-03`'s `synced` stage ran none either. Those sessions were ~5 min
  each of *agent overhead*, not validation.
- **The prose-only pytest skip already exists** (`change_scope.py`). The later stages that
  the earlier draft targeted for "stop running the full gate" were already skipping pytest
  — which is *why* they have no `test_run` telemetry. The residual cost there is the
  **unconditional installer smoke test** (~30 s), not the 2.5-min suite.
- The largest safe, wall-clock-relevant levers are therefore: **(1)** shorten the long
  implement/QA session (the actual 72%), **(2)** make the installer test conditional, and
  **(3)** investigate whether `--dist=loadgroup` is inflating pytest time for *every*
  stage. Stage-aware skipping of `reviewed`/`synced` — the earlier draft's headline
  recommendation — recovers almost nothing on the critical path.

## Measured Validation Costs (per invocation)

`make validate` (`Makefile:98-113`) is the single quality gate run at the end of an
orchestrator stage. Per-invocation timings on an M-series Mac with the repo in its normal
state:

| Step | Command | Time |
|------|---------|------|
| Python lint | `ruff check .` | ~0.3 s |
| Workflow lint | `src/aet/cli/validate_workflows.py` | ~0.15 s |
| Skills lint | `scripts/skills-lint --legacy=error` | ~0.7 s |
| Skill structure | `scripts/validate-skills.sh` | ~2.3 s |
| Plans lint | `aet plans lint` | ~0.9 s |
| Docs lint | `aet docs lint` | ~0.4 s |
| Test selection | `aet.change_scope` | ~0.1 s |
| **Pytest full suite** | `pytest tests/ -q -n auto --dist=loadgroup` | **~2.5 min** |
| Installer smoke tests | `pytest tests/installer/test_installer.py -q` | **~30.5 s** |
| **Total `make validate`** | | **~3 min** |

The pytest suite (1,192 tests) dominates a *single* invocation; everything else is noise.
The ~2.5-min figure is corroborated by telemetry — the five full runs in this batch ranged
**128 s–184 s**. But note two things this table hides, both of which matter below:

1. **Per-invocation cost is not wall-clock cost.** The suite runs in some sessions and is
   skipped in others (see next section), and when tasks run in parallel, only the critical
   path's invocations count toward wall clock.
2. **`--dist=loadgroup` is a live question, not a fixed constant.** The load-group
   serialization cost has produced conflicting A/B numbers; a narrowing to 18 tests
   reproduced a stall on 2026-07-22. The 2.5 min may be partly a distribution-mode
   artifact rather than raw test work — an unexplored lever (see Recommendation 3).

## Where the Wall Clock Actually Went

Sessions within a task are sequential; the two tasks ran concurrently. So the wall clock
is the *critical path*, and summing both tasks' timings double-counts overlapped work.

| | Duration | % of wall clock | On critical path? |
|---|---|---|---|
| **`cfg-01` (3 sessions)** | 2439.5 s (40.7 min) | **99.8%** | **yes — this *is* the critical path** |
| `cfg-03` (4 sessions) | 1690.5 s (28.2 min) | 69.1% | no — finished ~12 min inside cfg-01's shadow |
| **Wall clock** | **2444.8 s (40.7 min)** | 100% | |

`cfg-01`'s three sessions alone account for 99.8% of the wall clock. **`cfg-03`
contributed no wall-clock time** — it started with `cfg-01`, ran shorter, and finished
first. This is not merely inferred from "they started together": the wall clock itself
corroborates it. Wall clock (2444.8 s) exceeds `cfg-01`'s session sum (2439.5 s) by only
5.3 s of orchestrator overhead; had `cfg-03` (1690.5 s) extended past `cfg-01`, wall clock
would sit above `cfg-01`'s sum by far more than that. `cfg-03` therefore falls entirely
inside `cfg-01`'s span. (To make this fully airtight, cite the two tasks' raw start
timestamps from the `.jsonl` records — the one number the appendix does not yet show.) Any
optimization scoped to `cfg-03` (validation tiering, session grouping) saves **0 s** of
runtime for this batch.

Breaking down the critical path (`cfg-01`):

| Session | Stage(s) | Duration | % of wall | pytest inside | pytest % of session |
|---------|----------|----------|-----------|---------------|---------------------|
| 1 | plan-approved → implemented → qa-complete | 29 min 26 s | **72.2%** | 2 s fail + 2 min 41 s pass | **9.2%** |
| 2 | reviewed | 5 min 18 s | 13.0% | **none** (no `test_run` record) | 0% |
| 3 | reviewed + secure → synced | 5 min 55 s | 14.5% | 2 min 33 s pass | 43% |

**Session 1 is the story.** At 29 min 26 s it is 72% of the whole run, and validation was
9% of it. The remaining ~27 min was agent work: reading the plan, writing the config
resolution overhaul, and QA. No amount of validation tiering touches this.

Critical-path pytest total: 2.1 + 161.2 + 152.8 = **316 s = 5.3 min = 12.9% of wall
clock.** Adding lint and the installer smoke test on each `validate` invocation brings
validation on the critical path to an estimated **~7–8 min (~18%)** — not half.

## Corrected Session Breakdown

The earlier draft stated `make validate` "ran 3 times" for `cfg-01` and "4 times" for
`cfg-03.` The `test_run` telemetry records show **full pytest ran in 4 of the 7 sessions**,
not 7. The sessions marked "unknown scope" in the earlier draft in fact ran **no pytest at
all** — they emit no `test_run` record because `change_scope` skipped the suite for a
prose-only change set.

**cfg-01-config-resolution-overhaul** (3 sessions)

| Session | Stage(s) | Duration | pytest inside |
|---------|----------|----------|---------------|
| 1 | plan-approved → implemented → qa-complete | 29 min 26 s | failed (2 s) + passed (2 min 41 s) |
| 2 | reviewed | 5 min 18 s | **none — pytest skipped** |
| 3 | reviewed + secure → synced | 5 min 55 s | passed (2 min 33 s) |

**cfg-03-cli-surface-fixes** (4 sessions)

| Session | Stage | Duration | pytest inside |
|---------|-------|----------|---------------|
| 1 | implemented | 12 min 23 s | 2 impact runs (<1 s) → full failed (2 min 8 s) → full passed (2 min 39 s) |
| 2 | qa-complete | 5 min 26 s | passed (3 min 4 s) |
| 3 | reviewed | 5 min 4 s | **none — pytest skipped** |
| 4 | synced | 5 min 18 s | **none — pytest skipped** |

Two things stand out:

- **The `reviewed` stage ran no pytest in either task.** Whatever makes those sessions take
  ~5 min, it is not the test suite.
- **The `synced` stage is inconsistent:** `cfg-01`'s ran the full suite (2 min 33 s),
  `cfg-03`'s ran none. The difference is real (`cfg-01`'s `synced` was grouped with the
  `secure`/cso stage and its change set tripped `change_scope`'s code detection), and it is
  direct evidence that "synced" is **not reliably code-free** — a caution for any
  recommendation that blindly skips validation there.

Batch-wide pytest *compute* (both tasks summed): 5 full runs = **13.1 min**. This is the
honest "total time spent running tests," but it is spread across two parallel tasks and is
**not** additive to wall clock.

## Why the "Roughly Half" Figure Was Wrong

The earlier draft computed `7 validate invocations × ~3 min ≈ 21 min ≈ half of 41 min`.
Three compounding errors:

1. **Summed parallel work.** It added `cfg-01`'s and `cfg-03`'s validation time, but
   `cfg-03` ran concurrently with `cfg-01` and added no wall-clock time. Only the critical
   path counts.
2. **Overcounted invocations.** Full pytest ran in 4 sessions, not 7. The `reviewed`
   sessions (both) and `cfg-03`'s `synced` ran no suite.
3. **Assumed every invocation cost the full 3 min.** The fast fails (2 s, <1 s) and
   prose-only skips cost far less.

Corrected: validation is ~7–8 min of the 40.7-min critical path (~18%), a real cost worth
trimming, but a secondary one. The dominant cost is agent session time — above all the one
29-minute implement/QA session.

## Root Causes of Long Runtime

Separating what is slow (agent sessions) from what is *validation* (a smaller slice):

1. **One long implement/QA session dominates (the actual 72%).** `cfg-01` session 1 was
   29 min 26 s, ~27 min of it non-validation agent work. This is the single largest lever
   on wall clock and is unaddressed by any validation change.

2. **Full test suite when code changes, with no finer targeting.** `aet.change_scope`
   narrows to exactly two outcomes: skip pytest (prose-only) or run the entire 1,192-test
   suite (`change_scope.py:92-98`). A one-line CLI fix still runs the whole suite. There is
   no file-to-test mapping.

3. **The prose-only skip already fires in later stages — but the installer test doesn't.**
   `reviewed`/`synced` sessions that touch only Markdown already skip pytest via
   `change_scope`. However, `make validate` runs `test-installer` **unconditionally**
   (`Makefile:112`, after the pytest-skip block), so those sessions still pay ~30 s for a
   test that cannot be affected by a docs-only change.

4. **`--dist=loadgroup` may inflate every pytest run.** The 2.5-min suite time is treated
   as fixed, but the load-group distribution mode has a contested serialization cost and a
   reproduced stall. If it is inflating the suite, fixing it speeds up *every* stage that
   runs tests — with none of the risk of skipping a stage.

5. **QA-freshness is decided in code but obeyed in prose.** `orchestrator.py:414-434`
   (`_qa_freshness_decision`) computes whether the worktree is unchanged since the last
   green QA verdict, and `_freshness_clause` (`orchestrator.py:388-411`) injects a prompt
   sentence asking the agent to trust it. As the docstring says, this is "decided in code
   and obeyed in prose" — the agent may re-run the suite anyway. `cfg-01`'s `synced`
   session running the full suite while `cfg-03`'s skipped it is this non-determinism in
   action.

## Recommendations (ordered by critical-path impact)

### 1. Shorten the long implement/QA session — the real 72%

The single biggest lever is `cfg-01` session 1 (29 min, ~27 min non-validation). Options
worth measuring before anything else:

- Are plan-approved → implemented → qa-complete correctly grouped into one session, or is
  the agent re-reading context it already had?
- Token telemetry: this batch burned **42.8 M tokens**. A 29-min session at that scale
  suggests large context re-reads or verbose exploration. Profiling the session's tool
  calls will show more wall-clock savings than any validation change.

This is flagged as the top item precisely because the earlier draft did not address it,
yet it is where the time is.

### 2. Make `test-installer` conditional (cheapest safe win)

`make validate` runs the installer smoke test on **every** invocation, including
prose-only sessions that already skip pytest (`Makefile:112`). Gate it:

- Run only when `scripts/install.sh` or `src/aet/cli/setup.py` changed, or the plan tags
  the task as touching installation.

Put the gate in `change_scope` (emit an install-tests flag from the same path list it
already computes), not in Makefile shell — same code-enforced-determinism argument as
Recommendations 5–6, and it keeps every test-scope decision in one place. This is the one
change that actually recovers time from the `reviewed`/`synced` sessions, because it is the
only validation cost that *doesn't* already self-skip there. ~30 s per affected invocation,
near-zero risk.

### 3. Investigate `--dist=loadgroup` before optimizing around pytest

Before treating 2.5 min as immovable and building machinery to avoid it, confirm the
number is real work and not a distribution-mode stall. Re-measure `-n auto` with and
without `--dist=loadgroup` on the current suite (the rationale for choosing loadgroup is in
commit `a8ad3d89`; the A/B numbers there conflict). If loadgroup is inflating the suite,
fixing it speeds up **every** code-changing stage with no skip-a-stage risk — strictly
safer than Recommendations 5–6.

### 4. Enforce QA-freshness in code, not prose

`_qa_freshness_decision` already computes the right answer; the orchestrator should **act**
on it rather than ask the agent to. When the tree hash is unchanged since the last green QA
verdict, the orchestrator should run lint-only itself and not spawn a session that *can*
re-run the suite. This removes the `cfg-01`-vs-`cfg-03` `synced` inconsistency and is the
determinism-correct version of "cache verdicts across stages."

### 5. File-to-test mapping (higher leverage, more risk)

Narrow pytest to the tests most likely to exercise the changed code, for faster feedback in
`implemented`/`qa-complete`:

- **Heuristic:** `src/aet/cli/*.py` → `tests/cli/`, `src/aet/backends/*.py` →
  `tests/backends/`, etc.
- **Dynamic:** `pytest-testmon` / `pytest-picked` to run only diff-affected tests.

Trade-off: narrower tests can miss cross-module regressions. Safe compromise: targeted run
in early stages, one **full** `make validate` before `synced` seals the task. **Implement
this in `change_scope` (code-enforced, fail-safe), not as a prompt instruction** — extend
the mechanism that already deterministically decides full-vs-skip, rather than adding a
tier the agent may misapply.

The Makefile side is **already wired for this**: `test` consumes `PYTEST_TARGETS`
(`Makefile:17`, defaulting to `tests/`) and `validate` threads `change_scope`'s output
straight into it (`test PYTEST_TARGETS="$$targets"`). `change_scope` simply always emits
`tests/`. So the change is localized to `decide()`/`main()` returning a target list — **no
Makefile change required** — which lowers this from "Medium" toward "Low–Medium" effort.

### 6. Stage-aware validation (lowest priority — mind the determinism trap)

A stage → validation-tier mapping (review/security/docs stages run lint + targeted tests
only) is defensible, but two cautions demote it:

- On this batch it recovers **almost nothing on the critical path**: `reviewed` already
  runs no pytest, and `cfg-03`'s stages weren't on the critical path at all.
- The earlier draft's framing — "trust the stage agent to not silently skip needed tests,"
  "the agent can escalate" — is **AI discretion**, the exact failure mode Recommendation 4
  exists to remove. If this is done at all, the stage→tier decision must be **computed in
  code** (in `change_scope`, keyed on stage + change set), not delegated to the agent's
  judgment. Note also that `synced` is not reliably code-free (`cfg-01` proved it), so the
  tier must key on the actual change set, never on the stage name alone.

## Trade-offs

| Approach | Wall-clock gain (this batch) | Wall-clock gain (general) | Risk | Effort |
|----------|------------------------------|---------------------------|------|--------|
| Shorten long implement/QA session | **High** — targets the 72% | High | Low (measurement first) | Medium |
| Conditional installer test | Low (~30 s/invocation) | Low–Medium | Low | Low |
| Fix/replace `--dist=loadgroup` | Medium — speeds every code stage | Medium–High | Low | Low–Medium |
| Code-enforced QA-freshness | Low here | Medium | Low (orchestrator enforces) | Medium |
| File-to-test mapping | Low here | High (full suite → targeted) | Medium (cross-module regressions) | Low–Medium (Makefile already wired) |
| Stage-aware validation | **~0** (later stages already skip) | Low–Medium | Medium (false confidence) | Medium |

The biggest wall-clock lever is the **long agent session**, which no validation change
touches. Among validation changes, the safe wins are **conditional installer** and
**investigating loadgroup**; **code-enforced freshness** and **file-to-test mapping** are
higher-leverage-in-general but need care. Stage-aware skipping — the earlier draft's
headline — is last: it recovers nothing here and invites the determinism trap.

## Suggested Immediate Actions

1. **Profile `cfg-01` session 1.** Pull its tool-call / token breakdown from telemetry to
   find where the ~27 non-validation minutes went. This is the 72%; everything else is
   rounding.
2. **Make `test-installer` conditional** in `Makefile` (skip unless install paths changed
   or the plan tags installation). The only validation cost that doesn't already self-skip
   in later stages.
3. **Re-measure pytest with and without `--dist=loadgroup`** before building anything to
   avoid the 2.5-min suite. If it's a distribution artifact, this is the cheapest broad win.
4. **Make the orchestrator act on `_qa_freshness_decision`** instead of asking the agent
   to — run lint-only itself when the tree is unchanged since green QA.
5. **Do not** ship "stop running `make validate` in `reviewed`/`secure`/`synced`" as a
   prose instruction. It recovers ~0 on the critical path (those stages already skip pytest
   via `change_scope`), and prose-level skipping re-introduces the AI-discretion failure
   mode. If a tier is wanted, compute it in `change_scope`.

## Appendix: Telemetry Sources & Derived Numbers

**Sources**

- Run summary: `~/.aet/telemetry/aiskills/main/2026-07-24/run-20260724-113015-bgc8k8y1/last-run.json`
- Per-stage records: same dir, `cfg-01-config-resolution-overhaul.jsonl`, `cfg-03-cli-surface-fixes.jsonl`
- Validation pipeline: `Makefile` target `validate` (lines 98–113); installer at line 112
- Test-scope logic: `src/aet/change_scope.py` (`decide()` at lines 92–98)
- Freshness logic: `src/aet/cli/orchestrator.py` — `_freshness_clause` (388–411),
  `_qa_freshness_decision` (414–434)

**Derived numbers (from `last-run.json` + the two `.jsonl` files)**

| Quantity | Value | Source |
|---|---|---|
| Wall clock | 2444.8 s (40 min 45 s) | `wall_clock_seconds` |
| Tasks / succeeded | 2 / 2, parallel, cap 4 | `run_summary` |
| Total tokens | 42.8 M | `total_tokens` |
| cfg-01 critical path | 2439.5 s (99.8% of wall) | sum of 3 stage durations |
| cfg-03 total (overlapped) | 1690.5 s (0 s on wall clock) | sum of 4 stage durations |
| cfg-01 session 1 | 1765.7 s (72.2% of wall) | stage record |
| Critical-path pytest | 316 s (12.9% of wall) | 3 `test_run` durations |
| Sessions running full pytest | 4 of 7 | `test_run` records |
| Batch full-pytest compute | 784.5 s / 13.1 min (5 runs) | `test_run` durations |
| Full suite size | 1,192 tests | `pytest --collect-only` |

All wall-clock percentages are against the 2444.8 s total. Task-level times are **not**
additive across `cfg-01` and `cfg-03` because the tasks ran concurrently.
