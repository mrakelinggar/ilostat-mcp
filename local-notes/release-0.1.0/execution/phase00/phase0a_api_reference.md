# ILOSTAT API Reference

All calls go through `sdmx1`. Base URL: `https://sdmx.ilo.org/rest`
All samples are real output from the live API (captured 2026-07-23).

---

## Overview — 4 calls, that's it

| # | What it does | When it runs |
|---|---|---|
| 1 | Get all dataflow titles (for keyword search) | Once at server startup, cached |
| 2 | Get one dataflow's full description + schema | Per `get_indicator_metadata` call |
| 3 | Get a country's time series for an indicator | Per data tool call (`get_time_series`, `get_yoy_change`, `get_cagr`, `get_trend`) |
| 4 | Get the list of all countries | Once at server startup, cached |

Break detection is **not** a separate API call — it's post-processing on Call 3's result.

---

## Call 1 — Get all dataflows

**Used by:** `search_indicators(keyword)`

**What it does:** fetches every dataflow title in one request. We search this list client-side by keyword.

```python
msg = client.dataflow()
catalog = {flow_id: str(flow.name) for flow_id, flow in msg.dataflow.items()}
```

**Real result:** 1,210 dataflows returned. Example entries:

```
DF_UNE_DEAP_SEX_AGE_RT   → "Unemployment rate by sex and age"
DF_UNE_2EAP_SEX_AGE_RT   → "Unemployment rate by sex and age -- ILO modelled estimates, Nov. 2025"
DF_EAR_CMTA_SEX_CUR_NB   → "Average monthly earnings of care employees by sex and currency"
DF_EAR_EHRA_SEX_ECO_CUR_NB → "Average hourly earnings of employees by sex and economic activity and currency"
```

**What `search_indicators('unemployment rate')` returns (title contains both words):**
```
DF_GED_XLU1_SEX_HHT_CHL_RT → Unemployment rate for persons ages 25 to 54 by sex, household type and presence of children
DF_GED_XLU1_SEX_HHT_GEO_RT → Unemployment rate for persons ages 25 to 54 by sex, household type and rural / urban areas
DF_LUU_2LU2_SEX_AGE_RT     → LU2: Combined rate of time-related underemployment and unemployment by sex and age -- ILO modelled estimates
...
```

**Notes:**
- `DF_*_2EAP_*` / `DF_*_2WAP_*` in the title = ILO modelled estimates (imputed, covers all countries + future years). Always label these differently in results.
- `DF_*_DEAP_*` / `DF_*_DWAP_*` = national survey data (real, but patchy by country).
- Run at startup, cache the result. Do not hit this endpoint per search request.

---

## Call 2 — Get one dataflow's metadata

**Used by:** `get_indicator_metadata(dataflow_id)`

**What it does:** fetches the indicator name, description, dimension list, and last-updated date.

```python
msg = client.dataflow("DF_UNE_DEAP_SEX_AGE_RT", params={"references": "all"})
# params={"references": "all"} is required to also get the DSD (schema)

df_obj = list(msg.dataflow.values())[0]
dsd    = list(msg.structure.values())[0]

name         = str(df_obj.name)
description  = str(df_obj.description)   # may contain HTML tags — strip before returning
last_updated = next(str(a.text) for a in df_obj.annotations if a.type == "LAST_UPDATE")
dimensions   = [d.id for d in dsd.dimensions]
attributes   = [a.id for a in dsd.attributes]
```

**Real result** for `DF_UNE_DEAP_SEX_AGE_RT`:
```
name:         "Unemployment rate by sex and age"
description:  "With the aim of promoting international comparability, statistics presented
               on ILOSTAT are based on standard international definitions wherever feasible..."
last_updated: "17/07/2026 07:08:06"
dimensions:   ['REF_AREA', 'FREQ', 'MEASURE', 'SEX', 'AGE', 'TIME_PERIOD']
attributes:   ['OBS_STATUS', 'UNIT_MEASURE_TYPE', 'UNIT_MEASURE', 'UNIT_MULT', 'SOURCE',
               'NOTE_SOURCE', 'NOTE_INDICATOR', 'NOTE_CLASSIF', 'DECIMALS',
               'UPPER_BOUND', 'LOWER_BOUND']
measure:      ['OBS_VALUE']
```

**Notes:**
- `SOURCE` is in the attributes list — confirmed present in the schema for all survey flows.
- `UPPER_BOUND` / `LOWER_BOUND` appear here; they come through on modelled estimate flows (confidence intervals).
- The description field contains HTML — strip tags before returning to the agent.

---

## Call 3 — Get a time series

**Used by:** `get_time_series`, `get_yoy_change`, `get_cagr`, `get_trend`

**What it does:** fetches all data for one country + one indicator + one date range. `attributes='osgd'` is required to get the `SOURCE` column for break detection.

```python
msg = client.data(
    "DF_UNE_DEAP_SEX_AGE_RT",
    key={"REF_AREA": "MYS"},        # country filter — server-side, fast
    params={
        "startPeriod": "2018",      # strings, not ints
        "endPeriod":   "2023",
    },
    dsd=False,                      # skip schema validation — required for DF_ flows
)
df = sdmx.to_pandas(msg, attributes="osgd")
# attributes="osgd" = observation + series + group + dataset level attributes
# Without this flag, SOURCE is silently dropped from the result
```

### What the raw result looks like

```
Shape: (420 rows, 12 columns)   ← all frequencies + all sex/age combos for MYS 2018–2023

Index levels: [REF_AREA, FREQ, MEASURE, SEX, AGE, TIME_PERIOD]
Columns:      [value, OBS_STATUS, UNIT_MEASURE_TYPE, UNIT_MEASURE, UNIT_MULT,
               SOURCE, NOTE_SOURCE, NOTE_INDICATOR, NOTE_CLASSIF,
               DECIMALS, UPPER_BOUND, LOWER_BOUND]
```

**Important — FREQ dimension:** the response includes all three frequency variants:
- `A` = annual (e.g. `2022`)
- `M` = monthly (e.g. `2022-M01`)
- `Q` = quarterly (e.g. `2022-Q1`)

Filter to `FREQ=A` for clean annual series. Leave open if the user asks for monthly data.

### Default filters to get "total unemployment rate"

```python
idx = df.index
mask = (
    (idx.get_level_values("SEX") == "SEX_T")            # both sexes combined
  & (idx.get_level_values("AGE") == "AGE_YTHADULT_YGE15") # working age 15+
  & (idx.get_level_values("FREQ") == "A")                # annual only
)
result = df[mask]
```

### Real result after filtering (Malaysia unemployment, 2018–2023)

```
                                                                value       SOURCE             OBS_STATUS
REF_AREA FREQ MEASURE     SEX   AGE                TIME_PERIOD
MYS      A    UNE_DEAP_RT SEX_T AGE_YTHADULT_YGE15 2018        3.300  LFS - Labour Force Survey
                                                    2019        3.300  LFS - Labour Force Survey
                                                    2020        4.500  LFS - Labour Force Survey
                                                    2021        4.600  LFS - Labour Force Survey
                                                    2022        3.900  LFS - Labour Force Survey
```

One row per year. `value` is the unemployment rate in %. `SOURCE` confirms the survey.

---

### Call 3b — Same call, country with a methodology break (Nigeria)

```python
msg = client.data("DF_UNE_DEAP_SEX_AGE_RT",
    key={"REF_AREA": "NGA"}, params={"startPeriod": "2010", "endPeriod": "2023"}, dsd=False)
df = sdmx.to_pandas(msg, attributes="osgd")
```

**Real result (filtered to SEX_T, AGE_YTHADULT_YGE15, FREQ=A):**

```
                                                                  value                                       SOURCE
NGA   A   UNE_DEAP_RT SEX_T AGE_YTHADULT_YGE15 2011              3.770    HS - General Household Survey
                                                2013              3.711    HS - General Household Survey
                                                2014              4.562    LFS - Unemployment, Under-employment Watch
                                                2015              4.311    LFS - Unemployment, Under-employment Watch
                                                2016              7.060    LFS - Unemployment, Under-employment Watch
                                                2017              8.389    LFS - Unemployment, Under-employment Watch
                                                2019              4.448    HIES - Living Standards Survey
                                                2022              3.827    LFS - Unemployment, Under-employment Watch
                                                2023              3.074    LFS - Unemployment, Under-employment Watch
```

**Break detection output:**
```python
sources = [s for s in df["SOURCE"].unique() if s != ""]
# → ['LFS - Unemployment, Under-employment Watch',
#    'HIES - Living Standards Survey',
#    'HS - General Household Survey']
has_break = len(sources) > 1   # → True
```

Three different surveys — numbers from different years are NOT directly comparable. The tool must warn before computing any trend or CAGR.

---

### Call 3c — Wages dataflow (Thailand)

```python
msg = client.data("DF_EAR_CMTA_SEX_CUR_NB",
    key={"REF_AREA": "THA"}, params={"startPeriod": "2010", "endPeriod": "2023"}, dsd=False)
df = sdmx.to_pandas(msg, attributes="osgd")
```

**Extra dimension — CUR (currency type):** wages flows have a `CUR` dimension not present in employment flows.

```
Index levels: [REF_AREA, FREQ, MEASURE, SEX, CUR, TIME_PERIOD]
```

Each year has three currency rows:
- `CUR_TYPE_LCU` — local currency (Thai Baht here)
- `CUR_TYPE_PPP` — purchasing power parity (international $)
- `CUR_TYPE_USD` — US dollars

**Default for `get_time_series` on wages: `CUR_TYPE_LCU`** (local currency, most interpretable).

**Real result (SEX_T, CUR_TYPE_LCU, annual):**

```
                                              value                               SOURCE  UNIT_MEASURE
THA   A   EAR_CMTA_NB SEX_T CUR_TYPE_LCU 2014    21,349  LFS - Labour Force Survey        THB/month
                                          2015    16,832  LFS - Labour Force Survey        THB/month
                                          2016    22,447  LFS - Labour Force Survey        THB/month
                                          2017    22,338  LFS - Labour Force Survey        THB/month
                                          2018    22,417  LFS - Labour Force Survey        THB/month
                                          2019    22,139  LFS - Labour Force Survey        THB/month
                                          2020    22,737  LFS - Labour Force Survey        THB/month
                                            ...
                                          [later years switch to HIES — SOURCE changes]
```

```python
sources = [s for s in df["SOURCE"].unique() if s != ""]
# → ['LFS - Labour Force Survey', 'HIES - Household Socio-Economic Survey']
has_break = True
```

---

### Call 3d — No-data cases and what the API returns

| Scenario | Call | API response | How to handle in code |
|---|---|---|---|
| Country has no survey data (North Korea) | `key={'REF_AREA': 'PRK'}`, survey flow | **HTTP 404** | Catch `HTTPError`, return "no survey data available" |
| Date out of range (Malaysia 1970) | `key={'REF_AREA': 'MYS'}`, `startPeriod=1970` | Country absent in response — **KeyError** on `.xs()` | Catch `KeyError`, return "no data for this period" |
| Future date (Malaysia 2027) | `key={'REF_AREA': 'MYS'}`, `startPeriod=2027` | **HTTP 404** | Same as 404 above |
| Valid country, valid date, but no survey coverage | Response returns but country not in it | **KeyError** on `.xs()` | Same as date-out-of-range |

Two error types to handle: `HTTPError` (404) and `KeyError` (country absent in result). Both mean "no data."

---

## Call 4 — Country list

**Used by:** `get_countries()`

**What it does:** fetches the `CL_AREA` codelist — all country/territory codes and their names.

```python
msg = client.codelist("CL_AREA")
cl = list(msg.codelist.values())[0]
countries = {code: str(item.name) for code, item in cl.items.items()}
# cl.items is a plain dict — do NOT call it like a function
```

**Real result:** 335 entries. Sample:

```python
{
  "MYS": "Malaysia",
  "SGP": "Singapore",
  "DEU": "Germany",
  "FRA": "France",
  "NGA": "Nigeria",
  "THA": "Thailand",
  "GEO": "Georgia",           # ← both Georgia (country) and a potential US-state confusion
  "PRK": "Korea, Democratic People's Republic of",   # ← North Korea — valid code, no survey data
  "COG": "Congo",             # ← Republic of Congo
  "COD": "Congo, Democratic Republic of the",        # ← DRC — two Congos in the list
}
```

**Notes:**
- 335 entries includes territories, dependencies, and aggregates — not just sovereign states.
- A code being present here does NOT mean ILOSTAT has survey data for it. `get_countries` should say so in the system prompt.
- Cache at startup. Do not hit this per tool call.

---

## Dimension reference (for default filtering in sdmx_client.py)

| Dimension | "Total" default code | Notes |
|---|---|---|
| `SEX` | `SEX_T` | Both sexes combined |
| `AGE` | `AGE_YTHADULT_YGE15` | Working age 15 and over |
| `FREQ` | `A` | Annual — filter to this by default; leave open for monthly requests |
| `CUR` | `CUR_TYPE_LCU` | Local currency — wages flows only; not present in employment flows |

---

## Attribute reference (columns in the attributed DataFrame)

| Column | What it contains | Used for |
|---|---|---|
| `value` | The data value (float) | The actual number to return |
| `SOURCE` | Which survey the data came from (e.g. "LFS - Labour Force Survey") | **Break detection** — if this changes across years, flag a methodology break |
| `OBS_STATUS` | Observation status flag (`R` = revised, `P` = provisional, etc.) | Surface to user if not final |
| `UNIT_MEASURE` | The unit (e.g. "%" for rates, "THB/month" for wages) | Always include with the value |
| `UNIT_MULT` | Scale multiplier (e.g. 1, 1000) | Apply when converting raw value |
| `UPPER_BOUND` | Upper confidence bound (modelled estimates only) | Include if present |
| `LOWER_BOUND` | Lower confidence bound (modelled estimates only) | Include if present |
| `NOTE_SOURCE` | Internal repo label ("ILO-STATISTICS") | Not useful — ignore |
| `NOTE_INDICATOR` | Methodological footnote | Include if non-empty (rare) |
| `NOTE_CLASSIF` | Classification footnote | Include if non-empty (rare) |
