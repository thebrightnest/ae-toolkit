---
id: retire-vestigial-skills
status: scope-validated
---

# PRD: Retire aet-work, aet-extract-stack, and aet-upgrade

## Overview

Three of the 21 distributed skills no longer earn their place in the toolkit.

- **`aet-work`** began as the home of the queue code (the `aet-work/bin/` family:
  orchestrator, `next`, `sync`, `sprint`, `status`, …). ADR-038 moved that code to
  `src/aet/`, and the packaged workflow now lives at `src/aet/workflows/software.json`.
  The skill that was left behind is a 320-line manual of `aet` subcommands that contains
  almost no judgment. Under ADR-039 (deterministic work lives in the CLI, judgment lives
  in skills), a skill with no judgment should not exist. It also overlaps with
  `aet-drive` on triggers ("night shift", "AFK mode", "run all tasks" against "drive
  sprint", "run sprint"), still describes "sequential task execution" (`aet run` is
  pipelined), describes a tamper-evident hash on the JSON backend that was removed in
  1.10, and contradicts itself on the source of truth ("Plans are the source of truth"
  against ADR-061 in its own body).
- **`aet-extract-stack`** copies a working project's CI and tooling into a scaffold. It
  is a one-off job across the user's portfolio, not a step in the plan → implement →
  ship pipeline. Nothing routes to it, and session history shows no use beyond
  maintenance edits.
- **`aet-upgrade`** plans dependency upgrades, but its output is not a
  `docs/plans/active/<id>.md` with the frontmatter that intake requires. An upgrade plan
  therefore has no proper path to `aet sprint add`. Nothing routes to it either:
  `aet-prime` classifies "upgrade framework" as critical work without naming the skill.
  The parts worth keeping are the risk-classification table, the breaking-change
  template, and the rule that upgrades are critical-class work.

This PRD retires all three skills. It keeps the parts that are still useful by moving
them to where their readers are, and it closes an install gap: removing a skill
currently leaves a dangling symlink in every agent skills directory, because
`aet setup skills` only creates and repoints links and never removes one.

Precedent: ADR-017 (removal of `aet-discover`). The same rules apply here: historical
records (CHANGELOG, past PRDs, archived plans, release notes, and ADR prose that cites
the skills) stay unchanged.

## Intake Triage

Enhancement, not a defect. No existing behaviour misbehaves in a reproducible way; the
skills are redundant or unused. Classified `normal`.

## Goals

- **G1**: The distributed skill set contains no skill whose body is only a manual for
  CLI commands. Queue execution is the CLI plus one skill, `aet-drive`.
- **G2**: Every hand-off that currently says "run aet-work" points to a step that exists
  (`aet sprint add <plan>` then `/aet-drive`, or `aet run-one <id>` for a single task).
- **G3**: Upgrade requests go through the normal planning pipeline and produce
  plan files that can be queued.
- **G4**: Removing a skill from the repo does not leave dangling links in installed agent
  skills directories.

## Non-Goals

- Renaming "aet-work" where it is an internal name for the queue subsystem: module
  docstrings in `src/aet/`, the legacy config path `.agents/aet-work.json`, the log file
  `scripts/.aet-work-orchestrator.log`, and test names such as
  `tests/workflow/test_aet_work_*.py`.
- Rewriting history: `CHANGELOG.md`, `docs/releases/`, `docs/prds/*` other than this one,
  `docs/plans/archive/`, ADR-020, and ADR-039's skill inventory stay as written.
- Merging `.agents/commands/aet-work.md` (the in-repo operator guide) into
  `.agents/commands/aet-drive.md`. Only its claim that "the aet-work skill owns the
  queue/orchestrator" is corrected.
- Moving `aet-extract-stack` to another repository. It can be recovered from git history.
- Changing `aet run`, `aet sprint add`, or any other queue CLI behaviour.

## Requirements

- **R-1**: `skills/aet-work/` no longer exists, and `README.md` and `PRODUCT.md` no
  longer list `aet-work` as a skill.
- **R-2**: `aet-drive` triggers on the queue intents that `aet-work` owned ("what's
  next", "what's unblocked", "run tasks", "run the queue", "night shift", "AFK mode",
  "keep working").
- **R-3**: `aet-drive` has a curation step that runs before `aet run`. When the
  **Board** has no ready tasks and the **Plan Backlog** (plan files in
  `docs/plans/active/` whose `id` is not on the board in `aet status`) is not empty, the
  agent lists the backlog (id, title, `blocked_by`) and asks the user which plans to
  admit. It runs `aet sprint add` only on the user's explicit choice, never as a bulk
  add (board admission has one path, ADR-066).
- **R-4**: `aet-drive` handles the failures the engine leaves for a person, without
  repeating the engine's **Triage** (ADR-030). For each task left in `failed` or
  `quarantined` after a run settles, the agent reports the recorded **Failure Class**
  and stage from `aet status` along with the tail of `.agents/runs/<run-id>/output.log`.
  It never assigns its own failure class. It moves a task forward
  (`failed → ready`, `quarantined → ready`) only after the user confirms the cause is
  fixed, and abandons a task only on the user's word. Every move goes through
  `aet state transition`.
- **R-5**: Every skill that names `aet-work` as a next step (`aet-plan`,
  `aet-validate-scope`, `aet-pipeline-plan`, `aet-implement`, `aet-setup`) names
  `aet sprint add` + `/aet-drive` (or `aet run-one <id>`) instead. No file under
  `skills/` contains the string `aet-work` once this work is done.
- **R-6**: The operator references from `skills/aet-work/references/` (`queue-commands`,
  `github-backend`, `parallel-execution`, `context-isolation`, `reconcile`,
  `telemetry-log-schema`, `upgrading-existing-project`) live under
  `docs/reference/queue/`, and every link to them resolves.
- **R-7**: The plan-author part of `frontmatter-contract.md` (required and optional keys
  and what they mean) is merged into `skills/aet-plan/references/work-queue-format.md`.
  The parser-internals part (PyYAML shim, input-difference table, failure mode) moves to
  `docs/reference/queue/frontmatter-parsing.md`.
- **R-8**: `skills/aet-work/references/migration-aet-state.md` is deleted (a one-time
  migration from the `.agents/work-queue.json` era that has already run).
- **R-9**: The rules in `.agents/doc-rules.yaml` that target files under
  `skills/aet-work/` are retargeted to the files' new locations. The invariants they
  enforce (the intake durability rule, and no "direct JSON update") still hold. The
  intake durability rule moves to `skills/aet-drive/SKILL.md`, because that is where
  curation now lives.
- **R-10**: `docs/PIPELINE.md`, `docs/CONVENTIONS.md`, `docs/use-cases.md`,
  `docs/telemetry-guide.md`, `CONTEXT.md`, `docs/upgrades/README.md`, and
  `.agents/commands/aet-work.md` no longer describe `aet-work` as a skill. The
  orchestrator is referred to as `aet run`, and `aet-work sync` becomes `aet queue sync`.
- **R-11**: `skills/aet-extract-stack/` no longer exists, and `README.md` and
  `PRODUCT.md` no longer list it.
- **R-12**: `skills/aet-plan/references/upgrade-planning.md` contains the
  breaking-change procedure (find the guide, list breaking changes, search the code for
  each, rate the risk), the risk-classification table, and the breaking-change template.
  `aet-plan`'s `plan` command routes to it when the request is a dependency or framework
  upgrade, and requires the resulting plan to declare `work_class: critical`.
- **R-13**: `skills/aet-upgrade/` no longer exists, and `README.md`, `PRODUCT.md`, and the
  upgrade scenario in `docs/use-cases.md` route upgrades to `aet-plan` instead.
- **R-14**: `aet-prime`'s routing for critical upgrade requests names `aet-plan` and its
  upgrade-planning reference.
- **R-15**: ADR-080 records the retirement of all three skills, the new home for queue
  curation, and the upgrade fold-in. Its `relates` frontmatter cites ADR-017, 038, 039,
  and 066.
- **R-16**: `aet setup skills` removes symlinks in each target agent skills directory
  that point into a toolkit `skills/` root and whose target no longer exists. It never
  touches a link that points elsewhere, a link whose target exists, or a real directory.
- **R-17**: `aet setup verify` reports each dangling toolkit skill link by name, without
  changing anything, and suggests `aet setup skills`.
- **R-18**: The panel (`src/aet/panel/index.html`) no longer tells the user to "Run a plan
  with aet-work". It names `aet run`.

## User Stories

- As an operator, I say "what's next" or "run the queue" and land in `aet-drive`, the one
  skill that runs the queue, instead of a CLI manual (satisfies: R-1, R-2).
- As an operator with approved plans and an empty board, I am offered the candidates and
  admit the ones I choose, without remembering the `aet sprint add` syntax
  (satisfies: R-3).
- As an operator coming back to a night run, the agent shows me what the engine's
  triage left in `failed` or `quarantined`, with its recorded failure class and log tail,
  and moves each task forward only when I say so (satisfies: R-4).
- As a planner finishing `aet-plan` or `aet-validate-scope`, the next step I am told to
  take actually exists (satisfies: R-5).
- As a maintainer, the queue reference docs are where people read docs, and the lint
  rules still protect the same invariants (satisfies: R-6, R-7, R-8, R-9, R-10).
- As an operator upgrading a framework, I ask `aet-plan` and get a risk-mapped,
  critical-class plan file that `aet sprint add` accepts (satisfies: R-12, R-13, R-14).
- As a maintainer, I see the toolkit's skill list match its pipeline, with the reasons
  recorded (satisfies: R-11, R-15).
- As a user who installed with the one-line installer, a toolkit update that removes a
  skill does not leave dead entries in my agent's skill list (satisfies: R-16, R-17).
- As a panel user with no telemetry yet, the empty state names a command that exists
  (satisfies: R-18).

## Acceptance Criteria

- [ ] `ls skills/` shows no `aet-work`, `aet-extract-stack`, or `aet-upgrade`, and
  `make validate` passes (satisfies: R-1, R-11, R-13).
- [ ] `grep -rn "aet-work" skills/` returns nothing (satisfies: R-5).
- [ ] `aet-drive`'s description lists the queue triggers from R-2 (satisfies: R-2).
- [ ] `aet-drive/SKILL.md` contains a curation section that requires an explicit user
  choice before `aet sprint add`, and a residual-failure section that reads the
  recorded Failure Class, invents none, and moves a task forward only on user
  confirmation (satisfies: R-3, R-4).
- [ ] Every relative markdown link to the moved references resolves
  (`scripts/validate-skills.sh` and `aet docs lint` pass) (satisfies: R-6, R-7).
- [ ] `aet docs lint` passes with the retargeted rules, and none of its rules target a
  path under a removed skill (satisfies: R-9).
- [ ] `docs/reference/queue/migration-aet-state.md` does not exist (satisfies: R-8).
- [ ] `grep -n "aet-work" docs/PIPELINE.md docs/CONVENTIONS.md docs/use-cases.md
  docs/telemetry-guide.md CONTEXT.md docs/upgrades/README.md` returns nothing, apart
  from the legacy config path `.agents/aet-work.json` (satisfies: R-10).
- [ ] `aet-plan/references/upgrade-planning.md` exists, and `aet-plan/SKILL.md` links to
  it from the `plan` command with the `work_class: critical` rule (satisfies: R-12).
- [ ] `docs/use-cases.md`'s upgrade scenario routes to `aet-plan`, and
  `aet-prime/SKILL.md` names the upgrade-planning reference (satisfies: R-13, R-14).
- [ ] `docs/adr/080-*.md` exists with `subject` and `relates: [17, 38, 39, 66]`, and
  `aet docs lint` (`adr_corpus_integrity`, `unique_live_subject`) passes (satisfies: R-15).
- [ ] With a fixture skills directory that holds one dangling toolkit link, one valid
  toolkit link, one dangling foreign link, and one real directory,
  `aet setup skills` removes only the dangling toolkit link (satisfies: R-16).
- [ ] With the same fixture, `aet setup verify` names the dangling toolkit link, exits
  without changing anything, and points to `aet setup skills` (satisfies: R-17).
- [ ] The panel's empty-state text names `aet run` (satisfies: R-18).

## Technical Notes

- **"Points into a toolkit `skills/` root"** (R-16) means the link's raw target, read
  with `os.readlink` and resolved against the link's directory, has a parent directory
  named `skills` whose parent is a toolkit checkout (contains `src/aet/` or
  `pyproject.toml` naming `ae-toolkit`), or is the current `_repo_root() / "skills"`.
  The managed install (`~/.local/share/ae-toolkit/repo/skills/*`) and a development
  clone both match. A link to `~/other/skills/foo` does not. This check runs on the link
  text, because the target may no longer exist.
- `_report_skill_link_drift` in `src/aet/cli/setup.py` iterates only over the names of
  skills that exist. The dangling-link report (R-17) needs a second pass over the
  directory's entries.
- **Sequencing with the active queue.** `RDR-01` removes `--dry-run` from
  `src/aet/cli/setup.py`, and `UPD-01` edits `setup_verify()`. RVS-03 is blocked by both,
  so the pruning code is written against the post-`--dry-run` shape and the verify output
  that UPD-01 adds. `UPD-02`'s `aet update` re-links via `aet setup skills`, so it gets
  pruning for free once RVS-03 lands. `MWP-01` edits `skills/aet-setup/SKILL.md` in a
  different section than RVS-01. The overlap is small, and the merge-train conflict
  runbook covers it.
- `skills/aet-work/references/upgrading-existing-project.md` mentions `--dry-run`.
  RVS-01 moves it as is. RDR-01's docs sweep (or a follow-up) owns flag removal.
- `aet-plan/SKILL.md` is 303 lines. The upgrade routing (R-12) adds a short paragraph and
  a link. The procedure lives in the reference, so the 400-line limit is not at risk.
  `aet-drive/SKILL.md` is 215 lines. The curation and triage sections (R-3, R-4) add
  about 50.

## Architecture Decisions

- **Curation lives in `aet-drive`**, not `aet-prime`. One skill owns the queue journey
  from admission to epic finalization. `aet-prime` keeps routing intent and does not
  manage the board.
- **Reference docs are split by reader.** Operator docs go under `docs/`, and plan-author
  facts go into `aet-plan`. A skill's `references/` exists for that skill's agent. A
  user-facing reference library inside a skill that is otherwise retired is the vestige
  being removed.
- **Pruning is narrow** (R-16). It removes only links that are provably toolkit links and
  provably dead. Absence is not a fact (ADR-059), but a dangling link whose target path
  is gone *is* an observed fact about the filesystem, and removing it is reversible
  by running `aet setup skills` again from a checkout that still has the skill.

## Plan Breakdown

| ID     | Title                                                  | Size | Blocked by     | Traces              |
| ------ | ------------------------------------------------------ | ---- | -------------- | ------------------- |
| RVS-01 | Retire aet-work into aet-drive and docs, add ADR-080   | M    | —              | R-1…R-10, R-15      |
| RVS-02 | Fold aet-upgrade into aet-plan; remove aet-extract-stack | S  | RVS-01         | R-11…R-14           |
| RVS-03 | Prune dangling skill links; fix panel empty state      | S    | RDR-01, UPD-01 | R-16…R-18           |

RVS-02 is blocked by RVS-01 because both edit `README.md`, `PRODUCT.md`,
`docs/use-cases.md`, and `.agents/doc-rules.yaml`, and because ADR-080 (written in
RVS-01) is the record that RVS-02 implements. RVS-03 touches only `src/aet/` and its
tests, so it runs independently of the skill-content plans.

## Scope Validation Findings (2026-10-16)

- **Triage already exists (ADR-030).** The engine starts a Triage session on failure
  (`--on-failure=triage`, the default) with a fixed, code-owned Failure Class menu
  (`environment`, `flaky`, `design`, `timeout`, `canceled`), and the Circuit Breaker
  re-queues or quarantines tasks. The first draft of R-4 had `aet-drive` classify
  failures with its own taxonomy. That would duplicate a sanctioned judgment path and
  contradict "the breaker's counting never depends on an LLM inferring it". R-4 now
  covers only what is left for a person and reads the recorded class.
- **`aet status` does not report plan drift**, although `aet-work/SKILL.md` and
  `queue-commands.md` say it does. The Plan Backlog has no CLI listing, so the curation
  step (R-3) works it out from the plan files and the board. RVS-01 removes the stale
  claim from the moved reference.
- **Transitions verified:** `failed → ready` and `quarantined → ready` are legal in
  `LEGAL_TRANSITIONS` (`src/aet/queue.py`).
- **Terminology:** "Board", "Plan Backlog", "Triage", "Failure Class", and "Quarantined"
  are used as CONTEXT.md defines them. No glossary change is needed.

## Open Questions

None blocking. Decided in clarify-goal (2026-10-16): curation goes to `aet-drive`, the
references are split by reader, `aet-upgrade` is folded into `aet-plan`, and only
user-facing code strings change.

## Risks

- **Muscle memory.** Users who type `/aet-work` get nothing. Mitigation: `aet-drive`
  takes over the triggers (R-2), and the CHANGELOG entry at release names the
  replacement.
- **Other installs keep stale copies.** Installs made with `npx skills add --all`
  copy directories, not links, so R-16 does not reach them. The release notes tell
  those users to delete the three directories.
- **Doc-rule invariants lost in the move.** Mitigation: R-9 retargets each rule rather
  than deleting it, and the acceptance criteria check that `aet docs lint` passes.

## Divergence Summary

*Recorded: 2026-10-17 — Branch: RVS-01*

RVS-01 (retire `aet-work`, ADR-080) was built as planned. Tasks 1–7 match the plan;
the entries below are small additions found in the diff.

### Changed from plan

- None.

### Added (unplanned)

- `docs/adr/README.md`: added the ADR-080 row to the ADR index, as every new ADR needs.
- `skills/aet-setup/examples/worktree-ship-hygiene.md.example`: changed "`aet-work` runs
  tasks in isolated git worktrees" to "The `aet run` orchestrator ...". The plan's
  `aet-work` grep over `skills/` found this file, but it was not in Files to Modify.

### Deferred

- R-11…R-14 (retire `aet-extract-stack`, fold `aet-upgrade` into `aet-plan`) remain with
  RVS-02, and R-16…R-18 with RVS-03, as planned.

### RVS-02

*Recorded: 2026-10-17 — Branch: RVS-02*

RVS-02 (fold `aet-upgrade` into `aet-plan`, remove `aet-extract-stack`) was built as
planned. Tasks 1–6 match the plan; R-11…R-14 are delivered.

#### Changed from plan

- `skills/aet-prime/SKILL.md`: the upgrade route is its own `Upgrade:` bullet after the
  `Critical:` example rather than an inline addition to it; same routing, clearer read.

#### Added (unplanned)

- `skills/aet-plan/references/upgrade-planning.md`: also carries the rule that a
  Medium-risk change with a non-trivial fix is treated as High, and that planning never
  runs the bump itself, from the deleted `risk-classification.md` and `aet-upgrade`
  guardrails.
- `docs/use-cases.md`: the upgrade scenario's plan paths now point to
  `docs/plans/active/`, matching the current plan layout.

#### Deferred

- R-16…R-18 remain with RVS-03, as planned.

*Stage: synced*
*Next step: run `aet-ship` for RVS-02; RVS-03 follows through `/aet-drive`*

### RVS-03

*Recorded: 2026-10-17 — Branch: RVS-03*

RVS-03 (prune dangling skill links, panel empty state) was built as planned. Tasks 1–6
match the plan, including the locked-in toolkit-link predicate.

#### Changed from plan

- Task 3 (verify report): the dangling-link pass skips names the toolkit still ships.
  Those links are repointed rather than removed, and the existing drift pass already
  reports them, so listing them again would report the same link twice.

#### Added (unplanned)

- `src/aet/test_deps.py`: when matching quoted file literals, `_resolve` now skips the
  `__init__.py` basename. The new `"__init__.py"` literal in `setup.py` (the toolkit
  marker check) had wired `setup.py` to every package `__init__`, which pulled unrelated
  tests into change-scoped runs and failed `test_change_scope`. Covered in
  `tests/test_test_deps.py`, with a learning recorded in `.agents/learnings.jsonl`.

#### Deferred

- None.

*Stage: synced*
*Next step: run `aet-ship` for RVS-03*
