"""Digest-pinned native fixture lane for shared JTAG TDO outputs."""

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

JTAG_TDO_OUTPUT_SHARING_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS
JTAG_TDO_OUTPUT_SHARING_EXPECTATION = BusSignalPairFixtureExpectation(
    protocol="jtag",
    pair_name="tdo-output-sharing",
    rule_id="bus.jtag_tdo_outputs_share_net",
    fixture_directory="jtag-tdo-output-sharing",
    pin_functions=(
        ExpectedPinFunction(reference="U1.1", function="JTAG_TCK"),
        ExpectedPinFunction(reference="U1.2", function="JTAG_TMS"),
        ExpectedPinFunction(reference="U1.3", function="JTAG_TDI"),
        ExpectedPinFunction(reference="U1.4", function="JTAG_TDO"),
        ExpectedPinFunction(reference="U2.1", function="JTAG_TCK"),
        ExpectedPinFunction(reference="U2.2", function="JTAG_TMS"),
        ExpectedPinFunction(reference="U2.3", function="JTAG_TDI"),
        ExpectedPinFunction(reference="U2.4", function="JTAG_TDO"),
    ),
    fault=SameNetCaseExpectation(
        source_sha256="27780a89a033d3b5c4ca4a1179a14245edc400e96e9776251867926f1b464fc1",
        net_assignments=(
            ExpectedNetAssignment(name="JTAG_TCK_U1", pins=("U1.1",)),
            ExpectedNetAssignment(name="JTAG_TMS_U1", pins=("U1.2",)),
            ExpectedNetAssignment(name="JTAG_TDI_U1", pins=("U1.3",)),
            ExpectedNetAssignment(name="JTAG_TDO_SHARED", pins=("U1.4", "U2.4")),
            ExpectedNetAssignment(name="JTAG_TCK_U2", pins=("U2.1",)),
            ExpectedNetAssignment(name="JTAG_TMS_U2", pins=("U2.2",)),
            ExpectedNetAssignment(name="JTAG_TDI_U2", pins=("U2.3",)),
        ),
        subjects=("U1, U2: JTAG TDO outputs share JTAG_TDO_SHARED",),
    ),
    control=SameNetCaseExpectation(
        source_sha256="5f83444498c05f61cd7e6466203a7df14814eaa2846e05474361f9625fb5e4e5",
        net_assignments=(
            ExpectedNetAssignment(name="JTAG_TCK_U1", pins=("U1.1",)),
            ExpectedNetAssignment(name="JTAG_TMS_U1", pins=("U1.2",)),
            ExpectedNetAssignment(name="JTAG_TDI_U1", pins=("U1.3",)),
            ExpectedNetAssignment(name="JTAG_TDO_U1", pins=("U1.4",)),
            ExpectedNetAssignment(name="JTAG_TCK_U2", pins=("U2.1",)),
            ExpectedNetAssignment(name="JTAG_TMS_U2", pins=("U2.2",)),
            ExpectedNetAssignment(name="JTAG_TDI_U2", pins=("U2.3",)),
            ExpectedNetAssignment(name="JTAG_TDO_U2", pins=("U2.4",)),
        ),
        subjects=(),
    ),
)


def jtag_tdo_output_sharing_fixture_lane(
    root: Path,
    *,
    version: str,
    image: str,
    log: HostedLog,
) -> None:
    """Repeat native exports and compare the JTAG TDO output-sharing candidate."""
    bus_signal_pair_same_net_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        fixture=JTAG_TDO_OUTPUT_SHARING_EXPECTATION,
    )
