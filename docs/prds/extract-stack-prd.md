# PRD: aet-extract-stack

## Overview

`aet-extract-stack` is an AE Toolkit skill that scans an existing software project for its infrastructure, DevOps, and automation setup — CI/CD, containers, tooling configs, scripts, dependencies, and environment patterns — and extracts them into a reusable scaffold package. It produces an `INFRA.md` manifest and a `scaffold/` directory containing sanitized, placeholder-filled configurations ready to apply to a new project. It is the inverse of `aet-setup`: instead of bootstrapping from scratch, it clones the proven setup from a project that already works.

## Goals

- Reduce infrastructure setup time for new projects from 1+ hours of manual config archaeology to under 5 minutes of agent-assisted extraction.
- Ensure team consistency by making it trivial to replicate the infrastructure of a "golden" reference project.
- Prevent secret leakage by enforcing strict rules about what can and cannot be copied.
- Produce a self-documenting scaffold that a human can review and apply without needing to understand the source project.

## Non-Goals

- **No source code extraction.** This skill handles infrastructure, config, and automation only.
- **No live secret management.** The skill never copies `.env`, `secrets.yml`, kubeconfig, or service-account keys. Only `.env.example` or templates are extracted.
- **No automatic application.** The skill produces a scaffold; applying it to the new project is a separate human-reviewed step.
- **No cross-repo sync.** One-time extraction only. Keeping two projects' infrastructure in sync is out of scope.
- **No stack detection or research.** Unlike `aet-setup`, this skill does not research best practices. It copies what already exists.

## User Stories

- As an **engineering lead**, I want to extract the infrastructure from our team's reference project so that every new repo starts with the same CI/CD, linting, and container setup.
- As a **developer spinning up a PoC**, I want to clone the DevOps setup from a project I know works well so that I don't spend an hour manually copying configs.
- As a **developer inheriting a project**, I want to generate an `INFRA.md` manifest from an existing repo so that I can understand its infrastructure surface without reading 15 files.

## Acceptance Criteria

- [ ] Given a project with GitHub Actions, Dockerfile, and `.pre-commit-config.yaml`, when the skill runs, it detects all three categories and presents them as a selectable checklist.
- [ ] Given a user selects CI/CD and Tooling, when extraction completes, `scaffold/` contains only those categories' files with project-specific values replaced by `{{PLACEHOLDER}}` tokens.
- [ ] Given a project has a `.env` file with real secrets, when the skill runs, it refuses to copy `.env` and instead copies `.env.example` (or generates a template from keys if no example exists).
- [ ] Given extraction completes, `INFRA.md` lists every extracted file, every placeholder used, and step-by-step instructions for applying the scaffold to a new project.
- [ ] Given the user provides a destination path, the skill copies the scaffold to that location in addition to creating the local `scaffold/` directory.
- [ ] Given a project with no detectable infrastructure artifacts, the skill halts and reports that nothing was found.

## Technical Notes

### Detection Surface

The skill scans these categories and paths:

| Category | Paths |
| --- | --- |
| CI/CD | `.github/workflows/`, `.gitlab-ci.yml`, `.circleci/`, `azure-pipelines.yml`, `Jenkinsfile`, `bitbucket-pipelines.yml`, `.buildkite/`, `appveyor.yml` |
| Containers | `Dockerfile`, `docker-compose.yml`, `docker-compose.*.yml`, `.dockerignore`, `Containerfile`, `kubernetes/`, `k8s/`, `helm/`, `skaffold.yaml` |
| Infra-as-Code | `terraform/`, `*.tf`, `pulumi/`, `serverless.yml`, `sam.yaml`, `cloudformation/`, `ansible/`, `packer/`, `vagrant/` |
| Environment / Config | `.env*`, `config/`, `*.config.*`, `secrets.*`, `.aws/`, `.kube/`, `infrastructure/` |
| Dependencies | Lockfiles and manifest files (`package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `poetry.lock`, `Cargo.lock`, `go.sum`, `Gemfile.lock`, `uv.lock`, `requirements*.txt`) |
| Scripts | `Makefile`, `justfile`, `Taskfile.yml`, `package.json` scripts, `scripts/`, `bin/`, `*.sh`, `*.py` |
| Tooling | `.pre-commit-config.yaml`, linter configs, formatter configs, type-checker configs, security configs |
| Documentation | `README.md` setup sections, `docs/deployment.md`, `docs/ops.md`, `runbooks/`, `ARCHITECTURE.md` |

### Placeholder Convention

Standard tokens to replace project-specific values:

| Token | Replaces |
| --- | --- |
| `{{PROJECT_NAME}}` | App name, service name, repo name |
| `{{ORG_NAME}}` | GitHub org, DockerHub namespace |
| `{{DOMAIN}}` | Production domain, API host |
| `{{APP_PORT}}` | Primary application port |
| `{{DB_NAME}}` | Database name |
| `{{AWS_REGION}}` | AWS region |
| `{{CONTAINER_REGISTRY}}` | Docker image registry host |
| `{{SECRET}}` | Generic secret placeholder |

Custom descriptive placeholders are permitted for values that don't fit the standard set (e.g., `{{REDIS_CLUSTER_URL}}`).

### Secret Detection

Files that must **never** be copied without sanitization:

- `.env`, `.env.local`, `.env.production`, `.env.development`
- `secrets.yml`, `secrets.yaml`, `secrets.json`
- `kubeconfig`, `*.kubeconfig`
- Service account keys: `*.json` in `.aws/`, `credentials`, `*.pem`, `*.key`
- Any file containing `password=`, `api_key=`, `secret=`, `token=` with actual values

If `.env.example` does not exist, generate one from `.env` by copying keys and replacing all values with `{{PLACEHOLDER}}`.

### Output Structure

```
scaffold/
├── INFRA.md
├── README.md
├── Dockerfile
├── docker-compose.yml
├── .github/
│   └── workflows/
│       └── ...
└── ... (other selected configs)
```

`INFRA.md` must include:
- Stack overview
- What's included (file list + purpose)
- Placeholder table (token, meaning, where to set)
- How to apply instructions
- Prerequisites (required tools)
- Notes (caveats, manual steps)

## Open Questions

1. Should the skill attempt to detect and warn about project-specific values that weren't caught by the placeholder replacement (e.g., hardcoded IPs, internal URLs)?
2. Should extracted dependency lockfiles be preserved exactly, or should the skill offer to regenerate them for the new project?
3. Should the skill include a "dry-run" mode that previews what would be extracted without writing files?

---
*Stage: scope-validated*
*Next step: run `aet-pipeline-implement` (single task) or `aet-work` (multi-task queue)*
