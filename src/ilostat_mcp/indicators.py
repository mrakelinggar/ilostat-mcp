"""
Registry mapping theme names to canonical ILOSTAT dataflow IDs.

Adding a new theme = adding entries here only — nothing else changes.
"""

# Canonical flows for the four v1 labor market themes.
# Each value is the ILOSTAT SDMX dataflow ID that best covers the theme
# for a general (all-employee, economy-wide, total sex, adult age) query.
FLOWS: dict[str, str] = {
    "unemployment_rate": "DF_UNE_DEAP_SEX_AGE_RT",
    "employment_to_pop": "DF_EMP_DWAP_SEX_AGE_RT",
    "wages": "DF_EAR_EMTA_SEX_CUR_NB",
    "lfpr": "DF_EAP_DWAP_SEX_AGE_RT",
}

# Which dimensions each flow uses, plus any extra SDMX key values required.
#
# Each entry: {"dim": "age"|"cur"|None, **extra_sdmx_key_values}
# - "dim": the primary variable dimension — "age" injects AGE, "cur" injects CUR,
#   None means no extra dimension key is injected (e.g. flows whose AGE codes
#   don't include the standard AGE_YTHADULT_YGE15 total).
# - Extra keys (e.g. "GEO"): included verbatim in the SDMX key dict every call.
#   Required when a flow has an additional mandatory dimension beyond REF_AREA/SEX.
#
# Discovery result (Phase 2b Task 0): DF_UNE_3EAP_SEX_AGE_GEO_RT returns
# national + rural + urban rows when GEO is omitted. GEO_COV_NAT = national total.
#
# Discovery result (Phase 4.5): DF_UNE_3EAP_SEX_AGE_DSB_RT does not contain
# AGE_YTHADULT_YGE15 — passing it gives 404. dim=None so no AGE key is injected.
FLOW_DIMS: dict[str, dict[str, str | None]] = {
    # Canonical v1 flows
    "DF_UNE_DEAP_SEX_AGE_RT": {"dim": "age"},
    "DF_EMP_DWAP_SEX_AGE_RT": {"dim": "age"},
    "DF_EAR_EMTA_SEX_CUR_NB": {"dim": "cur"},
    "DF_EAP_DWAP_SEX_AGE_RT": {"dim": "age"},
    # Phase 2b additions — benchmark flows not in the canonical set
    # dim=None: AGE_YTHADULT_YGE15 not in this flow's AGE codelist (Phase 4.5)
    "DF_UNE_3EAP_SEX_AGE_DSB_RT": {"dim": None},  # Nigeria unemployment (q003, q018)
    # GEO_COV_NAT = national total; omitting GEO returns national+rural+urban mixed
    "DF_UNE_3EAP_SEX_AGE_GEO_RT": {  # ZAF youth unemployment (q016)
        "dim": "age",
        "GEO": "GEO_COV_NAT",
    },
    "DF_EMP_2WAP_SEX_AGE_RT": {"dim": "age"},  # modelled emp-to-pop (q013)
    "DF_EAR_CMTA_SEX_CUR_NB": {"dim": "cur"},  # care-sector wages (q004)
}

# Earliest year any country has data in each flow, from Phase 4.5 API discovery.
# Used to validate year inputs before making API calls.
# Upper bound is always the current calendar year (computed at runtime in server.py).
FLOW_MIN_YEARS: dict[str, int] = {
    "DF_UNE_DEAP_SEX_AGE_RT": 1983,
    "DF_EMP_DWAP_SEX_AGE_RT": 1983,
    "DF_EAR_EMTA_SEX_CUR_NB": 2000,
    "DF_EAP_DWAP_SEX_AGE_RT": 1983,
    "DF_UNE_3EAP_SEX_AGE_DSB_RT": 2011,
    "DF_UNE_3EAP_SEX_AGE_GEO_RT": 2008,
    "DF_EMP_2WAP_SEX_AGE_RT": 1991,
    "DF_EAR_CMTA_SEX_CUR_NB": 2000,  # ZAF goes back to 2000; THA starts 2013
}

# Default dimension values
AGE_TOTAL = "AGE_YTHADULT_YGE15"  # adults 15+
AGE_YOUTH = "AGE_YTHBANDS_Y15-29"  # youth 15-29 (ILO standard youth band)
SEX_TOTAL = "SEX_T"  # total (all sexes)
CUR_DEFAULT = "CUR_TYPE_LCU"  # local currency units

# Keyword fragments that identify modelled/estimated flows (ILO modelled estimates).
# A flow is "modelled" if its ID contains any of these strings.
# "2WAP" covers DF_EMP_2WAP_* (modelled employment-to-population series).
_MODELLED_MARKERS = ("_ILO_MODELLED", "_MOD_", "2WAP")


def is_modelled(flow_id: str) -> bool:
    """Return True if this flow is an ILO modelled estimate rather than survey data."""
    return any(marker in flow_id for marker in _MODELLED_MARKERS)


# ISO 4217 currency codes for countries most likely to appear in benchmark queries.
# Coverage prioritises countries confirmed to have ILOSTAT data (Phase 0 finding).
# Not exhaustive — extend here when new benchmark countries are added.
COUNTRY_CURRENCY: dict[str, str] = {
    # G20 members
    "ARG": "ARS",
    "AUS": "AUD",
    "BRA": "BRL",
    "CAN": "CAD",
    "CHN": "CNY",
    "DEU": "EUR",
    "FRA": "EUR",
    "GBR": "GBP",
    "IDN": "IDR",
    "IND": "INR",
    "ITA": "EUR",
    "JPN": "JPY",
    "KOR": "KRW",
    "MEX": "MXN",
    "RUS": "RUB",
    "SAU": "SAR",
    "TUR": "TRY",
    "USA": "USD",
    "ZAF": "ZAR",
    # Other common benchmark countries
    "BGD": "BDT",
    "CHL": "CLP",
    "COL": "COP",
    "ECU": "USD",
    "EGY": "EGP",
    "ETH": "ETB",
    "GHA": "GHS",
    "KEN": "KES",
    "MAR": "MAD",
    "MYS": "MYR",
    "NGA": "NGN",
    "PAK": "PKR",
    "PHL": "PHP",
    "POL": "PLN",
    "SWE": "SEK",
    "THA": "THB",
    "TZA": "TZS",
    "UGA": "UGX",
    "UKR": "UAH",
    "VEN": "VES",
    "VNM": "VND",
}
