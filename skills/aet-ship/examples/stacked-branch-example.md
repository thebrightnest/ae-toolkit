# Example: Stacked Branch Detection

## Scenario

Branch `s2-t2-opencode-sdk-fix` was branched from `s2-t1-runner-abort` (not from the trunk branch), because S2-T2 depended on the `IExecutionRunner.abort()` interface added in S2-T1. In this repo the trunk branch is `main`; substitute `<trunk>` with the branch reported by `aet setup verify`.

## Detection

```bash
$ git merge-base HEAD <trunk>
a1b2c3d4...

$ git rev-parse <trunk>
f9e8d7c6...
```

Values differ → stacked branch detected.

## Identify parent branch

```bash
$ git log --oneline --decorate <trunk>..HEAD
e5f6a7b (HEAD -> s2-t2-opencode-sdk-fix) fix: opencode sdk abort call shape
c8d9e0f (s2-t1-runner-abort) feat: add abort()/getStatus() to IExecutionRunner
```

Parent branch: `s2-t1-runner-abort` (nearest named ancestor below HEAD).

## PR body injection

```markdown
⚠️ STACKED PR — base is `s2-t1-runner-abort`, not `<trunk>`.
After `s2-t1-runner-abort` merges to `<trunk>`, run:
git rebase <trunk> && git push --force-with-lease && gh pr edit --base <trunk>
before merging this PR.

---

<!-- rest of PR description -->
```

## Terminal stop-note (printed after `gh pr create`)

```
⚠️  STACKED PR: this PR targets s2-t1-runner-abort, not <trunk>.
    After s2-t1-runner-abort merges, rebase onto <trunk> and update the base before merging.
```

## What the human does when the parent PR merges

```bash
git checkout s2-t2-opencode-sdk-fix
git rebase <trunk>
git push --force-with-lease
gh pr edit <PR-number> --base <trunk>
```
