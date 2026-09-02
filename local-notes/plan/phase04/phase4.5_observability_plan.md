# Phase 4.5 — Observability

## What and why

Right now, when a tool call is slow or returns unexpected results, there is no record of
what happened or where time was spent. Adding structured logs means every tool call leaves
a trace in stdout — what it was called with, what it returned, how long it took. Adding
OpenTelemetry spans means those events are sent to Honeycomb, where you can see the full
causal chain of a request as a timing waterfall (tool call → ILOSTAT API call → response).

Without this, debugging a slow or broken call means re-running it manually and guessing.
With it, you open Honeycomb and see the exact span that was slow. The benchmark article
also benefits: screenshots of real Honeycomb traces make the observability story concrete.

---

## Unknowns / resolved decisions

**Q: Where does OTel setup code live?**
CLAUDE.md says span creation lives only in `server.py` and `sdmx_client.py`. Setup
(TracerProvider, exporter config) goes in a new `telemetry.py` module so it doesn't
pollute either file.

**Q: Does OTel fail silently when offline?**
Yes. `BatchSpanProcessor` drops spans when the exporter cannot reach Honeycomb — no
exception is raised. If `HONEYCOMB_API_KEY` is unset, the exporter is never created;
spans are discarded by a no-export provider. Either way the MCP runs normally.

**Q: Does python-dotenv belong as a runtime dep?**
Yes. The `.env` file is used in dev; `load_dotenv()` in `telemetry.py` loads it
automatically. In production (Claude Desktop), env vars come from the client config and
`load_dotenv()` is a no-op when no `.env` is present.

---

## Files to create/modify

| File | Change |
|---|---|
| `src/ilostat_mcp/telemetry.py` | **Create** |
| `src/ilostat_mcp/server.py` | Add structlog + OTel spans |
| `src/ilostat_mcp/sdmx_client.py` | Replace stdlib logging; add API spans |
| `pyproject.toml` | Add 4 runtime dependencies |

---

## `telemetry.py` — specification

```python
"""
Observability setup. Call configure() once in main() before mcp.run().

After configure():
  - structlog.get_logger() returns a bound logger emitting JSON to stdout
  - get_tracer(__name__) returns an OTel Tracer; spans go to Honeycomb if
    HONEYCOMB_API_KEY is set, otherwise discarded silently.
"""
```

**Public API:**
- `configure() -> None` — runs both sub-configurers. Call once in `server.main()`.
- `get_tracer(name: str) -> trace.Tracer` — thin wrapper over `trace.get_tracer(name)`.
  Called at module level in server.py / sdmx_client.py; OTel's ProxyTracer correctly
  delegates to the real provider once configure() fires.

**`_configure_structlog()`:**
```python
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
```

**`_configure_otel()`:**
```python
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
```

---

## `pyproject.toml` — new dependencies

Add to `[project].dependencies` (follow existing version-bound convention):
```toml
"structlog>=23.0,<26.0",
"opentelemetry-sdk>=1.20,<3.0",
"opentelemetry-exporter-otlp-proto-http>=1.20,<3.0",
"python-dotenv>=1.0,<2.0",
```

---

## `sdmx_client.py` — changes

**Replace stdlib logger:**
```python
# Remove:  import logging; logger = logging.getLogger(__name__)
# Add:     import structlog; logger: structlog.BoundLogger = structlog.get_logger()
```

**Add at module level:**
```python
import time
from ilostat_mcp.telemetry import get_tracer
_tracer = get_tracer(__name__)
```

**Wrap each of the 4 API call sites.** Span names:
- `get_time_series`       → `"ilostat.api.data"`
- `get_indicator_metadata`→ `"ilostat.api.dataflow"`
- `search_indicators`     → `"ilostat.api.dataflow_all"`
- `get_countries`         → `"ilostat.api.codelist"`

Pattern for each (shown for `get_time_series`; others analogous):
```python
t0 = time.perf_counter()
with _tracer.start_as_current_span("ilostat.api.data") as span:
    span.set_attribute("flow_id", flow_id)
    span.set_attribute("country", country)
    try:
        resp = _client.data(flow_id, key=key, params={...})
        duration_ms = int((time.perf_counter() - t0) * 1000)
        span.set_attribute("http_status", 200)
        logger.debug("api", flow_id=flow_id, country=country,
                     http_status=200, duration_ms=duration_ms)
    except Timeout as exc:
        raise RuntimeError("...") from exc
    except RequestsConnectionError as exc:
        raise RuntimeError("...") from exc
    except HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        duration_ms = int((time.perf_counter() - t0) * 1000)
        span.set_attribute("http_status", status)
        logger.debug("api", flow_id=flow_id, country=country,
                     http_status=status, duration_ms=duration_ms)
        if exc.response is not None and exc.response.status_code in (404, 400):
            return pd.DataFrame()   # or {} or [] depending on function
        raise _plain_english_error(exc) from exc
```

Remove the two existing `logger.debug(...)` calls in the 404/400 paths — the new
span debug log covers them.

`get_indicator_metadata` and `get_countries` return `{}` and `[]` on 404/400 respectively.
`search_indicators` has no 404 special-case — the HTTPError path goes straight to
`_plain_english_error`. Span attributes for search/countries: omit `country`; keep
`flow_id` only where applicable.

---

## `server.py` — changes

**Add at top of imports:**
```python
import time
import structlog
from ilostat_mcp import telemetry
from ilostat_mcp.telemetry import get_tracer
```

**Add at module level (after imports):**
```python
logger: structlog.BoundLogger = structlog.get_logger()
_tracer = get_tracer(__name__)
```

**Update `main()`:**
```python
def main() -> None:
    telemetry.configure()
    mcp.run()
```

**Wrap all 7 tool functions + `labor_market_snapshot` prompt.** Common pattern:
```python
@mcp.tool()
def get_time_series(...) -> list[dict[str, object]]:
    """..."""
    t0 = time.perf_counter()
    with _tracer.start_as_current_span("tool.get_time_series") as span:
        span.set_attribute("dataflow_id", dataflow_id)
        span.set_attribute("country", country)
        span.set_attribute("start_year", start_year)
        span.set_attribute("end_year", end_year)
        span.set_attribute("age_group", age_group)
        try:
            # ALL existing logic unchanged inside the span context
            result = ...
            outcome = (
                "empty"
                if len(result) == 1 and result[0].get("_no_data_reason")
                else "success"
            )
            span.set_attribute("outcome", outcome)
            logger.info(
                "tool", tool="get_time_series", country=country,
                dataflow_id=dataflow_id, outcome=outcome,
                duration_ms=int((time.perf_counter() - t0) * 1000),
            )
            return result
        except (ValueError, RuntimeError) as exc:
            span.set_attribute("outcome", "error")
            span.set_attribute("error.message", str(exc))
            logger.info(
                "tool", tool="get_time_series", country=country,
                dataflow_id=dataflow_id, outcome="error",
                duration_ms=int((time.perf_counter() - t0) * 1000),
            )
            raise
```

**Outcome values:**
- `"success"` — data returned
- `"empty"` — metadata-only return (`_no_data_reason` is set, country has no data)
- `"error"` — validation failed or API error (exception re-raised)

**Span names and key span attributes:**

| Tool/Prompt | Span name | Key attributes |
|---|---|---|
| `search_indicators` | `tool.search_indicators` | `keyword` |
| `get_countries` | `tool.get_countries` | _(none)_ |
| `get_indicator_metadata` | `tool.get_indicator_metadata` | `dataflow_id` |
| `get_time_series` | `tool.get_time_series` | `dataflow_id`, `country`, `start_year`, `end_year`, `age_group` |
| `get_yoy_change` | `tool.get_yoy_change` | `dataflow_id`, `country`, `year`, `age_group` |
| `get_cagr` | `tool.get_cagr` | `dataflow_id`, `country`, `start_year`, `end_year`, `age_group` |
| `get_trend` | `tool.get_trend` | `dataflow_id`, `country`, `start_year`, `end_year`, `age_group` |
| `labor_market_snapshot` | `prompt.labor_market_snapshot` | `countries` (raw input str) |

For `get_countries` and `search_indicators`, outcome is always `"success"` or `"error"`;
no `"empty"` state exists for these two.

For `get_indicator_metadata`: outcome is `"empty"` when result is `{}` (unknown flow),
`"success"` when dict is non-empty.

For `labor_market_snapshot` (prompt, not tool): use `logger.info("prompt", ...)` and
`span name = "prompt.labor_market_snapshot"`. Outcome: `"success"` or `"error"`.

---

## Failure modes

| Failure | Expected behaviour |
|---|---|
| `HONEYCOMB_API_KEY` not set | OTel provider created with no exporter; spans discarded; MCP works normally |
| Honeycomb unreachable (network down) | `BatchSpanProcessor` drops spans silently after timeout; MCP works normally |
| structlog `configure()` not called before first log | Uses structlog default config (PrintLogger, no JSON) — acceptable for tests |
| `dotenv` import fails (not installed) | `try/except ImportError` swallows it; env vars must come from shell |

---

## Verification (acceptance criteria)

1. **All existing tests pass:** `uv run pytest` — zero regressions. Observability is
   additive; it changes no return values.

2. **ruff + mypy clean:** `uv run ruff check src/` and `uv run mypy src/` — zero warnings.

3. **JSON log line on tool call:** Run `fastmcp dev src/ilostat_mcp/server.py`, call
   `get_time_series("DF_UNE_DEAP_SEX_AGE_RT", "DEU", "2020", "2022")`. Expect a JSON
   line on stdout containing `"event": "tool"`, `"tool": "get_time_series"`,
   `"outcome": "success"`, `"duration_ms": <int>`.

4. **DEBUG log on API call:** Same call; expect a JSON line with `"event": "api"`,
   `"flow_id": "DF_UNE_DEAP_SEX_AGE_RT"`, `"country": "DEU"`, `"http_status": 200`.

5. **Empty/error outcomes logged:** Call with PRK (no data) — expect `"outcome": "empty"`.
   Call with invalid flow — expect `"outcome": "error"`.

6. **Honeycomb trace visible:** With `HONEYCOMB_API_KEY` set via `.env`, call a tool,
   open Honeycomb UI, confirm at least one trace with `tool.*` parent and `ilostat.api.*`
   child span.

7. **Offline silence:** Unset `HONEYCOMB_API_KEY`, call tool — no error, MCP responds
   normally.
