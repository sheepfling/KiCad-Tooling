"""Source registry for synthetic generic-connector SPI native fixtures."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_support import tooling_checkout_root
from .hwrepo.connector_coverage_models import (
    ConnectorCoverageEntry,
    ConnectorCoverageReport,
    ConnectorMappedPinEvidence,
)
from .hwrepo.connector_peer_pin_models import ConnectorPinRole
from .hwrepo.netlist_contract_models import NetlistContract

SPI_GENERIC_CONNECTOR_SOURCE_HASHES = {
    "control": "030cffc1bd67e6b3eaf925e02009b52db2a2382eba4d7ab548bb13543296d8f7",
    "fault": "713ff06b7497f9f57287324ca916c567243580e46e6c60239bf28049c865dda7",
}


def spi_generic_connector_fixture_sources() -> dict[str, Path]:
    """Return the tooling-owned SPI connector fault and named control schematics."""
    fixture_root = (
        tooling_checkout_root() / "tests/fixtures/design_lint/spi-generic-connector-native"
    )
    return {
        "fault": fixture_root / "fault.kicad_sch",
        "control": fixture_root / "control.kicad_sch",
    }


def spi_connector_role_map(
    observed: NetlistContract,
    *,
    has_return_role: bool,
) -> ConnectorCoverageReport:
    """Build a complete synthetic role map that matches one native SPI netlist."""
    descriptions: tuple[tuple[str, str, ConnectorPinRole], ...] = (
        ("1", "SCK", "signal"),
        ("2", "MOSI", "signal"),
        ("3", "MISO", "signal"),
        ("4", "GND" if has_return_role else "AUX", "return" if has_return_role else "other"),
        ("5", "VCC", "other"),
    )
    nets_by_pin = {
        f"J1.{number}": tuple(
            sorted(net for net, pins in observed.nets.items() if f"J1.{number}" in pins)
        )
        for number, _signal, _role in descriptions
    }
    return ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic SPI connector inventory",
        project_interfaces=("synthetic-spi",),
        inventory_review_basis="Synthetic complete connector inventory",
        interface_catalog_sha256="b" * 64,
        entries=(
            ConnectorCoverageEntry(
                reference="J1",
                status="COVERED",
                interface_id="synthetic-spi",
                basis="Synthetic reviewed SPI pin map",
                interface_pin_map={signal: number for number, signal, _role in descriptions},
                mapped_pins=tuple(
                    ConnectorMappedPinEvidence(
                        interface_pin_number=signal,
                        interface_signal=signal,
                        component_pin=f"J1.{number}",
                        role=role,
                        symbol_function=observed.pin_functions.get(f"J1.{number}"),
                        nets=nets_by_pin[f"J1.{number}"],
                    )
                    for number, signal, role in descriptions
                ),
            ),
        ),
    )
