"""
Live integration tests for sdmx_client.py.

These hit the real ILOSTAT API — no mocking. They verify that the client
handles the full range of expected inputs and edge cases correctly.

Run with: pytest tests/test_sdmx_client.py -v
Each test has a 60-second timeout (set globally in pyproject.toml).
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

import ilostat_mcp.sdmx_client as sdmx_client_mod
from ilostat_mcp.indicators import (
    AGE_TOTAL,
    CUR_DEFAULT,
    FLOWS,
)
from ilostat_mcp.sdmx_client import (
    get_catalogue,
    get_countries,
    get_time_series,
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
        df = get_time_series(UNE_FLOW, "DEU", "2015", "2023", dims={"AGE": AGE_TOTAL})
        assert isinstance(df, pd.DataFrame)
        assert not df.empty, "Expected data for DEU unemployment"

    def test_required_columns_present(self):
        """Output must contain the documented column set."""
        df = get_time_series(UNE_FLOW, "DEU", "2020", "2023", dims={"AGE": AGE_TOTAL})
        for col in ("time_period", "value", "obs_status", "source", "unit_measure"):
            assert col in df.columns, f"Missing column: {col}"

    def test_noise_columns_absent(self):
        """Constant and empty columns must be stripped from output."""
        df = get_time_series(UNE_FLOW, "DEU", "2020", "2023", dims={"AGE": AGE_TOTAL})
        for col in ("freq", "sex", "age", "cur", "geo", "note_classif"):
            assert col not in df.columns, f"Noise column still present: {col}"

    def test_freq_filter_annual_only(self):
        """Annual filter drops sub-annual rows; time_period must be 4-digit years."""
        df = get_time_series(
            UNE_FLOW, "DEU", "2015", "2023", freq="A", dims={"AGE": AGE_TOTAL}
        )
        # freq column is no longer returned, but the filter still runs —
        # verify by confirming every time_period is a 4-digit year string.
        assert all(tp.isdigit() and len(tp) == 4 for tp in df["time_period"]), (
            "Non-annual time_period leaked through annual filter"
        )

    def test_value_column_is_numeric(self):
        """Values should be numeric (float), not strings."""
        df = get_time_series(UNE_FLOW, "DEU", "2018", "2022", dims={"AGE": AGE_TOTAL})
        assert pd.api.types.is_numeric_dtype(df["value"]), "value column is not numeric"

    def test_wages_flow_cur_not_in_output(self):
        """cur is a per-call constant — it must be stripped from output rows."""
        df = get_time_series(WAG_FLOW, "DEU", "2015", "2022", dims={"CUR": CUR_DEFAULT})
        assert "cur" not in df.columns, "'cur' noise column should not appear in output"

    def test_no_data_country_returns_empty_dataframe(self):
        """PRK (North Korea) has no ILOSTAT data — must return empty DataFrame."""
        df = get_time_series(UNE_FLOW, "PRK", "2000", "2024", dims={"AGE": AGE_TOTAL})
        assert isinstance(df, pd.DataFrame)
        assert df.empty, "Expected empty DataFrame for PRK"

    def test_source_attribute_populated(self):
        """The SOURCE attribute should be non-null for DEU data."""
        df = get_time_series(UNE_FLOW, "DEU", "2015", "2022", dims={"AGE": AGE_TOTAL})
        assert "source" in df.columns
        # At least some rows should have a non-empty source
        assert df["source"].notna().any(), "All SOURCE values are null"

    def test_time_period_is_string(self):
        """time_period must hold plain strings, not Period or datetime objects."""
        df = get_time_series(UNE_FLOW, "DEU", "2018", "2022", dims={"AGE": AGE_TOTAL})
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
        df = get_time_series(WAG_FLOW, "THA", "2005", "2024", dims={"CUR": CUR_DEFAULT})
        assert not df.empty, "Expected wage data for THA"
        if "source" in df.columns:
            unique_sources = df["source"].dropna().unique()
            assert len(unique_sources) > 1, (
                "Expected multiple SOURCE values for THA wages (methodology breaks)"
            )


# ── get_catalogue ─────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def catalogue():
    """One live catalogue download shared by these tests (it takes 5-8 s)."""
    return get_catalogue()


class TestGetCatalogue:
    def test_contains_canonical_flow_with_title(self, catalogue):
        assert catalogue[UNE_FLOW].title, "Expected a non-empty title"

    def test_description_has_no_html(self, catalogue):
        description = catalogue[UNE_FLOW].description
        assert description, "Expected a description"
        assert "<" not in description, f"HTML left in description: {description[:80]}"

    def test_last_updated_is_iso_datetime(self, catalogue):
        """last_updated comes from the LAST_UPDATE annotation, as ISO 8601."""
        parsed = datetime.fromisoformat(str(catalogue[UNE_FLOW].last_updated))
        assert parsed.year >= 2024, f"Implausible last_updated: {parsed}"

    def test_is_modelled_flag_false_for_survey_flow(self, catalogue):
        assert catalogue[UNE_FLOW].is_modelled is False


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


# ── Annotation parsing (unit, no API) ─────────────────────────────────────────


def _fake_flow(name: str, **annotations: str) -> SimpleNamespace:
    """Stand-in sdmx1 dataflow; ILOSTAT puts the key in .type, value in .title."""
    return SimpleNamespace(
        name=name,
        annotations=[
            SimpleNamespace(id=None, type=t, title=v) for t, v in annotations.items()
        ],
    )


class TestAnnotations:
    def test_catalogue_follows_ilostat_order_annotation(self):
        catalogue = SimpleNamespace(
            dataflow={
                "DF_C": _fake_flow("Unemployment C", ORDER="300"),
                "DF_A": _fake_flow("Unemployment A", ORDER="100"),
                "DF_NONE": _fake_flow("Unemployment unranked"),
                "DF_B": _fake_flow("Unemployment B", ORDER="200"),
            }
        )
        with patch.object(sdmx_client_mod._client, "dataflow", return_value=catalogue):
            ids = list(get_catalogue())
        assert ids == ["DF_A", "DF_B", "DF_C", "DF_NONE"]

    def test_empty_catalogue_raises(self):
        empty = SimpleNamespace(dataflow={})
        with (
            patch.object(sdmx_client_mod._client, "dataflow", return_value=empty),
            pytest.raises(RuntimeError, match="empty dataflow list"),
        ):
            get_catalogue()

    def test_last_update_parsed_day_first(self):
        flow = _fake_flow("x", LAST_UPDATE="25/10/2026 21:50:07")
        assert sdmx_client_mod._last_updated(flow) == "2026-10-25T21:50:07"

    def test_missing_last_update_is_none(self):
        assert sdmx_client_mod._last_updated(_fake_flow("x")) is None

    def test_unparseable_last_update_is_none(self):
        flow = _fake_flow("x", LAST_UPDATE="sometime last week")
        assert sdmx_client_mod._last_updated(flow) is None
