"""
FastMCP server for ILOSTAT — registration and instrumentation, no business logic.

Tool implementations live in ilostat_mcp/tools/. This file wraps each one in
a span plus an INFO log (_instrumented), registers it with FastMCP, and
provides the entry point.

Adding a new tool: write a handler in tools/, then add one line here
(name = _instrumented(module.handler)) and one mcp.tool(name) call.
"""

import functools
import inspect
import time
from collections.abc import Callable, Mapping
from typing import ParamSpec, TypeVar

import structlog
from fastmcp import FastMCP
from opentelemetry.trace import Span

import ilostat_mcp.telemetry as telemetry
from ilostat_mcp.resources import (
    get_codelist_area,
    get_codelist_indicator,
    get_system_prompt,
)
from ilostat_mcp.tools import derived, lookup, snapshot, time_series

logger: structlog.BoundLogger = structlog.get_logger()
_tracer = telemetry.get_tracer(__name__)

_P = ParamSpec("_P")
_R = TypeVar("_R")


# ── Instrumentation ───────────────────────────────────────────────────────────


def _outcome(result: object) -> str:
    """
    Classify a handler's return value as "empty" or "success".

    Empty means nothing was found: [] / {} (no search match, unknown flow), or
    a series whose metadata sets _no_data_reason.
    """
    if not result:
        return "empty"
    if (
        isinstance(result, list)
        and isinstance(result[0], dict)
        and result[0].get("_no_data_reason")
    ):
        return "empty"
    return "success"


def _finish(
    span: Span,
    kind: str,
    name: str,
    inputs: Mapping[str, object],
    outcome: str,
    t0: float,
) -> None:
    """Record the outcome on the span and emit the per-call INFO log."""
    span.set_attribute("outcome", outcome)
    logger.info(
        kind,
        tool=name,
        inputs=dict(inputs),
        outcome=outcome,
        duration_ms=int((time.perf_counter() - t0) * 1000),
    )


def _instrumented(fn: Callable[_P, _R], kind: str = "tool") -> Callable[_P, _R]:
    """
    Wrap a tool or prompt handler in an OTel span and an INFO log line.

    The span is named "<kind>.<function name>" and carries every input as an
    attribute. The log has tool, inputs, outcome (success / empty / error) and
    duration_ms. Exceptions are re-raised unchanged; OTel marks the span as an
    error. functools.wraps keeps the signature and docstring, so FastMCP
    builds the same schema as for the bare handler.
    """
    signature = inspect.signature(fn)
    name = fn.__name__

    @functools.wraps(fn)
    def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
        inputs = bound.arguments
        t0 = time.perf_counter()
        with _tracer.start_as_current_span(f"{kind}.{name}") as span:
            for key, value in inputs.items():
                span.set_attribute(key, str(value))
            try:
                result = fn(*args, **kwargs)
            except (ValueError, RuntimeError) as exc:
                # Expected failures: bad input or an ILOSTAT outage, with a
                # plain-English message already written for the user.
                span.set_attribute("error.message", str(exc))
                _finish(span, kind, name, inputs, "error", t0)
                raise
            except Exception:
                # Last resort: anything else is a bug. Log it at ERROR so it is
                # visible, then re-raise unchanged.
                logger.exception("unexpected_error", tool=name, inputs=dict(inputs))
                raise
            _finish(span, kind, name, inputs, _outcome(result), t0)
            return result

    return wrapper


# ── Tools ─────────────────────────────────────────────────────────────────────
# Module-level names are the instrumented handlers, so
# `from ilostat_mcp.server import get_time_series` gives exactly what MCP calls.

search_indicators = _instrumented(lookup.search_indicators)
get_countries = _instrumented(lookup.get_countries)
get_indicator_metadata = _instrumented(lookup.get_indicator_metadata)
get_time_series = _instrumented(time_series.get_time_series)
get_yoy_change = _instrumented(derived.get_yoy_change)
get_cagr = _instrumented(derived.get_cagr)
get_trend = _instrumented(derived.get_trend)

mcp = FastMCP("ilostat-mcp")

mcp.tool(search_indicators)
mcp.tool(get_countries)
mcp.tool(get_indicator_metadata)
mcp.tool(get_time_series)
mcp.tool(get_yoy_change)
mcp.tool(get_cagr)
mcp.tool(get_trend)

# ── Resources ─────────────────────────────────────────────────────────────────

mcp.resource("ilostat://system-prompt")(get_system_prompt)
mcp.resource("ilostat://codelists/area")(get_codelist_area)
mcp.resource("ilostat://codelists/indicator")(get_codelist_indicator)

# ── Prompts ───────────────────────────────────────────────────────────────────

labor_market_snapshot = _instrumented(snapshot.labor_market_snapshot, kind="prompt")
mcp.prompt(labor_market_snapshot)


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    """Configure observability then start the MCP server."""
    telemetry.configure()
    mcp.run()
