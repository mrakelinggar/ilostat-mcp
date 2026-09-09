"""Tool handler for raw time-series fetching, plus shared fetch helpers."""

import time
from typing import cast

import pandas as pd
import structlog

from ilostat_mcp import breaks, sdmx_client, telemetry
from ilostat_mcp.indicators import CUR_DEFAULT, FLOW_DIMS, FLOW_MIN_YEARS
from ilostat_mcp.validation import (
    _AGE_GROUP_MAP,
    _validate_age_group,
    _validate_country,
    _validate_dataflow,
    _validate_year,
)

logger: structlog.BoundLogger = structlog.get_logger()
_tracer = telemetry.get_tracer(__name__)


# ── Shared helpers (also imported by tools/derived.py) ────────────────────────


def _detect_gaps(df: pd.DataFrame, start_year: str, end_year: str) -> list[str]:
    """
    Return years in [start_year, end_year] absent from the DataFrame.

    Compares the expected annual sequence against the time_period values actually
    returned by ILOSTAT. Years with no observation are returned as strings so
    the caller can include them in the metadata dict alongside _breaks.
    Returns an empty list for an empty DataFrame (no data at all, not a gap).
    """
    if df.empty:
        return []
    present = set(df["time_period"].astype(str).unique())
    expected = [str(y) for y in range(int(start_year), int(end_year) + 1)]
    return [y for y in expected if y not in present]


def _detection_start(start_year: str, dataflow_id: str) -> str:
    """
    Return the fetch start year to use for break detection.

    One year before start_year, clamped to the flow's minimum year.
    Fetching an extra year before the requested range lets detect_breaks()
    see a source transition that occurs AT start_year — without a prior row
    there is no previous source to compare against, so the break is silently
    missed.
    """
    min_year = FLOW_MIN_YEARS.get(dataflow_id, 1900)
    return str(max(min_year, int(start_year) - 1))


def _fetch_df(
    dataflow_id: str, country: str, start: str, end: str, age_group: str
) -> pd.DataFrame:
    """
    Fetch a time series DataFrame via sdmx_client, resolving flow dimensions.

    Looks up the flow's dimension type in FLOW_DIMS to inject the correct
    age/cur/geo parameter. Returns an empty DataFrame if no data exists.
    """
    flow_info = FLOW_DIMS.get(dataflow_id, {})
    dim = flow_info.get("dim")
    age = _AGE_GROUP_MAP[age_group] if dim == "age" else None
    cur = CUR_DEFAULT if dim == "cur" else None
    geo = flow_info.get("GEO")
    return sdmx_client.get_time_series(
        dataflow_id, country, start, end, age=age, cur=cur, geo=geo
    )


# ── Tool handler ──────────────────────────────────────────────────────────────


def get_time_series(
    dataflow_id: str,
    country: str,
    start_year: str,
    end_year: str,
    age_group: str = "total",
) -> list[dict[str, object]]:
    """
    Fetch a time series from ILOSTAT. Returns a list where the FIRST element
    is series metadata: {_breaks, _missing_years, _no_data_reason}.
    _breaks lists methodology breaks (each: {year, source_before, source_after};
    empty if none). _missing_years lists years in the requested range with no
    observation (gaps in ILOSTAT's data, not errors). _no_data_reason is set
    when the country has no data at all in this dataflow.
    Remaining elements are annual observations: time_period, value, obs_status,
    source, unit_measure.
    Do not compute multi-year trends across a break without flagging it.
    age_group: 'total' (default, adults 15+) or 'youth' (15-29); ignored
    for wage flows.
    """
    t0 = time.perf_counter()
    with _tracer.start_as_current_span("tool.get_time_series") as span:
        span.set_attribute("dataflow_id", dataflow_id)
        span.set_attribute("country", country)
        span.set_attribute("start_year", start_year)
        span.set_attribute("end_year", end_year)
        span.set_attribute("age_group", age_group)
        try:
            _validate_dataflow(dataflow_id)
            _validate_age_group(age_group)
            _validate_year("start_year", start_year, dataflow_id)
            _validate_year("end_year", end_year, dataflow_id)
            if start_year > end_year:
                raise ValueError(
                    f"start_year must be <= end_year (got {start_year} to {end_year})"
                )
            _validate_country(country)
            df = _fetch_df(dataflow_id, country, start_year, end_year, age_group)
            detected_breaks: list[dict[str, object]] = breaks.detect_breaks(df)
            if df.empty:
                result: list[dict[str, object]] = [
                    {
                        "_breaks": detected_breaks,
                        "_missing_years": [],
                        "_no_data_reason": (
                            f"No data available for {country} in {dataflow_id}."
                        ),
                    }
                ]
            else:
                missing = _detect_gaps(df, start_year, end_year)
                rows = cast(list[dict[str, object]], df.to_dict(orient="records"))
                meta: dict[str, object] = {
                    "_breaks": detected_breaks,
                    "_missing_years": missing,
                    "_no_data_reason": None,
                }
                result = [meta, *rows]
            outcome = (
                "empty"
                if len(result) == 1 and result[0].get("_no_data_reason")
                else "success"
            )
            span.set_attribute("outcome", outcome)
            logger.info(
                "tool",
                tool="get_time_series",
                dataflow_id=dataflow_id,
                country=country,
                outcome=outcome,
                duration_ms=int((time.perf_counter() - t0) * 1000),
            )
            return result
        except (ValueError, RuntimeError) as exc:
            span.set_attribute("outcome", "error")
            span.set_attribute("error.message", str(exc))
            logger.info(
                "tool",
                tool="get_time_series",
                dataflow_id=dataflow_id,
                country=country,
                outcome="error",
                duration_ms=int((time.perf_counter() - t0) * 1000),
            )
            raise
