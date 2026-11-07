"""Digest-pinned native acceptance for USB SuperSpeed two-pin return review."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_generic_connector_fixture_lane import generic_connector_fixture_lane
from .ci_hosted_support import HostedLog
from .ci_hosted_usb_superspeed_connector_return_cases import (
    USB_SUPERSPEED_CONNECTOR_RETURN_SOURCE_HASHES,
    usb_superspeed_connector_return_fixture_sources,
)

RULE_ID = "connector.usb_superspeed_pair_without_return_review"


def usb_superspeed_connector_return_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
) -> None:
    """Export exact two-pin SuperSpeed fault and three-pin return control twice."""
    generic_connector_fixture_lane(
        root,
        project=project,
        image=image,
        log=log,
        protocol="usb-superspeed-return",
        rule_id=RULE_ID,
        source_hashes=USB_SUPERSPEED_CONNECTOR_RETURN_SOURCE_HASHES,
        fixture_sources=usb_superspeed_connector_return_fixture_sources(),
        expected_subject=(
            "J1: two-pin USB SuperSpeed connector pair has no identified reference return"
        ),
        role_evidence=(
            (
                "SuperSpeed positive",
                "USB_SuperSpeed_positive_net",
                "USB_SuperSpeed_positive_connector_pin",
                "U1.1",
                "J1.1",
            ),
            (
                "SuperSpeed negative",
                "USB_SuperSpeed_negative_net",
                "USB_SuperSpeed_negative_connector_pin",
                "U1.2",
                "J1.2",
            ),
        ),
    )
