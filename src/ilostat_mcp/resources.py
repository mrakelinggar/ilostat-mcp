"""
System-prompt resource and the reference-data caches.

ILOSTAT's dataflow catalogue and country list change rarely, so each is
fetched once and kept in memory for 24 hours (see cache.TTLCache). Observation
data is cached separately, in tools/series.py.
"""

from ilostat_mcp import sdmx_client
from ilostat_mcp.cache import SECONDS_PER_DAY, TTLCache
from ilostat_mcp.indicators import FLOW_SPECS
from ilostat_mcp.sdmx_client import FlowInfo

# The four canonical flows for v1, exposed as a resource so the agent knows
# which dataflow IDs to use for common themes without calling search_indicators.
CANONICAL_FLOWS: list[dict[str, str]] = [
    {"theme": spec.theme, "dataflow_id": flow_id, "title": spec.title}
    for flow_id, spec in FLOW_SPECS.items()
    if spec.theme and spec.title
]

# Each of these caches holds a single entry (the whole list), under _ALL.
_ALL = "all"
_catalogue: TTLCache[str, dict[str, FlowInfo]] = TTLCache(
    ttl_seconds=SECONDS_PER_DAY, max_entries=1
)
_countries: TTLCache[str, list[dict[str, str]]] = TTLCache(
    ttl_seconds=SECONDS_PER_DAY, max_entries=1
)


def get_catalogue() -> dict[str, FlowInfo]:
    """
    Return ILOSTAT's dataflow catalogue (flow ID -> FlowInfo, in ORDER rank).

    Downloaded on first use and refreshed after 24 hours.
    Raises RuntimeError (plain English) if the download fails.
    """
    return _catalogue.get_or_fetch(_ALL, sdmx_client.get_catalogue)


def known_last_updated(flow_id: str) -> str | None:
    """
    Return a flow's last_updated if the catalogue is already in memory.

    Never downloads anything: returns None when the catalogue is not cached,
    so data calls do not pay the catalogue's download time.
    """
    catalogue = _catalogue.peek(_ALL)
    flow = catalogue.get(flow_id) if catalogue is not None else None
    return flow.last_updated if flow is not None else None


def get_cached_countries() -> list[dict[str, str]]:
    """
    Return the CL_AREA country list ({code, name}), refreshed after 24 hours.

    Raises RuntimeError (plain English) if the download fails.
    """
    return _countries.get_or_fetch(_ALL, sdmx_client.get_countries)


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
- **_breaks** lists methodology breaks: years where the survey changed or was
  redesigned, so values before and after are not directly comparable. Each has
  `reasons`: "ilostat_break_flag" (ILOSTAT marked it, obs_status "B") and/or
  "source_change" (the survey source changed). Never state a trend across a
  break without flagging it.
- For youth unemployment, age_group='youth' only works in flows with youth age codes. If
  it returns empty, use search_indicators('youth unemployment') to find the right flow
  (e.g. DF_UNE_3EAP_SEX_AGE_GEO_RT).
- If a result diverges from a manual ILOSTAT Data Explorer check, the most likely causes
  are: different age/sex filter, a currency view mismatch, or a different ICLS-standard
  flow selected in the Data Explorer. Check these before assuming a connector error.
- For CAGR and trend answers, always state both endpoints:
  "4.2% CAGR from 2015 to 2022".
"""
