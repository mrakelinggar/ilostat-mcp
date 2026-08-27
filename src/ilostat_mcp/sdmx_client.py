"""
ILOSTAT SDMX client — the only file in the codebase that imports sdmx1.

All other modules receive plain pandas DataFrames or plain dicts from here;
sdmx1 specifics never leak past this boundary.

Design decisions (all resolved in Phase 0):
- cloudscraper session replaces the default requests session to bypass Cloudflare
- sdmx.to_pandas(resp, attributes="o") surfaces observation-level attributes
  (SOURCE, OBS_STATUS, etc.) that the default call drops
- FREQ is filtered post-fetch in pandas, not in the SDMX key dict
- AGE/CUR dimension included in key dict only when the caller passes a value
- HTTPError on 404 → return empty DataFrame (both "no data" and "invalid flow ID")
- last_updated comes from the LAST_UPDATE annotation in client.dataflow()
- MEASURE column dropped from output (always single-valued per flow)
"""

import logging
from typing import Optional

import cloudscraper
import pandas as pd
import sdmx
import sdmx.message
from bs4 import BeautifulSoup
from requests.exceptions import HTTPError

from ilostat_mcp.indicators import is_modelled

logger = logging.getLogger(__name__)

# ── Client setup ─────────────────────────────────────────────────────────────


_scraper = cloudscraper.create_scraper()

_client = sdmx.Client("ILO")
_client.session = _scraper

# Columns to keep in get_time_series output (snake_case after lowering).
# MEASURE is always single-valued per flow — dropped as uninformative.
# unit_measure_type, unit_mult, note_source, note_indicator, decimals, bounds
# are either metadata noise or empty for our canonical flows.
_KEEP_COLUMNS = {
    "time_period", "value", "obs_status", "source",
    "unit_measure", "freq", "sex",
    # age and cur are added conditionally below
    "age", "cur",
    "note_classif",
}


# ── Public functions ──────────────────────────────────────────────────────────

def get_time_series(
    flow_id: str,
    country: str,
    start: str,
    end: str,
    *,
    freq: str = "A",
    sex: str = "SEX_T",
    age: Optional[str] = None,
    cur: Optional[str] = None,
) -> pd.DataFrame:
    """
    Fetch a time series from ILOSTAT and return a clean DataFrame.

    Parameters
    ----------
    flow_id : ILOSTAT dataflow ID (e.g. "DF_UNE_DEAP_SEX_AGE_RT")
    country : ISO 3166-1 alpha-3 country code (e.g. "DEU")
    start   : start year, inclusive (e.g. "2010")
    end     : end year, inclusive (e.g. "2023")
    freq    : frequency filter applied post-fetch ("A" = annual, "Q" = quarterly)
    sex     : SEX dimension value (default "SEX_T" = total)
    age     : AGE dimension value; include only if the flow uses AGE
    cur     : CUR dimension value; include only if the flow uses CUR

    Returns
    -------
    DataFrame with columns: time_period, value, obs_status, source,
    unit_measure, freq, sex, [age or cur if present], note_classif.
    Empty DataFrame if the country has no data (404).
    """
    key: dict[str, str] = {"REF_AREA": country, "SEX": sex}
    if age is not None:
        key["AGE"] = age
    if cur is not None:
        key["CUR"] = cur

    try:
        resp = _client.data(
            flow_id,
            key=key,
            params={"startPeriod": start, "endPeriod": end},
        )
    except HTTPError as exc:
        if exc.response is not None and exc.response.status_code in (404, 400):
            logger.debug("No data for %s/%s: %s", flow_id, country, exc)
            return pd.DataFrame()
        raise

    df = sdmx.to_pandas(resp, attributes="o").reset_index()

    if df.empty:
        return df

    # Normalise column names to snake_case
    df.columns = [c.lower() for c in df.columns]

    # Filter to requested frequency
    if "freq" in df.columns and freq:
        df = df[df["freq"] == freq]

    # Keep only the columns we want; ignore any that aren't present
    present = [c for c in df.columns if c in _KEEP_COLUMNS]
    df = df[present].copy()

    # Ensure time_period is a string (sdmx1 may return a Period object)
    if "time_period" in df.columns:
        df["time_period"] = df["time_period"].astype(str)

    return df.reset_index(drop=True)


def get_indicator_metadata(flow_id: str) -> dict:
    """
    Return title, description, and last_updated for a dataflow.

    last_updated comes from the LAST_UPDATE annotation in the dataflow
    response — this is when ILOSTAT last refreshed the data, not when
    the API response was generated.

    Returns an empty dict if the flow ID is invalid (404).
    """
    try:
        resp = _client.dataflow(flow_id)
    except HTTPError as exc:
        if exc.response is not None and exc.response.status_code in (404, 400):
            logger.debug("Unknown flow ID %s: %s", flow_id, exc)
            return {}
        raise

    flows = resp.dataflow
    if flow_id not in flows:
        return {}

    flow = flows[flow_id]
    name = str(flow.name) if flow.name else ""
    raw_desc = str(flow.description) if getattr(flow, "description", None) else ""
    description = BeautifulSoup(raw_desc, "html.parser").get_text(separator=" ", strip=True)

    last_updated = ""
    for ann in getattr(flow, "annotations", []):
        # sdmx1 uses ann.type for the annotation classification (e.g. "LAST_UPDATE")
        if getattr(ann, "type", None) == "LAST_UPDATE":
            last_updated = str(ann.text) if ann.text else ""
            break

    return {
        "id": flow_id,
        "title": name,
        "description": description,
        "last_updated": last_updated,
        "is_modelled": is_modelled(flow_id),
    }


def search_indicators(keyword: str, *, max_results: int = 20) -> list[dict]:
    """
    Search ILOSTAT dataflows by keyword and return matching flows.

    Searches flow titles (flow.name). Results are returned in ILOSTAT's
    native ORDER annotation order, capped at max_results.

    Each result dict has keys: id, title, is_modelled.
    """
    keyword_lower = keyword.lower()
    matches: list[tuple[int, dict]] = []

    try:
        resp = _client.dataflow()
    except HTTPError as exc:
        logger.warning("Failed to fetch dataflow catalog: %s", exc)
        return []

    for flow_id, flow in resp.dataflow.items():
        title = str(flow.name) if flow.name else ""
        if keyword_lower not in title.lower():
            continue

        order = 9999
        for ann in getattr(flow, "annotations", []):
            if getattr(ann, "id", None) == "ORDER":
                try:
                    order = int(str(ann.text))
                except (ValueError, TypeError):
                    pass
                break

        matches.append((order, {
            "id": flow_id,
            "title": title,
            "is_modelled": is_modelled(flow_id),
        }))

    matches.sort(key=lambda x: x[0])
    return [m[1] for m in matches[:max_results]]


def get_countries() -> list[dict]:
    """
    Return the list of valid country/area codes from ILOSTAT's CL_AREA codelist.

    Each entry has keys: code, name.

    Falls back to an empty list if the codelist endpoint fails — callers
    should treat an empty list as "try the data endpoint directly".
    """
    try:
        resp = _client.codelist("CL_AREA")
    except Exception as exc:
        logger.warning("Failed to fetch CL_AREA codelist: %s", exc)
        return []

    areas = []
    for cl_id, codelist in resp.codelist.items():
        # codelist.items is a plain dict {code_id: Code}, not a bound method
        for code_id, code in codelist.items.items():
            name = str(code.name) if code.name else str(code_id)
            areas.append({"code": str(code_id), "name": name})
        break  # only the first (and only) CL_AREA codelist

    return sorted(areas, key=lambda x: x["code"])
