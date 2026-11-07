"""
ILOSTAT SDMX client — the only file in the codebase that imports sdmx1.

All other modules receive plain pandas DataFrames or plain dicts from here;
sdmx1 specifics never leak past this boundary.

Design decisions (Phase 0, 2b and 5):
- cloudscraper session replaces the default requests session to bypass Cloudflare
- sdmx.to_pandas(resp, attributes="o") surfaces observation-level attributes
  (SOURCE, OBS_STATUS, etc.) that the default call drops
- FREQ is filtered post-fetch in pandas, not in the SDMX key dict
- Extra dimensions (AGE/CUR/GEO/DSB) are sent only when the caller passes them
- HTTP 404/400 on a data request → empty DataFrame (no data for that country)
- The catalogue is fetched whole (get_catalogue); search and metadata are
  answered from it by the callers, which cache it
- Flow annotations keep their name in `.type` and their value in `.title`
  (e.g. type="LAST_UPDATE", title="01/11/2026 07:13:16")
- 30-second timeout via _client._send_kwargs — sdmx1 passes this to session.send()
- Timeout / connection failure / other HTTP errors → RuntimeError with a
  plain-English message
"""

import html
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import TypeVar, cast

import cloudscraper
import pandas as pd
import sdmx
import sdmx.message
import structlog
from bs4 import BeautifulSoup
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError, Timeout

from ilostat_mcp.indicators import SEX_TOTAL, is_modelled
from ilostat_mcp.telemetry import get_tracer

logger: structlog.BoundLogger = structlog.get_logger()
_tracer = get_tracer(__name__)

_T = TypeVar("_T")

# ── Client setup ─────────────────────────────────────────────────────────────

_TIMEOUT_SECONDS = 30  # applied to every ILOSTAT API request

_scraper = cloudscraper.create_scraper()

_client = sdmx.Client("ILO")
_client.session = _scraper
# _send_kwargs is passed verbatim to session.send() on every request.
# Setting timeout here makes it apply globally without repeating it per call.
_client._send_kwargs["timeout"] = _TIMEOUT_SECONDS

# ── Constants ────────────────────────────────────────────────────────────────

_HTTP_OK = 200
_NOT_FOUND_STATUSES = (400, 404)  # ILOSTAT's "no data" / "no such flow" answers
_AREA_CODELIST = "CL_AREA"
_ANNOTATION_ORDER = "ORDER"  # ILOSTAT's own ranking of flows
_ANNOTATION_LAST_UPDATE = "LAST_UPDATE"  # when ILOSTAT last refreshed the flow
_LAST_UPDATE_FORMAT = "%d/%m/%Y %H:%M:%S"  # day first, e.g. "25/10/2026 21:50:07"
_UNRANKED = sys.maxsize  # sorts flows without an ORDER annotation last

_TIMEOUT_MESSAGE = (
    "ILOSTAT API request timed out — the server may be slow or unavailable. Try again."
)
_CONNECTION_MESSAGE = "Could not reach ILOSTAT's API — check your internet connection."

# Columns to keep in get_time_series output (snake_case after lowering).
# Dropped as uninformative:
# - freq: always "A" — we filter to annual before returning
# - sex/age/cur/geo/dsb: per-call constants that reflect the caller's own input
# - note_classif: always empty in ILOSTAT responses
# - unit_measure_type, unit_mult, note_source, note_indicator, decimals, bounds:
#   metadata noise or empty
# obs_status is kept — "B" marks ILOSTAT's own methodology-break flag.
_KEEP_COLUMNS = {
    "time_period",
    "value",
    "obs_status",
    "source",
    "unit_measure",
}


# ── Request helpers ──────────────────────────────────────────────────────────


def _plain_english_error(status: int | None) -> RuntimeError:
    """Convert an HTTP error status to a RuntimeError with a user-facing message."""
    if status == 429:
        return RuntimeError("ILOSTAT rate limit reached — wait a moment and try again.")
    if status in (500, 503):
        return RuntimeError(
            "ILOSTAT API returned a server error and may be temporarily down."
            " Try again shortly."
        )
    return RuntimeError(f"ILOSTAT API error (HTTP {status}).")


def _request(
    span_name: str,
    call: Callable[[], _T],
    *,
    allow_not_found: bool,
    **attrs: str,
) -> _T | None:
    """
    Run one ILOSTAT API call inside a span, with a debug log and clean errors.

    Parameters
    ----------
    span_name       : OTel span name, e.g. "ilostat.api.data"
    call            : zero-argument function that performs the sdmx1 request
    allow_not_found : if True, HTTP 400/404 returns None instead of raising
    attrs           : context recorded on the span and in the log (flow_id, ...)

    Returns
    -------
    The call's result, or None for 400/404 when allow_not_found is True.

    Raises
    ------
    RuntimeError with a plain-English message on timeout, connection failure,
    or any other HTTP error.
    """
    t0 = time.perf_counter()
    with _tracer.start_as_current_span(span_name) as span:
        for key, value in attrs.items():
            span.set_attribute(key, value)
        try:
            result = call()
        except Timeout as exc:
            raise RuntimeError(_TIMEOUT_MESSAGE) from exc
        except RequestsConnectionError as exc:
            raise RuntimeError(_CONNECTION_MESSAGE) from exc
        except HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status is not None:
                span.set_attribute("http_status", status)
            _log_api(attrs, status, t0)
            if allow_not_found and status in _NOT_FOUND_STATUSES:
                return None
            raise _plain_english_error(status) from exc
        span.set_attribute("http_status", _HTTP_OK)
        _log_api(attrs, _HTTP_OK, t0)
        return result


def _log_api(attrs: Mapping[str, str], status: int | None, t0: float) -> None:
    """Emit the per-request DEBUG log line."""
    logger.debug(
        "api",
        **attrs,
        http_status=status,
        duration_ms=int((time.perf_counter() - t0) * 1000),
    )


def _annotation(flow: object, annotation_type: str) -> str | None:
    """Return the value of a flow's annotation of the given type, or None."""
    for ann in getattr(flow, "annotations", []):
        if getattr(ann, "type", None) == annotation_type:
            title = getattr(ann, "title", None)
            return str(title) if title is not None else None
    return None


def _order(flow: object) -> int:
    """Return ILOSTAT's ORDER rank for a flow; flows without one sort last."""
    raw = _annotation(flow, _ANNOTATION_ORDER)
    try:
        return int(raw) if raw is not None else _UNRANKED
    except ValueError:
        return _UNRANKED


def _last_updated(flow: object) -> str | None:
    """Return the flow's LAST_UPDATE annotation as an ISO 8601 string, or None."""
    raw = _annotation(flow, _ANNOTATION_LAST_UPDATE)
    if raw is None:
        return None
    try:
        return datetime.strptime(raw, _LAST_UPDATE_FORMAT).isoformat()
    except ValueError:
        logger.warning("unparseable_last_update", value=raw)
        return None


# ── Public functions ──────────────────────────────────────────────────────────


def get_time_series(
    flow_id: str,
    country: str,
    start: str,
    end: str,
    *,
    dims: Mapping[str, str] | None = None,
    freq: str = "A",
    sex: str = SEX_TOTAL,
) -> pd.DataFrame:
    """
    Fetch a time series from ILOSTAT and return a clean DataFrame.

    Parameters
    ----------
    flow_id : ILOSTAT dataflow ID (e.g. "DF_UNE_DEAP_SEX_AGE_RT")
    country : ISO 3166-1 alpha-3 country code (e.g. "DEU")
    start   : start year, inclusive (e.g. "2010")
    end     : end year, inclusive (e.g. "2023")
    dims    : extra SDMX dimension values, e.g. {"AGE": "AGE_YTHADULT_YGE15"}.
              Any dimension left out returns every value of it, i.e. several
              rows per year.
    freq    : frequency filter applied post-fetch ("A" = annual, "Q" = quarterly)
    sex     : SEX dimension value (default SEX_TOTAL)

    Returns
    -------
    DataFrame with the columns in _KEEP_COLUMNS that ILOSTAT returned:
    time_period (str), value, obs_status, source, unit_measure.
    Empty DataFrame if the country has no data (HTTP 404/400).

    Raises
    ------
    RuntimeError with a plain-English message on timeout, connection failure,
    or any other HTTP error.
    """
    key: dict[str, str] = {"REF_AREA": country, "SEX": sex, **(dims or {})}
    resp = _request(
        "ilostat.api.data",
        lambda: _client.data(
            flow_id, key=key, params={"startPeriod": start, "endPeriod": end}
        ),
        allow_not_found=True,
        flow_id=flow_id,
        country=country,
    )
    if resp is None:
        return pd.DataFrame()

    df = cast(pd.DataFrame, sdmx.to_pandas(resp, attributes="o")).reset_index()  # type: ignore[no-untyped-call]
    if df.empty:
        return df

    df.columns = [c.lower() for c in df.columns]
    if "freq" in df.columns and freq:
        df = df[df["freq"] == freq]
    df = df[[c for c in df.columns if c in _KEEP_COLUMNS]].copy()
    # sdmx1 may return a Period object; downstream code compares year strings.
    if "time_period" in df.columns:
        df["time_period"] = df["time_period"].astype(str)
    return df.reset_index(drop=True)


@dataclass(frozen=True)
class FlowInfo:
    """
    One entry of ILOSTAT's dataflow catalogue, as plain data.

    description has its HTML stripped. last_updated is when ILOSTAT last
    refreshed the flow's data (ISO 8601), or None if not provided.
    """

    id: str
    title: str
    description: str
    is_modelled: bool
    last_updated: str | None


def get_catalogue() -> dict[str, FlowInfo]:
    """
    Download ILOSTAT's full dataflow catalogue (~1,200 flows, ~5-8 s).

    Returns flow ID -> FlowInfo, in ILOSTAT's own ORDER ranking (flows
    without one come last). Callers should cache this; it changes rarely.

    Raises
    ------
    RuntimeError with a plain-English message on any API failure, or if
    ILOSTAT returns an empty catalogue.
    """
    resp = cast(
        sdmx.message.StructureMessage,
        _request(
            "ilostat.api.dataflow_all",
            lambda: _client.dataflow(),
            allow_not_found=False,
        ),
    )
    if not resp.dataflow:
        raise RuntimeError("ILOSTAT returned an empty dataflow list — try again.")
    ranked = sorted(resp.dataflow.items(), key=lambda item: _order(item[1]))
    return {flow_id: _flow_info(flow_id, flow) for flow_id, flow in ranked}


def _flow_info(flow_id: str, flow: object) -> FlowInfo:
    """Convert one sdmx1 dataflow object to a FlowInfo."""
    name = getattr(flow, "name", None)
    raw_desc = getattr(flow, "description", None)
    return FlowInfo(
        id=flow_id,
        title=str(name) if name else "",
        description=BeautifulSoup(
            str(raw_desc) if raw_desc else "", "html.parser"
        ).get_text(separator=" ", strip=True),
        is_modelled=is_modelled(flow_id),
        last_updated=_last_updated(flow),
    )


def get_countries() -> list[dict[str, str]]:
    """
    Return the valid country/area codes from ILOSTAT's CL_AREA codelist.

    Each entry has keys: code, name; sorted by code.

    Raises RuntimeError on any API failure — an empty list is never a valid
    result (ILOSTAT always has countries), so callers cannot treat [] as
    "no countries".
    """
    resp = cast(
        sdmx.message.StructureMessage,
        _request(
            "ilostat.api.codelist",
            lambda: _client.codelist(_AREA_CODELIST),
            allow_not_found=False,
        ),
    )
    if not resp.codelist:
        raise RuntimeError("ILOSTAT returned no country list — try again shortly.")
    codelist = next(iter(resp.codelist.values()))
    # codelist.items is a plain dict {code_id: Code}, not a bound method
    areas = [
        {
            "code": str(code_id),
            "name": html.unescape(str(code.name)) if code.name else str(code_id),
        }
        for code_id, code in codelist.items.items()
    ]
    return sorted(areas, key=lambda a: a["code"])
