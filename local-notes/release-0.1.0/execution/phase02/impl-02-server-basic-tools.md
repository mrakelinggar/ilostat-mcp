# impl-02-server-basic-tools

## Task
Phase 2 — FastMCP server + 4 basic tools (search_indicators, get_countries,
get_indicator_metadata, get_time_series)

## Spec reference
/Users/mrla/.claude/plans/glimmering-napping-valiant.md

## What was built
- `src/ilostat_mcp/resources.py`: SYSTEM_PROMPT constant + `get_cached_countries()` (module-level cache, avoids re-hitting CL_AREA per request)
- `src/ilostat_mcp/server.py`: FastMCP instance, 4 tool registrations, `ilostat://system-prompt` resource, `main()` entry point
- `tests/test_server.py`: 9 smoke tests covering all 4 tool functions

## Test coverage
- tests/test_server.py: return type, required key shape, empty-dict on invalid flow, empty-list on PRK (no-data country), FLOW_DIMS auto-selection for wage flow (CUR injected, unit_measure present)
- Tests run: **9 passing, 0 failing** (22s with pre-warmed DSD cache)

## Issue fixed during implementation
- Spec said tests should take `client_ready` fixture parameter. The actual fixture in conftest.py is `prewarm_dsd_cache` with `autouse=True` — tests don't need to declare it. Removed the parameter; all 9 tests passed immediately.

## Deviations from spec
- Test count: 9 instead of 7 (split `get_countries` into 2 tests and `search_indicators` into 2 for clarity). Coverage is a superset of spec requirements.

## Blockers
None

## Notes
- `grep -r "import sdmx" src/` hits `resources.py` because `from ilostat_mcp import sdmx_client` contains the substring "sdmx" — but this is importing the wrapper module, not sdmx1 directly. sdmx1 isolation is intact.
- FLOW_DIMS auto-selection works: passing `DF_EAR_EMTA_SEX_CUR_NB` without a `cur` arg correctly injects `CUR_DEFAULT` — confirmed by wage test returning rows with `unit_measure` present.
- Claude Desktop config needed for manual E2E verification (see plan).
