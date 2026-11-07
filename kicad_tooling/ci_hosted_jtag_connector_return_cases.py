"""Registry for the synthetic JTAG connector return fault and control sources."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_support import tooling_checkout_root

JTAG_CONNECTOR_RETURN_SOURCE_HASHES = {
    "control": "814bef2ba33b6886936e3c7536c61b09f89d806a62c23c47a18065e7826461c7",
    "fault": "9cb38f8584ab580cb907ba588d576c3f6426fe2310a85d4aa238098e6659afdb",
}


def jtag_connector_return_fixture_sources() -> dict[str, Path]:
    """Return tooling-owned JTAG return fixtures, reusing the explicit-GND control."""
    fixture_root = tooling_checkout_root() / "tests/fixtures/design_lint"
    return {
        "fault": fixture_root / "jtag-connector-return-native/fault.kicad_sch",
        "control": fixture_root / "jtag-generic-connector-native/fault.kicad_sch",
    }
