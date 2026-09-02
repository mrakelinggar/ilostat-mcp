"""
Derived statistics for ILOSTAT time series — pure math functions.

All functions operate on a DataFrame with at minimum a `time_period` (str)
column and a `value` (float) column, as returned by sdmx_client.get_time_series.
They have no side effects and make no API calls.
"""

import pandas as pd


def yoy(df: pd.DataFrame, year: str) -> dict[str, object]:
    """
    Year-over-year percentage change for a given year.

    Compares the value at `year` to the value at `year - 1`. Both years must
    exist in the DataFrame. Uses the first row for each year if the DataFrame
    has multiple rows per year.

    Parameters
    ----------
    df   : DataFrame with 'time_period' (str) and 'value' (float) columns.
    year : 4-digit year string for which to compute the YoY change.

    Returns
    -------
    Dict with keys: year, value, prev_year, prev_value, change_pct.
    change_pct = ((value - prev_value) / abs(prev_value)) * 100, rounded to 4 dp.

    Raises
    ------
    ValueError if `year` or `year - 1` is not found in the DataFrame.
    ValueError if prev_value is zero (division undefined).
    """
    prev_year = str(int(year) - 1)

    year_rows = df[df["time_period"] == year]
    prev_rows = df[df["time_period"] == prev_year]

    if year_rows.empty:
        raise ValueError(f"Year {year!r} not found in data.")
    if prev_rows.empty:
        raise ValueError(f"Previous year {prev_year!r} not found in data.")

    value = float(year_rows["value"].iloc[0])
    prev_value = float(prev_rows["value"].iloc[0])

    if prev_value == 0:
        raise ValueError(
            f"Cannot compute YoY change: previous year ({prev_year}) value is zero."
        )

    change_pct = round(((value - prev_value) / abs(prev_value)) * 100, 4)

    return {
        "year": year,
        "value": value,
        "prev_year": prev_year,
        "prev_value": prev_value,
        "change_pct": change_pct,
    }


def cagr(df: pd.DataFrame, start_year: str, end_year: str) -> dict[str, object]:
    """
    Compound annual growth rate between start_year and end_year (inclusive).

    CAGR = (end_value / start_value) ^ (1 / n_years) - 1, where
    n_years = int(end_year) - int(start_year). Uses the first row for each
    boundary year if the DataFrame has multiple rows per year.

    Parameters
    ----------
    df         : DataFrame with 'time_period' (str) and 'value' (float) columns.
    start_year : 4-digit start year string (must be strictly before end_year).
    end_year   : 4-digit end year string.

    Returns
    -------
    Dict with keys: start_year, end_year, start_value, end_value, cagr_pct, n_years.
    cagr_pct is the CAGR expressed as a percentage (× 100), rounded to 4 dp.

    Raises
    ------
    ValueError if start_year == end_year (n_years must be >= 1).
    ValueError if start_year or end_year is not found in the DataFrame.
    ValueError if start_value is non-positive (CAGR undefined).
    """
    if start_year == end_year:
        raise ValueError(
            f"start_year and end_year must differ; CAGR requires n_years >= 1"
            f" (got {start_year!r} for both)."
        )

    start_rows = df[df["time_period"] == start_year]
    end_rows = df[df["time_period"] == end_year]

    if start_rows.empty:
        raise ValueError(f"start_year {start_year!r} not found in data.")
    if end_rows.empty:
        raise ValueError(f"end_year {end_year!r} not found in data.")

    start_value = float(start_rows["value"].iloc[0])
    end_value = float(end_rows["value"].iloc[0])
    n_years = int(end_year) - int(start_year)

    if start_value <= 0:
        raise ValueError(
            f"CAGR is undefined when start_value is non-positive"
            f" (got {start_value} for {start_year})."
        )

    cagr_val = (end_value / start_value) ** (1.0 / n_years) - 1.0
    cagr_pct = round(cagr_val * 100, 4)

    return {
        "start_year": start_year,
        "end_year": end_year,
        "start_value": start_value,
        "end_value": end_value,
        "cagr_pct": cagr_pct,
        "n_years": n_years,
    }


def trend(df: pd.DataFrame, start_year: str, end_year: str) -> dict[str, object]:
    """
    Ordinary-least-squares linear trend between start_year and end_year (inclusive).

    Regresses value on integer year for all data points in [start_year, end_year].
    Uses the first row per year if the DataFrame has multiple rows per year.

    Parameters
    ----------
    df         : DataFrame with 'time_period' (str) and 'value' (float) columns.
    start_year : 4-digit start year string (boundary year; must be in data).
    end_year   : 4-digit end year string (boundary year; must be in data).

    Returns
    -------
    Dict with keys: start_year, end_year, slope, intercept, r_squared, n_points.
    slope and intercept are from regressing value on integer year.
    r_squared rounded to 4 dp; slope and intercept rounded to 6 dp.

    Raises
    ------
    ValueError if start_year or end_year is not found in the DataFrame.
    ValueError if fewer than 2 data points fall within the range.
    """
    mask = (df["time_period"] >= start_year) & (df["time_period"] <= end_year)
    subset = df[mask].copy()

    if start_year not in subset["time_period"].values:
        raise ValueError(f"start_year {start_year!r} not found in data.")
    if end_year not in subset["time_period"].values:
        raise ValueError(f"end_year {end_year!r} not found in data.")

    n_points = len(subset)
    if n_points < 2:
        raise ValueError(
            f"Trend requires at least 2 data points in range"
            f" {start_year}-{end_year} (got {n_points})."
        )

    x = subset["time_period"].astype(int).astype(float)
    y = subset["value"].astype(float)

    mean_x = float(x.mean())
    mean_y = float(y.mean())

    ss_xx = float(((x - mean_x) ** 2).sum())
    ss_xy = float(((x - mean_x) * (y - mean_y)).sum())
    ss_yy = float(((y - mean_y) ** 2).sum())

    slope_val = ss_xy / ss_xx
    intercept_val = mean_y - slope_val * mean_x

    if ss_yy == 0:
        r_squared_val = 1.0
    else:
        ss_res = float(((y - (slope_val * x + intercept_val)) ** 2).sum())
        r_squared_val = 1.0 - ss_res / ss_yy

    return {
        "start_year": start_year,
        "end_year": end_year,
        "slope": round(slope_val, 6),
        "intercept": round(intercept_val, 6),
        "r_squared": round(r_squared_val, 4),
        "n_points": n_points,
    }
