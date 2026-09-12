# Phase 0a — Dataflow Selection + API Sanity Check

Date planned: 2026-07-23 (revised 2026-07-26)

## What and why

Out of ILOSTAT's 1,210 dataflows, this project uses a small handful. The most important question Phase 0a must answer is: **which ones, and why?** Picking the wrong flow means every data point the tool returns could be wrong — a different survey methodology, a different age group, a different country sample. That cannot be fixed later without rewriting the core data layer. The API sanity check (does the library connect, does SOURCE exist, do errors behave as expected) is secondary — useful, but pointless if the wrong flows are locked in.

The first Phase 0a execution (2026-07-23) ran the API sanity check and found the right answers there. It did not do the dataflow selection work. That gap is what this plan corrects. The selection work must be done before Phase 1 coding starts.

---

## Unknowns to resolve

### Part 1 — Dataflow selection (primary — not yet done)

---

#### 1a. What does each segment of a dataflow ID mean?

**What:** Decode the naming convention for ILOSTAT dataflow IDs so we can read the catalog systematically rather than guessing.

**Why:** Every decision below depends on being able to identify which flows cover which concept. Without knowing what `DEAP`, `EMTA`, `CMTA`, `2EAP`, `3EAP`, `2WAP`, `EHRA` mean, we cannot tell the difference between "unemployment rate by sex and age (survey)" and "unemployment rate by sex and age (modelled estimates)" by looking at the ID — which means we risk choosing the wrong one.

**Research:**
- Pull the full catalog title for every flow whose ID contains a segment we haven't decoded. Focus on the middle segment (the part between the concept code and the dimension list): `DEAP`, `EMTA`, `CMTA`, `EHRA`, `2EAP`, `3EAP`, `4EAP`, `2WAP`, `DWAP`.
- Record a translation table: segment → plain-English meaning.
- Confirm: is "leading digit in second segment = modelled estimate" a reliable rule, or are there exceptions?

**Output:** a segment translation table. The `is_modelled()` rule locked.

---

#### 1b. For each concept in scope, how many flows exist and what distinguishes them?

**What:** For each of the four concepts this project covers — unemployment rate, average monthly wages, youth unemployment, employment-to-population ratio — enumerate every flow in the 753 that covers that concept. Then describe what makes each one different from the others.

**Why:** We cannot pick the canonical flow without knowing the alternatives exist. We currently have one flow per concept chosen pragmatically during benchmark setup. There may be five flows for "unemployment rate," each covering a different dimension breakdown or population group. We need the full list before we can justify the selection.

**Research:**
- Search the 753-flow catalog title list for each concept keyword: "unemployment rate", "earnings", "wages", "employment-to-population".
- For each matching flow, record: full title, ID, what dimensions it has (from the ID and DSD), whether it is survey or modelled, and a one-line description of what distinguishes it from the others.
- Group by concept. Count how many alternatives exist per concept.

**Output:** one table per concept listing all alternative flows and their distinguishing characteristics.

---

#### 1c. Selection criterion — what makes a flow the right canonical choice?

**What:** Define the rule we use to pick one canonical flow per concept, then apply it to the alternatives found in 1b.

**Why:** Without a stated criterion, the canonical selection is just "the first one that worked in testing," which is not a defensible choice. The selection criterion is also what we'd use if we expand to a new concept in v2 — it should be reusable, not ad hoc.

**Proposed criterion (to verify, not assumed):** prefer the flow that is (a) survey-based, not modelled; (b) the most general disaggregation available for the concept (total, not broken down by sector or disability); (c) has the broadest real country coverage across the 335 CL_AREA entries.

**Research:**
- Apply the criterion to each alternative list from 1b. Does it produce a clear winner for each concept? Or does it produce a tie that needs a further tiebreaker?
- For the cases where our current canonical flows (from Phase 0b) were already chosen — do they match the criterion? If not, what should replace them?

**Output:** one canonical flow per concept, with a one-sentence justification for each.

---

#### 1d. Do alternative flows for the same concept give different numbers?

**What:** For 5 representative countries (one per region), pull the same year from every alternative flow for unemployment rate and verify whether they all return the same number or different numbers.

**Why:** If all flows for "unemployment rate" return the same number for the same country and year, any of them works and the selection matters less. If they return different numbers, then our canonical selection is critical — and we need to understand which number is "right" and why the alternatives differ (different age group, different survey, different methodology). Returning the wrong number is worse than returning no number.

**Research:**
- Pick 5 countries with confirmed unemployment survey data: MYS, DEU, NGA, BRA, THA.
- For each, pull the most recent available year from every alternative unemployment flow.
- Record all values. If they all match: note "flows are equivalent for this country." If they differ: record the difference and the reason (inspect the DSD and title of the differing flow).

**Output:** a comparison table. Verdict on whether canonical selection materially affects the numbers returned.

---

#### 1e. Does `search_indicators` reliably surface the canonical flow?

**What:** Test keyword searches that a user or agent would actually run ("unemployment rate", "wages", "monthly earnings", "youth unemployment") and check whether the canonical flow appears in the top results — or whether a modelled-estimates flow or a sector-specific flow comes first.

**Why:** The agent uses `search_indicators` before calling `get_time_series`. If the search returns a modelled-estimates flow first and the agent picks it, the tool silently returns imputed numbers. This is the exact failure mode the benchmark is designed to expose — but it would be an architectural failure, not an LLM failure. Understanding what `search_indicators` returns for common queries tells us whether we need to constrain it (e.g. by ranking survey flows above modelled ones, or by always defaulting to canonical flows regardless of search).

**Research:**
- For each concept keyword, run the live catalog search and record the top 5 results (title + ID + modelled/survey).
- Check: does the canonical flow appear first? Or is there a modelled-estimates flow ranked higher?
- Decision to lock: does `search_indicators` need to de-rank modelled flows, or does it rely on the system prompt to instruct the agent to prefer survey flows?

**Output:** search result samples per keyword. Decision on `search_indicators` ranking behaviour.

---

### Part 2 — API mechanics (largely resolved in the original execution — verify gaps only)

The original Phase 0a execution (2026-07-23) resolved most of the API mechanics questions. The following are the only items not yet fully closed:

- **FREQ=A filter implementation** — confirmed that mixed-frequency responses exist; the exact filter argument to restrict to Annual was not recorded. (See also unknown 16 in phase_0e_plan.md.)
- **CUR filter for wages** — confirmed that LCU/PPP/USD all appear; the exact `key=` argument to restrict to LCU was not recorded. (See also unknown 17 in phase_0e_plan.md.)
- **404 vs. KeyError distinction** — noted that both error types exist; not confirmed whether they produce different exception classes in Python. (See also unknown 18 in phase_0e_plan.md.)

These three carry into `code/phase0e_scratch.py` per the Phase 0e plan.

---

## Output

- `execution/phase00/code/phase0a_scratch_dataflow_selection.py` — script for unknowns 1a–1e above. Produces the catalog comparison tables, candidate flow lists, and search result samples.
- `execution/phase00/phase0a_dataflow_selection.md` — findings and locked decisions: canonical flow per concept, selection criterion, segment translation table, `search_indicators` ranking decision.
- Updates to `benchmark_questions.json` if any canonical flows change as a result.

---

## Timing

All of Part 1 must complete before Phase 1 coding starts. The `is_modelled()` rule (1a) and the canonical flow selection (1c) directly determine what `sdmx_client.py` and `indicators.py` contain.

Part 2 gaps carry into Phase 0e unknowns 16–18 and can run in the same session as the Phase 0e scratch script.

---

---

## What the original Phase 0a execution already found (2026-07-23)

The first execution ran the API mechanics check and resolved all of those questions cleanly. Key findings, brief:

- **1,210 total dataflows; 753 employment/wage-related.** `sdmx1` connects with `sdmx.Client('ILO')` — no auth needed.
- **`SOURCE` attribute confirmed present** when fetching with `attributes='osgd'`. `OBS_PRE_BREAK_VALUE` is empty everywhere — break detection uses SOURCE diff only.
- **Mixed-frequency responses confirmed.** ILOSTAT returns Annual + Monthly + Quarterly in the same response. Must filter to Annual.
- **Wage flows have a CUR dimension** (LCU, PPP, USD). Must filter to LCU for default responses.
- **Two data types confirmed:** survey (`DEAP` and similar) vs. modelled estimates (`2EAP`, `2WAP`). North Korea and 2027 both return modelled data — the tool must use survey flows only to correctly treat these as "no data."
- **Country filter:** `dsd=False` in `client.data()` is 3.5× faster than pulling everything. Use it everywhere.
- **Default dimension codes:** `SEX_T` (total), `AGE_YTHADULT_YGE15` (working age 15+).
- **FastMCP v3.4.4 confirmed:** `@mcp.tool`, `@mcp.resource("uri://...")`, return dict directly, `mcp.run()` for stdio.
- **Nigeria (NGA) and Pakistan (PAK) breaks confirmed** in `DF_UNE_3EAP_SEX_AGE_DSB_RT`. Thailand (THA) wage breaks confirmed in `DF_EAR_CMTA_SEX_CUR_NB` — picked for benchmark q020.
- **`LAST_UPDATE` annotation field** available in dataflow metadata — powers `get_indicator_metadata`.
- **`NOTE_SOURCE`** useless — same internal label on every row, not informative. Drop it.

Full detail: `execution/phase00/phase0a_results.md`.
