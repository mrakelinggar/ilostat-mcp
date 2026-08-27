# Phase 00 — Concept Discovery

Date planned: 2026-08-28

---

## What and why

We have four labor market concepts the server will expose: unemployment rate, employment-to-population ratio (emp-to-pop), average monthly earnings (wages), and labor force participation rate (LFPR). For each, we need to pick exactly one canonical ILOSTAT dataflow.

Three of the four were selected in Phase 0a with varying rigor — unemployment was cross-checked numerically, wages and emp-to-pop were not. LFPR was never researched at all. If we ship with the wrong canonical flow, every number the server returns for that concept is wrong, silently and confidently. We need to be certain before locking `indicators.py`.

The approach: read first (enumerate all flows, understand what each measures), then test (compare numbers from top candidates across real countries). Decisions locked here become the source of truth for `indicators.py`.

---

## Plan

### For each of the four concepts:

**Step 1 — Enumerate**
Pull all ILOSTAT dataflows matching the concept keyword. Record: flow ID, full title, whether it's survey or modelled (leading digit in variant code = modelled), and which dimensions it breaks down by (from the DSD). Cross-check the ILOSTAT website indicator page for any plain-English description not visible in the API title.

**Step 2 — Filter to candidates**
Apply the selection criterion in order:
1. Survey-based only — no modelled flows
2. Most general disaggregation — SEX + AGE only, no extra breakdowns (education, disability, sector, etc.)
3. Broadest country coverage — if two survive (1) and (2), pick the one with more countries

If only one flow survives, it's the canonical. If two or more survive, carry both to Step 3.

**Step 3 — Numerical cross-check**
For any concept with more than one candidate after Step 2, pull data for 3–5 countries from each candidate and compare. Record whether the numbers differ and why. Pick the one that matches the standard definition the agent should report.

---

## Concepts

| Concept | Confidence after Phase 0a | Status |
|---|---|---|
| Unemployment rate | High — enumerated, numerically cross-checked | Re-confirm only |
| Employment-to-population | Low — flow inferred, not enumerated or cross-checked | Full 3-step |
| Average monthly earnings | Medium — enumerated, not cross-checked | Step 1 re-read + Step 3 |
| LFPR | None | Full 3-step |

---

## Outputs

- One locked decision per concept: canonical flow ID, country coverage, why it was picked over alternatives
- `indicators.py` design is unblocked
- A `code/` subfolder with the discovery script(s) used
- A results file recording findings and the locked decisions

---

## What we are not doing here

- Not writing any production code
- Not resolving the other Phase 0e unknowns (FREQ=A filter, error handling, etc.) — those stay separate
- Not filling in benchmark ground truth — that comes after Phase 3
