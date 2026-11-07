"""Digest-pinned native acceptance for two-pin UART return review."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_generic_connector_fixture_lane import generic_connector_fixture_lane
from .ci_hosted_serial_connector_return_cases import (
    SERIAL_CONNECTOR_RETURN_SOURCE_HASHES,
    serial_connector_return_fixture_sources,
)
from .ci_hosted_support import HostedLog

RULE_ID = "connector.serial_pair_without_return_review"


def serial_connector_return_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
) -> None:
    """Export a generic two-contact fault and named-contact control twice."""
    generic_connector_fixture_lane(
        root,
        project=project,
        image=image,
        log=log,
        protocol="serial-return",
        rule_id=RULE_ID,
        source_hashes=SERIAL_CONNECTOR_RETURN_SOURCE_HASHES,
        fixture_sources=serial_connector_return_fixture_sources(),
        expected_subject="J1: two-pin UART connector has no identified reference return",
        role_evidence=(
            ("TX", "TX_net", "TX_generic_connector_pins", "U1.1", "J1.1"),
            ("RX", "RX_net", "RX_generic_connector_pins", "U1.2", "J1.2"),
        ),
    )
