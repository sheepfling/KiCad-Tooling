"""Digest-pinned native fixture adapter for USB 2.0 D+/D- same-net review."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .ci_hosted_bus_signal_pair_same_net import bus_signal_pair_same_net_fixture_lane
from .ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog


USB_DATA_SAME_NET_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS


def usb_dp_dm_same_net_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Check repeatable native exports and USB same-net review evidence."""
    bus_signal_pair_same_net_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        protocol="usb",
        pair_name="dp-dm",
        rule_id="bus.usb_dp_dm_same_net",
        fixture_directory="usb-dp-dm-same-net",
        source_hashes={
            "fault": "7182133d074e5f28fa7a80b36962ed11b4e659e85e107db9dbc5c708c5110ebe",
            "control": "ac9410b7cade422a635847bae9e1e4a7a57333a7a259756d4aad62afa8d8069e",
        },
        expected_pin_functions={"U1.1": "DP", "U1.2": "DM"},
        expected_nets={
            "fault": {"USB_SHARED": ("U1.1", "U1.2")},
            "control": {"USB_DM": ("U1.2",), "USB_DP": ("U1.1",)},
        },
        expected_subjects={
            "fault": ("U1: USB data port unindexed D+/D- pins share USB_SHARED",),
            "control": (),
        },
    )
