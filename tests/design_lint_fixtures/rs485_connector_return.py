"""Synthetic two-contact RS-485 connector return-review inputs."""

from __future__ import annotations

from kicad_tooling.hwrepo.connector_coverage_models import (
    ConnectorCoverageEntry,
    ConnectorCoverageReport,
    ConnectorMappedPinEvidence,
)
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract

from .rs485_generic_connector_pair import generic_rs485_connector_pair_netlist


def two_pin_rs485_connector_netlist(
    *,
    connector_functions: tuple[str, ...] = ("Pin_1", "Pin_2"),
    line_functions: tuple[str, str] = ("A", "B"),
    connector_dnp: bool = False,
    endpoint_dnp: bool = False,
    include_b_contact: bool = True,
    ambiguous_connector_contact: bool = False,
) -> NetlistContract:
    """Build a completely inventoried two-contact connector on an A/B pair."""
    source = generic_rs485_connector_pair_netlist()
    connectors = ("1", "2", "3") if "GND" in connector_functions else ("1", "2")
    removed = {f"j1.{number}" for number in ("3", "4") if number not in connectors}
    nets = {
        name: tuple(pin for pin in pins if pin.casefold() not in removed)
        for name, pins in source.nets.items()
    }
    nets = {name: pins for name, pins in nets.items() if pins}
    if not include_b_contact:
        nets["LINE_B"] = tuple(pin for pin in nets["LINE_B"] if pin.casefold() != "j1.2")
    if "3" in connectors:
        nets["BOARD_GND"] = (*nets.get("BOARD_GND", ()), "J1.3")
    if ambiguous_connector_contact:
        nets["OTHER"] = ("J1.1",)

    functions = {
        pin: function
        for pin, function in source.pin_functions.items()
        if pin.casefold() not in removed
    }
    functions.update(
        {f"J1.{index}": function for index, function in enumerate(connector_functions, 1)}
    )
    types = {
        pin: value
        for pin, value in source.pin_electrical_types.items()
        if pin.casefold() not in removed
    }
    types.update({f"J1.{number}": "passive" for number in connectors})
    dnp = tuple(
        reference
        for reference, selected in (("J1", connector_dnp), ("U1", endpoint_dnp))
        if selected
    )
    return source.model_copy(
        update={
            "components": {
                **source.components,
                "J1": source.components["J1"].model_copy(
                    update={"footprint": f"Synthetic:Conn_01x{len(connectors):02d}"}
                ),
            },
            "nets": nets,
            "dnp_components": dnp,
            "component_symbols": {
                **source.component_symbols,
                "J1": f"Connector_Generic:Conn_01x{len(connectors):02d}",
            },
            "pin_functions": {**functions, "U1.1": line_functions[0], "U1.2": line_functions[1]},
            "pin_electrical_types": types,
            "component_pin_numbers": {**source.component_pin_numbers, "J1": connectors},
        }
    )


def two_pin_rs485_connector_map(*, return_on_line_contact: bool = False) -> ConnectorCoverageReport:
    """Return complete source-matched A/B coverage or a mapped return-role control."""
    a_role = "return" if return_on_line_contact else "signal"
    a_name = "GND" if return_on_line_contact else "RS485_A"
    return ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic two-contact RS-485 connector",
        project_interfaces=("synthetic-rs485",),
        inventory_review_basis="Synthetic reviewed complete connector pinout",
        interface_catalog_sha256="c" * 64,
        entries=(
            ConnectorCoverageEntry(
                reference="J1",
                status="COVERED",
                interface_id="synthetic-rs485",
                basis="Synthetic approved A/B connector map",
                interface_pin_map={a_name: "1", "RS485_B": "2"},
                mapped_pins=(
                    ConnectorMappedPinEvidence(
                        interface_pin_number=a_name,
                        interface_signal=a_name,
                        component_pin="J1.1",
                        role=a_role,
                        symbol_function="Pin_1",
                        nets=("LINE_A",),
                    ),
                    ConnectorMappedPinEvidence(
                        interface_pin_number="RS485_B",
                        interface_signal="RS485_B",
                        component_pin="J1.2",
                        role="signal",
                        symbol_function="Pin_2",
                        nets=("LINE_B",),
                    ),
                ),
            ),
        ),
    )
