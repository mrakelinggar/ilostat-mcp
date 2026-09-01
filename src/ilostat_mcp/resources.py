"""
System-prompt resource and module-level country cache.

The countries cache avoids hitting the ILOSTAT API on every get_countries()
call — it populates once per process and stays for the session.
"""

from ilostat_mcp import sdmx_client

_countries_cache: list[dict[str, str]] | None = None


def get_cached_countries() -> list[dict[str, str]]:
    """Return CL_AREA country list, cached for the lifetime of the process."""
    global _countries_cache
    if _countries_cache is None:
        _countries_cache = sdmx_client.get_countries()
    return _countries_cache


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

## Rules
- Never answer a labour statistics question from training knowledge. If a tool
  returns no data, say so — do not invent numbers.
- Resolve country ambiguity before calling any tool. "Korea" → ask which one.
- Prefer flows where is_modelled is false (survey data). If you must use a modelled
  estimate, say so explicitly.
- Wages are in local currency units (LCU). Do not convert unless asked.
- In time-series results, obs_status "B" means a methodology break at that point.
  Do not state a multi-year trend that spans a break without flagging it.
"""
