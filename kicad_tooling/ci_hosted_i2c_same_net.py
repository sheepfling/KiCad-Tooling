"""Digest-pinned native fixture adapter for I2C SDA/SCL same-net review."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_bus_signal_pair_models import (
    BusSignalPairFixtureExpectation,
    ExpectedNetAssignment,
    ExpectedPinFunction,
    SameNetCaseExpectation,
)
from .ci_hosted_bus_signal_pair_same_net import bus_signal_pair_same_net_fixture_lane
from .ci_hosted_i2c_native import I2C_NATIVE_TOOLCHAINS
from .ci_hosted_support import HostedLog

I2C_SIGNAL_SAME_NET_EXPECTATION = BusSignalPairFixtureExpectation(
    protocol="i2c",
    pair_name="sda-scl",
    rule_id="bus.i2c_sda_scl_same_net",
    fixture_directory="i2c-sda-scl-same-net",
    pin_functions=(
        ExpectedPinFunction(reference="U1.1", function="SDA"),
        ExpectedPinFunction(reference="U1.2", function="SCL"),
    ),
    fault=SameNetCaseExpectation(
        source_sha256="e45583f123b62fe0769d19e5ffd08200510b9abb44afb97d6a8fc269ed3e84b6",
        net_assignments=(ExpectedNetAssignment(name="I2C_SHARED", pins=("U1.1", "U1.2")),),
        subjects=("U1: I2C SDA/SCL pins share I2C_SHARED",),
    ),
    control=SameNetCaseExpectation(
        source_sha256="1fd6caf4f272e3e492b012c01dc645f1b8077ecf127e2dd6569c45b147aaf523",
        net_assignments=(
            ExpectedNetAssignment(name="I2C_SDA", pins=("U1.1",)),
            ExpectedNetAssignment(name="I2C_SCL", pins=("U1.2",)),
        ),
        subjects=(),
    ),
)


def i2c_sda_scl_same_net_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Check repeatable native exports and I2C same-net review evidence."""
    if (version, image) not in I2C_NATIVE_TOOLCHAINS:
        raise ValueError(f"I2C same-net fixtures do not cover KiCad {version} with this image")
    bus_signal_pair_same_net_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        fixture=I2C_SIGNAL_SAME_NET_EXPECTATION,
    )
