# UI / CSS Completeness Check

Mechanical procedure for verifying that every custom `className` used in renderer components has a corresponding CSS definition.

## When to Run

Run this check during `aet-review` whenever the diff touches files in a renderer, UI, or frontend component directory (e.g., `src/renderer/`, `src/components/`, `app/`).

## Procedure

### 1. Identify Modified Renderer Files

```bash
# List new/modified TSX/JSX/Vue/Svelte files in the diff
git diff --name-only HEAD~1 | grep -E '\.(tsx|jsx|vue|svelte)$'
```

### 2. Extract className Values

```bash
# Extract quoted strings from className/class attributes
git diff HEAD~1 -- '*.tsx' '*.jsx' '*.vue' '*.svelte' | \
  grep -oE '(className|class)="[^"]+"' | \
  sed 's/.*="//;s/"$//' | \
  tr ' ' '\n' | \
  sort -u
```

For CSS-modules-style object references (`styles.foo`), also scan for:

```bash
git diff HEAD~1 -- '*.tsx' '*.jsx' | grep -oE 'styles\.[a-zA-Z0-9_-]+' | sed 's/styles\.//' | sort -u
```

### 3. Filter Known Global Classes

Remove framework globals and common utility classes that are not project-specific:

**Default filter list:**

```text
btn
icon-btn
spin
container
row
col
flex
grid
hidden
visible
d-none
d-block
d-flex
justify-content-start
justify-content-center
justify-content-end
align-items-start
align-items-center
align-items-end
mt-1 mt-2 mt-3 mt-4 mt-5
mb-1 mb-2 mb-3 mb-4 mb-5
ml-1 ml-2 ml-3 ml-4 ml-5
mr-1 mr-2 mr-3 mr-4 mr-5
p-1 p-2 p-3 p-4 p-5
px-1 px-2 px-3 px-4 px-5
py-1 py-2 py-3 py-4 py-5
m-1 m-2 m-3 m-4 m-5
mx-auto
w-100
h-100
text-left
text-center
text-right
small
large
active
disabled
readonly
focus
hover
```

Store a project-specific filter in `.agents/reference/css-global-classes.txt` and use it:

```bash
grep -vFf .agents/reference/css-global-classes.txt extracted-classes.txt > custom-classes.txt
```

### 4. Verify Against Stylesheets

```bash
# Find all stylesheet files
STYLES=$(find src -type f \( -name '*.css' -o -name '*.scss' -o -name '*.sass' -o -name '*.less' \))

# Check each custom class
while read -r cls; do
  if ! grep -rq "\.$cls" $STYLES; then
    echo "MISSING: .$cls"
  fi
done < custom-classes.txt
```

### 5. Report Findings

- **fix-now** — any custom class not found in stylesheets
- **flag-for-human** — CSS module imports that cannot be statically resolved

## Adapting to Different CSS Flavors

| Flavor                          | Adaptation                                                                                             |
| ------------------------------- | ------------------------------------------------------------------------------------------------------ |
| **Plain CSS**                   | Search `.css` files directly for `.className {`                                                        |
| **SCSS / Sass**                 | Search `.scss`/`.sass` files; class may be nested under parent selectors                               |
| **Less**                        | Search `.less` files; same nesting caveat as SCSS                                                      |
| **CSS Modules**                 | Verify the imported `.module.css` file defines the class; skip global stylesheet search                |
| **Tailwind**                    | Not applicable — classes are utility-generated; skip this lens unless custom `@apply` classes are used |
| **Styled-components / Emotion** | Not applicable — styles are co-located; skip this lens                                                 |

## Notes

- This is **static analysis**, not runtime verification. It catches missing definitions but not visual regressions.
- If Playwright or another visual-regression tool is configured, run it as a follow-up to catch layout or styling bugs that static analysis misses.
- Keep the project-specific global-classes filter file under version control so the lens stays accurate as the project evolves.
