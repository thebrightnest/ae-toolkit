---
name: aet-tdd
description: Test-driven development with red-green-refactor loop and vertical tracer bullets. Use when the user mentions TDD, red-green-refactor, test-first development, or wants to build features or fix bugs using tests. Triggers on requests like "write tests first," "use TDD," or "red-green-refactor."
---

# aet-tdd

Test-driven development for agentic engineering. Write behavior-driven tests through public interfaces, not implementation details. Work in vertical slices — one test, one behavior, one cycle at a time.

## When to Use

- Building a new feature and the user wants tests written first
- Fixing a bug and the user wants a regression test before the fix
- The user mentions "red-green-refactor," "TDD," or "test-first"
- Code exists but lacks tests and the user wants to backfill with TDD discipline
- Refactoring existing code and the user wants tests as safety rails

## Context

Run `aet context` and parse its JSON for session context (branch, repo
state, AGENTS.md, learnings, active plan/PRD stage); print the stage
banner it emits. Do not ask the user for this context manually.

- `TEST_SETUP` — test runner, coverage tool, existing test patterns

## Philosophy

**Core principle**: Tests should verify behavior through public interfaces, not implementation details. Code can change entirely; tests shouldn't.

**Good tests** are integration-style: they exercise real code paths through public APIs. They describe _what_ the system does, not _how_ it does it. A good test reads like a specification — "user can checkout with valid cart" tells you exactly what capability exists. These tests survive refactors because they don't care about internal structure.

**Bad tests** are coupled to implementation. They mock internal collaborators, test private methods, or verify through external means (like querying a database directly instead of using the interface). The warning sign: your test breaks when you refactor, but behavior hasn't changed.

See [references/tests.md](references/tests.md) for examples and [references/mocking.md](references/mocking.md) for mocking guidelines.

## Mock Boundary Policy

Mock **system boundaries**, not **first-party code**.

- **Acceptable to mock:** network calls, external APIs, file systems, email gateways, payment providers, timers, randomness
- **Unacceptable to mock:** internal services, repositories, use-case classes, utility modules, or any first-party code you own

Why: mocking first-party code hides real integration failures and makes tests match the imagined implementation. Execute your own code for real; isolate only what crosses the process boundary.

**Example:**

```python
# ACCEPTABLE — mock the external HTTP boundary
responses.add("GET", "https://api.stripe.com/v1/charges", json={"status": "succeeded"})

# UNACCEPTABLE — mock an internal repository
mock_repo.get.return_value = fake_order  # <- do not do this
```

If a test mocks a first-party module, treat it as a review flag and replace the mock with real code or move the test to an integration boundary.

## Anti-Pattern: Horizontal Slices

**DO NOT write all tests first, then all implementation.** This is "horizontal slicing" — treating RED as "write all tests" and GREEN as "write all code."

This produces **crap tests**:

- Tests written in bulk test _imagined_ behavior, not _actual_ behavior
- You end up testing the _shape_ of things (data structures, function signatures) rather than user-facing behavior
- Tests become insensitive to real changes — they pass when behavior breaks, fail when behavior is fine
- You outrun your headlights, committing to test structure before understanding the implementation

**Correct approach**: Vertical slices via tracer bullets. One test → one implementation → repeat.

```
WRONG (horizontal):
  RED:   test1, test2, test3, test4, test5
  GREEN: impl1, impl2, impl3, impl4, impl5

RIGHT (vertical):
  RED→GREEN: test1→impl1
  RED→GREEN: test2→impl2
  RED→GREEN: test3→impl3
  ...
```

## Commands

### `plan-tests`

Before writing any code, plan what to test and how.

**Procedure:**

1. Confirm with the user what interface changes are needed
2. Enumerate every new source file or class introduced by the plan. For each, identify the behavior(s) it provides and write at least one test name. This list is the minimum test plan — behaviors beyond it are optional additions
3. Identify opportunities for [deep modules](references/deep-modules.md) (small interface, deep implementation)
4. Design interfaces for [testability](references/interface-design.md)
5. List the behaviors to test (not implementation steps)
6. If the plan is a vertical slice that introduces both a backend endpoint and a frontend consumer, include an API boundary test. See [references/api-boundary-tests.md](references/api-boundary-tests.md) for patterns
7. Get user approval on the plan

**Ask:** "What should the public interface look like? Which behaviors are most important to test?"

Focus testing effort on critical paths and complex logic, not every possible edge case.

### `tracer`

Write ONE test that confirms ONE thing about the system.

```
RED:   Write test for first behavior → test fails
GREEN: Write minimal code to pass → test passes
```

This is your tracer bullet — proves the path works end-to-end through all layers.

**Rules:**

- The test must describe behavior, not implementation
- The test must use the public interface only
- The test must survive an internal refactor
- The implementation must be minimal — just enough to pass

### `cycle`

For each remaining behavior:

```
RED:   Write next test → fails
GREEN: Minimal code to pass → passes
```

**Rules:**

- One test at a time
- Only enough code to pass the current test
- Don't anticipate future tests
- Keep tests focused on observable behavior

After each cycle, run the full test suite to catch regressions early.

### `refactor`

After all tests pass, improve the code without changing behavior.

**Procedure:**

1. Look for [refactor candidates](references/refactoring.md)
2. Extract duplication
3. Deepen modules (move complexity behind simple interfaces)
4. Apply SOLID principles where natural
5. Consider what new code reveals about existing code
6. Run tests after each refactor step

**Critical rule: Never refactor while RED.** Get to GREEN first.

## Checklist Per Cycle

```
[ ] Test describes behavior, not implementation
[ ] Test uses public interface only
[ ] Test would survive internal refactor
[ ] Code is minimal for this test
[ ] No speculative features added
```

## Coverage Completeness

Before declaring `tdd-complete`, run the test suite with coverage. List every new source file and its coverage percentage. Any file at 0% is a blocking failure — the `tdd-complete` stage cannot be set until every new file has at least one test touching it.

## Completion Protocol

After `refactor` completes, all tests pass, and coverage completeness is satisfied:

1. The stage transition (`tdd-complete`) is recorded on the task record by the
   pipeline engine. Do not touch the plan.md footer — plan files are transient
   working copies (gitignored); the queue/ledger is the stage source.

2. Print: `"✓ Stage: tdd-complete → Next step: run \`aet-implement\` to write code that satisfies these tests"`

## Key Principles

- **Vertical slices** — one behavior at a time, end to end
- **Public interfaces only** — test WHAT, not HOW
- **Minimal code** — write just enough to pass the current test
- **Green before refactor** — never refactor while tests are failing
- **Integration-style tests** — prefer real code paths over mocks of internals
