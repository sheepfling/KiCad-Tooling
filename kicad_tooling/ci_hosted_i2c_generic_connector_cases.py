"""Source registry for synthetic generic-connector I2C native fixtures."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_support import tooling_checkout_root

I2C_GENERIC_CONNECTOR_SOURCE_HASHES = {
    "control": "506e1b9da8c2479d6c97155247a0bbd7d0b61af062b078c4cb904a3cb1e19459",
    "fault": "c05bc388870ce536d9607ef244e1ae1f91614585682c35d273afd47a4ad39e46",
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
