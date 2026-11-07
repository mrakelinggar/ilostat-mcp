# ilostat-mcp

MCP server giving AI agents access to ILOSTAT employment and wage data, with automatic methodology-break detection.

## Installation

### Option 1 — directly from GitHub (no manual install)

Add this to your MCP client config. For Claude Desktop, edit `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ilostat-mcp": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/mrakelinggar/ilostat-mcp", "ilostat-mcp"]
    }
  }
}
```

`uvx` fetches and installs the package from GitHub automatically. Restart Claude Desktop after editing the config.

### Option 2 — install from source

```bash
git clone https://github.com/mrakelinggar/ilostat-mcp
cd ilostat-mcp
pip install .
```

This installs an `ilostat-mcp` command into your Python environment. Then add it to your config:

```json
{
  "mcpServers": {
    "ilostat-mcp": {
      "command": "ilostat-mcp"
    }
  }
}
```

Restart Claude Desktop after editing the config. Confirm **ilostat-mcp** appears in the tools panel before running queries.

## Tools

| Tool | Purpose |
|---|---|
| `search_indicators(keyword)` | Find ILOSTAT dataflows by keyword. Dataflow IDs act as filters (per country, age, sex) rather than a flat indicator list, so this searches titles and descriptions. |
| `get_countries()` | List valid country codes from the `CL_AREA` codelist. |
| `get_indicator_metadata(dataflow_id)` | Definition, units, source, and last-updated date for a dataflow. |
| `get_time_series(dataflow_id, country, start, end)` | Raw data pull. Always includes a `_breaks` field — every series comes with its break status. |
| `get_yoy_change(dataflow_id, country, year)` | Year-over-year % change. |
| `get_cagr(dataflow_id, country, start, end)` | Compound annual growth rate. Warns or refuses if the range spans a detected methodology break. |
| `get_trend(dataflow_id, country, start, end)` | Linear trend and slope. Same break-spanning rule as `get_cagr`. |

## Methodology-break detection

Every `get_time_series` call automatically checks two signals: ILOSTAT's own break flag (`obs_status = "B"`, which catches survey redesigns that keep the same name) and changes in the survey source. Each break lists which signal found it. When a break falls inside the range of `get_yoy_change`, `get_cagr` or `get_trend`, the result carries a `_break_warning` — a trend line through a methodology break is a wrong number that looks right.

Example — `get_cagr("DF_UNE_DEAP_SEX_AGE_RT", "AUS", "2015", "2020")`. ILOSTAT flags a break in Australia's series in 2018, but the survey name is the same on both sides, so a source comparison alone would miss it:

```json
"_breaks": [{"year": "2018",
             "source_before": "LFS - Labour Force Survey",
             "source_after": "LFS - Labour Force Survey",
             "reasons": ["ilostat_break_flag"]}],
"_break_warning": "Methodology break within 2015-2020 at 2018 (ILOSTAT flags a break in series). Values across a methodology break are not directly comparable — interpret this result with caution."
```

## Data freshness

Everything comes from ILOSTAT's live SDMX API and is kept in memory for up to 24 hours, so repeated questions don't re-download the same data. An answer can therefore be up to 24 hours behind the live site; restarting the server always fetches fresh. Nothing is stored on disk.

## Benchmark

A hallucination benchmark comparing bare-LLM vs. MCP-equipped agent answers across 30+ questions with ground truth pulled from the live ILOSTAT API. Results in [`benchmark/`](benchmark/).

## Development

```bash
uv sync
uv run pytest                       # live API tests
uv run ruff check src/ tests/       # lint
uv run ruff format src/ tests/      # format
uv run mypy src/                    # type check
```

CI runs on every push: lint → type check → tests.

## License

MIT — see [LICENSE](LICENSE).
