"""
API Reference Script — captures real output for every ILOSTAT call we will make.
Run with: uv run --with sdmx1 python local-notes/execution/phase-0/scratch_api_reference.py

One section per tool. Shows the exact call, the URL it hits, and the actual result.
"""

import json
import sdmx
import pandas as pd
from requests.exceptions import HTTPError

SEP = "\n" + "=" * 70 + "\n"

def section(title):
    print(SEP + f"[{title}]")

def show_url(client, resource_type, resource_id=None, key=None, params=None, dsd=None):
    """Print the actual URL the client would hit (without making the call)."""
    try:
        req_kwargs = dict(resource_type=resource_type)
        if resource_id: req_kwargs["resource_id"] = resource_id
        if key: req_kwargs["key"] = key
        if params: req_kwargs["params"] = params
        if dsd is not None: req_kwargs["dsd"] = dsd
        req = client._request_from_args(req_kwargs)
        print(f"  URL: {req.url}")
    except Exception as e:
        print(f"  (URL preview failed: {e})")

client = sdmx.Client("ILO")

# ============================================================
# CALL 1: Bulk dataflow list
# Used by: search_indicators(keyword)
# ============================================================
section("CALL 1 — Bulk dataflow list (used by: search_indicators)")

print("Purpose: fetch all 1,210 ILOSTAT dataflows so we can search titles by keyword.")
print("Trigger: called once at server startup and cached; re-used for every search_indicators call.\n")
print("sdmx1 call:")
print("  msg = client.dataflow()")
print("  # msg.dataflow is a dict: {dataflow_id: Dataflow object}")
print("  # Dataflow.name gives the human-readable title\n")

msg = client.dataflow()
all_flows = {k: str(v.name) for k, v in msg.dataflow.items()}

print(f"Result: {len(all_flows)} dataflows returned\n")
print("Sample — first 5 employment/wage flows matching keyword 'unemployment':")
matches = {k: v for k, v in all_flows.items() if "unemployment" in v.lower() or "UNE_" in k}
for i, (k, v) in enumerate(list(matches.items())[:5]):
    print(f"  {k}: {v}")

print("\nSample — first 5 matching keyword 'earnings':")
wage_matches = {k: v for k, v in all_flows.items() if "earning" in v.lower()}
for i, (k, v) in enumerate(list(wage_matches.items())[:5]):
    print(f"  {k}: {v}")

print("\nWhat search_indicators('unemployment rate') would return (title contains both words):")
filtered = {k: v for k, v in all_flows.items()
            if "unemployment" in v.lower() and "rate" in v.lower()}
for k, v in list(filtered.items())[:8]:
    print(f"  {k}: {v}")

# ============================================================
# CALL 2: Single dataflow metadata
# Used by: get_indicator_metadata(dataflow_id)
# ============================================================
section("CALL 2 — Dataflow metadata (used by: get_indicator_metadata)")

DF_ID = "DF_UNE_DEAP_SEX_AGE_RT"  # national survey unemployment rate
print(f"Purpose: get the full description, units, dimension list, and last-updated date for a dataflow.")
print(f"Example dataflow: {DF_ID}\n")
print("sdmx1 call:")
print(f'  msg = client.dataflow("{DF_ID}", params={{"references": "all"}})')
print("  # params={'references': 'all'} fetches the DSD (data structure definition) too\n")

msg2 = client.dataflow(DF_ID, params={"references": "all"})
df_obj = list(msg2.dataflow.values())[0]

print("Result:")
print(f"  name:        {df_obj.name}")
desc = str(df_obj.description or "")
# strip HTML tags simply
import re
desc_plain = re.sub(r"<[^>]+>", "", desc).strip()
print(f"  description: {desc_plain[:300]}{'...' if len(desc_plain) > 300 else ''}")

# Annotations
last_updated = None
if df_obj.annotations:
    for ann in df_obj.annotations:
        if ann.type == "LAST_UPDATE":
            last_updated = str(ann.text or ann.title or "")
print(f"  last_updated: {last_updated}")

# DSD
if msg2.structure:
    dsd = list(msg2.structure.values())[0]
    dims = [d.id for d in dsd.dimensions]
    attrs = [a.id for a in dsd.attributes]
    print(f"  dimensions:  {dims}")
    print(f"  attributes:  {attrs}")
    print(f"  measure:     {[m.id for m in dsd.measures]}")

# ============================================================
# CALL 3a: Time series — clean data pull (no breaks)
# Used by: get_time_series, get_yoy_change, get_cagr, get_trend
# ============================================================
section("CALL 3a — Time series, clean country + date range (used by: get_time_series etc.)")

DF_UNE = "DF_UNE_DEAP_SEX_AGE_RT"   # survey unemployment rate
COUNTRY = "MYS"
START, END = "2018", "2023"

print(f"Purpose: fetch a country's time series for a specific indicator and date range.")
print(f"Example: Malaysia unemployment rate, {START}–{END}, national survey data.\n")
print("sdmx1 call:")
print(f'  msg = client.data(')
print(f'      "{DF_UNE}",')
print(f'      key={{"REF_AREA": "{COUNTRY}"}},')
print(f'      params={{"startPeriod": "{START}", "endPeriod": "{END}"}},')
print(f'      dsd=False,')
print(f'  )')
print(f'  df = sdmx.to_pandas(msg, attributes="osgd")')
print(f'  # Filter to totals: SEX_T (both sexes), AGE_YTHADULT_YGE15 (working age 15+)\n')

try:
    msg3 = client.data(DF_UNE, key={"REF_AREA": COUNTRY},
                       params={"startPeriod": START, "endPeriod": END}, dsd=False)
    df3 = sdmx.to_pandas(msg3, attributes="osgd")

    print(f"Raw result shape: {df3.shape}")
    print(f"Index levels: {df3.index.names}")
    print(f"Columns: {list(df3.columns)}")

    # Filter to totals
    idx = df3.index
    mask = pd.Series(True, index=idx)
    if "SEX" in idx.names:
        mask &= idx.get_level_values("SEX") == "SEX_T"
    if "AGE" in idx.names:
        mask &= idx.get_level_values("AGE") == "AGE_YTHADULT_YGE15"
    totals = df3[mask.values]

    print(f"\nAfter filtering to SEX_T + AGE_YTHADULT_YGE15: {len(totals)} rows")
    print("\nActual result:")
    print(totals[["value", "SOURCE", "OBS_STATUS"]].to_string())

except HTTPError as e:
    print(f"No survey data for {COUNTRY} in {DF_UNE}: {e}")
    print("Falling back to modelled estimates for demo...")
    DF_UNE_M = "DF_UNE_2EAP_SEX_AGE_RT"
    msg3 = client.data(DF_UNE_M, key={"REF_AREA": COUNTRY},
                       params={"startPeriod": START, "endPeriod": END}, dsd=False)
    df3 = sdmx.to_pandas(msg3, attributes="osgd")
    idx = df3.index
    mask = pd.Series(True, index=idx)
    if "SEX" in idx.names:
        mask &= idx.get_level_values("SEX") == "SEX_T"
    if "AGE" in idx.names:
        mask &= idx.get_level_values("AGE") == "AGE_YTHADULT_YGE15"
    totals = df3[mask.values]
    print(totals[["value", "SOURCE", "OBS_STATUS"]].to_string())

# ============================================================
# CALL 3b: Time series — with a methodology break
# Used by: get_time_series (break detection path)
# ============================================================
section("CALL 3b — Time series with a methodology break (used by: break detection)")

DF_BREAK = "DF_UNE_DEAP_SEX_AGE_RT"
BREAK_COUNTRY = "NGA"

print(f"Purpose: same call as 3a — break detection happens in post-processing, not a separate API call.")
print(f"Example: Nigeria unemployment rate (confirmed SOURCE change mid-series).\n")
print("sdmx1 call: identical to 3a, just different country.")
print(f'  msg = client.data("{DF_BREAK}", key={{"REF_AREA": "{BREAK_COUNTRY}"}},')
print(f'      params={{"startPeriod": "2010", "endPeriod": "2023"}}, dsd=False)')
print(f'  df = sdmx.to_pandas(msg, attributes="osgd")\n')

try:
    msg4 = client.data(DF_BREAK, key={"REF_AREA": BREAK_COUNTRY},
                       params={"startPeriod": "2010", "endPeriod": "2023"}, dsd=False)
    df4 = sdmx.to_pandas(msg4, attributes="osgd")

    idx = df4.index
    mask = pd.Series(True, index=idx)
    if "SEX" in idx.names:
        mask &= idx.get_level_values("SEX") == "SEX_T"
    if "AGE" in idx.names:
        mask &= idx.get_level_values("AGE") == "AGE_YTHADULT_YGE15"
    nga = df4[mask.values] if mask.any() else df4

    print(f"Result shape (totals): {nga.shape}")
    print("\nActual result — note SOURCE column changing:")
    if "SOURCE" in nga.columns:
        print(nga[["value", "SOURCE"]].to_string())
    else:
        print(nga.head(10).to_string())

    # Show the break detection logic output
    if "SOURCE" in nga.columns:
        sources = nga["SOURCE"].unique().tolist()
        non_empty = [s for s in sources if s != ""]
        print(f"\nBreak detection output:")
        print(f"  Unique SOURCE values: {non_empty}")
        print(f"  has_break: {len(non_empty) > 1}")

except HTTPError as e:
    print(f"HTTPError for {BREAK_COUNTRY} in {DF_BREAK}: {e}")
    # Try a dataflow confirmed to have NGA breaks from discovery #1
    DF_BREAK2 = "DF_UNE_3EAP_SEX_AGE_DSB_RT"
    print(f"Retrying with {DF_BREAK2}...")
    msg4 = client.data(DF_BREAK2, key={"REF_AREA": BREAK_COUNTRY},
                       params={"startPeriod": "2010", "endPeriod": "2023"}, dsd=False)
    df4 = sdmx.to_pandas(msg4, attributes="osgd")
    if "SOURCE" in df4.columns:
        print(df4[["value", "SOURCE"]].head(15).to_string())
        print(f"\n  Unique SOURCE values: {[s for s in df4['SOURCE'].unique() if s != '']}")

# ============================================================
# CALL 3c: Time series — wages
# Used by: get_time_series (wages theme)
# ============================================================
section("CALL 3c — Time series, wages (used by: get_time_series wages theme)")

DF_WAGE = "DF_EAR_CMTA_SEX_CUR_NB"  # monthly earnings, confirmed has breaks
WAGE_COUNTRY = "THA"

print(f"Purpose: same call shape as unemployment — different dataflow ID for wages.")
print(f"Example: Thailand monthly earnings (also demonstrates the wage break case).\n")
print("sdmx1 call:")
print(f'  msg = client.data("{DF_WAGE}", key={{"REF_AREA": "{WAGE_COUNTRY}"}},')
print(f'      params={{"startPeriod": "2010", "endPeriod": "2023"}}, dsd=False)')
print(f'  df = sdmx.to_pandas(msg, attributes="osgd")\n')

try:
    msg5 = client.data(DF_WAGE, key={"REF_AREA": WAGE_COUNTRY},
                       params={"startPeriod": "2010", "endPeriod": "2023"}, dsd=False)
    df5 = sdmx.to_pandas(msg5, attributes="osgd")
    print(f"Result shape: {df5.shape}")
    print(f"Index levels: {df5.index.names}")
    print(f"Columns: {list(df5.columns)}")

    # Filter to SEX_T if available
    idx = df5.index
    if "SEX" in idx.names:
        mask = idx.get_level_values("SEX") == "SEX_T"
        df5_t = df5[mask]
    else:
        df5_t = df5

    cols = [c for c in ["value", "SOURCE", "UNIT_MEASURE", "OBS_STATUS"] if c in df5_t.columns]
    print(f"\nActual result (SEX_T):")
    print(df5_t[cols].head(20).to_string())

    if "SOURCE" in df5_t.columns:
        sources = [s for s in df5_t["SOURCE"].unique() if s != ""]
        print(f"\nSOURCE values: {sources}  → has_break: {len(sources) > 1}")

except Exception as e:
    print(f"ERROR: {e}")

# ============================================================
# CALL 3d: Time series — no data (country absent from survey)
# Used by: get_time_series (no-data path)
# ============================================================
section("CALL 3d — Time series, no survey data for country")

print("Purpose: understand what the API returns when a country has no survey data.")
print("This informs the error handling contract in sdmx_client.py.\n")

no_data_cases = [
    ("DF_UNE_DEAP_SEX_AGE_RT", "PRK", "2020", "2023", "North Korea — no survey data"),
    ("DF_UNE_DEAP_SEX_AGE_RT", "MYS", "1970", "1971", "Malaysia 1970 — out of date range"),
    ("DF_UNE_DEAP_SEX_AGE_RT", "MYS", "2027", "2027", "Malaysia 2027 — future date"),
]

for df_id, country, start, end, label in no_data_cases:
    print(f"\n  {label}:")
    print(f"  client.data('{df_id}', key={{'REF_AREA': '{country}'}}, params={{...}}, dsd=False)")
    try:
        msg_nd = client.data(df_id, key={"REF_AREA": country},
                             params={"startPeriod": start, "endPeriod": end}, dsd=False)
        s_nd = sdmx.to_pandas(msg_nd)
        if hasattr(s_nd, "__len__") and len(s_nd) == 0:
            print(f"  → Empty result (len=0)")
        elif hasattr(s_nd, "xs") and "REF_AREA" in s_nd.index.names:
            try:
                filtered = s_nd.xs(country, level="REF_AREA")
                print(f"  → Country absent from response (KeyError on xs) — no data")
            except KeyError:
                print(f"  → {country} not in response — correct 'no data' signal")
        else:
            print(f"  → Result len={len(s_nd) if hasattr(s_nd,'__len__') else '?'}")
    except HTTPError as e:
        print(f"  → HTTPError {e.response.status_code}: {e.response.reason}")
    except Exception as e:
        print(f"  → {type(e).__name__}: {e}")

# ============================================================
# CALL 4: Country codelist
# Used by: get_countries()
# ============================================================
section("CALL 4 — Country codelist (used by: get_countries)")

print("Purpose: return the full list of valid country codes and their names.")
print("Called once at startup and cached.\n")
print("sdmx1 call:")
print("  msg = client.codelist('CL_AREA')")
print("  cl = list(msg.codelist.values())[0]")
print("  countries = {code: str(item.name) for code, item in cl.items.items()}\n")

msg6 = client.codelist("CL_AREA")
cl = list(msg6.codelist.values())[0]
countries = {code: str(item.name) for code, item in cl.items.items()}

print(f"Result: {len(countries)} entries")
print("\nSample (10 entries):")
sample_keys = ["MYS", "SGP", "DEU", "FRA", "NGA", "THA", "GEO", "PRK", "COG", "COD"]
for k in sample_keys:
    if k in countries:
        print(f"  {k}: {countries[k]}")

# ============================================================
# Summary table
# ============================================================
section("SUMMARY — all API calls")

print("""
┌──────┬──────────────────────────────────────┬──────────────────────────────────┬───────────────────────────────────┐
│ Call │ sdmx1 method                         │ Key parameters                   │ Used by (MCP tools)               │
├──────┼──────────────────────────────────────┼──────────────────────────────────┼───────────────────────────────────┤
│  1   │ client.dataflow()                    │ none                             │ search_indicators                 │
│  2   │ client.dataflow(id, references=all)  │ dataflow_id                      │ get_indicator_metadata            │
│  3   │ client.data(id, key, params, dsd=F)  │ dataflow_id, REF_AREA,           │ get_time_series, get_yoy_change,  │
│      │ + to_pandas(msg, attributes='osgd')  │ startPeriod, endPeriod           │ get_cagr, get_trend               │
│  4   │ client.codelist('CL_AREA')           │ none                             │ get_countries                     │
└──────┴──────────────────────────────────────┴──────────────────────────────────┴───────────────────────────────────┘

Notes:
- Call 1 and 4 are cached at startup. No live fetch per user request.
- Call 2 is per-tool call (one HTTP request per get_indicator_metadata call).
- Call 3 is per-tool call. dsd=False skips schema validation — required for DF_ prefixed flows.
- Break detection is post-processing on Call 3's result — no extra API call needed.
- Modelled estimate flows (DF_*_2EAP_*) and survey flows (DF_*_DEAP_*) use identical Call 3 syntax.
""")
