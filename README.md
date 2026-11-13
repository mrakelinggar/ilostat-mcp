# ilostat-mcp

MCP server that gives AI assistants such as Claude live access to [ILOSTAT](https://ilostat.ilo.org/) — the International Labour Organization's statistics database — for employment and wage data, with automatic detection of methodology breaks (points where a country changed how it measures a statistic, so values before and after aren't directly comparable).

![Demo: Claude Desktop answering two questions with ilostat-mcp — a clean series for Japan, and an Australian series with a 2018 methodology break](https://raw.githubusercontent.com/mrakelinggar/ilostat-mcp/main/docs/demo.gif)

## Installation

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/). Add this to your MCP client config. For Claude Desktop, edit `claude_desktop_config.json` (on macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "ilostat-mcp": {
      "command": "uvx",
      "args": ["ilostat-mcp"]
    }
  }
}
```

Quit and reopen Claude Desktop. `uvx` downloads the package from PyPI and runs it — no separate install step.

If Claude Desktop reports that `uvx` cannot be found, replace `"uvx"` with its full path (run `which uvx` on macOS/Linux or `where uvx` on Windows). Desktop apps do not always see the same PATH as your terminal.

### Alternative — pip

```bash
pip install ilostat-mcp
```

Then use `"command": "ilostat-mcp"` (no `args`) in the config above.

## Try asking

- *How did Japan's unemployment rate change between 2015 and 2023?*
- *What was the trend in Australia's unemployment rate from 2015 to 2020?* — the answer should flag ILOSTAT's 2018 methodology break.
- *Compare unemployment in Germany and Canada from 2015 to 2023.*
- *What were average monthly earnings in Brazil in 2022?*

## What it can do

Claude picks the right tools automatically; you only ask the question.

- **Find indicators** — search ILOSTAT's employment and wage datasets by keyword (matches dataset titles), and look up definitions, units and last-updated dates.
- **Fetch time series** — annual data for any country, with methodology breaks always reported alongside the numbers.
- **Derived statistics** — year-over-year change, compound annual growth rate (CAGR) and linear trend. If a methodology break falls inside the requested range, the result carries a warning.
- **Labour market snapshot** — a ready-made prompt that summarises the labour market for one to three countries.

Coverage is ILOSTAT's employment and wage themes only. When ILOSTAT has no data for a question, the server says so explicitly rather than returning an empty or estimated number.

## Methodology-break detection

Every time series is checked for two signals: ILOSTAT's own break flag (`obs_status = "B"`, which catches survey redesigns that keep the same name) and changes in the survey source. Each break lists which signal found it. When a break falls inside the range of a year-over-year, CAGR or trend calculation, the result carries a `_break_warning` — a trend line through a methodology break is a wrong number that looks right.

Example — CAGR of Australia's unemployment rate, 2015–2020. ILOSTAT flags a break in 2018, but the survey name is the same on both sides, so a source comparison alone would miss it:

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

A hallucination benchmark comparing bare-LLM vs. MCP-equipped agent answers across 30+ questions with ground truth pulled from the live ILOSTAT API. Results in [`benchmark/`](https://github.com/mrakelinggar/ilostat-mcp/tree/main/benchmark).

## Development

```bash
uv sync
uv run pytest                       # live API tests
uv run ruff check src/ tests/       # lint
uv run ruff format src/ tests/      # format
uv run mypy src/                    # type check
```

CI runs on every push: lint → type check → tests.

## Acknowledgements

Thanks to [Kanza Nabeela Puteri](mailto:kanzanabeela@gmail.com) for brainstorming input on the server's workflow and for verifying the benchmark ground truth against live ILOSTAT data.

## License

MIT — see [LICENSE](https://github.com/mrakelinggar/ilostat-mcp/blob/main/LICENSE).
