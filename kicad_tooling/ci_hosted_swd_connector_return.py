"""Digest-pinned native acceptance for SWD connector return review."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_generic_connector_fixture_lane import generic_connector_fixture_lane
from .ci_hosted_support import HostedLog
from .ci_hosted_swd_connector_return_cases import (
    SWD_CONNECTOR_RETURN_SOURCE_HASHES,
    swd_connector_return_fixture_sources,
)

RULE_ID = "connector.swd_pair_without_return_review"


def swd_connector_return_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
) -> None:
    """Export the SWD return fault and native-GND control with one exact KiCad image."""
    generic_connector_fixture_lane(
        root,
        project=project,
        image=image,
        log=log,
        protocol="swd-connector-return",
        rule_id=RULE_ID,
        source_hashes=SWD_CONNECTOR_RETURN_SOURCE_HASHES,
        fixture_sources=swd_connector_return_fixture_sources(),
        expected_subject="J1: SWD connector has no identified reference return",
        role_evidence=(
            ("SWDIO", "SWDIO_net", "SWDIO_generic_connector_pins", "U1.5", "J1.1"),
            ("SWCLK", "SWCLK_net", "SWCLK_generic_connector_pins", "U1.6", "J1.2"),
        ),
    )
