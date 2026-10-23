"""Small synthetic USB endpoint pairs for connector-to-PHY crossing checks."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def usb_data_pair_crossing_netlist(
    *,
    crossed: bool = True,
    net_names: tuple[str, str] = ("DATA_A", "DATA_B"),
) -> NetlistContract:
    """Return one fully inventoried USB connector and PHY with common reference."""
    positive_connector_phy_pin = "U1.2" if crossed else "U1.1"
    negative_connector_phy_pin = "U1.1" if crossed else "U1.2"
    return NetlistContract(
        components={
            "J1": ComponentContract(value="USB_A", footprint="Synthetic:USB-A"),
            "U1": ComponentContract(value="Synthetic USB PHY", footprint="Synthetic:QFN"),
        },
        nets={
            net_names[0]: ("J1.1", positive_connector_phy_pin),
            net_names[1]: ("J1.2", negative_connector_phy_pin),
            "BOARD_GND": ("J1.4", "U1.3"),
        },
        component_symbols={
            "J1": "Connector:USB_A",
            "U1": "Synthetic:USB_PHY",
        },
        pin_functions={
            "J1.1": "D+",
            "J1.2": "D-",
            "J1.4": "GND",
            "U1.1": "UD+",
            "U1.2": "UD-",
            "U1.3": "VSS",
        },
        pin_electrical_types={
            "J1.1": "passive",
            "J1.2": "passive",
            "J1.4": "passive",
            "U1.1": "input",
            "U1.2": "input",
            "U1.3": "unspecified",
        },
        component_pin_numbers={"J1": ("1", "2", "4"), "U1": ("1", "2", "3")},
    )


def usb_data_pair_crossing_with_port_groups(
    *,
    connector_port_group: str | None,
    phy_port_group: str | None,
) -> NetlistContract:
    """Add independent connector and PHY port identities to the synthetic pair."""
    observed = usb_data_pair_crossing_netlist()

    def function_names(group: str | None, *, phy: bool) -> tuple[str, str]:
        if group is None:
            return ("UD+", "UD-") if phy else ("D+", "D-")
        prefix = "USB_D" if phy else "D"
        return (f"{prefix}P{group}", f"{prefix}M{group}")

    connector_positive, connector_negative = function_names(connector_port_group, phy=False)
    phy_positive, phy_negative = function_names(phy_port_group, phy=True)
    return observed.model_copy(
        update={
            "pin_functions": {
                **observed.pin_functions,
                "J1.1": connector_positive,
                "J1.2": connector_negative,
                "U1.1": phy_positive,
                "U1.2": phy_negative,
            }
        }
    )


def usb_data_pair_crossing_with_tvs_shunt() -> NetlistContract:
    """Add one valid D-designated branch from a crossed USB data net to ground."""
    observed = usb_data_pair_crossing_netlist()
    return observed.model_copy(
        update={
            "components": {
                **observed.components,
                "D1": ComponentContract(value="Synthetic TVS", footprint="Synthetic:SOD-323"),
            },
            "component_symbols": {**observed.component_symbols, "D1": "Synthetic:TVS"},
            "component_pin_numbers": {
                **observed.component_pin_numbers,
                "D1": ("1", "2"),
            },
            "nets": {
                **observed.nets,
                "DATA_A": (*observed.nets["DATA_A"], "D1.1"),
                "BOARD_GND": (*observed.nets["BOARD_GND"], "D1.2"),
            },
            "pin_functions": {
                **observed.pin_functions,
                "D1.1": "D+",
                "D1.2": "GND",
            },
            "pin_electrical_types": {
                **observed.pin_electrical_types,
                "D1.1": "passive",
                "D1.2": "passive",
            },
        }
    )


def usb_data_pair_crossing_with_unrelated_branch() -> NetlistContract:
    """Add an unexplained passive branch to a crossed USB data net."""
    observed = usb_data_pair_crossing_netlist()
    return observed.model_copy(
        update={
            "components": {
                **observed.components,
                "R1": ComponentContract(value="Synthetic resistor", footprint="Synthetic:0603"),
            },
            "component_symbols": {**observed.component_symbols, "R1": "Device:R"},
            "component_pin_numbers": {
                **observed.component_pin_numbers,
                "R1": ("1", "2"),
            },
            "nets": {
                **observed.nets,
                "DATA_A": (*observed.nets["DATA_A"], "R1.1"),
                "+3V3": ("R1.2",),
            },
            "pin_functions": {
                **observed.pin_functions,
                "R1.1": "A",
                "R1.2": "B",
            },
            "pin_electrical_types": {
                **observed.pin_electrical_types,
                "R1.1": "passive",
                "R1.2": "passive",
            },
        }
    )
