#!/usr/bin/env bash
set -euo pipefail

# AE Toolkit one-line installer.
# Usage: curl -fsSL https://raw.githubusercontent.com/thebrightnest/ae-toolkit/main/scripts/install.sh | bash
# See docs/prds/uv-one-line-installer-prd.md for requirements.

AET_DATA_DIR="${AET_DATA_DIR:-"$HOME/.local/share/ae-toolkit"}"
AET_BIN_DIR="${AET_BIN_DIR:-"$HOME/.local/bin"}"
AET_SKILLS_DIR="${AET_SKILLS_DIR:-}"
REPO="${REPO:-"https://github.com/thebrightnest/ae-toolkit"}"
TAG="${TAG:-}"
AGENT="${AGENT:-}"
DRY_RUN=false

usage() {
    cat <<EOF
Usage: install.sh [OPTIONS]

Install the AE Toolkit: bootstrap uv, clone the repo, install the aet CLI
into a dedicated venv, link skills into agent directories, and symlink aet
onto PATH.

Options:
  --tag <tag>         Install a tagged release (default: latest semver tag,
                      falling back to main)
  --agent <agent>     Target one agent: claude-code, kimi, cursor, generic
  --bin-dir <dir>     Target PATH directory (default: ~/.local/bin)
  --skills-dir <dir>  Override skills directory (default: auto-detect)
  --repo <url|path>   Source to clone (default: GitHub main repo)
  --dry-run           Print planned actions without executing
  --help, -h          Show this message

Environment variables:
  AET_DATA_DIR        Persistent install path (default: ~/.local/share/ae-toolkit)
  AET_BIN_DIR         PATH directory for the aet symlink
  AET_SKILLS_DIR      Override skills directory
  REPO                Default repo URL/path
  TAG                 Default tag
  AGENT               Default agent
EOF
}

log() {
    echo "  $*"
}

error() {
    echo "error: $*" >&2
    exit 1
}

# Flags consumed by the bootstrap (before Python exists).
# --agent and --skills-dir are recognized only enough to know they take a
# value and to capture that value for the summary; the actual value is passed
# to the installed CLI through the documented environment variables (Typer
# binds AGENT / AET_SKILLS_DIR via envvar=). This avoids bash marshalling
# arguments for a Python program — the empty-array crash this plan exists to
# remove.
DRY_RUN_FLAG=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --tag)
            [[ $# -ge 2 ]] || error "--tag requires an argument"
            TAG="$2"
            shift 2
            ;;
        --repo)
            [[ $# -ge 2 ]] || error "--repo requires an argument"
            REPO="$2"
            shift 2
            ;;
        --bin-dir)
            [[ $# -ge 2 ]] || error "--bin-dir requires an argument"
            AET_BIN_DIR="$2"
            shift 2
            ;;
        --agent)
            [[ $# -ge 2 ]] || error "--agent requires an argument"
            AGENT="$2"
            shift 2
            ;;
        --skills-dir)
            [[ $# -ge 2 ]] || error "--skills-dir requires an argument"
            AET_SKILLS_DIR="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            DRY_RUN_FLAG="--dry-run"
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            error "unknown option: $1"
            ;;
    esac
done

REPO_DIR="$AET_DATA_DIR/repo"
VENV_DIR="$AET_DATA_DIR/venv"
AET_BIN="$VENV_DIR/bin/aet"

ensure_uv() {
    if command -v uv >/dev/null 2>&1; then
        log "uv already on PATH"
        return 0
    fi

    log "bootstrapping uv..."
    if [[ "$DRY_RUN" == true ]]; then
        log "would bootstrap uv via Astral installer"
        return 0
    fi

    # The Astral installer writes to ~/.local/bin by default.
    export UV_INSTALL_DIR="${UV_INSTALL_DIR:-"$HOME/.local/bin"}"
    if ! curl -LsSf https://astral.sh/uv/install.sh | sh; then
        error "failed to bootstrap uv"
    fi
    export PATH="$UV_INSTALL_DIR:$PATH"

    if ! command -v uv >/dev/null 2>&1; then
        error "uv bootstrap appeared to succeed but uv is not on PATH"
    fi
}

resolve_tag() {
    if [[ -n "$TAG" ]]; then
        echo "$TAG"
        return 0
    fi

    local latest
    latest=$(git ls-remote --tags --sort=-v:refname "$REPO" 2>/dev/null | \
        grep -E 'refs/tags/(v?[0-9]+\.[0-9]+\.[0-9]+)$' | \
        head -n1 | \
        sed 's|.*/||') || true

    if [[ -n "$latest" ]]; then
        echo "$latest"
    else
        echo "main"
    fi
}

clone_or_update_repo() {
    if [[ "$DRY_RUN" == true ]]; then
        log "would clone/update repo from $REPO to $REPO_DIR"
        log "would checkout tag: $TAG"
        return 0
    fi

    if [[ -d "$REPO_DIR/.git" ]]; then
        log "updating existing clone at $REPO_DIR"
        git -C "$REPO_DIR" fetch origin
    else
        log "cloning $REPO to $REPO_DIR"
        rm -rf "$REPO_DIR"
        git clone "$REPO" "$REPO_DIR"
    fi

    log "checking out $TAG"
    git -C "$REPO_DIR" checkout "$TAG"
}

create_venv_and_install() {
    if [[ "$DRY_RUN" == true ]]; then
        log "would create venv at $VENV_DIR"
        log "would install aet from $REPO_DIR"
        return 0
    fi

    if [[ ! -d "$VENV_DIR/bin" ]]; then
        log "creating venv at $VENV_DIR"
        uv venv "$VENV_DIR"
    else
        log "venv already exists at $VENV_DIR"
    fi

    log "installing aet from $REPO_DIR"
    uv pip install --python "$VENV_DIR/bin/python" "$REPO_DIR"
}

run_setup() {
    if [[ "$DRY_RUN" == true ]]; then
        log "would run: AET_REPO_ROOT=$REPO_DIR AET_SKILLS_DIR=$AET_SKILLS_DIR AGENT=$AGENT $AET_BIN setup skills $DRY_RUN_FLAG"
        log "would run: AET_BIN_DIR=$AET_BIN_DIR $AET_BIN setup link $DRY_RUN_FLAG"
        log "would run: AET_BIN_DIR=$AET_BIN_DIR $AET_BIN setup verify $DRY_RUN_FLAG"
        return 0
    fi

    log "linking skills"
    AET_REPO_ROOT="$REPO_DIR" AET_SKILLS_DIR="$AET_SKILLS_DIR" AGENT="$AGENT" \
        "$AET_BIN" setup skills ${DRY_RUN_FLAG:+--dry-run}

    log "linking aet"
    AET_BIN_DIR="$AET_BIN_DIR" "$AET_BIN" setup link ${DRY_RUN_FLAG:+--dry-run}

    log "verifying install"
    AET_BIN_DIR="$AET_BIN_DIR" "$AET_BIN" setup verify ${DRY_RUN_FLAG:+--dry-run}
}

print_summary() {
    echo
    echo "AE Toolkit installed."
    echo "  repo:   $REPO_DIR"
    echo "  venv:   $VENV_DIR"
    echo "  bin:    $AET_BIN_DIR/aet"
    if [[ -n "$AET_SKILLS_DIR" ]]; then
        echo "  skills: $AET_SKILLS_DIR"
    elif [[ -n "$AGENT" ]]; then
        echo "  agent:  $AGENT"
    fi
    if [[ "$DRY_RUN" == true ]]; then
        echo "  (dry run — no changes made)"
    fi
}

main() {
    echo "Installing AE Toolkit..."
    echo "  repo: $REPO"
    echo "  data: $AET_DATA_DIR"
    echo "  bin:  $AET_BIN_DIR"

    ensure_uv
    TAG=$(resolve_tag)
    clone_or_update_repo
    create_venv_and_install
    run_setup
    print_summary
}

main
