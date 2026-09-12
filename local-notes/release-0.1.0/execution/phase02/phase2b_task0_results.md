# Phase 2b Task 0 — GEO dimension discovery results

## Flow tested
`DF_UNE_3EAP_SEX_AGE_GEO_RT` — South Africa youth unemployment (q016)

## Finding

Omitting the GEO dimension returns **all three geographic coverages mixed together**:

| GEO code | Meaning | 2022 ZAF youth unemployment |
|---|---|---|
| `GEO_COV_NAT` | National total | 51.79% |
| `GEO_COV_RUR` | Rural | 57.88% |
| `GEO_COV_URB` | Urban | 49.18% |

Three rows per year, one per geography. Without a GEO filter, the caller gets all
three with no way to tell them apart (the `geo` column is not in `_KEEP_COLUMNS`
and gets dropped before the DataFrame is returned).

Adult total (`AGE_YTHADULT_YGE15`) on this flow → empty DataFrame. This flow only
carries youth and geographic breakdowns; it does not include adult totals.

## Decision for Task 1

`FLOW_DIMS` needs to carry both the dimension type **and** a default GEO filter
for this flow. Options:

1. **Store a `geo` key in `FLOW_DIMS`** — e.g. `{"dim": "age", "geo": "GEO_COV_NAT"}`.
   `server.py` reads it and adds `geo="GEO_COV_NAT"` to the `sdmx_client.get_time_series`
   call. `sdmx_client.py` gets a new optional `geo` kwarg that adds `GEO` to the key dict.

2. **Add `geo` as a hardcoded extra key in the FLOW_DIMS entry** — simpler: store
   the full extra key dict per flow rather than just a dimension type string.

Option 2 is simpler and cleaner — FLOW_DIMS becomes `dict[str, dict]` instead of
`dict[str, str]`, each entry is `{"dim": "age"|"cur"|None, "extra": {...}}`. The
`server.py` logic that reads it remains straightforward.

Also: `"geo"` must be added to `_KEEP_COLUMNS` in `sdmx_client.py` so the
geographic breakdown is visible in `get_time_series` output. Without this, the
GEO filter works but the caller can't see which geography was returned.

## Impact on Task 1

`FLOW_DIMS` structure changes from `dict[str, str]` to `dict[str, dict]`.
This is a breaking change in `indicators.py` and `server.py` — both files
must be updated together. The change is self-contained; no other files read
`FLOW_DIMS` directly.
