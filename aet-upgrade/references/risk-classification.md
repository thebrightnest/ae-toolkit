# Risk Classification Criteria

Every breaking change in an upgrade plan must be classified as **High**, **Medium**, or **Low** risk using these deterministic criteria.

## High Risk

A breaking change is **High** risk when **all** of the following are true:

1. The affected pattern appears in production code (not tests, not docs).
2. There is no automated test coverage for the affected behavior.
3. The breaking change would cause a silent failure (no exception, no compile error).

**Examples:**

- A cast behavior change that double-hashes passwords. The code compiles and runs, but authentication breaks silently.
- A default configuration change that moves a storage path. Files appear to save successfully but are written to the wrong location.

**Required action:**

- Write an integration or end-to-end test that exercises the affected behavior before upgrading.
- Apply the mitigation and verify the test passes.
- Do not mark the upgrade complete until the test is green.

## Medium Risk

A breaking change is **Medium** risk when **any** of the following are true:

1. The affected pattern appears in production code with automated test coverage.
2. The affected pattern appears only in tests (test code may need updating, but production behavior is unaffected).
3. The breaking change would cause an explicit failure (exception, compile error, type error) that is easy to detect and fix.

**Examples:**

- A renamed hook (`useHistory` → `useNavigate`) that is covered by component tests.
- A removed method that causes a compile error at a single call site.

**Required action:**

- Run the full test suite after the upgrade.
- Fix any failing tests.
- If the fix is non-trivial, treat as High risk.

## Low Risk

A breaking change is **Low** risk when **all** of the following are true:

1. The affected pattern does not appear in the codebase.
2. Or the pattern appears only in documentation, comments, or archived code that is not executed.

**Examples:**

- A breaking change in a CSS-in-JS API when the project uses plain CSS.
- A removed deprecated method that was already replaced in a prior refactor.

**Required action:**

- Document the breaking change in the plan with "no direct usage found".
- No code changes needed.

## Edge Cases

### Internal packages with no changelog

When upgrading an internal package with no published changelog:

1. Diff the package source between versions (if source is available).
2. Run the project's test suite against the new version in a branch.
3. Treat all behavioral changes as Medium risk until evidence proves otherwise.
4. Document the absence of a changelog as a process gap.

### Transitive dependencies

For transitive dependency upgrades (bumped because a direct dependency requires a newer version):

1. Focus on the direct dependency's upgrade guide first.
2. Check the transitive dependency's changelog only if tests fail after the bump.
3. Do not enumerate every transitive change unless there is evidence of impact.
