"""Exact-version native fixture adapter for connector-only I2C pull-up review."""

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

I2C_MISSING_PULLUP_CONNECTOR_EXPECTATION = BusSignalPairFixtureExpectation(
    protocol="i2c",
    pair_name="missing-pullup-connector",
    rule_id="bus.i2c_missing_pullup",
    fixture_directory="i2c-missing-pullup-connector-native",
    pin_functions=(
        ExpectedPinFunction(reference="J1.1", function="SDA"),
        ExpectedPinFunction(reference="J1.2", function="SCL"),
        ExpectedPinFunction(reference="R1.1", function="1"),
        ExpectedPinFunction(reference="R1.2", function="2"),
        ExpectedPinFunction(reference="R2.1", function="1"),
        ExpectedPinFunction(reference="R2.2", function="2"),
    ),
    fault=SameNetCaseExpectation(
        source_sha256="3051b1072f50b8afd38fa82a7dc67985750cc7204819f6fac1aa84df2ee6cd9b",
        net_assignments=(
            ExpectedNetAssignment(name="+3V3", pins=("R1.2", "R2.2")),
            ExpectedNetAssignment(name="I2C_SCL", pins=("J1.2", "R2.1")),
            ExpectedNetAssignment(name="I2C_SDA", pins=("J1.1", "R1.1")),
        ),
        subjects=("SDA I2C_SDA / SCL I2C_SCL",),
    ),
    control=SameNetCaseExpectation(
        source_sha256="36d766c8293e5a865e8ec006022297e738be3404ec2cdaff42259cafc9f839a6",
        net_assignments=(
            ExpectedNetAssignment(name="+3V3", pins=("R1.2", "R2.2")),
            ExpectedNetAssignment(name="I2C_SCL", pins=("J1.2", "R2.1")),
            ExpectedNetAssignment(name="I2C_SDA", pins=("J1.1", "R1.1")),
        ),
        subjects=(),
    ),
)


def i2c_missing_pullup_connector_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Check connector-only I2C pull-up fault/control exports on pinned KiCad."""
    if (version, image) not in KICAD_10_NATIVE_TOOLCHAINS:
        raise ValueError(f"Connector-only I2C pull-up fixtures do not cover KiCad {version}")
    bus_signal_pair_topology_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        fixture=I2C_MISSING_PULLUP_CONNECTOR_EXPECTATION,
        event_prefix="i2c-missing-pullup-connector-fixture",
    )
