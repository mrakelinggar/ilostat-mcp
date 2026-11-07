"""Tool handlers for indicator and country lookup, served from cached catalogues."""

from ilostat_mcp import resources

MAX_SEARCH_RESULTS = 20


def search_indicators(keyword: str) -> list[dict[str, object]]:
    """
    Search ILOSTAT dataflows by keyword. Returns up to 20 matches with their
    dataflow ID, title, and whether the series is an ILO modelled estimate
    (is_modelled: true) or survey data (is_modelled: false). Use the dataflow
    ID in subsequent calls. Prefer survey data (is_modelled: false).
    """
    keyword_lower = keyword.lower()
    matches = [
        flow
        for flow in resources.get_catalogue().values()
        if keyword_lower in flow.title.lower()
    ]
    return [
        {"id": flow.id, "title": flow.title, "is_modelled": flow.is_modelled}
        for flow in matches[:MAX_SEARCH_RESULTS]
    ]


def get_countries() -> list[dict[str, str]]:
    """
    List all valid country codes from ILOSTAT's CL_AREA codelist.
    Returns [{code, name}]. Use these codes in get_time_series.
    """
    return resources.get_cached_countries()


def get_indicator_metadata(dataflow_id: str) -> dict[str, object]:
    """
    Return metadata for a dataflow: title, plain-English description,
    last_updated (when ILOSTAT last refreshed the data, ISO 8601), and
    whether it is a modelled estimate.
    Returns an empty dict if the dataflow ID does not exist.
    """
    flow = resources.get_catalogue().get(dataflow_id)
    if flow is None:
        return {}
    return {
        "id": flow.id,
        "title": flow.title,
        "description": flow.description,
        "is_modelled": flow.is_modelled,
        "last_updated": flow.last_updated,
    }
