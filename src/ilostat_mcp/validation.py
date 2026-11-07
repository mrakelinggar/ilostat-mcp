"""
Input validation shared by all tool handlers.

Every tool calls these before any API call. All raise ValueError with a
plain-English message written for Claude to relay to the user.
"""

from datetime import date

from ilostat_mcp import resources
from ilostat_mcp.indicators import AGE_GROUP_CODES, FLOW_SPECS


def validate_dataflow(dataflow_id: str) -> None:
    """Raise ValueError if dataflow_id is not in the registered allowlist."""
    if dataflow_id not in FLOW_SPECS:
        valid = ", ".join(sorted(FLOW_SPECS))
        raise ValueError(f"Unknown dataflow {dataflow_id!r}. Valid dataflows: {valid}")


def validate_age_group(age_group: str) -> None:
    """Raise ValueError if age_group is not a recognised value."""
    if age_group not in AGE_GROUP_CODES:
        valid = " or ".join(repr(g) for g in AGE_GROUP_CODES)
        raise ValueError(f"age_group must be {valid} (got {age_group!r})")


def validate_year(label: str, year: str, dataflow_id: str) -> None:
    """
    Raise ValueError if year is not a valid 4-digit year for the given dataflow.

    Valid means between the flow's min_year and the current calendar year.
    The current year is read on every call, so a long-running server keeps
    accepting new years after New Year without a restart.
    dataflow_id must already be validated.
    """
    if not (year.isdigit() and len(year) == 4):
        raise ValueError(f"{label} must be a 4-digit year (got {year!r})")
    min_year = FLOW_SPECS[dataflow_id].min_year
    max_year = date.today().year
    if not (min_year <= int(year) <= max_year):
        raise ValueError(
            f"{label} for {dataflow_id} must be between {min_year}"
            f" and {max_year} (got {year})"
        )


def validate_year_range(
    start_year: str, end_year: str, dataflow_id: str, *, strict: bool
) -> None:
    """
    Validate both years, then their order.

    strict=True requires start_year < end_year (CAGR and trend need two
    distinct years); strict=False allows start_year == end_year.
    Raises ValueError on any failure. dataflow_id must already be validated.
    """
    validate_year("start_year", start_year, dataflow_id)
    validate_year("end_year", end_year, dataflow_id)
    # Both are validated 4-digit strings, so string order equals numeric order.
    if strict and start_year >= end_year:
        raise ValueError(
            "start_year must be strictly before end_year"
            f" (got {start_year!r} and {end_year!r})"
        )
    if not strict and start_year > end_year:
        raise ValueError(
            f"start_year must be <= end_year (got {start_year} to {end_year})"
        )


def validate_country(country: str) -> None:
    """Raise ValueError if country is not a valid ILOSTAT area code."""
    valid_codes = {c["code"] for c in resources.get_cached_countries()}
    if country not in valid_codes:
        raise ValueError(
            f"Unknown country code {country!r}."
            " Use get_countries() to find valid codes."
        )
