"""Tooling-owned synthetic case for a JTAG TCK/TMS same-net review."""

from __future__ import annotations

from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.design_lint_fixtures.jtag_data_same_net import jtag_data_same_net_netlist


def jtag_clock_mode_same_net_netlist() -> NetlistContract:
    """Return one complete JTAG IC with TCK/TMS shared and data pins separate."""
    source = jtag_data_same_net_netlist(shared=False)
    return source.model_copy(
        update={
            "nets": {
                "JTAG_CLOCK_MODE_SHARED": ("U1.1", "U1.2"),
                "JTAG_TDI_U1": ("U1.3",),
                "JTAG_TDO_U1": ("U1.4",),
            }
        }
    )
