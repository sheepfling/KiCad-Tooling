"""Synthetic netlists for unanchored connector footprint-peer coverage."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def connector_footprint_peer_scope_cases() -> dict[str, NetlistContract]:
    """Mirror source-hashed alias split and partial-open schematic fixtures."""
    references = ("J1", "J2")
    components = {
        reference: ComponentContract(
            value="Synthetic two-contact connector",
            footprint="Synthetic:Connector_2x1",
        )
        for reference in references
    }
    symbols = {"J1": "Synthetic:GenericPort", "J2": "Synthetic:GenericPortAlias"}
    pin_numbers = {reference: ("1", "2") for reference in references}
    functions = {
        f"{reference}.{number}": f"Pin_{number}"
        for reference in references
        for number in ("1", "2")
    }
    electrical_types = {pin: "passive" for pin in functions}
    return {
        "footprint-alias-unanchored-fault": NetlistContract(
            components=components,
            nets={
                "SYNTHETIC_NET_1": ("J1.1",),
                "SYNTHETIC_NET_2": ("J1.2",),
                "SYNTHETIC_NET_3": ("J2.2",),
                "SYNTHETIC_NET_4": ("J2.1",),
            },
            component_symbols=symbols,
            component_pin_numbers=pin_numbers,
            pin_functions=functions,
            pin_electrical_types=electrical_types,
        ),
        "footprint-alias-unanchored-partial-open-fault": NetlistContract(
            components=components,
            nets={"SYNTHETIC_NET_2": ("J1.2",)},
            unconnected_nets={"unconnected": ("J1.1", "J2.1", "J2.2")},
            component_symbols=symbols,
            component_pin_numbers=pin_numbers,
            pin_functions=functions,
            pin_electrical_types=electrical_types,
        ),
    }


def connector_same_voltage_power_input_cases() -> dict[str, NetlistContract]:
    """Mirror unanchored same-voltage connector power-input fault and control."""
    components: dict[str, ComponentContract] = {
        reference: ComponentContract(
            value="Synthetic named power-input peer",
            footprint="Synthetic:Package",
        )
        for reference in ("J1", "J2")
    }
    component_symbols = {"J1": "Lint:NamedPeerPowerInputA", "J2": "Lint:NamedPeerPowerInputB"}
    component_pin_numbers = {"J1": ("1", "2"), "J2": ("1", "2")}
    pin_functions = {"J1.1": "BIAS_IN", "J2.1": "BIAS_IN", "J1.2": "2", "J2.2": "2"}
    pin_electrical_types = {
        "J1.1": "power_in",
        "J2.1": "power_in",
        "J1.2": "passive",
        "J2.2": "passive",
    }

    def contract(nets: dict[str, tuple[str, ...]]) -> NetlistContract:
        return NetlistContract(
            components=components,
            nets=nets,
            component_symbols=component_symbols,
            component_pin_numbers=component_pin_numbers,
            pin_functions=pin_functions,
            pin_electrical_types=pin_electrical_types,
        )

    return {
        "footprint-alias-same-voltage-power-input-fault": contract(
            {
                "+3V3": ("J1.1",),
                "3.3V": ("J2.1",),
                "PORT_A": ("J1.2",),
                "PORT_B": ("J2.2",),
            },
        ),
        "footprint-alias-same-voltage-power-input-control": contract(
            {"+3V3": ("J1.1", "J2.1"), "PORT_A": ("J1.2", "J2.2")}
        ),
    }
