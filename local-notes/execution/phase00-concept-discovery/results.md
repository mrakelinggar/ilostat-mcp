# Phase 00 — Concept Discovery Results

Date: 2026-08-28
Script: `code/concept_discovery.py`
Raw output: `results_raw.txt`
Flow details + sample data: `flows_detail.md`

---

## What and why

For each of the four labor market concepts we're building tools around, we enumerated every ILOSTAT dataflow that matched, applied a three-step selection filter to each one, and ran a live numerical cross-check to verify the choice. This is the source of truth for `indicators.py`. Each dataflow's selection or discard is documented here with a specific reason.

---

## Infrastructure note

ILOSTAT's SDMX API now sits behind a Cloudflare bot challenge. Plain `requests.Session` calls get 403. Fixed by swapping the sdmx1 client's session to `cloudscraper.create_scraper()`. This must be applied in `sdmx_client.py` at startup.

---

## Glossary

**CUR** — currency type. Wage flows report earnings in three denominations: local currency (the country's own money, e.g. BRL for Brazil), PPP (purchasing power parity — a normalized international unit that removes price-level differences between countries), and USD (converted at market exchange rates). `CUR` is a dimension in the wage flow ID; the other three concept flows do not have it.

**Extra dims** — classification dimensions in a flow's ID beyond the concept's base set. For unemployment/emp-to-pop/LFPR the base is `{SEX, AGE}`; for wages it's `{SEX, CUR}`. Any dimension beyond the base means the flow slices by a subgroup (e.g. by disability status or education level) and cannot return a national total.

**13th vs 19th ICLS** — the International Conference of Labour Statisticians sets the international definition of unemployment. The 13th (1982) definition counts anyone actively seeking work as unemployed. The 19th (2013) definition is stricter: it also requires the person to be available to start work within a short window. The stricter definition counts fewer people as unemployed, so the rate is lower. Our tools use the 13th ICLS standard (the DEAP/DWAP flows), which is what most national statistical offices still report.

---

## Selection criteria (applied in order)

1. **Survey-based** — discard any flow tagged as ILO modelled estimate. Rule: leading digit in the variant segment (e.g. `2EAP`, `3WAP`) means modelled.
2. **General disaggregation** — discard any flow that slices by more than the base dimensions. Extra dims make the flow a subgroup, not a total.
3. **Title exclusions** — discard flows that pass the dim check but are still wrong:
   - `sub-annual`: monthly/quarterly only — no annual total exists in the flow
   - `19th icls`: uses a stricter unemployment definition that gives materially different numbers
4. **Coverage proxy** (only when multiple candidates survive steps 1–3): count how many of 5 test countries return a valid annual total. Pick the broadest.

---

## Concept 1 — Unemployment Rate

**Total flows:** 34 (24 survey, 10 modelled)

### Modelled flows — all discarded (ILO imputed estimates, not real survey data)

| # | Flow ID | Title | Reason |
|---|---|---|---|
| 1 | `DF_SDG_0852_SEX_AGE_RT` | SDG 8.5.2: Unemployment rate by sex and age | Modelled — leading `0` in variant `0852` flags this as an ILO estimate, not national survey data |
| 2 | `DF_SDG_0852_SEX_DSB_RT` | SDG 8.5.2: Unemployment rate by sex and disability status | Modelled — same reason as #1; also a disability subgroup |
| 3 | `DF_UNE_2EAP_SEX_AGE_RT` | Unemployment rate by sex and age — ILO modelled estimates, Nov. 2025 | Modelled — `2EAP` variant; covers all 185+ countries including those with no real surveys; includes future projections |
| 4 | `DF_UNE_3EAP_SEX_AGE_DSB_RT` | Youth unemployment rate by sex, age and disability status | Modelled — `3EAP` variant |
| 5 | `DF_UNE_3EAP_SEX_AGE_EDU_RT` | Youth unemployment rate by sex, age and education | Modelled — `3EAP` variant |
| 6 | `DF_UNE_3EAP_SEX_AGE_GEO_RT` | Youth unemployment rate by sex, age and rural/urban areas | Modelled — `3EAP` variant |
| 7 | `DF_UNE_3EAP_SEX_AGE_STU_RT` | Youth unemployment rate by sex, age and school attendance | Modelled — `3EAP` variant |
| 8 | `DF_UNE_5EAP_SEX_AGE_RT` | Unemployment rate by sex and age — 19th ICLS | Modelled — `5EAP` variant |
| 9 | `DF_UNE_5EAP_SEX_DSB_RT` | Unemployment rate by sex and disability status — 19th ICLS | Modelled — `5EAP` variant; also disability subgroup |
| 10 | `DF_UNE_5EAP_SEX_EDU_RT` | Unemployment rate by sex and education — 19th ICLS | Modelled — `5EAP` variant; also education subgroup |

### Survey flows — evaluated

| # | Flow ID | Extra dims | Verdict | Reason |
|---|---|---|---|---|
| 1 | `DF_GED_XLU1_SEX_HHT_CHL_RT` | HHT, CHL | ❌ Discard | Breaks down by household type (HHT) and presence of children (CHL). Only returns subgroup figures — no national total available |
| 2 | `DF_GED_XLU1_SEX_HHT_GEO_RT` | HHT, GEO | ❌ Discard | Breaks down by household type and urban/rural geography. Same issue — subgroup only, no total |
| 3 | `DF_SDG_B852_SEX_AGE_RT` | — | ❌ Discard | Passes the dim check (no extra dims) but uses the 19th ICLS unemployment definition. Confirmed to give different numbers for the same country/year: Nigeria is 4.68% under this flow but 3.45% under `DF_UNE_DEAP_SEX_AGE_RT`. Using two different definitions in the same server would silently produce inconsistent results |
| 4 | `DF_SDG_B852_SEX_DSB_RT` | DSB | ❌ Discard | Disability (DSB) subgroup + 19th ICLS definition |
| 5 | `DF_UNE_DEA1_SEX_AGE_RT` | — | ❌ Discard | Title says "Sub-annual" — this flow holds monthly/quarterly observations only. When filtered to annual frequency (FREQ=A), it returns zero rows. No annual totals exist in this flow |
| 6 | `DF_UNE_DEAP_SEX_AGE_CBR_RT` | CBR | ❌ Discard | Breaks down by country of birth (CBR) — native-born vs. foreign-born workers. Only subgroup figures, no national total |
| 7 | `DF_UNE_DEAP_SEX_AGE_CCT_RT` | CCT | ❌ Discard | Breaks down by citizenship status (CCT) — nationals vs. non-nationals. Subgroup only |
| 8 | `DF_UNE_DEAP_SEX_AGE_DSB_RT` | DSB | ❌ Discard | Breaks down by disability status (DSB). Subgroup only |
| 9 | `DF_UNE_DEAP_SEX_AGE_EDU_RT` | EDU | ❌ Discard | Breaks down by education level (EDU). Subgroup only |
| 10 | `DF_UNE_DEAP_SEX_AGE_GEO_RT` | GEO | ❌ Discard | Breaks down by urban vs. rural geography (GEO). Subgroup only |
| 11 | `DF_UNE_DEAP_SEX_AGE_MTS_RT` | MTS | ❌ Discard | Breaks down by migration status (MTS). Subgroup only |
| **12** | **`DF_UNE_DEAP_SEX_AGE_RT`** | **—** | **✅ Selected** | **Only survey flow with no extra dims and no title exclusions. This is the main ILO labour force survey flow for unemployment — used by 252 countries, the standard reference for SDG indicator 8.5.2 (13th ICLS version)** |
| 13 | `DF_UNE_DEAP_SEX_DSB_RT` | DSB | ❌ Discard | Disability subgroup |
| 14 | `DF_UNE_DEAP_SEX_EDU_CBR_RT` | EDU, CBR | ❌ Discard | Education + country of birth subgroup |
| 15 | `DF_UNE_DEAP_SEX_EDU_CCT_RT` | EDU, CCT | ❌ Discard | Education + citizenship subgroup |
| 16 | `DF_UNE_DEAP_SEX_EDU_DSB_RT` | EDU, DSB | ❌ Discard | Education + disability subgroup |
| 17 | `DF_UNE_DEAP_SEX_EDU_GEO_RT` | EDU, GEO | ❌ Discard | Education + geography subgroup |
| 18 | `DF_UNE_DEAP_SEX_EDU_MTS_RT` | EDU, MTS | ❌ Discard | Education + migration status subgroup |
| 19 | `DF_UNE_DEAP_SEX_EDU_RT` | EDU | ❌ Discard | Education subgroup |
| 20 | `DF_UNE_DEAP_SEX_GEO_DSB_RT` | GEO, DSB | ❌ Discard | Geography + disability subgroup |
| 21 | `DF_UNE_DEAP_SEX_GEO_MTS_RT` | GEO, MTS | ❌ Discard | Geography + migration status subgroup |
| 22 | `DF_UNE_DEAP_SEX_GEO_RT` | GEO | ❌ Discard | Geography subgroup |
| 23 | `DF_UNE_DEAP_SEX_MTS_DSB_RT` | MTS, DSB | ❌ Discard | Migration + disability subgroup |
| 24 | `DF_UNE_DEAP_SEX_MTS_RT` | MTS | ❌ Discard | Migration status subgroup |

### Decision

**`DF_UNE_DEAP_SEX_AGE_RT`** — single candidate after all filtering steps. No cross-check needed.

---

## Concept 2 — Employment-to-Population Ratio

**Total flows:** 32 (22 survey, 10 modelled)

### Modelled flows — all discarded

| # | Flow ID | Title | Reason |
|---|---|---|---|
| 1 | `DF_EMP_2WAP_SEX_AGE_RT` | Employment-to-population ratio — ILO modelled estimates, Nov. 2025 | Modelled — `2WAP` variant; imputed estimates, not survey data |
| 2 | `DF_EMP_3WAP_SEX_AGE_DSB_RT` | Youth emp-to-pop by sex, age and disability | Modelled — `3WAP` variant |
| 3 | `DF_EMP_3WAP_SEX_AGE_EDU_RT` | Youth emp-to-pop by sex, age and education | Modelled — `3WAP` variant |
| 4 | `DF_EMP_3WAP_SEX_AGE_GEO_RT` | Youth emp-to-pop by sex, age and rural/urban | Modelled — `3WAP` variant |
| 5 | `DF_EMP_3WAP_SEX_AGE_STU_RT` | Youth emp-to-pop by sex, age and school attendance | Modelled — `3WAP` variant |
| 6 | `DF_EMP_5WAP_SEX_AGE_RT` | Employment-to-population ratio — 19th ICLS | Modelled — `5WAP` variant |
| 7 | `DF_UNE_3WAP_SEX_AGE_DSB_RT` | Youth unemployment-to-population ratio by disability | Modelled — `3WAP` variant |
| 8 | `DF_UNE_3WAP_SEX_AGE_EDU_RT` | Youth unemployment-to-population ratio by education | Modelled — `3WAP` variant |
| 9 | `DF_UNE_3WAP_SEX_AGE_GEO_RT` | Youth unemployment-to-population ratio by rural/urban | Modelled — `3WAP` variant |
| 10 | `DF_UNE_3WAP_SEX_AGE_STU_RT` | Youth unemployment-to-population ratio by school attendance | Modelled — `3WAP` variant |

### Survey flows — evaluated

| # | Flow ID | Extra dims | Verdict | Reason |
|---|---|---|---|---|
| 1 | `DF_EMP_DWA1_SEX_AGE_RT` | — | ❌ Discard | Title says "SA by sex and age (Sub-annual)" — monthly/quarterly only. Filtered to FREQ=A returns nothing |
| 2 | `DF_EMP_DWAP_SEX_AGE_CBR_RT` | CBR | ❌ Discard | Country of birth subgroup — no national total |
| 3 | `DF_EMP_DWAP_SEX_AGE_CCT_RT` | CCT | ❌ Discard | Citizenship status subgroup |
| 4 | `DF_EMP_DWAP_SEX_AGE_DSB_RT` | DSB | ❌ Discard | Disability status subgroup |
| 5 | `DF_EMP_DWAP_SEX_AGE_EDU_RT` | EDU | ❌ Discard | Education level subgroup |
| 6 | `DF_EMP_DWAP_SEX_AGE_GEO_RT` | GEO | ❌ Discard | Urban/rural geography subgroup |
| 7 | `DF_EMP_DWAP_SEX_AGE_MTS_RT` | MTS | ❌ Discard | Migration status subgroup |
| **8** | **`DF_EMP_DWAP_SEX_AGE_RT`** | **—** | **✅ Selected** | **Only survey flow with no extra dims and no title exclusions. The standard ILO employment-to-population ratio from national labour force surveys** |
| 9 | `DF_EMP_DWAP_SEX_DSB_RT` | DSB | ❌ Discard | Disability subgroup |
| 10 | `DF_EMP_DWAP_SEX_EDU_CBR_RT` | EDU, CBR | ❌ Discard | Education + country of birth subgroup |
| 11 | `DF_EMP_DWAP_SEX_EDU_CCT_RT` | EDU, CCT | ❌ Discard | Education + citizenship subgroup |
| 12 | `DF_EMP_DWAP_SEX_EDU_DSB_RT` | EDU, DSB | ❌ Discard | Education + disability subgroup |
| 13 | `DF_EMP_DWAP_SEX_EDU_GEO_RT` | EDU, GEO | ❌ Discard | Education + geography subgroup |
| 14 | `DF_EMP_DWAP_SEX_EDU_MTS_RT` | EDU, MTS | ❌ Discard | Education + migration status subgroup |
| 15 | `DF_EMP_DWAP_SEX_EDU_RT` | EDU | ❌ Discard | Education subgroup |
| 16 | `DF_EMP_DWAP_SEX_GEO_DSB_RT` | GEO, DSB | ❌ Discard | Geography + disability subgroup |
| 17 | `DF_EMP_DWAP_SEX_GEO_MTS_RT` | GEO, MTS | ❌ Discard | Geography + migration status subgroup |
| 18 | `DF_EMP_DWAP_SEX_GEO_RT` | GEO | ❌ Discard | Geography subgroup |
| 19 | `DF_EMP_DWAP_SEX_MTS_DSB_RT` | MTS, DSB | ❌ Discard | Migration + disability subgroup |
| 20 | `DF_EMP_DWAP_SEX_MTS_RT` | MTS | ❌ Discard | Migration status subgroup |
| 21 | `DF_GED_PEPR_SEX_HHT_CHL_RT` | HHT, CHL | ❌ Discard | Household type + children subgroup — different survey family (GED) |
| 22 | `DF_GED_PEPR_SEX_HHT_GEO_RT` | HHT, GEO | ❌ Discard | Household type + geography subgroup — different survey family (GED) |

### Decision

**`DF_EMP_DWAP_SEX_AGE_RT`** — single candidate after all filtering steps. No cross-check needed.

---

## Concept 3 — Average Monthly Earnings (Wages)

**Total flows:** 56 (56 survey, 0 modelled — wage data is not modelled by ILO)

All 56 flows are survey-based. The dim filter left 13 candidates with no extra dims. All 13 were cross-checked live across 5 countries.

### Survey flows — evaluated (56 total, showing all)

Flows with extra dims are grouped at the end. Candidates (no extra dims) are listed first.

**Candidates (no extra dims beyond SEX and CUR):**

| # | Flow ID | Title | Coverage | Verdict | Reason |
|---|---|---|---|---|---|
| 1 | `DF_EAR_CMTA_SEX_CUR_NB` | Average monthly earnings of **care employees** by sex and currency | 3/5 | ❌ Discard | Care sector only (healthcare, childcare, social work). Numbers are different from the whole-economy average: Thailand care workers earned 22,526 baht/month while the general average was 16,519 baht/month in 2024. The tool should report the whole-economy figure |
| 2 | `DF_EAR_CMTA_SEX_NB` | Average monthly earnings of care employees by sex | 0/5 | ❌ Discard | Care sector only + no CUR dimension. Without a CUR dimension, the currency denomination is implicit and can't be filtered (LCU/PPP/USD not selectable). Returns nothing when the CUR=LCU key is applied |
| 3 | **`DF_EAR_EMTA_SEX_CUR_NB`** | **Average monthly earnings of employees by sex and currency** | **5/5** | **✅ Selected** | **All employees, whole economy, with explicit CUR dimension. The most general wage flow available. 5/5 test countries return data** |
| 4 | `DF_EAR_EMTA_SEX_NB` | Average monthly earnings of employees by sex | 0/5 | ❌ Discard | Same coverage as #3 but no CUR dimension — currency denomination is baked in and can't be filtered. Unclear whether values are LCU, PPP, or USD without inspecting each row's metadata. Returns nothing when CUR=LCU is applied |
| 5 | `DF_EAR_EMTG_SEX_NB` | **Gini index** of monthly earnings by sex | 0/5 | ❌ Discard | This is an inequality measure (0 = perfectly equal, 1 = maximum inequality), not an earnings level. It tells you how unequal wages are within a country, not what workers actually earn. Also no CUR dimension |
| 6 | `DF_EAR_EMTM_SEX_CUR_NB` | **Median** monthly earnings of employees by sex and currency | 5/5 | ❌ Discard | Median is a valid earnings measure — the midpoint where half of workers earn more and half earn less. Coverage matches EMTA (5/5). Discarded in favor of EMTA (average) because average earnings is the figure most commonly cited by statistical agencies, news, and policy reports. If median is ever needed, this is the flow |
| 7 | `DF_EAR_EMTM_SEX_NB` | Median monthly earnings by sex | 0/5 | ❌ Discard | Median + no CUR dimension |
| 8 | `DF_EAR_PMTA_SEX_CUR_NB` | Average monthly earnings of **public sector** employees | 4/5 | ❌ Discard | Public sector employees only. Nigeria had no data (404). Public sector pay is systematically different from private sector: France public sector averaged 2,304 EUR vs 2,197 EUR general average in 2024 |
| 9 | `DF_EAR_PMTA_SEX_NB` | Average monthly earnings of public sector employees | 0/5 | ❌ Discard | Public sector only + no CUR dimension |
| 10 | `DF_EAR_SMTA_SEX_CUR_NB` | Average monthly earnings of **STEM employees** | 3/5 | ❌ Discard | STEM workers only (science, technology, engineering, mathematics). STEM workers are typically higher-paid: Brazil STEM 5,310 BRL vs 3,155 BRL general average in 2024 |
| 11 | `DF_EAR_SMTA_SEX_NB` | Average monthly earnings of STEM employees | 0/5 | ❌ Discard | STEM only + no CUR dimension |
| 12 | `DF_EAR_TMTA_SEX_CUR_NB` | Average monthly earnings of **tourism sector** employees | 3/5 | ❌ Discard | Tourism sector only (hotels, restaurants, travel). France tourism had no data (404) |
| 13 | `DF_EAR_TMTA_SEX_NB` | Average monthly earnings of tourism sector employees | 0/5 | ❌ Discard | Tourism only + no CUR dimension |

**Discarded for extra dims (43 flows):**

| # | Flow ID | Extra dims | Reason |
|---|---|---|---|
| 14 | `DF_EAR_EMTA_SEX_AGE_CUR_NB` | AGE | Age subgroup — breaks earnings down by age band, no whole-economy total |
| 15 | `DF_EAR_EMTA_SEX_AGE_NB` | AGE | Age subgroup + no CUR |
| 16 | `DF_EAR_EMTA_SEX_CBR_CUR_NB` | CBR | Country of birth subgroup |
| 17 | `DF_EAR_EMTA_SEX_CBR_NB` | CBR | Country of birth subgroup + no CUR |
| 18 | `DF_EAR_EMTA_SEX_CCT_CUR_NB` | CCT | Citizenship status subgroup |
| 19 | `DF_EAR_EMTA_SEX_CCT_NB` | CCT | Citizenship + no CUR |
| 20 | `DF_EAR_EMTA_SEX_DSB_CUR_NB` | DSB | Disability status subgroup |
| 21 | `DF_EAR_EMTA_SEX_DSB_NB` | DSB | Disability + no CUR |
| 22 | `DF_EAR_EMTA_SEX_ECO_CUR_NB` | ECO | Economic activity / sector subgroup |
| 23 | `DF_EAR_EMTA_SEX_ECO_NB` | ECO | Economic activity + no CUR |
| 24 | `DF_EAR_EMTA_SEX_EDU_CUR_NB` | EDU | Education level subgroup |
| 25 | `DF_EAR_EMTA_SEX_EDU_NB` | EDU | Education + no CUR |
| 26 | `DF_EAR_EMTA_SEX_GEO_CUR_NB` | GEO | Urban/rural geography subgroup |
| 27 | `DF_EAR_EMTA_SEX_GEO_NB` | GEO | Geography + no CUR |
| 28 | `DF_EAR_EMTA_SEX_IND_CUR_NB` | IND | Industry subgroup |
| 29 | `DF_EAR_EMTA_SEX_IND_NB` | IND | Industry + no CUR |
| 30 | `DF_EAR_EMTA_SEX_MTS_CUR_NB` | MTS | Migration status subgroup |
| 31 | `DF_EAR_EMTA_SEX_MTS_NB` | MTS | Migration + no CUR |
| 32 | `DF_EAR_EMTA_SEX_OCU_CUR_NB` | OCU | Occupation subgroup |
| 33 | `DF_EAR_EMTA_SEX_OCU_NB` | OCU | Occupation + no CUR |
| 34 | `DF_EAR_EMTG_SEX_AGE_NB` | AGE | Gini by age subgroup |
| 35 | `DF_EAR_EMTG_SEX_DSB_NB` | DSB | Gini by disability |
| 36 | `DF_EAR_EMTG_SEX_ECO_NB` | ECO | Gini by economic activity |
| 37 | `DF_EAR_EMTG_SEX_EDU_NB` | EDU | Gini by education |
| 38 | `DF_EAR_EMTG_SEX_GEO_NB` | GEO | Gini by geography |
| 39 | `DF_EAR_EMTG_SEX_MTS_NB` | MTS | Gini by migration status |
| 40 | `DF_EAR_EMTG_SEX_OCU_NB` | OCU | Gini by occupation |
| 41 | `DF_EAR_EMTM_SEX_AGE_CUR_NB` | AGE | Median by age subgroup |
| 42 | `DF_EAR_EMTM_SEX_AGE_NB` | AGE | Median by age + no CUR |
| 43 | `DF_EAR_EMTM_SEX_DSB_CUR_NB` | DSB | Median by disability |
| 44 | `DF_EAR_EMTM_SEX_DSB_NB` | DSB | Median by disability + no CUR |
| 45 | `DF_EAR_EMTM_SEX_ECO_CUR_NB` | ECO | Median by economic activity |
| 46 | `DF_EAR_EMTM_SEX_ECO_NB` | ECO | Median by economic activity + no CUR |
| 47 | `DF_EAR_EMTM_SEX_EDU_CUR_NB` | EDU | Median by education |
| 48 | `DF_EAR_EMTM_SEX_EDU_NB` | EDU | Median by education + no CUR |
| 49 | `DF_EAR_EMTM_SEX_GEO_CUR_NB` | GEO | Median by geography |
| 50 | `DF_EAR_EMTM_SEX_GEO_NB` | GEO | Median by geography + no CUR |
| 51 | `DF_EAR_EMTM_SEX_MTS_CUR_NB` | MTS | Median by migration status |
| 52 | `DF_EAR_EMTM_SEX_MTS_NB` | MTS | Median by migration + no CUR |
| 53 | `DF_EAR_EMTM_SEX_OCU_CUR_NB` | OCU | Median by occupation |
| 54 | `DF_EAR_EMTM_SEX_OCU_NB` | OCU | Median by occupation + no CUR |
| 55 | `DF_GED_PEAR_SEX_HHT_CHL_NB` | HHT, CHL | Household type + children subgroup — different survey family (GED) |
| 56 | `DF_GED_PEAR_SEX_HHT_GEO_NB` | HHT, GEO | Household type + geography subgroup — different survey family (GED) |

### Cross-check results (LCU, SEX_T, annual)

| Country | CMTA care (3/5) | **EMTA all (5/5)** | EMTM median (5/5) | PMTA public (4/5) | SMTA STEM (3/5) | TMTA tourism (3/5) |
|---|---|---|---|---|---|---|
| BRA | 3,100.87 BRL | **3,154.84 BRL** | 2,000.00 BRL | 5,019.58 BRL | 5,310.15 BRL | 2,282.65 BRL |
| DEU | n/a | **4,412.67 EUR** | 3,774.43 EUR | n/a | n/a | n/a |
| FRA | 2,017.91 EUR | **2,196.95 EUR** | 1,937.00 EUR | 2,304.40 EUR | 2,844.86 EUR | n/a |
| NGA | n/a | **76,488.79 NGN** | 50,000.00 NGN | 95,735.54 NGN | n/a | 82,053.01 NGN |
| THA | 22,525.67 THB | **16,519.03 THB** | 13,000.00 THB | 22,388.23 THB | 28,870.78 THB | 15,116.10 THB |

The sector-specific flows give materially different numbers. Public sector pay in Nigeria is 25% above the general average. STEM workers in Brazil earn 68% more than the average. Sector flows are useful for specific analyses but wrong as a default "what do workers earn" answer.

### Decision

**`DF_EAR_EMTA_SEX_CUR_NB`** — average monthly earnings, all employees, with CUR dimension. Default filter: `CUR=CUR_TYPE_LCU`. Tied with `DF_EAR_EMTM_SEX_CUR_NB` on coverage (5/5); average selected over median because it is the standard reporting figure.

---

## Concept 4 — Labour Force Participation Rate (LFPR)

**Total flows:** 30 (23 survey, 7 modelled)

### Modelled flows — all discarded

| # | Flow ID | Title | Reason |
|---|---|---|---|
| 1 | `DF_EAP_2WAP_SEX_AGE_RT` | Labour force participation rate — ILO modelled estimates, Nov. 2025 | Modelled — `2WAP` variant |
| 2 | `DF_EAP_3WAP_SEX_AGE_DSB_RT` | Youth LFPR by sex, age and disability | Modelled — `3WAP` variant |
| 3 | `DF_EAP_3WAP_SEX_AGE_EDU_RT` | Youth LFPR by sex, age and education | Modelled — `3WAP` variant |
| 4 | `DF_EAP_3WAP_SEX_AGE_GEO_RT` | Youth LFPR by sex, age and rural/urban | Modelled — `3WAP` variant |
| 5 | `DF_EAP_3WAP_SEX_AGE_STU_RT` | Youth LFPR by sex, age and school attendance | Modelled — `3WAP` variant |
| 6 | `DF_EAP_5WAP_SEX_AGE_RT` | Labour force participation rate — 19th ICLS | Modelled — `5WAP` variant; also uses 19th ICLS definition |
| 7 | `DF_GED_2LFP_SEX_HHT_RT` | LFPR for persons ages 25–54 by sex and household type — ILO modelled, Nov. 2023 | Modelled — `2LFP` variant; also covers ages 25–54 only, not all working-age adults |

### Survey flows — evaluated

| # | Flow ID | Extra dims | Verdict | Reason |
|---|---|---|---|---|
| 1 | `DF_EAP_DWA1_SEX_AGE_RT` | — | ❌ Discard | Title says "Sub-annual" — monthly/quarterly only; no annual total |
| 2 | `DF_EAP_DWAP_SEX_AGE_CBR_RT` | CBR | ❌ Discard | Country of birth subgroup |
| 3 | `DF_EAP_DWAP_SEX_AGE_CCT_RT` | CCT | ❌ Discard | Citizenship status subgroup |
| 4 | `DF_EAP_DWAP_SEX_AGE_DSB_RT` | DSB | ❌ Discard | Disability status subgroup |
| 5 | `DF_EAP_DWAP_SEX_AGE_EDU_RT` | EDU | ❌ Discard | Education level subgroup |
| 6 | `DF_EAP_DWAP_SEX_AGE_GEO_RT` | GEO | ❌ Discard | Urban/rural geography subgroup |
| 7 | `DF_EAP_DWAP_SEX_AGE_MTS_RT` | MTS | ❌ Discard | Migration status subgroup |
| **8** | **`DF_EAP_DWAP_SEX_AGE_RT`** | **—** | **✅ Selected** | **Only survey flow with no extra dims and no title exclusions. This is the standard ILO LFPR from national labour force surveys — the mirror concept to unemployment rate** |
| 9 | `DF_EAP_DWAP_SEX_DSB_RT` | DSB | ❌ Discard | Disability subgroup |
| 10 | `DF_EAP_DWAP_SEX_EDU_CBR_RT` | EDU, CBR | ❌ Discard | Education + country of birth |
| 11 | `DF_EAP_DWAP_SEX_EDU_CCT_RT` | EDU, CCT | ❌ Discard | Education + citizenship |
| 12 | `DF_EAP_DWAP_SEX_EDU_DSB_RT` | EDU, DSB | ❌ Discard | Education + disability |
| 13 | `DF_EAP_DWAP_SEX_EDU_GEO_RT` | EDU, GEO | ❌ Discard | Education + geography |
| 14 | `DF_EAP_DWAP_SEX_EDU_MTS_RT` | EDU, MTS | ❌ Discard | Education + migration status |
| 15 | `DF_EAP_DWAP_SEX_EDU_RT` | EDU | ❌ Discard | Education subgroup |
| 16 | `DF_EAP_DWAP_SEX_GEO_DSB_RT` | GEO, DSB | ❌ Discard | Geography + disability |
| 17 | `DF_EAP_DWAP_SEX_GEO_MTS_RT` | GEO, MTS | ❌ Discard | Geography + migration status |
| 18 | `DF_EAP_DWAP_SEX_GEO_RT` | GEO | ❌ Discard | Geography subgroup |
| 19 | `DF_EAP_DWAP_SEX_MTS_DSB_RT` | MTS, DSB | ❌ Discard | Migration + disability |
| 20 | `DF_EAP_DWAP_SEX_MTS_RT` | MTS | ❌ Discard | Migration status subgroup |
| 21 | `DF_GED_PLFP_SEX_HHT_CHL_RT` | HHT, CHL | ❌ Discard | Household type + children subgroup — GED survey family |
| 22 | `DF_GED_PLFP_SEX_HHT_GEO_RT` | HHT, GEO | ❌ Discard | Household type + geography subgroup — GED survey family |
| 23 | `DF_GED_PLFP_SEX_HHT_RT` | HHT | ❌ Discard | Household type subgroup — GED survey family |

### Decision

**`DF_EAP_DWAP_SEX_AGE_RT`** — single candidate after all filtering steps. No cross-check needed.

---

## Special Check 1 — Youth unemployment age code

Youth unemployment has no standalone survey flow — all 14 flows are modelled estimates. The approach is to filter `DF_UNE_DEAP_SEX_AGE_RT` by the youth age group.

**Confirmed age codes available in `DF_UNE_DEAP_SEX_AGE_RT` (Brazil, 2020–2023):**

| Code | Meaning |
|---|---|
| `AGE_YTHADULT_YGE15` | All workers aged 15 and above — the standard working-age total. **This is our default** |
| `AGE_YTHADULT_Y15-24` | Youth — workers aged 15 to 24. **Use this for youth unemployment** |
| `AGE_YTHADULT_Y15-64` | Working-age adults 15–64 |
| `AGE_YTHADULT_YGE25` | Adults 25 and above |
| `AGE_AGGREGATE_YGE15` | Same as YGE15 but under a different grouping scheme |
| `AGE_AGGREGATE_Y15-24` | Youth under the aggregate grouping |
| `AGE_AGGREGATE_Y25-54` | Prime working-age adults |
| `AGE_AGGREGATE_Y55-64` | Older workers approaching retirement |
| `AGE_AGGREGATE_YGE65` | Retirement-age workers |
| `AGE_10YRBANDS_Y15-24` | Youth in 10-year bands |
| `AGE_10YRBANDS_Y25-34` | through `Y55-64` — decade breakdowns |
| `AGE_5YRBANDS_Y15-19` | through `Y60-64` — five-year breakdowns |

**Use `AGE_YTHADULT_Y15-24` for youth unemployment.** It is in the same classification scheme as the default (`AGE_YTHADULT_YGE15`), making the swap straightforward.

---

## Special Check 2 — Wages: PPP vs LCU

`DF_EAR_EMTA_SEX_CUR_NB` for France returns equal row counts for all three currency types: 9 annual rows each for LCU, PPP, and USD.

| CUR code | Meaning | When to use |
|---|---|---|
| `CUR_TYPE_LCU` | Local Currency Unit — the country's own money (EUR for France, NGN for Nigeria, BRL for Brazil) | Default for country-level trend analysis |
| `CUR_TYPE_PPP` | Purchasing Power Parity — a normalized unit that removes price-level differences so earnings in different countries are directly comparable | Cross-country comparison only |
| `CUR_TYPE_USD` | US Dollars at current market exchange rates | Cross-country comparison, but sensitive to exchange rate swings |

**Decision:** LCU remains the only canonical for v1. Cross-country wage comparison is not in scope. PPP is available in the same flow if needed later.

---

## Final canonical table

| # | Concept | Flow ID | Why chosen |
|---|---|---|---|
| 1 | Unemployment rate | `DF_UNE_DEAP_SEX_AGE_RT` | Only general survey flow out of 34. The main ILO LFS unemployment series |
| 2 | Employment-to-pop ratio | `DF_EMP_DWAP_SEX_AGE_RT` | Only general survey flow out of 32 |
| 3 | Average monthly earnings | `DF_EAR_EMTA_SEX_CUR_NB` | Best of 13 candidates: all employees, whole economy, with CUR dim, 5/5 countries |
| 4 | LFPR | `DF_EAP_DWAP_SEX_AGE_RT` | Only general survey flow out of 30. New addition confirmed by this discovery |

**Youth unemployment:** use flow #1 with `AGE=AGE_YTHADULT_Y15-24`.
**Wages PPP:** available in flow #3 with `CUR=CUR_TYPE_PPP`; not exposed as separate canonical for v1.

**Confidence level: HIGH for all four.** Every flow enumerated, evaluated, and documented.
