"""Digest-pinned native fixture adapter for USB-C CC1/CC2 same-net review."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .ci_hosted_bus_signal_pair_same_net import bus_signal_pair_same_net_fixture_lane
from .ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog


USB_C_CC_SAME_NET_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS


def usb_c_cc_same_net_fixture_lane(root: Path, *, version: str, image: str, log: HostedLog) -> None:
    """Check repeatable native exports and USB-C CC pin review evidence."""
    bus_signal_pair_same_net_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        protocol="usb-c",
        pair_name="cc1-cc2",
        rule_id="bus.usb_c_cc_same_net",
        fixture_directory="usb-c-cc-same-net",
        source_hashes={
            "fault": "621079d2d0e3fc5d782a3c6906545beca838857d4fcb3b0c2d500527b72d7c3c",
            "control": "1dd9812937047037d7f66d40eb7c9249027a61ccedb7edf140702476b4713d2c",
        },
        expected_pin_functions={
            "J1.1": "CC1",
            "J1.2": "CC2",
            "U1.1": "CC1",
            "U1.2": "CC2",
        },
        expected_nets={
            "fault": {"CC_SHARED": ("J1.1", "J1.2", "U1.1", "U1.2")},
            "control": {
                "CC1_BUS": ("J1.1", "U1.1"),
                "CC2_BUS": ("J1.2", "U1.2"),
            },
        },
        expected_subjects={
            "fault": ("J1: USB-C CC1/CC2 pins share CC_SHARED",),
            "control": (),
        },
    )
