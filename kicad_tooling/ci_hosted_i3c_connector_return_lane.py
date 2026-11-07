"""Digest-pinned native acceptance for two-pin I3C return review."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_generic_connector_fixture_lane import generic_connector_fixture_lane
from .ci_hosted_i3c_connector_return_cases import (
    I3C_CONNECTOR_RETURN_SOURCE_HASHES,
    i3c_connector_return_fixture_sources,
)
from .ci_hosted_support import HostedLog

RULE_ID = "connector.i3c_pair_without_return_review"


def i3c_connector_return_fixture_lane(
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
        protocol="i3c-return",
        rule_id=RULE_ID,
        source_hashes=I3C_CONNECTOR_RETURN_SOURCE_HASHES,
        fixture_sources=i3c_connector_return_fixture_sources(),
        expected_subject="J1: two-pin I3C connector has no identified reference return",
        role_evidence=(
            ("SDA", "SDA_net", "SDA_generic_connector_pins", "U1.1", "J1.1"),
            ("SCL", "SCL_net", "SCL_generic_connector_pins", "U1.2", "J1.2"),
        ),
    )
