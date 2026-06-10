# AE Toolkit Use Cases

Real-world scenarios showing how the skills compose into complete workflows.

---

## Scenario 1: Starting a New Project

You have an idea. You want solid foundations from day one.

```
/aet-setup
  → Scaffolds .agents/, docs/prds/, docs/plans/, AGENTS.md,
    linting, testing, git hooks, and agentic workflow infrastructure
  → Creates `make smoke` with foundation checks:
    login works, app boots, primary entity CRUDs, dev services respond
  → Runs gate calibration: plants trivial error, confirms validation
    commands actually fail, records authoritative commands

/aet-plan clarify-goal
  → "I want to build a task management app with team collaboration"
  → Agent interviews you with targeted questions until shared understanding

/aet-plan create-prd
  → Produces docs/prds/task-app-prd.md
  → You review and approve

/aet-plan create-stories
  → Breaks PRD into vertical-slice tickets in docs/plans/
  → Generates .agents/work-queue.json with DAG structure

/aet-work run --dry-run
  → Previews what the AFK loop would pick first

/aet-work run
  → Picks first unblocked task, implements, validates, commits
  → Clears context between tasks
  → Repeats until all tasks done

/aet-ship
  → Pre-merge gate: tests, coverage, review, security audit
  → Bisectable commits, CHANGELOG, VERSION bump, PR opened
```

**Skills used:** `aet-setup`, `aet-plan`, `aet-work`, `aet-ship`

---

## Scenario 2: Adopting on an Existing Project

You inherited a codebase with no standards. You want to add guardrails and start using agentic workflows.

```
/aet-setup
  → Detects existing stack
  → Audits against master checklist
  → Adds missing: linting, testing, pre-commit hooks, AGENTS.md
  → Creates .agents/ with templates and reference docs
  → Documents deviations from best practice in AGENTS.md

/aet-plan plan
  → Pick your first feature ticket
  → Produces docs/plans/{ticket}-plan.md

/aet-validate-scope validate
  → Checks the plan against existing code and CONTEXT.md
  → "Your glossary defines 'User' as an admin, but this plan uses
     it for end customers — which is it?"
  → Resolves terminology before implementation starts

/aet-prime
  → Loads AGENTS.md, plan.md, recent commits
  → "Based on the PRD, what should we build next?"

/aet-implement docs/plans/{ticket}-plan.md
  → Fresh session, reads plan as sole input
  → Writes code, runs validation, commits

/aet-review
  → Multi-lens diff review before merging
```

**Skills used:** `aet-setup`, `aet-plan`, `aet-validate-scope`, `aet-prime`, `aet-implement`, `aet-review`

---

## Scenario 3: Trivial Task — Fix and Ship

You spot a typo in the UI. No PRD needed.

```
/aet-prime
  → "Fix typo in login button"
  → Classified: trivial (≤ 3 files, ≤ 100 lines)
  → Routed to direct-edit path

# Edit the file

make validate
  → Lint and format check

/aet-ship
  → Diff review → merge
```

**Skills used:** `aet-prime`, `aet-ship`

**Key principle:** Trivial tasks skip planning, TDD, QA, and review. The triage front door prevents corporate-level ceremony from burdening every change.

---

## Scenario 4: Single Task / PIV Loop

You have one well-defined ticket. You want to run the full Plan → Implement → Validate cycle.

```
# Planning (human-in-the-loop)
/aet-plan clarify-goal
  → Quick alignment on what the ticket should do

/aet-plan plan
  → Produces docs/plans/TICKET-123-plan.md
  → Locked decisions, file list, ordered tasks, validation strategy
  → You review and approve

# Clear context. Start fresh session.

# Execution
/aet-prime
  → Load context: AGENTS.md, plan.md, recent commits

/aet-tdd plan-tests
  → "What should the public interface look like?"
  → "Which behaviors are most important to test?"
  → Identifies deep modules and designs testable interfaces

/aet-tdd tracer
  → Writes one test for the first behavior
  → Test fails (RED)
  → Minimal code to make it pass (GREEN)

/aet-tdd cycle
  → Repeats RED→GREEN for each remaining behavior
  → One vertical slice at a time

/aet-tdd refactor
  → All tests pass — now clean up duplication, deepen modules
  → Run tests after each refactor step

# Validation
/aet-review
  → Staff-level code review

/aet-cso
  → Security audit (if auth/data touched)

/aet-qa
  → Automated QA with tiered validation

/aet-ship
  → Pre-merge gate → PR
```

**Skills used:** `aet-plan`, `aet-prime`, `aet-tdd`, `aet-review`, `aet-cso`, `aet-qa`, `aet-ship`

---

## Scenario 5: Big Feature / Epic with Multiple Tasks (AFK Loop)

You have a multi-week epic. You want to plan it once, then let the agent work through tasks sequentially while you focus on other things.

```
# Day shift: Human plans
/aet-plan clarify-goal
  → Deep alignment session on the full epic

/aet-plan create-prd
  → docs/prds/epic-prd.md approved

/aet-validate-scope validate
  → Cross-checks epic against existing domain model and ADRs
  → Surfaces contradictions while they're still cheap to fix
  → Updates CONTEXT.md with any new terms

/aet-plan create-stories
  → 8 vertical-slice tickets in docs/plans/
  → .agents/work-queue.json with DAG created

/aet-plan publish-issues --tracker=github
  → Pushes tickets to GitHub Issues with HITL/AFK labels
  → Your team can view and triage in the tracker
  → Local work queue remains the source of truth for aet-work

# Night shift: Agent implements (AFK)
/aet-work run
  → Task 1: unblocked → implement → validate → done
  → CLEAR CONTEXT
  → Task 2: now unblocked → implement → validate → done
  → CLEAR CONTEXT
  → Task 3: implement → FAIL (test broken)
  → LOOP STOPS for human review

# Morning: Human reviews
# Fix the issue, update .agents/learnings.jsonl

# Resume night shift
/aet-work run
  → Picks up where it left off
  → Task 3: retry → done
  → Tasks 4–8: continue sequentially

# When all tasks done
/aet-ship
  → Merges the epic branch
```

**Skills used:** `aet-plan`, `aet-validate-scope`, `aet-work`, `aet-ship`

**Key feature:** Context is explicitly cleared between tasks. The loop can run 20+ tasks without degradation because each task starts with a clean 5–15k token context window.

---

## Scenario 6: System Evolution After a Bug

The agent made the same mistake twice. You want to fix the system, not just the code.

```
# Bug occurs during aet-implement
# Agent forgot to handle the error case again

/aet-evolve retro
  → Analyzes what went wrong
  → Root cause: plan.md template lacks an "error handling" section
  → Layer identified: .agents/templates/plan-template.md

/aet-evolve system-evolve
  → Updates plan-template.md with explicit error handling checklist
  → Documents the learning in .agents/learnings.jsonl
  → Commits the change to source control

# Next ticket uses the updated template
# The bug category never happens again
```

**Skills used:** `aet-evolve`

**Why this matters:** One improved template saves dozens of engineer-hours across future sessions. The system gets smarter over time.

---

## Scenario 7: Security-First PR

You're adding OAuth and payment processing. Security is non-negotiable. This is **critical-class** work.

```
/aet-prime
  → "Add OAuth and Stripe payment processing"
  → Classified: critical (touches auth and payments)
  → Routed to full PRD → TDD → QA → review → aet-verify → ship

/aet-plan plan
  → docs/plans/auth-payment-plan.md

/aet-implement docs/plans/auth-payment-plan.md
  → Implements OAuth + payment flow

/aet-cso
  → Scans diff for: secrets, SQL injection, auth bypass,
    LLM trust boundaries, dependency CVEs
  → Produces security report with severity
  → FAIL: found hardcoded API key in config

# Fix the issue, remove the key

/aet-cso
  → Re-scan
  → PASS

/aet-review
  → Architecture review of auth flow

/aet-qa --tier=exhaustive
  → All states tested: login, logout, expired token,
    payment success, payment failure, refund

/aet-verify
  → Foundation mode: `make smoke` (login, boot, CRUD)
  → Feature mode: exercise OAuth flow in running app
    → Capture: HTTP 302 redirect to provider, callback success,
      session cookie set, JWT decoded correctly
    → Evidence attached to QA report

/aet-ship
  → Pre-merge gate: checks aet-verify evidence exists
  → Merge only with observed proof
```

**Skills used:** `aet-prime`, `aet-plan`, `aet-implement`, `aet-cso`, `aet-review`, `aet-qa`, `aet-verify`, `aet-ship`

---

## Scenario 8: Dependency Upgrade

Laravel 11 is out. You want to upgrade without breaking the app.

```
/aet-prime
  → "Upgrade Laravel from 10 to 11"
  → Classified: critical (dependency bump)
  → Routed to aet-upgrade

/aet-upgrade
  → Fetches Laravel 11 upgrade guide and changelog
  → Enumerates breaking changes:
    1. `hashed` cast behavior changed (double-hashing risk)
    2. `storage/app/private` path moved
    3. Password validation rules stricter
  → Greps codebase for each affected pattern
  → Risk map:
    - HIGH: User model uses `hashed` cast → 47 factory passwords affected
    - MEDIUM: File upload references `storage/app/private`
    - LOW: Password validation already meets new rules

# Plan the fix

/aet-plan plan
  → docs/plans/laravel-11-upgrade-plan.md
  → Tasks: update User model, fix factories, migrate storage paths

/aet-verify
  → Foundation mode: `make smoke` before upgrade
  → All green — floor is solid

/aet-implement docs/plans/laravel-11-upgrade-plan.md

/aet-verify
  → Foundation mode: `make smoke` after upgrade
  → Login works, file uploads work, factories produce valid passwords

/aet-ship
```

**Skills used:** `aet-prime`, `aet-upgrade`, `aet-plan`, `aet-verify`, `aet-implement`, `aet-ship`

**Key principle:** Upgrades are not features and not bugs. They need their own skill because breaking-change analysis is a distinct competence from feature design or bug diagnosis.

---

## Scenario 9: Refactoring with TDD Safety Rails

You need to refactor a messy module. You want tests as safety rails, written the right way.

```
/aet-tdd plan-tests
  → "What behaviors must survive this refactor?"
  → Identifies public interfaces to test through
  → Rejects implementation-detail tests

/aet-tdd tracer
  → Writes one behavior test through the public API
  → Confirms the test passes against current (messy) code

/aet-tdd cycle
  → Backfills tests for each behavior the refactor must preserve
  → Each test verifies WHAT, not HOW
  → Tests will survive the internal rewrite

# Refactor with confidence
# Rename classes, extract modules, change data structures
# Tests stay green — behavior is preserved

/aet-tdd refactor
  → Deepens modules: small interfaces, complex implementations hidden
  → Removes duplication revealed by the refactor
  → All tests pass

/aet-review
  → Verifies the new structure is cleaner and tests are meaningful
```

**Skills used:** `aet-tdd`, `aet-review`

**Key principle:** Tests written through public interfaces survive any internal restructuring. Tests coupled to implementation break during refactors and provide false confidence.

---

## Scenario 9: Validating a Plan Against Existing Architecture

Your team has a mature codebase with documented domain language and ADRs. A new feature plan seems to contradict established patterns.

```
/aet-validate-scope validate
  → Reads docs/prds/new-feature-prd.md
  → Reads CONTEXT.md — glossary defines "Order" as immutable after placement
  → Reads docs/adr/0003-immutable-orders.md
  → Cross-checks with code: Order class has no setters
  → SURFACES: "This PRD says 'edit order after placement' but your
     glossary and ADR-0003 define Orders as immutable. Which is right?"

# Discussion resolves the conflict
# PRD is updated: "cancel and replace" instead of "edit"

/aet-validate-scope update-context
  → Adds "Order Replacement" to CONTEXT.md
  → Defines the new term and its relationship to Orders

/aet-validate-scope propose-adr
  → "This changes the immutable-orders policy. Should we record why?"
  → Creates docs/adr/0012-order-replacement.md
  → Explains the trade-off: immutability preserved, replacement is a new Order

/aet-plan create-stories
  → Now the stories are aligned with the domain model
```

**Skills used:** `aet-validate-scope`, `aet-plan`

**Key principle:** Catching domain misalignment at planning time is 100x cheaper than catching it in code review or production.
