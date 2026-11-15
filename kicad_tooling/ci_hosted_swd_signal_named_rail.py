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
            "fault": "6b1efd506bfd509806edada4a9fca7e48077f0f74c28bb85b12c2dda54eeb794",
            "control": "9aa939d5ec1e0cf359adbe1ae9962f5bf8857db107f28775e9ebd479d8f8ba93",
        },
        expected_pin_functions={
            "U1.1": "SYS_JTMS-SWDIO",
            "U1.2": "SYS_JTCK-SWCLK",
            "U1.3": "GPIO_AUX",
            "U1.4": "GPIO_OTHER",
        },
        expected_nets={
            "fault": {
                "GND": ("U1.1",),
                "SYS_JTCK-SWCLK": ("U1.2",),
                "GPIO_AUX_NET": ("U1.3",),
                "GPIO_OTHER": ("U1.4",),
            },
            "control": {
                "SYS_JTMS-SWDIO": ("U1.1",),
                "SYS_JTCK-SWCLK": ("U1.2",),
                "GPIO_AUX": ("U1.3",),
                "GPIO_OTHER": ("U1.4",),
            },
        },
        expected_subjects={
            "fault": ("U1.1: SYS_JTMS-SWDIO on return-like net GND",),
            "control": (),
        },
    )
