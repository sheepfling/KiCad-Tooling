"""Digest-pinned native acceptance for USB 2.0 two-pin return review."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_generic_connector_fixture_lane import generic_connector_fixture_lane
from .ci_hosted_support import HostedLog
from .ci_hosted_usb2_connector_return_cases import (
    USB2_CONNECTOR_RETURN_SOURCE_HASHES,
    usb2_connector_return_fixture_sources,
)

RULE_ID = "connector.usb2_pair_without_return_review"


def usb2_connector_return_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
) -> None:
    """Export exact two-contact USB 2.0 fault and named/GND control twice."""
    generic_connector_fixture_lane(
        root,
        project=project,
        image=image,
        log=log,
        protocol="usb2-return",
        rule_id=RULE_ID,
        source_hashes=USB2_CONNECTOR_RETURN_SOURCE_HASHES,
        fixture_sources=usb2_connector_return_fixture_sources(),
        expected_subject=("J1: two-pin USB 2.0 connector pair has no identified reference return"),
        role_evidence=(
            ("USB D+", "USB_D+_net", "USB_D+_connector_pin", "U1.1", "J1.1"),
            ("USB D-", "USB_D-_net", "USB_D-_connector_pin", "U1.2", "J1.2"),
        ),
    )
