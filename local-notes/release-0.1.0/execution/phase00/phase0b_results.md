# Phase 0b — Results

Date: 2026-07-24
Script: `scratch_phase0b.py`

---

## Group A — Benchmark question correctness

### A1. Nigeria break years (q003, q018) ✓

**Breaks confirmed in `DF_UNE_3EAP_SEX_AGE_DSB_RT` for NGA:**
- 2011: HIES → HS
- 2019: HS → HIES

(Output showed duplicates because multiple sex/age dimension combinations were iterated before fully collapsing. Unique break years: **2011 and 2019**.)

- q003 (2015–2022): break at **2019** falls within range → `warn_and_answer` confirmed
- q018 (2010–2022): breaks at **2011 and 2019** both within range → `warn_and_answer` confirmed

**Action:** Update `break_years` in q003 to `[2019]`, in q018 to `[2011, 2019]`.

---

### A2. Thailand wage break years (q020) ✓

**Breaks confirmed in `DF_EAR_CMTA_SEX_CUR_NB` for THA:**
- 2013: LFS → HIES
- 2014: HIES → LFS

Unique break years: **2013 and 2014**. The source alternates between surveys at these two points.

**Action:** Update `break_years` in q020 to `[2013, 2014]`.

---

### A3. Thailand employment break (q017) ✓

No SOURCE change in either `DF_UNE_DEAP_SEX_AGE_RT` or `DF_UNE_TUNE_SEX_AGE_NB` for THA within 2015–2022. Only source is "LFS - Labour Force Survey" throughout.

**Decision: q017 stays `answerable_clean`.** No changes needed.

---

### A4. Vietnam wage coverage (q029) ✓

VNM has wage data in `DF_EAR_CMTA_SEX_CUR_NB` for all years 2018–2022. THA's breaks (2013 and 2014) fall outside the q029 range (2018–2022), so no break affects this comparison.

**Decision: q029 stays `comparative`, `correct_response_type: exact_answer`.** Lock `dataflow_id: DF_EAR_CMTA_SEX_CUR_NB` for both countries.

---

### A5. 2023 data availability (q011) ⚠️ YEAR CHANGE NEEDED

- MYS: latest available year = **2022**
- SGP: latest available year = **2024**

The two countries have different latest years — MYS doesn't have 2023 data yet. Asking about 2023 means one country can answer and one can't, which tests data-lag behaviour rather than comparison.

**Decision: Change q011 year to 2022.** Both have 2022 data. Update question text and entities.

---

### A6. Ambiguous question data coverage

**q009 — Georgia (GEO) wages:**
404 on primary EAR flow (`DF_EAR_CMTA_SEX_CUR_NB`). GEO has no wage data in the main flow. Further EAR flow search was inconclusive due to error handling. 

**Flag for manual check:** Search ILOSTAT directly for Georgia wages before finalising. If no wage data exists for GEO, update q009 notes to reflect that after disambiguation the answer is still "no data" — but the `disambiguate` response type is still correct (agent should ask first, then report no data).

**q027 — Congo unemployment (COG and COD):**
- COG (Republic of Congo): 404 — no data
- COD (Democratic Republic of Congo): has data for 2020

One of the two Congos has data. **q027 stays `disambiguate`** — the agent must ask which Congo to give a meaningful answer.

**q028 — Guinea wages (GIN, GNQ, GNB):**
- GIN (Guinea): 404
- GNQ (Equatorial Guinea): 404
- GNB (Guinea-Bissau): has wage data for 2022

One of the three Guineas has data. **q028 stays `disambiguate`.**

---

## Group B — Missing question specifications

### B1. Employment-to-population dataflow (q013) ✓

Found: `DF_EMP_2WAP_SEX_AGE_RT` — DEU 2019 returns value `59.368`.

**Note:** The "2" in `2WAP` indicates ILO modelled estimates, not survey data. For Germany (high-reporting country), this is acceptable since modelled estimates are derived from official survey data. Flag for Phase 1: if a survey-based DWAP flow exists, prefer it; otherwise use `2WAP`.

**Action:** Lock `dataflow_id: DF_EMP_2WAP_SEX_AGE_RT` in q013 provisionally.

---

### B2. Youth unemployment dataflow + AGE code (q016) ✓

Found: `DF_UNE_3EAP_SEX_AGE_GEO_RT` — ZAF 2021 has data.

AGE codes available: `AGE_YTHBANDS_Y15-29`, `AGE_YTHBANDS_Y15-19`, `AGE_YTHBANDS_Y20-24`, `AGE_YTHBANDS_Y25-29`.

ILO definition of youth = 15–24. Use `AGE_YTHBANDS_Y15-29` (15–29) as the closest available "youth" code, or note that the 15–24 range can be approximated by using Y15-19 + Y20-24 strata. For the benchmark question, `AGE_YTHBANDS_Y15-29` is sufficient — the question says "youth" without specifying the age band.

**Action:** Lock `dataflow_id: DF_UNE_3EAP_SEX_AGE_GEO_RT` in q016. Note AGE code `AGE_YTHBANDS_Y15-29` in the question notes.

---

### B3. Pakistan employment break within 2010–2020 (q019) ✓

Multiple breaks confirmed in `DF_UNE_DEAP_SEX_AGE_RT` for PAK within 2010–2020:
- 2012: LFS → HIES
- 2013: HIES → LFS
- 2016: LFS → HIES
- 2018: HIES → LFS
- 2020: LFS → HIES

Five SOURCE changes in the requested range. `warn_and_answer` confirmed. Break years: **[2012, 2013, 2016, 2018, 2020]**.

**Action:** Lock `dataflow_id: DF_UNE_DEAP_SEX_AGE_RT`, update `break_years` in q019.

---

### B4. Pakistan wage break (q004) ✓ — NO COUNTRY SWAP NEEDED

PAK has a wage break in `DF_EAR_CMTA_SEX_CUR_NB`. Break years (unique): **2011, 2013, 2016, 2018, 2020, 2021**.

No need to swap country. Lock PAK and this dataflow. Update q004 question to anchor it to a specific range where breaks are confirmed (e.g. "over the past decade" covering 2013–2023 captures multiple breaks).

**Action:** Lock `dataflow_id: DF_EAR_CMTA_SEX_CUR_NB` in q004. Update `has_break: true`, `break_years: [2011, 2013, 2016, 2018, 2020, 2021]`. Keep `correct_response_type: warn_and_answer`.

---

### B5. Somalia (q021) 🚨 QUESTION MUST CHANGE

Somalia HAS data in `DF_UNE_DEAP_SEX_AGE_RT` — 75 rows returned, including a 2022 value of **11.087%**. ILO modelled estimates also exist separately. q021's premise ("Somalia has no data") is wrong.

**Action:** Replace q021 with a question about a country that genuinely has no survey data in ILOSTAT. Candidate: a small island state or post-conflict country confirmed to return 404. Alternatively, reframe to test the modelled-vs-survey distinction using Somalia (since both exist), but that changes what we're testing.

Simplest fix: change country to one that truly returns 404. Verify in a follow-up check before handing to Kanza.

---

### B6. EU aggregate (q023) 🚨 QUESTION MUST CHANGE

EU codes exist in CL_AREA and have unemployment data:
- **X92**: European Union 27 — has unemployment data
- **X82**: European Union 28 — has unemployment data

q023's premise ("EU is not a country code, no data available") is wrong. Asking for the EU unemployment rate would return a real answer.

**Action:** Replace q023 with a question about a supranational entity that genuinely doesn't have an ILOSTAT code — e.g. ASEAN, BRICS, G7, or NATO. Verify the replacement entity has no code in CL_AREA before using.

---

### B7. Canonical dataflow IDs ⚠️ TWO WAGE GAPS

**Confirmed working:**

| Question | Country | Dataflow | Latest year |
|---|---|---|---|
| q001 | MYS unemployment | DF_UNE_DEAP_SEX_AGE_RT | 2022 |
| q010 | FRA wages | DF_EAR_CMTA_SEX_CUR_NB | 2023 |
| q011 | MYS unemployment | DF_UNE_DEAP_SEX_AGE_RT | 2022 |
| q011 | SGP unemployment | DF_UNE_DEAP_SEX_AGE_RT | 2023 (use 2022) |
| q014 | FRA wages | DF_EAR_CMTA_SEX_CUR_NB | 2022 |
| q015 | BRA unemployment | DF_UNE_DEAP_SEX_AGE_RT | 2018 |
| q017 | THA unemployment | DF_UNE_DEAP_SEX_AGE_RT | 2022 |
| q019 | PAK unemployment | DF_UNE_DEAP_SEX_AGE_RT | 2020 |
| q029 | THA/VNM wages | DF_EAR_CMTA_SEX_CUR_NB | 2022 |
| q030 | ESP unemployment | DF_UNE_DEAP_SEX_AGE_RT | 2023 |
| q030 | ITA unemployment | DF_UNE_DEAP_SEX_AGE_RT | 2023 |

**404 — wrong dataflow:**

| Question | Country | Issue |
|---|---|---|
| q002 | SGP wages | `DF_EAR_CMTA_SEX_CUR_NB` returns 404 for Singapore — need correct wage flow for SGP |
| q010 | DEU wages | `DF_EAR_CMTA_SEX_CUR_NB` returns 404 for Germany — need correct wage flow for DEU |

These two need a follow-up check against other EAR flows for SGP and DEU. If neither has wage data in any EAR flow, these questions need to change country or indicator.

---

## Group C — Phase 1 coding decisions

### C1. MEASURE dimension cardinality ✓

Each dataflow has exactly one OBS_VALUE measure. The MEASURE dimension in the data carries a single coded value per flow (e.g. `UNE_DEAP_RT` for unemployment, `EAR_CMTA_NB` for wages). No MEASURE filter is needed in `sdmx_client.py` — filtering by dataflow ID is sufficient.

**Decision: No MEASURE filter needed.**

### C2. `indicators.py` structure

With B7 confirming that the main employment questions all use `DF_UNE_DEAP_SEX_AGE_RT` and the main wage questions use `DF_EAR_CMTA_SEX_CUR_NB` (where available), the natural structure for `indicators.py` is:

```python
THEMES = {
    "unemployment":           "DF_UNE_DEAP_SEX_AGE_RT",
    "employment_to_population": "DF_EMP_2WAP_SEX_AGE_RT",  # provisional — verify survey flow
    "youth_unemployment":     "DF_UNE_3EAP_SEX_AGE_GEO_RT",
    "wages":                  "DF_EAR_CMTA_SEX_CUR_NB",
}
```

`search_indicators` will still do live keyword search for non-canonical queries. `indicators.py` stores the canonical "safe default" per theme — the one `get_time_series` falls back to when the user doesn't specify a dataflow ID.

**Decision: Store one canonical ID per theme. Lock after SGP/DEU wage flow is resolved.**

---

## Open items before handing to Kanza

1. **q021** — replace Somalia with a truly no-data country (verify via API first)
2. **q023** — replace EU with a truly no-code supranational entity (verify ASEAN/BRICS/etc.)
3. **q002** (SGP wages) and **q010** (DEU wages) — find correct EAR dataflow for these two
4. **q009** (Georgia wages) — manual ILOSTAT check to confirm no wage data for GEO
5. **q013** — verify whether a survey-based (DWAP) employment-to-population flow exists for DEU

Once these 5 items are resolved, all 30 questions will have confirmed dataflow IDs and correct categories, and the lookup sheet for Kanza can be produced.
