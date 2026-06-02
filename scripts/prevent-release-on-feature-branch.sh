#!/usr/bin/env bash
# Reject chore(release) commits on non-main branches

branch=$(git rev-parse --abbrev-ref HEAD)
if [ "$branch" = "main" ]; then
    exit 0
fi

# Check commit message (commit-msg hook receives the message file as argument)
if [ -n "$1" ] && [ -f "$1" ]; then
    if grep -qE '^chore\(release\)' "$1"; then
        echo "❌ chore(release) commits are not allowed on feature branches." >&2
        echo "   Current branch: $branch" >&2
        exit 1
    fi
fi

# Check staged files for VERSION bumps or release commits (pre-commit hook)
if git diff --cached --name-only | grep -qE '^VERSION$|^CHANGELOG'; then
    echo "❌ VERSION and CHANGELOG modifications should not be committed on feature branches." >&2
    echo "   Current branch: $branch" >&2
    exit 1
fi

exit 0
