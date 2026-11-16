"""Bounded native identity recognition for Ethernet PHY lint rules."""

from __future__ import annotations

import re

from .casefold_mapping_lookup import lookup_unique_casefold
from .netlist_contract_models import NetlistContract

_ETHERNET_PHY_IDENTITY = re.compile(
    r"(?<![a-z0-9])(?:ethernet|eth)[\s_-]+(?:phy|transceiver)(?![a-z0-9])"
    r"|(?<![a-z0-9])(?:lan87\d{2,4}[a-z]?|dp83\d{3,4}[a-z]?|"
    r"rtl82\d{2,4}[a-z]?|ksz80\d{2,4}[a-z]?)(?![a-z0-9])",
    re.IGNORECASE,
)


def explicit_ethernet_phy_identity(observed: NetlistContract, reference: str) -> str | None:
    """Return bounded native Ethernet PHY identity text for one component."""
    component = lookup_unique_casefold(observed.components, reference)
    if component is None:
        return None
    symbol = lookup_unique_casefold(observed.component_symbols, reference)
    identity = " ".join(value for value in (symbol, component.value) if value)
    return identity if _ETHERNET_PHY_IDENTITY.search(identity) is not None else None
