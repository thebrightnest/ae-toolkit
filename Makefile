.PHONY: help install-skills install-binaries add-skill lint format format-check validate install-hooks test lint-py

# Development symlink target. Override if your skills ecosystem uses a different path.
SKILLS_DIR ?= $(HOME)/.agents/skills
BIN_DIR ?= $(HOME)/.local/bin
REPO_DIR := $(shell pwd)
SKILLS := $(filter-out README.md Makefile scripts .git .gitignore docs .agents content .claude, $(wildcard *))
MARKDOWN_FILES := $(shell git ls-files '*.md' 2>/dev/null | while read -r f; do [ -f "$$f" ] && printf '%s ' "$$f"; done || find . -type f -name '*.md' ! -path './.git/*' ! -path './node_modules/*' ! -path './content/*')

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install-skills: ## Symlink all skills from this repo to ~/.agents/skills/ and put binaries on PATH
	@for skill in $(SKILLS); do \
		if [ -d "$$skill" ] && [ -f "$$skill/SKILL.md" ]; then \
			if [ -L "$(SKILLS_DIR)/$$skill" ]; then \
				echo "✓ $$skill already linked"; \
			elif [ -e "$(SKILLS_DIR)/$$skill" ]; then \
				echo "⚠ $$skill exists in $(SKILLS_DIR) but is not a symlink. Skipping."; \
			else \
				ln -s "$(REPO_DIR)/$$skill" "$(SKILLS_DIR)/$$skill"; \
				echo "✓ Linked $$skill"; \
			fi; \
		fi; \
	done
	@AET_SKILLS_DIR="$(SKILLS_DIR)" AET_BIN_DIR="$(BIN_DIR)" ./aet-setup/bin/install-aet-binaries

install-binaries: ## Symlink skill binaries from installed skill dirs onto PATH
	@AET_SKILLS_DIR="$(SKILLS_DIR)" AET_BIN_DIR="$(BIN_DIR)" ./aet-setup/bin/install-aet-binaries

add-skill: ## Scaffold a new skill. Usage: make add-skill NAME=my-skill
	@if [ -z "$(NAME)" ]; then \
		echo "Usage: make add-skill NAME=my-skill"; \
		exit 1; \
	fi
	@mkdir -p "$(NAME)/examples" "$(NAME)/references"
	@echo "---" > "$(NAME)/SKILL.md"
	@echo "name: $(NAME)" >> "$(NAME)/SKILL.md"
	@echo "description: Describe what this skill does and when to use it. Be specific about triggers." >> "$(NAME)/SKILL.md"
	@echo "---" >> "$(NAME)/SKILL.md"
	@echo "" >> "$(NAME)/SKILL.md"
	@echo "# $(NAME)" >> "$(NAME)/SKILL.md"
	@echo "" >> "$(NAME)/SKILL.md"
	@echo "## When to Use" >> "$(NAME)/SKILL.md"
	@echo "" >> "$(NAME)/SKILL.md"
	@echo "Describe the specific situations where this skill should be invoked." >> "$(NAME)/SKILL.md"
	@echo "" >> "$(NAME)/SKILL.md"
	@echo "## Instructions" >> "$(NAME)/SKILL.md"
	@echo "" >> "$(NAME)/SKILL.md"
	@echo "Write the skill instructions here. Keep it concise." >> "$(NAME)/SKILL.md"
	@echo "✓ Created skill: $(NAME)"
	@echo "✓ Edit $(NAME)/SKILL.md to add your skill logic"

lint: ## Run markdownlint on all markdown files
	@npx markdownlint-cli2 --config .markdownlint.yaml $(MARKDOWN_FILES)
	@echo "✓ Lint passed"

format: ## Format all markdown files with prettier
	@npx prettier@3.1.0 --write $(MARKDOWN_FILES)
	@echo "✓ Format complete"

format-check: ## Check markdown formatting (CI mode)
	@npx prettier@3.1.0 --check $(MARKDOWN_FILES)
	@echo "✓ Format check passed"

lint-py: ## Run ruff on Python files
	@command -v ruff >/dev/null 2>&1 || { echo "ruff not installed. Install it: pip install ruff"; exit 1; }
	@ruff check .
	@echo "✓ Python lint passed"

test: ## Run pytest suite
	@python3 -m pytest tests/ -q
	@echo "✓ Tests passed"

validate: ## Run all quality checks (lint + format-check + lint-py + test + skill-structure)
	@$(MAKE) lint
	@$(MAKE) format-check
	@$(MAKE) lint-py
	@$(MAKE) test
	@./scripts/validate-skills.sh
	@echo "✓ All validation checks passed"

install-hooks: ## Install pre-commit hooks
	@pre-commit install
	@echo "✓ Pre-commit hooks installed"
