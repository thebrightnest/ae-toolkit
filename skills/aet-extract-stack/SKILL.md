---
name: aet-extract-stack
description: |
  Scan an existing software project for its infrastructure, DevOps, and automation
  setup — CI/CD, containers, tooling configs, scripts, dependencies, and environment
  patterns — and extract them into a reusable scaffold package. Produces an INFRA.md
  manifest and a scaffold/ directory containing sanitized, placeholder-filled
  configurations ready to apply to a new project. It is the inverse of aet-setup:
  instead of bootstrapping from scratch, it clones the proven setup from a project
  that already works. Triggers on requests like "extract the infrastructure from
  this project," "clone the DevOps setup," "generate an INFRA.md manifest," or
  "scaffold from existing config."
---

# aet-extract-stack

Extract proven infrastructure from an existing project into a reusable, sanitized scaffold. Reduces setup time for new projects from hours of manual config archaeology to minutes of agent-assisted extraction.

## When to Use

- You have a "golden" reference project and want to replicate its CI/CD, linting, and container setup in a new repo
- You want to clone the DevOps setup from a project you know works well
- You need an `INFRA.md` manifest to understand an inherited project's infrastructure surface
- You are spinning up a PoC and want to reuse proven automation without manually copying configs
- Triggers: "extract the infrastructure from this project," "clone the DevOps setup," "generate an INFRA.md manifest," "scaffold from existing config"

## Hard Gate

**No source code extraction. No live secrets. No automatic application.**

Your only outputs are:

- A `scaffold/` directory containing sanitized, placeholder-filled config files
- An `INFRA.md` manifest documenting every extracted file, placeholder, and application step

If the user asks to copy application source code, `.env` files with real values, or to silently apply the scaffold to a new project, decline and redirect: "This skill extracts infrastructure configs only. Application code and secrets are out of scope. Applying the scaffold is a separate human-reviewed step."

## Planning Lockout

This skill is **extraction-only**. No application source code is written, modified, or deleted in the source project.

- Do not create, edit, or delete application source files in the scanned project
- Do not run application tests, linting, or type-checking in the scanned project
- Do not modify the scanned project's existing configs

## Context

Run `aet context` and parse its JSON for session context (branch, repo
state, AGENTS.md, learnings, active plan/PRD stage); print the stage
banner it emits. Do not ask the user for this context manually.

- `SCAN_TARGET` — the project path to scan (default: current working directory)
- `OUTPUT_DIR` — where to write the scaffold (default: `./scaffold/`)

## Commands

### `extract`

Scan the target project, detect infrastructure artifacts, present a selectable checklist, and extract the selected categories into a sanitized scaffold.

**Procedure:**

1. **Discovery** — Scan the project for infrastructure artifacts across all categories (see Detection Surface below)
2. **Presentation** — Show the user a checklist of detected categories with file counts
3. **Selection** — Let the user select which categories to extract (default: all detected)
4. **Extraction** — Copy selected files to `scaffold/`, replacing project-specific values with placeholders
5. **Secret Sanitization** — Refuse to copy any file containing live secrets; generate `.env.example` from `.env` if needed
6. **Manifest Generation** — Write `scaffold/INFRA.md` with stack overview, file list, placeholder table, and application instructions
7. **Validation** — Verify all placeholders are documented, all links resolve, and no secrets leaked

**Detection Surface:**

| Category             | Paths                                                                                                                                                                    |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| CI/CD                | `.github/workflows/`, `.gitlab-ci.yml`, `.circleci/`, `azure-pipelines.yml`, `Jenkinsfile`, `bitbucket-pipelines.yml`, `.buildkite/`, `appveyor.yml`                     |
| Containers           | `Dockerfile`, `docker-compose.yml`, `docker-compose.*.yml`, `.dockerignore`, `Containerfile`, `kubernetes/`, `k8s/`, `helm/`, `skaffold.yaml`                            |
| Infra-as-Code        | `terraform/`, `*.tf`, `pulumi/`, `serverless.yml`, `sam.yaml`, `cloudformation/`, `ansible/`, `packer/`, `vagrant/`                                                      |
| Environment / Config | `.env*`, `config/`, `*.config.*`, `secrets.*`, `.aws/`, `.kube/`, `infrastructure/`                                                                                      |
| Dependencies         | Lockfiles and manifest files (`package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `poetry.lock`, `Cargo.lock`, `go.sum`, `Gemfile.lock`, `uv.lock`, `requirements*.txt`) |
| Scripts              | `Makefile`, `justfile`, `Taskfile.yml`, `package.json` scripts, `scripts/`, `bin/`, `*.sh`, `*.py`                                                                       |
| Tooling              | `.pre-commit-config.yaml`, linter configs, formatter configs, type-checker configs, security configs                                                                     |
| Documentation        | `README.md` setup sections, `docs/deployment.md`, `docs/ops.md`, `runbooks/`, `ARCHITECTURE.md`                                                                          |

**Placeholder Convention:**

Replace project-specific values with these standard tokens:

| Token                    | Replaces                          |
| ------------------------ | --------------------------------- |
| `{{PROJECT_NAME}}`       | App name, service name, repo name |
| `{{ORG_NAME}}`           | GitHub org, DockerHub namespace   |
| `{{DOMAIN}}`             | Production domain, API host       |
| `{{APP_PORT}}`           | Primary application port          |
| `{{DB_NAME}}`            | Database name                     |
| `{{AWS_REGION}}`         | AWS region                        |
| `{{CONTAINER_REGISTRY}}` | Docker image registry host        |
| `{{SECRET}}`             | Generic secret placeholder        |

Custom descriptive placeholders are permitted for values that don't fit the standard set (e.g., `{{REDIS_CLUSTER_URL}}`). Document every custom placeholder in `INFRA.md`.

**Secret Detection — Files that must NEVER be copied with live values:**

- `.env`, `.env.local`, `.env.production`, `.env.development`
- `secrets.yml`, `secrets.yaml`, `secrets.json`
- `kubeconfig`, `*.kubeconfig`
- Service account keys: `*.json` in `.aws/`, `credentials`, `*.pem`, `*.key`
- Any file containing `password=`, `api_key=`, `secret=`, `token=` with actual values

If `.env.example` does not exist, generate one from `.env` by copying keys and replacing all values with `{{PLACEHOLDER}}`.

**Extraction Rules:**

- Preserve directory structure relative to project root
- Strip comments that contain internal URLs, IP addresses, or hostnames unless they are generic
- Replace hardcoded project names, org names, domains, and ports with placeholders
- Keep dependency lockfiles exactly (they are reproducible and contain no secrets)
- Do not copy files larger than 1MB without explicit user confirmation
- If a file contains both config and secrets, extract only the config keys and replace secret values with placeholders

**Nothing-Found Handling:**

If zero infrastructure artifacts are detected across all categories:

1. Halt extraction
2. Print: `"No infrastructure artifacts detected in {path}. The project may be a library, a fresh repo, or use infrastructure-as-a-service with no local config."`
3. Suggest: "Run aet-setup to bootstrap infrastructure from scratch instead."

### `dry-run`

Preview what would be extracted without writing any files.

**Procedure:**

1. Run the discovery step of `extract`
2. Present the checklist to the user
3. Print a summary of what would be extracted, what placeholders would be applied, and what secrets would be redacted
4. Do not write any files

## Output Structure

```
scaffold/
├── INFRA.md
├── Dockerfile
├── docker-compose.yml
├── .github/
│   └── workflows/
│       └── ...
├── scripts/
│   └── ...
├── .pre-commit-config.yaml
├── Makefile
└── ... (other selected configs)
```

`INFRA.md` must include:

- Stack overview (what was detected and why)
- What's included (file list + purpose for each)
- Placeholder table (token, meaning, where to set it)
- How to apply (step-by-step instructions for applying to a new project)
- Prerequisites (required tools)
- Notes (caveats, manual steps, known limitations)

## Completion Protocol

After `extract` completes and all validation passes:

1. Print a summary:

   ```
   ✓ Extraction complete.

   Source: {source_path}
   Output: {output_path}
   Categories extracted: {list}
   Files written: {count}
   Placeholders used: {count}
   Secrets redacted: {count}

   Next step: Review scaffold/INFRA.md, then copy scaffold/ to your new project.
   ```

2. If the user provided a destination path, copy the scaffold there and confirm.

## Key Principles

- **Extraction, not invention** — copy what exists; do not research best practices or invent new configs
- **Secrets are radioactive** — one leaked secret ruins the extraction's trustworthiness; be paranoid
- **Placeholders are documentation** — every placeholder must be explained in INFRA.md so a human knows what to fill in
- **Self-documenting output** — the scaffold must be usable by someone who has never seen the source project
- **Agent-agnostic** — the skill produces files and instructions, not agent-specific commands
