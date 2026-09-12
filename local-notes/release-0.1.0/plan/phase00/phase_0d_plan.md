# Phase 0d — MCP Design Quality Research

Date planned: 2026-07-24

## What and why

Before writing `server.py`, we need to lock a set of design decisions: how tool descriptions are written, how errors are returned, what the response structure looks like, and what the system prompt says. These aren't experiments — they're research questions with a right answer that can be found by reading the MCP spec, studying reference MCPs, and thinking through what Claude needs to see to behave correctly. Getting these wrong means rewriting core files mid-build. Unknown 10 (response structure) is especially urgent — it must be decided before Phase 1 because it determines the shape of what `sdmx_client.py` returns.

---

## Unknowns to resolve (7)

### 8. Tool description quality

**What:** Decide how to write the docstring for each tool — how long, what to include, what to explicitly warn against.  
**Why:** The `@mcp.tool` docstring is the only thing Claude reads when deciding which tool to call and what to pass. A vague or missing description leads to wrong tool selection, invented dataflow IDs, or ignored `_breaks` — all of which show up as benchmark failures.

**Research:** Read FastMCP docs on how docstring Args sections map to JSON schema parameter descriptions (verify Claude reads them). Study Anthropic's reference MCPs (filesystem, Postgres, fetch) for description style — how long, what to include, whether they say what the tool does NOT do.

**Applied to our 7 tools — what each description must make explicit:**

| Tool | Must say |
|---|---|
| `search_indicators` | Returns dataflow IDs — pass one to subsequent tools, never invent an ID |
| `get_time_series` | Always includes `_breaks` — check it before interpreting the series |
| `get_indicator_metadata` | Call this to understand units/methodology before fetching data |
| `get_cagr` / `get_trend` | Will warn if break spans the range — intentional, not a failure |
| `get_countries` | Presence here does not mean survey data exists for that country |

**Validation (Phase 2):** Watch the tool-call panel in Claude Desktop on unscripted questions. If the agent guesses a dataflow ID or ignores `_breaks`, the description is wrong.

---

### 9. Error handling contract

**What:** Decide whether a tool signals "no data available" by raising an exception or by returning a structured dict with `has_data: false`.  
**Why:** The benchmark scores whether the agent correctly abstains when there's no data. That's easy to detect in a structured dict but unreliable via caught exceptions — Claude doesn't always treat a protocol-level error as a clean "no data" signal.

**Option A — raise an exception:**
MCP wraps it into a protocol-level error. Agent sees a failed tool call.

**Option B — return a structured error dict:**
```python
return {"error": "no_data", "has_data": False, "message": "No survey data for PRK."}
```
Agent sees a successful call, must inspect the dict.

**Research:** Check how Anthropic's reference MCPs handle absence vs. failure (filesystem raises exceptions; check what Postgres does). Does Claude handle protocol-level errors reliably across benchmark conditions, or does it sometimes treat them as partial success?

**Our likely answer:** Structured error dict for data-absence cases (`has_data: false`), because the benchmark needs to score "did the agent correctly abstain?" — and that's easier to detect in a dict than in a caught exception. Verify before committing.

---

### 10. `get_time_series` response structure ← lock before Phase 1

**What:** Decide and lock the exact JSON shape that `get_time_series` returns.  
**Why:** This structure cascades into `breaks.py`, `server.py`, and all tests. Changing it after Phase 1 means rewriting multiple files. It must be decided now.

**Proposed structure to lock:**
```json
{
  "dataflow_id": "DF_UNE_DEAP_SEX_AGE_RT",
  "country": "NGA",
  "data_type": "survey",
  "unit": "%",
  "breaks_detected": true,
  "break_years": [2014, 2019],
  "break_sources": [
    "HS - General Household Survey",
    "LFS - Unemployment Watch",
    "HIES - Living Standards Survey"
  ],
  "observations": [
    {"year": 2011, "value": 3.77, "source": "HS - General Household Survey"},
    {"year": 2013, "value": 3.71, "source": "HS - General Household Survey"},
    {"year": 2014, "value": 4.56, "source": "LFS - Unemployment Watch"}
  ]
}
```

`breaks_detected` at top level = agent cannot miss it. `source` on each observation = agent can see exactly where the break falls.

**Research:** Is there a response size concern? (A 20-year annual series is small; confirm this won't hit MCP payload limits.) Does embedding `source` per observation make the response too verbose for the agent to parse cleanly?

**Output:** Final locked structure goes in `mcp_design_decisions.md`.

---

### 11. System prompt resource content

**What:** Decide what standing instructions to include in the `ilostat://system-prompt` resource that Claude receives at connection time.  
**Why:** Without explicit instructions, Claude will sometimes guess dataflow IDs, present modelled estimates as survey data, or compute a trend across a break without disclosing it. The system prompt is the one place to prevent all of this at once.

**Must cover:**
1. Call order: `search_indicators` → `get_indicator_metadata` (optional) → `get_time_series` → derived stat tools. Never guess a dataflow ID.
2. Modelled estimates: if `data_type` is `"modelled_estimate"`, say so. Never present an imputed number as a survey observation.
3. Break field: if `breaks_detected` is true, always disclose the methodology change before stating any trend or growth figure.
4. Empty results: if `has_data` is false, say there is no data. Do not supplement from training knowledge.
5. Units: always include the unit in the answer.

**Research:** Does Claude reliably follow instructions in a resource vs. a conversation-level system prompt? Is there a content length limit on FastMCP resources? Check FastMCP docs for how resource content is delivered at connection time.

---

### 12. `search_indicators` output design

**What:** Decide the format and result cap for what `search_indicators` returns.  
**Why:** This is the entry point for every query. If the output is too long the agent gets overwhelmed; if it buries survey and modelled flows together without distinction, the agent picks the wrong one.

**Proposed output:**
```json
{
  "results": [
    {
      "dataflow_id": "DF_UNE_DEAP_SEX_AGE_RT",
      "title": "Unemployment rate by sex and age",
      "data_type": "survey",
      "last_updated": "2026-07-17"
    },
    {
      "dataflow_id": "DF_UNE_2EAP_SEX_AGE_RT",
      "title": "Unemployment rate by sex and age -- ILO modelled estimates, Nov. 2025",
      "data_type": "modelled_estimate",
      "last_updated": "2025-11-01"
    }
  ],
  "note": "Pass the dataflow_id to get_time_series or get_indicator_metadata."
}
```

**Questions to lock:**
- Result cap? (10? 20? all matches?) — start with 20, adjust if agent struggles to pick
- Should modelled flows be shown last or excluded by default?
- Is the `note` field worth including to reinforce call order, or is that the system prompt's job?

---

### 13. MCP Inspector as Phase 2 first-step

**What:** Confirm how to use the MCP Inspector tool to call our tools interactively before testing in Claude Desktop.  
**Why:** Claude Desktop gives you no visibility into raw tool call/response JSON, which makes debugging slow. The Inspector lets you verify tool schemas and responses directly, so you catch description or structure problems before they become Claude Desktop head-scratchers.

**Confirm:**
- Install and invocation: `npx @modelcontextprotocol/inspector python -m ilostat_mcp` (or `uvx` equivalent) — verify the exact command
- What it shows: tool JSON schemas, raw request/response, server errors
- Use it to verify docstring Args sections are correctly parsed into per-parameter descriptions before testing in Claude Desktop

**Decision:** MCP Inspector is the mandatory first verification step in Phase 2.

---

### 14. Prompt injection risk

**What:** Check whether any strings that ILOSTAT returns (source names, descriptions) could accidentally look like instructions to Claude.  
**Why:** Our tools pass ILOSTAT strings verbatim into responses. If one of those strings says something like "ignore previous instructions", Claude might act on it. Unlikely given these are institutional data labels, but it needs to be checked once and documented — not assumed away.

**Research:** Pull a sample of source names, NOTE_INDICATOR values, and dataflow descriptions from the discovery scripts. Scan for anything instruction-like.

**Likely verdict:** Low risk — these are institutional data labels. But confirm before dismissing so it's a documented decision, not an oversight.

---

## Output

`execution/phase00/`:
- `mcp_design_decisions.md` — one document: what was researched, what was found, and the exact decision locked for each of the 7 unknowns above. No scratch script needed — this is desk research.

**Decisions to lock:**

| Decision | Unknown |
|---|---|
| Tool description style and per-tool requirements | 8 |
| Error handling: exception vs. structured dict | 9 |
| `get_time_series` response structure (final) | 10 |
| System prompt resource content | 11 |
| `search_indicators` cap, format, modelled handling | 12 |
| MCP Inspector as Phase 2 first-step | 13 |
| Prompt injection: sanitize or dismiss | 14 |

## Timing

Do before Phase 2. Unknown 10 (response structure) ideally before Phase 1, since it determines `sdmx_client.py`'s return shape.
