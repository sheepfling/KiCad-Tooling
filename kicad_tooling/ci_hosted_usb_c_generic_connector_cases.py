"""Source registry for synthetic USB-C generic connector fixtures."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_support import tooling_checkout_root

USB_C_GENERIC_CONNECTOR_SOURCE_HASHES = {
    "control": "b396c89fce7f50cc7d895e616499a602ef6928c9b826e1cc801d8b53ab8fe4b4",
    "fault": "931f30569224f49daf1737eec02dec5d4060cf1497c1db4ab7f28d49d721c017",
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
