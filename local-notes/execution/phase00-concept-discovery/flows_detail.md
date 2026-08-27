# Flows Detail — Canonical Flows Reference

Date: 2026-08-28
Source: Live ILOSTAT SDMX API (`sdmx1` + `cloudscraper`).
All sample rows are real API responses, not fabricated.

---

## How to read this file

This covers the four canonical flows chosen in `results.md`. For each flow:
- **What it measures** — the definition in plain English
- **Key parameters** — the filter values used to get the standard (total) data
- **Sample data** — real rows from a test country, 2013–2024, annual total
- **Notes** — anything unusual about this specific flow

The column reference below explains every column and every categorical value once, so the per-flow sections only call out what's different.

---

## sdmx1 API call note

To get all columns (including OBS_STATUS, SOURCE, and other observation attributes), the `attributes` parameter must be set:

```python
resp = client.data(flow_id, key={...}, params={...})
df = sdmx.to_pandas(resp, attributes="o").reset_index()
```

Without `attributes="o"`, the returned DataFrame has only dimension columns and `value`. Observation attributes (OBS_STATUS, SOURCE, etc.) are silently omitted.

---

## Column reference

Every flow returns these columns. Dimensions appear first (they are the key that uniquely identifies a row), then `value`, then observation attributes.

### Dimension columns

**`REF_AREA`** — Which country the row is from. ISO 3166-1 alpha-3 codes: `NGA` = Nigeria, `BRA` = Brazil, `FRA` = France, `DEU` = Germany, `MYS` = Malaysia, and so on. Full list via `get_countries()`.

**`FREQ`** — How often the observation was collected.

| Value | Meaning |
|---|---|
| `A` | Annual — one number per calendar year |
| `Q` | Quarterly — one number per quarter (e.g. `2022-Q3`) |
| `M` | Monthly — one number per month (e.g. `2022-11`) |

Our tools default to `FREQ=A`. Not all flows provide all frequencies — wages (`DF_EAR_EMTA_SEX_CUR_NB`) is annual only; unemployment and LFPR have quarterly and monthly in some countries.

**`MEASURE`** — The specific metric ID. Constant within a flow — every row in `DF_UNE_DEAP_SEX_AGE_RT` has `MEASURE=UNE_DEAP_RT`, for example. Not used as a filter in our tools.

**`SEX`** — Sex of the workers the row covers.

| Value | Meaning |
|---|---|
| `SEX_T` | Total — both sexes combined. **Our default** |
| `SEX_M` | Male workers only |
| `SEX_F` | Female workers only |

**`AGE`** — Age group of the workers (present in unemployment, emp-to-pop, LFPR flows; absent in wages). The full classification tree has five sub-families:

*Standard working-age groups (the main ones):*

| Value | Meaning |
|---|---|
| `AGE_YTHADULT_YGE15` | All workers aged 15 and above — the standard working-age total. **Our default** |
| `AGE_YTHADULT_Y15-24` | Youth — workers aged 15 to 24. **Use this for youth unemployment** |
| `AGE_YTHADULT_Y15-64` | Working-age adults 15–64 |
| `AGE_YTHADULT_YGE25` | Adults 25 and above |

*Aggregate bands:*

| Value | Meaning |
|---|---|
| `AGE_AGGREGATE_YGE15` | Same population as YGE15, alternate grouping code |
| `AGE_AGGREGATE_Y15-24` | Youth, alternate grouping |
| `AGE_AGGREGATE_Y25-54` | Prime working-age adults |
| `AGE_AGGREGATE_Y55-64` | Older workers approaching retirement |
| `AGE_AGGREGATE_YGE65` | Retirement-age workers still in the labour force |

*10-year bands:* `AGE_10YRBANDS_Y15-24`, `Y25-34`, `Y35-44`, `Y45-54`, `Y55-64`

*5-year bands:* `AGE_5YRBANDS_Y15-19`, `Y20-24`, `Y25-29`, …, `Y60-64`

**`CUR`** — Currency type. Present in wages flow only; absent in all rate flows.

| Value | Meaning |
|---|---|
| `CUR_TYPE_LCU` | Local Currency Unit — the country's own currency (EUR for France, NGN for Nigeria, BRL for Brazil, etc.). **Our default** |
| `CUR_TYPE_PPP` | Purchasing Power Parity — a normalized unit that removes price-level differences between countries so earnings are directly comparable internationally |
| `CUR_TYPE_USD` | US Dollars at current market exchange rates — also comparable across countries, but exchange-rate movements distort year-on-year trends |

**`TIME_PERIOD`** — The year (for annual data: `"2022"`) or period (for quarterly: `"2022-Q3"`, for monthly: `"2022-11"`).

### Value column

**`value`** — The actual number.

For rate flows (`UNIT_MEASURE=PT`): a percentage expressed as 0–100. An unemployment rate of 8.4 means 8.4% of the labour force is unemployed.

For earnings flows (`UNIT_MEASURE=CR`): average monthly earnings in the stated currency. A value of 2196.954 with `CUR_TYPE_LCU` in France means €2,196.95 per month on average.

### Observation attribute columns

**`OBS_STATUS`** — Whether this observation is normal or flagged.

| Value | Meaning |
|---|---|
| `''` (empty string) | Normal — the observation is clean and reliable |
| `'B'` | Break in series — the methodology changed at this point. The number is real but not directly comparable to the previous observations in the same series |
| `'U'` | Unavailable — the observation exists as a slot in the series but no value could be reported |

Note: OBS_STATUS='B' is ILOSTAT's own flag. Our break detection also catches breaks that ILOSTAT does *not* flag: a SOURCE change between consecutive rows signals a methodology shift even without a 'B' status.

**`UNIT_MEASURE_TYPE`** — What category of measure this is.

| Value | Meaning |
|---|---|
| `RT` | Rate — the value is a ratio or proportion (unemployment rate, LFPR, emp-to-pop) |
| `NB` | Nominal balance — the value is a count or monetary amount (earnings) |

**`UNIT_MEASURE`** — The unit the value is expressed in.

| Value | Meaning |
|---|---|
| `PT` | Percentage — value is a percentage (0–100) |
| `CR` | Currency — value is a monetary amount in the currency specified by CUR |

**`UNIT_MULT`** — A multiplier for the value field. `0` means 10^0 = 1, i.e. no multiplication needed — the number is what it says. `3` would mean multiply by 1000 (not seen in these four flows).

**`SOURCE`** — The name of the national survey that provided the data for this row. This is the key column for methodology break detection. If SOURCE changes between consecutive rows in the same series, the survey changed — the numbers before and after are not from the same instrument and may not be comparable.

Common SOURCE prefixes:
- `LFS` — Labour Force Survey. The gold-standard household survey for labour statistics. Most countries.
- `HIES` — Household Income and Expenditure Survey. Broader survey repurposed for labour stats; different questionnaire design.
- `HS` — Household Survey. General-purpose household survey.

Examples from our sample data:
- `"LFS - Unemployment, Under-employment Watch"` — Nigeria's labour force survey
- `"LFS - EU Labour Force Survey"` — EU's harmonized labour force survey (used by Germany)
- `"LFS - Enquête sur l'emploi"` — France's labour force survey
- `"HS - Pesquisa Nacional por Amostra de Domicílios Contínua"` — Brazil's continuous household survey (PNADC)
- `"HS - General Household Survey"` — Nigeria's older general household survey (used in 2013 before LFS was established)
- `"HIES - Living Standards Survey"` — Nigeria's household income/expenditure survey (used in 2019 when LFS was not fielded)

**`NOTE_SOURCE`** — Supplementary note about the data source. Often `"Repository: ILO-STATISTICS - Micro data processing"` (meaning ILO re-processed the raw microdata). Can also flag coverage limitations: `"Age coverage - maximum age: 64 years old"` means the survey only interviewed people up to age 64, even though the flow's AGE code implies 15+.

**`NOTE_INDICATOR`** — Notes about the indicator definition itself. Usually empty.

**`NOTE_CLASSIF`** — Notes about classification. When OBS_STATUS='B', this field often says `"Break in series: Methodology revised"` or similar. Usually empty for clean observations.

**`DECIMALS`** — The number of decimal places reported. `1` for rate flows (e.g. 8.4%), `2` for earnings flows (e.g. 2196.95). Values from the API may have more decimals; this is the stated precision.

**`UPPER_BOUND`** / **`LOWER_BOUND`** — Confidence bounds for the estimate. Almost always empty — ILOSTAT rarely publishes confidence intervals in SDMX form.

---

## Flow 1 — Unemployment Rate

**Flow ID:** `DF_UNE_DEAP_SEX_AGE_RT`

**What it measures:** The share of the labour force that is unemployed. A person is counted as unemployed if they are: (1) without a job, (2) currently available to take a job, and (3) actively looking for work. The denominator is the labour force — employed plus unemployed. Someone who has given up looking for work is not counted as unemployed (they fall out of the labour force entirely). Definition follows the 13th ICLS (1982) standard.

**Unit:** Percentage (0–100). A value of 8.4 means 8.4% of the labour force is unemployed.

**Default filters:** `SEX=SEX_T`, `AGE=AGE_YTHADULT_YGE15`, `FREQ=A`
**Youth variant:** `AGE=AGE_YTHADULT_Y15-24`

**Test country:** Nigeria (NGA) — chosen because it has three different SOURCE values across 2013–2024, making break detection clearly visible.

**Sample data (annual, total, 2013–2024):**

| TIME_PERIOD | value | OBS_STATUS | UNIT_MEASURE | SOURCE | NOTE_SOURCE |
|---|---|---|---|---|---|
| 2013 | 3.711 | | PT | HS - General Household Survey | Repository: ILO-STATISTICS - Micro data processing |
| 2014 | 4.562 | | PT | LFS - Unemployment, Under-employment Watch | Age coverage - maximum age: 64 years old |
| 2015 | 4.311 | | PT | LFS - Unemployment, Under-employment Watch | Age coverage - maximum age: 64 years old |
| 2016 | 7.060 | | PT | LFS - Unemployment, Under-employment Watch | Age coverage - maximum age: 64 years old |
| 2017 | 8.389 | | PT | LFS - Unemployment, Under-employment Watch | Age coverage - maximum age: 64 years old |
| *2018* | *missing* | | | | |
| 2019 | 4.448 | | PT | HIES - Living Standards Survey | Repository: ILO-STATISTICS - Micro data processing |
| *2020* | *missing* | | | | |
| *2021* | *missing* | | | | |
| 2022 | 3.827 | | PT | LFS - Unemployment, Under-employment Watch | Repository: ILO-STATISTICS - Micro data processing |
| 2023 | 3.074 | | PT | LFS - Unemployment, Under-employment Watch | Repository: ILO-STATISTICS - Micro data processing |
| 2024 | 3.454 | **B** | PT | LFS - Unemployment, Under-employment Watch | Repository: ILO-STATISTICS - Micro data processing |

**Break detection demonstration:**

This series has three distinct methodology breaks, all detectable from SOURCE:

1. **2013 → 2014**: SOURCE changes from "HS - General Household Survey" to "LFS". Nigeria introduced a dedicated labour force survey in 2014. Numbers before and after are not methodologically comparable.

2. **2017 → 2019**: SOURCE changes from "LFS" to "HIES - Living Standards Survey". Nigeria did not field the LFS in 2018, 2019, so ILOSTAT used a household expenditure survey instead. Note the implausible swing: unemployment went from 8.4% in 2017 to 4.4% in 2019 under a completely different survey instrument.

3. **2024**: OBS_STATUS = 'B'. ILOSTAT's own flag — the methodology was revised within the LFS (SOURCE stays the same, but ILO flagged a definitional change). Our break detector catches #1 and #2 via SOURCE diff; ILOSTAT's B flag catches #3.

**Years 2018, 2020, 2021 are absent** — no survey was conducted or accepted for those years.

---

## Flow 2 — Employment-to-Population Ratio

**Flow ID:** `DF_EMP_DWAP_SEX_AGE_RT`

**What it measures:** The share of the working-age population that is employed. A person is counted as employed if they did any paid work during the reference week, even one hour. The denominator is the entire working-age population (15+), not just the labour force — this includes people who are not looking for work (students, caregivers, retirees). When this ratio falls, it could mean more unemployment, or simply more people choosing not to work. When it rises alongside a falling unemployment rate, the economy is genuinely creating jobs.

**Unit:** Percentage (0–100). A value of 58.9 means 58.9% of the working-age population has a job.

**Default filters:** `SEX=SEX_T`, `AGE=AGE_YTHADULT_YGE15`, `FREQ=A`

**Test country:** Brazil (BRA) — consistent series from 2013–2024 from a single survey (PNAD Contínua), no breaks. Shows the COVID employment shock in 2020.

**Sample data (annual, total, 2013–2024):**

| TIME_PERIOD | value | OBS_STATUS | UNIT_MEASURE | SOURCE |
|---|---|---|---|---|
| 2013 | 59.217 | | PT | HS - Pesquisa Nacional por Amostra de Domicílios Contínua |
| 2014 | 59.224 | | PT | HS - Pesquisa Nacional por Amostra de Domicílios Contínua |
| 2015 | 58.358 | | PT | HS - Pesquisa Nacional por Amostra de Domicílios Contínua |
| 2016 | 56.479 | | PT | HS - Pesquisa Nacional por Amostra de Domicílios Contínua |
| 2017 | 55.973 | | PT | HS - Pesquisa Nacional por Amostra de Domicílios Contínua |
| 2018 | 56.308 | | PT | HS - Pesquisa Nacional por Amostra de Domicílios Contínua |
| 2019 | 56.953 | | PT | HS - Pesquisa Nacional por Amostra de Domicílios Contínua |
| 2020 | 52.031 | | PT | HS - Pesquisa Nacional por Amostra de Domicílios Contínua |
| 2021 | 54.076 | | PT | HS - Pesquisa Nacional por Amostra de Domicílios Contínua |
| 2022 | 57.499 | | PT | HS - Pesquisa Nacional por Amostra de Domicílios Contínua |
| 2023 | 57.768 | | PT | HS - Pesquisa Nacional por Amostra de Domicílios Contínua |
| 2024 | 58.909 | | PT | HS - Pesquisa Nacional por Amostra de Domicílios Contínua |

**Notable:** SOURCE is identical for all 12 years — Brazil's PNAD Contínua has been the survey of record since 2012. No break detection flags will fire. The COVID shock (2020: 52.0%) is structural — fewer people actually had jobs — not an artifact of a survey change. The series has fully recovered and exceeded pre-COVID levels by 2024.

**FREQ available:** Annual (A) and Quarterly (Q). Quarterly is useful for tracking within-year labour market dynamics.

---

## Flow 3 — Average Monthly Earnings

**Flow ID:** `DF_EAR_EMTA_SEX_CUR_NB`

**What it measures:** The mean (average) gross monthly earnings of employees — what a worker takes home on average before taxes, expressed per month. "Employees" are paid workers; self-employed people are excluded. "Gross" means before income tax and social security deductions (the pre-tax number). This is an average, not a median — it is pulled up by high earners.

**Unit:** Currency (`UNIT_MEASURE=CR`). The specific currency depends on `CUR`: with `CUR_TYPE_LCU`, France reports in EUR, Nigeria in NGN, Brazil in BRL. The UNIT_MEASURE field alone says "currency" — the actual currency symbol comes from context (country + CUR).

**Default filters:** `SEX=SEX_T`, `CUR=CUR_TYPE_LCU`, `FREQ=A`

**Test country:** France (FRA) — clean annual series from 2013–2024, no breaks, no missing years. France's LFS is one of Europe's highest-quality labour surveys.

**Sample data (annual, total, LCU, 2013–2024):**

| TIME_PERIOD | value (EUR) | OBS_STATUS | UNIT_MEASURE | SOURCE |
|---|---|---|---|---|
| 2013 | 1,826.34 | | CR | LFS - Enquête sur l'emploi |
| 2014 | 1,843.54 | | CR | LFS - Enquête sur l'emploi |
| 2015 | 1,851.13 | | CR | LFS - Enquête sur l'emploi |
| 2016 | 1,866.95 | | CR | LFS - Enquête sur l'emploi |
| 2017 | 1,889.21 | | CR | LFS - Enquête sur l'emploi |
| 2018 | 1,931.65 | | CR | LFS - Enquête sur l'emploi |
| 2019 | 1,986.28 | | CR | LFS - Enquête sur l'emploi |
| 2020 | 2,015.55 | | CR | LFS - Enquête sur l'emploi |
| 2021 | 1,985.78 | | CR | LFS - Enquête sur l'emploi |
| 2022 | 2,027.80 | | CR | LFS - Enquête sur l'emploi |
| 2023 | 2,114.85 | | CR | LFS - Enquête sur l'emploi |
| 2024 | 2,196.95 | | CR | LFS - Enquête sur l'emploi |

**Notable:**

*This flow has no `AGE` dimension* — it is broken down by SEX and CUR only. There is a separate flow for age-disaggregated earnings (`DF_EAR_EMTA_SEX_AGE_CUR_NB`) but that is a subgroup flow, not canonical.

*FREQ = Annual only* (unlike the rate flows which also offer quarterly). ILOSTAT does not publish sub-annual average earnings from national surveys in this flow.

*DECIMALS = 2* — earnings are reported to two decimal places, compared to one decimal for rate flows.

*2020 paradox*: average earnings went up (€2,015 vs €1,986 in 2019) during COVID despite the overall crisis. This is a composition effect: COVID job losses fell disproportionately on lower-paid workers (hospitality, retail). With fewer low-wage workers in the sample, the average pulled higher. This is a well-documented statistical artifact, not a sign that workers were better off.

*CUR_TYPE_PPP is available in the same flow* — use `CUR=CUR_TYPE_PPP` for international comparison (not exposed as a v1 tool default).

---

## Flow 4 — Labour Force Participation Rate (LFPR)

**Flow ID:** `DF_EAP_DWAP_SEX_AGE_RT`

**What it measures:** The share of the working-age population that is in the labour force — either employed or actively looking for work. Someone who has given up looking for work is not in the labour force and not counted. A falling LFPR can mean more people are discouraged (bad sign) or that more people are choosing not to work (retirement, education — context-dependent). A rising LFPR, especially among women or youth, is typically a positive structural shift.

**Unit:** Percentage (0–100). A value of 61.8 means 61.8% of the working-age population is either employed or actively job-hunting.

**Relationship to other flows:** LFPR and emp-to-pop move together in most conditions. The gap between them equals the unemployment rate's contribution: `LFPR ≈ emp-to-pop + (unemployment rate × LFPR / 100)`.

**Default filters:** `SEX=SEX_T`, `AGE=AGE_YTHADULT_YGE15`, `FREQ=A`

**Test country:** Germany (DEU) — consistent series from EU Labour Force Survey, no breaks. Germany has one of Europe's more stable LFPRs, with a slow upward trend driven by increasing female participation.

**Sample data (annual, total, 2013–2024):**

| TIME_PERIOD | value | OBS_STATUS | UNIT_MEASURE | SOURCE |
|---|---|---|---|---|
| 2013 | 60.369 | | PT | LFS - EU Labour Force Survey |
| 2014 | 60.436 | | PT | LFS - EU Labour Force Survey |
| 2015 | 60.215 | | PT | LFS - EU Labour Force Survey |
| 2016 | 61.028 | | PT | LFS - EU Labour Force Survey |
| 2017 | 61.242 | | PT | LFS - EU Labour Force Survey |
| 2018 | 61.264 | | PT | LFS - EU Labour Force Survey |
| 2019 | 61.966 | | PT | LFS - EU Labour Force Survey |
| 2020 | 60.558 | | PT | LFS - EU Labour Force Survey |
| 2021 | 60.661 | | PT | LFS - EU Labour Force Survey |
| 2022 | 61.038 | | PT | LFS - EU Labour Force Survey |
| 2023 | 61.672 | | PT | LFS - EU Labour Force Survey |
| 2024 | 61.848 | | PT | LFS - EU Labour Force Survey |

**Notable:** SOURCE is identical for all 12 years (EU LFS — Eurostat's harmonized survey, common to all EU member states). No break detection flags will fire. The COVID dip (2020: 60.6%) was mild relative to Brazil's emp-to-pop shock — in Germany, people mostly left the labour force temporarily (furloughed workers were counted as employed if receiving income), and the structural participation rate resumed its upward trend by 2021.

**FREQ available:** Annual (A) and Quarterly (Q). Quarterly is especially useful for LFPR because participation shifts can be seasonal (students entering/leaving in summer), and quarterly data shows those patterns.

---

## Summary of column differences by flow

| Column | UNE (unemployment) | EMP (emp-to-pop) | EAR (wages) | EAP (LFPR) |
|---|---|---|---|---|
| AGE | ✓ | ✓ | ✗ | ✓ |
| CUR | ✗ | ✗ | ✓ | ✗ |
| FREQ options | A, Q, M | A, Q | A only | A, Q |
| UNIT_MEASURE | PT | PT | CR | PT |
| DECIMALS | 1 | 1 | 2 | 1 |
| OBS_STATUS='B' seen | Yes | No (BRA) | No (FRA) | No (DEU) |
| SOURCE changes seen | Yes (NGA) | No (BRA) | No (FRA) | No (DEU) |
