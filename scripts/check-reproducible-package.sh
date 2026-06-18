#!/usr/bin/env bash
# Reproducibility check for .skill packaging.
# Runs `make package` twice and asserts that no .skill archive bytes change.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if ! command -v shasum >/dev/null 2>&1 && ! command -v sha256sum >/dev/null 2>&1; then
  echo "❌ Missing shasum or sha256sum utility"
  exit 1
fi

checksum() {
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 *.skill
  else
    sha256sum *.skill
  fi
}

if ! ls *.skill >/dev/null 2>&1; then
  echo "❌ No .skill files found to check"
  exit 1
fi

echo "=== Reproducible Packaging Check ==="
echo "Running first package pass..."
make package >/dev/null
FIRST_SUMS=$(checksum | sort)

echo "Running second package pass..."
make package >/dev/null
SECOND_SUMS=$(checksum | sort)

if [ "$FIRST_SUMS" = "$SECOND_SUMS" ]; then
  echo "✅ .skill archives are byte-identical across consecutive packaging runs"
  exit 0
else
  echo "❌ .skill archives changed between packaging runs:"
  diff <(echo "$FIRST_SUMS") <(echo "$SECOND_SUMS") || true
  exit 1
fi
