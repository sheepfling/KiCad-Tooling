"""Digest-pinned native fixture adapter for USB 2.0 D+/D- same-net review."""

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

USB_DATA_SAME_NET_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS
USB_DATA_SAME_NET_EXPECTATION = BusSignalPairFixtureExpectation(
    protocol="usb",
    pair_name="dp-dm",
    rule_id="bus.usb_dp_dm_same_net",
    fixture_directory="usb-dp-dm-same-net",
    pin_functions=(
        ExpectedPinFunction(reference="U1.1", function="DP"),
        ExpectedPinFunction(reference="U1.2", function="DM"),
    ),
    fault=SameNetCaseExpectation(
        source_sha256="7182133d074e5f28fa7a80b36962ed11b4e659e85e107db9dbc5c708c5110ebe",
        net_assignments=(ExpectedNetAssignment(name="USB_SHARED", pins=("U1.1", "U1.2")),),
        subjects=("U1: USB data port unindexed D+/D- pins share USB_SHARED",),
    ),
    control=SameNetCaseExpectation(
        source_sha256="ac9410b7cade422a635847bae9e1e4a7a57333a7a259756d4aad62afa8d8069e",
        net_assignments=(
            ExpectedNetAssignment(name="USB_DM", pins=("U1.2",)),
            ExpectedNetAssignment(name="USB_DP", pins=("U1.1",)),
        ),
        subjects=(),
    ),
)


def usb_dp_dm_same_net_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Check repeatable native exports and USB same-net review evidence."""
    bus_signal_pair_same_net_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        fixture=USB_DATA_SAME_NET_EXPECTATION,
    )
