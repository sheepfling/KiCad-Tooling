"""Synthetic mixed-interface connector return cases."""

from __future__ import annotations

from collections.abc import Mapping

from kicad_tooling.hwrepo.connector_coverage import evaluate
from kicad_tooling.hwrepo.models import (
    ConnectorCoverageReport,
    ConnectorInterfaceReview,
    NetlistContract,
)
from tests.design_lint_fixtures.connector_coverage import (
    connector_return_role_catalog,
    inventory_review,
)


def two_usb_one_serial_return_case(
    *, common_return: bool, return_comparison_groups: Mapping[str, str] | None = None
) -> tuple[NetlistContract, ConnectorCoverageReport]:
    """Build two mapped USB peers and one serial peer with a split/common return."""
    nets: dict[str, tuple[str, ...]] = {
        "USB1_D+": ("J1.1",),
        "USB1_D-": ("J1.2",),
        "SERIAL_TX": ("J2.1",),
        "SERIAL_RX": ("J2.2",),
        "SERIAL_SUPPLY": ("J2.4",),
        "USB2_D+": ("J3.1",),
        "USB2_D-": ("J3.2",),
    }
    if common_return:
        nets["COMMON_RETURN"] = ("J1.3", "J2.3", "J3.3")
    else:
        nets["COMMON_RETURN"] = ("J1.3", "J2.3")
        nets["USB2_RETURN"] = ("J3.3",)

    netlist = NetlistContract(
        components={},
        nets=nets,
        component_symbols={
            "J1": "Connector:USB_C_Receptacle_USB2.0_16P",
            "J2": "Connector:DB9",
            "J3": "Connector:USB_C_Receptacle_USB2.0_16P",
        },
        component_pin_numbers={
            "J1": ("1", "2", "3"),
            "J2": ("1", "2", "3", "4"),
            "J3": ("1", "2", "3"),
        },
        pin_functions={
            "J1.1": "D+",
            "J1.2": "D-",
            "J1.3": "GND",
            "J2.1": "TX",
            "J2.2": "RX",
            "J2.3": "Pin_3",
            "J2.4": "Pin_4",
            "J3.1": "D+",
            "J3.2": "D-",
            "J3.3": "GND",
        },
    )
    peer_specs = (
        ("J1", "usb-interface", {"1": "1", "2": "2", "3": "3"}, "usb-port-1"),
        (
            "J2",
            "serial-interface",
            {"1": "1", "2": "2", "3": "3", "4": "4"},
            "serial-port",
        ),
        ("J3", "usb-interface", {"1": "1", "2": "2", "3": "3"}, "usb-port-2"),
    )
    reviews = tuple(
        ConnectorInterfaceReview(
            reference=reference,
            disposition="interface",
            basis=f"Synthetic source review for {interface_id}",
            interface_id=interface_id,
            pin_map=pin_map,
            peer_assignment_group=group,
            peer_assignment_basis=f"Reviewed {reference} in group {group}",
            return_comparison_group=(return_comparison_groups or {}).get(reference),
            return_comparison_basis=(
                f"Reviewed {reference} in return-comparison group "
                f"{return_comparison_groups[reference]}"
                if return_comparison_groups is not None and reference in return_comparison_groups
                else None
            ),
        )
        for reference, interface_id, pin_map, group in peer_specs
    )
    coverage = evaluate(
        netlist,
        ("usb-interface", "serial-interface"),
        reviews,
        interfaces=connector_return_role_catalog(),
        interface_catalog_path="catalog/interfaces.json",
        interface_catalog_sha256="9" * 64,
        inventory_review=inventory_review(),
    )
    return netlist, coverage
