# Retro: Planning-Pipeline Session, Telemetry Adapter Parity

**Date:** 2026-07-26
**Trigger:** `aet-pipeline-plan` run producing `docs/prds/telemetry-adapter-parity-prd.md`,
ADR-050/051/052, and plans `tap-01`..`tap-07`. No implementation ran; the loop under review is
the planning loop.
**Branch:** `main` (clean, pushed)

## Retro Debt Check — `docs/retros/2026-07-20-aet-metrics-cycle.md`

| Prior action item | Status | Evidence |
| --- | --- | --- |
| No further `aet-evolve` skill edit warranted; metrics evidence step is in the retro procedure | ✅ complete | This retro ran `aet metrics --json --since 2026-07-20` per the procedure |
| Follow-up queued: preserve `work_class` and `size` in `work-history.jsonl` so `aet metrics` can produce a per-class breakdown | ⚠️ **merged but purpose unmet** | `twe-01-work-class-attribute` is `status: merged`; `aet metrics --since 2026-07-20` still reports **65/65 tasks `unclassified`**. See Finding 2. |

The second item is the interesting kind of debt: the code shipped and the outcome did not.

## Metrics Evidence

`aet metrics --json --since 2026-07-20`:

| Measure | Value |
| --- | --- |
| Settled / merged tasks | 65 / 65 |
| First-pass merges | **0 (0.0%)** |
| Rework units | 299 |
| Tokens per merged task | ~11.25 M |
| USD cost coverage | 0 tasks |
| Class breakdown | `unclassified`: 65 (100%) |

Read Finding 3 before drawing any conclusion from the first-pass and rework rows.

## Findings

### 1. The telemetry archive layout is documented three times; only one copy is unambiguous — **recurrence ×2**

`derive_project_slug` (`src/aet/project_id.py:40`) returns `<main-worktree-dir>/<worktree-label>`
— a slug that **spans two path segments** (`aiskills/main`). Task logs therefore sit five levels
below the archive root:

```
~/.aet/telemetry/aiskills/main/2026-07-21/run-20260721-015638-bhldep0m/tap-01.jsonl
```

The contract is stated in three places. Only `skills/aet-work/references/telemetry-log-schema.md`
(lines 12–19) says the slug spans two segments. `docs/telemetry-guide.md` rendered a one-level
`{project-slug}` in its ASCII tree, and `CONTEXT.md` stated the four-segment form with no note at
all.

This is the **second** occurrence of this exact failure:

- **2026-07-13** (`.agents/learnings.jsonl`, entry 38): `aet retro` produced a malformed report
  because `mine-learnings` walked three levels under the root. Fixed by
  `tele-07-retro-reader-layout-fix`, whose own `docs_sync_reason` demanded the layout be stated
  explicitly "so future readers cannot re-derive it differently". It disambiguated **one** of the
  three documents.
- **2026-07-26** (this session): the agent wrote a four-level glob against the guide's form while
  measuring the telemetry corpus, got zero results for every project, and had to re-run the
  measurement after discovering the fifth level by listing the directory.

The failure mode is silent by construction: a wrong-depth glob returns an empty match set, which
reads as "no telemetry" rather than "bad path".

**Layer:** on-demand context / reference docs.

### 2. `work_class` is read but nothing writes it — the metric dimension is dead by construction

`plan_parser.py:242-246` reads `work_class` from plan frontmatter, accepts `trivial|normal|critical`,
and defaults to `"unclassified"`. But:

- `.agents/templates/plan-template.md` did not contain a `work_class` key.
- **0 of 289 plans** in `docs/plans/` declare one.
- `.agents/work-history.jsonl`: 238 records missing the field, 84 recording the literal
  `unclassified`. Zero classified records, ever.

`twe-01-work-class-attribute` shipped the reader and the validation; no layer was changed that
would cause a value to be written. The per-class breakdown the 2026-07-20 retro asked for cannot
exist until a plan declares the field, and no plan will declare a field the template does not
mention.

**Layer:** templates.

### 3. The 0.0% first-pass rate is an artifact of a counting defect — do not act on it yet

`aet metrics` computes rework through `metrics.py:116` → `track_record.rework_count`, and
`track_record._repeated_stage_count` (`:103`) groups records by `_stage_names(record)` over a set
that `iter_telemetry_task_records` (`:74`) yields as `type in ("stage", "test_run")`. `test_run`
records carry a `stage` field (`telemetry.py:363`), so every observed test run is counted as a
repeat of its own stage.

Measured this session over the 127 tasks with telemetry across `aiskills`/`blueocean`/`manager`:

| Clause | Current (stage + `test_run`) | Stage records only |
| --- | --- | --- |
| Tasks with rework > 0 | 121 (95%) | 25 (20%) |
| Tasks with a failed record | 52 | 27 |
| **Tasks passing both telemetry clauses** | **1 (1%)** | **93 (73%)** |

ADR-035 item 2 already defines rework as "stage telemetry records beyond the first for any stage
name", so this is a docs↔code defect, not a definitional choice.

The consequence for the retro loop: the 2026-07-20 retro's headline conclusion — *"rework is
universal (0% first-pass rate)"* — is a measurement artifact, and today's run reproduces it (0.0%,
299 rework units over 65 tasks). It was routed as a factory-quality finding when it is a counting
bug.

**No system edit here.** `tap-01-factory-metrics-stage-records-only` is `ready` in the queue and
fixes exactly this, ahead of the detection work so the metric does not move as a side effect. The
action is to **stop treating first-pass/rework figures as evidence until tap-01 merges** and
re-baseline afterwards.

**Layer:** none — already queued as work.

### 4. Frontmatter enums are discoverable for `status`, not for `docs_sync` / `security_review`

The agent wrote `docs_sync: conditional` on `tap-07` and `status: pending` on all seven plans;
`aet plans lint` and `aet plan validate` rejected both, costing four fix-and-revalidate cycles.
The template documents the `status` enum inline (line 14) — that error was the agent not reading
it. But the `security_review` / `docs_sync` comment described the *behaviour* of `required` and
`skipped` without stating they are the only accepted values, which is what invited a hedged third
value for a plan whose docs impact genuinely depends on its outcome.

**Layer:** templates (same file as Finding 2).

### Not a system finding

The agent invented test-file paths (`tests/test_wirelog.py` rather than
`tests/wirelog/test_wirelog.py`) across all seven plans. `aet plan validate` cannot catch this —
"Files to Modify" legitimately names files that do not exist yet. The fix is behavioural: list the
directory before citing paths in it. Recorded as a learning, no layer changed.

## Routed Actions

### AET-level (toolkit) — applied in this cycle

1. `docs/telemetry-guide.md` — the ASCII tree now shows the expanded five-level path and names the
   silent-empty-match failure mode.
2. `CONTEXT.md` — **Telemetry Archive** term states the five-level path, and its *Avoid* clause
   names writing `{project-slug}` as a single segment.
3. `.agents/templates/plan-template.md` — adds `work_class: [trivial/normal/critical]` with a
   comment explaining that omitting it is what makes the metric dimension empty; extends the
   `security_review` / `docs_sync` comment to state that `required` and `skipped` are the only
   accepted values.

### Project-level (this repo)

- **`tap-01` is the gating item for metric trust.** Already `ready` in the queue. Until it merges,
  `aet metrics` first-pass and rework figures are not evidence.
- **Backfilling `work_class` on 289 existing plans is deliberately not proposed.** New plans will
  carry it from the template; retrofitting historical plans would fabricate a classification
  nobody made at the time. The per-class view becomes meaningful going forward, not retroactively.

## Conclusion

The session's own friction was the useful signal. Two of the four findings are documentation and
template gaps that made an agent guess — and in Finding 1's case, guess the same way a previous
session guessed, thirteen days after a plan merged specifically to prevent it. The lesson that
generalises: **when a contract is stated in more than one document, fixing the authoritative copy
is not fixing the contract.** The copy an agent actually reads is the one named after the subject
— `docs/telemetry-guide.md` — not the one filed under a skill's references directory.
