"""
Methodology-break detection for ILOSTAT time series.

A break occurs when consecutive annual observations come from different survey
sources — e.g. the series switches from an LFS (Labour Force Survey) to a HIES
(Household Income and Expenditure Survey). Numbers across a break are not directly
comparable, so any multi-year derived stat (CAGR, trend) that spans a break must
carry a warning.

Detection method: SOURCE attribute diff across consecutive observations sorted by
time_period. ILOSTAT leaves OBS_PRE_BREAK_VALUE empty, so that field is not used.
"""

import pandas as pd


def detect_breaks(df: pd.DataFrame) -> list[dict[str, object]]:
    """
    Find methodology breaks in a time series DataFrame.

    A break is attributed to the later year — the first year whose data comes
    from the new source. For example, if 2012 is LFS and 2013 is HIES, the
    break is recorded at year "2013".

    Parameters
    ----------
    df : DataFrame from sdmx_client.get_time_series. Must have 'time_period'
         and 'source' columns. Returns [] if either column is missing, if the
         series has fewer than 2 observations, or if source is absent for all rows.

    Returns
    -------
    List of break dicts, one per detected break, ordered by year:
        {"year": str, "source_before": str, "source_after": str}
    Empty list if no breaks detected.
    """
    if df.empty or "source" not in df.columns or "time_period" not in df.columns:
        return []

    # Collapse to one source per time period before comparing.
    # ILOSTAT flows often return multiple rows per year (different sex/age
    # dimension values) — all rows for the same year share the same SOURCE
    # attribute. We take the first non-empty source per year to get a clean
    # year-over-year sequence for comparison.
    year_source = (
        pd.DataFrame(
            {
                "time_period": df["time_period"],
                "source": df["source"].fillna("").astype(str),
            }
        )
        .groupby("time_period", sort=True)["source"]
        .first()
        .reset_index()
    )

    if len(year_source) < 2:
        return []

    breaks: list[dict[str, object]] = []
    for i in range(1, len(year_source)):
        prev = str(year_source.loc[i - 1, "source"])
        curr = str(year_source.loc[i, "source"])
        # Skip years where source is unknown on either side
        if not prev and not curr:
            continue
        if prev != curr:
            breaks.append(
                {
                    "year": str(year_source.loc[i, "time_period"]),
                    "source_before": prev,
                    "source_after": curr,
                }
            )

    return breaks


def break_years_in_range(
    breaks: list[dict[str, object]], start_year: str, end_year: str
) -> list[str]:
    """
    Filter a break list to only those whose year falls inside [start_year, end_year].

    Used by get_cagr and get_trend to decide whether to warn.

    Parameters
    ----------
    breaks     : output of detect_breaks()
    start_year : inclusive lower bound (e.g. "2010")
    end_year   : inclusive upper bound (e.g. "2022")

    Returns
    -------
    List of break years (strings) within the range, in order.
    """
    return [str(b["year"]) for b in breaks if start_year <= str(b["year"]) <= end_year]
