"""Digest-pinned native I3C partially open signal-pair fixture lane."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS
from .ci_hosted_named_rail_fixtures import named_rail_fixture_lane
from .ci_hosted_support import HostedLog

I3C_UNCONNECTED_PIN_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS


def i3c_unconnected_pin_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Repeat native netlist/ERC exports and check the one-sided-open candidate."""
    named_rail_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        protocol="i3c",
        feature="unconnected-pin",
        rule_id="bus.i3c_unconnected_pin",
        fixture_directory="i3c-unconnected-pin-native",
        source_hashes={
            "control": "2e6219d860a33e9ccd54078d86b7c4afd50f3b5955da6750ba9ca4f6519768c3",
            "fault": "6c97dd20de08edc4bd6f0a5a23529faa15296632f4cdb8ad983399bc888f9fd3",
        },
        expected_nets={
            "control": {"I3C_SDA": ("U1.1",), "I3C_SCL": ("U1.2",)},
            "fault": {"I3C_SDA": ("U1.1",)},
        },
        expected_subjects={
            "control": (),
            "fault": ("U1.2: I3C1_SCL",),
        },
        expected_pin_functions={"U1.1": "I3C1_SDA", "U1.2": "I3C1_SCL"},
        expected_unconnected_pins={"control": (), "fault": ("U1.2",)},
        stage_prefix_override="i3c-unconnected-pin-fixture",
    )
