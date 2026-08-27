"""
Phase 0a — Dataflow Selection Script (1b–1e)
Run with: uv run --with sdmx1 python local-notes/execution/phase00/code/phase0a_scratch_dataflow_selection.py

Covers:
  1b. For each concept in scope, what flows exist and what distinguishes them?
  1c. Apply selection criterion → one canonical flow per concept
  1d. Do alternative survey flows for unemployment return different numbers?
  1e. Does keyword search surface the canonical flow first?

Four concepts in scope: unemployment rate, average monthly wages,
youth unemployment, employment-to-population ratio.
"""

import sdmx
import pandas as pd
from requests.exceptions import HTTPError
import traceback

SEP = "\n" + "=" * 70 + "\n"

def section(title):
    print(SEP + f"[{title}]")

client = sdmx.Client("ILO")

# Search keywords per concept — matched against catalog titles (case-insensitive)
CONCEPTS = {
    "unemployment_rate":        ["unemployment rate"],
    "monthly_wages":            ["monthly earnings"],
    "youth_unemployment":       ["youth unemployment"],
    "employment_to_population": ["employment-to-population"],
}

# Dimensions that make a flow more specific (beyond SEX/AGE/CUR)
SPECIFIC_DIMS = {"DSB", "ECO", "HHT", "GEO", "INS", "NOC", "MIG", "CHL", "OCU"}

# Five representative countries for 1d
TEST_COUNTRIES = ["MYS", "DEU", "NGA", "BRA", "THA"]

# Default codes for "total" observation
SEX_TOTAL  = "SEX_T"
AGE_TOTAL  = "AGE_YTHADULT_YGE15"
FREQ_ANNUAL = "A"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_modelled(flow_id):
    """True if the variant segment (position 2 in the DF_TOPIC_VARIANT_... ID) starts with a digit.

    Leading digit = ILO modelled/imputed estimate. Confirmed in SDMX API Guide v4.1 p.14
    and by Phase 0a title scan (all 2EAP/2WAP flows carry "ILO modelled estimates" in title).
    """
    parts = flow_id.split("_")
    return len(parts) > 2 and parts[2][0].isdigit()


def extra_dims(flow_id):
    """Returns classification dimensions beyond SEX, AGE, CUR.

    ID structure: DF_TOPIC_VARIANT_[CLASSIF...]_MEASURE
    Positions: 0=DF, 1=TOPIC, 2=VARIANT, 3..n-1=CLASSIFs, n=MEASURE
    """
    parts = flow_id.split("_")
    classifs = parts[3:-1] if len(parts) > 4 else []
    return [d for d in classifs if d not in {"SEX", "AGE", "CUR"}]


def count_countries(flow_id):
    """Number of countries with annual data in this flow (recent 4 years).

    Pulls 2020-2023 for all countries, filters to annual, counts unique REF_AREA.
    lastNObservations is rejected by the ILO API — use startPeriod/endPeriod instead.
    """
    try:
        msg = client.data(
            flow_id,
            params={"startPeriod": "2020", "endPeriod": "2023"},
            dsd=False,
        )
        df = sdmx.to_pandas(msg)
        if "REF_AREA" in df.index.names:
            if "FREQ" in df.index.names:
                df = df[df.index.get_level_values("FREQ") == FREQ_ANNUAL]
            return df.index.get_level_values("REF_AREA").nunique()
        return 0
    except Exception as e:
        print(f"    coverage check failed ({flow_id}): {e}")
        return 0


def latest_value(flow_id, country):
    """Pull the most recent annual total value for a country from a flow.

    Returns (year, value) or (None, note) on no data.
    Filters to SEX_T + AGE_YTHADULT_YGE15 + FREQ=A in pandas after the pull.
    """
    try:
        msg = client.data(
            flow_id,
            key={"REF_AREA": country},
            params={"startPeriod": "2019", "endPeriod": "2024"},
            dsd=False,
        )
        df = sdmx.to_pandas(msg, attributes="osgd")
        if not isinstance(df, pd.DataFrame) or df.empty:
            return None, "empty"

        idx = df.index
        mask = pd.Series(True, index=df.index)
        if "FREQ" in idx.names:
            mask &= idx.get_level_values("FREQ") == FREQ_ANNUAL
        if "SEX" in idx.names:
            mask &= idx.get_level_values("SEX") == SEX_TOTAL
        if "AGE" in idx.names:
            mask &= idx.get_level_values("AGE") == AGE_TOTAL
        sub = df[mask]

        if sub.empty:
            return None, "no SEX_T/AGE_YTHADULT_YGE15/A row"

        time_vals = sub.index.get_level_values("TIME_PERIOD")
        latest_year = sorted(time_vals)[-1]
        row = sub[sub.index.get_level_values("TIME_PERIOD") == latest_year]
        val = row["value"].iloc[0] if "value" in row.columns else row.iloc[0, 0]
        return latest_year, round(float(val), 2)

    except HTTPError as e:
        return None, f"HTTP {e.response.status_code}"
    except KeyError:
        return None, "KeyError (country absent)"
    except Exception as e:
        return None, str(e)[:40]


# ---------------------------------------------------------------------------
# Fetch catalog once
# ---------------------------------------------------------------------------
section("Catalog fetch")
print("Fetching all dataflows...")
msg = client.dataflow()
catalog = {fid: str(f.name) for fid, f in msg.dataflow.items()}
print(f"Total: {len(catalog)} dataflows")


# ---------------------------------------------------------------------------
# 1b — Enumerate flows per concept
# ---------------------------------------------------------------------------
section("1b — Flows per concept")

concept_flows = {}

for concept, keywords in CONCEPTS.items():
    matches = {
        fid: title
        for fid, title in catalog.items()
        if any(kw in title.lower() for kw in keywords)
    }
    concept_flows[concept] = matches

    n_survey  = sum(1 for fid in matches if not is_modelled(fid))
    n_modelled = sum(1 for fid in matches if is_modelled(fid))

    print(f"\n{'─'*70}")
    print(f"Concept: {concept.upper()}")
    print(f"  {len(matches)} flows total — {n_survey} survey, {n_modelled} modelled")
    print(f"{'─'*70}")
    print(f"  {'Mod?':<5}  {'Extra dims':<22}  {'ID':<48}  Title")
    print(f"  {'─'*5}  {'─'*22}  {'─'*48}  {'─'*40}")
    for fid in sorted(matches):
        mod   = "MOD" if is_modelled(fid) else "srv"
        extra = ", ".join(extra_dims(fid)) or "—"
        title = matches[fid][:55]
        print(f"  {mod:<5}  {extra:<22}  {fid:<48}  {title}")


# ---------------------------------------------------------------------------
# 1c — Apply selection criterion
# ---------------------------------------------------------------------------
section("1c — Canonical flow selection")

print("""
Selection criterion (from phase_0a_plan.md):
  (a) Survey-based, not modelled
  (b) Most general disaggregation — fewest extra dimensions beyond SEX/AGE/CUR
  (c) Broadest country coverage — most countries with annual data
""")

CANONICAL = {}

for concept, flows in concept_flows.items():
    print(f"\nConcept: {concept}")

    # (a) drop modelled flows
    survey = {fid: t for fid, t in flows.items() if not is_modelled(fid)}
    print(f"  (a) survey flows: {len(survey)} of {len(flows)}")
    if not survey:
        print("  → No survey flows — cannot select canonical. NEEDS INVESTIGATION.")
        continue

    # (a2) drop flows that are sector-specific, sub-annual, or non-average measures
    # These are general concepts; we want the flow covering all employees at annual frequency.
    TITLE_EXCLUDES = [
        "care employees", "public sector", "STEM", "tourism", "Gini", "median",
        "Sub-annual",
    ]
    general = {
        fid: t for fid, t in survey.items()
        if not any(excl.lower() in t.lower() for excl in TITLE_EXCLUDES)
    }
    if general:
        print(f"  (a2) after excluding sector-specific/sub-annual: {len(general)} of {len(survey)}")
        survey = general
    else:
        print(f"  (a2) no flows survived title exclusions — keeping all survey flows")

    # (b) fewest extra dims
    min_extra = min(len(extra_dims(fid)) for fid in survey)
    general = {fid: t for fid, t in survey.items() if len(extra_dims(fid)) == min_extra}
    print(f"  (b) most general (extra dims = {min_extra}): {len(general)} candidate(s)")
    for fid in general:
        print(f"      {fid}")

    if len(general) == 1:
        winner = list(general.keys())[0]
        reason = f"only survey flow with fewest extra dimensions ({min_extra})"
    else:
        # (c) broadest country coverage
        print("  (c) checking country coverage...")
        coverage = {}
        for fid in general:
            n = count_countries(fid)
            coverage[fid] = n
            print(f"      {fid}: {n} countries")
        winner = max(coverage, key=coverage.get)
        reason = (
            f"broadest coverage ({coverage[winner]} countries) "
            f"among survey flows with fewest extra dimensions ({min_extra})"
        )

    CANONICAL[concept] = (winner, reason)
    print(f"  → CANONICAL: {winner}")
    print(f"     Title:  {catalog.get(winner, 'unknown')}")
    print(f"     Reason: {reason}")

print("\n\n--- CANONICAL FLOW SUMMARY ---")
for concept, (fid, reason) in CANONICAL.items():
    print(f"\n{concept}:")
    print(f"  {fid}")
    print(f"  \"{catalog.get(fid, 'unknown')}\"")
    print(f"  Reason: {reason}")


# ---------------------------------------------------------------------------
# 1d — Cross-flow value comparison (unemployment rate, 5 countries)
# ---------------------------------------------------------------------------
section("1d — Cross-flow comparison: do different flows return different numbers?")

une_survey_flows = {
    fid: t
    for fid, t in concept_flows.get("unemployment_rate", {}).items()
    if not is_modelled(fid)
}

print(f"Survey unemployment flows ({len(une_survey_flows)}):")
for fid, t in une_survey_flows.items():
    print(f"  {fid}: {t}")

# Shorten flow IDs for table headers
def short(fid):
    # Strip DF_UNE_ prefix and _SEX_AGE_RT suffix for readability
    return fid.replace("DF_UNE_", "").replace("_SEX_AGE_RT", "").replace("_SEX_AGE_DSB_RT", "_DSB")

flow_list = list(une_survey_flows.keys())
col_width = 18

print(f"\nPulling most recent annual value per country per flow...")
print(f"Filter: SEX_T + AGE_YTHADULT_YGE15 + FREQ=A")

results = {}  # (country, flow_id) -> (year, value_or_note)
for fid in flow_list:
    for country in TEST_COUNTRIES:
        year, val = latest_value(fid, country)
        results[(country, fid)] = (year, val)
        marker = f"{val} ({year})" if isinstance(val, float) else val
        print(f"  {country} / {short(fid):<20}: {marker}")

# Print comparison table
print(f"\n{'Country':<8}", end="")
for fid in flow_list:
    print(f"  {short(fid):<{col_width}}", end="")
print("  Verdict")

print(f"{'─'*8}", end="")
for fid in flow_list:
    print(f"  {'─'*col_width}", end="")
print(f"  {'─'*10}")

for country in TEST_COUNTRIES:
    vals = []
    print(f"{country:<8}", end="")
    for fid in flow_list:
        year, val = results[(country, fid)]
        if isinstance(val, float):
            cell = f"{val} ({year})"
            vals.append(val)
        else:
            cell = val or "n/a"
        print(f"  {cell:<{col_width}}", end="")

    non_null = [v for v in vals if v is not None]
    if len(non_null) == 0:
        verdict = "NO DATA"
    elif len(set(non_null)) == 1:
        verdict = "SAME"
    elif max(non_null) - min(non_null) < 0.1:
        verdict = "~SAME (<0.1pp)"
    else:
        verdict = f"DIFFER ({min(non_null)}–{max(non_null)})"
    print(f"  {verdict}")

print()
print("DIFFER means the flows return meaningfully different numbers for the same")
print("country — canonical selection materially affects what the tool returns.")


# ---------------------------------------------------------------------------
# 1e — Search behavior
# ---------------------------------------------------------------------------
section("1e — Search behavior: does the canonical flow appear first?")

SEARCH_QUERIES = [
    "unemployment rate",
    "wages",
    "monthly earnings",
    "youth unemployment",
    "employment-to-population",
]

# Build reverse lookup: canonical fid -> concept
canonical_fids = {fid: concept for concept, (fid, _) in CANONICAL.items()}

for query in SEARCH_QUERIES:
    matches = [
        (fid, title)
        for fid, title in catalog.items()
        if query.lower() in title.lower()
    ]

    print(f"\nQuery: \"{query}\"  ({len(matches)} results)")
    print(f"  {'#':<3}  {'Type':<4}  {'ID':<50}  Title")
    print(f"  {'─'*3}  {'─'*4}  {'─'*50}  {'─'*45}")

    for rank, (fid, title) in enumerate(matches[:10], 1):
        mod    = "MOD" if is_modelled(fid) else "srv"
        marker = f"  ← canonical ({canonical_fids[fid]})" if fid in canonical_fids else ""
        print(f"  {rank:<3}  {mod:<4}  {fid:<50}  {title[:45]}{marker}")

    if len(matches) > 10:
        print(f"  ... ({len(matches) - 10} more not shown)")

    # Check if any canonical flow for this query is outside the top 10
    for fid, concept in canonical_fids.items():
        if query.lower() in catalog.get(fid, "").lower():
            all_fids = [f for f, _ in matches]
            if fid in all_fids:
                rank = all_fids.index(fid) + 1
                if rank > 10:
                    print(f"  ↳ Canonical ({fid}) is at rank {rank} — not in top 10")
            else:
                print(f"  ↳ Canonical ({fid}) NOT in results for this query")

    # Risk flag: does a modelled flow appear before the first survey flow?
    first_mod = next((i + 1 for i, (fid, _) in enumerate(matches) if is_modelled(fid)), None)
    first_srv = next((i + 1 for i, (fid, _) in enumerate(matches) if not is_modelled(fid)), None)
    if first_mod and first_srv and first_mod < first_srv:
        print(f"  ⚠ RISK: modelled flow at #{first_mod} ranked before first survey flow at #{first_srv}")
    elif first_srv:
        print(f"  OK: first survey flow at #{first_srv}" + (f", first modelled at #{first_mod}" if first_mod else ", no modelled flows in results"))


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
section("SUMMARY")

print("1b — Flow counts per concept:")
for concept, flows in concept_flows.items():
    n_srv = sum(1 for fid in flows if not is_modelled(fid))
    n_mod = sum(1 for fid in flows if is_modelled(fid))
    print(f"  {concept:<30}: {len(flows):>3} total  ({n_srv} survey, {n_mod} modelled)")

print("\n1c — Canonical flows selected:")
for concept, (fid, reason) in CANONICAL.items():
    print(f"  {concept:<30}: {fid}")

print("\n1d — See comparison table above")
print("      SAME = canonical selection doesn't matter for this country")
print("      DIFFER = canonical selection is critical")

print("\n1e — See search results above")
print("      RISK flags = search_indicators may surface a modelled flow before survey flows")
print("      Decision needed: rank survey flows above modelled? Or rely on system prompt?")

print("\nRecord findings in: local-notes/execution/phase00/phase0a_dataflow_selection.md")
