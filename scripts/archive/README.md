# Archived one-off migrations

This directory holds one-off data migrations that have already been applied to
this repository. They are kept for reference and for replay against older
clones or downstream projects, but they are not part of normal maintenance.

| Script | Shipped in | Purpose |
| ------ | ---------- | ------- |
| `migrate-plans-to-frontmatter.py` | `v0.7.0` | Migrate `docs/plans/*.md` files to the YAML-frontmatter contract (`id`, `blocked_by`, `size`). |
| `migrate-telemetry-slugs.py` | `v1.0.0` | Rename historical telemetry/report archive slugs after the worktree-based slug scheme landed. |

Run them from this directory if you need to replay a migration:

```bash
python3 scripts/archive/migrate-plans-to-frontmatter.py --plans-dir docs/plans --dry-run
python3 scripts/archive/migrate-telemetry-slugs.py OLD_SLUG NEW_SLUG --dry-run
```
