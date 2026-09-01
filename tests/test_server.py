"""
Phase 2 smoke tests — verify each tool function returns the correct Python
type and shape. All tests hit the real ILOSTAT API; the session-scoped
prewarm_dsd_cache fixture (conftest.py) runs automatically and pre-warms the
DSD cache so per-test timeouts are not burned on Cloudflare challenge-solving.
"""

import pytest

from ilostat_mcp.server import (
    get_countries,
    get_indicator_metadata,
    get_time_series,
    search_indicators,
)

_UNEMPLOYMENT_FLOW = "DF_UNE_DEAP_SEX_AGE_RT"
_WAGE_FLOW = "DF_EAR_EMTA_SEX_CUR_NB"
_GEO_FLOW = "DF_UNE_3EAP_SEX_AGE_GEO_RT"  # youth unemployment with GEO dimension
_REQUIRED_SEARCH_KEYS = {"id", "title", "is_modelled"}
_REQUIRED_METADATA_KEYS = {"id", "title", "description", "last_updated", "is_modelled"}
_REQUIRED_TS_KEYS = {"time_period", "value", "obs_status"}


class TestSearchIndicators:
    @pytest.mark.timeout(30)
    def test_returns_list_of_dicts_with_required_keys(self):
        result = search_indicators("unemployment")
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(_REQUIRED_SEARCH_KEYS <= set(d) for d in result)

    @pytest.mark.timeout(30)
    def test_is_modelled_is_bool(self):
        result = search_indicators("unemployment")
        assert all(isinstance(d["is_modelled"], bool) for d in result)


class TestGetCountries:
    @pytest.mark.timeout(30)
    def test_returns_non_empty_list(self):
        result = get_countries()
        assert isinstance(result, list)
        assert len(result) > 0, "get_countries() must never return an empty list"

    @pytest.mark.timeout(30)
    def test_each_entry_has_code_and_name(self):
        result = get_countries()
        assert all({"code", "name"} <= set(entry) for entry in result)


class TestGetIndicatorMetadata:
    @pytest.mark.timeout(30)
    def test_valid_flow_returns_required_keys(self):
        result = get_indicator_metadata(_UNEMPLOYMENT_FLOW)
        assert _REQUIRED_METADATA_KEYS <= set(result)

    @pytest.mark.timeout(30)
    def test_invalid_flow_returns_empty_dict(self):
        result = get_indicator_metadata("DF_FAKE_FLOW_DOES_NOT_EXIST")
        assert result == {}


class TestGetTimeSeries:
    @pytest.mark.timeout(30)
    def test_deu_unemployment_returns_data(self):
        result = get_time_series(_UNEMPLOYMENT_FLOW, "DEU", "2018", "2023")
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(_REQUIRED_TS_KEYS <= set(row) for row in result)

    @pytest.mark.timeout(30)
    def test_prk_returns_empty_list(self):
        # PRK (North Korea) confirmed 404 in Phase 0
        result = get_time_series(_UNEMPLOYMENT_FLOW, "PRK", "2010", "2023")
        assert result == []

    @pytest.mark.timeout(30)
    def test_wage_flow_auto_selects_cur_and_has_unit_measure(self):
        # FLOW_DIMS maps wage flow to "cur" — server must inject CUR_DEFAULT
        result = get_time_series(_WAGE_FLOW, "FRA", "2020", "2023")
        assert isinstance(result, list)
        assert len(result) > 0
        assert all("unit_measure" in row for row in result)

    @pytest.mark.timeout(30)
    def test_youth_age_group_returns_different_values_than_total(self):
        # ZAF youth unemployment (GEO flow) — adult total AGE code absent, youth present
        total = get_time_series(_GEO_FLOW, "ZAF", "2022", "2022", age_group="total")
        youth = get_time_series(_GEO_FLOW, "ZAF", "2022", "2022", age_group="youth")
        assert len(youth) == 1, "Youth query should return exactly 1 row (GEO_COV_NAT)"
        assert len(total) == 0, "Adult total AGE code not available in this GEO flow"
        assert youth[0]["value"] > 40, "ZAF youth unemployment should be >40%"

    def test_invalid_age_group_raises(self):
        with pytest.raises(ValueError, match="age_group"):
            get_time_series(
                _UNEMPLOYMENT_FLOW, "DEU", "2020", "2022", age_group="adult"
            )

    def test_start_year_after_end_year_raises(self):
        with pytest.raises(ValueError, match="start_year"):
            get_time_series(_UNEMPLOYMENT_FLOW, "DEU", "2022", "2018")
