# Product Brief — Example Output

This is what a completed `aet-discover` diagnostic produces. It is evidence, not a sales pitch. It includes uncomfortable truths.

---

## Meta

| Field | Value |
|-------|-------|
| **Product** | ReconcileBot |
| **Date** | 2026-05-03 |
| **Verdict** | NARROW |
| **Diagnostician** | aet-discover |

---

## Idea (as originally stated)

"An AI-powered tool that automates financial reconciliation for e-commerce businesses. It connects to Shopify, Stripe, and QuickBooks, finds discrepancies, and suggests corrections."

---

## Q1: Demand Reality

**Answer given:** "We talked to 15 e-commerce founders and 12 said they'd pay for this."

**Pushback applied:** "Saying they'd pay is free. Has anyone actually paid? Has anyone gotten angry when your spreadsheet broke?"

**Final answer:** "One founder paid us $200/month for a manual version where we reconciled their books in Google Sheets. They called us twice when we were late."

**Finding:** Single paying customer with demonstrated dependency. Weak signal — one data point — but real behavior.

---

## Q2: Status Quo

**Answer given:** "They use spreadsheets or hire bookkeepers."

**Pushback applied:** "Walk me through the exact spreadsheet. How many rows? How many people touch it?"

**Final answer:** "The founder who pays us has a 47-tab Google Sheet. Their VA spends 6 hours/week on it. They tried QuickBooks but it didn't catch Shopify payout timing discrepancies."

**Finding:** Specific workaround with measurable cost (6 hrs/week, 47-tab sheet, VA labor). QuickBooks is the incumbent but has a known gap (payout timing).

---

## Q3: Desperate Specificity

**Answer given:** "E-commerce founders doing $1M–$10M ARR."

**Pushback applied:** "Name the actual human. Not a revenue band — a name, a title, a consequence."

**Final answer:** "Sarah Chen, founder of KetoBox ($2.3M ARR). She stays up until 11pm on Sundays reconciling because her accountant needs clean books by Monday 9am. If the books are wrong, her accountant charges extra and she misses her loan covenant reporting."

**Finding:** Specific human (Sarah Chen), specific moment (Sunday 11pm), specific consequence (loan covenant risk, accountant overage). This is the customer.

---

## Q4: Narrowest Wedge

**Answer given:** "The full platform with Shopify + Stripe + QuickBooks integration and AI suggestions."

**Pushback applied:** "What's the one thing a user would pay for this week? What if they didn't have to integrate anything?"

**Final answer:** "A weekly email that flags the top 3 discrepancies in their Stripe payouts vs Shopify orders. No integration — they upload CSVs."

**Finding:** Wedge is a CSV-upload weekly email, not a full platform. Shipable in days. The AI suggestion layer is premature; discrepancy detection alone may be valuable.

---

## Q5: Observation & Surprise

**Answer given:** "We haven't built a prototype yet."

**Pushback applied:** "Have you watched Sarah reconcile her sheet? What does she actually do?"

**Final answer:** "She sorts by payout date, then manually checks each order ID against the Shopify export. She color-codes rows in the sheet. The surprise: she doesn't care about the discrepancy amount — she cares about whether the order was refunded or if the payout was split across two deposits."

**Finding:** Real behavior observed. User cares about *reason* for discrepancy, not magnitude. Product should surface "why" before "how much."

---

## Q6: Future-Fit

**Answer given:** "AI will keep getting better at accounting, so we'll keep getting better."

**Pushback applied:** "Every AI accounting tool can say that. Why do YOU survive if OpenAI builds a reconciliation agent?"

**Final answer:** "Sarah trusts us because we know her specific edge cases (split payouts, Shopify Plus vs regular, her accountant's format). An generic AI won't know her covenant reporting deadline or her accountant's quirks."

**Finding:** Moat is domain-specific knowledge + relationship, not AI capability. Defensible if we deepen the relationship and capture more of Sarah's workflow context.

---

## Synthesis

### What we know
- One paying customer (Sarah) with real pain and measurable workaround
- Status quo is a 47-tab Google Sheet + 6 hrs/week VA labor
- Incumbent (QuickBooks) has a known gap (payout timing)
- Wedge is weekly discrepancy email from CSV upload
- User cares about "why" not "how much"
- Moat is relationship/context, not AI

### What we don't know
- Will other founders besides Sarah pay?
- Is $200/month the right price?
- Can we automate the CSV processing reliably?
- Will Sarah stay if we don't add the full platform?

### Risks
| Risk | Level | Mitigation |
|------|-------|------------|
| Single-customer dependency | High | Find 2 more Sarahs before building |
| Feature creep (AI suggestions) | Medium | Ship CSV email first; no AI layer until 5 customers |
| Incumbent response (QuickBooks) | Low | Gap is known; they move slowly |

---

## Verdict: NARROW

**Reasoning:** Demand is real but sample size is one. The wedge is correct (CSV email) but the user keeps describing the full platform. Scope must be locked to the wedge before any planning or implementation.

**Assignment:** Find 2 more Sarahs. Offer them the CSV email for $200/month. If both pay, proceed to `aet-plan`. If not, re-run `aet-discover` on what those founders actually need.
