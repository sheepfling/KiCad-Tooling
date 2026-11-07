"""Digest-pinned native acceptance for JTAG connector return review."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_generic_connector_fixture_lane import generic_connector_fixture_lane
from .ci_hosted_jtag_connector_return_cases import (
    JTAG_CONNECTOR_RETURN_SOURCE_HASHES,
    jtag_connector_return_fixture_sources,
)
from .ci_hosted_support import HostedLog

RULE_ID = "connector.jtag_pair_without_return_review"


def jtag_connector_return_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
) -> None:
    """Export the JTAG return fault and explicit-GND control with one exact KiCad image."""
    generic_connector_fixture_lane(
        root,
        project=project,
        image=image,
        log=log,
        protocol="jtag-connector-return",
        rule_id=RULE_ID,
        source_hashes=JTAG_CONNECTOR_RETURN_SOURCE_HASHES,
        fixture_sources=jtag_connector_return_fixture_sources(),
        expected_subject="J1: JTAG connector has no identified reference return",
        role_evidence=(
            ("TCK", "TCK_net", "TCK_generic_connector_pins", "U1.6", "J1.2"),
            ("TMS", "TMS_net", "TMS_generic_connector_pins", "U1.5", "J1.1"),
        ),
    )
