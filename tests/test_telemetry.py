"""
Phase 4.5 Observability — unit tests for telemetry.py and instrumented tools.

All tests mock the ILOSTAT SDMX API. No live network calls here.

Every test references the spec section it exercises so a failing test points
directly to the relevant requirement.
"""

import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import structlog
import structlog.testing
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import ilostat_mcp.sdmx_client as sdmx_client_mod
from ilostat_mcp import telemetry
from ilostat_mcp.indicators import AGE_TOTAL, FLOWS

# ── Constants ─────────────────────────────────────────────────────────────────

_VALID_FLOW = FLOWS["unemployment_rate"]  # "DF_UNE_DEAP_SEX_AGE_RT"
_VALID_COUNTRY = "DEU"
_FAKE_COUNTRIES = [{"code": "DEU", "name": "Germany"}]

# A minimal DataFrame that passes the server's data-row path (non-empty result).
_FAKE_SERIES_DF = pd.DataFrame(
    {
        "time_period": ["2020", "2021", "2022"],
        "value": [5.0, 4.8, 3.5],
        "obs_status": ["A", "A", "A"],
        "source": ["LFS", "LFS", "LFS"],
        "unit_measure": ["%", "%", "%"],
    }
)


# ── Test isolation fixtures ───────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _restore_otel_provider():
    """Save and restore the global OTel TracerProvider around each test.

    OTel's public set_tracer_provider() is a "set once" operation — calling it
    a second time logs a warning and does nothing. To achieve real isolation we
    save and restore the private _TRACER_PROVIDER global and the _done flag on
    the Once guard directly. This is internal API access justified by the test
    isolation requirement; no equivalent public API exists.
    """
    import opentelemetry.trace as _otel_trace  # local import avoids circular dep

    original_provider = _otel_trace._TRACER_PROVIDER
    original_done = _otel_trace._TRACER_PROVIDER_SET_ONCE._done
    yield
    _otel_trace._TRACER_PROVIDER = original_provider
    _otel_trace._TRACER_PROVIDER_SET_ONCE._done = original_done


@pytest.fixture(autouse=True)
def _restore_structlog_config():
    """Save and restore the full structlog configuration around each test.

    telemetry._configure_structlog() mutates the global structlog config.
    Restoring it prevents state leakage into tests that don't expect JSON output.
    """
    cfg = structlog.get_config()
    old = {
        "processors": list(cfg["processors"]),
        "wrapper_class": cfg["wrapper_class"],
        "logger_factory": cfg["logger_factory"],
        "cache_logger_on_first_use": cfg["cache_logger_on_first_use"],
    }
    yield
    structlog.configure(**old)


# ── Tests: configure() ────────────────────────────────────────────────────────


def test_configure_without_honeycomb_key_does_not_raise():
    # Spec: configure() runs without error when HONEYCOMB_API_KEY is absent.
    # Failure mode: OTel provider created with no exporter; MCP works normally.
    # Empty string is falsy — no exporter created; load_dotenv() does not
    # override an env var that already exists.
    with patch.dict(os.environ, {"HONEYCOMB_API_KEY": ""}):
        telemetry.configure()


def test_configure_with_honeycomb_key_does_not_raise():
    # Spec: configure() runs without error when HONEYCOMB_API_KEY is set.
    # OTLPSpanExporter is mocked to avoid real HTTP connections in unit tests.
    with (
        patch.dict(os.environ, {"HONEYCOMB_API_KEY": "test_fake_key"}),
        patch("ilostat_mcp.telemetry.OTLPSpanExporter") as mock_exp,
    ):
        mock_exp.return_value = MagicMock()
        telemetry.configure()


# ── Tests: get_tracer() ───────────────────────────────────────────────────────


def test_get_tracer_before_configure_returns_tracer_object():
    # Spec: get_tracer() returns a Tracer before configure() is called.
    # OTel's ProxyTracer is the expected return type at this point.
    tracer = telemetry.get_tracer("test.before_configure")
    assert tracer is not None
    assert hasattr(tracer, "start_as_current_span"), (
        "Tracer must expose start_as_current_span"
    )


def test_get_tracer_after_configure_returns_tracer_object():
    # Spec: get_tracer() returns a Tracer after configure() is called.
    with patch.dict(os.environ, {"HONEYCOMB_API_KEY": ""}):
        telemetry.configure()
    tracer = telemetry.get_tracer("test.after_configure")
    assert tracer is not None
    assert hasattr(tracer, "start_as_current_span")


# ── Test: structlog JSON configuration ───────────────────────────────────────


def test_structlog_configured_with_json_renderer_after_configure():
    # Spec: after configure(), structlog processors include JSONRenderer.
    # CLAUDE.md: "structlog — JSON output, never bare print() or plain-text formatter"
    with patch.dict(os.environ, {"HONEYCOMB_API_KEY": ""}):
        telemetry.configure()
    processor_types = [type(p).__name__ for p in structlog.get_config()["processors"]]
    assert "JSONRenderer" in processor_types, (
        f"JSONRenderer absent from processor chain: {processor_types}"
    )


# ── Test: OTel TracerProvider set after configure() ──────────────────────────


def test_otel_sdk_tracer_provider_set_after_configure():
    # Spec: trace.get_tracer_provider() is an SDKTracerProvider after configure().
    with patch.dict(os.environ, {"HONEYCOMB_API_KEY": ""}):
        telemetry.configure()
    provider = trace.get_tracer_provider()
    assert isinstance(provider, SDKTracerProvider), (
        f"Expected SDKTracerProvider, got {type(provider).__name__}"
    )


# ── Test: no exporter when HONEYCOMB_API_KEY absent ─────────────────────────


def test_no_span_processor_when_honeycomb_key_absent():
    # Spec: provider has no span processors when HONEYCOMB_API_KEY is unset.
    # patch.dict with empty string is falsy; load_dotenv() does not override
    # existing env vars, so this reliably prevents exporter creation.
    with patch.dict(os.environ, {"HONEYCOMB_API_KEY": ""}):
        telemetry._configure_otel()

    provider = trace.get_tracer_provider()
    assert isinstance(provider, SDKTracerProvider)
    # _span_processors is a tuple of registered processors on the multi-processor.
    processors = provider._active_span_processor._span_processors
    assert len(processors) == 0, (
        f"Expected 0 processors with absent key, got {len(processors)}: {processors}"
    )


# ── Test: BatchSpanProcessor added when HONEYCOMB_API_KEY present ────────────


def test_batch_span_processor_added_when_honeycomb_key_present():
    # Spec: provider has a BatchSpanProcessor when HONEYCOMB_API_KEY is set.
    # OTLPSpanExporter is mocked to prevent real HTTP setup.
    with (
        patch.dict(os.environ, {"HONEYCOMB_API_KEY": "test_fake_key"}),
        patch("ilostat_mcp.telemetry.OTLPSpanExporter") as mock_exp,
    ):
        mock_exp.return_value = MagicMock()
        telemetry._configure_otel()

    provider = trace.get_tracer_provider()
    assert isinstance(provider, SDKTracerProvider)
    processors = provider._active_span_processor._span_processors
    assert len(processors) == 1, (
        f"Expected 1 span processor with key set, got {len(processors)}"
    )
    assert isinstance(processors[0], BatchSpanProcessor), (
        f"Expected BatchSpanProcessor, got {type(processors[0]).__name__}"
    )


# ── Test: tool outcome "empty" ────────────────────────────────────────────────


def test_tool_outcome_empty_logged_when_sdmx_returns_no_data():
    # Spec: outcome == "empty" fires when get_time_series returns empty DataFrame.
    # (server.py: outcome = "empty" if len(result)==1 and result[0]["_no_data_reason"])
    from ilostat_mcp.server import get_time_series as server_get_time_series

    with (
        patch(
            "ilostat_mcp.server.resources.get_cached_countries",
            return_value=_FAKE_COUNTRIES,
        ),
        patch(
            "ilostat_mcp.sdmx_client.get_time_series",
            return_value=pd.DataFrame(),
        ),
        structlog.testing.capture_logs() as log_entries,
    ):
        result = server_get_time_series(_VALID_FLOW, _VALID_COUNTRY, "2020", "2022")

    # Result must be a single-element list with _no_data_reason set.
    assert len(result) == 1
    assert result[0].get("_no_data_reason") is not None

    tool_logs = [e for e in log_entries if e.get("event") == "tool"]
    assert len(tool_logs) == 1, f"Expected 1 tool log entry, got: {tool_logs}"
    assert tool_logs[0]["outcome"] == "empty", (
        f"Expected outcome 'empty', got {tool_logs[0].get('outcome')!r}"
    )


# ── Test: tool outcome "error" ────────────────────────────────────────────────


def test_tool_outcome_error_logged_on_invalid_flow_id():
    # Spec: outcome == "error" fires when validation fails; exception is re-raised.
    # No API mock needed: _validate_dataflow raises ValueError before any network call.
    from ilostat_mcp.server import get_time_series as server_get_time_series

    with (
        structlog.testing.capture_logs() as log_entries,
        pytest.raises(ValueError, match="Unknown dataflow"),
    ):
        server_get_time_series(
            "DF_INVALID_FLOW_9999", _VALID_COUNTRY, "2020", "2022"
        )

    tool_logs = [e for e in log_entries if e.get("event") == "tool"]
    assert len(tool_logs) == 1, f"Expected 1 tool log entry, got: {tool_logs}"
    assert tool_logs[0]["outcome"] == "error", (
        f"Expected outcome 'error', got {tool_logs[0].get('outcome')!r}"
    )


# ── Test: tool outcome "success" ──────────────────────────────────────────────


def test_tool_outcome_success_logged_when_data_returned():
    # Spec: outcome == "success" fires when non-empty DataFrame is returned.
    from ilostat_mcp.server import get_time_series as server_get_time_series

    with (
        patch(
            "ilostat_mcp.server.resources.get_cached_countries",
            return_value=_FAKE_COUNTRIES,
        ),
        patch(
            "ilostat_mcp.sdmx_client.get_time_series",
            return_value=_FAKE_SERIES_DF,
        ),
        structlog.testing.capture_logs() as log_entries,
    ):
        result = server_get_time_series(_VALID_FLOW, _VALID_COUNTRY, "2020", "2022")

    # Result must have metadata + at least 1 data row.
    assert len(result) > 1
    assert result[0].get("_no_data_reason") is None

    tool_logs = [e for e in log_entries if e.get("event") == "tool"]
    assert len(tool_logs) == 1, f"Expected 1 tool log entry, got: {tool_logs}"
    assert tool_logs[0]["outcome"] == "success", (
        f"Expected outcome 'success', got {tool_logs[0].get('outcome')!r}"
    )


# ── Test: API span emitted on sdmx_client call ───────────────────────────────


def test_ilostat_api_span_emitted_with_name_and_attributes():
    # Spec: calling sdmx_client.get_time_series emits span "ilostat.api.data"
    # with flow_id and country attributes.
    # Uses SimpleSpanProcessor (not Batch) so spans are immediately in the exporter
    # without requiring a flush call.
    exporter = InMemorySpanExporter()
    test_provider = SDKTracerProvider()
    test_provider.add_span_processor(SimpleSpanProcessor(exporter))
    test_tracer = test_provider.get_tracer("test.sdmx_client")

    mock_resp = MagicMock()
    # Mock sdmx.to_pandas to return an empty DataFrame; get_time_series returns early.
    empty_df = pd.DataFrame()

    with (
        patch.object(sdmx_client_mod, "_tracer", test_tracer),
        patch.object(sdmx_client_mod._client, "data", return_value=mock_resp),
        patch.object(sdmx_client_mod.sdmx, "to_pandas", return_value=empty_df),
    ):
        sdmx_client_mod.get_time_series(
            _VALID_FLOW, _VALID_COUNTRY, "2020", "2022", age=AGE_TOTAL
        )

    spans = exporter.get_finished_spans()
    assert len(spans) == 1, (
        f"Expected 1 span, got {len(spans)}: {[s.name for s in spans]}"
    )
    span = spans[0]
    assert span.name == "ilostat.api.data", (
        f"Expected span name 'ilostat.api.data', got {span.name!r}"
    )
    attrs = dict(span.attributes) if span.attributes else {}
    assert attrs.get("flow_id") == _VALID_FLOW, (
        f"flow_id attribute missing or wrong: {attrs}"
    )
    assert attrs.get("country") == _VALID_COUNTRY, (
        f"country attribute missing or wrong: {attrs}"
    )
