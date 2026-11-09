"""Digest-pinned native fixture lane for I2S clock/data same-net review."""

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

I2S_CLOCK_DATA_SAME_NET_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS
I2S_CLOCK_DATA_SAME_NET_EXPECTATION = BusSignalPairFixtureExpectation(
    protocol="i2s",
    pair_name="bclk-data",
    rule_id="bus.i2s_clock_data_same_net",
    fixture_directory="i2s-clock-data-same-net",
    pin_functions=(
        ExpectedPinFunction(reference="U1.1", function="I2S_BCLK"),
        ExpectedPinFunction(reference="U1.3", function="I2S_DATA"),
    ),
    fault=SameNetCaseExpectation(
        source_sha256="eef6552c8ff6362b2bdc86e10b1ca2c541894102fab993c42fe0011813a97d83",
        net_assignments=(ExpectedNetAssignment(name="I2S_SHARED", pins=("U1.1", "U1.3")),),
        subjects=("U1: I2S bit clock U1.1 and serial data U1.3 share I2S_SHARED",),
    ),
    control=SameNetCaseExpectation(
        source_sha256="5f6dab83fbd594418b23b8c086c074e48ef1f4663d7cf0fb0140b75e3fa849f7",
        net_assignments=(
            ExpectedNetAssignment(name="I2S_BCLK", pins=("U1.1",)),
            ExpectedNetAssignment(name="I2S_DATA", pins=("U1.3",)),
        ),
        subjects=(),
    ),
)


def i2s_clock_data_same_net_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Check repeatable native netlists/ERC and the I2S clock/data review result."""
    bus_signal_pair_same_net_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        fixture=I2S_CLOCK_DATA_SAME_NET_EXPECTATION,
    )
