"""Tool handlers for indicator and country lookup."""

import time

import structlog

from ilostat_mcp import resources, sdmx_client, telemetry

logger: structlog.BoundLogger = structlog.get_logger()
_tracer = telemetry.get_tracer(__name__)


def search_indicators(keyword: str) -> list[dict[str, object]]:
    """
    Search ILOSTAT dataflows by keyword. Returns up to 20 matches with their
    dataflow ID, title, and whether the series is an ILO modelled estimate
    (is_modelled: true) or survey data (is_modelled: false). Use the dataflow
    ID in subsequent calls. Prefer survey data (is_modelled: false).
    """
    t0 = time.perf_counter()
    with _tracer.start_as_current_span("tool.search_indicators") as span:
        span.set_attribute("keyword", keyword)
        try:
            result = sdmx_client.search_indicators(keyword)
            span.set_attribute("outcome", "success")
            logger.info(
                "tool",
                tool="search_indicators",
                keyword=keyword,
                outcome="success",
                duration_ms=int((time.perf_counter() - t0) * 1000),
            )
            return result
        except (ValueError, RuntimeError) as exc:
            span.set_attribute("outcome", "error")
            span.set_attribute("error.message", str(exc))
            logger.info(
                "tool",
                tool="search_indicators",
                keyword=keyword,
                outcome="error",
                duration_ms=int((time.perf_counter() - t0) * 1000),
            )
            raise


def get_countries() -> list[dict[str, str]]:
    """
    List all valid country codes from ILOSTAT's CL_AREA codelist.
    Returns [{code, name}]. Use these codes in get_time_series.
    """
    t0 = time.perf_counter()
    with _tracer.start_as_current_span("tool.get_countries") as span:
        try:
            result = resources.get_cached_countries()
            span.set_attribute("outcome", "success")
            logger.info(
                "tool",
                tool="get_countries",
                outcome="success",
                duration_ms=int((time.perf_counter() - t0) * 1000),
            )
            return result
        except (ValueError, RuntimeError) as exc:
            span.set_attribute("outcome", "error")
            span.set_attribute("error.message", str(exc))
            logger.info(
                "tool",
                tool="get_countries",
                outcome="error",
                duration_ms=int((time.perf_counter() - t0) * 1000),
            )
            raise


def get_indicator_metadata(dataflow_id: str) -> dict[str, object]:
    """
    Return metadata for a dataflow: title, plain-English description,
    last_updated date, and whether it is a modelled estimate.
    Returns an empty dict if the dataflow ID does not exist.
    """
    t0 = time.perf_counter()
    with _tracer.start_as_current_span("tool.get_indicator_metadata") as span:
        span.set_attribute("dataflow_id", dataflow_id)
        try:
            result = sdmx_client.get_indicator_metadata(dataflow_id)
            outcome = "empty" if result == {} else "success"
            span.set_attribute("outcome", outcome)
            logger.info(
                "tool",
                tool="get_indicator_metadata",
                dataflow_id=dataflow_id,
                outcome=outcome,
                duration_ms=int((time.perf_counter() - t0) * 1000),
            )
            return result
        except (ValueError, RuntimeError) as exc:
            span.set_attribute("outcome", "error")
            span.set_attribute("error.message", str(exc))
            logger.info(
                "tool",
                tool="get_indicator_metadata",
                dataflow_id=dataflow_id,
                outcome="error",
                duration_ms=int((time.perf_counter() - t0) * 1000),
            )
            raise
