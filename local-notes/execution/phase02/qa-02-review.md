# qa-02-review — Phase 2 Server + Basic Tools

## Verdict
PASS

## Critical findings (blockers — must fix before Phase 3)
None.

## Minor findings (should fix but not blocking)
None.

## Checklist results
| Check | Result | Notes |
|---|---|---|
| SDMX isolation | ✅ | `import sdmx` appears only in `sdmx_client.py`. `resources.py` imports `sdmx_client` (the module), not the library — clean. |
| No attributions | ✅ | No AI or tool attributions anywhere. |
| Thin server (no business logic) | ✅ | Each tool is 1–9 lines. Dimension logic (FLOW_DIMS lookup) is the only non-delegation code and belongs here by design. |
| FLOW_DIMS auto-selection | ✅ | `server.py:60–62` — `dim = FLOW_DIMS.get(dataflow_id)`, then `age`/`cur` set accordingly. Callers never pass dimension codes. |
| DataFrame → list[dict] | ✅ | `server.py:66–68` — `if df.empty: return []` then `df.to_dict(orient="records")`. Handles both empty-no-columns and empty-with-columns correctly. |
| Countries cache pattern | ✅ | `resources.py:10` — module-level `_countries_cache: list[dict] | None = None`, populated via `global` assignment on first call. |
| System prompt content | ✅ | All 6 required elements present: call ordering, never-fabricate rule, country ambiguity, survey-over-modelled, LCU explanation, obs_status B = break. |
| main() entry point | ✅ | `server.py:71–72` — `def main() -> None: mcp.run()`. Importable, matches `pyproject.toml` entry point. |
| Tests import functions directly | ✅ | `test_server.py:10–15` imports the 4 tool functions from `ilostat_mcp.server`, not the `mcp` instance. |
| Tests no mocks | ✅ | No `unittest.mock` or `pytest-mock` usage. All tests hit the real API. |
| Tests have timeout | ✅ | All 9 tests have `@pytest.mark.timeout(30)`. |
| PRK empty test present | ✅ | `test_prk_returns_empty_list` — `get_time_series(_UNEMPLOYMENT_FLOW, "PRK", "2010", "2023")` asserts `== []`. |
| Wage unit_measure test | ✅ | `test_wage_flow_auto_selects_cur_and_has_unit_measure` — FRA wages 2020–2023, asserts `"unit_measure" in row` for every row. |
| KISS / DRY | ✅ | No duplicated logic. Constants (`_UNEMPLOYMENT_FLOW`, `_WAGE_FLOW`, required key sets) extracted at module level in test file. |

## Notes
- Developer delivered 9 tests vs. the 7 specified — 2 extras (`test_is_modelled_is_bool`, `test_each_entry_has_code_and_name_if_non_empty`). Both add genuine coverage; no action needed.
- `get_time_series` tool description already mentions `obs_status "B"` = methodology break. This is accurate — `obs_status` is returned in row data now. Phase 3 adds the dedicated `_breaks` detection layer on top; no conflict.
- The `ilostat://system-prompt` resource is registered via `@mcp.resource(...)` decorator on a plain function — correct FastMCP 3.x pattern.
