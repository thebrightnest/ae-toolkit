.PHONY: help install-skills install-binaries add-skill lint format validate install-hooks test lint-py install-editable test-installer

# Development symlink target. Override if your skills ecosystem uses a different path.
SKILLS_DIR ?= $(HOME)/.agents/skills
BIN_DIR ?= $(HOME)/.local/bin
REPO_DIR := $(shell pwd)
SKILL_ROOT := skills
SKILLS := $(wildcard $(SKILL_ROOT)/*)
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

install-editable: $(PYTHON) ## Ensure the aet package is installed editable (plain pip; uv optional)
	@$(PYTHON) -c "import aet" 2>/dev/null || $(PIP) install -e '.[dev]'
	@echo "✓ Editable install verified"

install-skills: install-editable ## Symlink all skills from this repo to ~/.agents/skills/ and put binaries on PATH
	@for skill in $(SKILLS); do \
		if [ -d "$$skill" ] && [ -f "$$skill/SKILL.md" ]; then \
			skill_name=$$(basename "$$skill"); \
			if [ -L "$(SKILLS_DIR)/$$skill_name" ]; then \
				echo "✓ $$skill_name already linked"; \
			elif [ -e "$(SKILLS_DIR)/$$skill_name" ]; then \
				echo "⚠ $$skill_name exists in $(SKILLS_DIR) but is not a symlink. Skipping."; \
			else \
				ln -s "$(REPO_DIR)/$$skill" "$(SKILLS_DIR)/$$skill_name"; \
				echo "✓ Linked $$skill_name"; \
			fi; \
		fi; \
	done
	@AET_SKILLS_DIR="$(SKILLS_DIR)" AET_BIN_DIR="$(BIN_DIR)" aet install

install-binaries: install-editable ## Symlink skill binaries from installed skill dirs onto PATH
	@AET_SKILLS_DIR="$(SKILLS_DIR)" AET_BIN_DIR="$(BIN_DIR)" aet install

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
	@$(MAKE) test-installer
	@echo "✓ All validation checks passed"

install-hooks: ## Install pre-commit hooks
	@pre-commit install
	@echo "✓ Pre-commit hooks installed"
