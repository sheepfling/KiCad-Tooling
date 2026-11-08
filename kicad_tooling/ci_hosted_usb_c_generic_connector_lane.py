"""Digest-pinned native acceptance for generic USB-C CC connector review."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_generic_connector_fixture_lane import generic_connector_fixture_lane
from .ci_hosted_support import HostedLog
from .ci_hosted_usb_c_generic_connector_cases import (
    USB_C_GENERIC_CONNECTOR_SOURCE_HASHES,
    usb_c_generic_connector_fixture_sources,
)

RULE_ID = "bus.usb_c_generic_connector_cc_pair_review"


def usb_c_generic_connector_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
) -> None:
    """Export and compare the synthetic CC pair fault/control with exact KiCad."""
    generic_connector_fixture_lane(
        root,
        project=project,
        image=image,
        log=log,
        protocol="usb-c-generic",
        rule_id=RULE_ID,
        source_hashes=USB_C_GENERIC_CONNECTOR_SOURCE_HASHES,
        fixture_sources=usb_c_generic_connector_fixture_sources(),
        expected_subject="J1 / U1: generic pins match USB-C CC1/CC2 nets",
        role_evidence=(
            (
                "USB-C CC1",
                "USB_C_CC1_net",
                "USB_C_CC1_generic_connector_pins",
                "U1.1",
                "J1.1",
            ),
            (
                "USB-C CC2",
                "USB_C_CC2_net",
                "USB_C_CC2_generic_connector_pins",
                "U1.2",
                "J1.2",
            ),
        ),
        expected_evidence=(("other_connector_contacts", ("J1.4 function=GND nets=unassigned",)),),
    )
