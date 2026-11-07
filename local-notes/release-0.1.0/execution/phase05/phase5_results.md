# Phase 5 — Benchmark Results

## Status: complete (ground truth fill deferred — Kanza's task)

Kanza ran the full manual benchmark audit on 2026-09-20. Results in
`benchmark/ILO MCP Benchmark Results 20260920.xlsx`.

Raw match rate: 63.3% (19/30 exact).
After root-cause reclassification: 76.7% trustworthy or explainably divergent.
True connector defects requiring fixes: 5/30 (16.7%).

---

## Open issues resolved in this phase (2026-09-21)

### Root cause D — Spain 2022 discrepancy

**Finding:** The connector is correct.

ILOSTAT returns 13.033% for Spain 2022 (adults 15+, AGE_YTHADULT_YGE15, EU Labour
Force Survey). No age code in DF_UNE_DEAP_SEX_AGE_RT gives ~15% for Spain 2022.
The nearest values are: 2021 = 14.914%, 2020 = 15.532%.

Kanza's ~15% figure came from a different source or was the 2021 value — not a
connector defect. Connector returns accurate ILOSTAT data.

No code change needed.

### Root cause B — South Africa youth dataflow

**Finding:** Real defect, fixed.

Root cause: DF_UNE_DEAP_SEX_AGE_RT does not have youth age codes (AGE_YTHBANDS_Y15-29)
for ZAF. Querying it with age_group='youth' returns 404 → empty DataFrame. The correct
flow is DF_UNE_3EAP_SEX_AGE_GEO_RT, which was already registered in FLOW_DIMS and
returns the correct value (ZAF 2021 = 55.574%). But the agent had no guidance to try
a youth-specific flow when the standard one returned empty.

**Fixes applied (commit on 2026-09-21):**

1. `tools/time_series.py` — when `age_group="youth"` and result is empty, `_no_data_reason`
   now says: "This flow may not have youth age codes for this country. Use
   search_indicators('youth unemployment') to find a youth-specific dataflow."

2. `resources.py` (system prompt) — added a rule: "For youth unemployment queries,
   age_group='youth' works only when the chosen flow has youth age codes. If a youth
   query returns no data, use search_indicators('youth unemployment') to find a
   youth-specific dataflow such as DF_UNE_3EAP_SEX_AGE_GEO_RT."

129/129 tests passing. ruff + mypy clean.

---

## Remaining for Phase 5

- benchmark_questions.json ground truth (null → real values) — Kanza's task.
  Values verified and recorded in the Excel file; transfer to JSON is pending.
