"""
Cache tests — no network. TTLCache is driven by a fake clock; the series
cache is tested with sdmx_client.get_time_series mocked, so the number of
"ILOSTAT calls" can be counted exactly.
"""

from contextlib import AbstractContextManager
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from ilostat_mcp import resources
from ilostat_mcp.cache import SECONDS_PER_DAY, SECONDS_PER_HOUR, TTLCache
from ilostat_mcp.sdmx_client import FlowInfo
from ilostat_mcp.tools import series

_FLOW = "DF_UNE_DEAP_SEX_AGE_RT"
_HISTORY = pd.DataFrame(
    {
        "time_period": ["2018", "2019", "2020", "2021"],
        "value": [3.4, 3.1, 3.6, 3.6],
        "obs_status": ["", "", "", ""],
        "source": ["LFS"] * 4,
    }
)


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _counting(value: object) -> tuple[list[int], object]:
    """Return (call counter, fetch function returning value)."""
    calls = [0]

    def fetch() -> object:
        calls[0] += 1
        return value

    return calls, fetch


# ── TTLCache ──────────────────────────────────────────────────────────────────


class TestTTLCache:
    def test_second_lookup_is_a_hit(self) -> None:
        cache: TTLCache[str, object] = TTLCache(ttl_seconds=10, max_entries=5)
        calls, fetch = _counting("v")
        assert cache.get_or_fetch("k", fetch) == "v"
        assert cache.get_or_fetch("k", fetch) == "v"
        assert calls[0] == 1

    def test_entry_expires_after_ttl(self) -> None:
        clock = _FakeClock()
        cache: TTLCache[str, object] = TTLCache(
            ttl_seconds=10, max_entries=5, clock=clock
        )
        calls, fetch = _counting("v")
        cache.get_or_fetch("k", fetch)
        clock.now = 9.9
        cache.get_or_fetch("k", fetch)
        assert calls[0] == 1, "Still fresh before the TTL"
        clock.now = 10.0
        cache.get_or_fetch("k", fetch)
        assert calls[0] == 2, "Refetched once the TTL passed"

    def test_ttl_for_overrides_default(self) -> None:
        clock = _FakeClock()
        cache: TTLCache[str, str] = TTLCache(
            ttl_seconds=100, max_entries=5, clock=clock
        )
        cache.get_or_fetch("k", lambda: "", ttl_for=lambda v: 1 if not v else 100)
        clock.now = 1.0
        assert cache.peek("k") is None

    def test_least_recently_used_entry_evicted_first(self) -> None:
        cache: TTLCache[str, str] = TTLCache(ttl_seconds=10, max_entries=2)
        cache.get_or_fetch("a", lambda: "A")
        cache.get_or_fetch("b", lambda: "B")
        cache.get_or_fetch("a", lambda: "A")  # "a" is now most recently used
        cache.get_or_fetch("c", lambda: "C")  # over the cap: drops "b"
        assert len(cache) == 2
        assert cache.peek("a") == "A"
        assert cache.peek("b") is None
        assert cache.peek("c") == "C"

    def test_failed_fetch_is_not_cached(self) -> None:
        cache: TTLCache[str, str] = TTLCache(ttl_seconds=10, max_entries=5)

        def fail() -> str:
            raise RuntimeError("ILOSTAT API request timed out")

        with pytest.raises(RuntimeError, match="timed out"):
            cache.get_or_fetch("k", fail)
        assert len(cache) == 0
        assert cache.get_or_fetch("k", lambda: "ok") == "ok"

    def test_peek_never_fetches(self) -> None:
        cache: TTLCache[str, str] = TTLCache(ttl_seconds=10, max_entries=5)
        assert cache.peek("missing") is None
        assert len(cache) == 0


# ── Series cache ──────────────────────────────────────────────────────────────


def _mock_ilostat(returning: pd.DataFrame) -> AbstractContextManager[MagicMock]:
    """Stand in for ILOSTAT; the returned mock counts the calls."""
    return patch("ilostat_mcp.sdmx_client.get_time_series", return_value=returning)


class TestSeriesCache:
    def test_different_ranges_share_one_fetch(self) -> None:
        with _mock_ilostat(_HISTORY) as api:
            a = series.fetch_series(_FLOW, "DEU", "2018", "2019", "total")
            b = series.fetch_series(_FLOW, "DEU", "2020", "2021", "total")
        assert api.call_count == 1
        assert list(a["time_period"]) == ["2018", "2019"]
        assert list(b["time_period"]) == ["2020", "2021"]

    def test_full_history_is_requested(self) -> None:
        with _mock_ilostat(_HISTORY) as api:
            series.fetch_series(_FLOW, "DEU", "2019", "2020", "total")
        _flow, _country, start, _end = api.call_args.args
        assert start == "1983", "Fetch should start at the flow's min_year"

    def test_different_country_or_age_group_fetches_again(self) -> None:
        with _mock_ilostat(_HISTORY) as api:
            series.fetch_series(_FLOW, "DEU", "2018", "2021", "total")
            series.fetch_series(_FLOW, "FRA", "2018", "2021", "total")
            series.fetch_series(_FLOW, "DEU", "2018", "2021", "youth")
        assert api.call_count == 3

    def test_new_ilostat_release_bypasses_old_copy(self) -> None:
        # Once the catalogue shows a newer LAST_UPDATE, the key changes.
        def catalogue(last_updated: str) -> dict[str, FlowInfo]:
            return {
                _FLOW: FlowInfo(
                    id=_FLOW,
                    title="Unemployment",
                    description="",
                    is_modelled=False,
                    last_updated=last_updated,
                )
            }

        with _mock_ilostat(_HISTORY) as api:
            with patch.object(
                resources._catalogue, "peek", return_value=catalogue("2026-10-01")
            ):
                series.fetch_series(_FLOW, "DEU", "2018", "2021", "total")
                series.fetch_series(_FLOW, "DEU", "2018", "2021", "total")
            with patch.object(
                resources._catalogue, "peek", return_value=catalogue("2026-11-01")
            ):
                series.fetch_series(_FLOW, "DEU", "2018", "2021", "total")
        assert api.call_count == 2

    def test_no_data_cached_for_an_hour_only(self) -> None:
        assert series._series_ttl(pd.DataFrame()) == SECONDS_PER_HOUR
        assert series._series_ttl(_HISTORY) == SECONDS_PER_DAY

    def test_range_with_no_rows_returns_empty(self) -> None:
        with _mock_ilostat(_HISTORY):
            result = series.fetch_series(_FLOW, "DEU", "2000", "2005", "total")
        assert result.empty

    def test_failed_fetch_is_retried_next_call(self) -> None:
        with patch(
            "ilostat_mcp.sdmx_client.get_time_series",
            side_effect=[RuntimeError("ILOSTAT API request timed out"), _HISTORY],
        ) as api:
            with pytest.raises(RuntimeError, match="timed out"):
                series.fetch_series(_FLOW, "DEU", "2018", "2021", "total")
            result = series.fetch_series(_FLOW, "DEU", "2018", "2021", "total")
        assert api.call_count == 2
        assert len(result) == 4


class TestKnownLastUpdated:
    def test_none_when_catalogue_not_cached(self) -> None:
        with patch.object(resources._catalogue, "peek", return_value=None):
            assert resources.known_last_updated(_FLOW) is None

    def test_never_downloads_catalogue(self) -> None:
        with (
            patch.object(resources._catalogue, "peek", return_value=None),
            patch("ilostat_mcp.sdmx_client.get_catalogue") as download,
        ):
            resources.known_last_updated(_FLOW)
        download.assert_not_called()
