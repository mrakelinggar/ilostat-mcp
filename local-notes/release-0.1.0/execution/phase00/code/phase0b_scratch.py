"""
Phase 0b — Remaining data discoveries.
Run: uv run --with sdmx1 python local-notes/execution/phase00/scratch_phase0b.py
"""

import traceback
import sdmx
import pandas as pd
from requests.exceptions import HTTPError

SEP = "=" * 65

def section(title):
    print(f"\n{SEP}\n  {title}\n{SEP}")

def pull(client, dataflow_id, country=None, start=None, end=None):
    """Pull data for a single country with optional date range. Returns attrs DataFrame."""
    params = {}
    if start:
        params["startPeriod"] = str(start)
    if end:
        params["endPeriod"] = str(end)
    key = {"REF_AREA": country} if country else {}
    msg = client.data(dataflow_id, key=key, params={**params, "detail": "full"}, dsd=False)
    return sdmx.to_pandas(msg, attributes="osgd")

def source_changes(df, country=None):
    """
    Find years where SOURCE attribute changes.
    Returns list of (year, old_source, new_source) tuples.
    """
    if country and "REF_AREA" in df.index.names:
        try:
            df = df.xs(country, level="REF_AREA")
        except KeyError:
            return None, []

    if df is None or df.empty:
        return df, []

    # Keep only annual frequency rows if FREQ is in index
    if "FREQ" in df.index.names:
        try:
            df = df.xs("A", level="FREQ")
        except KeyError:
            pass

    # Collapse to total sex / working-age where possible
    for level, val in [("SEX", "SEX_T"), ("AGE", "AGE_YTHADULT_YGE15")]:
        if level in df.index.names:
            try:
                df = df.xs(val, level=level)
            except KeyError:
                pass

    if "SOURCE" not in df.columns:
        return df, []

    src = df["SOURCE"].replace("", pd.NA).dropna()
    changes = []
    prev_src = None
    prev_year = None
    for year, source in sorted(src.items()):
        year_val = year[-1] if isinstance(year, tuple) else year
        if prev_src is not None and source != prev_src:
            changes.append((str(year_val), prev_src, source))
        prev_src = source
        prev_year = year_val

    return df, changes

client = sdmx.Client("ILO")

# Pre-load catalog once
catalog_msg = client.dataflow()
all_ids = list(catalog_msg.dataflow.keys())
print(f"Catalog loaded: {len(all_ids)} dataflows")


# ============================================================
# A1. Nigeria break years (q003, q018)
# ============================================================
section("A1. Nigeria break years — q003 / q018")

NGA_EMP_FLOW = "DF_UNE_3EAP_SEX_AGE_DSB_RT"
try:
    df, changes = source_changes(pull(client, NGA_EMP_FLOW, "NGA", 2010, 2023), None)
    if changes:
        print(f"SOURCE changes in {NGA_EMP_FLOW} for NGA:")
        for year, old, new in changes:
            print(f"  {year}: '{old}' → '{new}'")
        break_years = [c[0] for c in changes]
        print(f"Break years to record in q003/q018: {break_years}")
    else:
        print("No SOURCE changes found — check dataflow or country")
        # Try the main survey unemployment flow
        ALT_FLOW = "DF_UNE_DEAP_SEX_AGE_RT"
        df2, changes2 = source_changes(pull(client, ALT_FLOW, "NGA", 2010, 2023), None)
        if changes2:
            print(f"\nFound in {ALT_FLOW}:")
            for year, old, new in changes2:
                print(f"  {year}: '{old}' → '{new}'")
except Exception as e:
    traceback.print_exc()


# ============================================================
# A2. Thailand wage break years (q020)
# ============================================================
section("A2. Thailand wage break years — q020")

THA_WAGE_FLOW = "DF_EAR_CMTA_SEX_CUR_NB"
try:
    df, changes = source_changes(pull(client, THA_WAGE_FLOW, "THA", 2010, 2023), None)
    if changes:
        print(f"SOURCE changes in {THA_WAGE_FLOW} for THA:")
        for year, old, new in changes:
            print(f"  {year}: '{old}' → '{new}'")
        print(f"Break years to record in q020: {[c[0] for c in changes]}")
    else:
        print("No SOURCE changes found")
except Exception as e:
    traceback.print_exc()


# ============================================================
# A3. Thailand employment break check (q017 — currently answerable_clean)
# ============================================================
section("A3. Thailand employment break check — q017")

# Try the main survey unemployment flows for THA
UNE_SURVEY_FLOWS = [
    "DF_UNE_DEAP_SEX_AGE_RT",
    "DF_UNE_TUNE_SEX_AGE_NB",
]
tha_emp_break = False
for flow in UNE_SURVEY_FLOWS:
    try:
        df, changes = source_changes(pull(client, flow, "THA", 2015, 2022), None)
        if changes:
            print(f"Break found in {flow} for THA:")
            for year, old, new in changes:
                print(f"  {year}: '{old}' → '{new}'")
            tha_emp_break = True
        else:
            src_vals = []
            if df is not None and not df.empty and "SOURCE" in df.columns:
                src_vals = [s for s in df["SOURCE"].unique() if s]
            print(f"{flow}: no break. Unique SOURCE values: {src_vals}")
    except HTTPError as e:
        print(f"{flow}: HTTPError {e.response.status_code}")
    except Exception as e:
        print(f"{flow}: {type(e).__name__}: {e}")

print(f"\nVERDICT: q017 → {'answerable_break (recategorise)' if tha_emp_break else 'stays answerable_clean'}")


# ============================================================
# A4. Vietnam wage coverage for q029
# ============================================================
section("A4. Vietnam wage coverage — q029")

try:
    df, changes = source_changes(pull(client, THA_WAGE_FLOW, "VNM", 2018, 2022), None)
    if df is not None and not df.empty:
        years = sorted(set(
            str(idx[-1] if isinstance(idx, tuple) else idx)
            for idx in df.index
        ))
        print(f"VNM has wage data in {THA_WAGE_FLOW}: years available = {years}")
        if changes:
            print(f"VNM also has SOURCE changes: {changes}")
    else:
        print(f"VNM: no data in {THA_WAGE_FLOW} for 2018-2022")
        # Try other EAR flows
        ear_flows = [i for i in all_ids if "EAR_" in i and "_2" not in i.split("_")[2:3][0:1]]
        print(f"Trying other EAR flows for VNM...")
        for flow in ear_flows[:5]:
            try:
                df2, _ = source_changes(pull(client, flow, "VNM", 2018, 2022), None)
                if df2 is not None and not df2.empty:
                    print(f"  Found data in {flow}")
                    break
            except Exception:
                pass
        else:
            print("  No EAR flow found for VNM 2018–2022")
except Exception as e:
    traceback.print_exc()


# ============================================================
# A5. 2023 data availability: MYS and SGP (q011)
# ============================================================
section("A5. 2023 data availability — q011 (MYS vs SGP)")

UNE_FLOW = "DF_UNE_DEAP_SEX_AGE_RT"
for country in ["MYS", "SGP"]:
    try:
        df, _ = source_changes(pull(client, UNE_FLOW, country, 2020, 2024), None)
        if df is not None and not df.empty:
            years = sorted(set(
                str(idx[-1] if isinstance(idx, tuple) else idx)
                for idx in df.index
            ))
            print(f"{country}: latest available year = {max(years)}  (all: {years})")
        else:
            print(f"{country}: no data returned")
    except HTTPError as e:
        print(f"{country}: HTTPError {e.response.status_code}")
    except Exception as e:
        print(f"{country}: {type(e).__name__}: {e}")


# ============================================================
# A6. Data availability for ambiguous questions
# ============================================================
section("A6. Ambiguous question data coverage — q009, q027, q028")

# q009: Georgia wages
print("\nq009 — Georgia (GEO) wages:")
try:
    df, _ = source_changes(pull(client, THA_WAGE_FLOW, "GEO", 2018, 2023), None)
    if df is not None and not df.empty:
        years = sorted(set(str(idx[-1] if isinstance(idx, tuple) else idx) for idx in df.index))
        print(f"  GEO has wage data: {years}")
    else:
        print("  GEO: no wage data in primary EAR flow")
        # Try other EAR flows
        ear_flows = [i for i in all_ids if "EAR_" in i]
        found = False
        for flow in ear_flows[:10]:
            try:
                df2, _ = source_changes(pull(client, flow, "GEO", 2015, 2023), None)
                if df2 is not None and not df2.empty:
                    print(f"  Found in {flow}")
                    found = True
                    break
            except Exception:
                pass
        if not found:
            print("  No wage data found for GEO in any EAR flow")
except Exception as e:
    print(f"  Error: {e}")

# q027: Congo (COG and COD) unemployment
print("\nq027 — Congo unemployment (COG and COD):")
for country in ["COG", "COD"]:
    try:
        df, _ = source_changes(pull(client, UNE_FLOW, country, 2019, 2023), None)
        if df is not None and not df.empty:
            years = sorted(set(str(idx[-1] if isinstance(idx, tuple) else idx) for idx in df.index))
            print(f"  {country}: has unemployment data: {years}")
        else:
            print(f"  {country}: no unemployment data")
    except HTTPError as e:
        print(f"  {country}: HTTPError {e.response.status_code}")
    except Exception as e:
        print(f"  {country}: {type(e).__name__}: {e}")

# q028: Guinea wages (GIN, GNQ, GNB)
print("\nq028 — Guinea wages (GIN, GNQ, GNB):")
for country in ["GIN", "GNQ", "GNB"]:
    try:
        df, _ = source_changes(pull(client, THA_WAGE_FLOW, country, 2015, 2023), None)
        if df is not None and not df.empty:
            years = sorted(set(str(idx[-1] if isinstance(idx, tuple) else idx) for idx in df.index))
            print(f"  {country}: has wage data: {years}")
        else:
            print(f"  {country}: no wage data in primary EAR flow")
    except HTTPError as e:
        print(f"  {country}: HTTPError {e.response.status_code}")
    except Exception as e:
        print(f"  {country}: {type(e).__name__}: {e}")


# ============================================================
# B1. Employment-to-population dataflow (q013)
# ============================================================
section("B1. Employment-to-population dataflow — q013 (DEU 2019)")

emp_pop_flows = [i for i in all_ids if "EMP_" in i and ("DWAP" in i or "EPOP" in i or "WAP" in i)]
print(f"Candidate emp-to-pop flows: {emp_pop_flows[:10]}")

found_flow = None
for flow in emp_pop_flows[:5]:
    try:
        df, _ = source_changes(pull(client, flow, "DEU", 2019, 2019), None)
        if df is not None and not df.empty:
            print(f"\n{flow}: DEU 2019 — has data")
            print(f"  Sample: {df.head(3)}")
            found_flow = flow
            break
        else:
            print(f"{flow}: no data for DEU 2019")
    except HTTPError as e:
        print(f"{flow}: HTTPError {e.response.status_code}")
    except Exception as e:
        print(f"{flow}: {type(e).__name__}: {e}")

print(f"\nDataflow ID to lock for q013: {found_flow or 'NOT FOUND — check catalog manually'}")


# ============================================================
# B2. Youth unemployment dataflow + AGE code (q016)
# ============================================================
section("B2. Youth unemployment dataflow + AGE code — q016 (ZAF 2021)")

youth_flows = [i for i in all_ids if "UNE_" in i and ("YTH" in i or "Y15" in i or "YOUTH" in i.upper())]
print(f"Candidate youth unemployment flows: {youth_flows[:10]}")

# Also search titles for "youth"
youth_title_flows = [
    i for i in all_ids
    if "youth" in str(catalog_msg.dataflow[i].name).lower()
    and "UNE_" in i
]
print(f"Flows with 'youth' in title: {youth_title_flows[:10]}")

all_youth = list(set(youth_flows + youth_title_flows))
found_youth_flow = None
found_age_code = None

for flow in all_youth[:5]:
    try:
        df, _ = source_changes(pull(client, flow, "ZAF", 2021, 2021), None)
        if df is not None and not df.empty:
            print(f"\n{flow}: ZAF 2021 — has data")
            if "AGE" in df.index.names:
                age_codes = df.index.get_level_values("AGE").unique().tolist()
                print(f"  AGE codes present: {age_codes}")
                found_age_code = age_codes[0] if age_codes else None
            found_youth_flow = flow
            break
        else:
            print(f"{flow}: no data for ZAF 2021")
    except HTTPError as e:
        print(f"{flow}: HTTPError {e.response.status_code}")
    except Exception as e:
        print(f"{flow}: {type(e).__name__}: {e}")

print(f"\nDataflow to lock for q016: {found_youth_flow or 'NOT FOUND'}")
print(f"AGE code for youth: {found_age_code or 'NOT FOUND'}")


# ============================================================
# B3. Pakistan employment break within 2010–2020 (q019)
# ============================================================
section("B3. Pakistan employment break in 2010–2020 — q019")

for flow in [UNE_FLOW, "DF_UNE_3EAP_SEX_AGE_DSB_RT"]:
    try:
        df, changes = source_changes(pull(client, flow, "PAK", 2010, 2020), None)
        if changes:
            print(f"Break found in {flow} for PAK within 2010–2020:")
            for year, old, new in changes:
                print(f"  {year}: '{old}' → '{new}'")
        else:
            src_vals = []
            if df is not None and not df.empty and "SOURCE" in df.columns:
                src_vals = list({s for s in df["SOURCE"].unique() if s})
            print(f"{flow}: no break in 2010–2020. Sources: {src_vals}")
    except HTTPError as e:
        print(f"{flow}: HTTPError {e.response.status_code}")
    except Exception as e:
        print(f"{flow}: {type(e).__name__}: {e}")


# ============================================================
# B4. Pakistan wage break (q004)
# ============================================================
section("B4. Pakistan wage break — q004")

ear_flows = [i for i in all_ids if "EAR_" in i and "2EAR" not in i]
print(f"Survey EAR flows to check ({len(ear_flows)}): {ear_flows[:8]}")

pak_wage_break = None
for flow in ear_flows[:8]:
    try:
        df, changes = source_changes(pull(client, flow, "PAK", 2010, 2023), None)
        if changes:
            print(f"\nBreak found in {flow} for PAK:")
            for year, old, new in changes:
                print(f"  {year}: '{old}' → '{new}'")
            pak_wage_break = (flow, changes)
            break
        elif df is not None and not df.empty:
            print(f"{flow}: PAK has data but no break")
        else:
            print(f"{flow}: no PAK data")
    except HTTPError as e:
        print(f"{flow}: HTTPError {e.response.status_code}")
    except Exception as e:
        print(f"{flow}: {e}")

if not pak_wage_break:
    print("\nNo PAK wage break found — q004 country needs swapping")
    print("Confirmed wage break countries from Phase 0a: THA (DF_EAR_CMTA_SEX_CUR_NB)")


# ============================================================
# B5. Somalia coverage (q021)
# ============================================================
section("B5. Somalia (SOM) coverage — q021")

try:
    msg = client.data(UNE_FLOW, key={"REF_AREA": "SOM"},
                      params={"startPeriod": "2020", "endPeriod": "2023", "detail": "full"},
                      dsd=False)
    df = sdmx.to_pandas(msg, attributes="osgd")
    if df is not None and not df.empty:
        print(f"SOM: has data — {len(df)} rows")
        print(f"Sample:\n{df.head(5)}")
    else:
        print("SOM: empty response")
except HTTPError as e:
    print(f"SOM: HTTPError {e.response.status_code} — no data at all (clean 404)")
except Exception as e:
    print(f"SOM: {type(e).__name__}: {e}")

# Also check modelled estimates
MOD_FLOW = "DF_UNE_2EAP_SEX_AGE_RT"
try:
    msg2 = client.data(MOD_FLOW, key={"REF_AREA": "SOM"},
                       params={"startPeriod": "2023", "endPeriod": "2023", "detail": "full"},
                       dsd=False)
    df2 = sdmx.to_pandas(msg2, attributes="osgd")
    if df2 is not None and not df2.empty:
        print(f"SOM: modelled estimates DO exist in {MOD_FLOW}")
    else:
        print(f"SOM: no modelled estimates either")
except HTTPError as e:
    print(f"SOM modelled: HTTPError {e.response.status_code}")
except Exception as e:
    print(f"SOM modelled: {type(e).__name__}: {e}")


# ============================================================
# B6. EU aggregate in CL_AREA (q023)
# ============================================================
section("B6. EU aggregate in CL_AREA — q023")

try:
    cl_msg = client.codelist("CL_AREA")
    cl = list(cl_msg.codelist.values())[0]
    eu_entries = {
        code: str(item.name)
        for code, item in cl.items.items()
        if "european" in str(item.name).lower() or code.startswith("EU")
    }
    if eu_entries:
        print(f"EU-related entries in CL_AREA:")
        for code, name in eu_entries.items():
            print(f"  {code}: {name}")
        # Try pulling data for any EU code found
        for code in list(eu_entries.keys())[:2]:
            try:
                df, _ = source_changes(pull(client, UNE_FLOW, code, 2022, 2022), None)
                if df is not None and not df.empty:
                    print(f"  {code}: has unemployment data")
                else:
                    print(f"  {code}: no unemployment data")
            except Exception as e:
                print(f"  {code}: {type(e).__name__}: {e}")
    else:
        print("No EU aggregate code found in CL_AREA — q023 premise confirmed correct")
except Exception as e:
    traceback.print_exc()


# ============================================================
# B7. Canonical dataflow IDs for all answerable questions
# ============================================================
section("B7. Canonical dataflow IDs — all answerable questions")

# For each question: (question_id, country, year, theme, note)
checks = [
    ("q001", "MYS", 2022, 2022, "unemployment", UNE_FLOW),
    ("q002", "SGP", 2021, 2021, "wages",        THA_WAGE_FLOW),
    ("q010", "FRA", 2020, 2023, "wages",        THA_WAGE_FLOW),
    ("q010", "DEU", 2020, 2023, "wages",        THA_WAGE_FLOW),
    ("q011", "MYS", 2022, 2023, "unemployment", UNE_FLOW),
    ("q011", "SGP", 2022, 2023, "unemployment", UNE_FLOW),
    ("q014", "FRA", 2022, 2022, "wages",        THA_WAGE_FLOW),
    ("q015", "BRA", 2018, 2018, "unemployment", UNE_FLOW),
    ("q017", "THA", 2015, 2022, "unemployment", UNE_FLOW),
    ("q019", "PAK", 2010, 2020, "unemployment", UNE_FLOW),
    ("q030", "ESP", 2010, 2023, "unemployment", UNE_FLOW),
    ("q030", "ITA", 2010, 2023, "unemployment", UNE_FLOW),
]

results = {}
for qid, country, start, end, theme, flow in checks:
    try:
        df, _ = source_changes(pull(client, flow, country, start, end), None)
        has_data = df is not None and not df.empty
        if has_data:
            years = sorted(set(
                str(idx[-1] if isinstance(idx, tuple) else idx)
                for idx in df.index
            ))
            latest = max(years)
        else:
            years, latest = [], None
        status = f"OK  latest={latest}" if has_data else "NO DATA"
        print(f"  {qid} {country} {start}-{end} [{theme}]: {status}")
        results[f"{qid}_{country}"] = {"flow": flow, "has_data": has_data, "years": years}
    except HTTPError as e:
        print(f"  {qid} {country}: HTTPError {e.response.status_code}")
        results[f"{qid}_{country}"] = {"flow": flow, "has_data": False, "error": str(e.response.status_code)}
    except Exception as e:
        print(f"  {qid} {country}: {type(e).__name__}: {e}")
        results[f"{qid}_{country}"] = {"flow": flow, "has_data": False, "error": str(e)}


# ============================================================
# C1. MEASURE dimension cardinality
# ============================================================
section("C1. MEASURE dimension cardinality")

for flow in [UNE_FLOW, THA_WAGE_FLOW]:
    try:
        msg = client.dataflow(flow, params={"references": "all"})
        dsd_key = list(msg.structure.keys())[0]
        dsd = msg.structure[dsd_key]
        measures = [m.id for m in dsd.measures]
        print(f"{flow}: measures = {measures}")
    except Exception as e:
        print(f"{flow}: {type(e).__name__}: {e}")

    # Also check unique MEASURE values in a real data pull
    try:
        df, _ = source_changes(pull(client, flow, "MYS", 2020, 2022), None)
        if df is not None and "MEASURE" in df.index.names:
            measure_vals = df.index.get_level_values("MEASURE").unique().tolist()
            print(f"  {flow}: MEASURE values in data = {measure_vals}")
        else:
            print(f"  {flow}: MEASURE not in index")
    except Exception as e:
        print(f"  {flow}: data pull error: {e}")


print(f"\n{SEP}")
print("  ALL PHASE 0b CHECKS COMPLETE")
print(SEP)
