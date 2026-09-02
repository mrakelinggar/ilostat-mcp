"""
Live integration tests for sdmx_client.py.

These hit the real ILOSTAT API — no mocking. They verify that the client
handles the full range of expected inputs and edge cases correctly.

Run with: pytest tests/test_sdmx_client.py -v
Each test has a 60-second timeout (set globally in pyproject.toml).
"""

import pandas as pd
import pytest

from ilostat_mcp.indicators import (
    AGE_TOTAL,
    CUR_DEFAULT,
    FLOWS,
)
from ilostat_mcp.sdmx_client import (
    get_countries,
    get_indicator_metadata,
    get_time_series,
    search_indicators,
)

# Canonical flow IDs used across tests
UNE_FLOW = FLOWS["unemployment_rate"]  # DF_UNE_DEAP_SEX_AGE_RT
EMP_FLOW = FLOWS["employment_to_pop"]  # DF_EMP_DWAP_SEX_AGE_RT
WAG_FLOW = FLOWS["wages"]  # DF_EAR_EMTA_SEX_CUR_NB
LFP_FLOW = FLOWS["lfpr"]  # DF_EAP_DWAP_SEX_AGE_RT


# ── get_time_series ───────────────────────────────────────────────────────────


class TestGetTimeSeries:
    def test_unemployment_deu_returns_dataframe(self):
        """Basic smoke test — Germany unemployment should return rows."""
        df = get_time_series(UNE_FLOW, "DEU", "2015", "2023", age=AGE_TOTAL)
        assert isinstance(df, pd.DataFrame)
        assert not df.empty, "Expected data for DEU unemployment"

    def test_required_columns_present(self):
        """Output must contain the documented column set."""
        df = get_time_series(UNE_FLOW, "DEU", "2020", "2023", age=AGE_TOTAL)
        for col in ("time_period", "value", "obs_status", "source", "unit_measure"):
            assert col in df.columns, f"Missing column: {col}"

    def test_noise_columns_absent(self):
        """Constant and empty columns must be stripped from output."""
        df = get_time_series(UNE_FLOW, "DEU", "2020", "2023", age=AGE_TOTAL)
        for col in ("freq", "sex", "age", "cur", "geo", "note_classif"):
            assert col not in df.columns, f"Noise column still present: {col}"

    def test_freq_filter_annual_only(self):
        """Annual filter drops sub-annual rows; time_period must be 4-digit years."""
        df = get_time_series(UNE_FLOW, "DEU", "2015", "2023", freq="A", age=AGE_TOTAL)
        # freq column is no longer returned, but the filter still runs —
        # verify by confirming every time_period is a 4-digit year string.
        assert all(
            tp.isdigit() and len(tp) == 4 for tp in df["time_period"]
        ), "Non-annual time_period leaked through annual filter"

    def test_value_column_is_numeric(self):
        """Values should be numeric (float), not strings."""
        df = get_time_series(UNE_FLOW, "DEU", "2018", "2022", age=AGE_TOTAL)
        assert pd.api.types.is_numeric_dtype(df["value"]), "value column is not numeric"

    def test_wages_flow_cur_not_in_output(self):
        """cur is a per-call constant — it must be stripped from output rows."""
        df = get_time_series(WAG_FLOW, "DEU", "2015", "2022", cur=CUR_DEFAULT)
        assert "cur" not in df.columns, "'cur' noise column should not appear in output"

    def test_no_data_country_returns_empty_dataframe(self):
        """PRK (North Korea) has no ILOSTAT data — must return empty DataFrame."""
        df = get_time_series(UNE_FLOW, "PRK", "2000", "2024", age=AGE_TOTAL)
        assert isinstance(df, pd.DataFrame)
        assert df.empty, "Expected empty DataFrame for PRK"

    def test_source_attribute_populated(self):
        """The SOURCE attribute should be non-null for DEU data."""
        df = get_time_series(UNE_FLOW, "DEU", "2015", "2022", age=AGE_TOTAL)
        assert "source" in df.columns
        # At least some rows should have a non-empty source
        assert df["source"].notna().any(), "All SOURCE values are null"

    def test_time_period_is_string(self):
        """time_period must hold plain strings, not Period or datetime objects."""
        df = get_time_series(UNE_FLOW, "DEU", "2018", "2022", age=AGE_TOTAL)
        # pandas 3.x may return StringDtype instead of object — both are fine
        assert (
            pd.api.types.is_string_dtype(df["time_period"])
            or df["time_period"].dtype == object
        ), "time_period should be string dtype"
        assert all(isinstance(v, str) for v in df["time_period"]), (
            "time_period contains non-string values"
        )

    def test_source_changes_detected_in_break_country(self):
        """THA wages have confirmed SOURCE changes — verify they appear in raw data."""
        df = get_time_series(WAG_FLOW, "THA", "2005", "2024", cur=CUR_DEFAULT)
        assert not df.empty, "Expected wage data for THA"
        if "source" in df.columns:
            unique_sources = df["source"].dropna().unique()
            assert len(unique_sources) > 1, (
                "Expected multiple SOURCE values for THA wages (methodology breaks)"
            )


# ── get_indicator_metadata ────────────────────────────────────────────────────


class TestGetIndicatorMetadata:
    def test_valid_flow_returns_dict_with_title(self):
        """A known flow ID should return a dict with a non-empty title."""
        meta = get_indicator_metadata(UNE_FLOW)
        assert isinstance(meta, dict)
        assert meta.get("title"), "Expected a non-empty title"

    def test_invalid_flow_returns_empty_dict(self):
        """An invalid flow ID should return an empty dict, not raise."""
        meta = get_indicator_metadata("DF_FAKE_FLOW_DOES_NOT_EXIST")
        assert meta == {} or not meta, "Expected empty dict for invalid flow"

    def test_last_updated_absent(self):
        """last_updated is never populated by ILOSTAT — must not appear in output."""
        meta = get_indicator_metadata(UNE_FLOW)
        assert "last_updated" not in meta, "last_updated should be dropped"

    def test_is_modelled_flag_false_for_survey_flow(self):
        """Our canonical flows are survey-based, not modelled estimates."""
        meta = get_indicator_metadata(UNE_FLOW)
        assert meta.get("is_modelled") is False, (
            f"{UNE_FLOW} should not be flagged as modelled"
        )


# ── search_indicators ─────────────────────────────────────────────────────────


class TestSearchIndicators:
    def test_returns_list(self):
        """search_indicators always returns a list."""
        results = search_indicators("unemployment")
        assert isinstance(results, list)

    def test_results_capped_at_20(self):
        """Result count must not exceed the default cap of 20."""
        results = search_indicators("unemployment")
        assert len(results) <= 20, f"Got {len(results)} results, expected ≤20"

    def test_each_result_has_required_keys(self):
        """Every result dict must have id, title, is_modelled."""
        results = search_indicators("unemployment")
        for r in results:
            assert "id" in r and "title" in r and "is_modelled" in r, (
                f"Result missing required keys: {r}"
            )

    def test_no_match_returns_empty_list(self):
        """A nonsense keyword should return an empty list, not raise."""
        results = search_indicators("xyzzy_no_such_indicator_ever")
        assert results == []


# ── get_countries ─────────────────────────────────────────────────────────────


class TestGetCountries:
    def test_returns_list_of_dicts(self):
        """get_countries returns a list of {code, name} dicts."""
        countries = get_countries()
        # May be empty if codelist endpoint fails — that's acceptable
        assert isinstance(countries, list)
        if countries:
            assert "code" in countries[0] and "name" in countries[0]

    def test_contains_known_countries_if_non_empty(self):
        """If the list is non-empty, it should include DEU and FRA."""
        countries = get_countries()
        if not countries:
            pytest.skip("CL_AREA codelist not available — skipping content check")
        codes = {c["code"] for c in countries}
        assert "DEU" in codes, "DEU missing from country list"
        assert "FRA" in codes, "FRA missing from country list"
