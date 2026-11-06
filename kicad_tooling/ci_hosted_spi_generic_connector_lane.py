"""Digest-pinned native acceptance for generic connector SPI role triads."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_generic_connector_fixture_lane import generic_connector_fixture_lane
from .ci_hosted_spi_generic_connector_cases import (
    SPI_GENERIC_CONNECTOR_SOURCE_HASHES,
    spi_generic_connector_fixture_sources,
)
from .ci_hosted_support import HostedLog

RULE_ID = "bus.spi_generic_connector_triad_review"


def spi_generic_connector_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
) -> None:
    """Export the SPI fault and named control with the exact KiCad image."""
    generic_connector_fixture_lane(
        root,
        project=project,
        image=image,
        log=log,
        protocol="spi",
        rule_id=RULE_ID,
        source_hashes=SPI_GENERIC_CONNECTOR_SOURCE_HASHES,
        fixture_sources=spi_generic_connector_fixture_sources(),
        expected_subject="J1: generic pins match SPI clock and both data roles",
        role_evidence=(
            (
                "clock",
                "clock_net",
                "clock_generic_connector_pins",
                "U1.1",
                "J1.1",
            ),
            (
                "controller-to-peripheral data",
                "controller-to-peripheral data_net",
                "controller-to-peripheral data_generic_connector_pins",
                "U1.2",
                "J1.2",
            ),
            (
                "peripheral-to-controller data",
                "peripheral-to-controller data_net",
                "peripheral-to-controller data_generic_connector_pins",
                "U1.3",
                "J1.3",
            ),
        ),
    )
