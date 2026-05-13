# Plan: Fix aet-work SKILL.md Invalid YAML Frontmatter

## Context

The `aet-work/SKILL.md` frontmatter contains invalid YAML. The `description` field uses a plain scalar with `Triggers on:` followed by a space and double-quoted strings. In YAML, a colon followed by a space inside a plain scalar is interpreted as a mapping key separator, causing strict YAML parsers (e.g., PyYAML, Kimi Code's loader) to fail with:

```
mapping values are not allowed here
  in "<unicode string>", line 3, column 190:
     ...  check what's ready. Triggers on: "run the queue", "pick next
                                         ^
```

This causes Kimi Code to silently skip the skill entirely. Claude Code recognizes it because it likely uses a more lenient (regex-based) frontmatter parser.

Sibling skill `aet-plan` parses fine because it says `Triggers on requests like` — no colon+space inside the plain scalar.

## Tasks

1. **Fix frontmatter scalar** — Change `Triggers on:` to `Triggers on` (remove the colon) in `aet-work/SKILL.md` line 3. Size: **S**
2. **Regenerate `.skill` artifact** — Run `make package` to rebuild `aet-work.skill`. Size: **S**
3. **Validate** — Run `make validate` to ensure lint, formatting, and skill-structure checks pass. Size: **S**
4. **Verify YAML parses** — Confirm the fixed frontmatter loads cleanly with a strict YAML parser. Size: **S**

## Dependencies

- None — all tasks are independent and can run sequentially.

## Validation Steps

- [ ] `make validate` passes (lint, format-check, skill-structure validator)
- [ ] `aet-work/SKILL.md` frontmatter loads without errors in strict YAML parser
- [ ] `aet-work.skill` zip archive is regenerated and contains updated `SKILL.md`

## Rollback Plan

```bash
git checkout -- aet-work/SKILL.md aet-work.skill
```

Or revert the commit if already committed.

---

_Stage: implemented_
_Next step: run `aet-qa`_
