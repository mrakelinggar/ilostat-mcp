"""
ILOSTAT SDMX client — the only file in the codebase that imports sdmx1.

All other modules receive plain pandas DataFrames or plain dicts from here;
sdmx1 specifics never leak past this boundary.

Design decisions (all resolved in Phase 0 + Phase 2b):
- cloudscraper session replaces the default requests session to bypass Cloudflare
- sdmx.to_pandas(resp, attributes="o") surfaces observation-level attributes
  (SOURCE, OBS_STATUS, etc.) that the default call drops
- FREQ is filtered post-fetch in pandas, not in the SDMX key dict
- AGE/CUR/GEO dimension included in key dict only when the caller passes a value
- HTTPError on 404/400 → return empty DataFrame/dict (no data or invalid flow ID)
- last_updated comes from the LAST_UPDATE annotation in client.dataflow()
- MEASURE column dropped from output (always single-valued per flow)
- 30-second timeout via _client._send_kwargs — sdmx1 passes this to session.send()
- ConnectionError/Timeout/429/500/503 → RuntimeError with plain-English message
"""

import html
import time
from typing import cast

import cloudscraper
import pandas as pd
import sdmx
import sdmx.message
import structlog
from bs4 import BeautifulSoup
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError, Timeout

from ilostat_mcp.indicators import is_modelled
from ilostat_mcp.telemetry import get_tracer

logger: structlog.BoundLogger = structlog.get_logger()
_tracer = get_tracer(__name__)

# ── Client setup ─────────────────────────────────────────────────────────────


_TIMEOUT_SECONDS = 30  # applied to every ILOSTAT API request

_scraper = cloudscraper.create_scraper()

_client = sdmx.Client("ILO")
_client.session = _scraper
# _send_kwargs is passed verbatim to session.send() on every request.
# Setting timeout here makes it apply globally without repeating it per call.
_client._send_kwargs["timeout"] = _TIMEOUT_SECONDS

# Columns to keep in get_time_series output (snake_case after lowering).
# Dropped as uninformative:
# - freq: always "A" — we filter to annual before returning
# - sex: always "SEX_T" — hardcoded in every fetch
# - age/cur/geo: per-call constants that reflect the caller's own input
# - note_classif: always empty in ILOSTAT responses
# - unit_measure_type, unit_mult, note_source, note_indicator, decimals, bounds:
#   metadata noise or empty
# obs_status is kept — "B" appears on break-year observations and has real signal.
_KEEP_COLUMNS = {
    "time_period",
    "value",
    "obs_status",
    "source",
    "unit_measure",
}


# ── Error helpers ────────────────────────────────────────────────────────────


def _plain_english_error(exc: HTTPError) -> RuntimeError:
    """Convert a non-404 HTTPError to a RuntimeError with a user-facing message.

    Callers handle 404/400 themselves (empty result contract). This converts
    everything else to a message Claude can relay to the user.
    """
    status = exc.response.status_code if exc.response is not None else None
    if status == 429:
        return RuntimeError("ILOSTAT rate limit reached — wait a moment and try again.")
    if status in (500, 503):
        return RuntimeError(
            "ILOSTAT API returned a server error and may be temporarily down."
            " Try again shortly."
        )
    return RuntimeError(f"ILOSTAT API error (HTTP {status}).")


# ── Public functions ──────────────────────────────────────────────────────────


def get_time_series(
    flow_id: str,
    country: str,
    start: str,
    end: str,
    *,
    freq: str = "A",
    sex: str = "SEX_T",
    age: str | None = None,
    cur: str | None = None,
    geo: str | None = None,
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
    geo     : GEO dimension value; include only for flows with a GEO dimension
              (e.g. "GEO_COV_NAT" = national total)

    Returns
    -------
    DataFrame with columns: time_period, value, obs_status, source,
    unit_measure, freq, sex, [age|cur|geo if present], note_classif.
    Empty DataFrame if the country has no data (404).
    """
    key: dict[str, str] = {"REF_AREA": country, "SEX": sex}
    if age is not None:
        key["AGE"] = age
    if cur is not None:
        key["CUR"] = cur
    if geo is not None:
        key["GEO"] = geo

    t0 = time.perf_counter()
    with _tracer.start_as_current_span("ilostat.api.data") as span:
        span.set_attribute("flow_id", flow_id)
        span.set_attribute("country", country)
        try:
            resp = _client.data(
                flow_id,
                key=key,
                params={"startPeriod": start, "endPeriod": end},
            )
            duration_ms = int((time.perf_counter() - t0) * 1000)
            span.set_attribute("http_status", 200)
            logger.debug(
                "api",
                flow_id=flow_id,
                country=country,
                http_status=200,
                duration_ms=duration_ms,
            )
        except Timeout as exc:
            raise RuntimeError(
                "ILOSTAT API request timed out — the server may be slow or"
                " unavailable. Try again."
            ) from exc
        except RequestsConnectionError as exc:
            raise RuntimeError(
                "Could not reach ILOSTAT's API — check your internet connection."
            ) from exc
        except HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            duration_ms = int((time.perf_counter() - t0) * 1000)
            if status is not None:
                span.set_attribute("http_status", status)
            logger.debug(
                "api",
                flow_id=flow_id,
                country=country,
                http_status=status,
                duration_ms=duration_ms,
            )
            if exc.response is not None and exc.response.status_code in (404, 400):
                return pd.DataFrame()
            raise _plain_english_error(exc) from exc

    df = cast(pd.DataFrame, sdmx.to_pandas(resp, attributes="o")).reset_index()  # type: ignore[no-untyped-call]

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


def get_indicator_metadata(flow_id: str) -> dict[str, object]:
    """
    Return title, description, and last_updated for a dataflow.

    last_updated comes from the LAST_UPDATE annotation in the dataflow
    response — this is when ILOSTAT last refreshed the data, not when
    the API response was generated.

    Returns an empty dict if the flow ID is invalid (404).
    """
    t0 = time.perf_counter()
    with _tracer.start_as_current_span("ilostat.api.dataflow") as span:
        span.set_attribute("flow_id", flow_id)
        try:
            resp = _client.dataflow(flow_id)
            duration_ms = int((time.perf_counter() - t0) * 1000)
            span.set_attribute("http_status", 200)
            logger.debug(
                "api", flow_id=flow_id, http_status=200, duration_ms=duration_ms
            )
        except Timeout as exc:
            raise RuntimeError(
                "ILOSTAT API request timed out — the server may be slow or"
                " unavailable. Try again."
            ) from exc
        except RequestsConnectionError as exc:
            raise RuntimeError(
                "Could not reach ILOSTAT's API — check your internet connection."
            ) from exc
        except HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            duration_ms = int((time.perf_counter() - t0) * 1000)
            if status is not None:
                span.set_attribute("http_status", status)
            logger.debug(
                "api", flow_id=flow_id, http_status=status, duration_ms=duration_ms
            )
            if exc.response is not None and exc.response.status_code in (404, 400):
                return {}
            raise _plain_english_error(exc) from exc

    flows = resp.dataflow
    if flow_id not in flows:
        return {}

    flow = flows[flow_id]
    name = str(flow.name) if flow.name else ""
    raw_desc = str(flow.description) if getattr(flow, "description", None) else ""
    description = BeautifulSoup(raw_desc, "html.parser").get_text(
        separator=" ", strip=True
    )

    return {
        "id": flow_id,
        "title": name,
        "description": description,
        "is_modelled": is_modelled(flow_id),
    }


def search_indicators(
    keyword: str, *, max_results: int = 20
) -> list[dict[str, object]]:
    """
    Search ILOSTAT dataflows by keyword and return matching flows.

    Searches flow titles (flow.name). Results are returned in ILOSTAT's
    native ORDER annotation order, capped at max_results.

    Each result dict has keys: id, title, is_modelled.
    """
    keyword_lower = keyword.lower()
    matches: list[tuple[int, dict[str, object]]] = []

    t0 = time.perf_counter()
    with _tracer.start_as_current_span("ilostat.api.dataflow_all") as span:
        span.set_attribute("keyword", keyword)
        try:
            resp = _client.dataflow()
            duration_ms = int((time.perf_counter() - t0) * 1000)
            span.set_attribute("http_status", 200)
            logger.debug(
                "api", keyword=keyword, http_status=200, duration_ms=duration_ms
            )
        except Timeout as exc:
            raise RuntimeError(
                "ILOSTAT API request timed out — the server may be slow or"
                " unavailable. Try again."
            ) from exc
        except RequestsConnectionError as exc:
            raise RuntimeError(
                "Could not reach ILOSTAT's API — check your internet connection."
            ) from exc
        except HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            duration_ms = int((time.perf_counter() - t0) * 1000)
            if status is not None:
                span.set_attribute("http_status", status)
            logger.debug(
                "api", keyword=keyword, http_status=status, duration_ms=duration_ms
            )
            raise _plain_english_error(exc) from exc

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

        matches.append(
            (
                order,
                {
                    "id": flow_id,
                    "title": title,
                    "is_modelled": is_modelled(flow_id),
                },
            )
        )

    matches.sort(key=lambda x: x[0])
    return [m[1] for m in matches[:max_results]]


def get_countries() -> list[dict[str, str]]:
    """
    Return the list of valid country/area codes from ILOSTAT's CL_AREA codelist.

    Each entry has keys: code, name.

    Raises RuntimeError on any API failure — an empty list is never a valid
    result (ILOSTAT always has countries), so callers cannot treat [] as
    "no countries".
    """
    t0 = time.perf_counter()
    with _tracer.start_as_current_span("ilostat.api.codelist") as span:
        try:
            resp = _client.codelist("CL_AREA")
            duration_ms = int((time.perf_counter() - t0) * 1000)
            span.set_attribute("http_status", 200)
            logger.debug("api", http_status=200, duration_ms=duration_ms)
        except Timeout as exc:
            raise RuntimeError(
                "ILOSTAT API request timed out — the server may be slow or"
                " unavailable. Try again."
            ) from exc
        except RequestsConnectionError as exc:
            raise RuntimeError(
                "Could not reach ILOSTAT's API — check your internet connection."
            ) from exc
        except HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            duration_ms = int((time.perf_counter() - t0) * 1000)
            if status is not None:
                span.set_attribute("http_status", status)
            logger.debug("api", http_status=status, duration_ms=duration_ms)
            raise _plain_english_error(exc) from exc

    areas: list[dict[str, str]] = []
    for codelist in resp.codelist.values():
        # codelist.items is a plain dict {code_id: Code}, not a bound method
        for code_id, code in codelist.items.items():
            name = html.unescape(str(code.name)) if code.name else str(code_id)
            areas.append({"code": str(code_id), "name": name})
        break  # only the first (and only) CL_AREA codelist

    return sorted(areas, key=lambda x: x["code"])
