"""Synthetic I2S bit-clock/data same-net fault and distinct-net control."""

from __future__ import annotations

from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.design_lint_fixtures.i2s_clock_frame_same_net import i2s_clock_frame_netlist


def i2s_clock_data_netlist(*, shared: bool = True, dnp: bool = False) -> NetlistContract:
    """Return a complete audio IC with shared or distinct clock/data nets."""
    source = i2s_clock_frame_netlist(shared=False, dnp=dnp)
    if not shared:
        return source
    nets = {
        name: pins
        for name, pins in source.nets.items()
        if name not in {"I2S_BIT_CLOCK", "I2S_DATA"}
    }
    nets["I2S_SHARED"] = ("U1.1", "U1.3")
    return source.model_copy(update={"nets": nets})
