#!/usr/bin/env bash
#
# release-prep.sh — Analyze commits since last tag and suggest version bumps.
# Part of aet-release-prep skill for the AE Toolkit.
#
# Outputs JSON with last tag, commits, version info, and suggested bump.

set -euo pipefail

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

run_git() {
  git "$@" 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# Version detection
# ---------------------------------------------------------------------------

detect_version_source() {
  local src="" ver=""

  if [[ -f package.json ]]; then
    ver=$(grep -m1 '"version"' package.json 2>/dev/null | sed -E 's/.*"version".*"([^"]+)".*/\1/')
    if [[ -n "$ver" ]]; then
      printf '%s\t%s\n' "package.json" "$ver"
      return
    fi
  fi

  if [[ -f VERSION ]]; then
    ver=$(head -n1 VERSION 2>/dev/null | tr -d '[:space:]')
    if [[ -n "$ver" ]]; then
      printf '%s\t%s\n' "VERSION" "$ver"
      return
    fi
  fi

  ver=$(run_git describe --tags --abbrev=0 2>/dev/null || true)
  if [[ -n "$ver" ]]; then
    printf '%s\t%s\n' "git-tag" "$ver"
    return
  fi

  printf '%s\t%s\n' "none" "0.0.0"
}

# ---------------------------------------------------------------------------
# Commit classification
# ---------------------------------------------------------------------------

classify_commit() {
  local subject="$1" body="${2:-}"
  local subj_lower body_lower
  subj_lower=$(printf '%s' "$subject" | tr '[:upper:]' '[:lower:]')
  body_lower=$(printf '%s' "$body" | tr '[:upper:]' '[:lower:]')
  local re

  # Breaking changes
  re='^[a-z]+\!:'
  if [[ "$body_lower" == *"breaking change"* ]] || [[ "$subj_lower" =~ $re ]]; then
    printf 'breaking\n'
    return
  fi

  # Conventional commits
  re='^feat(\([^)]*\))?:'
  if [[ "$subj_lower" =~ $re ]]; then
    printf 'feature\n'
    return
  fi
  re='^feature(\([^)]*\))?:'
  if [[ "$subj_lower" =~ $re ]]; then
    printf 'feature\n'
    return
  fi
  re='^fix(\([^)]*\))?:'
  if [[ "$subj_lower" =~ $re ]]; then
    printf 'fix\n'
    return
  fi
  re='^bugfix(\([^)]*\))?:'
  if [[ "$subj_lower" =~ $re ]]; then
    printf 'fix\n'
    return
  fi
  re='^docs(\([^)]*\))?:'
  if [[ "$subj_lower" =~ $re ]]; then
    printf 'docs\n'
    return
  fi
  re='^chore(\([^)]*\))?:'
  if [[ "$subj_lower" =~ $re ]]; then
    printf 'chore\n'
    return
  fi
  re='^build(\([^)]*\))?:'
  if [[ "$subj_lower" =~ $re ]]; then
    printf 'chore\n'
    return
  fi
  re='^ci(\([^)]*\))?:'
  if [[ "$subj_lower" =~ $re ]]; then
    printf 'chore\n'
    return
  fi
  re='^refactor(\([^)]*\))?:'
  if [[ "$subj_lower" =~ $re ]]; then
    printf 'refactor\n'
    return
  fi
  re='^style(\([^)]*\))?:'
  if [[ "$subj_lower" =~ $re ]]; then
    printf 'style\n'
    return
  fi
  re='^test(\([^)]*\))?:'
  if [[ "$subj_lower" =~ $re ]]; then
    printf 'test\n'
    return
  fi
  re='^perf(\([^)]*\))?:'
  if [[ "$subj_lower" =~ $re ]]; then
    printf 'perf\n'
    return
  fi

  # Keyword fallbacks
  if [[ "$subj_lower" == add\ * ]] || [[ "$subj_lower" == *"new feature"* ]] || [[ "$subj_lower" == implement* ]]; then
    printf 'feature\n'
    return
  fi
  if [[ "$subj_lower" == fix\ * ]] || [[ "$subj_lower" == *bug* ]]; then
    printf 'fix\n'
    return
  fi
  if [[ "$subj_lower" == update\ * ]] || [[ "$subj_lower" == improve\ * ]]; then
    printf 'improvement\n'
    return
  fi
  if [[ "$subj_lower" == remove\ * ]] || [[ "$subj_lower" == delete\ * ]]; then
    printf 'removal\n'
    return
  fi

  printf 'other\n'
}

# ---------------------------------------------------------------------------
# Fetch commits
# ---------------------------------------------------------------------------

get_commits_since() {
  local ref="${1:-}"
  local fmt='%H|%s|%b---COMMIT_END---'
  local cmd_args

  if [[ -n "$ref" ]]; then
    cmd_args=("log" "${ref}..HEAD" "--pretty=format:${fmt}")
  else
    cmd_args=("log" "--pretty=format:${fmt}")
  fi

  local raw
  raw=$(run_git "${cmd_args[@]}" || true)

  if [[ -z "$raw" ]]; then
    return
  fi

  # Use awk to split records by delimiter
  awk -v RS='---COMMIT_END---' 'NF || $0 ~ /./ {
    gsub(/^[\n]+/, "")
    gsub(/[\n]+$/, "")
    line = $0
    # Extract hash (before first |)
    p = index(line, "|")
    if (p == 0) next
    hash = substr(line, 1, p - 1)
    rest = substr(line, p + 1)
    # Extract subject (before second |)
    p = index(rest, "|")
    if (p == 0) next
    subj = substr(rest, 1, p - 1)
    body = substr(rest, p + 1)
    # Replace newlines in body with spaces to keep output single-line
    gsub(/\n/, " ", body)
    # Escape quotes and backslashes in subject for JSON
    gsub(/\\/, "\\\\", subj)
    gsub(/"/, "\\\"", subj)
    gsub(/\t/, "\\t", subj)
    print hash "\t" subj "\t" body
  }' <<< "$raw"
}

# ---------------------------------------------------------------------------
# Version bump logic
# ---------------------------------------------------------------------------

determine_bump() {
  local has_breaking="" has_feature="" has_fix=""

  while IFS=$'\t' read -r _full subj body; do
    [[ -z "$_full" ]] && continue
    local ctype
    ctype=$(classify_commit "$subj" "$body")
    case "$ctype" in
      breaking) has_breaking="1" ;;
      feature) has_feature="1" ;;
      fix | improvement) has_fix="1" ;;
    esac
  done

  if [[ -n "$has_breaking" ]]; then
    printf 'major\n'
  elif [[ -n "$has_feature" ]]; then
    printf 'minor\n'
  elif [[ -n "$has_fix" ]]; then
    printf 'patch\n'
  else
    printf 'patch\n'
  fi
}

calculate_next_version() {
  local current="$1" bump="$2"

  if [[ -z "$current" || "$current" == "0.0.0" ]]; then
    printf '1.0.0\n'
    return
  fi

  # Strip a leading "v" so git tags like v0.6.0 parse correctly.
  current="${current#v}"

  # Handle versions like "1.0.0-beta3"
  if [[ "$current" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)(-.*)?$ ]]; then
    local major="${BASH_REMATCH[1]}"
    local minor="${BASH_REMATCH[2]}"
    local patch="${BASH_REMATCH[3]}"
    local prerelease="${BASH_REMATCH[4]:-}"

    # If prerelease, just remove it for the release
    if [[ -n "$prerelease" ]]; then
      printf '%s.%s.%s\n' "$major" "$minor" "$patch"
      return
    fi

    case "$bump" in
      major)
        printf '%s.0.0\n' "$((major + 1))"
        ;;
      minor)
        printf '%s.%s.0\n' "$major" "$((minor + 1))"
        ;;
      patch | *)
        printf '%s.%s.%s\n' "$major" "$minor" "$((patch + 1))"
        ;;
    esac
  else
    printf '%s\n' "$current"
  fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

main() {
  local last_tag all_tags current_version version_source commits_json bump next_version

  last_tag=$(run_git describe --tags --abbrev=0 2>/dev/null || true)
  all_tags=$(run_git tag --list --sort=-v:refname 2>/dev/null || true)

  # Detect version source
  local ver_info
  ver_info=$(detect_version_source)
  version_source="${ver_info%%$'\t'*}"
  current_version="${ver_info#*$'\t'}"

  # Fetch and classify commits
  local raw_commits
  raw_commits=$(get_commits_since "$last_tag")

  local commit_count=0
  local commit_jsons=""
  local breaking_count=0 feature_count=0 fix_count=0 improvement_count=0
  local docs_count=0 refactor_count=0 perf_count=0 chore_count=0 style_count=0 test_count=0 other_count=0

  while IFS=$'\t' read -r full subj body; do
    [[ -z "$full" ]] && continue
    ((commit_count++)) || true

    local ctype h8
    h8="${full:0:8}"
    ctype=$(classify_commit "$subj" "$body")

    case "$ctype" in
      breaking) ((breaking_count++)) || true ;;
      feature) ((feature_count++)) || true ;;
      fix) ((fix_count++)) || true ;;
      improvement) ((improvement_count++)) || true ;;
      docs) ((docs_count++)) || true ;;
      refactor) ((refactor_count++)) || true ;;
      perf) ((perf_count++)) || true ;;
      chore) ((chore_count++)) || true ;;
      style) ((style_count++)) || true ;;
      test) ((test_count++)) || true ;;
      *) ((other_count++)) || true ;;
    esac

    # Re-escape subject for JSON output
    local esubj
    esubj=$(printf '%s' "$subj" | sed 's/\\/\\\\/g; s/"/\\"/g; s/\t/\\t/g')

    local cjson
    cjson=$(printf '{"hash":"%s","fullHash":"%s","type":"%s","subject":"%s","body":null}' "$h8" "$full" "$ctype" "$esubj")

    if [[ -n "$commit_jsons" ]]; then
      commit_jsons="${commit_jsons},${cjson}"
    else
      commit_jsons="$cjson"
    fi
  done < <(printf '%s\n' "$raw_commits")

  bump=$(printf '%s\n' "$raw_commits" | determine_bump)
  next_version=$(calculate_next_version "$current_version" "$bump")

  # Build grouped JSON
  local grouped
  grouped=$(printf '{"breaking":%s,"feature":%s,"fix":%s,"improvement":%s,"docs":%s,"refactor":%s,"perf":%s,"chore":%s,"style":%s,"test":%s,"other":%s}' \
    "$breaking_count" "$feature_count" "$fix_count" "$improvement_count" \
    "$docs_count" "$refactor_count" "$perf_count" "$chore_count" \
    "$style_count" "$test_count" "$other_count")

  # Build tags array (last 5)
  local tags_array=""
  local tag
  while IFS= read -r tag; do
    [[ -z "$tag" ]] && continue
    local etag
    etag=$(printf '%s' "$tag" | sed 's/\\/\\\\/g; s/"/\\"/g')
    if [[ -n "$tags_array" ]]; then
      tags_array="${tags_array},\"${etag}\""
    else
      tags_array="\"${etag}\""
    fi
  done < <(printf '%s\n' "$all_tags" | head -n5)

  # Output JSON
  cat <<EOF
{
  "lastTag": $(jq -R . <<< "${last_tag:-(no tags)}"),
  "allTags": [${tags_array}],
  "currentVersion": "${current_version}",
  "versionSource": "${version_source}",
  "commitCount": ${commit_count},
  "commits": [${commit_jsons}],
  "suggestedBump": "${bump}",
  "nextVersion": "${next_version}",
  "summary": {
    "breaking": ${breaking_count},
    "features": ${feature_count},
    "fixes": ${fix_count},
    "improvements": ${improvement_count},
    "docs": ${docs_count},
    "chores": $((chore_count + refactor_count)),
    "other": $((other_count + perf_count + style_count + test_count))
  }
}
EOF
}

main "$@"
