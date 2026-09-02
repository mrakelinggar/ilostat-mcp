"""
Phase 2 smoke tests — verify each tool function returns the correct Python
type and shape. All tests hit the real ILOSTAT API; the session-scoped
prewarm_dsd_cache fixture (conftest.py) runs automatically and pre-warms the
DSD cache so per-test timeouts are not burned on Cloudflare challenge-solving.

get_time_series returns list[dict] since Phase 3, where:
  result[0] = {"_breaks": [...]}  — series-level metadata
  result[1:] = annual data rows
MCP 1.29.1 requires structured_content.result to be an array, so only list
return types work with FastMCP 3.x.
"""

from unittest.mock import patch

import pytest

from ilostat_mcp.server import (
    get_cagr,
    get_countries,
    get_indicator_metadata,
    get_time_series,
    get_trend,
    get_yoy_change,
    labor_market_snapshot,
    search_indicators,
)

_UNEMPLOYMENT_FLOW = "DF_UNE_DEAP_SEX_AGE_RT"
_WAGE_FLOW = "DF_EAR_EMTA_SEX_CUR_NB"
_GEO_FLOW = "DF_UNE_3EAP_SEX_AGE_GEO_RT"  # youth unemployment with GEO dimension
_REQUIRED_SEARCH_KEYS = {"id", "title", "is_modelled"}
_REQUIRED_METADATA_KEYS = {"id", "title", "description", "is_modelled"}
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
        assert "_breaks" in result[0]  # first element is metadata
        data_rows = result[1:]
        assert len(data_rows) > 0
        assert all(_REQUIRED_TS_KEYS <= set(row) for row in data_rows)

    @pytest.mark.timeout(30)
    def test_prk_returns_only_metadata_with_empty_breaks(self):
        # PRK (North Korea) confirmed 404 in Phase 0
        result = get_time_series(_UNEMPLOYMENT_FLOW, "PRK", "2010", "2023")
        assert len(result) == 1
        meta = result[0]
        assert meta["_breaks"] == []
        assert meta["_missing_years"] == []
        assert "PRK" in str(meta["_no_data_reason"])

    @pytest.mark.timeout(30)
    def test_wage_flow_auto_selects_cur_and_has_unit_measure(self):
        # FLOW_DIMS maps wage flow to "cur" — server must inject CUR_DEFAULT
        result = get_time_series(_WAGE_FLOW, "FRA", "2020", "2023")
        data_rows = result[1:]
        assert len(data_rows) > 0
        assert all("unit_measure" in row for row in data_rows)

    @pytest.mark.timeout(30)
    def test_youth_age_group_returns_different_values_than_total(self):
        # ZAF youth unemployment (GEO flow) — adult total AGE code absent, youth present
        total = get_time_series(_GEO_FLOW, "ZAF", "2022", "2022", age_group="total")
        youth = get_time_series(_GEO_FLOW, "ZAF", "2022", "2022", age_group="youth")
        assert len(youth[1:]) == 1, "Youth should return 1 data row (GEO_COV_NAT)"
        assert len(total[1:]) == 0, "Adult total AGE not available in GEO flow"
        assert youth[1]["value"] > 40, "ZAF youth unemployment >40%"

    def test_invalid_age_group_raises(self):
        with pytest.raises(ValueError, match="age_group"):
            get_time_series(
                _UNEMPLOYMENT_FLOW, "DEU", "2020", "2022", age_group="adult"
            )

    def test_start_year_after_end_year_raises(self):
        with pytest.raises(ValueError, match="start_year"):
            get_time_series(_UNEMPLOYMENT_FLOW, "DEU", "2022", "2018")

    def test_invalid_country_code_raises(self):
        with pytest.raises(ValueError, match="country code"):
            get_time_series(_UNEMPLOYMENT_FLOW, "XYZ", "2020", "2022")

    def test_non_numeric_year_raises(self):
        with pytest.raises(ValueError, match="end_year"):
            get_time_series(_UNEMPLOYMENT_FLOW, "DEU", "2020", "abcd")


# ── TestGetYoyChange ──────────────────────────────────────────────────────────

_YOY_STAT_KEYS = {"year", "value", "prev_year", "prev_value", "change_pct"}
_CAGR_STAT_KEYS = {
    "start_year",
    "end_year",
    "start_value",
    "end_value",
    "cagr_pct",
    "n_years",
}
_TREND_STAT_KEYS = {
    "start_year",
    "end_year",
    "slope",
    "intercept",
    "r_squared",
    "n_points",
}
_METADATA_KEYS = {"_breaks", "_break_warning"}


class TestGetYoyChange:
    @pytest.mark.timeout(30)
    def test_deu_unemployment_returns_correct_structure(self):
        result = get_yoy_change(_UNEMPLOYMENT_FLOW, "DEU", "2022")
        assert isinstance(result, list)
        assert len(result) == 2
        assert _METADATA_KEYS <= set(result[0])
        assert _YOY_STAT_KEYS <= set(result[1])

    @pytest.mark.timeout(30)
    def test_metadata_has_breaks_list_and_warning(self):
        result = get_yoy_change(_UNEMPLOYMENT_FLOW, "DEU", "2022")
        assert isinstance(result[0]["_breaks"], list)
        # DEU unemployment has no breaks -- warning should be None
        assert result[0]["_break_warning"] is None

    @pytest.mark.timeout(30)
    def test_stat_years_are_consecutive(self):
        result = get_yoy_change(_UNEMPLOYMENT_FLOW, "DEU", "2022")
        stat = result[1]
        assert stat["year"] == "2022"
        assert stat["prev_year"] == "2021"

    @pytest.mark.timeout(30)
    def test_prk_no_data_returns_metadata_only(self):
        result = get_yoy_change(_UNEMPLOYMENT_FLOW, "PRK", "2022")
        assert len(result) == 1
        meta = result[0]
        assert meta["_breaks"] == []
        assert meta["_break_warning"] is None
        assert meta["_missing_years"] == []
        assert "PRK" in str(meta["_no_data_reason"])

    def test_invalid_age_group_raises(self):
        with pytest.raises(ValueError, match="age_group"):
            get_yoy_change(_UNEMPLOYMENT_FLOW, "DEU", "2022", age_group="adult")

    def test_non_numeric_year_raises(self):
        with pytest.raises(ValueError, match="year"):
            get_yoy_change(_UNEMPLOYMENT_FLOW, "DEU", "22")

    def test_invalid_country_raises(self):
        with pytest.raises(ValueError, match="country code"):
            get_yoy_change(_UNEMPLOYMENT_FLOW, "XYZ", "2022")


# ── TestGetCagr ───────────────────────────────────────────────────────────────


class TestGetCagr:
    @pytest.mark.timeout(30)
    def test_deu_unemployment_returns_correct_structure(self):
        result = get_cagr(_UNEMPLOYMENT_FLOW, "DEU", "2018", "2022")
        assert isinstance(result, list)
        assert len(result) == 2
        assert _METADATA_KEYS <= set(result[0])
        assert _CAGR_STAT_KEYS <= set(result[1])

    @pytest.mark.timeout(30)
    def test_metadata_has_breaks_list_and_warning(self):
        result = get_cagr(_UNEMPLOYMENT_FLOW, "DEU", "2018", "2022")
        assert isinstance(result[0]["_breaks"], list)
        assert result[0]["_break_warning"] is None

    @pytest.mark.timeout(30)
    def test_n_years_correct(self):
        result = get_cagr(_UNEMPLOYMENT_FLOW, "DEU", "2018", "2022")
        assert result[1]["n_years"] == 4

    @pytest.mark.timeout(30)
    def test_prk_no_data_returns_metadata_only(self):
        result = get_cagr(_UNEMPLOYMENT_FLOW, "PRK", "2015", "2022")
        assert len(result) == 1
        meta = result[0]
        assert meta["_breaks"] == []
        assert meta["_break_warning"] is None
        assert meta["_missing_years"] == []
        assert "PRK" in str(meta["_no_data_reason"])

    def test_start_equals_end_raises(self):
        with pytest.raises(ValueError, match="strictly before"):
            get_cagr(_UNEMPLOYMENT_FLOW, "DEU", "2022", "2022")

    def test_start_after_end_raises(self):
        with pytest.raises(ValueError, match="strictly before"):
            get_cagr(_UNEMPLOYMENT_FLOW, "DEU", "2022", "2018")

    def test_invalid_age_group_raises(self):
        with pytest.raises(ValueError, match="age_group"):
            get_cagr(_UNEMPLOYMENT_FLOW, "DEU", "2018", "2022", age_group="adult")

    def test_non_numeric_year_raises(self):
        with pytest.raises(ValueError, match="start_year"):
            get_cagr(_UNEMPLOYMENT_FLOW, "DEU", "20xx", "2022")

    def test_invalid_country_raises(self):
        with pytest.raises(ValueError, match="country code"):
            get_cagr(_UNEMPLOYMENT_FLOW, "XYZ", "2018", "2022")


# ── TestGetTrend ──────────────────────────────────────────────────────────────


class TestGetTrend:
    @pytest.mark.timeout(30)
    def test_deu_unemployment_returns_correct_structure(self):
        result = get_trend(_UNEMPLOYMENT_FLOW, "DEU", "2018", "2022")
        assert isinstance(result, list)
        assert len(result) == 2
        assert _METADATA_KEYS <= set(result[0])
        assert _TREND_STAT_KEYS <= set(result[1])

    @pytest.mark.timeout(30)
    def test_metadata_has_breaks_list_and_warning(self):
        result = get_trend(_UNEMPLOYMENT_FLOW, "DEU", "2018", "2022")
        assert isinstance(result[0]["_breaks"], list)
        assert result[0]["_break_warning"] is None

    @pytest.mark.timeout(30)
    def test_n_points_at_least_2(self):
        result = get_trend(_UNEMPLOYMENT_FLOW, "DEU", "2018", "2022")
        assert int(result[1]["n_points"]) >= 2  # type: ignore[arg-type]

    @pytest.mark.timeout(30)
    def test_r_squared_in_unit_interval(self):
        result = get_trend(_UNEMPLOYMENT_FLOW, "DEU", "2018", "2022")
        r2 = float(result[1]["r_squared"])  # type: ignore[arg-type]
        assert 0.0 <= r2 <= 1.0

    @pytest.mark.timeout(30)
    def test_prk_no_data_returns_metadata_only(self):
        result = get_trend(_UNEMPLOYMENT_FLOW, "PRK", "2015", "2022")
        assert len(result) == 1
        meta = result[0]
        assert meta["_breaks"] == []
        assert meta["_break_warning"] is None
        assert meta["_missing_years"] == []
        assert "PRK" in str(meta["_no_data_reason"])

    def test_start_equals_end_raises(self):
        with pytest.raises(ValueError, match="strictly before"):
            get_trend(_UNEMPLOYMENT_FLOW, "DEU", "2022", "2022")

    def test_start_after_end_raises(self):
        with pytest.raises(ValueError, match="strictly before"):
            get_trend(_UNEMPLOYMENT_FLOW, "DEU", "2022", "2018")

    def test_invalid_age_group_raises(self):
        with pytest.raises(ValueError, match="age_group"):
            get_trend(_UNEMPLOYMENT_FLOW, "DEU", "2018", "2022", age_group="adult")

    def test_non_numeric_year_raises(self):
        with pytest.raises(ValueError, match="end_year"):
            get_trend(_UNEMPLOYMENT_FLOW, "DEU", "2018", "20xx")

    def test_invalid_country_raises(self):
        with pytest.raises(ValueError, match="country code"):
            get_trend(_UNEMPLOYMENT_FLOW, "XYZ", "2018", "2022")


# ── TestLaborMarketSnapshot ───────────────────────────────────────────────────

# Fixed country list used across snapshot tests -- avoids live API calls.
_MOCK_COUNTRIES = [
    {"code": "DEU", "name": "Germany"},
    {"code": "FRA", "name": "France"},
    {"code": "USA", "name": "United States"},
    {"code": "GBR", "name": "United Kingdom"},
    {"code": "KOR", "name": "Korea, Republic of"},
    {"code": "PRK", "name": "Korea, Democratic People's Republic of"},
]


class TestLaborMarketSnapshot:
    def test_too_many_countries_raises(self):
        # Count validation runs before country resolution -- no API call needed.
        with pytest.raises(ValueError, match="1-3 countries"):
            labor_market_snapshot("DEU, FRA, USA, GBR")

    def test_unknown_country_raises(self):
        with (
            patch(
                "ilostat_mcp.resources.get_cached_countries",
                return_value=_MOCK_COUNTRIES,
            ),
            pytest.raises(ValueError, match="did not match any ILOSTAT country"),
        ):
            labor_market_snapshot("Narnia")

    def test_ambiguous_country_raises(self):
        # "Korea" is a partial match for both KOR and PRK.
        with (
            patch(
                "ilostat_mcp.resources.get_cached_countries",
                return_value=_MOCK_COUNTRIES,
            ),
            pytest.raises(ValueError, match="is ambiguous"),
        ):
            labor_market_snapshot("Korea")

    def test_valid_single_country_returns_string(self):
        with patch(
            "ilostat_mcp.resources.get_cached_countries",
            return_value=_MOCK_COUNTRIES,
        ):
            result = labor_market_snapshot("DEU")
        assert isinstance(result, str)
        assert "DEU" in result

    def test_valid_three_countries_returns_string(self):
        with patch(
            "ilostat_mcp.resources.get_cached_countries",
            return_value=_MOCK_COUNTRIES,
        ):
            result = labor_market_snapshot("DEU, FRA, USA")
        assert isinstance(result, str)
        assert "DEU" in result
        assert "FRA" in result
        assert "USA" in result

    def test_iso_code_input_resolved(self):
        # ISO-3 code input should pass through directly.
        with patch(
            "ilostat_mcp.resources.get_cached_countries",
            return_value=_MOCK_COUNTRIES,
        ):
            result = labor_market_snapshot("GBR")
        assert "GBR" in result

    def test_full_name_input_resolved(self):
        # Exact full name match — resolved to ISO code in output.
        with patch(
            "ilostat_mcp.resources.get_cached_countries",
            return_value=_MOCK_COUNTRIES,
        ):
            result = labor_market_snapshot("Germany")
        assert "DEU" in result
