"""Compatibility facade for digital peer voltage review."""

from __future__ import annotations

from .digital_peer_voltage_scan import (
    format_nominal_voltage,
    scan_digital_peer_voltage_reviews,
    unmapped_digital_peer_voltage_reviews,
    unmapped_serial_peer_voltage_reviews,
    unmapped_spi_peer_voltage_reviews,
)
from .digital_peer_voltage_types import (
    DigitalPeerLink,
    DigitalPeerVoltageCoverage,
    DigitalPeerVoltageReview,
    DigitalPeerVoltageScan,
    VoltageNamedRail,
)

__all__ = [
    "DigitalPeerLink",
    "DigitalPeerVoltageCoverage",
    "DigitalPeerVoltageReview",
    "DigitalPeerVoltageScan",
    "VoltageNamedRail",
    "format_nominal_voltage",
    "scan_digital_peer_voltage_reviews",
    "unmapped_digital_peer_voltage_reviews",
    "unmapped_serial_peer_voltage_reviews",
    "unmapped_spi_peer_voltage_reviews",
]
