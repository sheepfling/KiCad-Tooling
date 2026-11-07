"""Source registry for synthetic USB SuperSpeed connector return fixtures."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_support import tooling_checkout_root

USB_SUPERSPEED_CONNECTOR_RETURN_SOURCE_HASHES = {
    "control": "6789b60e42cd430444e62ef98919b7eab5afd402f82e93f24856afad6e6df6e4",
    "fault": "a6bc8ce5ec66ae7b2b7e9649c26b0ebf20fcda855d9d11f0b6d3e3e3d61cf462",
}


def usb_superspeed_connector_return_fixture_sources() -> dict[str, Path]:
    """Return tooling-owned SuperSpeed two-pin return fault/control schematics."""
    fixture_root = (
        tooling_checkout_root()
        / "tests/fixtures/design_lint/usb-superspeed-connector-return-native"
    )
    return {
        "fault": fixture_root / "fault.kicad_sch",
        "control": fixture_root / "control.kicad_sch",
    }
