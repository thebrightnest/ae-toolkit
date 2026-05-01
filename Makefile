.PHONY: help install-skills package add-skill clean

SKILLS_DIR := $(HOME)/.claude/skills
REPO_DIR := $(shell pwd)
SKILLS := $(filter-out README.md Makefile scripts .git .gitignore, $(wildcard *))

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install-skills: ## Symlink all skills from this repo to ~/.claude/skills/
	@for skill in $(SKILLS); do \
		if [ -d "$$skill" ]; then \
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

package: ## Package all skills into .skill files
	@for skill in $(SKILLS); do \
		if [ -d "$$skill" ] && [ -f "$$skill/SKILL.md" ]; then \
			zip -r "$$skill.skill" "$$skill" -x "*.git*" -x "*node_modules*" -x "*.DS_Store"; \
			echo "✓ Packaged $$skill.skill"; \
		fi; \
	done

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

clean: ## Remove all .skill packages
	@rm -f *.skill
	@echo "✓ Cleaned .skill files"
