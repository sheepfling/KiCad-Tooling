"""Synthetic repeated-component power-domain peer netlists."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def component_peer_power_netlist(*, split_domains: bool) -> NetlistContract:
    nets = {
        "IO_SHARED": ("U1.1", "U2.1"),
        "+3V3": ("U1.2", "U2.2") if not split_domains else ("U1.2",),
        "GND": ("U1.3", "U2.3") if not split_domains else ("U1.3",),
    }
    if split_domains:
        nets["+5V"] = ("U2.2",)
        nets["AGND"] = nets.pop("GND")
        nets["DGND"] = ("U2.3",)
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic peer module", footprint="Synthetic:QFN-2"),
            "U2": ComponentContract(value="Synthetic peer module", footprint="Synthetic:QFN-2"),
        },
        nets=nets,
        component_symbols={"U1": "Synthetic:PeerModule", "U2": "Synthetic:PeerModule"},
        pin_functions={
            "U1.1": "IO",
            "U1.2": "VDD",
            "U1.3": "GND",
            "U2.1": "IO",
            "U2.2": "VDD",
            "U2.3": "GND",
        },
        pin_electrical_types={
            "U1.1": "passive",
            "U1.2": "power_in",
            "U1.3": "power_in",
            "U2.1": "passive",
            "U2.2": "power_in",
            "U2.3": "power_in",
        },
        component_pin_numbers={"U1": ("1", "2", "3"), "U2": ("1", "2", "3")},
    )
