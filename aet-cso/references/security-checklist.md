# Security Checklist by Category

## Secrets & Credentials

- [ ] No API keys, tokens, or passwords in code
- [ ] No private keys or certificates committed
- [ ] No hardcoded database connection strings with credentials
- [ ] No `.env` files or config files with secrets
- [ ] Environment variables used for all sensitive config

## Injection Risks

- [ ] All SQL queries use parameterized statements
- [ ] No string concatenation in SQL/query builders
- [ ] No user input passed directly to `exec()`, `eval()`, `system()`
- [ ] No user-controlled file paths without sanitization
- [ ] NoSQL queries validate object shapes before execution

## Authentication & Authorization

- [ ] New endpoints have authentication checks (if the app requires auth)
- [ ] Authorization is server-side, not client-side
- [ ] No insecure direct object references (IDs are validated)
- [ ] Session/token handling follows project conventions
- [ ] CORS policies are restrictive, not wildcard

## LLM Trust Boundaries

- [ ] User input is validated/sanitized before reaching prompt templates
- [ ] No user-controlled strings used as system prompts
- [ ] LLM outputs are treated as untrusted (validated before use)
- [ ] Prompt templates are static, not dynamically constructed from user input

## Dependencies

- [ ] New dependencies are from reputable sources
- [ ] Updated dependencies checked for known CVEs
- [ ] No unnecessary dependencies added
- [ ] Lockfile is updated and committed

## Data Handling

- [ ] Sensitive data is encrypted at rest (if applicable)
- [ ] PII is handled according to project standards
- [ ] Input validation occurs at API boundaries
- [ ] Error messages don't leak internal details (stack traces, DB schemas)
