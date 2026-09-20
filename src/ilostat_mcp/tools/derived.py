"""Tool handlers for derived statistics: YoY change, CAGR, and trend."""

import time

import structlog

from ilostat_mcp import breaks, telemetry
from ilostat_mcp.analysis import growth
from ilostat_mcp.indicators import is_modelled
from ilostat_mcp.tools.time_series import (
    _detect_gaps,
    _detection_start,
    _extract_unit,
    _fetch_df,
)
from ilostat_mcp.validation import (
    _validate_age_group,
    _validate_country,
    _validate_dataflow,
    _validate_year,
)

logger: structlog.BoundLogger = structlog.get_logger()
_tracer = telemetry.get_tracer(__name__)


def _build_break_warning(
    detected_breaks: list[dict[str, object]], start_year: str, end_year: str
) -> str | None:
    """
    Return a plain-English warning string if any detected break falls in the range.

    Uses detailed source names for a single break; lists years only for multiple.
    Returns None if no breaks fall within [start_year, end_year].
    """
    in_range = breaks.break_years_in_range(detected_breaks, start_year, end_year)
    if not in_range:
        return None
    if len(in_range) == 1:
        b = next(b for b in detected_breaks if str(b["year"]) == in_range[0])
        return (
            f"Methodology break at {in_range[0]}"
            f" (source changed from '{b['source_before']}' to '{b['source_after']}')."
            " Values across this break are not directly comparable"
            " — interpret this result with caution."
        )
    years_str = ", ".join(in_range)
    return (
        f"Methodology break detected within {start_year}-{end_year}"
        f" at year(s): {years_str}."
        " Values across a methodology break are not directly comparable"
        " -- interpret this result with caution."
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
    {_dataflow_id, _is_modelled, _unit_measure, _coverage_start, _coverage_end,
     _breaks, _break_warning, _missing_years, _no_data_reason}
    and result[1] is {year, value, prev_year, prev_value, change_pct}.
    _missing_years lists years in the fetch window with no observation.
    _no_data_reason is set (and result has only 1 element) when the country
    has no data in this dataflow.
    age_group: 'total' (default) or 'youth'.
    """
    t0 = time.perf_counter()
    with _tracer.start_as_current_span("tool.get_yoy_change") as span:
        span.set_attribute("dataflow_id", dataflow_id)
        span.set_attribute("country", country)
        span.set_attribute("year", year)
        span.set_attribute("age_group", age_group)
        try:
            _validate_dataflow(dataflow_id)
            _validate_age_group(age_group)
            _validate_year("year", year, dataflow_id)
            _validate_country(country)

            prev_year = str(int(year) - 1)
            df = _fetch_df(dataflow_id, country, prev_year, year, age_group)
            detected_breaks = breaks.detect_breaks(df)

            if df.empty:
                result: list[dict[str, object]] = [
                    {
                        "_dataflow_id": dataflow_id,
                        "_is_modelled": is_modelled(dataflow_id),
                        "_unit_measure": None,
                        "_coverage_start": None,
                        "_coverage_end": None,
                        "_breaks": [],
                        "_break_warning": None,
                        "_missing_years": [],
                        "_no_data_reason": (
                            f"No data available for {country} in {dataflow_id}."
                        ),
                    }
                ]
            else:
                missing = _detect_gaps(df, prev_year, year)
                warning = _build_break_warning(detected_breaks, prev_year, year)
                try:
                    stat = growth.yoy(df, year)
                except ValueError as exc:
                    gap_info = (
                        f" Missing years in window: {missing}." if missing else ""
                    )
                    raise ValueError(
                        f"Cannot compute year-over-year change for {country}"
                        f" in {dataflow_id}: {exc}{gap_info}"
                    ) from exc
                result = [
                    {
                        "_dataflow_id": dataflow_id,
                        "_is_modelled": is_modelled(dataflow_id),
                        "_unit_measure": _extract_unit(df),
                        "_coverage_start": str(df["time_period"].min()),
                        "_coverage_end": str(df["time_period"].max()),
                        "_breaks": detected_breaks,
                        "_break_warning": warning,
                        "_missing_years": missing,
                        "_no_data_reason": None,
                    },
                    stat,
                ]
            outcome = (
                "empty"
                if len(result) == 1 and result[0].get("_no_data_reason")
                else "success"
            )
            span.set_attribute("outcome", outcome)
            logger.info(
                "tool",
                tool="get_yoy_change",
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
                tool="get_yoy_change",
                dataflow_id=dataflow_id,
                country=country,
                outcome="error",
                duration_ms=int((time.perf_counter() - t0) * 1000),
            )
            raise


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
    {_dataflow_id, _is_modelled, _unit_measure, _coverage_start, _coverage_end,
     _breaks, _break_warning, _missing_years, _no_data_reason}
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
    t0 = time.perf_counter()
    with _tracer.start_as_current_span("tool.get_cagr") as span:
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
            if start_year >= end_year:
                raise ValueError(
                    f"start_year must be strictly before end_year"
                    f" (got {start_year!r} and {end_year!r})"
                )
            _validate_country(country)

            # Fetch one year before start_year so detect_breaks() can see a
            # transition that occurs AT start_year (needs a prior row to
            # compare sources).
            detect_start = _detection_start(start_year, dataflow_id)
            df = _fetch_df(dataflow_id, country, detect_start, end_year, age_group)
            detected_breaks = breaks.detect_breaks(df)

            if df.empty:
                result: list[dict[str, object]] = [
                    {
                        "_dataflow_id": dataflow_id,
                        "_is_modelled": is_modelled(dataflow_id),
                        "_unit_measure": None,
                        "_coverage_start": None,
                        "_coverage_end": None,
                        "_breaks": [],
                        "_break_warning": None,
                        "_missing_years": [],
                        "_no_data_reason": (
                            f"No data available for {country} in {dataflow_id}."
                        ),
                    }
                ]
            else:
                missing = _detect_gaps(df, start_year, end_year)
                warning = _build_break_warning(detected_breaks, start_year, end_year)
                try:
                    stat = growth.cagr(df, start_year, end_year)
                except ValueError as exc:
                    gap_info = f" Missing years in range: {missing}." if missing else ""
                    raise ValueError(
                        f"Cannot compute CAGR for {country} in"
                        f" {dataflow_id}: {exc}{gap_info}"
                    ) from exc
                result = [
                    {
                        "_dataflow_id": dataflow_id,
                        "_is_modelled": is_modelled(dataflow_id),
                        "_unit_measure": _extract_unit(df),
                        "_coverage_start": str(df["time_period"].min()),
                        "_coverage_end": str(df["time_period"].max()),
                        "_breaks": detected_breaks,
                        "_break_warning": warning,
                        "_missing_years": missing,
                        "_no_data_reason": None,
                    },
                    stat,
                ]
            outcome = (
                "empty"
                if len(result) == 1 and result[0].get("_no_data_reason")
                else "success"
            )
            span.set_attribute("outcome", outcome)
            logger.info(
                "tool",
                tool="get_cagr",
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
                tool="get_cagr",
                dataflow_id=dataflow_id,
                country=country,
                outcome="error",
                duration_ms=int((time.perf_counter() - t0) * 1000),
            )
            raise


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
    {_dataflow_id, _is_modelled, _unit_measure, _coverage_start, _coverage_end,
     _breaks, _break_warning, _missing_years, _no_data_reason}
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
    t0 = time.perf_counter()
    with _tracer.start_as_current_span("tool.get_trend") as span:
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
            if start_year >= end_year:
                raise ValueError(
                    f"start_year must be strictly before end_year"
                    f" (got {start_year!r} and {end_year!r})"
                )
            _validate_country(country)

            # Fetch one year before start_year so detect_breaks() can see a
            # transition that occurs AT start_year (needs a prior row to
            # compare sources).
            detect_start = _detection_start(start_year, dataflow_id)
            df = _fetch_df(dataflow_id, country, detect_start, end_year, age_group)
            detected_breaks = breaks.detect_breaks(df)

            if df.empty:
                result: list[dict[str, object]] = [
                    {
                        "_dataflow_id": dataflow_id,
                        "_is_modelled": is_modelled(dataflow_id),
                        "_unit_measure": None,
                        "_coverage_start": None,
                        "_coverage_end": None,
                        "_breaks": [],
                        "_break_warning": None,
                        "_missing_years": [],
                        "_no_data_reason": (
                            f"No data available for {country} in {dataflow_id}."
                        ),
                    }
                ]
            else:
                missing = _detect_gaps(df, start_year, end_year)
                warning = _build_break_warning(detected_breaks, start_year, end_year)
                try:
                    stat = growth.trend(df, start_year, end_year)
                except ValueError as exc:
                    gap_info = f" Missing years in range: {missing}." if missing else ""
                    raise ValueError(
                        f"Cannot compute trend for {country} in"
                        f" {dataflow_id}: {exc}{gap_info}"
                    ) from exc
                result = [
                    {
                        "_dataflow_id": dataflow_id,
                        "_is_modelled": is_modelled(dataflow_id),
                        "_unit_measure": _extract_unit(df),
                        "_coverage_start": str(df["time_period"].min()),
                        "_coverage_end": str(df["time_period"].max()),
                        "_breaks": detected_breaks,
                        "_break_warning": warning,
                        "_missing_years": missing,
                        "_no_data_reason": None,
                    },
                    stat,
                ]
            outcome = (
                "empty"
                if len(result) == 1 and result[0].get("_no_data_reason")
                else "success"
            )
            span.set_attribute("outcome", outcome)
            logger.info(
                "tool",
                tool="get_trend",
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
                tool="get_trend",
                dataflow_id=dataflow_id,
                country=country,
                outcome="error",
                duration_ms=int((time.perf_counter() - t0) * 1000),
            )
            raise
