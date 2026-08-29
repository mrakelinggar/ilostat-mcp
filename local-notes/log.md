# Session Log

---

## TODO — start of next session
- **Build Phase 2b** — see `plan/phase02/phase_2b_plan.md` for full task list.
- **Verify Phase 2 + 2b together** in a single test pass after Phase 2b is built.
  Phase 2b doesn't change Phase 2 tool behaviour, so one pass covers both.
  Checklist:
  - 4 original tools respond with real data; `[]` returned for PRK
  - `ilostat://system-prompt`, `ilostat://codelists/area`, `ilostat://codelists/indicator` all load
  - `get_time_series` with `age_group="youth"` returns correct youth band for ZAF
  - PAK wages (`DF_EAR_CMTA_SEX_CUR_NB`) and DEU emp-to-pop (`DF_EMP_2WAP_SEX_AGE_RT`) return data
  Phase 3 should not start until this passes.

---

## 2026-08-29

Audit of all three MCP primitives (resources, tools, prompts) against the full
benchmark question set. Found three categories of gap not covered by existing phases:

1. `FLOW_DIMS` in `indicators.py` is missing four flows that benchmark questions
   use — any call to `get_time_series` with those flows silently sends wrong
   dimensions. Correctness bug, not a missing feature.

2. No mechanism to request youth-band data — the tool has no `age_group` param,
   so q016 (South Africa youth unemployment) can't be answered correctly. Decided:
   add optional `age_group` param (`"total"` / `"youth"`) to the tool; mapping lives
   in `server.py`, `sdmx_client.py` unchanged.

3. Two specified resources (`ilostat://codelists/area`, `ilostat://codelists/indicator`)
   were never built in Phase 2. Also decided: `codelists/indicator` contains the
   4 canonical flows (theme, ID, title) — gives the agent upfront knowledge of what
   flows exist without relying on search.

4. `labor_market_snapshot` prompt and `COUNTRY_CURRENCY` map assigned to Phase 4.

All gaps captured in Phase 2b plan. ROADMAP updated with Phase 2b section.

Added Phase 4.5 (Resilience Audit) to ROADMAP — cross-phase hardening after
feature-complete, before benchmark.

Added observability stack to CLAUDE.md locked decisions: structlog for
structured JSON logs, OpenTelemetry → Honeycomb for distributed tracing,
metrics deferred. Observability is a Phase 4.5 deliverable.

Updated CLAUDE.md production standards section with full quality bar.

Created `local-notes/learnings/` — cross-project knowledge capture:
mcp-fundamentals, mcp-fastmcp, testing-disciplines, observability,
software-eng-breadth, cicd-github-actions. Rule: capture any meaningfully
learned concept before closing a session.

Added Phase 1.5 (CI/CD — GitHub Actions) to ROADMAP — inserted between
Phase 1 and Phase 2b. Must be done before Phase 2b. Two jobs: quality
(ruff + mypy) then tests (pytest vs live ILOSTAT). CD stub (publish.yml)
created now, fully wired in Phase 6. Pre-task discovery: confirm live API
tests work from GH Actions IPs (Cloudflare risk).

---

## 2026-08-28 (continued) — Phase 1 QA + fixes + public push

QA review of Phase 1 complete. Three findings; two fixed, one noted.

**F1 fixed — `ann.type` vs `ann.id` for LAST_UPDATE lookup (`sdmx_client.py:154`):** The developer used `ann.id` to find the `LAST_UPDATE` annotation but ILOSTAT uses the `type` field (confirmed in Phase 0 discovery script). Silent failure — `last_updated` would have returned `""` for every flow. Fixed to `getattr(ann, "type", None) == "LAST_UPDATE"`.

**F3 fixed — HTML not stripped from description (`sdmx_client.py:150`):** BeautifulSoup was declared in pyproject.toml but never imported or used. ILOSTAT descriptions can contain HTML tags. Fixed — description now passed through `BeautifulSoup(...).get_text(separator=" ", strip=True)`.

**F2 noted — `is_modelled()` uses substring markers instead of digit-prefix rule (`indicators.py:37`):** Spec said to check `parts[2][0].isdigit()` (third `_`-split segment starts with digit, e.g. `DF_UNE_2EAP_…`). Developer used `_ILO_MODELLED` / `_MOD_` substring markers instead. Left as-is for now — both approaches are reasonable; verify against live catalog before Phase 3 wires `is_modelled` into server responses.

**Bonus from QA:** Developer added a `FLOW_DIMS` registry to `indicators.py` (maps each canonical flow ID to `"age"` or `"cur"`). Not in spec but genuinely useful — Phase 2 can use it to auto-select the correct dimension without callers specifying it.

19/19 tests still pass after fixes. Pushed to `origin/main` (private). Published `publish` branch → `public/main` (public repo). Private and public repos are now in sync with Phase 1.

**Files:**
- [execution/phase01/qa-01-review.md](execution/phase01/qa-01-review.md)

---

## 2026-08-28 — Phase 1: scaffold + data layer

Built and committed all Phase 1 files. 19/19 integration tests pass.

**Files created:** `pyproject.toml`, `src/ilostat_mcp/indicators.py`, `src/ilostat_mcp/sdmx_client.py`, `tests/test_sdmx_client.py`, `tests/conftest.py`, `README.md`, `uv.lock`.

**Issues resolved during implementation:**

1. **DSD fetch / Cloudflare challenge** — sdmx1 fetches the DSD with `?references=all` when using dict keys. ILOSTAT's Cloudflare protection blocks this as a bot until challenge-solving completes (30–90s). Added session-scoped conftest fixture to pre-warm the DSD cache before tests run — pytest doesn't apply its per-test timeout to fixtures, so cloudscraper has time to solve the challenge. All individual tests then use the cache and complete in <5s each.

2. **`codelist.items()` bug** — sdmx1's `Codelist.items` is a plain dict, not a method. Fixed to `codelist.items.items()`.

3. **pandas 3.x dtype** — `astype(str)` returns `StringDtype` not `object`. Fixed test assertion to use `pd.api.types.is_string_dtype()`.

Pushed to `origin/main` (private repo).

---

## 2026-08-28 (continued) — Phase 0d/0e pre-Phase 1 design decisions

Ran `phase0de_api_checks.py` and locked all remaining decisions blocking Phase 1. Full record in `phase0de_decisions.md`.

**API findings:**
- PRK (North Korea) returns genuine 404 → confirmed benchmark q021 country
- 404 exception type: `requests.exceptions.HTTPError` from `requests.exceptions` — both "no data" and "invalid flow" raise this; distinguish by which endpoint
- `last_updated` for metadata: lives in the `LAST_UPDATE` annotation on the dataflow object (e.g. "23/08/2026 07:12:11") — NOT in the data message header (which is just the API response timestamp)
- Dataflow description is full HTML — needs stripping before use

**Design decisions locked:**
- `get_time_series` → DataFrame, lowercase columns, 9 kept (time_period, value, obs_status, source, unit_measure, freq, sex, age/cur, note_classif), 8 dropped (measure, unit_measure_type, unit_mult, note_source, note_indicator, decimals, bounds)
- `get_indicator_metadata` → dict {id, title, description, last_updated}
- `search_indicators` → list of {id, title, is_modelled}, cap 20, search flow.name
- FREQ filtered post-fetch in pandas (parameter, default 'A')
- Modelled detection only in search_indicators + indicators.py — client fetches whatever it's given
- `get_yoy_change` warns if source differs between N-1 and N
- Key dict built dynamically — AGE/CUR only included if not None

**Phase 0 status:** All pre-Phase 1 items now closed. Phase 1 is unblocked.

**Files:**
- [execution/phase00-concept-discovery/code/phase0de_api_checks.py](execution/phase00-concept-discovery/code/phase0de_api_checks.py)
- [execution/phase00-concept-discovery/phase0de_decisions.md](execution/phase00-concept-discovery/phase0de_decisions.md)

---

## 2026-08-28 (continued) — Phase 0b gap checks

Ran `phase0b_gaps.py` to close all outstanding data unknowns in one pass. Results in `phase0b_results.md`.

**LCU currency labeling:** API returns generic `CR` code for all countries — no ISO 4217 symbol in the response. Decision: surface the CUR dimension value (`CUR_TYPE_LCU`) in tool output; skip the ISO symbol for v1. Adding a country→currency map is a future enhancement, not a blocker.

**Wage break in canonical flow:** Confirmed in all 9 test countries (THA, NGA, EGY, IND, PAK, IDN, PHL, BGD, MEX). Best benchmark examples: **THA** (multiple SOURCE changes between HIES and LFS) and **EGY** (one clean break, value collapsed 1,091 → 71 EGP when changing from establishment survey to household LFS). ROADMAP updated: benchmark uses canonical `DF_EAR_EMTA_SEX_CUR_NB`, not the care-sector CMTA flow.

**PAK unemployment break:** Confirmed. The 2005→2006 jump (7.0% → 0.6%, OBS_STATUS=B) is the most dramatic example in the dataset. PAK also has HIES/LFS alternations in 2012, 2013, 2016, 2020. Locked for benchmark q019.

**PAK wage break:** Confirmed in canonical wage flow. Same HIES/LFS alternation pattern. Value reversal: 10,093 PKR (2011, LFS) → 9,401 PKR (2012, HIES) → 12,569 PKR (2013, LFS).

**SOM coverage:** Somalia is NOT "no data" — returns 2 rows from two different surveys (LFS + HIES). Cannot use SOM for q021. Finding a genuine "no data" country (PRK, ERI, small territories) is deferred to Phase 0c.

**EU aggregate:** No EU aggregate exists in ILOSTAT. All EU codes (EU, EU27, EU27_2020, EUU, XC) return 500 server errors. Benchmark q023 reclassified as `unanswerable_wrong_entity`.

**MEASURE dimension:** Always single-valued per flow (one MEASURE code per dataflow). Safe to drop from user-facing output.

**Remaining open:** `client.codelist()` call syntax fails (affects CL_AREA and CL_UNIT_MEASURE lookups). Genuine "no data" country for benchmark. Both are Phase 0c/benchmark items, not Phase 1 blockers.

**Files:**
- [execution/phase00-concept-discovery/code/phase0b_gaps.py](execution/phase00-concept-discovery/code/phase0b_gaps.py)
- [execution/phase00-concept-discovery/phase0b_results.md](execution/phase00-concept-discovery/phase0b_results.md)

---

## 2026-08-28 — Concept discovery: full dataflow enumeration for all four concepts

Ran `concept_discovery.py` against live ILOSTAT API. Enumerated every dataflow for unemployment rate (34), employment-to-pop (32), wages (56), and LFPR (30 — new). Applied three-step selection filter to each and ran live cross-checks on the wage candidates.

**Infrastructure note:** ILOSTAT's SDMX API now returns 403 from Cloudflare bot protection. Fixed by replacing sdmx1's default `requests.Session` with `cloudscraper.create_scraper()`. This must be applied in `sdmx_client.py`.

**Key findings:**
- Unemployment, emp-to-pop, and LFPR each had exactly one candidate after filtering. No ambiguity, no cross-check needed.
- Wages had 13 candidates. The 5 flows without a CUR dimension returned 0/5 coverage (can't filter to LCU). The 6 sector-specific flows (care, public, STEM, tourism, plus their no-CUR equivalents) give materially different numbers from the general-economy average. `DF_EAR_EMTA_SEX_CUR_NB` (average, all employees, with CUR) won on coverage (5/5) and scope.
- The SDG unemployment flow (`DF_SDG_B852_SEX_AGE_RT`) looked like a candidate (survey, no extra dims) but uses the 19th ICLS definition — gives NGA 4.68% vs the main flow's 3.45% for the same year. Title exclusion added for "19th icls".
- Sub-annual flows (`DEA1`, `DWA1`, `DWA1` for LFPR) were correctly excluded via title filter.
- Youth unemployment: `AGE_YTHADULT_Y15-24` confirmed to exist in `DF_UNE_DEAP_SEX_AGE_RT`. Use this code for youth filtering.
- Wages PPP: LCU, PPP, USD all have equal data (9 rows each for FRA). PPP not exposed as separate canonical for v1 — kept as option within the same flow.

**Decisions locked:**
- All four canonical flows confirmed (see table in `results.md`)
- `indicators.py` is now fully unblocked
- Youth unemployment = `AGE_YTHADULT_Y15-24` filter on canonical unemployment flow

**Files:**
- [execution/phase00-concept-discovery/code/concept_discovery.py](execution/phase00-concept-discovery/code/concept_discovery.py)
- [execution/phase00-concept-discovery/results_raw.txt](execution/phase00-concept-discovery/results_raw.txt)
- [execution/phase00-concept-discovery/results.md](execution/phase00-concept-discovery/results.md)

**Next:** Phase 0e unknowns 15–19 (API-call group), then Phase 0d unknown 10 (response structure), then Phase 1.

---

## 2026-07-26 (continued — Phase 0a dataflow selection)

Read ILOSTAT SDMX API Guide v4.1 (PDF in `local-notes/docs/`) to answer Part 2 unknowns from the Phase 0a plan (FREQ=A filter, SOURCE attribute, CUR filter, 404 vs KeyError). Wrote and ran `phase0a_scratch_dataflow_selection.py` to answer unknowns 1b–1e.

**Key findings:**
- 34 unemployment / 56 wage / 14 youth unemployment / 32 employment-to-pop flows total
- Youth unemployment: no survey flows exist — all 14 are ILO modelled estimates. Approach: filter `DF_UNE_DEAP_SEX_AGE_RT` by age 15–24 instead.
- Canonical flows confirmed: `DF_UNE_DEAP_SEX_AGE_RT` (unemployment, 252 countries), `DF_EAR_EMTA_SEX_CUR_NB` (wages, 130 countries), `DF_EMP_DWAP_SEX_AGE_RT` (employment-to-pop)
- 1d cross-flow comparison: all 5 test countries DIFFER — canonical selection materially changes the number returned. Example: NGA unemployment spans 3.15–10.7% depending on the flow.
- 1e search risk: plain keyword search is unreliable. "youth unemployment" returns 100% modelled results. Canonical unemployment flow ranks #22 for "unemployment rate". `search_indicators` must annotate `is_modelled` and the system prompt must steer to survey flows.

**Decisions locked:**
- Canonical flows per concept (see table in `phase0a_dataflow_selection.md`)
- Youth unemployment = age filter on `DF_UNE_DEAP_SEX_AGE_RT`, not a separate flow
- `search_indicators` must include `is_modelled` flag; "earnings" is the correct wage keyword (not "wages" — 0 results)

**Files:**
- [execution/phase00/code/phase0a_scratch_dataflow_selection.py](execution/phase00/code/phase0a_scratch_dataflow_selection.py)
- [execution/phase00/phase0a_dataflow_selection.md](execution/phase00/phase0a_dataflow_selection.md) — findings + locked decisions
- [execution/phase00/phase0a_results.md](execution/phase00/phase0a_results.md) — added sections 14–15 (ID structure, API mechanics)

**Next:** Phase 0e unknowns 15–19 (the API-call group), then Phase 0d unknown 10, then Phase 1.

---

## 2026-07-26 — Phase 0a plan written (dataflow selection as primary goal) + use_cases.md restructured + phase_0e_plan.md extended to 22 unknowns + ground truth lookup sheet (final) + overall dev steps

**Phase 0a plan written:** `plan/phase00/phase_0a_plan.md` created. Main goal is now dataflow selection — which of 1,210 flows do we use per concept and why? Five unknowns: decode the ID naming taxonomy, enumerate alternatives per concept, define and apply a selection criterion, check whether alternatives return the same numbers, verify `search_indicators` surfaces the canonical flow reliably. Original execution (API sanity check) appended at the bottom in brief — it answered the secondary questions but left the primary question completely open. ROADMAP updated to reflect split status (API check done; dataflow selection still pending).

**use_cases.md restructured:** removed "How the MCP guides Claude's behaviour" (moved to overall_dev_steps.md before Phase 2). Flow is now: what this project is → what you can ask → packaged workflow → what you can't ask → combo queries. All section headings are plain English now.

**Phase 0e extended from 16 to 22 unknowns:**
- Unknowns 31–34: full API coverage run — all 335 countries × 4 canonical dataflows for dimension values, country data presence, break prevalence, and PPP availability. Supersedes the narrow spot checks in unknowns 16–17.
- Unknown 35: where redirect-to-correct-source language lives (open).
- Unknown 36: `labour_market_snapshot` implementation — resolved: FastMCP prompt (Option A). Pros/cons: simpler server code, graceful partial failure, each tool call visible to user; tradeoff is non-deterministic chaining, but acceptable for a workflow prompt.
- Unknown 24 also resolved in same session: `labour_market_snapshot` chain uses FastMCP prompt returning a Message list.

**ROADMAP.md updated** to reflect 22 unknowns and two pre-Phase 1 scripts (narrow spot-check + full coverage).

---

## 2026-07-26 — Ground truth lookup sheet + use case specification + overall dev steps + Phase 0e plan

Audited all Phase 0a–0d plans and results for open questions that weren't addressed. Found 16 unknowns across future phases and wrote them up as Phase 0e.

**Four groups:**
- **Group A (unknowns 15–19):** `sdmx_client.py` internals that Phase 0a noted as symptoms but never resolved — modelled estimate detection rule, FREQ=A filter implementation, CUR dimension default, 404 vs KeyError distinction, `get_indicator_metadata` last_updated source. All five need a short API verification call. Block Phase 1.
- **Group B (unknowns 20–24):** Internal architecture decisions — break detection grain (per-series vs full DataFrame), where `DISABLE_BREAK_CHECK` is read, `get_yoy_change` → `breaks.py` call pattern, `growth.py` function signatures, `labor_market_snapshot` prompt chain. Desk research; no API calls needed. Block Phases 2–4.
- **Group C (unknowns 25–28):** Benchmark scoring design — judge system prompt text + JSON schema, metric aggregation formulas for the four benchmark metrics, `needs_review` flag definition for `BENCHMARK_SCHEMA.md`, DEU emp-to-pop survey flow check (the one Phase 0b open item that the follow-up didn't close). Block Phase 5.
- **Group D (unknowns 29–30):** Distribution research — `smithery.yaml` format, `pyproject.toml` entry point for `uvx`-installable publish. Block Phase 6; can be done any time after Phase 3.

**Files:**
- [../benchmark/ground_truth_lookup.md](../benchmark/ground_truth_lookup.md) — Kanza's lookup sheet: rewritten with step-by-step ILOSTAT website guidance (no code), why-we-do-this-benchmark intro, plain-English explanation of all 6 categories, and per-question recording format. All sdmx library references removed.
- [plan/use_cases.md](plan/use_cases.md) — use case specification: supported queries (unemployment, wages, youth unemployment) with expected results; unsupported queries with what the tool should say
- [plan/overall_dev_steps.md](plan/overall_dev_steps.md) — plain-English phase walkthrough with Mermaid diagrams (MCP lifecycle, module deps, break detection flow, benchmark conditions)
- [plan/phase00/phase_0e_plan.md](plan/phase00/phase_0e_plan.md) — new plan file
- [plan/ROADMAP.md](plan/ROADMAP.md) — Phase 0e entry added

**Next:** Phase 0e unknowns 15–19 (the API-call group), then Phase 0d unknown 10, then Phase 1.

---

## 2026-07-24 (continued — Phase 0b data discoveries)

Ran `scratch_phase0b.py` against live ILOSTAT API. All checks complete.

**Key findings:**
- NGA break years locked: 2011 and 2019 (q003, q018 updated)
- THA wage break years locked: 2013 and 2014 (q020 updated)
- THA employment series is clean — q017 stays `answerable_clean`
- VNM has wage data 2018–2022; THA breaks are outside that range — q029 stays `comparative`
- MYS latest unemployment is 2022 (not 2023) — q011 year shifted to 2022
- PAK wage break confirmed in `DF_EAR_CMTA_SEX_CUR_NB` — no country swap needed for q004
- PAK has 5 employment breaks in 2010–2020 — q019 `warn_and_answer` confirmed
- **SOM (Somalia) has unemployment data** — q021 premise is wrong, question must be rewritten
- **EU has codes X92 (EU27) and X82 (EU28) with data** — q023 premise is wrong, question must be rewritten
- q002 (SGP wages) and q010 (DEU wages): `DF_EAR_CMTA_SEX_CUR_NB` returns 404 — need correct wage flows
- MEASURE dimension: one value per dataflow, no filter needed in sdmx_client.py

**Decisions locked:**
- All answerable question dataflow IDs locked (except q002 SGP, q010 DEU — still TBD)
- `indicators.py` structure: one canonical ID per theme
- No MEASURE filter in sdmx_client.py

**Open before handing questions to Kanza:**
1. q021 rewrite — find a truly no-data country
2. q023 rewrite — find a truly no-code supranational entity (ASEAN/BRICS/etc.)
3. SGP wage flow (q002) and DEU wage flow (q010)
4. GEO wage data check (q009) — manual ILOSTAT lookup
5. DEU emp-to-pop: verify survey-based DWAP flow exists vs. using 2WAP modelled

**Files:**
- [execution/phase00/code/phase0b_scratch.py](execution/phase00/code/phase0b_scratch.py)
- [execution/phase00/phase0b_results.md](execution/phase00/phase0b_results.md)
- [../benchmark/benchmark_questions.json](../benchmark/benchmark_questions.json) — 15 questions updated; q021 and q023 flagged for rewrite

**Next:** Resolve 5 open items above, then produce Kanza's lookup sheet.

---

## 2026-07-24 (continued — Phase 0b follow-up)

Ran `scratch_phase0b_followup.py` to close the 4 remaining open items.

**Findings:**
- q021 replacement: Yemen (YEM) — no survey data, modelled estimates exist. Same pattern as PRK. Country changed.
- q023 replacement: GCC (Gulf Cooperation Council) — confirmed no code in CL_AREA. EU, ASEAN, BRICS, G7, G20, Arab League all have codes. q023 category also corrected to `unanswerable_wrong_entity`.
- SGP and DEU wages: both found in `DF_EAR_EMTA_SEX_CUR_NB` (average monthly earnings). FRA and THA also confirmed in the same flow. All wage questions unified onto this single canonical flow.
- GEO (Georgia) has wage data in `DF_EAR_EMTA_SEX_CUR_NB` — q009 stays `disambiguate`, notes updated to reflect that after disambiguation a real answer exists.

**All 30 questions now have locked dataflow IDs and correct categories. benchmark_questions.json is ready for Kanza.**

**Files:**
- [execution/phase00/code/phase0b_scratch_followup.py](execution/phase00/code/phase0b_scratch_followup.py)
- [../benchmark/benchmark_questions.json](../benchmark/benchmark_questions.json) — all questions finalised

**Next:** Produce Kanza's lookup sheet, then Phase 0d unknown 10, then Phase 1.

---

## 2026-07-24 (continued — Phase 0c extended discovery)

Ran `scratch_benchmark_infra.py` — all 17 "runs now" unknowns resolved.

**Key findings:**
- `claude -p` subprocess: clean, exit 0, empty stderr, no deadlock risk with `capture_output=True`.
- `--output-format json` gives `data["result"]` for the answer plus `total_cost_usd` and full token breakdown built in — no separate cost estimation needed.
- Config isolation: `CLAUDE_CONFIG_DIR` env var breaks auth (keychain-based). Use `--mcp-config <path> --strict-mcp-config` instead — confirmed working.
- No `--timeout` CLI flag. Use `subprocess.run(timeout=120)` as safety net.
- Judge: `--system-prompt` + `--json-schema` + `--output-format json` is the right pattern. 5/5 valid JSON, no markdown fences.
- Judge edge case: hedged-but-correct answers (e.g. "in the 3.7% range") scored `wrong_value`. Need manual review pass for these.
- Serial benchmark: 15.3 min for 120 calls. Under 45-min threshold — no parallelization needed.
- `--model claude-sonnet-5` confirmed. Auth is keychain; fails cleanly without it (exit 1, clear message).
- 5 unknowns deferred to Phase 2: MCP server lifecycle, tool-call output format, parallel contention, env var inheritance, MCP call timing.

**Decisions locked:** `run_benchmark.py` invocation pattern is now fully specified in `benchmark_infra_results.md`.

**Files:**
- [execution/phase00/code/phase0c_scratch.py](execution/phase00/code/phase0c_scratch.py)
- [execution/phase00/phase0c_results.md](execution/phase00/phase0c_results.md)

**Next:** Phase 0b data checks, then Phase 0d unknown 10 (response structure), then Phase 1.

---

## 2026-07-24

Cross-phase unknown audit. Added Phase 0b, 0c, 0d. Restructured directories to zero-padded numeric format.

**Phase 0b** — data unknowns blocking Phase 1: emp-to-pop dataflow ID (q013), youth AGE code (q016), PAK employment break in main flow (q019), PAK wage break (q004 country TBD), Somalia/EU coverage (q021/q023), MEASURE dimension cardinality, q029 THA recategorisation check.

**Phase 0c** — benchmark runner: 7 unknowns around `claude -p` subprocess (output format, config isolation, env inheritance, judge reliability, timing, model flag). No Anthropic API needed — `claude -p` handles all three conditions.

**Phase 0d** — MCP design quality: 7 unknowns (tool description style, error contract, `get_time_series` response structure, system prompt content, `search_indicators` format, MCP Inspector, prompt injection). Unknown 10 (response structure) must be locked before Phase 1 — it determines `sdmx_client.py`'s return shape.

**Decisions locked:**
- CAGR/trend when break detected: warn+compute, not refuse (forced by `warn_and_answer` expected response type)
- `get_yoy_change` checks for SOURCE break between N-1 and N
- Directory naming: `phase00`, `phase01`, … Sub-phases (0a/0b/0c/0d) stay within `phase00/`
- THA wage break corrected to resolved in ROADMAP (was incorrectly marked open)

**Files:**
- [plan/ROADMAP.md](plan/ROADMAP.md)
- [plan/phase00/phase_0c_plan.md](plan/phase00/phase_0c_plan.md)
- [plan/phase00/phase_0d_plan.md](plan/phase00/phase_0d_plan.md)
- `CLAUDE.md` — directory naming rule added

**Next:** Phase 0b data checks, then Phase 0d unknown 10, then Phase 1.

---

## 2026-07-23

Kickoff session. No code exists yet — only `CLAUDE.md` and `benchmark/` (schema + 12 starter questions with null ground truth).

**Decisions made:**
- Confirmed 6-phase plan (Phase 0 Discovery through Phase 6 Polish)
- Phase 0 runs first and must answer all critical unknowns before any production code
- `get_countries()` returns all ILOSTAT countries; tool reports if queried country lacks employment/wages coverage
- Smithery (discoverability) and PyPI (distribution) are separate — both in scope for v1
- Benchmark questions expanded to ~30 during Phase 0 (questions written now, ground truth filled after Phase 3)
- `search_indicators` design decision deferred to Phase 0 (depends on dataflow count)

**Open questions going into Phase 0:**
- Does ILOSTAT actually populate `SOURCE` attribute and `OBS_PRE_BREAK_VALUE` in SDMX responses?
- Which dataflow IDs cover employment + wages and return real data via `sdmx1`?
- Which countries have confirmed methodology breaks in employment/wages series?
- How many relevant dataflows exist → informs `search_indicators` design

**References:**
- [plan/ROADMAP.md](plan/ROADMAP.md) — full phase plan with open decisions
- [../benchmark/BENCHMARK_SCHEMA.md](../benchmark/BENCHMARK_SCHEMA.md) — benchmark methodology
- [../benchmark/benchmark_questions.json](../benchmark/benchmark_questions.json) — 12 starter questions (ground truth null)

**Next:** Start Phase 0 discovery.

---

## 2026-07-23 (continued — Phase 0 execution)

Ran `scratch_discovery.py` end-to-end against live ILOSTAT API. All 8 sections complete.

**Key findings:**
- 1210 total dataflows, 753 employment/wage-related. Bulk fetch works (no 413 in practice).
- `to_pandas(msg, attributes='osgd')` → DataFrame with SOURCE column confirmed present.
- `OBS_PRE_BREAK_VALUE` NOT populated by ILOSTAT — break detection uses SOURCE diff only.
- **Nigeria (NGA)** and **Pakistan (PAK)** confirmed employment SOURCE changes in `DF_UNE_3EAP_SEX_AGE_DSB_RT`.
- **Wage break:** not found in first pass — open item for Phase 1.
- ILO modelled estimates (`DF_*_2EAP_*`) cover North Korea AND 2027 — benchmark q005/q012 need to be tested against survey flows, not modelled estimates.
- CL_AREA: 335 country entries.

**Decisions locked:**
- `search_indicators`: live keyword search (too many flows to curate)
- Break detection: SOURCE attribute diff only

**Files updated:**
- [execution/phase00/code/phase0a_scratch_discovery.py](execution/phase00/code/phase0a_scratch_discovery.py) — discovery script
- [execution/phase00/phase0a_results.md](execution/phase00/phase0a_results.md) — structured findings
- [../benchmark/benchmark_questions.json](../benchmark/benchmark_questions.json) — expanded to 30 questions (q013–q030 added; q003 updated to NGA; q020 still TBD on wage break)
- [plan/ROADMAP.md](plan/ROADMAP.md) — open decisions updated

**Phase 0 checklist:**
- [x] `scratch_discovery.py` runs end-to-end
- [x] All 8 sections recorded in `discovery_results.md`
- [x] Break detection viability verdict logged
- [x] Confirmed break country for employment (NGA, PAK)
- [ ] Confirmed break country for wages — open, carry into Phase 1
- [x] `benchmark_questions.json` has 30 questions
- [x] ROADMAP.md updated with `search_indicators` decision
- [x] Log updated

**Next:** Phase 1 — scaffold + data layer. Carry in: find wage break country (early Phase 1 task).

---

## 2026-07-23 (continued — Phase 0 extended discovery)

Ran `scratch_discovery_2.py` and an Explore agent for FastMCP. All remaining unknowns resolved.

**Key findings:**
- Country filtering: `dsd=False` in `client.data()` — 1.4s vs 5.0s, 3.5× faster. String key format not supported by ILO endpoint (422 error).
- Dimension defaults: `SEX_T` (total), `AGE_YTHADULT_YGE15` (working age 15+).
- NOTE_SOURCE: not useful — just says "ILO-STATISTICS" for every row.
- Wage breaks: many found. Picked Thailand (THA) in `DF_EAR_CMTA_SEX_CUR_NB`. q020 updated.
- FastMCP v3.4.4: `@mcp.tool`, `@mcp.resource("uri")`, return dict directly, `mcp.run()` for stdio.
- Architecture decision: survey data by default; modelled estimates labelled and never used as silent fallback.

**Phase 0 fully complete.** All unknowns resolved.

**Files updated:**
- [execution/phase00/code/phase0a_scratch_discovery2.py](execution/phase00/code/phase0a_scratch_discovery2.py)
- 
- [../benchmark/benchmark_questions.json](../benchmark/benchmark_questions.json) — q020 updated to Thailand

**Next:** API reference, then Phase 1.

---

## 2026-07-23 (continued — API reference)

Ran `scratch_api_reference.py` — captured real output from every API call we'll make in production.

**New findings:**
- FREQ dimension: responses mix Annual (A), Monthly (M), Quarterly (Q) — must filter to FREQ=A for clean annual series
- CUR dimension: wages flows add a currency dimension (LCU/PPP/USD) not in employment flows — default to CUR_TYPE_LCU
- No-data error contract: two types — HTTP 404 (country has no data at all, or future date) and KeyError (country present but not for this period)
- Nigeria break confirmed in main survey flow DF_UNE_DEAP_SEX_AGE_RT with 3 distinct SOURCE values

**Files added:**
- [execution/phase00/code/phase0a_scratch_api_reference.py](execution/phase00/code/phase0a_scratch_api_reference.py)
- [execution/phase00/phase0a_api_reference.md](execution/phase00/phase0a_api_reference.md) — complete API reference with real samples

**Phase 0 fully complete. Ready for Phase 1.**
