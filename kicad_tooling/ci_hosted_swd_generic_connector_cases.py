"""Registry for synthetic generic SWD connector native fixture sources."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_support import tooling_checkout_root

SWD_GENERIC_CONNECTOR_SOURCE_HASHES = {
    "control": "f259e2b4095696ea8d7284d8add909a83800a0ac953b56f57829165c0060f0d3",
    "fault": "45e993200c7ba4669083de09c93fbcb5082bdecd540214bdbd7b01da600a1118",
}


def swd_generic_connector_fixture_sources() -> dict[str, Path]:
    """Return the tooling-owned generic SWD connector fault and control schematics."""
    fixture_root = (
        tooling_checkout_root() / "tests/fixtures/design_lint/swd-generic-connector-native"
    )
    return {
        "fault": fixture_root / "fault.kicad_sch",
        "control": fixture_root / "control.kicad_sch",
    }
