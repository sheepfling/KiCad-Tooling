"""Digest-pinned native fixtures for JTAG signals assigned to named rails."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS
from .ci_hosted_named_rail_fixtures import named_rail_fixture_lane
from .ci_hosted_support import HostedLog

JTAG_SIGNAL_NAMED_RAIL_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS


def jtag_signal_named_rail_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Repeat native netlist/ERC exports and relint one JTAG fault/control pair."""
    named_rail_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        protocol="jtag",
        feature="signal",
        rule_id="bus.jtag_signal_on_named_rail",
        fixture_directory="jtag-signal-named-rail",
        source_hashes={
            "fault": "78d7c9e9544b6af932e1f3283bd83c8d300f8266bc6dd844b59702ebfb382ad2",
            "control": "27d17fb821a66b12fe794a13c417edc4873b1ade32afeb187d877d135cfcb8ba",
        },
        expected_pin_functions={
            "U1.1": "JTAG_TCK",
            "U1.2": "JTAG_TMS",
            "U1.3": "JTAG_TDI",
            "U1.4": "JTAG_TDO",
        },
        expected_nets={
            "fault": {
                "GND": ("U1.1",),
                "JTAG_TMS": ("U1.2",),
                "+3V3": ("U1.3",),
                "JTAG_TDO": ("U1.4",),
            },
            "control": {
                "JTAG_TCK": ("U1.1",),
                "JTAG_TMS": ("U1.2",),
                "JTAG_TDI": ("U1.3",),
                "JTAG_TDO": ("U1.4",),
            },
        },
        expected_subjects={
            "fault": (
                "U1.1: JTAG_TCK on return-like net GND",
                "U1.3: JTAG_TDI on supply-like net +3V3",
            ),
            "control": (),
        },
    )
