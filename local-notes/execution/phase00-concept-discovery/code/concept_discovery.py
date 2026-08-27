"""
Phase 00 — Concept Discovery
Enumerate EVERY dataflow for each of the four labor market concepts, document
each one with a reason for selection or discard, and verify the canonical choice
with a live numerical cross-check.

Run:
    uv run --with sdmx1 --with cloudscraper --with tqdm \
        python local-notes/execution/phase00-concept-discovery/code/concept_discovery.py \
        2>&1 | tee local-notes/execution/phase00-concept-discovery/results_raw.txt

Concepts: unemployment rate, employment-to-population ratio,
          average monthly earnings (wages), labour force participation rate (LFPR)
"""

import sdmx
import cloudscraper
import pandas as pd
from requests.exceptions import HTTPError
from tqdm import tqdm

SEP = "\n" + "=" * 72 + "\n"
SUB = "\n" + "─" * 72 + "\n"


def section(title):
    tqdm.write(SEP + f"  {title}")


def subsection(title):
    tqdm.write(SUB + f"  {title}")


def log(msg):
    tqdm.write(msg)


# ── sdmx client ───────────────────────────────────────────────────────────────
# ILO's SDMX endpoint sits behind Cloudflare bot protection. Replacing the
# default requests.Session with a cloudscraper session passes the JS challenge
# transparently. Confirmed working 2026-08-28 after plain requests got 403.

client = sdmx.Client("ILO")
client.session = cloudscraper.create_scraper()

FREQ_ANNUAL = "A"
SEX_TOTAL   = "SEX_T"
AGE_TOTAL   = "AGE_YTHADULT_YGE15"


# ── helpers ───────────────────────────────────────────────────────────────────

def is_modelled(flow_id: str) -> bool:
    """
    Variant segment (position 2 in DF_TOPIC_VARIANT_...) starts with a digit
    for ILO modelled/imputed estimates. Confirmed in SDMX API Guide v4.1 p.14.
    """
    parts = flow_id.split("_")
    return len(parts) > 2 and parts[2][0].isdigit()


def extra_dims(flow_id: str, base: set) -> list:
    """
    Return classification dimensions beyond the concept's base set.
    These make the flow return a subgroup rather than the total.

    ID: DF_TOPIC_VARIANT_[CLASSIF1_CLASSIF2_...]_MEASURE
    `base` is concept-specific:
      unemployment / emp-to-pop / LFPR → {SEX, AGE}
      wages                            → {SEX, CUR}
    """
    parts = flow_id.split("_")
    classifs = parts[3:-1] if len(parts) > 4 else []
    return [d for d in classifs if d not in base]


def latest_value(flow_id: str, country: str, extra_key: dict = None) -> tuple:
    """
    Pull the most recent annual total value for a country.
    Returns (year, value) on success, (None, note) on failure.
    extra_key: additional dimension filters (e.g. {"CUR": "CUR_TYPE_LCU"} for wages).
    """
    key = {"REF_AREA": country}
    if extra_key:
        key.update(extra_key)

    try:
        msg = client.data(
            flow_id,
            key=key,
            params={"startPeriod": "2010", "endPeriod": "2024"},
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
        latest_yr = sorted(time_vals)[-1]
        row = sub[sub.index.get_level_values("TIME_PERIOD") == latest_yr]
        val = row["value"].iloc[0] if "value" in row.columns else row.iloc[0, 0]
        return latest_yr, round(float(val), 2)

    except HTTPError as e:
        return None, f"HTTP {e.response.status_code}"
    except KeyError:
        return None, "KeyError (country absent)"
    except Exception as e:
        return None, str(e)[:60]


# ── title-based exclusions ────────────────────────────────────────────────────
# Survey flows that survive the extra-dim check but must still be discarded.
# Applied after the dim filter, before cross-check.
#
# "sub-annual" — frequency is monthly/quarterly; our tools work in annual series.
#   These flows have no SEX_T/AGE total at annual frequency so the cross-check
#   correctly returns no data — but we exclude them explicitly so the reason is clear.
#
# "19th icls" — uses the revised 19th ICLS unemployment definition (2013),
#   which is stricter than the 13th ICLS used in the main DEAP/DWAP survey flows.
#   The two definitions give materially different numbers for the same country/year
#   (confirmed in cross-check: NGA 4.68 vs 3.45). We want one consistent standard.

TITLE_EXCLUDE = ["sub-annual", "19th icls"]


# ── concept definitions ───────────────────────────────────────────────────────

CONCEPTS = {
    "unemployment_rate": {
        "label":          "Unemployment Rate",
        "keywords":       ["unemployment rate"],
        "base_dims":      {"SEX", "AGE"},
        "extra_key":      {},
        "test_countries": ["BRA", "DEU", "MYS", "NGA", "THA"],
    },
    "employment_to_pop": {
        "label":          "Employment-to-Population Ratio",
        "keywords":       ["employment-to-population"],
        "base_dims":      {"SEX", "AGE"},
        "extra_key":      {},
        "test_countries": ["BRA", "DEU", "MYS", "NGA", "THA"],
    },
    "wages": {
        "label":          "Average Monthly Earnings (Wages)",
        "keywords":       ["monthly earnings"],
        "base_dims":      {"SEX", "CUR"},
        "extra_key":      {"CUR": "CUR_TYPE_LCU"},
        "test_countries": ["BRA", "DEU", "FRA", "NGA", "THA"],
    },
    "lfpr": {
        "label":          "Labour Force Participation Rate (LFPR)",
        "keywords":       ["labour force participation", "labor force participation"],
        "base_dims":      {"SEX", "AGE"},
        "extra_key":      {},
        "test_countries": ["BRA", "DEU", "MYS", "NGA", "THA"],
    },
}

# ── catalog ───────────────────────────────────────────────────────────────────

section("CATALOG FETCH")
log("Fetching all ILOSTAT dataflows...")
catalog_msg = client.dataflow()
CATALOG = {str(fid): str(f.name) for fid, f in catalog_msg.dataflow.items()}
log(f"Total dataflows: {len(CATALOG)}")

# ── per-concept analysis ──────────────────────────────────────────────────────

CANONICAL = {}

concept_items = list(CONCEPTS.items())
concept_bar = tqdm(concept_items, desc="Concepts", position=0, leave=True, unit="concept")

for concept_key, cfg in concept_bar:
    concept_bar.set_description(f"Concept: {cfg['label']}")

    section(f"CONCEPT: {cfg['label'].upper()}")

    # ── Step 1: find all matching flows ──────────────────────────────────────
    kws = cfg["keywords"]
    matches = {
        fid: title
        for fid, title in CATALOG.items()
        if any(kw.lower() in title.lower() for kw in kws)
    }

    survey   = {fid: t for fid, t in matches.items() if not is_modelled(fid)}
    modelled = {fid: t for fid, t in matches.items() if is_modelled(fid)}

    log(f"\nKeywords: {kws}")
    log(f"Total matches: {len(matches)}  ({len(survey)} survey, {len(modelled)} modelled)\n")

    # ── Step 2: document EVERY flow ──────────────────────────────────────────
    subsection("ALL FLOWS — MODELLED (discarded: ILO imputed estimates, not real survey data)")
    log(f"  {'ID':<52}  Title")
    log(f"  {'─'*52}  {'─'*50}")
    for fid in sorted(modelled):
        log(f"  {fid:<52}  {modelled[fid]}")

    subsection("ALL FLOWS — SURVEY (evaluated against selection criterion)")
    base = cfg["base_dims"]

    log(f"  Base dims for this concept: {sorted(base)}")
    log(f"  Title exclusions (applied after dim check): {TITLE_EXCLUDE}\n")
    log(f"  {'ID':<52}  {'Extra dims':<28}  Verdict")
    log(f"  {'─'*52}  {'─'*28}  {'─'*40}")

    candidates = []

    for fid in sorted(survey):
        extra = extra_dims(fid, base)
        title = survey[fid]
        title_lower = title.lower()

        if extra:
            verdict = f"DISCARD — subgroup dim(s): {', '.join(extra)}"
        elif any(excl in title_lower for excl in TITLE_EXCLUDE):
            matched = next(excl for excl in TITLE_EXCLUDE if excl in title_lower)
            verdict = f"DISCARD — title: '{matched}'"
        else:
            verdict = "CANDIDATE"
            candidates.append(fid)

        log(f"  {fid:<52}  {', '.join(extra) if extra else '—':<28}  {verdict}")

    log(f"\n  → {len(candidates)} candidate(s) remaining")
    for fid in candidates:
        log(f"     {fid}: {survey.get(fid, CATALOG.get(fid, ''))}")

    if not candidates:
        log("\n  ⚠ NO CANDIDATES — all survey flows discarded.")
        CANONICAL[concept_key] = []
        continue

    # ── Step 3: cross-check + coverage (combined) ─────────────────────────────
    # Coverage is derived from the cross-check: count how many of the 5 test
    # countries return valid data for each candidate. Avoids bulk data pulls
    # that cause 504 timeouts on large flows.

    if len(candidates) == 1:
        # No comparison needed — skip cross-check
        winner = candidates[0]
        subsection("DECISION")
        log(f"  Single candidate: {winner}")
        log(f"  Title: {survey.get(winner, '')}")
        log(f"  Why: only survey flow for this concept with no extra dims and no title exclusions.")
        CANONICAL[concept_key] = [winner]
        continue

    # Multiple candidates — run cross-check
    subsection(f"NUMERICAL CROSS-CHECK — {cfg['test_countries']}")
    log(f"  Filter: SEX_T, AGE_YTHADULT_YGE15, FREQ=A")
    if cfg["extra_key"]:
        log(f"  Extra key filter: {cfg['extra_key']}")
    log("")

    col_w = 22
    header  = f"  {'Country':<8}"
    for fid in candidates:
        short = fid.replace("DF_", "")[:col_w]
        header += f"  {short:<{col_w}}"
    header += "  Verdict"
    log(header)
    log("  " + "─" * max(len(header) - 2, 60))

    # Results store: fid -> count of countries with data (coverage proxy)
    coverage_proxy = {fid: 0 for fid in candidates}

    total_calls = len(candidates) * len(cfg["test_countries"])
    xcheck_bar = tqdm(
        total=total_calls,
        desc="  cross-check calls",
        position=1,
        leave=False,
        unit="call",
    )

    raw_results = {}  # (country, fid) -> (year, val_or_note)
    for country in cfg["test_countries"]:
        for fid in candidates:
            xcheck_bar.set_description(f"  {country} / {fid[-20:]}")
            yr, val = latest_value(fid, country, cfg["extra_key"] or None)
            raw_results[(country, fid)] = (yr, val)
            if isinstance(val, float):
                coverage_proxy[fid] += 1
            xcheck_bar.update(1)

    xcheck_bar.close()

    # Print table
    for country in cfg["test_countries"]:
        row_vals = []
        row_str  = f"  {country:<8}"
        for fid in candidates:
            yr, val = raw_results[(country, fid)]
            cell = f"{val} ({yr})" if isinstance(val, float) else str(val)
            row_str += f"  {cell[:col_w]:<{col_w}}"
            if isinstance(val, float):
                row_vals.append(val)

        non_null = row_vals
        if not non_null:
            verdict = "NO DATA"
        elif len(non_null) == 1:
            verdict = "only 1 candidate has data"
        elif max(non_null) - min(non_null) < 0.1:
            verdict = "~SAME (<0.1 diff)"
        else:
            verdict = f"DIFFER ({min(non_null):.2f}–{max(non_null):.2f})"
        log(row_str + f"  {verdict}")

    log("")
    log("  Coverage proxy (# of 5 test countries returning data):")
    for fid in candidates:
        log(f"    {fid}: {coverage_proxy[fid]}/5")

    # ── Decision ─────────────────────────────────────────────────────────────
    subsection("DECISION")
    winner = max(candidates, key=lambda f: coverage_proxy[f])
    tied   = [f for f in candidates if coverage_proxy[f] == coverage_proxy[winner]]

    if len(tied) > 1:
        log(f"  ⚠ TIE in coverage proxy — manual review needed.")
        log(f"  Tied candidates: {tied}")
        log(f"  Defaulting to first alphabetically: {tied[0]}")
        winner = tied[0]
    else:
        log(f"  Selected: {winner}")
        log(f"  Title: {survey.get(winner, CATALOG.get(winner, ''))}")
        log(f"  Coverage proxy: {coverage_proxy[winner]}/5 test countries returned data")
        others = [f for f in candidates if f != winner]
        if others:
            log(f"  Over: {others} (lower coverage or same numbers)")

    CANONICAL[concept_key] = [winner]


# ── special check 1: youth unemployment age code ──────────────────────────────

section("SPECIAL CHECK 1 — Youth unemployment: does age 15–24 code exist in unemployment flow?")

log("""
No standalone survey flow for youth unemployment exists — all 14 'youth
unemployment' flows are ILO modelled estimates. Approach: filter the canonical
unemployment flow by age 15–24. This check confirms that age code exists.
""")

UNE_FLOW   = "DF_UNE_DEAP_SEX_AGE_RT"
TEST_CNTRY = "BRA"

try:
    msg = client.data(
        UNE_FLOW,
        key={"REF_AREA": TEST_CNTRY},
        params={"startPeriod": "2020", "endPeriod": "2023"},
        dsd=False,
    )
    df = sdmx.to_pandas(msg, attributes="osgd")
    if "AGE" in df.index.names:
        age_codes = sorted(df.index.get_level_values("AGE").unique().tolist())
        log(f"AGE codes in {UNE_FLOW} for {TEST_CNTRY}:")
        for code in age_codes:
            log(f"  {code}")
        youth = [c for c in age_codes if any(x in c for x in ["Y15T24", "YTH", "15-24", "15T24"])]
        log(f"\nLikely youth (15–24) codes: {youth}")
        log("✅ Youth filtering supported." if youth else "⚠ No obvious 15–24 code — check manually.")
    else:
        log(f"AGE not in index: {df.index.names}")
except Exception as e:
    log(f"ERROR: {e}")


# ── special check 2: wages PPP vs LCU ────────────────────────────────────────

section("SPECIAL CHECK 2 — Wages: what CUR variants exist and is PPP worth exposing?")

log("""
Default is LCU (local currency unit) — right for within-country analysis.
PPP normalises across countries but requires a different interpretation.
This check shows what CUR codes exist and how much data each has.
""")

WAGE_FLOW  = "DF_EAR_EMTA_SEX_CUR_NB"
TEST_W     = "FRA"

try:
    msg = client.data(
        WAGE_FLOW,
        key={"REF_AREA": TEST_W},
        params={"startPeriod": "2015", "endPeriod": "2023"},
        dsd=False,
    )
    df = sdmx.to_pandas(msg, attributes="osgd")
    if "CUR" in df.index.names:
        cur_codes = sorted(df.index.get_level_values("CUR").unique().tolist())
        log(f"CUR codes in {WAGE_FLOW} for {TEST_W}: {cur_codes}")
        for cur in cur_codes:
            sub = df[df.index.get_level_values("CUR") == cur]
            if "FREQ" in sub.index.names:
                sub = sub[sub.index.get_level_values("FREQ") == FREQ_ANNUAL]
            if "SEX" in sub.index.names:
                sub = sub[sub.index.get_level_values("SEX") == SEX_TOTAL]
            log(f"  {cur}: {len(sub)} annual rows for {TEST_W}")
    else:
        log(f"CUR not in index: {df.index.names}")
except Exception as e:
    log(f"ERROR: {e}")

log("""
Decision after seeing output:
  - If PPP rows exist and are non-trivial: consider exposing as a second canonical.
  - If sparse or missing: keep LCU only and document why.
""")


# ── final summary ─────────────────────────────────────────────────────────────

section("SUMMARY — CANONICAL FLOWS")

log(f"\n  {'Concept':<40}  {'Selected flow':<52}")
log(f"  {'─'*40}  {'─'*52}")
for concept_key, cfg in CONCEPTS.items():
    label = cfg["label"]
    flows = CANONICAL.get(concept_key, [])
    if not flows:
        log(f"  {label:<40}  NO CANONICAL — needs manual review")
    else:
        for fid in flows:
            log(f"  {label:<40}  {fid}")

log("\nRecord findings in: local-notes/execution/phase00-concept-discovery/results.md")
