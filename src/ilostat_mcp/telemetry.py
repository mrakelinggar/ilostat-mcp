"""
Observability setup for ilostat-mcp.

Call configure() once in main() before mcp.run().

After configure():
  - structlog.get_logger() returns a bound logger emitting JSON to stdout
  - get_tracer(__name__) returns an OTel Tracer; spans go to Honeycomb if
    HONEYCOMB_API_KEY is set, otherwise discarded silently.

Fail-silent design: when HONEYCOMB_API_KEY is unset, no exporter is created
and all spans are discarded. When Honeycomb is unreachable, BatchSpanProcessor
drops spans silently after its timeout — the MCP keeps running normally.
"""

import logging
import os

import structlog
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def _configure_structlog() -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _configure_otel() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    resource = Resource.create({"service.name": "ilostat-mcp"})
    provider = TracerProvider(resource=resource)

    api_key = os.getenv("HONEYCOMB_API_KEY")
    if api_key:
        exporter = OTLPSpanExporter(
            endpoint="https://api.honeycomb.io/v1/traces",
            headers={"x-honeycomb-team": api_key},
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)


def configure() -> None:
    """Configure structlog and OpenTelemetry. Call once in main() before mcp.run()."""
    _configure_structlog()
    _configure_otel()


def get_tracer(name: str) -> trace.Tracer:
    """Return an OTel Tracer for the given module name.

    Called at module level in server.py and sdmx_client.py. OTel's ProxyTracer
    correctly delegates to the real provider once configure() fires.
    """
    return trace.get_tracer(name)
