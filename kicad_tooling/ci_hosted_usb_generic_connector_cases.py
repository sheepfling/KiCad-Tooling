"""Source registry for synthetic generic-connector USB native fixtures."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_support import tooling_checkout_root

USB_GENERIC_CONNECTOR_SOURCE_HASHES = {
    "fault": "26940f23b66b4660365bd4a3c4e0cd821a29dcf8739c61d2f9277c262e1ffcc5",
    "control": "a4805756125893183c61278af060ba0cdcadf42180096335340431d0eef89a82",
    "superspeed_fault": "d630e21b270a371aa9674c7021f04b1dde1a449c481ec4216811b4d447a57f57",
    "superspeed_control": "aa5c774319c88e32162462a0a32d8859a47a475b2bc75d1ede84f21d08087522",
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
