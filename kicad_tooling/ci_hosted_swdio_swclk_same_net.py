"""Digest-pinned native fixture lane for SWDIO/SWCLK same-net review."""

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

SWD_SIGNAL_SAME_NET_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS
SWD_SIGNAL_SAME_NET_EXPECTATION = BusSignalPairFixtureExpectation(
    protocol="swd",
    pair_name="swdio-swclk",
    rule_id="bus.swdio_swclk_same_net",
    fixture_directory="swd-signal-same-net",
    pin_functions=(
        ExpectedPinFunction(reference="U1.5", function="SYS_JTMS-SWDIO"),
        ExpectedPinFunction(reference="U1.6", function="SYS_JTCK-SWCLK"),
    ),
    fault=SameNetCaseExpectation(
        source_sha256="af9f943e6ad53f495ff790b8c41b01812aa1924e3eb5afc33e762151c86ace24",
        net_assignments=(ExpectedNetAssignment(name="SWD_SHARED", pins=("U1.5", "U1.6")),),
        subjects=("U1: SWDIO U1.5 and SWCLK U1.6 share SWD_SHARED",),
    ),
    control=SameNetCaseExpectation(
        source_sha256="a0b087f03a3aa5e422b638ca01cb17b1c984216d9ccf29815c9fbbd09939d7dc",
        net_assignments=(
            ExpectedNetAssignment(name="SWD_DATA", pins=("U1.5",)),
            ExpectedNetAssignment(name="SWD_CLOCK", pins=("U1.6",)),
        ),
        subjects=(),
    ),
)


def swdio_swclk_same_net_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Check repeated native exports, ERC, and the SWD same-net review result."""
    bus_signal_pair_same_net_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        fixture=SWD_SIGNAL_SAME_NET_EXPECTATION,
    )
