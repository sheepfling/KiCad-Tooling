"""Synthetic connector assignments on one native I3C SDA/SCL channel."""

from __future__ import annotations

from kicad_tooling.hwrepo.netlist_contract_models import ComponentContract, NetlistContract


def generic_i3c_connector_pair_netlist(
    *,
    connector_functions: tuple[str, ...] = ("Pin_1", "Pin_2", "Pin_3", "Pin_4", "Pin_5"),
    include_scl_contact: bool = True,
    other_contact_net: str | None = None,
) -> NetlistContract:
    """Return a complete synthetic connector and I3C endpoint inventory."""
    nets: dict[str, tuple[str, ...]] = {
        "I3C0_SDA": ("J1.1", "U1.1"),
        "I3C0_SCL": ("U1.2", *(("J1.2",) if include_scl_contact else ())),
    }
    if len(connector_functions) > 2:
        nets["BOARD_GND"] = ("J1.4", "U1.3")
        nets["+3V3"] = ("J1.3", "U1.4")
    if other_contact_net is not None:
        nets[other_contact_net] = ("J1.5",)

    connector_references = tuple(
        f"J1.{number}" for number in range(1, len(connector_functions) + 1)
    )
    connector_pin_numbers = tuple(str(number) for number in range(1, len(connector_functions) + 1))
    return NetlistContract(
        components={
            "J1": ComponentContract(
                value="Synthetic generic I3C connector", footprint="Synthetic:Conn_01x05"
            ),
            "U1": ComponentContract(value="Synthetic I3C endpoint", footprint="Synthetic:SOIC"),
        },
        nets=nets,
        component_symbols={
            "J1": "Connector_Generic:Conn_01x05",
            "U1": "Synthetic:I3cEndpoint",
        },
        pin_functions={
            **{
                pin: function
                for pin, function in zip(connector_references, connector_functions, strict=True)
            },
            "U1.1": "I3C0_SDA",
            "U1.2": "I3C0_SCL",
            "U1.3": "VSS",
            "U1.4": "VDD",
        },
        pin_electrical_types={
            **{pin: "passive" for pin in connector_references},
            "U1.1": "bidirectional",
            "U1.2": "bidirectional",
            "U1.3": "power_in",
            "U1.4": "power_in",
        },
        component_pin_numbers={
            "J1": connector_pin_numbers,
            "U1": ("1", "2", "3", "4"),
        },
    )
