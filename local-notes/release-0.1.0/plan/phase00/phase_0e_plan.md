# Phase 0e — Cross-Phase Design Gaps

Date planned: 2026-07-26

## What and why

Phases 0a through 0d answered the big questions — does the API work, do breaks exist, can the benchmark runner run, how should tools be described. But they left a set of smaller decisions unresolved that will each cause a real blocker the moment we hit the relevant phase: sdmx_client.py quirks that the API reference noted but didn't resolve, cross-module architecture questions that no plan file addressed, benchmark scoring logic that was never designed, and distribution research that was never done. Phase 0e catches all of these before they become mid-build surprises. Most items here are desk research or short API calls — none require a running server. The goal is to produce two documents: a locked decisions file for the design items, and a short scratch script for the five items that need a live API call to verify.

---

## Unknowns to resolve (16)

### Group A — `sdmx_client.py` internals (must lock before Phase 1)

These five affect what `sdmx_client.py` has to do to return clean data. Phase 0a and the API reference noted each symptom but didn't decide how to handle it.

---

#### 15. Modelled estimate detection

**What:** Decide the exact rule `sdmx_client.py` uses to classify a dataflow as `survey` or `modelled_estimate`, and verify it handles edge cases like the `3EAP` prefix.  
**Why:** The data_type field in every response (and the system prompt's instruction to never present a modelled number as survey data) depends on this classification being correct. If the rule is wrong, the server silently mislabels data and the agent can't tell the difference.

The API reference noted that `2EAP`/`2WAP` in the second segment of a dataflow ID signals ILO modelled estimates. But Phase 0b used `DF_UNE_3EAP_SEX_AGE_GEO_RT` for youth unemployment — the `3` prefix was never explained. Is it also modelled, or is it a disability-disaggregated survey flow?

**Research:**
- Pull the title for `DF_UNE_3EAP_SEX_AGE_GEO_RT` from the dataflow catalog. If "modelled estimates" appears in the title, the digit prefix is the right signal.
- Pull ten more examples: a `4EAP` or `5EAP` if any exist, and confirm whether only `2` = modelled or whether the rule is "digit prefix = modelled."
- Lock rule as: segment contains a leading digit → `modelled_estimate`; no leading digit → `survey`. Or find a better rule.

**Success:** a one-line Python function `is_modelled(dataflow_id: str) -> bool` with a confirmed rule.

---

#### 16. FREQ=A filter implementation

**What:** Verify the exact argument that filters ILOSTAT responses to annual observations only, and confirm it works in `client.data()` rather than requiring post-processing.  
**Why:** Phase 0a confirmed that ILOSTAT returns mixed-frequency data (Annual, Monthly, Quarterly in the same response). If `sdmx_client.py` doesn't filter to Annual, every DataFrame has duplicate years and YoY/CAGR calculations break silently.

The API reference said FREQ=A is needed but didn't record how to pass it. `sdmx1`'s key filter syntax for ILOSTAT is not the same as string-based key filtering (Phase 0a found 422 errors on string keys).

**Research:**
- Try `client.data(resource_id, key={"FREQ": "A"})` on a known wage dataflow (e.g. `DF_EAR_EMTA_SEX_CUR_NB` for FRA).
- If that errors, try post-filtering the DataFrame: `df[df["FREQ"] == "A"]` and confirm FREQ is a column in the result.
- Record which approach works and what the column name is.

**Success:** working one-liner to isolate annual data, confirmed on a real ILOSTAT response.

---

#### 17. CUR dimension default

**What:** Verify the exact filter argument that restricts wage dataflow responses to local currency unit (LCU) observations.  
**Why:** Wage dataflows return three currency variants per country (LCU, PPP, USD). Without filtering, the DataFrame has three rows per year and the agent might pick the wrong one. LCU is the right default for country-level comparisons.

**Research:**
- Pull `DF_EAR_EMTA_SEX_CUR_NB` for one country and inspect the CUR dimension values.
- Try `client.data(resource_id, key={"CUR": "CUR_TYPE_LCU"})` — confirm the exact code value.
- Verify the filtered DataFrame has one row per year per sex.

**Success:** confirmed CUR code value and working filter argument.

---

#### 18. Error handling: HTTP 404 vs. KeyError distinction

**What:** Confirm that the two sdmx1 failure modes — HTTP 404 (country has no data at all) and KeyError (country has data but not for the requested period) — are distinguishable in Python and can each be mapped to a structured error response.  
**Why:** Both failures mean "no data," but they are triggered by different conditions and may need different error messages (e.g. "PRK has no survey data" vs. "MYS has no data for 2025"). Phase 0d unknown 9 decides the error contract format; this decides how to implement it. If they look the same in Python, one `except` clause handles both. If they look different, we need two.

**Research:**
- Trigger a 404: call `client.data()` on a known no-data country (PRK or YEM in `DF_UNE_DEAP_SEX_AGE_RT`). Record the exception class and message.
- Trigger a KeyError: call a country that has data but request a future year (SGP, 2030). Record exception class and message.
- Check if `sdmx1` wraps both in the same exception type or uses different classes.

**Success:** two exception types (or one type with distinguishable message) recorded. Decision: handle both with a single `except` that maps to `{"has_data": False, ...}`, or two separate paths.

---

#### 19. `get_indicator_metadata` last_updated source

**What:** Find where "last updated" comes from in an SDMX dataflow response and verify it's consistently populated by ILOSTAT.  
**Why:** The `get_indicator_metadata` tool lists "last updated" as one of its outputs. If this field comes from an SDMX attribute that ILOSTAT doesn't reliably populate, we'll return empty or wrong values — which is worse than not returning it at all.

**Research:**
- Call `client.dataflow(resource_id="DF_UNE_DEAP_SEX_AGE_RT", references="all")` and inspect the response object for anything resembling a date: `validFrom`, `validTo`, DSD `version`, or similar.
- Also check if the dataflow catalog (Call 1) includes a `last_updated` field per entry.
- If no reliable date source exists, remove the field from the tool's output rather than returning a guess.

**Success:** specific attribute path confirmed (e.g. `msg.dataflow["DF_UNE_DEAP_SEX_AGE_RT"].maintainable_artefact.valid_from`) or explicit decision to drop the field.

---

### Group B — Internal architecture (lock before the relevant phase)

These affect how modules call each other. None require an API call — they're design decisions that must be made before writing the corresponding file.

---

#### 20. Break detection grain

**What:** Decide whether `breaks.py` operates on a single time series (one row per year) or on a full multi-dimensional DataFrame (multiple rows per year because sex × age × geography combinations are still present).  
**Why:** If `sdmx_client.py` passes the full multi-dimensional DataFrame to `breaks.py`, the break detection logic needs to group by dimension values first — otherwise it will false-positive on legitimate differences between the male and female series. Getting this wrong means break detection fires constantly on valid data or misses real breaks.

**Decision to lock:**
- Option A: `sdmx_client.py` collapses to a single canonical series (e.g. `SEX_T`, `AGE_YTHADULT_YGE15`) before passing to `breaks.py`. Simpler; `breaks.py` sees one row per year.
- Option B: `sdmx_client.py` passes the full DataFrame; `breaks.py` groups by all non-time dimensions. Flexible; `breaks.py` is more complex.

Option A is correct for v1 — the tools all return a single aggregated series, not a disaggregated breakdown. Lock this and record it.

---

#### 21. `DISABLE_BREAK_CHECK` read location

**What:** Decide which file reads the `DISABLE_BREAK_CHECK` environment variable and how it suppresses break detection for the `mcp_no_breakcheck` benchmark condition.  
**Why:** Phase 0c confirmed that env vars set on the `claude -p` call may or may not reach the MCP server subprocess (unknown 2.4, deferred to Phase 2). But regardless of how the var arrives, we need to decide *where* it's consumed — if `breaks.py` reads it directly, break detection is suppressed everywhere; if `server.py` reads it and skips the `breaks.py` call, break detection is suppressed only at the tool layer. The wrong choice makes the `mcp_no_breakcheck` condition not actually isolate break detection.

**Decision to lock:**
- `server.py` reads the env var and conditionally calls `breaks.py`. Keeps `breaks.py` pure — it never knows about the flag.
- This matches the architecture rule: `breaks.py` does one thing (detect breaks). Whether to call it is `server.py`'s responsibility.

---

#### 22. `get_yoy_change` → `breaks.py` call pattern

**What:** Decide whether `get_yoy_change` fetches raw data and calls `breaks.py` directly, or calls `get_time_series` internally and reuses its already-computed `_breaks` output.  
**Why:** Phase 0b locked that `get_yoy_change` must check for a SOURCE break between year N−1 and year N. If it duplicates the data fetch and break detection logic, any future change to `breaks.py` must be updated in two places — a DRY violation. If it calls `get_time_series` internally, it takes on a dependency between two tool functions, which can make testing harder.

**Decision to lock:**
- `get_yoy_change` calls `sdmx_client.fetch_series()` directly (not `get_time_series`), then calls `breaks.check_breaks()` on the result. Both are internal functions, not MCP tool calls — there's no circular dependency.
- This keeps tool functions independent at the MCP layer while reusing the underlying data/break logic.

---

#### 23. `analysis/growth.py` function signatures

**What:** Lock the exact input and output types for `yoy()`, `cagr()`, and `trend()`.  
**Why:** These are described as "pure functions, unit-testable." If their signatures aren't locked before Phase 4, the tests are written against one interface and the server wires up a different one — causing a rewrite of either the functions or the tests.

**Decision to lock:**

```python
# All three accept the same input type: a list of (year: int, value: float) tuples,
# sorted ascending by year. This is what sdmx_client returns after collapsing to annual.

def yoy(series: list[tuple[int, float]], year: int) -> dict:
    # returns {"year": int, "previous_year": int, "change_pct": float}
    # raises ValueError if year or year-1 not in series

def cagr(series: list[tuple[int, float]], start: int, end: int) -> dict:
    # returns {"start": int, "end": int, "cagr_pct": float, "n_years": int}
    # raises ValueError if start or end not in series

def trend(series: list[tuple[int, float]], start: int, end: int) -> dict:
    # returns {"start": int, "end": int, "slope": float, "r_squared": float, "direction": str}
    # "direction": "increasing" | "decreasing" | "flat"
    # raises ValueError if fewer than 3 data points in range
```

The `warn_and_compute` break warning is added by `server.py` using the `_breaks` output — not inside `growth.py`. Keeps `growth.py` pure.

---

#### 24. `labor_market_snapshot` prompt chain

**What:** Design the exact chain of tool calls the `labor_market_snapshot(country)` prompt triggers and what the output template looks like.  
**Why:** FastMCP prompts are pre-packaged workflows the client (Claude Desktop) surfaces as a slash command. If the chain is designed now, `server.py` registers it correctly in Phase 2. If it's designed in Phase 2 under time pressure, it'll be underpowered or over-complex.

**Decision to lock:**

The prompt returns a message template that instructs the agent to:
1. Call `search_indicators("unemployment")` → pick the survey flow
2. Call `get_time_series(dataflow_id, country)` → get the series + breaks
3. Call `get_yoy_change` for the latest available year
4. Call `search_indicators("wages")` → pick the survey flow
5. Call `get_time_series` for wages → check for breaks
6. Call `get_trend` for wages over the last 5 available years

Output template: country name, unemployment rate (latest year, YoY change, break warning if applicable), wage trend (direction, slope, break warning if applicable), data sources cited.

FastMCP prompt registration: `@mcp.prompt()` decorator returning a `Message` list. Confirm decorator syntax against Phase 0d's FastMCP research.

---

### Group C — Benchmark design (lock before Phase 5)

These are design decisions for the scoring logic that the Phase 0c runner depends on. None require code to verify — they need to be written down.

---

#### 25. Judge system prompt and output schema

**What:** Draft the actual text of `JUDGE_SYSTEM` (the grading rubric Claude receives) and `JUDGE_SCHEMA` (the JSON schema that `--json-schema` enforces).  
**Why:** Phase 0c confirmed the mechanism works — `--system-prompt` + `--json-schema` + `--output-format json` reliably returns valid structured JSON. But the actual rubric text and schema shape were never written. Without them, `run_benchmark.py` can't be built in Phase 5.

**Draft to lock:**

`JUDGE_SCHEMA`:
```json
{
  "type": "object",
  "properties": {
    "score": {
      "type": "string",
      "enum": ["correct", "fabrication", "wrong_value", "false_abstention",
               "break_blindness", "disambiguation_failure", "correct_abstention"]
    },
    "needs_review": {"type": "boolean"},
    "reason": {"type": "string", "maxLength": 200}
  },
  "required": ["score", "needs_review", "reason"],
  "additionalProperties": false
}
```

`JUDGE_SYSTEM` must instruct the judge to:
1. Score `correct` only if the response contains the ground truth value within 0.1 percentage points and correctly names the year.
2. Score `fabrication` if the response states a specific value that is not in the ground truth and the model had no tool access (or did not use tools).
3. Score `break_blindness` if the question has `has_break: true` and the response gives a number without mentioning a methodology change.
4. Score `correct_abstention` if the question is `unanswerable_*` and the response declines to give a number.
5. Score `false_abstention` if the question is `answerable_*` and the response refuses to answer or says data is unavailable.
6. Set `needs_review: true` if the answer is hedged (contains "approximately", "around", "roughly", or a range) — automated score may be wrong.

---

#### 26. Scoring aggregation logic

**What:** Define exactly how the four benchmark metrics are calculated from individual judge scores.  
**Why:** The README must show four numbers — fabrication rate, break-blindness rate, abstention accuracy, false-abstention rate. Without a formal definition of which question categories feed each metric, two people running the benchmark could compute different numbers from the same raw scores.

**Definitions to lock:**

| Metric | Numerator | Denominator |
|---|---|---|
| Fabrication rate | `score == "fabrication"` in `bare_llm` condition | All `answerable_*` questions in `bare_llm` condition |
| Break-blindness rate | `score == "break_blindness"` | All `answerable_break` questions, all 3 conditions |
| Abstention accuracy | `score == "correct_abstention"` | All `unanswerable_*` questions |
| False-abstention rate | `score == "false_abstention"` | All `answerable_*` questions |

Reported as percentages, rounded to one decimal place. `needs_review: true` items excluded from automated metric totals and listed separately.

---

#### 27. `needs_review` flag in BENCHMARK_SCHEMA.md

**What:** Add `needs_review` as a documented field to `BENCHMARK_SCHEMA.md` so it's part of the official schema, not just an undocumented key in the JSON output.  
**Why:** Phase 0c identified that hedged-but-correct answers are scored wrong by the automated judge, and the fix is a manual review pass. If `needs_review` isn't in the schema, whoever reads the benchmark results won't know what the flag means or that a manual pass is expected.

**Action:** Add to `BENCHMARK_SCHEMA.md` under the scoring section: definition of `needs_review`, which judge scores it can appear with, and the instruction that `needs_review: true` items must be manually verified before final metric reporting.

This is a doc update, not a discovery. Can be done in the same session as this plan.

---

#### 28. DEU employment-to-population survey flow (q013)

**What:** Verify whether a survey-based employment-to-population dataflow exists for Germany, or whether the modelled-estimate flow (`DF_EMP_2WAP_SEX_AGE_RT`) is the only option.  
**Why:** Phase 0b provisionally locked `DF_EMP_2WAP_SEX_AGE_RT` for q013 with a note to verify the survey alternative. This is still open — the Phase 0b follow-up only closed the other 4 items. If a survey flow exists, q013 should use it (consistent with the architecture rule: survey data by default). If not, the question notes need to acknowledge the modelled estimate is unavoidable.

**Research:**
- Search the dataflow catalog for titles containing "employment-to-population" or "employment to population ratio" that do NOT contain "modelled estimates."
- Look for `DF_EMP_DWAP_*` (the DWAP prefix is the survey equivalent of 2WAP). Try `client.data("DF_EMP_DWAP_SEX_AGE_RT", key={"REF_AREA": "DEU"})`.
- If a survey flow exists and has DEU data: update q013's `dataflow_id`. If not: update q013's notes to confirm modelled is the only available source.

---

### Group E — Full API coverage (run before Phase 1)

The API-call items in Group A (unknowns 16–18) were written as spot checks — one dataflow, one or two countries. That is not enough. Before Phase 1 code is written, we need to know how the API behaves across **all** canonical dataflows and **all** countries, not just the ones that appeared in benchmark questions. Unknowns 31–34 run the same checks but at full scale. Their results supersede the narrow checks in 16–17.

---

#### 31. Full dimension coverage — all values, all canonical dataflows

**What:** For each of the 4 canonical dataflows, pull the DSD to enumerate every valid value for every dimension (SEX, AGE, CUR, GEO where applicable). Then verify which combinations actually return data versus which exist in the codelist but return empty.

**Why:** The supported queries table relies on specific dimension values (SEX_T, SEX_M, SEX_F, AGE_YTHADULT_YGE15, AGE_YTHBANDS_Y15-29, CUR_TYPE_LCU, CUR_TYPE_PPP, etc.). If a value is in the codelist but not populated by ILOSTAT for the relevant flow, every query that depends on it silently returns nothing. We need to know which values work before we write the sdmx_client filter logic.

Also check consistency: for countries where SEX_M and SEX_F both return data, do they approximately sum to SEX_T? A large inconsistency signals the flows are not additive and the tool should not imply they are.

**Flows to check:** `DF_UNE_DEAP_SEX_AGE_RT`, `DF_EAR_EMTA_SEX_CUR_NB`, `DF_UNE_3EAP_SEX_AGE_GEO_RT`, `DF_EMP_2WAP_SEX_AGE_RT`

**Research:**
- For each flow, call `client.datastructure(resource_id=dsd_id)` to get the full DSD.
- For each dimension, list all codelist values.
- Pick 5 representative countries (one per region: Europe, Asia, Africa, Americas, MENA) and test each dimension value against each country. Record which return data and which return 404/empty.
- For youth unemployment specifically: confirm whether AGE_YTHBANDS_Y15-24 exists and returns data (the unsupported queries table claims 15–24 is available — verify this is true, not an assumption).
- Test SEX_M + SEX_F ≈ SEX_T on 5 countries in the unemployment flow.

**Output:** table of (dataflow, dimension, value, coverage) — "works", "empty", or "404".

---

#### 32. Full country coverage — all 335 CL_AREA entries, all canonical dataflows

**What:** For every country code in CL_AREA, check whether each canonical dataflow returns actual data, and if so, record the year range and data type (survey vs. modelled).

**Why:** The supported queries table implies the tool works for many countries. Right now we only know it works for the countries that appeared in benchmark questions (MYS, SGP, NGA, THA, VNM, PAK, ZAF, DEU, FRA, BRA, etc. — roughly 15 countries). We have no picture of how broad the real coverage is. Building tools that claim to cover 335 countries but silently fail for most of them is a correctness problem. The coverage map also tells us whether `get_countries()` should filter to countries that actually have employment/wage data, rather than returning all 335.

**Research:**
- For each of the 4 canonical flows, loop over all CL_AREA codes and call `client.data()` with a short date range (latest 5 years) for SEX_T / total age / LCU (for wages).
- Record for each country: HTTP status (200/404), whether result is empty, year range if data exists, SOURCE attribute sample (survey name).
- This will be slow — batch it or add short sleeps to avoid rate limiting.
- Produce a CSV summary: country, flow, has_data, start_year, end_year, data_type.

**Output:** a coverage matrix (`country × dataflow → has_data, year_range, data_type`). This becomes the canonical reference for what the tool can actually answer, and informs whether `get_countries()` should be filtered.

---

#### 33. Full break prevalence — all countries with data, all canonical dataflows

**What:** For every country that has data in each canonical dataflow (as identified in unknown 32), run SOURCE attribute diff detection across the full available date range and record all methodology breaks.

**Why:** Break detection is core differentiator #1 and the benchmark's most important condition. But we built the whole system around ~4 confirmed break countries (NGA, PAK, THA, and a few others from the benchmark). We have no idea how common breaks are across the full 335-country dataset. If breaks are extremely rare (fewer than 5% of countries), the differentiator is weaker than claimed — the benchmark should reflect that. If breaks are common (30%+ of countries), that strengthens the claim significantly and may mean the tool needs clearer break communication. We need the real number before writing the article.

**Research:**
- Reuse the data pulled in unknown 32 (or re-pull if needed with SOURCE attribute included: `to_pandas(msg, attributes='osgd')`).
- For each country × flow combination with data, compute SOURCE diff across consecutive annual observations.
- Record: country, flow, break years, source_before, source_after.
- Aggregate: total countries with ≥1 break per flow, break prevalence % per flow.

**Output:** a break prevalence table by flow. A list of all break countries, their flows, and their break years. This updates the log and informs the article's "how common is this problem?" framing.

---

#### 34. PPP data availability in wage flows

**What:** For every country with wage data in `DF_EAR_EMTA_SEX_CUR_NB`, check whether CUR_TYPE_PPP returns actual data (not just whether PPP is in the codelist).

**Why:** Cross-country wage comparisons (Thailand vs Vietnam, France vs Germany) are only meaningful if the tool can provide a common currency. The CUR dimension includes PPP as a value, but this does not mean ILOSTAT actually populates it for most countries. If PPP is only available for ~20% of countries, the cross-country comparison design must warn instead of providing PPP data. If PPP is available for most countries, the tool should return it alongside LCU for comparisons. We cannot design the cross-country comparison behaviour without knowing the actual PPP coverage.

**Research:**
- From the country list identified in unknown 32 for `DF_EAR_EMTA_SEX_CUR_NB`, filter to countries with LCU data.
- For each of those countries, try `client.data(flow, key={"REF_AREA": country, "CUR": "CUR_TYPE_PPP"})`.
- Record: has_ppp_data (bool), year range if available.
- Produce a summary: % of wage-data countries that also have PPP data.

**Design decision to lock based on result:**
- If PPP coverage ≥ 80% of countries: return both LCU and PPP for all wage calls; include note on cross-country comparisons.
- If PPP coverage < 80%: return LCU only; include a static warning on cross-country wage comparisons that PPP adjustment would be needed for a valid comparison.

---

### Group F — Remaining design decisions (lock before Phase 2)

These are design choices that affect Phase 2 implementation. They need a decision before building, not a live API call.

---

#### 35. Redirect-to-correct-source language — where does it live?

**What:** When a user asks about something outside ILOSTAT's scope (GDP → World Bank; inflation → IMF/Eurostat; literacy → UNESCO), the tool should redirect them to the right source. The question is where this redirect language is stored and how it reaches Claude.

**Why:** This language has to come from somewhere — Claude doesn't know on its own to say "World Bank" when it declines a GDP question. If it comes from training knowledge rather than explicit server instruction, the tool looks good but it's secretly relying on Claude's memory rather than the server's design. That's exactly what we're trying to avoid.

**Options — no decision locked yet, research needed:**

- **Option A: System prompt resource** — one central list of "if you see X type of question, redirect to Y." Advantages: one place to maintain, consistent. Disadvantages: system prompt grows large; hard to keep topic-to-source mappings accurate over time.
- **Option B: Tool error message** — when a tool call fails because the indicator is out of scope, the error message includes the redirect. Advantages: redirect is close to the failure point, doesn't bloat the system prompt. Disadvantages: redirect only fires if Claude attempted a tool call first (it may not for clearly out-of-scope questions like GDP).
- **Option C: Both** — system prompt has the general rule ("for out-of-scope indicators, name the correct source"); individual tool error messages have the specific redirect ("GDP is not in ILOSTAT — use World Bank API or data.worldbank.org"). Advantages: covers both cases. Disadvantages: more to write and maintain.

**Research:** Read Phase 0d findings on system prompt design and error contract. Review how other MCP servers handle out-of-scope queries. Pick one option and record why.

---

#### 36. `labour_market_snapshot` implementation: prompt vs. tool

**What:** Decide whether the packaged workflow is implemented as a FastMCP prompt (returns a message template that instructs Claude to make multiple tool calls) or as a single tool (internally calls sdmx_client multiple times and returns a combined response).

**Why:** This is a structural decision — it determines what goes in `server.py`, how it's tested, and what the user sees. See use_cases.md for the workflow spec.

**Decision locked: Option A — FastMCP prompt.**

Reasoning:

| | Option A: FastMCP prompt | Option B: Single tool |
|---|---|---|
| Server code | Simple — a message template | Complex — orchestration in server.py |
| Determinism | Non-deterministic (Claude chains) | Fully deterministic |
| Partial failure | Graceful — Claude reports what it found | Brittle — one failure blocks everything |
| Transparency | Every tool call visible in the panel | One black-box call |
| Flexibility | Claude adapts narrative to findings | Fixed output structure |
| MCP design intent | Correct — prompts are for workflows | Violates single-responsibility |

Option A is how FastMCP prompts are designed to work. The non-determinism risk is acceptable for a packaged workflow — Claude's reasoning between tool calls is a feature (it can surface a break warning more prominently if one is found), not a bug. Implementation: `@mcp.prompt()` returning a `Message` list with the chain instructions.

This resolves unknown 24. Record the final decision here and remove the ambiguity from unknown 24's description.

---

### Group D — Distribution research (lock before Phase 6)

These are one-time research tasks. Nothing blocks earlier phases, but they need to be done before Phase 6 starts — not discovered mid-publish.

---

#### 29. `smithery.yaml` format

**What:** Find the required and optional fields for `smithery.yaml` and what Smithery uses them for in its MCP catalog listing.  
**Why:** `smithery.yaml` is in the architecture but has never been researched. Discovering the format mid-Phase 6 means rewriting the file and possibly the README alongside it. Getting it right the first time is a one-time lookup.

**Research:** Read the Smithery documentation or a reference MCP repo's `smithery.yaml`. Record: required fields, how tool descriptions are surfaced in the catalog, whether there's validation tooling.

**Output:** a minimal valid `smithery.yaml` template written into `execution/phase00/phase0e_results.md`.

---

#### 30. PyPI publish process

**What:** Confirm the steps to publish an MCP server as a `uvx`-installable package, including what `pyproject.toml` must declare and whether a `__main__.py` entry point is required.  
**Why:** The distribution plan is `pip`/`uvx` install, but the exact `pyproject.toml` shape for this — specifically, the `[project.scripts]` entry point that lets `uvx ilostat-mcp` launch the server — has never been verified. Discovering a missing entry point or wrong packaging on publish day is avoidable.

**Research:**
- Find a reference FastMCP server published to PyPI and inspect its `pyproject.toml`. Record the `[project.scripts]` entry, the `[build-system]` table, and any FastMCP-specific packaging notes.
- Confirm whether `uvx` requires a `__main__.py` or whether the entry point in `pyproject.toml` is sufficient.
- Check if a TestPyPI dry-run step is standard or skippable for a first publish.

**Output:** a `pyproject.toml` scaffold with the known-correct fields filled in, written into `execution/phase00/phase0e_results.md`.

---

## Output

Three documents in `execution/phase00/`:

- `phase0e_results.md` — findings and locked decisions for all 22 unknowns. Decisions go here first, then get copied into `mcp_design_decisions.md` (for design items) or `benchmark_questions.json` (for q013).
- `code/phase0e_scratch.py` — script covering the items that need a live API call: unknowns 15 (modelled detection), 16 (FREQ filter), 17 (CUR filter), 18 (error types), 28 (DEU DWAP flow). Narrow spot checks — superseded by unknowns 31–34 but still worth running first as a fast sanity check.
- `code/phase0e_scratch_full_coverage.py` — separate script for the full-scale API checks: unknowns 31 (dimension coverage), 32 (country coverage), 33 (break prevalence), 34 (PPP coverage). This will be slow — expect 10–30 minutes of API calls across 335 countries. Run once; save results to a CSV in `execution/phase00/`.

**Decisions to lock:**

| Decision | Unknown | Blocks |
|---|---|---|
| `is_modelled()` rule | 15 | Phase 1 — `sdmx_client.py` |
| FREQ=A filter implementation | 16 | Phase 1 — `sdmx_client.py` |
| CUR_TYPE_LCU filter | 17 | Phase 1 — `sdmx_client.py` |
| Error handling: 404 vs KeyError | 18 | Phase 1 — `sdmx_client.py` |
| `last_updated` source (or drop) | 19 | Phase 1 — `get_indicator_metadata` |
| Break detection grain | 20 | Phase 3 — `breaks.py` |
| `DISABLE_BREAK_CHECK` read location | 21 | Phase 3 — `server.py` / `breaks.py` |
| `get_yoy_change` call pattern | 22 | Phase 4 — `server.py` |
| `growth.py` function signatures | 23 | Phase 4 — `analysis/growth.py` |
| `labor_market_snapshot` chain | 24 (resolved: Option A) | Phase 2 — `server.py` |
| `JUDGE_SYSTEM` + `JUDGE_SCHEMA` | 25 | Phase 5 — `run_benchmark.py` |
| Metric aggregation formulas | 26 | Phase 5 — `run_benchmark.py` |
| `needs_review` in schema | 27 | Phase 5 — `BENCHMARK_SCHEMA.md` |
| q013 dataflow (survey vs modelled) | 28 | Phase 5 — benchmark ground truth |
| `smithery.yaml` template | 29 | Phase 6 — publish |
| `pyproject.toml` entry point | 30 | Phase 6 — publish |
| Dimension coverage (all flows, all values) | 31 | Phase 1 — `sdmx_client.py` filter logic |
| Country coverage matrix | 32 | Phase 1 — `get_countries()` scope |
| Break prevalence across all countries | 33 | Phase 3 — `breaks.py` and article framing |
| PPP coverage → comparison design | 34 | Phase 2 — cross-country wage query design |
| Redirect language location | 35 | Phase 2 — `server.py` / system prompt |

---

## Timing

- **Before Phase 1:** unknowns 15–19 (sdmx_client internals) + 31–34 (full API coverage). Run the narrow scratch script first, then the full-coverage script.
- **Before Phase 2:** unknowns 24 (resolved — Option A), 35 (redirect language), 36 (prompt chain — resolved — Option A).
- **Before Phase 3:** unknowns 20–21 (break detection grain, DISABLE_BREAK_CHECK).
- **Before Phase 4:** unknowns 22–23 (yoy call pattern, growth.py signatures).
- **Before Phase 5:** unknowns 25–28 (benchmark scoring design, q013 follow-up).
- **Before Phase 6:** unknowns 29–30 (distribution research). Can be done any time after Phase 3.
