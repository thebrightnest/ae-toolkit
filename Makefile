.PHONY: help install-skills install-binaries add-skill lint format validate install-hooks test lint-py install-editable test-installer

# Development symlink target. Override if your skills ecosystem uses a different path.
SKILLS_DIR ?= $(HOME)/.agents/skills
BIN_DIR ?= $(HOME)/.local/bin
REPO_DIR := $(shell pwd)
SKILL_ROOT := skills
MARKDOWN_FILES := $(shell git ls-files '*.md' 2>/dev/null | while read -r f; do [ -f "$$f" ] && printf '%s ' "$$f"; done || find . -type f -name '*.md' ! -path './.git/*' ! -path './node_modules/*' ! -path './content/*')

VENV := .venv
PYTHON := $(VENV)/bin/python3
PIP := $(VENV)/bin/pip

# What pytest runs. `validate` skips pytest when the change set is prose-only;
# every other entry point runs the whole suite.
PYTEST_TARGETS ?= tests/

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

$(PYTHON):
	@python3 -m venv $(VENV)

install-editable: $(PYTHON) ## Ensure the aet package is installed editable from this repo root
	@if ! stale="$$($(PYTHON) scripts/check-editable-install.py 2>&1)"; then \
		echo "Editable install stale ($$stale); reinstalling..."; \
		$(PIP) install -e '.[dev]'; \
	else \
		echo "✓ Editable install verified"; \
	fi

# Skill linking goes through `aet setup skills`, which reads each existing
# symlink's target and repoints one that is stale. The loop this replaced tested
# only whether a symlink existed and reported "already linked" whatever it
# pointed at, so a link left behind by an older install was never corrected and
# the drift was silent. AET_REPO_ROOT pins the source to this checkout, and the
# venv interpreter runs this repo's code: a bare `aet` on PATH may belong to a
# release clone and would relink from there.
install-skills: install-editable ## Symlink all skills from this repo to ~/.agents/skills/ and put binaries on PATH
	@AET_REPO_ROOT="$(REPO_DIR)" $(PYTHON) -m aet.cli.main setup skills --skills-dir "$(SKILLS_DIR)"
	@AET_REPO_ROOT="$(REPO_DIR)" AET_SKILLS_DIR="$(SKILLS_DIR)" AET_BIN_DIR="$(BIN_DIR)" $(PYTHON) -m aet.cli.main setup link

install-binaries: install-editable ## Symlink skill binaries from installed skill dirs onto PATH
	@AET_REPO_ROOT="$(REPO_DIR)" AET_SKILLS_DIR="$(SKILLS_DIR)" AET_BIN_DIR="$(BIN_DIR)" $(PYTHON) -m aet.cli.main setup link

add-skill: ## Scaffold a new skill. Usage: make add-skill NAME=my-skill
	@if [ -z "$(NAME)" ]; then \
		echo "Usage: make add-skill NAME=my-skill"; \
		exit 1; \
	fi
	@mkdir -p "$(SKILL_ROOT)/$(NAME)/examples" "$(SKILL_ROOT)/$(NAME)/references"
	@echo "---" > "$(SKILL_ROOT)/$(NAME)/SKILL.md"
	@echo "name: $(NAME)" >> "$(SKILL_ROOT)/$(NAME)/SKILL.md"
	@echo "description: Describe what this skill does and when to use it. Be specific about triggers." >> "$(SKILL_ROOT)/$(NAME)/SKILL.md"
	@echo "---" >> "$(SKILL_ROOT)/$(NAME)/SKILL.md"
	@echo "" >> "$(SKILL_ROOT)/$(NAME)/SKILL.md"
	@echo "# $(NAME)" >> "$(SKILL_ROOT)/$(NAME)/SKILL.md"
	@echo "" >> "$(SKILL_ROOT)/$(NAME)/SKILL.md"
	@echo "## When to Use" >> "$(SKILL_ROOT)/$(NAME)/SKILL.md"
	@echo "" >> "$(SKILL_ROOT)/$(NAME)/SKILL.md"
	@echo "Describe the specific situations where this skill should be invoked." >> "$(SKILL_ROOT)/$(NAME)/SKILL.md"
	@echo "" >> "$(SKILL_ROOT)/$(NAME)/SKILL.md"
	@echo "## Instructions" >> "$(SKILL_ROOT)/$(NAME)/SKILL.md"
	@echo "" >> "$(SKILL_ROOT)/$(NAME)/SKILL.md"
	@echo "Write the skill instructions here. Keep it concise." >> "$(SKILL_ROOT)/$(NAME)/SKILL.md"
	@echo "✓ Created skill: $(NAME)"
	@echo "✓ Edit $(SKILL_ROOT)/$(NAME)/SKILL.md to add your skill logic"

lint: ## Run markdownlint on all markdown files
	@npx markdownlint-cli2@0.17.2 --config .markdownlint.yaml $(MARKDOWN_FILES)
	@echo "✓ Lint passed"

format: ## Format all markdown files with prettier
	@npx prettier@3.1.0 --write $(MARKDOWN_FILES)
	@echo "✓ Format complete"

lint-py: install-editable ## Run ruff on Python files
	@$(PYTHON) -m ruff check .
	@echo "✓ Python lint passed"

test: install-editable ## Run pytest suite (parallel if pytest-xdist is installed)
	@if $(PYTHON) -c "import xdist" 2>/dev/null; then \
		$(PYTHON) -m pytest $(PYTEST_TARGETS) -q -n auto --dist=loadgroup; \
	else \
		$(PYTHON) -m pytest $(PYTEST_TARGETS) -q; \
	fi
	@echo "✓ Tests passed"

test-installer: install-editable ## Run installer smoke tests in isolation
	@$(PYTHON) -m pytest tests/installer/test_installer.py -q
	@echo "✓ Installer tests passed"

validate: install-editable ## Run all quality checks, fail-fast; pytest is skipped when only prose changed
	@$(MAKE) lint-py
	@$(PYTHON) ./src/aet/cli/validate_workflows.py
	@$(PYTHON) ./scripts/skills-lint --legacy=error
	@./scripts/validate-skills.sh
	@$(PYTHON) -m aet.cli.main plans lint
	@$(PYTHON) -m aet.cli.main docs lint
	@$(PYTHON) -m aet.change_scope --explain
	@targets=$$($(PYTHON) -m aet.change_scope); \
	if [ -n "$$targets" ]; then \
		$(MAKE) test PYTEST_TARGETS="$$targets"; \
	else \
		echo "→ Skipping pytest (prose-only change)"; \
	fi
	@echo "✓ All validation checks passed"

install-hooks: ## Install pre-commit hooks
	@pre-commit install
	@echo "✓ Pre-commit hooks installed"
