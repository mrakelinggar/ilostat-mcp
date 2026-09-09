"""
FastMCP server for ILOSTAT — registration only, no business logic.

All tool implementations live in ilostat_mcp/tools/. Validation helpers
live in ilostat_mcp/validation.py. This file wires FastMCP registrations
and the entry point.

Adding a new tool: create a handler in tools/, then add two lines here
(import + mcp.tool call).
"""

from fastmcp import FastMCP

import ilostat_mcp.telemetry as telemetry
from ilostat_mcp.resources import (
    get_codelist_area,
    get_codelist_indicator,
    get_system_prompt,
)
from ilostat_mcp.tools.derived import get_cagr, get_trend, get_yoy_change
from ilostat_mcp.tools.lookup import (
    get_countries,
    get_indicator_metadata,
    search_indicators,
)
from ilostat_mcp.tools.snapshot import labor_market_snapshot
from ilostat_mcp.tools.time_series import get_time_series

mcp = FastMCP("ilostat-mcp")

# ── Tools ─────────────────────────────────────────────────────────────────────
# mcp.tool() is an identity decorator: it registers the function and returns it
# unchanged. Importing into this namespace keeps `from ilostat_mcp.server import X`
# working for tests without requiring any changes to the test files.

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

mcp.prompt(labor_market_snapshot)


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    """Configure observability then start the MCP server."""
    telemetry.configure()
    mcp.run()
