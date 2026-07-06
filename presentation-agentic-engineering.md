---
marp: true
theme: default
paginate: true
size: 16:9
style: |
  section {
    font-family: "Helvetica Neue", Arial, sans-serif;
  }
  h1 {
    color: #1a73e8;
  }
  strong {
    color: #1a73e8;
  }
---

<!-- markdownlint-disable MD031 MD032 MD060 -->

<!--
  Title slide
  Say hello, set the tone: this is a conversation, not a deep-tech sermon.
-->

# Agentic Engineering

## From “using AI” to working _with_ agents

A high-level tour for everyone — not just engineers

_Example: the Agentic Engineering Toolkit (AE Toolkit)_

---

## Why this conversation matters

- AI is already in the room: chatbots, copilots, summaries, code suggestions
- Most people are using it **casually** — a prompt here, a draft there
- A smaller group is learning to **partner with AI** as a repeatable system
- That gap is the difference between “vibe coding” and **agentic engineering**

> This isn’t about replacing people. It’s about upgrading how we think about work.

---

## The shift: from syntax to intent

> “The most profound shift in software engineering isn’t a new language or framework. It’s the transition from **writing code** to **expressing intent**, and trusting intelligent systems to translate that intent into working software.”
> — Google, _The New SDLC with Vibe Coding_ (May 2026)

- We stop typing every step
- We start defining the goal, the constraints, and the verification

---

## The new reality (by the numbers)

- **85%** of professional developers regularly use AI coding agents
- **51%** use them daily
- **~41%** of new code is AI-generated
- Reported productivity gains: **25–39%**
- But experienced developers can take **longer** when they verify and correct AI output

> Speed is easy. Confidence is hard.

---

## What is an AI agent?

A system that:

1. **Perceives** a goal
2. **Plans** steps
3. **Acts** through tools
4. **Observes** results
5. **Iterates** until done

Unlike a chatbot, an agent runs its own loop.

---

## The spectrum: vibe coding → agentic engineering

| Vibe coding             | Agentic engineering                       |
| ----------------------- | ----------------------------------------- |
| Casual prompts          | Formal specs, guardrails, memory          |
| “Does it seem to work?” | Automated tests + evaluations             |
| Disposable prototypes   | Production systems                        |
| High ongoing cost       | Higher upfront cost, lower long-term cost |

> The tools can be the same. The **discipline** around them is what changes.

---

## The real skill: context engineering

- The quality of AI output depends less on clever prompts and more on the **context** you give it
- Six kinds of context: instructions, knowledge, memory, examples, tools, guardrails
- Static context (always loaded) vs dynamic context (loaded on demand)
- **Agent skills** = portable packages of know-how the agent loads only when needed

> Think of it as onboarding a new team member: what would they need to know to do good work?

---

## The new SDLC

AI compresses the software life cycle unevenly:

- **Requirements** → become a conversation, not a hand-off
- **Architecture** → stays human; AI implements the chosen structure
- **Implementation** → fastest to accelerate
- **Testing** → becomes the contract with the AI
- **Review & deploy** → AI-assisted, human-gated
- **Maintenance** → legacy code becomes safer to touch

---

## Harness engineering: the factory model

> “A raw model is not an agent. It becomes one once a **harness** gives it state, tool execution, feedback loops, and enforceable constraints.”

The harness includes:

- Instructions and rule files
- Tools and APIs
- Sandboxes
- Orchestration logic
- Guardrails / hooks
- Observability

> The model is the engine. The harness is the factory around it.

---

## Two ways to work with agents

**Conductor mode**

- Real-time pair programming
- You guide every move
- Great for learning, debugging, complex logic

**Orchestrator mode**

- You define goals and review results
- Agents work in the background
- Great for well-defined, repeatable work

> Most of us will move between both.

---

## The 80% problem

- AI can rapidly produce ~**80%** of a solution
- The last **20%** — edge cases, error handling, integration, correctness — still needs human judgment
- AI errors now look right and may even pass basic tests

> The winning posture: let AI handle the routine, reserve your expertise for the ambiguous and the critical.

---

## Agentic economics

| Vibe coding                     | Agentic engineering         |
| ------------------------------- | --------------------------- |
| Low upfront cost (CapEx)        | Higher upfront cost         |
| High ongoing cost (OpEx)        | Lower ongoing cost          |
| “Prompting loops” burn tokens   | First-pass success improves |
| Technical debt accumulates fast | Standards and tests pay off |

> Upfront discipline creates long-term leverage.

---

## Example: the Agentic Engineering Toolkit

**AE Toolkit is a process, not a collection of prompts.**

It encodes a full agentic workflow into reusable skills:

```text
Triage → Discover → Plan → Design → Validate
  → Prime → Implement → QA → Review → Ship → Evolve
```

- Works with Claude, Kimi, Cursor, Codex, Copilot, or paste-into-chat
- Every request is classified before any skill runs
- Rules and learnings live in `.agents/` and improve over time

---

## Proportionate ceremony

AE Toolkit sorts work into three classes:

| Class        | Example                    | Ceremony                                                  |
| ------------ | -------------------------- | --------------------------------------------------------- |
| **Trivial**  | Fix a typo                 | Direct edit → validate → ship                             |
| **Normal**   | Add a field                | Quick plan → implement → checks → ship                    |
| **Critical** | Auth, payments, migrations | Full PRD → tests → QA → review → live verification → ship |

> Not every task needs a 20-page plan. The right amount of process for the right risk.

---

## Two workflows in action

**Single task / PIV loop**

```text
clarify goal → write plan → clear context → implement
→ review → security audit → QA → ship
```

**Big feature / AFK loop**

```text
human plans by day → agent works overnight → each task starts fresh
→ loop stops on failure → human reviews → loop resumes
```

> The magic: context is cleared between tasks, so quality doesn’t degrade.

---

## This mindset applies beyond engineering

Agentic thinking is not about code. It’s about:

- **Triage** — what kind of work is this?
- **Plan** — what does good look like?
- **Verify** — how do we know it’s right?
- **Learn** — how do we make the system smarter next time?

That pattern works in **consulting, operations, legal, finance, HR, marketing, support**.

---

## Agentic patterns in other professions

| Area           | Agentic workflow                                                     |
| -------------- | -------------------------------------------------------------------- |
| **Consulting** | Research → synthesize → draft → partner review → client-ready        |
| **Legal**      | Clause library → contract draft → compliance check → redline         |
| **Finance**    | Data pull → assumptions → model → sensitivity test → report          |
| **HR**         | Job spec → candidate screen → structured interview guide → feedback  |
| **Support**    | Ticket triage → knowledge-base answer → escalation rules → follow-up |

> In every case, the human defines the goal and the guardrails. The AI accelerates the execution.

---

## Addressing the fear

Common worry: _“Will AI take my job?”_

What we actually see:

- AI replaces **tasks**, not **roles**
- The bottleneck moves from **doing** to **judging, specifying, and verifying**
- People who can direct agents well become more valuable, not less
- The 80% problem means humans are still essential for the hardest 20%

> “Generation is solved. Verification, judgment, and direction are the new craft.”

---

## Where to start

1. **Pick one repetitive workflow** you do today
2. **Write down the rules** — what would a new colleague need to know?
3. **Define “done”** — tests, checklists, examples
4. **Run it with an AI partner** and review the output critically
5. **Update your rules** every time the AI makes a mistake
6. **Graduate** the workflow from “conductor” to “orchestrator”

> Start small. One working agentic workflow teaches more than a hundred slide decks.

---

## Three principles to remember

1. **Structure scales, vibes don’t**
   - Exploration is fine; production needs discipline
2. **AI amplifies your culture**
   - Good standards get stronger; weak standards get weaker
3. **The human role is evolving, not shrinking**
   - Judgment, architecture, and verification matter more than ever

---

## The invitation

- You don’t need to be an engineer to think agentically
- You don’t need to adopt everything tomorrow
- You only need to get curious about one workflow you can redesign with intent, verification, and learning

> **Intent is the new interface.**

---

## References

- Google / Osmani, Saboo, Kartakis. _The New SDLC with Vibe Coding: From Ad-Hoc Prompting to Agentic Engineering._ May 2026.
- AE Toolkit repository: `README.md`, `docs/PIPELINE.md`, `docs/use-cases.md`, `docs/CONVENTIONS.md`.

**Further reading:**

- Addy Osmani — “Agentic Engineering” and “The Factory Model”
- Google Agents Whitepaper Series (Nov 2025)
- Agent Development Kit (ADK) and Agent-to-Agent (A2A) Protocol
