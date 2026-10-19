"""Native-matched cases for numeric connector pin-function labels."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def footprint_alias_numeric_peer_pin_cases() -> dict[str, NetlistContract]:
    """Return numeric-label fault, quiet-control, and open-pin cases."""
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
    pin_functions = {
        f"{reference}.{number}": function
        for reference in references
        for number, function in (("1", "1"), ("2", "7"))
    }
    electrical_types = {pin: "passive" for pin in pin_functions}

    def observed(
        *, second_pin_nets: dict[str, tuple[str, ...]], open_pin: bool = False
    ) -> NetlistContract:
        return NetlistContract(
            components=components,
            nets={"SYNTHETIC_NET_1": ("J1.1", "J2.1"), **second_pin_nets},
            unconnected_nets={"unconnected": ("J2.2",)} if open_pin else {},
            component_symbols=symbols,
            component_pin_numbers=pin_numbers,
            pin_functions=pin_functions,
            pin_electrical_types=electrical_types,
        )

    return {
        "footprint-alias-numeric-fault": observed(
            second_pin_nets={
                "SYNTHETIC_NET_2": ("J1.2",),
                "SYNTHETIC_NET_3": ("J2.2",),
            }
        ),
        "footprint-alias-numeric-control": observed(
            second_pin_nets={"SYNTHETIC_NET_2": ("J1.2", "J2.2")}
        ),
        "footprint-alias-numeric-open-fault": observed(
            second_pin_nets={"SYNTHETIC_NET_2": ("J1.2",)}, open_pin=True
        ),
    }
