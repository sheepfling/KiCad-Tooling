"""Intentional multi-domain USB isolation stays outside the split-reference predicate."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract
from kicad_tooling.hwrepo.usb_peer_reference_review import usb_peer_reference_reviews
from tests.usb_peer_reference_support import RULE_ID, lint_report

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def test_two_port_isolator_is_quiet_but_remains_incomplete_coverage() -> None:
    observed = NetlistContract(
        components={
            "J1": ComponentContract(value="Synthetic host USB port", footprint="Synthetic:USB-A"),
            "J2": ComponentContract(value="Synthetic device USB port", footprint="Synthetic:USB-A"),
            "U1": ComponentContract(
                value="Synthetic two-port USB isolator", footprint="Synthetic:QFN"
            ),
        },
        nets={
            "USB1_DP": ("J1.1", "U1.1"),
            "USB1_DM": ("J1.2", "U1.2"),
            "HOST_GND": ("J1.4", "U1.3"),
            "USB2_DP": ("J2.1", "U1.4"),
            "USB2_DM": ("J2.2", "U1.5"),
            "DEVICE_GND": ("J2.4", "U1.6"),
        },
        component_symbols={
            "J1": "Connector:USB_A",
            "J2": "Connector:USB_A",
            "U1": "Synthetic:UsbIsolator",
        },
        pin_functions={
            "J1.1": "D+",
            "J1.2": "D-",
            "J1.4": "GND",
            "J2.1": "D+",
            "J2.2": "D-",
            "J2.4": "GND",
            "U1.1": "USB1D+",
            "U1.2": "USB1D-",
            "U1.3": "AGND",
            "U1.4": "USB2D+",
            "U1.5": "USB2D-",
            "U1.6": "GND2",
        },
        pin_electrical_types={
            "J1.1": "passive",
            "J1.2": "passive",
            "J1.4": "passive",
            "J2.1": "passive",
            "J2.2": "passive",
            "J2.4": "passive",
            "U1.1": "input",
            "U1.2": "input",
            "U1.3": "power_in",
            "U1.4": "input",
            "U1.5": "input",
            "U1.6": "power_in",
        },
        component_pin_numbers={
            "J1": ("1", "2", "4"),
            "J2": ("1", "2", "4"),
            "U1": ("1", "2", "3", "4", "5", "6"),
        },
    )

    assert usb_peer_reference_reviews(observed) == ()
    report = lint_report(observed)
    assert RULE_ID not in {item.rule_id for item in report.findings}
    coverage = report.usb_peer_reference_coverage
    assert coverage is not None
    assert coverage.status == "INCOMPLETE"
    assert coverage.recognized_connector_group_count == 2
    assert coverage.supported_connector_group_count == 2
    assert coverage.recognized_phy_group_count == 2
    assert coverage.supported_phy_group_count == 0
    assert coverage.incomplete_group_count == 2
    assert coverage.supported_data_path_count == 0
    assert coverage.candidate_group_count == 0
    assert coverage.path_entries == ()
    assert tuple(
        (item.endpoint_role, item.reference, item.port_group, item.disposition)
        for item in coverage.endpoint_groups or ()
    ) == (
        ("connector", "J1", None, "SUPPORTED"),
        ("connector", "J2", None, "SUPPORTED"),
        ("phy", "U1", "1", "INCOMPLETE"),
        ("phy", "U1", "2", "INCOMPLETE"),
    )
