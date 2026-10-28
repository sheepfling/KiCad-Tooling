"""Digest-pinned native fixture adapter for USB-C CC1/CC2 same-net review."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_bus_signal_pair_models import (
    BusSignalPairFixtureExpectation,
    ExpectedNetAssignment,
    ExpectedPinFunction,
    SameNetCaseExpectation,
)
from .ci_hosted_bus_signal_pair_same_net import bus_signal_pair_same_net_fixture_lane
from .ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS
from .ci_hosted_support import HostedLog

USB_C_CC_SAME_NET_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS
USB_C_CC_SAME_NET_EXPECTATION = BusSignalPairFixtureExpectation(
    protocol="usb-c",
    pair_name="cc1-cc2",
    rule_id="bus.usb_c_cc_same_net",
    fixture_directory="usb-c-cc-same-net",
    pin_functions=(
        ExpectedPinFunction(reference="J1.1", function="CC1"),
        ExpectedPinFunction(reference="J1.2", function="CC2"),
        ExpectedPinFunction(reference="U1.1", function="CC1"),
        ExpectedPinFunction(reference="U1.2", function="CC2"),
    ),
    fault=SameNetCaseExpectation(
        source_sha256="621079d2d0e3fc5d782a3c6906545beca838857d4fcb3b0c2d500527b72d7c3c",
        net_assignments=(
            ExpectedNetAssignment(name="CC_SHARED", pins=("J1.1", "J1.2", "U1.1", "U1.2")),
        ),
        subjects=("J1: USB-C CC1/CC2 pins share CC_SHARED",),
    ),
    control=SameNetCaseExpectation(
        source_sha256="1dd9812937047037d7f66d40eb7c9249027a61ccedb7edf140702476b4713d2c",
        net_assignments=(
            ExpectedNetAssignment(name="CC1_BUS", pins=("J1.1", "U1.1")),
            ExpectedNetAssignment(name="CC2_BUS", pins=("J1.2", "U1.2")),
        ),
        subjects=(),
    ),
)


def usb_c_cc_same_net_fixture_lane(root: Path, *, version: str, image: str, log: HostedLog) -> None:
    """Check repeatable native exports and USB-C CC pin review evidence."""
    bus_signal_pair_same_net_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        fixture=USB_C_CC_SAME_NET_EXPECTATION,
    )
