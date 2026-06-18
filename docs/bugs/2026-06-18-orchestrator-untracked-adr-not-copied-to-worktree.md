# Bug Report: orchestrator does not copy untracked `docs/adr/` files into the worktree

## Metadata

- **Reported:** 2026-06-18T16:53:21Z
- **Severity:** medium
- **Status:** fixed

## Symptoms

When a plan references an ADR that was authored in the same session and is still
**untracked**, `aet-work run-one`/`run` copies the untracked plan and PRD into the
task worktree but **not** the ADR. The ADR therefore never lands on the
implementation branch, so a PR can ship code whose governing ADR is missing.

Observed while shipping `fods-01`: `docs/prds/forward-only-...-prd.md` and
`docs/plans/fods-01-record-merge.md` (both untracked) reached the branch, but
`docs/adr/011-forward-only-deterministic-work-state.md` (also untracked) did not —
it had to be added to the branch manually before shipping.

## Reproduction Steps

1. Start from a clean repo. Create three **untracked** files:
   - `docs/plans/x-demo.md`
   - `docs/prds/x-demo-prd.md`
   - `docs/adr/099-x-demo.md`
2. Run `aet-work run-one docs/plans/x-demo.md`.
3. Inspect the worktree `.worktrees/x-demo/`:
   - `docs/plans/x-demo.md` — **present**
   - `docs/prds/x-demo-prd.md` — **present**
   - `docs/adr/099-x-demo.md` — **absent**

## Root Cause

`aet-work/lib/worktree.py:94` `copy_untracked_files()`:

```python
result = subprocess.run(
    ["git", "-C", repo_root, "ls-files", "--others", "--exclude-standard",
     "docs/plans/", "docs/prds/"],
    ...
)
```

The pathspec allowlist contains only `docs/plans/` and `docs/prds/`. `docs/adr/`
(and `docs/audits/`, `docs/retros/`, `docs/product-briefs/`) are omitted, so
untracked files there are never copied. The docstring ("Copy untracked plan/PRD
files") confirms the scope is intentional — but the scope misses ADRs that a plan
explicitly depends on.

- **Wrong assumption:** plans and PRDs are the only untracked artifacts an
  implementation needs.
- **Why not caught:** no requirement/test that an ADR referenced by a plan reaches
  the worktree/branch.

## Fix Summary (proposed — NOT applied)

- **Files to modify:** `aet-work/lib/worktree.py` (1 file, ~2–5 lines).
- **Key change:** add `docs/adr/` (and likely `docs/audits/`, `docs/retros/`) to the
  `ls-files` pathspec, or broaden to `docs/` with sensible excludes. Update the
  docstring accordingly.
- **Risk:** low (copies a few more untracked docs into the worktree; harmless).
- **Diff budget:** within.

## Regression Test

None added (bug filed, not fixed). Proposed: create untracked plan + PRD + ADR, run
the copy, assert all three exist in the worktree.

## Validation

- [ ] Reproduction steps no longer trigger the bug
- [ ] Existing test suite passes with no new failures
- [ ] No regressions observed in related functionality

## Lessons Learned

- **Pattern:** an allowlist that silently drops a relevant input category.
- **Prevention:** when copying "context" untracked files, cover all `docs/`
  artifact types a plan can reference, not just plans/PRDs.
- **Workaround:** commit the ADR before running the pipeline, or add it to the
  branch post-hoc.
