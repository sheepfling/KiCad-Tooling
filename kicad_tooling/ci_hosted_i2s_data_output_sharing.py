"""Digest-pinned native fixture lane for I2S data-output sharing review."""

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

I2S_DATA_OUTPUT_SHARING_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS
I2S_DATA_OUTPUT_SHARING_EXPECTATION = BusSignalPairFixtureExpectation(
    protocol="i2s",
    pair_name="data-output-sharing",
    rule_id="bus.i2s_data_outputs_share_net",
    fixture_directory="i2s-data-output-sharing",
    pin_functions=(
        ExpectedPinFunction(reference="U1.1", function="I2S_BCLK"),
        ExpectedPinFunction(reference="U1.3", function="SDOUT"),
        ExpectedPinFunction(reference="U2.1", function="I2S_BCLK"),
        ExpectedPinFunction(reference="U2.3", function="SDOUT"),
    ),
    fault=SameNetCaseExpectation(
        source_sha256="a18aa0c56446bfa35874c1aa1e555d2a5f152522bb36d1eab552c291ef4e9f73",
        net_assignments=(
            ExpectedNetAssignment(name="I2S_BCLK", pins=("U1.1", "U2.1")),
            ExpectedNetAssignment(name="I2S_DATA_SHARED", pins=("U1.3", "U2.3")),
        ),
        subjects=("U1, U2: I2S data-output pins share I2S_DATA_SHARED",),
    ),
    control=SameNetCaseExpectation(
        source_sha256="0f05fe6c579a4b8950bb9e932f77baacd28046a9f2bb3eef607e1482d5c16528",
        net_assignments=(
            ExpectedNetAssignment(name="I2S_BCLK", pins=("U1.1", "U2.1")),
            ExpectedNetAssignment(name="U1_I2S_DATA", pins=("U1.3",)),
            ExpectedNetAssignment(name="U2_I2S_DATA", pins=("U2.3",)),
        ),
        subjects=(),
    ),
)


def i2s_data_output_sharing_fixture_lane(
    root: Path,
    *,
    version: str,
    image: str,
    log: HostedLog,
) -> None:
    """Repeat native exports and compare the I2S output-sharing candidate."""
    bus_signal_pair_same_net_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        fixture=I2S_DATA_OUTPUT_SHARING_EXPECTATION,
    )
