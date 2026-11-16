"""Digest-pinned native lane for JTAG TCK/TMS same-net review."""

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

JTAG_CLOCK_MODE_SAME_NET_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS
JTAG_CLOCK_MODE_SAME_NET_EXPECTATION = BusSignalPairFixtureExpectation(
    protocol="jtag",
    pair_name="tck-tms",
    rule_id="bus.jtag_tck_tms_same_net",
    fixture_directory="jtag-clock-mode-same-net",
    pin_functions=(
        ExpectedPinFunction(reference="U1.1", function="JTAG_TCK"),
        ExpectedPinFunction(reference="U1.2", function="JTAG_TMS"),
        ExpectedPinFunction(reference="U1.3", function="JTAG_TDI"),
        ExpectedPinFunction(reference="U1.4", function="JTAG_TDO"),
    ),
    fault=SameNetCaseExpectation(
        source_sha256="7b4cf2b56449a51ea5409de6091787eddcc7d0e83fa099313678b98e6f9c05b2",
        net_assignments=(
            ExpectedNetAssignment(name="JTAG_CLOCK_MODE_SHARED", pins=("U1.1", "U1.2")),
            ExpectedNetAssignment(name="JTAG_TDI_U1", pins=("U1.3",)),
            ExpectedNetAssignment(name="JTAG_TDO_U1", pins=("U1.4",)),
        ),
        subjects=("U1: JTAG TCK U1.1 and TMS U1.2 share JTAG_CLOCK_MODE_SHARED",),
    ),
    control=SameNetCaseExpectation(
        source_sha256="963cb4909133eb49b80c1dddeb8fa525ee5e56935687901b8870194401eb9fe4",
        net_assignments=(
            ExpectedNetAssignment(name="JTAG_TCK_U1", pins=("U1.1",)),
            ExpectedNetAssignment(name="JTAG_TMS_U1", pins=("U1.2",)),
            ExpectedNetAssignment(name="JTAG_TDI_U1", pins=("U1.3",)),
            ExpectedNetAssignment(name="JTAG_TDO_U1", pins=("U1.4",)),
        ),
        subjects=(),
    ),
)


def jtag_clock_mode_same_net_fixture_lane(
    root: Path,
    *,
    version: str,
    image: str,
    log: HostedLog,
) -> None:
    """Repeat native exports and compare JTAG TCK/TMS same-net candidates."""
    bus_signal_pair_same_net_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        fixture=JTAG_CLOCK_MODE_SAME_NET_EXPECTATION,
    )
