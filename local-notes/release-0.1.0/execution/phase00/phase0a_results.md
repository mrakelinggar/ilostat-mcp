# Phase 0a — Discovery Results

Date: 2026-07-23 (API sanity check); 2026-07-26 (doc research — dataflow ID structure, FREQ/SOURCE/CUR clarifications)
Scripts: `phase0a_scratch_discovery.py` (8 checks), `phase0a_scratch_discovery2.py` (6 checks) — both ran end-to-end clean.
Doc: `local-notes/docs/ILOSTAT-SDMX_Dissem API Ref Guide_V4.1-(ILO Style).pdf` (ILO Dept of Statistics, 2024-04-26)

---

## 1. Environment

`sdmx1` v2.26.0 is available and works. Import it as `import sdmx` (not `import sdmx1`).
Connecting to ILOSTAT is one line: `sdmx.Client('ILO')` — no API key, no registration.

---

## 2. Catalog structure

ILOSTAT has **1,210 dataflows** total. A dataflow is just one specific slice of data —
for example, "unemployment rate broken down by sex and age group." Fetching the full list
in one request works fine (no errors).

Of those 1,210, **753 are employment or wage related.** That's far too many to maintain
a hardcoded list — so `search_indicators` will search against live catalog titles at
query time (see decision below).

**Two flavours of data to know about:**

- **Modelled estimates** (`DF_*_2EAP_*` IDs): ILO fills these in by imputation for
  countries that don't report, and includes projections into the future. They cover
  everyone, including North Korea and years like 2027 — but they're constructed numbers,
  not real survey results.
- **National survey data** (`DF_*_DEAP_*` etc.): actual data reported by countries from
  their own labour force surveys. Patchy by country, but real.

The distinction matters for benchmark questions about "missing" data (see section 6).

### Decision: how `search_indicators` will work

→ **Live keyword search against the catalog.** 753 flows is too many to curate by hand;
a title search is more maintainable and always current.

---

## 3. What the data looks like when you fetch it

When you pull a dataflow without asking for metadata:
```
pandas.Series
Index levels: TIME_PERIOD, REF_AREA, FREQ, MEASURE, SEX, AGE
Values: float64 (the actual number, e.g. 3.3 for 3.3% unemployment)
```

When you add `attributes='osgd'` (which you must, for break detection):
```
pandas.DataFrame
Columns: value, DECIMALS, UNIT_MEASURE, UNIT_MULT, UNIT_MEASURE_TYPE,
         UPPER_BOUND, LOWER_BOUND, SOURCE, OBS_STATUS
Some flows also add: NOTE_SOURCE, NOTE_INDICATOR, NOTE_CLASSIF
```

The `SOURCE` column is what makes break detection possible. Missing values come back
as empty string `''`, not `NaN` — watch for this in comparisons.

**`attributes='osgd'` must be used everywhere** — without it, SOURCE is silently dropped
and break detection stops working.

---

## 4. Break detection

### What break detection is, simply

A country reports unemployment at 5% in 2018 and 7% in 2019. Did unemployment actually
jump 2 points, or did the country switch to a different survey that measures differently?
You can't tell by looking at the numbers alone. Break detection catches this: it checks
whether the data source (the survey) changed between years. If it did, the numbers
before and after aren't directly comparable — so the tool warns instead of blindly
computing "unemployment rose 2%."

### What signals ILOSTAT provides

**`SOURCE` attribute — CONFIRMED, works.** Each data point is tagged with where it came
from, e.g. "Labour Force Survey" or "Household Income Survey." When this tag changes
mid-series for a country, that's the break signal.

**`OBS_PRE_BREAK_VALUE` — NOT used by ILOSTAT.** The SDMX standard has a field for
this but ILOSTAT leaves it empty. We can't rely on it.

→ **Break detection = watch for SOURCE tag changes across consecutive years. That's it.**

---

## 5. Confirmed break countries

### Employment breaks

| Country | What changed | Dataflow used to confirm |
|---|---|---|
| Nigeria (NGA) | Survey switched from "HIES - Living Standards Survey" to "HS - General Household Survey" | `DF_UNE_3EAP_SEX_AGE_DSB_RT` |
| Pakistan (PAK) | Survey switched from "LFS - Labour Force Survey" to "HIES - Household Income and Expenditure Survey" | `DF_UNE_3EAP_SEX_AGE_DSB_RT` |

These two are locked in for benchmark q003 and q018/q019.

Before writing ground truth: verify the break also shows up in `DF_UNE_DEAP_SEX_AGE_RT`
(the main national survey unemployment rate), not just the disability-disaggregated flow.

### Wage breaks

Many countries with wage SOURCE changes found across three EAR dataflows:

| Country | Dataflow | Survey change |
|---|---|---|
| Thailand (THA) | `DF_EAR_CMTA_SEX_CUR_NB` | LFS → Household Socio-Economic Survey |
| Argentina (ARG) | `DF_EAR_CMTA_SEX_CUR_NB` | Permanent Household Survey → National Household Expenditure Survey |
| Ghana (GHA) | `DF_EAR_CMTA_SEX_CUR_NB` | LFS → Living Standards Measurement Survey |
| Colombia (COL) | `DF_EAR_CMTA_SEX_CUR_NB` | Gran Encuesta Integrada → Encuesta Continua |
| Chile (CHL) | `DF_EAR_EHRA_SEX_ECO_CUR_NB` | CASEN → Supplemental Income Survey |
| Kenya (KEN) | `DF_EAR_EHRA_SEX_ECO_CUR_NB` | Continuous household survey → Household Budget Survey |
| Peru (PER) | `DF_EAR_EHRA_SEX_ECO_CUR_NB` | Permanent Employment Survey → National Household Survey |

**Picked for benchmark q020: Thailand (THA), `DF_EAR_CMTA_SEX_CUR_NB`** (monthly earnings).
Clean two-source change, well-known country, English-language source names.

---

## 6. Edge cases — what happens when data doesn't exist

| What you ask for | What happens | What the tool should say |
|---|---|---|
| Malaysia wages in 1960 (too old) | HTTP 404 error | "No data available for this period" |
| North Korea unemployment 2023 | Returns data (36 rows) — but it's modelled estimates, not real survey data | "No national survey data; ILO does publish modelled estimates but they are imputed, not observed" |
| Malaysia unemployment in 2027 (future) | Returns data (9 rows) — ILO projections | Same as above — these are projections, not observed data |

The practical implication: benchmark q005 (North Korea) and q012 (future date) only
behave as "no data" if the tool is using survey dataflows. If it falls back to modelled
estimates, it will wrongly return a number. This is an architecture decision for Phase 1.

---

## 7. Country list

`client.codelist('CL_AREA')` returns **335 countries/territories**.
Access with `cl.items` (a dict — do NOT call it like a function).

Georgia (`GEO`) confirmed present — validates benchmark q009 (Georgia ambiguity).

---

## 8. Indicator metadata

Calling `client.dataflow('ID', params={'references': 'all'})` gives you:
- The indicator's name and description
- What dimensions and attributes it has (including confirmation that SOURCE is defined)
- When it was last updated (via a `LAST_UPDATE` annotation field)

This is enough to power the `get_indicator_metadata()` tool.

---

## 9. Country filtering — how to do it fast

Three strategies tested. Only one works well:

| Strategy | Time | Result |
|---|---|---|
| Pull all countries, filter in pandas | 5.0s | Works but downloads 2,475 rows to get 9 |
| String key `'MYS'` | — | 422 error from ILO's endpoint — not supported |
| `dsd=False` in the client call | 1.4s | ✅ Works, 3.5× faster |

**Winner: `dsd=False`.**

What `dsd=False` does: normally, when you pass a dict key like `{'REF_AREA': 'MYS'}`, the library fetches the dataflow's schema first (to validate your key). That schema fetch is what sometimes fails. `dsd=False` skips the validation and sends the filter directly — the ILO endpoint handles it fine.

```python
msg = client.data(
    "DF_UNE_2EAP_SEX_AGE_RT",
    key={"REF_AREA": "MYS"},
    params={"startPeriod": "2022", "endPeriod": "2023"},
    dsd=False,
)
```

Every `get_time_series` call in `sdmx_client.py` should use `dsd=False`.

---

## 10. Dimension defaults — exact codes

When a user asks "Malaysia's unemployment rate," they don't want 9 rows broken down by sex and age. They want one number: total, working-age adults.

**Confirmed default codes:**

| Dimension | Code for "total / all" | Meaning |
|---|---|---|
| `SEX` | `SEX_T` | Both sexes combined |
| `AGE` | `AGE_YTHADULT_YGE15` | All working age (15 and over) |

Survey dataflows have many more age bands (5-year, 10-year, aggregate groups), but `AGE_YTHADULT_YGE15` is consistently the "total working age" entry across both modelled and survey flows.

`get_time_series` should default to `SEX=SEX_T, AGE=AGE_YTHADULT_YGE15` and let the user override if they want breakdowns.

---

## 11. NOTE_SOURCE — not useful

Every source in NGA's data has the same note: `"Repository: ILO-STATISTICS - Micro data processing"`. It doesn't explain *why* the survey changed or what changed methodologically. It's just a data provenance label.

**Decision:** don't surface `NOTE_SOURCE` in the break warning. The break message should say what surveys were involved (from `SOURCE`) and that the numbers before and after may not be comparable — that's enough without the internal repo label.

---

## 12. Architecture decision — modelled estimates vs. survey data

**The problem:** ILOSTAT has two kinds of data for the same indicators:
- **Survey data** — real numbers from countries' own surveys. Patchy (not every country, not every year). Has methodology breaks.
- **Modelled estimates** — ILO fills in the gaps by imputing. Covers all countries, all recent years, even North Korea and future years. Looks like real data but isn't.

If the MCP just picks whichever dataflow has data, it will sometimes silently return an imputed number when no real data exists — which is exactly the hallucination failure mode we're trying to prevent.

**Decision: survey data by default; modelled estimates surfaced only if explicitly requested, and always labelled.**

In practice this means:
- `search_indicators` returns both types but marks modelled flows clearly (e.g. with a `"modelled_estimate": true` flag)
- `get_time_series` uses the dataflow ID the user passes — it doesn't silently switch to a modelled flow
- The system prompt (via `ilostat://system-prompt`) instructs the agent to prefer survey flows and to disclose when a result comes from a modelled estimate
- If a survey flow returns no data for a country, the tool says "no survey data available" — it does NOT automatically fall back to the modelled estimate

This preserves the benchmark's `unanswerable_no_data` category: asking for North Korea's survey unemployment rate genuinely has no data, even if the modelled estimate exists.

---

## 13. FastMCP API — what we need to write server.py

FastMCP v3.4.4 is available. Everything needed for v1:

**Server setup:**
```python
from fastmcp import FastMCP
mcp = FastMCP("ilostat", instructions="...")
```

**Registering a tool:** `@mcp.tool` decorator. Docstring becomes the tool description shown to the LLM. Args section of the docstring feeds per-parameter descriptions into the schema.
```python
@mcp.tool
def get_time_series(dataflow_id: str, country: str, start: int, end: int) -> dict:
    """Fetch a labour market time series from ILOSTAT.

    Args:
        dataflow_id: The ILOSTAT dataflow ID (use search_indicators to find one).
        country: ISO 3-letter country code (e.g. 'MYS', 'DEU').
        start: Start year.
        end: End year.
    """
    ...
```

**Return types:** just return a `dict` — FastMCP serialises it to JSON automatically. No need to manually stringify anything.

**Registering a resource:**
```python
@mcp.resource("ilostat://system-prompt")
def system_prompt() -> str:
    return "..."
```
URI with `{param}` in it becomes a template resource automatically.

**Entry point:**
```python
if __name__ == "__main__":
    mcp.run()  # stdio by default — what Claude Desktop uses
```

**Sync vs async:** both work. Sync tools run in a thread pool automatically (won't block the event loop). Use sync for simplicity — no async needed for `sdmx1` calls.

**Gotcha:** `@mcp.resource` requires the URI in parentheses — `@mcp.resource` alone raises `TypeError`.

---

---

## 14. Dataflow ID structure — what each segment means

**Source:** ILOSTAT SDMX API Guide v4.1, §III.2.5–III.2.6 (p.10) and footnote 2 (p.13)

Structure: `DF_[TOPIC]_[VARIANT]_[CLASSIF1]_[CLASSIF2]_[MEASURE_TYPE]`

| Segment | What it is | Examples |
|---|---|---|
| `DF_` | Marks it as a dataflow. One dataflow per DSD. | — |
| **TOPIC** | The statistical concept | `UNE` = Unemployment, `EMP` = Employment, `EAP` = Economically Active Population, `EAR` = Earnings |
| **VARIANT** | Population reference and methodology | `TEMP` = Total EMPloyment (only one explicitly decoded in doc). `DEAP`, `EMTA`, `CMTA`, `EHRA` — **not decoded in this doc**, defined in `CL_INDICATOR` codelist |
| **CLASSIF(s)** | Dimension breakdowns inserted after the variant | `SEX`, `AGE`, `ECO` (economic activity), `CUR` (currency), `DSB` (disability) |
| **MEASURE_TYPE** | How the value is expressed | `NB` = Number (count), `RT` = Rate |

**Leading-digit rule for modelled estimates:** variants starting with `2` (e.g. `2EAP`, `2EMP`) are ILO modelled estimates. Confirmed by the doc's filtering example (p.14): `/data/ILO,DF_EAP_2EAP_SEX_AGE_NB/X85....` — annotated as "(only valid for estimates)". No exceptions shown in the doc. Matches our Phase 0a title search: every `2EAP`/`2WAP` flow name contains "ILO modelled estimates".

**What the doc does NOT decode:** the specific expansions of `DEAP`, `EMTA`, `CMTA`, `EHRA`. These are defined in the `CL_INDICATOR` codelist — retrieve via `GET /codelist/ILO/CL_INDICATOR` (§III.2.4, p.9).

---

## 15. API mechanics — gaps closed by doc research

**Source:** ILOSTAT SDMX API Guide v4.1

### FREQ=A filter
§III.4.2, p.13: *"The characters 'M', 'Q' and 'A' in the FREQ dimension can be used to filter data points with Monthly, Quarterly and Annual time reference periods."*
FREQ is the second dimension in the key. In sdmx1: `key={"FREQ": "A"}`.

### SOURCE attribute — officially documented
§III.4.4, p.15: *"The attribute SOURCE returns to the type and title of the data source e.g. 'LFS – Labour Force Survey', 'ADM - Sistema Integrado Previsional Argentino'."*
This is the official confirmation that SOURCE is the right signal for break detection. Not a quirk of the data — it is a defined attribute of every observation.

### CUR filter for wages
Not explicitly covered in the doc. CUR is a standard dimension (appears in `DF_EAR_CMTA_SEX_CUR_NB`). It filters the same way as any other dimension per §III.4.2. The code for local currency is `CUR_TYPE_LCU` — from Phase 0a execution, not from the doc.

### 404 vs KeyError distinction
The cheat sheet (p.17) defines HTTP 404 as "Not found. No results." The doc does not distinguish at the Python level between a 404 and a country-absent-in-results case that produces a `KeyError` in pandas. Still empirical.

### Browsing by topic (for 1b — flow enumeration)
§III.2.7, p.11: `GET /categoryscheme/ILO` returns all categories (e.g. EMP, UNE) linked to their associated dataflows. Better starting point than keyword-searching all 1,210 titles when you want every flow for a given concept.

---

## Decisions locked by Phase 0a

| Decision | What we decided and why |
|---|---|
| `search_indicators` | Live keyword search — 753 flows is too many to hand-curate |
| Break detection signal | SOURCE tag changes only — `OBS_PRE_BREAK_VALUE` is empty everywhere |
| Data fetch key strategy | `dsd=False` — skips schema validation that sometimes fails, 3.5× faster |
| Attributes flag | Always use `attributes='osgd'` or SOURCE gets silently dropped |
| Codelist access | `cl.items` is a plain dict attribute, not a method — don't call it |
| NOTE_SOURCE | Not useful — skip it in break warnings |
| Modelled vs. survey | Survey data by default; modelled labelled and opt-in |
| Dimension defaults | `SEX_T`, `AGE_YTHADULT_YGE15` |
| Wage break country for q020 | Thailand (THA), `DF_EAR_CMTA_SEX_CUR_NB` |

**Phase 0a fully complete. All unknowns resolved. Ready for Phase 1.**
