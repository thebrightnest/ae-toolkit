# Open items: reset replay, validation scoping, client-project findings

*Compiled 2026-08-24 — every item verified against `main` at `7c94b248` (v1.10.0).
Eleven items closed the same day; the closures are recorded under "Closed".*

Three sources feed this register: the divergence record at
`docs/audits/2026-08-24-local-main-reset-divergence.md`, which lists work
discarded when local `main` was reset; `content/2026-08-19-scoped-validation-review.md`;
and `content/2026-08-24-aet-findings-from-a-client-project.md`. Items that were
already resolved when those documents were written are listed under "Not open";
items closed against this register are listed under "Closed 2026-08-24". Both
carry the evidence that closed them.

Ordering is by leverage. IDs are stable; the order is not.

## Summary

| ID | Item | Source | Size |
|---|---|---|---|
| OI-05 | Settled siblings drop out of r-trace coverage | client 2 | design |
| OI-06 | `run-one` skips the intake validation `sprint add` enforces | client 1 | M |
| OI-07 | No failure class for "retry cannot succeed yet" | client 8 | S |
| OI-09 | Decide the direction for test-target selection | review F-2 | design |
| OI-10 | Replay owb-13: integration branch derived from the PRD (R-17) | reset 1 | L |
| OI-17 | `test_stall_killed_and_classified_timeout` is flaky and unfiled | review | S |
| OI-18 | Scope `validate-skills.sh` to changed skills | review | S |
| OI-19 | Delete the preserved reset branches | reset | one line |

## OI-05 — Settled siblings drop out of r-trace coverage

`src/aet/plan_validate.py:393-394` builds the coverage union from a
non-recursive `plans_dir.glob("*.md")` filtered by `plan_parser.is_settled_plan`.
A plan whose footer reads `Stage: merged` is settled, and `docs/plans/archive/`
falls outside the glob, so a merged plan is invisible twice over. For a PRD whose
siblings have all merged, a new plan is judged against its own traces alone and
intake demands it trace every requirement the PRD declares — 30 findings for a
plan legitimately delivering 6 of 38, in the reported case. Staging the archived
siblings back into `docs/plans/` does not help, because the staged copies are
settled.

The pressure this creates is to annotate requirements a plan does not deliver,
which falsifies the check's own input. No live plan covers it:
`docs/prds/the-record-is-the-plan-prd.md` (R-1 through R-10) addresses
post-intake consumers, ship resolution, metrics and archive retirement, and
never touches r-trace.

Three candidate directions: credit coverage from settled plans, scope the
requirement set per plan rather than per PRD, or emit a distinct finding class
for "covered by a settled sibling" that does not block promotion.

## OI-06 — `run-one` skips the intake validation `sprint add` enforces

`sprint add` refuses a plan that fails intake validation
(`src/aet/cli/sprint.py:168`, `:175`). `plan_validate` appears nowhere in
`src/aet/cli/orchestrator.py`, and `run-one` records its task in the queue on
completion (`:3603`). A plan `sprint add` refuses runs through `run-one`, and the
resulting queue entry is indistinguishable from a validated one.

Two properties follow: intake quality is advisory while presenting as mandatory,
and the audit trail cannot answer whether a queued task passed intake. Either
`run-one` applies the same validation with an explicit recorded `--skip-intake`,
or `_record_run_one_in_queue` marks the task intake-unvalidated.

## OI-07 — No failure class for "retry cannot succeed yet"

`FailureClass` (`src/aet/failure.py:10-17`) offers `environment`, `flaky`,
`design`, `timeout` and `canceled`. No pattern in `_ENVIRONMENT_PATTERNS`
(`:23-47`) matches a rate limit, quota or session limit, so an API 429 with a
non-zero exit falls through to `FLAKY` at `:91` and is requeued. Nothing about a
session limit is transient within the retry interval.

The unbounded cycling recorded in the client project is now capped: signatures
normalise timestamps, hex and paths (`:116-143`), and
`breaker.should_quarantine_task` with a threshold of 3 is consulted at
`src/aet/cli/orchestrator.py:2850`. Three wasted attempts and a quarantine
replace 185 attempts. The classification is still wrong, and a class whose
remedy is "wait for the window" has no representation.

## OI-09 — Decide the direction for test-target selection

Two mechanisms select pytest targets and neither references the other.
`change_scope.targets` reads the hand-maintained `_PATH_TARGETS`
(`src/aet/change_scope.py:22-54`) over the whole branch diff against
`origin/main` (`:140-146`), and drives `make validate`.
`validation.select_targeted_tests` (`src/aet/validation.py:84-98`) derives
targets from a caller-supplied changed-file list by same-directory and
matching-name lookup, needs no table, and drives `aet-implement`
(`skills/aet-implement/SKILL.md:125`). Both fail safe to `["tests/"]`.
`validation.py` is itself one of the three unmapped modules in OI-08.

The scoped-validation review's recommendation was to hand-map the fifteen
unmapped modules. That predates the derived mechanism. Two of its candidate
mappings are unsupported: `src/aet/risk.py` and the root-level
`src/aet/harness_guard.py` have no importing tests.

The open question the review left — whether `change_scope` should offer a
working-tree-only mode for mid-branch iteration — is partly answered:
`select_targeted_tests` is that mode, reached through a different caller and not
wired into `make`. A `make test-affected` target stays deferred until the two
mechanisms are reconciled.

## OI-10 — Replay owb-13: integration branch derived from the PRD (R-17)

Commits `53ca943f` and `7362ee51`, discarded in the reset. R-17 is open upstream:
`docs/prds/open-work-board-prd.md:73` states it, its acceptance criterion at
`:131` is unchecked, and `:143` records that "R-17 is the delta, not the mode".
The discarded work is the only implementation.

Each commit conflicts in one file on replay — `src/aet/cli/aet_state.py` and
`docs/prds/open-work-board-prd.md`. The same work is also live at
`.worktrees/owb-13-prd-integration-branch`, checked out at `7362ee51`. Item 1 of
the divergence record carries the file inventory and the review commands.

## OI-17 — `test_stall_killed_and_classified_timeout` is flaky and unfiled

`tests/orchestrator/test_nightshift_rehearsal.py:325`. Measured at roughly
13–27% failure across two arms of a 30-run comparison in August 2026; last
touched by `6bc5367f` (osd-02), which addressed signal-exit classification
rather than the flake. It passed in the 2026-08-24 full-suite run. No bug
document exists for it.

## OI-18 — Scope `validate-skills.sh` to changed skills

The script takes 5 s over all 20 skills on every `make validate`, the only
structural gate above a second. Trigger-uniqueness and the repo-wide link check
are inherently global, so scoping saves part of it at best. Lowest priority in
this register.

## OI-19 — Delete the preserved reset branches

`backup/main-pre-sync` and `wip/main-sync-merge-20260824` hold the discarded
state and are unpushed. OI-03, OI-08, OI-11 and OI-15 are replayed, so OI-10 is
the last claim on them. `.worktrees/owb-13-prd-integration-branch`
outlives them and is removed with `git worktree remove`; removing it does not
change what `aet` executes, which is a non-editable install of
`~/.local/share/ae-toolkit/repo`.

## Closed 2026-08-24

Each entry names what the code now does and the test that holds it there.

**OI-01 — Name the ack syntax in the intake refusal.** The `sprint add` refusal
prints the ack line after the findings (`src/aet/cli/sprint.py:180-185`), so the
third option is visible at the point of refusal rather than only in two module
docstrings. `aet plan validate` prints it on the same terms
(`src/aet/cli/plan.py`). Held by
`tests/plan/test_intake_gate.py::TestAddIntakeGate::test_refusal_names_the_ack_syntax_that_resolves_it`.

**OI-02 — Ignore list still names the pre-rename queue paths.**
`AET_RETIRED_IGNORED_PATHS` (`src/aet/worktree.py:648-656`) declares the names
the toolkit once wrote and no longer does. `aet setup verify` reports both
directions of drift — an `AET_IGNORED_PATHS` entry the `.gitignore` lacks, and a
retired name it still carries — and `aet setup bootstrap` reports the retired
names it cannot prune. Reporting is restricted to names the toolkit itself
wrote, so a project's own entries are never flagged. This repository's
`.gitignore` gained `.agents/aet-queue`, `.agents/aet-queue.lease`,
`.agents/ledger.jsonl` and `.agents/ledger.jsonl.lock`, and dropped
`.agents/work-queue.json`, `.agents/work-queue.json.lock` and
`.agents/work-archive.json`; the stale `.agents/work-queue.json.lock` was
removed from disk.

The register's claim that `.agents/work-queue.lease` is stale was wrong.
`LEASE_FILENAME` is still `work-queue.lease` (`src/aet/queue.py:114`) and the
lease path is derived from it (`:125`), so the queue rename did not reach the
lease. `AET_IGNORED_PATHS` carries both names and `.agents/aet-queue.lease` is
the one nothing writes.

The write-declaration guard in
`tests/worktree/test_agents_path_registration.py` excludes retired names from
its universe: a path is declared retired precisely because no write-time
declaration should cover it.

**OI-04 — `tree_hash` fingerprints the main checkout, not the worktree.**
`_verdict_tree_root` (`src/aet/cli/gate.py:313-325`) prefers `AET_WORKTREE` and
falls back to `telemetry.resolve_repo_root()`, which the two coincide with
outside a task session. The freshness reader already hashed the worktree
(`orchestrator._qa_freshness_decision`), so writer and reader now fingerprint
the same tree. Held by
`tests/gate/test_gate_submit.py::TestGateSubmit::test_submit_stamps_the_worktree_not_the_main_checkout`.

**OI-12 — A removed config key aborts read-only commands with a traceback.**
`LegacyTaskBackendError` and `LegacyConfigError` are caught at the CLI boundary
(`src/aet/cli/main.py:566-571`) alongside `QueueOutsideRepositoryError` and
`LedgerCorruptionError`. `aet state audit` on a config carrying `task_backend`
exits 1 with the migration message and no traceback. Held by
`tests/cli/test_legacy_config_boundary.py`.

**OI-13 — Single-file plan validation does not state its weaker mode.**
`plan_validate.corpus_dir` (`src/aet/plan_validate.py:204-217`) is the single
answer to whether whole-set coverage was available, used by `validate` to build
the coverage union and by the CLI to name the mode. Success prints the count and
the mode — `✓ 1 plan passed validation — r-trace coverage judged against the
plan set in docs/plans/` — and failure prints a finding count, the affected
share of the plans checked, and the same mode.

**OI-14 — `plan validate` crashes on a directory argument.** `_expand_plan_args`
(`src/aet/cli/plan.py`) expands a directory to its `*.md` children and collapses
duplicates, so `aet plan validate docs/plans/` names the same set the glob does.

Adjacent, found while reproducing it: `_repo_root_from` ran git in the *parent*
of the path it was given, which is correct for a plan file and wrong for the
`Path.cwd()` the no-argument invocation passes. `aet plan validate` from the
repository root therefore resolved the repository's grandparent, found no
`docs/plans`, and printed `✓ no live plans to validate` — a silent no-op for the
documented default shape. The function now runs git in the nearest directory
either way. In this repository the default invocation reports 49 findings across
6 of 11 live plans, none of them previously visible. No gate invokes
`aet plan validate`, so nothing was passing on the strength of the no-op.

Both are held by `tests/plan/test_plan_validate_cli.py`.

**OI-16 — Pre-commit ruff lints the whole repo on every commit.** The `ruff`
hook carries neither `args: ["."]` nor `pass_filenames: false`
(`.pre-commit-config.yaml:19-22`), so it receives the staged filenames.

**OI-03 — Replay the test-isolation guard against the real remote.** `223814c4`
replayed. The autouse `_no_real_remote` fixture in `tests/conftest.py` makes
`git_refs_backend._has_remote` report no remote for this checkout only, so the
forced `+refs/aet/*:refs/aet/*` refspec cannot overwrite local refs from origin;
the scoping keeps the tests that exercise fetch and push against tmpdir fixture
remotes working. `tests/test_suite_isolation.py` pins both halves.

The fixture patches a module attribute, which does not cross a process
boundary, so `TestGateDispatcherRouting` — which spawns the real dispatcher
with a hand-built env — still reached the remote. Its child now runs in a
remote-less tmpdir repository. With both changes the full suite leaves
`.git/FETCH_HEAD` untouched; `tests/gate/test_gate_submit.py` runs in 7.3 s
against 84.7 s before.

**OI-08 — Replay the `_PATH_TARGETS` drift guard.** `2bce0d7e` cherry-picked
without conflict. `src/aet/liveness.py`, `src/aet/validation.py` and
`src/aet/validation_cache.py` — the three modules the guard flagged — map to
their own test files, so the unmapped set is exactly the `_UNMAPPED_MODULES`
allowlist and both drift assertions hold.

**OI-11 — `GitRefsBackend(repo_root=…)` pass-through.** The constructor accepts
an optional pre-resolved `repo_root` and `create_backend` passes the
`queue_root` it already derived; discovery stays the fallback for direct
construction. Construction is still not subprocess-free — config resolution
reaches `derive_config_slug`, which runs `git rev-parse --git-common-dir` — so
`test_backend_construction_does_not_rediscover_the_root` is scoped to the
`--show-toplevel` call it removes rather than to git as a whole.

The wider claim in `queue_repo_root`'s docstring is therefore narrower than it
reads: the read path resolves config with a git subprocess, and
`tests/orchestrator/test_read_path_no_git.py`, which the docstring cites, never
constructs a backend. Not tracked as an item; noted where the next reader of
that docstring will meet it.

**OI-15 — Restore three bug writeups and three learnings entries.** All six
restored: two of each rode along with the OI-03 and OI-11 replays, and the
third of each was checked out of `backup/main-pre-sync`. The learnings entries
slot in at their own 2026-08-19 timestamps, ahead of what upstream appended
from 2026-08-20 onward; the rest of the append-only file is unchanged.

## Not open

- **The subdirectory-invocation crash** (review F-1b). Upstream kept the factory
  half of `49977159`; `queue_repo_root` and `GitRefsBackend.__init__` both walk up
  in pure Python, so the crash is gone. What remains is OI-11, a cost.
- **The `abc123def456/` directory left in the repo root** (review, observed
  defect). `tests/state/test_desk_actions.py:210-261` on `main` delegates `-C`
  invocations to the real subprocess and answers `--show-toplevel` with a real
  path. No such directory exists.
- **Demoting `make format`** (review recommendation 4). ADR-026 states that the
  target "may remain, but it is not part of the required path"
  (`docs/adr/026-slim-markdown-quality-gates.md:22`). Keeping it is the recorded
  decision, so the recommendation has no ADR backing.
- **Plan re-render resetting a committed footer** (client 8). `render_plan`
  writes frontmatter, title and body with the stage footer stripped
  (`src/aet/plan_parser.py:383-409`, `:305`), so a rendered worktree plan carries
  no footer at all. Stage lives on the task record under R-4/R-19.
- **`state transition … merged` no longer archiving the plan** (client 8). The
  removal is deliberate and documented in code
  (`src/aet/cli/aet_state.py:561`, `:644`), the reference documentation
  no longer claims it, and `docs/plans/trp-05-retire-the-plan-archive.md` retires
  both archives.
- **Unbounded requeue of a rate-limited task** (client 8). Capped at three
  attempts by the per-task breaker; the misclassification survives as OI-07.
- **Markdown lint cost** (review F-3). The corpus is 394 tracked files and
  `make lint` takes 3 s, against 636 files and 13 s when the review was written.
- **Impact-scoped guidance in `aet-qa`** (review, "What Already Works").
  `skills/aet-qa/SKILL.md:39` now instructs the opposite — full suite
  unconditionally, no impact scoping and no reuse of an `aet-implement` result —
  changed deliberately by `validation-01-stage-based-split`. `aet-implement`
  still scopes.
