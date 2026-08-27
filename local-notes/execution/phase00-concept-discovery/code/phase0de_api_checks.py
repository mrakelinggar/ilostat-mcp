"""
Phase 0d/0e — API-verifiable unknowns before Phase 1.

Checks:
  1. No-data country for benchmark q021 — try PRK, ERI, NRU, TUV
  2. Exception type for 404 — what does sdmx1 raise when country has no data?
  3. Dataflow metadata structure — what does client.dataflow() return?
     Specifically: is there a last_updated timestamp anywhere?
  4. What does a KeyError look like vs 404? (invalid flow ID)
"""

import sdmx
import cloudscraper
import pandas as pd
import traceback

client = sdmx.Client("ILO")
client.session = cloudscraper.create_scraper()

SEP = "=" * 70

# ── CHECK 1: No-data countries ───────────────────────────────────────────────
print(f"\n{SEP}")
print("CHECK 1 — No-data country candidates for benchmark q021")
print(SEP)

candidates = ["PRK", "ERI", "NRU", "TUV", "SSD", "TKM"]

for country in candidates:
    try:
        resp = client.data(
            "DF_UNE_DEAP_SEX_AGE_RT",
            key={"REF_AREA": country, "SEX": "SEX_T", "AGE": "AGE_YTHADULT_YGE15"},
            params={"startPeriod": "2000", "endPeriod": "2024"}
        )
        df = sdmx.to_pandas(resp, attributes="o").reset_index()
        if df.empty:
            print(f"  {country}: empty response (no data)")
        else:
            df_a = df[df["FREQ"] == "A"] if "FREQ" in df.columns else df
            print(f"  {country}: {len(df_a)} annual rows — NOT a no-data country")
            if "SOURCE" in df_a.columns:
                print(f"    sources: {df_a['SOURCE'].unique().tolist()}")
    except Exception as e:
        exc_type = type(e).__name__
        print(f"  {country}: {exc_type} — {str(e)[:120]}")


# ── CHECK 2: Exception type for 404 ─────────────────────────────────────────
print(f"\n{SEP}")
print("CHECK 2 — Exception type raised on 404 (no data for country)")
print(SEP)

# Use NGA for wages which we know returns 404 (from phase0b run)
print("Using NGA wages (confirmed 404 in phase0b):")
try:
    resp = client.data(
        "DF_EAR_EMTA_SEX_CUR_NB",
        key={"REF_AREA": "NGA", "SEX": "SEX_T", "CUR": "CUR_TYPE_LCU"},
        params={"startPeriod": "2022", "endPeriod": "2023"}
    )
    print("  No exception raised — got data")
except Exception as e:
    print(f"  Exception type: {type(e).__name__}")
    print(f"  Module: {type(e).__module__}")
    print(f"  MRO: {[c.__name__ for c in type(e).__mro__]}")
    print(f"  str(e): {str(e)[:200]}")

# Also try an invalid flow ID to see what that looks like
print("\nUsing invalid flow ID 'DF_FAKE_FLOW_ID':")
try:
    resp = client.data(
        "DF_FAKE_FLOW_ID",
        key={"REF_AREA": "FRA"},
        params={}
    )
    print("  No exception raised")
except Exception as e:
    print(f"  Exception type: {type(e).__name__}")
    print(f"  Module: {type(e).__module__}")
    print(f"  str(e): {str(e)[:200]}")


# ── CHECK 3: Dataflow metadata structure ────────────────────────────────────
print(f"\n{SEP}")
print("CHECK 3 — Dataflow metadata: what fields are available?")
print("Looking for: title, description, last_updated, unit, source info")
print(SEP)

try:
    resp = client.dataflow("DF_UNE_DEAP_SEX_AGE_RT")
    print(f"Response type: {type(resp)}")
    print(f"Response attrs: {[a for a in dir(resp) if not a.startswith('_')]}")

    if hasattr(resp, 'dataflow'):
        flows = resp.dataflow
        print(f"\ndataflow type: {type(flows)}")
        for flow_id, flow in list(flows.items())[:1]:
            print(f"\nFlow ID: {flow_id}")
            print(f"  name: {flow.name}")
            print(f"  description: {getattr(flow, 'description', 'N/A')}")
            print(f"  valid_from: {getattr(flow, 'valid_from', 'N/A')}")
            print(f"  valid_to: {getattr(flow, 'valid_to', 'N/A')}")
            print(f"  annotations: {getattr(flow, 'annotations', 'N/A')}")
            print(f"  attrs: {[a for a in dir(flow) if not a.startswith('_')]}")
            # Check the structure reference
            if hasattr(flow, 'structure'):
                print(f"  structure ref: {flow.structure}")
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()

# Also try fetching all unemployment dataflows to see the title format
print("\n--- All UNE dataflows: title format ---")
try:
    resp = client.dataflow("DF_UNE_DEAP_SEX_AGE_RT", params={"references": "none"})
    for flow_id, flow in resp.dataflow.items():
        print(f"  {flow_id}: {flow.name}")
        break  # just one
except Exception as e:
    print(f"  ERROR: {e}")


# ── CHECK 4: Data response — is there a last_updated in data metadata? ───────
print(f"\n{SEP}")
print("CHECK 4 — Data message metadata: is there a last_updated / prepared date?")
print(SEP)

try:
    resp = client.data(
        "DF_UNE_DEAP_SEX_AGE_RT",
        key={"REF_AREA": "DEU", "SEX": "SEX_T", "AGE": "AGE_YTHADULT_YGE15"},
        params={"startPeriod": "2022", "endPeriod": "2023"}
    )
    print(f"Response type: {type(resp)}")
    print(f"Response attrs: {[a for a in dir(resp) if not a.startswith('_')]}")
    if hasattr(resp, 'header'):
        hdr = resp.header
        print(f"\nheader: {hdr}")
        print(f"header attrs: {[a for a in dir(hdr) if not a.startswith('_')]}")
        for attr in ['prepared', 'sender', 'id', 'test', 'extracted']:
            print(f"  header.{attr}: {getattr(hdr, attr, 'N/A')}")
    if hasattr(resp, 'footer'):
        print(f"footer: {resp.footer}")
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()

print(f"\n{SEP}")
print("Done.")
print(SEP)
