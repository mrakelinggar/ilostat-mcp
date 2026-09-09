"""
Input validation helpers shared across all tool handlers.

Every public tool calls these before any API call. All raise ValueError with
a plain-English message written for Claude to relay to the user.
"""

import datetime

from ilostat_mcp.indicators import AGE_TOTAL, AGE_YOUTH, FLOW_DIMS, FLOW_MIN_YEARS

# Upper year bound applied to all dataflow validation — current calendar year.
_CURRENT_YEAR: int = datetime.date.today().year

# Maps the age_group tool parameter to SDMX dimension values.
_AGE_GROUP_MAP: dict[str, str] = {
    "total": AGE_TOTAL,  # adults 15+
    "youth": AGE_YOUTH,  # youth 15-29
}


def _validate_dataflow(dataflow_id: str) -> None:
    """Raise ValueError if dataflow_id is not in the registered allowlist."""
    if dataflow_id not in FLOW_DIMS:
        valid = ", ".join(sorted(FLOW_DIMS.keys()))
        raise ValueError(
            f"Unknown dataflow {dataflow_id!r}. Valid dataflows: {valid}"
        )


def _validate_age_group(age_group: str) -> None:
    """Raise ValueError if age_group is not a recognised value."""
    if age_group not in _AGE_GROUP_MAP:
        raise ValueError(f"age_group must be 'total' or 'youth' (got {age_group!r})")


def _validate_year(label: str, year: str, dataflow_id: str) -> None:
    """
    Raise ValueError if year is not a valid 4-digit year for the given dataflow.

    Checks format, then validates against the per-flow minimum year from
    FLOW_MIN_YEARS and the current calendar year as the upper bound.
    """
    if not (year.isdigit() and len(year) == 4):
        raise ValueError(f"{label} must be a 4-digit year (got {year!r})")
    yr = int(year)
    min_year = FLOW_MIN_YEARS.get(dataflow_id, 1900)
    if not (min_year <= yr <= _CURRENT_YEAR):
        raise ValueError(
            f"{label} for {dataflow_id} must be between {min_year}"
            f" and {_CURRENT_YEAR} (got {yr})"
        )


def _validate_country(country: str) -> None:
    """Raise ValueError if country is not a valid ILOSTAT area code."""
    from ilostat_mcp.resources import get_cached_countries  # avoid circular import

    valid_codes = {c["code"] for c in get_cached_countries()}
    if country not in valid_codes:
        raise ValueError(
            f"Unknown country code {country!r}."
            " Use get_countries() to find valid codes."
        )
