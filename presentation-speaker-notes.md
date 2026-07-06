<!-- markdownlint-disable MD032 -->

# Speaker Notes — Agentic Engineering Overview

_Target: 25–30 minutes. Aim for ~1:30 per content slide and a little extra on the AE Toolkit example._

---

## Slide 1 — Title: Agentic Engineering

**Opening (1 min)**

- Welcome everyone. Today we’re not doing a deep technical dive.
- We’re going to look at a way of working that is starting to separate teams that use AI as a nice-to-have from teams that use AI as a real operating system.
- I’ll use a concrete engineering example — the Agentic Engineering Toolkit — but the ideas apply to consulting, operations, legal, finance, HR, and beyond.

**Tone:** curious, inclusive, no jargon gatekeeping.

---

## Slide 2 — Why this conversation matters

**Key message:** Most people in this room already use AI. The gap is between casual use and structured partnership.

**Talking points (1:30)**

- Raise your hand mentally if you’ve used ChatGPT, Copilot, Gemini, or Claude in the last week.
- Now ask yourself: was it a one-off prompt, or was it part of a repeatable workflow with a known definition of “done”?
- That second part is what we’re calling agentic engineering.
- It’s not about being a programmer. It’s about designing work so a human and an AI can do it better together.

**Bridge:** “Let’s name the shift first.”

---

## Slide 3 — The shift: from syntax to intent

**Key message:** The interface to work is changing from “type every step” to “describe the goal and verify the result.”

**Talking points (1:30)**

- Read the quote from Google’s May 2026 paper.
- This is already happening in coding, but the pattern is general:
  - Lawyer: don’t write every clause from scratch; specify the deal and review the draft.
  - Consultant: don’t build every slide; define the insight and verify the narrative.
  - Finance analyst: don’t copy every cell; define the model and check the assumptions.
- The human still owns the judgment. The machine handles more of the translation.

---

## Slide 4 — The new reality (by the numbers)

**Key message:** Adoption is high, but raw speed is not the whole story.

**Talking points (1:30)**

- 85% of developers use AI coding agents; half daily; ~41% of new code is AI-generated.
- Productivity studies show 25–39% gains.
- But the METR study found experienced developers can take _longer_ because they spend time verifying and correcting AI output.
- That tension is the heart of the talk: **speed is easy, confidence is hard.**

---

## Slide 5 — What is an AI agent?

**Key message:** An agent is not a chatbot. It is a goal-driven loop.

**Talking points (1:30)**

- Define perceive → plan → act → observe → iterate.
- Contrast: chatbot answers one prompt and waits. An agent keeps going until the goal is met or hits a guardrail.
- This loop is the same whether the agent is writing code, answering support tickets, or generating a report.
- Use a simple example: “Draft a client email” is a chatbot task. “Find all overdue invoices, draft reminder emails, and schedule follow-ups” starts to be an agentic workflow.

---

## Slide 6 — The spectrum: vibe coding → agentic engineering

**Key message:** Same tools, different discipline.

**Talking points (1:30)**

- “Vibe coding” = describe what you want, accept what comes back, paste errors back in.
- It’s great for exploration and prototypes.
- Agentic engineering adds specs, tests, guardrails, memory, and verification.
- Neither is wrong. The skill is matching the approach to the stakes.
- A weekend prototype can be vibes. A client deliverable or production system needs structure.

---

## Slide 7 — The real skill: context engineering

**Key message:** Good output comes from good context, not clever prompts.

**Talking points (1:30)**

- Six context types: instructions, knowledge, memory, examples, tools, guardrails.
- Static context = loaded every time (rule files, identity). Dynamic context = loaded on demand (skills, retrieved docs).
- Agent skills are like specialist playbooks the AI opens only when the task matches.
- Analogy: onboarding a new teammate. You don’t whisper magic words; you give them the handbook, examples, and boundaries.

---

## Slide 8 — The new SDLC

**Key message:** AI compresses the software life cycle unevenly.

**Talking points (1:30)**

- Requirements become a conversation, not a hand-off document.
- Architecture stays human because it involves business trade-offs.
- Implementation gets the biggest speed boost.
- Testing becomes the contract that tells the AI what “correct” means.
- Review, deploy, and maintenance all get AI assistance but keep human gates.
- Even if you don’t ship software, notice the pattern: plan → execute → verify → maintain.

---

## Slide 9 — Harness engineering: the factory model

**Key message:** The model is just the engine; the harness around it determines whether it ships.

**Talking points (1:30)**

- A harness = instructions, tools, sandboxes, orchestration, guardrails, observability.
- The Google paper notes that one team moved from outside the Top 30 to the Top 5 on a coding benchmark by changing only the harness — same model.
- Another study raised scores 13.7 points by tuning prompts, tools, and middleware.
- Most agent failures are configuration failures, not model failures.

---

## Slide 10 — Two ways to work with agents

**Key message:** Humans move between real-time direction and async delegation.

**Talking points (1:30)**

- Conductor = pair programming in real time. Good for learning, debugging, and unfamiliar territory.
- Orchestrator = assign goals and review results. Good for well-defined, repeatable work.
- We’ll all do both. The question is which mode fits the task.

---

## Slide 11 — The 80% problem

**Key message:** AI gets most of the way there; humans finish the hard part.

**Talking points (1:30)**

- AI produces ~80% fast. The last 20% — edge cases, error handling, integration, correctness — is harder.
- AI errors increasingly look correct. That’s more dangerous than obvious syntax mistakes.
- The winning posture: use AI for the routine, focus human expertise on the ambiguous and critical.
- This is why verification and judgment are the durable skills.

---

## Slide 12 — Agentic economics

**Key message:** Discipline has an upfront cost and a long-term payoff.

**Talking points (1:30)**

- Vibe coding: low upfront cost, high ongoing cost. Unstructured prompts burn tokens and create debt.
- Agentic engineering: higher upfront cost, lower ongoing cost. Standards and tests pay off.
- Business translation: invest in the harness once, ship cheaper many times.

---

## Slide 13 — Example: the Agentic Engineering Toolkit

**Key message:** AE Toolkit turns agentic principles into a reusable process.

**Talking points (2:30)**

- It is a process, not a bag of prompts.
- The pipeline: Triage → Discover → Plan → Design → Validate → Prime → Implement → QA → Review → Ship → Evolve.
- It works across tools: Claude, Kimi, Cursor, Codex, Copilot, or even pasted into chat.
- Knowledge and rules live in `.agents/` and improve across sessions.
- It’s open-source and modular, so a team can adopt one skill at a time.

---

## Slide 14 — Proportionate ceremony

**Key message:** Not every task needs the same process.

**Talking points (1:30)**

- Trivial tasks: typo fixes ship fast.
- Normal tasks: a lightweight plan and automated checks.
- Critical tasks: full PRD, tests, QA, review, live verification.
- This prevents two failures: bureaucracy on small things, and recklessness on big things.

---

## Slide 15 — Two workflows in action

**Key message:** The toolkit supports both focused and long-running work.

**Talking points (1:30)**

- Single task / PIV loop: plan, clear context, implement, review, ship.
- Big feature / AFK loop: human plans, agent runs overnight, stops on failures, resumes after review.
- The key hygiene: context is cleared between tasks, so quality doesn’t degrade over a long run.

---

## Slide 16 — This mindset applies beyond engineering

**Key message:** Agentic engineering is a pattern, not a tech stack.

**Talking points (1:30)**

- Four repeating moves: Triage, Plan, Verify, Learn.
- If you can describe the work and the definition of done, you can agent-ify it.
- This is the bridge for non-engineers in the room.

---

## Slide 17 — Agentic patterns in other professions

**Key message:** Concrete examples make the pattern feel real.

**Talking points (2 min)**

- Walk through the table quickly.
- For each row, name the human value: judgment, escalation, client relationship, compliance.
- The AI does the repeatable parts; the human owns the exceptions and the relationship.
- Ask the room: “Where does your team repeat the same sequence of steps every week?”

---

## Slide 18 — Addressing the fear

**Key message:** AI changes tasks, not necessarily roles.

**Talking points (1:30)**

- The bottleneck moves from doing to directing, specifying, and verifying.
- The 80% problem keeps humans in the loop for the hardest parts.
- People who can design good workflows become more valuable.
- Read the closing quote: “Generation is solved. Verification, judgment, and direction are the new craft.”

---

## Slide 19 — Where to start

**Key message:** One workflow, well defined, beats a hundred vague experiments.

**Talking points (1:30)**

- Pick something repetitive.
- Write the rules.
- Define done.
- Run it with an AI partner and review critically.
- Update the rules when it goes wrong.
- Graduate from conductor to orchestrator.

---

## Slide 20 — Three principles to remember

**Key message:** Durable principles outlast any tool.

**Talking points (1 min)**

- Structure scales, vibes don’t.
- AI amplifies your culture — good or bad.
- The human role evolves; judgment and verification matter more.

---

## Slide 21 — The invitation

**Key message:** Curiosity is the only prerequisite.

**Talking points (1 min)**

- You don’t need to be an engineer.
- You don’t need to adopt everything tomorrow.
- Start with one workflow and redesign it around intent, verification, and learning.
- End with the line: **“Intent is the new interface.”**

---

## Slide 22 — References

**Use this for Q&A.**

- Google white paper: _The New SDLC with Vibe Coding_ (May 2026)
- AE Toolkit docs in this repository
- Further reading links for anyone who wants to go deeper

**Optional closing question:** “What is one repetitive process in your area that we could make agentic?”
