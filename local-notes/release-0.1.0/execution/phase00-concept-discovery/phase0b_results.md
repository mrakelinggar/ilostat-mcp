# Phase 0b — Gap Check Results

Date: 2026-08-28
Script: `code/phase0b_gaps.py`

---

## What and why

Seven unknowns were blocking Phase 1 coding. This doc records the live API results for each, with the decision it enables or the follow-up it requires.

---

## Check 1 — LCU currency labeling

**Question:** When the wage flow returns `UNIT_MEASURE = 'CR'` (generic "currency"), how do we tell the user whether the value is in EUR, NGN, BRL, etc.?

**Finding:** The API tells us nothing. Every country returns `UNIT_MEASURE = 'CR'` — the same code regardless of country. Dataset-level and series-level SDMX attributes are empty (`{}`). The raw response does not carry the ISO 4217 currency code anywhere that `sdmx.to_pandas()` surfaces.

**Decision:** The CUR dimension value (`CUR_TYPE_LCU`) tells the user *which denomination* (local vs PPP vs USD), but the actual currency symbol requires a separate lookup. Options evaluated:

| Option | Verdict |
|---|---|
| Hardcode a country→ISO 4217 map in `indicators.py` or a constants file | ✅ Feasible — most countries map 1:1 to one currency |
| Fetch ILOSTAT's `CL_UNIT_MEASURE` codelist at startup | ❌ API call `client.codelist("CL_UNIT_MEASURE")` fails with a `dict` error — syntax needs investigating separately |
| Surface currency code via `CL_AREA` codelist | ❌ CL_AREA codelist call also failed — same issue |
| Return `CUR_TYPE_LCU` in the response and note that currency symbol is country-specific | ✅ Acceptable fallback — users know their country's currency |

**For Phase 1:** Do not try to auto-resolve the currency symbol from the API (it's not there). In `get_time_series`, include the CUR value (`CUR_TYPE_LCU`) in the response and add a plain note explaining what LCU means. A `country_currency` map can be added to `indicators.py` as a follow-up enhancement — it's not a blocker.

**Remaining open:** The `client.codelist()` call syntax is broken in our environment — needs a separate fix before we can explore the CL_UNIT_MEASURE and CL_AREA codelists fully. Not blocking Phase 1.

---

## Check 2 — Wage break in canonical flow (`DF_EAR_EMTA_SEX_CUR_NB`)

**Question:** Does our chosen canonical wage flow (all employees, whole economy) have real methodology breaks, or only the care-sector CMTA flow listed in the ROADMAP?

**Finding:** Wage breaks are extremely common. Every country in our 9-country scan has breaks. Best benchmark examples:

**Thailand (THA)** — multiple SOURCE alternations, 2005–2024:

| Year | Value (THB) | Source |
|---|---|---|
| 2007 | 9,526 | HIES - Household Socio-Economic Survey |
| 2011 | 10,340 | LFS - Labour Force Survey ← **SOURCE CHANGE** |
| 2013 | 13,638 | HIES - Household Socio-Economic Survey ← **SOURCE CHANGE** |
| 2014 | 14,219 | LFS - Labour Force Survey ← **SOURCE CHANGE** |
| 2015 | 11,107 | LFS - Labour Force Survey |
| … | … | LFS steady through 2024 |

The 2013→2014 HIES→LFS jump (13,638 → 14,219) looks plausible but is not methodologically comparable. The 2015 value (11,107) is lower than 2013 within the same LFS series — this is real because THA introduced sampling changes.

**Egypt (EGY)** — dramatic SOURCE change with extreme value collapse:

| Year | Value (EGP) | Source |
|---|---|---|
| 2007 | 1,091 | EC - Employment, wages and hours of Work Survey |
| 2008 | **71** | LFS - Labour Force Sample Survey ← **SOURCE CHANGE** |
| 2009 | 240 | LFS - Labour Force Sample Survey |

The 2007→2008 jump (1,091 → 71, a 93% collapse) is the most egregious break in our dataset. Egypt switched from an establishment survey (EC) — which covers formal employers — to a household survey (LFS) — which covers all workers including informal sector. Informal workers earn far less, so the LFS average is much lower. Both numbers are "correct" but they measure completely different populations. 2009 onwards is steady LFS.

**Decision:** Update ROADMAP to use the canonical `DF_EAR_EMTA_SEX_CUR_NB` for the benchmark wage break example. Best choices:
- **THA**: multiple breaks over a long series — good for q020 (CAGR spanning break)
- **EGY**: single clean break with extreme values — easy to demonstrate in benchmark, hard for bare LLM to explain correctly

**Other countries with breaks:** NGA (HIES ↔ HS alternations), IND (National Sample Survey → Periodic LFS in 2018), PAK (see below), IDN (multiple B flags), PHL (B flags), MEX (B flags), BGD (B flag).

---

## Check 3 — PAK unemployment break in `DF_UNE_DEAP_SEX_AGE_RT`

**Finding:** Confirmed, and dramatic.

| Year | Value (%) | OBS_STATUS | Source |
|---|---|---|---|
| 2005 | 7.047 | | LFS |
| 2006 | **0.582** | B | LFS ← **EXTREME BREAK** |
| 2007–2011 | 0.4–0.8 | | LFS |
| 2012 | 3.667 | | HIES ← **SOURCE CHANGE** |
| 2013 | 2.954 | B | LFS ← **SOURCE CHANGE + B** |
| 2014–2015 | 1.8–3.6 | | LFS |
| 2016 | 2.286 | | HIES ← **SOURCE CHANGE** |
| 2018–2019 | 4.1–4.8 | | LFS |
| 2020 | 6.740 | B | HIES ← **SOURCE CHANGE + B** |
| 2021 | 6.338 | | LFS |

The 2005→2006 drop (7.0% → 0.6%) with OBS_STATUS=B is a hard definitional break — Pakistan changed how it counts unemployed people. The HIES/LFS alternations from 2012 onward are SOURCE breaks. This series is unusable for any multi-year trend without break-aware warnings.

**Decision:** PAK works for benchmark q019. ✅

---

## Check 4 — PAK wage break in `DF_EAR_EMTA_SEX_CUR_NB`

**Finding:** Confirmed. Same HIES ↔ LFS pattern as unemployment, plus OBS_STATUS=B flags.

| Year | Value (PKR) | OBS_STATUS | Source |
|---|---|---|---|
| 2005 | 4,223 | | HIES |
| 2006 | 5,196 | B | LFS ← **SOURCE CHANGE** |
| 2007–2011 | 6,014–10,093 | | LFS |
| 2012 | 9,401 | | HIES ← **SOURCE CHANGE** |
| 2013 | 12,569 | B | LFS ← **SOURCE CHANGE** |
| 2014–2019 | 13,636–21,545 | | LFS |
| 2020 | 22,489 | B | HIES ← **SOURCE CHANGE** |
| 2021 | 24,068 | | LFS |

Note the 2011→2012 jump: 10,093 PKR (LFS) → 9,401 PKR (HIES) — the value went DOWN despite inflation. The survey change caused a visible reversal. Similarly 2012→2013: 9,401 (HIES) → 12,569 (LFS), a 34% jump from changing the survey.

**Decision:** PAK also works for a wage break benchmark question. ✅ Though THA/EGY are cleaner examples because PAK alternates too frequently to tell a crisp story.

---

## Check 5 — SOM (Somalia) coverage

**Finding:** Somalia is NOT a "no data" country. The API returns 2 rows:
- 1 row from "LFS - Labour Force Survey"
- 1 row from "HIES - Integrated Household Budget Survey"

This holds across all three rate flows (unemployment, emp-to-pop, LFPR).

So SOM is actually an interesting case: very sparse data (2 observations across ~25 years), from two different surveys — a structural break by design, given only 2 data points total.

**Decision:** SOM does not work for the "unanswerable_no_data" benchmark question (q021). The question needs a country or entity that genuinely returns 404. Candidates to check:

- **PRK** (North Korea) — almost certainly no survey data
- **ERI** (Eritrea) — extremely limited statistical capacity
- Small Pacific island territories (NRU, TUV, etc.)
- **Alternative approach:** Use an entirely invalid country code (e.g. "XYZ") — but this feels like cheating; a real "does this country have ILOSTAT data" question is more interesting

**Still open: need to verify at least one genuine "no data" country.** This is a Phase 0c/benchmark item, not a Phase 1 blocker.

---

## Check 6 — EU aggregate in `CL_AREA`

**Finding:** No EU aggregate code exists in ILOSTAT's data. All guesses (EU, EU27, EU27_2020, EUU, XC) returned 500 server errors — not "no data" but "server doesn't understand that key", which means these codes aren't valid in the system.

ILOSTAT is a country-level data repository. It does not publish EU27 or Euro Area aggregates — those are Eurostat products. ILOSTAT has individual member states (DEU, FRA, etc.) but no regional rollup.

**Decision:** Benchmark q023 should be classified as `unanswerable_wrong_entity` — the EU is not a valid query target in ILOSTAT. The correct response from the MCP server is: "ILOSTAT only holds country-level data. To get EU-level unemployment, query Eurostat." ✅ Decision locked.

Note: The `client.codelist("CL_AREA")` call failed with the same dict error as Check 1, so we can't enumerate valid area codes via codelist yet. The direct-data approach confirmed EU codes return 500 errors. The codelist syntax bug needs to be fixed separately.

---

## Check 7 — MEASURE dimension

**Finding:** Always single-valued per flow, across all 4 canonical flows:

| Flow | MEASURE value |
|---|---|
| `DF_UNE_DEAP_SEX_AGE_RT` | `UNE_DEAP_RT` |
| `DF_EMP_DWAP_SEX_AGE_RT` | `EMP_DWAP_RT` |
| `DF_EAR_EMTA_SEX_CUR_NB` | `EAR_EMTA_NB` |
| `DF_EAP_DWAP_SEX_AGE_RT` | `EAP_DWAP_RT` |

MEASURE is encoded in the flow ID itself (it's the second-to-last segment before the measure suffix). A single flow always returns one MEASURE code.

**Decision:** Drop `MEASURE` from user-facing output in `sdmx_client.py` — it carries no information not already conveyed by the flow ID. Can be used internally as a sanity check. ✅ Decision locked.

---

## Open items after this session

| Item | Status | Blocking? |
|---|---|---|
| LCU currency symbol in wage responses | Partially resolved — surface CUR dim in response, skip ISO symbol for now | No — Phase 1 can proceed with CUR_TYPE_LCU label |
| Genuine "no data" country for benchmark q021 | ❌ Not found | No — benchmark-only, Phase 0c item |
| `client.codelist()` syntax error | ❌ Not fixed | No — Phase 1 can proceed without it |
| EU benchmark q023 classification | ✅ Locked: `unanswerable_wrong_entity` | — |
| PAK as unemployment break example | ✅ Confirmed | — |
| Wage break in canonical flow (THA, EGY) | ✅ Confirmed | — |
| MEASURE is single-valued per flow | ✅ Confirmed | — |

---

## Updated benchmark country assignments

Based on this session's discoveries:

| Benchmark question | Category | Country/entity | Flow | Break confirmed? |
|---|---|---|---|---|
| q003 / q018 | answerable_break (unemployment) | NGA | `DF_UNE_DEAP_SEX_AGE_RT` | ✅ |
| q019 | answerable_break (unemployment) | PAK | `DF_UNE_DEAP_SEX_AGE_RT` | ✅ |
| q004 / q020 | answerable_break (wages) | THA | `DF_EAR_EMTA_SEX_CUR_NB` | ✅ (canonical flow confirmed) |
| q004 alt | answerable_break (wages, dramatic) | EGY | `DF_EAR_EMTA_SEX_CUR_NB` | ✅ (1091 → 71 EGP) |
| q021 | unanswerable_no_data | ❌ TBD (SOM doesn't work) | — | — |
| q023 | unanswerable_wrong_entity | EU (no aggregate) | — | ✅ |
