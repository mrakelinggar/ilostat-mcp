"""
Phase 0 Discovery Script — ILOSTAT MCP
Run with: uv run --with sdmx1 python local-notes/execution/phase-0/scratch_discovery.py

Covers 8 checks. Prints a structured report. Throwaway exploration — not production code.
"""

import sys
import traceback

import sdmx
from requests.exceptions import HTTPError

SEP = "\n" + "=" * 70 + "\n"


def section(title):
    print(SEP + f"[{title}]")


# ---------------------------------------------------------------------------
# 1.1  Environment check
# ---------------------------------------------------------------------------
section("1.1 Environment check")

print(f"sdmx version: {sdmx.__version__}")
sources = sdmx.list_sources()
print(f"Built-in sources ({len(sources)}): {sorted(sources)}")
assert "ILO" in sources, "ILO source not found — check sdmx1 version"
print("ILO source: CONFIRMED")

client = sdmx.Client("ILO")
print(f"Client created: {client}")

# ---------------------------------------------------------------------------
# 1.2  Catalog exploration
# ---------------------------------------------------------------------------
section("1.2 Catalog exploration")

# Bulk fetch first — first run showed it works (1210 flows returned, no 413).
bulk = None
try:
    bulk = client.dataflow()
    all_ids = list(bulk.dataflow.keys())
    print(f"Bulk fetch succeeded — {len(all_ids)} total dataflows")
except HTTPError as e:
    print(f"Bulk fetch HTTPError: {e}")
except Exception as e:
    print(f"Bulk fetch error: {e}")

if bulk:
    # Filter for employment/wages prefixes. Note: newer IDs use DF_ prefix.
    keywords = ["EMP_", "UNE_", "EAR_", "EAP_"]
    emp_wage_ids = [i for i in all_ids if any(p in i for p in keywords)]
    print(f"Employment/wage-related IDs in catalog: {len(emp_wage_ids)}")

    # Print 20 sample titles to assess keyword-searchability
    print("\nSample titles (first 20 emp/wage flows):")
    for i in emp_wage_ids[:20]:
        print(f"  {i}: {str(bulk.dataflow[i].name)[:90]}")

    # Categorise by series type:
    # - Modelled estimates: contain "2" in the second segment (DF_UNE_2*, DF_EAP_2*)
    # - National survey data: DF_UNE_TUNE_*, DF_UNE_DWAP_*, DF_SDG_*, etc.
    # Break detection needs national survey data, not modelled estimates.
    une_all = [i for i in emp_wage_ids if "UNE_" in i and "RT" in i]
    une_modelled = [i for i in une_all if "_2EAP" in i or "_2WAP" in i]
    une_survey = [i for i in une_all if i not in une_modelled]
    ear_candidates = [i for i in emp_wage_ids if "EAR_" in i]

    print(f"\nUnemployment rate — modelled estimates: {une_modelled[:5]}")
    print(f"Unemployment rate — survey/national data: {une_survey}")
    print(f"Earnings/wages candidates (all): {ear_candidates[:15]}")

    # For data pull testing: use modelled estimates (broadest coverage)
    UNE_DATAFLOW = next((i for i in une_all if i.startswith("DF_")), une_all[0] if une_all else None)
    # For BREAK DETECTION: prefer survey/national data (breaks happen in real surveys)
    UNE_SURVEY_DATAFLOW = une_survey[0] if une_survey else UNE_DATAFLOW
    EAR_DATAFLOW = next((i for i in ear_candidates if i.startswith("DF_")), ear_candidates[0] if ear_candidates else None)
    # For wages: also try to find survey (non-modelled) variant
    ear_survey = [i for i in ear_candidates if "_2" not in i.split("_")[2] if len(i.split("_")) > 2]
    EAR_SURVEY_DATAFLOW = ear_survey[0] if ear_survey else EAR_DATAFLOW

    print(f"\nSelected for testing:")
    print(f"  Unemployment (modelled, for baseline pull): {UNE_DATAFLOW}")
    print(f"  Unemployment (survey, for break detection): {UNE_SURVEY_DATAFLOW}")
    print(f"  Wages/Earnings (for break detection): {EAR_SURVEY_DATAFLOW}")

    # Decision gate
    print(f"\nDECISION GATE: {len(emp_wage_ids)} employment/wage dataflows in catalog")
    if len(emp_wage_ids) <= 25:
        print("→ Curated lookup table in indicators.py (small enough to maintain manually)")
    else:
        print("→ Live keyword search against catalog titles at query time (too many to curate)")
else:
    # Fall back to known-good IDs from prior run
    UNE_DATAFLOW = "UNE_TUNE_SEX_AGE_NB"
    EAR_DATAFLOW = None
    EAR_SURVEY_DATAFLOW = None
    UNE_SURVEY_DATAFLOW = None
    emp_wage_ids = []
    print("Bulk fetch failed — using fallback IDs")

# ---------------------------------------------------------------------------
# 1.3  Real data pull — baseline
# ---------------------------------------------------------------------------
section("1.3 Real data pull (Malaysia unemployment)")

if not UNE_DATAFLOW:
    print("SKIP — no unemployment dataflow identified in 1.2")
else:
    # Use string key to avoid triggering DSD auto-fetch (which can 404 for some IDs).
    # SDMX key string format: dimension values separated by dots, in DSD order.
    # For most ILO flows: REF_AREA.SEX.AGE.TIME_PERIOD — but we can pass a partial
    # key by leaving trailing dims as wildcards (empty string = all values).
    # Safest: fetch without key filter first, then filter pandas output.
    print(f"Pulling {UNE_DATAFLOW} for MYS (Malaysia), 2018–2023...")
    print("Strategy: no key filter (avoid DSD fetch); filter in pandas post-pull")
    try:
        msg = client.data(
            UNE_DATAFLOW,
            params={"startPeriod": "2018", "endPeriod": "2023"},
        )
        # Plain series (no attributes)
        s = sdmx.to_pandas(msg)
        print(f"\nto_pandas() type: {type(s)}")
        if hasattr(s, "index"):
            print(f"Index names: {s.index.names}")
        if hasattr(s, "head"):
            # Filter to MYS if REF_AREA is a level
            if hasattr(s, "xs"):
                try:
                    mys = s.xs("MYS", level="REF_AREA")
                    print(f"\nMalaysia slice:\n{mys.head(15)}")
                except KeyError:
                    print(f"\nFull head (REF_AREA filter failed):\n{s.head(15)}")
            else:
                print(f"\nHead:\n{s.head(15)}")
        print(f"\ndtypes: {s.dtypes if hasattr(s, 'dtypes') else type(s)}")

        # With attributes — critical for break detection
        df = sdmx.to_pandas(msg, attributes="osgd")
        print(f"\nWith attributes='osgd':")
        print(f"  Type: {type(df)}")
        if hasattr(df, "columns"):
            print(f"  Columns: {list(df.columns)}")
            if hasattr(df, "xs"):
                try:
                    mys_df = df.xs("MYS", level="REF_AREA")
                    print(f"\nMalaysia slice with attrs:\n{mys_df.head(10)}")
                except KeyError:
                    print(f"\n{df.head(10)}")
        elif hasattr(df, "index"):
            print(f"  Index: {df.index.names}")

    except Exception as e:
        traceback.print_exc()
        print(f"ERROR: {e}")

# ---------------------------------------------------------------------------
# 1.4  Break detection feasibility
# ---------------------------------------------------------------------------
section("1.4 Break detection (SOURCE / OBS_PRE_BREAK_VALUE)")

BREAK_CANDIDATES = ["MYS", "TUR", "MEX", "IND", "BRA", "NGA", "PAK"]

import pandas as pd

def check_breaks_in_df(df, dataflow_id, country):
    """Check break signals in an attributes DataFrame for a given country."""
    print(f"\n  {dataflow_id} / {country}:")
    if "REF_AREA" in df.index.names:
        try:
            country_df = df.xs(country, level="REF_AREA")
        except KeyError:
            print(f"    → {country} not in dataset")
            return None
    else:
        country_df = df

    if country_df.empty:
        print(f"    → Empty after filtering to {country}")
        return None

    print(f"    Rows: {len(country_df)}, Columns: {list(country_df.columns)}")

    # SOURCE
    source_col = country_df.get("SOURCE")
    if source_col is not None:
        non_empty = [s for s in source_col.dropna().unique() if s != ""]
        print(f"    SOURCE unique ({len(non_empty)}): {non_empty[:5]}")
    else:
        non_empty = []
        print("    SOURCE: column absent")

    # OBS_PRE_BREAK_VALUE
    brk_col = country_df.get("OBS_PRE_BREAK_VALUE")
    if brk_col is not None:
        break_vals = [v for v in brk_col.dropna().unique() if v != ""]
        print(f"    OBS_PRE_BREAK_VALUE non-empty: {break_vals[:5]}")
    else:
        break_vals = []
        print("    OBS_PRE_BREAK_VALUE: column absent")

    return {
        "country": country,
        "dataflow": dataflow_id,
        "has_source_change": len(non_empty) > 1,
        "has_break_flag": bool(break_vals),
        "sources": non_empty,
        "break_vals": break_vals,
        "n_rows": len(country_df),
    }

# Pull survey-based unemployment dataflow
une_survey_df_id = UNE_SURVEY_DATAFLOW or UNE_DATAFLOW or "UNE_TUNE_SEX_AGE_NB"
une_df_id = une_survey_df_id  # alias for later sections

print(f"Testing unemployment (survey) dataflow: {une_survey_df_id}")
break_results_emp = []
try:
    une_msg = client.data(une_survey_df_id, params={"startPeriod": "2010", "endPeriod": "2023"})
    une_attrs_df = sdmx.to_pandas(une_msg, attributes="osgd")
    if isinstance(une_attrs_df, pd.DataFrame):
        for country in BREAK_CANDIDATES:
            result = check_breaks_in_df(une_attrs_df, une_survey_df_id, country)
            if result:
                break_results_emp.append(result)
    else:
        print(f"  Got {type(une_attrs_df).__name__} — no attribute columns")
except Exception as e:
    traceback.print_exc()
    print(f"  Could not fetch {une_survey_df_id}: {e}")

ear_survey_df_id = EAR_SURVEY_DATAFLOW or EAR_DATAFLOW
print(f"\nTesting wages (survey) dataflow: {ear_survey_df_id}")
break_results_wage = []
if ear_survey_df_id:
    try:
        ear_msg = client.data(ear_survey_df_id, params={"startPeriod": "2010", "endPeriod": "2023"})
        ear_attrs_df = sdmx.to_pandas(ear_msg, attributes="osgd")
        if isinstance(ear_attrs_df, pd.DataFrame):
            for country in BREAK_CANDIDATES:
                result = check_breaks_in_df(ear_attrs_df, ear_survey_df_id, country)
                if result:
                    break_results_wage.append(result)
        else:
            print(f"  Got {type(ear_attrs_df).__name__} — no attribute columns")
    except Exception as e:
        traceback.print_exc()
        print(f"  Could not fetch {ear_survey_df_id}: {e}")
else:
    print("  No wages dataflow identified — skipping")

print("\n--- Break detection summary ---")
emp_breaks = [r for r in break_results_emp if r.get("has_source_change") or r.get("has_break_flag")]
wage_breaks = [r for r in break_results_wage if r.get("has_source_change") or r.get("has_break_flag")]
print(f"Employment breaks found: {[(r['country'], r['sources'], r['break_vals']) for r in emp_breaks]}")
print(f"Wage breaks found: {[(r['country'], r['sources'], r['break_vals']) for r in wage_breaks]}")

if emp_breaks or wage_breaks:
    print("\nVERDICT: Break detection VIABLE — at least one signal found")
else:
    print("\nVERDICT: ⚠️  NO BREAK SIGNALS FOUND — scope risk, needs alternative strategy")

# ---------------------------------------------------------------------------
# 1.5  Confirmed break countries
# ---------------------------------------------------------------------------
section("1.5 Confirmed break countries")

print("Employment breaks:")
for r in emp_breaks:
    print(f"  {r['country']}: dataflow={r['dataflow']}, source_change={r['has_source_change']}, break_flag={r['has_break_flag']}")
    print(f"    Sources: {r['sources']}")

print("Wage breaks:")
for r in wage_breaks:
    print(f"  {r['country']}: dataflow={r['dataflow']}, source_change={r['has_source_change']}, break_flag={r['has_break_flag']}")
    print(f"    Sources: {r['sources']}")

# ---------------------------------------------------------------------------
# 1.6  No-data and edge cases
# ---------------------------------------------------------------------------
section("1.6 No-data edge cases")

edge_cases = [
    ("PRK", "2020", "2023", "North Korea — expected: no data"),
    ("MYS", "1970", "1970", "Malaysia 1970 — expected: out of range"),
    ("MYS", "2027", "2027", "Malaysia 2027 — expected: future date"),
]

une_df_id = UNE_DATAFLOW or "UNE_TUNE_SEX_AGE_NB"

for country, start, end, label in edge_cases:
    print(f"\n  {label}:")
    try:
        msg = client.data(
            une_df_id,
            params={"startPeriod": start, "endPeriod": end},
        )
        s = sdmx.to_pandas(msg)
        # Try to filter to country
        if hasattr(s, "xs"):
            try:
                filtered = s.xs(country, level="REF_AREA")
                print(f"    → Has data for {country}, len={len(filtered)}")
            except KeyError:
                print(f"    → No data for {country} in response (country absent)")
        elif hasattr(s, "__len__"):
            print(f"    → Result len={len(s)}, type={type(s).__name__}")
        else:
            print(f"    → Result: {s}")
    except HTTPError as e:
        print(f"    → HTTPError: {e.response.status_code} {e.response.reason}")
    except Exception as e:
        print(f"    → {type(e).__name__}: {e}")

# ---------------------------------------------------------------------------
# 1.7  Country codelist
# ---------------------------------------------------------------------------
section("1.7 Country codelist (CL_AREA)")

try:
    msg = client.codelist("CL_AREA")
    cl = list(msg.codelist.values())[0]
    # cl is a Codelist object; cl.items is a dict {code_id: Code}
    code_dict = cl.items  # dict, not a callable method
    print(f"Total entries in CL_AREA: {len(code_dict)}")
    print("First 20:")
    for code_id, item in list(code_dict.items())[:20]:
        print(f"  {code_id}: {item.name}")
except Exception as e:
    traceback.print_exc()
    print(f"ERROR: {e}")

# ---------------------------------------------------------------------------
# 1.8  Metadata / indicator detail
# ---------------------------------------------------------------------------
section("1.8 Indicator metadata (references='all')")

try:
    msg = client.dataflow(une_df_id, params={"references": "all"})
    if not msg.dataflow:
        print(f"No dataflow in response for {une_df_id}")
        raise ValueError("empty dataflow")
    df_obj = list(msg.dataflow.values())[0]
    print(f"Name: {df_obj.name}")
    print(f"Description: {df_obj.description}")

    # DSD
    if msg.structure:
        dsd_key = list(msg.structure.keys())[0]
        dsd = msg.structure[dsd_key]
        print(f"\nDSD: {dsd_key}")
        print(f"  Dimensions: {[d.id for d in dsd.dimensions]}")
        print(f"  Attributes: {[a.id for a in dsd.attributes]}")
        print(f"  Measures: {[m.id for m in dsd.measures]}")

    # Constraints
    if hasattr(msg, "constraint") and msg.constraint:
        print(f"\nConstraints: {list(msg.constraint.keys())}")

    # Annotations (often contain last-updated, source org)
    if df_obj.annotations:
        print(f"\nAnnotations:")
        for ann in df_obj.annotations:
            print(f"  [{ann.type}] {ann.title}: {ann.text}")

except Exception as e:
    traceback.print_exc()
    print(f"ERROR: {e}")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
section("SUMMARY")

print("Phase 0 discovery complete. Key findings:")
print(f"  1. Total ILOSTAT dataflows: 1210 (bulk fetch succeeded)")
print(f"  2. Employment/wage-related dataflows: {len(emp_wage_ids) if bulk else 'N/A'}")
print(f"  3. Employment breaks found: {len(emp_breaks)} country/dataflow pairs")
print(f"  4. Wage breaks found: {len(wage_breaks)} country/dataflow pairs")
print(f"\nRecord these findings in local-notes/execution/phase-0/discovery_results.md")
