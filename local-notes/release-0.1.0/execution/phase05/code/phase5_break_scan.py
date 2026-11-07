"""
Compare our SOURCE-diff break detection against ILOSTAT's own break flag.

ILOSTAT marks the first observation after a methodology break with
obs_status "B". This script fetches the full history of the 4 canonical flows
for the 39 countries in COUNTRY_CURRENCY, then counts every year-to-year
transition by (did the source change?, did ILOSTAT flag "B"?).

Run from the repo root:
    uv run python local-notes/release-0.1.0/execution/phase05/code/phase5_break_scan.py
    uv run python .../phase5_break_scan.py --analyse-only   # reuse saved JSON

Output: phase5_break_scan.json next to this script, plus a summary on stdout.
Findings are written up in ../phase5_break_detection_findings.md.
"""

import collections
import json
import sys
from pathlib import Path

_OUT = Path(__file__).with_name("phase5_break_scan.json")
_FIRST_YEAR = "1983"
_LAST_YEAR = "2026"


def scan() -> None:
    """Fetch every flow x country series and save (year, source, obs_status)."""
    from ilostat_mcp.indicators import COUNTRY_CURRENCY, FLOWS
    from ilostat_mcp.tools.series import fetch_series

    out = []
    for flow in FLOWS.values():
        for cty in COUNTRY_CURRENCY:
            try:
                df = fetch_series(flow, cty, _FIRST_YEAR, _LAST_YEAR, "total")
            except RuntimeError as exc:
                out.append({"flow": flow, "cty": cty, "err": str(exc)})
                continue
            if df.empty:
                continue
            df = df.sort_values("time_period")
            out.append(
                {
                    "flow": flow,
                    "cty": cty,
                    "rows_per_year": int(df.groupby("time_period").size().max()),
                    "obs": [
                        [
                            r.time_period,
                            None if r.source != r.source else r.source,
                            r.obs_status or "",
                        ]
                        for r in df.itertuples()
                    ],
                }
            )
    _OUT.write_text(json.dumps(out))


def analyse() -> None:
    """Print transition counts and examples from the saved scan."""
    data = json.loads(_OUT.read_text())
    errors = [x for x in data if "err" in x]
    series = [x for x in data if "err" not in x]
    n_obs = sum(len(x["obs"]) for x in series)
    n_blank = sum(1 for x in series for o in x["obs"] if not o[1])
    print(f"series: {len(series)}  errors: {len(errors)}")
    print(f"max rows per year: {max(x['rows_per_year'] for x in series)}")
    print(f"observations: {n_obs}  with blank source: {n_blank}")

    counts: collections.Counter[tuple[str, bool]] = collections.Counter()
    examples: dict[tuple[str, bool], list[tuple[str, ...]]] = collections.defaultdict(
        list
    )
    for x in series:
        for prev, curr in zip(x["obs"], x["obs"][1:], strict=False):
            a, b = prev[1] or "", curr[1] or ""
            if a == b:
                kind = "same_source"
            elif a and b:
                kind = "source_changed"
            else:
                kind = "blank_on_one_side"
            flagged = curr[2] == "B"
            counts[(kind, flagged)] += 1
            if kind != "same_source" or flagged:
                examples[(kind, flagged)].append(
                    (x["flow"], x["cty"], prev[0], curr[0], a[:35], b[:35])
                )
    print("\n(transition kind, ILOSTAT flagged B): count")
    for key, n in sorted(counts.items()):
        print(f"  {key}: {n}")
    for key, rows in examples.items():
        print(f"\nexamples {key}:")
        for row in rows[:8]:
            print("  ", row)


if __name__ == "__main__":
    if "--analyse-only" not in sys.argv:
        scan()
    analyse()
