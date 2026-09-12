"""
Phase 0b follow-up — 4 remaining open items.
Run: uv run --with sdmx1 python local-notes/execution/phase00/scratch_phase0b_followup.py
"""

import sdmx
import pandas as pd
from requests.exceptions import HTTPError

SEP = "=" * 65

def section(title):
    print(f"\n{SEP}\n  {title}\n{SEP}")

def has_data(client, flow, country, start, end):
    """Returns True if live API returns any rows for this country/period."""
    try:
        msg = client.data(flow, key={"REF_AREA": country},
                          params={"startPeriod": str(start), "endPeriod": str(end),
                                  "detail": "full"}, dsd=False)
        df = sdmx.to_pandas(msg, attributes="osgd")
        return df is not None and not df.empty
    except HTTPError:
        return False
    except Exception:
        return False

client = sdmx.Client("ILO")
catalog_msg = client.dataflow()
all_ids = list(catalog_msg.dataflow.keys())
print(f"Catalog: {len(all_ids)} dataflows")

UNE_FLOW = "DF_UNE_DEAP_SEX_AGE_RT"

# ============================================================
# 1. q021 — find a truly no-data country for unemployment
# ============================================================
section("1. q021 — find a truly no-data survey unemployment country")

# Candidates: countries unlikely to report survey data to ILOSTAT
# (small island states, heavily sanctioned states, very low admin capacity)
candidates = [
    ("ERI", "Eritrea"),
    ("SSD", "South Sudan"),
    ("TKM", "Turkmenistan"),
    ("SYR", "Syria"),
    ("YEM", "Yemen"),
    ("LBY", "Libya"),
    ("MMR", "Myanmar"),
    ("AFG", "Afghanistan"),
    ("HTI", "Haiti"),
    ("TCD", "Chad"),
]

no_data_countries = []
for code, name in candidates:
    result = has_data(client, UNE_FLOW, code, 2020, 2023)
    status = "HAS DATA" if result else "NO DATA ✓"
    print(f"  {code} ({name}): {status}")
    if not result:
        no_data_countries.append((code, name))

# Also check modelled estimates for the no-data ones
# (we want: no survey data BUT modelled estimates exist — same setup as PRK)
MOD_FLOW = "DF_UNE_2EAP_SEX_AGE_RT"
print(f"\nChecking modelled estimates for no-data candidates:")
best = []
for code, name in no_data_countries:
    has_mod = has_data(client, MOD_FLOW, code, 2020, 2023)
    print(f"  {code}: modelled estimates = {'YES' if has_mod else 'no'}")
    if has_mod:
        best.append((code, name))

print(f"\nBest candidates (no survey data, but modelled estimates exist): {best}")
print(f"Any no-survey country works: {no_data_countries}")


# ============================================================
# 2. q023 — find a supranational entity with no CL_AREA code
# ============================================================
section("2. q023 — find a supranational entity with no ILOSTAT code")

cl_msg = client.codelist("CL_AREA")
cl = list(cl_msg.codelist.values())[0]
all_area_codes = set(cl.items.keys())
all_area_names = {code: str(item.name) for code, item in cl.items.items()}

# Check candidate supranational entities by name
search_terms = ["asean", "brics", "g7", "g20", "nato", "arab league",
                "african union", "mercosur", "gcc", "opec", "commonwealth"]
print("Searching CL_AREA names for supranational entities:")
found = {}
for term in search_terms:
    matches = {c: n for c, n in all_area_names.items() if term in n.lower()}
    if matches:
        print(f"  '{term}': {matches}")
        found[term] = matches
    else:
        print(f"  '{term}': NOT FOUND in CL_AREA ✓")

# Pick best replacement: not in CL_AREA at all, and plausible for a user to ask about
no_code_entities = [t for t in search_terms if t not in found]
print(f"\nEntities with NO code in CL_AREA: {no_code_entities}")
print("Recommended replacement for q023: pick one of these — ASEAN or G7 is most natural")


# ============================================================
# 3. SGP and DEU wages — find correct EAR flow
# ============================================================
section("3. SGP / DEU wages — find the right EAR dataflow")

ear_flows = [i for i in all_ids if "EAR_" in i and "2EAR" not in i]
print(f"Total survey EAR flows: {len(ear_flows)}")

for country, qid in [("SGP", "q002"), ("DEU", "q010")]:
    print(f"\n--- {country} ({qid}) ---")
    found_flows = []
    for flow in ear_flows:
        if has_data(client, flow, country, 2019, 2022):
            # Get a sample value to understand what this flow measures
            try:
                msg = client.data(flow, key={"REF_AREA": country},
                                  params={"startPeriod": "2021", "endPeriod": "2021",
                                          "detail": "full"}, dsd=False)
                df = sdmx.to_pandas(msg, attributes="osgd")
                if df is not None and not df.empty:
                    # Get the flow title
                    title = str(catalog_msg.dataflow[flow].name)[:70]
                    # Get unit/measure info
                    measure_val = ""
                    if "MEASURE" in df.index.names:
                        measures = df.index.get_level_values("MEASURE").unique().tolist()
                        measure_val = str(measures[0]) if measures else ""
                    # Get currency if present
                    cur_val = ""
                    if "CUR_TYPE" in df.index.names:
                        curs = df.index.get_level_values("CUR_TYPE").unique().tolist()
                        cur_val = str(curs)
                    sample_val = df["value"].dropna().iloc[0] if "value" in df.columns else "?"
                    print(f"  {flow}")
                    print(f"    title: {title}")
                    print(f"    measure: {measure_val}  currency: {cur_val}  sample: {sample_val}")
                    found_flows.append(flow)
            except Exception as e:
                print(f"  {flow}: sample error: {e}")

    if not found_flows:
        print(f"  No EAR flow found for {country} — country may not report wages to ILOSTAT")
    else:
        print(f"\n  Flows with {country} wage data: {found_flows}")


# ============================================================
# 4. GEO (Georgia) wages — exhaustive EAR check
# ============================================================
section("4. GEO (Georgia) wages — q009")

geo_flows = []
for flow in ear_flows:
    if has_data(client, flow, "GEO", 2018, 2023):
        title = str(catalog_msg.dataflow[flow].name)[:70]
        print(f"  {flow}: {title}")
        geo_flows.append(flow)

if not geo_flows:
    print("  No wage data found for GEO in any EAR flow")
    print("  → q009 notes: after disambiguation, answer is 'no wage data available for Georgia'")
else:
    print(f"\n  GEO has wage data in: {geo_flows}")


print(f"\n{SEP}")
print("  FOLLOW-UP CHECKS COMPLETE")
print(SEP)
