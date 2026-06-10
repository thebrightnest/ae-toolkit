# Retro: 2026-06-07 — Login / Password Seeder Bug

## What Went Well

- Pinpointed the factory double-hashing issue quickly (`hashed` cast + `Hash::make` in factory).
- Identified Sanctum session misconfiguration through direct HTTP testing (curl → stack trace).
- Minimal fixes: two small config/code changes, no refactoring.

## What Went Poorly

### 1. Double-hashed password in factory

- `UserFactory` passed `Hash::make('password')` to a model that casts `password` => `hashed`.
- Laravel 11's `hashed` cast hashes on assignment, so the stored value was a hash-of-a-hash.
- `Auth::attempt()` in tinker returned `true`, but via HTTP the password never matched because the bcrypt verification compared plaintext against a double-hash.
- This is a classic Laravel 11 migration pitfall.

### 2. Sanctum stateful domains mismatched dev ports

- Vite runs on `localhost:5183` (per `vite.config.ts` + Makefile).
- `.env` had `SANCTUM_STATEFUL_DOMAINS=localhost:5173,localhost:8000` — neither matching the actual frontend nor API port.
- `EnsureFrontendRequestsAreStateful` did not add session middleware for requests from `localhost:5183`.
- `Auth::attempt()` succeeded (credentials valid), but `$request->session()->regenerate()` threw `Session store not set on request.`
- The frontend catch block shows **"Invalid email or password" for ANY error**, masking the real 500 as a credential failure.

### 3. Frontend swallowed the real error

- `LoginPage.tsx` catch block: `setError('Invalid email or password.')` — no inspection of `status` or `message`.
- This sent us chasing a password problem when the real issue was a session/server error.

## Action Items

- [x] Fix `UserFactory` to pass plaintext password (let `hashed` cast do the work).
- [x] Derive `FRONTEND_URL` into Sanctum `stateful` domains automatically.
- [ ] Add frontend error-handling guardrail: distinguish 401 (bad creds) from 419/500 (session/server) in login UI.
- [ ] Add Laravel auth setup validation to onboarding/seeder docs.

## Learnings

```jsonl
{"date":"2026-06-07","problem":"UserFactory double-hashed password because it used Hash::make() while User model casts password to 'hashed'","layer":"AGENTS.md / api-conventions.md","fix":"Factory now passes plaintext 'password'; model cast handles hashing","prevents":"Login failures on seeded test users in Laravel 11+"}
{"date":"2026-06-07","problem":"Sanctum stateful domains did not include actual Vite dev port (5183), so session middleware was skipped and login threw 500 masked as 'invalid password' by frontend","layer":"AGENTS.md / setup conventions","fix":"sanctum.php now auto-derives FRONTEND_URL into stateful domains","prevents":"Session auth breaking silently when dev ports change"}
{"date":"2026-06-07","problem":"Frontend login catch block showed generic 'Invalid email or password' for all errors, hiding server/session issues","layer":"reference/testing-strategy.md or AGENTS.md guardrails","fix":"TBD — update LoginPage to check status code before showing generic message","prevents":"Misdiagnosis of server errors as credential errors"}
```
