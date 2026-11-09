"""Synthetic fitted-IC SWDIO/SWCLK same-net fault and valid control."""

from __future__ import annotations

from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract

from .swd_generic_connector_pair import generic_swd_connector_netlist


def swd_signal_same_net_netlist(*, shared: bool = True, dnp: bool = False) -> NetlistContract:
    """Return complete SWD endpoint evidence with shared or distinct signal nets."""
    endpoint_assignments = {
        "1": "GPIO_1",
        "2": "GPIO_2",
        "3": "GPIO_3",
        "4": "GPIO_4",
        "5": "SWD_SHARED" if shared else "SWD_DATA",
        "6": "SWD_SHARED" if shared else "SWD_CLOCK",
    }
    return generic_swd_connector_netlist(
        endpoint_assignments=endpoint_assignments,
        dnp=("U1",) if dnp else (),
    )
