# Phase 5 — Break detection vs. ILOSTAT's own break flag (2026-11-07)

## What and why

Our break detection only looked for a change in the survey name (the SOURCE
attribute) between consecutive years. ILOSTAT also marks breaks itself: the
first year after a methodology change gets `obs_status = "B"` ("break in
series"). We never read that flag. This scan checks how often the two agree,
because a break we miss means `get_cagr` / `get_trend` silently compute across
numbers that are not comparable — the exact failure the project exists to stop.

Script: `code/phase5_break_scan.py` (re-runnable). Raw data:
`code/phase5_break_scan.json`.

## Scope

- 4 canonical flows (unemployment, employment-to-population, wages, LFPR)
- 39 countries in `COUNTRY_CURRENCY`, full history 1983–2026
- 159 series, 4,657 observations, all live from ILOSTAT
- Not covered: the disability, GEO, modelled and care-sector-wage flows

## Findings

**1. Blank sources never happen.** 0 of 4,657 observations had an empty
SOURCE. The question of what to do when one side is blank (the code and its
comment disagreed) has never affected a real result.

**2. We missed about 70% of ILOSTAT's own flagged breaks.** Year-to-year
transitions:

| Transition | Count | Meaning |
|---|---|---|
| Source changed and ILOSTAT flagged `B` | 73 | both methods agree |
| ILOSTAT flagged `B`, same source name | **168** | breaks we missed |
| Source changed, no `B` flag | 234 | we flag, ILOSTAT does not |
| No change, no flag | 4,023 | — |

The missed ones are survey redesigns that kept the same survey name — for
example Australia 2018, UK 1999, France 2005, Argentina 2004 are all
"LFS → LFS" with a `B` flag. In plain terms: the survey was rebuilt, so the
numbers jump for reasons that have nothing to do with the labour market, but
the name stayed the same, so we did not notice.

**3. Source-only changes are a mix of real and noise.**
- Real: China census → labour survey (2000 → 2016), Indonesia census → LFS
  (1985 → 1986), India NSS → PLFS (2012 → 2018). ILOSTAT did not flag these
  but the numbers are clearly not comparable.
- Noise: the UK flips between "LFS - EU Labour Force Survey" and
  "LFS - Labour Force Survey" (1992/93, 2003/04) — same survey, two labels.

## Decision

- A break is now recorded when **either** signal fires: ILOSTAT's `B` flag, or
  a change between two known source names. Each break carries a `reasons` list
  (`ilostat_break_flag`, `source_change`) so the agent can explain it.
- Blank sources are ignored, and a source is compared against the **last known**
  source, so a blank year in the middle neither hides a real change nor creates
  two false ones.
- Label noise (the UK case) is accepted for now: a false warning is safer than
  a missed break. If it proves noisy, compare only the source-type prefix
  (LFS / HS / PC) — that needs its own check first.

## Knock-on effects

- More `_break_warning`s will appear in `get_cagr` / `get_trend` answers. The
  `answerable_break` ground truth and the `mcp_no_breakcheck` comparison should
  be re-checked against the new logic before the next benchmark run.
- Benchmark q003 / q018 ("Nigeria unemployment") point at
  `DF_UNE_3EAP_SEX_AGE_DSB_RT`, which turned out to be a **youth-only** flow
  split by disability status (age bands 15–19, 20–24, 25–29, 15–29; disability
  total / with / without). It has no adult-total rows, so it does not answer
  "Nigeria's unemployment rate". Nigeria is also in the main flow
  `DF_UNE_DEAP_SEX_AGE_RT` (sources change 2011, 2014, 2019, 2022; `B` flags in
  2011 and 2024). Re-pointing these two questions is a benchmark decision, not
  made here.
