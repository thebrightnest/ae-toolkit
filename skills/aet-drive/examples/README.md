# Examples for aet-drive

This directory contains usage examples for `/aet-drive`.

## Example 1: Standard Hands-Free Epic Execution

User prompt:

```text
/aet-drive
```

Agent actions:

1. Emits initialization banner showing auto-detected host adapter (`agy`, `claude`, or `kimi`).
2. Checks active epic (`feat/user-auth`) and queue tasks.
3. Launches `aet run` to run pipeline stages.
4. Waits for the run batch to finish.
5. Runs `aet status` and finds tasks `auth-01` and `auth-02` in `awaiting_merge`.
6. Executes `aet ship merge auth-01` and `aet ship merge auth-02`. Both succeed.
7. Next tasks `auth-03` become unblocked and `ready`.
8. Loops back to run `aet run` for `auth-03`.
9. Ships `auth-03`.
10. All epic tasks complete. Prints completion summary and offers `aet ship open-epic`.

---

## Example 2: Handling Merge Conflicts Intelligently

During step 6, `aet ship merge auth-02` reports:

```text
Merging feat/auth-02 into feat/user-auth produced conflicts in:
  - src/auth/service.py
Rebase onto the target branch or resolve the conflicts first.
```

Agent actions:

1. Inspects `src/auth/service.py`.
2. Locates conflicting imports and method additions from both `auth-01` and `auth-02`.
3. Synthesizes both changes into a coherent implementation.
4. Runs `pytest tests/test_auth.py` in the workspace. Tests pass.
5. Stages and commits: `git commit -m "fix(merge): resolve integration conflict for auth-02"`.
6. Re-executes `aet ship merge auth-02`. Merge succeeds and task is closed.
7. Resumes the epic execution loop.
