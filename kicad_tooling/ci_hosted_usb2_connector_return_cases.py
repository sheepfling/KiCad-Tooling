"""Source registry for synthetic USB 2.0 connector return fixtures."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_support import tooling_checkout_root

USB2_CONNECTOR_RETURN_SOURCE_HASHES = {
    "control": "d68d586f253471ae0c3ad3bef435ca3dbaaed9600340e4417cd57a6fa50249bc",
    "fault": "d3cce01f646798bc8c8ba9dcbb574842ea540886e5d5fb3fd1db7f0ba79bb20c",
}


def usb2_connector_return_fixture_sources() -> dict[str, Path]:
    """Return tooling-owned USB 2.0 two-pin return fault and control schematics."""
    fixture_root = (
        tooling_checkout_root() / "tests/fixtures/design_lint/usb2-connector-return-native"
    )
    return {
        "fault": fixture_root / "fault.kicad_sch",
        "control": fixture_root / "control.kicad_sch",
    }
