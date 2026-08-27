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

### Phase 2 — Server + basic tools

**Goal:** Working MCP in Claude Desktop; no break detection yet.

Outputs:
- `src/ilostat_mcp/server.py` — FastMCP instance, tool registration
- `src/ilostat_mcp/resources.py` — `ilostat://system-prompt`, codelist caching
- Tools wired: `search_indicators`, `get_countries`, `get_indicator_metadata`, `get_time_series` (no `_breaks` yet)
- Manually verified end-to-end in Claude Desktop

Execution notes: `execution/phase02/`

---

### Phase 3 — Break detection

**Goal:** Core differentiator #1 complete and tested.

Outputs:
- `src/ilostat_mcp/breaks.py` — SOURCE attr diff detection
- `_breaks` field added to `get_time_series` response
- `get_cagr` and `get_trend` warn+compute when range spans a detected break
- `tests/test_breaks.py` — verified against real ILOSTAT data (NGA, THA)

Execution notes: `execution/phase03/`

---

### Phase 4 — Derived stats + remaining tools

**Goal:** Full 7-tool list working.

Outputs:
- `src/ilostat_mcp/analysis/growth.py` — `yoy()`, `cagr()`, `trend()` pure functions
- `src/ilostat_mcp/analysis/__init__.py`
- Tools wired: `get_yoy_change`, `get_cagr`, `get_trend`
- `tests/test_analysis.py` — math verified against hand-calculated cases

Execution notes: `execution/phase04/`

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
