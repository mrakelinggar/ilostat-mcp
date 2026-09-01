# ILOSTAT MCP — Roadmap

## Locked decisions (from CLAUDE.md)

- Language: Python, FastMCP, `sdmx1` for SDMX transport
- Data domain: employment + wages only (v1)
- No local caching — always live ILOSTAT API
- Local install via `pip`/`uvx`; published to PyPI for distribution, Smithery for discoverability (separate concerns)
- 7 tools (see CLAUDE.md tool list)
- Two core differentiators: (1) methodology-break detection, (2) hallucination benchmark

---

## Open decisions (to be resolved in Phase 0)

| Decision | Options | Resolved? |
|---|---|---|
| `search_indicators` impl | ~~Live SDMX catalog search vs. curated lookup table~~ → **Live search** (753 employment/wage dataflows >> 25-dataflow threshold) | ✅ Resolved in Phase 0 |
| Break signal availability | ~~`SOURCE` attr diff + `OBS_PRE_BREAK_VALUE`~~ → **SOURCE diff only** (`OBS_PRE_BREAK_VALUE` not populated by ILOSTAT) | ✅ Resolved in Phase 0 |
| Break countries for benchmark q003 (employment) | **Nigeria (NGA)** — SOURCE change confirmed: "HIES - Living Standards Survey" → "HS - General Household Survey" | ✅ Resolved in Phase 0 |
| Break countries for benchmark q004/q020 (wages) | **Thailand (THA)** and **Egypt (EGY)**, canonical `DF_EAR_EMTA_SEX_CUR_NB` — SOURCE change confirmed. THA: HIES↔LFS alternations. EGY: establishment survey → household LFS (value 1,091 → 71 EGP). Updated from CMTA (care sector) to canonical EMTA flow. | ✅ Resolved in Phase 0b |
| MEASURE dimension (single per flow?) | Always exactly one MEASURE value per flow — safe to drop from user-facing output. | ✅ Resolved in Phase 0b |
| EU aggregate in CL_AREA | No EU aggregate exists. All EU codes return 500 errors. Benchmark q023 = `unanswerable_wrong_entity`. | ✅ Resolved in Phase 0b |
| PAK unemployment break | Confirmed in `DF_UNE_DEAP_SEX_AGE_RT`: 2005→2006 drop 7.0%→0.6% (OBS_STATUS=B), plus HIES/LFS alternations in 2012/2013/2016/2020. | ✅ Resolved in Phase 0b |
| PAK wage break | Confirmed in canonical `DF_EAR_EMTA_SEX_CUR_NB`: HIES/LFS alternations with visible value reversals. | ✅ Resolved in Phase 0b |
| LCU currency symbol in API response | Not in the API — `UNIT_MEASURE='CR'` for all countries. Decision: surface CUR dim value (CUR_TYPE_LCU) in response; skip ISO symbol for v1. | ✅ Resolved in Phase 0b |
| "No data" country for benchmark q021 | **PRK** (North Korea) — confirmed 404 on all flows. ERI also 404. | ✅ Resolved in Phase 0d/0e |
| 404 exception type | `requests.exceptions.HTTPError` — same type for both "no data" and "invalid flow ID". Distinguish by which endpoint raises it. Client returns empty DataFrame on 404. | ✅ Resolved in Phase 0d/0e |
| `get_indicator_metadata` last_updated source | `LAST_UPDATE` annotation in `client.dataflow()` response (e.g. "23/08/2026 07:12:11"). Not from the data message header (that's the API response timestamp, not the data update date). | ✅ Resolved in Phase 0d/0e |
| `get_time_series` response structure | DataFrame with lowercased columns: time_period, value, obs_status, source, unit_measure, freq, sex, age/cur, note_classif. Drop: measure, unit_measure_type, unit_mult, note_source, note_indicator, decimals, bounds. | ✅ Resolved in Phase 0d/0e |
| `search_indicators` return format + cap | list of {id, title, is_modelled} dicts; cap 20; search in flow.name; sort by ORDER annotation. | ✅ Resolved in Phase 0d/0e |
| FREQ filter location | Parameter to get_time_series (default 'A'), applied post-fetch in pandas. Not in sdmx key dict. | ✅ Resolved in Phase 0d/0e |
| Modelled estimate detection (runtime) | In search_indicators (flags is_modelled) and indicators.py only. sdmx_client.py fetches any flow given to it without filtering. | ✅ Resolved in Phase 0d/0e |
| get_yoy_change SOURCE break check | Yes — warn if source differs between year N-1 and N. Value still computed. | ✅ Resolved in Phase 0d/0e |
| Key dict construction (AGE vs CUR) | Dynamic — only include AGE/CUR if not None. indicators.py stores which dims each theme needs. | ✅ Resolved in Phase 0d/0e |
| LCU currency display | Surface CUR_TYPE_LCU label in response. ISO 4217 symbol (EUR/NGN/BRL) deferred to Phase 2 via COUNTRY_CURRENCY map in indicators.py. | ✅ Resolved in Phase 0d/0e |

---

## Phases

### Phase 0 — Discovery

**Goal:** Answer every unknown before writing production code.

Outputs:
- Scratch script results: confirmed dataflow IDs for employment + wages that return real data via `sdmx1`
- Verified whether `SOURCE` attribute and `OBS_PRE_BREAK_VALUE` are actually populated in ILOSTAT responses
- 2+ countries with confirmed methodology breaks identified (fills q003/q004 in benchmark)
- Understanding of `sdmx1` response shape (columns, attributes, quirks)
- Decision logged: `search_indicators` implementation approach
- Benchmark questions expanded to ~30 (without ground truth — filled after Phase 3)

Sub-phases all live in `execution/phase00/` and `plan/phase00/`:
- **Phase 0a** — dataflow selection (primary: which of 1,210 flows do we use and why?) + API sanity check (secondary: does the library connect, does SOURCE exist, how do errors work). See `plan/phase00/phase_0a_plan.md`. The API sanity check portion ran 2026-07-23 and is complete; the dataflow selection portion is still pending and must complete before Phase 1.
- **Phase 0b** — data unknowns blocking Phase 1 coding (see below)
- **Phase 0c** — benchmark infrastructure discovery (see `plan/phase00/phase_0c_plan.md`)

Execution notes: `execution/phase00/`

---

#### Phase 0b — Remaining pre-Phase 1 data discoveries

**Goal:** Close the data unknowns that block Phase 1 coding.

Checks to run (quick API calls):
- Employment-to-population dataflow ID (needed for q013)
- Youth unemployment dataflow ID + youth AGE code (needed for q016)
- PAK employment break in `DF_UNE_DEAP_SEX_AGE_RT`, within 2010–2020 (needed for q019)
- PAK wage break in any EAR dataflow (needed for q004 — "swap country if not found")
- Somalia (`SOM`) — 404 or modelled estimate? (needed for q021)
- EU — is there an aggregate code in CL_AREA? (needed for q023)
- MEASURE dimension — one value per dataflow or multiple? (needed for sdmx_client filter logic)
- q029 (THA/VNM 2018–2022): THA has confirmed wage break in that range — recategorise from `comparative` to `answerable_break`?

Design decisions to lock before Phase 1 coding:
- What `indicators.py` stores (curated canonical dataflow IDs for each theme)
- `search_indicators` return format and result cap
- CAGR/trend behavior when break detected: **warn+compute** (not refuse) — locked by q003/q018/q019/q020 expected `warn_and_answer`
- `get_yoy_change`: does it check for a SOURCE break between year N-1 and year N?

---

#### Phase 0c — Benchmark infrastructure discovery

7 unknowns — `claude -p` subprocess mechanics for `run_benchmark.py`.
See `plan/phase00/phase_0c_plan.md`. Timing: unknowns 1/3/5/6/7 after Phase 1; unknowns 2/4 after Phase 2.

---

#### Phase 0d — MCP design quality research

7 unknowns — tool descriptions, error contract, response structure, system prompt,
`search_indicators` format, MCP Inspector, prompt injection.
See `plan/phase00/phase_0d_plan.md`. Do before Phase 2; unknown 10 (response structure) before Phase 1.

---

#### Phase 0e — Cross-phase design gaps

22 unknowns spanning all remaining phases — caught after 0a–0d. Includes a full-scale API coverage run (all 335 countries, all 4 canonical dataflows) that replaces the narrow spot checks from earlier sub-phases.

- `sdmx_client.py` internals: modelled estimate detection rule, FREQ=A filter, CUR default, 404 vs KeyError error types, `get_indicator_metadata` last_updated source (unknowns 15–19)
- Internal architecture: break detection grain, `DISABLE_BREAK_CHECK` read location, `get_yoy_change` call pattern, `growth.py` signatures, `labor_market_snapshot` prompt chain — **resolved: FastMCP prompt, Option A** (unknowns 20–24)
- Benchmark scoring: judge system prompt + schema text, metric aggregation formulas, `needs_review` flag in schema, DEU emp-to-pop survey flow (unknowns 25–28)
- Distribution: `smithery.yaml` format, `pyproject.toml` entry point for `uvx` (unknowns 29–30)
- **Full API coverage (new):** complete dimension coverage across all 4 flows, complete country coverage matrix (335 countries × 4 flows), full break prevalence scan across all countries, PPP data availability in wage flows (unknowns 31–34)
- **Remaining design decisions (new):** redirect-to-correct-source language location — open; `labour_market_snapshot` implementation — **resolved: FastMCP prompt** (unknowns 35–36)

See `plan/phase00/phase_0e_plan.md`. Timing: unknowns 15–19 + 31–34 before Phase 1; 35–36 before Phase 2; 20–21 before Phase 3; 22–23 before Phase 4; 25–28 before Phase 5; 29–30 before Phase 6.

---

### Phase 1 — Scaffold + data layer

**Goal:** Importable `sdmx_client` returning clean DataFrames; nothing else.

Outputs:
- `pyproject.toml`
- `src/ilostat_mcp/sdmx_client.py` — only file that touches `sdmx1`
- `src/ilostat_mcp/indicators.py` — theme → dataflow ID registry (design informed by Phase 0)
- `tests/test_sdmx_client.py` — live API tests, not mocks
- `.gitignore` with `CLAUDE.md` and `local-notes/`

Execution notes: `execution/phase01/`

---

### Phase 1.5 — CI/CD with GitHub Actions

**Goal:** Every commit from Phase 2b onward is automatically linted,
type-checked, and tested before it can merge. Quality gate in place before
more features are built.

**Why here:** CI set up retroactively is a checkbox, not a gate. Set it up
now so the pipeline actually catches things.

Pre-task discovery:
- Confirm live ILOSTAT API tests work from GitHub Actions IPs (Cloudflare
  may block shared cloud IPs). Fallback: mark live tests, skip in CI.

Outputs:
- `.github/workflows/ci.yml` — two jobs: `quality` (ruff + mypy, seconds)
  then `tests` (pytest against live ILOSTAT API, minutes). Tests job only
  runs if quality passes.
- `.github/workflows/publish.yml` — stub only. Trigger: version tag push.
  Full implementation in Phase 6.
- Branch protection on `main` (private repo) — require `quality` job to pass
- Fix any ruff/mypy failures found in existing Phase 1 code

Plan: `plan/phase01.5/phase_1.5_plan.md`
Execution notes: `execution/phase01.5/`

---

### Phase 2 — Server + basic tools

**Goal:** Working MCP in Claude Desktop; no break detection yet.

Outputs:
- `src/ilostat_mcp/server.py` — FastMCP instance, tool registration
- `src/ilostat_mcp/resources.py` — `ilostat://system-prompt`, codelist caching
- Tools wired: `search_indicators`, `get_countries`, `get_indicator_metadata`, `get_time_series` (no `_breaks` yet)
- Manually verified end-to-end in Claude Desktop

Execution notes: `execution/phase02/`

---

### Phase 2b — MCP completeness fixes

**Goal:** Close gaps found in audit before Phase 3 locks the `get_time_series` interface.

Decisions locked:
- `age_group` optional param on `get_time_series`: `"total"` (adults 15+) or `"youth"` (15–29)
- `ilostat://codelists/indicator` contains the 4 canonical flows with theme name, flow ID, title

Outputs:
- `indicators.py` — 4 missing benchmark flows added to `FLOW_DIMS`; `"2WAP"` added to `_MODELLED_MARKERS`
- `sdmx_client.py` — request timeout (30s); plain-English errors for `ConnectionError`, `Timeout`, 429, 500/503; `get_countries` and `search_indicators` raise on API failure instead of returning empty
- `server.py` — `age_group` param on `get_time_series`; year-order validation; `age_group` validation; 2 new resource endpoints
- `resources.py` — `CANONICAL_FLOWS` constant for indicator codelist resource
- Resources live: `ilostat://codelists/area`, `ilostat://codelists/indicator`
- Pre-task discovery: GEO dimension behavior on `DF_UNE_3EAP_SEX_AGE_GEO_RT` (may affect FLOW_DIMS design)
- Combined Phase 2 + 2b verification pass: `fastmcp dev` tool checks + Claude Desktop sanity pass

Plan: `plan/phase02/phase_2b_plan.md`
Execution notes: `execution/phase02/` (same folder as Phase 2)

---

### Phase 3 — Break detection

**Goal:** Core differentiator #1 complete and tested.

Outputs:
- `src/ilostat_mcp/breaks.py` — `detect_breaks()` (SOURCE attr diff detection) and
  `break_years_in_range()` helper (ready for Phase 4 derived-stat tools to call)
- `_breaks` field added to `get_time_series` response (first element of result list)
- `tests/test_breaks.py` — verified against real ILOSTAT data (NGA, THA)

Note: `get_cagr` and `get_trend` warn+compute when range spans a break — this
is Phase 4 work (built alongside those tools). The mechanism is complete here;
the tools that call it are Phase 4.

Execution notes: `execution/phase03/`

---

### Phase 4 — Derived stats + remaining tools

**Goal:** Full 7-tool list working.

Design decisions to lock before building:
- `get_yoy_change`, `get_cagr`, `get_trend` must each accept the same `age_group`
  param as `get_time_series` (`"total"` / `"youth"`) — they all fetch a time series
  internally, so omitting the param means derived stats can only operate on adult
  totals even when the user asked about youth. Consistent interface; same mapping
  logic as Phase 2b.
- `labor_market_snapshot` accepts a list of 1–3 countries (name or ISO-3 code),
  no optional indicator field — always returns the full snapshot.

Error contract for `labor_market_snapshot`:
- More than 3 countries → raise `ValueError` immediately, before any API call.
  Message names the count and lists what was passed.
- Country name not found after `get_countries()` lookup → raise `ValueError`
  per unresolved name. Message written for Claude to relay to the user in plain English.
- Ambiguous name (e.g. "Congo" matches COG and COD) → raise `ValueError` listing
  all candidates with their ISO-3 codes so the user can pick.
- Partial failure (2 of 3 countries resolve, 1 doesn't) → return results for the
  resolved countries plus a structured error field for the failed one. Do not
  silently drop it.
- All error messages are written for Claude to relay — plain English, not stack
  traces or code identifiers.

Outputs:
- `src/ilostat_mcp/analysis/growth.py` — `yoy()`, `cagr()`, `trend()` pure functions
- `src/ilostat_mcp/analysis/__init__.py`
- Tools wired: `get_yoy_change`, `get_cagr`, `get_trend` (all with `age_group` param)
- `labor_market_snapshot(countries)` prompt — accepts 1–3 country names/codes;
  chains search + fetch + YoY/trend; full error contract above
- `COUNTRY_CURRENCY` map in `indicators.py` — surfaces ISO 4217 symbol alongside LCU label in wage results
- `tests/test_analysis.py` — math verified against hand-calculated cases

Execution notes: `execution/phase04/`

---

### Phase 4.5 — Resilience Audit

**Goal:** Harden the full system before the benchmark runs against it. Find and
fix failure modes that only become visible once all phases exist — things that
were invisible in Phase 2 but surface when Phase 3's break detection or Phase 4's
derived stats are running on top.

**Why here:** Can't audit what doesn't exist. The full tool chain (7 tools, prompt,
break detection, derived stats) must be complete before this phase can be meaningful.
Benchmark results are more trustworthy if the system is hardened first.

**What this phase does:**

1. **Cross-phase gap analysis** — re-read every phase's code asking "what can go
   wrong here that we didn't see when we built it?" Each module gets a fresh-eyes
   failure mode sweep.

2. **End-to-end trace** — walk every request path from prompt input → tool chain
   → SDMX API → response. At each step: what breaks silently? What produces a
   wrong answer without raising? What does the agent see if it fails?

3. **Adversarial input testing** — malformed, boundary, and unexpected inputs to
   every tool and the prompt. Examples: empty keyword, nonsense dataflow ID,
   start_year in the future, country code that exists in CL_AREA but has no data
   for any flow, `age_group="youth"` on a wage flow.

4. **Dependency failure simulation** — ILOSTAT API down, timeout, rate limited,
   returns unexpected SDMX shape. Confirm every failure surfaces a plain-English
   message to Claude, not a raw traceback.

5. **Break detection edge cases** — single-observation series, series with all
   observations from the same source, series where every observation is a break,
   range that starts or ends exactly on a break year.

6. **Fix all gaps found** — implement missing resilience measures. Document any
   gaps that are intentionally deferred to v2 and why.

**Output:**
- Gap analysis doc in `execution/phase04.5/`
- Fixes applied across whichever source files they belong to
- Updated tests where new failure modes warrant them
- `structlog` integrated throughout — structured JSON logs replacing all bare
  `logging` calls in `server.py` and `sdmx_client.py`
- OpenTelemetry instrumentation in `server.py` (tool spans) and `sdmx_client.py`
  (API spans), exporting to Honeycomb free tier
- Benchmark run logging: per-question structured JSON trace alongside results table
- `pyproject.toml` updated with observability deps:
  `structlog`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp`

Plan: `plan/phase04.5/phase_4.5_plan.md` (written at the start of this phase,
after Phase 4 is complete and the full system is visible)
Execution notes: `execution/phase04.5/`

---

### Phase 5 — Benchmark

**Goal:** Core differentiator #2 complete; results table ready for README.

Outputs:
- Benchmark questions at ~30 with all ground truth filled from live ILOSTAT (no guessing)
- `benchmark/run_benchmark.py` — scores `bare_llm`, `mcp_full`, `mcp_no_breakcheck` via `claude -p` subprocess
- Results table (fabrication rate, break-blindness rate, abstention accuracy, false-abstention rate)

Execution notes: `execution/phase05/`

---

### Phase 6 — Polish + publish

**Goal:** Repo public-ready; showcase assets drafted.

Outputs:
- `README.md` with benchmark results table
- `smithery.yaml`
- PyPI publish
- Article draft (TDS/Dev.to)

Execution notes: `execution/phase06/`
