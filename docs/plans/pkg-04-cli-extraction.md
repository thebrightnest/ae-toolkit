---
id: pkg-04-cli-extraction
size: L
blocked_by:
  - pkg-03-lib-extraction
pipeline: standard
status: approved
security_review: skipped
security_review_reason: Pure relocation of existing CLI modules behind the same dispatcher; no new dependencies or behavior changes.
docs_sync: required
docs_sync_reason: docs/CONVENTIONS.md "Skill Binaries" section describes aet-work/bin locations and must be updated in the same change.
---

# Plan: Extract `aet-work/bin` into `aet/cli/` (A1c)

## Context

PRD: `docs/prds/aet-package-extraction-prd.md` (R-2, R-3).
Move the 16 `aet-work/bin` binaries into `src/aet/cli/` as importable modules
with `main()` functions. The multicall dispatcher (`aet-work/bin/aet`) keeps
exec-dispatching in this plan — only its targets move. `aet install`, the PATH
self-repair, and skills-lint's parser-tree validation keep working against the
new locations.

> **⚠️ ATOMIC OVERSIZED — requires explicit user approval.**
> 16 binaries + dispatcher + their tests exceed the file guardrail. Splitting
> per-binary creates 16 micro-PRs with identical mechanical content and forces
> the dispatcher's `SUBCOMMANDS` spec through 16 mixed old/new-path states.
> Rename-dominated diff; low per-file complexity.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Move each `aet-work/bin` binary to `src/aet/cli/<name>.py` with logic inside
   a `main(argv=None)`; keep `if __name__ == "__main__"` entry — L (traces: R-2)
2. Update the dispatcher `SUBCOMMANDS` targets to the package locations; the
   dispatcher file itself stays at `aet-work/bin/aet` until pkg-06 — M
   (traces: R-3)
3. Add console entry points in `pyproject.toml` for the dispatcher (`aet`) and
   verify `aet install` + `_ensure_path_link()` resolve the running script
   correctly from an editable install — M (traces: R-3)
4. Update skills-lint's parser-tree validation to the new module paths;
   `make validate` must still gate documented `aet` invocations (roadmap-p2
   reality-gap gate preserved) — M (traces: R-3)
5. Update `docs/CONVENTIONS.md` "Skill Binaries" section to describe the
   package layout; SKILL.md Prerequisites sections stay as-is (they reference
   `aet` subcommands, not paths) — S (traces: R-3)
6. Update affected tests (dispatcher, multicall, install, command-groups,
   cli-adapter tests) to the new locations — M (traces: R-3)
7. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] One cohesive relocation; not batchable with pkg-06 (different source
  skills, separate review domain).

## Rejected Alternatives

- **Per-binary migration plans** — rejected: 16 identical mechanical PRs;
  gate overhead dwarfs review value.
- **Straight to Typer in this plan** — rejected: PRD phases dependency adoption
  separately (pkg-11); mixing relocation with a parsing rewrite destroys
  behavior-preservation guarantees.

## Files to Modify

- `aet-work/bin/{aet-state,backlog,desk,gate,init-queue,next,orchestrator,plan,reconcile,report,review,sprint,status,sync,validate-workflows}` → `src/aet/cli/*.py`
- `aet-work/bin/aet` (SUBCOMMANDS targets only)
- `pyproject.toml` (entry points)
- `scripts/skills-lint` (parser-tree paths)
- `docs/CONVENTIONS.md` (Skill Binaries section)
- `tests/test_aet_multicall.py`, `tests/test_aet_dispatcher.py`,
  `tests/test_aet_install.py`, `tests/test_command_groups.py`,
  `tests/test_cli_adapter.py` and other affected test files

## Validation Steps

- [ ] `make validate` green, including skills-lint against the new parser tree
- [ ] `tests/test_aet_multicall.py` and `tests/test_aet_dispatcher.py` (named,
  existing) cover the moved dispatcher spec; `tests/test_aet_install.py`
  covers `aet install` from the editable install
- [ ] Every existing subcommand (`aet status`, `aet desk`, `aet gate`, ...)
  runs identically; spot-check `aet state --help` output unchanged
- [ ] `~/.local/bin/aet` symlink target resolves after `aet install`; isolation
  fixtures (`AET_BIN_DIR` per-test tmp dir) still pass
  (`tests/test_telemetry_isolation.py` stays green — see learning 2026-07-15)
- [ ] R-trace coverage: R-2 by task 1; R-3 by tasks 2–6; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

`git revert` the merge; dispatcher targets flip back to `aet-work/bin` paths in
the same revert. No state or user-facing behavior changes to roll back.

---

*Stage: plan-approved*
*Next step: run `aet-work`*
