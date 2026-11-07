"""Digest-pinned native acceptance for generic connector JTAG pair review."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_generic_connector_fixture_lane import generic_connector_fixture_lane
from .ci_hosted_jtag_generic_connector_cases import (
    JTAG_GENERIC_CONNECTOR_SOURCE_HASHES,
    jtag_generic_connector_fixture_sources,
)
from .ci_hosted_support import HostedLog

RULE_ID = "bus.jtag_generic_connector_pair_review"


def jtag_generic_connector_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
) -> None:
    """Export and compare the JTAG fault/control with one exact KiCad image."""
    generic_connector_fixture_lane(
        root,
        project=project,
        image=image,
        log=log,
        protocol="jtag",
        rule_id=RULE_ID,
        source_hashes=JTAG_GENERIC_CONNECTOR_SOURCE_HASHES,
        fixture_sources=jtag_generic_connector_fixture_sources(),
        expected_subject="J1: generic pins match native JTAG TCK/TMS nets",
        role_evidence=(
            ("TCK", "TCK_net", "TCK_generic_connector_pins", "U1.6", "J1.2"),
            ("TMS", "TMS_net", "TMS_generic_connector_pins", "U1.5", "J1.1"),
        ),
    )
