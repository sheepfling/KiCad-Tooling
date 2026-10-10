"""Coordinate protocol-specific peer candidate translators."""

from __future__ import annotations

from .design_lint_digital_peer_voltage_candidates import digital_peer_voltage_candidates
from .design_lint_serial_peer_candidates import (
    serial_reference_candidates,
    serial_unmapped_peer_candidates,
)
from .design_lint_spi_peer_candidates import spi_participant_candidates
from .design_lint_types import Candidate
from .design_lint_usb_c_candidates import usb_c_port_candidates
from .design_lint_usb_peer_candidates import usb_peer_reference_candidates
from .digital_peer_voltage_scan import scan_digital_peer_voltage_reviews
from .digital_peer_voltage_types import (
    DigitalPeerVoltageLintContext,
    DigitalPeerVoltageScan,
)
from .models import NetlistContract, UsbDataPathMap
from .serial_participants import SerialPeerRosterContext
from .serial_peer_reference_scan import scan_serial_peer_reference_reviews
from .serial_peer_reference_types import SerialPeerReferenceScan
from .spi_participants import SpiRosterContext
from .usb_c_ports import UsbCPortRosterContext
from .usb_peer_reference_scan import scan_usb_peer_reference_reviews
from .usb_peer_reference_types import UsbPeerReferenceScan


def peer_candidates(
    observed: NetlistContract,
    *,
    digital_peer_voltage_context: DigitalPeerVoltageLintContext | None = None,
    digital_peer_voltage_scan: DigitalPeerVoltageScan | None = None,
    reviewed_connector_references: tuple[str, ...] = (),
    serial_peer_reference_scan: SerialPeerReferenceScan | None = None,
    serial_peer_roster: SerialPeerRosterContext | None = None,
    spi_roster: SpiRosterContext | None = None,
    usb_c_port_roster: UsbCPortRosterContext | None = None,
    usb_data_path_map: UsbDataPathMap | None = None,
    usb_data_map_sha256: str | None = None,
    usb_peer_reference_scan: UsbPeerReferenceScan | None = None,
) -> tuple[Candidate, ...]:
    """Coordinate peer scans and translate results in stable protocol order."""
    serial_scope = serial_peer_roster or SerialPeerRosterContext(state="not_configured")
    serial_reference_scan = serial_peer_reference_scan or scan_serial_peer_reference_reviews(
        observed,
        serial_scope.analysis,
        reviewed_connector_references,
    )
    usb_scan = usb_peer_reference_scan or scan_usb_peer_reference_reviews(
        observed,
        usb_data_path_map,
        reviewed_connector_references,
    )
    spi_scope = spi_roster or SpiRosterContext(state="not_configured")
    peer_voltage_scope = digital_peer_voltage_context or DigitalPeerVoltageLintContext(
        state="not_configured"
    )
    peer_voltage_scan = digital_peer_voltage_scan or scan_digital_peer_voltage_reviews(
        observed,
        peer_voltage_scope.analysis,
    )
    usb_c_scope = usb_c_port_roster or UsbCPortRosterContext(state="not_configured")
    return (
        *serial_unmapped_peer_candidates(observed, serial_scope),
        *serial_reference_candidates(serial_reference_scan, serial_scope),
        *usb_peer_reference_candidates(usb_scan, usb_data_path_map, usb_data_map_sha256),
        *spi_participant_candidates(observed, spi_scope),
        *digital_peer_voltage_candidates(peer_voltage_scope, peer_voltage_scan),
        *usb_c_port_candidates(observed, usb_c_scope, reviewed_connector_references),
    )
