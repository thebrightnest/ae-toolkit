---
id: t2r-04-aet-context-command
size: L
work_class: normal
blocked_by: []
pipeline: standard
security_review: required
security_review_reason: new CLI command surface with positional-target resolution, env-var reading, and git subprocess calls
docs_sync: required
docs_sync_reason: as-built JSON field list, flag names, and banner format must be reconciled against R-3 wording and t2r-05's recorded assumptions
---

# Plan: `aet context` — Session Workflow Context Command

## Context

PRD: `docs/prds/structural-review-tier-2-prd.md` (R-3). The Shared Preamble
block (canonical copy at `skills/aet-review/SKILL.md:17-30`, duplicated at
`skills/aet-prime/SKILL.md:18-29` and 14 other skills) is hand-collected
prose: agents half-execute it and hand-parse the wrong footer. This plan
delivers one command — the shape of `bd prime` — emitting the fixed battery
(BRANCH, REPO_STATE, AGENTS_MD, LEARNINGS top-3, ACTIVE_PLAN, LAST_PIV,
ACTIVE_PRD_STAGE, ACTIVE_PLAN_STAGE) as JSON plus the stage banner, with
token budget, `PRIME.md` override, `--memories-only`, and `--hook-json`
modes.

Decisions this plan is scoped against:

- ADR-039 (`docs/adr/039-namespace-taxonomy.md`): `context` is a top-level
  single-word command in the `next`/`status` family, registered in
  `src/aet/cli/main.py:80-92`. The name is free — `grep` over
  `src/aet/cli/` shows no collision; repo-root `CONTEXT.md` is unrelated
  prose.
- ADR-055 (post-slc state): no plan frontmatter `status`; this plan
  introduces no prose writer around `aet gate submit` or
  `aet state set-stage`.
- ADR-037: no new runtime dependency — the module uses stdlib + `typer`
  (already runtime); the command is read-only, so no `filelock` path.
- Ledger (`src/aet/ledger.py:28`): `ALLOWED_KINDS` is
  `{cut, stage, verdict, land}` — a read-only context emission produces no
  state, so this mechanism emits **no** ledger event (same disposition as
  t2r-01).

Collisions and assumptions, verified 2026-08-10:

- Sibling `docs/plans/t2r-05-skills-preamble-absorption.md` already exists,
  `blocked_by: t2r-04`, and records assumptions this plan satisfies: the
  JSON battery includes `ACTIVE_PLAN` and `LAST_PIV`, learnings selection
  moves into the command, and the banner is emitted verbatim
  (`📍 Current stage: {stage}.`, `skills/aet-review/SKILL.md:32`). This
  plan's emitted field list and banner format are t2r-05's replacement
  contract (its task 1).
- The digest/learnings-injection half of the PRD (R-5) is **not** in this
  plan — that is t2r-07. LEARNINGS here is the plain top-3-by-recency
  selection the preamble already specifies, not promoted-learnings
  injection.
- The PRD's "16 Shared Preamble blocks" reconciles to 12 `## Shared
  Preamble` + 4 renamed `## Before You Start` blocks; that reconciliation
  is t2r-05's docs-sync scope. This plan touches **no** file under
  `skills/`.
- Two footer stage readers exist with divergent semantics:
  `plan_parser.stage_from_plan` (`src/aet/plan_parser.py:161`, first match;
  callers `backlog.py:64`, `gate.py:126`, `sprint.py:94`) and
  `verifier.read_plan_stage` (`src/aet/verifier.py:37-53`, last match,
  because body text may mention stage lines; callers
  `orchestrator.py:288,3090`). The absorption consolidates on last-match —
  strictly safer on polluted bodies — with `read_plan_stage` delegating.
- There is no `most_recent_plan` helper; only `most_recent_prd`
  (`src/aet/plan_parser.py:216`). The command adds the plan twin.
- SessionStart envelope: all three harnesses currently accept the same
  shape, `{"hookSpecificOutput": {"hookEventName": "SessionStart",
  "additionalContext": "..."}}` (Anthropic hooks reference; Codex's strict
  SessionStart validator; Gemini's `hookSpecificOutput.additionalContext`).
  One builder, three harness values; exact bytes pinned by golden fixtures.
- MCP detection has no precedent in `src/aet/`; the budget resolution order
  defined in task 4 is new mechanism, pinned by tests.

**Size re-evaluation (assigned L).** Signals tripped: expected diff
(~880 lines: ~380 new module, ~50 consolidation/registration, ~450 tests)
exceeds 600, and the collector + three-mode surface plausibly exceeds one
human-day. Subsystems touched: one (`src/aet` code + tests; no `skills/`,
no `.agents/`). Two signals → the task list is split in-plan into dependent
children rather than shipped as one oversized block: tasks 1–3 are the
foundation, tasks 4–7 (the modes) depend on task 3, tasks 8–10 close out.
Cross-plan splitting was rejected (see Rejected Alternatives): the command
is one reviewable contract and t2r-05 is blocked on its full shape.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

Child split per Context: **foundation** (1–3) → **modes** (4–7, each
depends on task 3) → **closeout** (8–10).

1. [✓] `src/aet/plan_parser.py`: add `most_recent_plan(plans_dir)` mirroring
   `most_recent_prd` (:216), and change `stage_from_plan` (:161) to
   last-match semantics per the rule documented at
   `src/aet/verifier.py:40-43`; `verifier.read_plan_stage` becomes a thin
   delegate (signature kept; callers `orchestrator.py:288,3090` untouched).
   Existing callers of `stage_from_plan` (`backlog.py:64`, `gate.py:126`,
   `sprint.py:94`) need no edits — S (traces: R-3)
2. [✓] New module `src/aet/cli/context.py`, collectors half: git-backed
   collectors (BRANCH; REPO_STATE = clean/dirty/merge-conflict from
   `git status --porcelain` unmerged entries or `MERGE_HEAD`; LAST_PIV =
   most recent commit date touching both `docs/plans/*.md` and `src/` or
   `tests/`, scan bounded to 200 commits, null when none) and filesystem
   collectors (AGENTS_MD presence + mtime; ACTIVE_PLAN = `docs/plans/*.md`
   modified in the last 7 days; ACTIVE_PRD_STAGE / ACTIVE_PLAN_STAGE via
   `most_recent_prd` / `most_recent_plan` + `stage_from_plan`; LEARNINGS =
   top-3 by recency from `.agents/learnings.jsonl`, tolerating both the
   `timestamp` and legacy `date` entry shapes). Every collector fails
   open — non-git directory, missing files, malformed lines yield nulls,
   never a traceback; the command always exits 0 — M (traces: R-3)
3. [✓] Same module, command half: Typer app `context` on the
   `invoke_without_command` pattern (`src/aet/cli/next.py:142-165`).
   Default output = the banner `📍 Current stage: {stage}.` (verbatim;
   ACTIVE_PLAN_STAGE first, else ACTIVE_PRD_STAGE, else no banner)
   followed by pretty JSON with `schema_version: 1` and snake_case keys
   (`branch`, `repo_state`, `agents_md`, `learnings`, `active_plan`,
   `last_piv`, `active_prd_stage`, `active_plan_stage`). `--json` emits
   the battery only. Optional positional TARGET (ticket number, task id,
   or plan path) resolves through `resolve_plan_arg`
   (`src/aet/plan_parser.py:416`) and `build_ticket_map`
   (`src/aet/plan_parser.py:148`) and pins `active_plan` /
   `active_plan_stage` to that plan — M (traces: R-3)
4. [✓] Token budget (depends on task 3): `--budget {auto,cli,mcp}` and
   `--max-lines N`. Resolution order: explicit flag → `AET_CONTEXT_CLIENT`
   env → MCP session env markers → `cli`. Budgets reshape the human/hook
   rendering only (`mcp` = compact: top-1 learning, single-line entries;
   `--max-lines` caps rendered lines); the `--json` schema is never
   truncated — S (traces: R-3)
5. [✓] `PRIME.md` wholesale override (depends on task 3): a repo-root
   `PRIME.md` replaces the human-facing output verbatim in default and
   hook modes; `--json` still emits the computed battery with
   `"prime_md_override": true` so machine consumers can detect the
   override — S (traces: R-3)
6. [✓] `--memories-only` (depends on task 3): emits only the learnings
   selection plus the stage line, in the compact rendering, for hook
   contexts — S (traces: R-3)
7. [✓] `--hook-json {claude-code,codex,gemini}` (depends on tasks 3, 4, 6):
   wraps the budget-shaped block (or `PRIME.md` contents) in the
   SessionStart envelope `{"hookSpecificOutput": {"hookEventName":
   "SessionStart", "additionalContext": "..."}}` — one builder for all
   three harnesses per the Context verification; mutually exclusive with
   `--json` (usage error, exit non-zero) — S (traces: R-3)
8. [✓] Register in `src/aet/cli/main.py`: import `context` in the subcommand
   import block (:26-53) and `app.add_typer(context.app, name="context")`
   in the top-level single-word block (:80-92) — S (traces: R-3)
9. [✓] New test file `tests/cli/test_context.py` covering tasks 1–8
   (unit/integration split named in Validation Steps) — M (traces: R-3)
10. [Deferred: merge to main and integration verification happen at the aet-ship stage]
   Merge branch to main and verify integration — S

### Floor Check

- [x] Stands alone: one new read-only command is an independently
  shippable, reviewable behaviour change; its consumers (t2r-05, t2r-07)
  are separate plans already queued behind it.
- [x] Expected diff (~880 lines) materially exceeds branch/PR/review
  overhead.
- [x] Cannot share a branch with t2r-05: merging a `src/` command with a
  16-file `skills/` sweep is the multi-concern PR pattern the slc series
  split apart; t2r-05's own Rejected Alternatives already declined the
  merge from its side.

## Rejected Alternatives

- **Split cross-plan into t2r-04a (core command) and t2r-04b (hook
  modes)** — rejected: the command is one contract; t2r-05 is blocked on
  the full shape (banner + JSON), and a modes-only follow-up plan would
  sit in the queue with no independent consumer. The in-plan child split
  above carries the dependency structure instead.
- **Truncate the `--json` output to satisfy token budgets** — rejected:
  truncated JSON breaks every downstream parser (t2r-05's skills parse the
  battery); budgets reshape the human rendering only.
- **Per-harness envelope builders** — rejected: all three harnesses
  currently accept the identical `hookSpecificOutput`/`SessionStart`/
  `additionalContext` shape; one builder with a harness-valued flag
  absorbs future divergence. Golden fixtures pin today's bytes.
- **Emit a ledger event per invocation** — rejected: the command is
  read-only and produces no state; `ALLOWED_KINDS`
  (`src/aet/ledger.py:28`) has no fitting kind, and extending the taxonomy
  is an ADR-level decision (same disposition as t2r-01).
- **Extend `aet status` instead of a new command** — rejected:
  `aet status` reports queue health and plan drift; session-context
  emission is a distinct noun under ADR-039, and the `context` name is
  verified free.
- **Keep both stage readers as-is and call `verifier.read_plan_stage`
  from the new module** — rejected: two readers with divergent match
  semantics is the drift pattern the absorption exists to delete; the
  consolidation is 25 lines and covered by existing callers' tests.

## Files to Modify

- `src/aet/cli/context.py` (new)
- `src/aet/cli/main.py`
- `src/aet/plan_parser.py`
- `src/aet/verifier.py`
- `tests/cli/test_context.py` (new)

## Validation Steps

- [x] Lint passes (`make lint-py`)
- [x] Tests pass (`make test`)
- [x] New-source coverage: `tests/cli/test_context.py` covers
  `src/aet/cli/context.py`:
  - unit (single layer): each collector against fixture filesystems/git
    repos (REPO_STATE three-way classification, LAST_PIV bound and null
    case, learnings top-3 across `timestamp`/`date` shapes, malformed
    learnings lines skipped); budget resolution order; PRIME.md detection;
    stage-reader last-match on a body polluted with `_Stage:` mentions
  - integration (CLI → filesystem/git): `run_typer(aet.app, ["context"])`
    against a temp git repo with AGENTS.md, learnings, plans, and PRDs —
    exit 0, banner verbatim, all eight battery keys present; TARGET
    pinning by ticket number and by task id; `--json` parses clean;
    `--memories-only` omits non-learnings keys; PRIME.md override in
    default and hook modes
  - contract (golden fixtures): `--hook-json` output for each of
    `claude-code`, `codex`, `gemini` matches a checked-in golden envelope
    byte-for-byte; `--json` + `--hook-json` together exits non-zero
  - no frontend ↔ backend contract exists — no API boundary tests apply
- [x] `src/aet/plan_parser.py` / `src/aet/verifier.py` consolidation is
  covered by the stage-reader tests above plus the existing suites for
  the unchanged callers (`tests/cli/test_command_groups.py`,
  gate/sprint/orchestrator tests stay green)
- [x] `git diff --name-only origin/main...HEAD` contains no `skills/` or
  `.agents/` path (skill absorption is t2r-05)
- [x] Observable behavior in this repo: `.venv/bin/aet context` exits 0
  with all eight battery keys and the banner; `.venv/bin/aet context
  --hook-json claude-code | python3 -m json.tool` parses; `.venv/bin/aet
  context --json` contains `"active_plan_stage"` matching this plan's
  footer (the `aet` wrapper in `~/.local/bin/` is a stale pre-existing
  install and not part of this change)
- [x] R-trace coverage: R-3 covered by tasks 1–9; no task cites another
  R-id
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge. The command and its tests disappear with the revert;
`stage_from_plan`'s last-match semantics revert with it (callers are
behavior-compatible either way — last-match only differs on bodies that
mention stage lines). No state, ledger events, or skill content is
written, so nothing else needs unwinding.

## Pipeline

`standard` — L-size default per the template; no risk override to `full`
(no auth, data-model, API, or dependency surface — read-only stdlib +
typer), and security review stays `required` per frontmatter.

---

*Stage: merged*
*Next step: run `aet-ship`*
