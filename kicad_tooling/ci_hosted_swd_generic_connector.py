"""Digest-pinned native acceptance for generic connector SWD pair review."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_generic_connector_fixture_lane import generic_connector_fixture_lane
from .ci_hosted_support import HostedLog
from .ci_hosted_swd_generic_connector_cases import (
    SWD_GENERIC_CONNECTOR_SOURCE_HASHES,
    swd_generic_connector_fixture_sources,
)

RULE_ID = "bus.swd_generic_connector_pair_review"


def swd_generic_connector_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
) -> None:
    """Export and compare the SWD fault/control with one exact KiCad image."""
    generic_connector_fixture_lane(
        root,
        project=project,
        image=image,
        log=log,
        protocol="swd",
        rule_id=RULE_ID,
        source_hashes=SWD_GENERIC_CONNECTOR_SOURCE_HASHES,
        fixture_sources=swd_generic_connector_fixture_sources(),
        expected_subject="J1: generic pins match native SWDIO/SWCLK nets",
        role_evidence=(
            ("SWDIO", "SWDIO_net", "SWDIO_generic_connector_pins", "U1.5", "J1.1"),
            ("SWCLK", "SWCLK_net", "SWCLK_generic_connector_pins", "U1.6", "J1.2"),
        ),
    )
