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

# Which dimensions each flow uses (determines key dict construction in the client).
# "age" flows use the AGE dimension; "cur" flows use the CUR dimension.
FLOW_DIMS: dict[str, str] = {
    "DF_UNE_DEAP_SEX_AGE_RT": "age",
    "DF_EMP_DWAP_SEX_AGE_RT": "age",
    "DF_EAR_EMTA_SEX_CUR_NB": "cur",
    "DF_EAP_DWAP_SEX_AGE_RT": "age",
}

# Default dimension values
AGE_TOTAL = "AGE_YTHADULT_YGE15"  # adults 15+
AGE_YOUTH = "AGE_YTHADULT_Y15-24"  # youth 15-24
SEX_TOTAL = "SEX_T"  # total (all sexes)
CUR_DEFAULT = "CUR_TYPE_LCU"  # local currency units

# Keyword fragments that identify modelled/estimated flows (ILO modelled estimates).
# A flow is "modelled" if its ID contains any of these strings.
_MODELLED_MARKERS = ("_ILO_MODELLED", "_MOD_")


def is_modelled(flow_id: str) -> bool:
    """Return True if this flow is an ILO modelled estimate rather than survey data."""
    return any(marker in flow_id for marker in _MODELLED_MARKERS)
