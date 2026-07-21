# Routing Rules Reference

## Deterministic Classification

These rules are evaluated in order. The first match wins.

### 1. Bug / Defect

**Question:** Is this a reproducible misbehavior of existing code?

- Error messages, crashes, exceptions, stack traces
- Unexpected behavior that the user can reproduce with steps
- Performance regressions (was fast, now slow)
- Visual regressions (was correct, now broken)

**Route:** `aet-bug-report`
**Guard:** `aet-plan` and `aet-pipeline-plan` must reject bug reports with: "This looks like a reproducible defect. Route to `aet-bug-report` instead."

### 2. Critical

**Question:** Does this touch any of the following?

| Area           | Examples                                                          |
| -------------- | ----------------------------------------------------------------- |
| Authentication | OAuth, SSO, login/logout, sessions, JWT, cookies, password resets |
| Authorization  | Permissions, roles, access control, gates, policies               |
| Data models    | Migrations, schema changes, foreign keys, constraints, indexes    |
| Infrastructure | Queues, storage, env vars, domains, load balancers, networking    |
| Dependencies   | Major or minor version bumps (not patch)                          |

**Route:** Full PRD → `aet-tdd` → `aet-implement` → `aet-qa` → `aet-review` → `aet-verify` → `aet-ship`
**Note:** Critical-class tasks are never downgraded. If uncertain, classify as critical.

### 3. Trivial vs Normal

**Question:** How many files and lines will this touch?

| Scope                | Class       | Examples                                                     |
| -------------------- | ----------- | ------------------------------------------------------------ |
| ≤ 1 file / ≤ 5 lines | **Trivial** | Typos, copy changes, color tweaks, single-line fixes         |
| Everything else      | **Normal**  | New fields, new endpoints, simple components, config changes |

**Trivial route:** Direct edit → `make validate` → `aet-ship`
**Normal route:** Quick plan (≤ 4 tasks) → `aet-implement` → auto checks → `aet-ship`

## Symmetric Routing Guards

Every entry-point skill includes an intake triage question to prevent misfit work:

- `aet-plan` / `aet-pipeline-plan`: "Is this a reproducible defect?" → redirect to `aet-bug-report`
- `aet-bug-report`: "Is this a new capability or redesign?" → redirect to `aet-plan`
- `aet-prime` (this skill): Evaluates all classification rules before routing

## Edge Cases

### Security patch

A security patch in a dependency is a **critical** dependency bump, even if the diff is small.

### Copy change that affects legal terms

If copy changes include legal, pricing, or compliance language, classify as **normal** (needs review) not trivial.

### Bug fix that requires a refactor

If `aet-bug-report` analysis shows the fix requires > 3 files or > 100 lines, the agent must justify the scope before continuing. Exceeding the budget without justification is a hard stop.
