"""Digest-pinned native fixture adapter for RS-485 A/B same-net review."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .ci_hosted_bus_signal_pair_same_net import bus_signal_pair_same_net_fixture_lane
from .ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog


RS485_AB_SAME_NET_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS


def rs485_ab_same_net_fixture_lane(root: Path, *, version: str, image: str, log: HostedLog) -> None:
    """Check repeatable native exports and RS-485 A/B same-net evidence."""
    bus_signal_pair_same_net_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        protocol="rs485",
        pair_name="a-b",
        rule_id="bus.rs485_ab_same_net",
        fixture_directory="rs485-ab-same-net",
        source_hashes={
            "fault": "12df9c40538c819cbd6369cb88f264d4497dff69051e20d3d2c17314bcb13f61",
            "control": "088e4f94449678f4ccb01569d69220dc3c225e533848a8e91a05586d6eac1400",
        },
        expected_pin_functions={"U1.1": "A", "U1.2": "B"},
        expected_nets={
            "fault": {"AB_SHARED": ("U1.1", "U1.2")},
            "control": {"RS485_A": ("U1.1",), "RS485_B": ("U1.2",)},
        },
        expected_subjects={
            "fault": ("U1: RS-485 A/B bus pins share AB_SHARED",),
            "control": (),
        },
    )
