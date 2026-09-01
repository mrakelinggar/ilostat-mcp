"""
Phase 2b Task 0 — GEO dimension discovery on DF_UNE_3EAP_SEX_AGE_GEO_RT.

Question: what happens when we call this flow without a GEO value?
Does it return national totals, all geographies mixed, or an error?

This flow is used in q016 (South Africa youth unemployment rate).
The youth AGE code for 15-29 is AGE_YTHBANDS_Y15-29.
"""

import sys
sys.path.insert(0, "src")

from ilostat_mcp import sdmx_client
from ilostat_mcp.indicators import AGE_TOTAL

FLOW = "DF_UNE_3EAP_SEX_AGE_GEO_RT"
COUNTRY = "ZAF"
YOUTH_AGE = "AGE_YTHBANDS_Y15-29"

print("=" * 70)
print(f"Flow: {FLOW}")
print(f"Country: {COUNTRY}")
print("=" * 70)

# --- Call 1: adult total (AGE_YTHADULT_YGE15), no GEO ---
print("\n[1] Adult total (AGE_TOTAL), no GEO key:")
df1 = sdmx_client.get_time_series(FLOW, COUNTRY, "2019", "2023", age=AGE_TOTAL)
print(f"  Shape: {df1.shape}")
print(f"  Columns: {df1.columns.tolist()}")
if not df1.empty:
    print(f"  Rows:\n{df1.to_string(index=False)}")
else:
    print("  → Empty DataFrame")

# --- Call 2: youth band, no GEO ---
print(f"\n[2] Youth band ({YOUTH_AGE}), no GEO key:")
df2 = sdmx_client.get_time_series(FLOW, COUNTRY, "2019", "2023", age=YOUTH_AGE)
print(f"  Shape: {df2.shape}")
print(f"  Columns: {df2.columns.tolist()}")
if not df2.empty:
    print(f"  Rows:\n{df2.to_string(index=False)}")
else:
    print("  → Empty DataFrame")

# --- Check: is there a GEO column? ---
for label, df in [("adult", df1), ("youth", df2)]:
    if not df.empty and "geo" in df.columns:
        unique_geo = df["geo"].unique().tolist()
        print(f"\n  GEO values in {label} result: {unique_geo}")
        print(f"  Row count per GEO value:")
        print(df.groupby("geo").size().to_string())
