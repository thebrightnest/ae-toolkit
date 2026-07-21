# aet-extract-stack References

## Placeholder Naming Conventions

Use these rules when creating custom placeholders beyond the standard set.

### Standard Tokens

| Token                    | Replaces                                   | Example match                                                          |
| ------------------------ | ------------------------------------------ | ---------------------------------------------------------------------- |
| `{{PROJECT_NAME}}`       | App name, service name, repo name          | `my-awesome-api`, `webapp`                                             |
| `{{ORG_NAME}}`           | GitHub org, DockerHub namespace, npm scope | `acme-corp`, `@acme`                                                   |
| `{{DOMAIN}}`             | Production domain, API host, base URL      | `api.example.com`, `https://app.example.com`                           |
| `{{APP_PORT}}`           | Primary application port                   | `3000`, `8080`, `5000`                                                 |
| `{{DB_NAME}}`            | Database name                              | `mydb_prod`, `app_database`                                            |
| `{{AWS_REGION}}`         | AWS region                                 | `us-east-1`, `eu-west-2`                                               |
| `{{CONTAINER_REGISTRY}}` | Docker image registry host                 | `ghcr.io`, `docker.io`, `123456789012.dkr.ecr.us-east-1.amazonaws.com` |
| `{{SECRET}}`             | Generic secret placeholder                 | Any API key, password, token                                           |

### Custom Placeholder Rules

1. **Descriptive, not generic** — `{{REDIS_CLUSTER_URL}}` is better than `{{VALUE_1}}`
2. **Upper snake case** — `{{MY_PLACEHOLDER}}` not `{{myPlaceholder}}`
3. **Category prefix for clarity** — `{{DB_HOST}}`, `{{CACHE_PORT}}`, `{{SMTP_USER}}`
4. **Document every custom token** in INFRA.md with: what it replaces, where it appears, and what the user should set it to

### Values That Should Always Be Replaced

- Hardcoded IP addresses (except `127.0.0.1`, `0.0.0.0`, `::1`)
- Internal hostnames and URLs
- Project-specific names in labels, comments, and metadata
- Hardcoded ports (except well-known ports like 80, 443, 22, 5432 when used generically)
- Email addresses in config files
- Slack webhook URLs
- Any value that would cause a conflict if applied to a different project

### Values That Should NOT Be Replaced

- Well-known defaults (`node:18-alpine`, `python:3.11-slim`)
- Standard paths (`/usr/src/app`, `/app`, `/var/log`)
- Common environment variable names (`NODE_ENV`, `PORT`, `DATABASE_URL` as a key)
- Boolean flags and numeric thresholds that are not project-specific
- Standard Makefile targets (`build`, `test`, `lint`, `clean`)

---

## Secret Detection Patterns

Files that must **never** be copied with live values.

### Blocked File Names (exact match)

```
.env
.env.local
.env.production
.env.development
.env.staging
.env.test
secrets.yml
secrets.yaml
secrets.json
kubeconfig
*.kubeconfig
credentials
*.pem
*.key
*.p12
*.pfx
id_rsa
id_ed25519
.htpasswd
```

### Blocked Directory Names

```
.aws/
.kube/
.ssh/
secrets/
credentials/
```

### Content Patterns (if found, replace value with `{{SECRET}}`)

```
password=...
api_key=...
apikey=...
secret=...
secret_key=...
private_key=...
token=...
auth_token=...
access_token=...
refresh_token=...
bearer_token=...
aws_access_key_id=...
aws_secret_access_key=...
```

### Handling `.env` Files

| Scenario                         | Action                                                                                        |
| -------------------------------- | --------------------------------------------------------------------------------------------- |
| `.env.example` exists            | Copy `.env.example` directly (already sanitized)                                              |
| `.env` exists, no `.env.example` | Generate `.env.example` from `.env`: copy all keys, replace all values with `{{PLACEHOLDER}}` |
| Neither exists                   | Skip the Environment / Config category for this file                                          |

---

## Category-Specific Stripping Rules

### CI/CD Configs

- Replace project names in workflow names and job names
- Replace org names in `uses: org/action@ref` only if the org is project-specific (keep `actions/checkout`)
- Replace container image names that include the project or org name
- Replace environment names that are project-specific
- Keep standard GitHub Actions (`actions/checkout`, `actions/setup-node`, etc.) unchanged
- Replace hardcoded branch protection rules that reference project-specific teams

### Docker & Compose

- Replace `LABEL` values that contain project metadata
- Replace `EXPOSE` port only if it's the app's custom port (keep 80, 443, 8080 as generic)
- Replace image names in `FROM` that include the project org
- Replace service names in `docker-compose.yml` only if they are project-specific (keep generic names like `db`, `cache`, `app`)
- Replace volume names that include the project name
- Replace network names that include the project name

### Infra-as-Code

- Replace resource names that include the project name
- Replace backend bucket/key paths in Terraform
- Replace project IDs in GCP, Azure, or AWS configs
- Replace region only if it's not a well-known default (use `{{AWS_REGION}}` for any AWS region)
- Keep module sources from public registries unchanged

### Scripts & Makefiles

- Replace project-specific target names (keep standard targets: `build`, `test`, `lint`, `format`, `clean`, `install`, `dev`)
- Replace project names in echo statements and log messages
- Replace paths that include the project name
- Keep standard shell patterns and utilities unchanged

### Tooling Configs

- Replace project names in tool config descriptions and titles
- Replace org-specific URLs in tool configs
- Keep standard rule sets and presets unchanged
- Replace ignore patterns that include project-specific paths

### Documentation

- Replace internal URLs and domains
- Replace project names in setup instructions
- Replace org-specific contact information
- Keep generic instructions and standard commands unchanged
- Add a header noting the document was extracted and may need updates
