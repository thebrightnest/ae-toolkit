# Illustrative Walkthrough: How `/aet-setup` Works

**This is an illustration, not a template.** It shows how the skill's methodology applies to a hypothetical project. The actual skill does not contain any of these specifics — it researches them on demand.

---

## Scenario

User invokes `/aet-setup` on a repo containing:

- `pyproject.toml` with FastAPI and Pydantic dependencies
- `package.json` with React and TypeScript
- `web/src/` and `api/app/` directories
- Basic `README.md` but no `AGENTS.md`
- A `.pre-commit-config.yaml` with only format checks

## Step 1: Discovery

The skill scans and finds:

- **Backend:** Python (pyproject.toml), FastAPI framework, Pydantic v2
- **Frontend:** Node (package.json), React, TypeScript, Vite
- **Database:** None explicitly declared, but SQLite mentioned in README
- **Pattern:** `api/app/` has `domain/`, `application/`, `infrastructure/`, `api/` → Clean Architecture

## Step 2: Research

The skill searches:

- "FastAPI best practices 2025 code quality"
- "React TypeScript strict ESLint best practices 2025"
- "Python security scanning tools 2025"

Finds: ruff + mypy dominate Python linting; ESLint flat config is standard for React 19; bandit and pip-audit are standard security tools.

## Step 3: Audit against Master Checklist

| Topic              | Status | Notes                                                   |
| ------------------ | ------ | ------------------------------------------------------- |
| Stack              | ✅     | Detected correctly                                      |
| Architecture       | ✅     | Clean Architecture identified                           |
| Type safety        | ⚠️     | MyPy strict enabled, but TS strict needs verification   |
| Linting            | ⚠️     | Ruff present, but ESLint v9 has no config file (broken) |
| Security           | ❌     | No bandit, pip-audit, or secret scanning                |
| Testing            | ⚠️     | pytest present but coverage threshold inconsistent      |
| Git hooks          | ⚠️     | Present but missing security and type checks            |
| AI guardrails      | ❌     | No AGENTS.md                                            |
| Documentation      | ⚠️     | Has docs/ but no CONVENTIONS.md or ADRs                 |
| Observability      | ❌     | Basic logging only                                      |
| DB migrations      | ❌     | SQLite without Alembic                                  |
| Dependency locking | ⚠️     | No lockfile committed                                   |
| API contracts      | ⚠️     | OpenAPI auto-generated but no frontend sync             |
| Git workflow       | ❌     | No conventional commits or branch naming                |

## Step 4: Propose

```
Detected: Python FastAPI + React TS + SQLite (monorepo)

Top gaps:
- No AGENTS.md (AI has no guardrails)
- No security scanning (static analysis, dependency audit, secrets)
- No AI guardrails in the codebase
- Git hooks missing security and type checks
- No dependency lockfile

Will create/modify:
- AGENTS.md (root + api/ + web/)
- docs/CONVENTIONS.md
- docs/adr/000-template.md + README.md
- api/pyproject.toml (add security tools, test factories)
- web/eslint.config.js (modern flat config + a11y)
- .pre-commit-config.yaml (add security, type checks, tests)
- Makefile (add security-audit, type-check, lock targets)
- .gitmessage (conventional commits template)
```

## Step 5: Implement (Illustrative)

The skill would:

1. Generate `AGENTS.md` with the project's actual Clean Architecture layers
2. Add `bandit`, `pip-audit`, `detect-secrets` to Python dev dependencies
3. Create a modern ESLint flat config with JSX a11y rules
4. Rewrite `.pre-commit-config.yaml` to include all 14 topics' gates
5. Enhance `Makefile` with `security-audit`, `type-check`, `lock` targets
6. Create `docs/CONVENTIONS.md` documenting the actual patterns found
7. Create `docs/adr/` with template

## Step 6: Validate

Run:

- `make lint` → passes
- `make type-check` → passes
- `make format-check` → passes
- `make security-audit` → passes
- `make test` → passes
- `pre-commit install` → succeeds

If any step fails, fix before claiming complete.

---

**Key point:** The skill did not know any of these specifics beforehand. It detected the stack, researched current practices, and applied the 14-topic methodology.
