# Phase 2b — MCP Completeness Fixes

## What and why

Phase 2 delivered a working MCP with 4 tools and 1 resource, but an audit
against the full benchmark question set revealed four categories of gap:
`get_time_series` silently misbehaves for any dataflow not in `FLOW_DIMS`;
the tool has no way to request youth-band data; two specified resources were
never built; and error handling conflates infrastructure failures (API down,
network timeout, rate limiting) with legitimate empty results, leaving Claude
unable to tell the user what actually went wrong. This phase closes all four
before Phase 3 (break detection) locks the `get_time_series` interface.

---

## Decisions already locked (no unknowns)

| Decision | Value | Rationale |
|---|---|---|
| Youth AGE architecture | Optional `age_group` param on `get_time_series` tool: `"total"` (default) or `"youth"` | Transparent to agent and user; Option A (per-flow registry default) hides the choice and could cause silent wrong results |
| `ilostat://codelists/indicator` content | 4 canonical flows from `indicators.py` — theme name, flow ID, title | Loads into agent context before conversation; reduces reliance on `search_indicators` for common cases and removes temptation to guess flow IDs |
| `ilostat://codelists/area` | Already cached in `resources.py` via `get_cached_countries()` — just needs a resource endpoint registered in `server.py` | Pure wiring, no new logic |

---

## Tasks

### Task 0 — Pre-task discovery: GEO dimension on `DF_UNE_3EAP_SEX_AGE_GEO_RT`

**What and why:** This flow (used in q016, South Africa youth unemployment) has
a GEO dimension beyond the standard REF_AREA/SEX/AGE set. We don't know what
happens if we omit it — the API might return national totals, all geographic
breakdowns mixed together, or an error. If we code Task 1 without checking this,
we might register the flow correctly and still get wrong data for q016.

Run before writing any code:

```python
# In a scratch script — call the flow without a GEO value and inspect the result
df = sdmx_client.get_time_series("DF_UNE_3EAP_SEX_AGE_GEO_RT", "ZAF", "2021", "2021",
                                  age=AGE_YTHBANDS_Y15-29)
print(df)
print(df.columns.tolist())
```

Possible outcomes and what to do:

- **Returns one row (national total):** GEO defaults to national — no extra
  handling needed. Proceed with Task 1 as planned.
- **Returns multiple rows (all geographies):** Need a GEO filter. Find the
  "national total" GEO code from the data or ILOSTAT codelist and store it in
  `FLOW_DIMS` alongside the dimension type. Update Task 1 accordingly.
- **Returns empty or errors:** Investigate. May need a separate `FLOW_DIMS`
  structure that can carry extra key values beyond dimension type.

Record the finding before starting Task 1.

---

### Task 1 — Extend `FLOW_DIMS` and fix `is_modelled` in `indicators.py`

**Part A — `FLOW_DIMS`:** Add the four benchmark flows missing from the registry.
Without this, `get_time_series` sends no AGE/CUR dimension for these flows,
returning mixed or unexpected data. GEO handling for `DF_UNE_3EAP_SEX_AGE_GEO_RT`
may add complexity — resolve in Task 0 first.

Flows to add:

| Flow ID | Dimension type | Used in benchmark |
|---|---|---|
| `DF_UNE_3EAP_SEX_AGE_DSB_RT` | `"age"` | q003, q018 (Nigeria unemployment) |
| `DF_UNE_3EAP_SEX_AGE_GEO_RT` | `"age"` (see Task 0) | q016 (South Africa youth) |
| `DF_EMP_2WAP_SEX_AGE_RT` | `"age"` | q013 (Germany emp-to-pop, modelled) |
| `DF_EAR_CMTA_SEX_CUR_NB` | `"cur"` | q004 (Pakistan wages, care sector) |

**Part B — `is_modelled`:** The `_MODELLED_MARKERS` tuple currently checks for
`_ILO_MODELLED` and `_MOD_` only. `DF_EMP_2WAP_SEX_AGE_RT` uses the `2WAP`
prefix to signal modelled estimates — it matches neither pattern, so
`is_modelled()` returns `False` for it. This causes `search_indicators` and
`get_indicator_metadata` to misreport it as survey data.

Fix: add `"2WAP"` to `_MODELLED_MARKERS`. One line change. Then verify no
legitimate survey flows contain `"2WAP"` in their ID (quick grep of the
dataflow catalog).

---

### Task 2 — Add `age_group` parameter to `get_time_series` tool

**In `server.py`:**

Add `age_group: str = "total"` as an optional parameter to the
`get_time_series` tool function. Map it to the correct SDMX age code before
passing to `sdmx_client.get_time_series`:

```
"total" → AGE_YTHADULT_YGE15   (adults 15+, the current default)
"youth" → AGE_YTHBANDS_Y15-29  (youth 15–29, ILO standard youth band)
```

Only apply this mapping when the flow uses the `"age"` dimension (i.e.
`FLOW_DIMS.get(dataflow_id) == "age"`). For `"cur"` flows the parameter is
ignored. Raise a clear error if an unrecognised value is passed.

**In `sdmx_client.py`:**

No change needed — it already accepts an `age` kwarg and passes it through.
The mapping lives entirely in `server.py`.

**Tool description update:**

Add to the existing tool description: `age_group` accepts `"total"` (default,
adults 15+) or `"youth"` (15–29). Ignored for wage flows.

---

### Task 3 — Register `ilostat://codelists/area` resource

**In `server.py`:**

Add a `@mcp.resource("ilostat://codelists/area")` function that calls
`resources.get_cached_countries()` and returns the list serialised as JSON.
The cache already exists in `resources.py` — this is pure wiring.

---

### Task 4 — Build and register `ilostat://codelists/indicator` resource

**In `resources.py`:**

Add a `CANONICAL_FLOWS` constant — a list of dicts, one per canonical theme,
drawn directly from `indicators.FLOWS`:

```python
[
  {"theme": "unemployment_rate", "dataflow_id": "DF_UNE_DEAP_SEX_AGE_RT",  "title": "..."},
  {"theme": "employment_to_pop", "dataflow_id": "DF_EMP_DWAP_SEX_AGE_RT",  "title": "..."},
  {"theme": "wages",             "dataflow_id": "DF_EAR_EMTA_SEX_CUR_NB",  "title": "..."},
  {"theme": "lfpr",              "dataflow_id": "DF_EAP_DWAP_SEX_AGE_RT",  "title": "..."},
]
```

Titles are human-readable strings — fill them from `get_indicator_metadata`
during a one-off lookup or hardcode from known ILOSTAT titles (acceptable
since these flows are locked for v1 and won't change).

**In `server.py`:**

Add `@mcp.resource("ilostat://codelists/indicator")` returning
`resources.CANONICAL_FLOWS` serialised as JSON.

---

### Task 5 — Infrastructure error handling in `sdmx_client.py`

**What and why:** All HTTP calls go through `sdmx_client.py`. Currently, anything
that isn't a 404/400 propagates to FastMCP as a raw Python exception — Claude sees
a cryptic traceback instead of a message it can relay to the user. More critically,
no request timeout is set, so a slow or hanging ILOSTAT response blocks the tool
indefinitely. These need to be fixed at the client layer, centrally, before the
codebase grows more callers.

**Pre-task discovery — timeout with sdmx1 + cloudscraper:**

It's unclear whether sdmx1 forwards a `timeout` kwarg to the underlying requests
session, or whether timeout must be set on the `cloudscraper` session object
directly. Check sdmx1's source or test both before writing the fix. If neither
works cleanly, set it via a session-level `request` hook.

**Fixes in `sdmx_client.py`:**

1. **Request timeout** — set a 30-second timeout on all API calls. A hung request
   is worse than a failed one: the MCP tool never returns and Claude sits waiting.
   Where exactly this is configured depends on the discovery above.

2. **Network failures** — catch `requests.exceptions.ConnectionError` and
   `requests.exceptions.Timeout` in each public function and re-raise as
   `RuntimeError` with plain English: "Could not reach ILOSTAT's API — check your
   internet connection." and "ILOSTAT API request timed out — the server may be
   slow or unavailable. Try again." respectively.

3. **HTTP 429 (rate limited)** — currently treated the same as any non-404 error.
   Catch it explicitly and raise: "ILOSTAT rate limit reached — wait a moment and
   try again."

4. **HTTP 500/503 (server error)** — raise: "ILOSTAT API returned a server error
   and may be temporarily down. Try again shortly."

5. **`get_countries` silent swallow** — currently catches all exceptions and returns
   `[]`, identical to "no countries". Re-raise instead. An empty country list is
   never a valid result.

6. **`search_indicators` silent swallow** — currently returns `[]` on HTTPError,
   identical to "no keyword matches". Re-raise on API failure; `[]` should only
   mean "no matches found."

**What stays as-is:**

- 404/400 → empty DataFrame/dict — correct, unambiguous, documented.
- sdmx1 parse errors — let these propagate; they're unexpected and should be
  visible, not swallowed.
- No retry logic — over-engineering for v1.

---

### Task 6 — User-input error handling in `server.py`

**What and why:** Two existing tools silently return empty results on API failure,
making infrastructure problems indistinguishable from legitimate "no data" results.
The agent can't tell the difference and will give the user a wrong answer instead
of flagging a problem. Fix these before Phase 3, since break detection and the
prompt both depend on `get_countries` working correctly.

**In `server.py`:**

`get_time_series` — add year-order validation before calling the client. If
`start_year > end_year`, raise a `ValueError` with a plain-English message:
"start_year must be before or equal to end_year (got 2022–2018)." The API does
not catch this — it returns empty silently, which the agent will misread as
"no data available."

`get_time_series` (Phase 2b addition) — validate `age_group` on entry:
accepted values are `"total"` and `"youth"` only. Raise `ValueError` for
anything else: "age_group must be 'total' or 'youth' (got 'adult')."

**What stays as-is:**

`get_indicator_metadata` returning `{}` on 404 — correct, unambiguous, documented.
`get_time_series` returning `[]` on 404 — correct, unambiguous, documented.

---

### Task 7 — Manual end-to-end verification

Use `fastmcp dev` dashboard for tool checks, Claude Desktop for one real
conversation test.

**Phase 2 tools (never verified):**
1. `search_indicators("unemployment")` — returns real matches, not empty
2. `get_countries()` — returns list with recognisable country names
3. `get_indicator_metadata("DF_UNE_DEAP_SEX_AGE_RT")` — returns title, description, last_updated
4. `get_time_series("DF_UNE_DEAP_SEX_AGE_RT", "PRK", "2020", "2022")` — returns `[]` (North Korea, no data)
5. `ilostat://system-prompt` loads in client

**Phase 2b additions:**
6. All three resources load: `system-prompt`, `codelists/area`, `codelists/indicator`
7. `get_time_series("DF_UNE_3EAP_SEX_AGE_GEO_RT", "ZAF", "2021", "2021", age_group="youth")` — returns youth band data, not adult totals
8. `get_time_series("DF_EAR_CMTA_SEX_CUR_NB", "PAK", "2010", "2021")` — CUR dimension set, data returns
9. `get_time_series("DF_EMP_2WAP_SEX_AGE_RT", "DEU", "2019", "2019")` — AGE dimension set, data returns; `is_modelled` shows `true`

**User-input error checks:**
10. `get_time_series(..., start_year="2022", end_year="2018")` — raises clear error about year ordering
11. `get_time_series(..., age_group="adult")` — raises clear error about accepted values

**Infrastructure error checks (simulate by temporarily breaking connectivity):**
12. Disconnect from internet, call any tool — Claude receives a plain-English "can't reach ILOSTAT" message, not a raw Python traceback
13. Confirm no tool hangs indefinitely — 30-second timeout fires and raises cleanly

**Claude Desktop sanity pass:**
14. Ask "What was Malaysia's unemployment rate in 2022?" — confirm Claude calls `search_indicators` then `get_time_series`, returns a real number, does not invent one

---

## Failure modes considered in this phase

*This section is required in every phase plan. For each failure mode, note
whether it is handled here, deferred, or intentionally out of scope. Phase 4.5
(Resilience Audit) will re-examine all of these with the full system in view.*

| Failure mode | Handled in this phase? | Notes |
|---|---|---|
| ILOSTAT API down / unreachable | ✅ Task 5 | `ConnectionError` → plain-English raise |
| Request hangs (slow API) | ✅ Task 5 | 30s timeout |
| HTTP 429 rate limit | ✅ Task 5 | Explicit message: "wait and retry" |
| HTTP 500/503 server error | ✅ Task 5 | Explicit message: "temporarily down" |
| `get_countries` / `search_indicators` API failure silently returns empty | ✅ Task 5 | Re-raise instead of swallowing |
| `start_year > end_year` | ✅ Task 6 | `ValueError` with plain-English message |
| Invalid `age_group` value | ✅ Task 6 | `ValueError` with accepted values listed |
| Flow not in `FLOW_DIMS` sends wrong dimensions | ✅ Task 1 | 4 missing flows added |
| `is_modelled` misclassifies `2WAP` flows as survey data | ✅ Task 1 | `"2WAP"` added to `_MODELLED_MARKERS` |
| GEO dimension on `DF_UNE_3EAP_SEX_AGE_GEO_RT` behaves unexpectedly | ⚠️ Task 0 | Unknown — discovery required first |
| Cloudflare challenge fails (cloudscraper unable to bypass) | ❌ Deferred to Phase 4.5 | Rare; cloudscraper is actively maintained |
| ILOSTAT changes SDMX response shape (sdmx1 parse error) | ❌ Out of scope for v1 | Let propagate — unexpected, should be visible |
| Agent passes a valid ISO-3 code that exists in CL_AREA but has no data | ✅ Existing | `get_time_series` returns `[]` — documented |
| Empty keyword to `search_indicators` | ❌ Deferred to Phase 4.5 | Low priority; returns full catalog capped at 20 |
| `sex` dimension mismatch (hardcoded `SEX_T`, user wants M/F) | ❌ Out of scope for v1 | No benchmark question tests this |

---

## What this phase does NOT cover

- Break detection (`_breaks` field, SOURCE diff logic) — Phase 3
- Derived stat tools (`get_yoy_change`, `get_cagr`, `get_trend`) — Phase 4
- `labor_market_snapshot` prompt — Phase 4 (needs all 7 tools first)
- Currency display (ISO 4217 symbol map) — Phase 4
- Full cross-phase resilience audit — Phase 4.5
