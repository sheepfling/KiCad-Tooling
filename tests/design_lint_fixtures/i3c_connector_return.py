"""Synthetic two-pin I3C connector return-review fixtures."""

from __future__ import annotations

from kicad_tooling.hwrepo.connector_coverage_models import (
    ConnectorCoverageEntry,
    ConnectorCoverageReport,
    ConnectorMappedPinEvidence,
)
from kicad_tooling.hwrepo.netlist_contract_models import ComponentContract, NetlistContract


def two_pin_i3c_connector_netlist(
    *,
    connector_functions: tuple[str, ...] = ("Pin_1", "Pin_2"),
    connected_return_contact: bool = False,
    channel: str = "",
) -> NetlistContract:
    """Build a fully inventoried I3C endpoint and two-contact connector."""
    sda_role = f"I3C{channel}_SDA"
    scl_role = f"I3C{channel}_SCL"
    sda_net = f"I3C{channel}_SDA_NET"
    scl_net = f"I3C{channel}_SCL_NET"
    pin_numbers = {"J1": ("1", "2"), "U1": ("1", "2", "3", "4")}
    functions = {
        "J1.1": connector_functions[0],
        "J1.2": connector_functions[1],
        "U1.1": sda_role,
        "U1.2": scl_role,
        "U1.3": "VSS",
        "U1.4": "VDD",
    }
    electrical_types = {
        "J1.1": "passive",
        "J1.2": "passive",
        "U1.1": "bidirectional",
        "U1.2": "bidirectional",
        "U1.3": "power_in",
        "U1.4": "power_in",
    }
    nets = {
        sda_net: ("J1.1", "U1.1"),
        scl_net: ("J1.2", "U1.2"),
        "BOARD_GND": ("U1.3",),
        "+3V3": ("U1.4",),
    }
    if connected_return_contact:
        pin_numbers["J1"] = ("1", "2", "3")
        functions["J1.3"] = "GND"
        electrical_types["J1.3"] = "passive"
        nets["BOARD_GND"] = (*nets["BOARD_GND"], "J1.3")
    return NetlistContract(
        components={
            "J1": ComponentContract(
                value="Synthetic generic connector", footprint="Synthetic:Conn_01x02"
            ),
            "U1": ComponentContract(value="Synthetic I3C endpoint", footprint="Synthetic:QFN"),
        },
        nets=nets,
        component_symbols={
            "J1": "Connector_Generic:Conn_01x02",
            "U1": "Synthetic:I3cEndpoint",
        },
        pin_functions=functions,
        pin_electrical_types=electrical_types,
        component_pin_numbers=pin_numbers,
    )


def two_pin_i3c_connector_map(*, return_on_signal_contact: bool = False) -> ConnectorCoverageReport:
    """Build a current source-matched I3C pinout map for the two contacts."""
    signal_1 = "GND" if return_on_signal_contact else "SDA"
    role_1 = "return" if return_on_signal_contact else "signal"
    return ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic two-contact I3C connector",
        project_interfaces=("synthetic-i3c",),
        inventory_review_basis="Synthetic approved complete connector pinout",
        interface_catalog_sha256="c" * 64,
        entries=(
            ConnectorCoverageEntry(
                reference="J1",
                status="COVERED",
                interface_id="synthetic-i3c",
                basis="Synthetic approved I3C SDA/SCL map",
                interface_pin_map={signal_1: "1", "SCL": "2"},
                mapped_pins=(
                    ConnectorMappedPinEvidence(
                        interface_pin_number=signal_1,
                        interface_signal=signal_1,
                        component_pin="J1.1",
                        role=role_1,
                        symbol_function="Pin_1",
                        nets=("I3C_SDA_NET",),
                    ),
                    ConnectorMappedPinEvidence(
                        interface_pin_number="SCL",
                        interface_signal="SCL",
                        component_pin="J1.2",
                        role="signal",
                        symbol_function="Pin_2",
                        nets=("I3C_SCL_NET",),
                    ),
                ),
            ),
        ),
    )


def i3c_not_applicable_map() -> ConnectorCoverageReport:
    """Build a reviewed exception for a connector outside the I3C scope."""
    return ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic reviewed connector inventory",
        inventory_review_basis="Reviewed I3C connector applicability decision",
        entries=(ConnectorCoverageEntry(reference="J1", status="NOT_APPLICABLE"),),
    )
