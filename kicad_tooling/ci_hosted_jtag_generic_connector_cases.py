"""Registry for synthetic generic JTAG connector native fixture sources."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_support import tooling_checkout_root

JTAG_GENERIC_CONNECTOR_SOURCE_HASHES = {
    "control": "c29d130451022eb095d84fdb709ae7f3253124a23b9d1d3d6bff1378d91681bc",
    "fault": "814bef2ba33b6886936e3c7536c61b09f89d806a62c23c47a18065e7826461c7",
}


def jtag_generic_connector_fixture_sources() -> dict[str, Path]:
    """Return the tooling-owned generic JTAG connector fault/control schematics."""
    fixture_root = (
        tooling_checkout_root() / "tests/fixtures/design_lint/jtag-generic-connector-native"
    )
    return {
        "fault": fixture_root / "fault.kicad_sch",
        "control": fixture_root / "control.kicad_sch",
    }
