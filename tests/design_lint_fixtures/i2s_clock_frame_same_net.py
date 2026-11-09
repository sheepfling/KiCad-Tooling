"""Synthetic I2S clock/frame same-net fault and distinct-net control."""

from __future__ import annotations

from kicad_tooling.hwrepo.netlist_contract_models import (
    ComponentContract,
    NetlistContract,
)


def i2s_clock_frame_netlist(*, shared: bool = True, dnp: bool = False) -> NetlistContract:
    """Return a complete fitted audio IC with shared or distinct clock nets."""
    bit_clock_net = "AUDIO_SHARED" if shared else "I2S_BIT_CLOCK"
    word_select_net = "AUDIO_SHARED" if shared else "I2S_WORD_SELECT"
    nets = {
        bit_clock_net: ("U1.1", "U1.2") if shared else ("U1.1",),
        "I2S_DATA": ("U1.3",),
        "AUDIO_MASTER_CLOCK": ("U1.4",),
    }
    if not shared:
        nets[word_select_net] = ("U1.2",)
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic audio codec", footprint="Synthetic:Codec")
        },
        nets=nets,
        dnp_components=("U1",) if dnp else (),
        component_symbols={"U1": "Synthetic:I2SAudioCodec"},
        component_pin_numbers={"U1": ("1", "2", "3", "4")},
        pin_functions={
            "U1.1": "I2S_BCLK",
            "U1.2": "I2S_LRCLK",
            "U1.3": "I2S_DATA",
            "U1.4": "MCLK",
        },
        pin_electrical_types={
            "U1.1": "passive",
            "U1.2": "passive",
            "U1.3": "passive",
            "U1.4": "passive",
        },
    )
