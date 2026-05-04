# Sub-Agent Patterns for Planning

## When to Use Sub-Agents

Delegate to a sub-agent when the main agent would need to:

- Explore more than 10 files to understand codebase structure
- Research external libraries, APIs, or documentation
- Consume more than 50k tokens on research
- Analyze git history beyond the last 10 commits

## How to Brief a Sub-Agent

1. Give a clear, narrow mission: "Explore the auth module and return: (a) which files handle login, (b) what patterns are used for middleware, (c) how sessions are stored."
2. Set a token budget: "Use at most 30k tokens for this exploration."
3. Specify output format: "Return a 10-line bullet summary, not code."

## How to Consume Sub-Agent Output

- Read only the summary into main context
- Discard the sub-agent's full reasoning trace
- If the summary is insufficient, spawn a second sub-agent with a refined mission — don't expand the first one's scope

## Anti-Patterns

- **Don't** let the main agent do deep exploration directly — it pollutes context
- **Don't** chain sub-agents (sub-agent spawns sub-agent) — hard to debug
- **Don't** accept vague summaries — demand specific file paths and line references
