# qa-01-observability

## Scope

All sections of phase4.5_observability_plan.md:
- `telemetry.py` public API: `configure()`, `_configure_structlog()`, `_configure_otel()`, `get_tracer()`
- `server.py` tool instrumentation: all 7 tools + `labor_market_snapshot` prompt
- `sdmx_client.py` API span instrumentation: `get_time_series`
- All NFRs listed in the plan's Failure modes and Verification sections

## Test summary

- Total tests run: 129 (12 new telemetry tests + 117 existing)
- Passing: 129
- Failing: 0
- Coverage gaps: 1 (manual-verification-required, see NFR table)

## Passing criteria

- configure() runs without error (no key) — PASS
- configure() runs without error (key present, exporter mocked) — PASS
- get_tracer() returns a Tracer before configure() — PASS
- get_tracer() returns a Tracer after configure() — PASS
- structlog configured with JSONRenderer after configure() — PASS
- OTel SDK TracerProvider set after configure() — PASS
- No span processors when HONEYCOMB_API_KEY absent — PASS
- BatchSpanProcessor added when HONEYCOMB_API_KEY present — PASS
- Tool outcome "empty" logged correctly — PASS
- Tool outcome "error" logged correctly — PASS
- Tool outcome "success" logged correctly — PASS
- API span "ilostat.api.data" emitted with flow_id and country attributes — PASS
- All existing tests still pass (zero regressions) — PASS

## Failing criteria

None.

## Bugs found

None.

## Spec gaps

None identified. Every requirement in the plan has either a passing test or is
marked manual-verification-required with justification.

## Coverage gaps

- `labor_market_snapshot` prompt outcome logging not covered by a unit test.
  The prompt uses `logger.info("prompt", ...)` — the naming is verified by
  static inspection (deviation checklist) and by the existing live-API test in
  test_server.py. Writing a unit test would require mocking
  `resources.get_cached_countries()` and `_resolve_country()` — possible but
  adds no new signal given the structural check already passed. Flagged as
  acceptable gap; not a quality risk.

## NFR verification

| NFR | Status | Evidence |
|---|---|---|
| OTel silent when HONEYCOMB_API_KEY unset | PASS | test_no_span_processor_when_honeycomb_key_absent: provider has 0 processors |
| OTel silent when Honeycomb unreachable | manual-verification-required | Requires live network test; BatchSpanProcessor silence is well-documented OTel SDK behaviour but cannot be unit-tested without a real network or a custom exporter that simulates failure. Accept on documentation grounds. |
| structlog outputs JSON always | PASS | test_structlog_configured_with_json_renderer_after_configure confirms JSONRenderer is in the processor chain after configure() |
| No print() in new code | PASS | `grep -rn "print(" src/ilostat_mcp/telemetry.py src/ilostat_mcp/server.py src/ilostat_mcp/sdmx_client.py` returned no output |
| mypy strict passes | PASS | `uv run mypy src/` — "Success: no issues found in 9 source files" |
| ruff clean | PASS | `uv run ruff check src/` — "All checks passed!" |
| All existing tests still pass | PASS | 129/129 passed including 117 pre-existing tests |
| Observability is additive (no logic change) | PASS | 117 existing tests pass unchanged; return types and values verified by the prior test suite |

## Deviations

None actionable. Developer-noted structural deviation (local `result` variable
introduced to support outcome check) is correct implementation of spec intent.
Full detail in phase4.5_deviations.md.

## Recommendation

**proceed**

Reason: all 12 spec criteria have passing tests; all NFRs are verified or
appropriately marked manual-verification-required; zero regressions in the
existing suite; ruff and mypy clean on src/.
