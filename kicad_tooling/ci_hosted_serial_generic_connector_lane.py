"""Digest-pinned native acceptance for generic connector UART pairs."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_generic_connector_fixture_lane import generic_connector_fixture_lane
from .ci_hosted_serial_generic_connector_cases import (
    SERIAL_GENERIC_CONNECTOR_SOURCE_HASHES,
    serial_generic_connector_fixture_sources,
)
from .ci_hosted_support import HostedLog

RULE_ID = "bus.serial_generic_connector_pair_review"


def serial_generic_connector_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
) -> None:
    """Export the UART fault and named control with the exact KiCad image."""
    generic_connector_fixture_lane(
        root,
        project=project,
        image=image,
        log=log,
        protocol="serial",
        rule_id=RULE_ID,
        source_hashes=SERIAL_GENERIC_CONNECTOR_SOURCE_HASHES,
        fixture_sources=serial_generic_connector_fixture_sources(),
        expected_subject="J1: generic pins match UART TX/RX nets",
        role_evidence=(
            ("TX", "TX_net", "TX_generic_connector_pins", "U1.1", "J1.1"),
            ("RX", "RX_net", "RX_generic_connector_pins", "U1.2", "J1.2"),
        ),
        expected_evidence=(
            (
                "other_connector_contacts",
                (
                    "J1.3 function=Pin_3 nets=SPI_MISO",
                    "J1.4 function=Pin_4 nets=AUX",
                ),
            ),
        ),
    )
