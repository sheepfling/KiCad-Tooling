"""Digest-pinned native fixture adapter for crossed USB-C CC endpoint nets."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_bus_signal_pair_models import (
    BusSignalPairFixtureExpectation,
    ExpectedNetAssignment,
    ExpectedPinFunction,
    SameNetCaseExpectation,
)
from .ci_hosted_bus_signal_pair_same_net import bus_signal_pair_topology_fixture_lane
from .ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS
from .ci_hosted_support import HostedLog

USB_C_CC_ENDPOINT_CROSSED_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS
USB_C_CC_ENDPOINT_CROSSED_EXPECTATION = BusSignalPairFixtureExpectation(
    protocol="usb-c",
    pair_name="cc1-cc2-endpoint-crossed",
    rule_id="bus.usb_c_cc_endpoint_crossed",
    fixture_directory="usb-c-cc-endpoint-crossed",
    pin_functions=(
        ExpectedPinFunction(reference="J1.1", function="CC1"),
        ExpectedPinFunction(reference="J1.2", function="CC2"),
        ExpectedPinFunction(reference="U1.1", function="CC1"),
        ExpectedPinFunction(reference="U1.2", function="CC2"),
    ),
    fault=SameNetCaseExpectation(
        source_sha256="64171977c2fe6012b153a351453a87bdf6122a5a5b95baefab69a14a167a5b4e",
        net_assignments=(
            ExpectedNetAssignment(name="CC1_BUS", pins=("J1.2", "U1.1")),
            ExpectedNetAssignment(name="CC2_BUS", pins=("J1.1", "U1.2")),
        ),
        subjects=("J1/U1: USB-C CC1/CC2 endpoint nets appear crossed",),
    ),
    control=SameNetCaseExpectation(
        source_sha256="9782df476a406bdbb8f353c0b700e7b41e2d34cdd7279497c53685f8b544e7d0",
        net_assignments=(
            ExpectedNetAssignment(name="CC1_BUS", pins=("J1.1", "U1.1")),
            ExpectedNetAssignment(name="CC2_BUS", pins=("J1.2", "U1.2")),
        ),
        subjects=(),
    ),
)


def usb_c_cc_endpoint_crossed_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Verify repeatable native exports for crossed and direct CC mappings."""
    bus_signal_pair_topology_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        fixture=USB_C_CC_ENDPOINT_CROSSED_EXPECTATION,
        event_prefix="usb-c-cc-endpoint-crossed-fixture",
    )
