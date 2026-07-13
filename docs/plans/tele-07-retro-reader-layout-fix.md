---
id: tele-07-retro-reader-layout-fix
size: M
blocked_by: []
pipeline: standard
security_review: skipped
security_review_reason: read-only archive scanners plus deletion of one known-bad archive file; no new trust boundaries, no network, no writes into the tracked tree
docs_sync: required
docs_sync_reason: aet-work/references/telemetry-log-schema.md must state explicitly that {project-slug} is the worktree-based `<main-worktree-dir>/<worktree-label>` value from aet-work/lib/telemetry.py derive_project_slug, so future readers cannot re-derive it differently
---

# Plan: Fix aet-retro / mine-learnings Telemetry Reader Layout Drift

## Context

- Bug discovered 2026-07-13 when `aet retro` produced a malformed report
  (`docs/retros/2026-07-13-aet-retro.md`, since deleted): mine-learnings
  scanned 16 runs but 0 files / 0 reports, "Project-level findings" were bare
  stage names (`secure`, `reviewed`, `qa-complete`…), and "AET-level findings"
  were raw Python dict reprs of June queue tasks.
- Logged in `.agents/learnings.jsonl` (commit `1ef65a0`).
- **Root cause 1 — slug/layout drift.** The writer
  (`aet-work/lib/telemetry.py:derive_project_slug`) derives the slug as
  `<main-worktree-dir>/<worktree-label>` (e.g. `aiskills/main`), so the on-disk
  layout is `~/.aet/telemetry/{dir}/{label}/{date}/{run-id}/{task}.jsonl`.
  `aet-evolve/bin/aet-retro` re-implements its own `derive_project_slug()` from
  the git origin URL (`thebrightnest/ae-toolkit`), and
  `aet-evolve/bin/mine-learnings:mine_archive` walks exactly three levels
  (`{project}/{date}/{run}`). Result: the retro read a _different_ project's
  archive (origin-slug collided with another repo's dir/label layout), and
  mine-learnings treated `aiskills/main/2026-07-13` as a run dir, finding no
  JSONL files one level too high.
- **Root cause 2 — unfiltered findings extraction.**
  `aet-retro:extract_message` treats every telemetry record as a finding: it
  falls back to the `stage` key (bare stage names), then to `str(record)`
  (full dict reprs). Queue-snapshot records are not findings.
- **Side effect to clean up:** the buggy run's `emit_learning_candidates`
  appended those bogus findings as `learning_candidate` records at
  `~/.aet/telemetry/thebrightnest/ae-toolkit/2026-07-13/76dbc80d6849442abe8682b7f294164f/aet-retro.jsonl`
  (verified on disk). That file must be deleted so future mining never sees
  "findings" like `secure` or queue-task dicts.

## Intake Triage

- [ ] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] Reproducible defect — handled here as a queued bug-fix plan (aet-bug-report
      investigation already completed in-session; root causes verified against code
      and on-disk archive layout)

## Locked design

- **Single source of slug truth.** Both readers import `derive_project_slug`
  from `aet-work/lib/telemetry.py` via sibling-skill path resolution
  (`Path(__file__).resolve().parents[2] / "aet-work" / "lib"`, added to
  `sys.path`) — the same pattern `aet-retro:run_mine_learnings` already uses to
  locate its sibling binary. If the import fails, exit 1 with a named error
  naming the expected sibling skill; do NOT fall back to an origin-URL
  derivation (that fallback is the bug).
- **mine-learnings walk matches the writer.** `mine_archive` iterates
  `{project-dir}/{label}/{date}/{run-id}/*.jsonl`, validating `{date}` against
  `%Y-%m-%d` (dirs that fail are skipped, not treated as runs). "Runs scanned"
  counts actual run-id dirs.
- **Findings are typed, not guessed.** `categorize_records` only considers
  records with `type == "learning_candidate"` (the type aet-retro itself and
  the skills emit) or records carrying an explicit human-readable
  `message`/`error`/`summary` field. `extract_message` drops the `stage` and
  bare-`str(record)` fallbacks entirely; a record with no usable text is
  skipped, never rendered. AET-vs-project split keeps the existing heuristic,
  applied to the description text.
- **Archive cleanup.** Delete the verified-bad
  `~/.aet/telemetry/thebrightnest/ae-toolkit/2026-07-13/76dbc80d6849442abe8682b7f294164f/`
  run dir (contains only the polluted `aet-retro.jsonl`), then sweep empty
  parents.

## Rejected Alternatives

- **Support both old and new layouts in the readers** — rejected: every
  current archive dir on disk follows the writer's `{dir}/{label}/...` layout;
  the "old scheme" was only ever the retro's own mis-derivation. One layout,
  one reader contract.
- **Fix only aet-retro, leave mine-learnings** — rejected: mine-learnings
  output is the retro's Telemetry Summary section; a half-fix leaves the
  report's top block at zero-counts forever.
- **Re-derive the slug in each reader but "correctly" (dirname + label)** —
  rejected: duplicates the writer's logic in two more places; the drift
  happened precisely because the derivation was re-implemented. Import the
  writer's function and pin it with a contract test.
- **Keep the stage/str(record) fallbacks but dedupe harder** — rejected: the
  fallback output is never a useful finding; dedupe only makes the garbage
  shorter.

## Task List

1. aet-retro: import writer `derive_project_slug`, delete local origin-URL
   version; fail named-error on import failure — S (traces: root cause 1)
2. aet-retro: restrict `categorize_records`/`extract_message` to typed records;
   remove `stage` and `str(record)` fallbacks — S (traces: root cause 2)
3. mine-learnings: four-level walk with date validation; correct run/file
   counts — S (traces: root cause 1)
4. Tests: fixture archive in the writer layout for both readers (retro finds
   real findings, mine-learnings reports nonzero file/run counts), plus a
   contract test asserting reader slug == writer slug for a temp repo — M
   (traces: root cause 1, root cause 2)
5. Docs: make the slug definition explicit in
   `aet-work/references/telemetry-log-schema.md`; delete the polluted archive
   run dir and sweep empty parents — S
6. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] This is not one of several near-identical additions (templates, examples, docs).
- [x] The diff is expected to exceed 3 files or 50 lines.
- [x] The work cannot share a branch/PR with related tasks.

## Files to Modify

- `aet-evolve/bin/aet-retro`
- `aet-evolve/bin/mine-learnings`
- `tests/test_aet_retro.py` (new or extended — name the test covering both readers)
- `tests/test_mine_learnings.py` (new or extended)
- `aet-work/references/telemetry-log-schema.md`

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] For each new source file introduced by this plan, name the test that will cover it
- [ ] Contract test: reader slug derivation is literally the writer's
      `derive_project_slug` (no second implementation)
- [ ] Live check: `aet retro` against the real `~/.aet/telemetry` produces
      nonzero file counts and no dict-repr findings
- [ ] Polluted run dir
      `~/.aet/telemetry/thebrightnest/ae-toolkit/2026-07-13/76dbc80d6849442abe8682b7f294164f/`
      confirmed deleted
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. The readers revert to broken-but-harmless output; no
data is mutated in the tracked tree. The deleted archive run dir is
intentionally not restorable (its contents are the bug's pollution).

## Pipeline

`standard` — touches two CLI tools plus tests; no auth/data-model/API surface.

---

_Stage: plan-approved_
