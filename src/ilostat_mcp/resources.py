"""
System-prompt resource and module-level country cache.

The countries cache avoids hitting the ILOSTAT API on every get_countries()
call — it populates once per process and stays for the session.
"""

from ilostat_mcp import sdmx_client
from ilostat_mcp.indicators import FLOWS

# The four canonical flows for v1, exposed as a resource so the agent knows
# which dataflow IDs to use for common themes without having to call search_indicators.
# Titles are the official ILOSTAT names (verified against live API, Phase 0).
CANONICAL_FLOWS: list[dict[str, str]] = [
    {
        "theme": "unemployment_rate",
        "dataflow_id": FLOWS["unemployment_rate"],
        "title": "Unemployment rate by sex and age",
    },
    {
        "theme": "employment_to_pop",
        "dataflow_id": FLOWS["employment_to_pop"],
        "title": "Employment-to-population ratio by sex and age",
    },
    {
        "theme": "wages",
        "dataflow_id": FLOWS["wages"],
        "title": "Average monthly earnings of employees by sex and currency",
    },
    {
        "theme": "lfpr",
        "dataflow_id": FLOWS["lfpr"],
        "title": "Labour force participation rate by sex and age",
    },
]

_countries_cache: list[dict[str, str]] | None = None


def get_cached_countries() -> list[dict[str, str]]:
    """Return CL_AREA country list, cached for the lifetime of the process."""
    global _countries_cache
    if _countries_cache is None:
        _countries_cache = sdmx_client.get_countries()
    return _countries_cache


# ── Resource handler functions (registered in server.py) ─────────────────────


def get_system_prompt() -> str:
    """Return the ILOSTAT MCP system prompt."""
    return SYSTEM_PROMPT


def get_codelist_area() -> list[dict[str, str]]:
    """All valid ILOSTAT country/area codes from CL_AREA."""
    return get_cached_countries()


def get_codelist_indicator() -> list[dict[str, str]]:
    """The four canonical v1 dataflows — theme, dataflow_id, title."""
    return CANONICAL_FLOWS


SYSTEM_PROMPT = """\
You have access to ILOSTAT — the ILO's official labour statistics database.
It holds country-level employment and wage data sourced from national surveys.

## What this server covers (v1)
Unemployment rate, employment-to-population ratio, labour force participation rate,
and average wages (in local currency). Country-level only — no EU, ASEAN, or other
regional aggregates.

## Call order — never skip steps
1. search_indicators(keyword) — find the right dataflow ID
2. get_indicator_metadata(dataflow_id) — confirm units and last-update date (optional
   for flows you already know)
3. get_time_series(dataflow_id, country, start_year, end_year) — fetch the numbers
4. Apply derived stats if the user asked for a trend or change rate

## Reading tool responses
Every data response returns a metadata object as its first element:

- **_is_modelled**: true = ILO modelled estimate, not survey data. Always flag this.
- **_unit_measure**: unit of the values (e.g. "%", "EUR"). State it in every response.
- **_currency_code**: ISO currency for wage flows (e.g. "THB", "NGN"). Name the currency
  explicitly in all wage responses; for cross-country comparisons, state both currencies
  before drawing conclusions — FX movements can flip the winner.
- **_coverage_end**: latest year available. Always state "data through [year]";
  if earlier than requested, explain the gap.
- **_coverage_start** / **_missing_years**: explain if the user's range isn't
  fully covered.

## Rules
- Never answer from training knowledge. No data → say so, do not invent numbers.
- Resolve country ambiguity before calling any tool. "Korea" → ask which one.
- Prefer survey flows (is_modelled: false). When multiple flows match, prefer the most
  current ICLS standard.
- Wages are in local currency by default. Do not convert unless asked.
- obs_status "B" = methodology break. Never state a trend across a break without
  flagging it.
- For youth unemployment, age_group='youth' only works in flows with youth age codes. If
  it returns empty, use search_indicators('youth unemployment') to find the right flow
  (e.g. DF_UNE_3EAP_SEX_AGE_GEO_RT).
- If a result diverges from a manual ILOSTAT Data Explorer check, the most likely causes
  are: different age/sex filter, a currency view mismatch, or a different ICLS-standard
  flow selected in the Data Explorer. Check these before assuming a connector error.
- For CAGR and trend answers, always state both endpoints:
  "4.2% CAGR from 2015 to 2022".
"""
