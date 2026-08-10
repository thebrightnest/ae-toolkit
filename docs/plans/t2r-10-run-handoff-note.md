---
id: t2r-10-run-handoff-note
size: M
work_class: normal
blocked_by: []
pipeline: standard
security_review: required
security_review_reason: new file-to-prompt injection path — run-scoped file content flows into stage prompts (LLM trust boundary)
docs_sync: required
docs_sync_reason: adds write/consume procedures to three shipped skills
---

# Plan: Run-Scoped Handoff Note — `aet handoff` and Orchestrator Prompt Injection

## Context

PRD: `docs/prds/structural-review-tier-2-prd.md` (R-8). Audit R1
(`docs/audits/2026-07-13-pipeline-flow-efficiency.md:48-51`, finding F1) has
been unbuilt for 3+ weeks: every stage session starts with zero memory of the
previous one. The priced incident: a 39.7-min review on a 635-line diff
against an 11-min baseline, spent re-investigating the evidence-verdict path
contract that the same run's QA session had already navigated (F1, lines
39-42). The fix is one run-scoped handoff artifact — decisions taken,
pre-existing failures, validation commands, evidence path — written by the
implement session, appended by each later stage, and injected by the
orchestrator into subsequent stage prompts.

Verified anchors (2026-08-10):

- Run dirs exist today: `.agents/runs/<run-id>/` holds `pid`, `returncode`,
  `output.log`, `telemetry_dir` (`src/aet/cli/main.py:129-141`,
  `src/aet/cli/orchestrator.py:173-214`). The note lives alongside them as
  `handoff.json`.
- `build_prompt` (`src/aet/cli/orchestrator.py:445-461`) currently passes
  only the skills chain, plan file, current/target stage, and the freshness
  clause. The injection pattern to mirror is the QA-verdict freshness
  clause (`orchestrator.py:396-442`, pfe-01/02): computed best-effort at
  spawn, never raises, threaded through `run_stage` (orchestrator.py:994-998)
  and `run_stage_group` (orchestrator.py:1097-1100).
- Stage sessions always receive `AET_RUN_ID` in env
  (orchestrator.py:1008-1009, 1110-1111), so skill-invoked appends resolve
  the run without new plumbing.

Decisions this plan is scoped against:

- ADR-055 (post-slc state): the note never carries verdicts and never
  touches plan footers or queue state — `aet gate submit` remains the sole
  verdict writer; the note's `evidence_path` field is a pointer to the
  verdict file, not a copy. No prose writer is introduced around
  `aet gate submit` or `aet state set-stage`.
- ADR-039 (CLI noun taxonomy): the writer is a noun-scoped group `handoff`
  with verbs `append` and `show`, registered in `src/aet/cli/main.py`
  alongside the existing groups.
- Ledger (`src/aet/ledger.py:28`): `ALLOWED_KINDS` is
  `{cut, stage, verdict, land}` — no kind fits a handoff append (run-scoped
  working memory, not a provenance fact), so this mechanism emits **no**
  ledger event. Extending the taxonomy is an ADR-level decision, out of
  scope (same disposition as t2r-01).
- `filelock` is already a runtime dependency (used by `src/aet/ledger.py`);
  the append path reuses that pattern.

Collisions recorded: t2r-01 (same batch) edits
`skills/aet-implement/SKILL.md:46` and t2r-05 deletes the Shared Preamble
blocks in all three skills this plan touches (`aet-implement:16`,
`aet-qa:17`, `aet-review:17`). This plan's edits land in the Completion
Protocol / verdict-contract sections — disjoint regions, same files. No
ordering dependency (the edits commute textually), but whichever of t2r-01 /
t2r-05 / t2r-10 merges last should expect a trivial rebase on those files.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. New module `src/aet/handoff.py`: schema v1 and the read/append/render
   core. `handoff_path(repo_root, run_id)` →
   `.agents/runs/<run-id>/handoff.json`; `append_entry(...)` creates the
   file lazily on first append and writes one entry under a `filelock`
   lock; `read_note(...)` returns the parsed note or `None` on any
   missing/corrupt file (never raises); `render_prompt_block(note)` renders
   the injection text. Entry shape (exactly the four R-8 fields, all
   optional but at least one non-empty per append, enforced by the CLI):

   ```json
   {
     "schema_version": 1,
     "run_id": "run-20260810-093000-abcd1234",
     "entries": [
       {
         "stage": "plan-approved",
         "decisions": ["..."],
         "pre_existing_failures": ["..."],
         "validation_commands": ["make test"],
         "evidence_path": null,
         "recorded_at": "<ISO-8601 UTC, minted by the command>"
       }
     ]
   }
   ```

   — M (traces: R-8)
2. New CLI module `src/aet/cli/handoff.py`: Typer group `handoff` with
   `append` (options `--stage` required; repeatable `--decision`,
   `--pre-existing-failure`, `--validation-command`; optional
   `--evidence-path`; run id from `--run-id` or `AET_RUN_ID`, missing →
   exit 1 with a named error; at least one of the four fields required) and
   `show` (prints `render_prompt_block` output for a run id). Register the
   group in `src/aet/cli/main.py` (import + `app.add_typer` in the
   noun-scoped block) and add `"handoff"` to `_NOUN_GROUPS` in
   `tests/cli/test_command_groups.py:307-319` — S (traces: R-8)
3. Orchestrator injection in `src/aet/cli/orchestrator.py`: add a
   `handoff_clause: str = ""` parameter to `build_prompt`
   (orchestrator.py:445-461) appended after the freshness clause; add
   `_handoff_clause(repo_root, run_id)` mirroring `_qa_freshness_decision`
   (orchestrator.py:422-442) — best-effort, returns `""` on absent
   run id/note or any error; wire it into `run_stage`
   (orchestrator.py:994-998) and `run_stage_group`
   (orchestrator.py:1097-1100). Injected format:

   ```
   Run handoff note (written by earlier stages of this same run — trust
   what it records and do NOT re-investigate it):
   [stage: plan-approved]
   decisions: ...
   pre-existing failures: ...
   validation commands: ...
   evidence path: ...
   ```

   `render_prompt_block` caps the block at 4000 chars with an explicit
   truncation marker so a verbose run cannot bloat the prompt — M
   (traces: R-8)
4. Tests: new `tests/test_handoff.py` (unit: schema round-trip, lazy
   create, corrupt-file read returns `None`, render cap, at-least-one-field
   rule) and `tests/cli/test_handoff.py` (integration via `run_typer`:
   append → file round-trip, `AET_RUN_ID` env resolution, missing run id
   exits 1, `show` renders); extend
   `tests/orchestrator/test_orchestrator.py` (prompt injection: note
   present → block in single-stage and group prompts; note absent → prompt
   byte-identical to today) — M (traces: R-8)
5. Skill updates — write/consume wiring, one block each:
   `skills/aet-implement/SKILL.md` (Completion Protocol: when `AET_RUN_ID`
   is set, write the run's first entry via `aet handoff append` with all
   four fields — decisions taken, pre-existing failures encountered,
   validation commands run, evidence path if any);
   `skills/aet-qa/SKILL.md` (after `aet gate submit`, append the QA entry
   including the verdict's evidence path; consume the injected note instead
   of re-deriving setup context); `skills/aet-review/SKILL.md` (consume the
   injected note — decisions and pre-existing failures are settled inputs,
   not review targets; after `aet gate submit`, append the review entry) —
   S (traces: R-8)
6. Merge branch to main and verify integration — S

### Floor Check

- [x] Stands alone: one artifact, one writer command, one injection point —
  an independently shippable behavior with no blockers (`blocked_by: []`).
- [x] Expected diff (~500 lines across src, tests, and skills) materially
  exceeds branch/PR/review overhead.
- [x] Cannot share a branch with siblings: t2r-01 (learnings CLI), t2r-05
  (preamble absorption), t2r-08 (boundary lens), and t2r-11 (generated CLI
  reference) touch disjoint mechanisms; merging would re-create the
  multi-concern PR pattern the slc series split apart.

## Rejected Alternatives

- **A hand-written `context.md` per run, as the audit text literally
  proposed** — rejected: a prose-authored structured artifact is exactly
  the writer-split pattern slc-05 deleted (learnings 32, 37, 41, 43, 53).
  The write path is a schema-validating command; JSON on disk, markdown
  only at render time.
- **Orchestrator auto-generates entries from telemetry instead of skill
  appends** — rejected: decisions taken and pre-existing failures are
  judgment content only the stage session possesses; telemetry records
  carry no such fields, and inventing them is a larger mechanism than the
  audit priced.
- **Extend the ledger taxonomy with a handoff event kind** — rejected:
  `ALLOWED_KINDS` has no fitting kind and the note is run-scoped working
  memory, not a provenance fact; taxonomy changes are ADR-level (same
  disposition as t2r-01).
- **One mutable entry overwritten per stage instead of append-only
  per-stage entries** — rejected: overwrite loses which stage recorded
  what, and append-only matches the ledger discipline this repo settled on
  (ADR-055).
- **Inject the note at prime time via `aet context` (R-3/R-5) instead of at
  stage spawn** — rejected: the note is run-scoped and only the
  orchestrator knows the run id at spawn; prime-time injection would leak
  one run's context into unrelated sessions.

## Files to Modify

- `src/aet/handoff.py` (new)
- `src/aet/cli/handoff.py` (new)
- `src/aet/cli/main.py`
- `src/aet/cli/orchestrator.py`
- `tests/test_handoff.py` (new)
- `tests/cli/test_handoff.py` (new)
- `tests/cli/test_command_groups.py`
- `tests/orchestrator/test_orchestrator.py`
- `skills/aet-implement/SKILL.md`
- `skills/aet-qa/SKILL.md`
- `skills/aet-review/SKILL.md`

## Validation Steps

- [ ] Lint passes (`make lint-py`)
- [ ] Tests pass (`make test`)
- [ ] New-source coverage: `src/aet/handoff.py` is covered by
  `tests/test_handoff.py` (unit: single layer, schema/append/render);
  `src/aet/cli/handoff.py` is covered by `tests/cli/test_handoff.py`
  (integration: CLI → filesystem round-trip via `run_typer`); no API
  boundary tests apply (no frontend/backend contract)
- [ ] `tests/orchestrator/test_orchestrator.py` proves the observable
  injection behavior: with a note present, the review-stage prompt contains
  the implement session's four fields; with no note, the prompt is
  byte-identical to the pre-change shape
- [ ] `tests/cli/test_command_groups.py::TestNounGroups` passes with
  `"handoff"` registered
- [ ] End-to-end observable behavior (manual, on this repo): run
  `aet handoff append --run-id <scratch> --stage plan-approved --decision d
  --validation-command "make test"` against a scratch run dir, then
  `aet handoff show --run-id <scratch>` renders the four fields as the
  prompt block
- [ ] `grep -n "handoff" skills/aet-implement/SKILL.md
  skills/aet-qa/SKILL.md skills/aet-review/SKILL.md` shows each skill
  invokes `aet handoff append` and none instructs hand-editing
  `handoff.json`
- [ ] R-trace coverage: R-8 covered by tasks 1–5; no task cites another
  R-id
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge. Skill prose additions and the injection wiring restore
with the revert; `handoff.json` files already written under
`.agents/runs/` are untracked run metadata and need no cleanup (the
post-revert orchestrator never reads them).

## Pipeline

`standard` — touches the orchestrator spawn path every run depends on, so
the default TDD→implement→QA isolation stays on; no auth/data-model/API
surface that would justify `full`.

---

*Stage: secure*
*Next step: run `aet-sync-docs`, then `aet-ship`*
