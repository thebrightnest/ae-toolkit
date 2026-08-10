---
id: t2r-01-learnings-append-cli
size: M
work_class: normal
blocked_by: []
pipeline: standard
security_review: required
security_review_reason: new CLI command surface with file-path and free-text input handling
docs_sync: required
docs_sync_reason: deletes documented hand-append procedures in three shipped skills
---

# Plan: `aet learnings append` — Code Writer for `.agents/learnings.jsonl`

## Context

PRD: `docs/prds/structural-review-tier-2-prd.md` (R-1). Today zero commands
write `.agents/learnings.jsonl`; every entry was appended by hand from prose
instructions in aet-bug-report, aet-evolve, and aet-implement. The PRD states
169 entries exist; the file actually holds 54 JSON entries (verified
2026-08-10 via `grep -c '{'`) — the discrepancy is recorded here, not
re-litigated; the requirement (one schema-validated writer, three call sites
migrated) is unaffected.

Verified entry shape (`.agents/learnings.jsonl`): 44 entries use `timestamp`
(ISO-8601), 10 older entries use `date` (YYYY-MM-DD); fields are `trigger`
(list of keywords, optional), `problem`, `layer`, `fix`, `prevents`, and
optional `recurrence` (int, 5 entries). One outlier entry uses a
`context`/`lesson`/`source` shape. The command writes the canonical
`timestamp` shape only; legacy entries are not validated or migrated.

Decisions this plan is scoped against:

- ADR-039 (CLI noun taxonomy): the command is a noun-scoped group
  `learnings` with verb `append`, registered in `src/aet/cli/main.py`
  alongside the existing groups. The top-level `mine-learnings` command
  (`src/aet/cli/mine_learnings.py`) is unrelated (telemetry archive mining)
  — naming adjacency noted, no collision.
- ADR-055 (post-slc state): no plan frontmatter `status`; no prose writer is
  introduced around `aet gate submit` or `aet state set-stage`.
- Ledger (`src/aet/ledger.py:28`): `ALLOWED_KINDS` is
  `{cut, stage, verdict, land}` — no kind fits a learning append, so this
  mechanism emits **no** ledger event. Extending the taxonomy is an
  ADR-level decision and is out of scope.
- `filelock` is already a runtime dependency (`pyproject.toml:14`, used by
  `src/aet/ledger.py`); the append path reuses that pattern.

Known remainders, deliberately out of scope: `AGENTS.md`'s guardrail
"Always update `.agents/learnings.jsonl` after a bug or misalignment" stays
generic prose (it does not instruct a hand-append format), and
`skills/aet-evolve/references/escalation-ladder.md`'s recurrence-increment
procedure edits an existing entry, which an append-only writer cannot do —
it remains prose.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. New module `src/aet/cli/learnings.py`: Typer group `learnings` with an
   `append` command. Required options `--problem`, `--layer`, `--fix`,
   `--prevents` (non-empty after strip, else exit 1 with a named error);
   repeatable `--trigger`; optional `--recurrence` (positive int). The
   command mints the `timestamp` itself (ISO-8601 UTC), serializes one
   canonical JSON line, and appends it under a `filelock` lock to
   `.agents/learnings.jsonl` (default path overridable via `--file` for
   tests); it never rewrites or validates existing lines — S (traces: R-1)
2. Register the group in `src/aet/cli/main.py` (import +
   `app.add_typer(learnings.app, name="learnings", ...)` in the noun-scoped
   block) and add `"learnings"` to `_NOUN_GROUPS` in
   `tests/cli/test_command_groups.py:307-319` — S (traces: R-1)
3. New test file `tests/cli/test_learnings.py`: unit tests for schema
   validation (missing/empty required field exits 1; `--recurrence 0` and
   negative values rejected; no `--trigger` produces an entry without the
   key) and integration tests via `run_typer` against a temp `--file`
   (appended line parses as JSON with exactly the canonical field set;
   second append preserves the first line byte-for-byte; entry shape matches
   the dominant `timestamp` entries in the real file) — S (traces: R-1)
4. Migrate the three prose call sites to invoke the command:
   `skills/aet-bug-report/SKILL.md:128` (Step 4 item 5) and `:145`
   (integration-table "How" cell); `skills/aet-evolve/SKILL.md:60` and
   `:76-98` (field list, hand-written JSON format block, and trigger-fallback
   note replaced by the command and its options);
   `skills/aet-evolve/references/escalation-ladder.md:18` (1st-occurrence
   action) and `skills/aet-evolve/references/aet-retro.md:27`;
   `skills/aet-implement/SKILL.md:46` (override logging) — S (traces: R-1)
5. Merge branch to main and verify integration — S

### Floor Check

- [x] Stands alone: one new command plus its call-site migration is an
  independently shippable, reviewable behaviour change with no blockers.
- [x] Expected diff (~300 lines across src, tests, and skills) materially
  exceeds branch/PR/review overhead.
- [x] Cannot share a branch with siblings: the other t2r plans are unblocked
  but touch disjoint surfaces (ship, context, lenses); merging them would
  re-create the multi-concern PR pattern the slc series split apart.

## Rejected Alternatives

- **Validate or migrate the 54 legacy entries** (`date` shape, the
  `context`/`lesson`/`source` outlier) — rejected: the writer is
  append-only; rewriting hand-written history risks data loss for zero
  behavior change, and no reader schema-validates the file today.
- **Emit a ledger event per append** — rejected: `ALLOWED_KINDS` in
  `src/aet/ledger.py:28` has no fitting kind; adding one is an ADR-level
  taxonomy change, not a ride-along.
- **`aet learnings bump --recurrence` to implement the escalation-ladder
  increment** — rejected: that edits an existing entry, contradicting the
  append-only contract; the increment stays documented prose until a
  follow-up prices an edit command.
- **Extend `mine-learnings` instead of a new group** — rejected:
  `mine_learnings.py` scans the telemetry archive for patterns; gluing a
  JSONL writer onto it conflates two unrelated nouns (ADR-039).

## Files to Modify

- `src/aet/cli/learnings.py` (new)
- `src/aet/cli/main.py`
- `tests/cli/test_learnings.py` (new)
- `tests/cli/test_command_groups.py`
- `skills/aet-bug-report/SKILL.md`
- `skills/aet-evolve/SKILL.md`
- `skills/aet-evolve/references/escalation-ladder.md`
- `skills/aet-evolve/references/aet-retro.md`
- `skills/aet-implement/SKILL.md`

## Validation Steps

- [ ] Lint passes (`make lint-py`)
- [ ] Tests pass (`make test`)
- [ ] New-source coverage: `src/aet/cli/learnings.py` is covered by
  `tests/cli/test_learnings.py` — schema-validation tests are unit tests
  (single layer: argument → validation); the temp-file append tests are
  integration tests (CLI → filesystem); no API boundary tests apply (no
  frontend/backend contract)
- [ ] `tests/cli/test_command_groups.py::TestNounGroups` passes with
  `"learnings"` registered
- [ ] `grep -n "learnings.jsonl" skills/aet-bug-report/SKILL.md
  skills/aet-evolve/SKILL.md skills/aet-evolve/references/escalation-ladder.md
  skills/aet-evolve/references/aet-retro.md skills/aet-implement/SKILL.md`
  shows no hand-append instructions (field lists or raw JSON blocks); every
  remaining mention either invokes `aet learnings append` or reads the file
- [ ] `aet learnings append --problem p --layer l --fix f --prevents pr`
  against a scratch `--file` produces a line whose `timestamp` shape matches
  the dominant entries in `.agents/learnings.jsonl` (observable behavior:
  the written entry is indistinguishable in shape from a correctly
  hand-written one)
- [ ] R-trace coverage: R-1 covered by tasks 1–4; no task cites another R-id
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge. The skill prose restorations come back with the revert;
any entries already appended via the command are valid canonical-shape data
and need no cleanup.

## Pipeline

`standard` — the command defines the canonical write schema for the tracked,
persisted `.agents/learnings.jsonl`, so ADR-047's persisted-state override
applies: `standard` was chosen for it over the S-size `minimal` default.

---

*Stage: qa-complete*
*Next step: run `aet-review`*
