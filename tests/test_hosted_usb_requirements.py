"""Focused checks for authored USB topology maps used by native fixture lanes."""

from __future__ import annotations

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
