"""
Unit tests for analysis/growth.py -- pure math, no API calls.

All expected values are hand-calculated. Tests verify correctness, not just
"does it run". See spec comments for derivations of expected values.
"""

import pandas as pd
import pytest

from ilostat_mcp.analysis.growth import cagr, trend, yoy

# -- Helpers ------------------------------------------------------------------


def make_df(periods: list[str], values: list[float]) -> pd.DataFrame:
    """Minimal DataFrame matching the sdmx_client.get_time_series schema."""
    return pd.DataFrame({"time_period": periods, "value": values})


# -- yoy ----------------------------------------------------------------------


class TestYoy:
    def test_simple_increase(self) -> None:
        # 8.0 -> 10.0: ((10 - 8) / |8|) * 100 = 25.0
        df = make_df(["2019", "2020"], [8.0, 10.0])
        result = yoy(df, "2020")
        assert result["change_pct"] == 25.0

    def test_simple_decrease(self) -> None:
        # 10.0 -> 8.0: ((8 - 10) / |10|) * 100 = -20.0
        df = make_df(["2019", "2020"], [10.0, 8.0])
        result = yoy(df, "2020")
        assert result["change_pct"] == -20.0

    def test_negative_base(self) -> None:
        # -5.0 -> -4.0: ((-4 - -5) / |-5|) * 100 = (1 / 5) * 100 = 20.0
        df = make_df(["2019", "2020"], [-5.0, -4.0])
        result = yoy(df, "2020")
        assert result["change_pct"] == 20.0

    def test_result_keys(self) -> None:
        df = make_df(["2019", "2020"], [8.0, 10.0])
        result = yoy(df, "2020")
        assert set(result.keys()) == {
            "year",
            "value",
            "prev_year",
            "prev_value",
            "change_pct",
        }

    def test_result_values(self) -> None:
        df = make_df(["2019", "2020"], [8.0, 10.0])
        result = yoy(df, "2020")
        assert result["year"] == "2020"
        assert result["value"] == 10.0
        assert result["prev_year"] == "2019"
        assert result["prev_value"] == 8.0

    def test_rounded_to_4dp(self) -> None:
        # (4/3 - 1) * 100 = 33.3333...% -- must be rounded to 4 dp
        df = make_df(["2019", "2020"], [3.0, 4.0])
        result = yoy(df, "2020")
        assert result["change_pct"] == round(((4.0 - 3.0) / abs(3.0)) * 100, 4)

    def test_missing_year_raises(self) -> None:
        df = make_df(["2019", "2020"], [8.0, 10.0])
        with pytest.raises(ValueError, match="2021"):
            yoy(df, "2021")

    def test_missing_prev_year_raises(self) -> None:
        # Only 2020 present; 2019 (prev_year) is absent
        df = make_df(["2020"], [10.0])
        with pytest.raises(ValueError, match="2019"):
            yoy(df, "2020")

    def test_zero_prev_value_raises(self) -> None:
        df = make_df(["2019", "2020"], [0.0, 10.0])
        with pytest.raises(ValueError, match="zero"):
            yoy(df, "2020")


# -- cagr ---------------------------------------------------------------------


class TestCagr:
    def test_five_year_ten_percent(self) -> None:
        # 100 -> 161.051 over 5 years: 1.1^5 = 1.61051 -> CAGR = 10.0%
        df = make_df(
            ["2015", "2016", "2017", "2018", "2019", "2020"],
            [100.0, 110.0, 121.0, 133.1, 146.41, 161.051],
        )
        result = cagr(df, "2015", "2020")
        assert result["cagr_pct"] == pytest.approx(10.0, abs=0.0001)

    def test_one_year_ten_percent(self) -> None:
        # 100 -> 110 over 1 year: CAGR = 10.0%
        df = make_df(["2019", "2020"], [100.0, 110.0])
        result = cagr(df, "2019", "2020")
        assert result["cagr_pct"] == 10.0

    def test_result_keys(self) -> None:
        df = make_df(["2019", "2020"], [100.0, 110.0])
        result = cagr(df, "2019", "2020")
        assert set(result.keys()) == {
            "start_year",
            "end_year",
            "start_value",
            "end_value",
            "cagr_pct",
            "n_years",
        }

    def test_n_years_correct(self) -> None:
        df = make_df(["2015", "2020"], [100.0, 161.051])
        result = cagr(df, "2015", "2020")
        assert result["n_years"] == 5

    def test_rounded_to_4dp(self) -> None:
        # 100 -> 150 over 3 years: (1.5)^(1/3) - 1 ~= 14.4714...%
        df = make_df(["2017", "2018", "2019", "2020"], [100.0, 115.0, 130.0, 150.0])
        result = cagr(df, "2017", "2020")
        expected = round(((150.0 / 100.0) ** (1.0 / 3) - 1) * 100, 4)
        assert result["cagr_pct"] == expected

    def test_start_equals_end_raises(self) -> None:
        df = make_df(["2020"], [100.0])
        with pytest.raises(ValueError, match="n_years"):
            cagr(df, "2020", "2020")

    def test_missing_start_year_raises(self) -> None:
        df = make_df(["2020"], [110.0])
        with pytest.raises(ValueError, match="2019"):
            cagr(df, "2019", "2020")

    def test_missing_end_year_raises(self) -> None:
        df = make_df(["2019"], [100.0])
        with pytest.raises(ValueError, match="2020"):
            cagr(df, "2019", "2020")

    def test_zero_start_value_raises(self) -> None:
        df = make_df(["2019", "2020"], [0.0, 110.0])
        with pytest.raises(ValueError, match="non-positive"):
            cagr(df, "2019", "2020")

    def test_negative_start_value_raises(self) -> None:
        df = make_df(["2019", "2020"], [-5.0, 10.0])
        with pytest.raises(ValueError, match="non-positive"):
            cagr(df, "2019", "2020")


# -- trend --------------------------------------------------------------------


class TestTrend:
    def test_perfectly_collinear_three_points(self) -> None:
        # x = [2020, 2021, 2022], y = [5, 6, 7]
        # mean_x = 2021, mean_y = 6
        # ss_xx = 1+0+1 = 2, ss_xy = 1+0+1 = 2
        # slope = 1.0, intercept = 6 - 1*2021 = -2015.0, r_squared = 1.0
        df = make_df(["2020", "2021", "2022"], [5.0, 6.0, 7.0])
        result = trend(df, "2020", "2022")
        assert result["slope"] == 1.0
        assert result["intercept"] == -2015.0
        assert result["r_squared"] == 1.0

    def test_result_keys(self) -> None:
        df = make_df(["2020", "2021", "2022"], [5.0, 6.0, 7.0])
        result = trend(df, "2020", "2022")
        assert set(result.keys()) == {
            "start_year",
            "end_year",
            "slope",
            "intercept",
            "r_squared",
            "n_points",
        }

    def test_n_points_correct(self) -> None:
        df = make_df(["2020", "2021", "2022"], [5.0, 6.0, 7.0])
        result = trend(df, "2020", "2022")
        assert result["n_points"] == 3

    def test_two_point_trend(self) -> None:
        # Minimum valid case: 2 points
        # mean_x = 2020.5, mean_y = 5.0
        # slope = ss_xy/ss_xx = ((-0.5)(-1)+(.5)(1)) / (0.25+0.25) = 1/0.5 = 2.0
        # intercept = 5 - 2 * 2020.5 = 5 - 4041 = -4036.0
        df = make_df(["2020", "2021"], [4.0, 6.0])
        result = trend(df, "2020", "2021")
        assert result["slope"] == 2.0
        assert result["intercept"] == -4036.0

    def test_r_squared_in_unit_interval(self) -> None:
        # Non-perfect fit -- r_squared must be in [0, 1]
        df = make_df(["2020", "2021", "2022"], [5.0, 5.5, 7.0])
        result = trend(df, "2020", "2022")
        assert 0.0 <= float(result["r_squared"]) <= 1.0

    def test_r_squared_rounded_to_4dp(self) -> None:
        df = make_df(["2020", "2021", "2022"], [5.0, 5.5, 7.0])
        result = trend(df, "2020", "2022")
        assert result["r_squared"] == round(float(result["r_squared"]), 4)

    def test_slope_intercept_rounded_to_6dp(self) -> None:
        df = make_df(["2020", "2021", "2022"], [5.0, 5.5, 7.0])
        result = trend(df, "2020", "2022")
        assert result["slope"] == round(float(result["slope"]), 6)
        assert result["intercept"] == round(float(result["intercept"]), 6)

    def test_subset_of_dataframe_range(self) -> None:
        # DataFrame has 2018-2022 but we request 2020-2022 -- only 3 points used
        df = make_df(
            ["2018", "2019", "2020", "2021", "2022"],
            [1.0, 2.0, 5.0, 6.0, 7.0],
        )
        result = trend(df, "2020", "2022")
        assert result["n_points"] == 3
        assert result["slope"] == 1.0

    def test_fewer_than_two_points_raises(self) -> None:
        # Only one point in range
        df = make_df(["2020"], [5.0])
        with pytest.raises(ValueError, match="2 data points"):
            trend(df, "2020", "2020")

    def test_missing_start_year_raises(self) -> None:
        df = make_df(["2021", "2022"], [6.0, 7.0])
        with pytest.raises(ValueError, match="2020"):
            trend(df, "2020", "2022")

    def test_missing_end_year_raises(self) -> None:
        df = make_df(["2020", "2021"], [5.0, 6.0])
        with pytest.raises(ValueError, match="2022"):
            trend(df, "2020", "2022")
