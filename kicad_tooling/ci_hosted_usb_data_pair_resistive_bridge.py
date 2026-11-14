"""Digest-pinned native fixture adapter for USB data-pair resistor review."""

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

USB_DATA_PAIR_RESISTIVE_BRIDGE_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS
USB_DATA_PAIR_RESISTIVE_BRIDGE_EXPECTATION = BusSignalPairFixtureExpectation(
    protocol="usb",
    pair_name="dp-dm-resistive-bridge",
    rule_id="bus.usb_dp_dm_resistive_bridge",
    fixture_directory="usb-dp-dm-resistive-bridge",
    pin_functions=(
        ExpectedPinFunction(reference="U1.1", function="DP"),
        ExpectedPinFunction(reference="U1.2", function="DM"),
        ExpectedPinFunction(reference="R1.1", function="1"),
        ExpectedPinFunction(reference="R1.2", function="2"),
    ),
    fault=SameNetCaseExpectation(
        source_sha256="511276b9f7e82f01c446e9ee05952089084900101de33fe9d843eed97a320f6e",
        net_assignments=(
            ExpectedNetAssignment(name="USB_DP", pins=("R1.1", "U1.1")),
            ExpectedNetAssignment(name="USB_DM", pins=("R1.2", "U1.2")),
        ),
        subjects=("U1: USB data port unindexed D+/D- nets USB_DP and USB_DM are bridged by R1",),
    ),
    control=SameNetCaseExpectation(
        source_sha256="3cf34e863b751d9ec713775ca51732bda4c60829e47d63e1c4b148b709f3bf3d",
        net_assignments=(
            ExpectedNetAssignment(name="AUX_A", pins=("R1.1",)),
            ExpectedNetAssignment(name="AUX_B", pins=("R1.2",)),
            ExpectedNetAssignment(name="USB_DM", pins=("U1.2",)),
            ExpectedNetAssignment(name="USB_DP", pins=("U1.1",)),
        ),
        subjects=(),
    ),
)


def usb_data_pair_resistive_bridge_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Check native pin/net evidence and repeatability for the fault and control."""
    bus_signal_pair_topology_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        fixture=USB_DATA_PAIR_RESISTIVE_BRIDGE_EXPECTATION,
        event_prefix="usb-dp-dm-resistive-bridge-fixture",
    )
