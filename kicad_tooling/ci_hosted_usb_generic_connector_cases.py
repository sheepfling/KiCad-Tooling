"""Source registry for synthetic generic-connector USB native fixtures."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_support import tooling_checkout_root

USB_GENERIC_CONNECTOR_SOURCE_HASHES = {
    "fault": "26940f23b66b4660365bd4a3c4e0cd821a29dcf8739c61d2f9277c262e1ffcc5",
    "control": "a4805756125893183c61278af060ba0cdcadf42180096335340431d0eef89a82",
    "superspeed_fault": "b8d9f784e7aee88355510f62d402e2a706823085ab3a98822ae861d20b6a1b21",
    "superspeed_control": "9997264ed1266c61e3012553fea8e25d3b50957548d35d5af706aea1e3cba1f1",
}


def usb_generic_connector_fixture_sources() -> dict[str, Path]:
    """Return the tooling-owned generic connector fault and control schematics."""
    fixture_root = (
        tooling_checkout_root() / "tests/fixtures/design_lint/usb-generic-connector-native"
    )
    return {
        "fault": fixture_root / "fault.kicad_sch",
        "control": fixture_root / "control.kicad_sch",
        "superspeed_fault": fixture_root / "superspeed-fault.kicad_sch",
        "superspeed_control": fixture_root / "superspeed-control.kicad_sch",
    }
