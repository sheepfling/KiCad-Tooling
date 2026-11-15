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
            "fault": "62837263395b23916e1b61ec5687c1d658666c92c7db0a7cc064c44711bfa675",
            "control": "787e89740492874bc952fdad71e4f605d449b292c7d0db7d217f5fbc92f77e19",
        },
        expected_pin_functions={
            "U1.1": "SYS_JTMS-SWDIO",
            "U1.2": "SYS_JTCK-SWCLK",
            "U1.3": "SWO",
            "U1.4": "GPIO_OTHER",
        },
        expected_nets={
            "fault": {
                "GND": ("U1.1",),
                "SYS_JTCK-SWCLK": ("U1.2",),
                "+3V3": ("U1.3",),
                "GPIO_OTHER": ("U1.4",),
            },
            "control": {
                "SYS_JTMS-SWDIO": ("U1.1",),
                "SYS_JTCK-SWCLK": ("U1.2",),
                "SWO_TRACE": ("U1.3",),
                "GPIO_OTHER": ("U1.4",),
            },
        },
        expected_subjects={
            "fault": (
                "U1.1: SYS_JTMS-SWDIO on return-like net GND",
                "U1.3: SWO on supply-like net +3V3",
            ),
            "control": (),
        },
    )
