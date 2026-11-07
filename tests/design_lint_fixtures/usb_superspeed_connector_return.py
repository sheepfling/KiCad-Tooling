"""Synthetic two-pin USB SuperSpeed connector return-review inputs."""

from __future__ import annotations

from typing import Literal

from kicad_tooling.hwrepo.connector_coverage_models import (
    ConnectorCoverageEntry,
    ConnectorCoverageReport,
    ConnectorMappedPinEvidence,
)
from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract

from .usb_superspeed_generic_connector import generic_usb_superspeed_connector_pair_netlist


def two_pin_usb_superspeed_connector_netlist(
    *,
    phy_family: Literal["TX", "RX"] = "TX",
    connector_functions: tuple[str, str] = ("Pin_1", "Pin_2"),
    include_return_contact: bool = False,
    connector_dnp: bool = False,
    endpoint_dnp: bool = False,
    include_negative_contact: bool = True,
    ambiguous_connector_contact: bool = False,
    ambiguous_phy_endpoint: bool = False,
) -> NetlistContract:
    """Build complete or deliberately incomplete native-shaped USB SS evidence."""
    source = generic_usb_superspeed_connector_pair_netlist(phy_family=phy_family)
    connector_numbers = ("1", "2", "3") if include_return_contact else ("1", "2")
    removed = {f"j1.{number}" for number in ("3", "4") if number not in connector_numbers}
    nets = {
        name: tuple(pin for pin in pins if pin.casefold() not in removed)
        for name, pins in source.nets.items()
    }
    nets = {name: pins for name, pins in nets.items() if pins}
    if include_return_contact:
        nets["USB_GND"] = (*nets.get("USB_GND", ()), "J1.3")
    if not include_negative_contact:
        negative_net = f"SS_{phy_family}_N"
        nets[negative_net] = tuple(pin for pin in nets[negative_net] if pin.casefold() != "j1.2")
    if ambiguous_connector_contact:
        nets["OTHER"] = ("J1.1",)

    functions = {
        pin: function
        for pin, function in source.pin_functions.items()
        if pin.casefold() not in removed
    }
    functions.update({f"J1.{index}": value for index, value in enumerate(connector_functions, 1)})
    types = {
        pin: value
        for pin, value in source.pin_electrical_types.items()
        if pin.casefold() not in removed
    }
    types.update({f"J1.{number}": "passive" for number in connector_numbers})
    dnp = tuple(
        reference
        for reference, selected in (("J1", connector_dnp), ("U1", endpoint_dnp))
        if selected
    )
    components = dict(source.components)
    symbols = dict(source.component_symbols)
    inventories = {**source.component_pin_numbers, "J1": connector_numbers}
    if ambiguous_phy_endpoint:
        components["U2"] = ComponentContract(
            value="Second synthetic USB SuperSpeed PHY", footprint="Synthetic:QFN"
        )
        symbols["U2"] = "Synthetic:UsbSuperspeedPhy"
        inventories["U2"] = source.component_pin_numbers["U1"]
        functions.update(
            {
                f"U2.{number}": source.pin_functions[f"U1.{number}"]
                for number in ("1", "2", "3", "4")
            }
        )
        types.update(
            {
                f"U2.{number}": source.pin_electrical_types[f"U1.{number}"]
                for number in ("1", "2", "3", "4")
            }
        )
        for number in ("1", "2", "3", "4"):
            net = next(name for name, pins in nets.items() if f"U1.{number}" in pins)
            nets[net] = (*nets[net], f"U2.{number}")
    return source.model_copy(
        update={
            "components": components,
            "nets": nets,
            "dnp_components": dnp,
            "component_symbols": {
                **symbols,
                "J1": f"Connector_Generic:Conn_01x{len(connector_numbers):02d}",
            },
            "pin_functions": functions,
            "pin_electrical_types": types,
            "component_pin_numbers": inventories,
        }
    )


def usb_superspeed_connector_coverage(
    *,
    not_applicable: bool = False,
    map_return_to_data_contact: bool = False,
    data_only: bool = False,
) -> ConnectorCoverageReport:
    """Build current role evidence that either identifies a return or only data."""
    if not_applicable:
        entry = ConnectorCoverageEntry(reference="J1", status="NOT_APPLICABLE")
    else:
        first_role = "return" if map_return_to_data_contact else "signal"
        first_name = "GND" if map_return_to_data_contact else "SSTX+"
        pins = (
            ConnectorMappedPinEvidence(
                interface_pin_number=first_name,
                interface_signal=first_name,
                component_pin="J1.1",
                role=first_role,
                symbol_function="Pin_1",
                nets=("SS_TX_P",),
            ),
            ConnectorMappedPinEvidence(
                interface_pin_number="SSTX-",
                interface_signal="SSTX-",
                component_pin="J1.2",
                role="signal",
                symbol_function="Pin_2",
                nets=("SS_TX_N",),
            ),
        )
        entry = ConnectorCoverageEntry(
            reference="J1",
            status="COVERED",
            interface_id="synthetic-usb-superspeed",
            basis=(
                "Synthetic reviewed USB SuperSpeed data-only map"
                if data_only
                else "Synthetic reviewed USB SuperSpeed connector map"
            ),
            interface_pin_map={
                item.interface_pin_number: item.component_pin.rsplit(".", 1)[1] for item in pins
            },
            mapped_pins=pins,
        )
    return ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic USB SuperSpeed connector inventory",
        inventory_review_basis="Synthetic reviewed connector disposition",
        interface_catalog_sha256="d" * 64,
        entries=(entry,),
    )
