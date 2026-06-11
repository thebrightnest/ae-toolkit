# AE Toolkit Pipeline and Work-Class Routing

This document defines the canonical pipeline stages and the work-class routing table used by the AE Toolkit skills.

## Work Classes

Every incoming request is classified into one of three work classes before any skill runs.

| Class        | Trigger Examples                                | Pipeline                                                | Plans?           | QA Gate           |
| ------------ | ----------------------------------------------- | ------------------------------------------------------- | ---------------- | ----------------- |
| **Trivial**  | Fix typo, change button color, update copy      | Direct edit → `make validate` → ship                    | No               | Diff review only  |
| **Normal**   | Add email field, new API endpoint, simple modal | Quick plan (≤ 4 tasks) → implement → auto checks → ship | Yes, lightweight | Automated tests   |
| **Critical** | Add OAuth, migrate database, upgrade framework  | Full PRD → TDD → QA → review → `aet-verify` → ship      | Yes, full        | Observed evidence |

## Classification Decision Tree

1. **Is this a reproducible defect in existing code?**
   - Yes → **Bug** → `aet-bug-report`
2. **Does it touch auth, sessions, permissions, passwords, data models, migrations, infrastructure, or bump a dependency?**
   - Yes → **Critical** → Full PRD + TDD + QA + review + `aet-verify`
3. **Is it a copy change, color tweak, typo fix, or similarly small (≤ 3 files, ≤ 100 lines)?**
   - Yes → **Trivial** → Direct edit + `make validate` + ship
4. **Everything else** → **Normal** → Quick plan → implement → ship

## Symmetric Routing Guards

Entry-point skills enforce symmetric guards to prevent misrouted work:

- **`aet-plan` / `aet-pipeline-plan`**: If the user describes a reproducible defect, redirect to `aet-bug-report`.
- **`aet-bug-report`**: If the user describes a new capability or redesign, redirect to `aet-plan`.

## Canonical Stage State Machine

| Stage             | Meaning                             | Next Step                 |
| ----------------- | ----------------------------------- | ------------------------- |
| `plan-draft`      | PRD written, not yet validated      | `aet-validate-scope`      |
| `prd-approved`    | PRD approved by human               | `aet-validate-scope`      |
| `scope-validated` | Scope validated, plans approved     | `aet-work run`            |
| `plan-approved`   | Plan ready for implementation       | `aet-work run`            |
| `tdd-complete`    | Tests written, failing (RED)        | `aet-implement`           |
| `implemented`     | Code written, tests passing         | `aet-qa`                  |
| `qa-complete`     | All tests pass, coverage maintained | `aet-review`              |
| `reviewed`        | Code review passed                  | `aet-cso` (if applicable) |
| `secure`          | Security audit passed               | `aet-sync-docs`           |
| `synced`          | Docs synced to reality              | `aet-ship`                |
| `merged`          | On `origin/main`                    | None — pipeline complete  |

## Diff Budget for Bug Fixes

`aet-bug-report` enforces a diff budget to keep fixes proportional:

- **Budget**: ≤ 3 files and ≤ 100 lines
- **Exceeding the budget** requires explicit justification:
  - Why a smaller change is insufficient
  - Why the scope expansion is necessary to fix the root cause
- **Weak justification** → redirect to `aet-plan`; the issue likely requires redesign, not a targeted fix.
