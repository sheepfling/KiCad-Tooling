"""Digest-pinned native fixtures for same-role serial endpoint wiring."""

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

SERIAL_ENDPOINT_ROLE_COLLISION_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS
SERIAL_ENDPOINT_ROLE_COLLISION_EXPECTATION = BusSignalPairFixtureExpectation(
    protocol="usb",
    pair_name="endpoint-role-collision",
    rule_id="bus.serial_endpoint_role_collision",
    fixture_directory="serial-endpoint-role-collision",
    pin_functions=(
        ExpectedPinFunction(reference="J1.1", function="UART1_RX"),
        ExpectedPinFunction(reference="J1.2", function="UART1_TX"),
        ExpectedPinFunction(reference="U1.1", function="UART1_TX"),
        ExpectedPinFunction(reference="U1.2", function="UART1_RX"),
    ),
    fault=SameNetCaseExpectation(
        source_sha256="a63ea158cb5f8adc9d0a95328442eded39f8e0e770e58de3f56f73adc86fdb6b",
        net_assignments=(
            ExpectedNetAssignment(name="UART_TX", pins=("J1.2", "U1.1")),
            ExpectedNetAssignment(name="UART_RX", pins=("J1.1", "U1.2")),
        ),
        subjects=(
            "J1/U1: serial RX functions share UART_RX",
            "J1/U1: serial TX functions share UART_TX",
        ),
    ),
    control=SameNetCaseExpectation(
        source_sha256="56864303858fc7b1cf512fb4d3165343edb9a496e83c0e7e814d8b666a18b44e",
        net_assignments=(
            ExpectedNetAssignment(name="UART_TX", pins=("J1.1", "U1.1")),
            ExpectedNetAssignment(name="UART_RX", pins=("J1.2", "U1.2")),
        ),
        subjects=(),
    ),
)


def serial_endpoint_role_collision_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Verify repeatable native exports for crossed-role and valid UART pins."""
    bus_signal_pair_topology_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        fixture=SERIAL_ENDPOINT_ROLE_COLLISION_EXPECTATION,
        event_prefix="serial-endpoint-role-collision-fixture",
    )
