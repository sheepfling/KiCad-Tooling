"""Digest-pinned native exports for generic RS-485 connector review."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_generic_connector_fixture_lane import generic_connector_fixture_lane
from .ci_hosted_rs485_generic_connector_cases import (
    RS485_GENERIC_CONNECTOR_SOURCE_HASHES,
    rs485_generic_connector_fixture_sources,
)
from .ci_hosted_support import HostedLog

RULE_ID = "bus.rs485_generic_connector_pair_review"


def rs485_generic_connector_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
) -> None:
    """Export the fault/control sources twice through the shared native lane."""
    generic_connector_fixture_lane(
        root,
        project=project,
        image=image,
        log=log,
        protocol="rs485",
        rule_id=RULE_ID,
        source_hashes=RS485_GENERIC_CONNECTOR_SOURCE_HASHES,
        fixture_sources=rs485_generic_connector_fixture_sources(),
        expected_subject="J1: generic pins match RS-485 A/B bus nets",
        role_evidence=(
            ("A", "A_net", "A_generic_connector_pins", "U1.1", "J1.1"),
            ("B", "B_net", "B_generic_connector_pins", "U1.2", "J1.2"),
        ),
        expected_evidence=(("other_connector_contacts", ("J1.4 function=GND nets=unassigned",)),),
    )
