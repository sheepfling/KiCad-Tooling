"""Digest-pinned native exports for SWD signal named-rail fixtures."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS
from .ci_hosted_named_rail_fixtures import named_rail_fixture_lane
from .ci_hosted_support import HostedLog

SWD_SIGNAL_NAMED_RAIL_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS


def swd_signal_named_rail_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Repeat native exports and relint one SWD signal fault/control pair."""
    named_rail_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        protocol="swd",
        feature="signal",
        rule_id="bus.swd_signal_on_named_rail",
        fixture_directory="swd-signal-named-rail",
        source_hashes={
            "fault": "e62b668c34f6c3a77f7923cb8e494e1f9ca54324131a678188a8fc5dca70bc3b",
            "control": "29ee2641ec06a7d7ec4b120d4e54007c3c3cdee5cbefdc9061468e08c0a22699",
        },
        expected_pin_functions={
            "U1.1": "SYS_JTMS-SWDIO",
            "U1.2": "SYS_JTCK-SWCLK",
            "U1.3": "SWO",
            "U1.4": "nRESET",
        },
        expected_nets={
            "fault": {
                "GND": ("U1.1",),
                "SYS_JTCK-SWCLK": ("U1.2",),
                "+3V3": ("U1.3",),
                "+5V": ("U1.4",),
            },
            "control": {
                "SYS_JTMS-SWDIO": ("U1.1",),
                "SYS_JTCK-SWCLK": ("U1.2",),
                "SWO_TRACE": ("U1.3",),
                "nRESET_LINE": ("U1.4",),
            },
        },
        expected_subjects={
            "fault": (
                "U1.1: SYS_JTMS-SWDIO on return-like net GND",
                "U1.3: SWO on supply-like net +3V3",
                "U1.4: nRESET on supply-like net +5V",
            ),
            "control": (),
        },
    )
