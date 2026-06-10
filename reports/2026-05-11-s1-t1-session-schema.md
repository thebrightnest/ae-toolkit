# Retro: S1-T1 Session Messages Schema

## What Happened

Implemented `session_messages` table, FTS5 virtual table, and two new repositories
(`trackedSessionRepository`, `sessionMessageRepository`) per the S1-T1 plan. Three
issues surfaced during implementation and review that were not anticipated by the plan.

## Root Cause

### Issue 1 — FK constraint omitted from schema and migration

The plan described the FK in prose ("FK → tracked_sessions.session_id") and in the
risks table, but the Architecture code block showed `session_id TEXT NOT NULL` without
a `REFERENCES` clause. The implement agent followed the code block. The FK was caught
during review and fixed.

**Root cause**: Plan code blocks are treated as authoritative by the implement agent.
When a constraint is described in prose but absent from the code block, it gets missed.

### Issue 2 — Drizzle raw SQL queries return snake_case column names

The plan recommended `db.all(sql\`SELECT \* FROM session_messages WHERE rowid IN ...\`)` for FTS5 search. At runtime, this returns raw SQLite column names (`session_id`, `created_at`) rather than Drizzle's camelCase mappings (`sessionId`, `createdAt`). The TypeScript type was wrong on all rows returned by `searchMessages`, causing a test failure on first run.

Required adding an unplanned `RawSessionMessage` interface and `mapRow()` function.

**Root cause**: No documentation anywhere in `.agents/` about this Drizzle behavior.
It's non-obvious because ORM queries map correctly — only raw `sql` template queries bypass the mapping.

### Issue 3 — `npm run db:generate` requires a TTY

The plan step "Run `npm run db:generate`" fails in Claude Code's shell environment with
`Interactive prompts require a TTY terminal`. The `drizzle-kit generate` command prompts
for conflict resolution when it detects schema ambiguity, which requires an interactive
terminal.

Workaround used: `npx drizzle-kit generate --custom --name="..."` to create an empty
migration, then fill it manually.

**Root cause**: Plan template doesn't document this known limitation of drizzle-kit.

## What Went Well

- FTS5 virtual table, triggers, and indexes implemented correctly on first try
- `searchMessages` FTS query pattern was correct (parameterized, no injection risk)
- Review caught the FK issue before merge
- Validator bug (false-positive "table recreation" warning on all migrations) was
  identified and fixed as part of this cycle

## What Could Be Better

- Plan code blocks should be complete — constraints described in prose must also appear
  in the code
- Drizzle raw SQL behavior (snake_case column names) should be documented before writing
  any repository that uses FTS5 or custom SQL
- `db:generate` TTY limitation should be in the reference docs so plans can specify
  the correct command

## Action Items

| Action                                                  | Owner  | Due |
| ------------------------------------------------------- | ------ | --- |
| Add "Raw SQL column mapping" section to architecture.md | system | now |
| Add `db:generate` TTY workaround to architecture.md     | system | now |
| Add FK code-block completeness note to plan-template.md | system | now |

## Rules Updated

- `.agents/reference/architecture.md` — added Drizzle raw SQL and db:generate sections
- `.agents/templates/plan-template.md` — added FK completeness note

## Learning

Three learnings added to `.agents/learnings.jsonl`.
