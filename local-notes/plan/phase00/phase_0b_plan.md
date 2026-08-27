# Phase 0b — Remaining Data Discoveries

Date planned: 2026-07-24

## What and why

Phase 0a confirmed the SDMX API works, found break countries for employment (Nigeria) and wages (Thailand), and established the general data shape. But it left a set of specific data questions unanswered — mostly things that couldn't be checked until we had the full question list. Phase 0b closes those gaps. There are two types: questions that must be answered before the benchmark questions can be handed to a human for ground truth lookup (she can't fill in values for questions that are incomplete or wrongly categorised), and questions that must be answered before Phase 1 coding can start (because they affect what `sdmx_client.py` and `indicators.py` need to handle). Nothing in Phase 1 gets written until this phase is done.

---

## Unknowns to resolve

### Group A — Benchmark question correctness

These affect the category, expected response type, or feasibility of specific questions. Wrong answers here mean the benchmark tests the wrong thing.

---

#### A1. Nigeria break years (q003, q018)

**What:** Find the exact years where Nigeria's employment data has a source change.  
**Why:** Both q003 and q018 have `has_break: true` but `break_years: null`. Kanza can't fill ground truth without knowing which years the break falls on, and the benchmark can't check whether the tool correctly identifies the break year.

Pull `DF_UNE_3EAP_SEX_AGE_DSB_RT` for NGA, 2010–2023. Extract SOURCE per observation row and find where it changes.

**Expected:** 1–2 break years between 2010 and 2022. Record exact years in q003 and q018.

---

#### A2. Thailand wage break years (q020)

**What:** Find the exact year(s) where Thailand's wage data in `DF_EAR_CMTA_SEX_CUR_NB` has a source change.  
**Why:** q020 has `has_break: true` but `break_years: null`. Same problem as A1 — can't fill ground truth without the year, and can't verify the tool correctly flags it.

Pull `DF_EAR_CMTA_SEX_CUR_NB` for THA, 2010–2023. Extract SOURCE per row, find change points.

**Expected:** At least one year where SOURCE switches from LFS to HIES. Record exact year(s) in q020.

---

#### A3. Thailand employment break check (q017)

**What:** Check whether Thailand's employment (unemployment rate) series also has a methodology break between 2015 and 2022.  
**Why:** q017 is currently categorised `answerable_clean`, meaning no break. We confirmed THA has a wage break, but never checked the employment series. If THA employment also has a break inside 2015–2022, the category is wrong and the expected response type changes from `exact_answer` to `warn_and_answer`.

Pull the main survey unemployment dataflow for THA, 2015–2022. Check SOURCE uniqueness.

**Decision:** If break found inside range → recategorise q017 to `answerable_break`, set `correct_response_type: warn_and_answer`. If clean → confirm `answerable_clean`.

---

#### A4. Vietnam wage coverage for q029

**What:** Check whether Vietnam (VNM) has wage data in the same period (2018–2022) as Thailand for the comparison question.  
**Why:** q029 asks which country had higher wage growth between THA and VNM. If VNM has no wage data in that range, the question is unanswerable — wrong category (`comparative` → `unanswerable_no_data`).

Pull the same EAR dataflow used for THA, filter to VNM, 2018–2022. Also check if THA's wage break falls inside 2018–2022 (already confirmed it exists, just need the exact year from A2 to know).

**Decision:**
- VNM has data + THA break inside range → q029 is `answerable_break` (not `comparative`)  
- VNM has data + THA break outside range → q029 stays `comparative`, `exact_answer`
- VNM has no data → q029 becomes `unanswerable_no_data`

---

#### A5. 2023 data availability for q011 (Malaysia vs Singapore)

**What:** Check whether 2023 unemployment data is published in ILOSTAT for both Malaysia (MYS) and Singapore (SGP).  
**Why:** q011 asks which country had a lower unemployment rate in 2023. ILOSTAT has publication lags — if only one country has 2023 data, the comparison fails in a confusing way. If neither has 2023, shift the question to 2022.

Pull the main unemployment dataflow for both MYS and SGP, check what the latest available year is.

**Decision:** If 2023 available for both → keep as-is. If not → update `start_year`/`end_year` to the most recent year both have in common.

---

#### A6. Data availability for ambiguous questions (q009, q027, q028)

**What:** Check whether the countries in the three ambiguous questions actually have data — Georgia wages (q009), Congo unemployment (q027), Guinea wages (q028).  
**Why:** These questions are categorised `disambiguate` — meaning the agent should ask which Georgia/Congo/Guinea we mean. But if none of the candidate countries have data, the correct behaviour is `abstain_no_data` after disambiguation, not a data answer. We need to know this so the expected response type is accurate.

- q009: Pull EAR dataflow for GEO (Georgia the country). Does it have wage data?
- q027: Pull unemployment dataflow for COG and COD. Does either have data in 2021?
- q028: Pull EAR dataflow for GIN, GNQ, GNB. Does any have wage data?

**Decision per question:** If any candidate country has data → keep `disambiguate`. If none do → update `notes` to reflect that after disambiguation the answer is still "no data available".

---

### Group B — Missing question specifications

These questions have `dataflow_id: null` or missing year/break info. They need to be filled before the lookup sheet can be given to Kanza.

---

#### B1. Employment-to-population dataflow ID (q013)

**What:** Find the correct ILOSTAT dataflow ID for employment-to-population ratio and confirm it returns data for Germany (DEU) in 2019.  
**Why:** q013 asks for Germany's employment-to-population ratio. Without the right dataflow ID, the tool either can't find the data or fetches the wrong thing, and there's no way to fill in the correct ground truth value.

Search catalog for "employment to population" or "EMP_DWAP". Pull for DEU, 2019. Confirm data is present and note the unit (% of working-age population).

**Output:** Lock `dataflow_id` in q013.

---

#### B2. Youth unemployment dataflow + AGE code (q016)

**What:** Find the dataflow and correct AGE dimension code for youth (15–24) unemployment, and confirm it returns data for South Africa (ZAF) in 2021.  
**Why:** q016 asks for South Africa's youth unemployment rate. The standard unemployment dataflows cover all ages — we need the specific youth breakdown and the AGE code to filter to it, otherwise the tool returns the wrong number.

Search for youth unemployment flows (look for "AGE_Y" or "Y15-24" in dimension codelists). Confirm ZAF has youth data in 2021. Note exact AGE code.

**Output:** Lock `dataflow_id` in q016, note the AGE code for `sdmx_client.py`.

---

#### B3. Pakistan employment break within 2010–2020 (q019)

**What:** Confirm that Pakistan's employment SOURCE change actually falls inside the 2010–2020 date range in `DF_UNE_DEAP_SEX_AGE_RT`.  
**Why:** q019 asks for CAGR of Pakistan employment 2010–2020, and expects `warn_and_answer` because of a break. If the break falls outside that range (e.g. 2021), the question's expected response type is wrong — there's no break to warn about in the requested period.

Pull `DF_UNE_DEAP_SEX_AGE_RT` for PAK, 2010–2020. Check SOURCE per row.

**Decision:** Break inside 2010–2020 → confirm `warn_and_answer`, record `break_years`. Break outside → change `correct_response_type` to `exact_answer`, `has_break: false` for this range.

---

#### B4. Pakistan wage break (q004)

**What:** Check whether Pakistan has a SOURCE change in any EAR (wages) dataflow.  
**Why:** q004 is currently a placeholder — it uses PAK but notes "swap country if wage break not found". We need to either confirm PAK has a wage break (and lock the dataflow ID and break year) or pick a different country so the question can be finalised.

Pull the main EAR dataflows for PAK. Check SOURCE uniqueness across rows.

**Decision:** Break found → lock dataflow ID and break year in q004. No break found → swap to a country from the list in `discovery_results_2.md` (e.g. a confirmed EAR break country from Phase 0a), update q004 question text and entities.

---

#### B5. Somalia coverage (q021)

**What:** Check whether Somalia (SOM) returns a 404 (no data at all) or returns modelled estimates when queried in the main unemployment dataflow.  
**Why:** q021 expects `abstain_no_data`. If ILOSTAT returns modelled estimates for SOM, the tool must not present those as real data — which is a different (harder) case than a clean 404. We need to know which case we're dealing with so the notes are accurate and the behaviour we're testing for is correct.

Pull unemployment dataflow for SOM, 2023. Check whether the response is a 404, an empty result, or contains data rows (and if so, what `data_type` they have).

**Output:** Update q021 notes with confirmed behaviour.

---

#### B6. EU aggregate code in CL_AREA (q023)

**What:** Check whether "European Union" or any EU aggregate exists as a country code in ILOSTAT's area codelist.  
**Why:** q023 expects `abstain_no_data` with the explanation that ILOSTAT doesn't have an EU aggregate. But if ILOSTAT does have an EU aggregate code, the question's premise is wrong and the expected behaviour changes.

Check `CL_AREA` for entries containing "EU", "European Union", or "EUU". Also try pulling unemployment data for any EU aggregate code found.

**Output:** Confirm no EU aggregate exists (or update q023 if one does).

---

#### B7. Canonical dataflow IDs for all answerable questions

**What:** For every question with `dataflow_id: null` that is expected to return real data, find and record the specific ILOSTAT dataflow the tool will use.  
**Why:** Kanza needs to query the exact same dataflow to pull ground truth values. If she queries the wrong flow (e.g. modelled estimates instead of survey data), the ground truth values will be wrong and the benchmark will be comparing against the wrong number.

Questions needing a dataflow ID locked:
- q001 (MYS unemployment 2022)
- q002 (SGP wages 2021)
- q010 (FRA/DEU wages 2020–2023)
- q011 (MYS/SGP unemployment 2023)
- q013 (DEU emp-to-pop 2019) ← also covered in B1
- q014 (FRA wages 2022)
- q015 (BRA unemployment 2018)
- q016 (ZAF youth unemployment 2021) ← also covered in B2
- q017 (THA unemployment 2015–2022)
- q019 (PAK employment CAGR 2010–2020)
- q029 (THA/VNM wages 2018–2022)
- q030 (ESP/ITA unemployment 2010–2023)

For each: identify the correct survey dataflow, confirm it returns data for the country and year, and write the ID into the JSON.

---

### Group C — Phase 1 coding decisions

These don't affect the benchmark questions directly but must be decided before writing `sdmx_client.py`.

---

#### C1. MEASURE dimension cardinality

**What:** Check whether each dataflow has one MEASURE value or multiple — and if multiple, how to pick the right one.  
**Why:** If a dataflow returns both "unemployment rate" and "unemployment count" as separate MEASURE values, `sdmx_client.py` needs a filter. If there's always exactly one measure per flow, no filter is needed. Getting this wrong means the data layer silently returns mixed or duplicate rows.

Pull a few employment and wage dataflows and check unique MEASURE values in the response.

**Decision:** One value → no filter needed. Multiple → add a MEASURE filter parameter to `sdmx_client.py`.

---

#### C2. `indicators.py` design decision

**What:** Decide what `indicators.py` stores — a mapping from theme name to one canonical dataflow ID, or to a list of related IDs.  
**Why:** The tool uses `indicators.py` to go from a theme like "unemployment" to the right dataflow. If we store only one ID per theme, the code is simple but may miss edge cases (e.g. youth unemployment is a different flow). If we store a list, `search_indicators` has more to work with but the selection logic is harder.

This decision is informed by B1, B2, and B7 above — once we know all the dataflow IDs in use, the right structure becomes clear.

**Decision:** Lock the structure of `indicators.py` before writing any Phase 1 code.

---

## Output

`execution/phase00/`:
- `scratch_phase0b.py` — script covering all API checks (Groups A and B)
- `phase0b_results.md` — findings, decisions locked, updated question entries

`benchmark/`:
- `benchmark_questions.json` — updated with locked `dataflow_id` values, corrected categories, filled `break_years`, updated question text where needed

**Decisions to lock:**

| Decision | Unknown |
|---|---|
| NGA break years | A1 |
| THA wage break years | A2 |
| q017 category (clean or break) | A3 |
| q029 category and feasibility | A4 |
| q011 year (2023 or earlier) | A5 |
| Ambiguous question expected behaviours | A6 |
| Emp-to-pop dataflow ID | B1 |
| Youth unemployment dataflow + AGE code | B2 |
| PAK employment break in range | B3 |
| PAK wage break country (confirmed or swapped) | B4 |
| Somalia response type | B5 |
| EU aggregate existence | B6 |
| All answerable question dataflow IDs | B7 |
| MEASURE dimension filter needed | C1 |
| `indicators.py` structure | C2 |

## Timing

All of Group A and B can run now against the live API. Group C decisions follow naturally once B7 is complete — do C1 and C2 last in the same session.
