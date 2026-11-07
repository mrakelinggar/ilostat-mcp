"""
Shared helpers for tools that fetch a time series and describe it.

Series are cached: the first request for a (flow, country, age group) fetches
its full history, and every later request — whatever the years, whichever
tool — is cut from that copy. Entries live 24 hours ("no data" results 1 hour),
at most _MAX_SERIES are kept, and when the flow catalogue is in memory the key
includes the flow's LAST_UPDATE, so a newer ILOSTAT release is never hidden
behind an old copy.
"""

from datetime import date

import pandas as pd

from ilostat_mcp import resources, sdmx_client
from ilostat_mcp.cache import SECONDS_PER_DAY, SECONDS_PER_HOUR, TTLCache
from ilostat_mcp.indicators import FLOW_SPECS, currency_for, is_modelled

_YOUTH = "youth"
_MAX_SERIES = 500  # ~10 KB each (43-year series) -> ~5 MB worst case
_NO_DATA_TTL_SECONDS = SECONDS_PER_HOUR  # a wrong "no data" must not stick around

# (dataflow_id, country, age_group, flow's last_updated or None) -> full history
SeriesKey = tuple[str, str, str, str | None]
_series: TTLCache[SeriesKey, pd.DataFrame] = TTLCache(
    ttl_seconds=SECONDS_PER_DAY, max_entries=_MAX_SERIES
)


def _series_ttl(df: pd.DataFrame) -> float:
    """Cache "no data" results for an hour, real series for a day."""
    return _NO_DATA_TTL_SECONDS if df.empty else SECONDS_PER_DAY


def _fetch_full_history(dataflow_id: str, country: str, age_group: str) -> pd.DataFrame:
    """Fetch every year of one series from ILOSTAT and check it is one row per year."""
    spec = FLOW_SPECS[dataflow_id]
    df = sdmx_client.get_time_series(
        dataflow_id,
        country,
        str(spec.min_year),
        str(date.today().year),
        dims=spec.sdmx_key(age_group),
    )
    if not df.empty and df["time_period"].duplicated().any():
        raise RuntimeError(
            f"ILOSTAT returned several rows per year for {dataflow_id}, so the"
            " values would mix different groups. This flow needs an extra"
            " filter before it can be used — please report this."
        )
    return df


def fetch_series(
    dataflow_id: str, country: str, start: str, end: str, age_group: str
) -> pd.DataFrame:
    """
    Return one annual series (one row per year) for [start, end].

    For a validated flow, country and age group. Served from the series cache
    when possible; otherwise fetches the full history from ILOSTAT and caches
    it. The flow's FlowSpec decides which dimension values are sent, so the
    response is a single series rather than a mix of breakdowns.

    Returns an empty DataFrame if ILOSTAT has no data in that range.

    Raises
    ------
    RuntimeError if the API call fails, or if ILOSTAT returns more than one row
    for a year — that means the flow has a breakdown FLOW_SPECS does not pin
    down, and any stat computed from it would silently mix groups.
    """
    key: SeriesKey = (
        dataflow_id,
        country,
        age_group,
        resources.known_last_updated(dataflow_id),
    )
    history = _series.get_or_fetch(
        key,
        lambda: _fetch_full_history(dataflow_id, country, age_group),
        ttl_for=_series_ttl,
    )
    if history.empty:
        return history
    in_range = (history["time_period"] >= start) & (history["time_period"] <= end)
    return history[in_range].reset_index(drop=True)


def detection_start(start_year: str, dataflow_id: str) -> str:
    """
    Return the fetch start year to use for break detection.

    One year before start_year, clamped to the flow's minimum year. The extra
    year lets detect_breaks() compare sources for a change that happens AT
    start_year — without a prior row there is nothing to compare against.
    """
    return str(max(FLOW_SPECS[dataflow_id].min_year, int(start_year) - 1))


def missing_years(df: pd.DataFrame, start_year: str, end_year: str) -> list[str]:
    """
    Return years in [start_year, end_year] with no observation in df.

    Returns [] for an empty DataFrame — that is "no data at all", not a gap.
    """
    if df.empty:
        return []
    present = set(df["time_period"])
    return [
        str(y)
        for y in range(int(start_year), int(end_year) + 1)
        if str(y) not in present
    ]


def no_data_reason(dataflow_id: str, country: str, age_group: str) -> str:
    """Return the plain-English explanation used when a series is empty."""
    reason = f"No data available for {country} in {dataflow_id}."
    if age_group == _YOUTH:
        reason += (
            " This flow may not have youth age codes for this country."
            " Use search_indicators('youth unemployment') to find a"
            " youth-specific dataflow."
        )
    return reason


def _unit(df: pd.DataFrame) -> str | None:
    """Return the unit_measure from the first non-null row, or None."""
    if "unit_measure" not in df.columns:
        return None
    units = df["unit_measure"].dropna()
    return str(units.iloc[0]) if not units.empty else None


def series_meta(
    df: pd.DataFrame,
    dataflow_id: str,
    country: str,
    age_group: str,
    detected_breaks: list[dict[str, object]],
    missing: list[str],
) -> dict[str, object]:
    """
    Build the metadata dict returned as result[0] by every series tool.

    Keys: _dataflow_id, _is_modelled, _unit_measure, _currency_code,
    _coverage_start, _coverage_end, _breaks, _missing_years, _no_data_reason.
    For an empty df the coverage and unit fields are None and _no_data_reason
    explains why; otherwise _no_data_reason is None.
    """
    empty = df.empty
    return {
        "_dataflow_id": dataflow_id,
        "_is_modelled": is_modelled(dataflow_id),
        "_unit_measure": None if empty else _unit(df),
        "_currency_code": currency_for(dataflow_id, country),
        "_coverage_start": None if empty else str(df["time_period"].min()),
        "_coverage_end": None if empty else str(df["time_period"].max()),
        "_breaks": detected_breaks,
        "_missing_years": missing,
        "_no_data_reason": (
            no_data_reason(dataflow_id, country, age_group) if empty else None
        ),
    }
