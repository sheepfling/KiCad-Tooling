"""Digest-pinned native fixture adapter for I2C resistor-bridge review."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_bus_signal_pair_models import (
    BusSignalPairFixtureExpectation,
    ExpectedNetAssignment,
    ExpectedPinFunction,
    SameNetCaseExpectation,
)
from .ci_hosted_bus_signal_pair_same_net import bus_signal_pair_topology_fixture_lane
from .ci_hosted_i2c_native import I2C_NATIVE_TOOLCHAINS
from .ci_hosted_support import HostedLog

I2C_SDA_SCL_RESISTIVE_BRIDGE_TOOLCHAINS = I2C_NATIVE_TOOLCHAINS
I2C_SDA_SCL_RESISTIVE_BRIDGE_EXPECTATION = BusSignalPairFixtureExpectation(
    protocol="i2c",
    pair_name="sda-scl-resistive-bridge",
    rule_id="bus.i2c_sda_scl_resistive_bridge",
    fixture_directory="i2c-sda-scl-resistive-bridge",
    pin_functions=(
        ExpectedPinFunction(reference="U1.1", function="SDA"),
        ExpectedPinFunction(reference="U1.2", function="SCL"),
        ExpectedPinFunction(reference="R1.1", function="1"),
        ExpectedPinFunction(reference="R1.2", function="2"),
    ),
    fault=SameNetCaseExpectation(
        source_sha256="ba998932f011b666e95f21c4b4645998be840b780073749d5d7c3f2bc480914b",
        net_assignments=(
            ExpectedNetAssignment(name="I2C_SDA", pins=("R1.1", "U1.1")),
            ExpectedNetAssignment(name="I2C_SCL", pins=("R1.2", "U1.2")),
        ),
        subjects=("U1: I2C SDA/SCL nets I2C_SDA and I2C_SCL are bridged by R1",),
    ),
    control=SameNetCaseExpectation(
        source_sha256="a1f6d89697b2727cb836c41687ade71f3e326fe3ae92e78a76b659d2a0520f69",
        net_assignments=(
            ExpectedNetAssignment(name="AUX_A", pins=("R1.1",)),
            ExpectedNetAssignment(name="AUX_B", pins=("R1.2",)),
            ExpectedNetAssignment(name="I2C_SCL", pins=("U1.2",)),
            ExpectedNetAssignment(name="I2C_SDA", pins=("U1.1",)),
        ),
        subjects=(),
    ),
)


def i2c_sda_scl_resistive_bridge_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Check native I2C pin/net evidence and repeatability for both cases."""
    if (version, image) not in I2C_SDA_SCL_RESISTIVE_BRIDGE_TOOLCHAINS:
        raise ValueError(f"I2C resistor bridge fixtures do not cover KiCad {version}")
    bus_signal_pair_topology_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        fixture=I2C_SDA_SCL_RESISTIVE_BRIDGE_EXPECTATION,
        event_prefix="i2c-sda-scl-resistive-bridge-fixture",
    )
