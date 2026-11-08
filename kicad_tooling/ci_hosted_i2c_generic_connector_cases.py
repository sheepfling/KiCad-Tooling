"""Source registry for synthetic generic-connector I2C native fixtures."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_support import tooling_checkout_root

I2C_GENERIC_CONNECTOR_SOURCE_HASHES = {
    "control": "096da82167af4feb73c8e69d2d758c55b5f204214b85f367e3ed69e91a7f8e2d",
    "fault": "0d8292071410762c81dd447e48e6456d3bf5feb3701c00d2afd74cf91c45f587",
}


def i2c_generic_connector_fixture_sources() -> dict[str, Path]:
    """Return the tooling-owned generic connector fault and control schematics."""
    fixture_root = (
        tooling_checkout_root() / "tests/fixtures/design_lint/i2c-generic-connector-native"
    )
    return {
        "fault": fixture_root / "fault.kicad_sch",
        "control": fixture_root / "control.kicad_sch",
    }
