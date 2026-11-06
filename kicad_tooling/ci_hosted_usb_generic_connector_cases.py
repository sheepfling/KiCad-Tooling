"""Source registry for synthetic generic-connector USB native fixtures."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_support import tooling_checkout_root

USB_GENERIC_CONNECTOR_SOURCE_HASHES = {
    "fault": "cc6a6fd8b860bfef7e3a784ae0c46eea82e96c591796b13a36013383f5c2317b",
    "control": "a4805756125893183c61278af060ba0cdcadf42180096335340431d0eef89a82",
}


def usb_generic_connector_fixture_sources() -> dict[str, Path]:
    """Return the tooling-owned generic connector fault and control schematics."""
    fixture_root = (
        tooling_checkout_root() / "tests/fixtures/design_lint/usb-generic-connector-native"
    )
    return {
        "fault": fixture_root / "fault.kicad_sch",
        "control": fixture_root / "control.kicad_sch",
    }
