---
name: aet-setup
description: Bootstrap or upgrade any software project with best-practice documentation, code quality enforcement, local automation, and AI guardrails. Part of the Agentic Engineering Toolkit (AE Toolkit). Use when starting a new project, inheriting a codebase without standards, or wanting to prevent AI-generated "fast slop." Adapts to any stack through research-driven detection. Triggers on requests like "set up project quality," "enforce code standards," "bootstrap best practices," or "prevent AI slop."
---

# aet-setup

Bootstrap or upgrade any software project with best-practice documentation, code quality enforcement, local automation, and AI guardrails — without hardcoded templates or paid CI services.

## When to Use

- Starting a new project and want solid foundations
- Inheriting an existing project that lacks quality standards
- Tired of writing the same "setup best practices + enforce quality + no AI slop" prompt
- Want reusable, research-driven setup that adapts to any stack

## Invocation

```
/aet-setup
```

Auto-detects stack, infers sensible defaults, suggests key decisions, and implements everything.

```
/aet-setup stack="backend-lang + frontend-lang + sqlite"
```

Explicit stack declaration. Skips detection. Useful for new/empty repos.

```
/aet-setup stack="backend-lang + frontend-lang + postgres" enforce-security=true containerize=true
```

With optional flags to override sensible defaults.

## Philosophy

**Research-driven, not template-driven.** This skill does not ship hardcoded config files for every possible stack. Instead it:

1. **Detects** the stack from existing files (or accepts explicit declaration)
2. **Researches** current best practices for that stack (using web search when needed)
3. **Audits** the current project state against the master checklist
4. **Implements** tailored configs, docs, and automation
5. **Guards** against AI slop with explicit rules in `AGENTS.md`

The skill **suggests** important topics but never blocks waiting for user input. It uses common-sense defaults.

## Master Checklist

For every project, ensure these topics are addressed. Use auto-detection; fall back to sensible defaults.

| # | Topic | How to Detect | Sensible Default |
|---|-------|---------------|-----------------|
| 1 | **Stack** | Look for build/config files (e.g., package manifests, build configs) | Ask user if ambiguous; default to detected |
| 2 | **Architecture pattern** | Framework used, directory structure conventions | Clean/hexagonal for backends; component-based for frontends |
| 3 | **Type safety** | Presence of type checker config, strict flags | Strict mode enabled everywhere |
| 4 | **Linting & formatting** | Presence of linter/formatter configs | Dominant tools for the language, configured and runnable |
| 5 | **Security scanning** | Presence of static analysis, dependency audit, secret scanning | **Enable by default** — never optional |
| 6 | **Testing** | Presence of test runner config | Unit + integration for backend; unit + component for frontend |
| 7 | **Git hooks** | Presence of pre-commit config or git hooks | pre-commit with format/lint/type-check/test/security gates |
| 8 | **AI guardrails** | Presence of `AGENTS.md` | Generate with explicit forbidden/mandatory rules |
| 9 | **Documentation** | Presence of docs, README quality | `AGENTS.md` + `docs/CONVENTIONS.md` + ADR process |
| 10 | **Observability** | Presence of structured logging, metrics, tracing | Structured logging + health checks at minimum |
| 11 | **DB migrations** | Presence of ORM + migration tool | Migration tool if ORM detected; document if intentionally skipped |
| 12 | **Dependency locking** | Presence of lockfiles | Enforce lockfile; add runtime version constraints |
| 13 | **API contracts** | Presence of schema generation, type sync | Schema auto-gen for backend; frontend type sync if applicable |
| 14 | **Git workflow** | Presence of commit message template, branch conventions | Conventional commits; branch naming conventions |

## Execution Steps

When invoked, follow this sequence:

### Step 1: Discovery
Scan the project root for stack indicators. Look for:
- Build/config files (package manifests, build tool configs, lockfiles)
- Source file extensions
- Framework-specific files

If multiple stacks detected, treat as monorepo.

### Step 2: Research (if needed)
If the stack is novel or you're unsure about current best practices, search the web:
- "{detected framework/language} best practices {current year}"
- "{detected framework/language} code quality tools {current year}"
- "{detected framework/language} security scanning setup"

Focus on tooling that is:
- **Maintained** (active repository, recent releases)
- **Widely adopted** (used by major projects)
- **Compatible** with the existing dependency versions

### Step 3: Audit
Compare the current project against the Master Checklist. For each item:
- **Present & good** → note it
- **Present but weak** → flag for upgrade
- **Missing** → flag for creation

Produce a concise audit report (bullet list, max 1 page).

### Step 4: Propose
Show the user:
1. Detected stack
2. Top 5 gaps found
3. What will be created/modified

Example:
```
Detected: Backend API + Frontend SPA + SQLite (monorepo)

Top gaps:
- No AGENTS.md (AI has no guardrails)
- No security scanning (static analysis, dependency audit)
- No dependency locking (lockfile missing)
- No DB migration tool (ORM present but no migrations)
- Frontend lacks a11y and bundle analysis

Will create/modify:
- AGENTS.md, docs/CONVENTIONS.md
- backend config (add security tools, test factories)
- frontend config (add a11y linting, bundle analyzer)
- .pre-commit-config.yaml (enhanced hooks)
- Makefile (add security-audit, type-check targets)
- docs/adr/000-template.md
```

### Step 5: Implement
Create/modify files. Always:
- **Prefer editing existing files** over creating new ones
- **Preserve existing conventions** when they conflict with "best practice" — document the deviation in `AGENTS.md`
- **Make minimal changes** — don't rewrite the project
- **Ensure all hooks/tools are local** — no paid CI services

### Step 6: Validate
Before finishing:
1. Run the newly added linters/formatters — they should pass (or have zero false positives)
2. Run the test suite — it should pass
3. Verify pre-commit hooks can install
4. Confirm `AGENTS.md` is readable and actionable

## Methodology by Topic

### AI Context Files (`AGENTS.md`)

Always generate `AGENTS.md` at project root and per-subproject. It must contain:
- Project overview and detected stack
- Architecture pattern and layer rules
- Directory structure
- **Tooling reference table** — what command runs what check
- **AI Guardrails** section with explicit Forbidden and Mandatory lists

The guardrails must be generated based on the project's actual patterns, not copied from a template.

### Type Safety

For every typed language in the project:
- Enable the strictest available compiler/interpreter settings
- Document the specific flags in `AGENTS.md`
- Ban implicit dynamic typing (`any`, `interface{}`, `void*`, etc.) except at explicit boundaries

### Linting & Formatting

Every code directory must have automated format and lint checks:
- Use the dominant tools for the detected language/framework
- Ensure formatter and linter configs don't conflict
- Line length: pick a standard (80, 100, or 120) and enforce it everywhere

### Security Scanning

Security is non-optional. For every stack:
- **Static analysis:** scan source code for vulnerabilities (e.g., unsafe deserialization, injection risks)
- **Dependency audit:** scan installed packages for known CVEs
- **Secret scanning:** detect accidentally committed credentials, API keys, tokens
- Add suppression comments (e.g., `# nosec`) only with explicit justification
- Document all security exceptions in `AGENTS.md`

### Testing

Define the testing pyramid:
- **Unit tests:** Fast, deterministic, no I/O. Mock external dependencies.
- **Integration tests:** Test boundaries (API endpoints, DB queries, external calls).
- **Coverage target:** Default 80%, but adjust to reality if the project is far below.
- **Test data:** Use factories/fakers. Never hardcode domain values in tests.

### Git Hooks & Local Automation

All quality gates must run locally:
- Create `.pre-commit-config.yaml` or git hooks running: format check, lint, type check, security scan, tests
- Create root orchestration (`Makefile` or `justfile`) with: install, dev, test, lint, format, type-check, security-audit
- Ensure every target actually works

### Git Workflow

Enforce commit conventions and branch naming:
- Add `.gitmessage` template for conventional commits
- Add branch naming conventions to `AGENTS.md`
- Optional: add commitlint if easily supported by the stack

### Dependency Locking

Reproducible builds are mandatory:
- Ensure lockfiles exist and are committed
- Add runtime version constraints (e.g., minimum language/runtime version in package config)
- Add a `lock` or equivalent target to the orchestration file

### Database Migrations

If an ORM or database abstraction is detected:
- Research the standard migration tool for that ORM
- Set it up OR document why migrations aren't needed (e.g., SQLite in dev only, schema-less DB)

### API Contracts

If backend and frontend are separate stacks in the same repo:
- Generate a machine-readable schema from the backend (OpenAPI, tRPC, GraphQL)
- Generate or sync frontend types from the schema
- Document the sync command in `AGENTS.md`

### Observability

Structured logging is the minimum:
- Replace basic logging with structured format (timestamp, level, name, message)
- Add a health check endpoint that verifies critical dependencies
- Reduce third-party log noise to warning level by default

### Accessibility (Frontend)

If a frontend is detected:
- Add a11y linting rules to the frontend linter config
- Document a11y requirements in `AGENTS.md`
- Enforce: keyboard accessibility, image alt text, form labels, semantic HTML

### Documentation

Humans need conventions docs; AI needs guardrails:
- Generate `docs/CONVENTIONS.md` with: structure, naming, error handling, state management patterns
- Create `docs/adr/` with template and README explaining ADRs
- Explain what an ADR is: a short document capturing a significant architectural decision, its context, and its consequences

## Generated Artifacts

### 1. AGENTS.md (root)
The most important file. Contains:
- Project overview and stack
- Architecture pattern and layer rules
- **AI Guardrails** section with explicit Forbidden and Mandatory lists
- Tooling reference (what runs where)
- Decision log (brief, high-level)

### 2. docs/CONVENTIONS.md
Human-readable patterns:
- Project structure and naming conventions
- Code style rules
- Testing conventions
- Error handling patterns
- API conventions (if applicable)

### 3. Tool configs
Linter, formatter, type checker, security scanner configs tailored to the detected stack.

### 4. Root orchestration
`Makefile` or `justfile` with targets: install, dev, test, lint, format, type-check, security-audit, clean

### 5. ADR template
`docs/adr/000-template.md` and `docs/adr/README.md`

## AI Guardrails Template

Every `AGENTS.md` must include a section like this, adapted to the project:

```markdown
## AI Assistant Guardrails

### Forbidden
- Never add a new dependency without explicit justification and version pinning
- Never disable linter, formatter, or type-checker rules to make code pass — fix the root cause
- Never write code without corresponding tests (unless explicitly asked to prototype)
- Never modify generated files (lock files, migration files) by hand
- Never commit secrets, API keys, or `.env` files
- Never introduce new patterns/abstractions without checking existing ones first

### Mandatory
- Always run the full test suite before claiming a task is complete
- Always update this file if you change architectural patterns or tooling
- Always use factories/fixtures for test data, never hardcode domain values
- Always type-annotate public functions; dynamic typing is banned except at explicit boundaries
- Always prefer composition over inheritance
- Always keep functions small and focused; extract helpers rather than nesting logic
```

## Rules

- **Never use paid CI services** — all automation must be local (pre-commit, Make, git hooks, scripts)
- **Security is not optional** — always include security scanning tools
- **Don't over-engineer** — if the project is a small script, don't force enterprise architecture
- **Respect existing choices** — if the project already uses a specific package manager or build tool, don't switch unless asked
- **Document deviations** — if you choose not to follow a "best practice", explain why in `AGENTS.md`
- **Keep it runnable** — every command in the Makefile must actually work
- **Suggest, don't block** — propose key decisions but never halt waiting for user input
