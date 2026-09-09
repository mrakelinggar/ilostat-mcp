"""Prompt handler for the labour market snapshot workflow."""

import time

import structlog

from ilostat_mcp import resources, telemetry

logger: structlog.BoundLogger = structlog.get_logger()
_tracer = telemetry.get_tracer(__name__)


def _resolve_country(inp: str, countries: list[dict[str, str]]) -> str:
    """
    Resolve a user-supplied country name or ISO-3 code to an ISO-3 code.

    Resolution order:
    1. Exact code match (case-insensitive).
    2. Exact name match (case-insensitive).
    3. Single partial name match (case-insensitive substring) → resolved.
    4. Multiple partial matches → ValueError (ambiguous).
    5. No match → ValueError.

    Parameters
    ----------
    inp       : User-supplied country name or code.
    countries : List of {code, name} dicts from get_cached_countries().

    Returns
    -------
    ISO-3 country code string.

    Raises
    ------
    ValueError for no match or multiple partial matches (ambiguous).
    """
    inp_lower = inp.lower()

    for c in countries:
        if c["code"].lower() == inp_lower:
            return c["code"]

    for c in countries:
        if c["name"].lower() == inp_lower:
            return c["code"]

    partials = [c for c in countries if inp_lower in c["name"].lower()]
    if len(partials) == 1:
        return partials[0]["code"]
    if len(partials) > 1:
        candidates = ", ".join(f"{c['code']} ({c['name']})" for c in partials)
        raise ValueError(f"'{inp}' is ambiguous — matches: {candidates}")

    raise ValueError(
        f"'{inp}' did not match any ILOSTAT country."
        " Use get_countries() to find valid codes."
    )


def labor_market_snapshot(countries: str) -> str:
    """
    Generate a labour market snapshot for 1–3 countries.

    `countries` is a comma-separated string of country names or ISO-3 codes.
    Validates count, resolves each to an ISO-3 code, then returns a prompt
    message that instructs the model to fetch and compare key labour market
    indicators for those countries.

    Raises ValueError for >3 countries, unknown names, or ambiguous names.
    """
    t0 = time.perf_counter()
    with _tracer.start_as_current_span("prompt.labor_market_snapshot") as span:
        span.set_attribute("countries", countries)
        try:
            inputs = [c.strip() for c in countries.split(",") if c.strip()]
            n = len(inputs)
            if n == 0:
                raise ValueError(
                    "countries must not be empty."
                    " Provide 1-3 country names or ISO-3 codes, comma-separated."
                )
            if n > 3:
                raise ValueError(
                    f"labor_market_snapshot accepts 1-3 countries, got {n}: {inputs}."
                )

            country_list = resources.get_cached_countries()
            errors: list[ValueError] = []
            resolved: list[str] = []

            for inp in inputs:
                try:
                    code = _resolve_country(inp, country_list)
                    resolved.append(code)
                except ValueError as e:
                    errors.append(e)

            if errors:
                raise errors[0]

            codes_str = ", ".join(resolved)
            flows_str = "\n".join(
                f"  - {f['theme']}: {f['dataflow_id']}"
                for f in resources.CANONICAL_FLOWS
            )

            result = (
                f"Fetch a labour market snapshot for: {codes_str}.\n\n"
                f"For each country, call get_time_series with the following"
                f" dataflow IDs"
                f" (use the most recent 2 years available):\n{flows_str}\n\n"
                f"For each dataflow and country:\n"
                f"1. Retrieve the data with get_time_series.\n"
                f"2. Compute year-over-year change for the most recent year"
                f" using get_yoy_change.\n"
                f"3. Note any methodology breaks in the _breaks field.\n\n"
                f"Present the results as a concise table comparing all countries."
                f" Use ISO codes ({codes_str}) as column headers."
                f" If data is unavailable for a country/indicator, show 'N/A'."
            )
            span.set_attribute("outcome", "success")
            logger.info(
                "prompt",
                tool="labor_market_snapshot",
                countries=countries,
                outcome="success",
                duration_ms=int((time.perf_counter() - t0) * 1000),
            )
            return result
        except (ValueError, RuntimeError) as exc:
            span.set_attribute("outcome", "error")
            span.set_attribute("error.message", str(exc))
            logger.info(
                "prompt",
                tool="labor_market_snapshot",
                countries=countries,
                outcome="error",
                duration_ms=int((time.perf_counter() - t0) * 1000),
            )
            raise
