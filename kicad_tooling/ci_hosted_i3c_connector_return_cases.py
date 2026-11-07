"""Source registry for the synthetic two-pin I3C return-review fixture."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_support import tooling_checkout_root

I3C_CONNECTOR_RETURN_SOURCE_HASHES = {
    "control": "566f016ba98324898170f121f47538f687de27f6478bb04eb40145a7ce02bffa",
    "fault": "a59d297559ebe4bd24ad413e50b82a37baf46667802f22bd46e70dc79c51f5d3",
}


def i3c_connector_return_fixture_sources() -> dict[str, Path]:
    """Return the tooling-owned I3C missing-return fault and named control."""
    fixture_root = (
        tooling_checkout_root() / "tests/fixtures/design_lint/i3c-connector-return-native"
    )
    return {
        "fault": fixture_root / "fault.kicad_sch",
        "control": fixture_root / "control.kicad_sch",
    }
