"""
Phase 0b gap checks — run all outstanding unknowns in one pass.

Checks:
  1. LCU currency labeling — how does the API communicate the actual currency?
  2. Wage break in canonical flow DF_EAR_EMTA_SEX_CUR_NB — find a country with SOURCE change
  3. PAK unemployment break — DF_UNE_DEAP_SEX_AGE_RT, 2008–2024
  4. PAK wage break — DF_EAR_EMTA_SEX_CUR_NB
  5. SOM coverage — 404 or real data in unemployment flow?
  6. EU aggregate — is there an EU/EU27 code in CL_AREA?
  7. MEASURE dimension — single value per flow or multiple?
"""

import sdmx
import cloudscraper
import pandas as pd

client = sdmx.Client("ILO")
client.session = cloudscraper.create_scraper()

SEP = "=" * 70

# ── helper ──────────────────────────────────────────────────────────────────

def pull(flow_id, country, key_extra, start, end, freq="A"):
    """Return annual-total DataFrame with attributes, or None on failure."""
    key = {"REF_AREA": country, **key_extra}
    try:
        resp = client.data(flow_id, key=key, params={"startPeriod": start, "endPeriod": end})
        df = sdmx.to_pandas(resp, attributes="o").reset_index()
        if df.empty:
            return None
        if "FREQ" in df.columns:
            df = df[df["FREQ"] == freq]
        return df if not df.empty else None
    except Exception as e:
        print(f"  ERROR ({country}): {e}")
        return None

def sources(df):
    """Return list of (TIME_PERIOD, SOURCE, OBS_STATUS) sorted by period."""
    cols = ["TIME_PERIOD", "value"]
    for c in ["SOURCE", "OBS_STATUS"]:
        if c in df.columns:
            cols.append(c)
    return df[cols].sort_values("TIME_PERIOD").to_string(index=False)

def has_break(df):
    """True if SOURCE changes between consecutive rows OR OBS_STATUS='B' exists."""
    if df is None or df.empty:
        return False
    df = df.sort_values("TIME_PERIOD").reset_index(drop=True)
    if "OBS_STATUS" in df.columns and (df["OBS_STATUS"] == "B").any():
        return True
    if "SOURCE" in df.columns:
        for i in range(1, len(df)):
            if df.loc[i, "SOURCE"] != df.loc[i-1, "SOURCE"]:
                return True
    return False


# ── CHECK 1: LCU currency labeling ──────────────────────────────────────────
print(f"\n{SEP}")
print("CHECK 1 — LCU currency labeling")
print("Goal: find what field tells us the actual currency (EUR, NGN, BRL...)")
print(SEP)

# 1a) Look at the raw SDMX dataset-level and series-level attributes
try:
    resp = client.data(
        "DF_EAR_EMTA_SEX_CUR_NB",
        key={"REF_AREA": "FRA", "SEX": "SEX_T", "CUR": "CUR_TYPE_LCU"},
        params={"startPeriod": "2022", "endPeriod": "2023"}
    )
    ds = resp.data[0]
    # Dataset-level attributes
    print(f"Dataset attribs: {dict(ds.attrib)}")
    # Series-level attributes
    for sk, sv in list(ds.series.items())[:2]:
        print(f"Series key: {dict(sk)}")
        print(f"Series attribs: {dict(sv.attrib)}")
        for i, obs in enumerate(sv):
            print(f"  obs attrib: {dict(obs.attrib)}")
            if i >= 1:
                break
except Exception as e:
    print(f"  ERROR: {e}")

# 1b) Check what CL_UNIT_MEASURE codelist looks like
print("\n--- CL_UNIT_MEASURE codelist (first 20 entries) ---")
try:
    cl_resp = client.codelist("CL_UNIT_MEASURE")
    if hasattr(cl_resp, "codelist"):
        cl = list(cl_resp.codelist.values())[0]
        for i, (code, item) in enumerate(cl.items()):
            print(f"  {code}: {item.name}")
            if i >= 19:
                print("  ...")
                break
except Exception as e:
    print(f"  ERROR: {e}")

# 1c) Check FRA vs NGA: are UNIT_MEASURE values different?
print("\n--- UNIT_MEASURE comparison: FRA vs NGA ---")
for country in ["FRA", "NGA", "BRA", "DEU"]:
    df = pull("DF_EAR_EMTA_SEX_CUR_NB", country,
              {"SEX": "SEX_T", "CUR": "CUR_TYPE_LCU"}, "2022", "2023")
    if df is not None and "UNIT_MEASURE" in df.columns:
        print(f"  {country}: UNIT_MEASURE={df['UNIT_MEASURE'].unique().tolist()}")
    else:
        print(f"  {country}: no data or no UNIT_MEASURE column")


# ── CHECK 2: Wage break in canonical flow ────────────────────────────────────
print(f"\n{SEP}")
print("CHECK 2 — Wage break in DF_EAR_EMTA_SEX_CUR_NB (canonical flow)")
print("Scanning: THA, NGA, BGD, EGY, IND, PAK, IDN, PHL, MEX")
print(SEP)

wage_break_countries = ["THA", "NGA", "BGD", "EGY", "IND", "PAK", "IDN", "PHL", "MEX"]
found_wage_break = []

for country in wage_break_countries:
    df = pull("DF_EAR_EMTA_SEX_CUR_NB", country,
              {"SEX": "SEX_T", "CUR": "CUR_TYPE_LCU"}, "2005", "2024")
    if df is None:
        print(f"  {country}: no data")
        continue
    if has_break(df):
        found_wage_break.append(country)
        print(f"  {country}: BREAK FOUND ✓")
        print(sources(df))
    else:
        srcs = df["SOURCE"].unique().tolist() if "SOURCE" in df.columns else ["?"]
        print(f"  {country}: clean ({len(df)} rows, source: {srcs[0][:50]})")

if not found_wage_break:
    print("\n  No wage breaks found in this list — need to widen search.")


# ── CHECK 3: PAK unemployment break ─────────────────────────────────────────
print(f"\n{SEP}")
print("CHECK 3 — PAK unemployment break in DF_UNE_DEAP_SEX_AGE_RT")
print(SEP)

df = pull("DF_UNE_DEAP_SEX_AGE_RT", "PAK",
          {"SEX": "SEX_T", "AGE": "AGE_YTHADULT_YGE15"}, "2005", "2024")
if df is None:
    print("  PAK: no data")
else:
    print(f"  {len(df)} annual rows")
    print(sources(df))
    print(f"  Has break: {has_break(df)}")


# ── CHECK 4: PAK wage break ──────────────────────────────────────────────────
print(f"\n{SEP}")
print("CHECK 4 — PAK wage break in DF_EAR_EMTA_SEX_CUR_NB")
print(SEP)

df = pull("DF_EAR_EMTA_SEX_CUR_NB", "PAK",
          {"SEX": "SEX_T", "CUR": "CUR_TYPE_LCU"}, "2005", "2024")
if df is None:
    print("  PAK: no data in canonical wage flow")
else:
    print(f"  {len(df)} annual rows")
    print(sources(df))
    print(f"  Has break: {has_break(df)}")


# ── CHECK 5: SOM coverage ────────────────────────────────────────────────────
print(f"\n{SEP}")
print("CHECK 5 — SOM (Somalia) coverage")
print(SEP)

for flow_id in ["DF_UNE_DEAP_SEX_AGE_RT", "DF_EMP_DWAP_SEX_AGE_RT", "DF_EAP_DWAP_SEX_AGE_RT"]:
    df = pull(flow_id, "SOM",
              {"SEX": "SEX_T", "AGE": "AGE_YTHADULT_YGE15"}, "2000", "2024")
    if df is None:
        print(f"  {flow_id}: SOM → no data (404 or empty)")
    else:
        print(f"  {flow_id}: SOM → {len(df)} rows, source: {df['SOURCE'].unique().tolist() if 'SOURCE' in df.columns else '?'}")


# ── CHECK 6: EU aggregate in CL_AREA ────────────────────────────────────────
print(f"\n{SEP}")
print("CHECK 6 — EU aggregate code in CL_AREA")
print(SEP)

try:
    cl_resp = client.codelist("CL_AREA")
    cl = list(cl_resp.codelist.values())[0]
    eu_codes = [(code, str(item.name)) for code, item in cl.items()
                if "european union" in str(item.name).lower()
                or "euro area" in str(item.name).lower()
                or str(code).startswith("EU")
                or str(code) in ("EUU", "EUI", "EUR")]
    if eu_codes:
        for code, name in eu_codes:
            print(f"  {code}: {name}")
    else:
        print("  No EU aggregate codes found in CL_AREA")
except Exception as e:
    print(f"  ERROR: {e}")

# Also try pulling directly with a guess
print("\n--- Direct pull attempts ---")
for eu_code in ["EU", "EU27", "EU27_2020", "EUU", "XC"]:
    df = pull("DF_UNE_DEAP_SEX_AGE_RT", eu_code,
              {"SEX": "SEX_T", "AGE": "AGE_YTHADULT_YGE15"}, "2020", "2023")
    if df is not None:
        print(f"  {eu_code}: got data ({len(df)} rows)")
    else:
        print(f"  {eu_code}: no data")


# ── CHECK 7: MEASURE dimension ───────────────────────────────────────────────
print(f"\n{SEP}")
print("CHECK 7 — MEASURE dimension: single value per flow?")
print(SEP)

checks = [
    ("DF_UNE_DEAP_SEX_AGE_RT", "NGA", {"SEX": "SEX_T", "AGE": "AGE_YTHADULT_YGE15"}),
    ("DF_EMP_DWAP_SEX_AGE_RT", "BRA", {"SEX": "SEX_T", "AGE": "AGE_YTHADULT_YGE15"}),
    ("DF_EAR_EMTA_SEX_CUR_NB", "FRA", {"SEX": "SEX_T", "CUR": "CUR_TYPE_LCU"}),
    ("DF_EAP_DWAP_SEX_AGE_RT", "DEU", {"SEX": "SEX_T", "AGE": "AGE_YTHADULT_YGE15"}),
]

for flow_id, country, key_extra in checks:
    # Don't filter FREQ — want all frequencies to see if MEASURE varies
    key = {"REF_AREA": country, **key_extra}
    try:
        resp = client.data(flow_id, key=key, params={"startPeriod": "2020", "endPeriod": "2023"})
        df = sdmx.to_pandas(resp, attributes="o").reset_index()
        measures = df["MEASURE"].unique().tolist() if "MEASURE" in df.columns else ["(no MEASURE col)"]
        print(f"  {flow_id}: MEASURE = {measures}")
    except Exception as e:
        print(f"  {flow_id}: ERROR {e}")

print(f"\n{SEP}")
print("Done.")
print(SEP)
