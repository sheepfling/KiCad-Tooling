"""Source registry for synthetic generic-connector CAN native fixtures."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_support import tooling_checkout_root

CAN_GENERIC_CONNECTOR_SOURCE_HASHES = {
    "fault": "b70560940aeec2baf120bea51ffbc5bd45ea7bed65b5c285e45f218602dc6112",
    "control": "9bb6e5f00617cc1b6b3f76acc4ac9c0090eb2101fca107bbc9c022bb278aaeaa",
}


def can_generic_connector_fixture_sources() -> dict[str, Path]:
    """Return the tooling-owned generic connector fault and control schematics."""
    fixture_root = (
        tooling_checkout_root() / "tests/fixtures/design_lint/can-generic-connector-native"
    )
    return {
        "fault": fixture_root / "fault.kicad_sch",
        "control": fixture_root / "control.kicad_sch",
    }
