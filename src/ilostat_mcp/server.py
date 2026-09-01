"""
FastMCP server — tool and resource registration only.

All business logic lives in sdmx_client.py, resources.py, breaks.py,
and analysis/. This file registers tools, prompts, and wires entry points.
"""

from typing import cast

import pandas as pd
from fastmcp import FastMCP

from ilostat_mcp import breaks, resources, sdmx_client
from ilostat_mcp.analysis import growth
from ilostat_mcp.indicators import AGE_TOTAL, AGE_YOUTH, CUR_DEFAULT, FLOW_DIMS

mcp = FastMCP("ilostat-mcp")


# ── Resources ─────────────────────────────────────────────────────────────────


@mcp.resource("ilostat://system-prompt")
def system_prompt() -> str:
    return resources.SYSTEM_PROMPT


@mcp.resource("ilostat://codelists/area")
def codelist_area() -> list[dict[str, str]]:
    """All valid ILOSTAT country/area codes from CL_AREA."""
    return resources.get_cached_countries()


@mcp.resource("ilostat://codelists/indicator")
def codelist_indicator() -> list[dict[str, str]]:
    """The four canonical v1 dataflows — theme, dataflow_id, title."""
    return resources.CANONICAL_FLOWS


# ── Shared validation helpers ─────────────────────────────────────────────────


_AGE_GROUP_MAP: dict[str, str] = {
    "total": AGE_TOTAL,  # adults 15+
    "youth": AGE_YOUTH,  # youth 15-29
}


def _validate_age_group(age_group: str) -> None:
    """Raise ValueError if age_group is not a recognised value."""
    if age_group not in _AGE_GROUP_MAP:
        raise ValueError(f"age_group must be 'total' or 'youth' (got {age_group!r})")


def _validate_year(label: str, year: str) -> None:
    """Raise ValueError if year is not a 4-digit numeric string."""
    if not (year.isdigit() and len(year) == 4):
        raise ValueError(f"{label} must be a 4-digit year (got {year!r})")


def _validate_country(country: str) -> None:
    """Raise ValueError if country is not a valid ILOSTAT area code."""
    valid_codes = {c["code"] for c in resources.get_cached_countries()}
    if country not in valid_codes:
        raise ValueError(
            f"Unknown country code {country!r}."
            " Use get_countries() to find valid codes."
        )


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


# ── Tools ─────────────────────────────────────────────────────────────────────


@mcp.tool(
    description=(
        "Search ILOSTAT dataflows by keyword. Returns up to 20 matches with their "
        "dataflow ID, title, and whether the series is an ILO modelled estimate "
        "(is_modelled: true) or survey data (is_modelled: false). Use the dataflow "
        "ID in subsequent calls. Prefer survey data (is_modelled: false)."
    )
)
def search_indicators(keyword: str) -> list[dict[str, object]]:
    return sdmx_client.search_indicators(keyword)


@mcp.tool(
    description=(
        "List all valid country codes from ILOSTAT's CL_AREA codelist. "
        "Returns [{code, name}]. Use these codes in get_time_series."
    )
)
def get_countries() -> list[dict[str, str]]:
    return resources.get_cached_countries()


@mcp.tool(
    description=(
        "Return metadata for a dataflow: title, plain-English description, "
        "last_updated date, and whether it is a modelled estimate. "
        "Returns an empty dict if the dataflow ID does not exist."
    )
)
def get_indicator_metadata(dataflow_id: str) -> dict[str, object]:
    return sdmx_client.get_indicator_metadata(dataflow_id)


@mcp.tool(
    description=(
        "Fetch a time series from ILOSTAT. Returns a list where the FIRST element "
        "is series metadata: {_breaks: [...]} listing methodology breaks detected "
        "(each break: {year, source_before, source_after}; empty list if none). "
        "Remaining elements are annual observations with columns: time_period, "
        "value, obs_status, source, unit_measure. "
        "Do not compute multi-year trends across a break without flagging it. "
        "age_group: 'total' (default, adults 15+) or 'youth' (15-29); ignored "
        "for wage flows. Returns [{_breaks: []}] if country has no data."
    )
)
def get_time_series(
    dataflow_id: str,
    country: str,
    start_year: str,
    end_year: str,
    age_group: str = "total",
) -> list[dict[str, object]]:
    _validate_age_group(age_group)
    _validate_year("start_year", start_year)
    _validate_year("end_year", end_year)
    if start_year > end_year:
        raise ValueError(
            f"start_year must be <= end_year (got {start_year} to {end_year})"
        )
    _validate_country(country)
    df = _fetch_df(dataflow_id, country, start_year, end_year, age_group)
    detected_breaks: list[dict[str, object]] = breaks.detect_breaks(df)
    if df.empty:
        return [{"_breaks": detected_breaks}]
    rows = cast(list[dict[str, object]], df.to_dict(orient="records"))
    return [{"_breaks": detected_breaks}, *rows]


@mcp.tool(
    description=(
        "Year-over-year percentage change for a single year. "
        "Compares the value at `year` to `year - 1`. "
        "Returns a list where result[0] is metadata: {_breaks, _break_warning} "
        "and result[1] is {year, value, prev_year, prev_value, change_pct}. "
        "Returns [{_breaks: [], _break_warning: null}] if no data. "
        "age_group: 'total' (default) or 'youth'."
    )
)
def get_yoy_change(
    dataflow_id: str,
    country: str,
    year: str,
    age_group: str = "total",
) -> list[dict[str, object]]:
    _validate_age_group(age_group)
    _validate_year("year", year)
    _validate_country(country)

    prev_year = str(int(year) - 1)
    df = _fetch_df(dataflow_id, country, prev_year, year, age_group)
    detected_breaks = breaks.detect_breaks(df)

    if df.empty:
        return [{"_breaks": [], "_break_warning": None}]

    warning = _build_break_warning(detected_breaks, prev_year, year)
    stat = growth.yoy(df, year)
    return [{"_breaks": detected_breaks, "_break_warning": warning}, stat]


@mcp.tool(
    description=(
        "Compound annual growth rate (CAGR) between start_year and end_year. "
        "Returns a list where result[0] is metadata: {_breaks, _break_warning} "
        "and result[1] is "
        "{start_year, end_year, start_value, end_value, cagr_pct, n_years}. "
        "A _break_warning is set if any methodology break falls within the range "
        "-- CAGR across a break is unreliable. "
        "Returns [{_breaks: [], _break_warning: null}] if no data. "
        "start_year must be strictly before end_year. "
        "age_group: 'total' (default) or 'youth'."
    )
)
def get_cagr(
    dataflow_id: str,
    country: str,
    start_year: str,
    end_year: str,
    age_group: str = "total",
) -> list[dict[str, object]]:
    _validate_age_group(age_group)
    _validate_year("start_year", start_year)
    _validate_year("end_year", end_year)
    if start_year >= end_year:
        raise ValueError(
            f"start_year must be strictly before end_year"
            f" (got {start_year!r} and {end_year!r})"
        )
    _validate_country(country)

    df = _fetch_df(dataflow_id, country, start_year, end_year, age_group)
    detected_breaks = breaks.detect_breaks(df)

    if df.empty:
        return [{"_breaks": [], "_break_warning": None}]

    warning = _build_break_warning(detected_breaks, start_year, end_year)
    stat = growth.cagr(df, start_year, end_year)
    return [{"_breaks": detected_breaks, "_break_warning": warning}, stat]


@mcp.tool(
    description=(
        "OLS linear trend between start_year and end_year. "
        "Returns a list where result[0] is metadata: {_breaks, _break_warning} "
        "and result[1] is "
        "{start_year, end_year, slope, intercept, r_squared, n_points}. "
        "A _break_warning is set if any methodology break falls within the range "
        "-- a trend across a break is unreliable. "
        "Returns [{_breaks: [], _break_warning: null}] if no data. "
        "start_year must be strictly before end_year. "
        "age_group: 'total' (default) or 'youth'."
    )
)
def get_trend(
    dataflow_id: str,
    country: str,
    start_year: str,
    end_year: str,
    age_group: str = "total",
) -> list[dict[str, object]]:
    _validate_age_group(age_group)
    _validate_year("start_year", start_year)
    _validate_year("end_year", end_year)
    if start_year >= end_year:
        raise ValueError(
            f"start_year must be strictly before end_year"
            f" (got {start_year!r} and {end_year!r})"
        )
    _validate_country(country)

    df = _fetch_df(dataflow_id, country, start_year, end_year, age_group)
    detected_breaks = breaks.detect_breaks(df)

    if df.empty:
        return [{"_breaks": [], "_break_warning": None}]

    warning = _build_break_warning(detected_breaks, start_year, end_year)
    stat = growth.trend(df, start_year, end_year)
    return [{"_breaks": detected_breaks, "_break_warning": warning}, stat]


# ── Prompts ───────────────────────────────────────────────────────────────────


def _resolve_country(inp: str, countries: list[dict[str, str]]) -> str:
    """
    Resolve a user-supplied country name or ISO-3 code to an ISO-3 code.

    Resolution order:
    1. Exact code match (case-insensitive).
    2. Exact name match (case-insensitive).
    3. Single partial name match (case-insensitive substring) → resolved.
    4. Multiple partial matches → ValueError (ambiguous).
    5. No match → ValueError.

    Parameters
    ----------
    inp       : User-supplied country name or code.
    countries : List of {code, name} dicts from get_cached_countries().

    Returns
    -------
    ISO-3 country code string.

    Raises
    ------
    ValueError for no match or multiple partial matches (ambiguous).
    """
    inp_lower = inp.lower()

    for c in countries:
        if c["code"].lower() == inp_lower:
            return c["code"]

    for c in countries:
        if c["name"].lower() == inp_lower:
            return c["code"]

    partials = [c for c in countries if inp_lower in c["name"].lower()]
    if len(partials) == 1:
        return partials[0]["code"]
    if len(partials) > 1:
        candidates = ", ".join(f"{c['code']} ({c['name']})" for c in partials)
        raise ValueError(f"'{inp}' is ambiguous — matches: {candidates}")

    raise ValueError(
        f"'{inp}' did not match any ILOSTAT country."
        " Use get_countries() to find valid codes."
    )


@mcp.prompt()
def labor_market_snapshot(countries: str) -> str:
    """
    Generate a labour market snapshot for 1–3 countries.

    `countries` is a comma-separated string of country names or ISO-3 codes.
    Validates count, resolves each to an ISO-3 code, then returns a prompt
    message that instructs the model to fetch and compare key labour market
    indicators for those countries.

    Raises ValueError for >3 countries, unknown names, or ambiguous names.
    """
    inputs = [c.strip() for c in countries.split(",") if c.strip()]
    n = len(inputs)
    if n > 3:
        raise ValueError(
            f"labor_market_snapshot accepts 1-3 countries, got {n}: {inputs}."
        )

    country_list = resources.get_cached_countries()
    errors: list[ValueError] = []
    resolved: list[str] = []

    for inp in inputs:
        try:
            code = _resolve_country(inp, country_list)
            resolved.append(code)
        except ValueError as e:
            errors.append(e)

    if errors:
        raise errors[0]

    codes_str = ", ".join(resolved)
    flows_str = "\n".join(
        f"  - {f['theme']}: {f['dataflow_id']}" for f in resources.CANONICAL_FLOWS
    )

    return (
        f"Fetch a labour market snapshot for: {codes_str}.\n\n"
        f"For each country, call get_time_series with the following dataflow IDs"
        f" (use the most recent 2 years available):\n{flows_str}\n\n"
        f"For each dataflow and country:\n"
        f"1. Retrieve the data with get_time_series.\n"
        f"2. Compute year-over-year change for the most recent year"
        f" using get_yoy_change.\n"
        f"3. Note any methodology breaks in the _breaks field.\n\n"
        f"Present the results as a concise table comparing all countries."
        f" Use ISO codes ({codes_str}) as column headers."
        f" If data is unavailable for a country/indicator, show 'N/A'."
    )


def main() -> None:
    mcp.run()
