# Pipeline Flow Efficiency — Session Audit (2026-07-13)

## Scope and method

Audit of one full PIV cycle — plan → validate-scope → queue → `aet run-one` —
for `lvp-01-panel-live-run-visibility`, plus the planning-session flow around
it. Data sources: the run's telemetry archive
(`~/.aet/telemetry/aiskills/main/2026-07-13/17e9ccc4-*/`), the orchestrator
session log (320 KB), queue state, verdict files, and the tele-07 run
(`b0cfc5a5`, same day, same pipeline) as a baseline.

## Headline numbers

| Run                                                      | Implement+QA (group) | Review   | Secure+Synced (group) | Total wall |
| -------------------------------------------------------- | -------------------- | -------- | --------------------- | ---------- |
| lvp-01 (635-line diff, HTTP handler + UI + 2 test files) | 45.8 min             | 39.7 min | 13.6 min              | **99 min** |
| tele-07 (reader-layout fix, CSO skipped)                 | 25.1 min             | 11.1 min | 4.6 min               | **41 min** |

Within lvp-01's 99 minutes, the measurable repetition:

- **Full `make validate` ran 4–5 times** (`583 passed` appears 4× in the log;
  sync-docs reports "green again" on top) — ~6–7.5 min of pure pytest at
  ~86 s/run, plus lint/format/ruff/validators each time.
- **The CDP E2E harness ran ≥5 times** (implement, live-archive regression,
  old-code stash control run, QA re-run, review re-run) — each run spawns
  headless Chrome + a serve process.
- **`tests/test_panel_serve.py` ran 2× as a targeted run** in QA and review,
  minutes after the same six tests passed inside the full suite.
- **3 fresh agent sessions**, each re-loading skill docs, the plan,
  CONTEXT.md, ADRs, `evidence.py`, and the full diff from zero.

## Findings

### F1 — Stage sessions re-derive settled context (highest cost)

Each stage session starts with zero memory of the previous one. Concrete
re-investigations observed in this single run:

- The **review session re-investigated the evidence-verdict path contract**
  (`write_verdict` vs `resolve_verdict_path` env precedence) — a question
  already settled by frh-18 and recorded in `.agents/learnings.jsonl`, and
  already navigated by the QA session of this same run.
- The **QA session investigated coverage tooling from scratch** (no
  pytest-cov, no coverage.py) and flagged it as a setup gap — the same gap
  previous plans flagged (see F7).
- Every session re-read the 51 KB `index.html` diff regions and the plan.

There is no run-scoped handoff artifact. A one-page `context.md` per run
(decisions made, evidence-path recipe, validation commands, known
pre-existing failures) written by the implement session and appended by each
later stage would eliminate most of this ramp-up.

### F2 — Validation runs are not deduplicated

The full suite ran 4–5 times against diffs that, between stages, often
changed **only the plan footer** (markdown). The review and CSO sessions
re-ran everything because the skill instructions say "run validations in the
foreground" without a freshness concept. A tree-hash-keyed validation cache
(or a rule: "if the diff since the last green validation is docs-only, run
lint/format only") makes the dedup mechanical rather than judgment-based.
Estimated saving: 5–10 min per run, plus agent attention.

### F3 — Live-archive E2E fixtures drift; cost ~10 min inside implement

`scripts/test-panel-plan-detail.mjs` runs against the live
`~/.aet/telemetry` archive. Its empty-state check depends on a `T/tmp`
run_summary-only plan row that vanished (retention prune). The implement
session hit the failure and spent ~10 minutes on a stash-based control
experiment to prove the failure was pre-existing archive drift, not its
regression. The new `scripts/test-panel-live-runs.mjs` already uses the
right pattern (fixture archive via `HOME` override). Migrating the older
harness to fixtures is a small, self-contained follow-up.

### F4 — Review was the outlier stage (39.7 min vs 11.1 baseline)

lvp-01's review session did genuinely thorough work (line-by-line mirror
verification against `telemetry.py`, removed-symbol grep, lens checklist) —
but a large share of its 40 minutes was F1 ramp-up and F2 re-validation. With
those two fixed, review should land near the tele-07 baseline of ~11–15 min
for a diff this size.

### F5 — Launch-time guardrails fail late

The first `aet run-one` launch died instantly on "local main is ahead of
origin/main" — a state knowable at `aet add` time or in a preflight. Cost:
one failed run, one user round-trip, one relaunch. The same class applies to
the lease check (active run) and the uncommitted-work stash dance: all three
are preflight-able warnings instead of launch-time halts or tribal
knowledge.

### F6 — validate-scope conflates content validation with the closure gate

Scope validation's substantive findings (terminology, ADR alignment, code
cross-checks) were completed and resolved in one pass — but the stage could
not close because the closure check requires queue entries, and queueing is a
later, deliberately human step. Result: a mandatory second validate-scope
invocation that was pure ceremony. Splitting "content validated" (cacheable)
from "closure gate" (5-second re-check) removes the round-trip without
weakening the gate.

### F7 — No coverage tooling; flagged repeatedly, never resolved

QA flagged the missing coverage tool as a setup gap (no pytest-cov, no
coverage.py), as previous QA sessions have. Each flag costs investigation
time and produces no lasting fix. Either install pytest-cov or codify the
current substitute ("named test per new source file", already in the plan
template's validation gate) as the standing rule so QA stops re-discovering
the gap.

### F8 — Flow observability lags reality (the lvp blind spot, felt firsthand)

The queue's `stage` field showed `qa-complete` while the review stage had
already finished; stage records write only at stage-group completion. During
this very audit, answering "what's happening now" required reading the
orchestrator's raw session log. The tier-3 heartbeat (`live.json` written at
stage transitions) that was deferred from the panel PRD would fix flow
observability for the panel _and_ for humans watching a run.

### F9 — Human-in-the-loop confirmations add latency but not much cost

Push confirmation, ship confirmation, and the validate-scope closure
round-trip each cost a user interaction. They are cheap in attention and
worth keeping for outward-facing actions — but a per-run opt-in ("run
unattended through PR creation") would let a trusted pipeline complete
without the idle gaps between them.

## What worked — keep these

- **Gate discipline produced real signal, not theater:** QA caught and fixed
  an E2E teardown race; review verified the `telemetry.py` mirror
  line-by-line; CSO confirmed archive-root confinement with a new regression
  test; sync-docs kept the PRD footer honest ("lvp-01 synced, lvp-02
  pending" instead of stamping `synced` over unbuilt work).
- **Verdict files + fail-closed gates** meant every stage transition was
  auditable after the fact (this audit is built on them).
- **The plan's size discipline held:** lvp-01/02 split kept each plan inside
  the guardrails, and the `pipeline: minimal` flip for lvp-02 (owner
  decision, mid-flight) was a one-line, low-risk adjustment.

## Recommendations (impact × effort)

| #   | Change                                                                                                                                               | Impact                                                     | Effort     | Where it lives                             |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- | ---------- | ------------------------------------------ |
| R1  | Run-scoped session briefing (`context.md` per run, appended per stage: decisions, evidence recipe, validation commands, known pre-existing failures) | High — kills F1, the largest single cost                   | Medium     | aet-work orchestrator + stage skills       |
| R2  | Validation freshness rule (tree-hash diff since last green; docs-only → lint/format only)                                                            | High — 5–10 min/run + attention (F2)                       | Low–medium | aet-qa / aet-review / aet-cso skills       |
| R3  | Migrate `test-panel-plan-detail.mjs` to fixture archive (F3)                                                                                         | Medium — removes a recurring ~10 min regression-alibi cost | Low        | `scripts/` — candidate plan                |
| R4  | Preflight at `aet add`/launch: push-state, active lease, uncommitted work (F5)                                                                       | Medium — removes failed-launch round-trips                 | Low        | aet-work                                   |
| R5  | Split validate-scope into content validation + 5-second closure re-check (F6)                                                                        | Medium — removes a full ceremony round-trip per feature    | Low        | aet-validate-scope                         |
| R6  | Formalize pipeline-selection guidance at plan time (the minimal-pipeline checklist lvp-02 used)                                                      | Medium — tele-07 vs lvp-01 shows 2× wall-clock swing       | Low        | aet-plan, plan template                    |
| R7  | Decide coverage tooling once: install pytest-cov, or codify "named test per new file" as the standing rule (F7)                                      | Low–medium — stops per-run rediscovery                     | Low        | repo tooling / aet-qa                      |
| R8  | Tier-3 heartbeat (`live.json` at stage transitions)                                                                                                  | Medium — fixes F8 and the panel's mid-stage blind window   | Medium     | orchestrator (already scoped in panel PRD) |
| R9  | Optional "unattended through PR" per-run opt-in (F9)                                                                                                 | Low–medium — removes idle gaps between human gates         | Low        | aet-work / session policy                  |

## Suggested next steps

1. Run `aet-evolve` with this audit as input — R1, R2, R5, R6 are skill-text
   changes that pay back on every future run.
2. Queue R3 (fixture migration) as a small standalone plan — it is the only
   item with a live, failing-adjacent test today.
3. Keep R8 attached to the panel live-executions PRD as the already-named
   tier 3, now doubly justified (panel UX + flow observability).

## Raw data appendix

- lvp-01 run: `~/.aet/telemetry/aiskills/main/2026-07-13/17e9ccc4-1620-4f5d-8517-f98433a47206/`
  — stage records: `qa-complete` group [plan-approved, implemented] 45.8 min;
  `reviewed` 39.7 min; `synced` group [reviewed, secure] 13.6 min.
- tele-07 run: `~/.aet/telemetry/aiskills/main/2026-07-13/b0cfc5a5-c5b4-4c23-8471-539f1ab7e401/`
  — 25.1 / 11.1 / 4.6 min (CSO skipped).
- Verdicts: `~/.aet/reports/aiskills/main/lvp-01-panel-live-run-visibility/{qa,review,cso,sync-docs}.json` — all pass.
- lvp-01 branch: `lvp-01-panel-live-run-visibility`, commits `0e9eada` (feat),
  `8589e56` (qa), `20652d5` (review), `a6190ab` (secure), `9e7f39d` (synced).
- Orchestrator log: session `session_199cb3cc` task `bash-a0tgndcq` (320 KB).
