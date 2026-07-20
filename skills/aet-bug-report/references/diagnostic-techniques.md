# Diagnostic Techniques

Reference guide for the Root-Cause step of `aet-bug-report`. Use the technique
that best matches the bug's behavior and your current information.

---

## 1. Binary Search / Git Bisect

**When to use:** The bug appeared recently and you know it worked in the past.

**How:**

1. Identify a "good" commit where the bug did not exist
2. Identify a "bad" commit where the bug exists (often HEAD)
3. Run `git bisect start && git bisect bad && git bisect good <commit>`
4. For each commit git checks out, run your reproduction steps
5. Mark each as good or bad until git isolates the first bad commit

**Tip:** Automate the test with `git bisect run <script>` if your reproduction
can be scripted.

---

## 2. Logging and Tracing

**When to use:** The bug involves state you cannot see directly (async flows,
distributed calls, data transformations).

**How:**

1. Add structured logging at key decision points in the suspected code path
2. Log inputs, outputs, and intermediate state
3. Reproduce the bug and read the log trail
4. Remove or downgrade the added logs after the fix — don't leave debug noise

**Tip:** Prefer structured logs (JSON) over plain text so you can grep and
filter efficiently.

---

## 3. Isolation and Minimization

**When to use:** The reproduction is complex or involves many moving parts.

**How:**

1. Strip away everything that is not essential to triggering the bug
2. Remove features, config, data, and dependencies one at a time
3. Stop when you have the smallest possible reproduction
4. The minimal reproduction often reveals the root cause directly

**Tip:** If you cannot minimize, the bug may be an emergent property of
interactions — look for timing, ordering, or concurrency issues.

---

## 4. Hypothesis-Driven Debugging

**When to use:** You have a theory but need evidence.

**How:**

1. Form a specific, falsifiable hypothesis (e.g., "the bug occurs because X is
   null when Y is called")
2. Design an experiment that would prove or disprove it (log, test, code probe)
3. Run the experiment
4. If confirmed, proceed to Fix. If disproved, form a new hypothesis.

**Anti-pattern:** Changing code randomly and hoping. Every change should test a
specific hypothesis.

---

## 5. Rubber Duck / Explain to the Agent

**When to use:** You've been staring at the bug too long and lost perspective.

**How:**

1. Explain the bug, the code, and your reasoning out loud (or in writing)
2. Force yourself to articulate each assumption
3. The weak assumption usually surfaces during explanation

**Tip:** This works because explanation forces sequential, explicit reasoning —
which gaps and contradictions cannot survive.

---

## 6. Differential Analysis

**When to use:** Two similar code paths behave differently and only one has the
bug.

**How:**

1. Find a working path and a broken path that should behave identically
2. Systematically compare inputs, state, and logic at each step
3. The first divergence is usually the root cause

---

## Choosing a Technique

| Situation                 | Start with                  |
| ------------------------- | --------------------------- |
| Bug is new, worked before | Git bisect                  |
| Invisible state / async   | Logging and tracing         |
| Reproduction is huge      | Isolation and minimization  |
| You have a hunch          | Hypothesis-driven debugging |
| Stuck after hours         | Rubber duck                 |
| Similar path works        | Differential analysis       |
