# Bug: `aet ship` resolves a behind-main branch's PR base to the branch itself

- **ID:** 20260723-211250-aet-ship-pr-base-misdetects-behind-main
- **Reported:** 2026-07-23
- **Component:** `src/aet/cli/ship.py` — `_determine_pr_base()`
- **Severity:** High — blocks PR creation for nearly every queued branch
- **Status:** Fixed — `HEAD -> <branch>` excluded from stacked-parent search in `src/aet/cli/ship.py`, regression tests added in `tests/test_ship_open.py`

## Summary

`aet ship open` (and bare `aet ship`) fails at PR creation with:

```
head branch "<branch>" is the same as base branch "<branch>", cannot create a pull request
```

for any independent feature branch whose fork point is behind `origin/main` —
i.e. the normal state of a queued worktree once other plans have merged ahead of
it. The PR base is computed as the branch's **own** name instead of `origin/main`.

## Environment

- Repo: `thebrightnest/ae-toolkit` (aiskills), branch layout: ~18 `.worktrees/*`
- `aet` version `1.4.1.dev55+gfd9dad6e3` (editable, main)
- Surfaced while shipping `psr-03-size-calibration-report` (PR #187). Worked
  around with `--base origin/main`; psr-03 is now merged.

## Reproduction

Reliable, deterministic. Any independent branch with
`merge-base(HEAD, origin/main) != origin/main` triggers it.

Live repro on a still-behind-main worktree (main's code, no side effects):

```
$ cd .worktrees/psr-01-sizing-model-recalibration
$ python -c "from aet.cli.ship import _determine_pr_base; print(_determine_pr_base())"
psr-01-sizing-model-recalibration      # expected: origin/main
```

Underlying git state that triggers it:

```
merge-base HEAD origin/main = 0508260a…   # fork point (older)
rev-parse   origin/main     = fd9dad6e…   # advanced 4+ commits after the fork
# => merge_base != origin_main, so the code enters the "stacked" branch
git log --oneline --decorate --ancestry-path <merge_base>..HEAD
22400d8c (HEAD -> psr-03-size-calibration-report, origin/psr-03-size-calibration-report) …
```

End to end: `aet ship open <plan>` → gate passes, branch pushes, then
`gh pr create` aborts with "head branch is the same as base branch".

## Root cause

`_determine_pr_base()` (at `src/aet/cli/ship.py:110` when reported; now at
`src/aet/cli/ship.py:209` post-fix) classifies any branch whose
merge-base differs from `origin/main` as **stacked on a parent feature branch**,
then walks the ancestry-path log to name that parent:

```python
    if merge_base == origin_main:
        return "origin/main"
    log = _run_git("log", "--oneline", "--decorate", "--ancestry-path", f"{merge_base}..HEAD").stdout
    for line in log.splitlines():
        ...
        for r in refs:
            r = r.replace("HEAD -> ", "").strip()          # <-- strips, then keeps
            if r in ("HEAD",) or r.startswith("origin/") or r.startswith("tag:"):
                continue
            return r                                        # <-- returns the branch's OWN name
    return "origin/main"
```

The premise is false. `merge_base != origin_main` is **also** true whenever
`origin/main` has simply advanced past the branch's fork point — the ordinary
case for a queued branch. In that case the only decorated non-remote ref in the
ancestry path is the branch's **own** tip decoration `HEAD -> <branch>`. The
loop (at line 126 when reported; now at `src/aet/cli/ship.py:225`) strips the
`"HEAD -> "` prefix and then treats the resulting name as a stacked
parent, returning the current branch as its own PR base. `gh pr create` then
rejects head == base.

The `HEAD -> <branch>` decoration specifically marks the **current** (checked-out) branch
— the branch being shipped — which can never be its own parent, yet it is the one
ref the loop fails to exclude.

## Impact

- Blocks `aet ship` for essentially the whole queue: a branch only stays "even"
  with `origin/main` until the next plan merges; after that every subsequent ship
  hits this.
- Connects to the epi-01/epi-02 base/trunk-resolver thread ("replace every
  hardcoded `main` with the resolved refs", #185). `_determine_pr_base` is a
  consumer that still hardcodes `origin/main` and was not covered by that work.

## Proposed fix

Exclude the current-branch ref (the `HEAD -> …` decoration) from the
stacked-parent search, so a branch that is merely behind `origin/main` falls
through to the `return "origin/main"` default:

```python
        for r in refs:
            if r.startswith("HEAD -> "):
                continue  # current branch — the one being shipped, never its own parent
            r = r.strip()
            if r in ("HEAD",) or r.startswith("origin/") or r.startswith("tag:"):
                continue
            return r
```

- **Files to modify:** `src/aet/cli/ship.py` (1 file), plus a regression test in
  `tests/test_ship_open.py`.
- **Diff budget:** ~3 source lines + 1 test — well within the ≤3 files / ≤100 lines budget.
- **Risk:** Low. Behavior changes only for the bug case (self-return → `origin/main`).
  Genuinely stacked branches are unaffected: the parent's ref is decorated
  without `HEAD -> <branch>`, so it is still returned.

## Test gap

`tests/test_ship_open.py` mocks git responses and never feeds a realistic
`HEAD -> <branch>, origin/<branch>` decorated ancestry log into the walk (the
default `_base_responses` sets `merge_base == origin_main`, and
`test_open_pushes_force_with_lease_after_rebase` stubs the rebase rather than the
decoration). The fix should add a unit test for `_determine_pr_base()`:

- behind-main independent branch (decoration `HEAD -> feat, origin/feat`) → `origin/main`
- genuinely stacked branch (a non-HEAD parent ref present) → the parent name

Both tests were added as `TestDeterminePrBase` (`tests/test_ship_open.py:117`).
One residual risk: the tests hand-craft the `git log --decorate` output strings,
so the mock is now the contract — if git's decoration format drifts (e.g.
`HEAD -> x` ordering or the `tag:` prefix), tests and parser could drift
together without either failing.

## Related observation (not part of this fix)

During recovery, the tool's post-rebase push (`_push_branch`, bare
`git push --force-with-lease`) was rejected as `non-fast-forward` after an earlier
non-rebased push had created the remote branch; a manual force-push with an
explicit lease (`--force-with-lease=<branch>:<old-sha>`) was required. Lower
confidence and a distinct code path — flagging for a separate look, not bundling
into this fix.

## Residual risk (not part of this fix)

The fix removes the self-return case, but the underlying heuristic — "the first
decorated non-remote ref in the ancestry path is the stacked parent" — can still
false-positive. Any *other* local branch pointing at a commit in
`merge_base..HEAD` (e.g. an abandoned `wip-foo` left at an ancestor commit)
would be returned as the PR base. This is rarer than the bug fixed here, but it
stems from the same false premise: decoration presence does not prove
intentional stacking. A durable fix likely means recording the parent at
branch-creation time rather than inferring it from decorations — fold into the
epi-01/epi-02 base/trunk-resolver thread (#185).

## Workaround (pre-fix versions only)

Ship behind-main branches with an explicit base from the worktree:

```
aet ship open --base origin/main <plan>
```

This rebases onto `origin/main` and opens the PR against `main` — the correct
intended flow the misdetection bypasses.
