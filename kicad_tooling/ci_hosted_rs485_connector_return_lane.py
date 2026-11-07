"""Digest-pinned native acceptance for two-contact RS-485 return review."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_generic_connector_fixture_lane import generic_connector_fixture_lane
from .ci_hosted_rs485_connector_return_cases import (
    RS485_CONNECTOR_RETURN_SOURCE_HASHES,
    rs485_connector_return_fixture_sources,
)
from .ci_hosted_support import HostedLog

RULE_ID = "connector.rs485_pair_without_return_review"


def rs485_connector_return_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
) -> None:
    """Export a two-contact RS-485 fault and named-contact control twice."""
    generic_connector_fixture_lane(
        root,
        project=project,
        image=image,
        log=log,
        protocol="rs485-return",
        rule_id=RULE_ID,
        source_hashes=RS485_CONNECTOR_RETURN_SOURCE_HASHES,
        fixture_sources=rs485_connector_return_fixture_sources(),
        expected_subject="J1: two-pin RS-485 connector has no identified reference return",
        role_evidence=(
            ("RS-485 A", "A_net", "A_generic_connector_pins", "U1.1", "J1.1"),
            ("RS-485 B", "B_net", "B_generic_connector_pins", "U1.2", "J1.2"),
        ),
    )
