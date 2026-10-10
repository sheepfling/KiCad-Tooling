"""Coordinate SPI, serial peer-reference, and component-power fixtures."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_digital_peer_component_power import verify_component_peer_power_cases
from .ci_hosted_digital_peer_context import DigitalPeerLog, prepare_digital_peer_fixture_context
from .ci_hosted_digital_peer_serial_connector_reference import (
    verify_serial_connector_reference_cases,
)
from .ci_hosted_digital_peer_serial_label_reference import verify_serial_label_reference_cases
from .ci_hosted_digital_peer_serial_peer_voltage import verify_serial_peer_voltage_cases
from .ci_hosted_digital_peer_spi_participants import verify_spi_participant_voltage
from .ci_hosted_digital_peer_spi_peer_voltage import verify_spi_peer_voltage_cases
from .ci_hosted_digital_peer_spi_roster import verify_spi_roster_coverage


def digital_peer_fixture_lane(root: Path, *, project: str, image: str, log: DigitalPeerLog) -> None:
    """Verify deterministic SPI and peer-interface fixture cases."""
    context = prepare_digital_peer_fixture_context(root, project=project, image=image, log=log)
    verify_spi_participant_voltage(context)
    verify_spi_roster_coverage(context)
    verify_spi_peer_voltage_cases(context)
    serial_peer_policy = verify_serial_peer_voltage_cases(context)
    verify_serial_connector_reference_cases(context, serial_peer_policy)
    verify_serial_label_reference_cases(context)
    verify_component_peer_power_cases(context)
