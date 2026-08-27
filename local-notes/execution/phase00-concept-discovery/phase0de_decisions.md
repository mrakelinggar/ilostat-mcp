# Phase 0d/0e — Pre-Phase 1 Design Decisions

Date: 2026-08-28
API checks: `code/phase0de_api_checks.py`

All decisions here are locked before Phase 1 coding begins. Each item either came from a live API check this session or is a pure design decision made here.

---

## D1 — Benchmark q021: genuine "no data" country

**API result:** PRK (North Korea) and ERI (Eritrea) both return `requests.exceptions.HTTPError` 404 on `DF_UNE_DEAP_SEX_AGE_RT`. No data exists for either.

Smaller countries tested (NRU, TUV, SSD, TKM) all have data — from population censuses or official estimates when no household survey exists.

**Decision:** Use **PRK** for benchmark q021 (`unanswerable_no_data`). It is universally understood as a country with no independent statistical reporting, so the "why" is intuitive and the benchmark question isn't contrived.

---

## D2 — Exception type for 404

**API result:** Both "country has no data" and "invalid flow ID" raise `requests.exceptions.HTTPError` with status 404. The two cases are distinguishable only by which endpoint is called:

- `client.data(...)` → 404 = "no data for this country/flow/filter combination"
- `client.dataflow(...)` → 404 = "flow ID does not exist in ILOSTAT"

**Decision for `sdmx_client.py`:**

```python
from requests.exceptions import HTTPError

try:
    resp = client.data(flow_id, key=key, params=params)
    ...
except HTTPError as e:
    if e.response.status_code == 404:
        return pd.DataFrame()  # empty → caller checks df.empty
    raise  # unexpected non-404 HTTP errors propagate
```

Return an empty DataFrame on 404 — don't raise from the client. The tool layer checks `df.empty` and formats the "no data available" MCP response. This keeps the client boundary clean: it either returns a DataFrame or raises an unexpected error.

---

## D3 — `get_indicator_metadata`: last_updated source

**API result:** The `last_updated` timestamp is in the dataflow metadata, not in the data response.

From `client.dataflow("DF_UNE_DEAP_SEX_AGE_RT")`:
```
flow.annotations = [
    Annotation(type='LAST_UPDATE', title='23/08/2026 07:12:11', ...),
    Annotation(type='LAYOUT_COLUMN', title='AGE', ...),
    Annotation(type='DEFAULT', title='FREQ=A,...', ...),
    ...
]
```

The `LAST_UPDATE` annotation holds when ILOSTAT last updated this dataflow's data. The data message header `prepared` field is the API response timestamp (i.e. "now") — not the data update date. Don't use it.

**Decision for `sdmx_client.get_indicator_metadata(flow_id)`:**

```python
resp = client.dataflow(flow_id)
flow = resp.dataflow[flow_id]

last_updated = next(
    (a.title for a in flow.annotations if a.type == "LAST_UPDATE"),
    None
)
```

Full return dict from `get_indicator_metadata`:

```python
{
    "id":           flow_id,
    "title":        str(flow.name),
    "description":  strip_html(str(flow.description)),  # HTML in raw
    "last_updated": last_updated,    # "23/08/2026 07:12:11" or None
}
```

No unit or source info in the dataflow metadata — those come from the data itself (UNIT_MEASURE, SOURCE columns). Don't try to surface them from metadata; the agent can call `get_time_series` if it needs them.

---

## D4 — Response structure for `sdmx_client.py` functions

**Rule:** The client returns the simplest structure each tool needs. No over-engineering.

### `get_time_series(flow_id, country, start, end, *, freq="A", sex="SEX_T", age=None, cur=None) → pd.DataFrame`

Returns a DataFrame. Columns kept from the SDMX response (all lowercased):

| Column | Keep? | Why |
|---|---|---|
| `time_period` | ✅ | The data key |
| `value` | ✅ | The number |
| `obs_status` | ✅ | Break detection ('' / 'B' / 'U') |
| `source` | ✅ | Break detection (SOURCE diff) |
| `unit_measure` | ✅ | 'PT' (percent) or 'CR' (currency) — tool uses for display |
| `freq` | ✅ | Useful if caller requests non-annual |
| `sex` | ✅ | Validation |
| `age` | ✅ if present | Validation |
| `cur` | ✅ if present | Wages — tells caller LCU/PPP/USD |
| `note_classif` | ✅ | Often has "Break in series: ..." text — useful for break context |
| `measure` | ❌ | Always single-valued per flow — redundant with flow_id |
| `unit_measure_type` | ❌ | Redundant with unit_measure |
| `unit_mult` | ❌ | Always 0 for our flows |
| `note_source` | ❌ | Verbose, low signal |
| `note_indicator` | ❌ | Almost always empty |
| `decimals` | ❌ | Not needed downstream |
| `upper_bound` | ❌ | Always empty in our flows |
| `lower_bound` | ❌ | Always empty in our flows |

Implementation note: fetch with `sdmx.to_pandas(resp, attributes="o")`, rename ALL_CAPS → lowercase, drop the columns marked ❌.

Empty DataFrame on 404. Caller checks `df.empty`.

### `get_indicator_metadata(flow_id) → dict`

```python
{"id": str, "title": str, "description": str, "last_updated": str | None}
```

See D3.

### `get_countries() → list[dict]`

```python
[{"code": "FRA", "name": "France"}, ...]
```

Source: `CL_AREA` codelist via `client.codelist("CL_AREA")` — once the codelist() call syntax is fixed. Until then: the call is needed but not in Phase 1 tools (get_countries is Phase 2).

### `search_indicators(keyword) → list[dict]`

```python
[{"id": "DF_UNE_DEAP_SEX_AGE_RT", "title": "Unemployment rate by sex and age", "is_modelled": False}, ...]
```

Implementation: call `client.dataflow()` (returns all ILO flows), filter where `keyword.lower()` appears in `flow.name.lower()`. Cap at 20 results. Include `is_modelled` flag (leading digit in variant segment).

---

## D5 — FREQ filter location

**Decision:** FREQ is a parameter to `get_time_series`, defaulting to `"A"`. It is applied as a post-fetch pandas filter (not in the sdmx key dict), because:
1. Simpler to implement — no need to know whether FREQ is a named dimension in the key
2. We already fetch only one country at a time — the overhead of fetching all frequencies is small
3. Quarterly/monthly data is useful for future tools; making it a parameter now costs nothing

```python
def get_time_series(flow_id, country, start, end, *, freq="A", ...):
    ...
    df = df[df["freq"] == freq]
```

---

## D6 — Modelled estimate detection (runtime)

**Decision:** `sdmx_client.py` does not filter or warn on modelled flows — it fetches whatever flow ID it's given. Modelled detection lives in two places only:

1. `search_indicators` — sets `is_modelled: True` in the result so the agent can see it
2. `indicators.py` — only canonical (survey-based) flows are registered there

An agent querying a modelled flow directly gets the data without a warning. This is acceptable because modelled flows are clearly labelled "ILO modelled estimates" in their title, and `search_indicators` flags them. No need to guard at the client level.

Detection rule (for `search_indicators` and `indicators.py`):
```python
def is_modelled(flow_id: str) -> bool:
    parts = flow_id.split("_")
    return len(parts) > 2 and parts[2][0].isdigit()
```

---

## D7 — `get_yoy_change`: SOURCE break check

**Decision:** Yes — if the SOURCE changed between year N-1 and year N, include a warning in the `get_yoy_change` response. The year-over-year number is real but unreliable when the surveys are different. Consistent with the "never silently compute across a break" principle.

Implementation: after fetching rows for year N and N-1, check if `source` values differ. If so, append a break warning to the response. The warning does not suppress the computed value — it wraps it with context (same pattern as `get_cagr` / `get_trend`).

---

## D8 — `search_indicators` result cap and format

**Decision:** Cap at 20 results. Rationale: an agent calling this tool needs enough results to find the right flow, not an exhaustive list. 20 covers any reasonable keyword.

Sort order: use `ORDER` annotation from the dataflow metadata (ILOSTAT assigns these) when available; otherwise alphabetical by flow ID.

---

## D9 — `get_time_series` key filter construction

When calling `client.data()`, the key dict must match only the dimensions present in the flow. For example, unemployment flows have `AGE` but wage flows don't; wage flows have `CUR` but unemployment flows don't. Passing `CUR` to an unemployment flow would cause an error.

**Decision:** Build the key dict dynamically — only include `age` if it's not None, only include `cur` if it's not None.

```python
key = {"REF_AREA": country, "SEX": sex}
if age is not None:
    key["AGE"] = age
if cur is not None:
    key["CUR"] = cur
```

The caller (tool layer) passes the right combination based on which flow it's querying. `indicators.py` stores the required key shape for each theme.

---

## D10 — LCU currency display

**Decision (Phase 1):** Return the `cur` column value in the DataFrame (`CUR_TYPE_LCU`) and include a note in the tool response that LCU means "the country's own currency." Do not attempt to resolve EUR/NGN/BRL.

**Deferred to Phase 2 enhancement:** A `COUNTRY_CURRENCY` dict in `indicators.py` mapping ISO alpha-3 → ISO 4217 (e.g. `{"FRA": "EUR", "NGA": "NGN", "BRA": "BRL"}`). This allows the tool to say "2,196.95 EUR" instead of "2,196.95 LCU." Not a blocker — the tool is still useful without it.

---

## Summary: what's now locked for Phase 1

| Decision | Value |
|---|---|
| No-data benchmark country | PRK |
| 404 handling | `requests.exceptions.HTTPError` → return empty DataFrame |
| `last_updated` source | `LAST_UPDATE` annotation from `client.dataflow()` |
| `get_time_series` return type | DataFrame, lowercased columns, 9 kept + others dropped |
| `get_indicator_metadata` return type | dict with id, title, description, last_updated |
| `get_countries` return type | list of {code, name} dicts |
| `search_indicators` return type | list of {id, title, is_modelled} dicts, cap 20 |
| FREQ filter | parameter to get_time_series, default 'A', post-fetch pandas filter |
| Modelled detection | in search_indicators + indicators.py only; not in client |
| get_yoy_change SOURCE check | Yes — warn if sources differ between N and N-1 |
| Key dict construction | Dynamic — only include AGE/CUR if not None |
| LCU currency display | Surface CUR_TYPE_LCU label; ISO symbol deferred to Phase 2 |
| MEASURE column | Drop from returned DataFrame |
