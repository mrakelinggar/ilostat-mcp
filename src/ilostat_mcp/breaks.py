"""
Methodology-break detection for ILOSTAT time series.

A break is a year where the way the numbers were collected changed, so values
before and after it are not directly comparable. Any multi-year derived stat
(CAGR, trend) that spans a break must carry a warning.

Two signals, either of which records a break (Phase 5 finding — each catches
breaks the other misses):
- ILOSTAT's own flag: obs_status "B" ("break in series") on the first year
  after the change. Catches survey redesigns that keep the same survey name.
- SOURCE change: the survey source differs from the last known source, e.g.
  a census replaced by a labour force survey. Catches changes ILOSTAT did
  not flag.
ILOSTAT leaves OBS_PRE_BREAK_VALUE empty, so that field is not used.
"""

from typing import cast

import pandas as pd

BREAK_STATUS = "B"  # ILOSTAT obs_status code for "break in series"
REASON_ILOSTAT_FLAG = "ilostat_break_flag"
REASON_SOURCE_CHANGE = "source_change"


def _by_year(df: pd.DataFrame) -> pd.DataFrame:
    """
    Collapse a series to one row per year, sorted by year.

    Columns: time_period, source (first non-blank source that year, else NA),
    flagged (True if any row that year has obs_status "B").
    """
    if "source" in df.columns:
        source = df["source"].astype("string").str.strip().replace("", pd.NA)
    else:
        source = pd.Series(pd.NA, index=df.index, dtype="string")
    if "obs_status" in df.columns:
        flagged = df["obs_status"].astype("string") == BREAK_STATUS
    else:
        flagged = pd.Series(False, index=df.index)
    tidy = pd.DataFrame(
        {
            "time_period": df["time_period"].astype(str),
            "source": source,
            "flagged": flagged.fillna(False).astype(bool),
        }
    )
    # groupby "first" skips NA, so a blank row never hides a known source.
    return (
        tidy.groupby("time_period", sort=True)
        .agg(source=("source", "first"), flagged=("flagged", "any"))
        .reset_index()
    )


def detect_breaks(df: pd.DataFrame) -> list[dict[str, object]]:
    """
    Find methodology breaks in a time series DataFrame.

    A break is attributed to the later year — the first year measured the new
    way. For example, if 2012 is LFS and 2013 is HIES, the break is "2013".

    The source comparison uses the last known source, so a year with a blank
    source neither hides a change nor creates a false one.

    Parameters
    ----------
    df : DataFrame from sdmx_client.get_time_series. Needs 'time_period';
         uses 'source' and 'obs_status' when present. Returns [] if df is
         empty or has no 'time_period' column.

    Returns
    -------
    List of break dicts ordered by year:
        {"year": str,
         "source_before": str | None,   # last known source before the break
         "source_after": str | None,    # source in the break year
         "reasons": list[str]}          # REASON_ILOSTAT_FLAG / REASON_SOURCE_CHANGE
    Empty list if no breaks are detected.
    """
    if df.empty or "time_period" not in df.columns:
        return []

    breaks: list[dict[str, object]] = []
    last_known: str | None = None
    for row in _by_year(df).itertuples(index=False):
        source = None if pd.isna(row.source) else str(row.source)
        reasons: list[str] = []
        if row.flagged:
            reasons.append(REASON_ILOSTAT_FLAG)
        if source is not None and last_known is not None and source != last_known:
            reasons.append(REASON_SOURCE_CHANGE)
        if reasons:
            breaks.append(
                {
                    "year": str(row.time_period),
                    "source_before": last_known,
                    "source_after": source,
                    "reasons": reasons,
                }
            )
        if source is not None:
            last_known = source
    return breaks


def _describe(brk: dict[str, object]) -> str:
    """Return a plain-English reason for one break, e.g. for a warning message."""
    reasons = cast(list[str], brk["reasons"])
    parts: list[str] = []
    if REASON_ILOSTAT_FLAG in reasons:
        parts.append("ILOSTAT flags a break in series")
    if REASON_SOURCE_CHANGE in reasons:
        parts.append(
            f"source changed from '{brk['source_before']}' to '{brk['source_after']}'"
        )
    return "; ".join(parts)


def break_warning(
    breaks: list[dict[str, object]], start_year: str, end_year: str
) -> str | None:
    """
    Return a plain-English warning if any break falls in [start_year, end_year].

    Used by get_yoy_change, get_cagr and get_trend: a derived stat over a range
    that contains a break compares numbers measured in different ways.

    One break: names the year and why. Several: lists each year with its reason.
    Returns None if no break falls in the range.
    """
    in_range = [b for b in breaks if start_year <= str(b["year"]) <= end_year]
    if not in_range:
        return None
    details = "; ".join(f"{b['year']} ({_describe(b)})" for b in in_range)
    label = "Methodology break" if len(in_range) == 1 else "Methodology breaks"
    return (
        f"{label} within {start_year}-{end_year} at {details}."
        " Values across a methodology break are not directly comparable"
        " — interpret this result with caution."
    )
