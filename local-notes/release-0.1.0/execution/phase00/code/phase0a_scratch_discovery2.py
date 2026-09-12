"""
Phase 0 Discovery Script #2
Run with: uv run --with sdmx1 python local-notes/execution/phase-0/scratch_discovery_2.py

Covers:
  A. Country filtering — can we filter server-side without triggering DSD auto-fetch?
  B. Dimension defaults — exact codes for SEX=total, AGE=total
  C. NOTE_SOURCE attribute content — does it explain breaks in plain text?
  D. Wage break country — find a country where the wage survey changed mid-series
"""

import traceback
import time
import pandas as pd
import sdmx
from requests.exceptions import HTTPError

SEP = "\n" + "=" * 70 + "\n"

def section(title):
    print(SEP + f"[{title}]")

client = sdmx.Client("ILO")

# We know from discovery #1 that the main dataflows to use are:
UNE_MODELLED  = "DF_UNE_2EAP_SEX_AGE_RT"   # ILO modelled estimates — broadest coverage
UNE_SURVEY    = "DF_UNE_DEAP_SEX_AGE_RT"   # national survey unemployment rate (DEAP = survey)
EAR_HOURLY    = "DF_EAR_CHRA_SEX_CUR_NB"   # hourly earnings (tested in discovery #1)
EAR_MONTHLY   = "DF_EAR_CMTA_SEX_CUR_NB"   # monthly earnings
EAR_EMPLOYEE  = "DF_EAR_EHRA_SEX_ECO_CUR_NB"  # hourly earnings by economic activity

# ---------------------------------------------------------------------------
# A. Country filtering — string key vs. no-filter
# ---------------------------------------------------------------------------
section("A. Country filtering performance")

# Strategy 1: no key filter — pull everything, slice in pandas
print("Strategy 1: no key filter, pull all countries")
t0 = time.time()
try:
    msg = client.data(UNE_MODELLED, params={"startPeriod": "2022", "endPeriod": "2022"})
    s = sdmx.to_pandas(msg)
    t1 = time.time()
    print(f"  Time: {t1-t0:.1f}s")
    print(f"  Total rows: {len(s)}")
    if "REF_AREA" in s.index.names:
        n_countries = s.index.get_level_values("REF_AREA").nunique()
        print(f"  Countries in response: {n_countries}")
        mys = s.xs("MYS", level="REF_AREA")
        print(f"  Malaysia rows: {len(mys)}")
        print(f"  Malaysia values:\n{mys.head(6)}")
except Exception as e:
    traceback.print_exc()

# Strategy 2: string key — pass REF_AREA as the first key position
# SDMX key string format: value1.value2.value3... in dimension order
# Dimensions for UNE_MODELLED: [REF_AREA, FREQ, MEASURE, SEX, AGE, TIME_PERIOD]
# So REF_AREA-only string key: "MYS" (just first dim, rest wildcarded)
print("\nStrategy 2: string key 'MYS' (REF_AREA only, rest wildcard)")
t0 = time.time()
try:
    msg2 = client.data(
        UNE_MODELLED,
        key="MYS",
        params={"startPeriod": "2022", "endPeriod": "2022"},
    )
    s2 = sdmx.to_pandas(msg2)
    t1 = time.time()
    print(f"  Time: {t1-t0:.1f}s")
    print(f"  Rows returned: {len(s2)}")
    print(f"  Values:\n{s2.head(6)}")
except Exception as e:
    print(f"  ERROR: {e}")

# Strategy 3: dict key with known DSD (pass dsd= explicitly to skip auto-fetch)
print("\nStrategy 3: dict key with explicit dsd=False (skip validation)")
t0 = time.time()
try:
    # Try passing dsd=False or similar to skip DSD fetch
    msg3 = client.data(
        UNE_MODELLED,
        key={"REF_AREA": "MYS"},
        params={"startPeriod": "2022", "endPeriod": "2022"},
        dsd=False,
    )
    s3 = sdmx.to_pandas(msg3)
    t1 = time.time()
    print(f"  Time: {t1-t0:.1f}s  Rows: {len(s3)}")
except TypeError as e:
    print(f"  dsd= not a valid param: {e}")
except Exception as e:
    print(f"  ERROR: {e}")

# Strategy 4: fetch with params filter (some SDMX endpoints support query params)
print("\nStrategy 4: URL-level filter via params key= ")
t0 = time.time()
try:
    msg4 = client.data(
        UNE_MODELLED,
        params={"startPeriod": "2022", "endPeriod": "2022", "REF_AREA": "MYS"},
    )
    s4 = sdmx.to_pandas(msg4)
    t1 = time.time()
    print(f"  Time: {t1-t0:.1f}s  Rows: {len(s4)}")
except Exception as e:
    print(f"  ERROR: {e}")

# ---------------------------------------------------------------------------
# B. Dimension defaults — exact codes for totals
# ---------------------------------------------------------------------------
section("B. Dimension defaults (SEX=total, AGE=total)")

print("Pulling Malaysia 2022 from modelled flow to inspect dimension values...")
try:
    msg = client.data(UNE_MODELLED, params={"startPeriod": "2022", "endPeriod": "2022"})
    s = sdmx.to_pandas(msg)
    mys = s.xs("MYS", level="REF_AREA")

    # Print all unique values for each dimension
    for dim in mys.index.names:
        vals = mys.index.get_level_values(dim).unique().tolist()
        print(f"  {dim}: {vals}")

    print("\nFull Malaysia 2022 slice:")
    print(mys.to_string())

except Exception as e:
    traceback.print_exc()

# Also check the survey flow (may have different dimension values)
print("\nChecking survey flow dimension values (DF_UNE_DEAP_SEX_AGE_RT)...")
try:
    msg_s = client.data(UNE_SURVEY, params={"startPeriod": "2020", "endPeriod": "2022"})
    s_s = sdmx.to_pandas(msg_s)
    # Pick any country that has data
    areas = s_s.index.get_level_values("REF_AREA").unique()[:3]
    print(f"  Countries with data: {list(areas)} (showing first 3)")
    sample = s_s.xs(areas[0], level="REF_AREA")
    for dim in sample.index.names:
        vals = sample.index.get_level_values(dim).unique().tolist()
        print(f"  {dim}: {vals}")
except Exception as e:
    print(f"  ERROR: {e}")

# ---------------------------------------------------------------------------
# C. NOTE_SOURCE content
# ---------------------------------------------------------------------------
section("C. NOTE_SOURCE attribute content")

# Pull a dataflow known to have NOTE_SOURCE (the disability flow had it)
FLOW_WITH_NOTE = "DF_UNE_3EAP_SEX_AGE_DSB_RT"

print(f"Pulling {FLOW_WITH_NOTE} for NGA (Nigeria) to inspect NOTE_SOURCE...")
try:
    msg = client.data(FLOW_WITH_NOTE, params={"startPeriod": "2010", "endPeriod": "2023"})
    df = sdmx.to_pandas(msg, attributes="osgd")

    if "REF_AREA" in df.index.names:
        nga = df.xs("NGA", level="REF_AREA")
    else:
        nga = df

    print(f"  Columns: {list(nga.columns)}")

    # Print NOTE_SOURCE for all rows where SOURCE changes
    if "NOTE_SOURCE" in nga.columns and "SOURCE" in nga.columns:
        cols = ["value", "SOURCE", "NOTE_SOURCE"]
        subset = nga[cols].drop_duplicates(subset=["SOURCE", "NOTE_SOURCE"])
        print("\n  Unique SOURCE + NOTE_SOURCE combinations:")
        for _, row in subset.iterrows():
            print(f"\n    SOURCE: {row['SOURCE']}")
            print(f"    NOTE_SOURCE: {row['NOTE_SOURCE'][:300] if row['NOTE_SOURCE'] else '(empty)'}")
    elif "SOURCE" in nga.columns:
        print("  NOTE_SOURCE column absent. SOURCE values:")
        print(nga["SOURCE"].unique())
    else:
        print("  Neither SOURCE nor NOTE_SOURCE found")

except Exception as e:
    traceback.print_exc()

# ---------------------------------------------------------------------------
# D. Wage break country
# ---------------------------------------------------------------------------
section("D. Wage break country search")

# Try more countries and more EAR dataflows
WAGE_FLOWS = [
    "DF_EAR_CMTA_SEX_CUR_NB",       # monthly earnings by sex and currency
    "DF_EAR_EHRA_SEX_ECO_CUR_NB",   # hourly earnings by sex and economic activity
    "DF_EAR_EHRA_SEX_CUR_NB",       # hourly earnings by sex
]
WAGE_COUNTRIES = [
    "THA", "VNM", "ARG", "CHL", "TUR", "IDN", "PHL",
    "ZAF", "KEN", "GHA", "ETH", "MAR", "EGY", "COL", "PER",
]

def check_source_changes(dataflow_id, countries, start="2005", end="2023"):
    """Pull a dataflow and find countries with multiple SOURCE values."""
    print(f"\nDataflow: {dataflow_id}")
    try:
        msg = client.data(dataflow_id, params={"startPeriod": start, "endPeriod": end})
        df = sdmx.to_pandas(msg, attributes="osgd")
        if not isinstance(df, pd.DataFrame) or "SOURCE" not in df.columns:
            print("  No SOURCE column")
            return []

        found = []
        if "REF_AREA" not in df.index.names:
            print("  No REF_AREA in index — can't filter by country")
            return []

        available = set(df.index.get_level_values("REF_AREA").unique())
        for country in countries:
            if country not in available:
                continue
            try:
                country_df = df.xs(country, level="REF_AREA")
                sources = [s for s in country_df["SOURCE"].unique() if s != ""]
                if len(sources) > 1:
                    print(f"  ✓ {country}: {sources}")
                    found.append({"country": country, "dataflow": dataflow_id, "sources": sources})
            except KeyError:
                pass

        if not found:
            print(f"  No wage breaks in {len([c for c in countries if c in available])} countries checked")
        return found

    except Exception as e:
        print(f"  ERROR fetching: {e}")
        return []

wage_breaks = []
for flow in WAGE_FLOWS:
    results = check_source_changes(flow, WAGE_COUNTRIES)
    wage_breaks.extend(results)

print(f"\n--- Wage break summary ---")
if wage_breaks:
    for r in wage_breaks:
        print(f"  FOUND: {r['country']} in {r['dataflow']}")
        print(f"    Sources: {r['sources']}")
else:
    print("  No wage breaks found in expanded search.")
    print("  Try: fetch ALL countries for one flow and scan globally.")

    # Last resort: scan all countries in one flow for any multi-source country
    print("\nGlobal scan: DF_EAR_CMTA_SEX_CUR_NB (all countries, 2000–2023)...")
    try:
        msg = client.data("DF_EAR_CMTA_SEX_CUR_NB", params={"startPeriod": "2000", "endPeriod": "2023"})
        df = sdmx.to_pandas(msg, attributes="osgd")
        if isinstance(df, pd.DataFrame) and "SOURCE" in df.columns and "REF_AREA" in df.index.names:
            multi_source = []
            for country in df.index.get_level_values("REF_AREA").unique():
                try:
                    cdf = df.xs(country, level="REF_AREA")
                    sources = [s for s in cdf["SOURCE"].unique() if s != ""]
                    if len(sources) > 1:
                        multi_source.append((country, sources))
                except KeyError:
                    pass
            if multi_source:
                print(f"  Found {len(multi_source)} countries with wage SOURCE changes:")
                for c, s in multi_source[:10]:
                    print(f"    {c}: {s}")
            else:
                print("  No wage SOURCE changes found globally in this dataflow.")
    except Exception as e:
        print(f"  ERROR: {e}")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
section("SUMMARY")
print("A. Country filtering: check which strategy was fastest / worked")
print("B. Dimension codes: recorded above")
print("C. NOTE_SOURCE: check if it has useful break narrative text")
print(f"D. Wage breaks: {'FOUND' if wage_breaks else 'NOT FOUND — see notes above'}")
