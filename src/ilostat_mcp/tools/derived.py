"""Tool handlers for derived statistics: YoY change, CAGR, and trend."""

from collections.abc import Callable

import pandas as pd

from ilostat_mcp import breaks, validation
from ilostat_mcp.analysis import growth
from ilostat_mcp.tools import series

# A pure stat function from analysis.growth, bound to its years.
StatFn = Callable[[pd.DataFrame], dict[str, object]]


def _derived_result(
    df: pd.DataFrame,
    dataflow_id: str,
    country: str,
    age_group: str,
    range_start: str,
    range_end: str,
    stat_name: str,
    stat_fn: StatFn,
) -> list[dict[str, object]]:
    """
    Build [metadata, stat] for a derived-stat tool, or [metadata] if no data.

    Metadata is series_meta() plus _break_warning, which is set when a
    methodology break falls inside [range_start, range_end].

    Raises ValueError with a plain-English message if the stat cannot be
    computed (e.g. a boundary year is missing).
    """
    detected = breaks.detect_breaks(df)
    missing = series.missing_years(df, range_start, range_end)
    meta = series.series_meta(df, dataflow_id, country, age_group, detected, missing)
    meta["_break_warning"] = breaks.break_warning(detected, range_start, range_end)
    if df.empty:
        return [meta]
    try:
        stat = stat_fn(df)
    except ValueError as exc:
        gap_info = f" Missing years in range: {missing}." if missing else ""
        raise ValueError(
            f"Cannot compute {stat_name} for {country} in {dataflow_id}:"
            f" {exc}{gap_info}"
        ) from exc
    return [meta, stat]


def _range_stat(
    dataflow_id: str,
    country: str,
    start_year: str,
    end_year: str,
    age_group: str,
    stat_name: str,
    stat_fn: StatFn,
) -> list[dict[str, object]]:
    """Validate, fetch and compute a stat over [start_year, end_year] (CAGR, trend)."""
    validation.validate_dataflow(dataflow_id)
    validation.validate_age_group(age_group)
    validation.validate_year_range(start_year, end_year, dataflow_id, strict=True)
    validation.validate_country(country)

    fetch_start = series.detection_start(start_year, dataflow_id)
    df = series.fetch_series(dataflow_id, country, fetch_start, end_year, age_group)
    return _derived_result(
        df, dataflow_id, country, age_group, start_year, end_year, stat_name, stat_fn
    )


def get_yoy_change(
    dataflow_id: str,
    country: str,
    year: str,
    age_group: str = "total",
) -> list[dict[str, object]]:
    """
    Year-over-year percentage change for a single year.
    Compares the value at `year` to `year - 1`.
    Returns a list where result[0] is metadata:
    {_dataflow_id, _is_modelled, _unit_measure, _currency_code, _coverage_start,
     _coverage_end, _breaks, _break_warning, _missing_years, _no_data_reason}
    and result[1] is {year, value, prev_year, prev_value, change_pct}.
    _missing_years lists years in the fetch window with no observation.
    _no_data_reason is set (and result has only 1 element) when the country
    has no data in this dataflow.
    age_group: 'total' (default) or 'youth'.
    """
    validation.validate_dataflow(dataflow_id)
    validation.validate_age_group(age_group)
    validation.validate_year("year", year, dataflow_id)
    validation.validate_country(country)

    prev_year = str(int(year) - 1)
    df = series.fetch_series(dataflow_id, country, prev_year, year, age_group)
    return _derived_result(
        df,
        dataflow_id,
        country,
        age_group,
        prev_year,
        year,
        "year-over-year change",
        lambda d: growth.yoy(d, year),
    )


def get_cagr(
    dataflow_id: str,
    country: str,
    start_year: str,
    end_year: str,
    age_group: str = "total",
) -> list[dict[str, object]]:
    """
    Compound annual growth rate (CAGR) between start_year and end_year.
    Returns a list where result[0] is metadata:
    {_dataflow_id, _is_modelled, _unit_measure, _currency_code, _coverage_start,
     _coverage_end, _breaks, _break_warning, _missing_years, _no_data_reason}
    and result[1] is
    {start_year, end_year, start_value, end_value, cagr_pct, n_years}.
    A _break_warning is set if any methodology break falls within the range
    -- CAGR across a break is unreliable.
    _missing_years lists years in the range with no observation.
    _no_data_reason is set (and result has only 1 element) when the country
    has no data in this dataflow.
    start_year must be strictly before end_year.
    age_group: 'total' (default) or 'youth'.
    """
    return _range_stat(
        dataflow_id,
        country,
        start_year,
        end_year,
        age_group,
        "CAGR",
        lambda d: growth.cagr(d, start_year, end_year),
    )


def get_trend(
    dataflow_id: str,
    country: str,
    start_year: str,
    end_year: str,
    age_group: str = "total",
) -> list[dict[str, object]]:
    """
    OLS linear trend between start_year and end_year.
    Returns a list where result[0] is metadata:
    {_dataflow_id, _is_modelled, _unit_measure, _currency_code, _coverage_start,
     _coverage_end, _breaks, _break_warning, _missing_years, _no_data_reason}
    and result[1] is
    {start_year, end_year, slope, intercept, r_squared, n_points}.
    A _break_warning is set if any methodology break falls within the range
    -- a trend across a break is unreliable.
    _missing_years lists years in the range with no observation.
    _no_data_reason is set (and result has only 1 element) when the country
    has no data in this dataflow.
    start_year must be strictly before end_year.
    age_group: 'total' (default) or 'youth'.
    """
    return _range_stat(
        dataflow_id,
        country,
        start_year,
        end_year,
        age_group,
        "trend",
        lambda d: growth.trend(d, start_year, end_year),
    )
