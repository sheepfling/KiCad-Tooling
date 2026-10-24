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
            "fault": "9c65be1911ef729b3ae066a63807ff021d6f6d70ce29a33ac4c9f6fef74028bb",
            "control": "05bf8adab0a4f0d54d1667008ed72f2e45a9b4ed5a8593a8e988612b8a9287ec",
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
