"""Synthetic two-pin I2C connector return-review fixtures."""

from __future__ import annotations

from kicad_tooling.hwrepo.connector_coverage_models import (
    ConnectorCoverageEntry,
    ConnectorCoverageReport,
    ConnectorMappedPinEvidence,
)
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.design_lint_fixtures.i2c_generic_connector_pair import (
    generic_i2c_connector_pair_netlist,
)


def two_pin_i2c_connector_netlist(
    *,
    connector_functions: tuple[str, ...] = ("Pin_1", "Pin_2"),
    connected_return_contact: bool = False,
) -> NetlistContract:
    """Build an exact native SDA/SCL pair on a two-contact generic connector."""
    source = generic_i2c_connector_pair_netlist()
    removed = {"j1.3", "j1.4"}
    nets = {
        name: tuple(pin for pin in pins if pin.casefold() not in removed)
        for name, pins in source.nets.items()
    }
    nets = {name: pins for name, pins in nets.items() if pins}
    functions = {
        pin: value for pin, value in source.pin_functions.items() if pin.casefold() not in removed
    }
    functions.update(
        {f"J1.{index}": function for index, function in enumerate(connector_functions, 1)}
    )
    electrical_types = {
        pin: value
        for pin, value in source.pin_electrical_types.items()
        if pin.casefold() not in removed
    }
    pin_numbers = {**source.component_pin_numbers, "J1": ("1", "2")}
    components = dict(source.components)
    components["J1"] = components["J1"].model_copy(update={"footprint": "Synthetic:Conn_01x02"})
    symbols = {**source.component_symbols, "J1": "Connector_Generic:Conn_01x02"}

    if connected_return_contact:
        pin_numbers["J1"] = ("1", "2", "3")
        functions["J1.3"] = "GND"
        electrical_types["J1.3"] = "passive"
        nets["BOARD_GND"] = (*nets.get("BOARD_GND", ()), "J1.3")

    return source.model_copy(
        update={
            "components": components,
            "nets": nets,
            "component_symbols": symbols,
            "pin_functions": functions,
            "pin_electrical_types": electrical_types,
            "component_pin_numbers": pin_numbers,
        }
    )


def two_pin_i2c_connector_map(
    *,
    return_on_signal_contact: bool = False,
) -> ConnectorCoverageReport:
    """Return a source-matched signal map, optionally with conflicting return role."""
    return ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic two-contact I2C connector",
        project_interfaces=("synthetic-i2c",),
        inventory_review_basis="Synthetic approved complete connector pinout",
        interface_catalog_sha256="b" * 64,
        entries=(
            ConnectorCoverageEntry(
                reference="J1",
                status="COVERED",
                interface_id="synthetic-i2c",
                basis="Synthetic approved SDA/SCL map",
                interface_pin_map={
                    "GND" if return_on_signal_contact else "SDA": "1",
                    "SCL": "2",
                },
                mapped_pins=(
                    ConnectorMappedPinEvidence(
                        interface_pin_number="GND" if return_on_signal_contact else "SDA",
                        interface_signal="GND" if return_on_signal_contact else "SDA",
                        component_pin="J1.1",
                        role="return" if return_on_signal_contact else "signal",
                        symbol_function="Pin_1",
                        nets=("I2C_SDA",),
                    ),
                    ConnectorMappedPinEvidence(
                        interface_pin_number="SCL",
                        interface_signal="SCL",
                        component_pin="J1.2",
                        role="signal",
                        symbol_function="Pin_2",
                        nets=("I2C_SCL",),
                    ),
                ),
            ),
        ),
    )
