"""Tool handler for raw time-series fetching."""

from typing import cast

from ilostat_mcp import breaks, validation
from ilostat_mcp.tools import series


def get_time_series(
    dataflow_id: str,
    country: str,
    start_year: str,
    end_year: str,
    age_group: str = "total",
) -> list[dict[str, object]]:
    """
    Fetch a time series from ILOSTAT. Returns a list where the FIRST element
    is series metadata and remaining elements are annual observations.

    Metadata keys:
      _dataflow_id     : the dataflow this data came from
      _is_modelled     : true if the flow is ILO modelled estimates, not survey data
      _unit_measure    : unit of the values (e.g. "%", "USD", "EUR/month")
      _currency_code   : ISO 4217 code for wage flows (local currency), else null
      _coverage_start  : earliest year available for this country in the response
      _coverage_end    : latest year available — may be earlier than end_year if
                         ILOSTAT has not yet published data for recent years
      _breaks          : methodology breaks ({year, source_before, source_after,
                         reasons}); empty if none
      _missing_years   : years in the requested range with no observation (gaps)
      _no_data_reason  : plain-English explanation when the country has no data

    Observation keys: time_period, value, obs_status, source, unit_measure.
    Do not compute multi-year trends across a break without flagging it.
    age_group: 'total' (default, adults 15+) or 'youth' (15-29); ignored
    for wage flows.
    """
    validation.validate_dataflow(dataflow_id)
    validation.validate_age_group(age_group)
    validation.validate_year_range(start_year, end_year, dataflow_id, strict=False)
    validation.validate_country(country)

    df = series.fetch_series(dataflow_id, country, start_year, end_year, age_group)
    meta = series.series_meta(
        df,
        dataflow_id,
        country,
        age_group,
        breaks.detect_breaks(df),
        series.missing_years(df, start_year, end_year),
    )
    rows = cast(list[dict[str, object]], df.to_dict(orient="records"))
    return [meta, *rows]
