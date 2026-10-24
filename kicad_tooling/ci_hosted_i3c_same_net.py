"""Digest-pinned native fixture adapter for I3C SDA/SCL same-net review."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .ci_hosted_bus_signal_pair_same_net import bus_signal_pair_same_net_fixture_lane
from .ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog


I3C_SIGNAL_SAME_NET_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS


def i3c_sda_scl_same_net_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Check repeatable native exports and I3C same-net review evidence."""
    bus_signal_pair_same_net_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        protocol="i3c",
        rule_id="bus.i3c_sda_scl_same_net",
        fixture_directory="i3c-sda-scl-same-net",
        source_hashes={
            "fault": "48a20d238dec4af201c15867d2c1d0064d5fa82e6f9ebcdf4cbbf452f657767b",
            "control": "60781c2942046cc85c0bc33e4317a5d2f411567c27d5e3e1407f8bc127c6ba6e",
        },
        expected_pin_functions={"U1.1": "I3C1_SDA", "U1.2": "I3C1_SCL"},
        expected_nets={
            "fault": {"I3C_SHARED": ("U1.1", "U1.2")},
            "control": {"I3C_SDA": ("U1.1",), "I3C_SCL": ("U1.2",)},
        },
        expected_subjects={
            "fault": ("U1: I3C1 SDA/SCL pins share I3C_SHARED",),
            "control": (),
        },
    )
