"""Digest-pinned native fixtures for I2S signals assigned to named rails."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS
from .ci_hosted_named_rail_fixtures import named_rail_fixture_lane
from .ci_hosted_support import HostedLog

I2S_SIGNAL_NAMED_RAIL_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS


def i2s_signal_named_rail_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Repeat native netlist/ERC exports and relint one I2S fault/control pair."""
    named_rail_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        protocol="i2s",
        feature="signal",
        rule_id="bus.i2s_signal_on_named_rail",
        fixture_directory="i2s-signal-named-rail",
        source_hashes={
            "fault": "c4612a19cb10cccede0b225dcd78ff7f7c47b812b10e1e72e104b25e1d0a8f2c",
            "control": "ec18ed6db52cf8503718fcdd310d43348d81fa93f13a0ca42b249843889cb189",
        },
        expected_pin_functions={
            "U1.1": "I2S_BCLK",
            "U1.2": "I2S_LRCLK",
            "U1.3": "I2S_DATA",
            "U1.4": "MCLK",
        },
        expected_nets={
            "fault": {
                "GND": ("U1.1",),
                "I2S_LRCLK": ("U1.2",),
                "+3V3": ("U1.3",),
                "AUDIO_MCLK": ("U1.4",),
            },
            "control": {
                "I2S_BCLK": ("U1.1",),
                "I2S_LRCLK": ("U1.2",),
                "I2S_DATA": ("U1.3",),
                "AUDIO_MCLK": ("U1.4",),
            },
        },
        expected_subjects={
            "fault": (
                "U1.1: I2S_BCLK on return-like net GND",
                "U1.3: I2S_DATA on supply-like net +3V3",
            ),
            "control": (),
        },
    )
