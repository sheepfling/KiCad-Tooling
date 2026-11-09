"""Digest-pinned native fixture lane for I2S clock/frame same-net review."""

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

I2S_CLOCK_FRAME_SAME_NET_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS
I2S_CLOCK_FRAME_SAME_NET_EXPECTATION = BusSignalPairFixtureExpectation(
    protocol="i2s",
    pair_name="bclk-lrclk",
    rule_id="bus.i2s_clock_frame_same_net",
    fixture_directory="i2s-clock-frame-same-net",
    pin_functions=(
        ExpectedPinFunction(reference="U1.1", function="I2S_BCLK"),
        ExpectedPinFunction(reference="U1.2", function="I2S_LRCLK"),
    ),
    fault=SameNetCaseExpectation(
        source_sha256="80dd97e68045c32d750d41108aa3fcb67f21756a9c3a44aedd5772007c2d6cb9",
        net_assignments=(ExpectedNetAssignment(name="I2S_SHARED", pins=("U1.1", "U1.2")),),
        subjects=("U1: I2S bit clock U1.1 and word select U1.2 share I2S_SHARED",),
    ),
    control=SameNetCaseExpectation(
        source_sha256="296e48767b563dfbb8f71e4bde45353c26480fff69293fa8a0e939f13a046ed4",
        net_assignments=(
            ExpectedNetAssignment(name="I2S_BCLK", pins=("U1.1",)),
            ExpectedNetAssignment(name="I2S_LRCLK", pins=("U1.2",)),
        ),
        subjects=(),
    ),
)


def i2s_clock_frame_same_net_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Check repeatable native netlists/ERC and the I2S same-net review result."""
    bus_signal_pair_same_net_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        fixture=I2S_CLOCK_FRAME_SAME_NET_EXPECTATION,
    )
