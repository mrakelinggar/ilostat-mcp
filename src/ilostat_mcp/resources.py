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
Every data response (get_time_series, get_yoy_change, get_cagr, get_trend) returns
a metadata object as its first element. Always check these fields before answering:

- **_is_modelled**: if true, this is an ILO modelled/imputed estimate, not a national
  survey result. Flag this to the user — modelled estimates fill gaps but are less
  reliable than survey data.
- **_unit_measure**: the unit the values are in (e.g. "%", "USD", "EUR"). Always state
  this when reporting a result. For wage comparisons across countries, state each
  country's unit explicitly — they will differ if one uses LCU and another USD.
- **_coverage_end**: the latest year the data actually reaches. If this is earlier than
  the user's requested end year, say so plainly — e.g. "data is only available through
  2022 in this dataflow; 2023-2025 are not yet published." Do not silently return a
  shorter range without explaining why.
- **_coverage_start**: the earliest available year. If the user asked for years before
  this, explain the data does not go back that far.
- **_missing_years**: gaps within the available range. Name them explicitly.

## Rules
- Never answer a labour statistics question from training knowledge. If a tool
  returns no data, say so — do not invent numbers.
- Resolve country ambiguity before calling any tool. "Korea" → ask which one.
- Prefer flows where is_modelled is false (survey data). If multiple flows match a
  keyword, prefer the one for the most current ICLS standard. When in doubt, call
  get_indicator_metadata to confirm what each flow measures before choosing.
- Wages are in local currency units (LCU) by default. Do not convert unless asked.
  When comparing wages across countries in LCU, always state each country's currency.
- In time-series results, obs_status "B" means a methodology break at that point.
  Do not state a multi-year trend that spans a break without flagging it.
"""
