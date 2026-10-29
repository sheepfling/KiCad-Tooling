"""Coordinate protocol-specific peer candidate translators."""

from __future__ import annotations

from .design_lint_candidate_inputs import PeerCandidateInputs
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
from .digital_peer_voltage_types import DigitalPeerVoltageLintContext
from .models import NetlistContract
from .serial_participants import SerialPeerRosterContext
from .serial_peer_reference_scan import scan_serial_peer_reference_reviews
from .spi_participants import SpiRosterContext
from .usb_c_ports import UsbCPortRosterContext
from .usb_data_path_models import UsbDataPathMap
from .usb_peer_data_crossing import usb_peer_data_pair_crossing_candidates
from .usb_peer_reference_scan import scan_usb_peer_reference_reviews


def peer_candidates(
    observed: NetlistContract,
    inputs: PeerCandidateInputs,
    *,
    reviewed_connector_references: tuple[str, ...] = (),
    spi_roster: SpiRosterContext | None = None,
    usb_data_path_map: UsbDataPathMap | None = None,
    usb_data_map_sha256: str | None = None,
) -> tuple[Candidate, ...]:
    """Coordinate peer scans and translate results in stable protocol order."""
    serial_scope = inputs.serial_roster or SerialPeerRosterContext(state="not_configured")
    serial_reference_scan = inputs.serial_reference_scan or scan_serial_peer_reference_reviews(
        observed,
        serial_scope.analysis,
        reviewed_connector_references,
    )
    usb_scan = inputs.usb_reference_scan or scan_usb_peer_reference_reviews(
        observed,
        usb_data_path_map,
        reviewed_connector_references,
    )
    spi_scope = spi_roster or SpiRosterContext(state="not_configured")
    peer_voltage_scope = inputs.digital_voltage_context or DigitalPeerVoltageLintContext(
        state="not_configured"
    )
    peer_voltage_scan = inputs.digital_voltage_scan or scan_digital_peer_voltage_reviews(
        observed,
        peer_voltage_scope.analysis,
    )
    usb_c_scope = inputs.usb_c_port_roster or UsbCPortRosterContext(state="not_configured")
    return (
        *serial_unmapped_peer_candidates(observed, serial_scope),
        *serial_reference_candidates(serial_reference_scan, serial_scope),
        *usb_peer_data_pair_crossing_candidates(
            observed,
            usb_data_path_map,
            reviewed_connector_references,
        ),
        *usb_peer_reference_candidates(usb_scan, usb_data_path_map, usb_data_map_sha256),
        *spi_participant_candidates(observed, spi_scope),
        *digital_peer_voltage_candidates(peer_voltage_scope, peer_voltage_scan),
        *usb_c_port_candidates(observed, usb_c_scope, reviewed_connector_references),
    )
