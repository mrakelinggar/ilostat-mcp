# ilostat-mcp

MCP server that gives AI assistants such as Claude live access to [ILOSTAT](https://ilostat.ilo.org/) — the International Labour Organization's statistics database — for employment and wage data, with automatic detection of methodology breaks (points where a country changed how it measures a statistic, so values before and after aren't directly comparable).

![Demo: Claude Desktop answering two questions with ilostat-mcp — a clean series for Japan, and an Australian series with a 2018 methodology break](https://raw.githubusercontent.com/mrakelinggar/ilostat-mcp/main/docs/demo.gif)

## Installation

Setup takes about five minutes and is done once. You don't need to know how to code.

### Step 1 — Install uv (one time)

[uv](https://docs.astral.sh/uv/) is a small, free tool that downloads and runs ilostat-mcp for Claude. You install it once; after that, it fetches ilostat-mcp automatically.

- **Mac:** open the **Terminal** app (press Cmd+Space, type "Terminal", press Enter), paste this line and press Enter:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **Windows:** open **PowerShell** (Start menu → type "PowerShell"), paste this line and press Enter:
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

When it finishes, close the window. You don't need to install Python or ilostat-mcp yourself — uv handles both.

### Step 2 — Add ilostat-mcp to Claude Desktop

1. In Claude Desktop, open **Settings → Desktop app**, scroll down to **Extensions**, click **Manage**, then **Edit Config**. This opens a file called `claude_desktop_config.json`.
2. Open that file in a text editor (TextEdit on Mac, Notepad on Windows).
3. **If the file is empty or only contains `{}`**, replace everything with:
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
   **If the file already has text in it**, don't delete anything. Look for `"mcpServers": {` and add the `"ilostat-mcp": { ... }` block inside it, with a comma between it and any entry before or after it. If there is no `"mcpServers"` yet, add the whole `"mcpServers": { ... }` section just after the first `{`, followed by a comma.
4. Save the file.

### Step 3 — Restart Claude Desktop

Quit Claude Desktop completely (Mac: Cmd+Q; Windows: right-click the Claude icon in the system tray → Quit), then open it again. Closing the window is not enough.

The first start can take a minute while uv downloads ilostat-mcp. To check it worked, go to **Settings → Customize → Connectors** — **ilostat-mcp** should be listed. Then try one of the questions below.

### If it doesn't work

- **Claude says it can't find `uvx`, or ilostat-mcp doesn't appear:** Claude Desktop sometimes can't find uv on its own. Give it the full location instead:
  1. Mac: in Terminal, run `which uvx`. Windows: in PowerShell, run `where.exe uvx`.
  2. Copy the line it prints (for example `/Users/yourname/.local/bin/uvx`).
  3. In the config file, replace `"uvx"` with that location in quotes. On Windows, double every backslash — `C:\Users\yourname\.local\bin\uvx.exe`.
  4. Save and restart Claude Desktop again.
- **It showed an error the very first time:** the first download may have taken too long. Restart Claude Desktop once more.
- **Claude Desktop says the config file is invalid:** a comma or bracket is usually missing or extra. Paste the file's contents into [jsonlint.com](https://jsonlint.com/) to find the mistake.

### For developers

`pip install ilostat-mcp` installs an `ilostat-mcp` command; use `"command": "ilostat-mcp"` (no `args`) in any MCP client config.

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
