# Retro: 2026-06-07 — Document Upload Cascade

## What Went Well

- Root cause was found quickly once we had visibility (storage path mismatch in Laravel 11)
- All stack layers were fixed: frontend (.md support, polling, retry UI), backend (validation, retry endpoint, error logging), AI service (markdown parsing), dev tooling (Makefile queue worker)
- A proper feature test was added that would have caught the bug

## What Went Poorly

### 1. Zero integration test coverage for file upload

There was no `DocumentControllerTest`. The existing `ParseDocumentJobTest` mocked `AIService`, and `AIServiceTest` mocked the HTTP layer. The actual integration — _controller stores file → file lands on disk → job reads it from that path_ — was completely untested. A Laravel 11 filesystem change (`local` disk root: `storage/app/` → `storage/app/private/`) broke the path resolution, and no test failed.

**Impact:** Users saw "Parsing failed" with no useful error. Files were saved but could never be read.

### 2. Error swallowing made debugging impossible

`ParseDocumentJob::handle()` had a `catch (Throwable $e)` block that discarded the actual exception and replaced it with a generic "Parsing failed. Try re-uploading the document." No logging, no stack trace, no exception class. The job completed in ~12ms (too fast for an HTTP call), which should have been a clear signal that something failed before the network layer — but the error message gave no clue.

**Impact:** Both user and agent wasted time guessing. The user had to ask "WTF is happening?"

### 3. Queue worker missing from `make dev`

The `Procfile` declared a queue worker. The `Makefile` `dev` target did not. Uploads dispatched jobs to the database queue, but nothing processed them. The user had to discover this manually.

**Impact:** Documents sat in "Uploading" state forever.

### 4. Laravel 11 filesystem breaking change was invisible

Neither `AGENTS.md` nor `api-conventions.md` mentioned that Laravel 11 changed the `local` disk root. The AIService code used `storage_path("app/{$path}")`, which was correct in Laravel 10 but wrong in Laravel 11.

**Impact:** Silent regression on the most basic file operation.

### 5. Frontend had no real-time status updates

The document list was fetched once on mount. Status changes in the backend (`uploading` → `parsing` → `ready`/`failed`) were invisible until manual refresh.

**Impact:** User had to guess whether processing was done or broken.

## Root Cause Layer Analysis

| Problem                    | Layer                      | Why it was missed                                                                     |
| -------------------------- | -------------------------- | ------------------------------------------------------------------------------------- |
| No upload integration test | `testing-strategy.md`      | Strategy only mentions unit + integration, but has no checklist for file-upload flows |
| Error swallowing           | `api-conventions.md`       | No convention requiring exception logging in queue jobs                               |
| Missing queue worker       | `AGENTS.md` / dev topology | Makefile and Procfile were not kept in sync                                           |
| Laravel 11 fs change       | `api-conventions.md`       | No note on Laravel 11 breaking changes                                                |
| No polling UI              | N/A — ad-hoc omission      | Not a systemic issue, but worth noting                                                |

## Action Items

- [x] Add `DocumentControllerTest` with file storage path assertion (catches path mismatch)
- [x] Fix `ParseDocumentJob` to log and expose real exceptions
- [x] Fix `Makefile` to start queue worker in `make dev`
- [x] Fix `AIService::parseDocument` path to use `app/private/`
- [ ] Update `testing-strategy.md` with file-upload integration test mandate
- [ ] Update `api-conventions.md` with Laravel 11 filesystem note + error handling rules
- [ ] Update `AGENTS.md` with queue worker dev topology check

## Learnings

- **File upload features require an integration test that asserts the file exists at the resolved path.** Mocking the service layer hides storage config mismatches.
- **`catch (Throwable)` in queue jobs is dangerous without `logger()->error()`.** Swallowed exceptions waste engineering time and erode user trust.
- **Dev environment tooling (Makefile, Procfile, docker-compose) must be kept in sync.** Divergence causes silent failures.
- **Framework version bumps need a "breaking changes" checklist in conventions.** Laravel 11 moved the local disk root; this should have been flagged during upgrade.
