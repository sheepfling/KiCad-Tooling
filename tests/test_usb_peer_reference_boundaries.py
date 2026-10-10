"""Focused USB connector-to-PHY reference lint regressions."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract
from kicad_tooling.hwrepo.usb_peer_reference_review import usb_peer_reference_reviews
from tests.usb_peer_reference_support import (
    RULE_ID,
    lint_report,
    usb_peer_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def test_input_order_is_stable_and_commoning_clears_only_this_review() -> None:
    observed = usb_peer_netlist()
    reordered = observed.model_copy(
        update={
            "components": dict(reversed(tuple(observed.components.items()))),
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(observed.pin_electrical_types.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
        }
    )
    assert (lint_report(observed)) == (lint_report(reordered))
    commoned = observed.model_copy(
        update={
            "nets": {
                **{
                    name: pins
                    for name, pins in observed.nets.items()
                    if name not in {"USB_GND", "BOARD_GND"}
                },
                "BOARD_GND": ("J1.3", "U1.3"),
            }
        }
    )
    commoned_report = lint_report(commoned)
    assert (RULE_ID) not in ({item.rule_id for item in commoned_report.findings})


def test_extra_data_peers_and_ambiguous_metadata_fail_closed() -> None:
    assert (usb_peer_reference_reviews(usb_peer_netlist(dnp=("U1",)))) == (())
    assert (usb_peer_reference_reviews(usb_peer_netlist(incomplete=True))) == (())
    assert (usb_peer_reference_reviews(usb_peer_netlist(extra_positive_pin=True))) == (())
    explicit_suffix = usb_peer_netlist()
    explicit_suffix_functions = dict(explicit_suffix.pin_functions)
    explicit_suffix_functions["J1.3"] = "GND_A"
    explicit_suffix_functions["U1.3"] = "VSSA1"
    explicit_suffix = explicit_suffix.model_copy(
        update={"pin_functions": explicit_suffix_functions}
    )
    assert (len(usb_peer_reference_reviews(explicit_suffix))) == (1)
    shield_only = usb_peer_netlist()
    shield_functions = dict(shield_only.pin_functions)
    shield_functions["J1.3"] = "GND_SHIELD"
    shield_only = shield_only.model_copy(update={"pin_functions": shield_functions})
    assert (usb_peer_reference_reviews(shield_only)) == (())


def test_phy_with_multiple_reference_domains_is_outside_predicate() -> None:
    observed = usb_peer_netlist()
    nets = dict(observed.nets)
    nets["ISOLATED_GND"] = ("U1.5",)
    functions = dict(observed.pin_functions)
    functions["U1.5"] = "GND"
    electrical_types = dict(observed.pin_electrical_types)
    electrical_types["U1.5"] = "power_in"
    pin_numbers = dict(observed.component_pin_numbers)
    pin_numbers["U1"] = (*pin_numbers["U1"], "5")
    isolated_reference = observed.model_copy(
        update={
            "nets": nets,
            "pin_functions": functions,
            "pin_electrical_types": electrical_types,
            "component_pin_numbers": pin_numbers,
        }
    )

    assert (usb_peer_reference_reviews(isolated_reference)) == (())
    report = lint_report(isolated_reference)
    assert (RULE_ID) not in ({item.rule_id for item in report.findings})


def test_isolator_mediated_usb_path_is_not_traced_across_domains() -> None:
    observed = NetlistContract(
        components={
            "J1": ComponentContract(value="Synthetic USB connector", footprint="Synthetic:J"),
            "U1": ComponentContract(value="Synthetic USB isolator", footprint="Synthetic:SOIC"),
            "U2": ComponentContract(value="Synthetic USB PHY", footprint="Synthetic:QFN"),
        },
        nets={
            "HOST_DP": ("J1.1", "U1.1"),
            "HOST_DM": ("J1.2", "U1.2"),
            "HOST_GND": ("J1.3", "U1.5"),
            "DEVICE_DP": ("U1.3", "U2.1"),
            "DEVICE_DM": ("U1.4", "U2.2"),
            "DEVICE_GND": ("U1.6", "U2.3"),
            "+3V3": ("U2.4",),
        },
        component_symbols={
            "J1": "Connector:USB_A",
            "U1": "Synthetic:UsbIsolator",
            "U2": "Synthetic:UsbPhy",
        },
        pin_functions={
            "J1.1": "D+",
            "J1.2": "D-",
            "J1.3": "GND",
            "J1.4": "VBUS",
            "U1.1": "DP1",
            "U1.2": "DM1",
            "U1.3": "DP2",
            "U1.4": "DM2",
            "U1.5": "GND1",
            "U1.6": "GND2",
            "U2.1": "D+",
            "U2.2": "D-",
            "U2.3": "GND",
            "U2.4": "VDD",
        },
        pin_electrical_types={
            "J1.1": "passive",
            "J1.2": "passive",
            "J1.3": "passive",
            "J1.4": "passive",
            "U1.1": "bidirectional",
            "U1.2": "bidirectional",
            "U1.3": "bidirectional",
            "U1.4": "bidirectional",
            "U1.5": "power_in",
            "U1.6": "power_in",
            "U2.1": "bidirectional",
            "U2.2": "bidirectional",
            "U2.3": "power_in",
            "U2.4": "power_in",
        },
        component_pin_numbers={
            "J1": ("1", "2", "3", "4"),
            "U1": ("1", "2", "3", "4", "5", "6"),
            "U2": ("1", "2", "3", "4"),
        },
    )

    assert (usb_peer_reference_reviews(observed)) == (())
    report = lint_report(observed)
    assert (RULE_ID) not in ({item.rule_id for item in report.findings})
    coverage = report.usb_peer_reference_coverage
    assert (coverage) is not None
    assert coverage is not None
    assert (coverage.status) == ("INCOMPLETE")
    assert (coverage.recognized_connector_group_count) == (1)
    assert (coverage.recognized_phy_group_count) == (3)
    assert (coverage.supported_phy_group_count) == (1)
    assert (coverage.incomplete_group_count) == (2)
    assert (coverage.supported_data_path_count) == (0)


def test_multi_pin_protection_array_and_ferrite_remain_unsupported() -> None:
    base = usb_peer_netlist()
    protected = base.model_copy(
        update={
            "components": {
                **base.components,
                "U6": ComponentContract(
                    value="Synthetic USB protection array", footprint="Synthetic:SC70"
                ),
                "FB2": ComponentContract(
                    value="Synthetic reference ferrite", footprint="Synthetic:0603"
                ),
            },
            "nets": {
                "+3V3": ("U1.4",),
                "USB_DP": ("J1.1", "U6.1"),
                "USB_DP_PROTECTED": ("U6.2", "U1.1"),
                "USB_DM": ("J1.2", "U6.3"),
                "USB_DM_PROTECTED": ("U6.4", "U1.2"),
                "USB_GND": ("J1.3", "U6.5", "FB2.1"),
                "BOARD_GND": ("U1.3", "FB2.2"),
            },
            "component_symbols": {
                **base.component_symbols,
                "U6": "Synthetic:UsbProtectionArray",
                "FB2": "Device:L",
            },
            "pin_functions": {
                **base.pin_functions,
                "U6.1": "LINE1_IN",
                "U6.2": "LINE1_OUT",
                "U6.3": "LINE2_IN",
                "U6.4": "LINE2_OUT",
                "U6.5": "GND",
                "FB2.1": "~",
                "FB2.2": "~",
            },
            "pin_electrical_types": {
                **base.pin_electrical_types,
                "U6.1": "passive",
                "U6.2": "passive",
                "U6.3": "passive",
                "U6.4": "passive",
                "U6.5": "power_in",
                "FB2.1": "passive",
                "FB2.2": "passive",
            },
            "component_pin_numbers": {
                **base.component_pin_numbers,
                "U6": ("1", "2", "3", "4", "5"),
                "FB2": ("1", "2"),
            },
        }
    )

    report = lint_report(protected)
    coverage = report.usb_peer_reference_coverage
    assert coverage is not None
    assert coverage.status == "NO_SUPPORTED_PEER_PATHS"
    assert coverage.recognized_connector_group_count == 1
    assert coverage.supported_connector_group_count == 1
    assert coverage.recognized_phy_group_count == 1
    assert coverage.supported_phy_group_count == 1
    assert coverage.incomplete_group_count == 0
    assert coverage.supported_data_path_count == 0
    assert coverage.common_reference_path_count == 0
    assert coverage.separate_reference_path_count == 0
    assert coverage.candidate_group_count == 0
    assert coverage.path_entries == ()
    assert RULE_ID not in {finding.rule_id for finding in report.findings}

    control = lint_report(
        usb_peer_netlist(connector_reference_net="BOARD_GND", phy_reference_net="BOARD_GND")
    )
    control_coverage = control.usb_peer_reference_coverage
    assert control_coverage is not None
    assert control_coverage.status == "EVALUATED"
    assert control_coverage.common_reference_path_count == 1
    assert control_coverage.candidate_group_count == 0
    assert RULE_ID not in {finding.rule_id for finding in control.findings}
