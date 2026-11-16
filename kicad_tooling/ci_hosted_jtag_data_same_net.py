"""Digest-pinned native lane for JTAG TDI/TDO same-net review."""

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

JTAG_DATA_SAME_NET_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS
JTAG_DATA_SAME_NET_EXPECTATION = BusSignalPairFixtureExpectation(
    protocol="jtag",
    pair_name="tdi-tdo",
    rule_id="bus.jtag_tdi_tdo_same_net",
    fixture_directory="jtag-data-same-net",
    pin_functions=(
        ExpectedPinFunction(reference="U1.1", function="JTAG_TCK"),
        ExpectedPinFunction(reference="U1.2", function="JTAG_TMS"),
        ExpectedPinFunction(reference="U1.3", function="JTAG_TDI"),
        ExpectedPinFunction(reference="U1.4", function="JTAG_TDO"),
    ),
    fault=SameNetCaseExpectation(
        source_sha256="50b3259121e4ac74c2db976d3f0ed3adf680969cccb5025ab89343293e1ecbbf",
        net_assignments=(
            ExpectedNetAssignment(name="JTAG_TCK_U1", pins=("U1.1",)),
            ExpectedNetAssignment(name="JTAG_TMS_U1", pins=("U1.2",)),
            ExpectedNetAssignment(name="JTAG_DATA_SHARED", pins=("U1.3", "U1.4")),
        ),
        subjects=("U1: JTAG TDI U1.3 and TDO U1.4 share JTAG_DATA_SHARED",),
    ),
    control=SameNetCaseExpectation(
        source_sha256="4ff3cf87d3c41385495317d0a7bb29fa568701568fa068722339779ca276e83c",
        net_assignments=(
            ExpectedNetAssignment(name="JTAG_TCK_U1", pins=("U1.1",)),
            ExpectedNetAssignment(name="JTAG_TMS_U1", pins=("U1.2",)),
            ExpectedNetAssignment(name="JTAG_TDI_U1", pins=("U1.3",)),
            ExpectedNetAssignment(name="JTAG_TDO_U1", pins=("U1.4",)),
        ),
        subjects=(),
    ),
)


def jtag_data_same_net_fixture_lane(
    root: Path,
    *,
    version: str,
    image: str,
    log: HostedLog,
) -> None:
    """Repeat native exports and compare JTAG TDI/TDO same-net candidates."""
    bus_signal_pair_same_net_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        fixture=JTAG_DATA_SAME_NET_EXPECTATION,
    )
