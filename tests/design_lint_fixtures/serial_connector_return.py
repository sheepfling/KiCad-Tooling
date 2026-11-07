"""Synthetic two-pin UART connector return-review fixtures."""

from __future__ import annotations

from kicad_tooling.hwrepo.connector_coverage_models import (
    ConnectorCoverageEntry,
    ConnectorCoverageReport,
    ConnectorMappedPinEvidence,
)
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.design_lint_fixtures.serial_generic_connector_pair import (
    generic_serial_connector_pair_netlist,
)


def two_pin_uart_connector_netlist(
    *,
    return_pin: str | None = None,
    connector_functions: tuple[str, str] = ("Pin_1", "Pin_2"),
) -> NetlistContract:
    """Build a complete two-pin generic UART connector and optional return control."""
    source = generic_serial_connector_pair_netlist()
    nets = {
        name: tuple(pin for pin in pins if pin.casefold() not in {"j1.3", "j1.4"})
        for name, pins in source.nets.items()
    }
    nets = {name: pins for name, pins in nets.items() if pins}
    functions = {
        pin: function
        for pin, function in source.pin_functions.items()
        if pin.casefold() not in {"j1.3", "j1.4"}
    }
    functions.update({f"J1.{index}": role for index, role in enumerate(connector_functions, 1)})
    electrical_types = {
        pin: value
        for pin, value in source.pin_electrical_types.items()
        if pin.casefold() not in {"j1.3", "j1.4"}
    }
    component_pin_numbers = {
        **source.component_pin_numbers,
        "J1": ("1", "2"),
    }
    if return_pin is not None:
        return_number = "3"
        connector_pins = tuple(sorted((*component_pin_numbers["J1"], return_number)))
        component_pin_numbers["J1"] = connector_pins
        functions[f"J1.{return_number}"] = return_pin
        electrical_types[f"J1.{return_number}"] = "passive"
        nets["BOARD_GND"] = (*nets.get("BOARD_GND", ()), f"J1.{return_number}")
    return source.model_copy(
        update={
            "nets": nets,
            "pin_functions": functions,
            "pin_electrical_types": electrical_types,
            "component_pin_numbers": component_pin_numbers,
        }
    )


def two_pin_uart_connector_return_map(
    *, tx_contact_role: str = "UART_TX"
) -> ConnectorCoverageReport:
    """Return a current UART contact map with an optional return-role contact."""
    tx_signal = tx_contact_role
    return ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic two-contact UART connector",
        project_interfaces=("synthetic-uart",),
        inventory_review_basis="Synthetic reviewed complete connector pinout",
        interface_catalog_sha256="b" * 64,
        entries=(
            ConnectorCoverageEntry(
                reference="J1",
                status="COVERED",
                interface_id="synthetic-uart",
                basis="Synthetic approved two-contact UART pinout",
                interface_pin_map={tx_signal: "1", "UART_RX": "2"},
                mapped_pins=(
                    ConnectorMappedPinEvidence(
                        interface_pin_number=tx_signal,
                        interface_signal=tx_signal,
                        component_pin="J1.1",
                        role="return" if tx_signal == "GND" else None,
                        symbol_function="Pin_1",
                        nets=("LINE_A",),
                    ),
                    ConnectorMappedPinEvidence(
                        interface_pin_number="UART_RX",
                        interface_signal="UART_RX",
                        component_pin="J1.2",
                        symbol_function="Pin_2",
                        nets=("LINE_B",),
                    ),
                ),
            ),
        ),
    )
