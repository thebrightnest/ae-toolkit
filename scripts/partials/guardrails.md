### Forbidden

- Never modify a `.skill` file by hand — always run `make package` after editing a skill directory
- Never delete or rename a skill directory without updating README.md skill table
- Never commit the `content/` directory (it is gitignored; used for local scratch)
- Never add a new skill without `examples/` and `references/` subdirectories
- Never write skill instructions that assume a specific AI agent (keep them agent-agnostic)
- Never introduce new skill patterns without checking `docs/CONVENTIONS.md` first

### Mandatory

- Always run `make validate` before claiming any skill edit is complete
- Always update `docs/CONVENTIONS.md` if you introduce a new skill pattern
- Always keep `SKILL.md` under 400 lines; move deep detail to `references/`
- Always use YAML frontmatter with `name` and `description` in every new SKILL.md
- Always ensure `description` explicitly states when to trigger the skill
- Always run `make package` after editing skills to regenerate `.skill` files
- Always add an ADR in `docs/adr/` for structural changes to the toolkit itself
