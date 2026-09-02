# Phase 3 — Break Detection Results

Date: 2026-09-01

---

## What and why

Break detection is core differentiator #1. Without it, the tool silently
computes trends and growth rates across methodology changes (e.g. a survey
source swap), producing numbers that look valid but aren't comparable.
This phase adds automatic detection to every `get_time_series` call.

---

## What was built

| File | Purpose |
|---|---|
| `src/ilostat_mcp/breaks.py` | `detect_breaks(df)` and `break_years_in_range()` |
| `tests/test_breaks.py` | 20 tests: 13 unit (pure logic) + 7 live (real ILOSTAT data) |

`get_time_series` return type updated from `list[dict]` (raw rows only) to a list
where `result[0]` is a metadata dict `{_breaks: [...]}` and subsequent elements
are the data rows. Always present — not opt-in.

---

## Implementation decisions

**SOURCE attribute diff, not OBS_PRE_BREAK_VALUE.** Phase 0a confirmed
`OBS_PRE_BREAK_VALUE` is never populated in ILOSTAT responses. SOURCE attribute
diff across consecutive annual observations is the only reliable signal.

**Deduplication before comparison.** ILOSTAT returns multiple rows per year
(different sex/age combinations that all share the same SOURCE). Without deduplication
to one source per year, the same break would be detected once per row at the
year boundary. `detect_breaks` collapses to one source per year before comparing.

**Break year attributed to the later year.** The break fires at the year where
the source changes *to* — the first year with the new methodology.
This matches how CAGR/trend warnings describe the event: "break at 2014" means
2014 is the first year that uses the new source, and comparisons across 2013→2014
are unreliable.

---

## Key corrections to Phase 0b findings

Phase 0b identified breaks via a different detection method than the production
implementation. Two corrections locked during Phase 3 testing:

| Finding | Phase 0b said | Actual (Phase 3 live test) |
|---|---|---|
| NGA unemployment breaks | 2011 and 2019 | 2019 only — NGA's flow starts at 2011, no prior row exists to detect a transition there |
| THA wage breaks | 2013 and 2014 | 2014 only — 2013 = HIES, 2014 = LFS. Both years are listed in Phase 0b but 2014 is the break year (first year of new source) |

---

## Test results

**20/20 in test_breaks.py. 53/53 total (all phases).** ruff + mypy clean.

Test classes:
- `TestDetectBreaksUnit` (9 tests) — pure logic: empty df, missing column, single
  row, same source throughout, single change, multiple changes, break attribution,
  NaN sources, unsorted input
- `TestBreakYearsInRange` (4 tests) — range filtering: all in range, outside range,
  boundary years, empty breaks
- `TestDetectBreaksLive` (4 tests) — live API: NGA break at 2019, THA wage break
  at 2014, DEU no breaks, required keys in break dict
- `TestGetTimeSeriesBreakField` (3 tests) — tool integration: break field present
  on clean series, populated for break country, empty on no-data country

---

## Issues found and fixed during implementation

**Phase 0b data corrections (above).** The detection method in the scratch scripts
was different from the production implementation, producing different break years.
All benchmark questions referencing NGA and THA break years were updated.

---

## Phase 4 readiness

`break_years_in_range()` is the helper Phase 4 derived-stat tools use to check
whether a requested CAGR or trend range spans a break. It's already tested and
ready. Phase 4 wires the warning logic into `get_yoy_change`, `get_cagr`, `get_trend`.
