"""Digest-pinned native acceptance for two-pin I2C return review."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_generic_connector_fixture_lane import generic_connector_fixture_lane
from .ci_hosted_i2c_connector_return_cases import (
    I2C_CONNECTOR_RETURN_SOURCE_HASHES,
    i2c_connector_return_fixture_sources,
)
from .ci_hosted_support import HostedLog

RULE_ID = "connector.i2c_pair_without_return_review"


def i2c_connector_return_fixture_lane(
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
        protocol="i2c-return",
        rule_id=RULE_ID,
        source_hashes=I2C_CONNECTOR_RETURN_SOURCE_HASHES,
        fixture_sources=i2c_connector_return_fixture_sources(),
        expected_subject="J1: two-pin I2C connector has no identified reference return",
        role_evidence=(
            ("SDA", "SDA_net", "SDA_generic_connector_pins", "U1.1", "J1.1"),
            ("SCL", "SCL_net", "SCL_generic_connector_pins", "U1.2", "J1.2"),
        ),
    )
