"""Typed prepared inputs for design-lint peer candidate scans."""

from __future__ import annotations

from dataclasses import dataclass

from .digital_peer_voltage_types import DigitalPeerVoltageLintContext, DigitalPeerVoltageScan
from .netlist_contract_models import NetlistContract
from .serial_participants import SerialPeerRosterContext
from .serial_peer_reference_types import SerialPeerReferenceScan
from .spi_participants import SpiRosterContext
from .usb_c_ports import UsbCPortRosterContext
from .usb_data_path_models import UsbDataPathMap
from .usb_peer_reference_types import UsbPeerReferenceScan


@dataclass(frozen=True, slots=True)
class PeerCandidateInputs:
    """Resolved protocol and digital-peer evidence for one candidate pass."""

    digital_voltage_context: DigitalPeerVoltageLintContext | None
    digital_voltage_scan: DigitalPeerVoltageScan | None
    usb_reference_scan: UsbPeerReferenceScan | None
    serial_reference_scan: SerialPeerReferenceScan | None
    serial_roster: SerialPeerRosterContext | None
    usb_c_port_roster: UsbCPortRosterContext | None


@dataclass(frozen=True, slots=True)
class PeerCandidateScanInputs:
    """One observed netlist plus all evidence and authored context used by peer rules."""

    observed: NetlistContract
    peer: PeerCandidateInputs
    reviewed_connector_references: tuple[str, ...]
    spi_roster: SpiRosterContext | None
    usb_data_path_map: UsbDataPathMap | None
    usb_data_map_sha256: str | None
