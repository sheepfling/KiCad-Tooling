"""Source registry for the synthetic two-pin I2C return review fixture."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_support import tooling_checkout_root

I2C_CONNECTOR_RETURN_SOURCE_HASHES = {
    "control": "2655b1be35e8f593c3a645084d91f622a62745b92ef968d8b8e1964074a940b3",
    "fault": "16f09bf2a07fc32a529c7e107814cb14cea8e49a8cc2532dbda013a2a0df8909",
}


def i2c_connector_return_fixture_sources() -> dict[str, Path]:
    """Return the tooling-owned I2C missing-return fault and named control."""
    fixture_root = (
        tooling_checkout_root() / "tests/fixtures/design_lint/i2c-connector-return-native"
    )
    return {
        "fault": fixture_root / "fault.kicad_sch",
        "control": fixture_root / "control.kicad_sch",
    }
