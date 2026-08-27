"""
Test session setup for ilostat-mcp.

Pre-warms the sdmx1 DSD cache for the canonical flows before any test runs.

Why: sdmx1 fetches the full DSD (with ?references=all) the first time you use
a dict key in client.data(). ILOSTAT's endpoint requires a Cloudflare challenge-
response, which cloudscraper handles automatically but takes 30–90 seconds per
flow on first access. By triggering this once at session start (no pytest-timeout
applies to session fixtures), all individual tests can use cached DSDs and complete
well within the 60-second per-test limit.
"""

import pytest

from ilostat_mcp.indicators import AGE_TOTAL, CUR_DEFAULT, FLOWS, SEX_TOTAL
from ilostat_mcp.sdmx_client import get_time_series


@pytest.fixture(scope="session", autouse=True)
def prewarm_dsd_cache():
    """Fetch DSD for each canonical flow once so tests use the in-memory cache."""
    # One small request per flow is enough to populate the DSD cache.
    # Failures here are non-fatal — individual tests will handle API errors.
    prewarm_calls = [
        (FLOWS["unemployment_rate"], "DEU", "2023", "2023",
         dict(age=AGE_TOTAL)),
        (FLOWS["wages"], "DEU", "2023", "2023",
         dict(cur=CUR_DEFAULT)),
    ]
    for flow_id, country, start, end, kwargs in prewarm_calls:
        try:
            get_time_series(flow_id, country, start, end, **kwargs)
        except Exception:
            pass  # Cache pre-warm is best-effort; tests fail if API is down
