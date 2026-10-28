"""Digest-pinned native fixture adapter for RS-485 A/B same-net review."""

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

RS485_AB_SAME_NET_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS
RS485_AB_SAME_NET_EXPECTATION = BusSignalPairFixtureExpectation(
    protocol="rs485",
    pair_name="a-b",
    rule_id="bus.rs485_ab_same_net",
    fixture_directory="rs485-ab-same-net",
    pin_functions=(
        ExpectedPinFunction(reference="U1.1", function="A"),
        ExpectedPinFunction(reference="U1.2", function="B"),
    ),
    fault=SameNetCaseExpectation(
        source_sha256="12df9c40538c819cbd6369cb88f264d4497dff69051e20d3d2c17314bcb13f61",
        net_assignments=(ExpectedNetAssignment(name="AB_SHARED", pins=("U1.1", "U1.2")),),
        subjects=("U1: RS-485 A/B bus pins share AB_SHARED",),
    ),
    control=SameNetCaseExpectation(
        source_sha256="088e4f94449678f4ccb01569d69220dc3c225e533848a8e91a05586d6eac1400",
        net_assignments=(
            ExpectedNetAssignment(name="RS485_A", pins=("U1.1",)),
            ExpectedNetAssignment(name="RS485_B", pins=("U1.2",)),
        ),
        subjects=(),
    ),
)


def rs485_ab_same_net_fixture_lane(root: Path, *, version: str, image: str, log: HostedLog) -> None:
    """Check repeatable native exports and RS-485 A/B same-net evidence."""
    bus_signal_pair_same_net_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        fixture=RS485_AB_SAME_NET_EXPECTATION,
    )
