"""Focused checks for authored USB topology maps used by native fixture lanes."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_usb_requirements import usb_data_path_requirements

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def test_hosted_usb_topology_maps_cover_native_fixture_cases() -> None:
    requirements = usb_data_path_requirements()

    assert set(requirements) == {
        "integrated-direct",
        "external-series",
        "external-series-reference-bond-control",
        "external-series-reference-fault",
        "external-bypass",
        "peer-reference-fault",
        "peer-reference-control",
        "usb-c-peer-reference-fault",
        "usb-c-peer-reference-control",
        "usb-multiport-peer-reference-fault",
        "usb-multiport-peer-reference-control",
        "intentional-isolation-boundary",
        "inline-component-ground-fault",
        "inline-component-control",
        "inline-component-peer-reference-fault",
        "inline-component-peer-reference-map-control",
        "inline-component-peer-reference-bond-fault",
        "inline-component-peer-reference-bond-control",
        "protection-shunt-split-reference",
        "protection-shunt-common-reference",
        "protection-shunt-pin-fault",
    }

    bonded = requirements["external-series-reference-bond-control"].interfaces[0]
    assert bonded.reference_policy == "bonded"
    assert bonded.reference_bond is not None
    assert bonded.reference_bond.reference == "R3"

    usb_c = requirements["usb-c-peer-reference-control"].interfaces[0]
    assert usb_c.positive.connector_parallel_pins == ("J1.B6",)
    assert usb_c.negative.connector_parallel_pins == ("J1.B7",)

    multiport = requirements["usb-multiport-peer-reference-control"].interfaces
    assert tuple(interface.data_port_group for interface in multiport) == ("1", "2")

    inline_peer_fault = requirements["inline-component-peer-reference-fault"].interfaces[0]
    assert inline_peer_fault.reference_policy is None
    assert inline_peer_fault.inline_component.pins[4].net == "BOARD_GND"
    inline_peer_control = requirements["inline-component-peer-reference-map-control"].interfaces[0]
    assert inline_peer_control.reference_policy == "separate_nets"
    inline_peer_bond = requirements["inline-component-peer-reference-bond-control"].interfaces[0]
    assert inline_peer_bond.reference_policy == "bonded"
    assert inline_peer_bond.reference_bond is not None
    assert inline_peer_bond.reference_bond.reference == "R3"

    protection_shunt = requirements["protection-shunt-split-reference"].interfaces[0]
    assert protection_shunt.reference_policy is None
    assert protection_shunt.protection_shunts[0].reference == "U6"
    assert tuple(
        (item.pin, item.line, item.net) for item in protection_shunt.protection_shunts[0].data_pins
    ) == (("U6.1", "D+", "USB_DP"), ("U6.3", "D-", "USB_DM"))
    assert tuple(item.pin for item in protection_shunt.protection_shunts[0].pins) == tuple(
        f"U6.{number}" for number in range(1, 7)
    )
    assert protection_shunt.protection_shunts[0].pins[-1].disposition == "unconnected"
    protection_shunt_common = requirements["protection-shunt-common-reference"].interfaces[0]
    assert protection_shunt_common.reference_policy == "common_net"
    assert (
        requirements["protection-shunt-pin-fault"]
        == requirements["protection-shunt-split-reference"]
    )


def test_protection_shunt_native_fixture_sources_match_pinned_hashes() -> None:
    fixture_root = Path(__file__).parent / "fixtures/design_lint/usb-data-path-native"
    expected_hashes = {
        "protection-shunt-split-reference.kicad_sch": "315b0318669d9cadeb28fcfe2ec549100f9ac5c10555e3828619e379770d287b",
        "protection-shunt-common-reference.kicad_sch": "0d2d087d73bc68cae85b2446cf2f8432ed07296d999fd4a588d53a7470b43ec5",
        "protection-shunt-pin-fault.kicad_sch": "27a95acc910f2b379a3c1158c0dcb3bf7ca1faf644564d6d8b7811433838cc61",
    }

    assert {
        name: hashlib.sha256((fixture_root / name).read_bytes()).hexdigest()
        for name in expected_hashes
    } == expected_hashes
