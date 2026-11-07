"""Registry for the synthetic SWD connector return fault and control sources."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_support import tooling_checkout_root

SWD_CONNECTOR_RETURN_SOURCE_HASHES = {
    "control": "45e993200c7ba4669083de09c93fbcb5082bdecd540214bdbd7b01da600a1118",
    "fault": "5962aae08d6eef3581371b2410a45ec68f33158c303fe114287a629ba3965485",
}


def swd_connector_return_fixture_sources() -> dict[str, Path]:
    """Return the tooling-owned SWD connector return fault and control schematics."""
    fixture_root = tooling_checkout_root() / "tests/fixtures/design_lint"
    return {
        "fault": fixture_root / "swd-connector-return-native/fault.kicad_sch",
        "control": fixture_root / "swd-generic-connector-native/fault.kicad_sch",
    }
