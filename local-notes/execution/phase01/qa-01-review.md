# qa-01-review — Phase 1 Scaffold + Data Layer

Date: 2026-08-28

---

## Verdict

**PASS-WITH-NOTES**

Three findings: two minor deviations from the Phase 0d/0e spec (annotation
attribute name, `is_modelled` heuristic), one spec compliance note (HTML
stripping). None block Phase 2 — the tests pass and the data layer works
correctly. The annotation attribute finding is worth a quick verify against
the live API before Phase 3.

---

## Critical findings (blockers — must fix before Phase 2)

None.

---

## Minor findings (should fix, not blocking)

**F1 — `get_indicator_metadata`: annotation attribute mismatch**
`sdmx_client.py:154` — The spec (D3) uses `ann.type == "LAST_UPDATE"` to find
the annotation. The implementation checks `ann.id == "LAST_UPDATE"`. In sdmx1,
`Annotation` objects have both an `id` field and a `type_` or `annotationType`
field depending on the version. This coincidentally works if sdmx1 populates
`id` from the XML `<common:AnnotationType>` tag — but the spec said `.type`,
not `.id`. Should be verified against the live API (e.g. `print(ann.id,
ann.type)`) and aligned with whichever attribute actually holds `"LAST_UPDATE"`.
Impact: if the attribute is wrong, `last_updated` silently returns `""` for
every flow. The tests don't fail because they only check the key exists, not
that it's non-empty.

**F2 — `is_modelled()` heuristic diverges from spec (D6)**
`indicators.py:34-39` — The spec says: detect modelled flows by checking if the
third `_`-split segment starts with a digit (e.g. `DF_UNE_2EAP_SEX_AGE_RT`).
The implementation instead uses substring markers `_ILO_MODELLED` and `_MOD_`.
This may produce false negatives for actual ILO modelled flows that use the
digit-prefix convention. Before Phase 2 (when `search_indicators` is wired into
the server), verify against live ILOSTAT modelled flow IDs which heuristic
catches more flows accurately, and align with D6 or update D6 to reflect the
chosen approach.

**F3 — `get_indicator_metadata`: HTML not stripped from description**
`sdmx_client.py:150` — The spec (D3) calls for stripping HTML from
`flow.description` using BeautifulSoup. The implementation assigns the raw
string directly: `description = str(flow.description)`. `beautifulsoup4` is
already a declared dependency (pyproject.toml:16) but not imported in
`sdmx_client.py`. If ILOSTAT's description fields contain HTML tags (they
sometimes do), those will leak into tool responses. Low impact for now because
the descriptions in practice are often plain text, but the spec requirement is
unmet.

---

## Checklist results

| Check | Result | Notes |
|---|---|---|
| SDMX isolation | ✅ | `import sdmx` appears only in `sdmx_client.py` |
| No attributions | ✅ | No Co-Authored-By, Generated-by, or AI attribution anywhere |
| get_time_series key dict | ✅ | AGE/CUR added only if not None (lines 86–89) |
| 404 handling | ✅ | HTTPError 404/400 → `pd.DataFrame()` (line 98–101) |
| attributes="o" in to_pandas | ✅ | Line 103 |
| Column naming + drops | ✅ | Lowercased; `_KEEP_COLUMNS` whitelist drops all banned columns |
| FREQ post-fetch filter | ✅ | Lines 112–113 |
| last_updated from annotation | ⚠️ | Uses `ann.id` not `ann.type` — see F1 |
| HTML stripped from description | ❌ | Raw string assigned; BS4 not imported — see F3 |
| search_indicators return shape | ✅ | `{id, title, is_modelled}` dicts |
| result cap (max_results) | ✅ | `matches[:max_results]` (line 206) |
| FLOWS dict complete | ✅ | All 4 canonical flows present with correct IDs |
| is_modelled() logic | ⚠️ | Substring markers instead of digit-prefix rule — see F2 |
| Tests hit real API | ✅ | No mocking of `_client` |
| Tests have timeout | ✅ | Global `timeout = 60` in pyproject.toml — acceptable substitute for per-test decorators |
| PRK for no-data test | ✅ | `test_no_data_country_returns_empty_dataframe` uses PRK |
| KISS / DRY | ✅ | No duplicated logic; each function does one thing |

---

## Notes

**`FLOW_DIMS` registry (indicators.py:19–24):** The spec does not mention this.
It maps each flow ID to its dimension type ("age" or "cur"). This is a useful
addition — Phase 2 server code can use it to auto-fill the right dim kwarg
without hardcoding per-flow logic. Not a problem; just noting it's a small
useful addition beyond the Phase 1 spec.

**Global timeout vs. per-test timeout:** The spec asked for `@pytest.mark.timeout`
on each test. The implementation sets `timeout = 60` globally in `pyproject.toml`
instead, which is equivalent (pytest-timeout applies it to every test). Cleaner
than repeating the decorator. Acceptable.

**`dev` declared twice in pyproject.toml:** Lines 23–26 and 35–39 both define a
`[project.optional-dependencies] dev` / `[dependency-groups] dev` section. The
`[dependency-groups]` block is the uv-native format (newer); the
`[project.optional-dependencies]` is the PEP 517 format. Having both is
harmless but redundant. Minor cleanup opportunity.

**`ilostat-mcp = "ilostat_mcp.server:main"` (pyproject.toml:21):** The original
spec said entrypoint `ilostat_mcp.server:mcp`. The implementation uses `:main`.
`server.py` doesn't exist yet so this can't be verified — just ensure Phase 2
exports a `main` function (or `mcp`) consistent with whatever entrypoint name
lands here.

**19 tests vs 11 in spec:** The implementation wrote 19 tests (spec asked for 11).
All are meaningful — the extras cover `value` dtype, `source` population, string
dtype, break detection in real data (THA), and `get_countries` content. More
coverage is better.
