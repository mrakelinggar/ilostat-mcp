"""
Registry of the ILOSTAT dataflows this server accepts, and how to query each.

Adding a flow = adding one FlowSpec entry to FLOW_SPECS — nothing else changes.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal

# ── SDMX dimension values ─────────────────────────────────────────────────────

AGE_TOTAL = "AGE_YTHADULT_YGE15"  # adults 15+
AGE_YOUTH = "AGE_YTHBANDS_Y15-29"  # youth 15-29 (ILO standard youth band)
SEX_TOTAL = "SEX_T"  # total (all sexes)
CUR_DEFAULT = "CUR_TYPE_LCU"  # local currency units
GEO_NATIONAL = "GEO_COV_NAT"  # national total (vs. rural / urban)
DSB_TOTAL = "DSB_STATUS_TOTAL"  # total (with and without disability)

# Maps the age_group tool parameter to the SDMX AGE code.
AGE_GROUP_CODES: Mapping[str, str] = MappingProxyType(
    {
        "total": AGE_TOTAL,
        "youth": AGE_YOUTH,
    }
)

# The flow's main variable dimension: "age" means the caller's age_group picks
# the AGE code; "cur" means wages, always queried in local currency.
VariableDim = Literal["age", "cur"]


@dataclass(frozen=True)
class FlowSpec:
    """
    How to query one ILOSTAT dataflow.

    Attributes
    ----------
    min_year  : earliest year any country has data (Phase 4.5 discovery); used
                to reject impossible years before calling the API.
    dim       : the flow's main variable dimension (see VariableDim).
    fixed_key : extra SDMX key values sent on every call. Needed when a flow
                has a breakdown that would otherwise return several rows per
                year (e.g. rural/urban, disability status).
    theme     : canonical v1 theme name, for the four headline flows only.
    title     : official ILOSTAT title, for the four headline flows only.
    """

    min_year: int
    dim: VariableDim
    fixed_key: Mapping[str, str] = field(default_factory=dict)
    theme: str | None = None
    title: str | None = None

    def sdmx_key(self, age_group: str) -> dict[str, str]:
        """
        Return the dimension values to send for this flow, beyond REF_AREA/SEX.

        age_group must be a key of AGE_GROUP_CODES; it is ignored for wage
        flows (dim == "cur").
        """
        key = dict(self.fixed_key)
        if self.dim == "age":
            key["AGE"] = AGE_GROUP_CODES[age_group]
        else:
            key["CUR"] = CUR_DEFAULT
        return key


FLOW_SPECS: Mapping[str, FlowSpec] = MappingProxyType(
    {
        # ── Canonical v1 flows ────────────────────────────────────────────────
        "DF_UNE_DEAP_SEX_AGE_RT": FlowSpec(
            min_year=1983,
            dim="age",
            theme="unemployment_rate",
            title="Unemployment rate by sex and age",
        ),
        "DF_EMP_DWAP_SEX_AGE_RT": FlowSpec(
            min_year=1983,
            dim="age",
            theme="employment_to_pop",
            title="Employment-to-population ratio by sex and age",
        ),
        "DF_EAR_EMTA_SEX_CUR_NB": FlowSpec(
            min_year=2000,
            dim="cur",
            theme="wages",
            title="Average monthly earnings of employees by sex and currency",
        ),
        "DF_EAP_DWAP_SEX_AGE_RT": FlowSpec(
            min_year=1983,
            dim="age",
            theme="lfpr",
            title="Labour force participation rate by sex and age",
        ),
        # ── Benchmark flows outside the canonical set ─────────────────────────
        # Youth-only flow split by disability status. It has no adult-total AGE
        # code, so age_group="total" returns no data. Without the DSB key it
        # returns 8-11 mixed rows per year (Phase 5 finding).
        "DF_UNE_3EAP_SEX_AGE_DSB_RT": FlowSpec(
            min_year=2011,
            dim="age",
            fixed_key={"DSB": DSB_TOTAL},
        ),
        # Without GEO this returns national + rural + urban rows mixed together.
        "DF_UNE_3EAP_SEX_AGE_GEO_RT": FlowSpec(
            min_year=2008,
            dim="age",
            fixed_key={"GEO": GEO_NATIONAL},
        ),
        "DF_EMP_2WAP_SEX_AGE_RT": FlowSpec(min_year=1991, dim="age"),  # modelled
        "DF_EAR_CMTA_SEX_CUR_NB": FlowSpec(min_year=2000, dim="cur"),  # care sector
    }
)

# Theme name -> dataflow ID for the four canonical flows.
FLOWS: Mapping[str, str] = MappingProxyType(
    {spec.theme: flow_id for flow_id, spec in FLOW_SPECS.items() if spec.theme}
)

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
COUNTRY_CURRENCY: Mapping[str, str] = MappingProxyType(
    {
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
)


def currency_for(dataflow_id: str, country: str) -> str | None:
    """
    Return the ISO 4217 code for a wage flow's local currency, or None.

    None for non-wage flows, and for countries not in COUNTRY_CURRENCY.
    """
    if FLOW_SPECS[dataflow_id].dim == "cur":
        return COUNTRY_CURRENCY.get(country)
    return None
