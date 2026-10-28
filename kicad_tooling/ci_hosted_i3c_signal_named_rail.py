"""Digest-pinned native fixtures for I3C signals assigned to named rails."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS
from .ci_hosted_named_rail_fixtures import named_rail_fixture_lane
from .ci_hosted_support import HostedLog

I3C_SIGNAL_NAMED_RAIL_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS


def i3c_signal_named_rail_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Repeat source-bound exports for I3C SDA/SCL named-rail fixtures."""
    named_rail_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        protocol="i3c",
        feature="signal",
        rule_id="bus.i3c_signal_on_named_rail",
        fixture_directory="i3c-signal-named-rail",
        source_hashes={
            "control": "aa22ae02257335f0bbe756cfaf3b03ed35e86ad9f9b2659d8b54e15fb2b4fca9",
            "fault": "56764b6a7ba59ad5700876bb2a91959c7f7894fea0afdd778689d75beeba0bb4",
        },
        expected_pin_functions={
            "J1.1": "I3C1_SDA",
            "J1.2": "I3C1_SCL",
            "U1.1": "I3C1_SDA",
            "U1.2": "I3C1_SCL",
        },
        expected_nets={
            "fault": {"GND": ("J1.1", "U1.1"), "+3V3": ("J1.2", "U1.2")},
            "control": {
                "I3C1_SDA_BUS": ("J1.1", "U1.1"),
                "I3C1_SCL_BUS": ("J1.2", "U1.2"),
            },
        },
        expected_subjects={
            "fault": (
                "U1.1: I3C SDA on return-like net GND",
                "U1.2: I3C SCL on supply-like net +3V3",
            ),
            "control": (),
        },
    )
