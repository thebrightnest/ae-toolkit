# Open items register: reset replay, validation scoping, client-project findings

*Compiled 2026-08-24 — every item verified against `main` at `7c94b248` (v1.10.0).
All nineteen items closed the same day; the closures are recorded under
"Closed".*

Three sources feed this register: the divergence record at
`docs/audits/2026-08-24-local-main-reset-divergence.md`, which lists work
discarded when local `main` was reset; `content/2026-08-19-scoped-validation-review.md`;
and `content/2026-08-24-aet-findings-from-a-client-project.md`. Items that were
already resolved when those documents were written are listed under "Not open";
items closed against this register are listed under "Closed 2026-08-24". Both
carry the evidence that closed them.

Ordering was by leverage. IDs are stable and are not reused.

## Summary

No open items. All nineteen are closed; each closure names what the code now
does and the test that holds it there.

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

**OI-10 — Replay owb-13: integration branch derived from the PRD (R-17).**
`53ca943f` and `7362ee51` replayed. `derive_integration_branch_from_prd` and
`resolve_integration_branch_for_task` (`src/aet/branch_ref.py`) resolve a
task's integration branch from its PRD in `single-pr` mode, with explicit CLI
and env overrides still winning and `pr-per-task` unchanged — ADR-045's
Scenario A stays the degenerate case. `aet state` audit, heal, validate, reset,
transition and record-merge resolve per task; `ship verify` checks the derived
target branch; `plan_parser.prd_path_from_text` and `prd_path_for_plan` are the
shared extraction that `plan_validate` now calls through to. The R-17
acceptance criterion in `docs/prds/open-work-board-prd.md` is checked.

Three resolutions the replay had to make, none of them in the original commits:

`_derive_all_states` (`src/aet/cli/aet_state.py`) was the substantive conflict.
Upstream had removed its `history` parameter under R-8 — the settled log is not
an authority, and a blocker absent from the board is terminal — while owb-13
layered per-task branch resolution onto the older history-seeded version.
Upstream's semantics are kept and the per-task resolution layered on top of
them: `_task_target` falls back to the static branch when the caller supplies
no repository context, which is what leaves the many direct callers unchanged.

`tests/cli/test_ship_verify.py` and `tests/state/test_aet_state.py` seeded
`.agents/work-queue.json` and read it back with `json.load`. That store no
longer exists; both now seed and read through the git-refs backend.

The three divergence summaries in `docs/prds/open-work-board-prd.md` are
additive and all three are kept, each with its own Deferred section.

**OI-19 — Delete the preserved reset branches.** `backup/main-pre-sync`
(`e011f9cf`) and `wip/main-sync-merge-20260824` (`4750bac9`) deleted, along with
`owb-13-prd-integration-branch` (`7362ee51`) and its worktree. Every claim on
them was replayed first; what they carried that `main` does not is upstream's
own removals — the 250 files under `docs/plans/archive/` retired by trp-05,
`src/aet/backends/json_backend.py` removed by owb-07, and the two test files
covering those. All three SHAs are named in the divergence record and held by
the reflog for its expiry window.

The `dia-03-record-the-principle` and `owb-05-board-is-open-work` worktrees are
unrelated to the reset and were left in place.

**OI-05 — Settled siblings drop out of r-trace coverage.** Coverage is read
from the task record. `plan_validate.record_coverage` maps each record's
`spec.tasks` traces onto the PRD its `spec.body` references;
`coverage_from_backend` sources the records from the live board plus the sealed
tombstones, which are written in every posture and pushed, unlike the history
JSONL — 9 history records against 29 tombstones in this repository.
`plan_validate` receives the result as `extra_coverage` and gains no backend
dependency; `aet plan validate` and `sprint add` supply it, sharing one repo
root because the PRD paths are dict keys.

ADR-061 places `plan validate` in phase 1 and has it glob `docs/plans/*.md`.
That holds for the structural checks, which ask whether a file parses. It does
not hold for coverage, which asks what the whole decomposition has delivered
over time, and the record is the only place that answer lives. The carve-out is
narrowed to the checks it fits.

Records carrying no spec are named rather than skipped (ADR-059), and a store
that cannot be read degrades to empty coverage with the reason printed. In this
repository the corpus run drops from 49 findings across 6 plans to 26 across 5,
and names the one pre-R-19 record whose coverage cannot be counted.

Three premises of the item as written were stale. `docs/plans/archive/` no
longer exists — trp-05 retired it — so nothing falls outside the glob. Nothing
writes a terminal `*Stage:*` footer any more, so `is_settled_plan` returns False
for every file on disk and the filter the item blamed is a no-op; the real
settled signal is `refs/aet/sealed/<id>`. And staging archived siblings back in
would not have failed for the reason given: the files are gitignored and mostly
absent, not filtered.

**OI-09 — Decide the direction for test-target selection.** Derivation is
authoritative and the table is deleted. `aet.test_deps` reads which test files
reference which source files — imports, plus the quoted-path idiom that feeds
`SourceFileLoader` in 68 of 161 test files — and follows those references
transitively, so a test driving an entry point counts for what the entry point
reaches. `change_scope.targets` selects from it and
`validation.select_targeted_tests` delegates, so ADR-049's single authority has
a single implementation.

The measurement that settled the direction: the filename rule named a
non-existent test file for 69 of the 82 modules under `src/aet` and fell back
to the full suite for none, because the same-directory floor was appended
without an existence check and the phantom kept the list non-empty. `pytest`
exits 4 on such a path. Every test for that rule built a synthetic repo in which
the matching file existed.

Import derivation is also more accurate than the table it replaces: no phantom
targets, every source file reached by some test, 74 of 83 files selecting under
half the suite, median 32 of 162, built in 0.4 s. `src/aet/liveness.py` was
mapped to one test file while 46 tests reach it. Hub modules now select most of
the suite — the honest answer for a hub — and anything at or above half is
reported as `tests/`.

Two things derivation cannot see, handled rather than lost. Coverage crossing a
shell boundary is declared in `test_deps.BOUNDARY_EDGES`, whose one entry is
ADR-049 §2's `src/aet/cli/setup.py` → installer edge. And a test naming paths
as data is textually indistinguishable from one exercising them, so the
acknowledged-uncovered list lives in
`tests/fixtures/uncovered-source-files.txt`: in a Python test module it would
have made itself true.

The OI-08 drift guard is replaced in kind. `TestCoverageDerivationDrift` fails
when a source file no test reaches is unacknowledged, and when an acknowledged
file gains coverage. The `make test-affected` target OI-09 left deferred is now
trivial — `changed_paths` and `targets` are already separate — but nothing has
asked for it.

**OI-06 — `run-one` skips the intake validation `sprint add` enforces.**
`run-one` runs the same suite over the same corpus with the same
record-sourced coverage and the same ack escape hatch, and refuses on an
unacked finding (`src/aet/cli/orchestrator.py:_intake_findings`).
`--skip-intake` runs anyway and records the bypassed check ids as
`intake_skipped` on the task record; an empty bypass leaves the field off, so
its presence means exactly one thing. A batch child is not re-judged: its task
passed intake on the way in, and re-judging mid-flight would fail a run for a
PRD edited after promotion. Held by
`tests/orchestrator/test_run_one_intake_gate.py`.

The item's premise was half right. There was no queue entry to be
indistinguishable from a validated one — `_find_queued_task` only ever finds
tasks already on the board, so a refused plan ran as a synthetic task with no
entry at all. The defect was the execution, not the record.

**OI-07 — No failure class for "retry cannot succeed yet".** `throttled` is the
sixth class, added by ADR-065 amending ADR-030's fixed menu. Its patterns are
qualified the way `_ENVIRONMENT_PATTERNS` documents — a bare `rate limit`
matches a pytest line for `test_rate_limit_handling` — and it is checked ahead
of `environment` because a 429 body often carries an auth word too. A throttle
is not breaker evidence, the task is requeued, and the shift stops spawning:
the limited resource is shared, so the next task meets the same wall. This
overrides `--on-failure continue`, which would otherwise burn the queue on one
limit. No triage session is spent on an answer already known.

**OI-17 — `test_stall_killed_and_classified_timeout` is flaky and unfiled.**
Filed at `docs/bugs/20260824-nightshift-stall-timeout-flake.md`, and not
reproduced: 0 failures in 25 isolated runs, 0 in 12 under four-way parallel
load, 0 across 8 full-suite runs. `6bc5367f` (osd-02) made a signal exit
classify as timeout — the assertion's own subject — and is the likeliest reason
the August measurement no longer holds. The writeup names three candidate
mechanisms with anchors; the first is that every branch tests `exit_code < 0`,
and a shell in the path turns `-9` into `137`. The assertions now carry the
whole signature list, which the diagnosis needs and the last entry did not give.

**OI-18 — Scope `validate-skills.sh` to changed skills.** Rejected as written,
on measurement. The script takes 2.17 s, not 5 s, and divides as: structure
loop 0.79 s, trigger uniqueness 0.77 s, next-step consistency 0.25 s, internal
links 0.29 s. Scoping cannot touch trigger uniqueness or the link check — both
are inherently global — so it addresses at most half the cost while making a
structural gate depend on the diff.

The cost is process spawning: roughly thirteen `grep`/`sed`/`tr` invocations per
skill across the two loops, plus two per trigger phrase. The trigger loop is now
one python pass, 0.77 s to 0.27 s, most of the remainder being interpreter
startup through a pyenv shim. The structure loop is left at 0.79 s deliberately:
collapsing it means rewriting seventy lines of checks, which is not worth 0.7 s
against a 170 s suite.

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
