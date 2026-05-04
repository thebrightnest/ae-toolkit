# Command Workflows

This directory holds reusable command workflows — sequences of shell commands or agent instructions that can be triggered as a unit.

## Usage

Commands are referenced from `AGENTS.md` or loaded on demand during a session. They are not auto-loaded on every session to protect context window.

## Adding a Command

Create a new `.md` file with:

- Trigger condition (when to run this command)
- Step-by-step instructions
- Expected output or validation step
