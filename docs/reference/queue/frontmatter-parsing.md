# Plan Frontmatter Parsing

Plan files use YAML frontmatter between leading `---` fences. The
`aet.plan_parser.parse_frontmatter` function is the canonical reader. The keys a
plan author sets are documented in
[`skills/aet-plan/references/work-queue-format.md`](../../../skills/aet-plan/references/work-queue-format.md#plan-frontmatter-keys).

## PyYAML shim

`parse_frontmatter` delegates to `yaml.safe_load`.  Because the existing plan
corpus uses Markdown backticks and unquoted colons in prose fields such as
`security_review_reason`, a small preprocessor quotes scalar values that would
otherwise be misinterpreted as YAML structure.

Values are quoted when they contain characters that plain YAML scalars cannot
contain, including `:`, `` ` ``, `#`, `|`, `>`, `%`, `@`, `!`, `&`, `*`, `{`,
`}`, `[`, `]`, and `,`.  Already-quoted values and inline flow collections
(`[...]`, `{...}`) are left untouched.

## Accepted/rejected-input differences versus the hand-rolled parser

| Input | Hand-rolled | PyYAML + shim | Notes |
| ----- | ----------- | ------------- | ----- |
| `key: value` | string | string | unchanged |
| `key: 1` | `"1"` | `1` | typed; intake validation rejects non-string ids/sizes |
| `key: true` | `"true"` | `True` | typed; intake validation rejects non-string routing keys |
| `key:` | `[]` | `None` | only `blocked_by: None` is normalized back to `[]` |
| `key: \| multi` | first line or `\|` | full block scalar | PyYAML supports block scalars |
| `key:\n  - a\n  - b` | list of strings | list of strings | unchanged |
| unclosed quote in inline list | raw string | raw string (quoted by shim) | downstream validation rejects non-list |
| top-level list frontmatter | partial parse | `{}` | treated as missing frontmatter |

## Failure mode

If the frontmatter fence is missing, unclosed, or cannot be normalized into
valid YAML, `parse_frontmatter` returns an empty dict.  Downstream intake
validation then reports the missing/invalid fields.
