"""Digest-pinned native fixtures for USB and USB-C named-rail heuristics."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Literal

from .ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS
from .ci_hosted_named_rail_fixtures import named_rail_fixture_lane
from .ci_hosted_support import HostedLog

USB_SIGNAL_NAMED_RAIL_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS

_SIGNAL_RULE_ID = "bus.usb_signal_on_named_rail"
_SIGNAL_SOURCE_HASHES: Mapping[str, str] = MappingProxyType(
    {
        "control": "30270e674ad045a2ebc238b6f632ed455c04f549d6c53061f74151c77d160002",
        "fault": "9330de44f6600afd92d2aa7199eced1ca6e892ed74fb5765f20a1832eef97148",
    }
)
_CC_RULE_ID = "bus.usb_c_cc_signal_on_named_rail"
_CC_SOURCE_HASHES: Mapping[str, str] = MappingProxyType(
    {
        "fault": "9f484af298d4a8bbd9e779e7bf2659098f3b05473343411dd5698c4204fa90b2",
        "control": "e49f410117e4ef7a2d3bead575c68cc184c05efe9c42a3f6bea29c7bab467b5a",
    }
)
_SBU_RULE_ID = "bus.usb_c_sbu_signal_on_named_rail"
_SBU_SOURCE_HASHES: Mapping[str, str] = MappingProxyType(
    {
        "fault": "65907be4e4d13ebae004f10dc74076ca350759a692dc614b1e9aa9166b907619",
        "control": "ad15d977415856e97c8e701c653d20f26e9cc9d9751d662dcba0f459491fde87",
    }
)
_SBU_UNCONNECTED_RULE_ID = "bus.usb_c_sbu_unconnected_pin"
_SBU_UNCONNECTED_SOURCE_HASHES: Mapping[str, str] = MappingProxyType(
    {
        "fault": "7244d4285c4624aadc302905ab051462e16280a56e8dfe01b1791aea701f6bed",
        "control": "9b16bfcbc1efff9a72db1ac636a3decdb069f0136b827d03b6aed72ea66128d7",
    }
)
_SBU_SAME_NET_RULE_ID = "bus.usb_c_sbu_same_net"
_SBU_SAME_NET_SOURCE_HASHES: Mapping[str, str] = MappingProxyType(
    {
        "fault": "c4b68ed7849e661f3a5fe3eaf901947b7c83eda649b00ffce93fa3c4bdc534c6",
        "control": "255e96c70b634c5658fd35d05722f0098d838478bf07d4e15744c15e48c4f8f9",
    }
)


def usb_signal_named_rail_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Repeat native exports for USB data pins assigned to a named rail."""
    _usb_named_rail_fixture_lane(root, version=version, image=image, log=log, feature="signal")


def usb_c_cc_named_rail_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Repeat native exports for USB-C controller CC pins assigned to rails."""
    _usb_named_rail_fixture_lane(root, version=version, image=image, log=log, feature="cc")


def usb_c_sbu_named_rail_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Repeat native exports for USB-C controller SBU pins assigned to rails."""
    _usb_named_rail_fixture_lane(root, version=version, image=image, log=log, feature="sbu")


def usb_c_sbu_unconnected_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Repeat native exports for asymmetric SBU pin assignments."""
    _usb_named_rail_fixture_lane(
        root, version=version, image=image, log=log, feature="sbu-unconnected"
    )


def usb_c_sbu_same_net_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Repeat native exports for USB-C controller SBU pins on one net."""
    _usb_named_rail_fixture_lane(
        root, version=version, image=image, log=log, feature="sbu-same-net"
    )


def _usb_named_rail_fixture_lane(
    root: Path,
    *,
    version: str,
    image: str,
    log: HostedLog,
    feature: Literal["signal", "cc", "sbu", "sbu-unconnected", "sbu-same-net"],
) -> None:
    expected_unconnected_pins = None
    if feature == "signal":
        protocol = "usb"
        rule_id = _SIGNAL_RULE_ID
        fixture_directory = "usb-signal-named-rail"
        source_hashes = _SIGNAL_SOURCE_HASHES
        expected_pin_functions = None
        expected_nets = {
            "fault": {
                "GND": ("U1.1",),
                "USB_D-": ("J1.2", "U1.2"),
                "USB_D+": ("J1.1",),
            },
            "control": {
                "USB_D+": ("J1.1", "U1.1"),
                "USB_D-": ("J1.2", "U1.2"),
            },
        }
        expected_subjects = {
            "fault": ("U1.1: USB_DP on return-like net GND",),
            "control": (),
        }
    elif feature == "cc":
        protocol = "usb-c"
        rule_id = _CC_RULE_ID
        fixture_directory = "usb-c-cc-named-rail"
        source_hashes = _CC_SOURCE_HASHES
        expected_pin_functions = {
            "J1.1": "CC1",
            "J1.2": "CC2",
            "U1.1": "CC1",
            "U1.2": "CC2",
        }
        expected_nets = {
            "fault": {"GND": ("J1.1", "U1.1"), "+3V3": ("J1.2", "U1.2")},
            "control": {"CC1_BUS": ("J1.1", "U1.1"), "CC2_BUS": ("J1.2", "U1.2")},
        }
        expected_subjects = {
            "fault": (
                "U1.1: CC1 on return-like net GND",
                "U1.2: CC2 on supply-like net +3V3",
            ),
            "control": (),
        }
    elif feature == "sbu":
        protocol = "usb-c"
        rule_id = _SBU_RULE_ID
        fixture_directory = "usb-c-sbu-named-rail"
        source_hashes = _SBU_SOURCE_HASHES
        expected_pin_functions = {
            "J1.1": "SBU1",
            "J1.2": "SBU2",
            "U1.1": "SBU1",
            "U1.2": "SBU2",
        }
        expected_nets = {
            "fault": {"GND": ("J1.1", "U1.1"), "+3V3": ("J1.2", "U1.2")},
            "control": {
                "SBU1_BUS": ("J1.1", "U1.1"),
                "SBU2_BUS": ("J1.2", "U1.2"),
            },
        }
        expected_subjects = {
            "fault": (
                "U1.1: SBU1 on return-like net GND",
                "U1.2: SBU2 on supply-like net +3V3",
            ),
            "control": (),
        }
        expected_unconnected_pins = None
    elif feature == "sbu-unconnected":
        protocol = "usb-c"
        rule_id = _SBU_UNCONNECTED_RULE_ID
        fixture_directory = "usb-c-sbu-unconnected-pin"
        source_hashes = _SBU_UNCONNECTED_SOURCE_HASHES
        expected_pin_functions = {
            "J1.1": "SBU1",
            "J1.2": "SBU2",
            "U1.1": "SBU1",
            "U1.2": "SBU2",
        }
        expected_nets = {
            "fault": {"SBU1_BUS": ("J1.1",), "SBU2_BUS": ("J1.2", "U1.2")},
            "control": {
                "SBU1_BUS": ("J1.1", "U1.1"),
                "SBU2_BUS": ("J1.2", "U1.2"),
            },
        }
        expected_subjects = {
            "fault": ("U1.1: SBU1",),
            "control": (),
        }
        expected_unconnected_pins = {"fault": ("U1.1",), "control": ()}
    else:
        protocol = "usb-c"
        rule_id = _SBU_SAME_NET_RULE_ID
        fixture_directory = "usb-c-sbu-same-net"
        source_hashes = _SBU_SAME_NET_SOURCE_HASHES
        expected_pin_functions = {
            "J1.1": "SBU1",
            "J1.2": "SBU2",
            "U1.1": "SBU1",
            "U1.2": "SBU2",
        }
        expected_nets = {
            "fault": {"SBU_SHARED": ("J1.1", "J1.2", "U1.1", "U1.2")},
            "control": {
                "SBU1_BUS": ("J1.1", "U1.1"),
                "SBU2_BUS": ("J1.2", "U1.2"),
            },
        }
        expected_subjects = {
            "fault": ("U1: USB-C SBU1/SBU2 pins share SBU_SHARED",),
            "control": (),
        }
        expected_unconnected_pins = None

    named_rail_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        protocol=protocol,
        feature=feature,
        rule_id=rule_id,
        fixture_directory=fixture_directory,
        source_hashes=source_hashes,
        expected_pin_functions=expected_pin_functions,
        expected_nets=expected_nets,
        expected_subjects=expected_subjects,
        expected_unconnected_pins=expected_unconnected_pins,
    )
