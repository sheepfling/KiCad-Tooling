"""Digest-pinned native acceptance for two-pin CAN connector return review."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_can_connector_return_cases import (
    CAN_CONNECTOR_RETURN_SOURCE_HASHES,
    can_connector_return_fixture_sources,
)
from .ci_hosted_generic_connector_fixture_lane import generic_connector_fixture_lane
from .ci_hosted_support import HostedLog

RULE_ID = "connector.can_pair_without_return_review"


def can_connector_return_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
) -> None:
    """Export a two-contact CAN fault and a larger connector control twice."""
    generic_connector_fixture_lane(
        root,
        project=project,
        image=image,
        log=log,
        protocol="can-return",
        rule_id=RULE_ID,
        source_hashes=CAN_CONNECTOR_RETURN_SOURCE_HASHES,
        fixture_sources=can_connector_return_fixture_sources(),
        expected_subject="J1: two-pin CAN connector has no identified reference return",
        role_evidence=(
            ("CANH", "CANH_net", "CANH_generic_connector_pins", "U1.1", "J1.1"),
            ("CANL", "CANL_net", "CANL_generic_connector_pins", "U1.2", "J1.2"),
        ),
    )
