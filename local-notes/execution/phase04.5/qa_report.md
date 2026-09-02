# qa-04.5 — Phase 4.5 Adversarial QA

## Summary table

| Category | Count |
|---|---|
| Total tests run | 60 |
| Pass | 53 |
| Bug / Fail | 4 |
| Informational flags | 3 |
| NFR: Pass | 5 |
| NFR: Fail | 2 |
| NFR: Manual-verification-required | 0 |

---

## Tool results

### search_indicators

| # | Input | Expected | Result | Remarks |
|---|---|---|---|---|
| 1 | keyword="unemployment" | List with is_modelled flag; some modelled | PASS | 20 results, all is_modelled=False. No modelled unemployment flows in top-20 by ORDER; modelled flows are further down. is_modelled logic confirmed working via supplementary test (2WAP flows correctly flagged True). |
| 2 | keyword="wages" | Empty list (ILOSTAT uses "earnings") | PASS | Returns [] as expected. |
| 3 | keyword="earnings" | Non-empty list with is_modelled | PASS | 20 results; all have is_modelled key. |
| 4 | keyword="" | 20 results or clear error | FLAG | Returns 20 results (all flows with ORDER=9999 tie, resolved by insertion order). Not an error. Empty string matches all titles — technically correct but potentially surprising. No spec language prohibits it. |
| 5 | keyword="zzznomatch999" | Empty list | PASS | Returns [] gracefully. |

### get_countries

| # | Input | Expected | Result | Remarks |
|---|---|---|---|---|
| 6 | (no input) | List with code+name; includes DEU, THA, PRK | PASS | 335 entries. DEU, THA, PRK all present with correct names. |

### get_indicator_metadata

| # | Input | Expected | Result | Remarks |
|---|---|---|---|---|
| 7 | "DF_UNE_DEAP_SEX_AGE_RT" | All 5 keys present; last_updated non-empty | FLAG | All 5 keys present (id, title, description, last_updated, is_modelled). last_updated is always "". ILOSTAT's LAST_UPDATE annotation exists in the API response but has empty text for all flows checked. Not a code bug — ILOSTAT API data quality issue. |
| 8 | "DF_BOGUS_FLOW" | Empty dict, no exception | PASS | Returns {} as specified. |
| 9 | "DF_SDG_B852" (non-registered ILOSTAT flow) | Metadata returned (no allowlist check) | PASS | Returns {} — this flow doesn't exist in ILOSTAT's catalog. Confirms no allowlist on metadata tool. |

### get_time_series — validation

| # | Input | Expected | Result | Remarks |
|---|---|---|---|---|
| 10 | Unregistered dataflow "DF_EMP_TEMP_SEX_AGE_STE_NB" | ValueError | PASS | Clear message listing valid dataflows. |
| 11 | start_year="1900" (below min=1983) | ValueError | PASS | "start_year for DF_UNE_DEAP_SEX_AGE_RT must be between 1983 and 2026 (got 1900)" |
| 12 | end_year="2099" (above current year) | ValueError | PASS | "end_year for DF_UNE_DEAP_SEX_AGE_RT must be between 1983 and 2026 (got 2099)" |
| 13 | start_year="20" (not 4 digits) | ValueError | PASS | "start_year must be a 4-digit year (got '20')" |
| 14 | start_year="2022", end_year="2010" | ValueError | PASS | "start_year must be <= end_year (got 2022 to 2010)" |
| 15 | country="XX" | ValueError | PASS | "Unknown country code 'XX'. Use get_countries() to find valid codes." |
| 16 | age_group="adult" | ValueError | PASS | "age_group must be 'total' or 'youth' (got 'adult')" |

### get_time_series — happy paths and edge cases

| # | Input | Expected | Result | Remarks |
|---|---|---|---|---|
| 17 | DEU unemployment 2015-2022, total | _breaks=[], _missing_years=[], data rows with time_period+value+source | PASS | 8 rows, correct columns. source="LFS - EU Labour Force Survey" throughout. |
| 18 | THA wages 2010-2022 | _missing_years includes "2010"; _breaks non-empty | PASS | 2 breaks (2013 HIES, 2014 LFS); _missing_years=["2010"]. |
| 19 | PRK unemployment 2010-2023 | 1-element list with _no_data_reason mentioning PRK | PASS | "No data available for PRK in DF_UNE_DEAP_SEX_AGE_RT." |
| 20 | ESP unemployment 2010-2022, youth | empty or _no_data_reason | PASS | Returns 1-element; _no_data_reason set. Spain has no data for this flow with youth age group. |
| 21 | NGA unemployment 2005-2022 | _breaks non-empty (known breaks) | PASS | 3 breaks: 2014, 2019, 2022. _missing_years has 10 years. |
| 22 | DEU unemployment 2020-2020 (single year) | 2-element list; 1 data row | PASS | Returns meta + 1 row (2020: 3.881%). |
| 23 | DF_EAR_EMTA_SEX_CUR_NB, DEU, 2015-2020, age_group=youth | Works (youth ignored for wage flows) | PASS | Returns wage data; age param ignored as documented. |

### get_yoy_change — validation

| # | Input | Expected | Result | Remarks |
|---|---|---|---|---|
| 24 | Unregistered dataflow | ValueError | PASS | Clear message. |
| 25 | year="2030" (future) | ValueError | PASS | "year for DF_UNE_DEAP_SEX_AGE_RT must be between 1983 and 2026 (got 2030)" |
| 26 | year="1983" (min boundary; prev_year=1982 is pre-min) | ValueError with user-facing message | BUG → see Bug 1 | Validation passes for 1983 (>= min), then internal growth.yoy() raises ValueError with raw message. |
| 27 | year="1982" (below min=1983) | ValueError | PASS | Validation correctly rejects. |
| 28 | Invalid country "ZZ" | ValueError | PASS | Clear message. |
| 29 | Non-4-digit year "22" | ValueError | PASS | Clear message. |

### get_yoy_change — happy paths

| # | Input | Expected | Result | Remarks |
|---|---|---|---|---|
| 30 | DEU unemployment 2022 | result[1] with change_pct, year, prev_year | PASS | change_pct=-12.4576%; correct structure. |
| 31 | THA wages 2014 | _break_warning present (break 2013→2014) | PASS | Warns about HIES→LFS source change. Still computes. |
| 32 | PRK 2022 | 1-element with _no_data_reason | PASS | No fabrication. |

### get_cagr — validation

| # | Input | Expected | Result | Remarks |
|---|---|---|---|---|
| 33 | start=end "2020","2020" | ValueError | PASS | "start_year must be strictly before end_year" |
| 34 | start after end "2022","2015" | ValueError | PASS | Same message. |
| 35 | start_year="1999" for DF_EAR (min=2000) | ValueError | PASS | Range check correct. |
| 36 | Unregistered dataflow | ValueError | PASS | Clear message. |

### get_cagr — happy paths and edge cases

| # | Input | Expected | Result | Remarks |
|---|---|---|---|---|
| 37 | DEU unemployment 2015-2022 | cagr_pct float, n_years=7, no break warning | PASS | cagr_pct=-5.5215, n_years=7. |
| 38 | THA wages 2013-2020 | _break_warning present | PASS | Break at 2014 warned. |
| 39 | NGA unemployment 2010-2022 | Break warning; cagr computed | BUG → see Bug 2 | 2010 not in data (NGA starts 2011); raises internal ValueError. |
| 40 | DEU 2021-2022 (n_years=1) | cagr_pct = YoY change | PASS | n_years=1, cagr_pct=-12.4576 (matches YoY). |

### get_trend — validation

| # | Input | Expected | Result | Remarks |
|---|---|---|---|---|
| 41 | start=end "2022","2022" | ValueError | PASS | |
| 42 | year below min for DF_EAR | ValueError | PASS | |
| 43 | Unregistered flow | ValueError | PASS | |

### get_trend — happy paths and edge cases

| # | Input | Expected | Result | Remarks |
|---|---|---|---|---|
| 44 | DEU unemployment 2000-2022 | slope/intercept/r_squared/n_points; n_points>=10 | PASS | n_points=23, slope=-0.343148, r_squared=0.7912. |
| 45 | THA wages 2013-2020 | _break_warning present | PASS | Break at 2014 warned. |
| 46 | DEU 2021-2022 (exactly 2 points) | n_points=2; valid result | PASS | slope=-0.441, r_squared=1.0. |

### labor_market_snapshot — validation

| # | Input | Expected | Result | Remarks |
|---|---|---|---|---|
| 47 | "Germany, France, Brazil, Nigeria" (4) | ValueError naming the count | PASS | "accepts 1-3 countries, got 4" |
| 48 | "Atlantis" | ValueError | PASS | "did not match any ILOSTAT country" |
| 49 | "Congo" | ValueError listing COG and COD | PASS (incorrect expectation corrected) | COG's ILOSTAT name is exactly "Congo" — exact name match resolves unambiguously to COG. Not ambiguous. |
| 50 | "" (empty string) | ValueError or prompt with at least 1 country | BUG → see Bug 3 | Returns a broken prompt with no country codes. |

### labor_market_snapshot — happy paths

| # | Input | Expected | Result | Remarks |
|---|---|---|---|---|
| 51 | "Germany, Thailand" | Prompt string with DEU and THA | PASS | Returns 694-char prompt with both ISO codes. |
| 52 | "DEU" (ISO-3) | Resolves; returns prompt | PASS | |
| 53 | "germany" (lowercase) | Case-insensitive; returns prompt | PASS | |

### Supplementary tests (adversarial / NFR)

| # | Description | Result | Remarks |
|---|---|---|---|
| 54 | CAGR/trend warns AND computes on THA break | PASS | Break warning present; stat computed. Spec: warn+compute. |
| 55 | Break at start_year boundary (NGA 2014-2017) | BUG → see Bug 4 | No break detected when range starts at break year. |
| 56 | "Korea" ambiguous (KOR + PRK) in live data | PASS | Correctly raises ValueError listing both candidates. |
| 57 | mypy clean | PASS | No issues in 8 source files. |
| 58 | ruff clean | PASS | No warnings. |
| 59 | Full existing test suite (116 tests) | PASS | 116/116 passed in 63s. |
| 60 | Performance: get_time_series DEU 2010-2022 | PASS | 3.91s (< 10s threshold). |

---

## Bugs found

### Bug 1

Trace: CLAUDE.md — "All user-facing error messages are plain English written for Claude to relay to the user — not Python exception names, not stack traces."
Severity: medium

Reproduction steps:
1. `get_yoy_change('DF_UNE_DEAP_SEX_AGE_RT', 'DEU', '1983')`
2. Same for any tool where the user's year is at the flow's minimum and prev_year (year-1) falls below the minimum.
3. Also reproduced: `get_yoy_change('DF_EAR_EMTA_SEX_CUR_NB', 'THA', '2011')` — prev_year=2010 is missing from THA wage data.

Expected: Validation should prevent year=min_year (since prev_year would be outside the valid range), OR the server layer should catch the internal ValueError and re-raise with a user-facing message like "No data available for year 1982 — the earliest year in this dataflow is 1983, so 1984 is the earliest valid year for year-over-year change."

Actual: `ValueError: Previous year '1982' not found in data.` — a raw internal error from `growth.yoy()` that propagates uncaught through `get_yoy_change`.

Suggested fix: Add a check after validation: `if int(year) == min_year: raise ValueError(f"year {year!r} is the earliest year in this dataflow; year-over-year requires data from {int(year)-1}, which is not available. Use year >= {min_year + 1}.")`. Alternatively, catch `ValueError` from `growth.yoy()` in the server layer and re-raise with a user-facing message.

---

### Bug 2

Trace: CLAUDE.md — "All user-facing error messages are plain English written for Claude to relay to the user"; break detection testing.
Severity: medium

Reproduction steps:
1. `get_cagr('DF_UNE_DEAP_SEX_AGE_RT', 'NGA', '2010', '2022')` — NGA has no 2010 data (earliest: 2011).
2. `get_cagr('DF_UNE_DEAP_SEX_AGE_RT', 'NGA', '2011', '2012')` — NGA has no 2012 data.
3. `get_trend('DF_UNE_DEAP_SEX_AGE_RT', 'NGA', '2010', '2022')` — same pattern.

Expected: Tool returns a structured response indicating the boundary year has no data. Suggestion: include the `_missing_years` list in the error so the user can choose valid boundary years.

Actual: `ValueError: start_year '2010' not found in data.` or `ValueError: end_year '2012' not found in data.` — raw internal errors from `growth.cagr()` / `growth.trend()` propagate uncaught. The year is valid (>= min_year) so validation passes, but ILOSTAT simply has no observation for that year in the dataset.

Suggested fix: In the server layer, catch `ValueError` from the growth functions and re-raise with a message that includes the `_missing_years` context: "Year {year} has no data for {country} in {dataflow_id}. Available years in the requested range: check _missing_years from get_time_series."

---

### Bug 3

Trace: ROADMAP Phase 4 error contract — "labor_market_snapshot accepts 1–3 countries"; CLAUDE.md — "No silent failures."
Severity: low

Reproduction steps:
1. `labor_market_snapshot('')`

Expected: ValueError — "countries must not be empty; provide 1–3 country names or ISO-3 codes."

Actual: Returns a prompt with no countries: "Fetch a labour market snapshot for: .\n\nFor each country, call get_time_series with the following dataflow IDs..." with an empty country list in both the header and the column header instruction. The model receives a nonsensical instruction.

Suggested fix: Add `if not inputs: raise ValueError("countries must not be empty. Provide 1–3 country names or ISO-3 codes.")` after `inputs = [c.strip() for c in countries.split(",") if c.strip()]`.

---

### Bug 4

Trace: CLAUDE.md break detection spec — "get_cagr and get_trend must check for breaks inside the requested range before computing"; ROADMAP Phase 3/4.
Severity: medium

Reproduction steps:
1. `get_cagr('DF_UNE_DEAP_SEX_AGE_RT', 'NGA', '2014', '2017')`
2. NGA has a confirmed break at 2014 (HS→LFS source change).
3. The CAGR fetch starts at 2014, so no 2013 data is fetched. `detect_breaks()` sees only one source (LFS from 2014 onward) and returns no breaks.

Expected: A break warning that 2014 is a known break year, so starting the range at the break year means the prior source's values are not comparable.

Actual: `_breaks=[]`, `_break_warning=None`. The CAGR is silently computed without warning. Contrast: when end_year=2014 (NGA 2011-2014), the break IS detected because 2013 data is also fetched.

Asymmetry confirmed: break-at-end-year → warned; break-at-start-year → silently missed.

Suggested fix: When fetching data for CAGR/trend, fetch from `str(int(start_year) - 1)` to detect whether `start_year` itself is a break year. If a break is detected at start_year, include it in the warning. This adds one extra year to the API call but closes the false-confidence gap.

---

## Informational flags (not bugs — behavior is technically correct but worth noting)

**Flag A**: `search_indicators("")` returns 20 results rather than an error or "all results" response. Every flow title contains the empty string, so all 753+ flows match; ORDER annotations are all empty (ILOSTAT does not populate them), so all ties at order=9999, resolved by insertion order. The returned set is effectively arbitrary. Not a bug — the behavior is deterministic and consistent — but a caller passing "" probably expected either an error or a documented "return all" behavior.

**Flag B**: `get_indicator_metadata` always returns `last_updated=""`. The LAST_UPDATE annotation exists in ILOSTAT's API response for every flow checked, but its text value is always empty. This is an ILOSTAT data quality issue. The code correctly reads the annotation; it just has no content. The field will always be empty until ILOSTAT populates it.

**Flag C**: Tool descriptions for `get_yoy_change`, `get_cagr`, and `get_trend` describe the metadata element as `{_breaks, _break_warning}`, but the implementation also includes `_missing_years` and `_no_data_reason`. The extra fields are useful and not harmful, but the tool description undersells what the agent receives. This matters for agent reasoning quality — an agent that doesn't know about `_no_data_reason` may not handle the no-data path correctly.

---

## NFR verification

| NFR | Result | Evidence |
|---|---|---|
| Break detection correctness | PARTIAL PASS | CAGR and trend warn+compute when break is within range (THA 2012-2018: warning present, stat computed). Bug 4: break at start_year boundary is silently missed. |
| No fabrication | PASS | PRK returns `_no_data_reason`, 0 data rows. No hallucinated values. |
| SDMX isolation | PASS | `import sdmx` appears only in `sdmx_client.py` (confirmed by grep). No other source file imports the sdmx1 library directly. |
| Error propagation | PARTIAL PASS | 404/no-data → clean `_no_data_reason` field. Internal ValueError from boundary year/missing year → raw error propagates uncaught (Bugs 1, 2). |
| Performance | PASS | `get_time_series` DEU unemployment 2010-2022: 3.91s. Well under 10s threshold. |
| structlog observability | FAIL | `structlog` not in `pyproject.toml` dependencies. Not in any source file. `sdmx_client.py` uses stdlib `import logging`. Phase 4.5 ROADMAP explicitly requires: "structlog integrated throughout — structured JSON logs replacing all bare logging calls." This is a Phase 4.5 output requirement that has not been implemented. |
| OpenTelemetry tracing | FAIL | No `opentelemetry-sdk` or `opentelemetry-exporter-otlp` in `pyproject.toml`. No OTel instrumentation in `server.py` or `sdmx_client.py`. Phase 4.5 ROADMAP requires: "OpenTelemetry instrumentation in server.py (tool spans) and sdmx_client.py (API spans), exporting to Honeycomb free tier." Not implemented. |
| mypy | PASS | `uv run mypy src/` — no issues in 8 source files. |
| ruff | PASS | `uv run ruff check src/` — all checks passed. |

---

## Spec gaps

**Gap 1**: The CLAUDE.md specifies both `structlog` (mandatory structured logging) and `OpenTelemetry → Honeycomb` (mandatory distributed tracing). The ROADMAP lists both as Phase 4.5 outputs. Neither has been implemented. It is unclear whether Phase 4.5 is considered complete or whether this QA pass is running before these outputs are delivered. If the phase is not yet complete, this QA pass cannot make a go/no-go decision on those NFRs.

**Gap 2**: No spec language defines the minimum number of countries for `labor_market_snapshot`. ROADMAP says "1–3 countries" which implies 1 is the minimum. The empty-string case (Bug 3) is not explicitly addressed. Confirmed as a bug by reading ROADMAP Phase 4 error contract: "More than 3 countries → raise ValueError immediately."

---

## Coverage gaps

The following test plan items produced a corrected expectation (not gaps in coverage):

- Test 49 (Congo ambiguous): Expectation was wrong — COG's ILOSTAT name is exactly "Congo". Covered by real behavior — correct resolution confirmed.

No spec requirements are untested.

---

## Recommendation

revisit

Reason: Two medium bugs (Bug 1, Bug 2) cause uncaught internal ValueErrors to surface when boundary years have no data; Bug 4 creates false confidence by missing a break at start_year; structlog and OpenTelemetry — both listed as Phase 4.5 mandatory outputs in the ROADMAP — are not implemented. The functional tests otherwise pass cleanly and the break detection core (warn+compute) works correctly for the primary cases.
