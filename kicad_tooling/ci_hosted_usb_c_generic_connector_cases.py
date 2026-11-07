"""Source registry for synthetic USB-C generic connector fixtures."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_support import tooling_checkout_root

USB_C_GENERIC_CONNECTOR_SOURCE_HASHES = {
    "control": "b396c89fce7f50cc7d895e616499a602ef6928c9b826e1cc801d8b53ab8fe4b4",
    "fault": "4f4780115f91f5ccd4e4c196a6799c93d00e354538112636d83953ce1bab4830",
}


def usb_c_generic_connector_fixture_sources() -> dict[str, Path]:
    """Return tooling-owned USB-C controller and generic connector schematics."""
    fixture_root = (
        tooling_checkout_root() / "tests/fixtures/design_lint/usb-c-generic-connector-native"
    )
    return {
        "fault": fixture_root / "fault.kicad_sch",
        "control": fixture_root / "control.kicad_sch",
    }
