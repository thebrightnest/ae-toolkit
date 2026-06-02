#!/usr/bin/env bash
set -euo pipefail

# Hook behavior tests for AE Toolkit repository hooks.
# Tests pre-push deletion short-circuit and pre-commit quality checks.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FAILED=0
PASS=0

cleanup() {
  if [ -n "${TMPDIR:-}" ] && [ -d "$TMPDIR" ]; then
    rm -rf "$TMPDIR"
  fi
}
trap cleanup EXIT

assert() {
  local msg="$1"
  shift
  if "$@"; then
    echo "  ✓ $msg"
    ((PASS+=1))
  else
    echo "  ✗ $msg"
    ((FAILED+=1))
  fi
}

TMPDIR=$(mktemp -d -t aet-hooks-test-XXXXXX)

# ---------------------------------------------------------------------------
# pre-push deletion short-circuit
# ---------------------------------------------------------------------------

echo "TEST: pre-push short-circuits when all refs are deletions"
output=$(echo "0000000000000000000000000000000000000000 0000000000000000000000000000000000000000 refs/heads/test-branch" | bash "$SCRIPT_DIR/hooks/pre-push" origin https://github.com/test/repo 2>&1) && ec=0 || ec=$?
assert "exits 0 on all-deletion push" [ "$ec" -eq 0 ]
assert "prints skip message" grep -qi "deletion" <<< "$output"

# ---------------------------------------------------------------------------
# pre-push runs gate on normal push
# ---------------------------------------------------------------------------

echo "TEST: pre-push runs coverage gate when commits are being pushed"

# Mock make so we don't run the full (slow) validation suite
mkdir -p "$TMPDIR/bin"
cat > "$TMPDIR/bin/make" <<'EOF'
#!/usr/bin/env bash
echo "MOCK_MAKE: $*"
exit 0
EOF
chmod +x "$TMPDIR/bin/make"

output=$(echo "abc123def456789012345678901234567890abcd 0000000000000000000000000000000000000000 refs/heads/feature" | PATH="$TMPDIR/bin:$PATH" bash "$SCRIPT_DIR/hooks/pre-push" origin https://github.com/test/repo 2>&1) && ec=0 || ec=$?
assert "exits 0 with mocked gate" [ "$ec" -eq 0 ]
assert "runs coverage gate" grep -qi "coverage gate\|MOCK_MAKE" <<< "$output"

rm -f "$TMPDIR/bin/make"

# ---------------------------------------------------------------------------
# pre-commit runs quality checks
# ---------------------------------------------------------------------------

echo "TEST: pre-commit runs quality checks"

# Mock pre-commit so the test is deterministic
cat > "$TMPDIR/bin/pre-commit" <<'EOF'
#!/usr/bin/env bash
echo "FAKE_PRECOMMIT: $*"
exit 0
EOF
chmod +x "$TMPDIR/bin/pre-commit"

output=$(PATH="$TMPDIR/bin:$PATH" bash "$SCRIPT_DIR/hooks/pre-commit" 2>&1) && ec=0 || ec=$?
assert "exits 0 with mocked pre-commit" [ "$ec" -eq 0 ]
assert "runs pre-commit checks" grep -q "FAKE_PRECOMMIT" <<< "$output"

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

echo ""
echo "============================================"
echo "Hook Tests: $PASS passed, $FAILED failed"
echo "============================================"

if [ "$FAILED" -gt 0 ]; then
  exit 1
fi
