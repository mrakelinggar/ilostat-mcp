# impl-01-observability

## Task
Implement Phase 4.5 Observability: structlog JSON logging + OpenTelemetry spans for all tool and API call sites.

## Spec reference
Phase 4.5 Observability — phase4.5_observability_plan.md

## What was built
- `src/ilostat_mcp/telemetry.py`: created — `configure()`, `_configure_structlog()`, `_configure_otel()`, `get_tracer()`
- `pyproject.toml`: added 4 runtime deps (structlog, opentelemetry-sdk, opentelemetry-exporter-otlp-proto-http, python-dotenv); reordered existing deps alphabetically
- `src/ilostat_mcp/sdmx_client.py`: replaced `import logging` / `logging.getLogger` with structlog + `get_tracer`; wrapped all 4 API call sites in OTel spans with `http_status` attribute and `logger.debug("api", ...)` log; removed two old stdlib `logger.debug(...)` calls in 404/400 branches
- `src/ilostat_mcp/server.py`: added `time`, `structlog`, `telemetry`, `get_tracer` imports; added module-level `logger` and `_tracer`; wrapped all 7 tools and `labor_market_snapshot` prompt in OTel spans with outcome + duration logging; updated `main()` to call `telemetry.configure()` before `mcp.run()`

## Test results
- ruff: PASS
- mypy: PASS (9 source files, no issues)
- pytest: 117/117 passing (64s)

## Deviations from spec
One minor structural deviation in `get_time_series`, `get_yoy_change`, `get_cagr`, and `get_trend` in `server.py`: the original functions had direct `return` statements inside the `if df.empty:` branch. To capture the result before computing `outcome`, I introduced a local `result` variable and returned it at the end of the success path. The logic is identical — only the code shape changed to support the outcome check without duplicating the logger.info call.

Six lines in the initial implementation exceeded the 88-char limit (due to added indentation inside `with` + `try` blocks) and were wrapped to multi-line calls. No behaviour change.

## Blockers
None

## Needs Verification
- Acceptance criteria 3–7 from the plan require a live run: JSON log line on tool call, DEBUG log on API call, empty/error outcomes logged, Honeycomb trace visible with HONEYCOMB_API_KEY set, and offline silence without the key. These need a manual `fastmcp dev` run — cannot be verified by pytest alone.

## Notes
- `http_status` span attribute is omitted (not set to None) when `exc.response is None` in the HTTPError branch, since OTel's `set_attribute` does not accept None. The `logger.debug` call still passes `http_status=None` so the field appears in the JSON log.
- `python-dotenv` is a runtime dep but wrapped in `try/except ImportError` per spec, for defence-in-depth if somehow not installed.
- `search_indicators` in `sdmx_client.py` has a scoping consideration: the `resp` variable is assigned inside the `with` block but used after it (in the `for flow_id, flow in resp.dataflow.items()` loop). This works because Python's `with` block does not create a new scope. mypy is happy with this pattern.
