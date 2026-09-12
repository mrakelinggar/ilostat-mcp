# Phase 0a — Dataflow Selection Findings

Date: 2026-07-26
Script: `execution/phase00/code/phase0a_scratch_dataflow_selection.py`

---

## What and why

Out of ILOSTAT's 1,210 dataflows, we need to pick one per concept to serve as the tool's default. If we pick the wrong one, every number the tool returns for that concept could be wrong — a different population, a different methodology, a different definition. This file records which flows exist, which one we picked, and why.

---

## 1b — How many flows cover each concept?

| Concept | Total flows | Survey | Modelled |
|---|---|---|---|
| Unemployment rate | 34 | 24 | 10 |
| Monthly wages (earnings) | 56 | 56 | 0 |
| Youth unemployment | 14 | 0 | 14 |
| Employment-to-population ratio | 32 | 22 | 10 |

**Note on overlap:** the unemployment and youth unemployment lists share flows — youth unemployment flows (e.g. `DF_UNE_3EAP_SEX_AGE_DSB_RT`) appeared in both searches. These counts are not disjoint.

**What distinguishes the survey flows from each other:** they are the same underlying survey data, sliced by different additional dimensions. For unemployment, all 24 survey flows pull from the same national labour force surveys. What varies is *how the data is broken down* — by education level, by disability status, by rural/urban area, by marital status, etc. A flow without any of those extra breakdowns gives you the total; a flow with them gives you the total plus subgroups.

**What distinguishes survey from modelled:** modelled flows (leading digit in the variant code — `2EAP`, `3EAP`, `3WAP`, etc.) are ILO-imputed estimates. They cover all countries including ones with no surveys, and include projections into the future. They are not real data. Survey flows (`DEAP`, `DWAP`, `EMTA`, etc.) are nationally reported numbers from actual labour force surveys.

**Monthly wages — no modelled flows:** wage data isn't modelled by ILO the way employment is. All 56 wage flows are survey-based. Within those 56, there are different variants for what type of worker is covered — all employees (EMTA), care sector employees (CMTA), public sector (PMTA), STEM employees (SMTA), tourism sector (TMTA) — and different statistical summaries (average, median, Gini). The most general is EMTA: all employees, average earnings.

**Youth unemployment — no survey flows:** there is no standalone survey-based flow with "youth unemployment" in the title. All 14 flows labelled "youth unemployment" are ILO modelled estimates (`3EAP`, `3UNE`, `3WAP` variants). To get real survey data on youth unemployment, you filter the general unemployment flow (`DF_UNE_DEAP_SEX_AGE_RT`) by age group (15–24). This is not a gap in the data — the survey data exists — it just isn't exposed as a separate named flow.

---

## 1c — Which flow is the canonical choice per concept?

"Canonical" means: the single flow the tool uses by default when a user asks about that concept. If someone asks for Malaysia's unemployment rate, the tool needs to pick one flow. This is that choice.

**Selection criterion (applied in order):**
1. Survey-based only — no modelled flows
2. Most general disaggregation — no extra breakdowns beyond sex and age (the tool returns the total, not a subgroup)
3. Broadest country coverage — if two flows survive (1) and (2), pick the one with more countries

| Concept | Canonical flow | Coverage | Why |
|---|---|---|---|
| Unemployment rate | `DF_UNE_DEAP_SEX_AGE_RT` | 252 countries | Only survey flow with no extra dimensions (SEX + AGE only) and by far the broadest coverage — the SDG 8.5.2 survey flow covers only 107 countries by comparison |
| Monthly wages | `DF_EAR_EMTA_SEX_CUR_NB` | 130 countries | EMTA = all employees (not a specific sector). After excluding sector-specific flows (care, public, STEM, tourism) and non-average measures (Gini, median), this is the most general and broadest-coverage option |
| Employment-to-population | `DF_EMP_DWAP_SEX_AGE_RT` | — | Only survey flow with no extra dimensions after excluding the sub-annual variant |
| Youth unemployment | **none** | — | No survey-based flow exists. Use `DF_UNE_DEAP_SEX_AGE_RT` filtered to age 15–24 |

**EMTA vs CMTA — what these codes mean:**
Both are average monthly earnings flows. EMTA covers all employees across the whole economy. CMTA covers care-sector employees only (healthcare, childcare, social work). The variant code encodes who is being measured, not how. CMTA looks like a general flow because it has no extra dimension breakdown — but it's a sector-specific flow by definition of its variant. This is a case where the ID structure alone (criterion b) isn't enough; the title must also be checked.

**On youth unemployment:** the canonical for this concept is "use the general unemployment flow and filter to age 15–24." This approach means `search_indicators("youth unemployment")` will return all-modelled results and must not be used to drive the tool for this concept. Youth unemployment is a dimension of the unemployment flow, not its own flow.

---

## 1d — Does which flow you pick actually change the number?

Yes, materially. Across the 5 test countries, every single country showed DIFFER — the same country's "total unemployment rate" (filtered to SEX_T + AGE_YTHADULT_YGE15 + annual) came back different across flows.

| Country | Range across flows | Example spread |
|---|---|---|
| MYS | 3.16–3.94% | GED flow (ages 25–54 only) vs. DEAP flow (all working age 15+) |
| DEU | 2.85–5.8% | GED household-type flow vs. disability flow (different population) |
| NGA | 3.15–10.7% | General survey flow vs. citizenship-disaggregated flow |
| BRA | 5.18–6.8% | GED flow vs. DEAP general flow |
| THA | 0.61–0.89% | GED flow (2021) vs. DEAP flows (2024) |

**Why the numbers differ:** most of the spread comes from three things. First, the GED flows cover only ages 25–54, not 15+ — so their "total" is for a different age bracket even when filtered to AGE_YTHADULT_YGE15. Second, the SDG 8.5.2 flow (`DF_SDG_B852`) uses the 19th ICLS definition of unemployment, which is slightly different from the 13th ICLS definition used in the main DEAP flow. Third, some flows return data from a different year depending on what's available, and unemployment changes year-to-year.

**Implication:** canonical selection is not cosmetic. Returning the wrong flow means returning a different number, for a concept that sounds identical. The canonical flows in 1c are the correct defaults.

---

## 1e — Does a keyword search surface the canonical flow?

Short answer: no, not reliably. For three of five queries, the canonical flow does not appear in the top 10 results, and for two queries, modelled flows rank above all survey flows.

| Query | Canonical rank | Risk |
|---|---|---|
| "unemployment rate" | #22 — not in top 10 | Modelled flow at #3, before most survey flows |
| "wages" | 0 results | The word "wages" doesn't appear in any ILOSTAT title |
| "monthly earnings" | #9 | Two care-sector (CMTA) flows rank above the canonical EMTA flow |
| "youth unemployment" | no canonical | **All 14 results are modelled** — 100% wrong for real data use |
| "employment-to-population" | #14 — not in top 10 | 6 modelled flows rank before the first survey flow |

**What this means for the tool:** `search_indicators` cannot be a plain title search and left for the agent to navigate. An agent following the top result will pick a modelled flow for youth unemployment every single time. It will pick a care-sector wage flow instead of a general one. It will skip the canonical unemployment flow entirely.

**Decision:** `search_indicators` must annotate results with a `is_modelled` flag, and the system prompt must instruct the agent to prefer survey flows. For youth unemployment specifically, the system prompt (or tool logic) must redirect the agent to the general unemployment flow filtered by age, not to the "youth unemployment" search results.

---

## Decisions locked by this phase

| Decision | Value |
|---|---|
| Canonical unemployment flow | `DF_UNE_DEAP_SEX_AGE_RT` |
| Canonical monthly wages flow | `DF_EAR_EMTA_SEX_CUR_NB` |
| Canonical employment-to-population flow | `DF_EMP_DWAP_SEX_AGE_RT` |
| Youth unemployment | Not a standalone flow — filter `DF_UNE_DEAP_SEX_AGE_RT` by age 15–24 |
| `search_indicators` design | Must include `is_modelled` flag on each result. System prompt must steer agent to prefer survey flows. |
| Keyword for wage search | Use "earnings" not "wages" — "wages" returns 0 results in ILOSTAT titles |
