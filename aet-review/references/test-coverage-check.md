# Test Coverage Completeness Check

Mechanical procedure for verifying that every new source file in the diff is referenced by at least one test file.

## When to Run

Run this check during `aet-review` whenever the diff adds new source files (not config, types, migrations, or seeds).

## Procedure

### 1. Identify New Source Files

```bash
# List files added by the diff
git diff --name-status HEAD~1 | grep '^A' | cut -f2 > added-files.txt

# Filter out non-source files: tests, configs, migrations, seeds, type-only definitions
cat added-files.txt | \
  grep -vE '\.(test|spec)\.' | \
  grep -vE '(config|rc)\.' | \
  grep -vE '^(database/migrations|db/migrate|seeders|database/seeders)/' | \
  grep -vE '\.d\.ts$' | \
  grep -vE 'types?\.ts$' > source-files.txt
```

Apply judgment: a file exporting only interfaces or constants does not require a test; a file containing business logic, a controller, an observer, or a job does.

### 2. Check for Test References

For each source file, search the codebase for test files that import or reference it:

```bash
while read -r f; do
  basename=$(basename "$f" | sed 's/\.[a-zA-Z0-9]*$//')
  if ! grep -rlE "(from ['\"].*/$basename['\"]|import.*$basename|require.*$basename|$basename)" \
       --include='*.test.*' --include='*.spec.*' . > /dev/null 2>&1; then
    echo "MISSING: $f — no test references found"
  fi
done < source-files.txt
```

### 3. Check for API Boundary Tests (Vertical Slices)

If the diff adds both a new backend route/controller **and** new frontend API client code:

```bash
# Detect backend endpoint addition
git diff --name-status HEAD~1 | grep -qE '(routes|controllers|api|handlers)/' && BACKEND=1

# Detect frontend API client addition
git diff --name-status HEAD~1 | grep -qE '(api|clients|services|fetch|http)/' && FRONTEND=1

if [ -n "$BACKEND" ] && [ -n "$FRONTEND" ]; then
  if ! grep -rlE '(msw|nock|Http::fake|mirage|intercept|boundary)' \
       --include='*.test.*' --include='*.spec.*' . > /dev/null 2>&1; then
    echo "MISSING: API boundary test — backend endpoint + frontend client with no boundary test"
  fi
fi
```

### 4. Report Findings

- **fix-now** — any new source file with no test reference
- **fix-now** — vertical slice with backend endpoint + frontend client but no API boundary test
- **flag-for-human** — file type judgment calls (e.g., a utility with unclear test boundaries)
