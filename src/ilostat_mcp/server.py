"""
FastMCP server — tool and resource registration only.

All business logic lives in sdmx_client.py and resources.py.
This file registers tools and wires entry points.
"""

from typing import cast

from fastmcp import FastMCP

from ilostat_mcp import resources, sdmx_client
from ilostat_mcp.indicators import AGE_TOTAL, AGE_YOUTH, CUR_DEFAULT, FLOW_DIMS

mcp = FastMCP("ilostat-mcp")


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


_AGE_GROUP_MAP = {
    "total": AGE_TOTAL,  # adults 15+
    "youth": AGE_YOUTH,  # youth 15-29
}


@mcp.tool(
    description=(
        "Fetch a time series from ILOSTAT. Returns a list of annual observations "
        "with columns: time_period, value, obs_status, source, unit_measure. "
        "obs_status 'B' = methodology break — do not compute trends across breaks. "
        "age_group: 'total' (default, adults 15+) or 'youth' (15-29); ignored for "
        "wage flows. Returns [] if the country has no data for this flow."
    )
)
def get_time_series(
    dataflow_id: str,
    country: str,
    start_year: str,
    end_year: str,
    age_group: str = "total",
) -> list[dict[str, object]]:
    if age_group not in _AGE_GROUP_MAP:
        raise ValueError(f"age_group must be 'total' or 'youth' (got {age_group!r})")
    if start_year > end_year:
        raise ValueError(
            f"start_year must be <= end_year (got {start_year} to {end_year})"
        )
    flow_info = FLOW_DIMS.get(dataflow_id, {})
    dim = flow_info.get("dim")
    age = _AGE_GROUP_MAP[age_group] if dim == "age" else None
    cur = CUR_DEFAULT if dim == "cur" else None
    geo = flow_info.get("GEO")
    df = sdmx_client.get_time_series(
        dataflow_id, country, start_year, end_year, age=age, cur=cur, geo=geo
    )
    if df.empty:
        return []
    return cast(list[dict[str, object]], df.to_dict(orient="records"))


def main() -> None:
    mcp.run()
