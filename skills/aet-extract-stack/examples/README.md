# aet-extract-stack Examples

## Full-Stack Web App Extraction

A Next.js project with GitHub Actions, Docker, and pre-commit hooks.

**Project structure:**

```
my-web-app/
├── .github/workflows/ci.yml
├── .github/workflows/deploy.yml
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .pre-commit-config.yaml
├── Makefile
├── package.json
├── package-lock.json
├── .env
├── .env.example
├── README.md
└── docs/deployment.md
```

**Invocation:**

```
Run aet-extract-stack on this project
```

**Detected categories:** CI/CD (2 workflows), Containers (3 files), Tooling (1 config), Scripts (1 Makefile), Dependencies (2 files), Documentation (2 files)

**User selects:** All categories

**Extracted scaffold:**

```
scaffold/
├── INFRA.md
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .github/
│   └── workflows/
│       ├── ci.yml          # {{PROJECT_NAME}} replaces "my-web-app"
│       └── deploy.yml      # {{DOMAIN}} replaces "api.myapp.com"
├── .pre-commit-config.yaml
├── Makefile                # {{PROJECT_NAME}} replaces project-specific targets
├── package.json            # Scripts preserved, project name → {{PROJECT_NAME}}
└── docs/
    └── deployment.md       # Internal URLs → {{DOMAIN}}
```

**INFRA.md placeholder table excerpt:**

| Token              | Meaning                  | Where to set                                         |
| ------------------ | ------------------------ | ---------------------------------------------------- |
| `{{PROJECT_NAME}}` | Application / repo name  | `package.json`, `Dockerfile` LABEL, Makefile         |
| `{{DOMAIN}}`       | Production API host      | `.github/workflows/deploy.yml`, `docs/deployment.md` |
| `{{APP_PORT}}`     | Primary application port | `Dockerfile` EXPOSE, `docker-compose.yml`            |

---

## Minimal API Extract

A small Python FastAPI project with only a Makefile and requirements.txt.

**Detected categories:** Scripts (1 file), Dependencies (1 file)

**User selects:** Scripts, Dependencies

**Extracted scaffold:**

```
scaffold/
├── INFRA.md
├── Makefile
└── requirements.txt
```

**Notes:** No containers or CI detected. INFRA.md notes that CI/CD and containers are not present and suggests adding them if the project will be deployed.

---

## Monorepo Extraction

A monorepo with backend (Go) and frontend (React) subprojects.

**Project structure:**

```
monorepo/
├── .github/workflows/
│   ├── backend-ci.yml
│   ├── frontend-ci.yml
│   └── release.yml
├── backend/
│   ├── Dockerfile
│   ├── go.mod
│   ├── go.sum
│   └── Makefile
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── package-lock.json
│   └── vite.config.ts
├── docker-compose.yml
├── .pre-commit-config.yaml
├── Taskfile.yml
└── README.md
```

**Detected categories:** CI/CD (3 workflows), Containers (3 Dockerfiles + compose), Tooling (1 config), Scripts (2 files), Dependencies (3 files), Documentation (1 file)

**User selects:** All categories

**Extracted scaffold:** Preserves monorepo structure. Backend and frontend Dockerfiles each get their own `{{PROJECT_NAME}}` context. The release workflow gets `{{ORG_NAME}}` and `{{CONTAINER_REGISTRY}}` placeholders.

---

## Nothing-Found Scenario

A fresh repository with only source code and a README.

**Project structure:**

```
fresh-repo/
├── src/
│   └── main.py
└── README.md
```

**Invocation:**

```
Run aet-extract-stack on this project
```

**Result:**

```
No infrastructure artifacts detected in /path/to/fresh-repo. The project may be a library, a fresh repo, or use infrastructure-as-a-service with no local config.

Suggestion: Run aet-setup to bootstrap infrastructure from scratch instead.
```

No files are written.
