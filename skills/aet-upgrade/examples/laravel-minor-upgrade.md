# Example: Laravel 10.x → 11.x Upgrade Plan

## Context

- **Dependency:** `laravel/framework`
- **Current:** `^10.0`
- **Target:** `^11.0`
- **Package manager:** Composer

## Breaking Changes Enumerated

### 1. `hashed` cast double-hashing

**Description:** Laravel 11 changed the `hashed` cast behavior. In Laravel 10, applying the `hashed` cast to an already-hashed value would not re-hash it. In Laravel 11, the `hashed` cast unconditionally hashes the value on set, causing double-hashing if the input is already a bcrypt hash.

**Grep evidence:**

```bash
$ rg "hashed" app/Models/ --type php
app/Models/User.php
15:    protected $casts = [
16:        'password' => 'hashed',
17:    ];
```

**Risk:** **High** — `User` model uses `hashed` cast on `password`. If any code path sets an already-hashed password (e.g., social login, password reset token flow), the password will be double-hashed and authentication will fail silently.

**Mitigation:**

- Audit all code paths that set `User::password`
- Add an explicit check: only hash if the value is not already a bcrypt hash (starts with `$2y$`)
- Add an integration test that sets an already-hashed password and verifies authentication still works

### 2. `storage/app/private` path move

**Description:** Laravel 11 moved the default private storage path from `storage/app` to `storage/app/private`. Any code referencing `storage_path('app/')` for private files will now resolve to a different location.

**Grep evidence:**

```bash
$ rg "storage_path\('app" app/ config/ --type php
app/Services/ExportService.php
42:    $path = storage_path('app/exports/' . $filename);

config/filesystems.php
32:    'local' => [
33:        'root' => storage_path('app'),
34:    ],
```

**Risk:** **Medium** — `ExportService` references `storage_path('app/exports/')`. After upgrade, this will still work because `storage/app` still exists, but new private files should use `storage_path('app/private/')`. The `config/filesystems.php` `local` disk root should be reviewed.

**Mitigation:**

- Update `config/filesystems.php` `local` disk root to `storage_path('app/private')` if private files are the intent
- Verify `ExportService` behavior — if exports are meant to be private, update the path; if public, move to `storage/app/public`

## Smoke Results

- **Before upgrade:** Smoke passed (2024-06-01)
- **After upgrade:** Pending

## Rollback

Revert `composer.json`, `composer.lock`, and any code changes. Re-run smoke to confirm baseline restoration.
