"""
Break detection tests — verified against real ILOSTAT data.

Break countries and expected years (confirmed against live data, not just Phase 0b):
- NGA (DF_UNE_3EAP_SEX_AGE_DSB_RT): break at 2019 (HS -> HIES).
  Flow uses youth age bands — AGE_YTHADULT_YGE15 returns no data.
  Series starts at 2011 so no pre-2011 comparison exists.
- THA wages (DF_EAR_CMTA_SEX_CUR_NB): break at 2014 (2013=HIES, 2014+=LFS).
  One SOURCE transition → one break year.
- DEU unemployment: no breaks (LFS throughout).
"""

import pandas as pd
import pytest

from ilostat_mcp.breaks import break_years_in_range, detect_breaks
from ilostat_mcp.indicators import CUR_DEFAULT
from ilostat_mcp.sdmx_client import get_time_series

_NGA_FLOW = "DF_UNE_3EAP_SEX_AGE_DSB_RT"
_THA_WAGE_FLOW = "DF_EAR_CMTA_SEX_CUR_NB"
_UNE_FLOW = "DF_UNE_DEAP_SEX_AGE_RT"


# ── Unit tests (no API calls) ─────────────────────────────────────────────────


class TestDetectBreaksUnit:
    def test_empty_dataframe_returns_empty(self) -> None:
        assert detect_breaks(pd.DataFrame()) == []

    def test_missing_source_column_returns_empty(self) -> None:
        df = pd.DataFrame({"time_period": ["2020", "2021"], "value": [5.0, 5.1]})
        assert detect_breaks(df) == []

    def test_single_row_returns_empty(self) -> None:
        df = pd.DataFrame({"time_period": ["2020"], "source": ["LFS"], "value": [5.0]})
        assert detect_breaks(df) == []

    def test_same_source_throughout_returns_empty(self) -> None:
        df = pd.DataFrame(
            {
                "time_period": ["2020", "2021", "2022"],
                "source": ["LFS", "LFS", "LFS"],
                "value": [5.0, 5.1, 5.2],
            }
        )
        assert detect_breaks(df) == []

    def test_single_source_change_detected(self) -> None:
        df = pd.DataFrame(
            {
                "time_period": ["2020", "2021", "2022"],
                "source": ["LFS", "LFS", "HIES"],
                "value": [5.0, 5.1, 4.9],
            }
        )
        result = detect_breaks(df)
        assert len(result) == 1
        assert result[0]["year"] == "2022"
        assert result[0]["source_before"] == "LFS"
        assert result[0]["source_after"] == "HIES"

    def test_multiple_source_changes_all_detected(self) -> None:
        df = pd.DataFrame(
            {
                "time_period": ["2019", "2020", "2021", "2022"],
                "source": ["LFS", "HIES", "LFS", "LFS"],
                "value": [5.0, 4.8, 5.1, 5.2],
            }
        )
        result = detect_breaks(df)
        assert len(result) == 2
        assert result[0]["year"] == "2020"
        assert result[1]["year"] == "2021"

    def test_break_attributed_to_later_year(self) -> None:
        # 2013 is LFS, 2014 is HIES — break is at 2014 (first year of new source)
        df = pd.DataFrame(
            {
                "time_period": ["2013", "2014"],
                "source": ["LFS", "HIES"],
                "value": [10.0, 9.8],
            }
        )
        result = detect_breaks(df)
        assert result[0]["year"] == "2014"

    def test_nan_source_both_sides_skipped(self) -> None:
        df = pd.DataFrame(
            {
                "time_period": ["2020", "2021"],
                "source": [None, None],
                "value": [5.0, 5.1],
            }
        )
        assert detect_breaks(df) == []

    def test_unsorted_input_sorted_before_detection(self) -> None:
        # Rows in reverse order — should still detect the break at 2021
        df = pd.DataFrame(
            {
                "time_period": ["2022", "2021", "2020"],
                "source": ["LFS", "HIES", "LFS"],
                "value": [5.2, 4.9, 5.0],
            }
        )
        result = detect_breaks(df)
        assert len(result) == 2
        assert result[0]["year"] == "2021"
        assert result[1]["year"] == "2022"


class TestBreakYearsInRange:
    def test_all_breaks_in_range(self) -> None:
        b = [{"year": "2013"}, {"year": "2016"}]
        assert break_years_in_range(b, "2010", "2020") == ["2013", "2016"]  # type: ignore[arg-type]

    def test_break_outside_range_excluded(self) -> None:
        b = [{"year": "2009"}, {"year": "2013"}, {"year": "2025"}]
        assert break_years_in_range(b, "2010", "2020") == ["2013"]  # type: ignore[arg-type]

    def test_boundary_years_included(self) -> None:
        b = [{"year": "2010"}, {"year": "2020"}]
        assert break_years_in_range(b, "2010", "2020") == ["2010", "2020"]  # type: ignore[arg-type]

    def test_empty_breaks_returns_empty(self) -> None:
        assert break_years_in_range([], "2010", "2020") == []


# ── Integration tests (live ILOSTAT API) ─────────────────────────────────────


class TestDetectBreaksLive:
    @pytest.mark.timeout(30)
    def test_nga_unemployment_break_at_2019(self) -> None:
        # NGA series starts at 2011 (HS), jumps to 2019 (HIES) — one break at 2019.
        # No age filter: this flow uses youth bands, not AGE_YTHADULT_YGE15.
        df = get_time_series(_NGA_FLOW, "NGA", "2005", "2022")
        result = detect_breaks(df)
        years = [b["year"] for b in result]
        assert "2019" in years, f"Expected break at 2019; got {years}"

    @pytest.mark.timeout(30)
    def test_tha_wage_break_at_2014(self) -> None:
        # 2013=HIES, 2014+=LFS: one SOURCE transition → break attributed to 2014.
        df = get_time_series(_THA_WAGE_FLOW, "THA", "2010", "2020", cur=CUR_DEFAULT)
        result = detect_breaks(df)
        years = [b["year"] for b in result]
        assert "2014" in years, f"Expected break at 2014; got {years}"

    @pytest.mark.timeout(30)
    def test_deu_unemployment_no_breaks(self) -> None:
        from ilostat_mcp.indicators import AGE_TOTAL

        df = get_time_series(_UNE_FLOW, "DEU", "2010", "2023", age=AGE_TOTAL)
        result = detect_breaks(df)
        assert result == [], f"Expected no breaks for DEU; got {result}"

    @pytest.mark.timeout(30)
    def test_break_dict_has_required_keys(self) -> None:
        df = get_time_series(_THA_WAGE_FLOW, "THA", "2010", "2020", cur=CUR_DEFAULT)
        result = detect_breaks(df)
        assert len(result) > 0
        for b in result:
            assert {"year", "source_before", "source_after"} <= set(b)


class TestGetTimeSeriesBreakField:
    """Verify the _breaks field is present and correct in the server tool output."""

    @pytest.mark.timeout(30)
    def test_break_field_present_on_clean_series(self) -> None:
        from ilostat_mcp.server import get_time_series as tool_get_time_series

        result = tool_get_time_series(_UNE_FLOW, "DEU", "2018", "2023")
        assert "data" in result
        assert "_breaks" in result
        assert result["_breaks"] == []

    @pytest.mark.timeout(30)
    def test_break_field_populated_for_break_country(self) -> None:
        from ilostat_mcp.server import get_time_series as tool_get_time_series

        # THA wages: break at 2014 (HIES → LFS)
        result = tool_get_time_series(_THA_WAGE_FLOW, "THA", "2010", "2020")
        assert "_breaks" in result
        years = [b["year"] for b in result["_breaks"]]  # type: ignore[union-attr]
        assert "2014" in years

    @pytest.mark.timeout(30)
    def test_no_data_returns_empty_data_and_breaks(self) -> None:
        from ilostat_mcp.server import get_time_series as tool_get_time_series

        result = tool_get_time_series(_UNE_FLOW, "PRK", "2010", "2023")
        assert result == {"data": [], "_breaks": []}
