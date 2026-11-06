"""Source registry for synthetic generic-connector SPI native fixtures."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_support import tooling_checkout_root

SPI_GENERIC_CONNECTOR_SOURCE_HASHES = {
    "control": "e11144f442f5d727753a010bc3bb22fb2cfcc2662efa263ea1e291f90f51699a",
    "fault": "9b5eabbcc50ab7e9b19557d438e917f64ffb81ecdf3bdb151ea8087ffa53e538",
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
