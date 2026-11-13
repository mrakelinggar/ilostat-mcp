"""
Break detection tests — verified against real ILOSTAT data.

Break countries and expected years (confirmed against live data, not just Phase 0b):
- NGA (DF_UNE_3EAP_SEX_AGE_DSB_RT): break at 2019 (HS -> HIES).
  Youth-only flow (no adult total); queried with age_group="youth".
  Series starts at 2011 so no pre-2011 comparison exists.
- AUS unemployment (DF_UNE_DEAP_SEX_AGE_RT): ILOSTAT flags a break at 2018
  (obs_status "B") with the same source name either side — a survey redesign
  the old source-only check missed (Phase 5 finding).
- THA wages (DF_EAR_CMTA_SEX_CUR_NB): break at 2014 (2013=HIES, 2014+=LFS).
  One SOURCE transition → one break year.
- DEU unemployment: no breaks (LFS throughout).
"""

import pandas as pd
import pytest

from ilostat_mcp.breaks import (
    REASON_ILOSTAT_FLAG,
    REASON_SOURCE_CHANGE,
    break_warning,
    detect_breaks,
)
from ilostat_mcp.indicators import CUR_DEFAULT
from ilostat_mcp.sdmx_client import get_time_series
from ilostat_mcp.tools.series import fetch_series

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


class TestDetectBreaksSignals:
    """ILOSTAT's "B" flag and source changes each record a break (Phase 5)."""

    def test_ilostat_flag_with_same_source_detected(self) -> None:
        # Survey redesign that kept its name: only the "B" flag shows it.
        df = pd.DataFrame(
            {
                "time_period": ["2017", "2018"],
                "source": ["LFS", "LFS"],
                "obs_status": ["", "B"],
            }
        )
        assert detect_breaks(df) == [
            {
                "year": "2018",
                "source_before": "LFS",
                "source_after": "LFS",
                "reasons": [REASON_ILOSTAT_FLAG],
            }
        ]

    def test_source_change_without_flag_has_source_reason_only(self) -> None:
        df = pd.DataFrame(
            {
                "time_period": ["2012", "2013"],
                "source": ["PC", "LFS"],
                "obs_status": ["", ""],
            }
        )
        assert detect_breaks(df)[0]["reasons"] == [REASON_SOURCE_CHANGE]

    def test_flag_and_source_change_give_both_reasons(self) -> None:
        df = pd.DataFrame(
            {
                "time_period": ["2012", "2013"],
                "source": ["PC", "LFS"],
                "obs_status": ["", "B"],
            }
        )
        result = detect_breaks(df)
        assert len(result) == 1
        assert result[0]["reasons"] == [REASON_ILOSTAT_FLAG, REASON_SOURCE_CHANGE]

    def test_flag_on_first_year_has_no_source_before(self) -> None:
        df = pd.DataFrame(
            {
                "time_period": ["2011", "2012"],
                "source": ["HS", "HS"],
                "obs_status": ["B", ""],
            }
        )
        result = detect_breaks(df)
        assert result[0]["year"] == "2011"
        assert result[0]["source_before"] is None

    def test_works_without_source_column(self) -> None:
        df = pd.DataFrame({"time_period": ["2020", "2021"], "obs_status": ["", "B"]})
        assert [b["year"] for b in detect_breaks(df)] == ["2021"]

    def test_blank_source_year_bridged_to_last_known(self) -> None:
        # LFS, blank, HIES: one real change (at 2022), not two false ones.
        df = pd.DataFrame(
            {"time_period": ["2020", "2021", "2022"], "source": ["LFS", None, "HIES"]}
        )
        result = detect_breaks(df)
        assert len(result) == 1
        assert result[0]["year"] == "2022"
        assert result[0]["source_before"] == "LFS"

    def test_blank_source_between_same_sources_is_not_a_break(self) -> None:
        df = pd.DataFrame(
            {"time_period": ["2020", "2021", "2022"], "source": ["LFS", "", "LFS"]}
        )
        assert detect_breaks(df) == []


_SAMPLE_BREAKS: list[dict[str, object]] = [
    {
        "year": "2013",
        "source_before": "PC",
        "source_after": "LFS",
        "reasons": [REASON_SOURCE_CHANGE],
    },
    {
        "year": "2018",
        "source_before": "LFS",
        "source_after": "LFS",
        "reasons": [REASON_ILOSTAT_FLAG],
    },
]


class TestBreakWarning:
    def test_no_break_in_range_returns_none(self) -> None:
        assert break_warning(_SAMPLE_BREAKS, "2019", "2022") is None

    def test_empty_breaks_returns_none(self) -> None:
        assert break_warning([], "2010", "2020") is None

    def test_single_break_names_year_and_source_change(self) -> None:
        warning = break_warning(_SAMPLE_BREAKS, "2010", "2015")
        assert warning is not None
        assert "Methodology break within 2010-2015 at 2013" in warning
        assert "source changed from 'PC' to 'LFS'" in warning

    def test_flag_only_break_says_ilostat_flagged_it(self) -> None:
        warning = break_warning(_SAMPLE_BREAKS, "2016", "2020")
        assert warning is not None
        assert "2018 (ILOSTAT flags a break in series)" in warning

    def test_boundary_years_included(self) -> None:
        warning = break_warning(_SAMPLE_BREAKS, "2013", "2018")
        assert warning is not None
        assert "Methodology breaks" in warning
        assert "2013" in warning and "2018" in warning


# ── Integration tests (live ILOSTAT API) ─────────────────────────────────────


class TestDetectBreaksLive:
    @pytest.mark.timeout(30)
    def test_nga_unemployment_break_at_2019(self) -> None:
        # NGA series starts at 2011 (HS), jumps to 2019 (HIES) — one break at 2019.
        # Youth-only flow, so it is queried with age_group="youth".
        df = fetch_series(_NGA_FLOW, "NGA", "2011", "2022", "youth")
        result = detect_breaks(df)
        years = [b["year"] for b in result]
        assert "2019" in years, f"Expected break at 2019; got {years}"

    @pytest.mark.timeout(30)
    def test_tha_wage_break_at_2014(self) -> None:
        # 2013=HIES, 2014+=LFS: one SOURCE transition → break attributed to 2014.
        df = get_time_series(
            _THA_WAGE_FLOW, "THA", "2010", "2020", dims={"CUR": CUR_DEFAULT}
        )
        result = detect_breaks(df)
        years = [b["year"] for b in result]
        assert "2014" in years, f"Expected break at 2014; got {years}"

    @pytest.mark.timeout(30)
    def test_aus_ilostat_flagged_break_at_2018_detected(self) -> None:
        # Same source name either side; only ILOSTAT's "B" flag reveals it.
        df = fetch_series(_UNE_FLOW, "AUS", "2015", "2020", "total")
        flagged = [b for b in detect_breaks(df) if b["year"] == "2018"]
        assert flagged, "Expected ILOSTAT-flagged break at 2018 for AUS"
        assert REASON_ILOSTAT_FLAG in flagged[0]["reasons"]  # type: ignore[operator]
        assert flagged[0]["source_before"] == flagged[0]["source_after"]

    @pytest.mark.timeout(30)
    def test_deu_unemployment_no_breaks(self) -> None:
        from ilostat_mcp.indicators import AGE_TOTAL

        df = get_time_series(_UNE_FLOW, "DEU", "2010", "2023", dims={"AGE": AGE_TOTAL})
        result = detect_breaks(df)
        assert result == [], f"Expected no breaks for DEU; got {result}"

    @pytest.mark.timeout(30)
    def test_break_dict_has_required_keys(self) -> None:
        df = get_time_series(
            _THA_WAGE_FLOW, "THA", "2010", "2020", dims={"CUR": CUR_DEFAULT}
        )
        result = detect_breaks(df)
        assert len(result) > 0
        for b in result:
            assert {"year", "source_before", "source_after", "reasons"} <= set(b)


class TestGetTimeSeriesBreakField:
    """Verify the _breaks field is present and correct in the server tool output."""

    @pytest.mark.timeout(30)
    def test_break_field_present_on_clean_series(self) -> None:
        from ilostat_mcp.server import get_time_series as tool_get_time_series

        result = tool_get_time_series(_UNE_FLOW, "DEU", "2018", "2023")
        assert "_breaks" in result[0]
        assert result[0]["_breaks"] == []

    @pytest.mark.timeout(30)
    def test_break_field_populated_for_break_country(self) -> None:
        from ilostat_mcp.server import get_time_series as tool_get_time_series

        # THA wages: break at 2014 (HIES → LFS)
        result = tool_get_time_series(_THA_WAGE_FLOW, "THA", "2010", "2020")
        assert "_breaks" in result[0]
        years = [b["year"] for b in result[0]["_breaks"]]  # type: ignore[index]
        assert "2014" in years

    @pytest.mark.timeout(30)
    def test_no_data_returns_metadata_only(self) -> None:
        from ilostat_mcp.server import get_time_series as tool_get_time_series

        result = tool_get_time_series(_UNE_FLOW, "PRK", "2010", "2023")
        assert len(result) == 1
        meta = result[0]
        assert meta["_breaks"] == []
        assert meta["_missing_years"] == []
        assert "PRK" in str(meta["_no_data_reason"])
